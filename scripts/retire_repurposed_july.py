#!/usr/bin/env python3
"""One-off: retire July 2026's rows after Rowan reused its file for November.

## Why this exists

On 2026-11-02 the Drive file pinned as "July 2026 Daily Crime Log"
(`14LFgZwIAeQLjWSJBDkk2QNf1UI9vA0dsCB3ITSVtV2o`) was found renamed in Drive to
"November 2026 Daily Crime Log", its 23 July rows deleted, its banner row rewritten to
`Rowan University Daily Crime Log, November 2026`, and one November row added. Rowan
reused the container rather than publishing a new file. The folder listing shows four
files and no separate July sheet.

This is the first time the source has changed which month a file id represents, and the
archive's model assumes one file id is one month. Two things follow from that, and
neither resolves on its own:

1. The fetch gate rejects the file today -- `MIN_DATA_ROWS = 3` in `fetch.py`, and the
   file has two newlines -- so it is logged UNFETCHED and July's rows sit on the absence
   ladder at 1 of 3. The ladder would reach `source_removed` on its own in three days,
   except that Rowan's next November entry pushes the file past the floor, and a
   reappearance resets `absent_count` to 0 (`pipeline.py`). October averaged about six
   entries a day, so the ladder will almost certainly never finish.
2. Once past the floor, the shrink guard scores the fetch against every prior row for
   that file id. Twenty-three July rows against a handful of November ones is far below
   `MIN_RETENTION = 0.90`, so the file is quarantined on every run from then on, and the
   alarm never clears. Quarantine is absence-blind, so nothing is lost -- but an alarm
   that fires every day stops being a signal, which is how June's 401 went unnoticed for
   twenty runs.

Marking the July rows `source_removed` resolves both: that status is exempt from the
retention denominator, so the file's November rows are scored on their own.

`source_removed` is defined in METHODOLOGY.md as "its entire monthly sheet is gone from
Drive", which is what happened -- by overwriting rather than by deletion. That difference
is recorded in the changelog event's `removal_mechanism` field rather than being flattened
away, because a log that was overwritten is a different act from one that was locked, and
June's 14 rows went the other way.

## What it does and does not do

It does NOT delete or rewrite anything. Every field of every July row is preserved; only
`status` changes, and `missing_since` is stamped with the date the removal was observed,
matching what the pipeline did to June's rows. Each change appends a `source_removed`
event to `changelog.jsonl` in the same shape the pipeline writes, so the published change
feed reads identically whether a removal was found by the pipeline or by this script.

The corpus brake is left armed rather than exempted. Twenty-three rows is 0.9% of the
~2,511 active rows, under the 5% fraction the brake needs alongside its 10-row floor, so
it does not fire. If it ever would, that is a change too large to make unattended and the
script should stop.

Re-running is safe: rows already `source_removed` are skipped, so nothing is double-logged.

## Usage

    python scripts/retire_repurposed_july.py --data data            # report only
    python scripts/retire_repurposed_july.py --data data --apply    # write

Always dry-run first, and prefer `--apply` against a copy of `data/` before the real one.
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rowan_clery.archive import Archive  # noqa: E402

#: The file whose container Rowan reused. Pinned here rather than read from config,
#: because the config entry is being renamed to November as part of this change and the
#: script has to keep naming the same id afterwards.
REPURPOSED_FILE_ID = "14LFgZwIAeQLjWSJBDkk2QNf1UI9vA0dsCB3ITSVtV2o"

#: The month whose rows are being retired. Scoped by month as well as file id so that
#: November rows later archived from the same id are never touched by a re-run.
RETIRED_MONTH = "July 2026"

#: The date the repurposing was observed in the folder listing.
OBSERVED_DATE = "2026-11-02"


def find_rows(rows: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    """The July rows still carrying a live status, in a stable order."""
    found = [
        row
        for row in rows.values()
        if row.get("source_file_id") == REPURPOSED_FILE_ID
        and row.get("source_month") == RETIRED_MONTH
        and row.get("status") in ("active", "missing", "withdrawn")
    ]
    return sorted(found, key=lambda r: r.get("date_reported_raw", ""))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--data", default="data", help="path to the data directory")
    parser.add_argument(
        "--apply", action="store_true", help="write the correction; omit for a dry run"
    )
    args = parser.parse_args()

    archive = Archive(pathlib.Path(args.data))
    rows = archive.load()
    before = {uid: dict(row) for uid, row in rows.items()}

    targets = find_rows(rows)
    if not targets:
        print(f"no live {RETIRED_MONTH} rows found for {REPURPOSED_FILE_ID} — nothing to do")
        return 0

    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    events = []
    for row in targets:
        previous = row.get("status", "")
        print(f"  {row.get('case_number_raw', ''):34} {previous} -> source_removed")

        row["status"] = "source_removed"
        # Stamped the way the pipeline stamped June's rows: the date the removal was
        # observed, not the date this script happened to run.
        row["missing_since"] = OBSERVED_DATE

        events.append(
            {
                "observed_date": OBSERVED_DATE,
                "incident_uid": row["incident_uid"],
                "change_type": "source_removed",
                "case_number": row.get("case_number_raw", ""),
                "date_reported": row.get("date_reported_raw", ""),
                "nature": row.get("nature_raw", ""),
                "last_known_disposition": row.get("disposition_raw", ""),
                "previous_status": previous,
                "source_file_id": REPURPOSED_FILE_ID,
                "source_month": RETIRED_MONTH,
                # June's sheet was locked (HTTP 401); July's was overwritten in place.
                # Both end as `source_removed`, and the distinction is worth keeping.
                "removal_mechanism": "file_repurposed_for_november_2026",
                "corrected_on": today,
                "source": "july-repurposing-backfill",
            }
        )

    print(f"\n{len(events)} {RETIRED_MONTH} row(s) to retire")

    if not args.apply:
        print("dry run — nothing written. Re-run with --apply to write.")
        return 0

    # Brake left armed on purpose; see the module docstring.
    archive._assert_invariants(before, rows)
    archive.write(rows)
    archive.append_changelog(events)
    print(f"wrote {archive.incidents_path} and appended {len(events)} event(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
