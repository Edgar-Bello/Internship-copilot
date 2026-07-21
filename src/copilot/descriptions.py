"""Fetch real job descriptions from the ATS endpoints this project is allowed to use.

Only public Greenhouse and Ashby JSON APIs (see the hard rules in CLAUDE.md).
Anything else returns None and the caller degrades gracefully - we never guess.

A None for a Greenhouse/Ashby URL is also a liveness signal: the employer's board
no longer lists that job, even when the community feed still calls it active.
"""
import html
import re
import urllib.parse

import requests

TIMEOUT = 30


def _strip_html(raw: str) -> str:
    """Greenhouse returns escaped HTML; the model wants prose."""
    text = html.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _fetch_ashby(org: str, job_id: str) -> str | None:
    resp = requests.get(
        f"https://api.ashbyhq.com/posting-api/job-board/{org}", timeout=TIMEOUT
    )
    resp.raise_for_status()
    for job in resp.json().get("jobs", []):
        if job.get("id") == job_id:
            return job.get("descriptionPlain")
    return None  # board loaded fine, job is not on it -> delisted


def _fetch_greenhouse(board: str, job_id: str) -> str | None:
    resp = requests.get(
        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}",
        params={"content": "true"},
        timeout=TIMEOUT,
    )
    if resp.status_code == 404:
        return None  # job pulled from the board
    resp.raise_for_status()
    content = resp.json().get("content")
    return _strip_html(content) if content else None


def fetch_description(url: str) -> str | None:
    """Real description text for a posting, or None if we can't get one."""
    parsed = urllib.parse.urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    query = urllib.parse.parse_qs(parsed.query)
    try:
        if "ashbyhq.com" in parsed.netloc and len(parts) >= 2:
            return _fetch_ashby(parts[0], parts[1])
        if "greenhouse.io" in parsed.netloc:
            # Two shapes in the wild: /<board>/jobs/<id> and /embed/job_app?for=<board>&token=<id>
            if parts[:2] == ["embed", "job_app"] and "for" in query and "token" in query:
                return _fetch_greenhouse(query["for"][0], query["token"][0])
            if len(parts) >= 3 and parts[1] == "jobs":
                return _fetch_greenhouse(parts[0], parts[2])
    except requests.RequestException:
        return None  # a network hiccup degrades the draft, it does not crash it
    return None


def supports(url: str) -> bool:
    """True when this URL is on an ATS we can query - distinguishes 'delisted' from 'unsupported'."""
    netloc = urllib.parse.urlparse(url).netloc
    return "ashbyhq.com" in netloc or "greenhouse.io" in netloc
