import pathlib
import sqlite3

DB_PATH = pathlib.Path("data/copilot.db")

CREATE_SQL = """CREATE TABLE IF NOT EXISTS postings (
source TEXT, source_id TEXT, company TEXT, title TEXT, url TEXT, locations TEXT, season TEXT, sponsorship TEXT, active INTEGER, is_visible INTEGER, date_posted INTEGER, first_seen TEXT, PRIMARY KEY (source, source_id))"""

def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.execute(CREATE_SQL)
    return connection

if __name__ == "__main__":
    conn = get_connection()
    print(conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())