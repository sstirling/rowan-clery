"""Parsing and identity tests, run against byte-exact copies of the real sheets."""

from __future__ import annotations

import pytest

from rowan_clery import parse
from tests.conftest import REAL_SHEETS, TOTAL_INCIDENTS

DUPLICATE_CASE = "RUPD 26-026280"
AUGUST = "1Ms5gjJX_-vnA4wUaTW-z60Hd98guINjRU5R-e5n58Ts"


def test_golden_row_counts(all_sheets):
    """Every sheet yields exactly the number of incidents counted from the source."""
    for file_id, (label, expected) in REAL_SHEETS.items():
        incidents = parse.parse_and_key(all_sheets[file_id], file_id)
        assert len(incidents) == expected, f"{label}: expected {expected}, got {len(incidents)}"


def test_golden_total(all_sheets):
    total = sum(len(parse.parse_and_key(b, fid)) for fid, b in all_sheets.items())
    assert total == TOTAL_INCIDENTS == 186


def test_no_field_is_silently_dropped(all_sheets):
    """Every incident carries all eight source fields, even when a cell is empty."""
    for file_id, body in all_sheets.items():
        for record in parse.parse_and_key(body, file_id):
            for field in parse.SOURCE_FIELDS:
                assert field in record
            # Case Number and Date/Time Reported are the identity fields; if either is
            # ever blank the uid degenerates and rows could merge.
            assert record["Case Number"].strip(), f"{file_id}: blank case number"
            assert record["Date/Time Reported"].strip(), f"{file_id}: blank reported date"


def test_uids_are_unique_across_the_whole_corpus(all_sheets):
    """186 rows must produce 186 distinct uids, with the key being file-independent."""
    uids = [r["incident_uid"] for fid, b in all_sheets.items() for r in parse.parse_and_key(b, fid)]
    assert len(uids) == TOTAL_INCIDENTS
    assert len(set(uids)) == TOTAL_INCIDENTS, "uid collision — two incidents would merge"


def test_duplicate_case_number_survives_as_two_incidents(all_sheets):
    """The one real duplicate case number must stay two records, not one."""
    august = parse.parse_and_key(all_sheets[AUGUST], AUGUST)
    pair = [r for r in august if parse.normalize_case_number(r["Case Number"]) == DUPLICATE_CASE]
    assert len(pair) == 2, "the RUPD 26-026280 pair was lost"
    assert pair[0]["incident_uid"] != pair[1]["incident_uid"]
    # ...and it must be flagged, because identical narrative + disposition + location is
    # equally consistent with a source copy-paste error.
    assert all("near_duplicate" in r["flags"] for r in pair)


def test_uid_is_independent_of_file_id(all_sheets):
    """Re-uploading a sheet under a new file id must not change any identity.

    This is the scenario that would otherwise fabricate a mass deletion: if Rowan
    deletes a month and re-uploads it, the file id changes. A file-scoped key would
    report every row as withdrawn and an equal number as new.
    """
    body = all_sheets[AUGUST]
    before = [r["incident_uid"] for r in parse.parse_and_key(body, AUGUST)]
    after = [r["incident_uid"] for r in parse.parse_and_key(body, "1aNewFileIdAfterReupload000000000000000000")]
    assert before == after


def test_uid_is_independent_of_row_order(all_sheets):
    """Reordering rows must not change any identity.

    Any positional component in the key would corrupt identity when a row is inserted
    or when the first of a duplicate pair is deleted.
    """
    body = all_sheets[AUGUST].decode("utf-8")
    lines = body.split("\r\n") if "\r\n" in body else body.split("\n")
    header, data = lines[:2], [ln for ln in lines[2:] if ln.strip()]
    reordered = "\n".join(header + list(reversed(data)))

    original = {r["incident_uid"] for r in parse.parse_and_key(all_sheets[AUGUST], AUGUST)}
    shuffled = {r["incident_uid"] for r in parse.parse_and_key(reordered, AUGUST)}
    assert original == shuffled


def test_uid_is_stable_under_amendment(all_sheets):
    """Amending a disposition changes the content hash but never the uid."""
    august = parse.parse_and_key(all_sheets[AUGUST], AUGUST)
    original = august[0]
    amended = dict(original)
    amended["Disposition"] = "Closed; Subject arrested; Disposition updated"

    assert parse.incident_uid(amended["Case Number"], amended["Date/Time Reported"]) == original["incident_uid"]
    assert parse.content_hash(amended) != parse.content_hash(original)


def test_case_number_normalization_preserves_structure():
    """Only whitespace and case are normalized — never the structure of the reference."""
    assert parse.normalize_case_number("  RUPD 26-028143/  CSA 85932 ") == "RUPD 26-028143/ CSA 85932"
    assert parse.normalize_case_number("csa 86141, 86143") == "CSA 86141, 86143"
    # Distinct multi-agency references must not collapse into one another.
    assert parse.normalize_case_number("RUPD 26-001/ CSA 1") != parse.normalize_case_number("RUPD 26-001")


def test_header_is_located_by_content_not_position(all_sheets):
    """An extra banner row must not shift every field by one column."""
    body = all_sheets[AUGUST].decode("utf-8")
    with_extra_banner = "Extra banner inserted by the owner,,,,,,,\n" + body
    incidents = parse.parse_and_key(with_extra_banner, AUGUST)
    assert len(incidents) == REAL_SHEETS[AUGUST][1]
    assert all(r["Campus"] in ("Glassboro", "Rowan-Virtua SOM (Stratford)", "West") for r in incidents)


def test_source_month_read_from_banner(all_sheets):
    """The month comes from the document's own banner, not from the file name."""
    assert parse.source_month(all_sheets[AUGUST]) == "August 2026"


def test_missing_column_is_a_hard_failure(all_sheets):
    """A schema change must raise, never silently produce rows with blank fields."""
    body = all_sheets[AUGUST].decode("utf-8").replace("Disposition", "Outcome", 1)
    with pytest.raises(parse.ParseError, match="missing expected columns"):
        parse.parse_csv(body, AUGUST)


def test_garbage_input_is_a_hard_failure():
    with pytest.raises(parse.ParseError):
        parse.parse_csv("<!doctype html><html><body>Sign in</body></html>", "x")
