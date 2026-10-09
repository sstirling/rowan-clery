# Rowan Clery crime log archive

An independent, append-only archive of Rowan University's Clery Act daily crime log, with
a reporting tool for finding stories in it.

The published page covers the log as Rowan publishes it now: Google Sheets, from June
2026. The archive on disk holds more (see *What is archived but not published* below).

Rowan publishes the log as monthly Google Sheets in a
[public Drive folder](https://drive.google.com/drive/folders/1nYFW4qkOa-r9tCHyB5-lI1qin7giAD4p).
That folder is a rolling window — Rowan's annual security report says the most recent
90 days are posted — so months disappear, and entries are amended in place with no record
of what they said before. This project checks the folder daily, preserves every version of
every record, and keeps a timestamped trail of what was added, amended or removed.

It also holds a pre-June-2026 record recovered from Internet Archive captures of Rowan's
old `cleryapp` log. That is **archived but not published** — see below.

**The risk is not hypothetical.** On the day this archive was first run, the June 2026
sheet was captured successfully and began returning HTTP 401 within the hour. Those 14
incidents are no longer public. They are in `data/raw/`, and the page still shows them.

**Nothing it has ever seen is ever deleted.** That is the one property everything else is
built around.

## Quick start

```bash
git clone <this repo> && cd rowan-clery
python3 -m venv .venv && .venv/bin/pip install pytest

.venv/bin/python run.py all          # fetch, archive, rebuild the pages
open docs/index.html                 # the reporting tool
.venv/bin/python -m pytest           # 152 tests
```

The pipeline itself uses **only the Python standard library** — no dependencies to install
or pin. `pytest` is needed only to run the tests.

## Commands

| Command | What it does |
|---|---|
| `python run.py fetch` | One daily run: list the folder, fetch each sheet, snapshot changes, merge into the archive |
| `python run.py build` | Regenerate `data/processed/` and all three pages in `docs/` from the archive |
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
data/processed/incidents.json      derived view that feeds the pages
docs/index.html                    overview: recent activity, charts, searchable incident table
docs/changes.html                  audit trail: every observed amendment, plus data quality
docs/about.html                    what this is, how it works, how to use it responsibly
```

### How the pages are built

The site is three pages composed at build time from shared parts, so the masthead, theme
and footer are written once:

```
site/base.html            page skeleton: <head>, masthead, nav, footer
site/css/chrome.css       tokens, layout, masthead — emitted on every page
site/css/{charts,table,audit}.css   only on the pages that need them
site/js/lib.js            payload, theme, tooltip, copy/download — every page
site/js/{index,changes}.js          page-specific rendering
site/pages/<name>.html    the body of each page
site/assets/              artwork, base64-inlined at build time
```

`rowan_clery/build.py` holds the page table (`PAGES`), which also decides **which slice of
the payload each page is given**. No page ships data it cannot use: the overview carries
the incidents, the changes page carries the changelog and the quality audit, and the about
page carries neither. A page that reads a key it was not given is a test failure, not a
blank section.

Every page inlines all its data and its logo, so each one works from `file://`, works with
no network, and can be emailed as a single attachment — which matters when the thing being
archived may stop being public.

### Artwork

Source art lives in `assets/` (plus `RUclery.png` at the root). The small assets the pages
actually inline are generated once, by hand, and committed:

```bash
python scripts/make_assets.py          # all of them
python scripts/make_assets.py logo     # or one, by name
```

| Built | From | Used for |
|---|---|---|
| `logo.png` 144px | `RUclery.png` | masthead wordmark, shown 34px tall |
| `favicon.png` 64px | the owl emblem | tab icon — trimmed and squared, since a wide logo is unreadable at 16px |
| `emblem.png` 120px | the owl emblem | the owl overhanging a `.callout` |
| `divider-dots.png` 1000px | `assets/divider-dots.png` | section rule |
| `divider-dots-center.png` 420px | `assets/divider-dots-center.png` | ornamental break before the footer |

The script decodes, resamples and re-encodes PNG with the standard library alone — no
Pillow, no `sips`, because the daily job runs on an Ubuntu runner. Two details matter:

- Sources with no alpha are keyed by **flood-filling inward from the border**, not by
  making white transparent. `RUclery.png` contains its own near-white — the clipboard and
  the owl's eyes — and a plain white key punches a hole through 51,300 px of the drawing.
- Resampling happens in **premultiplied alpha**, so edges between artwork and transparency
  do not pick up a pale halo.

`assets/owl-callout.png` is deliberately **not** built. It is a flattened mockup with the
transparency checkerboard and a paper texture baked into its pixels, and a raster frame
cannot stretch to fit a paragraph or adapt to dark mode. Its design is reproduced as the
`.callout` component in `site/css/chrome.css`, using colours sampled from the file —
cream `#fcf3e3`, gold `#fdb00d`, brown `#4a1b03` — with the owl emblem as the artwork.
That callout keeps its cream fill in both themes, like a printed sidebar, so its ink is
fixed rather than tokenised and gets its own contrast test.

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
- **Built around the school year in progress.** The page opens on 2026-27. Academic years
  run August to July, because a Glassboro June and a Glassboro September are different
  places and a calendar year splits the population cycle in half.
- **Charts** — incidents per month by offense, offense ranking, location hotspots and
  outcomes, all scoped to the selected year. Colorblind-safe, light and dark.
- **Each offense, month by month** — one sparkline per offense, so "is theft moving"
  is answerable at a glance rather than by reading twelve lines off one axis.
- **Data quality** — impossible dates, imprecise times, reclassified offenses, possible
  duplicates. Problems in the source are shown, not silently cleaned.
- **Every incident** — the full published log, filterable by month, offense, campus, agency, status,
  publication era and student status, searchable across narratives. Records the source no
  longer publishes are included and struck through.
- **Copy data** on every chart, and **Copy filtered rows** on the table — TSV on the
  clipboard, ready to paste into Datawrapper, Sheets or Excel. The table export follows
  whatever filters are applied.

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

## What is archived but not published

`run.py backfill` replays Internet Archive captures of Rowan's pre-June-2026 `cleryapp`
log — 2,167 incidents back to December 2017, plus 48 amendments Rowan never published a
record of. That data is in `data/raw/_wayback/`, in `data/archive/incidents.csv`, and
under version control.

**It is deliberately kept off the page.** Its coverage is too uneven to put in front of a
reader: 2021-22 holds twelve captured months, 2023-24 holds one, and 2018-2020 and
April-May 2026 were never captured at all. A count from a one-month year sitting beside a
twelve-month year invites a comparison the data cannot support, and no amount of
annotation reliably prevents it.

It also differs in kind. That log recorded non-crime police activity (disputes, vehicle
stops, assists) alongside offenses, carried a student/non-student flag the current format
dropped, and had no incident narrative.

To publish it anyway, set `PUBLISHED_ERA = None` in `rowan_clery/build.py` and rebuild.
To stop collecting it, simply never run `backfill` again — nothing in the daily job
touches it.

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
counted exactly, and listed on the Data & changes page — never folded into an offense
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
