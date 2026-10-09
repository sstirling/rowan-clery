"""Shared fixtures.

Tests run against byte-exact copies of the real monthly sheets rather than tidy
synthetic data, so they exercise the actual mess in the source: dual case numbers,
a duplicate case number, unparseable dates, inconsistent capitalisation and a September
31st that does not exist.

They come in two sets. REAL_SHEETS is the frozen golden corpus of closed months, whose
counts are fixed forever and so can be asserted exactly. CURRENT_SHEETS is the month in
progress, which grows daily; it exists so the vocabulary-coverage tests can see the one
sheet where a new wording can first appear.
"""

from __future__ import annotations

import pathlib

import pytest

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"

# The frozen golden corpus: file_id -> (month label, expected incident count).
# These four are CLOSED months, so their counts can never change again and the archive,
# parse and pipeline invariants can assert exact numbers against them. Do not add the
# month in progress here -- it grows daily and would make every golden total a moving
# target. See CURRENT_SHEETS.
REAL_SHEETS = {
    "1TLdzJn6iUkTi7KIUYR7A1uH-_c6NLy8yqCn3Wc16mAE": ("June 2026", 14),
    "14LFgZwIAeQLjWSJBDkk2QNf1UI9vA0dsCB3ITSVtV2o": ("July 2026", 23),
    "1Ms5gjJX_-vnA4wUaTW-z60Hd98guINjRU5R-e5n58Ts": ("August 2026", 42),
    "1HULCgv9mk7XMkfC2DKkBaOUm5rA00aVfO83lU9489p0": ("September 2026", 107),
}

TOTAL_INCIDENTS = sum(count for _, count in REAL_SHEETS.values())

# The month in progress, kept separate from the golden corpus and used only by the
# vocabulary-coverage tests.
#
# Rowan only appends to the current month, so that sheet is the one place a new
# Nature/Disposition wording can first appear -- and the coverage tests can only catch
# an unmapped token in a sheet they actually hold. While the fixtures stopped at
# September, the suite stayed green locally and the scheduled run died in CI instead
# (2026-10-09, on "Offensive Language" and "Subjects arrested/issued summons").
#
# No row count is pinned: this sheet grows daily, and asserting a count here would turn
# a routine append into a test failure. Refresh the fixture when a month closes, then
# move it into REAL_SHEETS with its final count.
CURRENT_SHEETS = {
    "1vVeupKAr-Wj6BYogmaOTPjmWvF1zR_I5u9lJsD73p3I": "October 2026",
}


@pytest.fixture
def sheet_bytes():
    """Return a callable giving the raw CSV bytes for a fixture file id."""

    def _load(file_id: str) -> bytes:
        return (FIXTURE_DIR / f"{file_id}.csv").read_bytes()

    return _load


@pytest.fixture
def all_sheets(sheet_bytes):
    """{file_id: raw csv bytes} for the frozen golden corpus (closed months only)."""
    return {fid: sheet_bytes(fid) for fid in REAL_SHEETS}


@pytest.fixture
def live_sheets(sheet_bytes):
    """{file_id: raw csv bytes} for every month the source currently publishes.

    The golden corpus plus the month in progress. Use this for anything that has to hold
    true of the CURRENT feed -- above all, that the config maps cover every token in it.
    """
    return {fid: sheet_bytes(fid) for fid in (*REAL_SHEETS, *CURRENT_SHEETS)}
