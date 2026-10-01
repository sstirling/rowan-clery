"""Parse a crime-log CSV into incident records and assign stable identities.

The identity key is the most consequential decision in this project. Get it wrong and
either routine amendments look like deletions (destroying the audit trail) or two
distinct incidents collapse into one (losing a record).
"""

from __future__ import annotations

import csv
import hashlib
import io
import re

SOURCE_FIELDS = [
    "Case Number",
    "Date/Time Reported",
    "Date/Time Occurred",
    "Nature",
    "Incident Narrative",
    "Campus",
    "Location",
    "Disposition",
]

UNIT_SEP = "\x1f"


class ParseError(RuntimeError):
    """The CSV did not look like a crime log."""


def normalize_case_number(raw: str) -> str:
    """Collapse whitespace and upper-case a case number, and nothing else.

    Case numbers come in many shapes: plain ("CSA 86047"), dual references
    ("RUPD 26-028143/ CSA 85932"), multiple CSA numbers ("CSA 86141, 86143"), and
    combinations naming several agencies at once. Only whitespace and case are touched.

    Resist any temptation to "extract the RUPD number" — a rule like that would merge
    distinct incidents that happen to share one agency reference. Searchable agency
    references are derived separately, downstream, and never used for identity.
    """
    return re.sub(r"\s+", " ", raw or "").strip().upper()


def content_hash(record: dict[str, str]) -> str:
    """sha256 over the eight raw source fields, for revision detection."""
    joined = UNIT_SEP.join(record.get(f, "") for f in SOURCE_FIELDS)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def incident_uid(case_number: str, date_reported: str) -> str:
    """Derive the permanent identity of an incident.

    uid = sha1(normalized case number | raw Date/Time Reported)[:16]

    Two fields, chosen for IMMUTABILITY rather than for uniqueness:

    - `Case Number` is the natural identifier, but not unique on its own. Verified:
      RUPD 26-026280 appears twice (reported 8/17 and 8/21). Keying on it alone drops
      one of them.
    - `Date/Time Reported` is the clock time a report was filed — a clerical fact that
      has not been observed to change. It parses for 100% of rows (186/186) and it
      resolves the one real collision. Verified across all 186 live rows: 186 distinct
      uids, zero collisions.

    Deliberately EXCLUDED, and why each exclusion matters:

    - `Date/Time Occurred` IS amended — it gets refined from "Unk." to a real time.
    - `Nature`, `Disposition`, `Incident Narrative`, `Location` are precisely the fields
      Rowan amends after publication. ~10% of current rows carry "Disposition updated"
      or "Nature updated" markers, including one offense escalated to Aggravated
      Assault-Strangulation. Keying on them would log every amendment as a deletion plus
      an unrelated insertion, destroying the audit trail this archive exists to create.
    - `source_file_id` is excluded, which is subtle but critical. If Rowan deletes a
      monthly sheet and re-uploads it — an ordinary thing to do — the file id changes.
      A file-scoped key would then record every row in that month as withdrawn and an
      equal number as new, fabricating a mass deletion. File-independent identity means
      that event is correctly recorded as a relocation instead.
    - Row position is excluded. Any ordinal recomputed from the current snapshot's order
      is positional, and position is derived from mutable data. If the first of a
      duplicate pair were deleted, the second's ordinal would shift, inventing an
      amendment and hiding the real deletion — the exact failure this project must not
      have.

    The invariant: a uid, once written to the archive, is immutable for the life of the
    project. Never recompute identity from a later snapshot's shape.
    """
    basis = f"{normalize_case_number(case_number)}{UNIT_SEP}{re.sub(r'\s+', ' ', date_reported or '').strip()}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def parse_csv(data: bytes | str, file_id: str) -> list[dict[str, str]]:
    """Parse one monthly sheet into a list of incident dicts.

    Sheets open with a title banner ("Rowan University Daily Crime Log, September 2026")
    before the header row. Rather than assume the header is always the second line,
    locate it by content, so an extra banner row cannot shift every field by one column.
    """
    text = data.decode("utf-8-sig", "replace") if isinstance(data, bytes) else data
    rows = list(csv.reader(io.StringIO(text)))

    header_idx = next((i for i, row in enumerate(rows[:10]) if any(c.strip() == "Case Number" for c in row)), None)
    if header_idx is None:
        raise ParseError(f"{file_id}: no header row containing 'Case Number' in first 10 rows")

    header = [c.strip() for c in rows[header_idx]]
    missing = [f for f in SOURCE_FIELDS if f not in header]
    if missing:
        raise ParseError(f"{file_id}: header is missing expected columns: {missing}")

    col = {f: header.index(f) for f in SOURCE_FIELDS}
    incidents = []
    for row_index, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
        if not any(c.strip() for c in row):
            continue  # blank spacer row
        record = {f: (row[i].strip() if i < len(row) else "") for f, i in col.items()}
        if not any(record.values()):
            continue
        record["source_file_id"] = file_id
        # Informational only. Never part of identity — see incident_uid().
        record["source_row_index"] = str(row_index)
        incidents.append(record)

    return incidents


def source_month(data: bytes | str) -> str:
    """Read the month label from the sheet's banner row.

    Taken from the banner rather than the file name because the banner is part of the
    document's own content, and the file name is metadata the owner can change freely.
    """
    text = data.decode("utf-8-sig", "replace") if isinstance(data, bytes) else data
    first = next(csv.reader(io.StringIO(text)), [""])
    match = re.search(r"Daily Crime Log,\s*([A-Z][a-z]+ \d{4})", first[0] if first else "")
    return match.group(1) if match else ""


def flag_near_duplicates(incidents: list[dict[str, str]]) -> None:
    """Mark rows that share a case number and are identical but for their dates.

    The RUPD 26-026280 pair is byte-identical in six of eight fields, including the
    narrative verbatim and the disposition. That is consistent with two real incidents
    involving a repeat offender at the same spot — and equally consistent with a
    copy-paste error in the source.

    Both rows are preserved either way; this only records the ambiguity so the tool
    never silently presents a possible duplicate as two confirmed incidents. Resolving
    it needs a call to RUPD, not a heuristic.
    """
    by_case: dict[str, list[dict[str, str]]] = {}
    for record in incidents:
        by_case.setdefault(normalize_case_number(record["Case Number"]), []).append(record)

    comparable = [f for f in SOURCE_FIELDS if f not in ("Date/Time Reported", "Date/Time Occurred")]
    for group in by_case.values():
        if len(group) < 2:
            continue
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                if all(a[f] == b[f] for f in comparable):
                    for record in (a, b):
                        flags = set(filter(None, record.get("flags", "").split(";")))
                        flags.add("near_duplicate")
                        record["flags"] = ";".join(sorted(flags))


def parse_and_key(data: bytes | str, file_id: str) -> list[dict[str, str]]:
    """Parse a sheet, assign uids and content hashes, and flag near-duplicates."""
    incidents = parse_csv(data, file_id)
    for record in incidents:
        record["incident_uid"] = incident_uid(record["Case Number"], record["Date/Time Reported"])
        record["content_hash"] = content_hash(record)
        record.setdefault("flags", "")
    flag_near_duplicates(incidents)
    return incidents
