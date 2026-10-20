"""1.4.0 M5: `export-devices` and `import-devices` (the same planner as the Devices tab)."""

from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.templates import create_project


@pytest.fixture
def folders(tmp_path: Path) -> tuple[Path, Path, Path]:
    src, dst = tmp_path / "src", tmp_path / "dst"
    create_project(src, "small-satellite")
    create_project(dst, "blank")
    return src, dst, tmp_path / "lib.json"


def test_save_list_preview_and_add(
    folders: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    src, dst, lib = folders
    units = sorted(load_project(src).project.units)[:2]
    assert cli_main(["export-devices", str(src), str(lib), "--unit", units[0]]) == 0
    assert cli_main(["export-devices", str(src), str(lib), "--unit", units[1]]) == 0  # added to it
    capsys.readouterr()
    assert cli_main(["import-devices", str(dst), str(lib), "--list"]) == 0
    listed = capsys.readouterr().out
    assert all(f"{u}:" in listed for u in units)

    before = model_hash(load_project(dst).project)
    assert cli_main(["import-devices", str(dst), str(lib), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Dry run: nothing was changed." in out and f"{units[0]}: OK as {units[0]}" in out
    assert model_hash(load_project(dst).project) == before

    assert cli_main(["import-devices", str(dst), str(lib), "--unit", units[0]]) == 0
    assert "Added 1 device(s)" in capsys.readouterr().out
    got = load_project(dst).project
    assert set(got.units) == {units[0]}
    assert all(c.part_id in got.parts for c in got.connectors.values())

    assert cli_main(["import-devices", str(dst), str(lib), "--unit", units[0]]) == 0  # again
    assert f"{units[0]}-2" in capsys.readouterr().out
    assert set(load_project(dst).project.units) == {units[0], f"{units[0]}-2"}


def test_a_unit_that_does_not_exist_and_a_file_that_is_not_a_library(
    folders: tuple[Path, Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src, dst, lib = folders
    assert cli_main(["export-devices", str(src), str(lib), "--unit", "NOPE"]) == 2
    assert "does not exist" in capsys.readouterr().err
    assert not lib.exists()
    other = tmp_path / "other.json"
    other.write_text("[]")
    assert cli_main(["import-devices", str(dst), str(other)]) == 2
    assert "not a device library" in capsys.readouterr().err


def test_a_device_that_the_file_lacks_changes_nothing(
    folders: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    src, dst, lib = folders
    unit = sorted(load_project(src).project.units)[0]
    assert cli_main(["export-devices", str(src), str(lib), "--unit", unit]) == 0
    before = model_hash(load_project(dst).project)
    assert cli_main(["import-devices", str(dst), str(lib), "--unit", "GHOST"]) == 1
    assert "The file has no such device." in capsys.readouterr().out
    assert model_hash(load_project(dst).project) == before
