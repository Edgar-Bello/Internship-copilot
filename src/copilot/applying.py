"""Open a posting in a real browser so you can apply, with your notes in front of you.

HARD LIMITS, by design and not negotiable:
  - never submits a form
  - never logs in, never creates an account, never types a password
  - never touches a CAPTCHA or bot check; if one appears, you take over

Slice 1 opens the page and stops. Field pre-fill comes next, and even then the
last click is always yours.
"""
import json
import pathlib
import tomllib

from playwright.sync_api import Error, sync_playwright

from copilot.draft import DRAFTS_DIR, _slug

SELECT_ONE_SQL = """SELECT p.*, s.score, s.red_flags
FROM postings p
LEFT JOIN scores s ON s.source = p.source AND s.source_id = p.source_id
WHERE p.source_id LIKE ?"""

IDENTITY_PATH = pathlib.Path("identity.toml")

# Never type an answer to these, whatever else matches. Two kinds live here:
# legal declarations that must be YOUR statement, and protected characteristics
# that are nobody's business but yours. A wrong guess here is a false statement
# on an application, so the cost of being careful is one manual field.
NEVER_FILL = (
    "authorization", "authorized", "sponsorship", "sponsor", "visa", "citizen",
    "export control", "clearance", "felony", "convicted",
    "gender", "ethnicity", "hispanic", "latino", "race", "veteran", "disability",
    "will you", "are you willing", "do you agree", "certify", "acknowledge",
    "how did you hear", "salary", "compensation expectation",
)

# Label text -> where the answer lives in identity.toml. Matched as a substring
# of the form's visible label, because Greenhouse question ids are per-posting
# (question_12114509007 is LinkedIn at Anduril and something else everywhere).
# Order matters: "first name" must be tested before the looser "name".
FILL_RULES = (
    ("first name", ("personal", "first_name")),
    ("last name", ("personal", "last_name")),
    ("email", ("personal", "email")),
    ("phone", ("personal", "phone")),
    ("linkedin", ("links", "linkedin")),
    ("github", ("links", "github")),
    ("website", ("links", "website")),
    ("personal site", ("links", "website")),
    ("school", ("education", "school")),
    ("university", ("education", "school")),
    ("degree", ("education", "degree")),
    ("discipline", ("education", "major")),
    ("major", ("education", "major")),
    ("end date month", ("education", "graduation_month")),
    ("end date year", ("education", "graduation_year")),
)


def load_identity() -> dict:
    with open(IDENTITY_PATH, "rb") as f:
        return tomllib.load(f)


def _value_for(label: str, identity: dict) -> str | None:
    """The value this label asks for, or None if we have no business answering it."""
    lowered = label.lower()
    if any(banned in lowered for banned in NEVER_FILL):
        return None
    for needle, (section, key) in FILL_RULES:
        if needle in lowered:
            return identity.get(section, {}).get(key) or None
    return None


def prefill(page, identity: dict) -> tuple[list[str], list[str]]:
    """Type what we can into labelled text inputs. Returns (filled, left alone)."""
    filled, skipped = [], []
    for label in page.locator("label[for]").all():
        target_id = label.get_attribute("for") or ""
        text = (label.inner_text() or "").strip().replace("\n", " ")
        if not target_id or not text:
            continue
        field = page.locator(f"#{target_id}")
        # Only plain text-ish inputs: comboboxes, file pickers and radios all
        # need a human eye, and a wrong click is worse than an empty field.
        if field.count() != 1 or (field.get_attribute("type") or "") not in {
            "text", "email", "tel", "url", "number",
        }:
            continue
        value = _value_for(text, identity)
        if value is None:
            skipped.append(text[:60])
            continue
        try:
            field.fill(value)
            filled.append(f"{text[:40]} = {value}")
        except Error:
            skipped.append(f"{text[:60]} (could not type)")
    return filled, skipped


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

        if IDENTITY_PATH.exists():
            page.wait_for_timeout(1500)  # let the form's JS finish rendering
            filled, skipped = prefill(page, load_identity())
            print(f"\npre-filled {len(filled)} field(s):")
            for item in filled:
                print(f"  + {item}")
            if skipped:
                print(f"left for you ({len(skipped)}) - declarations, demographics, and anything ambiguous:")
                for item in skipped:
                    print(f"  - {item}")
        else:
            print(f"\nno {IDENTITY_PATH} yet - copy identity.example.toml to fill fields automatically")

        print("\nNothing has been submitted. Check every field, answer the rest,")
        print("attach your resume, and click submit yourself.")
        input("Press Enter here when you're done to close the browser... ")
        browser.close()
