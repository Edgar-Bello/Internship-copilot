import json
import pathlib
import tomllib

PROFILE_PATH = pathlib.Path("profile.toml")

SELECT_SUMMER_SQL = """SELECT p.*, s.score, s.rationale, s.emphasize
FROM postings p
LEFT JOIN scores s ON s.source = p.source AND s.source_id = p.source_id
WHERE p.season = 'Summer' AND p.active = 1 AND p.is_visible = 1
ORDER BY s.score DESC, p.date_posted DESC"""


def load_profile() -> dict:
    with open(PROFILE_PATH, "rb") as f:
        return tomllib.load(f)
    
def matching_postings(conn) -> list:
    """Return postings matching the keywords in profile.toml."""
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
    rows = matching_postings(conn)
    for row in rows:
        first_location = json.loads(row["locations"])[0]
        print(f"{row['source_id'][:8]} - {row['status']}")
        print(f"{row['company']} - {row['title']} - {first_location}")
    print(f"{len(rows)} matching Summer postings")