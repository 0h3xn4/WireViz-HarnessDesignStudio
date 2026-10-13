"""REQ-STD-06: the family-group mapping worksheet cites only requirements that exist and covers
every part class of the library (ECSS-Q-ST-30-11C 6.11, 6.12, 6.32; action A-16)."""

from __future__ import annotations

import csv
from pathlib import Path

from harness_design_studio.core.model.library import PART_CATEGORIES

ROOT = Path(__file__).resolve().parent.parent


def _rows() -> list[dict[str, str]]:
    with (ROOT / "compliance" / "family_group_mapping.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_cited_requirements_exist() -> None:
    with (ROOT / "compliance" / "requirements" / "ECSS-Q-ST-30-11C.csv").open(
        newline="", encoding="utf-8"
    ) as f:
        known = {r["ID"] for r in csv.DictReader(f)}
    cited = {i for r in _rows() for i in r["requirements"].split()}
    assert cited and cited <= known, cited - known


def test_every_part_class_has_a_line() -> None:
    classes = {r["tool_class"].split(" ")[0] for r in _rows()}
    assert set(PART_CATEGORIES) <= classes


def test_no_line_claims_a_mapping_the_text_does_not_state() -> None:
    for r in _rows():
        if r["tool_class"].startswith("connector") and "not RF" in r["tool_class"]:
            assert r["status"].startswith("not stated")
