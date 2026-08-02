# Internship Application Co-pilot

A command-line tool that helps you **find, track, score, and apply to tech
internships** — while keeping a human in control of everything that leaves your
computer. It aggregates postings from community internship lists, ranks them
against your résumé using an LLM, drafts tailored cover letters, and pre-fills
application forms in a real browser — but it **never submits anything and never
solves a bot check**. You review and click the final button yourself.

Built as a learning project (Summer 2027 internship hunt), so the code favours
being readable and honest over being clever.

---

## Contents

- [What it does](#what-it-does)
- [The co-pilot philosophy](#the-co-pilot-philosophy)
- [Hard rules](#hard-rules)
- [Requirements](#requirements)
- [Setup](#setup)
- [Configuration — what you must change](#configuration--what-you-must-change)
- [Usage](#usage)
- [A typical session](#a-typical-session)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Privacy & what is gitignored](#privacy--what-is-gitignored)
- [Testing](#testing)
- [Limitations](#limitations)

---

## What it does

The tool runs in three phases, exposed as CLI subcommands:

1. **Aggregate & track** — pulls postings from permitted community GitHub lists
   into a local SQLite database, dedupes them, filters by your keywords, and
   tracks a status per posting (`new` → `seen` → `interested` → `applied`, plus
   `rejected` / `closed`).
2. **Score & draft** — sends each matching posting plus your résumé to an LLM,
   stores a 1–5 fit score with a rationale, the résumé points to emphasise, and
   red flags (e.g. citizenship requirements). Then drafts a grounded cover
   letter per posting.
3. **Assisted apply** — opens the real application form in a visible browser and
   pre-fills the mechanical fields (name, email, school, etc.) from your saved
   details. It stops before submit. Always.

## The co-pilot philosophy

This is **not an auto-apply bot**. A human reviews everything before it goes
anywhere. Scoring is used for *effort ordering* and *per-posting tailoring* — not
to auto-reject jobs. Drafts open with an `UNREVIEWED` banner. The apply step
fills what it safely can and then hands you the keyboard.

## Hard rules

These are enforced in code and are the reason the tool stays on the right side of
site terms of service:

- **Sources are limited to** community GitHub internship lists (via the raw
  GitHub file API), public Greenhouse / Ashby / Lever ATS JSON endpoints, and
  links you explicitly provide.
- **No scraping LinkedIn / Indeed / Handshake** (their ToS forbid it).
- **No CAPTCHA / bot-check solving** and no code to defeat bot detection. If a
  site challenges the browser, you clear it by hand or apply in your own Chrome.
- **No bulk auto-submission.** The apply step pre-fills, then stops.
- **Legal declarations and demographics are never auto-answered** — work
  authorization, sponsorship, export-control, veteran/disability/ethnicity
  questions are always left for you.

## Requirements

- **Python 3.14+**
- A **Greenhouse/Ashby-friendly OS browser** for the apply step (uses your
  installed Google Chrome if present, else Playwright's bundled Chromium)
- An **OpenAI-compatible API key** for the scoring/drafting steps (any endpoint
  that speaks the OpenAI API — the author uses a school-provided key). Phases 1
  and 3 work without it; only `score` and `draft` need it.

## Setup

```bash
# 1. Clone
git clone https://github.com/Edgar-Bello/Internship-copilot.git
cd Internship-copilot

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# 3. Install the package and its dev tools
python -m pip install -e ".[dev]"

# 4. Install the browser used by the apply step
python -m playwright install chromium
```

> On Windows the examples below call `.venv\Scripts\python.exe -m copilot ...`.
> If you activated the venv (step 2) you can just write `python -m copilot ...`.

## Configuration — what you must change

Five files. Two are committed templates you copy; the rest hold your personal
data and are gitignored.

| File | Committed? | What to do |
| --- | --- | --- |
| `profile.toml` | yes | Edit `[search].keywords` / `exclude_keywords` to match the roles you want. |
| `.env` | **no** — you create it | `OPENAI_API_KEY=...` and `OPENAI_BASE_URL=...` (the base URL of your OpenAI-compatible endpoint). Needed only for `score` / `draft`. |
| `resume.md` | **no** — you create it | Paste your résumé as plain Markdown. This is the *corpus* the model reads — make it a superset of your PDF (every project, so it can tailor to any role). |
| `identity.toml` | **no** — copy from example | `cp identity.example.toml identity.toml`, then fill in your real name, email, school, links, and the path to your résumé PDF. Used to pre-fill forms. |
| the source lists | in `src/copilot/sources.py` | Optional: add another community list by writing a `normalize()` for it (see the two existing sources). |

Nothing secret is ever committed — `.env`, `resume.md`, `identity.toml`, your
résumé PDF, and the `data/` folder are all in `.gitignore`.

## Usage

Every command is `python -m copilot <subcommand>`:

| Command | What it does |
| --- | --- |
| `python -m copilot` | Fetch every source, store new postings, print new Summer ones. |
| `report [--all]` | Ranked to-do list. `--all` also shows closed/delisted. |
| `shortlist [--check]` | What's left to apply to, with scores + red flags. `--check` re-asks each ATS first. |
| `mark <id> <status>` | Set a posting's status (`seen`, `interested`, `applied`, `rejected`, `closed`). |
| `check [--recheck]` | Ask each queryable ATS whether the job is still listed; caches descriptions. |
| `describe <id> [--file F]` | Store a job description you pasted (stdin or a file) for postings we can't fetch. |
| `score [--force]` | Score matching postings against your résumé. `--force` rescores all. |
| `draft <id> [--force]` | Write a cover-letter draft to `drafts/`. Refuses to overwrite an edited draft without `--force`. |
| `apply <id>` | Open the posting in a browser and pre-fill it. **Never submits.** |

`<id>` is the short 8-character handle shown at the start of each posting in
`report` / `shortlist` (a prefix is enough).

## A typical session

```bash
# Pull the latest postings and see what's new
python -m copilot

# Score anything unscored against your résumé (needs .env)
python -m copilot score

# Prune dead listings, then see your ranked shortlist
python -m copilot shortlist --check

# Pick one (say handle e6ef564e), draft a letter, review the red flags
python -m copilot draft e6ef564e

# Open the form, pre-filled, and finish it yourself
python -m copilot apply e6ef564e

# Record what you did
python -m copilot mark e6ef564e applied
```

For a posting whose description can't be fetched automatically (Workday, company
career sites), open it, copy the description, and feed it in so the score and
letter are grounded:

```bash
python -m copilot describe e6ef564e --file jd.txt
```

## How it works

```
community GitHub lists ─┐
public ATS JSON APIs  ──┼─► fetch + normalize ─► SQLite (data/copilot.db)
links you provide     ─┘                              │
                                                       ├─► score  (LLM + résumé) ─► scores table
                                                       ├─► draft  (LLM + résumé + description) ─► drafts/*.md
                                                       └─► apply  (Playwright, headed, pre-fill only)
```

- **Identity & dedupe.** Each posting is identified by `(source, source_id)`, so
  two lists never collide. When a job appears twice under different URLs, it's
  folded by its underlying ATS job id — merging on *proof*, never resemblance.
- **Facts vs. opinions.** The database stores every posting as a fact; your
  keyword filters are applied at read time, so changing `profile.toml` never
  loses data and needs no re-fetch.
- **Grounded generation.** The model is told exactly what it does and doesn't
  know. With a real job description it cites the posting; without one it stays
  general rather than inventing details about the company.

## Project structure

```
src/copilot/
  sources.py       fetch community lists, normalize each into one shape
  storage.py       SQLite schema, migrations, ingest, status, handles
  descriptions.py  fetch real job descriptions from Greenhouse/Ashby
  checking.py      ask each ATS whether a posting is still live
  scoring.py       orchestrate résumé-vs-posting scoring
  llm.py           the OpenAI-compatible client, prompts, structured outputs
  report.py        keyword filtering, ATS dedupe, ranked output
  draft.py         write grounded cover-letter drafts
  applying.py      Playwright: open + pre-fill forms, never submit
  __main__.py      CLI dispatch
tests/             offline test suite (pure functions + a temp SQLite db)
profile.toml            your search keywords (committed)
identity.example.toml   template for identity.toml (committed)
```

## Privacy & what is gitignored

The repository is public, so everything personal is kept out of git:
`.env` (API key), `resume.md`, `identity.toml`, your résumé PDF, `drafts/`, and
the entire `data/` folder (the SQLite database and the browser profile). The
LLM calls send your résumé and posting text to whatever endpoint you configure
in `.env` — use a key and provider you're comfortable with.

## Testing

```bash
python -m pytest        # ~100 tests, offline, runs in ~2s
python -m ruff check .  # lint
```

The tests exercise the pure logic (filtering, dedupe, form-fill safety rules,
per-source translation) and a throwaway SQLite database. They never touch the
network, the API, or a browser.

## Limitations

- **Community lists rot.** Postings marked "active" are often already gone;
  `check` verifies the ones on queryable ATSs, and you mark the rest `closed`.
- **Not every site can be filled.** Workday and company sites often need an
  account, and some firms (SIG, Citadel) actively block automated browsers. For
  those, the tool's value is the drafted letter, the red-flag checklist, and
  your saved details — apply in your own browser.
- **Personal / learning project.** No license file yet; add one if you intend to
  let others reuse it.
