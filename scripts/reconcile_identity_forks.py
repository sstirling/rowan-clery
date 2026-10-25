#!/usr/bin/env python3
"""One-off: correct the live-era identity forks already sitting in the archive.

## Why this exists

`incident_uid = sha1(normalized case number | raw Date/Time Reported)`. When Rowan edits a
published case-number cell — almost always to append a CSA number — the uid changes, so the
archive reads one incident as a deleted row plus a new row. `archive.py` now recognises
this during the merge, but three October 2026 incidents were forked before it could:

    RUPD 26-032705                  -> RUPD 26-032705/ CSA 87668            (Theft)
    RUPD 26-033208                  -> RUPD 26-033208/ CSA 87974            (Sex offense)
    RUPD 26-034005/ CSA 88071       -> RUPD 26-034005, 26-034174/ CSA 88071 (DV; assault)

Two of them finished the three-run confirmation ladder, so the changelog carries published
`withdrawn` events claiming Rowan removed records it never removed. One of those is a
sexual assault report. This script retires the stale halves so the duplicates stop being
counted and the false withdrawals are retracted.

## What it does and does not do

It does NOT rewrite or remove anything. The original `withdrawn` events stay in
`changelog.jsonl` exactly as published — that file is the evidence record, and an
append-only guarantee that bends for embarrassing entries is not a guarantee. Each
correction is a new appended `superseded_identity` event carrying `retracted_status`, so
the feed shows both the claim and its retraction.

`observed_date` is backdated to the replacement row's `first_seen_by_archive`, which is
when the amendment actually reached the archive, so the retraction sorts beside the
withdrawal it corrects rather than appearing as today's news. `corrected_on` records when
this script ran.

Re-running is safe: rows already `superseded` are skipped, so nothing is double-logged.

## Usage

    python scripts/reconcile_identity_forks.py --data data            # report only
    python scripts/reconcile_identity_forks.py --data data --apply    # write

Always dry-run first, and prefer `--apply` against a copy of `data/` before the real one.
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from rowan_clery.archive import (  # noqa: E402
    IDENTITY_CORROBORANTS,
    Archive,
    case_references,
)

LIVE_ERA = "drive-2026"


def find_forks(rows: dict[str, dict[str, str]]) -> list[tuple[dict, dict]]:
    """Return (old_row, new_row) pairs, using the same rule as the merge path.

    Deliberately imported from `archive` rather than reimplemented: if the two ever
    disagree, this script would correct rows the pipeline would then re-fork, or vice
    versa.
    """
    buckets: dict[tuple, list[dict]] = {}
    for row in rows.values():
        if row.get("source_era") != LIVE_ERA or row.get("status") == "superseded":
            continue
        # File id plus reported time, matching archive._match_identity_forks. Not the
        # month: see the bucket() docstring there for why that term is a trap.
        key = (row.get("source_file_id", ""), row.get("date_reported_raw", ""))
        buckets.setdefault(key, []).append(row)

    pairs: list[tuple[dict, dict]] = []
    for group in buckets.values():
        for old in group:
            mine = case_references(old.get("case_number_raw", ""))
            if not mine:
                continue
            matches = [
                new
                for new in group
                if new["incident_uid"] != old["incident_uid"]
                and mine < case_references(new.get("case_number_raw", ""))
                and all(old.get(f, "") == new.get(f, "") for f in IDENTITY_CORROBORANTS)
            ]
            # Only an unambiguous single match is acted on, exactly as in the merge. Two
            # candidates is a question for a human, not a tie to break by sort order.
            if len(matches) == 1:
                pairs.append((old, matches[0]))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="data", help="path to the data directory")
    parser.add_argument("--apply", action="store_true", help="write the correction; omit for a dry run")
    args = parser.parse_args()

    data_dir = pathlib.Path(args.data)
    archive = Archive(data_dir)
    rows = archive.load()
    before = {uid: dict(row) for uid, row in rows.items()}

    pairs = find_forks(rows)
    if not pairs:
        print("no unreconciled identity forks found")
        return 0

    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    events = []
    for old, new in pairs:
        retracted = old.get("status", "")
        print(f"{old['case_number_raw']!r}")
        print(f"  -> {new['case_number_raw']!r}")
        print(f"     {retracted} -> superseded   (nature: {old.get('nature_raw','')})")

        flags = set(filter(None, old.get("flags", "").split(";")))
        flags.add("superseded_identity")
        old["flags"] = ";".join(sorted(flags))
        old["status"] = "superseded"
        old["superseded_by"] = new["incident_uid"]

        events.append(
            {
                # When the amendment reached the archive, not when we noticed the bug, so
                # the retraction sits beside the claim it corrects.
                "observed_date": new.get("first_seen_by_archive", today),
                "incident_uid": old["incident_uid"],
                "change_type": "superseded_identity",
                "superseded_by": new["incident_uid"],
                "old_case_number": old["case_number_raw"],
                "new_case_number": new["case_number_raw"],
                "old_date_reported": old.get("date_reported_raw", ""),
                "new_date_reported": new.get("date_reported_raw", ""),
                "retracted_status": retracted,
                "corrected_on": today,
                "source": "identity-fork-backfill",
            }
        )

    retractions = sum(1 for e in events if e["retracted_status"] == "withdrawn")
    print(f"\n{len(pairs)} fork(s); {retractions} false withdrawal(s) retracted")

    if not args.apply:
        print("dry run — nothing written. Re-run with --apply to write.")
        return 0

    # The backfill reconciliation writes straight to disk without any invariant check.
    # Run them here: they are cheap, and they are the difference between a correction and
    # a quiet corruption. The corpus brake only counts `active` rows, and a fork's stale
    # half never is one, so it cannot fire on this change.
    archive._assert_invariants(before, rows)
    archive.write(rows)
    archive.append_changelog(events)
    print(f"wrote {archive.incidents_path} and appended {len(events)} event(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
