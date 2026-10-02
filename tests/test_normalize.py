"""Normalization tests, including the audit-marker handling that the raw data demands."""

from __future__ import annotations

import csv
import io
import pathlib
import re

import pytest

from rowan_clery import normalize, parse

CONFIG = pathlib.Path(__file__).parent.parent / "config"


@pytest.fixture(scope="module")
def maps():
    return normalize.load_maps(CONFIG)


@pytest.fixture(scope="module")
def category_map(maps):
    return maps[0]


@pytest.fixture(scope="module")
def disposition_map(maps):
    return maps[1]


# ---- the reclassification bug this module exists to prevent --------------------


def test_nature_updated_supersedes_the_withdrawn_classification(category_map):
    """'Theft; Nature updated; Motor Vehicle Theft' is a motor vehicle theft.

    Counting it as a theft would report the classification RUPD explicitly withdrew.
    """
    result = normalize.categorize("Theft; Nature updated; Motor Vehicle Theft", category_map)
    assert result["categories"] == ["Motor vehicle theft"]
    assert result["reclassified_from"] == ["Theft"]
    assert result["was_reclassified"] is True


def test_assault_escalation_is_not_double_counted(category_map):
    """The September strangulation case must not count as a simple assault too."""
    raw = "Domestic Violence; Simple Assault; False Imprisonment; Nature updated; Aggravated Assault-Strangulation"
    result = normalize.categorize(raw, category_map)
    assert result["categories"] == ["Aggravated assault"]
    assert "Simple assault" in result["reclassified_from"]
    assert "Simple assault" not in result["categories"]


def test_audit_marker_never_becomes_a_category(category_map):
    """A naive split would mint a category literally named 'Nature updated'."""
    result = normalize.categorize("Theft; Nature updated; Motor Vehicle Theft", category_map)
    assert "Nature updated" not in result["categories"]


def test_multi_offense_rows_keep_every_offense(category_map):
    result = normalize.categorize("Theft; Criminal Mischief", category_map)
    assert result["categories"] == ["Theft", "Criminal mischief"]
    assert result["was_reclassified"] is False


def test_comma_containing_token_is_not_split(category_map):
    """Splitting on commas would corrupt tokens that legitimately contain them."""
    result = normalize.categorize("Alcohol Violations (Open Container in Vehicle, DWI)", category_map)
    assert result["categories"] == ["Alcohol violation", "DWI"]


def test_synonyms_collapse(category_map):
    for raw in ("Trespassing", "Defiant Trespassing", "Trespassing (Defiant)"):
        assert normalize.categorize(raw, category_map)["categories"] == ["Trespassing"]
    for raw in ("Criminal Mischief", "Criminal mischief", "Criminal Mischief- Graffiti"):
        assert normalize.categorize(raw, category_map)["categories"] == ["Criminal mischief"]


def test_unmapped_nature_token_fails_loudly(category_map):
    with pytest.raises(normalize.MappingError, match="Unmapped Nature token"):
        normalize.categorize("Interdimensional Trespass", category_map)


# ---- dispositions --------------------------------------------------------------


def test_disposition_update_supersedes_earlier_state(disposition_map):
    """'Open/Active; Disposition updated; Closed' is closed, not both."""
    result = normalize.disposition_flags("Open/Active; Disposition updated; Closed", disposition_map)
    assert "closed" in result["flags"]
    assert "open_active" not in result["flags"]
    assert result["disposition_amended"] is True


def test_multiple_outcomes_are_all_kept(disposition_map):
    result = normalize.disposition_flags("Closed; Subject arrested; Trespass notice issued", disposition_map)
    assert set(result["flags"]) == {"closed", "arrested", "trespass_notice"}


def test_disposition_matching_is_case_insensitive(disposition_map):
    upper = normalize.disposition_flags("Closed; Subject Issued Summons", disposition_map)
    lower = normalize.disposition_flags("Closed; Subject issued summons", disposition_map)
    assert upper["flags"] == lower["flags"] == ["closed", "summons_issued"]


def test_unmapped_disposition_token_fails_loudly(disposition_map):
    with pytest.raises(normalize.MappingError, match="Unmapped Disposition token"):
        normalize.disposition_flags("Closed; Subject teleported", disposition_map)


# ---- every real token is covered ----------------------------------------------


def test_every_live_nature_string_maps(all_sheets, category_map):
    for file_id, body in all_sheets.items():
        for record in parse.parse_and_key(body, file_id):
            normalize.categorize(record["Nature"], category_map)  # must not raise


def test_every_live_disposition_string_maps(all_sheets, disposition_map):
    for file_id, body in all_sheets.items():
        for record in parse.parse_and_key(body, file_id):
            normalize.disposition_flags(record["Disposition"], disposition_map)  # must not raise


def test_config_maps_cover_every_live_token(all_sheets, category_map, disposition_map):
    """Every token in the CURRENT feed must be mapped.

    The maps also carry pre-2026 tokens that no 2026 sheet contains, so this checks
    coverage rather than exact equality: the live vocabulary must be a subset.
    """
    nature_tokens, disposition_tokens = set(), set()
    for file_id, body in all_sheets.items():
        for record in parse.parse_and_key(body, file_id):
            nature_tokens.update(t for t in re.split(r"\s*;\s*", record["Nature"].strip()) if t)
            disposition_tokens.update(
                normalize.normalize_disposition_token(t)
                for t in re.split(r"\s*;\s*", record["Disposition"].strip())
                if normalize.normalize_disposition_token(t)
            )
    assert nature_tokens <= set(category_map), f"unmapped: {nature_tokens - set(category_map)}"
    assert disposition_tokens <= set(disposition_map), f"unmapped: {disposition_tokens - set(disposition_map)}"


def test_config_maps_are_well_formed():
    """A stray unquoted comma would silently shift every later column."""
    for name in ("category_map.csv", "disposition_map.csv"):
        lines = [ln for ln in (CONFIG / name).read_text().splitlines() if not ln.lstrip().startswith("#")]
        for row in csv.DictReader(io.StringIO("\n".join(lines))):
            assert None not in row, f"{name}: ragged row {row}"
            assert row["role"] in (
                "offense", "audit_marker", "outcome", "activity", "object", "channel"
            ), f"{name}: bad role {row['role']!r}"


# ---- dates ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,precision,value",
    [
        ("9/1/26 23:20", "minute", "2026-09-01T23:20:00"),
        ("6/30/26 Unk.", "day", "2026-06-30"),
        ("6/29/2026 Unk.", "day", "2026-06-29"),  # four-digit-year variant
        ("10/2025 Unk.", "month", "2025-10"),
        ("2021 Unknown", "year", "2021"),
        ("Unknown", "unknown", None),
        ("", "unknown", None),
        ("9/31/26 11:30", "invalid", None),  # September 31 does not exist
    ],
)
def test_date_precision_ladder(raw, precision, value):
    result = normalize.parse_datetime(raw)
    assert result["precision"] == precision
    assert result["value"] == value
    assert result["raw"] == raw


def test_ongoing_range_is_marked_not_discarded():
    result = normalize.parse_datetime("Since 5/13/26 Unk.")
    assert result["ongoing"] is True
    assert result["precision"] == "range_start"
    assert result["value"] == "2026-05-13"


def test_impossible_date_is_surfaced_not_silently_dropped(all_sheets):
    """The live August sheet contains 9/31/26. It must be reported, not swallowed."""
    found = []
    for file_id, body in all_sheets.items():
        for record in parse.parse_and_key(body, file_id):
            if normalize.parse_datetime(record["Date/Time Occurred"])["precision"] == "invalid":
                found.append(record["Date/Time Occurred"])
    assert "9/31/26 11:30" in found


def test_year_is_checked_against_the_logs_own_month():
    """`%y` turns a stray "/99" into 1999; that must be caught.

    The comparison is to the year of the log the row appears in, not to today: the
    archive spans 2017-2026, so comparing to "now" would flag every historical row.
    """
    parsed = normalize.parse_datetime("3/4/99 10:00")
    assert normalize.year_sanity_warning(parsed, expected_year=2026) is not None
    ok = normalize.parse_datetime("3/4/26 10:00")
    assert normalize.year_sanity_warning(ok, expected_year=2026) is None


def test_reporting_lag_requires_minute_precision_at_both_ends():
    reported = normalize.parse_datetime("9/5/26 18:45")
    exact = normalize.parse_datetime("8/28/26 6:00")
    vague = normalize.parse_datetime("8/28/26 Unk.")
    assert normalize.reporting_lag_hours(reported, exact) == pytest.approx(204.75)
    assert normalize.reporting_lag_hours(reported, vague) is None


# ---- agencies ------------------------------------------------------------------


def test_agency_extraction():
    assert normalize.agencies("RUPD 26-028143/ CSA 85932") == ["RUPD", "CSA"]
    assert normalize.agencies("CSA 86047") == ["CSA"]
    assert normalize.agencies("RUPD 26-028159") == ["RUPD"]


def test_csa_only_rows_exist_in_the_live_data(all_sheets):
    """Rows reported to a Campus Security Authority with no police response.

    These are why the tool must never present an undifferentiated total: "Rowan police
    responded to N incidents" would be wrong for every one of them.
    """
    csa_only = [
        r
        for fid, body in all_sheets.items()
        for r in parse.parse_and_key(body, fid)
        if normalize.agencies(r["Case Number"]) == ["CSA"]
    ]
    assert len(csa_only) > 5
