"""Archive merge tests.

These are the tests that matter. The project's promise is that no observed record is
ever lost and that a fetch failure never looks like a deletion, so most of what follows
is an attempt to break exactly those two properties.
"""

from __future__ import annotations

import json

import pytest

from rowan_clery import archive as arch
from rowan_clery.archive import Archive
from rowan_clery import parse
from tests.conftest import REAL_SHEETS

AUGUST = "1Ms5gjJX_-vnA4wUaTW-z60Hd98guINjRU5R-e5n58Ts"
SEPT = "1HULCgv9mk7XMkfC2DKkBaOUm5rA00aVfO83lU9489p0"


@pytest.fixture
def archive(tmp_path):
    return arch.Archive(tmp_path)


@pytest.fixture
def parsed(all_sheets):
    return {fid: parse.parse_and_key(body, fid) for fid, body in all_sheets.items()}


def commit(archive, observed, fetched_ok, today, file_meta=None):
    """Run one full merge cycle and persist it, as the real pipeline does."""
    rows, events, report = archive.merge(observed, fetched_ok, file_meta or {}, today=today)
    archive.write(rows)
    archive.append_changelog(events)
    return rows, events, report


# ---- baseline -----------------------------------------------------------------


def test_first_run_ingests_everything(archive, parsed):
    rows, events, report = commit(archive, parsed, set(parsed), "2026-10-01")
    assert len(rows) == 186
    assert report.added == 186
    assert all(r["status"] == "active" for r in rows.values())
    assert all(r["first_seen_by_archive"] == "2026-10-01" for r in rows.values())
    assert sum(1 for e in events if e["change_type"] == "added") == 186


def test_second_identical_run_is_a_no_op(archive, parsed):
    commit(archive, parsed, set(parsed), "2026-10-01")
    before = archive.incidents_path.read_bytes()

    rows, events, report = commit(archive, parsed, set(parsed), "2026-10-02")

    assert events == []
    assert report.changed is False
    assert report.unchanged == 186
    # Only last_verified moves, so the file is not byte-identical; the record set is.
    assert len(rows) == 186
    after = archive.incidents_path.read_bytes()
    assert before.count(b"\n") == after.count(b"\n")


# ---- amendment ----------------------------------------------------------------


def test_amendment_keeps_identity_and_records_old_value(archive, parsed):
    commit(archive, parsed, set(parsed), "2026-10-01")

    amended = {fid: [dict(r) for r in recs] for fid, recs in parsed.items()}
    target = amended[AUGUST][0]
    uid, old_disposition = target["incident_uid"], target["Disposition"]
    target["Disposition"] = "Closed; Subject arrested; Disposition updated"
    target["content_hash"] = parse.content_hash(target)

    rows, events, report = commit(archive, amended, set(parsed), "2026-10-02")

    assert report.amended == 1
    assert len(rows) == 186, "an amendment must not create a second record"
    assert rows[uid]["revision"] == "2"
    assert rows[uid]["disposition_raw"] == "Closed; Subject arrested; Disposition updated"

    change = next(e for e in events if e["change_type"] == "amended")
    assert change["field"] == "disposition_raw"
    assert change["old"] == old_disposition
    assert change["new"] == "Closed; Subject arrested; Disposition updated"


def test_nature_escalation_is_captured(archive, parsed):
    """The newsworthy case: an offense reclassified upward after publication."""
    commit(archive, parsed, set(parsed), "2026-10-01")

    amended = {fid: [dict(r) for r in recs] for fid, recs in parsed.items()}
    target = amended[SEPT][0]
    target["Nature"] = "Simple Assault; Nature updated; Aggravated Assault-Strangulation"
    target["content_hash"] = parse.content_hash(target)

    _, events, _ = commit(archive, amended, set(parsed), "2026-10-02")
    change = next(e for e in events if e.get("field") == "nature_raw")
    assert "Aggravated Assault-Strangulation" in change["new"]
    assert change["old"] != change["new"]


# ---- the core guarantee: nothing is ever lost ---------------------------------


def test_deleted_row_is_preserved_and_confirmed_over_three_days(archive, parsed):
    commit(archive, parsed, set(parsed), "2026-10-01")

    reduced = {fid: list(recs) for fid, recs in parsed.items()}
    removed = reduced[SEPT].pop(5)
    uid = removed["incident_uid"]

    rows, events, report = commit(archive, reduced, set(parsed), "2026-10-02")
    assert rows[uid]["status"] == "missing"
    assert report.withdrawn == 0, "one absence is not a deletion"

    rows, _, _ = commit(archive, reduced, set(parsed), "2026-10-03")
    assert rows[uid]["status"] == "missing"

    rows, events, report = commit(archive, reduced, set(parsed), "2026-10-04")
    assert rows[uid]["status"] == "withdrawn"
    assert report.withdrawn == 1

    # The whole point: the record and its last known values survive intact.
    assert len(rows) == 186
    assert rows[uid]["narrative_raw"] == removed["Incident Narrative"]
    assert rows[uid]["disposition_raw"] == removed["Disposition"]
    assert rows[uid]["missing_since"] == "2026-10-02"

    event = next(e for e in events if e["change_type"] == "withdrawn")
    assert event["case_number"] == removed["Case Number"]
    assert event["last_known_disposition"] == removed["Disposition"]


def test_row_that_returns_is_restored_but_keeps_its_history(archive, parsed):
    commit(archive, parsed, set(parsed), "2026-10-01")
    reduced = {fid: list(recs) for fid, recs in parsed.items()}
    uid = reduced[SEPT].pop(5)["incident_uid"]

    commit(archive, reduced, set(parsed), "2026-10-02")
    rows, events, report = commit(archive, parsed, set(parsed), "2026-10-03")

    assert rows[uid]["status"] == "active"
    assert report.reappeared == 1
    assert "was_missing" in rows[uid]["flags"], "a disappearance must stay on the record"
    assert any(e["change_type"] == "reappeared" for e in events)


def test_whole_file_deleted_preserves_every_row(archive, parsed):
    """The scenario the project exists for: the university removes a month."""
    commit(archive, parsed, set(parsed), "2026-10-01")

    remaining = {fid: recs for fid, recs in parsed.items() if fid != AUGUST}
    august_uids = {r["incident_uid"] for r in parsed[AUGUST]}

    # The file is simply gone from the listing, so it is never fetched. Its rows must
    # not be touched at all — we have no successful observation saying they are absent.
    for day in ("2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05"):
        rows, _, _ = commit(archive, remaining, set(remaining), day)

    assert len(rows) == 186
    assert all(rows[uid]["status"] == "active" for uid in august_uids), (
        "rows from an unfetched file must never be marked missing — absence of the file "
        "is not evidence of absence of its rows"
    )
    assert all(rows[uid]["narrative_raw"] for uid in august_uids)


# ---- fetch failures must never look like deletions ----------------------------


def test_unfetched_file_never_advances_the_ladder(archive, parsed):
    commit(archive, parsed, set(parsed), "2026-10-01")
    uids = {r["incident_uid"] for r in parsed[SEPT]}

    # September fetch failed: it contributes no observations and is not in fetched_ok.
    without = {fid: recs for fid, recs in parsed.items() if fid != SEPT}
    rows, events, report = commit(archive, without, set(parsed) - {SEPT}, "2026-10-02")

    assert report.missing == 0 and report.withdrawn == 0
    assert all(rows[uid]["status"] == "active" for uid in uids)
    assert all(rows[uid]["missing_count"] == "0" for uid in uids)
    assert events == []


def test_empty_but_valid_snapshot_is_quarantined(archive, parsed):
    """A file that parses but yields nothing must not empty the archive."""
    commit(archive, parsed, set(parsed), "2026-10-01")
    uids = {r["incident_uid"] for r in parsed[SEPT]}

    emptied = dict(parsed) | {SEPT: []}
    rows, _, report = commit(archive, emptied, set(parsed), "2026-10-02")

    assert SEPT in report.quarantined
    assert all(rows[uid]["status"] == "active" for uid in uids)
    assert len(rows) == 186


def test_mass_removal_is_quarantined_not_applied(archive, parsed):
    commit(archive, parsed, set(parsed), "2026-10-01")
    uids = {r["incident_uid"] for r in parsed[SEPT]}

    gutted = dict(parsed) | {SEPT: parsed[SEPT][:50]}  # 107 -> 50
    rows, events, report = commit(archive, gutted, set(parsed), "2026-10-02")

    assert SEPT in report.quarantined
    assert report.missing == 0 and report.withdrawn == 0
    assert all(rows[uid]["status"] == "active" for uid in uids), "quarantine must apply no mutations"
    assert events == []
    assert any("quarantined" in w for w in report.warnings)


def test_small_drop_is_allowed_through_the_ladder(archive, parsed):
    """One or two missing rows is a routine correction, not a catastrophe."""
    commit(archive, parsed, set(parsed), "2026-10-01")
    reduced = dict(parsed) | {SEPT: parsed[SEPT][:-2]}

    rows, _, report = commit(archive, reduced, set(parsed), "2026-10-02")
    assert SEPT not in report.quarantined
    assert report.missing == 2


# ---- re-upload under a new file id --------------------------------------------


def test_reupload_under_new_file_id_is_a_relocation_not_a_mass_deletion(archive, parsed, all_sheets):
    """Deleting a sheet and re-uploading it gives it a new id. Identity must survive."""
    commit(archive, parsed, set(parsed), "2026-10-01")

    new_id = "1reuploadedAugustWithABrandNewFileId00000"
    reuploaded = {fid: recs for fid, recs in parsed.items() if fid != AUGUST}
    reuploaded[new_id] = parse.parse_and_key(all_sheets[AUGUST], new_id)

    rows, events, report = commit(archive, reuploaded, set(reuploaded), "2026-10-02")

    assert len(rows) == 186, "a re-upload must not duplicate every row"
    assert report.added == 0, "re-uploaded rows are the same incidents, not new ones"
    assert report.relocated == REAL_SHEETS[AUGUST][1]
    assert report.withdrawn == 0 and report.missing == 0
    assert all(r["status"] == "active" for r in rows.values())
    assert all(rows[r["incident_uid"]]["source_file_id"] == new_id for r in reuploaded[new_id])


# ---- invariants ---------------------------------------------------------------


def test_integrity_error_if_a_uid_would_disappear(archive, parsed):
    commit(archive, parsed, set(parsed), "2026-10-01")
    existing = archive.load()
    truncated = dict(list(existing.items())[:100])
    with pytest.raises(arch.ArchiveIntegrityError, match="append-only"):
        archive._assert_invariants(existing, truncated)


def test_integrity_error_if_identity_fields_are_rewritten(archive, parsed):
    commit(archive, parsed, set(parsed), "2026-10-01")
    existing = archive.load()
    mutated = {uid: dict(row) for uid, row in existing.items()}
    victim = next(iter(mutated))
    mutated[victim]["case_number_norm"] = "RUPD 99-999999"
    with pytest.raises(arch.ArchiveIntegrityError, match="case number changed"):
        archive._assert_invariants(existing, mutated)


def test_integrity_error_if_first_seen_is_rewritten(archive, parsed):
    commit(archive, parsed, set(parsed), "2026-10-01")
    existing = archive.load()
    mutated = {uid: dict(row) for uid, row in existing.items()}
    mutated[next(iter(mutated))]["first_seen_by_archive"] = "2026-01-01"
    with pytest.raises(arch.ArchiveIntegrityError, match="first_seen_by_archive"):
        archive._assert_invariants(existing, mutated)


def test_archive_round_trips_through_csv(archive, parsed):
    """Reloading from disk must reproduce the record set exactly."""
    rows, _, _ = commit(archive, parsed, set(parsed), "2026-10-01")
    reloaded = archive.load()
    assert set(reloaded) == set(rows)
    for uid in rows:
        for column in ("case_number_raw", "narrative_raw", "disposition_raw", "content_hash"):
            assert reloaded[uid][column] == rows[uid][column]


# ---- a whole month removed from the source ------------------------------------


def test_confirmed_file_removal_preserves_rows_and_is_distinct_from_withdrawal(archive, parsed):
    """Rowan deleting an entire monthly sheet is the headline scenario.

    Every field must survive, and the event must be distinguishable from an individual
    row being quietly dropped out of a sheet that still exists.
    """
    commit(archive, parsed, set(parsed), "2026-10-01")
    august_uids = {r["incident_uid"] for r in parsed[AUGUST]}
    sample = parsed[AUGUST][0]

    remaining = {fid: recs for fid, recs in parsed.items() if fid != AUGUST}
    rows, events, report = archive.merge(
        remaining, set(remaining), {}, removed_files={AUGUST}, today="2026-10-05"
    )
    archive.write(rows)
    archive.append_changelog(events)

    assert len(rows) == 186, "no record may be lost when a month is deleted"
    assert report.source_removed == REAL_SHEETS[AUGUST][1]
    assert report.withdrawn == 0, "a deleted file is not the same event as a withdrawn row"
    assert all(rows[uid]["status"] == "source_removed" for uid in august_uids)

    # The evidence has to remain fully readable after the source is gone.
    preserved = rows[sample["incident_uid"]]
    assert preserved["narrative_raw"] == sample["Incident Narrative"]
    assert preserved["disposition_raw"] == sample["Disposition"]
    assert preserved["case_number_raw"] == sample["Case Number"]

    event = next(e for e in events if e["change_type"] == "source_removed")
    assert event["source_file_id"] == AUGUST
    assert event["last_known_disposition"]


def test_file_removal_is_logged_once_not_every_day(archive, parsed):
    commit(archive, parsed, set(parsed), "2026-10-01")
    remaining = {fid: recs for fid, recs in parsed.items() if fid != AUGUST}

    for day in ("2026-10-05", "2026-10-06", "2026-10-07"):
        rows, events, report = archive.merge(remaining, set(remaining), {}, removed_files={AUGUST}, today=day)
        archive.write(rows)
        archive.append_changelog(events)
        if day != "2026-10-05":
            assert report.source_removed == 0, "a settled removal must not re-log daily"
            assert events == []


def test_restored_file_reactivates_its_rows(archive, parsed, all_sheets):
    """If Rowan puts a deleted month back, the rows must come back to life."""
    commit(archive, parsed, set(parsed), "2026-10-01")
    remaining = {fid: recs for fid, recs in parsed.items() if fid != AUGUST}
    rows, events, _ = archive.merge(remaining, set(remaining), {}, removed_files={AUGUST}, today="2026-10-05")
    archive.write(rows)
    archive.append_changelog(events)

    rows, events, report = commit(archive, parsed, set(parsed), "2026-10-06")
    august_uids = {r["incident_uid"] for r in parsed[AUGUST]}
    assert all(rows[uid]["status"] == "active" for uid in august_uids)
    assert report.reappeared == 0 or all("was_missing" in rows[uid]["flags"] for uid in august_uids)


def test_read_changelog_drops_exactly_duplicated_events(tmp_path):
    """A git merge of two branches that both ran the same day duplicates log lines.

    `changelog.jsonl` is an append-only text file, so when a local run and the scheduled
    run both record the same day's events and the branches are merged, git concatenates
    both copies. That really happened: all 17 events from 2026-10-07 (15 added, 2
    amended) appeared twice, and the page showed every amendment twice.

    `incidents.csv` is immune because it is keyed by uid. The log is not, so it is
    deduplicated on READ — the file itself is evidence and is never rewritten.
    """
    data = tmp_path / "data"
    (data / "archive").mkdir(parents=True)
    event = {"observed_date": "2026-10-07", "incident_uid": "abc123",
             "change_type": "amended", "field": "disposition_raw",
             "old": "Open/Active", "new": "Closed"}
    other = dict(event, incident_uid="def456", new="Open/Active; Closed")
    lines = [json.dumps(event), json.dumps(other), json.dumps(event)]
    (data / "archive" / "changelog.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    entries = Archive(data).read_changelog()
    assert len(entries) == 2, "the repeated event should be read once"
    assert [e["incident_uid"] for e in entries] == ["abc123", "def456"], "order is preserved"


def test_read_changelog_keeps_genuinely_different_events(tmp_path):
    """Two amendments to the same field on the same day are two events, not a duplicate."""
    data = tmp_path / "data"
    (data / "archive").mkdir(parents=True)
    first = {"observed_date": "2026-10-07", "incident_uid": "abc123",
             "change_type": "amended", "field": "disposition_raw",
             "old": "Open/Active", "new": "Closed"}
    second = dict(first, old="Closed", new="Open/Active; Closed; Reopened")
    (data / "archive" / "changelog.jsonl").write_text(
        json.dumps(first) + "\n" + json.dumps(second) + "\n", encoding="utf-8")

    assert len(Archive(data).read_changelog()) == 2
