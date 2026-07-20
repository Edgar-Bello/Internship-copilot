"""Orchestrate scoring: matching postings + resume -> model -> scores table."""
import pathlib

from copilot.llm import MODEL, get_client, score_posting
from copilot.report import matching_postings
from copilot.storage import insert_score

RESUME_PATH = pathlib.Path("resume.md")


def score_matching(conn) -> None:
    resume = RESUME_PATH.read_text(encoding="utf-8")
    postings = matching_postings(conn)
    already = {
        (row["source"], row["source_id"])
        for row in conn.execute("SELECT source, source_id FROM scores").fetchall()
    }
    todo = [p for p in postings if (p["source"], p["source_id"]) not in already]
    print(f"{len(postings)} matching, {len(postings) - len(todo)} already scored, {len(todo)} to score")

    client = get_client()
    for i, posting in enumerate(todo, start=1):
        assessment = score_posting(client, resume, posting)
        insert_score(conn, posting["source"], posting["source_id"], assessment, MODEL)
        print(f"[{i}/{len(todo)}] {posting['company']} - {posting['title']} -> {assessment.score}")
