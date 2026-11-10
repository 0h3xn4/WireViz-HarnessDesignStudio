# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The compliance assessment (ours) is complete and consistent, and the matrix tool builds a matrix
from it. The requirement lists and the matrix hold ESA's text: they are not in the repository
(the owner's decision of 2026-11-10, D-221), so the tool is run here on invented lists."""

from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

import pytest

from tools import build_compliance_matrix as m

ROOT = Path(__file__).resolve().parent.parent / "compliance"
ASSESSMENT = ROOT / "assessment"
PROCESS_STATUSES = {"evidence-candidate", "partial", "gap", "human", "na"}
DESIGN_STATUSES = {"none", "partial", "automatic", "human", "na"}


def rows(name: str) -> list[dict[str, str]]:
    return m.read(ASSESSMENT / name)


def _standard_of(rid: str) -> str:
    if rid.startswith("ESCC3901"):
        return "ESCC-3901"
    return next(s for s in m.DESIGN if rid.startswith(s[:-1].rstrip("-") + "_"))


def _invented_lists(folder: Path) -> None:
    """One invented requirement for every clause rule and single assessment of ours, plus one that
    does not apply at criticality C. The text is made up: it is not the text of any standard."""
    folder.mkdir()
    process = {s: [] for s in m.PROCESS}  # type: dict[str, list[dict[str, str]]]
    for i, r in enumerate(rows("process_rules.csv")):
        prefix = r["prefix"]
        clause = prefix if not prefix[:1].isdigit() else f"{prefix}.1"
        process[r["standard"]].append(
            {"ID": f"{r['standard']}_9{i:05d}", "clause": clause, "text": "Invented text.",
             "deleted": "", "cat_C": "Y"}
        )  # fmt: skip
    for s in m.PROCESS:
        process[s].append(
            {
                "ID": f"{s}_8000000",
                "clause": "5.1",
                "text": "Invented.",
                "deleted": "",
                "cat_C": "N",
            }
        )
    for r in rows("process_overrides.csv"):
        std = "ECSS-E-ST-40C" if r["ID"].startswith("ECSS-E-ST-40_") else "ECSS-Q-ST-80C"
        process[std].append(
            {"ID": r["ID"], "clause": "5.1", "text": "Invented text.", "deleted": "", "cat_C": "Y"}
        )
    design = {s: [] for s in m.DESIGN}  # type: dict[str, list[dict[str, str]]]
    for r in rows("design_assessment.csv"):
        design[_standard_of(r["ID"])].append(
            {"ID": r["ID"], "clause": "1", "text": "Invented text.", "deleted": "",
             "harness_relevant": "Y"}
        )  # fmt: skip
    for name, table in [*process.items(), *design.items()]:
        with (folder / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(table[0]))
            w.writeheader()
            w.writerows(table)


@pytest.fixture
def built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    _invented_lists(tmp_path / "requirements")
    monkeypatch.setattr(m, "REQUIREMENTS", tmp_path / "requirements")
    return m.build()


def test_the_tool_builds_a_matrix_with_a_status_and_a_reason_for_every_row(
    built: list[list[str]],
) -> None:
    assert built
    for r in built:
        assert len(r) == len(m.HEADER)
        assert r[6], r[2]
        assert r[10], r[2]
        if r[6] in ("gap", "partial") and r[1] == "A":
            assert r[9], f"{r[2]} has no gap reference"
    assert any(r[6] == "na" for r in built)
    assert {r[2] for r in built if r[1] == "B"} == {r["ID"] for r in rows("design_assessment.csv")}


def test_the_tool_refuses_without_the_lists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(m, "REQUIREMENTS", tmp_path / "nothing")
    assert m.main() == 2
    assert "tools.extract_requirements" in capsys.readouterr().err


def test_no_assessment_claims_compliance() -> None:
    for name in ("process_rules.csv", "process_overrides.csv", "design_assessment.csv"):
        for r in rows(name):
            assert not any("complian" in v.lower() for k, v in r.items() if "status" in k), r
    assert {r["status"] for r in rows("process_rules.csv")} <= PROCESS_STATUSES
    assert {r["after_status"] for r in rows("process_rules.csv")} <= PROCESS_STATUSES
    assert {r["status"] for r in rows("process_overrides.csv")} <= PROCESS_STATUSES
    for r in rows("design_assessment.csv"):
        assert {r["today"], r["target"], r["after"]} <= DESIGN_STATUSES, r


def test_gap_references_are_in_the_analysis() -> None:
    text = (ROOT / "gap_analysis.md").read_text(encoding="utf-8")
    for name in ("process_rules.csv", "process_overrides.csv", "design_assessment.csv"):
        for r in rows(name):
            if r["gap"]:
                assert f"| {r['gap']} |" in text, (name, r["gap"])


def test_files_named_as_evidence_exist() -> None:
    root = ROOT.parent
    fields = {
        "process_rules.csv": ("evidence", "after_evidence"),
        "process_overrides.csv": ("evidence",),
        "design_assessment.csv": ("evidence", "tests"),
    }
    for name, keys in fields.items():
        for r in rows(name):
            for key in keys:
                for path in re.findall(
                    r"\b((?:tests|tools|docs|compliance|src)/[\w./-]+\.(?:py|md|csv|json|toml))",
                    r[key],
                ):
                    assert (root / path).exists(), f"{name} {r.get('ID') or r['prefix']}: {path}"


def test_the_text_of_the_standards_is_not_in_the_repository_and_stays_out() -> None:
    """D-221: the lists and the matrix are gone and Git ignores them when they are made locally."""
    for name in (*m.PROCESS, *m.DESIGN):
        assert not (m.REQUIREMENTS / f"{name}.csv").exists() or _ignored(
            m.REQUIREMENTS / f"{name}.csv"
        )
    ignore = (ROOT.parent / ".gitignore").read_text(encoding="utf-8").splitlines()
    for line in (
        "compliance/requirements/ECSS-*.csv",
        "compliance/requirements/ESCC-*.csv",
        "compliance/compliance_matrix.csv",
    ):
        assert line in ignore
    assert (m.REQUIREMENTS / "overrides.csv").is_file()  # our own classification stays


def _ignored(path: Path) -> bool:
    done = subprocess.run(  # noqa: S603
        ["git", "check-ignore", "-q", str(path)],  # noqa: S607
        cwd=ROOT.parent,
        check=False,
    )
    return done.returncode == 0
