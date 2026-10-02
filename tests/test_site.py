"""Checks on the generated page itself.

A JavaScript syntax error in the template produces a page that serves with HTTP 200,
renders its headings and chrome, and shows **no data at all** — every chart and the whole
table silently empty. That has happened twice during development (a duplicated `const`
declaration, and a missing comma in an object literal), and neither was caught by any
other test because the Python pipeline was perfectly healthy both times.

So the built page gets parsed here.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).parent.parent
TEMPLATE = ROOT / "site" / "template.html"
BUILT = ROOT / "docs" / "index.html"

SCRIPT_RE = re.compile(r"<script>\s*\n(.*?)</script>", re.S)


def extract_main_script(html: str) -> str:
    """Return the page's own inline script, excluding the JSON payload block."""
    scripts = SCRIPT_RE.findall(html)
    assert scripts, "no inline <script> found in the page"
    return max(scripts, key=len)


def check_with_node(source: str, tmp_path: pathlib.Path) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available to parse the page script")
    target = tmp_path / "page.mjs"
    # Top-level await is used in the page, so parse as a module.
    target.write_text(source, encoding="utf-8")
    result = subprocess.run([node, "--check", str(target)], capture_output=True, text=True)
    assert result.returncode == 0, f"page script does not parse:\n{result.stderr}"


def test_template_script_parses(tmp_path):
    """The source template must be valid JavaScript."""
    source = extract_main_script(TEMPLATE.read_text(encoding="utf-8"))
    # The template carries a placeholder where the data is injected; give it a value so
    # the parse exercises the real code rather than failing on the placeholder.
    check_with_node(source.replace("__DATA__", "{}"), tmp_path)


@pytest.mark.skipif(not BUILT.exists(), reason="page not built yet")
def test_built_page_parses(tmp_path):
    """And so must the page that actually ships."""
    check_with_node(extract_main_script(BUILT.read_text(encoding="utf-8")), tmp_path)


@pytest.mark.skipif(not BUILT.exists(), reason="page not built yet")
def test_built_page_has_its_data_and_mounts():
    """Guard the specific failure mode: chrome renders, data does not."""
    html = BUILT.read_text(encoding="utf-8")
    assert '<script id="payload" type="application/json">' in html
    assert "__DATA__" not in html, "the data placeholder was never substituted"
    for mount in ("chart-month", "chart-cat", "chart-trend", "chart-loc", "chart-disp", "tbl", "scope"):
        assert f'id="{mount}"' in html, f"missing mount point: {mount}"
    # The payload should be substantial; an empty object means the build produced nothing.
    payload = html.split('type="application/json">', 1)[1].split("</script>", 1)[0]
    assert len(payload) > 100_000, f"payload is only {len(payload)} bytes"


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

    template = TEMPLATE.read_text(encoding="utf-8")
    block = template.split("const DISP_LABEL = {", 1)[1].split("};", 1)[0]
    labelled = set(re.findall(r"(\w+)\s*:", block))
    assert flags <= labelled, f"disposition flags with no display label: {sorted(flags - labelled)}"


def test_axis_text_colour_uses_inline_style_not_a_fill_attribute():
    """`.axis { fill: ... }` beats a `fill="..."` presentation attribute.

    The coverage labels under the year matrix were written with a fill attribute and
    silently rendered grey, so "complete year" and "partial" looked identical.
    """
    template = TEMPLATE.read_text(encoding="utf-8")
    offenders = re.findall(r'<text class="axis"[^`>]*\sfill="(?!none)[^"]+"', template)
    assert not offenders, f"these .axis texts set fill as an attribute and will be overridden: {offenders}"


@pytest.mark.skipif(not BUILT.exists(), reason="page not built yet")
def test_built_page_actually_runs_and_renders():
    """Execute the page script against a DOM stub and confirm it fills its charts.

    `node --check` only parses. It cannot catch an identifier that was renamed or deleted,
    which is how a page shipped whose headings rendered and whose every chart was empty.
    This runs the script for real: a throw exits 1, mount points left empty exit 2.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available to execute the page script")
    result = subprocess.run(
        [node, str(ROOT / "tests" / "run_page.mjs"), str(BUILT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"page does not render:\n{result.stdout}{result.stderr}"
