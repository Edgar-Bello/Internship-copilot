"""Ingestion and migration behaviour, against a throwaway database.

The regression that matters most is in TestIngestIdempotence: adding
row_factory = sqlite3.Row for the report once made ingest's set-diff compare a
Row against a tuple, which is always False, so every posting looked new and the
primary key turned a silent duplication into a loud IntegrityError.
"""
import pytest

from copilot import storage


@pytest.fixture
def conn(tmp_path, monkeypatch):
    """A real database in a temp directory - no mocks, no touching data/."""
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.db")
    connection = storage.get_connection()
    yield connection
    connection.close()


def feed_row(source_id, **overrides):
    """A posting shaped like the community feed, whose keys differ from our columns."""
    row = {
        "id": source_id, "company_name": "Example Corp", "title": "Software Engineer Intern",
        "url": "https://example.com/jobs/1", "locations": ["Austin, TX"], "season": "Summer",
        "sponsorship": "Other", "active": True, "is_visible": True, "date_posted": 1783425669,
    }
    return row | overrides


class TestSchema:
    def test_both_tables_exist(self, conn):
        names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"postings", "scores"} <= names

    def test_every_migrated_column_is_present(self, conn):
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(postings)")}
        for column, _ in storage.MIGRATIONS:
            assert column in columns, column

    def test_status_defaults_to_new_but_check_columns_stay_null(self, conn):
        storage.ingest(conn, "vanshb03", [feed_row("a")])
        row = conn.execute("SELECT * FROM postings").fetchone()
        assert row["status"] == "new"
        # NULL is the honest value for "we have never asked the employer".
        assert row["listing_state"] is None
        assert row["checked_at"] is None

    def test_get_connection_is_idempotent(self, conn):
        storage.ingest(conn, "vanshb03", [feed_row("a")])
        again = storage.get_connection()  # same path, second call
        assert again.execute("SELECT COUNT(*) FROM postings").fetchone()[0] == 1


class TestIngestIdempotence:
    def test_first_run_stores_everything(self, conn):
        new = storage.ingest(conn, "vanshb03", [feed_row("a"), feed_row("b")])
        assert len(new) == 2
        assert conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0] == 2

    def test_second_run_stores_nothing(self, conn):
        postings = [feed_row("a"), feed_row("b")]
        storage.ingest(conn, "vanshb03", postings)
        assert storage.ingest(conn, "vanshb03", postings) == []
        assert conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0] == 2

    def test_only_the_genuinely_new_row_comes_back(self, conn):
        storage.ingest(conn, "vanshb03", [feed_row("a")])
        new = storage.ingest(conn, "vanshb03", [feed_row("a"), feed_row("b")])
        assert [p["id"] for p in new] == ["b"]

    def test_the_same_id_from_another_source_is_a_different_posting(self, conn):
        storage.ingest(conn, "vanshb03", [feed_row("a")])
        new = storage.ingest(conn, "someone-else", [feed_row("a")])
        assert len(new) == 1, "identity is (source, source_id), not source_id alone"

    def test_feed_keys_are_translated_to_our_column_names(self, conn):
        storage.ingest(conn, "vanshb03", [feed_row("a", company_name="Anduril")])
        row = conn.execute("SELECT * FROM postings").fetchone()
        assert row["source_id"] == "a"      # feed calls this "id"
        assert row["company"] == "Anduril"  # feed calls this "company_name"

    def test_locations_survive_the_round_trip(self, conn):
        import json
        storage.ingest(conn, "vanshb03", [feed_row("a", locations=["Austin, TX", "Remote"])])
        stored = conn.execute("SELECT locations FROM postings").fetchone()["locations"]
        assert json.loads(stored) == ["Austin, TX", "Remote"]

    def test_all_seasons_are_stored_because_they_are_facts(self, conn):
        storage.ingest(conn, "vanshb03", [feed_row("a", season="Winter")])
        assert conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0] == 1


class TestStatusIsPreciousState:
    def test_a_status_survives_re_ingestion(self, conn):
        storage.ingest(conn, "vanshb03", [feed_row("a")])
        storage.set_status(conn, "a", "applied")
        storage.ingest(conn, "vanshb03", [feed_row("a")])
        assert conn.execute("SELECT status FROM postings").fetchone()["status"] == "applied"

    def test_an_ambiguous_prefix_changes_nothing(self, conn):
        storage.ingest(conn, "vanshb03", [feed_row("kudu-1"), feed_row("kudu-2")])
        assert storage.set_status(conn, "kudu", "applied") == 2
        statuses = [r["status"] for r in conn.execute("SELECT status FROM postings")]
        assert statuses == ["new", "new"], "a rolled-back update must leave no trace"

    def test_an_unknown_prefix_reports_zero(self, conn):
        storage.ingest(conn, "vanshb03", [feed_row("a")])
        assert storage.set_status(conn, "zzz", "applied") == 0


class TestDescriptionCache:
    def test_a_pasted_description_marks_the_listing_live(self, conn):
        storage.ingest(conn, "vanshb03", [feed_row("a")])
        assert storage.set_description(conn, "a", "Real posting text") == 1
        row = conn.execute("SELECT * FROM postings").fetchone()
        assert row["description"] == "Real posting text"
        assert row["listing_state"] == "live"
        assert row["checked_at"] is not None

    def test_recording_a_check_leaves_feed_columns_alone(self, conn):
        storage.ingest(conn, "vanshb03", [feed_row("a", title="Original Title")])
        storage.record_listing_check(conn, "vanshb03", "a", "gone")
        row = conn.execute("SELECT * FROM postings").fetchone()
        assert row["title"] == "Original Title"
        assert row["listing_state"] == "gone"
