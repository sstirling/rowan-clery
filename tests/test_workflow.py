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


# ---- raw-evidence integrity check ---------------------------------------------

import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402

SCRIPT = pathlib.Path(__file__).parent.parent / "scripts" / "verify_raw_integrity.py"


def run_check(cwd):
    return subprocess.run([sys.executable, str(SCRIPT)], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """A tiny git repo shaped like data/raw/, with one commit."""
    raw = tmp_path / "data" / "raw"
    (raw / "FILEID").mkdir(parents=True)
    (raw / "FILEID" / "2026-10-01.csv").write_text("case,date\nA,1\n")
    (raw / "_runs").mkdir()
    (raw / "_runs" / "2026-10-01.json").write_text('{"date":"2026-10-01"}')
    (raw / "manifest.json").write_text(
        json.dumps({"files": {"FILEID": {"last_verified": "2026-10-01",
                                        "snapshots": [{"date": "2026-10-01", "sha256": "x"}]}}})
    )
    for cmd in (["init", "-q"], ["add", "-A"],
                ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"]):
        subprocess.run(["git", *cmd], cwd=tmp_path, capture_output=True)
    return tmp_path


def test_manifest_may_change_every_run(repo):
    """The regression that broke CI three runs running.

    last_verified advances daily by design. The previous guard watched all of data/raw/
    and failed on it, passing only on a day when the committed manifest already carried
    that date.
    """
    path = repo / "data" / "raw" / "manifest.json"
    doc = json.loads(path.read_text())
    doc["files"]["FILEID"]["last_verified"] = "2026-10-02"
    path.write_text(json.dumps(doc))
    assert run_check(repo).returncode == 0


def test_new_run_record_is_allowed(repo):
    (repo / "data" / "raw" / "_runs" / "2026-10-02.json").write_text('{"date":"2026-10-02"}')
    assert run_check(repo).returncode == 0


def test_new_snapshot_is_allowed(repo):
    (repo / "data" / "raw" / "FILEID" / "2026-10-02.csv").write_text("case,date\nA,1\nB,2\n")
    assert run_check(repo).returncode == 0


def test_rewriting_a_snapshot_fails(repo):
    (repo / "data" / "raw" / "FILEID" / "2026-10-01.csv").write_text("tampered\n")
    result = run_check(repo)
    assert result.returncode == 1
    assert "modified or deleted" in result.stderr


def test_deleting_a_snapshot_fails(repo):
    (repo / "data" / "raw" / "FILEID" / "2026-10-01.csv").unlink()
    assert run_check(repo).returncode == 1


def test_manifest_dropping_a_snapshot_fails(repo):
    """The manifest is not evidence, but it is the index of what evidence exists."""
    path = repo / "data" / "raw" / "manifest.json"
    doc = json.loads(path.read_text())
    doc["files"]["FILEID"]["snapshots"] = []
    path.write_text(json.dumps(doc))
    result = run_check(repo)
    assert result.returncode == 1
    assert "dropped snapshot entries" in result.stderr
