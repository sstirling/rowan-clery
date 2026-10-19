# The record that vanished — conference talk

A 30-slide talk (30–45 minutes) walking a non-technical newsroom audience through
building an append-only archive of a public record, using this repository as the worked
example and introducing the terminal, Claude Code and GitHub as the story needs them.

| File | What it is |
|---|---|
| `the-record-that-vanished.pptx` | The deck. Opens in PowerPoint, Keynote or Google Slides. Speaker notes are on every slide. |
| `record-vanished-web.html` | A web version for circulating afterwards. Self-contained; open it in any browser. Arrow keys move between slides, `n` toggles speaker notes. |
| `build_deck.js` | Generates the `.pptx`. Edit this rather than the deck, so a rebuild does not lose your changes. |

## Structure

1. **The record that vanished** (slides 1–5) — what a Clery daily crime log is, how Rowan
   publishes it, and why a record that is overwritten in place cannot be cited.
2. **What we built** (6–8) — the four-layer architecture and what a reader gets.
3. **The tools** (9–17) — terminal, Claude Code, GitHub, git, scheduled runs.
4. **The decisions** (18–26) — the five rules, the reporting-lag finding, and what the
   fail-loudly design costs.
5. **What to steal** (27–30) — the division of labour, how to pick a record, how to start.

## Every figure is measured, not illustrative

The numbers in the deck were read out of the archive on **2026-10-18**, at commit
`6b3bb0f`. They drift as data arrives. To refresh them, re-run the commands below and
update the `F` block near the top of `build_deck.js`.

```bash
# archive size, era split, category/disposition vocabulary, reporting lag by agency
python - <<'PY'
import collections, pathlib, sys
sys.path.insert(0, ".")
from rowan_clery import normalize
from rowan_clery.archive import Archive
rows = Archive(pathlib.Path("data")).load()
cmap, dmap = normalize.load_maps(pathlib.Path("config"))
print("archive rows:", len(rows))
print("by era:", collections.Counter(r.get("source_era", "drive-2026") for r in rows.values()))
print("nature tokens:", len(cmap), "| disposition tokens:", len(dmap))
PY

# changelog event counts (added / amended / source_removed)
python -c "import collections,json,pathlib; \
ev=[json.loads(l) for l in pathlib.Path('data/archive/changelog.jsonl').read_text().splitlines() if l.strip()]; \
print(collections.Counter(e['change_type'] for e in ev))"

# test counts
python -m pytest -q | tail -1
```

The monthly reported-vs-occurred series on slide 25 comes from `build.occurred_bin`
over the live era; see `METHODOLOGY.md` for what that binning does and does not count.

## Rebuilding the deck

`pptxgenjs` is a build-time dependency of the slides only. It is deliberately **not**
installed into this repository, which is stdlib-only by design. Build somewhere else:

```bash
mkdir -p /tmp/deckbuild && cd /tmp/deckbuild
npm install pptxgenjs
cp /path/to/rowan-clery/talk/build_deck.js .
SKILL_DIR=<pptx skill dir> NODE_PATH="$PWD/node_modules" node build_deck.js
```

`SKILL_DIR` points at the directory holding `scripts/apply_theme.js`, which writes the
theme colours into the generated file. Without it the deck still builds, but the palette
falls back to Office's stock colours.

## A note on the two chart slides

Slides 24 and 25 use native PowerPoint charts rather than images, so they stay editable
and re-colour with the theme. macOS Quick Look cannot render native charts and shows
those two slides as blank — that is a previewer limitation. They render normally in
PowerPoint, Keynote and Google Slides.
