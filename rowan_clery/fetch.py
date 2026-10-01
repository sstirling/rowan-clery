"""Network layer: retrieve the Drive folder listing and each sheet's CSV export.

Everything here is Python stdlib. The source needs no authentication, and avoiding
third-party HTTP libraries keeps the GitHub Actions run dependency-free.

The functions here are deliberately paranoid. A silent fetch failure is the one bug that
could corrupt the archive: if a bad response were treated as "the file is now empty",
the differ would mark every row withdrawn. So fetches either return data that has passed
every sanity gate, or they raise. Absence of a file is never evidence of absence of its
rows.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import io
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

# Identifies the project and gives Rowan a way to make contact. Traffic is ~5-10
# requests a day; if the folder is ever locked down, a clean record of non-abusive
# access matters.
USER_AGENT = "rowan-clery-archive/1.0 (+https://github.com/sstirling/rowan-clery)"

# The modern Drive folder page is a 350KB React app whose markup changes with every
# release. `embeddedfolderview` is a ~5KB server-rendered listing that has been stable
# for years. Verified: returns all 4 files with ids, titles and modified hints.
LISTING_URL = "https://drive.google.com/embeddedfolderview?id={folder_id}#list"
CSV_URL = "https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
ZIP_URL = "https://docs.google.com/spreadsheets/d/{file_id}/export?format=zip"

EXPECTED_TAB = "Crime Log"
EXPECTED_HEADER = (
    "Case Number",
    "Date/Time Reported",
    "Date/Time Occurred",
    "Nature",
    "Incident Narrative",
    "Campus",
    "Location",
    "Disposition",
)
BANNER_RE = re.compile(r"^Rowan University Daily Crime Log,\s*[A-Z][a-z]+ \d{4}$")

# Do NOT reach for the gviz endpoint (`/gviz/tq?tqx=out:csv`). Verified: when asked for
# a tab that does not exist it silently returns the FIRST sheet instead of erroring, so
# it is useless as a tab probe, and it folds the banner row into the header, corrupting
# the data.

RETRY_DELAYS = (5, 30, 120)
MIN_BODY_BYTES = 200
MIN_DATA_ROWS = 3


class FetchError(RuntimeError):
    """A fetch failed or returned something untrustworthy.

    Callers must treat this as "we do not know the current state of this file" and leave
    the archive untouched — never as "the file is empty".
    """


@dataclasses.dataclass
class FetchResult:
    """A validated response plus the provenance we keep alongside the snapshot."""

    body: bytes
    status: int
    content_type: str
    content_disposition: str
    fetched_at: str
    sha256: str
    byte_length: int

    def provenance(self) -> dict:
        return {
            "status": self.status,
            "content_type": self.content_type,
            "content_disposition": self.content_disposition,
            "fetched_at_utc": self.fetched_at,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
        }


def _get(url: str, timeout: int = 45) -> FetchResult:
    """GET a URL with retries. Raises FetchError on anything less than a clean 200."""
    last_exc: Exception | None = None
    for delay in (0,) + RETRY_DELAYS:
        if delay:
            time.sleep(delay)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                return FetchResult(
                    body=body,
                    status=resp.status,
                    content_type=resp.headers.get("Content-Type", ""),
                    content_disposition=urllib.parse.unquote(resp.headers.get("Content-Disposition", "")),
                    fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    sha256=hashlib.sha256(body).hexdigest(),
                    byte_length=len(body),
                )
        except urllib.error.HTTPError as exc:
            # 403/404/410 are real answers about the resource, not transient noise.
            # They still are NOT proof of deletion — the caller decides that.
            if exc.code in (403, 404, 410):
                raise FetchError(f"HTTP {exc.code} for {url}") from exc
            last_exc = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
    raise FetchError(f"{url} failed after {len(RETRY_DELAYS) + 1} attempts: {last_exc}")


def _tab_name_from_disposition(disposition: str) -> str | None:
    """Pull the tab name out of a CSV export's Content-Disposition header.

    Google names the download "<doc title> - <tab name>.csv", which means every CSV
    fetch tells us for free which tab we actually received. This catches the dangerous
    case: not "a tab was added" but "a tab was added in position 1", at which point the
    CSV export silently becomes a different tab's data while still being valid CSV.
    """
    match = re.search(r"filename\*=UTF-8''(.+?)(?:;|$)", disposition)
    if not match:
        match = re.search(r'filename="(.+?)"', disposition)
    if not match:
        return None
    name = match.group(1).strip().removesuffix(".csv")
    return name.rsplit(" - ", 1)[-1].strip() if " - " in name else None


def list_folder(folder_id: str) -> dict[str, dict[str, str]]:
    """List the public folder via embeddedfolderview.

    Returns {file_id: {"name": ..., "modified_hint": ...}}.

    The `modified_hint` is Drive's localized, year-less display string ("Sep 29",
    "4:13 am"). It is a liveness hint only and must never be stored as an archival
    timestamp.

    This function may legitimately return fewer files than expected. The caller unions
    the result with the pinned floor in config/known_files.json so that a listing
    regression can never shrink the known set.
    """
    result = _get(LISTING_URL.format(folder_id=folder_id))
    html = result.body.decode("utf-8", "replace")

    ids = re.findall(r'id="entry-([A-Za-z0-9_-]{25,})"', html)
    titles = re.findall(r'flip-entry-title">([^<]*)<', html)
    modified = re.findall(r'flip-entry-last-modified"><div>([^<]*)<', html)

    if not ids:
        raise FetchError(
            "Folder listing returned zero entries. The markup has probably changed, or "
            "the folder was made private. This is a hard failure, not an empty folder — "
            "refusing to continue so a listing regression is never mistaken for deletion."
        )

    # If the three parallel lists ever fall out of step, the markup has drifted and the
    # parse is silently degrading. Fail rather than mis-pair names to ids.
    if not (len(ids) == len(titles) == len(modified)):
        raise FetchError(
            f"Folder listing markup drifted: {len(ids)} ids, {len(titles)} titles, "
            f"{len(modified)} modified stamps. Refusing to guess the pairing."
        )

    # embeddedfolderview paginates somewhere around 50-100 entries with no page token.
    # At ~12 files a year that is years away, but it would manifest as silent truncation.
    if len(ids) >= 50:
        raise FetchError(
            f"Folder listing returned {len(ids)} entries, at or above the pagination "
            "threshold. The listing is probably truncated; add paging before trusting it."
        )

    return {
        file_id: {"name": title.strip(), "modified_hint": mod.strip()}
        for file_id, title, mod in zip(ids, titles, modified)
    }


def fetch_csv(file_id: str) -> FetchResult:
    """Fetch one sheet's CSV export, after every sanity gate.

    CSV (not XLSX) is the archival format for two reasons. It is byte-stable across
    repeated identical requests, where XLSX re-exports differ byte-for-byte even when
    nothing changed — which would make hashing useless for change detection. And it is
    text, so a removed row shows up as a readable diff in GitHub's UI. A diff you can
    show a lawyer is the point; byte-stability is what enables it.
    """
    result = _get(CSV_URL.format(file_id=file_id))

    # Google serves sign-in walls, quota pages and other interstitials with HTTP 200 and
    # a text/html body. Without this gate, an access revocation would parse as a file
    # with zero rows and the differ would withdraw every incident in it.
    if not result.content_type.lower().startswith("text/csv"):
        raise FetchError(
            f"{file_id}: expected text/csv, got {result.content_type!r}. "
            "The file may have been made private, removed, or Google served an interstitial."
        )

    if result.byte_length < MIN_BODY_BYTES:
        raise FetchError(f"{file_id}: body is only {result.byte_length} bytes")

    tab = _tab_name_from_disposition(result.content_disposition)
    if tab is not None and tab != EXPECTED_TAB:
        raise FetchError(
            f"{file_id}: CSV export came from tab {tab!r}, expected {EXPECTED_TAB!r}. "
            "A tab may have been added ahead of the crime log — the export would be "
            "valid CSV containing the wrong data."
        )

    text = result.body.decode("utf-8-sig", "replace")
    if "Case Number" not in text:
        raise FetchError(f"{file_id}: CSV has no 'Case Number' header; schema may have changed")
    if text.count("\n") < MIN_DATA_ROWS:
        raise FetchError(f"{file_id}: only {text.count(chr(10))} lines, below floor of {MIN_DATA_ROWS}")

    return result


def sheet_tab_names(file_id: str) -> list[str]:
    """Conclusive tab census via the zip export, whose member list IS the tab inventory.

    Verified: returns ['Crime Log.html', 'resources/sheet.css'] for a one-tab sheet.
    Cheaper to reason about than unzipping XLSX and parsing xl/workbook.xml, and it
    sidesteps XLSX byte-instability because we read the namelist and discard the bytes.

    This is the expensive check (~500KB), so run it only when a file's CSV hash changed,
    plus unconditionally once a week. The Content-Disposition check in fetch_csv covers
    the dangerous case on every run for free.
    """
    result = _get(ZIP_URL.format(file_id=file_id), timeout=90)
    try:
        with zipfile.ZipFile(io.BytesIO(result.body)) as zf:
            names = zf.namelist()
    except zipfile.BadZipFile as exc:
        raise FetchError(f"{file_id}: zip export unreadable ({exc})") from exc
    return [n.removesuffix(".html") for n in names if n.endswith(".html")]
