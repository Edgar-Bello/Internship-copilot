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
import re
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
# These stay manual permanently. They are yes/no legal declarations whose
# phrasing inverts between employers - "Are you authorized to work?" and "Will
# you require sponsorship?" want opposite answers to the same fact - so a stored
# "Yes" cannot be applied safely without reading the question. You read it.
NEVER_FILL = (
    "authorization", "authorized", "sponsorship", "sponsor", "visa", "citizen",
    "export control", "clearance", "felony", "convicted",
    "will you", "are you willing", "do you agree", "certify", "acknowledge",
    "how did you hear", "salary", "compensation expectation",
)

# Voluntary self-identification. Unlike the above these are enumerated choices,
# not invertible yes/no questions, so an exact option match is unambiguous.
# Only filled when you put a value in identity.toml, and only when that exact
# option exists on the form - otherwise the field is left for you.
SELF_ID_RULES = (
    ("gender", ("self_identification", "gender")),
    ("hispanic", ("self_identification", "hispanic_latino")),
    ("latino", ("self_identification", "hispanic_latino")),
    ("veteran", ("self_identification", "veteran_status")),
    ("disability", ("self_identification", "disability_status")),
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
    ("country", ("personal", "country")),
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
    for needle, (section, key) in FILL_RULES + SELF_ID_RULES:
        if needle in lowered:
            return identity.get(section, {}).get(key) or None
    return None


def _normalize(text: str) -> str:
    """Compare option text the way a human reads it, not byte for byte.

    Greenhouse lists 'The University of Texas Rio Grande Valley'; a resume says
    'University of Texas Rio Grande Valley'. Same school. Punctuation, casing
    and a leading 'the' are noise - the words are what identify it.
    """
    text = re.sub(r"^the\s+", "", text.strip().casefold())
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _close_menu(page, field) -> None:
    """Shut the dropdown before touching anything else.

    An open react-select menu paints its options over the rest of the form and
    swallows clicks meant for the next field - Playwright then retries for 30s,
    scrolling the page up and down, which is what it looks like from outside.
    """
    field.press("Escape")
    try:
        page.locator(".select__option").first.wait_for(state="hidden", timeout=2000)
    except Error:
        page.keyboard.press("Escape")


def _choose_option(page, field, value: str) -> tuple[bool, str]:
    """Pick an option in a react-select combobox. Exact text match or nothing.

    Returns (chose_one, why_not). fill() cannot be used here: it sets the value
    programmatically and react-select only reacts to real keystrokes, so the
    menu never opens and the field silently stays empty - which is exactly how
    school/degree/discipline submitted blank. press_sequentially types for real.

    A near-match is never accepted: 'University of Texas at Austin' is not
    'University of Texas Rio Grande Valley'.
    """
    field.scroll_into_view_if_needed()
    field.click()
    field.press_sequentially(value, delay=20)
    page.wait_for_timeout(800)  # let the menu render and filter

    options = page.locator('[role="option"]:visible, .select__option:visible')
    count = options.count()
    seen = [(options.nth(i).inner_text() or "").strip() for i in range(min(count, 40))]
    wanted = _normalize(value)

    matches = [i for i, text in enumerate(seen) if _normalize(text) == wanted]
    if not matches and len(seen) == 1 and wanted in _normalize(seen[0]):
        # Typing the full value narrowed the list to exactly one entry that
        # contains it: 'X' vs 'The X'. One candidate is not a guess.
        matches = [0]
    if len(matches) == 1:
        options.nth(matches[0]).click()
        chosen = seen[matches[0]]
        _close_menu(page, field)
        return True, chosen

    _close_menu(page, field)
    field.fill("")
    if count == 0:
        return False, "no menu opened"
    if len(matches) > 1:
        return False, f"{len(matches)} options match equally - pick one yourself"
    return False, f"{count} offered, none matched - e.g. {'; '.join(seen[:3])}"


def attach_resume(page, identity: dict) -> str | None:
    """Attach the resume PDF. Never the cover letter: that draft is unreviewed."""
    path = identity.get("files", {}).get("resume_pdf", "")
    if not path:
        return None
    resume = pathlib.Path(path)
    if not resume.is_file():
        return f"resume_pdf in identity.toml points at nothing: {resume}"
    for i in range(page.locator('input[type="file"]').count()):
        field = page.locator('input[type="file"]').nth(i)
        ident = f"{field.get_attribute('id') or ''} {field.get_attribute('name') or ''}".lower()
        if "resume" in ident and "cover" not in ident:
            field.set_input_files(str(resume))
            return f"attached {resume.name}"
    return "no resume upload field found on this form"


def prefill(page, identity: dict) -> tuple[list[str], list[str]]:
    """Type what we can into labelled text inputs. Returns (filled, left alone)."""
    filled, skipped = [], []
    for label in page.locator("label[for]").all():
        target_id = label.get_attribute("for") or ""
        text = (label.inner_text() or "").strip().replace("\n", " ")
        if not target_id or not text:
            continue
        field = page.locator(f"#{target_id}")
        if field.count() != 1 or (field.get_attribute("type") or "") not in {
            "text", "email", "tel", "url", "number",
        }:
            continue
        value = _value_for(text, identity)
        if value is None:
            skipped.append(text[:60])
            continue
        try:
            # A combobox announces itself; typing into one without choosing an
            # option leaves it empty on submit.
            if field.get_attribute("role") == "combobox":
                chose, detail = _choose_option(page, field, value)
                if chose:
                    filled.append(f"{text[:40]} = {detail}")
                else:
                    skipped.append(f"{text[:35]} -> {value!r}: {detail}")
            else:
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
        # Fail fast: the default 30s turns one stuck field into half a minute
        # of the page scrolling itself while Playwright retries.
        page.set_default_timeout(8000)
        page.goto(posting["url"], wait_until="domcontentloaded")
        print(f"\nopened: {page.title()[:80]}")

        if IDENTITY_PATH.exists():
            page.wait_for_timeout(1500)  # let the form's JS finish rendering
            identity = load_identity()
            filled, skipped = prefill(page, identity)
            attachment = attach_resume(page, identity)
            if attachment:
                print(f"\nresume: {attachment}")
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
