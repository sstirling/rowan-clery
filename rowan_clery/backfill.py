"""Replay the Internet Archive's captures of Rowan's pre-2026 crime log into the archive.

Each Wayback capture is treated as an observation dated to the capture, and the captures
are replayed in chronological order. The ordinary merge logic then does the rest: an
incident seen for the first time is an addition, and a field that differs from the last
capture is an amendment with both values recorded.

That reconstructs a change history nobody has otherwise: which dispositions Rowan revised
after publishing, and the window in which it happened. Verified on September 2022, where
four dispositions changed between captures — one to "Unfounded".

What it cannot do is date those changes precisely. Captures are irregular and often years
apart, so the honest claim is usually "changed between capture A and capture B".

Each month is merged under its own pseudo file id (`wayback:2022-09`), which reuses the
existing per-file scoping: a capture of one month says nothing about any other month's
rows, exactly as a real fetch of one sheet says nothing about the others.
"""

from __future__ import annotations

import pathlib
import re

from . import legacy, parse, wayback
from .archive import Archive

ERA = "cleryapp-php"


def pseudo_file_id(month: str) -> str:
    return f"wayback:{month}"


def _prepare(records: list[dict[str, str]], month: str) -> list[dict[str, str]]:
    """Attach identity and era metadata to parsed legacy records."""
    file_id = pseudo_file_id(month)
    out = []
    for record in records:
        enriched = dict(record)
        enriched["source_file_id"] = file_id
        enriched["source_era"] = ERA
        enriched["source_month"] = month
        enriched["incident_uid"] = parse.incident_uid(
            record["Case Number"], record["Date/Time Reported"]
        )
        enriched["content_hash"] = parse.content_hash(record)
        enriched.setdefault("flags", "")
        out.append(enriched)
    parse.flag_near_duplicates(out)
    return out


def run(data_dir: pathlib.Path, limit_months: list[str] | None = None, progress=print) -> dict:
    """Harvest and replay every archived capture. Returns a summary report."""
    data_dir = pathlib.Path(data_dir)
    store = wayback.CaptureStore(data_dir)
    archive = Archive(data_dir)

    captures = wayback.list_captures()
    if limit_months:
        captures = {m: c for m, c in captures.items() if m in limit_months}

    # Replay in capture order, not month order: a 2025 capture of September 2022 is a
    # later observation than a 2022 one, and the change log has to reflect that.
    timeline = sorted(
        ((c["timestamp"], month, c) for month, cs in captures.items() for c in cs),
        key=lambda t: t[0],
    )

    report = {
        "captures_total": len(timeline),
        "captures_used": 0,
        "captures_dead": 0,
        "captures_failed": 0,
        "months": sorted(captures),
        "added": 0,
        "amended": 0,
        "absent_flagged": 0,
        "warnings": [],
    }

    for timestamp, month, _capture in timeline:
        observed = wayback.capture_date(timestamp)
        try:
            html = store.fetch(month, timestamp)
        except wayback.WaybackError as exc:
            report["captures_failed"] += 1
            report["warnings"].append(f"{month} @ {timestamp}: fetch failed ({exc})")
            continue

        if legacy.is_dead_page(html):
            # From 2026 the PHP app returns an empty CMS shell for every month. It is a
            # valid HTTP 200 with no table, so without this check it would read as "the
            # month is now empty" and look like a mass deletion.
            report["captures_dead"] += 1
            continue

        try:
            records = _prepare(legacy.parse_legacy(html, month), month)
        except legacy.LegacyParseError as exc:
            report["captures_failed"] += 1
            report["warnings"].append(f"{month} @ {timestamp}: {exc}")
            continue

        if not records:
            report["captures_dead"] += 1
            continue

        file_id = pseudo_file_id(month)
        rows, events, merge_report = archive.merge(
            {file_id: records},
            {file_id},
            {file_id: {"name": f"cleryapp {month}", "month": month}},
            today=observed,
            confirm_withdrawals=False,
        )
        archive.write(rows)
        archive.append_changelog(
            [e | {"source": "wayback", "capture_timestamp": timestamp} for e in events]
        )

        report["captures_used"] += 1
        report["added"] += merge_report.added
        report["amended"] += merge_report.amended
        report["absent_flagged"] += sum(
            1 for e in events if e["change_type"] == "absent_in_later_capture"
        )
        report["warnings"].extend(merge_report.warnings)
        progress(
            f"  {observed}  {month}  {len(records):>4} rows  "
            f"+{merge_report.added} added, {merge_report.amended} amended"
        )

    report["archive_rows"] = len(archive.load())
    return report


def reconcile_identity_amendments(data_dir: pathlib.Path) -> list[dict]:
    """Link rows that are the same incident under an amended identity field.

    The uid is deliberately built from case number and reported date, on the assumption
    that Rowan does not revise them. That holds for the 2026 feed. It does NOT hold
    throughout the pre-2026 era, where three incidents were later re-published with an
    extended identity:

        22-030093          ->  22-030093/CSA on-line report
        24-006956          ->  24-006956/CSA 58387
        06/06/22           ->  06/06/22 0:01     (a time was added)

    Each produces two uids for one incident. Rather than loosen the key for everything —
    400 legacy rows have no parseable case-number core, so a looser key risks merging
    genuinely distinct incidents — the pair is detected and linked.

    The rule is deliberately strict: same month, same case-number core, same calendar
    date, and one of the two strings must be a literal PREFIX of the other. An extension
    is evidence of the same record being re-published with more detail; two merely
    similar rows are left alone.

    Nothing is deleted. The earlier row stays in full, marked `superseded`, pointing at
    the row that replaced it.
    """
    archive = Archive(data_dir)
    rows = archive.load()

    def core(case: str) -> str | None:
        match = re.search(r"\b(\d{2}-\d{5,6})\b", case or "")
        return match.group(1) if match else None

    def day(stamp: str) -> str:
        match = re.match(r"(\d{1,2}/\d{1,2}/\d{2,4})", (stamp or "").strip())
        return match.group(1) if match else (stamp or "").strip()

    groups: dict[tuple, list[dict]] = {}
    for row in rows.values():
        if row.get("source_era") != ERA or row.get("status") == "superseded":
            continue
        key = core(row["case_number_raw"])
        if not key:
            continue
        groups.setdefault((row["source_month"], key, day(row["date_reported_raw"])), []).append(row)

    events = []
    for group in groups.values():
        if len(group) < 2:
            continue
        # The fuller identity is the later publication.
        group.sort(key=lambda r: (len(r["case_number_raw"]), len(r["date_reported_raw"])))
        winner = group[-1]
        for loser in group[:-1]:
            case_extends = winner["case_number_raw"].startswith(loser["case_number_raw"])
            date_extends = winner["date_reported_raw"].startswith(loser["date_reported_raw"])
            if not (case_extends or date_extends):
                continue
            loser["status"] = "superseded"
            loser["superseded_by"] = winner["incident_uid"]
            flags = set(filter(None, loser.get("flags", "").split(";")))
            flags.discard("absent_in_later_capture")
            flags.add("superseded_identity")
            loser["flags"] = ";".join(sorted(flags))
            events.append({
                "observed_date": loser.get("last_verified", ""),
                "incident_uid": loser["incident_uid"],
                "change_type": "superseded_identity",
                "superseded_by": winner["incident_uid"],
                "old_case_number": loser["case_number_raw"],
                "new_case_number": winner["case_number_raw"],
                "old_date_reported": loser["date_reported_raw"],
                "new_date_reported": winner["date_reported_raw"],
                "source": "reconciliation",
            })

    if events:
        archive.write(rows)
        archive.append_changelog(events)
    return events


def flag_duplicate_candidates(data_dir: pathlib.Path) -> list[str]:
    """Flag rows that MIGHT be the same incident under a corrected case number.

    Deliberately flags rather than merges. A wider auto-merge rule was tested and
    rejected: grouping on month + reported minute + nature + location pulled in pairs
    like `GPD 25-034057` and `GPD 25-034052` — two distinct Glassboro PD summonses issued
    in the same minute at the same spot. Collapsing those would destroy records, which is
    a worse error than leaving a duplicate visible.

    So only the narrow, suspicious class is flagged: rows that agree on month, reported
    timestamp, nature and location AND whose case numbers overlap textually, which is
    what a corrected typo looks like (`21-03470` -> `21-034370`). A human decides.
    """
    archive = Archive(data_dir)
    rows = archive.load()

    groups: dict[tuple, list[dict]] = {}
    for row in rows.values():
        if row.get("status") == "superseded":
            continue
        key = (
            row["source_month"],
            parse.canonical_reported(row["date_reported_raw"]),
            row["nature_raw"].strip().lower(),
            row["location_raw"].strip().lower(),
        )
        groups.setdefault(key, []).append(row)

    def overlapping(a: str, b: str) -> bool:
        a, b = a.strip().upper(), b.strip().upper()
        if a in b or b in a:
            return True
        # Same digits in the same order, one having gained or lost a character — the
        # signature of a corrected transposition or dropped digit.
        da, db = re.sub(r"\D", "", a), re.sub(r"\D", "", b)
        return bool(da and db and (da in db or db in da)) and abs(len(da) - len(db)) <= 2

    flagged = []
    for group in groups.values():
        if len(group) < 2:
            continue
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                if not overlapping(a["case_number_raw"], b["case_number_raw"]):
                    continue
                for row in (a, b):
                    marks = set(filter(None, row.get("flags", "").split(";")))
                    marks.add("possible_duplicate_identity")
                    row["flags"] = ";".join(sorted(marks))
                    flagged.append(row["incident_uid"])

    if flagged:
        archive.write(rows)
    return sorted(set(flagged))
