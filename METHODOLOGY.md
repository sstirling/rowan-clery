# Methodology

How this archive is built, what it can and cannot support, and what is wrong with the
source data. Read this before publishing anything derived from the archive.

## What the source is

Rowan University publishes its Clery Act daily crime log as monthly Google Sheets in a
public Google Drive folder, linked from
[sites.rowan.edu/publicsafety/clery/crimeandfire](https://sites.rowan.edu/publicsafety/clery/crimeandfire/):

<https://drive.google.com/drive/folders/1nYFW4qkOa-r9tCHyB5-lI1qin7giAD4p>

Each sheet has one tab, "Crime Log", a title banner row, a header row, then one row per
incident across eight columns: Case Number, Date/Time Reported, Date/Time Occurred,
Nature, Incident Narrative, Campus, Location, Disposition.

## Why an independent archive exists

**The folder is a rolling window, not an archive.** Rowan's
[annual security report](https://sites.rowan.edu/publicsafety/_docs/annual_security_report.pdf)
(p. 96) states that logs "for the most recent 90-day period are available for public
inspection online," with older logs available on request. When this archive began on
2026-10-01 the folder held only June through September 2026. Everything earlier was
already gone from the web.

**The source also changes under you.** At first capture, 18 of 186 rows carried inline
"Disposition updated" or "Nature updated" markers. One read:

> Domestic Violence; Simple Assault; False Imprisonment; Nature updated; Aggravated Assault-Strangulation

The sheet records *that* an entry was amended, but never *when*, or what it said before.
This archive captures both.

### The regulatory backdrop

Useful context for reporting, but note carefully which guidance is current.

- **The log itself.** 34 CFR 668.46(f)(1) requires institutions with a campus police or
  security department to maintain a daily crime log recording "by the date the crime was
  reported" the "nature, date, time, and general location of each crime" and "the
  disposition of the complaint, if known."
  ([eCFR](https://www.ecfr.gov/current/title-34/section-668.46))
- **Updates are required.** 668.46(f)(2) requires an entry "or an addition to an entry"
  within two business days. The statute is more explicit: 20 U.S.C. 1092(f)(4)(B)(ii)
  requires new information to be recorded "not later than two business days after the
  information becomes available."
  ([Cornell LII](https://www.law.cornell.edu/uscode/text/20/1092))
- **Required fields, in current post-2020 guidance.** Electronic Announcement
  [GENERAL-24-78](https://fsapartners.ed.gov/knowledge-center/library/electronic-announcements/2024-06-26/reminder-institution-responsibilities-under-clery-act)
  (June 26, 2024): "Log entries must include the offense type, date/time reported,
  date/time of the occurrence, general location, and the current disposition of the
  matter."
- **Deletion. Read this caveat carefully.** The instruction not to delete entries appears
  only in the Department of Education's *2016 Handbook for Campus Safety and Security
  Reporting*, which ED **rescinded on Oct. 9, 2020** and now stamps "Maintained for
  Historical Purposes Only." It said, at p. 5-6: "Do not delete an entry once it's been
  made; update the disposition instead," and at p. 3-54, on unfounded reports: "You may
  not delete the report from the crime log."
  ([2016 handbook](https://files.eric.ed.gov/fulltext/ED575475.pdf) ·
  [rescission notice](https://fsapartners.ed.gov/knowledge-center/library/electronic-announcements/2020-10-09/rescission-and-replacement-2016-handbook-campus-safety-and-security-reporting-updated-jan-19-2021))

  **Do not describe this as a current requirement.** The replacement guidance says
  nothing about deletion, retention, or updating dispositions. ED does still enforce the
  substance — its March 2024 Liberty University final program review determination
  faulted the university for failing to update log dispositions — but if you intend to
  write that deleting entries violates a rule, put the question to ED at Clery@ed.gov
  first and get it on the record.
- **Retention.** 34 CFR 668.46(f) contains **no retention period**. The widely cited
  "seven years" is ED's stated enforcement position, derived from keeping supporting
  records three years past the last annual security report that uses them. Attribute it
  to ED guidance, not to the regulation.
- **The law was renamed.** The Stop Campus Hazing Act (Pub. L. 118-173, Dec. 23, 2024)
  renamed the Clery Act the "Jeanne Clery Campus Safety Act." That is why Rowan's 2026
  report uses that title.

## How the archive works

Three layers. Each is immutable with respect to the one below it, and the raw layer is
never rewritten.

### Layer 1 — raw capture

`data/raw/<file_id>/<date>.csv`, with a `.headers.json` sidecar recording the HTTP
status, content type, content disposition, byte length, sha256 and fetch time.

CSV, not XLSX, for two reasons. CSV exports are byte-stable across repeated identical
requests, so hashing detects real change; XLSX re-exports differ byte-for-byte even when
nothing changed. And CSV is text, so a removed row appears as a readable diff in GitHub —
a diff you can show someone is the point.

A new snapshot is written only when the content hash changes, so an unchanged month costs
nothing per day. `data/raw/_runs/<date>.json` records every run regardless, which is both
the proof that a check happened on a given date and what keeps GitHub from disabling the
schedule for inactivity.

### Layer 2 — the canonical archive

`data/archive/incidents.csv`. **Rows are never deleted or overwritten.**
`data/archive/changelog.jsonl` appends one event per observed change.

#### Identity

```
incident_uid = sha1(normalized_case_number | raw Date/Time Reported)[:16]
```

Chosen for **immutability**, not merely uniqueness:

- Case Number alone is not unique. `RUPD 26-026280` appears twice in the August sheet.
- `Date/Time Reported` is a clerical fact that has not been observed to change, and it
  parses for 100% of rows. Together these give 186 distinct ids for 186 rows.
- **Excluded:** Nature, Disposition, Narrative, Location — the fields Rowan actually
  amends. Keying on them would log every amendment as a deletion plus an unrelated
  insertion, destroying the audit trail.
- **Excluded:** `Date/Time Occurred`, which does get refined from "Unk." to a real time.
- **Excluded: the source file id.** If Rowan deletes a monthly sheet and re-uploads it,
  the file id changes. A file-scoped key would report every row in that month as withdrawn
  and an equal number as new — a fabricated mass deletion. File-independent identity
  records that correctly as a relocation.
- **Excluded: row position.** Any ordinal recomputed from the current snapshot is
  positional. If the first of a duplicate pair were deleted, the second's ordinal would
  shift, inventing an amendment and hiding the real deletion.

Once written, a uid is immutable for the life of the project.

#### Statuses

| Status | Meaning |
|---|---|
| `active` | Present in the most recent successful fetch |
| `missing` | Absent from 1–2 successful fetches; not yet confirmed |
| `withdrawn` | Absent from 3+ successful fetches on distinct days, from a sheet that still exists |
| `source_removed` | Its entire monthly sheet is gone from Drive |

`withdrawn` and `source_removed` are kept distinct: one row quietly dropped from a live
sheet is a different event from a whole month disappearing. In both cases every field is
preserved and remains readable.

#### Safety interlocks

The archive's integrity rests on never mistaking a fetch failure for a deletion.

- A row moves toward `withdrawn` **only** when its file was fetched successfully,
  validated, and the row was genuinely absent. Absence of a file is never evidence of
  absence of its rows.
- Fetches must return HTTP 200 **and** `text/csv` — Google serves sign-in walls and quota
  pages with status 200 and an HTML body. Without this gate, losing access would parse as
  a file with zero rows.
- Every CSV fetch checks the tab name in the `Content-Disposition` header. A tab added
  ahead of the crime log would otherwise silently change what is being archived while
  still returning valid CSV. A conclusive tab census runs on change and weekly.
- File ids are pinned in `config/known_files.json` and fetched directly every run. The
  known set can grow from a folder listing but can never shrink because of one.
- A file losing more than 2 rows **and** more than 10% of its rows is **quarantined**: its
  raw snapshot is still written, but no archive mutation is applied and the run exits
  non-zero for a human.
- If every file fails, the run aborts without diffing.
- The merged archive is assembled in memory and checked — no uid lost, no shrink, no
  rewritten identity or first-seen date — before anything is written.

### Layer 3 — derived

Regenerated from the archive every run; delete `data/processed/` and it rebuilds
identically.

- **Offenses** are mapped token-by-token via `config/category_map.csv` (64 tokens → 29
  categories). An unmapped token **fails the build** rather than falling into a silent
  "Other" bucket.
- **`Nature updated` is an audit marker, not an offense.** Tokens before it are superseded
  by those after. "Theft; Nature updated; Motor Vehicle Theft" is a motor vehicle theft;
  counting it as a theft would report the classification RUPD withdrew. The superseded
  value is retained and shown as a reclassification.
- **Dispositions** become a set of boolean flags via `config/disposition_map.csv`
  (41 tokens), because rows routinely carry several outcomes at once. The same
  supersession rule applies: "Open/Active; Disposition updated; Closed" is closed.
- **Agencies** are derived from case-number prefixes (RUPD, CSA, GPD, GEN, LLEA), using
  the vocabulary Rowan publishes.

## Known problems in the source

Surfaced in the page's data-quality panel rather than silently cleaned.

| Problem | Count at first capture | Note |
|---|---|---|
| Impossible date | 1 | `9/31/26 11:30` — September 31 does not exist |
| Occurred after reported | 1 | Occurrence timestamp later than the report |
| Imprecise occurrence time | 13 | `Unknown`, `6/30/26 Unk.`, `10/2025 Unk.`, `2021 Unknown`, `Since 5/13/26 Unk.` |
| Possible duplicate records | 2 | `RUPD 26-026280` — same case number, identical narrative, disposition and location, different dates |
| Offenses reclassified | 2 | Marked inline with "Nature updated" |
| Inconsistent capitalisation | — | `Criminal Mischief` / `Criminal mischief`, `Subject Arrested` / `Subject arrested` |

Dates are never coerced to a single timestamp. Each carries a precision
(`minute`/`day`/`month`/`year`/`range_start`/`unknown`/`invalid`) and the original string.
Anything binned on occurrence date must report how many incidents it could not place.

## Limits on what the data supports

- **This is a count of logged incidents, not of crime.** Reporting rates, Campus Security
  Authority referrals and the academic calendar move these numbers independently of
  underlying crime.
- **Four months is not a trend line.** June holds 14 incidents and September 107. That is
  a campus filling up for the semester, not a crime wave. Seasonal and year-over-year
  claims are out of reach until the archive is deeper.
- **Do not write "campus police handled N incidents."** Of the first 186 incidents, 142
  carry an RUPD reference, 33 a Glassboro municipal police reference and 41 a Campus
  Security Authority reference. CSA-only rows had no police response.
- **The archive cannot attest to the past.** `first_seen_by_archive` is the date this
  project first saw a row, not the date Rowan published it. For rows captured on day one
  it says only "present on 2026-10-01." The archive cannot show that a row was unchanged
  in August.
- **Campus coverage is uneven.** Of the first 186 incidents, 178 are Glassboro, 5
  Rowan-Virtua SOM (Stratford) and 3 West. Camden has none, although Rowan's annual
  security report documents security offices at CMSRU and the Camden Academic Building.
  Whether that reflects reality or a gap in what is published is an open question for
  Rowan, not something to infer from this data.

## Reproducing it

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python run.py all      # fetch, archive and rebuild the page
.venv/bin/python -m pytest       # 82 tests
```

The pipeline uses only the Python standard library. `pytest` is needed for the tests.

Tests run against byte-exact copies of the four real sheets in `tests/fixtures/`, so they
exercise the actual mess rather than tidy synthetic data, plus hostile fixtures for HTML
error pages served as 200, truncated bodies, drifted listing markup and wrong-tab exports.
