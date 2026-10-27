"""1.8.1 trust fixes of the command line (audit C-4, C-5, C-9, C-10, C-11, C-12, F-16): redirected
output is UTF-8, an import that changes nothing exits 0, the lengths import refuses conflicting or
impossible rows, a wrong folder is left empty, a .tsv is tab separated, and the small
inconsistencies between commands are gone."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness_design_studio.cli import quoted
from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core.commands import History
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.kicad import plan_netlist_import, read_netlist
from harness_design_studio.core.model import Project, evolve
from tests.test_data_import import project_with_segments
from tests.test_edit_device import device
from tests.test_kicad import FIXTURE, project_with_unit

SRC = Path(__file__).resolve().parents[1] / "src"
CSV = "Connector,Pin,Signal,Mode\nJ1,A1,PWR,fixed\nJ1,A2,RTN,fixed\nJ1,3,CANH,\nJ1,4,CANL,\n"


def run(project: Project, tmp_path: Path, name: str = "p") -> Path:
    save_project(project, tmp_path / name)
    return tmp_path / name


# ---- C-4 ------------------------------------------------------------------------------------


def test_redirected_output_is_utf8_on_a_system_whose_code_page_is_not(tmp_path: Path) -> None:
    p = tmp_path / "p"
    proj = device()
    proj.meta = evolve(proj.meta, name="Sensor Ω ≤ 5 V ✓")
    save_project(proj, p)
    env = {
        **os.environ,
        "PYTHONIOENCODING": "cp1252",
        "PYTHONUTF8": "0",
        "PYTHONPATH": os.pathsep.join([str(SRC), os.environ.get("PYTHONPATH", "")]),
    }
    done = subprocess.run(
        [sys.executable, "-m", "harness_design_studio.cli.main", "drc", str(p)],
        capture_output=True,
        env=env,
        cwd=tmp_path,
        check=False,
    )
    assert b"charmap" not in done.stderr, done.stderr
    assert "Sensor Ω ≤ 5 V ✓".encode() in done.stdout  # UTF-8, not cp1252


# ---- C-5 / F-16 ------------------------------------------------------------------------------


def test_importing_the_same_pinout_again_is_up_to_date_and_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = run(device(), tmp_path)
    f = tmp_path / "gyro.csv"
    f.write_text(CSV)
    base = ["import-pinout", str(p), str(f), "--unit", "GYRO1", "--default-part", "MY-HD-6-F"]
    assert cli_main(base) == 0
    first = capsys.readouterr().out
    assert "OK added (4 pin(s))" in first
    assert "Generate harnesses again" not in first  # F-16: this project has no interfaces
    before = (p / "units").stat().st_mtime_ns if (p / "units").exists() else 0
    assert cli_main(base) == 0
    again = capsys.readouterr().out
    assert "OK unchanged (4 pin(s))" in again and "OK updated" not in again
    assert "Already up to date." in again and "Nothing to import" not in again
    assert cli_main([*base, "--dry-run"]) == 0
    assert "Already up to date." in capsys.readouterr().out
    assert before == ((p / "units").stat().st_mtime_ns if (p / "units").exists() else 0)


def test_a_pinout_with_a_new_pin_is_still_updated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = run(device(), tmp_path)
    f = tmp_path / "gyro.csv"
    f.write_text(CSV)
    base = ["import-pinout", str(p), str(f), "--unit", "GYRO1", "--default-part", "MY-HD-6-F"]
    assert cli_main(base) == 0
    f.write_text(CSV + "J1,5,SPARE,\n")
    capsys.readouterr()
    assert cli_main(base) == 0
    out = capsys.readouterr().out
    assert "OK updated (5 pin(s))" in out and "Already up to date" not in out


def test_the_generate_again_hint_is_only_for_a_project_with_interfaces(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_design_studio.core.samples import mini3

    proj = mini3()
    unit = sorted(proj.units)[0]
    p = run(proj, tmp_path)
    f = tmp_path / "x.csv"
    f.write_text("Connector,Pin,Signal\nJ9,1,PWR\n")
    part = next(i for i, x in proj.parts.items() if x.category == "connector")
    argv = ["import-pinout", str(p), str(f), "--unit", unit, "--default-part", part]
    assert cli_main(argv) == 0
    assert proj.interfaces and "Generate harnesses again" in capsys.readouterr().out


def test_a_file_with_no_rows_is_still_nothing_to_import(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = run(device(), tmp_path)
    empty = tmp_path / "empty.csv"
    empty.write_text("Pin,Signal\n")
    argv = ["import-pinout", str(p), str(empty), "--unit", "GYRO1", "--default-part", "MY-HD-6-F"]
    assert cli_main(argv) == 1
    assert "Nothing to import." in capsys.readouterr().out


def test_importing_the_same_parts_again_is_up_to_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = run(device(), tmp_path)
    f = tmp_path / "parts.csv"
    f.write_text("Part number,Category,Status\nNEW-1,connector,A\n")
    argv = ["import-parts", str(p), str(f), "--approved", "A"]
    assert cli_main(argv) == 0
    assert "OK added NEW-1" in capsys.readouterr().out
    assert cli_main(argv) == 0
    out = capsys.readouterr().out
    assert "OK unchanged NEW-1" in out and "Already up to date." in out


def test_a_netlist_that_says_what_the_connector_holds_is_unchanged() -> None:
    p = project_with_unit()
    p.connectors["OBC-J01"] = evolve(p.connectors["OBC-J01"], part_id="EX-MICROD-9-F")
    first = plan_netlist_import(
        p, read_netlist(FIXTURE), "OBC", refs=["J1"], connector_ids={"J1": "OBC-J01"}
    )
    assert first.rows[0].action == "updated"
    History(p).execute("import", first.ops)
    again = plan_netlist_import(
        p, read_netlist(FIXTURE), "OBC", refs=["J1"], connector_ids={"J1": "OBC-J01"}
    )
    assert again.rows[0].ok and again.rows[0].action == "unchanged" and again.ops == []


# ---- C-9 -------------------------------------------------------------------------------------


def lengths(tmp_path: Path, rows: str, *extra: str) -> tuple[int, Path]:
    p = tmp_path / "p"
    if not p.exists():
        save_project(project_with_segments(), p)
    f = tmp_path / "len.csv"
    f.write_text("harness,segment,length\n" + rows)
    return cli_main(["import-lengths", str(p), str(f), *extra]), p


def length_of(p: Path) -> float | None:
    return load_project(p).project.harnesses["W010"].segments[0].length_m


def test_conflicting_duplicate_lengths_are_refused_naming_the_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, p = lengths(tmp_path, "W010,W010-L1,850\nW010,W010-L1,1\n")
    out = capsys.readouterr().out
    assert rc == 1 and "row 3" in out and "row 2 says '850'" in out and "another length" in out
    assert "Nothing was changed." in out and length_of(p) is None


def test_identical_duplicate_lengths_are_fine(tmp_path: Path) -> None:
    rc, p = lengths(tmp_path, "W010,W010-L1,850\nW010,W010-L1,850\n")
    assert rc == 0 and length_of(p) == pytest.approx(0.85)


def test_a_huge_length_says_too_large_not_digits_with_a_point(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, p = lengths(tmp_path, "W010,W010-L1,99999999999999999999\n")
    out = capsys.readouterr().out
    assert rc == 1 and "too large" in out and "digits with a decimal point" not in out
    assert length_of(p) is None


# ---- C-10 ------------------------------------------------------------------------------------


def test_a_command_on_an_empty_folder_leaves_it_empty_and_new_still_works(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "emptydir"
    empty.mkdir()
    assert cli_main(["generate", str(empty)]) == 2
    assert list(empty.iterdir()) == [] and not list(empty.glob(".*"))
    capsys.readouterr()
    assert cli_main(["new", str(empty)]) == 0
    assert (empty / "project.json").is_file()


def test_a_command_on_another_folder_leaves_no_helper_file(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    (other / "notes.txt").write_text("x")
    assert cli_main(["generate", str(other)]) == 2
    assert sorted(x.name for x in other.iterdir()) == ["notes.txt"]


# ---- C-11 ------------------------------------------------------------------------------------


def with_pins(tmp_path: Path) -> Path:
    p = run(device(), tmp_path)
    f = tmp_path / "in.csv"
    f.write_text(CSV)
    assert cli_main(["import-pinout", str(p), str(f), "--unit", "GYRO1", "--default-part", "MY-HD-6-F"]) == 0  # fmt: skip
    return p


def test_a_tsv_is_written_with_tabs_and_read_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = with_pins(tmp_path)
    out = tmp_path / "x.tsv"
    assert cli_main(["export-pinout", str(p), "--unit", "GYRO1", "-o", str(out)]) == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# ") and "\t" in lines[1] and "," not in lines[1]
    q = run(device(), tmp_path, "q")
    capsys.readouterr()
    argv = ["import-pinout", str(q), str(out), "--unit", "GYRO1", "--default-part", "MY-HD-6-F"]
    assert cli_main(argv) == 0, capsys.readouterr()
    pins = load_project(q).project.connectors["GYRO1-J01"].pins
    assert [(x.id, x.signal) for x in pins] == [("A1", "PWR"), ("A2", "RTN"), ("3", "CANH"), ("4", "CANL")]  # fmt: skip


def test_an_unknown_ending_is_refused_and_nothing_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = with_pins(tmp_path)
    capsys.readouterr()
    for name in ("x.txt", "x"):
        assert cli_main(["export-pinout", str(p), "--unit", "GYRO1", "-o", str(tmp_path / name)]) == 2  # fmt: skip
        assert ".csv, .tsv, .xlsx" in capsys.readouterr().err
        assert not (tmp_path / name).exists()
    assert cli_main(["export-pinout", str(p), "--unit", "GYRO1", "-o", str(tmp_path / "x.csv")]) == 0  # fmt: skip
    assert "," in (tmp_path / "x.csv").read_text(encoding="utf-8").splitlines()[1]


# ---- C-12 ------------------------------------------------------------------------------------


def test_config_and_library_changes_on_a_read_only_project_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    p = run(device(), tmp_path)
    from harness_design_studio.core.io import loader

    real = loader.load_project

    def read_only(path: Path):  # type: ignore[no-untyped-def]
        result = real(path)
        result.project.read_only = True
        return result

    monkeypatch.setattr("harness_design_studio.cli.data.load_project", read_only)
    monkeypatch.setattr("harness_design_studio.cli.main.load_project", read_only)
    assert cli_main(["library", str(p), "--library-name", "X"]) == 2
    assert "read-only" in capsys.readouterr().err
    assert cli_main(["config", str(p), "--apply-profile", "ecss-q-st-30-11c"]) == 2
    assert "read-only" in capsys.readouterr().err
    assert cli_main(["library", str(p)]) == 0  # only reporting still works


def test_hint_paths_with_spaces_are_quoted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert quoted("plain/dir") == "plain/dir"
    assert quoted("dir with space/ünï") == '"dir with space/ünï"'
    target = tmp_path / "dir with space"
    assert cli_main(["new", str(target)]) == 0
    assert f'validate "{target}"' in capsys.readouterr().out


def test_export_into_a_missing_folder_is_an_error_not_a_new_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = with_pins(tmp_path)
    capsys.readouterr()
    missing = tmp_path / "nowhere"
    assert cli_main(["export-pinout", str(p), "--unit", "GYRO1", "-o", str(missing / "x.csv")]) == 2  # fmt: skip
    assert "does not exist" in capsys.readouterr().err
    assert cli_main(["export-devices", str(p), str(missing / "d.json"), "--unit", "GYRO1"]) == 2
    assert "does not exist" in capsys.readouterr().err
    argv = ["export-subsystem", str(p), str(missing / "s.json"), "--unit", "GYRO1", "--name", "S"]
    assert cli_main(argv) == 2
    assert "does not exist" in capsys.readouterr().err
    assert not missing.exists()
    assert cli_main(["export-devices", str(p), str(tmp_path / "d.json"), "--unit", "GYRO1"]) == 0
