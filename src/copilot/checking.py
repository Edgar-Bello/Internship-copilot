"""Ask each employer's ATS whether it still lists the posting, and cache the text.

The community feed's `active` flag goes stale: jobs disappear from company boards
while the list still advertises them. This is the only place that asks the
employer directly, so scoring and drafting can read a cached answer instead of
re-fetching (and instead of trusting the feed).
"""
from copilot.descriptions import fetch_description, supports
from copilot.report import matching_postings
from copilot.storage import record_listing_check


def check_listings(conn, recheck: bool = False) -> None:
    """Check every matching posting on an ATS we can query.

    recheck=True re-asks postings already checked; otherwise they are skipped,
    so a rerun costs nothing for answers we already have.
    """
    postings = matching_postings(conn)
    checkable = [p for p in postings if supports(p["url"])]
    todo = checkable if recheck else [p for p in checkable if p["checked_at"] is None]
    skipped = len(postings) - len(checkable)
    print(
        f"{len(postings)} matching, {skipped} on sources we cannot query, "
        f"{len(todo)} to check"
    )

    live = gone = 0
    for i, posting in enumerate(todo, start=1):
        description = fetch_description(posting["url"])
        state = "live" if description else "gone"
        if description:
            live += 1
        else:
            gone += 1
        record_listing_check(conn, posting["source"], posting["source_id"], state, description)
        print(f"[{i}/{len(todo)}] {state:<4} {posting['company']} - {posting['title']}")

    print(f"\n{live} still listed, {gone} no longer on the employer's board")
