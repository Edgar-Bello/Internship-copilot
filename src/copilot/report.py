import json
import pathlib
import tomllib

from copilot.descriptions import ats_key

PROFILE_PATH = pathlib.Path("profile.toml")

SELECT_SUMMER_SQL = """SELECT p.*, s.score, s.rationale, s.emphasize
FROM postings p
LEFT JOIN scores s ON s.source = p.source AND s.source_id = p.source_id
WHERE p.season = 'Summer' AND p.active = 1 AND p.is_visible = 1
ORDER BY s.score DESC, p.date_posted DESC"""


def load_profile() -> dict:
    with open(PROFILE_PATH, "rb") as f:
        return tomllib.load(f)
    
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


def matching_with_duplicates(conn) -> tuple[list, int]:
    """Matching postings plus how many duplicate listings were folded away."""
    return dedupe_by_ats(_matching_raw(conn))


def matching_postings(conn) -> list:
    """Postings matching profile.toml, one row per real job."""
    return matching_with_duplicates(conn)[0]


def _matching_raw(conn) -> list:
    """Every row matching the profile, duplicates included."""
    search = load_profile()["search"]
    keywords = [kw.lower() for kw in search["keywords"]]
    excludes = [ex.lower() for ex in search["exclude_keywords"]]

    rows = conn.execute(SELECT_SUMMER_SQL).fetchall()
    result = []
    for row in rows:
        title = row["title"].lower()
        if not any(kw in title for kw in keywords):
            continue  # no keyword hit -> not interesting
        if any(ex in title for ex in excludes):
            continue  # exclude wins even when a keyword hit
        if row["status"] == "rejected":
            continue
        result.append(row)
    return result

def report(conn) -> None:
    rows, collapsed = matching_with_duplicates(conn)
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