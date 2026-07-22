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

# Some companies skin Greenhouse on their own domain, leaving only ?gh_jid=<id>
# behind - the board name is nowhere in the URL. We guess it from the company
# name; these are the ones the guess cannot reach. Add entries as you find them.
GREENHOUSE_BOARD_OVERRIDES = {
    "tower research": "towerresearchcapital",
    "stoke space": "stokespacetechnologies",
}


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


def _board_candidates(company: str, host: str) -> list[str]:
    """Plausible Greenhouse board names, best guess first.

    'Jump Trading Group' -> jumptradinggroup, jumptrading, jump (the middle one
    is the real board). Dropping trailing words catches most corporate suffixes.
    """
    override = GREENHOUSE_BOARD_OVERRIDES.get(company.lower().strip())
    candidates = [override] if override else []
    words = re.findall(r"[a-z0-9]+", company.lower())
    for stop in range(len(words), 0, -1):
        candidates.append("".join(words[:stop]))
    # The company's own domain is often the board name too: tower-research.com -> towerresearch
    candidates.append(re.sub(r"[^a-z0-9]", "", host.lower().removeprefix("www.").split(".")[0]))
    return list(dict.fromkeys(c for c in candidates if c))  # dedupe, keep order


def _fetch_greenhouse_by_jid(job_id: str, company: str, host: str) -> str | None:
    """Company-hosted Greenhouse page: we have the job id but must find the board."""
    for board in _board_candidates(company, host):
        description = _fetch_greenhouse(board, job_id)
        if description:
            return description
    return None


def fetch_description(url: str, company: str = "") -> str | None:
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
        if "gh_jid" in query:
            return _fetch_greenhouse_by_jid(query["gh_jid"][0], company, parsed.netloc)
    except requests.RequestException:
        return None  # a network hiccup degrades the draft, it does not crash it
    return None


def ats_key(url: str) -> str | None:
    """Identity of the underlying job at the ATS, or None if we cannot read one.

    Two feed rows with the same key are the same job reached by different URLs -
    "Aquatic" and "Aquatic Capital" are both Greenhouse job 8489233002, one via
    /board/jobs/id and one via /embed/job_app. Greenhouse and Ashby job ids are
    globally unique, so the board name is deliberately not part of the key.

    None means "we cannot prove these are the same job", which is the answer for
    the three Kudu Dynamics postings: separate Workday requisitions, separate
    jobs, and merging them would cost a real application.
    """
    parsed = urllib.parse.urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    query = urllib.parse.parse_qs(parsed.query)
    if "ashbyhq.com" in parsed.netloc and len(parts) >= 2:
        return f"ashby:{parts[1]}"
    if "gh_jid" in query:
        return f"greenhouse:{query['gh_jid'][0]}"
    if "greenhouse.io" in parsed.netloc:
        if parts[:2] == ["embed", "job_app"] and "token" in query:
            return f"greenhouse:{query['token'][0]}"
        if len(parts) >= 3 and parts[1] == "jobs":
            return f"greenhouse:{parts[2]}"
    return None


def supports(url: str) -> bool:
    """True when this URL is on an ATS we can query - distinguishes 'delisted' from 'unsupported'."""
    parsed = urllib.parse.urlparse(url)
    if "ashbyhq.com" in parsed.netloc or "greenhouse.io" in parsed.netloc:
        return True
    return "gh_jid" in urllib.parse.parse_qs(parsed.query)
