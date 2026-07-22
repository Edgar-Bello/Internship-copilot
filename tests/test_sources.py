"""Feed filtering, per-source translation, and the draft filename builder."""
from datetime import datetime

from copilot.draft import _slug
from copilot.sources import SOURCES, _from_vanshb03, _from_zshah101, summer_postings

# A real row from zshah101's jobs.json, trimmed.
ZSHAH_ROW = {
    "id": "greenhouse:andurilindustries:5148079007",
    "company": "Anduril",
    "title": "2027 Software Engineer Intern",
    "url": "https://boards.greenhouse.io/andurilindustries/jobs/5148079007",
    "location": "Atlanta, Georgia, United States; Boston, Massachusetts, United States;",
    "season": "Summer 2027",
    "is_open": "True",
    "sponsorship": "citizens-only",
    "posted_at": "2026-06-10T19:33:06-04:00",
}


class TestZshah101Normalizer:
    """Each case here is a silent failure if the translation is skipped."""

    def test_season_is_translated_into_our_vocabulary(self):
        # "Summer 2027" == "Summer" is legal and always False, so an untranslated
        # season would make the entire list disappear with no error.
        assert _from_zshah101(ZSHAH_ROW)["season"] == "Summer"
        assert summer_postings([_from_zshah101(ZSHAH_ROW)]) != []

    def test_other_seasons_are_left_alone_and_filtered_out(self):
        for season in ("Fall 2026", "Summer 2026"):
            row = _from_zshah101(ZSHAH_ROW | {"season": season})
            assert row["season"] == season
            assert summer_postings([row]) == []

    def test_is_open_is_a_string_not_a_boolean(self):
        # bool("False") is True - taking this field at face value would
        # resurrect every closed posting on the list.
        assert _from_zshah101(ZSHAH_ROW | {"is_open": "False"})["active"] is False
        assert _from_zshah101(ZSHAH_ROW | {"is_open": "True"})["active"] is True

    def test_closed_postings_never_reach_the_summer_list(self):
        assert summer_postings([_from_zshah101(ZSHAH_ROW | {"is_open": "False"})]) == []

    def test_locations_are_split_out_of_one_string(self):
        assert _from_zshah101(ZSHAH_ROW)["locations"] == [
            "Atlanta, Georgia, United States", "Boston, Massachusetts, United States",
        ]

    def test_a_missing_location_is_an_empty_list_not_a_crash(self):
        assert _from_zshah101(ZSHAH_ROW | {"location": ""})["locations"] == []

    def test_posted_at_becomes_unix_seconds(self):
        # 2026-06-10T19:33:06-04:00 -> an int the report can ORDER BY.
        posted = _from_zshah101(ZSHAH_ROW)["date_posted"]
        assert isinstance(posted, int)
        assert posted == int(datetime.fromisoformat("2026-06-10T19:33:06-04:00").timestamp())

    def test_unparseable_dates_do_not_crash_the_run(self):
        assert _from_zshah101(ZSHAH_ROW | {"posted_at": "not a date"})["date_posted"] == 0
        assert _from_zshah101(ZSHAH_ROW | {"posted_at": None})["date_posted"] == 0

    def test_rows_without_an_id_are_dropped(self):
        assert _from_zshah101(ZSHAH_ROW | {"id": ""}) is None

    def test_output_matches_the_shape_the_other_source_produces(self):
        theirs = _from_zshah101(ZSHAH_ROW)
        ours = _from_vanshb03({
            "id": "x", "company_name": "C", "title": "T", "url": "u", "locations": [],
            "season": "Summer", "sponsorship": "Other", "active": True,
            "is_visible": True, "date_posted": 1,
        })
        assert theirs.keys() == ours.keys()


def test_source_names_are_unique_because_they_namespace_ids():
    names = [source.name for source in SOURCES]
    assert len(names) == len(set(names))


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
