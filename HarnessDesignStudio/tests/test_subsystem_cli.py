"""REQ-LIB-05. `export-subsystem` and `import-subsystem` (the same planner as the Library window)."""

import json
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.links import plan_add_link
from harness_design_studio.core.templates import create_project
from tests.helpers import pinout_project


@pytest.fixture
def folders(tmp_path: Path) -> tuple[Path, Path, Path]:
    src, dst = tmp_path / "src", tmp_path / "dst"
    p = pinout_project()
    ops, _ = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    save_project(p, src)
    create_project(dst, "blank")
    return src, dst, tmp_path / "wheel.json"


def export(src: Path, lib: Path, *extra: str) -> int:
    return cli_main(
        ["export-subsystem", str(src), str(lib), "--device", "OBC", "--device", "RW1",
         "--name", "Wheel drive", *extra]
    )  # fmt: skip


def test_export_show_dry_run_and_import(
    folders: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    src, dst, lib = folders
    assert export(src, lib, "--description", "OBC and a wheel") == 0
    assert "Saved subsystem 'Wheel drive' (2 device(s)" in capsys.readouterr().out
    assert json.loads(lib.read_text())["format"] == "harness-subsystem-library"

    assert cli_main(["import-subsystem", str(dst), str(lib), "--show"]) == 0
    shown = capsys.readouterr().out
    assert "Wheel drive: 2 device(s)" in shown and "OBC and a wheel" in shown and "RW1:" in shown

    before = model_hash(load_project(dst).project)
    assert cli_main(["import-subsystem", str(dst), str(lib), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Dry run: nothing was changed." in out and "OBC: OK as OBC" in out
    assert model_hash(load_project(dst).project) == before

    assert cli_main(["import-subsystem", str(dst), str(lib)]) == 0
    assert "Added subsystem 'Wheel drive': 2 device(s), 1 connection(s)" in capsys.readouterr().out
    got = load_project(dst).project
    assert set(got.units) == {"OBC", "RW1"} and set(got.links) == {"L1"}
    assert {u.subsystem for u in got.units.values()} == {"Wheel drive"}

    assert cli_main(["import-subsystem", str(dst), str(lib)]) == 0  # again: renamed, not replaced
    out = capsys.readouterr().out
    assert "OBC is taken in this project; it is added as OBC-2" in out
    assert set(load_project(dst).project.units) == {"OBC", "RW1", "OBC-2", "RW1-2"}


def test_a_file_is_not_replaced_unless_asked(
    folders: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    src, _, lib = folders
    assert export(src, lib) == 0
    first = lib.read_bytes()
    capsys.readouterr()
    assert export(src, lib, "--description", "changed") == 2
    assert "exists already" in capsys.readouterr().err and lib.read_bytes() == first
    assert export(src, lib, "--description", "changed", "--replace") == 0
    assert lib.read_bytes() != first


def test_mistakes_are_said_in_words_and_change_nothing(
    folders: tuple[Path, Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src, dst, lib = folders
    assert (
        cli_main(["export-subsystem", str(src), str(lib), "--device", "NOPE", "--name", "x"]) == 2
    )
    assert "does not exist" in capsys.readouterr().err and not lib.exists()
    other = tmp_path / "other.json"
    other.write_text("[]")
    before = model_hash(load_project(dst).project)
    assert cli_main(["import-subsystem", str(dst), str(other)]) == 2
    assert "not a subsystem library" in capsys.readouterr().err
    assert export(src, lib) == 0
    data = json.loads(lib.read_text())
    data["connections"][0]["pairs"][0]["a_pin"] = "99"
    lib.write_text(json.dumps(data))
    capsys.readouterr()
    assert cli_main(["import-subsystem", str(dst), str(lib)]) == 1
    captured = capsys.readouterr()
    assert "L1" in captured.err and "Nothing was changed." in captured.out
    assert model_hash(load_project(dst).project) == before
