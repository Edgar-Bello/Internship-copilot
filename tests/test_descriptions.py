"""URL parsing for the ATS endpoints we are allowed to query.

These break silently in the wild: a vendor changes a path shape and every
posting quietly reports DELISTED. Real URLs from the database are used below so
the failure is loud and local instead.
"""
from copilot.descriptions import GREENHOUSE_BOARD_OVERRIDES, _board_candidates, _strip_html, supports

GREENHOUSE_DIRECT = "https://job-boards.greenhouse.io/andurilindustries/jobs/5148079007"
GREENHOUSE_EU = "https://job-boards.eu.greenhouse.io/veeamsoftware/jobs/4857832101"
GREENHOUSE_EMBED = ("https://job-boards.greenhouse.io/embed/job_app"
                    "?for=aquaticcapitalmanagement&jr_id=6a06fd77&token=8489233002")
COMPANY_SITE_GH_JID = "https://www.jumptrading.com/hr/job?gh_jid=8003019"
ASHBY = "https://jobs.ashbyhq.com/ether.fi/6dcb712c-8fe5-4725-ad6a-0e9771af22cb"
WORKDAY = ("https://leidos.wd5.myworkdayjobs.com/External/job/Chantilly-VA/"
           "Software-Engineer-Intern_R-00183714")
AMAZON = "https://www.amazon.jobs/en/jobs/3136266/robotics-software-development-engineer-intern"


class TestSupports:
    def test_recognises_every_shape_we_can_query(self):
        for url in (GREENHOUSE_DIRECT, GREENHOUSE_EU, GREENHOUSE_EMBED, COMPANY_SITE_GH_JID, ASHBY):
            assert supports(url) is True, url

    def test_rejects_hosts_with_no_public_endpoint(self):
        # Not a value judgement - we simply cannot ask these, so "no description"
        # must not be reported to the user as "the employer delisted it".
        for url in (WORKDAY, AMAZON, "https://www.citadel.com/careers/details/swe-intern-us/"):
            assert supports(url) is False, url

    def test_a_company_page_is_only_supported_because_of_gh_jid(self):
        assert supports("https://www.jumptrading.com/hr/job") is False
        assert supports(COMPANY_SITE_GH_JID) is True


class TestBoardCandidates:
    def test_drops_corporate_suffixes_one_word_at_a_time(self):
        # The real board is 'jumptrading', but the feed says 'Jump Trading Group'.
        candidates = _board_candidates("Jump Trading Group", "www.jumptrading.com")
        assert "jumptrading" in candidates
        assert candidates.index("jumptradinggroup") < candidates.index("jumptrading")

    def test_falls_back_to_the_domain(self):
        assert "towerresearch" in _board_candidates("Tower Research", "tower-research.com")

    def test_overrides_are_tried_first(self):
        candidates = _board_candidates("Tower Research", "tower-research.com")
        assert candidates[0] == GREENHOUSE_BOARD_OVERRIDES["tower research"]

    def test_overrides_ignore_case_and_padding(self):
        assert _board_candidates("  STOKE SPACE ", "www.stokespace.com")[0] == \
               GREENHOUSE_BOARD_OVERRIDES["stoke space"]

    def test_no_duplicates_so_we_do_not_repeat_requests(self):
        candidates = _board_candidates("Podium", "podium.com")
        assert len(candidates) == len(set(candidates))

    def test_never_yields_an_empty_board_name(self):
        assert "" not in _board_candidates("!!!", "example.com")


class TestStripHtml:
    def test_unescapes_entities_and_drops_tags(self):
        assert _strip_html("<p>Ben &amp; Jerry&#39;s</p>") == "Ben & Jerry's"

    def test_tags_become_spaces_so_words_do_not_fuse(self):
        assert _strip_html("<li>C++</li><li>Python</li>") == "C++ Python"
