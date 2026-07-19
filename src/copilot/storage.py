import json
import pathlib
import sqlite3
from datetime import datetime, timezone

DB_PATH = pathlib.Path("data/copilot.db")

CREATE_SQL = """CREATE TABLE IF NOT EXISTS postings (
source TEXT, source_id TEXT, company TEXT, title TEXT, url TEXT, locations TEXT, season TEXT, sponsorship TEXT, active INTEGER, is_visible INTEGER, date_posted INTEGER, first_seen TEXT, PRIMARY KEY (source, source_id))"""

INSERT_SQL = """INSERT INTO postings (
    source, source_id, company, title, url, locations,
    season, sponsorship, active, is_visible, date_posted, first_seen
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.execute(CREATE_SQL)
    connection.row_factory = sqlite3.Row  # so we can access columns by name
    return connection

def ingest(conn: sqlite3.Connection, source_name: str, postings: list[dict]) -> list[dict]:
    """Insert postings not already in the db; return only the newly inserted ones."""
    rows = conn.execute("SELECT source, source_id FROM postings").fetchall()
    # Build plain tuples explicitly: with row_factory = sqlite3.Row, `rows`
    # holds Row objects, and a Row never equals a tuple — set(rows) would
    # make every membership test below silently miss.
    known = {(row["source"], row["source_id"]) for row in rows}

    new = []
    first_seen = datetime.now(timezone.utc).isoformat()  # one timestamp for the whole batch
    for posting in postings:
        # our namespace is the source_name parameter, NOT posting["source"]
        identity = (source_name, posting["id"])
        # (the `continue` keyword jumps straight to the next loop iteration)
        if identity in known:
            continue
        conn.execute(INSERT_SQL, (
            # json.dumps(...) for locations; the first_seen variable for the last slot.
            source_name, posting["id"], posting["company_name"], posting["title"], posting["url"], json.dumps(posting["locations"]),
            posting["season"], posting["sponsorship"], int(posting["active"]), int(posting["is_visible"]), posting["date_posted"], first_seen
        ))
        new.append(posting)

    conn.commit()
    return new


if __name__ == "__main__":
    conn = get_connection()
    print(conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())