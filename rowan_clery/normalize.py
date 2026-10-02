"""Layer 3: turn verbatim archive rows into analysable fields.

Nothing here writes back to the archive. The archive keeps the source's exact strings,
including its inconsistent capitalisation; this module produces a derived view that can
be regenerated at any time by rerunning it.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import pathlib
import re

TOKEN_SPLIT = re.compile(r"\s*;\s*")


class MappingError(RuntimeError):
    """A token in the source has no entry in the config map.

    Deliberately fatal. Silently bucketing an unrecognised offense into "Other" is how
    a category quietly undercounts, and an undercount published as a finding is the
    failure mode that would embarrass a reporter most.
    """


def _load_map(path: pathlib.Path) -> dict[str, dict[str, str]]:
    """Read a config map, skipping the `#` comment lines that document it."""
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("#")]
    rows = list(csv.DictReader(io.StringIO("\n".join(lines))))
    key = "raw_token" if rows and "raw_token" in rows[0] else "raw_value"
    for row in rows:
        if None in row:
            raise MappingError(f"{path.name}: ragged row (unquoted comma?): {row}")
    return {row[key]: row for row in rows}


def _split_flags(value: str) -> list[str]:
    return [f for f in (value or "").split("|") if f]


def _apply_supersession(tokens: list[str], lookup, is_marker) -> tuple[list[str], list[str]]:
    """Split tokens at the last audit marker into (superseded, current).

    The university records amendments inline rather than by editing in place:

        "Theft; Nature updated; Motor Vehicle Theft"

    Everything before the marker is the classification RUPD withdrew; everything from
    the marker onward is what it now says. Reading the whole string as a flat list would
    count the incident as a theft it has explicitly stopped calling a theft — and, in
    the September case, would count one incident as both a simple assault and an
    aggravated assault/strangulation.

    Returns (superseded_tokens, current_tokens). The superseded ones are kept so the
    reclassification can be reported rather than just silently corrected.
    """
    last_marker = max((i for i, t in enumerate(tokens) if is_marker(lookup, t)), default=None)
    if last_marker is None:
        return [], tokens
    return tokens[:last_marker], tokens[last_marker:]


# ---- Nature -------------------------------------------------------------------


#: Roles whose tokens contribute offense categories. `audit_marker` is included because
#: legacy markers are written as a single combined token ("Nature updated - Assault
#: (Aggravated)") that carries the replacement classification inline.
CATEGORY_ROLES = ("offense", "audit_marker")


def categorize(
    nature_raw: str,
    category_map: dict[str, dict[str, str]],
    strict: bool = True,
) -> dict:
    """Resolve a raw `Nature` string into canonical categories.

    `strict=True` (the live 2026 feed) raises on an unrecognised token. The vocabulary
    there is small and stable, so a new term is both rare and meaningful — it should stop
    the build and get classified deliberately.

    `strict=False` (the pre-2026 backfill) records unknown tokens as `unclassified`
    instead. That era has a 622-token vocabulary with a long tail of one-off objects, so
    failing on each would make the backfill impossible. The tokens are still reported
    exactly and never folded into an offense category — the integrity rule is "never
    silently miscount", not "never leave anything unclassified".

    Returns the current categories, the categories the incident was reclassified away
    from, and the non-offense detail the legacy format bundled into the same cell.
    """
    tokens = [t for t in TOKEN_SPLIT.split((nature_raw or "").strip()) if t]
    unknown = [t for t in tokens if t not in category_map]
    if unknown and strict:
        raise MappingError(
            f"Unmapped Nature token(s): {unknown}. Add them to config/category_map.csv "
            "with a role and categories. Refusing to guess, because a wrong guess "
            "silently undercounts a category."
        )

    known = [t for t in tokens if t in category_map]

    def is_marker(cmap, token):
        return cmap[token]["role"] == "audit_marker"

    superseded, current = _apply_supersession(known, category_map, is_marker)

    def collect(token_list, roles):
        out = []
        for token in token_list:
            if category_map[token]["role"] not in roles:
                continue
            # No fallback to the token itself: an audit marker with no categories
            # ("Nature updated") must contribute nothing, or it becomes a phantom
            # category named after the marker.
            for value in _split_flags(category_map[token]["categories"]):
                if value not in out:
                    out.append(value)
        return out

    def tokens_with_role(token_list, role):
        """Return the token text itself for descriptive roles.

        Objects, activity and channel carry no canonical category — the token IS the
        value ("Bicycle", "Dispute"), so these are reported verbatim.
        """
        return [t for t in token_list if category_map[t]["role"] == role]

    current_cats = collect(current, CATEGORY_ROLES)
    prior_cats = [c for c in collect(superseded, CATEGORY_ROLES) if c not in current_cats]
    return {
        "categories": current_cats,
        "reclassified_from": prior_cats,
        "was_reclassified": bool(prior_cats or superseded),
        # What the offense was committed against ("Bicycle", "Exit sign"). Only the
        # legacy format carries this; it is how you would count bicycle thefts.
        "objects": tokens_with_role(current, "object"),
        # Non-crime police activity ("Dispute", "Motor Vehicle Stop"). Kept out of
        # categories so it cannot inflate crime counts.
        "activity": tokens_with_role(current, "activity"),
        "channels": tokens_with_role(current, "channel"),
        "unclassified": unknown,
    }


# ---- Disposition --------------------------------------------------------------


def normalize_disposition_token(token: str) -> str:
    return re.sub(r"\s+", " ", token).strip().lower().rstrip(".")


def disposition_flags(
    disposition_raw: str,
    disposition_map: dict[str, dict[str, str]],
    strict: bool = True,
) -> dict:
    """Resolve a raw `Disposition` string into a set of outcome flags.

    `strict` behaves as in categorize(): fatal for the live feed, recorded as
    `unclassified` for the pre-2026 backfill's 340-token vocabulary.
    """
    tokens = [normalize_disposition_token(t) for t in TOKEN_SPLIT.split((disposition_raw or "").strip())]
    tokens = [t for t in tokens if t]
    unknown = [t for t in tokens if t not in disposition_map]
    if unknown and strict:
        raise MappingError(
            f"Unmapped Disposition token(s): {unknown}. Add them to config/disposition_map.csv."
        )
    tokens = [t for t in tokens if t in disposition_map]

    def is_marker(dmap, token):
        return dmap[token]["role"] == "audit_marker"

    superseded, current = _apply_supersession(tokens, disposition_map, is_marker)

    flags: list[str] = []
    for token in current:
        for flag in _split_flags(disposition_map[token]["flags"]):
            if flag not in flags:
                flags.append(flag)
    return {
        "flags": flags,
        "disposition_amended": bool(superseded),
        "superseded_flags": [
            f for t in superseded for f in _split_flags(disposition_map[t]["flags"]) if f not in flags
        ],
        "unclassified": unknown,
    }


# ---- Agencies -----------------------------------------------------------------

# Rowan publishes this prefix vocabulary itself, on its crime-and-fire log page.
# Taken from there rather than inferred from the data, so a prefix that has not yet
# appeared in a sheet is still recognised the first time it does.
AGENCY_PATTERNS = {
    "RUPD": re.compile(r"\bRUPD\b", re.I),  # Rowan University Police Department
    "CSA": re.compile(r"\bCSA\b", re.I),  # Campus Security Authority report
    "GPD": re.compile(r"\bGPD\b", re.I),  # Glassboro Police Department
    "GEN": re.compile(r"\bGEN\b", re.I),  # General / non-police reference number
    "LLEA": re.compile(r"\bLLEA\b", re.I),  # Local law enforcement agency
}


def agencies(case_number_raw: str) -> list[str]:
    """Which agencies' reference numbers appear in a case number.

    This matters journalistically. A CSA-only row was reported to a Campus Security
    Authority with no police response, and a GPD row was handled by Glassboro's
    municipal force rather than campus police. Writing "Rowan University police
    responded to 186 incidents" would be wrong on both counts, so the tool derives this
    and shows the breakdown rather than offering an undifferentiated total.

    Derived here in layer 3 only. Never used for identity — see parse.incident_uid.
    """
    return [name for name, pattern in AGENCY_PATTERNS.items() if pattern.search(case_number_raw or "")]


# ---- Dates --------------------------------------------------------------------

_DATETIME_FORMATS = ("%m/%d/%y %H:%M", "%m/%d/%Y %H:%M")
_DATE_FORMATS = ("%m/%d/%y", "%m/%d/%Y")


def parse_datetime(raw: str, reference_year: int | None = None) -> dict:
    """Parse one of the source's date strings into a value plus its precision.

    The source is not uniform. Verified across the live data, `Date/Time Occurred`
    contains all of: exact timestamps, "6/30/26 Unk." (day known, time not),
    "10/2025 Unk." (month only), "2021 Unknown" (year only), "Since 5/13/26 Unk."
    (an open-ended range), bare "Unknown", a four-digit-year variant inconsistent with
    every other row, and "9/31/26 11:30" — a date that does not exist.

    Never coerce these to a single timestamp. A chart binned on date-occurred must be
    able to say how many incidents it could not place, or it silently drops them.
    """
    raw = (raw or "").strip()
    if not raw:
        return {"value": None, "precision": "unknown", "raw": raw, "ongoing": False}

    ongoing = bool(re.match(r"^since\b", raw, re.I))
    cleaned = re.sub(r"^since\s+", "", raw, flags=re.I).strip()

    # The pre-2026 log routinely expressed occurrence as a RANGE:
    #   "8/31/22 22:00 to 9/1/22 9:31"
    # Treat the start as the value and record that it is a range, rather than failing to
    # parse it and reporting ~900 perfectly good timestamps as impossible dates.
    range_match = re.split(r"\s+to\s+", cleaned, maxsplit=1, flags=re.I)
    range_end = None
    if len(range_match) == 2:
        cleaned, range_end = range_match[0].strip(), range_match[1].strip()
        ongoing = True
    cleaned = re.sub(r"\s*\b(unk\.?|unknown)\s*$", "", cleaned, flags=re.I).strip()

    if not cleaned:
        return {"value": None, "precision": "unknown", "raw": raw, "ongoing": ongoing}

    for fmt in _DATETIME_FORMATS:
        try:
            parsed = dt.datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        return {
            "value": parsed.isoformat(),
            "precision": "range_start" if ongoing else "minute",
            "raw": raw,
            "ongoing": ongoing,
            "range_end": range_end,
        }

    for fmt in _DATE_FORMATS:
        try:
            parsed = dt.datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        return {
            "value": parsed.date().isoformat(),
            "precision": "range_start" if ongoing else "day",
            "raw": raw,
            "ongoing": ongoing,
        }

    if match := re.fullmatch(r"(\d{1,2})/(\d{4})", cleaned):
        return {"value": f"{match.group(2)}-{int(match.group(1)):02d}", "precision": "month", "raw": raw, "ongoing": ongoing}

    if match := re.fullmatch(r"(\d{4})", cleaned):
        return {"value": match.group(1), "precision": "year", "raw": raw, "ongoing": ongoing}

    # Looks like a date but is not one — "9/31/26 11:30" is in the live August sheet.
    # Surfaced as a data-quality finding rather than dropped, because a log containing
    # an impossible date is itself worth asking the university about.
    if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", cleaned):
        return {"value": None, "precision": "invalid", "raw": raw, "ongoing": ongoing}

    return {"value": None, "precision": "unknown", "raw": raw, "ongoing": ongoing}


def year_sanity_warning(parsed: dict, expected_year: int) -> str | None:
    """Flag a date that resolved to a year its own monthly log contradicts.

    `%y` will happily turn a stray "/25" into 2025, so a mis-typed year has to be
    caught. The check is against the year of the sheet the row appears in, NOT against
    the current year: this archive spans 2017-2026, and comparing to "now" would flag
    every historical row as suspect.

    A reported date more than a year off its own log's month is a genuine anomaly. An
    OCCURRED date legitimately precedes it, sometimes by years, so callers pass only
    the reported date here.
    """
    value = parsed.get("value")
    if not value or parsed.get("precision") in ("unknown", "invalid"):
        return None
    year = int(str(value)[:4])
    if abs(year - expected_year) > 1:
        return f"{parsed['raw']!r} resolved to {year}, but the log month says {expected_year}"
    return None


def reporting_lag_hours(reported: dict, occurred: dict) -> float | None:
    """Hours between an incident happening and it being reported.

    Only computed when both ends are known to the minute. Day- or month-precision
    values would produce a lag with an error bar wider than the value itself.
    """
    if reported.get("precision") != "minute" or occurred.get("precision") != "minute":
        return None
    delta = dt.datetime.fromisoformat(reported["value"]) - dt.datetime.fromisoformat(occurred["value"])
    return delta.total_seconds() / 3600


def load_campus_map(config_dir: pathlib.Path) -> dict[str, str]:
    """Raw campus string -> canonical campus name, across both publication eras."""
    rows = _load_map(pathlib.Path(config_dir) / "campus_map.csv")
    return {k: v["campus"] for k, v in rows.items()}


def load_maps(config_dir: pathlib.Path) -> tuple[dict, dict]:
    config_dir = pathlib.Path(config_dir)
    return (
        _load_map(config_dir / "category_map.csv"),
        _load_map(config_dir / "disposition_map.csv"),
    )
