"""Layer 3: turn the canonical archive into the data the page renders.

Regenerated from scratch every run. Nothing here is a source of truth — delete
data/processed/ and this rebuilds it identically from the archive.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import re

from . import normalize
from .archive import Archive

# The page presents only what Rowan publishes in its current format. The pre-2026 record
# recovered from the Internet Archive stays in the archive, in data/raw/ and in
# incidents.csv — it is simply not shown, because its coverage is too uneven to put in
# front of a reader: some academic years hold twelve months, others hold one.
# Set to None to publish every era again.
PUBLISHED_ERA = "drive-2026"

# Statuses meaning "the source still publishes this".
LIVE_STATUSES = {"active", "missing"}
# Replaced by another row after the source amended an identity field. Not a removal:
# the incident is still published, under a corrected case number or timestamp.
SUPERSEDED = "superseded"


def _load_run_records(data_dir: pathlib.Path) -> list[dict]:
    runs_dir = pathlib.Path(data_dir) / "raw" / "_runs"
    if not runs_dir.exists():
        return []
    records = []
    for path in sorted(runs_dir.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return records


def build(data_dir: pathlib.Path, config_dir: pathlib.Path, today: str | None = None) -> dict:
    """Assemble the page payload from the archive, changelog and run records."""
    today = today or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    data_dir, config_dir = pathlib.Path(data_dir), pathlib.Path(config_dir)
    category_map, disposition_map = normalize.load_maps(config_dir)
    campus_map = normalize.load_campus_map(config_dir)

    archive = Archive(data_dir)
    rows = archive.load()
    changelog = archive.read_changelog()
    runs = _load_run_records(data_dir)

    incidents = []
    quality: dict[str, list] = {
        "invalid_dates": [],
        "imprecise_occurred": [],
        "reclassified": [],
        "near_duplicates": [],
        "unclassified_offenses": [],
        "unclassified_dispositions": [],
        "duplicate_candidates": [],
        "year_warnings": [],
        "occurred_after_reported": [],
    }

    current_year = int(today[:4])

    for uid in sorted(rows):
        row = rows[uid]
        reported = normalize.parse_datetime(row["date_reported_raw"])
        occurred = normalize.parse_datetime(row["date_occurred_raw"])
        # The pre-2026 vocabulary has a 622-token long tail, so the backfill records
        # unknown tokens as `unclassified` instead of failing. The live 2026 feed stays
        # strict: a new term there is rare and should stop the build.
        strict = row.get("source_era", "drive-2026") == "drive-2026"
        nature = normalize.categorize(row["nature_raw"], category_map, strict=strict)
        disposition = normalize.disposition_flags(row["disposition_raw"], disposition_map, strict=strict)
        lag = normalize.reporting_lag_hours(reported, occurred)

        incident = {
            "uid": uid,
            "case_number": row["case_number_raw"],
            "agencies": normalize.agencies(row["case_number_raw"]),
            "reported": reported,
            "occurred": occurred,
            "reporting_lag_hours": round(lag, 2) if lag is not None else None,
            "nature_raw": row["nature_raw"],
            "categories": nature["categories"],
            "reclassified_from": nature["reclassified_from"],
            "unclassified": nature["unclassified"],
            "unclassified_disposition": disposition["unclassified"],
            "narrative": row["narrative_raw"],
            "campus": campus_map.get(row["campus_raw"], row["campus_raw"] or "Unknown"),
            "campus_raw": row["campus_raw"],
            "era": row.get("source_era", "drive-2026"),
            "location": row["location_raw"],
            "disposition_raw": row["disposition_raw"],
            "disposition_flags": disposition["flags"],
            "disposition_amended": disposition["disposition_amended"],
            "month": row["source_month"],
            "month_key": month_key(row["source_month"]),
            "school_year": school_year(row["source_month"]),
            "status": row["status"],
            "revision": int(row["revision"] or 1),
            "first_seen_by_archive": row["first_seen_by_archive"],
            "last_verified": row["last_verified"],
            "missing_since": row["missing_since"],
            "flags": [f for f in (row["flags"] or "").split(";") if f],
        }
        incidents.append(incident)

        case = row["case_number_raw"]
        if occurred["precision"] == "invalid":
            quality["invalid_dates"].append({"uid": uid, "case_number": case, "raw": occurred["raw"]})
        elif occurred["precision"] in ("day", "month", "year", "unknown", "range_start"):
            quality["imprecise_occurred"].append(
                {"uid": uid, "case_number": case, "raw": occurred["raw"], "precision": occurred["precision"]}
            )
        if nature["reclassified_from"]:
            quality["reclassified"].append(
                {
                    "uid": uid,
                    "case_number": case,
                    "from": nature["reclassified_from"],
                    "to": nature["categories"],
                }
            )
        if "near_duplicate" in incident["flags"]:
            quality["near_duplicates"].append({"uid": uid, "case_number": case})
        if "possible_duplicate_identity" in incident["flags"]:
            quality["duplicate_candidates"].append(
                {"uid": uid, "case_number": case, "month": row["source_month"]}
            )
        if incident["unclassified"]:
            quality["unclassified_offenses"].append(
                {"uid": uid, "case_number": case, "tokens": incident["unclassified"]}
            )
        if incident["unclassified_disposition"]:
            quality["unclassified_dispositions"].append(
                {"uid": uid, "case_number": case, "tokens": incident["unclassified_disposition"]}
            )
        # Checked against the row's own log month. Only the REPORTED date is checked:
        # an occurrence legitimately predates the report, sometimes by years.
        month_year = _month_year(row["source_month"]) or current_year
        if warning := normalize.year_sanity_warning(reported, month_year):
            quality["year_warnings"].append({"uid": uid, "case_number": case, "warning": warning})
        if lag is not None and lag < 0:
            quality["occurred_after_reported"].append(
                {"uid": uid, "case_number": case, "hours": round(lag, 2)}
            )

    if PUBLISHED_ERA:
        incidents = [i for i in incidents if i["era"] == PUBLISHED_ERA]
        shown = {i["uid"] for i in incidents}
        changelog = [e for e in changelog if e.get("incident_uid") in shown]
        for key, rows in quality.items():
            quality[key] = [r for r in rows if r.get("uid") in shown]

    live = [i for i in incidents if i["status"] in LIVE_STATUSES]
    by_era = collections.Counter(i["era"] for i in incidents)
    gone = [i for i in incidents if i["status"] not in LIVE_STATUSES | {SUPERSEDED}]
    superseded = [i for i in incidents if i["status"] == SUPERSEDED]

    last_run = runs[-1] if runs else None
    last_success = next(
        (r["date"] for r in reversed(runs) if r.get("archive_rows") is not None), None
    )
    staleness = (
        (dt.date.fromisoformat(today) - dt.date.fromisoformat(last_success)).days if last_success else None
    )

    year_months: dict[str, set] = collections.defaultdict(set)
    year_eras: dict[str, set] = collections.defaultdict(set)
    for i in incidents:
        if i["school_year"]:
            year_months[i["school_year"]].add(i["month_key"])
            year_eras[i["school_year"]].add(i["era"])

    current = school_year(f"{today[:4]}-{today[5:7]}")

    payload = {
        "current_school_year": current,
        "school_years": [
            {
                "year": y,
                "incidents": sum(1 for i in incidents if i["school_year"] == y),
                "months_covered": len(year_months[y]),
                "months": sorted(year_months[y]),
                "complete": len(year_months[y]) == 12,
                "eras": sorted(year_eras[y]),
            }
            for y in sorted(year_months)
        ],
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "archive_started": _archive_started(data_dir, today),
        "source_folder": "https://drive.google.com/drive/folders/1nYFW4qkOa-r9tCHyB5-lI1qin7giAD4p",
        "published_era": {
            "id": PUBLISHED_ERA,
            "label": "Google Sheets on Drive",
            "count": by_era.get(PUBLISHED_ERA, 0),
            "since": "June 2026",
        },
        "counts": {
            "total_archived": len(incidents),
            "currently_published": len(live),
            "no_longer_published": len(gone),
            "superseded": len(superseded),
            "distinct_incidents": len(incidents) - len(superseded),
            "withdrawn": sum(1 for i in incidents if i["status"] == "withdrawn"),
            "source_removed": sum(1 for i in incidents if i["status"] == "source_removed"),
        },
        "status": {
            "last_run": last_run["date"] if last_run else None,
            "last_successful_run": last_success,
            "staleness_days": staleness,
            "alarms": last_run.get("alarms", []) if last_run else [],
            "warnings": last_run.get("warnings", []) if last_run else [],
        },
        "incidents": incidents,
        "changelog": changelog,
        "quality": quality,
        "facets": _facets(incidents),
        "runs": [
            {"date": r["date"], "summary": r.get("summary", ""), "alarms": len(r.get("alarms", []))}
            for r in runs
        ],
    }

    out_dir = data_dir / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "incidents.json").write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_dir / "status.json").write_text(
        json.dumps(payload["status"] | {"counts": payload["counts"]}, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def month_key(source_month: str) -> str | None:
    """Normalize either era's month label to YYYY-MM.

    The Drive sheets say "August 2026"; the legacy log says "2026-08".
    """
    if not source_month:
        return None
    if re.fullmatch(r"\d{4}-\d{2}", source_month):
        return source_month
    try:
        parsed = dt.datetime.strptime(source_month, "%B %Y")
    except ValueError:
        return None
    return f"{parsed.year}-{parsed.month:02d}"


def school_year(source_month: str) -> str | None:
    """Academic year label ("2026-27") for a log month.

    Campus crime tracks the academic calendar, not the calendar year: a Glassboro June
    and a Glassboro September are different places. Grouping Aug-Jul keeps a year's
    population cycle intact, so year-over-year comparison means something.
    """
    key = month_key(source_month)
    if not key:
        return None
    year, month = int(key[:4]), int(key[5:7])
    start = year if month >= 8 else year - 1
    return f"{start}-{str(start + 1)[2:]}"


def _month_year(source_month: str) -> int | None:
    """Year of a log month, from either era's label ("August 2026" or "2022-09")."""
    if match := re.search(r"(20\d{2})", source_month or ""):
        return int(match.group(1))
    return None


def _archive_started(data_dir: pathlib.Path, today: str) -> str:
    manifest_path = pathlib.Path(data_dir) / "raw" / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8")).get("archive_started", today)
    return today


def _facets(incidents: list[dict]) -> dict:
    """Pre-computed filter vocabularies, so the page does not derive them at load."""
    counter = lambda values: [  # noqa: E731
        {"value": v, "count": n} for v, n in collections.Counter(values).most_common()
    ]
    return {
        "categories": counter(c for i in incidents for c in i["categories"]),
        "school_years": counter(i["school_year"] for i in incidents if i["school_year"]),

        "campuses": counter(i["campus"] for i in incidents if i["campus"]),
        "months": counter(i["month"] for i in incidents if i["month"]),
        "locations": counter(i["location"] for i in incidents if i["location"]),
        "disposition_flags": counter(f for i in incidents for f in i["disposition_flags"]),
        "agencies": counter(a for i in incidents for a in i["agencies"]),
        "statuses": counter(i["status"] for i in incidents),
    }


def render_site(data_dir: pathlib.Path, site_dir: pathlib.Path, out_dir: pathlib.Path, payload: dict) -> pathlib.Path:
    """Inline the payload into the page template to make one self-contained file.

    No CDN, no fetch, no build step. The page works from file://, works offline, and
    can be emailed as a single attachment — which matters when the thing being archived
    may stop being public.
    """
    template = (pathlib.Path(site_dir) / "template.html").read_text(encoding="utf-8")
    # `</script>` inside the JSON would close the host <script> tag early.
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "index.html"
    target.write_text(template.replace("__DATA__", data), encoding="utf-8")
    return target
