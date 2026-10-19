# Four commands and a folder

A short deck for college students who have never opened a terminal, used git or run
Claude Code. Where `the-record-that-vanished` is a case study about building an archive,
this one teaches a single skill: open a terminal, get to the folder where your repos
live, and start Claude Code there.

(Kept as its own file rather than folded into `README.md` — see "Note on this file" at
the bottom.)

## Files

| File | What it is |
|---|---|
| `four-commands-and-a-folder.pptx` | 18 slides, speaker notes on every slide |
| `four-commands-web.html` | the same deck as a web page (arrow keys to move, `n` for notes) |
| `build_setup_deck.js` | the pptxgenjs generator that produces the .pptx |
| `geom_audit.py` | reads shapes back out of a .pptx and reports overlap, overflow and off-slide elements |

## Structure

18 slides, five sections, roughly 30 minutes with questions:

1. **Start here** (1–2) — the title, and the two-command end state the deck builds toward
2. **The terminal** (3–5) — what it is, how to open one, how to read the prompt
3. **Four commands** (6–9) — `pwd`, `ls`, `cd`, and the vocabulary slide to photograph
4. **A folder** (10) — `mkdir`, and why every project belongs in one place
5. **GitHub** (11–12), **Claude Code** (13–16), **When it breaks** (17–18)

The deck deliberately omits commit, push, branch, pull request, SSH keys, private-repo
authentication, editors and `rm`. Students can ask Claude Code to do git work in English,
and the vocabulary is easier to learn by watching it run the commands.

## Sources

Every install command, keyboard shortcut, error string and account requirement came from
the official docs on **2026-10-19**:

- https://code.claude.com/docs/en/terminal-guide — opening a terminal, install, first session
- https://code.claude.com/docs/en/setup — system requirements, install, plans
- https://code.claude.com/docs/en/quickstart — first prompts, session commands

These pages change. Re-check all three the week you present. Slide 13 (install) goes
stale fastest, and the version string shown there (`2.1.302`) is simply what was
installed on the machine that built the deck.

Two claims worth re-verifying specifically:

- **Claude Code needs a paid plan** — Pro, Max, Team, Enterprise or Console. The free
  claude.ai plan does not include it. Check what the campus provides before the session;
  students who find this out at the login prompt will feel misled.
- **The PATH fix on slide 17** assumes zsh, the macOS default. Bash users need
  `~/.bashrc` instead of `~/.zshrc`.

## Rebuilding

`pptxgenjs` is **not** a dependency of this repo and should not become one — the pipeline
is stdlib-only on purpose. Build outside the project:

```bash
mkdir -p /tmp/deckbuild && cd /tmp/deckbuild
npm install pptxgenjs
cp /path/to/rowan-clery/talk/build_setup_deck.js .
SKILL_DIR=/path/to/pptx-skill node build_setup_deck.js
```

`SKILL_DIR` points at the pptx skill directory, for `scripts/apply_theme.js`. pptxgenjs
cannot write theme colours itself, so without that step every scheme colour falls back to
Office's stock palette.

### Fonts

Georgia (headings), Arial (body), Courier New (commands). All three ship with both macOS
and Microsoft Office, so the deck renders the same on a presenter's laptop as it does in
QA. Don't swap in Cambria or Calibri: neither is installed on a Mac without Office, and
the substitution changes line widths enough to break the layout.

### Geometry

The generator sizes terminal panes at `fontSize * 1.22 / 72` inches per line plus 0.36"
of padding, measured against rendered slides. Blank spacer lines are set at 7pt so they
read as a half-line of air rather than a full empty row. After changing any font size or
card height, re-run both checks rather than eyeballing:

```bash
python geom_audit.py four-commands-and-a-folder.pptx
python <pptx-skill>/scripts/office/validate.py four-commands-and-a-folder.pptx
```

Both report clean as of this build, and all 18 slides were rendered and reviewed.

## The web version

`four-commands-web.html` is self-contained: no build step, no dependencies, fonts from
Google Fonts with a local fallback stack. Open it in any browser.

- `←` / `→` or space to move, `Home` / `End` to jump
- `n` toggles the speaker notes, which are the same text as the .pptx notes
- It follows the reader's light or dark setting

## Note on this file

This content belongs in `README.md` alongside the other deck, but the session that wrote
it lost read access to pre-existing files in this repo partway through — existing files
could be written to but not read, so appending to `README.md` would have risked
clobbering it. Fold this in by hand when convenient.
