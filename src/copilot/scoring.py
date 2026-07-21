"""Orchestrate scoring: matching postings + resume -> model -> scores table."""
import pathlib

from copilot.descriptions import fetch_description, supports
from copilot.llm import MODEL, get_client, score_posting
from copilot.report import matching_postings
from copilot.storage import insert_score

RESUME_PATH = pathlib.Path("resume.md")


def score_matching(conn, force: bool = False) -> None:
    """Score every matching posting that has no score yet.

    force=True rescores everything - use it after editing resume.md, since old
    scores were computed against a resume that no longer exists.
    """
    resume = RESUME_PATH.read_text(encoding="utf-8")
    postings = matching_postings(conn)
    already = {
        (row["source"], row["source_id"])
        for row in conn.execute("SELECT source, source_id FROM scores").fetchall()
    }
    todo = postings if force else [p for p in postings if (p["source"], p["source_id"]) not in already]
    if force:
        print(f"{len(postings)} matching, rescoring all of them (--force)")
    else:
        print(f"{len(postings)} matching, {len(postings) - len(todo)} already scored, {len(todo)} to score")

    client = get_client()
    grounded = delisted = 0
    for i, posting in enumerate(todo, start=1):
        # A real description turns "guess from the title" into "read the requirements".
        description = fetch_description(posting["url"])
        if description:
            grounded += 1
            marker = "desc"
        elif supports(posting["url"]):
            delisted += 1
            marker = "DELISTED?"
        else:
            marker = "meta"
        assessment = score_posting(client, resume, posting, description)
        insert_score(conn, posting["source"], posting["source_id"], assessment, MODEL, replace=force)
        print(
            f"[{i}/{len(todo)}] {posting['company']} - {posting['title']} "
            f"-> {assessment.score} ({marker})"
        )

    print(
        f"\nscored {len(todo)}: {grounded} from the employer's description, "
        f"{len(todo) - grounded - delisted} from metadata only, "
        f"{delisted} whose ATS no longer lists them"
    )
