"""Open a posting in a real browser so you can apply, with your notes in front of you.

HARD LIMITS, by design and not negotiable:
  - never submits a form
  - never logs in, never creates an account, never types a password
  - never touches a CAPTCHA or bot check; if one appears, you take over

Slice 1 opens the page and stops. Field pre-fill comes next, and even then the
last click is always yours.
"""
import json

from playwright.sync_api import Error, sync_playwright

from copilot.draft import DRAFTS_DIR, _slug

SELECT_ONE_SQL = """SELECT p.*, s.score, s.red_flags
FROM postings p
LEFT JOIN scores s ON s.source = p.source AND s.source_id = p.source_id
WHERE p.source_id LIKE ?"""


def _briefing(posting) -> None:
    """Everything worth knowing before the page even loads."""
    print(f"\n{posting['company']} - {posting['title']}")
    print(f"  {posting['url']}")
    print(f"  fit score: {posting['score'] if posting['score'] is not None else '-'}"
          f" | status: {posting['status']} | sponsorship: {posting['sponsorship']}")

    if posting["listing_state"] == "gone":
        print("  WARNING: the employer's board no longer listed this job when we checked.")

    flags = json.loads(posting["red_flags"]) if posting["red_flags"] else []
    if flags:
        print("  check before you send:")
        for flag in flags:
            print(f"    - {flag}")

    draft_path = DRAFTS_DIR / f"{_slug(posting['company'])}-{posting['source_id'][:8]}.md"
    if draft_path.exists():
        print(f"  your draft: {draft_path}")
    else:
        print(f"  no draft yet - run: python -m copilot draft {posting['source_id'][:8]}")


def apply(conn, id_prefix: str) -> None:
    rows = conn.execute(SELECT_ONE_SQL, (f"{id_prefix}%",)).fetchall()
    if not rows:
        print(f"no posting id starts with {id_prefix!r}")
        return
    if len(rows) > 1:
        print(f"{len(rows)} postings match {id_prefix!r} - use a longer prefix")
        return

    posting = rows[0]
    _briefing(posting)

    with sync_playwright() as p:
        # headless=False on purpose: this is your browser session, not a scraper.
        try:
            browser = p.chromium.launch(headless=False)
        except Error as exc:
            print(f"\ncould not open a browser window: {exc.message.splitlines()[0]}")
            print("A visible browser needs a desktop session - run this from your own")
            print("terminal, not a service or remote shell. Open the link above manually:")
            print(f"  {posting['url']}")
            return
        page = browser.new_page()
        page.goto(posting["url"], wait_until="domcontentloaded")
        print(f"\nopened: {page.title()[:80]}")
        print("The browser is yours. Review, fill, and submit it yourself.")
        input("Press Enter here when you're done to close the browser... ")
        browser.close()
