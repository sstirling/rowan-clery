"""End-to-end pipeline tests with the network stubbed out.

These exercise the paths that only appear when fetching really fails: the file-level
removal ladder, the refusal to proceed when everything is down, and the heartbeat that
keeps the scheduled workflow alive.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from rowan_clery import fetch, parse, pipeline
from rowan_clery.archive import Archive
from tests.conftest import CURRENT_SHEETS, FIXTURE_DIR, REAL_SHEETS, TOTAL_INCIDENTS

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

    #: Pinned months the stub serves as created-but-empty. Named explicitly rather than
    #: inferred from "no fixture on disk": the month in progress now HAS a fixture, for
    #: the vocabulary-coverage tests, and the unpopulated-month case must keep working
    #: regardless of which fixtures happen to exist.
    UNPOPULATED = frozenset(CURRENT_SHEETS)

    def __init__(
        self,
        failing: set[str] | None = None,
        listing_fails: bool = False,
        unpopulated: set[str] | None = None,
    ):
        self.failing = failing or set()
        self.listing_fails = listing_fails
        self.unpopulated = frozenset(self.UNPOPULATED if unpopulated is None else unpopulated)
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
        if file_id in self.unpopulated or not path.exists():
            # A pinned month Rowan has created but not yet populated — October 2026
            # appeared this way, as a 191-byte file that fetch_csv rejects as too small.
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


#: A file id Rowan reuses mid-test. Five rows, because the corpus brake needs a drop of
#: more than MAX_CORPUS_DROP_ROWS before it fires and this test is about the ladder, not
#: the brake. tests/test_archive.py covers the brake on the real 23-row July fixture.
REUSED = "1ReUsEdFiLeIdFoRpIpElInEtEsTiNgOnLy00000000"

_SHEET_HEAD = (
    b"Case Number,Date/Time Reported,Date/Time Occurred,Nature,Incident Narrative,Campus,Location,Disposition\r\n"
    b"RUPD 26-030001,10/1/26 1:00,10/1/26 1:00,Theft,Student reported a stolen laptop.,Glassboro,Mimosa Hall,Open/Active\r\n"
    b"RUPD 26-030002,10/2/26 2:00,10/2/26 2:00,Criminal mischief,Student reported a damaged door.,Glassboro,Holly Pointe Commons,Open/Active\r\n"
    b"RUPD 26-030003,10/3/26 3:00,10/3/26 3:00,Harassment,Student reported harassing messages.,Glassboro,Rowan Blvd.,Closed\r\n"
    b"RUPD 26-030004,10/4/26 4:00,10/4/26 4:00,Trespassing,Non-student found in a residence hall.,Glassboro,Chestnut Hall,Closed\r\n"
    b"RUPD 26-030005,10/5/26 5:00,10/5/26 5:00,Simple Assault,Students reported a fight.,Glassboro,Student Center,Open/Active\r\n"
)
OCTOBER_BODY = b'"Rowan University Daily Crime Log, October 2026",,,,,,,\r\n' + _SHEET_HEAD
#: Same container, same rows, new banner — the shape of what Rowan did to July's sheet,
#: minus the deletion, so the only thing that changes is which month the file claims.
NOVEMBER_BODY = b'"Rowan University Daily Crime Log, November 2026",,,,,,,\r\n' + (
    b"Case Number,Date/Time Reported,Date/Time Occurred,Nature,Incident Narrative,Campus,Location,Disposition\r\n"
    b"RUPD 26-036207,11/1/26 0:24,11/1/26 0:24,Trespassing,Non-student warned.,Glassboro,Holly Pointe Commons,Closed\r\n"
    b"RUPD 26-036301,11/2/26 9:10,11/2/26 8:55,Theft,Student reported a stolen bicycle.,Glassboro,Mimosa Hall,Open/Active\r\n"
)


class RepurposingSource(StubSource):
    """Serves one extra file whose banner month flips partway through the test."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.body = OCTOBER_BODY

    def list_folder(self, folder_id):
        listing = super().list_folder(folder_id)
        listing[REUSED] = {"name": "October 2026 Daily Crime Log", "modified_hint": "Nov 2"}
        return listing

    def fetch_csv(self, file_id):
        if file_id != REUSED:
            return super().fetch_csv(file_id)
        import hashlib
        return fetch.FetchResult(
            body=self.body, status=200, content_type="text/csv",
            content_disposition="attachment; filename*=UTF-8''X - Crime Log.csv",
            fetched_at="2026-10-01T00:00:00+00:00",
            sha256=hashlib.sha256(self.body).hexdigest(), byte_length=len(self.body),
        )


def test_a_reused_file_retires_its_old_month_after_two_confirmations(project, monkeypatch):
    """The whole point: CI fixes this itself, so no merge can revert the fix.

    This was hand-applied twice and lost twice — once to an uncommitted working tree and
    once to a merge that resolved `data/archive/incidents.csv` in favour of CI's own
    regeneration of it. A correction that only exists as a committed data file cannot
    survive a pipeline that rewrites that file twice a day. This one is recomputed from
    the banner on every run, so losing it costs at most two runs.
    """
    data, config = project
    source = RepurposingSource().install(monkeypatch)

    pipeline.run(data, config, today="2026-11-01")
    archive = Archive(data)
    october_uids = {
        uid for uid, row in archive.load().items() if row.get("source_file_id") == REUSED
    }
    assert len(october_uids) == 5
    assert all(archive.load()[uid]["source_month"] == "October 2026" for uid in october_uids)

    # Rowan renames the container and rewrites the banner.
    source.body = NOVEMBER_BODY

    # Run one of the ladder: a warning, and the rows are left strictly alone.
    report = pipeline.run(data, config, today="2026-11-02")
    assert any("confirmation 1 of 2" in w for w in report["warnings"]), report["warnings"]
    assert not any(REUSED in a for a in report["alarms"])
    rows = archive.load()
    assert all(rows[uid]["status"] == "active" for uid in october_uids)
    # No quarantine: the old month was never accountable for the new fetch.
    assert REUSED not in report["merge"]["quarantined"]

    # Run two: confirmed, so the month retires and says why.
    report = pipeline.run(data, config, today="2026-11-03")
    assert any("Retiring those rows as source_removed" in a for a in report["alarms"]), report["alarms"]
    rows = archive.load()
    assert all(rows[uid]["status"] == "source_removed" for uid in october_uids)
    assert october_uids <= set(rows), "every row of the replaced month is preserved"
    assert all(rows[uid]["nature_raw"] for uid in october_uids), "fields preserved in full"

    # Never withdrawn: that status is reserved for a row pulled from a sheet Rowan still
    # publishes, and this is a sheet that stopped existing.
    assert report["merge"]["withdrawn"] == 0
    events = [json.loads(l) for l in (data / "archive" / "changelog.jsonl").read_text().splitlines()]
    retired = [e for e in events if e.get("removal_mechanism") == "file_repurposed"]
    assert len(retired) == 5

    # Run three: settled. Nothing is re-logged and the alarm stops.
    report = pipeline.run(data, config, today="2026-11-04")
    assert not any("Retiring those rows" in a for a in report["alarms"])
    assert report["merge"]["source_removed"] == 0


def test_an_unreadable_banner_never_retires_a_month(project, monkeypatch):
    """`parse.source_month()` returns "" when the banner does not match its pattern.

    That is Rowan reformatting the line, not changing which month the file holds. Without
    a guard, "" compares unequal to every archived month, so every row in the file looks
    like it belongs to a month the file has stopped holding — and two runs later the
    whole file retires. This is the one way the ladder could destroy a month on its own,
    so it gets its own test rather than relying on the confirmation count.
    """
    data, config = project
    source = RepurposingSource().install(monkeypatch)
    pipeline.run(data, config, today="2026-11-01")
    archive = Archive(data)
    uids = {uid for uid, row in archive.load().items() if row.get("source_file_id") == REUSED}
    assert len(uids) == 5

    # Same rows, same month, banner rewritten into a shape source_month cannot read.
    source.body = b'"Rowan University Crime Log for the month of October 2026",,,,,,,\r\n' + _SHEET_HEAD
    assert parse.source_month(source.body) == "", "fixture no longer exercises the guard"

    for day in ("2026-11-02", "2026-11-03", "2026-11-04"):
        report = pipeline.run(data, config, today=day)
        assert not any("Retiring those rows" in a for a in report["alarms"]), day
        rows = archive.load()
        assert all(rows[uid]["status"] == "active" for uid in uids), f"{day}: a month was retired"
    assert any("did not parse as a month label" in w for w in report["warnings"])
