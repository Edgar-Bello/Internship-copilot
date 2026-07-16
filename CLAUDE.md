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
2. **Fit scoring + drafting:** score postings against resume/profile; Anthropic
   API drafts cover letters and resume-bullet emphasis — always human-edited.
3. **Assisted apply:** Playwright opens the posting, pre-fills obvious fields,
   hard stop before submit.

## Dev environment

- Windows 11, Python 3.14 (C:\Python314), venv at .venv (not committed)
- Install: `.venv\Scripts\python.exe -m pip install -e ".[dev]"`
- Tests: `.venv\Scripts\python.exe -m pytest`
- Lint: `.venv\Scripts\python.exe -m ruff check .`
- src-layout: the package is `src/copilot/`; `data/` and `.env` are gitignored.

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
