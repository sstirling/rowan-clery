"""Harvest Rowan's pre-2026 crime log from the Internet Archive.

Rowan published the log through a PHP app until roughly March 2026. That app is now dead
— it returns an empty CMS shell for every month — so Wayback captures are the only
surviving copies.

Two properties make this worth doing properly rather than scraping once:

1. **Many months were captured more than once.** Diffing consecutive captures of the same
   month recovers a retroactive change log: which dispositions Rowan amended, and the
   window in which it happened. Verified against September 2022, where four dispositions
   changed between captures, one of them to "Unfounded".
2. **Captures are immutable.** A Wayback capture never changes, so once harvested, a
   capture is cached on disk and never re-fetched.

The honest limit: capture dates are irregular and often years apart, so the tightest
claim available is usually "changed between <capture A> and <capture B>", not a date.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "rowan-clery-archive/1.0 (+https://github.com/sstirling/rowan-clery)"

LOG_URL = "https://sites.rowan.edu/publicsafety/clery/crimeandfire/cleryapp/index.php?month={month}"
CDX_URL = (
    "http://web.archive.org/cdx/search/cdx"
    "?url=sites.rowan.edu/publicsafety/clery/crimeandfire/cleryapp/index.php"
    "&matchType=prefix&output=json&fl=timestamp,original,statuscode,digest,length&limit=5000"
)
# `id_` asks Wayback for the original bytes without its injected navigation toolbar.
SNAPSHOT_URL = "https://web.archive.org/web/{timestamp}id_/{url}"

# Wayback rate-limits aggressively. These values completed a full 95-capture harvest.
REQUEST_DELAY = 2.5
RETRY_DELAYS = (6, 20, 60)


class WaybackError(RuntimeError):
    """A capture could not be retrieved."""


def _get(url: str, timeout: int = 60) -> bytes:
    last: Exception | None = None
    for delay in (0,) + RETRY_DELAYS:
        if delay:
            time.sleep(delay)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            last = exc
    raise WaybackError(f"{url}: {last}")


def list_captures() -> dict[str, list[dict[str, str]]]:
    """Return {month: [capture, ...]} for every archived month, oldest capture first.

    Deliberately does NOT use the CDX `collapse=urlkey` parameter. Collapsing returns one
    capture per URL, which would silently discard exactly the repeat captures that make
    the change history recoverable.
    """
    rows = json.loads(_get(CDX_URL).decode("utf-8"))[1:]
    by_month: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for timestamp, original, status, digest, length in rows:
        match = re.search(r"month=(\d{4}-\d{2})", urllib.parse.unquote(original))
        if not match or status != "200":
            continue
        by_month[match.group(1)].append(
            {"timestamp": timestamp, "digest": digest, "length": int(length)}
        )
    for captures in by_month.values():
        captures.sort(key=lambda c: c["timestamp"])
    return dict(sorted(by_month.items()))


def capture_date(timestamp: str) -> str:
    """Wayback's 14-digit timestamp -> YYYY-MM-DD."""
    return f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]}"


class CaptureStore:
    """On-disk cache of harvested captures, under the immutable raw store.

    Captures live beside the live snapshots because they are the same kind of thing:
    evidence of what the source said on a given date. A Wayback capture is immutable, so
    once written it is never re-fetched or rewritten.
    """

    def __init__(self, data_dir: pathlib.Path):
        self.root = pathlib.Path(data_dir) / "raw" / "_wayback"

    def path(self, month: str, timestamp: str) -> pathlib.Path:
        return self.root / month / f"{timestamp}.html"

    def has(self, month: str, timestamp: str) -> bool:
        return self.path(month, timestamp).exists()

    def read(self, month: str, timestamp: str) -> str:
        return self.path(month, timestamp).read_text(encoding="utf-8", errors="replace")

    def fetch(self, month: str, timestamp: str) -> str:
        """Return a capture, from cache when possible, otherwise from the Archive."""
        if self.has(month, timestamp):
            return self.read(month, timestamp)
        url = SNAPSHOT_URL.format(timestamp=timestamp, url=LOG_URL.format(month=month))
        body = _get(url)
        target = self.path(month, timestamp)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        time.sleep(REQUEST_DELAY)
        return body.decode("utf-8", "replace")
