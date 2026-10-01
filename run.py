#!/usr/bin/env python3
"""Command-line entry point for the Rowan Clery archive.

    python run.py fetch     one daily run: discover, snapshot, merge into the archive
    python run.py build     regenerate the page data from the archive
    python run.py all       both, in order

Exit codes carry meaning so a CI job can react to them:
    0  clean run
    1  unexpected error
    2  the run completed but raised alarms a human should look at
    3  the run could not proceed safely; the archive was NOT modified
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from rowan_clery import build as build_mod
from rowan_clery import pipeline

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
CONFIG = ROOT / "config"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["fetch", "build", "all"])
    parser.add_argument("--date", help="override the run date (YYYY-MM-DD), for testing")
    parser.add_argument("--json", action="store_true", help="print the full run report as JSON")
    args = parser.parse_args()

    report = None
    if args.command in ("fetch", "all"):
        try:
            report = pipeline.run(DATA, CONFIG, today=args.date)
        except pipeline.RunFailure as exc:
            print(f"RUN FAILED: {exc}", file=sys.stderr)
            print("The archive was not modified.", file=sys.stderr)
            return 3
        _print_report(report)

    if args.command in ("build", "all"):
        payload = build_mod.build(DATA, CONFIG, today=args.date)
        page = build_mod.render_site(DATA, ROOT / "site", ROOT / "docs", payload)
        counts = payload["counts"]
        print(
            f"built page data: {counts['total_archived']} archived, "
            f"{counts['currently_published']} currently published, "
            f"{counts['no_longer_published']} no longer published"
        )
        print(f"wrote {page.relative_to(ROOT)} ({page.stat().st_size / 1024:.0f} KB, self-contained)")

    if args.json and report:
        print(json.dumps(report, indent=2))
    if report and report.get("alarms"):
        return 2
    return 0


def _print_report(report: dict) -> None:
    print(f"run {report['date']}  listing: {report['listing'].get('status')}")
    for file_id, info in sorted(report["files"].items(), key=lambda kv: kv[1].get("month") or ""):
        if info.get("status") == "ok":
            mark = "*" if info.get("snapshot_written") else " "
            print(f"  {mark} {info.get('month') or info.get('name'):<20} {info['rows']:>4} rows  {file_id}")
        else:
            print(f"  ! {info.get('name', file_id):<20} {info['status'].upper()}: {info.get('error', '')}")
    print(f"  {report.get('summary', '')}")
    for warning in report.get("warnings", []):
        print(f"  warning: {warning}")
    for alarm in report.get("alarms", []):
        print(f"  ALARM: {alarm}")


if __name__ == "__main__":
    sys.exit(main())
