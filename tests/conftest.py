"""Shared fixtures.

Tests run against byte-exact copies of the four real monthly sheets rather than tidy
synthetic data, so they exercise the actual mess in the source: dual case numbers,
a duplicate case number, unparseable dates, inconsistent capitalisation and a September
31st that does not exist.
"""

from __future__ import annotations

import pathlib

import pytest

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"

# file_id -> (month label, expected incident count), counted from the live source.
REAL_SHEETS = {
    "1TLdzJn6iUkTi7KIUYR7A1uH-_c6NLy8yqCn3Wc16mAE": ("June 2026", 14),
    "14LFgZwIAeQLjWSJBDkk2QNf1UI9vA0dsCB3ITSVtV2o": ("July 2026", 23),
    "1Ms5gjJX_-vnA4wUaTW-z60Hd98guINjRU5R-e5n58Ts": ("August 2026", 42),
    "1HULCgv9mk7XMkfC2DKkBaOUm5rA00aVfO83lU9489p0": ("September 2026", 107),
}

TOTAL_INCIDENTS = sum(count for _, count in REAL_SHEETS.values())


@pytest.fixture
def sheet_bytes():
    """Return a callable giving the raw CSV bytes for a fixture file id."""

    def _load(file_id: str) -> bytes:
        return (FIXTURE_DIR / f"{file_id}.csv").read_bytes()

    return _load


@pytest.fixture
def all_sheets(sheet_bytes):
    """{file_id: raw csv bytes} for all four real sheets."""
    return {fid: sheet_bytes(fid) for fid in REAL_SHEETS}
