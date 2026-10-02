# Rowan Clery crime log archive

An independent, append-only archive of Rowan University's Clery Act daily crime log —
**2,353 incidents spanning December 2017 to September 2026** — with a reporting tool for
finding stories in it.

Rowan publishes the log as monthly Google Sheets in a
[public Drive folder](https://drive.google.com/drive/folders/1nYFW4qkOa-r9tCHyB5-lI1qin7giAD4p).
That folder is a rolling window — Rowan's annual security report says the most recent
90 days are posted — so months disappear, and entries are amended in place with no record
of what they said before. This project checks the folder daily, preserves every version of
every record, and keeps a timestamped trail of what was added, amended or removed.

It also reaches backwards. Rowan published the log through a PHP app until early 2026;
that app is now dead, returning an empty page for every month. Its last decade survives
only as Internet Archive captures, and this project replays them — recovering **2,167
incidents and 76 amendments Rowan never published a record of**, including 34 disposition
changes and 6 offenses reclassified after the fact.

**The risk is not hypothetical.** On the day this archive was first run, the June 2026
sheet was captured successfully and began returning HTTP 401 within the hour. Those 14
incidents are no longer public. They are in `data/raw/`, and the page still shows them.

**Nothing it has ever seen is ever deleted.** That is the one property everything else is
built around.

## Quick start

```bash
git clone <this repo> && cd rowan-clery
python3 -m venv .venv && .venv/bin/pip install pytest

.venv/bin/python run.py all          # fetch, archive, rebuild the page
open docs/index.html                 # the reporting tool
.venv/bin/python -m pytest           # 82 tests
```

The pipeline itself uses **only the Python standard library** — no dependencies to install
or pin. `pytest` is needed only to run the tests.

## Commands

| Command | What it does |
|---|---|
| `python run.py fetch` | One daily run: list the folder, fetch each sheet, snapshot changes, merge into the archive |
| `python run.py build` | Regenerate `data/processed/` and `docs/index.html` from the archive |
| `python run.py all` | Both, in order |
| `python run.py backfill` | Replay the Internet Archive's captures of the pre-2026 log (one-off, re-runnable) |
| `python run.py rebuild` | Reconstruct the archive from stored raw snapshots, offline |
| `--date YYYY-MM-DD` | Override the run date (for testing) |
| `--json` | Print the full run report |

Exit codes: `0` clean · `2` completed with alarms a human should read · `3` could not
proceed safely, **archive not modified** · `1` unexpected error.

## What you get

```
data/raw/<file_id>/<date>.csv      byte-exact snapshots, written only when content changes
data/raw/_wayback/<month>/<ts>.html  cached Internet Archive captures of the pre-2026 log
data/raw/<file_id>/<date>.headers.json   HTTP provenance for each snapshot
data/raw/_runs/<date>.json         one record per run, whether or not anything changed
data/archive/incidents.csv         the permanent record — append-only, never deleted
data/archive/changelog.jsonl       one event per added / amended / withdrawn / removed row
data/processed/incidents.json      derived view that feeds the page
docs/index.html                    self-contained reporting tool (no CDN, works offline)
```

`docs/index.html` inlines all its data, so it works from `file://`, works with no network,
and can be emailed as a single attachment — which matters when the thing being archived
may stop being public.

## Rebuilding from raw

The raw store is the evidence layer; everything else derives from it.

```bash
python run.py rebuild     # replays stored snapshots, no network
python run.py backfill    # replays cached Wayback captures
python run.py build       # regenerates the page
```

`rebuild` reads only from disk. That matters: re-fetching from Drive would now silently
drop the 14 June 2026 incidents, because Drive no longer serves them.

## The reporting tool

- **What changed** — additions, amendments and removals, with old → new values. This is
  where stories surface, so it sits at the top.
- **Charts cover the current publication format only.** Rowan moved to Google Sheets in
  June 2026; everything graphed comes from that format. The 2,167 pre-2026 incidents are
  fully searchable in the table but deliberately **not charted** — that record survives
  only as irregular Internet Archive snapshots, so some academic years hold twelve months
  and others hold one, and graphing them side by side invites year-over-year comparisons
  the coverage cannot support.
- **Built around the school year in progress.** The page opens on 2026-27. Academic years
  run August to July, because a Glassboro June and a Glassboro September are different
  places and a calendar year splits the population cycle in half.
- **Charts** — incidents per month by offense, offense ranking, location hotspots and
  outcomes, all scoped to the selected year. Colorblind-safe, light and dark.
- **Each offense, month by month** — one sparkline per offense, so "is theft moving"
  is answerable at a glance rather than by reading twelve lines off one axis.
- **Data quality** — impossible dates, imprecise times, reclassified offenses, possible
  duplicates. Problems in the source are shown, not silently cleaned.
- **Every incident** — all 2,353, filterable by month, offense, campus, agency, status,
  publication era and student status, searchable across narratives. Records the source no
  longer publishes are included and struck through.
- **The full record stays reachable** — the table covers all 2,353 incidents back to 2017
  regardless of which window the charts are showing, filterable by publication era.

## How it protects the archive

The failure that would matter is mistaking a broken fetch for a deletion. The guards:

- A row is only ever marked missing if its file was **fetched successfully** and the row
  was genuinely absent. Absence of a file is never evidence of absence of its rows.
- Fetches must return `text/csv`, not just HTTP 200 — Google serves sign-in walls and
  error pages with status 200.
- A row must be absent from **three** successful fetches on distinct days before it counts
  as withdrawn.
- A file losing more than 2 rows and more than 10% of its rows is **quarantined**: the
  snapshot is kept as evidence, but no archive change is applied and the run exits
  non-zero.
- If every file fails, the run aborts without diffing anything.
- File ids are pinned in `config/known_files.json` and fetched directly every run, so a
  broken folder listing can never shrink the known set.
- Identity is independent of the file id, so Rowan deleting and re-uploading a sheet is
  recorded as a relocation rather than a mass deletion.
- CI fails if anything under `data/raw/` is ever modified or deleted. Additions only.

See [METHODOLOGY.md](METHODOLOGY.md) for the identity key, the Clery regulatory backdrop,
known source errors, and what the data does **not** support.

## The two eras

| | pre-2026 (`cleryapp` PHP log) | 2026- (Drive sheets) |
|---|---|---|
| Incidents | 2,167 | 186 |
| Source | Internet Archive captures | Live, fetched daily |
| Incident narrative | no | **yes** |
| Student / non-student flag | **yes** (~70% of rows) | no |
| Non-crime police activity | **recorded** (disputes, vehicle stops, assists) | not recorded |
| Campus | a prefix inside "General Location" | its own column |
| Occurrence time | often a range | a single value |

Two consequences worth stating before publishing anything:

- **Counts are not comparable across the line.** The old log recorded police activity that
  is not a crime. The page keeps those out of offense categories, but the underlying
  collection practice still differed.
- **Rowan dropped a field.** The student/non-student flag appeared on ~70% of pre-2026
  rows and appears **zero** times in the 2026 sheets. It partly survives as prose inside
  the new narrative column, but it stopped being something you can filter or count.

Months missing entirely: all of 2018–2020, 2021-01, and **April–May 2026** — the handover
between the two systems, which the Internet Archive never captured. Those two months are
not recoverable from the web and would have to be requested from the Clery Compliance
Office.

## Editing the category maps

`config/category_map.csv` and `config/disposition_map.csv` are plain, commented CSVs meant
to be edited by hand. Each maps a raw token from the source to canonical categories or
outcome flags.

A token the maps don't recognise **fails the build for the live 2026 feed**, naming the
token. That is deliberate — silently bucketing an unrecognised offense into "Other" is how
a category quietly undercounts. When Rowan uses a new term, the build stops and asks you to
classify it.

The pre-2026 backfill is lenient instead, because its vocabulary is 622 Nature tokens with
a long tail of one-off objects. Unknown tokens there are recorded as `unclassified`,
counted exactly, and listed in the data-quality panel — never folded into an offense
category. Every one of the 2,353 incidents currently carries an offense category or is
classed as non-crime police activity.

Legacy `Nature` cells bundled an offense with its object and with police activity, so the
map has extra roles: `object` ("Bicycle", "Exit sign" — how you would count bicycle
thefts), `activity` ("Dispute", "Motor Vehicle Stop" — kept out of crime counts), and
`channel` ("Cyber", "Texts").

Both maps mark `Nature updated` and `Disposition updated` as **audit markers**, not values:
tokens before them are superseded by those after. `"Theft; Nature updated; Motor Vehicle
Theft"` is a motor vehicle theft.

## Automation

`.github/workflows/daily.yml` runs twice daily, commits any changes, and deploys the page
to GitHub Pages in the same run. It commits a run record every time even when nothing
changed — partly because GitHub disables scheduled workflows after 60 days of inactivity,
and partly because "we verified on 47 consecutive days that this row was present, and on
day 48 it was gone" is the evidentiary core of the project.

On failure it opens (or comments on) a GitHub issue. The page also reports its own
staleness with a red banner if the last successful run is more than two days old.

**Before enabling it:** this repository has no git remote yet, and both Actions and Pages
need one. See the note on repository visibility below.

## Repository visibility — decide before you publish

The narratives are republished verbatim and include reports of sexual assault, domestic
violence between roommates, false imprisonment and strangulation. Rowan publishes them, but
putting them on GitHub Pages is republication on a second platform with its own reach.

The page ships with `<meta name="robots" content="noindex, nofollow">`, which asks search
engines not to index it. That is a request, not a control.

A private repository with the archive kept locally gives you the full evidentiary benefit —
the daily capture, the change log, the preserved deletions — without republishing anything.
Make this call deliberately rather than by default.

## Source

Rowan University daily crime log ·
[Drive folder](https://drive.google.com/drive/folders/1nYFW4qkOa-r9tCHyB5-lI1qin7giAD4p) ·
[Rowan public safety](https://sites.rowan.edu/publicsafety/clery/crimeandfire/)

Clery Compliance Office, RUPD — cleryact@rowan.edu, (856) 256-4562. Logs older than the
posted window are available on request; 34 CFR 668.46(f)(5) gives institutions two business
days to produce them.
