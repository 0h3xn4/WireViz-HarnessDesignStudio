"""REQ-CLI-01: `harness validate` and `harness check`."""

from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from tests.helpers import MINI3, copy_project, edit_json


def test_validate_clean_project(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(MINI3)]) == 0
    out = capsys.readouterr().out
    assert "3 units" in out and "0 error(s)" in out and "placeholder" in out.lower()


def test_validate_reports_errors_exit_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = copy_project(MINI3, tmp_path / "p")
    (root / "physical/connectors/aocs.json").write_text('{"connectors": []}')
    assert main(["validate", str(root)]) == 1
    assert "ERROR" in capsys.readouterr().out


def test_validate_not_a_project_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(tmp_path)]) == 2
    assert "not a harness project" in capsys.readouterr().err


def test_check_flags_non_canonical_and_conflicts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = copy_project(MINI3, tmp_path / "p")
    assert main(["check", str(root)]) == 0
    edit_json(root / "logical/units/power.json", lambda d: None)
    assert main(["check", str(root)]) == 0
    assert "not_canonical" in capsys.readouterr().out
    (root / "logical/units/aocs.json").write_text("<<<<<<< HEAD\n")
    assert main(["check", str(root)]) == 1
    assert "merge_conflict" in capsys.readouterr().out


def test_check_read_only_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = copy_project(MINI3, tmp_path / "p")
    edit_json(root / "project.json", lambda d: d.update(schema_version=99))
    main(["check", str(root)])
    assert "newer_version" in capsys.readouterr().out


def test_verify_before_generate_says_to_generate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_design_studio.core import templates

    templates.create_project(tmp_path / "p", "first-steps")
    assert main(["verify", str(tmp_path / "p")]) == 1
    out = capsys.readouterr().out
    assert "signal_missing" in out and "run `harness generate` first" in out
    assert main(["generate", str(tmp_path / "p")]) == 0
    capsys.readouterr()
    assert main(["verify", str(tmp_path / "p")]) == 0
    assert "harness generate" not in capsys.readouterr().out
