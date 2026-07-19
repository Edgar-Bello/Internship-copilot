import json
import pathlib
import tomllib

PROFILE_PATH = pathlib.Path("profile.toml")

SELECT_SUMMER_SQL = """SELECT * FROM postings
WHERE season = 'Summer' AND active = 1 AND is_visible = 1
ORDER BY date_posted DESC"""


def load_profile() -> dict:
    with open(PROFILE_PATH, "rb") as f:
        return tomllib.load(f)

def report(conn) -> None:
    search = load_profile()["search"]
    # Normalize once here so matching is case-insensitive no matter how
    # profile.toml is typed.
    keywords = [kw.lower() for kw in search["keywords"]]
    excludes = [ex.lower() for ex in search["exclude_keywords"]]

    rows = conn.execute(SELECT_SUMMER_SQL).fetchall()
    shown = 0
    for row in rows:
        title = row["title"].lower()
        if not any(kw in title for kw in keywords):
            continue  # no keyword hit -> not interesting
        if any(ex in title for ex in excludes):
            continue  # exclude wins even when a keyword hit
        first_location = json.loads(row["locations"])[0]
        print(f"{row['company']} - {row['title']} - {first_location}")
        shown += 1
    print(f"{shown} matching Summer postings (db has {len(rows)} Summer total)")
