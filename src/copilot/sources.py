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


SOURCES = (
    Source(
        name="vanshb03",
        url="https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/.github/scripts/listings.json",
        normalize=_from_vanshb03,
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
