"""Entry point for the co-pilot.

Usage:
  .venv\\Scripts\\python.exe -m copilot           fetch + store, show new Summer postings
  .venv\\Scripts\\python.exe -m copilot report    show stored postings matching profile.toml
"""
import sys

from copilot.report import report
from copilot.sources import SOURCE_NAME, fetch_listings, summer_postings
from copilot.storage import get_connection, ingest

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        report(get_connection())
    else:
        listings = fetch_listings()
        conn = get_connection()
        new = ingest(conn, SOURCE_NAME, listings)  # store facts: every season goes in
        new_summer = summer_postings(new)          # opinions at read time: show Summer only
        print(f"{len(new)} new postings stored ({len(new_summer)} Summer):")
        for post in new_summer:
            print(f"{post['company_name']} - {post['title']} - {post['locations'][0]}")