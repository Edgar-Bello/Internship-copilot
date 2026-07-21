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