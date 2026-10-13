"""M7: the usability kit computes SUS and success correctly and prepares the task material."""

import sys
from pathlib import Path

import pytest

from harness_design_studio.core.io.loader import load_project
from tools.usability_setup import build
from tools.usability_summary import read, report, sus_score

DOCS = Path(__file__).resolve().parents[1] / "docs" / "usability"


def test_sus_score_matches_the_standard_formula() -> None:
    assert sus_score([5, 1, 5, 1, 5, 1, 5, 1, 5, 1]) == 100.0
    assert sus_score([1, 5, 1, 5, 1, 5, 1, 5, 1, 5]) == 0.0
    assert sus_score([3] * 10) == 50.0
    assert sus_score([4, 2, 4, 2, 4, 2, 4, 2, 4, 2]) == 75.0
    with pytest.raises(ValueError):
        sus_score([1, 2, 3])
    with pytest.raises(ValueError):
        sus_score([6] * 10)


def test_report_flags_tasks_below_target() -> None:
    results = [
        {
            "participant": "P1",
            "persona": "Dana",
            "task": "T1",
            "success": "1",
            "seconds": "600",
            "wrong_clicks": "1",
            "unclear_remarks": "0",
        },
        {
            "participant": "P2",
            "persona": "Dana",
            "task": "T1",
            "success": "0",
            "seconds": "900",
            "wrong_clicks": "5",
            "unclear_remarks": "3",
        },
        {
            "participant": "P1",
            "persona": "Sam",
            "task": "T5",
            "success": "1",
            "seconds": "20",
            "wrong_clicks": "0",
            "unclear_remarks": "0",
        },
    ]
    sus = [{"participant": "P1", **{f"q{k}": v for k, v in enumerate("4242424242", start=1)}}]
    text, ok = report(results, sus)
    assert not ok and "T1: success 50%" in text and "T5" not in text.split("Priority bugs")[1]
    assert "SUS: 75.0" in text


def test_templates_parse_and_pass() -> None:
    text, ok = report(read(DOCS / "results-template.csv"), read(DOCS / "sus-template.csv"))
    assert "T1" in text and "SUS: 75.0" in text and not ok  # 75 is below the target of 80


def test_setup_builds_loadable_material_with_one_corrupt_project(tmp_path: Path) -> None:
    build(tmp_path)
    assert (tmp_path / "icd.csv").read_text().count("\n") == 4
    assert not load_project(tmp_path / "t1-empty").has_errors
    assert load_project(tmp_path / "t6-t7-generated").project.harnesses
    broken = load_project(tmp_path / "t8-corrupt")
    assert broken.project.recovered and len(broken.project.units) > 5  # the rest still loads


def test_icd_csv_has_exactly_two_bad_rows_for_t4(tmp_path: Path) -> None:
    from harness_design_studio.core.imports import parse_csv, plan_interface_import

    build(tmp_path)
    table = parse_csv((tmp_path / "icd.csv").read_text())
    project = load_project(tmp_path / "t6-t7-generated").project
    plan = plan_interface_import(project, table, {"id": 0, "type": 1, "from": 2, "to": 3})
    assert plan.ok_count == 1 and len([r for r in plan.rows if not r.ok]) == 2


def test_a_missing_input_file_is_a_message_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tools import usability_summary

    monkeypatch.setattr(sys, "argv", ["x", str(tmp_path / "a.csv"), str(tmp_path / "b.csv")])
    assert usability_summary.main() == 2
    err = capsys.readouterr().err
    assert "could not be read" in err and "a.csv" in err
