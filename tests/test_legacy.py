"""Tests for the pre-2026 crime log parser and the Wayback backfill.

Fixtures are real captures covering the three markup variants the archived pages use:
2017 (dates split across <br/>), 2021 (the student flag), and a 2022 pair that differs
between captures so amendment detection can be exercised.
"""

from __future__ import annotations

import pathlib

import pytest

from rowan_clery import backfill, legacy, normalize, parse

WAYBACK = pathlib.Path(__file__).parent / "fixtures" / "wayback"

CAPTURES = {
    "2017-12": "20191023031206",
    "2021-02": "20210921043837",
}
SEPT22_EARLY = "2022-09__20220921193311.html"
SEPT22_LATE = "2022-09__20250516204914.html"


def load(name: str) -> str:
    return (WAYBACK / name).read_text(encoding="utf-8", errors="replace")


@pytest.fixture
def early_2022():
    return legacy.parse_legacy(load(SEPT22_EARLY), "2022-09")


@pytest.fixture
def late_2022():
    return legacy.parse_legacy(load(SEPT22_LATE), "2022-09")


# ---- parsing across eras -------------------------------------------------------


@pytest.mark.parametrize("month,timestamp", CAPTURES.items())
def test_every_era_parses(month, timestamp):
    records = legacy.parse_legacy(load(f"{month}__{timestamp}.html"), month)
    assert len(records) > 10
    for record in records:
        assert record["Case Number"]
        assert record["Date/Time Reported"]
        # The narrative column did not exist before 2026 and must never be invented.
        assert record["Incident Narrative"] == ""


def test_campus_is_split_out_of_general_location():
    """Campus was a bold prefix inside General Location, not its own column."""
    records = legacy.parse_legacy(load("2021-02__20210921043837.html"), "2021-02")
    campuses = {r["Campus"] for r in records}
    assert "Glassboro Campus" in campuses
    # The campus must not be duplicated into the location. ("On Campus Residential
    # Housing" is a legitimate location name, so a bare substring check is wrong.)
    assert all(not r["Location"].startswith(r["Campus"]) for r in records if r["Campus"])
    assert any(r["Location"] for r in records)


def test_student_flag_is_extracted_from_the_disposition_cell():
    """A field the 2026 format dropped entirely."""
    records = legacy.parse_legacy(load("2021-02__20210921043837.html"), "2021-02")
    flagged = [r for r in records if r["student_flag"]]
    assert len(flagged) > 20
    assert {r["student_flag"] for r in flagged} <= {"Student", "Non Student", "Unknown"}
    # ...and it must not pollute the disposition vocabulary.
    assert all("Student?" not in r["Disposition"] for r in records)


def test_2017_dates_split_across_br_are_rejoined():
    """2017 rows render a date and its time on separate lines."""
    records = legacy.parse_legacy(load("2017-12__20191023031206.html"), "2017-12")
    occurred = [r["Date/Time Occurred"] for r in records if r["Date/Time Occurred"]]
    assert any(" " in o and "/" in o for o in occurred)
    assert all("\n" not in o for o in occurred)


def test_multi_value_bullets_become_the_2026_separator():
    """So one category map serves both eras."""
    records = legacy.parse_legacy(load(SEPT22_EARLY), "2022-09")
    multi = [r for r in records if ";" in r["Nature"]]
    assert multi
    assert all("•" not in r["Nature"] for r in records)


def test_dead_shell_is_detected_not_read_as_empty():
    """The dead app returns HTTP 200 with no table for every month.

    Reading that as "the month is now empty" would look like a mass deletion.
    """
    assert legacy.is_dead_page("<html><body><p>Nothing here</p></body></html>")
    assert not legacy.is_dead_page(load(SEPT22_EARLY))


def test_unrecognised_markup_raises():
    with pytest.raises(legacy.LegacyParseError):
        legacy.parse_legacy("<html><body><table><tr><td>a</td></tr></table></body></html>", "x")


# ---- the amendment history this backfill exists to recover ---------------------


def test_repeat_captures_reveal_disposition_amendments(early_2022, late_2022):
    """Four dispositions changed between the 2022 and 2025 captures of Sept 2022."""
    a = {r["Case Number"]: r for r in early_2022}
    b = {r["Case Number"]: r for r in late_2022}
    changed = [k for k in set(a) & set(b) if a[k]["Disposition"] != b[k]["Disposition"]]
    assert len(changed) == 4

    # The newsworthy one: a report later determined to be unfounded.
    unfounded = [k for k in changed if "unfounded" in b[k]["Disposition"].lower()]
    assert unfounded, "the Unfounded reclassification should be detectable"


def test_no_rows_vanish_between_captures(early_2022, late_2022):
    """Rowan adds to a month after it closes, but does not remove from it."""
    a = {r["Case Number"] for r in early_2022}
    b = {r["Case Number"] for r in late_2022}
    assert not (a - b), f"rows disappeared: {a - b}"
    assert b - a, "the later capture should contain incidents added after the first"


# ---- identity under source edits ----------------------------------------------


def test_cosmetic_date_reformat_does_not_fork_identity():
    """February 2022: 34 of 59 rows changed 02/13/22 -> 02/13/2022 and nothing else.

    Hashing the raw string there forked one incident into two identities.
    """
    assert parse.incident_uid("22-004739", "02/13/22 2:23") == parse.incident_uid(
        "22-004739", "02/13/2022 2:23"
    )


def test_adding_a_time_is_not_treated_as_the_same_instant():
    """"06/06/22" and "06/06/22 0:01" are different values; reconciliation links them."""
    assert parse.incident_uid("x", "06/06/22") != parse.incident_uid("x", "06/06/22 0:01")


def test_canonical_reported_falls_back_safely():
    assert parse.canonical_reported("not a date at all") == "not a date at all"
    assert parse.canonical_reported("  9/1/26   23:20 ") == "2026-09-01T23:20"


# ---- legacy vocabulary handling ------------------------------------------------


@pytest.fixture(scope="module")
def maps():
    return normalize.load_maps(pathlib.Path(__file__).parent.parent / "config")


def test_non_crime_activity_is_not_counted_as_an_offense(maps):
    """200 "Dispute" and 118 "Motor Vehicle Stop" tokens must not inflate crime counts."""
    category_map, _ = maps
    result = normalize.categorize("Dispute", category_map, strict=False)
    assert result["categories"] == []
    assert result["activity"] == ["Dispute"]


def test_the_object_of_an_offense_is_kept_separate(maps):
    """"Criminal Mischief/Vandalism; Exit sign" is one offense against one object."""
    category_map, _ = maps
    result = normalize.categorize("Criminal Mischief/Vandalism; Exit sign", category_map, strict=False)
    assert result["categories"] == ["Criminal mischief"]
    assert result["objects"] == ["Exit sign"]


def test_legacy_combined_audit_marker_supersedes(maps):
    """The legacy format writes the marker and its replacement as one token."""
    category_map, _ = maps
    result = normalize.categorize("Theft; Nature updated - Assault (Aggravated)", category_map, strict=False)
    assert result["categories"] == ["Aggravated assault"]
    assert result["reclassified_from"] == ["Theft"]


def test_unknown_token_is_fatal_for_live_data_but_recorded_for_backfill(maps):
    category_map, _ = maps
    with pytest.raises(normalize.MappingError):
        normalize.categorize("Interdimensional Trespass", category_map, strict=True)

    lenient = normalize.categorize("Theft; Interdimensional Trespass", category_map, strict=False)
    assert lenient["categories"] == ["Theft"]
    assert lenient["unclassified"] == ["Interdimensional Trespass"]


def test_occurrence_ranges_parse_to_their_start():
    """The legacy log routinely expressed occurrence as a range."""
    result = normalize.parse_datetime("8/31/22 22:00 to 9/1/22 9:31")
    assert result["value"] == "2022-08-31T22:00:00"
    assert result["precision"] == "range_start"
    assert result["range_end"] == "9/1/22 9:31"


def test_year_check_is_against_the_logs_own_month_not_today():
    """A 2017 row is not suspect merely because it is old."""
    parsed = normalize.parse_datetime("12/01/17 14:20")
    assert normalize.year_sanity_warning(parsed, expected_year=2017) is None
    assert normalize.year_sanity_warning(parsed, expected_year=2024) is not None


# ---- backfill wiring -----------------------------------------------------------


def test_prepare_assigns_identity_and_era():
    records = backfill._prepare(legacy.parse_legacy(load(SEPT22_EARLY), "2022-09"), "2022-09")
    assert all(r["source_era"] == backfill.ERA for r in records)
    assert all(r["source_file_id"] == "wayback:2022-09" for r in records)
    assert len({r["incident_uid"] for r in records}) == len(records)


def test_months_are_scoped_so_one_capture_says_nothing_about_another():
    assert backfill.pseudo_file_id("2022-09") != backfill.pseudo_file_id("2022-06")
