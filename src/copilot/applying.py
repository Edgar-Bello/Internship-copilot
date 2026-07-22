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
from urllib.parse import urljoin

from playwright.sync_api import Error, sync_playwright

from copilot.descriptions import application_url
from copilot.draft import DRAFTS_DIR, _slug
from copilot.llm import get_client, match_option

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
    # Not a declaration - a different fact. "When did you graduate from High
    # School" otherwise matches the `school` rule and gets a university typed in.
    "high school",
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
    ("location (city)", ("personal", "location")),
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
    # Apostrophes join a word, they do not split it: "Bachelor's" must reduce to
    # "bachelors", not "bachelor s", or it stops matching "Bachelors".
    text = text.replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _reset_field(page, field) -> None:
    """Empty the box and shut the dropdown, in that order.

    Order matters and getting it backwards is expensive: filling an input
    refocuses it, which reopens react-select's menu. Closing first and clearing
    second leaves the menu open, painted over the rest of the form, swallowing
    the clicks meant for the next two fields. That is why one bad value used to
    take its neighbours down with it.
    """
    try:
        field.fill("")
    except Error:
        pass
    field.press("Escape")
    try:
        page.locator(".select__option").first.wait_for(state="hidden", timeout=2000)
    except Error:
        page.keyboard.press("Escape")
    page.wait_for_timeout(250)  # let the close finish; a closing menu still eats clicks


def _choose_option(page, field, value: str, label: str = "", client=None) -> tuple[bool, str]:
    """Pick an option in a react-select combobox.

    First tries to match the words exactly. If that fails and a model client is
    given, it shows the model the employer's real option list and asks which one
    means the same thing - because "Bachelor of Science" and "Bachelor's Degree"
    are one fact in two vocabularies, and only a human-ish reader sees that.

    The model can only answer with an option that is actually on the list, or
    null. A different school or a different degree level is never accepted: the
    candidate signs this form, so blank always beats plausible.
    """
    matched, detail = _try_exact(page, field, value)
    if matched or client is None:
        if not matched:
            _reset_field(page, field)
        return matched, detail
    _reset_field(page, field)

    # Exact matching failed. Show the model the employer's actual list and let it
    # recognise the same fact under different wording - "Bachelor of Science" is
    # "Bachelor's Degree". It may only answer with an option that exists, or null.
    offered = _list_all_options(page, field)
    if not offered:
        _reset_field(page, field)
        return False, "the menu never opened"
    if len(offered) >= 60:
        # A long alphabetical list arrives truncated, so the model would only
        # ever see the entries starting with A. Report what the form's own
        # search actually said instead - that is the useful fact.
        _reset_field(page, field)
        return False, f"{detail}; searched several ways, pick this one yourself"

    suggestion = match_option(client, label, value, offered)
    if suggestion is None:
        _reset_field(page, field)
        return False, f"nothing here means {value!r}; they offer: {'; '.join(offered[:8])}"

    _reset_field(page, field)
    matched, detail = _try_exact(page, field, suggestion)
    if matched:
        return True, f"{detail}  (matched from {value!r})"
    _reset_field(page, field)
    return False, f"{value!r} looks like {suggestion!r}, but selecting it failed"


def _search_variants(value: str) -> list[str]:
    """Ways to type a value so the form's own filter finds it.

    These filters match literal substrings, so the full string often finds
    nothing: IMC lists a school we spell differently, and typing the whole name
    matches no entry at all. Shorter, distinctive fragments do - "Rio Grande
    Valley" narrows a list of thousands to one. Whatever comes back is still
    judged against the FULL value, so a fragment cannot pick the wrong school.
    """
    words = [w for w in re.findall(r"[A-Za-z0-9]+", value) if w.lower() != "the"]
    variants = [value, " ".join(words)]
    if len(words) >= 3:
        variants.append(" ".join(words[-3:]))
    if len(words) >= 2:
        variants.append(" ".join(words[-2:]))
    return list(dict.fromkeys(v for v in variants if v.strip()))


def _try_exact(page, field, value: str) -> tuple[bool, str]:
    """Type `value` and click an option that means exactly that. No interpretation."""
    wanted = _normalize(value)
    last = "the menu never opened"
    for attempt, query in enumerate(_search_variants(value)):
        if attempt:
            _reset_field(page, field)
        field.scroll_into_view_if_needed()
        field.click()
        # A click swallowed by a neighbour's closing menu leaves this field
        # unfocused, and every keystroke then goes nowhere. Check, don't assume.
        if not field.evaluate("el => el === document.activeElement"):
            page.wait_for_timeout(400)
            field.click()
        field.press_sequentially(query, delay=20)
        page.wait_for_timeout(800)  # let the menu render and filter

        options = page.locator('[role="option"]:visible, .select__option:visible')
        count = options.count()
        seen = [(options.nth(i).inner_text() or "").strip() for i in range(min(count, 40))]

        matches = [i for i, text in enumerate(seen) if _normalize(text) == wanted]
        if not matches and len(seen) == 1 and wanted in _normalize(seen[0]):
            # One remaining entry that contains the whole value: 'X' vs 'The X'.
            matches = [0]
        if len(matches) == 1:
            options.nth(matches[0]).click()
            return True, seen[matches[0]]
        if len(matches) > 1:
            return False, f"{len(matches)} options match equally - pick one yourself"
        last = (f"no option contains {query!r}" if count == 0
                else f"{count} offered, none matched - e.g. {'; '.join(seen[:5])}")
    return False, last


def _list_all_options(page, field) -> list[str]:
    """Every option this field offers, filter cleared."""
    field.scroll_into_view_if_needed()
    field.click()
    field.fill("")
    page.wait_for_timeout(600)
    options = page.locator('[role="option"]:visible, .select__option:visible')
    return [(options.nth(i).inner_text() or "").strip() for i in range(min(options.count(), 150))]


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


def _follow_apply_link(page) -> str | None:
    """Click through from an advert to the form, if there is an obvious way.

    Never touches anything that says submit: the point is to reach the form, and
    the last click on a real application is always the human's.
    """
    for role in ("link", "button"):
        control = page.get_by_role(role, name=re.compile(r"\bapply\b", re.I)).first
        if not control.count():
            continue
        text = (control.inner_text() or "").lower()
        if "submit" in text:
            continue
        if role == "link":
            href = control.get_attribute("href")
            if not href:
                continue
            page.goto(urljoin(page.url, href), wait_until="domcontentloaded")
        else:
            control.click()
        page.wait_for_timeout(2500)
        return page.url
    return None


def looks_like_application_form(page) -> bool:
    """Is this actually a job application, or just a page with an input on it?

    Stoke Space's Greenhouse link redirects to their careers page, whose only
    field is a newsletter box - and an unguarded pre-fill happily typed an email
    address into a mailing list. Every real application asks for a name or a
    resume; a subscribe box asks for neither.
    """
    for selector in ('[id*="first_name" i]', '[name*="first_name" i]',
                     '[id*="last_name" i]', '[name*="last_name" i]',
                     'input[type="file"]'):
        if page.locator(selector).count():
            return True
    return False


def _is_self_id(label: str) -> bool:
    lowered = label.lower()
    return any(needle in lowered for needle, _ in SELF_ID_RULES)


def prefill(page, identity: dict, client=None) -> tuple[list[str], list[str]]:
    """Type what we can into labelled text inputs. Returns (filled, left alone).

    `client` enables model-assisted matching for comboboxes whose wording differs
    from yours. It is never used for self-identification: those lists are short
    and legally meaningful, so if your words are not their words, you choose.
    """
    if not looks_like_application_form(page):
        # Refuse rather than scatter personal data into whatever inputs exist.
        return [], []

    filled, skipped = [], []
    for label in page.locator("label[for]").all():
        target_id = label.get_attribute("for") or ""
        text = (label.inner_text() or "").strip().replace("\n", " ")
        if not target_id or not text:
            continue
        if '"' in target_id:
            continue  # would break the selector below; nothing we can safely fill
        # Attribute form, not "#id": real forms carry ids like
        # question_9170567101[]_66340074101, which is not valid CSS after a hash.
        field = page.locator(f'[id="{target_id}"]')
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
                helper = None if _is_self_id(text) else client
                chose, detail = _choose_option(page, field, value, label=text, client=helper)
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

        # The feed often links the advert, not the form. When the advert's URL
        # still carries the ATS job id, go straight to the form instead.
        target = application_url(posting["url"], posting["company"]) or posting["url"]
        if target != posting["url"]:
            print(f"\nthe link is an advert; the form is at:\n  {target}")
        page.goto(target, wait_until="domcontentloaded")
        print(f"\nopened: {page.title()[:80]}")

        if IDENTITY_PATH.exists():
            page.wait_for_timeout(1500)  # let the form's JS finish rendering
            identity = load_identity()
            client = get_client()
            filled, skipped = prefill(page, identity, client=client)
            if not filled and not skipped:
                # Either an advert page or something that is not an application
                # at all. Look for a way through; fill nothing until we find one.
                print("no application form here - looking for an Apply link...")
                moved = _follow_apply_link(page)
                if moved:
                    print(f"followed to: {moved}")
                    filled, skipped = prefill(page, identity, client=client)
                if not filled and not skipped:
                    print("still no application form on this page. Nothing was typed.")
                    print("The posting may be closed - if so: "
                          f"python -m copilot mark {posting['source_id'][:8]} closed")
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
