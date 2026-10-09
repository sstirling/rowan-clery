"""Checks on the generated pages.

A JavaScript syntax error in a partial produces a page that serves with HTTP 200,
renders its headings and chrome, and shows **no data at all** — every chart and the whole
table silently empty. That has happened twice during development (a duplicated `const`
declaration, and a missing comma in an object literal), and neither was caught by any
other test because the Python pipeline was perfectly healthy both times.

So the built pages get parsed, and then executed, here.

Since the site became three pages, every check below is parametrised over all of them.
The single-page versions of these tests were worse than useless on the other two: they
asserted the overview's chart mounts, so they would have failed on the about page, and
they skipped silently when a page was missing rather than failing.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess

import pytest

from rowan_clery import build

ROOT = pathlib.Path(__file__).parent.parent
SITE = ROOT / "site"
DOCS = ROOT / "docs"

PAGE_NAMES = sorted(build.PAGES)

#: Source files the pages are composed from. Any guard that scans "the template" has to
#: scan all of these, or markup that moves into a partial stops being checked.
SOURCE_FILES = sorted(
    list(SITE.glob("*.html")) + list(SITE.glob("css/*.css"))
    + list(SITE.glob("js/*.js")) + list(SITE.glob("pages/*.html"))
)
JS_FILES = sorted(SITE.glob("js/*.js"))

MAIN_SCRIPT_RE = re.compile(r"<script data-main>\s*\n(.*?)</script>", re.S)

DISCLAIMER = (
    "This site isn't associated with Rowan University. It is built using the\n    help of "
    "Claude Code. Always confirm information presented here against official records,\n    "
    "and consult responsible authorities."
)


def built(name: str) -> pathlib.Path:
    """The built page, or a hard failure.

    Deliberately not `skipif(exists)`: a page that failed to build used to skip its own
    tests, which is the quietest possible way for the site to break.
    """
    path = DOCS / name
    assert path.exists(), f"{name} was not built — run `python run.py build` first"
    return path


def read(name: str) -> str:
    return built(name).read_text(encoding="utf-8")


def main_script(html: str) -> str:
    match = MAIN_SCRIPT_RE.search(html)
    assert match, "no <script data-main> block in the page"
    return match.group(1)


def check_with_node(source: str, tmp_path: pathlib.Path, label: str) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available to parse the page script")
    target = tmp_path / "page.mjs"
    target.write_text(source, encoding="utf-8")
    result = subprocess.run([node, "--check", str(target)], capture_output=True, text=True)
    assert result.returncode == 0, f"{label} does not parse:\n{result.stderr}"


# ---- the sources ---------------------------------------------------------------


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_each_script_partial_parses(path, tmp_path):
    """Each partial must be valid JavaScript on its own."""
    check_with_node(path.read_text(encoding="utf-8"), tmp_path, path.name)


def test_no_partial_redeclares_a_shared_binding():
    """Two partials are concatenated into one scope, so a repeated top-level `const` is a
    hard SyntaxError that blanks the whole page. That has shipped before."""
    seen: dict[str, str] = {}
    clashes = []
    for path in JS_FILES:
        names = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"(?:const|let|var|function)\s+([A-Za-z_$][\w$]*)", line)
            if match:
                names.add(match.group(1))
        for name in sorted(names):
            if name in seen and seen[name] != path.name:
                clashes.append(f"{name}: {seen[name]} and {path.name}")
            seen.setdefault(name, path.name)
    assert not clashes, f"top-level declarations repeated across partials: {clashes}"


def test_every_disposition_flag_has_a_label():
    """An unlabelled flag leaks raw snake_case onto the page.

    Cheap to check, and it is how `title_ix` and `other_agency` reached a screenshot.
    """
    import csv
    import io

    lines = [
        ln
        for ln in (ROOT / "config" / "disposition_map.csv").read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    ]
    flags = {
        flag
        for row in csv.DictReader(io.StringIO("\n".join(lines)))
        for flag in (row["flags"] or "").split("|")
        if flag
    }

    source = "\n".join(p.read_text(encoding="utf-8") for p in JS_FILES)
    assert "const DISP_LABEL = {" in source, "DISP_LABEL moved — this test no longer guards anything"
    block = source.split("const DISP_LABEL = {", 1)[1].split("};", 1)[0]
    labelled = set(re.findall(r"(\w+)\s*:", block))
    assert flags <= labelled, f"disposition flags with no display label: {sorted(flags - labelled)}"


def test_axis_text_colour_uses_inline_style_not_a_fill_attribute():
    """`.axis { fill: ... }` beats a `fill="..."` presentation attribute.

    The coverage labels under the year matrix were written with a fill attribute and
    silently rendered grey, so "complete year" and "partial" looked identical. Scans
    every source file, not one template: the chart markup has moved once already, and a
    guard that only reads the old location fails open.
    """
    offenders = []
    for path in SOURCE_FILES:
        offenders += [
            (path.name, hit)
            for hit in re.findall(r'<text class="axis"[^`>]*\sfill="(?!none)[^"]+"',
                                  path.read_text(encoding="utf-8"))
        ]
    assert not offenders, f"these .axis texts set fill as an attribute and will be overridden: {offenders}"


def test_each_page_only_reads_payload_keys_it_is_given():
    """A page that reads `D.changelog` without being given it renders an empty section.

    The payload is sliced per page to keep each one small, which makes this the obvious
    new way to break the site — so it is checked rather than trusted.
    """
    problems = []
    for name, spec in build.PAGES.items():
        allowed = set(spec["keys"])
        for js in spec["js"]:
            source = (SITE / "js" / js).read_text(encoding="utf-8")
            for key in sorted(set(re.findall(r"\bD\.([A-Za-z_]\w*)", source))):
                if key not in allowed:
                    problems.append(f"{name} ({js}) reads D.{key}, which it is not given")
    assert not problems, problems


# ---- the built pages -----------------------------------------------------------


@pytest.mark.parametrize("name", PAGE_NAMES)
def test_built_page_parses(name, tmp_path):
    check_with_node(main_script(read(name)), tmp_path, name)


@pytest.mark.parametrize("name", PAGE_NAMES)
def test_built_page_has_its_payload_and_no_stray_placeholders(name):
    html = read(name)
    assert '<script id="payload" type="application/json">' in html
    leftover = sorted(set(re.findall(r"__[A-Z_]{3,}__", html)))
    assert not leftover, f"{name}: placeholders never substituted: {leftover}"
    payload = html.split('type="application/json">', 1)[1].split("</script>", 1)[0]
    # Not a fixed byte floor: about.html is meant to be small. Enough to prove the slice
    # was actually substituted rather than left as an empty object.
    assert len(payload) > 200, f"{name}: payload is only {len(payload)} bytes"
    for key in build.PAGES[name]["keys"]:
        assert f'"{key}"' in payload, f"{name}: payload is missing {key}"


@pytest.mark.parametrize("name", PAGE_NAMES)
def test_built_page_has_the_mounts_its_scripts_write_to(name):
    """Guard the specific failure mode: chrome renders, data does not."""
    html = read(name)
    expected = {
        "index.html": ("activity", "banners", "scope", "stats", "chart-month", "chart-cat",
                       "chart-trend", "chart-loc", "chart-disp", "tbl", "q", "tcount"),
        "changes.html": ("feed", "feedsub", "quality"),
        "about.html": ("srclink",),
    }[name]
    for mount in expected + ("foot", "theme", "payload"):
        assert f'id="{mount}"' in html, f"{name}: missing mount point: {mount}"


@pytest.mark.parametrize("name", PAGE_NAMES)
def test_built_page_is_self_contained(name):
    """No CDN, no external stylesheet, no remote image.

    The whole point of inlining is that a page keeps working from file://, offline, and
    as an email attachment — which matters when the thing being archived may stop being
    public. One `<script src>` would quietly end that.
    """
    html = read(name)
    assert "<script src=" not in html, f"{name}: loads an external script"
    assert '<link rel="stylesheet"' not in html, f"{name}: loads an external stylesheet"
    remote_img = re.findall(r'<img[^>]+src="(?!data:)([^"]*)"', html)
    assert not remote_img, f"{name}: image is not inlined: {remote_img}"


@pytest.mark.parametrize("name", PAGE_NAMES)
def test_built_page_carries_the_disclaimer(name):
    """The site must never read as though it speaks for Rowan."""
    text = re.sub(r"\s+", " ", read(name))
    for phrase in (
        "This site isn't associated with Rowan University.",
        "It is built using the help of Claude Code.",
        "Always confirm information presented here against official records, and consult responsible authorities.",
    ):
        assert phrase in text, f"{name}: disclaimer missing: {phrase!r}"


@pytest.mark.parametrize("name", PAGE_NAMES)
def test_nav_links_point_at_pages_that_exist(name):
    html = read(name)
    nav = html.split("<nav", 1)[1].split("</nav>", 1)[0]
    targets = re.findall(r'href="([^"]+)"', nav)
    assert targets, f"{name}: no nav links"
    for target in targets:
        assert target in PAGE_NAMES, f"{name}: nav links to {target}, which is not built"
    assert f'href="{name}" aria-current="page"' in nav, f"{name}: does not mark itself current"


@pytest.mark.parametrize("name", PAGE_NAMES)
def test_inlined_artwork_stays_small(name):
    """Every page is rewritten and committed on every run, so an oversized inline asset
    is re-stored in git twice a day, three times over. The source artwork totals 3.8 MB;
    inlining it unresampled would add that to every page, every run."""
    html = read(name)
    encoded = re.findall(r"data:image/png;base64,([^\"')]*)", html)
    assert encoded, f"{name}: no inlined artwork"
    biggest = max(len(e) for e in encoded)
    assert biggest < 24_000, f"{name}: largest inlined asset is {biggest / 1024:.1f} KB encoded"
    total = sum(len(e) for e in encoded)
    assert total < 80_000, f"{name}: inlined artwork totals {total / 1024:.1f} KB"


@pytest.mark.parametrize("name", PAGE_NAMES)
def test_every_declared_asset_is_inlined(name):
    """build.ASSETS is the contract. A placeholder left in the CSS renders as a broken
    background and a missing one breaks the build, but a token that no longer appears
    anywhere would just silently stop being used."""
    html = read(name)
    for token, filename in build.ASSETS.items():
        assert (SITE / "assets" / filename).exists(), f"{filename} has not been built"
        assert token not in html, f"{name}: {token} was never substituted"
    # The favicon, the masthead logo, the callout owl and both rules.
    assert len(re.findall(r"data:image/png;base64,", html)) >= len(build.ASSETS), \
        f"{name}: not every declared asset reached the page"


def test_asset_sources_are_present_for_rebuilding():
    """The committed outputs are what ship, but the sources have to stay so the artwork
    can be regenerated at a different size. README documents the command."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_assets", ROOT / "scripts" / "make_assets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    missing = [job["source"] for job in module.JOBS.values() if not (ROOT / job["source"]).exists()]
    assert not missing, f"source artwork missing: {missing}"
    declared = {job["out"].split("/")[-1] for job in module.JOBS.values()}
    assert set(build.ASSETS.values()) <= declared, \
        f"build inlines assets nothing builds: {set(build.ASSETS.values()) - declared}"


def test_callout_text_clears_contrast_on_its_fixed_cream():
    """The callout keeps the artwork's cream fill in BOTH themes, so its ink is fixed
    rather than tokenised — which means the usual palette test does not cover it."""
    css = (SITE / "css" / "chrome.css").read_text(encoding="utf-8")
    block = css.split(".callout {", 1)[1].split("\n}", 1)[0]
    cream = re.search(r"--callout-cream:\s*(#[0-9a-fA-F]{6})", block).group(1)
    ink = re.search(r"color:\s*(#[0-9a-fA-F]{6})", block).group(1)
    ratio = contrast(ink, cream)
    assert ratio >= 4.5, f"callout ink {ink} on {cream} is only {ratio:.2f}:1"
    for selector in (".callout strong", ".callout a"):
        rule = css.split(selector + " {", 1)[1].split("}", 1)[0]
        colour = re.search(r"color:\s*(#[0-9a-fA-F]{6})", rule).group(1)
        r = contrast(colour, cream)
        assert r >= 4.5, f"{selector} {colour} on {cream} is only {r:.2f}:1"


@pytest.mark.parametrize("name", PAGE_NAMES)
def test_built_page_actually_runs_and_renders(name):
    """Execute the page script against a DOM stub and confirm it fills its mounts.

    `node --check` only parses. It cannot catch an identifier that was renamed or deleted,
    which is how a page shipped whose headings rendered and whose every chart was empty.
    This runs the script for real: a throw exits 1, mount points left empty exit 2,
    exports with no rows exit 3.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available to execute the page script")
    result = subprocess.run(
        [node, str(ROOT / "tests" / "run_page.mjs"), str(built(name))],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{name} does not render:\n{result.stdout}{result.stderr}"


def test_every_page_is_covered_by_the_render_harness():
    """A page with no entry in run_page.mjs would exit 64 — but only if something runs
    it. This makes adding a page without adding its expectations a failure."""
    harness = (ROOT / "tests" / "run_page.mjs").read_text(encoding="utf-8")
    block = harness.split("const EXPECT = {", 1)[1].split("\n};", 1)[0]
    for name in PAGE_NAMES:
        assert f'"{name}"' in block, f"run_page.mjs has no expectations for {name}"


# ---- colour ---------------------------------------------------------------------


def _relative_luminance(hex_colour: str) -> float:
    value = hex_colour.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(fg: str, bg: str) -> float:
    a, b = _relative_luminance(fg), _relative_luminance(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", block))


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_body_text_clears_the_contrast_floor(theme):
    """4.5:1 minimum for text, in both themes.

    `--text-3` carries the chart axis labels, the `.sub` captions and the footer
    disclaimer — all small text. It shipped at #7a7975, which measured 4.24:1 on
    surface-1 and 3.96:1 on surface-0, so it was below the floor everywhere it was used
    on light. Checked here rather than eyeballed.
    """
    css = (SITE / "css" / "chrome.css").read_text(encoding="utf-8")
    light = _tokens(css.split(":root {", 1)[1].split("}", 1)[0])
    if theme == "dark":
        palette = dict(light, **_tokens(css.split(':root[data-theme="dark"] {', 1)[1].split("}", 1)[0]))
    else:
        palette = light

    failures = []
    for ink in ("--text-1", "--text-2", "--text-3"):
        for surface in ("--surface-0", "--surface-1", "--surface-2"):
            ratio = contrast(palette[ink], palette[surface])
            if ratio < 4.5:
                failures.append(f"{theme}: {ink} on {surface} is {ratio:.2f}:1")
    assert not failures, failures


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_accent_is_only_ever_a_fill_behind_dark_text(theme):
    """Rowan gold is 1.59:1 on white — it can never be text or a mark on a light surface.

    It is used the way The Whit uses it: as a fill with dark ink on top, and as rules.
    So what has to hold is `--accent-ink` ON `--accent`.
    """
    css = (SITE / "css" / "chrome.css").read_text(encoding="utf-8")
    light = _tokens(css.split(":root {", 1)[1].split("}", 1)[0])
    palette = dict(light, **_tokens(css.split(':root[data-theme="dark"] {', 1)[1].split("}", 1)[0])) \
        if theme == "dark" else light
    ratio = contrast(palette["--accent-ink"], palette["--accent"])
    assert ratio >= 4.5, f"{theme}: accent-ink on accent is only {ratio:.2f}:1"
