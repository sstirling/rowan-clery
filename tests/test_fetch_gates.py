"""Hostile-input tests for the fetch layer.

Every case here is a way a bad response could be mistaken for "this file is now empty",
which is the one misreading that would let the differ destroy the archive.
"""

from __future__ import annotations

import pytest

from rowan_clery import fetch


class FakeResponse:
    """Minimal stand-in for urlopen's context manager."""

    def __init__(self, body: bytes, status: int = 200, headers: dict | None = None):
        self.body, self.status = body, status
        self.headers = headers or {}

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def patch_response(monkeypatch, body, status=200, content_type="text/csv; charset=utf-8", disposition=""):
    headers = {"Content-Type": content_type, "Content-Disposition": disposition}
    monkeypatch.setattr(
        fetch.urllib.request, "urlopen", lambda *a, **k: FakeResponse(body, status, headers)
    )


GOOD_CSV = (
    b'"Rowan University Daily Crime Log, September 2026",,,,,,,\n'
    b"Case Number,Date/Time Reported,Date/Time Occurred,Nature,Incident Narrative,Campus,Location,Disposition\n"
    b"RUPD 26-1,9/1/26 23:20,9/1/26 22:30,Theft,A thing happened that is long enough to clear the size floor,Glassboro,Somewhere,Open/Active\n"
    b"RUPD 26-2,9/2/26 01:04,9/2/26 01:04,Theft,Another thing happened here as well to pad the body length,Glassboro,Elsewhere,Closed\n"
)
GOOD_DISPOSITION = "attachment; filename*=UTF-8''September 2026 Daily Crime Log - Crime Log.csv"


def test_valid_csv_passes(monkeypatch):
    patch_response(monkeypatch, GOOD_CSV, disposition=GOOD_DISPOSITION)
    result = fetch.fetch_csv("fileid")
    assert result.body == GOOD_CSV
    assert result.sha256


def test_html_error_page_served_as_200_is_rejected(monkeypatch):
    """Google serves sign-in walls and quota pages with HTTP 200 and an HTML body.

    Without the content-type gate this would parse as a file with zero rows, and every
    incident in it would be marked withdrawn.
    """
    patch_response(
        monkeypatch,
        b"<!doctype html><html><body>Sign in to continue</body></html>" + b" " * 300,
        content_type="text/html; charset=utf-8",
    )
    with pytest.raises(fetch.FetchError, match="expected text/csv"):
        fetch.fetch_csv("fileid")


def test_empty_body_is_rejected(monkeypatch):
    patch_response(monkeypatch, b"")
    with pytest.raises(fetch.FetchError):
        fetch.fetch_csv("fileid")


def test_truncated_body_is_rejected(monkeypatch):
    patch_response(monkeypatch, b"Case Number,Date/Time Reported\n")
    with pytest.raises(fetch.FetchError, match="bytes"):
        fetch.fetch_csv("fileid")


def test_csv_without_expected_header_is_rejected(monkeypatch):
    patch_response(monkeypatch, b"a,b,c\n" + b"1,2,3\n" * 60)
    with pytest.raises(fetch.FetchError, match="Case Number"):
        fetch.fetch_csv("fileid")


def test_export_from_the_wrong_tab_is_rejected(monkeypatch):
    """The dangerous case: a tab added AHEAD of the crime log.

    The export stays valid CSV, so only the filename reveals it is a different tab's
    data. Without this check the archive would quietly start recording the wrong sheet.
    """
    patch_response(
        monkeypatch,
        GOOD_CSV,
        disposition="attachment; filename*=UTF-8''September 2026 Daily Crime Log - Summary.csv",
    )
    with pytest.raises(fetch.FetchError, match="came from tab"):
        fetch.fetch_csv("fileid")


def test_missing_disposition_does_not_block_a_good_fetch(monkeypatch):
    """The tab check is a bonus signal; its absence must not fail an otherwise good fetch."""
    patch_response(monkeypatch, GOOD_CSV, disposition="")
    assert fetch.fetch_csv("fileid").body == GOOD_CSV


def test_tab_name_parsing():
    assert fetch._tab_name_from_disposition(GOOD_DISPOSITION) == "Crime Log"
    assert fetch._tab_name_from_disposition('attachment; filename="Sheet - Crime Log.csv"') == "Crime Log"
    assert fetch._tab_name_from_disposition("") is None


# ---- folder listing ------------------------------------------------------------

LISTING = """<html><head><title>Rowan Clery Daily Crime Logs - Google Drive</title></head><body>
<div class="flip-entry" id="entry-1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA">
  <div class="flip-entry-title">August 2026 Daily Crime Log</div>
  <div class="flip-entry-last-modified"><div>Sep 29</div></div></div>
<div class="flip-entry" id="entry-1BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB">
  <div class="flip-entry-title">September 2026 Daily Crime Log</div>
  <div class="flip-entry-last-modified"><div>4:13 am</div></div></div>
</body></html>"""


def test_listing_parses(monkeypatch):
    patch_response(monkeypatch, LISTING.encode(), content_type="text/html")
    found = fetch.list_folder("folder")
    assert set(found) == {"1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "1BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"}
    assert found["1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"]["name"] == "August 2026 Daily Crime Log"
    assert found["1BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"]["modified_hint"] == "4:13 am"


def test_empty_listing_is_a_hard_failure(monkeypatch):
    """A listing with no entries must never read as 'the folder is empty'."""
    patch_response(monkeypatch, b"<html><body>nothing here</body></html>", content_type="text/html")
    with pytest.raises(fetch.FetchError, match="zero entries"):
        fetch.list_folder("folder")


def test_drifted_markup_is_a_hard_failure(monkeypatch):
    """Ids without matching titles means the parse is silently degrading."""
    broken = LISTING.replace('<div class="flip-entry-title">August 2026 Daily Crime Log</div>', "")
    patch_response(monkeypatch, broken.encode(), content_type="text/html")
    with pytest.raises(fetch.FetchError, match="markup drifted"):
        fetch.list_folder("folder")


def test_suspicious_entry_count_is_a_hard_failure(monkeypatch):
    """embeddedfolderview paginates without a page token; truncation must not look like truth."""
    entries = "".join(
        f'<div class="flip-entry" id="entry-1{chr(65 + i % 26)}{"X" * 31}">'
        f'<div class="flip-entry-title">Log {i}</div>'
        f'<div class="flip-entry-last-modified"><div>Sep {i % 28 + 1}</div></div></div>'
        for i in range(60)
    )
    patch_response(monkeypatch, f"<html><body>{entries}</body></html>".encode(), content_type="text/html")
    with pytest.raises(fetch.FetchError, match="pagination threshold"):
        fetch.list_folder("folder")
