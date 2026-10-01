"""Layer 3: turn the canonical archive into the data the page renders.

Regenerated from scratch every run. Nothing here is a source of truth — delete
data/processed/ and this rebuilds it identically from the archive.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib

from . import normalize
from .archive import Archive

# Statuses meaning "the source still publishes this".
LIVE_STATUSES = {"active", "missing"}


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
        "year_warnings": [],
        "occurred_after_reported": [],
    }

    current_year = int(today[:4])

    for uid in sorted(rows):
        row = rows[uid]
        reported = normalize.parse_datetime(row["date_reported_raw"])
        occurred = normalize.parse_datetime(row["date_occurred_raw"])
        nature = normalize.categorize(row["nature_raw"], category_map)
        disposition = normalize.disposition_flags(row["disposition_raw"], disposition_map)
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
            "narrative": row["narrative_raw"],
            "campus": row["campus_raw"],
            "location": row["location_raw"],
            "disposition_raw": row["disposition_raw"],
            "disposition_flags": disposition["flags"],
            "disposition_amended": disposition["disposition_amended"],
            "month": row["source_month"],
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
        for parsed in (reported, occurred):
            if warning := normalize.year_sanity_warning(parsed, current_year):
                quality["year_warnings"].append({"uid": uid, "case_number": case, "warning": warning})
        if lag is not None and lag < 0:
            quality["occurred_after_reported"].append(
                {"uid": uid, "case_number": case, "hours": round(lag, 2)}
            )

    live = [i for i in incidents if i["status"] in LIVE_STATUSES]
    gone = [i for i in incidents if i["status"] not in LIVE_STATUSES]

    last_run = runs[-1] if runs else None
    last_success = next(
        (r["date"] for r in reversed(runs) if r.get("archive_rows") is not None), None
    )
    staleness = (
        (dt.date.fromisoformat(today) - dt.date.fromisoformat(last_success)).days if last_success else None
    )

    payload = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "archive_started": _archive_started(data_dir, today),
        "source_folder": "https://drive.google.com/drive/folders/1nYFW4qkOa-r9tCHyB5-lI1qin7giAD4p",
        "counts": {
            "total_archived": len(incidents),
            "currently_published": len(live),
            "no_longer_published": len(gone),
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
