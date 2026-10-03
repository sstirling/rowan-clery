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

## What this page publishes

The page covers only the log as Rowan publishes it now: Google Sheets, from June 2026.

The pre-2026 record described in the next section is **archived but not shown**. Its
coverage is too uneven to present: 2021-22 holds twelve captured months, 2023-24 holds
one, and 2018-2020 and April-May 2026 were never captured. Any chart placing those side by
side implies a comparison the data cannot support.

The data is retained in full, under version control, because deleting an archive to tidy a
chart would defeat the point of keeping one. It is documented below so that anyone working
from it knows exactly what it is and is not.

## The pre-2026 backfill (archived, not published)

Rowan published the log through a PHP app at
`sites.rowan.edu/publicsafety/clery/crimeandfire/cleryapp/index.php?month=YYYY-MM` until
roughly March 2026. That app now returns an empty CMS shell for every month, so its last
decade survives only as Internet Archive captures.

84 captures across 40 months were harvested and cached under `data/raw/_wayback/`, then
replayed in capture order so the ordinary merge logic treats each as a dated observation.
That recovers **2,167 incidents and 48 substantive amendments** — 38 disposition changes,
6 offense reclassifications and 4 occurrence-time corrections — none of which Rowan
published a record of.

A further **67 edits were cosmetic**: the source reformats dates without changing them
(`02/13/22` to `02/13/2022`, including inside occurrence ranges). These are recorded in the
changelog, flagged `cosmetic`, and kept out of the change feed, where they would otherwise
outnumber and bury the amendments worth reading.

### What the captures prove, and what they do not

- **Rowan does not retroactively delete from closed months.** February 2021 was compared
  across captures in 2021, 2023 and 2025: 40 incidents, nothing added, nothing removed,
  nothing amended. Every apparent disappearance investigated turned out to be a corrected
  case number or a reformatted date. That is a useful documented baseline — it is what
  would make a future deletion significant rather than ambiguous.
- **Rowan does amend dispositions after publishing.** In September 2022, four changed
  between captures, including one that became **"Unfounded; Closed; Referred to Dean of
  Students"** and one where "Two subjects issued trespass warnings" became "Three".
- **Changes cannot be dated precisely.** Captures are irregular and often years apart, so
  the honest claim is usually "changed between capture A and capture B", not a date.
- **Coverage is uneven.** All of 2018-2020 and 2021-01 are absent. So are **April and May
  2026** — the handover between the two systems — which no capture covers and which are
  not recoverable from the web.

### Identity under source edits

The uid assumes the case number and reported date are never revised. That holds for 2026.
It does not hold throughout the legacy era, and two distinct problems appeared:

1. **Cosmetic reformats.** In February 2022, 34 of 59 rows changed from `02/13/22 2:23` to
   `02/13/2022 2:23` with no other field touched anywhere in the month. Hashing the raw
   string forked one incident into two identities, so the uid now hashes a **canonicalized**
   timestamp. The reformats are still recorded in the changelog, marked `cosmetic` so they
   do not bury real amendments.
2. **Genuine identity amendments.** Four incidents were re-published with a fuller
   identity (`22-030093` to `22-030093/CSA on-line report`; a reported time added). These
   are linked by a reconciliation pass: the earlier row is kept in full, marked
   `superseded`, pointing at the row that replaced it.

A wider auto-merge rule — grouping on month, reported minute, nature and location — was
tested and **rejected**. It collapsed pairs like `GPD 25-034057` and `GPD 25-034052`, two
distinct Glassboro PD summonses issued in the same minute at the same spot. Merging those
would destroy records, which is a worse error than leaving a duplicate visible. Six
suspicious pairs are therefore **flagged for human review, never merged**.

### Legacy vocabulary

The pre-2026 `Nature` field has 622 distinct tokens against the 2026 format's 64, because
cells bundled the offense with its object and with non-crime police activity. The category
map gained three roles beyond `offense`:

- `object` — what was taken or damaged ("Bicycle", "Exit sign"). Real data, and how you
  would count bicycle thefts, but not an offense.
- `activity` — non-crime police activity ("Dispute" ×200, "Motor Vehicle Stop" ×118).
  Counting these as crimes would badly inflate the legacy era against the 2026 data.
- `channel` — the medium ("Cyber", "Texts", "via email").

Unknown tokens in the backfill are recorded as `unclassified` rather than failing the
build; the live 2026 feed stays strict. Every one of the 2,353 incidents carries an offense
category or is classed as non-crime activity.

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

## School years, not calendar years

Incidents are grouped into academic years running **August to July**. Campus crime tracks
the academic calendar, not the calendar year: a 14-incident June and a 107-incident
September are the same campus with and without students on it. Grouping Aug-Jul keeps a
year's population cycle intact so year-over-year comparison means something.

Coverage per year is deeply uneven and **must** be read alongside any count:

| School year | Incidents | Months captured |
|---|---|---|
| 2017-18 | 67 | 1 of 12 |
| 2020-21 | 165 | 6 of 12 |
| 2021-22 | 539 | **12 of 12** |
| 2022-23 | 322 | 5 of 12 |
| 2023-24 | 76 | 1 of 12 |
| 2024-25 | 370 | 7 of 12 |
| 2025-26 | 665 | 10 of 12 |
| 2026-27 | 149 | 2 of 12 (in progress) |

**2021-22 is the only complete year.** 2023-24's 76 incidents are a single captured month,
not a quiet year.

Because of that, **the pre-2026 record is not charted at all.** It is archived in full,
searchable in full, and documented here — but putting a 1-month year beside a 12-month
year on the same axis invites a comparison the coverage cannot support, and no amount of
annotation reliably stops a reader making it. Charts cover the current publication format
(June 2026 onward); the school-year table above is the honest way to see the older
record's shape.

## The two formats are not comparable

| | pre-2026 (`cleryapp`) | 2026- (Drive) |
|---|---|---|
| Incident narrative | absent | present |
| Student / non-student flag | present (~70% of rows) | **absent** |
| Non-crime police activity | recorded | not recorded |
| Campus | prefix inside "General Location" | own column |
| Occurrence time | often a range | single value |
| Case numbers | `22-026152` | `RUPD 26-026152` |

Case numbers are left exactly as published. Adding an `RUPD` prefix the source never wrote
would be fabrication, and the eras do not overlap, so nothing depends on reconciling them.

**There is no month present in both formats**, so the schema mapping cannot be validated
against a known-good overlap. Any cross-era comparison rests on an unverifiable join and
should be presented as such.

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
  project (or the Internet Archive) first saw a row, not the date Rowan published it. For
  backfilled rows it is the capture date, which may be months after publication.
- **Rowan dropped the student/non-student flag in 2026.** It appeared on ~70% of pre-2026
  rows and zero times in the 2026 sheets. It partly survives as prose inside the new
  narrative column — "non-student" appears 87 times across the four 2026 sheets — but it
  stopped being a field you can filter or count. Any trend in student vs non-student
  involvement stops at the format change.
- **Camden appears only in the legacy data.** The pre-2026 log records incidents at both
  Cooper Medical School (CMSRU) and the Camden Academic Building; the 2026 sheets contain
  none. Whether that reflects reality or a gap in what is published is a question for
  Rowan, not something to infer from this data.
- **Campus coverage is uneven.** Of the first 186 incidents, 178 are Glassboro, 5
  Rowan-Virtua SOM (Stratford) and 3 West. Camden has none, although Rowan's annual
  security report documents security offices at CMSRU and the Camden Academic Building.
  Whether that reflects reality or a gap in what is published is an open question for
  Rowan, not something to infer from this data.

## Reproducing it

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python run.py all      # fetch, archive and rebuild the page
.venv/bin/python run.py backfill # replay the Internet Archive captures (one-off)
.venv/bin/python run.py rebuild  # reconstruct the archive from raw snapshots, offline
.venv/bin/python -m pytest       # 103 tests
```

The pipeline uses only the Python standard library. `pytest` is needed for the tests.

Tests run against byte-exact copies of the four real sheets in `tests/fixtures/`, so they
exercise the actual mess rather than tidy synthetic data, plus hostile fixtures for HTML
error pages served as 200, truncated bodies, drifted listing markup and wrong-tab exports.
