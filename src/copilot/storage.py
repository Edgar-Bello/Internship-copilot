import json
import pathlib
import sqlite3
from datetime import datetime, timezone

DB_PATH = pathlib.Path("data/copilot.db")

CREATE_SQL = """CREATE TABLE IF NOT EXISTS postings (
source TEXT, source_id TEXT, company TEXT, title TEXT, url TEXT, locations TEXT, 
season TEXT, sponsorship TEXT, active INTEGER, is_visible INTEGER, date_posted INTEGER, 
first_seen TEXT, status TEXT NOT NULL DEFAULT 'new', PRIMARY KEY (source, source_id))"""

INSERT_SQL = """INSERT INTO postings (
    source, source_id, company, title, url, locations,
    season, sponsorship, active, is_visible, date_posted, first_seen
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

CREATE_SCORES_SQL = """CREATE TABLE IF NOT EXISTS scores (
    source TEXT, source_id TEXT, score INTEGER, rationale TEXT, emphasize TEXT, 
    red_flags TEXT, model TEXT, scored_at TEXT, PRIMARY KEY (source, source_id))"""

ALLOWED_STATUSES = ("new", "seen", "interested", "applied", "rejected")

def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row  # before any query, so helpers can use row["name"]
    connection.execute(CREATE_SQL)
    _ensure_status_column(connection)
    connection.execute(CREATE_SCORES_SQL)
    return connection

def _ensure_status_column(connection: sqlite3.Connection) -> None:
    """Migrate databases created before the status column existed. Safe on every startup."""
    columns = connection.execute("PRAGMA table_info(postings)").fetchall()
    if not any(col["name"] == "status" for col in columns):
        connection.execute("ALTER TABLE postings ADD COLUMN status TEXT NOT NULL DEFAULT 'new'")


def set_status(conn, source_id_prefix: str, status: str) -> int:
    """Set status on the single posting matching the id prefix; report how many matched.

    Commits only on an exact single match — an ambiguous prefix must not
    mass-update lookalike postings (the Kudu case), so anything else rolls back.
    """
    cursor = conn.execute(
        "UPDATE postings SET status = ? WHERE source_id LIKE ?",
        (status, f"{source_id_prefix}%"),
    )
    if cursor.rowcount == 1:
        conn.commit()
    else:
        conn.rollback()
    return cursor.rowcount


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

def insert_score(conn, source, source_id, assessment, model):
    """Store one score. Plain INSERT on purpose: a duplicate means the caller's
    skip logic is broken, and the PK must make that loud, not paper over it."""
    conn.execute(
        "INSERT INTO scores (source, source_id, score, rationale, emphasize, red_flags, model, scored_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            source,
            source_id,
            assessment.score,
            assessment.rationale,
            json.dumps(assessment.emphasize),
            json.dumps(assessment.red_flags),
            model,
            datetime.now(timezone.utc).isoformat()
        )
    )
    conn.commit()

if __name__ == "__main__":
    conn = get_connection()
    print([row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()])