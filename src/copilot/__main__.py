"""Entry point for the co-pilot.

Usage:
  .venv\\Scripts\\python.exe -m copilot           fetch + store, show new Summer postings
  .venv\\Scripts\\python.exe -m copilot report    show stored postings matching profile.toml
"""
import sys

from copilot.report import report
from copilot.sources import SOURCE_NAME, fetch_listings, summer_postings
from copilot.storage import ALLOWED_STATUSES, get_connection, ingest, set_status

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        report(get_connection())
    elif len(sys.argv) > 1 and sys.argv[1] == "mark":
        if len(sys.argv) < 4:
            print("usage: python -m copilot mark <id-prefix> <status>")
            sys.exit(1)
        prefix, status = sys.argv[2], sys.argv[3]
        if status not in ALLOWED_STATUSES:
            print(f"unknown status {status!r} - allowed: {', '.join(ALLOWED_STATUSES)}")
            sys.exit(1)
        changed = set_status(get_connection(), prefix, status)
        if changed == 0:
            print(f"no posting id starts with {prefix!r}")
        elif changed == 1:
            print(f"marked {prefix}* as {status}")
        else:
            print(f"{changed} postings match {prefix!r} - nothing changed, use a longer prefix")
    else:
        listings = fetch_listings()
        conn = get_connection()
        new = ingest(conn, SOURCE_NAME, listings)  # store facts: every season goes in
        new_summer = summer_postings(new)          # opinions at read time: show Summer only
        print(f"{len(new)} new postings stored ({len(new_summer)} Summer):")
        for post in new_summer:
            print(f"{post['company_name']} - {post['title']} - {post['locations'][0]}")