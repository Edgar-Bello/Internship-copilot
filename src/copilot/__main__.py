"""Entry point for the co-pilot.

Usage:
  .venv\\Scripts\\python.exe -m copilot                          fetch + store, show new Summer postings
  .venv\\Scripts\\python.exe -m copilot report                   show stored postings matching profile.toml
  .venv\\Scripts\\python.exe -m copilot mark <id-prefix> <status>  set a posting's status
  .venv\\Scripts\\python.exe -m copilot check [--recheck]        ask each ATS whether the job is still listed
  .venv\\Scripts\\python.exe -m copilot describe <id-prefix> [--file F]  store a description you pasted yourself
  .venv\\Scripts\\python.exe -m copilot score [--force]          score matching postings (--force rescores all)
  .venv\\Scripts\\python.exe -m copilot draft <id-prefix> [--force]  write a cover letter draft to drafts/
  .venv\\Scripts\\python.exe -m copilot apply <id-prefix>        open the posting in a browser (never submits)
"""
import pathlib
import sys

from copilot.applying import apply
from copilot.checking import check_listings
from copilot.draft import draft
from copilot.report import report
from copilot.scoring import score_matching
from copilot.sources import SOURCE_NAME, fetch_listings, summer_postings
from copilot.storage import (
    ALLOWED_STATUSES,
    get_connection,
    ingest,
    set_description,
    set_status,
)

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
    elif len(sys.argv) > 1 and sys.argv[1] == "check":
        check_listings(get_connection(), recheck="--recheck" in sys.argv)
    elif len(sys.argv) > 1 and sys.argv[1] == "describe":
        if len(sys.argv) < 3:
            print("usage: python -m copilot describe <id-prefix> [--file PATH]")
            print("  without --file, paste the text then press Ctrl+Z and Enter")
            sys.exit(1)
        if "--file" in sys.argv:
            source = pathlib.Path(sys.argv[sys.argv.index("--file") + 1])
            if not source.is_file():
                print(f"no such file: {source}")
                sys.exit(1)
            text = source.read_text(encoding="utf-8")
        else:
            print("Paste the job description, then Ctrl+Z and Enter:")
            text = sys.stdin.read()
        text = text.strip()
        if not text:
            print("nothing to store - no text given")
            sys.exit(1)
        changed = set_description(get_connection(), sys.argv[2], text)
        if changed == 1:
            print(f"stored {len(text)} chars; score and draft will use it from now on")
        elif changed == 0:
            print(f"no posting id starts with {sys.argv[2]!r}")
        else:
            print(f"{changed} postings match {sys.argv[2]!r} - nothing stored, use a longer prefix")
    elif len(sys.argv) > 1 and sys.argv[1] == "score":
        score_matching(get_connection(), force="--force" in sys.argv)
    elif len(sys.argv) > 1 and sys.argv[1] == "draft":
        if len(sys.argv) < 3:
            print("usage: python -m copilot draft <id-prefix> [--force]")
            sys.exit(1)
        draft(get_connection(), sys.argv[2], force="--force" in sys.argv)
    elif len(sys.argv) > 1 and sys.argv[1] == "apply":
        if len(sys.argv) < 3:
            print("usage: python -m copilot apply <id-prefix>")
            sys.exit(1)
        apply(get_connection(), sys.argv[2])
    else:
        listings = fetch_listings()
        conn = get_connection()
        new = ingest(conn, SOURCE_NAME, listings)  # store facts: every season goes in
        new_summer = summer_postings(new)          # opinions at read time: show Summer only
        print(f"{len(new)} new postings stored ({len(new_summer)} Summer):")
        for post in new_summer:
            print(f"{post['company_name']} - {post['title']} - {post['locations'][0]}")