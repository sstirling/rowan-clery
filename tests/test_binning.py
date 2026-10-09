"""Checks on counting incidents by when they occurred rather than when they were logged.

The site defaults to binning the month-to-month charts on the date of occurrence. That
is the honest answer to "when was there crime", but the column is messier than the
reported date and it is not complete: Glassboro police report on a median lag of about
two weeks, so a month's count keeps rising after the month ends.

Neither of those is a reason to avoid the column. They are reasons the page has to be
able to say exactly what it left out — which is what these tests pin down. The one thing
that must never happen is an incident disappearing from both the chart and the count of
what is missing from it.

Built against the real archive, copied into a tmp directory so the build's own output
never lands in the repo.
"""

from __future__ import annotations

import pathlib
import shutil

import pytest

from rowan_clery import build, normalize

ROOT = pathlib.Path(__file__).parent.parent
CONFIG = ROOT / "config"

#: Precisions that cannot name a month, so can never be charted.
UNPLACEABLE = {"year", "unknown", "invalid"}


@pytest.fixture(scope="module")
def payload(tmp_path_factory):
    """The real payload, built in a scratch directory.

    `build()` writes data/processed/ beside the archive it reads, so it is pointed at a
    copy. Module-scoped because the build walks the whole archive.
    """
    data = tmp_path_factory.mktemp("data")
    shutil.copytree(ROOT / "data" / "archive", data / "archive")
    raw = ROOT / "data" / "raw"
    # Optional inputs: present in the repo, but build() degrades without them, and the
    # binning math does not depend on either.
    if (raw / "manifest.json").exists():
        (data / "raw").mkdir(exist_ok=True)
        shutil.copy(raw / "manifest.json", data / "raw" / "manifest.json")
    return build.build(data, CONFIG, today="2026-10-09")


@pytest.fixture(scope="module")
def incidents(payload):
    return payload["incidents"]


# ---- nothing may vanish --------------------------------------------------------


def test_every_incident_is_either_charted_or_counted_as_missing(payload, incidents):
    """The arithmetic the page's note rests on.

    If these ever fail to add up, the chart and the sentence explaining it have drifted
    apart, and the page is quietly undercounting with a note that says otherwise.
    """
    b = payload["binning"]
    assert b["total"] == len(incidents)
    assert b["shown"] + b["excluded_no_date"] + b["excluded_before_window"] == b["total"]


def test_an_excluded_incident_always_carries_its_reason(incidents):
    for i in incidents:
        if i["occurred_month_key"] is None:
            assert i["occurred_excluded"] in ("no_date", "before_window"), i["case_number"]
        else:
            assert i["occurred_excluded"] is None, i["case_number"]


def test_shown_count_matches_the_incidents_that_have_a_bin(payload, incidents):
    assert payload["binning"]["shown"] == sum(1 for i in incidents if i["occurred_month_key"])


# ---- the window ----------------------------------------------------------------


def test_nothing_before_the_window_is_charted(incidents):
    """June 2026 is the first sheet Rowan published in this format.

    An occurred date before it is a late report of something from a month the log never
    covered. Charting it would plant a one-incident bar in empty history.
    """
    for i in incidents:
        if i["occurred_month_key"]:
            assert i["occurred_month_key"] >= build.OCCURRED_WINDOW_START, i["case_number"]


def test_before_window_rows_are_real_dates_not_junk(incidents):
    """`before_window` and `no_date` are different findings and must not be conflated.

    A row excluded for falling outside the window has a perfectly good date; one
    excluded as `no_date` does not. Collapsing them would misreport both in the note.
    """
    outside = [i for i in incidents if i["occurred_excluded"] == "before_window"]
    assert outside, "expected at least one late report from before June 2026"
    for i in outside:
        assert i["occurred"]["precision"] not in UNPLACEABLE
        assert str(i["occurred"]["value"])[:7] < build.OCCURRED_WINDOW_START


def test_a_date_with_no_month_is_never_charted(incidents):
    """"2021 Unknown" is worth reporting and impossible to place in a month.

    Year-only precision is the trap: it parses, it has a value, and assigning it to a
    month would invent one the source never gave.
    """
    for i in incidents:
        if i["occurred"]["precision"] in UNPLACEABLE:
            assert i["occurred_month_key"] is None, i["case_number"]
            assert i["occurred_excluded"] == "no_date", i["case_number"]


# ---- the derived fields agree ---------------------------------------------------


def test_occurred_label_and_school_year_follow_the_occurred_key(incidents):
    for i in incidents:
        key = i["occurred_month_key"]
        if not key:
            assert i["occurred_month"] is None
            assert i["occurred_school_year"] is None
            continue
        assert i["occurred_month"] == build.month_label(key)
        assert i["occurred_school_year"] == build.school_year(key)
        # The label has to round-trip, or the chart's axis and its tooltips disagree.
        assert build.month_key(i["occurred_month"]) == key


def test_the_two_school_year_groupings_each_add_up(payload, incidents):
    by_reported = sum(y["incidents"] for y in payload["school_years"])
    by_occurred = sum(y["incidents"] for y in payload["school_years_occurred"])
    assert by_reported == sum(1 for i in incidents if i["school_year"])
    assert by_occurred == payload["binning"]["shown"]


def test_occurred_grouping_never_claims_a_month_outside_its_academic_year(payload):
    """The reason the scope selector follows the binning.

    A scope whose months come from one binning while its bars come from the other can
    draw a bar outside its own August-to-July window.
    """
    for year in payload["school_years_occurred"]:
        for month in year["months"]:
            assert build.school_year(month) == year["year"], (year["year"], month)


# ---- the behaviour the change exists for ----------------------------------------


def test_a_late_reported_incident_bins_to_the_month_it_happened(incidents):
    """The whole point: Glassboro's September incidents belong to September.

    Asserted as a population rather than a case number, which Rowan may amend.
    """
    moved = [
        i for i in incidents
        if i["occurred_month_key"] and i["month_key"] and i["occurred_month_key"] < i["month_key"]
    ]
    assert moved, "expected incidents reported in a later month than they occurred"
    for i in moved:
        assert i["occurred_month"] != i["month"]
        assert i["occurred_month_key"] == str(i["occurred"]["value"])[:7]


def test_glassboro_lag_is_reported_and_campus_police_is_not_inflated(payload):
    """The note quotes this median as the reason the newest month reads short."""
    lags = payload["binning"]["lag_median_days"]
    assert "GPD" in lags, "the note needs Glassboro's median lag"
    assert lags["GPD"] > 1, "a sub-day median would contradict the premise for this view"
    if "RUPD" in lags:
        assert lags["GPD"] > lags["RUPD"]


def test_lag_medians_are_only_published_for_a_real_sample(payload, incidents):
    counts: dict[str, int] = {}
    for i in incidents:
        if i["reporting_lag_hours"] is None or i["reporting_lag_hours"] < 0:
            continue
        for agency in i["agencies"] or ["(none)"]:
            counts[agency] = counts.get(agency, 0) + 1
    for agency in payload["binning"]["lag_median_days"]:
        assert counts.get(agency, 0) >= build.LAG_MIN_SAMPLE, agency
        assert agency != "(none)"


# ---- the payload the page is handed ---------------------------------------------


def test_the_page_is_given_what_the_note_interpolates(payload):
    b = payload["binning"]
    for key in ("default", "window_start", "window_start_label", "total", "shown",
                "excluded_no_date", "excluded_before_window", "lag_median_days"):
        assert key in b, key
    assert b["default"] == "occurred"
    assert b["window_start_label"] == build.month_label(build.OCCURRED_WINDOW_START)


def test_month_label_rejects_what_it_cannot_format():
    assert build.month_label(None) is None
    assert build.month_label("") is None
    assert build.month_label("2021") is None, "year-only must not become a month"
    assert build.month_label("September 2026") is None, "a label is not a key"
    assert build.month_label("2026-09") == "September 2026"


def test_occurred_bin_classifies_each_precision():
    """Unit coverage of the ladder, independent of whatever the archive holds today."""
    bin_of = lambda raw: build.occurred_bin(normalize.parse_datetime(raw))  # noqa: E731
    assert bin_of("9/24/26 23:47") == ("2026-09", None)
    assert bin_of("6/30/26 Unk.") == ("2026-06", None)
    assert bin_of("Since 7/13/26 Unk.") == ("2026-07", None)
    assert bin_of("10/2026 Unk.") == ("2026-10", None)
    assert bin_of("2021 Unknown") == (None, "no_date")
    assert bin_of("Unknown") == (None, "no_date")
    assert bin_of("9/31/26 11:30") == (None, "no_date"), "an impossible date is not a month"
    assert bin_of("5/2/26 0:43") == (None, "before_window")
    assert bin_of("10/2025 Unk.") == (None, "before_window")
