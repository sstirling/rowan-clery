#!/usr/bin/env python3
"""Verify the raw evidence layer was only added to, never rewritten.

Run in CI before committing. Exits non-zero, naming the offending paths, if anything
that is supposed to be immutable changed.

`data/raw/` holds two different kinds of thing, and conflating them is a bug this
replaced:

  IMMUTABLE — the evidence itself. Byte-exact copies of what the source served:
    data/raw/<file_id>/<date>.csv          a snapshot
    data/raw/<file_id>/<date>.headers.json its HTTP provenance
    data/raw/_wayback/<month>/<ts>.html    an Internet Archive capture
  These may be added. They may never be modified or deleted.

  MUTABLE — bookkeeping about the evidence, which has to change every run:
    data/raw/manifest.json   last_verified, absent counts, snapshot hashes
    data/raw/_runs/<date>.json  one record per run

An earlier version of this check guarded all of `data/raw/`, so it failed the moment the
manifest recorded a new date — which is every single run. It passed exactly once, on a day
when the committed manifest happened to already carry that date.

The manifest is not evidence, but it is not free to shrink either: it is the index of
which snapshots exist. So it gets its own weaker invariant — entries may be added, never
dropped.
"""

from __future__ import annotations

import json
import subprocess
import sys

MUTABLE = (
    "data/raw/manifest.json",
    "data/raw/_runs/",
)


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def changed_immutable_files() -> list[str]:
    """Tracked snapshot files modified (M) or deleted (D) since HEAD."""
    out = git("diff", "--diff-filter=MD", "--name-only", "HEAD", "--", "data/raw/")
    paths = [p for p in out.splitlines() if p.strip()]
    return [p for p in paths if not p.startswith(MUTABLE)]


def manifest_lost_snapshots() -> list[str]:
    """Snapshot entries the manifest used to list and no longer does."""
    before_raw = git("show", "HEAD:data/raw/manifest.json")
    if not before_raw.strip():
        return []  # first commit of the manifest; nothing to compare against
    try:
        before = json.loads(before_raw)
        with open("data/raw/manifest.json", encoding="utf-8") as fh:
            after = json.load(fh)
    except (json.JSONDecodeError, FileNotFoundError) as exc:
        return [f"manifest unreadable: {exc}"]

    lost = []
    for file_id, entry in before.get("files", {}).items():
        was = {s["date"] for s in entry.get("snapshots", [])}
        now = {s["date"] for s in after.get("files", {}).get(file_id, {}).get("snapshots", [])}
        for dropped in sorted(was - now):
            lost.append(f"{file_id}: snapshot {dropped} no longer listed")
    return lost


def main() -> int:
    problems = []

    rewritten = changed_immutable_files()
    if rewritten:
        problems.append("Raw snapshots were modified or deleted (they are append-only):")
        problems += [f"  {p}" for p in rewritten]

    lost = manifest_lost_snapshots()
    if lost:
        problems.append("The manifest dropped snapshot entries:")
        problems += [f"  {p}" for p in lost]

    if problems:
        for line in problems:
            print(f"::error::{line}" if not line.startswith("  ") else line, file=sys.stderr)
        return 1

    print("raw evidence intact: no snapshot modified or deleted, no manifest entry dropped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
