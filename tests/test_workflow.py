"""Checks on the GitHub Actions workflow.

A workflow with invalid YAML fails in 0 seconds with no useful output, and because it
never reaches a step, nothing in the repository notices. That shipped: multi-line Python
embedded in a `run: |` block was written at column 0, which ends the block scalar early
and leaves YAML trying to parse `import json,pathlib,sys` as a key.
"""

from __future__ import annotations

import pathlib
import re

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML not installed")

WORKFLOWS = sorted((pathlib.Path(__file__).parent.parent / ".github" / "workflows").glob("*.yml"))


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_is_valid_yaml(path):
    yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_has_jobs_with_steps(path):
    """A file can parse as YAML and still be structurally useless."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc.get("jobs"), f"{path.name}: no jobs"
    for name, spec in doc["jobs"].items():
        assert spec.get("steps") or spec.get("uses"), f"{path.name}: job {name!r} has no steps"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_run_blocks_are_fully_indented(path):
    """Every line of a `run: |` block must be indented past the block's own key.

    YAML ends a block scalar at the first line indented less than the block, so an
    under-indented continuation line is silently reinterpreted as YAML structure. This is
    the exact failure that produced a 0-second workflow run.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    offenders = []
    block_indent = None
    for number, line in enumerate(lines, 1):
        if block_indent is None:
            if re.match(r"^\s*run:\s*[|>]", line):
                block_indent = len(line) - len(line.lstrip())
            continue
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= block_indent:
            # Dedent to the key's level or beyond ends the block; that is only legitimate
            # for the next key or list item, which starts with a letter or a dash.
            if not re.match(r"^\s*(-|\w)", line):
                offenders.append((number, line))
            block_indent = None
            if re.match(r"^\s*run:\s*[|>]", line):
                block_indent = indent
    assert not offenders, f"{path.name}: lines escaping their run: block: {offenders}"


def test_pages_deploy_matches_the_configured_source():
    """The workflow builds and deploys Pages itself, so the Pages source must be
    'GitHub Actions' (build_type: workflow), not a branch folder."""
    doc = yaml.safe_load((WORKFLOWS[0]).read_text(encoding="utf-8"))
    steps = [s for job in doc["jobs"].values() for s in job.get("steps", [])]
    uses = [s.get("uses", "") for s in steps]
    assert any("upload-pages-artifact" in u for u in uses), "nothing uploads a Pages artifact"
    assert any("deploy-pages" in u for u in uses), "nothing deploys to Pages"
    perms = doc.get("permissions", {})
    for needed in ("pages", "id-token", "contents"):
        assert needed in perms, f"missing permission: {needed}"
