"""Run the whole pipeline: fetch everything, store what's new, report new Summer postings.

Usage: .venv\\Scripts\\python.exe -m copilot
"""

from copilot.sources import SOURCE_NAME, fetch_listings, summer_postings
from copilot.storage import get_connection, ingest

if __name__ == "__main__":
    listings = fetch_listings()
    conn = get_connection()
    new = ingest(conn, SOURCE_NAME, listings)  # store facts: every season goes in
    new_summer = summer_postings(new)          # apply opinions at read time: report Summer only
    print(f"{len(new)} new postings stored ({len(new_summer)} Summer):")
    for post in new_summer:
        print(f'{post["company_name"]} - {post["title"]} - {post["locations"][0]}')
