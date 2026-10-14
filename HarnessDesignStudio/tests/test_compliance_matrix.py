"""The compliance matrix is rebuilt from the requirement lists and the assessments."""

from __future__ import annotations

import csv
from pathlib import Path

from tools import build_compliance_matrix as m

ROOT = Path(__file__).resolve().parent.parent / "compliance"


def test_every_applicable_requirement_has_a_status_and_a_reason() -> None:
    rows = m.build()
    assert rows
    for r in rows:
        assert r[6], r[2]
        assert r[10], r[2]
        if r[6] in ("gap", "partial") and r[1] == "A":
            assert r[9], f"{r[2]} has no gap reference"


def test_matrix_file_is_current() -> None:
    with (ROOT / "compliance_matrix.csv").open(newline="", encoding="utf-8") as f:
        on_disk = list(csv.reader(f))
    assert on_disk[0] == m.HEADER
    assert on_disk[1:] == m.build()


def test_no_row_claims_compliance() -> None:
    assert not any("complian" in r[6].lower() for r in m.build())


def test_gap_references_are_in_the_analysis() -> None:
    text = (ROOT / "gap_analysis.md").read_text(encoding="utf-8")
    for r in m.build():
        if r[9]:
            assert f"| {r[9]} |" in text, r[9]


def test_files_named_as_evidence_exist() -> None:
    import re

    root = ROOT.parent
    for r in m.build():
        for field in (r[8], r[12]):
            for path in re.findall(
                r"\b((?:tests|tools|docs|compliance|src)/[\w./-]+\.(?:py|md|csv|json|toml))", field
            ):
                assert (root / path).exists(), f"{r[2]}: {path}"
