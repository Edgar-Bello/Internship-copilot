"""The feed filter and the draft filename builder - the two smallest pure functions."""
from copilot.draft import _slug
from copilot.sources import summer_postings


def posting(**overrides):
    return {"season": "Summer", "active": True, "is_visible": True,
            "title": "Software Engineer Intern"} | overrides


class TestSummerPostings:
    def test_keeps_a_live_summer_posting(self):
        assert len(summer_postings([posting()])) == 1

    def test_drops_other_seasons(self):
        # One feed file carries all four seasons; the year lives in the repo name.
        for season in ("Winter", "Spring", "Fall"):
            assert summer_postings([posting(season=season)]) == []

    def test_season_comparison_is_exact(self):
        # "Summer" != "Summer 2027" - the mismatch that would silently show zero.
        assert summer_postings([posting(season="Summer 2027")]) == []

    def test_drops_inactive_and_hidden(self):
        assert summer_postings([posting(active=False)]) == []
        assert summer_postings([posting(is_visible=False)]) == []

    def test_all_three_conditions_are_required(self):
        assert summer_postings([posting(season="Fall", active=False, is_visible=False)]) == []

    def test_preserves_order_and_returns_the_originals(self):
        rows = [posting(title="A"), posting(title="B", season="Fall"), posting(title="C")]
        assert [p["title"] for p in summer_postings(rows)] == ["A", "C"]

    def test_empty_feed_is_not_an_error(self):
        assert summer_postings([]) == []


class TestSlug:
    def test_punctuation_and_case_become_hyphens(self):
        assert _slug("Apex Technology, Inc.") == "apex-technology-inc"

    def test_no_leading_or_trailing_hyphens(self):
        assert _slug("  Ether.fi  ") == "ether-fi"

    def test_ampersands_do_not_survive_into_a_filename(self):
        assert _slug("H&CO") == "h-co"

    def test_distinct_companies_keep_distinct_names(self):
        assert _slug("Jump Trading") != _slug("Jump Trading Group")
