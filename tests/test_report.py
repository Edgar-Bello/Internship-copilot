"""Folding duplicate listings.

The rule under test: merge only when the ATS says two rows are the same job.
Everything else stays on the list, because a wrong merge silently costs an
application and a visible duplicate costs three seconds.
"""
from copilot.report import dedupe_by_ats

AQUATIC_DIRECT = "https://job-boards.greenhouse.io/aquaticcapitalmanagement/jobs/8489233002"
AQUATIC_EMBED = ("https://job-boards.greenhouse.io/embed/job_app"
                 "?for=aquaticcapitalmanagement&token=8489233002")
KUDU_1 = "https://leidos.wd5.myworkdayjobs.com/External/job/Chantilly-VA/SWE-Intern_R-00183714"
KUDU_2 = "https://leidos.wd5.myworkdayjobs.com/External/job/Chantilly-VA/SWE-Intern_R-00183721"
KUDU_3 = "https://leidos.wd5.myworkdayjobs.com/External/job/Chantilly-VA/SWE-Intern_R-00183707"


def row(url, company="Example", description=None, score=None, source_id="x"):
    return {"url": url, "company": company, "description": description,
            "score": score, "source_id": source_id}


class TestDedupe:
    def test_the_aquatic_pair_becomes_one_posting(self):
        kept, collapsed = dedupe_by_ats([
            row(AQUATIC_DIRECT, "Aquatic"), row(AQUATIC_EMBED, "Aquatic Capital"),
        ])
        assert len(kept) == 1
        assert collapsed == 1

    def test_the_kudu_triplet_is_left_alone(self):
        # Three Workday requisitions: similar looking, genuinely different jobs,
        # and no readable ATS identity to prove otherwise.
        kept, collapsed = dedupe_by_ats([row(u, "Kudu Dynamics") for u in (KUDU_1, KUDU_2, KUDU_3)])
        assert len(kept) == 3
        assert collapsed == 0

    def test_unreadable_urls_never_merge_with_each_other(self):
        identical = "https://www.workatastartup.com/jobs/94400"
        kept, collapsed = dedupe_by_ats([row(identical, "A"), row(identical, "B")])
        assert len(kept) == 2, "no ATS identity means no proof, so no merge"
        assert collapsed == 0

    def test_different_jobs_on_the_same_board_both_survive(self):
        kept, _ = dedupe_by_ats([
            row("https://job-boards.greenhouse.io/veeamsoftware/jobs/4857832101"),
            row("https://job-boards.greenhouse.io/veeamsoftware/jobs/4857828101"),
        ])
        assert len(kept) == 2

    def test_empty_input(self):
        assert dedupe_by_ats([]) == ([], 0)


class TestWhichDuplicateSurvives:
    def test_the_row_with_a_description_wins(self):
        kept, _ = dedupe_by_ats([
            row(AQUATIC_EMBED, "Aquatic Capital"),
            row(AQUATIC_DIRECT, "Aquatic", description="Real posting text"),
        ])
        assert kept[0]["description"] == "Real posting text"

    def test_a_description_beats_a_score(self):
        kept, _ = dedupe_by_ats([
            row(AQUATIC_EMBED, "Aquatic Capital", score=4),
            row(AQUATIC_DIRECT, "Aquatic", description="Real posting text"),
        ])
        assert kept[0]["description"] == "Real posting text"

    def test_a_scored_row_beats_an_untouched_one(self):
        kept, _ = dedupe_by_ats([
            row(AQUATIC_EMBED, "Aquatic Capital"),
            row(AQUATIC_DIRECT, "Aquatic", score=4),
        ])
        assert kept[0]["score"] == 4

    def test_ties_keep_the_first_seen_so_ordering_is_stable(self):
        kept, _ = dedupe_by_ats([
            row(AQUATIC_DIRECT, "Aquatic", source_id="first"),
            row(AQUATIC_EMBED, "Aquatic Capital", source_id="second"),
        ])
        assert kept[0]["source_id"] == "first"


def test_surviving_rows_keep_their_original_order():
    other = "https://job-boards.greenhouse.io/podium81/jobs/7939921"
    kept, _ = dedupe_by_ats([
        row(other, "Podium"), row(AQUATIC_DIRECT, "Aquatic"), row(AQUATIC_EMBED, "Aquatic Capital"),
    ])
    assert [r["company"] for r in kept] == ["Podium", "Aquatic"]
