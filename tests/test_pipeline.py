"""End-to-end pipeline tests with the network stubbed out.

These exercise the paths that only appear when fetching really fails: the file-level
removal ladder, the refusal to proceed when everything is down, and the heartbeat that
keeps the scheduled workflow alive.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from rowan_clery import fetch, pipeline
from rowan_clery.archive import Archive
from tests.conftest import FIXTURE_DIR, REAL_SHEETS, TOTAL_INCIDENTS

AUGUST = "1Ms5gjJX_-vnA4wUaTW-z60Hd98guINjRU5R-e5n58Ts"


@pytest.fixture
def project(tmp_path):
    """A scratch project: real config, empty data directory."""
    config = tmp_path / "config"
    config.mkdir()
    real_config = pathlib.Path(__file__).parent.parent / "config" / "known_files.json"
    config.joinpath("known_files.json").write_text(real_config.read_text())
    return tmp_path / "data", config


class StubSource:
    """Serves the fixture sheets, with chosen file ids made to fail."""

    def __init__(self, failing: set[str] | None = None, listing_fails: bool = False):
        self.failing = failing or set()
        self.listing_fails = listing_fails
        self.tab_calls = 0

    def install(self, monkeypatch):
        monkeypatch.setattr(pipeline.fetch, "list_folder", self.list_folder)
        monkeypatch.setattr(pipeline.fetch, "fetch_csv", self.fetch_csv)
        monkeypatch.setattr(pipeline.fetch, "sheet_tab_names", self.tabs)
        return self

    def list_folder(self, folder_id):
        if self.listing_fails:
            raise fetch.FetchError("listing markup changed")
        # Only the four fixture sheets are listed; a pinned-but-unpopulated month is
        # fetched anyway, because the pinned set is the floor.
        return {
            fid: {"name": label, "modified_hint": "Sep 29"}
            for fid, (label, _) in REAL_SHEETS.items()
            if fid not in self.failing
        }

    def fetch_csv(self, file_id):
        if file_id in self.failing:
            raise fetch.FetchError(f"HTTP 404 for {file_id}")
        path = FIXTURE_DIR / f"{file_id}.csv"
        if not path.exists():
            # A pinned month Rowan has created but not yet populated — October 2026
            # appeared this way. There is no fixture because there is no data.
            raise fetch.FetchError(f"{file_id}: body is only 191 bytes")
        body = path.read_bytes()
        return fetch.FetchResult(
            body=body, status=200, content_type="text/csv",
            content_disposition="attachment; filename*=UTF-8''X - Crime Log.csv",
            fetched_at="2026-10-01T00:00:00+00:00",
            sha256=__import__("hashlib").sha256(body).hexdigest(), byte_length=len(body),
        )

    def tabs(self, file_id):
        self.tab_calls += 1
        return ["Crime Log"]


def test_full_run_ingests_everything(project, monkeypatch):
    data, config = project
    StubSource().install(monkeypatch)
    report = pipeline.run(data, config, today="2026-10-01")

    assert report["archive_rows"] == TOTAL_INCIDENTS
    assert report["merge"]["added"] == TOTAL_INCIDENTS
    assert not report["alarms"]


def test_pinned_but_unpopulated_month_is_pending_not_missing(project, monkeypatch):
    """Rowan creates each month's sheet before any incident is logged in it.

    That must not advance the removal ladder or raise an alarm: nothing is at risk for a
    file the archive has never held rows for.
    """
    data, config = project
    StubSource().install(monkeypatch)
    report = pipeline.run(data, config, today="2026-10-01")

    pending = [f for f, info in report["files"].items() if info["status"] == "pending"]
    assert pending, "the unpopulated month should be reported as pending"
    assert not report["alarms"]
    assert any("nothing is at risk" in w for w in report["warnings"])
    assert (data / "archive" / "incidents.csv").exists()
    assert (data / "raw" / "_runs" / "2026-10-01.json").exists()


def test_run_record_is_written_even_when_nothing_changes(project, monkeypatch):
    """The heartbeat keeps the scheduled workflow from being disabled for inactivity,
    and records that we checked on a given day and saw no change."""
    data, config = project
    StubSource().install(monkeypatch)
    pipeline.run(data, config, today="2026-10-01")
    report = pipeline.run(data, config, today="2026-10-02")

    assert report["merge"]["changed"] is False
    assert (data / "raw" / "_runs" / "2026-10-02.json").exists()
    # No second snapshot: identical content must not be stored twice.
    assert len(list((data / "raw" / AUGUST).glob("*.csv"))) == 1


def test_missing_file_takes_three_days_to_become_source_removed(project, monkeypatch):
    data, config = project
    StubSource().install(monkeypatch)
    pipeline.run(data, config, today="2026-10-01")

    gone = StubSource(failing={AUGUST}).install(monkeypatch)
    august_rows = REAL_SHEETS[AUGUST][1]

    for day in ("2026-10-02", "2026-10-03"):
        report = pipeline.run(data, config, today=day)
        assert report["merge"]["source_removed"] == 0, "one or two failures is not a deletion"
        assert report["archive_rows"] == TOTAL_INCIDENTS

    report = pipeline.run(data, config, today="2026-10-04")
    assert report["merge"]["source_removed"] == august_rows
    assert report["archive_rows"] == TOTAL_INCIDENTS, "nothing may be lost"
    assert any("treating the source file as removed" in a for a in report["alarms"])

    # Every field of every August row is still readable.
    rows = Archive(data).load()
    august = [r for r in rows.values() if r["source_file_id"] == AUGUST]
    assert len(august) == august_rows
    assert all(r["status"] == "source_removed" for r in august)
    assert all(r["narrative_raw"] for r in august)


def test_a_failing_file_never_touches_other_files_rows(project, monkeypatch):
    data, config = project
    StubSource().install(monkeypatch)
    pipeline.run(data, config, today="2026-10-01")

    StubSource(failing={AUGUST}).install(monkeypatch)
    report = pipeline.run(data, config, today="2026-10-02")

    rows = Archive(data).load()
    others = [r for r in rows.values() if r["source_file_id"] != AUGUST]
    assert all(r["status"] == "active" for r in others)
    assert report["merge"]["withdrawn"] == 0


def test_total_outage_refuses_to_diff(project, monkeypatch):
    """If every file fails, that is an outage — never a source that lost every record."""
    data, config = project
    StubSource().install(monkeypatch)
    pipeline.run(data, config, today="2026-10-01")
    before = (data / "archive" / "incidents.csv").read_bytes()

    StubSource(failing=set(REAL_SHEETS)).install(monkeypatch)
    with pytest.raises(pipeline.RunFailure, match="No file could be fetched"):
        pipeline.run(data, config, today="2026-10-02")

    assert (data / "archive" / "incidents.csv").read_bytes() == before


def test_listing_failure_still_fetches_the_pinned_floor(project, monkeypatch):
    """A broken scrape must degrade to 'no new files discovered', never to data loss."""
    data, config = project
    StubSource(listing_fails=True).install(monkeypatch)
    report = pipeline.run(data, config, today="2026-10-01")

    assert report["listing"]["status"] == "failed"
    assert any("Folder listing failed" in a for a in report["alarms"])
    assert report["archive_rows"] == TOTAL_INCIDENTS, "pinned ids are fetched regardless"


def test_file_reappearing_resets_the_ladder(project, monkeypatch):
    data, config = project
    StubSource().install(monkeypatch)
    pipeline.run(data, config, today="2026-10-01")

    StubSource(failing={AUGUST}).install(monkeypatch)
    pipeline.run(data, config, today="2026-10-02")

    StubSource().install(monkeypatch)
    report = pipeline.run(data, config, today="2026-10-03")

    manifest = json.loads((data / "raw" / "manifest.json").read_text())
    assert manifest["files"][AUGUST]["absent_count"] == 0
    assert manifest["files"][AUGUST]["status"] == "present"
    assert report["merge"]["source_removed"] == 0


def test_tab_census_runs_on_change_then_weekly(project, monkeypatch):
    data, config = project
    stub = StubSource().install(monkeypatch)
    pipeline.run(data, config, today="2026-10-01")
    assert stub.tab_calls == len(REAL_SHEETS), "first sight of each file is a change"

    pipeline.run(data, config, today="2026-10-02")
    assert stub.tab_calls == len(REAL_SHEETS), "unchanged files skip the expensive census"

    pipeline.run(data, config, today="2026-10-09")
    assert stub.tab_calls == 2 * len(REAL_SHEETS), "census runs again after a week"


def test_unexpected_second_tab_raises_an_alarm(project, monkeypatch):
    data, config = project
    stub = StubSource().install(monkeypatch)
    monkeypatch.setattr(pipeline.fetch, "sheet_tab_names", lambda fid: ["Crime Log", "Summary"])
    report = pipeline.run(data, config, today="2026-10-01")
    assert any("NOT being archived" in a for a in report["alarms"])
