"""Community internship lists, translated into one shape.

Every list invents its own field names, its own season vocabulary, and its own
idea of what a boolean is. Each source therefore owns a `normalize` function,
and that function is the only place its vocabulary is allowed to exist - past
this module, the rest of the program sees one shape:

    id, company_name, title, url, locations (list), season,
    sponsorship, active, is_visible, date_posted (unix seconds)

`name` namespaces the ids in the database: identity is (source, source_id), so
two lists can reuse an id without colliding.
"""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import requests

TIMEOUT = 30


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    normalize: Callable[[dict], dict | None]  # their row -> our shape, None to drop


def _from_vanshb03(row: dict) -> dict | None:
    """This feed's shape is the one the database was designed around."""
    if not row.get("id"):
        return None
    return {
        "id": row["id"],
        "company_name": row.get("company_name", ""),
        "title": row.get("title", ""),
        "url": row.get("url", ""),
        "locations": row.get("locations") or [],
        "season": row.get("season", ""),
        "sponsorship": row.get("sponsorship", ""),
        "active": bool(row.get("active")),
        "is_visible": bool(row.get("is_visible")),
        "date_posted": row.get("date_posted") or 0,
    }


def _from_zshah101(row: dict) -> dict | None:
    """Translate the zshah101 list, which disagrees with us on almost everything.

    Three traps, each of which fails silently if ignored:
      - `season` is "Summer 2027", not "Summer". Comparing those is legal Python
        that is always False, so the whole list would just vanish.
      - `is_open` is the STRING "True"/"False". bool("False") is True, which
        would resurrect every closed posting.
      - `location` is one semicolon-joined string, not a list.
    """
    job_id = row.get("id")
    if not job_id:
        return None
    # This list covers several seasons; ours means Summer 2027 by "Summer",
    # because it grew up around a repo that only carried that one year.
    season = row.get("season", "")
    return {
        "id": job_id,
        "company_name": row.get("company", ""),
        "title": row.get("title", ""),
        "url": row.get("url", ""),
        "locations": [part.strip() for part in row.get("location", "").split(";") if part.strip()],
        "season": "Summer" if season == "Summer 2027" else season,
        "sponsorship": row.get("sponsorship", ""),
        "active": str(row.get("is_open", "")).strip().lower() == "true",
        "is_visible": True,  # no such concept here: if it is in the file, it is listed
        "date_posted": _unix_seconds(row.get("posted_at")),
    }


def _unix_seconds(timestamp: str | None) -> int:
    """ISO 8601 text -> unix seconds, which is what our column holds."""
    if not timestamp:
        return 0
    try:
        return int(datetime.fromisoformat(timestamp).timestamp())
    except ValueError:
        return 0


SOURCES = (
    Source(
        name="vanshb03",
        url="https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/.github/scripts/listings.json",
        normalize=_from_vanshb03,
    ),
    Source(
        name="zshah101",
        url="https://raw.githubusercontent.com/zshah101/"
            "Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships/main/data/jobs.json",
        normalize=_from_zshah101,
    ),
)


def fetch(source: Source) -> list[dict]:
    """Download one list and translate every row into our shape."""
    resp = requests.get(source.url, timeout=TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    # Some lists are an array of jobs, others a dict keyed by job id.
    rows = payload.values() if isinstance(payload, dict) else payload
    return [normalized for row in rows if (normalized := source.normalize(row)) is not None]


def summer_postings(postings: list[dict]) -> list[dict]:
    result = []
    for posting in postings:
        if posting["season"] == "Summer" and posting["active"] and posting["is_visible"]:
            result.append(posting)
    return result


if __name__ == "__main__":
    for src in SOURCES:
        listings = fetch(src)
        summer = summer_postings(listings)
        print(f"{src.name}: {len(listings)} rows, {len(summer)} Summer")
