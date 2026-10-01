"""Layer 1: the immutable raw store.

Everything the source served us, kept byte-exact and never rewritten. This is the
evidence layer — if a row is later removed from the live sheet, the proof that it once
existed is a file in here, and the proof of when it vanished is the git history of this
directory.

Files are grouped by file id rather than by date so that one month's full revision
history is a single directory listing, and `git log data/raw/<id>/` reads as that
sheet's biography.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

from .fetch import FetchResult

RAW_DIR = "raw"
MANIFEST_NAME = "manifest.json"
RUNS_DIR = "_runs"


def _utc_today() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")


class RawStore:
    """Append-only snapshot store plus its manifest."""

    def __init__(self, data_dir: pathlib.Path):
        self.root = pathlib.Path(data_dir) / RAW_DIR
        self.manifest_path = self.root / MANIFEST_NAME
        self.runs_dir = self.root / RUNS_DIR

    # ---- manifest -------------------------------------------------------------

    def load_manifest(self) -> dict:
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return {"files": {}, "archive_started": _utc_today()}

    def save_manifest(self, manifest: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # ---- snapshots ------------------------------------------------------------

    def latest_sha256(self, manifest: dict, file_id: str) -> str | None:
        snaps = manifest.get("files", {}).get(file_id, {}).get("snapshots", [])
        return snaps[-1]["sha256"] if snaps else None

    def store(
        self,
        manifest: dict,
        file_id: str,
        name: str,
        month: str,
        result: FetchResult,
        today: str | None = None,
    ) -> bool:
        """Record a fetch. Writes a new snapshot only if the content changed.

        Returns True if a new snapshot file was written.

        Skipping identical content keeps the repository from accumulating 365 copies of
        an unchanged month per year. The manifest still records that the file was
        verified today, so "nothing changed" remains a positive, dated observation
        rather than an absence of evidence.
        """
        today = today or _utc_today()
        entry = manifest.setdefault("files", {}).setdefault(
            file_id,
            {"name": name, "month": month, "first_seen": today, "snapshots": [], "status": "present"},
        )
        entry["name"] = name or entry.get("name", "")
        entry["month"] = month or entry.get("month", "")
        entry["last_verified"] = today
        entry["status"] = "present"
        entry.pop("missing_since", None)

        if self.latest_sha256(manifest, file_id) == result.sha256:
            return False

        target_dir = self.root / file_id
        target_dir.mkdir(parents=True, exist_ok=True)

        # If the content changes twice in one day, keep both rather than overwrite —
        # the raw store is append-only and nothing in it may ever be rewritten.
        stem, suffix = today, 1
        while (target_dir / f"{stem}.csv").exists():
            suffix += 1
            stem = f"{today}.{suffix}"

        (target_dir / f"{stem}.csv").write_bytes(result.body)
        (target_dir / f"{stem}.headers.json").write_text(
            json.dumps(result.provenance(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        entry["snapshots"].append({"date": stem, "sha256": result.sha256, "bytes": result.byte_length})
        return True

    def mark_unfetched(self, manifest: dict, file_id: str, reason: str, today: str | None = None) -> None:
        """Record that a known file could not be fetched.

        This is explicitly NOT a deletion. The entry keeps its snapshots and its rows
        stay active in the archive; only the fetch outcome is recorded.
        """
        today = today or _utc_today()
        entry = manifest.setdefault("files", {}).setdefault(
            file_id, {"name": "", "month": "", "first_seen": today, "snapshots": [], "status": "present"}
        )
        entry["status"] = "unfetched"
        entry["last_fetch_error"] = {"date": today, "reason": reason}
        entry.setdefault("missing_since", today)

    def snapshot_path(self, file_id: str, date: str) -> pathlib.Path:
        return self.root / file_id / f"{date}.csv"

    def read_snapshot(self, file_id: str, date: str) -> bytes:
        return self.snapshot_path(file_id, date).read_bytes()

    # ---- run heartbeat --------------------------------------------------------

    def write_run_record(self, record: dict, today: str | None = None) -> pathlib.Path:
        """Write a per-run record, on every run, whether or not anything changed.

        Two reasons this is not optional:

        1. GitHub disables scheduled workflows in a repository with no commit activity
           for 60 days. Because snapshots are written only on change, a quiet stretch
           (say, winter break) would produce no commits and silently switch the scraper
           off — precisely when nobody would notice.
        2. For a journalist, "we verified on 47 consecutive days that this row was
           present, and on day 48 it was gone" is the evidentiary core of the project.
           A dated record of an uneventful check is itself evidence.
        """
        today = today or _utc_today()
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        path = self.runs_dir / f"{today}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        return path
