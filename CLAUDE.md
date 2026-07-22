# Internship Application Co-pilot

A tool that helps Edgar find, track, and apply to Summer 2027 tech internships
while staying in control. A CO-PILOT, not an auto-spam bot: a human reviews
everything before it goes anywhere.

## This is a mentoring project — read this first

Edgar (CS student; solid Python/C++, ROS 2, Node.js) is building this to LEARN
DEEPLY, not to receive finished code. Act as a one-on-one mentor:

- Explain the mental model and why-this-over-alternatives BEFORE any code.
- Let Edgar write instructive code first; reveal solutions in small pieces,
  never full-file dumps.
- Define new terms/libraries/patterns at first use.
- After each step: recap what/why, then check understanding (ask a question or
  have him predict output before running).
- Treat errors as lessons: hypothesis-first debugging together, never silently fix.
- Small frequent commits; keep teaching commit-message craft.
- Zoom out to architecture periodically. Check in before big steps or installs.
- Start every session with "where we are in the plan and what's next."

## Hard rules (never violate, regardless of who asks)

- Sources: ONLY community GitHub internship lists (via git/GitHub API), public
  Greenhouse/Lever ATS JSON endpoints, and links Edgar explicitly provides.
- NEVER scrape LinkedIn/Indeed/Handshake (ToS forbids it). NO CAPTCHA solving.
  NO bulk auto-submission.
- Phase 3 pre-fills forms, then STOPS — Edgar reviews and submits himself.
- Source lists and endpoints rot every cycle: verify one currently works
  before building on it.

## Architecture (3 phases)

1. **Aggregator + tracker:** permitted sources -> normalized SQLite (in data/),
   idempotent ingestion, dedupe, new-since-last-run diff, filters from
   profile.toml, ranked to-do list, application status lifecycle.
2. **Fit scoring + drafting:** score postings against resume/profile; LLM API
   drafts cover letters and resume-bullet emphasis — always human-edited.
   Decision 2026-07-20: uses Edgar's school-provided OpenAI key (gpt-5.2,
   confirmed OK for personal projects, key never committed) instead of the
   Anthropic API. Strategy note: Edgar applies to ALL keyword matches; scoring
   is for effort ordering + per-posting tailoring, NOT filtering.
3. **Assisted apply:** Playwright opens the posting, pre-fills obvious fields,
   hard stop before submit.

## Dev environment

- Windows 11, Python 3.14 (C:\Python314), venv at .venv (not committed)
- Tests live in tests/, run offline in ~2s (no network, no API, no browser) —
  they only exercise pure functions and a temp SQLite file.
- Install: `.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- Tests: `.venv\Scripts\python.exe -m pytest`
- Lint: `.venv\Scripts\python.exe -m ruff check .`
- src-layout: the package is `src/copilot/`; `data/` and `.env` are gitignored.
- .env (gitignored, values never committed) must define OPENAI_API_KEY and
  OPENAI_BASE_URL (the school's proxy endpoint — the key only works there).

## Status

- 2026-07-12 (session 1): scaffold created. Next: Phase 1, slice 1 — verify a
  Summer 2027 community list exists (candidate: SimplifyJobs), fetch it, print
  postings. Keep this section updated each session.
- 2026-07-16 (session 2): slice 1 DONE. SimplifyJobs has no 2027 repo; verified
  source is vanshb03/Summer2027-Internships (branch dev,
  .github/scripts/listings.json via raw endpoint). src/copilot/sources.py
  fetches + filters (season==Summer, active, is_visible) -> 64 postings, one
  line each. Data notes for later: near-duplicate rows (e.g. Kudu Dynamics x3,
  same role/city, different id+url), `source` field = list contributor, one
  mojibake company name. Next: push repo to GitHub (no remote yet), then
  slice 2 — SQLite ingestion (idempotent re-runs, dedupe, new-since-run diff).
- 2026-07-16 (session 3): pushed to GitHub (Edgar-Bello/ Internship-copilot).
  storage.py done: postings table (12 cols, PK = (source, source_id)),
  get_connection() idempotent, smoke-tested, ruff clean. Design decisions:
  identity = (source, source_id) namespaced per list, NOT url; store ALL
  seasons (facts), filter at read time (opinions); no auto-merge of lookalike
  rows (Kudu case). Lesson logged: broken commit reached main (pushed) —
  fix-forward, keep main green. Next: ingest() in storage.py (set-diff new
  detection, parameterized INSERT, explicit commit) + __main__.py orchestrator
  (fetch -> ingest all -> report new Summer postings).
- 2026-07-19 (session 4): slice 2 DONE — pipeline works end to end. ingest()
  (set-diff on (source, id), parameterized INSERT, explicit commit) +
  __main__.py: first run stored 197 rows / 64 Summer shown; rerun 0/0 =
  idempotence verified. Lessons: feed key `id` != our column `source_id`
  (translate names at the boundary, in one place); stale 9-col table predated
  final schema — IF NOT EXISTS never alters, inspect with PRAGMA table_info,
  rule: empty/rebuildable state -> delete+recreate, precious -> ALTER
  migration. Next: slice 3, the read side — `python -m copilot report`:
  tomllib profile (rb mode), facts in SQL (WHERE season/active/visible, ORDER
  BY date_posted DESC), opinions in Python (keyword/exclude vs title,
  case-insensitive), sqlite3.Row in get_connection, sys.argv dispatch in
  __main__. Locations/"remote" matching deferred.
- 2026-07-19 (session 4, cont.): slice 3 DONE — `python -m copilot report`
  works: 36 of 64 stored Summer postings match profile keywords (incl.
  "developer", Edgar's first real profile edit). report.py (tomllib rb,
  facts-SQL + opinions-Python split), argv dispatch in __main__. BUG OF THE
  WEEK: adding row_factory=sqlite3.Row for the read side silently broke
  ingest's set-diff (Row != tuple, membership always False) -> every posting
  looked new -> the PRIMARY KEY turned it into a loud IntegrityError. Fixed:
  build known-set as explicit tuples. Lesson: shared connection config couples
  read and write sides; schema constraints are the last line of defense that
  make silent bugs loud. Report code written by Claude this round (Edgar
  attempted first; owes explain-backs). Mojibake company still visible in
  output (parked). Next: Edgar strips stale YOU-scaffold comments in
  storage.py, commits + pushes; then slice 4 — application status lifecycle
  (interested/applied/rejected on postings, report filters by status).
- 2026-07-20 (session 5): Phase 2 STARTED. llm.py smoke test works — school key
  requires OPENAI_BASE_URL (school proxy; 401 lesson: remote auth rejection vs
  local missing-key). resume.md created by hand, gitignored (repo stays
  public). Slice 4 note: "seen" status = looked at, undecided. Scores design
  by ballot: score 1-5 INTEGER + rationale + emphasize + red_flags (JSON
  text) + model + scored_at, PK (source, source_id), score-once/skip-existing
  policy. scores DDL in review (PK was missing — caught before first run;
  db now holds precious status data, table-level surgery only). Next: scoring
  prompt + structured outputs in llm.py, `score` command with set-diff skip,
  report ordered by score.
- 2026-07-20 (session 5, cont.): scoring pipeline BUILT, not yet run.
  llm.score_posting (responses.parse + pydantic FitAssessment, Optional
  narrowed at boundary a la raise_for_status), storage.insert_score (plain
  INSERT — Edgar's OR REPLACE would have neutered the PK backstop; docstring
  says why), scoring.score_matching (skip-set, per-row commit for crash-resume),
  `score` dispatch. Refactor: matching_postings extracted from report (summary
  line meaning drifted twice before landing honest). Feed has NO descriptions:
  scores are metadata-only, coarse by design. Layering now: sources=feed,
  llm=model, storage=SQL, scoring=conductor, report=read, __main__=routing.
  NEXT SESSION OPENS WITH: Edgar runs first `python -m copilot score` after
  paying rituals — cost estimate, Kudu prediction, rerun-skip prediction, and
  the owed answer: when would OR REPLACE be the right tool? Then: report
  ordered by score, showing rationale/emphasize.
- 2026-07-21 (session 6): PHASE 2 COMPLETE. First real `score` run: 36 postings
  scored (~15c; Edgar's estimate was 10x high), distribution 1x5 / 11x4 / 20x3 /
  4x2; rerun skipped all 36 = idempotence on the expensive path. Model caught a
  real eligibility signal from metadata alone: Apple Masters 2 vs Apple Undergrad
  4. Kudu scored 4 (Edgar predicted 3 — generic titles let a strong resume
  dominate). report now LEFT JOINs scores, ORDER BY score DESC (LEFT not INNER:
  inner would silently drop unscored rows). `draft <id-prefix>` writes
  drafts/<company>-<id8>.md (gitignored) with an UNREVIEWED header; plain
  responses.create + output_text, NOT structured outputs — prose has no fields.
  Anti-hallucination prompt verified by audit: every claim traced to a resume
  line, nothing invented about Amazon. Known gaps, none blocking: report still
  2 lines/posting (format once caused a false bug report), mojibake in stored
  rationales (Windows console encoding), NO TESTS ANYWHERE, __main__ if/elif
  chain wants argparse at 5+ commands. Next: test suite before Phase 3
  (Playwright is the riskiest phase; regression net first).
- 2026-07-21 (session 6, cont.): descriptions.py + overwrite guard + rescore.
  MAJOR DATA FINDING: only 2 of 15 Greenhouse/Ashby postings are still live on
  the employer's board — 13 are delisted while the feed still says active=true.
  Verified not a mapping bug (ether.fi board lists 11 jobs, none is the feed's
  "GTM Engineer Intern"; ATS pages return 200 because they are JS shells).
  Treat feed `active` as unreliable. descriptions.fetch_description handles
  Greenhouse (/board/jobs/id + /embed/job_app?for=&token=, HTML stripped) and
  Ashby (board API, descriptionPlain); returns None otherwise. supports()
  distinguishes delisted from unsupported so draft can say which. draft now
  writes a grounded "why this role" paragraph ONLY with a real description,
  else says so; refuses to overwrite an existing draft without --force (an
  edited draft is precious). score --force rescores all (insert_score gained
  replace= -> OR REPLACE, the one case where it is correct).
  NEXT: feed descriptions into SCORING too — Anduril scored 4 with no red flag
  for "U.S. Person status is required", which is stated plainly in its
  description. One `score --force` run then fixes both stale-resume and
  metadata-only scoring. After that: tests, then Phase 3.
- 2026-07-21 (session 6, cont.2): descriptions wired into scoring; full
  `score --force` run done (36 rescored: 3 with real descriptions, 28 metadata
  only, 5 DELISTED?). Prompt now splits SCORING_WITH_/WITHOUT_DESCRIPTION;
  with a description, red_flags quote stated requirements. Anduril now flags
  "U.S. Person status is required", "must be returning to school", and the real
  timing: "reviewing applications in August 2026" — a live deadline metadata
  never showed. KEY MEASUREMENT: the three byte-identical Kudu postings scored
  3, 4, 4 — model variance is +/-1 tier on identical input. So a 3-vs-4 gap is
  noise; only wide gaps mean anything, and red_flags/rationale are more stable
  and more useful than the number (Apple Masters moved 2->3 but kept its
  "targets Masters, resume is BS 2028" flag). This vindicates the 1-5 tier
  ballot over 0-100. Next: tests (still zero), then Phase 3.
- 2026-07-21 (session 6, cont.3): `check` command + description cache.
  Migration generalized: _ensure_status_column -> _ensure_column(conn, table,
  column, ddl) driven by a MIGRATIONS tuple (status + listing_state, checked_at,
  description). New columns are nullable ON PURPOSE — NULL means "never checked",
  which a DEFAULT would erase. Verified 13->16 cols with 197 rows, 1 interested
  status and 36 scores intact. checking.check_listings asks each supported ATS,
  stores state + caches description via storage.record_listing_check (UPDATE, not
  INSERT — feed-owned columns stay untouched); score/draft now read the cache and
  only hit the network when it is empty. Result on real data: of 36 matching, 28
  are on sources we cannot query, 3 live, 5 gone. report marks GONE only when we
  actually asked. DEDUPE BREAKTHROUGH: "Aquatic" (0ebb6ea9) and "Aquatic Capital"
  (bda8b046) are the SAME Greenhouse job (board aquaticcapitalmanagement, id
  8489233002) reached via /board/jobs/id and /embed/job_app?for=&token= — so ATS
  board+job-id extracted from the URL is a principled identity for dedupe, better
  than fuzzy title matching (revisits the Kudu decision from slice 2).
  Next: tests (STILL zero, ~500 lines now), then Phase 3.
- 2026-07-21 (session 6, cont.4): description coverage + apply URL in drafts.
  RESEARCH (verify-before-building): plain page fetch is a dead end — Citadel
  returns a Cloudflare "Just a moment..." interstitial, and defeating that is
  exactly what the CAPTCHA/bot rule forbids; Workday JSON is 404/403 (not
  public); Apple's job API is gone. So NO generic scraping — rules unchanged.
  What DOES work: company career pages that carry ?gh_jid= are Greenhouse
  underneath. descriptions.py now follows gh_jid, guessing the board from the
  company name (progressive word-prefixes + domain) with a small
  GREENHOUSE_BOARD_OVERRIDES dict for the ones guessing misses (tower research
  -> towerresearchcapital, stoke space -> stokespacetechnologies). Checkable
  went 8 -> 12, live 3 -> 7. Plus `describe <id-prefix> [--file F]`: paste a
  description yourself (stdin or file) — covers 100% of postings, uses the
  "links Edgar explicitly provides" rule, no circumvention. Demoed on Amazon
  (3afa0d8c): stored 3321 chars, redrafted, and the letter now cites what the
  posting actually emphasizes. Drafts open with a header block: Apply URL,
  location, fit score, sponsorship, red_flags as a pre-send checklist, a GONE
  warning, and an explicit TODO when no description existed.
  KNOWN GAP: `score` skips already-scored postings, so the 7 newly-live
  descriptions will not be used until `score --force`. Better fix later:
  rescore when checked_at is newer than scored_at (same shape as the
  resume-fingerprint idea). Next: tests, then Phase 3.
- 2026-07-22 (session 7): PHASE 3 STARTED (tests still deferred by Edgar's call).
  Scare check first: three commits titled "Git ignore test"/"Include sensitive
  information" turned out to touch ONLY .gitignore and net to zero; verified no
  .env/resume/drafts/data ever committed, no key-shaped strings in any commit,
  14 files total in history. Edgar then rewrote history to drop them; local and
  origin now agree at 4d6fb10. Playwright + chromium installed (approved);
  pydantic + playwright declared in pyproject. identity.toml (gitignored) holds
  personal form-fill data, identity.example.toml committed as the template —
  profile.toml could not hold it because that file IS committed to a public repo.
  applying.py slice 1: `apply <id-prefix>` prints a briefing (URL, score,
  status, sponsorship, red_flags checklist, GONE warning, draft path) then opens
  the posting in a HEADED chromium and blocks until Enter. Never submits, never
  logs in, never touches a bot check — if one appears the human takes over.
  ENVIRONMENT NOTE: headless=True works in Claude's shell but headless=False
  fails there with "spawn UNKNOWN" (no interactive desktop session), so the
  headed path can only be verified by Edgar on his own terminal; a friendly
  fallback prints the URL instead of a traceback. Next: Edgar runs `apply`
  himself, then slice 2 — pre-fill Greenhouse/Ashby fields from identity.toml,
  stopping before submit. Workday/Amazon need accounts, so they stay open-only.
- 2026-07-22 (session 7, cont.): slice 1 CONFIRMED working on Edgar's terminal
  after he ran `playwright install chromium` himself — Claude's earlier install
  had landed in a sandbox overlay (file existed for Claude, not for Edgar), a
  second environment mismatch after the missing desktop session. Lesson stands:
  Claude cannot verify the headed browser path at all; Edgar runs it.
  SLICE 2 BUILT (unverified in a real browser): prefill() types identity.toml
  values into labelled text inputs. Design comes from INSPECTING Anduril's real
  Greenhouse form, not from guessing: (a) question ids are per-posting
  (question_12114509007 = LinkedIn only at Anduril), so matching is on LABEL
  TEXT via FILL_RULES; (b) the form carries a g-recaptcha-response field, so the
  tool structurally cannot submit — the hard stop is the only possible design;
  (c) NEVER_FILL blocks legal declarations (work authorization, export control,
  sponsorship, "will you return to school") and protected characteristics
  (gender, ethnicity, veteran, disability) — a wrong guess there is a false
  statement on an application. Verified offline against the 24 real Anduril
  labels: 10 filled, 14 correctly skipped. KNOWN RISK: school/degree/discipline
  look like comboboxes (each has an adjacent empty-id required input), so fill()
  may type text without registering a selection — Edgar must check visually.
  Next: Edgar runs `apply` on Anduril, reports which fields actually took.
- 2026-07-22 (session 7, cont.2): combobox fix + resume upload + opt-in self-ID.
  Edgar confirmed school/degree/discipline came out EMPTY, as predicted: they are
  react-select comboboxes (role=combobox, class select__input), so fill() types
  text that never becomes a selection. _choose_option now clicks the input,
  types, waits, and clicks an option whose text matches EXACTLY (casefold) —
  otherwise it clears the box and reports. GOVERNING PRINCIPLE, now shared by
  three features: exact option match or leave it empty. A near-match is a lie
  ("University of Texas at Austin" is not "Rio Grande Valley").
  attach_resume sets identity.toml [files].resume_pdf on a file input whose
  id/name says resume and not cover — the cover letter is never attached,
  because the draft is unreviewed by definition.
  Self-identification moved OUT of NEVER_FILL into opt-in SELF_ID_RULES at
  Edgar's request: they are enumerated choices, not invertible yes/no questions,
  so an exact match is unambiguous. Blank in identity.toml = left for the human.
  Work authorization / sponsorship / export control STAY blocked forever: their
  phrasing inverts between employers ("Are you authorized?" vs "Will you require
  sponsorship?"), so one stored answer cannot be applied without reading the
  question. Verified offline both ways (blank -> all None; filled -> exact
  values; legal declarations -> None regardless). Next: Edgar reruns `apply`
  after adding [self_identification] and [files].resume_pdf to identity.toml.
- 2026-07-22 (session 7, cont.3): comboboxes FIXED and verified end to end.
  Edgar reported no selection plus the page scrolling up and down. Claude's
  hypothesis (fill() does not trigger react-select, needs press_sequentially)
  was WRONG — a headless probe against the live Anduril form showed both fill()
  and press_sequentially() open the menu with 1 option. Two real causes:
  (1) Greenhouse lists "The University of Texas Rio Grande Valley"; identity.toml
  says it without "The", so byte-exact matching rejected the only right answer.
  (2) The open menu was never closed, so its options overlaid the form and
  intercepted the click on the next field — Playwright then retried for the full
  30s default, scrolling the page, which is exactly what Edgar saw.
  Fixes: _normalize() compares by words (casefold, drop leading "the", strip
  punctuation); a single remaining option containing the typed value counts as a
  match ("United States +1" for "United States"); >1 equal match still refuses;
  _close_menu() presses Escape and waits for options to hide; page timeout cut
  to 8s so a stuck field fails fast instead of thrashing.
  VERIFIED headless against the real form: 13 fields filled including all five
  comboboxes (school/degree/discipline/end-month/country) and the three self-ID
  answers that were set; blank self-ID and every legal declaration left alone.
  NOTE: Claude CAN test the form headless — only the headed window needs Edgar.
  Next: Edgar reruns `apply` (resume upload still unverified), then TESTS.
- 2026-07-22 (session 7, cont.4): CASCADE BUG found and fixed. Edgar reported
  Degree, Discipline and End-date-month failing — three CONSECUTIVE fields, which
  was the clue. Reproduced headless: a failed combobox took its neighbours down
  with it ("could not type"). Two causes, both in cleanup:
  (1) cleanup called _close_menu THEN field.fill(""), but filling refocuses the
  input and REOPENS react-select's menu — so cleanup left the menu open over the
  next field. Order reversed into _reset_field (clear first, then Escape).
  (2) Even closed correctly, the next click landed while the menu was still
  animating shut and got swallowed, leaving that field unfocused so every
  keystroke went nowhere (symptom: "nothing here is called X" listing the
  UNFILTERED option list). Fixed with a 250ms settle after close plus an
  activeElement check that re-clicks once if focus did not land.
  Also: a count==0 result used to report "no menu opened" when the truth was
  usually "your text filtered every option away" — now it clears the filter,
  re-reads, and prints what the employer actually offers.
  DATA FOR EDGAR: Greenhouse has NO "Bachelor of Science" — its list has
  "Bachelors" and "Bachelor's Degree". Discipline offers "Computer Science".
  Months are full names ("May"). Verified: with a deliberately wrong Degree,
  School/Discipline/End-month/End-year all still fill.
  Next: Edgar sets degree = "Bachelor's Degree", reruns, confirms resume upload.
  Then TESTS — _normalize and the single-candidate rule now decide what lands on
  a real application, and the only thing checking them is a hand-run probe.
- 2026-07-22 (session 7, cont.5): model-assisted option matching, on request.
  Edgar wanted the tool to bridge his wording and the employer's "not to the
  point where it lies". Layered: _try_exact (words, no interpretation) runs
  first; only on failure does _list_all_options + llm.match_option show the model
  the employer's REAL list and ask which option means the same fact. The model
  may answer only with a string that is on that list (validated after parsing —
  a hallucinated option is discarded) or null. Filled entries are annotated
  "(matched from 'X')" so an interpreted answer is never mistaken for an exact
  one. NOT used for self-identification: those lists are short and legally
  meaningful, so _is_self_id() withholds the client and exact matching stands.
  NEVER_FILL fields never reach the model at all.
  VERIFIED headless on the live Anduril form: 11/11 fields fill, "Bachelor of
  Science" -> "Bachelor's Degree", "BS" -> "Bachelor's Degree"; and refusals
  hold — Hogwarts, "Nanodegree in Vibes", "Underwater Basket Weaving" all
  return False and leave the field blank with the employer's options listed.
  Costs one small API call per unmatched combobox, none when wording already
  agrees. Edgar's earlier School failure was pre-cascade-fix; it fills now.
  Next: Edgar reruns `apply` (resume upload STILL unverified), then TESTS.
- 2026-07-22 (session 7, cont.6): FIRST TESTS EXIST — 55 of them, ~2s, offline.
  Edgar confirmed `apply` works end to end (all comboboxes + resume upload).
  tests/: test_applying.py (NEVER_FILL holds against a full identity, self-ID is
  opt-in and blank-safe, _is_self_id keeps the model away from demographics,
  _normalize equivalences), test_descriptions.py (supports() and board-name
  guessing on real URLs from the db — the thing that breaks silently when a
  vendor changes a path shape), test_storage.py (ingest set-diff idempotence
  incl. the Row-vs-tuple regression, (source, source_id) identity, feed-key
  translation, status survives re-ingestion, ambiguous prefix rolls back
  cleanly, description cache), test_sources.py (season filter incl. the
  "Summer" != "Summer 2027" trap, _slug).
  THE FIRST RUN FOUND A REAL BUG: _normalize turned "Bachelor's" into
  "bachelor s", so a config saying "Bachelors Degree" could never match
  Greenhouse's "Bachelor's Degree". Apostrophes are now stripped, not spaced.
  That bug survived two rounds of hand-verification on the live form.
  Storage tests use a tmp_path DB via monkeypatch on storage.DB_PATH; nothing
  touches data/. Next: Edgar's call — more sources, dedupe by ATS job id
  (Aquatic case), or the score-staleness fix (checked_at newer than scored_at).
- 2026-07-22 (session 7, cont.7): DEDUPE BY ATS JOB ID done (71 tests now).
  descriptions.ats_key(url) returns "greenhouse:<job_id>" or "ashby:<uuid>",
  covering all four URL shapes (/board/jobs/id, /embed/job_app?token=,
  ?gh_jid=, ashby /org/uuid). The board name is deliberately NOT in the key:
  Greenhouse job ids are globally unique and the same job appears under more
  than one board path. None means "cannot prove identity" — never merged.
  report.dedupe_by_ats folds only exact-key matches and keeps the richest row
  (has description > has score > first seen), preserving order. Wired into
  matching_postings so report, score and check all see one row per real job;
  matching_with_duplicates() also returns the collapsed count, which report
  prints. RESULT on live data: 36 -> 35, the Aquatic/Aquatic Capital pair
  folded into the row that has the description, and the three Kudu Dynamics
  Workday requisitions all survived (key=None) — which is the whole point:
  this merges on proof, not resemblance, reversing nothing from the slice-2
  no-auto-merge decision. Phase 1-3 all complete; Edgar starts applying.
  Remaining known gaps: score staleness (checked_at newer than scored_at),
  more sources, mojibake in stored rationales, __main__ if/elif wants argparse.
- 2026-07-22 (session 7, cont.8): advert-vs-form, from a real failure on IMC
  (80f8fd77) where the feed URL is a career page with an Apply button.
  descriptions.application_url() spots an ATS job id still present in a company
  URL (imc.com/us/careers/jobs/4823924101 -> Greenhouse imc/4823924101), finds
  the board with the existing candidate guessing, and returns the direct form.
  Resolves 7 of the Summer postings (IMC, Stoke Space, Tower Research, Jump
  Trading x4). Generic fallback too: when a page yields no labelled inputs at
  all, _follow_apply_link clicks an "apply" link/button (never one saying
  submit) and prefill runs again.
  Three bugs found only because a SECOND form was finally exercised:
  (1) `#id` selectors break on real ids like question_9170567101[]_66340074101
      -> use [id="..."], which also crashed the whole prefill before.
  (2) "When did you graduate from High School" matched the `school` rule and
      would have typed a university into it -> "high school" added to NEVER_FILL.
  (3) These combobox filters match literal substrings, so the full school name
      finds nothing when the employer spells it differently. _search_variants
      now retries with shorter distinctive fragments (drop "the", last 3 words,
      last 2), and every candidate is still judged against the FULL value, so a
      fragment cannot select the wrong school.
  Long lists (60+) no longer go to the model: an alphabetical list arrives
  truncated, so it would only ever see entries starting with A. It reports what
  the form's own search said instead.
  VERIFIED on two different forms: IMC 11 filled (School correctly refused —
  their list genuinely has no UT Rio Grande Valley, confirmed by searching
  "Rio Grande" on their own widget), Anduril 11 filled, no regressions, 71
  tests green. NOTE for Edgar: IMC's "university email" field gets the personal
  email from identity.toml — worth checking before submitting.