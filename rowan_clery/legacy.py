"""Parse Rowan's pre-2026 crime log, as rendered by the old `cleryapp` PHP pages.

Rowan published the log through a PHP app at
`sites.rowan.edu/publicsafety/clery/crimeandfire/cleryapp/index.php?month=YYYY-MM`
until roughly March 2026, when it moved to Google Sheets on Drive. The app is now dead —
it returns an empty CMS shell for every month — so the only surviving copies of that
decade are Internet Archive captures.

The markup is stable and self-describing. A comment in the page reads
"Column Headers from line 1 of CSV", so the app was rendering a CSV all along; the HTML
is a faithful table, not a layout.

## The schema is NOT the same as the 2026 Drive format

Old (6 columns): Case Number, Date/Time Reported, Date/Time Occurred, Nature,
General Location, Disposition.

Differences that matter, each handled below:

- **Campus is a prefix, not a column.** `General Location` is
  `<strong>Glassboro Campus</strong><br/>&bull; Rowan Blvd. Student Housing`.
- **There is no incident narrative.** That column is new in 2026. Legacy rows get an
  empty narrative, never a fabricated one.
- **There IS a student/non-student flag**, embedded in the disposition cell as
  `<strong>Student?:</strong> Student`. It appears on ~70% of legacy rows and was
  **dropped entirely** in the 2026 format. It is extracted into its own field so the
  loss is visible rather than silent.
- **Multi-value cells use `<br/>`-separated bullets**, not the 2026 format's `;`.
- **Some cells split a single value across `<br/>`** — 2017 rows render a date and its
  time on separate lines. These are rejoined with a space.
- **Case numbers carry no `RUPD` prefix.** A 2022 Rowan case is `22-026152`, where the
  2026 equivalent would be `RUPD 26-026152`. They are left exactly as published: adding
  a prefix the source never wrote would be fabrication, and the eras do not overlap, so
  nothing depends on reconciling them.
"""

from __future__ import annotations

import html as html_mod
import re

from .parse import SOURCE_FIELDS

LEGACY_HEADER = [
    "Case Number",
    "Date/Time Reported",
    "Date/Time Occurred",
    "Nature",
    "General Location",
    "Disposition",
]

ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL_RE = re.compile(r"<t([dh])[^>]*>(.*?)</t\1>", re.S | re.I)
BR_RE = re.compile(r"<br\s*/?>", re.I)
STRONG_RE = re.compile(r"<strong[^>]*>(.*?)</strong>", re.S | re.I)
STUDENT_RE = re.compile(r"<strong[^>]*>\s*Student\?:\s*</strong>\s*(.*)$", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
BULLET_RE = re.compile(r"^[•\-\*]\s*")


class LegacyParseError(RuntimeError):
    """The captured page was not a readable crime log."""


def _text(fragment: str) -> str:
    """Strip tags and entities from an HTML fragment and collapse whitespace."""
    s = html_mod.unescape(TAG_RE.sub("", fragment))
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def _bullets(cell_html: str) -> list[str]:
    """Split a cell into its `<br/>`-separated bullet values."""
    parts = [_text(p) for p in BR_RE.split(cell_html)]
    return [BULLET_RE.sub("", p).strip() for p in parts if BULLET_RE.sub("", p).strip()]


def _rows(page_html: str) -> list[list[str]]:
    """Return the raw inner HTML of each cell, per table row."""
    out = []
    for row in ROW_RE.findall(page_html):
        cells = [body for _, body in CELL_RE.findall(row)]
        if cells:
            out.append(cells)
    return out


def is_dead_page(page_html: str) -> bool:
    """True if this is the empty CMS shell the dead app serves for every month.

    Captures from 2026 onward return a valid HTTP 200 page with no table at all. Treating
    that as "the month is now empty" would read as a mass deletion, so it is detected and
    reported as an unusable capture instead.
    """
    return not any(len(cells) == 6 for cells in _rows(page_html))


def parse_legacy(page_html: str, month: str) -> list[dict[str, str]]:
    """Parse one archived month into records shaped like the current schema.

    Returns dicts carrying the eight canonical SOURCE_FIELDS (with an empty
    `Incident Narrative`, which did not exist in this era) plus legacy-only extras.
    """
    rows = _rows(page_html)

    header_idx = next(
        (i for i, cells in enumerate(rows) if [_text(c) for c in cells][:1] == ["Case Number"]),
        None,
    )
    if header_idx is None:
        raise LegacyParseError(f"{month}: no 'Case Number' header row found")

    header = [_text(c) for c in rows[header_idx]]
    if header != LEGACY_HEADER:
        raise LegacyParseError(f"{month}: unexpected legacy header {header}")

    records = []
    for cells in rows[header_idx + 1 :]:
        if len(cells) != 6:
            continue
        case, reported, occurred, nature, location, disposition = cells
        if not _text(case):
            continue

        campus, place = _split_location(location)
        disposition_text, student = _split_disposition(disposition)

        record = {
            "Case Number": _text(case),
            # 2017 rows split a date and its time across <br/>; rejoin rather than
            # letting the time become a second, orphaned value.
            "Date/Time Reported": " ".join(_bullets(reported)),
            "Date/Time Occurred": " ".join(_bullets(occurred)),
            # Bullets become the 2026 format's ";" separator so one category map serves
            # both eras.
            "Nature": "; ".join(_bullets(nature)),
            "Incident Narrative": "",  # did not exist before 2026 — never invented
            "Campus": campus,
            "Location": place,
            "Disposition": disposition_text,
            "student_flag": student,
            "source_month": month,
        }
        if any(record[f] for f in SOURCE_FIELDS):
            records.append(record)

    return records


def _split_location(cell_html: str) -> tuple[str, str]:
    """Split `General Location` into (campus, location).

    Campus is wrapped in `<strong>`; the location follows as a bullet. If the markup is
    missing, the whole cell becomes the location and campus stays blank rather than
    being guessed.
    """
    strong = STRONG_RE.search(cell_html)
    campus = _text(strong.group(1)) if strong else ""
    remainder = STRONG_RE.sub("", cell_html, count=1) if strong else cell_html
    return campus, "; ".join(_bullets(remainder))


def _split_disposition(cell_html: str) -> tuple[str, str]:
    """Split the disposition cell into (disposition, student flag).

    The student flag rides inside the disposition cell as a labelled bullet. Pulling it
    out keeps it from polluting the disposition vocabulary, and makes a field the 2026
    format no longer publishes explicitly visible.
    """
    student = ""
    kept = []
    for part in BR_RE.split(cell_html):
        match = STUDENT_RE.search(part)
        if match:
            student = _text(match.group(1))
            continue
        text = BULLET_RE.sub("", _text(part)).strip()
        if text:
            kept.append(text)
    return "; ".join(kept), student
