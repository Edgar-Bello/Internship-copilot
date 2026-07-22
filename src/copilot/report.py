import json
import pathlib
import tomllib

from copilot.descriptions import ats_key

PROFILE_PATH = pathlib.Path("profile.toml")

SELECT_SUMMER_SQL = """SELECT p.*, s.score, s.rationale, s.emphasize, s.red_flags
FROM postings p
LEFT JOIN scores s ON s.source = p.source AND s.source_id = p.source_id
WHERE p.season = 'Summer' AND p.active = 1 AND p.is_visible = 1
ORDER BY s.score DESC, p.date_posted DESC"""


def load_profile() -> dict:
    with open(PROFILE_PATH, "rb") as f:
        return tomllib.load(f)
    
# Off the to-do list: one is your decision, one is theirs.
HIDDEN_STATUSES = ("rejected", "closed")


def _is_dead(row, include_closed: bool) -> bool:
    """Postings not worth showing: closed by you, rejected, or delisted by the employer."""
    if include_closed:
        return False
    return row["status"] in HIDDEN_STATUSES or row["listing_state"] == "gone"


def _richer(candidate, incumbent) -> bool:
    """Which of two rows for the same job is worth keeping: the one we know more about."""
    def rank(row):
        return (row["description"] is not None, row["score"] is not None)
    return rank(candidate) > rank(incumbent)


def dedupe_by_ats(rows) -> tuple[list, int]:
    """Collapse rows that are provably the same job at the ATS. Returns (kept, collapsed).

    Only exact ATS identity merges anything. Rows whose identity we cannot read
    are always kept - "looks similar" has never been good enough here, because a
    wrong merge silently costs an application.
    """
    kept: dict[str, object] = {}
    collapsed = 0
    for position, row in enumerate(rows):
        key = ats_key(row["url"]) or f"unverifiable:{position}"
        if key not in kept:
            kept[key] = row
            continue
        collapsed += 1
        if _richer(row, kept[key]):
            kept[key] = row
    return list(kept.values()), collapsed


def matching_with_duplicates(conn, include_closed: bool = False) -> tuple[list, int, int]:
    """Matching postings, duplicates folded, plus (collapsed, hidden) counts."""
    raw, hidden = _matching_raw(conn, include_closed)
    kept, collapsed = dedupe_by_ats(raw)
    return kept, collapsed, hidden


def matching_postings(conn, include_closed: bool = False) -> list:
    """Postings matching profile.toml, one row per real job, dead ones dropped."""
    return matching_with_duplicates(conn, include_closed)[0]


def _matching_raw(conn, include_closed: bool = False) -> tuple[list, int]:
    """Every row matching the profile, duplicates included, plus how many were dead."""
    search = load_profile()["search"]
    keywords = [kw.lower() for kw in search["keywords"]]
    excludes = [ex.lower() for ex in search["exclude_keywords"]]

    rows = conn.execute(SELECT_SUMMER_SQL).fetchall()
    result, hidden = [], 0
    for row in rows:
        title = row["title"].lower()
        if not any(kw in title for kw in keywords):
            continue  # no keyword hit -> not interesting
        if any(ex in title for ex in excludes):
            continue  # exclude wins even when a keyword hit
        if _is_dead(row, include_closed):
            hidden += 1
            continue
        result.append(row)
    return result, hidden

def score_report(conn) -> None:
    """The ranked shortlist with the reasoning attached: what is left to apply to.

    Same filtering as `report`, minus the ones already applied to - this answers
    "what should I do next", not "what happened to everything".
    """
    rows = [row for row in matching_postings(conn) if row["status"] != "applied"]
    for row in rows:
        score = row["score"] if row["score"] is not None else "-"
        print(f"\n[{score}] {row['source_id'][:8]}  {row['company']} - {row['title']}")
        print(f"      {row['status']} | {json.loads(row['locations'])[0]} | {row['url']}")
        for flag in json.loads(row["red_flags"]) if row["red_flags"] else []:
            print(f"      ! {flag}")
        if row["rationale"]:
            print(f"      {row['rationale']}")
    scored = sum(1 for row in rows if row["score"] is not None)
    print(f"\n{len(rows)} still to apply to ({scored} scored)")


def report(conn, include_closed: bool = False) -> None:
    rows, collapsed, hidden = matching_with_duplicates(conn, include_closed)
    for row in rows:
        first_location = json.loads(row["locations"])[0]
        score = row["score"] if row["score"] is not None else "-"
        # "GONE" only when we actually asked and were told no; never-checked stays quiet.
        listing = " GONE" if row["listing_state"] == "gone" else ""
        print(f"{row['source_id'][:8]} - {row['status']}{listing}")
        print(f"{row['company']} - {row['title']} - {first_location} - score: {score}")
    print(f"{len(rows)} matching Summer postings")
    if collapsed:
        print(f"({collapsed} duplicate listing(s) hidden - same job at the ATS under another URL)")
    if hidden:
        # Say so out loud: quietly dropping rows is how a to-do list starts lying.
        print(f"({hidden} hidden as closed, rejected, or delisted - see them with --all)")