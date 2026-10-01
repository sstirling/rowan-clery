"""Orchestration: one daily run, from Drive to the canonical archive.

Order of operations matters here. Everything is fetched and validated before anything
is diffed, and the archive is written only once the whole run has been assembled and
checked. A run that fails partway through leaves the archive exactly as it was.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

from . import archive as archive_mod
from . import fetch, parse, snapshot

# A pinned file must fail a direct fetch-by-id on this many distinct days before its
# rows are marked `source_removed`. A single 404 is far more likely to be a Drive
# hiccup than a deletion.
FILE_REMOVAL_CONFIRMATIONS = 3

# The expensive conclusive tab census runs only when a file changed, or weekly.
TAB_CENSUS_INTERVAL_DAYS = 7


class RunFailure(RuntimeError):
    """The run could not complete safely. The archive was not modified."""


def load_known_files(config_dir: pathlib.Path) -> tuple[str, dict[str, str]]:
    config = json.loads((pathlib.Path(config_dir) / "known_files.json").read_text(encoding="utf-8"))
    return config["folder_id"], config["files"]


def run(
    data_dir: pathlib.Path,
    config_dir: pathlib.Path,
    today: str | None = None,
    allow_listing_failure: bool = True,
) -> dict:
    """Execute one full daily run and return a structured report."""
    today = today or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    data_dir, config_dir = pathlib.Path(data_dir), pathlib.Path(config_dir)
    folder_id, pinned = load_known_files(config_dir)

    store = snapshot.RawStore(data_dir)
    manifest = store.load_manifest()
    manifest.setdefault("archive_started", today)

    report: dict = {
        "date": today,
        "folder_id": folder_id,
        "listing": {},
        "files": {},
        "alarms": [],
        "warnings": [],
    }

    # ---- 1. discover ---------------------------------------------------------
    discovered: dict[str, dict[str, str]] = {}
    try:
        discovered = fetch.list_folder(folder_id)
        report["listing"] = {"status": "ok", "count": len(discovered)}
    except fetch.FetchError as exc:
        # A broken listing must never read as "no new files". It does not stop the run,
        # because the pinned ids are fetched directly regardless — but it is an alarm.
        report["listing"] = {"status": "failed", "error": str(exc)}
        report["alarms"].append(f"Folder listing failed: {exc}")
        if not allow_listing_failure:
            raise RunFailure(f"Folder listing failed: {exc}") from exc

    missing_from_listing = set(pinned) - set(discovered)
    if discovered and missing_from_listing:
        # Not a deletion on its own. The direct fetch below is what decides.
        report["warnings"].append(
            f"{len(missing_from_listing)} pinned file(s) absent from the listing: {sorted(missing_from_listing)}"
        )

    newly_discovered = set(discovered) - set(pinned)
    if newly_discovered:
        report["warnings"].append(
            f"New file(s) in the folder, not yet pinned in config/known_files.json: {sorted(newly_discovered)}"
        )

    # The union is the floor: a listing regression can never shrink what we fetch.
    targets = sorted(set(pinned) | set(discovered))

    # ---- 2. fetch and snapshot ----------------------------------------------
    observed: dict[str, list[dict[str, str]]] = {}
    fetched_ok: set[str] = set()
    file_meta: dict[str, dict[str, str]] = {}
    removed_files: set[str] = set()

    for file_id in targets:
        name = discovered.get(file_id, {}).get("name") or pinned.get(file_id, "")
        entry = manifest.setdefault("files", {}).setdefault(
            file_id, {"name": name, "month": "", "first_seen": today, "snapshots": [], "status": "present"}
        )
        try:
            result = fetch.fetch_csv(file_id)
        except fetch.FetchError as exc:
            state = _record_fetch_failure(entry, file_id, exc, today, pinned, report)
            store.mark_unfetched(manifest, file_id, str(exc), today)
            if state == "removed":
                removed_files.add(file_id)
            report["files"][file_id] = {"name": name, "status": state, "error": str(exc)}
            continue

        try:
            incidents = parse.parse_and_key(result.body, file_id)
            month = parse.source_month(result.body)
        except parse.ParseError as exc:
            report["alarms"].append(f"{file_id}: parsed as valid CSV but not as a crime log: {exc}")
            store.mark_unfetched(manifest, file_id, f"parse error: {exc}", today)
            report["files"][file_id] = {"name": name, "status": "unparseable", "error": str(exc)}
            continue

        # The file is back after having been absent.
        if entry.get("status") in ("unfetched", "removed"):
            report["warnings"].append(f"{file_id}: file reappeared after being absent")
        entry["absent_count"] = 0

        changed = store.store(manifest, file_id, name, month, result, today)
        file_meta[file_id] = {"name": name, "month": month}
        observed[file_id] = incidents
        fetched_ok.add(file_id)
        report["files"][file_id] = {
            "name": name,
            "month": month,
            "status": "ok",
            "rows": len(incidents),
            "sha256": result.sha256,
            "snapshot_written": changed,
        }

        if changed or _census_due(entry, today):
            _run_tab_census(file_id, entry, today, report)

    if not fetched_ok:
        # Every single file failed. That is an outage or a lockout, never a source in
        # which every record simultaneously ceased to exist.
        raise RunFailure(
            "No file could be fetched successfully. Refusing to diff — the archive is unchanged."
        )

    # ---- 3. merge ------------------------------------------------------------
    arch = archive_mod.Archive(data_dir)
    rows, events, merge_report = arch.merge(
        observed, fetched_ok, file_meta, removed_files=removed_files, today=today
    )
    arch.write(rows)
    arch.append_changelog(events)

    report["merge"] = merge_report.as_dict()
    report["summary"] = merge_report.summary()
    report["archive_rows"] = len(rows)
    report["warnings"].extend(merge_report.warnings)
    if merge_report.quarantined:
        report["alarms"].append(f"Quarantined file(s), archive untouched for them: {merge_report.quarantined}")

    store.save_manifest(manifest)
    store.write_run_record(report, today)
    return report


def _record_fetch_failure(
    entry: dict, file_id: str, exc: Exception, today: str, pinned: dict, report: dict
) -> str:
    """Advance the file-level removal ladder. Returns the file's new state."""
    if entry.get("last_absent_date") != today:
        entry["absent_count"] = int(entry.get("absent_count") or 0) + 1
        entry["last_absent_date"] = today
    count = int(entry.get("absent_count") or 0)

    if count >= FILE_REMOVAL_CONFIRMATIONS:
        entry["status"] = "removed"
        report["alarms"].append(
            f"{file_id} ({pinned.get(file_id, 'unknown')}): absent for {count} runs — "
            "treating the source file as removed. Its rows are preserved in full."
        )
        return "removed"

    report["warnings"].append(
        f"{file_id} ({pinned.get(file_id, 'unknown')}): fetch failed ({exc}); "
        f"absence {count} of {FILE_REMOVAL_CONFIRMATIONS}. Rows left untouched."
    )
    return "unfetched"


def _census_due(entry: dict, today: str) -> bool:
    last = entry.get("last_tab_census")
    if not last:
        return True
    delta = dt.date.fromisoformat(today) - dt.date.fromisoformat(last)
    return delta.days >= TAB_CENSUS_INTERVAL_DAYS


def _run_tab_census(file_id: str, entry: dict, today: str, report: dict) -> None:
    """Confirm the sheet still has exactly one tab.

    The CSV export only ever returns the first tab, so an added tab could silently
    change what the archive is recording. The Content-Disposition check in fetch_csv
    catches that on every run for free; this is the conclusive inventory.
    """
    try:
        tabs = fetch.sheet_tab_names(file_id)
    except fetch.FetchError as exc:
        report["warnings"].append(f"{file_id}: tab census failed ({exc})")
        return
    entry["last_tab_census"] = today
    entry["tabs"] = tabs
    if tabs != [fetch.EXPECTED_TAB]:
        report["alarms"].append(
            f"{file_id}: expected exactly one tab named {fetch.EXPECTED_TAB!r}, found {tabs}. "
            "The CSV export only returns the first tab, so other tabs are NOT being archived."
        )
