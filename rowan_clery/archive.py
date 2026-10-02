"""Layer 2: the append-only canonical archive.

This module holds the project's central promise: **no record that has ever been
observed is ever lost**, whatever the university later does to the source.

Three rules govern everything here.

1. Rows are appended and amended in place, never deleted. A row that disappears from
   the source is marked, not removed, and its last known values stay readable.
2. A row may move toward `withdrawn` only if its source file was fetched SUCCESSFULLY
   and the row was genuinely absent. Absence of a file is never evidence of absence of
   its rows. A fetch failure must never look like a deletion.
3. The new archive is built entirely in memory, checked against a set of invariants,
   and only then written. A half-written archive is how this project would fail at the
   one job it has.
"""

from __future__ import annotations

import csv
import dataclasses
import datetime as dt
import json
import pathlib

from .parse import (
    SOURCE_FIELDS,
    canonical_reported,
    is_cosmetic_date_change,
    normalize_case_number,
)

ARCHIVE_COLUMNS = [
    "incident_uid",
    "case_number_raw",
    "case_number_norm",
    "date_reported_raw",
    "date_occurred_raw",
    "nature_raw",
    "narrative_raw",
    "campus_raw",
    "location_raw",
    "disposition_raw",
    "source_file_id",
    "source_file_name",
    "source_month",
    # Which publication era this row came from. The pre-2026 PHP log and the 2026 Drive
    # sheets are different schemas, and any view that mixes them has to say so.
    "source_era",
    # Student / Non Student / Unknown. Published on ~70% of pre-2026 rows and dropped
    # entirely in the 2026 format. Carried here so the loss is visible, not silent.
    "student_flag",
    "source_row_index",
    "content_hash",
    "first_seen_by_archive",
    "last_verified",
    "missing_since",
    "missing_count",
    # Last date this row was absent from a trusted snapshot. Persisted so that several
    # runs on the same day cannot push a row toward withdrawal faster than the
    # confirmation window intends.
    "last_absent",
    "status",
    # Set when an identity-field amendment produced a second uid for one incident;
    # points at the row that replaced this one. See backfill.reconcile_identity_amendments.
    "superseded_by",
    "revision",
    "flags",
]

# Source column -> archive column, for the eight verbatim fields.
FIELD_MAP = {
    "Case Number": "case_number_raw",
    "Date/Time Reported": "date_reported_raw",
    "Date/Time Occurred": "date_occurred_raw",
    "Nature": "nature_raw",
    "Incident Narrative": "narrative_raw",
    "Campus": "campus_raw",
    "Location": "location_raw",
    "Disposition": "disposition_raw",
}

# A row must be absent from this many SUCCESSFUL fetches, on distinct calendar days,
# before it is called withdrawn. A row that vanishes for a day and returns is a story in
# itself, but it is not a deletion.
WITHDRAWAL_CONFIRMATIONS = 3

# Per-file shrink guards. Exceeding either sends the file to quarantine: its raw
# snapshot is still written (it is evidence), but no archive mutation is applied and the
# run exits non-zero for a human to look at.
MAX_SILENT_DROPS = 2
MIN_RETENTION = 0.90

# Corpus-wide brake, applied across all files before anything is written.
MAX_CORPUS_DROP_FRACTION = 0.05
MAX_CORPUS_DROP_ROWS = 10


class ArchiveIntegrityError(RuntimeError):
    """An invariant that must never fail, failed. Nothing is written."""


class QuarantineError(RuntimeError):
    """A change too large to apply automatically. Needs human confirmation."""


def _utc_today() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


@dataclasses.dataclass
class MergeReport:
    """What a single run did, for the commit message, the page and the run record."""

    added: int = 0
    amended: int = 0
    missing: int = 0
    withdrawn: int = 0
    source_removed: int = 0
    reappeared: int = 0
    relocated: int = 0
    unchanged: int = 0
    quarantined: list[str] = dataclasses.field(default_factory=list)
    unfetched: list[str] = dataclasses.field(default_factory=list)
    warnings: list[str] = dataclasses.field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(
            self.added or self.amended or self.withdrawn or self.source_removed
            or self.reappeared or self.relocated
        )

    def summary(self) -> str:
        return (
            f"+{self.added} added, {self.amended} amended, {self.missing} missing, "
            f"{self.withdrawn} withdrawn, {self.source_removed} source-removed, "
            f"{self.reappeared} reappeared"
        )

    def as_dict(self) -> dict:
        return dataclasses.asdict(self) | {"changed": self.changed}


class Archive:
    """Loads, merges and writes the canonical incident archive."""

    def __init__(self, data_dir: pathlib.Path):
        self.dir = pathlib.Path(data_dir) / "archive"
        self.incidents_path = self.dir / "incidents.csv"
        self.changelog_path = self.dir / "changelog.jsonl"

    # ---- io -------------------------------------------------------------------

    def load(self) -> dict[str, dict[str, str]]:
        if not self.incidents_path.exists():
            return {}
        with self.incidents_path.open(newline="", encoding="utf-8") as fh:
            return {row["incident_uid"]: row for row in csv.DictReader(fh)}

    def rows_per_file(self) -> dict[str, int]:
        """How many archived rows each source file accounts for."""
        counts: dict[str, int] = {}
        for row in self.load().values():
            counts[row.get("source_file_id", "")] = counts.get(row.get("source_file_id", ""), 0) + 1
        return counts

    def write(self, rows: dict[str, dict[str, str]]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        # Sorted by uid so the file has a stable order and git diffs show only real
        # changes rather than reshuffled lines.
        with self.incidents_path.open("w", newline="", encoding="utf-8") as fh:
            # Explicit LF: csv defaults to CRLF, which git would then normalize on every
            # commit. A derived file whose bytes git rewrites produces noisy diffs and
            # makes it harder to see the changes that actually matter.
            writer = csv.DictWriter(
                fh, fieldnames=ARCHIVE_COLUMNS, extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            for uid in sorted(rows):
                writer.writerow(rows[uid])

    def append_changelog(self, events: list[dict]) -> None:
        if not events:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.changelog_path.open("a", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")

    def read_changelog(self) -> list[dict]:
        if not self.changelog_path.exists():
            return []
        with self.changelog_path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    # ---- merge ----------------------------------------------------------------

    def merge(
        self,
        observed_by_file: dict[str, list[dict[str, str]]],
        fetched_ok: set[str],
        file_meta: dict[str, dict[str, str]] | None = None,
        removed_files: set[str] | None = None,
        today: str | None = None,
        confirm_withdrawals: bool = True,
    ) -> tuple[dict[str, dict[str, str]], list[dict], MergeReport]:
        """Merge one run's observations into the archive.

        `observed_by_file` holds parsed incidents keyed by source file id, and contains
        an entry only for files that were fetched and validated successfully.
        `fetched_ok` is the set of file ids whose fetch succeeded — the authority for
        whether an absent row means anything at all.
        `removed_files` is the set of file ids confirmed gone from the source (a direct
        fetch by id returned 404/403 on enough distinct days). Their rows are preserved
        in full and marked `source_removed`.

        Returns (new_rows, changelog_events, report) WITHOUT writing anything, so the
        caller can assert invariants on the result first.
        """
        today = today or _utc_today()
        file_meta = file_meta or {}
        removed_files = removed_files or set()
        existing = self.load()
        report = MergeReport()
        events: list[dict] = []

        observed: dict[str, dict[str, str]] = {}
        for file_id, incidents in observed_by_file.items():
            for record in incidents:
                observed[record["incident_uid"]] = record

        # Per-file shrink guards. Quarantine makes a file ABSENCE-BLIND: its rows can
        # still be added and amended, but nothing it fails to mention is treated as
        # missing. Discarding its observations outright would also throw away genuinely
        # new rows — that cost 9 December 2021 incidents before this was fixed. Additions
        # are never destructive; only inferred absence is.
        quarantined_files = self._check_shrink(existing, observed_by_file, fetched_ok, report)
        trusted = fetched_ok - quarantined_files

        new_rows: dict[str, dict[str, str]] = {}

        for uid, row in existing.items():
            row = dict(row)
            if uid in observed:
                row, row_events = self._apply_seen(row, observed[uid], file_meta, today, report)
                events.extend(row_events)
            elif row.get("source_file_id") in removed_files:
                row, row_events = self._apply_source_removed(row, today, report)
                events.extend(row_events)
            elif confirm_withdrawals:
                row, row_events = self._apply_absent(row, trusted, today, report)
                events.extend(row_events)
            else:
                # Backfill mode. Wayback captures are irregular and often years apart, so
                # "absent from the next capture" cannot be laddered into a withdrawal the
                # way daily observations can. Absences are flagged for review instead.
                row, row_events = self._flag_absent(row, trusted, today, report)
                events.extend(row_events)
            new_rows[uid] = row

        for uid, record in observed.items():
            if uid in new_rows:
                continue
            new_rows[uid] = self._new_row(record, file_meta, today)
            report.added += 1
            events.append(
                {
                    "observed_date": today,
                    "incident_uid": uid,
                    "change_type": "added",
                    "case_number": record["Case Number"],
                    "date_reported": record["Date/Time Reported"],
                    "nature": record["Nature"],
                }
            )

        # Rows whose whole source file was confirmed gone are exempt from the corpus
        # brake below: that transition has already cleared the file-level confirmation
        # ladder, so it is explained loss. The brake exists to catch UNEXPLAINED loss.
        exempt = {uid for uid, row in new_rows.items() if row.get("status") == "source_removed"}
        self._assert_invariants(existing, new_rows, exempt=exempt)
        return new_rows, events, report

    # ---- merge helpers --------------------------------------------------------

    def _new_row(self, record: dict[str, str], file_meta: dict, today: str) -> dict[str, str]:
        meta = file_meta.get(record["source_file_id"], {})
        row = {
            "incident_uid": record["incident_uid"],
            "case_number_norm": normalize_case_number(record["Case Number"]),
            "source_file_id": record["source_file_id"],
            "source_file_name": meta.get("name", ""),
            "source_month": meta.get("month", "") or record.get("source_month", ""),
            "source_era": record.get("source_era", "drive-2026"),
            "student_flag": record.get("student_flag", ""),
            "source_row_index": record.get("source_row_index", ""),
            "content_hash": record["content_hash"],
            # Named for what it can actually attest to. The archive cannot say anything
            # about a row's state before the day it started watching.
            "first_seen_by_archive": today,
            "last_verified": today,
            "missing_since": "",
            "missing_count": "0",
            "status": "active",
            "revision": "1",
            "flags": record.get("flags", ""),
        }
        row.update({FIELD_MAP[f]: record.get(f, "") for f in SOURCE_FIELDS})
        return row

    def _apply_seen(
        self, row: dict[str, str], record: dict[str, str], file_meta: dict, today: str, report: MergeReport
    ) -> tuple[dict[str, str], list[dict]]:
        """The row is present in a trusted snapshot: verify, amend, or restore it."""
        events: list[dict] = []
        uid = row["incident_uid"]

        if row.get("status") in ("missing", "withdrawn"):
            events.append(
                {
                    "observed_date": today,
                    "incident_uid": uid,
                    "change_type": "reappeared",
                    "was_missing_since": row.get("missing_since", ""),
                    "previous_status": row.get("status", ""),
                }
            )
            report.reappeared += 1
            # The disappearance stays on the record permanently. A row that vanished and
            # came back is a different kind of fact from one that was never away.
            flags = set(filter(None, row.get("flags", "").split(";")))
            flags.add("was_missing")
            row["flags"] = ";".join(sorted(flags))

        if record["source_file_id"] != row.get("source_file_id"):
            events.append(
                {
                    "observed_date": today,
                    "incident_uid": uid,
                    "change_type": "relocated",
                    "from_file_id": row.get("source_file_id", ""),
                    "to_file_id": record["source_file_id"],
                }
            )
            report.relocated += 1

        if record["content_hash"] != row.get("content_hash"):
            for field in SOURCE_FIELDS:
                old, new = row.get(FIELD_MAP[field], ""), record.get(field, "")
                if old != new:
                    # A date the source merely reformatted (02/13/22 -> 02/13/2022) is a
                    # real edit but not a newsworthy one. Marking it keeps 35 such
                    # reformats in February 2022 alone from burying genuine amendments
                    # in the change feed. It is recorded, not discarded.
                    cosmetic = is_cosmetic_date_change(FIELD_MAP[field], old, new)
                    events.append(
                        {
                            "observed_date": today,
                            "incident_uid": uid,
                            "change_type": "amended",
                            "field": FIELD_MAP[field],
                            "old": old,
                            "new": new,
                            "case_number": record["Case Number"],
                            "cosmetic": cosmetic,
                        }
                    )
            row["revision"] = str(int(row.get("revision") or 0) + 1)
            report.amended += 1
        else:
            report.unchanged += 1

        meta = file_meta.get(record["source_file_id"], {})
        row.update({FIELD_MAP[f]: record.get(f, "") for f in SOURCE_FIELDS})
        row["case_number_norm"] = normalize_case_number(record["Case Number"])
        row["content_hash"] = record["content_hash"]
        row["source_file_id"] = record["source_file_id"]
        row["source_file_name"] = meta.get("name", row.get("source_file_name", ""))
        row["source_month"] = meta.get("month", "") or record.get("source_month", "") or row.get("source_month", "")
        row["source_era"] = record.get("source_era", row.get("source_era", ""))
        # Never blank an existing student flag: a later capture that omits it has lost
        # the value, not learned that it is empty.
        row["student_flag"] = record.get("student_flag") or row.get("student_flag", "")
        row["source_row_index"] = record.get("source_row_index", "")
        row["last_verified"] = today
        row["missing_since"] = ""
        row["missing_count"] = "0"
        row["status"] = "active"
        if record.get("flags"):
            flags = set(filter(None, row.get("flags", "").split(";"))) | set(record["flags"].split(";"))
            row["flags"] = ";".join(sorted(filter(None, flags)))
        return row, events

    def _apply_absent(
        self, row: dict[str, str], trusted: set[str], today: str, report: MergeReport
    ) -> tuple[dict[str, str], list[dict]]:
        """The row was not in this run's observations.

        This only means something if the row's source file was fetched successfully and
        was not quarantined. Otherwise we simply do not know, and the row is left
        completely untouched — the single most important branch in this file.
        """
        if row.get("source_file_id") not in trusted:
            return row, []

        if row.get("status") == "withdrawn":
            return row, []  # already settled; don't re-log every day

        # Count at most one absence per calendar day, so a manual re-run cannot push a
        # row toward withdrawal faster than the confirmation window allows.
        if row.get("missing_since") == today or row.get("last_absent") == today:
            return row, []

        count = int(row.get("missing_count") or 0) + 1
        row["missing_count"] = str(count)
        row["last_absent"] = today
        if not row.get("missing_since"):
            row["missing_since"] = today

        events = []
        if count >= WITHDRAWAL_CONFIRMATIONS:
            row["status"] = "withdrawn"
            report.withdrawn += 1
            events.append(
                {
                    "observed_date": today,
                    "incident_uid": row["incident_uid"],
                    "change_type": "withdrawn",
                    "missing_since": row["missing_since"],
                    "confirmations": count,
                    "case_number": row.get("case_number_raw", ""),
                    "date_reported": row.get("date_reported_raw", ""),
                    "nature": row.get("nature_raw", ""),
                    "last_known_disposition": row.get("disposition_raw", ""),
                }
            )
        else:
            row["status"] = "missing"
            report.missing += 1
            events.append(
                {
                    "observed_date": today,
                    "incident_uid": row["incident_uid"],
                    "change_type": "missing",
                    "missing_since": row["missing_since"],
                    "confirmations": count,
                    "case_number": row.get("case_number_raw", ""),
                }
            )
        return row, events

    def _apply_source_removed(
        self, row: dict[str, str], today: str, report: MergeReport
    ) -> tuple[dict[str, str], list[dict]]:
        """The row's entire source file is gone from Drive.

        Kept distinct from `withdrawn`, which means an individual row was taken out of a
        sheet that still exists. A whole month disappearing is a different and larger
        event, and conflating the two would understate it.

        Every field is preserved. This status says "the source no longer publishes
        this", not "this did not happen".
        """
        if row.get("status") == "source_removed":
            return row, []
        previous = row.get("status", "")
        row["status"] = "source_removed"
        row["missing_since"] = row.get("missing_since") or today
        report.source_removed += 1
        return row, [
            {
                "observed_date": today,
                "incident_uid": row["incident_uid"],
                "change_type": "source_removed",
                "source_file_id": row.get("source_file_id", ""),
                "source_month": row.get("source_month", ""),
                "previous_status": previous,
                "case_number": row.get("case_number_raw", ""),
                "date_reported": row.get("date_reported_raw", ""),
                "nature": row.get("nature_raw", ""),
                "last_known_disposition": row.get("disposition_raw", ""),
            }
        ]

    def _flag_absent(
        self, row: dict[str, str], trusted: set[str], today: str, report: MergeReport
    ) -> tuple[dict[str, str], list[dict]]:
        """Note that a row was absent from a capture, without advancing any ladder.

        Verified against February 2021 across captures in 2021, 2023 and 2025: Rowan does
        not retroactively delete from closed months. So an absence here is rare and
        deserves a human look rather than an automatic status change.
        """
        if row.get("source_file_id") not in trusted or row.get("status") != "active":
            return row, []
        flags = set(filter(None, row.get("flags", "").split(";")))
        flags.add("absent_in_later_capture")
        row["flags"] = ";".join(sorted(flags))
        report.warnings.append(
            f"{row['incident_uid']} ({row.get('case_number_raw','')}) was absent from the "
            f"{today} capture of {row.get('source_month','')} — flagged for review, not withdrawn"
        )
        return row, [{
            "observed_date": today,
            "incident_uid": row["incident_uid"],
            "change_type": "absent_in_later_capture",
            "source_month": row.get("source_month", ""),
            "case_number": row.get("case_number_raw", ""),
        }]

    def _check_shrink(
        self,
        existing: dict[str, dict[str, str]],
        observed_by_file: dict[str, list[dict[str, str]]],
        fetched_ok: set[str],
        report: MergeReport,
    ) -> set[str]:
        """Quarantine any file that lost more rows than a routine correction would."""
        quarantined: set[str] = set()
        for file_id in fetched_ok:
            prior = {
                uid
                for uid, row in existing.items()
                if row.get("source_file_id") == file_id and row.get("status") in ("active", "missing")
            }
            if not prior:
                continue
            seen = {r["incident_uid"] for r in observed_by_file.get(file_id, [])}
            dropped = prior - seen
            retention = len(prior & seen) / len(prior)

            if not seen:
                quarantined.add(file_id)
                report.warnings.append(f"{file_id}: fetch validated but produced zero rows — quarantined")
            elif len(dropped) > MAX_SILENT_DROPS or retention < MIN_RETENTION:
                quarantined.add(file_id)
                report.warnings.append(
                    f"{file_id}: {len(dropped)} of {len(prior)} rows absent "
                    f"(retention {retention:.0%}) — quarantined, archive untouched for this file"
                )
            elif dropped:
                report.warnings.append(f"{file_id}: {len(dropped)} row(s) absent — advancing confirmation ladder")

        report.quarantined = sorted(quarantined)
        return quarantined

    def _assert_invariants(
        self,
        old: dict[str, dict[str, str]],
        new: dict[str, dict[str, str]],
        exempt: set[str] | None = None,
    ) -> None:
        """Checks that must hold before anything touches disk.

        These are not defensive niceties. Each one corresponds to a way this project
        could quietly destroy the evidence it exists to preserve.
        """
        lost = set(old) - set(new)
        if lost:
            raise ArchiveIntegrityError(
                f"{len(lost)} uid(s) would vanish from the archive: {sorted(lost)[:5]}. "
                "The archive is append-only; this must never happen."
            )
        if len(new) < len(old):
            raise ArchiveIntegrityError(f"archive would shrink from {len(old)} to {len(new)} rows")

        for uid, row in new.items():
            if uid in old:
                was, now = old[uid], row
                if was.get("first_seen_by_archive") != now.get("first_seen_by_archive"):
                    raise ArchiveIntegrityError(f"{uid}: first_seen_by_archive was rewritten")
                # Identity is derived from these two fields; if either changed, the uid
                # would no longer describe the row and a different incident has been
                # written over this one.
                if was.get("case_number_norm") and was["case_number_norm"] != now.get("case_number_norm"):
                    raise ArchiveIntegrityError(f"{uid}: case number changed under a fixed uid")
                # Compare the CANONICAL date, not the raw string: the source reformats
                # dates without changing them (02/13/22 -> 02/13/2022), and a cosmetic
                # reformat under a stable uid is correct, not a violation.
                if was.get("date_reported_raw") and canonical_reported(
                    was["date_reported_raw"]
                ) != canonical_reported(now.get("date_reported_raw", "")):
                    raise ArchiveIntegrityError(f"{uid}: reported date changed under a fixed uid")

        exempt = exempt or set()
        active_old = sum(1 for uid, r in old.items() if r.get("status") == "active" and uid not in exempt)
        active_new = sum(1 for uid, r in new.items() if r.get("status") == "active" and uid not in exempt)
        drop = active_old - active_new
        if active_old and drop > MAX_CORPUS_DROP_ROWS and drop / active_old > MAX_CORPUS_DROP_FRACTION:
            raise ArchiveIntegrityError(
                f"active rows would fall from {active_old} to {active_new} ({drop} rows) in one run. "
                "Refusing to apply a change this large automatically."
            )
