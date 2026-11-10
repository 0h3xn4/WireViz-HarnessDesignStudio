# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Supply chain (brief 2.9): every action is pinned to a full commit, every workflow has the least
permissions it needs, and nothing publishes without a tag.

The inherited WireViz workflow `main.yml` is upstream's file, kept byte for byte as at the fork base
(decision D-218, tests/test_upstream_unchanged.py), so the pinning and permission rules do not
apply to it: it has unpinned actions and no `permissions` (owner-checklist.md B3 and C: disable it
in the Actions tab if it is not needed). It is still checked for secrets on pull requests."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = set(
    json.loads((ROOT / "tests" / "fixtures" / "upstream_e4fe099f.json").read_text("utf-8"))["files"]
)
ALL_WORKFLOWS = sorted((ROOT.parent / ".github" / "workflows").glob("*.yml"))
WORKFLOWS = [p for p in ALL_WORKFLOWS if f".github/workflows/{p.name}" not in UPSTREAM]
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)(.*)$")
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


def _id(path: Path) -> str:
    return path.name


@pytest.mark.parametrize("path", WORKFLOWS, ids=_id)
def test_every_action_is_pinned_to_a_full_commit_with_its_version_in_a_comment(path: Path) -> None:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = USES.match(line)
        if match is None or match.group(1).startswith("./"):
            continue
        assert PINNED.match(match.group(1)), f"{path.name}:{number}: not pinned: {line.strip()}"
        assert re.search(r"#\s*v\d", match.group(2)), f"{path.name}:{number}: no version comment"


@pytest.mark.parametrize("path", WORKFLOWS, ids=_id)
def test_every_workflow_sets_its_permissions_at_the_top(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    top = re.search(r"^permissions:\s*\n\s+contents:\s*read\b", text, re.MULTILINE)
    assert top, f"{path.name}: needs a top-level `permissions: contents: read`"


def test_only_the_upstream_workflow_is_left_out() -> None:
    left_out = sorted(p.name for p in ALL_WORKFLOWS if p not in WORKFLOWS)
    assert left_out in ([], ["main.yml"]), left_out


@pytest.mark.parametrize("path", ALL_WORKFLOWS, ids=_id)
def test_no_workflow_runs_code_of_a_pull_request_with_secrets(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "pull_request_target" not in text
    assert "workflow_run" not in text


def test_only_the_jobs_that_need_more_say_so() -> None:
    wide = []
    for path in WORKFLOWS:
        for line in path.read_text(encoding="utf-8").splitlines():
            if re.match(
                r"^\s{4,}(contents|security-events|id-token|attestations|pages):\s*write", line
            ):
                wide.append(f"{path.name}: {line.strip()}")
    allowed = {
        "harness-legal.yml": {
            "security-events: write  # the one job that uploads results to code scanning"
        },
    }
    for item in wide:
        name, _, what = item.partition(": ")
        assert what in allowed.get(name, set()) or name == "release.yml", item


def test_codeql_leaves_out_only_the_upstream_wireviz_files() -> None:
    """D-218: the CodeQL configuration ignores the restored upstream files and nothing else."""
    import fnmatch

    legal = (ROOT.parent / ".github" / "workflows" / "harness-legal.yml").read_text("utf-8")
    assert "config-file: ./.github/codeql/codeql-config.yml" in legal
    config = (ROOT.parent / ".github" / "codeql" / "codeql-config.yml").read_text("utf-8")
    assert "queries" not in config and "paths:" not in config.replace("paths-ignore:", "")
    ignored = re.findall(r"^\s+-\s+(\S+)\s*$", config.split("paths-ignore:", 1)[1], re.M)
    assert ignored == ["src/wireviz/**", "setup.py"]
    python = sorted(
        p.relative_to(ROOT.parent).as_posix()
        for p in ROOT.parent.rglob("*.py")
        if "HarnessDesignStudio" not in p.parts
        and not any(part.startswith(".") for part in p.relative_to(ROOT.parent).parts)
    )
    hit = [f for f in python if any(fnmatch.fnmatch(f, g) for g in ignored)]
    assert hit and set(hit) <= UPSTREAM, set(hit) - UPSTREAM
    assert {f for f in UPSTREAM if f.endswith(".py")} <= set(hit)
