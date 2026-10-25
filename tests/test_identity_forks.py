"""What a superseded row must and must not be counted in.

Marking the stale half of an identity fork `superseded` is only half the fix. Nothing in
the build or on the page excluded superseded rows from any aggregation, so a corrected
incident was still counted twice in every offense bar, month bar and school-year total —
which was the whole harm. These tests pin the line: the row stays in the archive and in
the payload, visible under its own case number, and counts for nothing.

Built against the real archive copied into a tmp directory, so the build's own output
never lands in the repo.
"""

from __future__ import annotations

import pathlib
import shutil

import pytest

from rowan_clery import archive as arch
from rowan_clery import build, parse

ROOT = pathlib.Path(__file__).parent.parent
CONFIG = ROOT / "config"

SEPT = "1HULCgv9mk7XMkfC2DKkBaOUm5rA00aVfO83lU9489p0"


@pytest.fixture
def forked(tmp_path, all_sheets):
    """An archive holding one incident republished under an amended case number.

    Returns (payload, old_uid, new_uid, category). The pair is synthesised through the
    real merge rather than hand-written, so the fields under test are the ones the
    pipeline actually produces.
    """
    parsed = {fid: parse.parse_and_key(body, fid) for fid, body in all_sheets.items()}
    archive = arch.Archive(tmp_path)

    rows, _, _ = archive.merge(parsed, set(parsed), {}, today="2026-10-01")
    archive.write(rows)

    original = parsed[SEPT][7]
    old_uid = original["incident_uid"]
    amended = dict(original)
    amended["Case Number"] = original["Case Number"] + "/ CSA 99999"
    amended["incident_uid"] = parse.incident_uid(amended["Case Number"], amended["Date/Time Reported"])
    amended["content_hash"] = parse.content_hash(amended)

    observed = dict(parsed) | {SEPT: parsed[SEPT][:7] + [amended] + parsed[SEPT][8:]}
    rows, events, report = archive.merge(observed, set(parsed), {}, today="2026-10-02")
    archive.write(rows)
    archive.append_changelog(events)
    assert report.superseded == 1, "fixture must actually produce a supersession"

    raw = ROOT / "data" / "raw"
    if (raw / "manifest.json").exists():
        (tmp_path / "raw").mkdir(exist_ok=True)
        shutil.copy(raw / "manifest.json", tmp_path / "raw" / "manifest.json")

    payload = build.build(tmp_path, CONFIG, today="2026-10-03")
    return payload, old_uid, amended["incident_uid"], original["Nature"]


def test_the_superseded_row_is_still_in_the_payload(forked):
    """Nothing is hidden. The amendment is part of the record, not an embarrassment.

    A reader who looks up the old case number has to find it, and find out what happened
    to it, or the archive has quietly rewritten history to tidy up its own counts.
    """
    payload, old_uid, new_uid, _ = forked
    by_uid = {i["uid"]: i for i in payload["incidents"]}

    assert old_uid in by_uid
    assert by_uid[old_uid]["status"] == "superseded"
    assert by_uid[new_uid]["status"] == "active"


def test_a_superseded_row_counts_for_nothing(forked):
    """The double count, which is the harm this whole change exists to stop."""
    payload, old_uid, _, _ = forked
    counts = payload["counts"]

    # It is archived, and it is not a distinct incident.
    assert counts["total_archived"] == counts["distinct_incidents"] + 1
    assert counts["superseded"] == 1

    # Not published, and not "no longer published" either — it was replaced, not removed.
    assert counts["currently_published"] + counts["no_longer_published"] == counts["distinct_incidents"]
    assert counts["withdrawn"] == 0

    # Excluded from the binning totals, which the page uses to say what it leaves out.
    assert payload["binning"]["total"] == counts["distinct_incidents"]


def test_a_superseded_row_does_not_inflate_its_offense_or_its_month(forked, all_sheets):
    """The counts a reader actually reads: the offense bars and the month bars."""
    payload, old_uid, _, _ = forked
    by_uid = {i["uid"]: i for i in payload["incidents"]}
    stale = by_uid[old_uid]

    facet = {f["value"]: f["count"] for f in payload["facets"]["categories"]}
    for category in stale["categories"]:
        charted = sum(
            1
            for i in payload["incidents"]
            if i["status"] != "superseded" and category in i["categories"]
        )
        assert facet[category] == charted, f"{category} counts the superseded row"

    months = {f["value"]: f["count"] for f in payload["facets"]["months"]}
    if stale["month"]:
        charted = sum(
            1 for i in payload["incidents"] if i["status"] != "superseded" and i["month"] == stale["month"]
        )
        assert months[stale["month"]] == charted

    # School-year totals feed the scope selector, so they have to agree too.
    years = {y["year"]: y["incidents"] for y in payload["school_years"]}
    assert sum(years.values()) == sum(
        1 for i in payload["incidents"] if i["status"] != "superseded" and i["school_year"]
    )


def test_the_status_facet_still_offers_superseded(forked):
    """The one facet that must count it.

    Every other filter counts what the charts draw. `statuses` is how a reader reaches a
    superseded row at all, so a status the archive holds has to appear in its own
    dropdown — otherwise the row is in the payload but unreachable.
    """
    payload, _, _, _ = forked
    statuses = {f["value"]: f["count"] for f in payload["facets"]["statuses"]}
    assert statuses.get("superseded") == 1


def test_the_supersession_is_in_the_change_feed(forked):
    """A correction the reader cannot see is not a correction."""
    payload, old_uid, new_uid, _ = forked
    events = [e for e in payload["changelog"] if e["change_type"] == "superseded_identity"]

    assert len(events) == 1
    assert events[0]["incident_uid"] == old_uid
    assert events[0]["superseded_by"] == new_uid
    # The feed renders old -> new from these two keys; empty strings would render blank.
    assert events[0]["old_case_number"] and events[0]["new_case_number"]
