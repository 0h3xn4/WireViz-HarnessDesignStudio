"""CD-B6: the commands `import-pinout` and `export-pinout` (the same planner as the wizard) and
the round trip between them."""

from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import devices
from harness_design_studio.core.commands import History
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.issues import errors
from harness_design_studio.core.model import Project
from tests.test_change_control import do_release, exported, full, releasable
from tests.test_edit_device import device, with_connector

CSV = "Connector,Pin,Signal,Mode,Remarks\nJ1,A1,PWR,fixed,x\nJ1,A2,RTN,fixed,\nJ1,3,CANH,,\nJ1,4,CANL,,\n"


def folder(tmp_path: Path, project: Project | None = None) -> Path:
    save_project(project or device(), tmp_path / "p")
    return tmp_path / "p"


def test_dry_run_changes_nothing_and_a_real_run_saves(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = folder(tmp_path)
    f = tmp_path / "gyro.csv"
    f.write_text(CSV)
    before = model_hash(load_project(p).project)
    base = ["import-pinout", str(p), str(f), "--unit", "GYRO1", "--default-part", "MY-HD-6-F"]
    assert cli_main([*base, "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "GYRO1-J01: OK added (4 pin(s))" in out and "Dry run: nothing was changed." in out
    assert "Column 'Remarks' is not imported" in out
    assert model_hash(load_project(p).project) == before
    assert cli_main(base) == 0
    out = capsys.readouterr().out
    assert "Imported 1 connector(s), 4 pin(s)" in out
    q = load_project(p).project
    c = q.connectors["GYRO1-J01"]
    assert [(x.id, x.signal, x.fixed) for x in c.pins] == [
        ("A1", "PWR", True),
        ("A2", "RTN", True),
        ("3", "CANH", False),
        ("4", "CANL", False),
    ]
    assert errors(check_integrity(q)) == []
    assert cli_main(["validate", str(p)]) == 0


def test_a_bad_row_stops_everything(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = folder(tmp_path)
    f = tmp_path / "bad.csv"
    f.write_text("Pin,Signal\nA1,PWR\nA 2,RTN\n")
    before = model_hash(load_project(p).project)
    assert (
        cli_main(
            ["import-pinout", str(p), str(f), "--unit", "GYRO1", "--default-part", "MY-HD-6-F"]
        )
        == 1
    )
    out = capsys.readouterr().out
    assert "row 3: ERROR" in out and "pin name" in out and "Nothing was changed." in out
    assert model_hash(load_project(p).project) == before


def test_errors_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = folder(tmp_path)
    f = tmp_path / "gyro.csv"
    f.write_text(CSV)
    assert (
        cli_main(["import-pinout", str(p), str(f), "--unit", "NOPE", "--default-part", "MY-HD-6-F"])
        == 2
    )
    assert "does not exist" in capsys.readouterr().err
    assert cli_main(["import-pinout", str(p), str(f), "--unit", "GYRO1"]) == 1  # no part
    assert "No part for the new connector J1" in capsys.readouterr().out
    assert (
        cli_main(["import-pinout", str(p), str(tmp_path / "missing.csv"), "--unit", "GYRO1"]) == 2
    )
    nopin = tmp_path / "nopin.csv"
    nopin.write_text("Signal\nPWR\n")
    assert (
        cli_main(
            ["import-pinout", str(p), str(nopin), "--unit", "GYRO1", "--default-part", "MY-HD-6-F"]
        )
        == 2
    )
    assert "needs a Pin column" in capsys.readouterr().err
    empty = tmp_path / "empty.csv"
    empty.write_text("Pin,Signal\n")
    assert (
        cli_main(
            ["import-pinout", str(p), str(empty), "--unit", "GYRO1", "--default-part", "MY-HD-6-F"]
        )
        == 1
    )
    assert "Nothing to import." in capsys.readouterr().out
    assert (
        cli_main(
            [
                "import-pinout",
                str(p),
                str(f),
                "--unit",
                "GYRO1",
                "--default-part",
                "MY-HD-6-F",
                "--part",
                "oops",
            ]
        )
        == 2
    )


def test_new_device_parts_columns_and_replace(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = folder(tmp_path)
    f = tmp_path / "cam.csv"
    f.write_text("Terminal,Name_of_signal,Where\n1,PWR,J1\n2,RTN,J1\n1,CANH,J2\n")
    args = ["import-pinout", str(p), str(f), "--unit", "CAM1", "--new-device", "Camera", "--subsystem", "payload",
            "--part", "J1=MY-HD-6-F", "--part", "J2=MY-PLAIN-4", "--gender", "male"]  # fmt: skip
    # the headings are not the ones the tool knows: say which column is which
    assert cli_main(args) == 2
    assert "needs a Pin column" in capsys.readouterr().err
    cols = [
        "--column",
        "pin=Terminal",
        "--column",
        "connector=Where",
        "--column",
        "signal=Name_of_signal",
    ]
    assert cli_main([*args, *cols]) == 0
    q = load_project(p).project
    assert q.units["CAM1"].name == "Camera" and q.units["CAM1"].subsystem == "payload"
    assert {c.part_id for c in q.connectors.values() if c.unit_id == "CAM1"} == {
        "MY-HD-6-F",
        "MY-PLAIN-4",
    }
    assert all(c.gender == "male" for c in q.connectors.values() if c.unit_id == "CAM1")
    assert cli_main([*args, "--column", "nonsense=Where"]) == 2
    assert cli_main([*args, "--column", "pin=Nope"]) == 2
    # replace: only the named pins stay
    g = tmp_path / "again.csv"
    g.write_text("Connector,Pin,Signal\nJ1,9,X\n")
    assert (
        cli_main(["import-pinout", str(p), str(g), "--unit", "CAM1", "--replace", "--dry-run"]) == 0
    )
    assert cli_main(["import-pinout", str(p), str(g), "--unit", "CAM1", "--replace"]) == 0
    q = load_project(p).project
    assert [x.id for x in q.connectors["CAM1-J01"].pins] == ["9"]


def test_xlsx_in(tmp_path: Path) -> None:
    from openpyxl import Workbook

    p = folder(tmp_path)
    wb = Workbook()
    ws = wb.active
    for row in (["Pin", "Signal", "Gender"], ["1", "PWR", "Female"], ["2", "RTN", "Female"]):
        ws.append(row)
    f = tmp_path / "icd.xlsx"
    wb.save(f)
    assert (
        cli_main(
            ["import-pinout", str(p), str(f), "--unit", "GYRO1", "--default-part", "MY-PLAIN-4"]
        )
        == 0
    )
    q = load_project(p).project
    assert (
        q.connectors["GYRO1-J01"].gender == "female"
        and q.connectors["GYRO1-J01"].pins[0].signal == "PWR"
    )


def test_a_released_harness_blocks_the_import(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    proj = full()
    hid = releasable(proj)
    do_release(proj, hid, exported(proj, tmp_path / "o"))
    cid = next(c.mates_with for c in proj.harnesses[hid].connectors if c.mates_with)
    unit, name = proj.connectors[cid].unit_id, proj.connectors[cid].name
    used = next(x for x in proj.connectors[cid].pins if x.interface_id)
    p = folder(tmp_path, proj)
    f = tmp_path / "x.csv"
    f.write_text(f"Connector,Pin,Signal\n{name},{used.id},TEST\n")
    assert cli_main(["import-pinout", str(p), str(f), "--unit", unit or "", "--dry-run"]) == 1
    out = capsys.readouterr().out
    assert hid in out and "released" in out and "Nothing was changed." in out


def test_export_pinout_to_the_screen_and_to_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    proj, cid = with_connector()
    History(proj).execute("fill", devices.fill_from_type(proj, cid, ["3", "4"], "can"))
    p = folder(tmp_path, proj)
    assert cli_main(["export-pinout", str(p), "--unit", "GYRO1"]) == 0
    out = capsys.readouterr().out
    assert "Connector,Role,Mates with,Part,Pin,Signal,Interface,Wires,Spare" in out
    assert "GYRO1-J01,box,,MY-HD-6-F,3,CANH,,,no" in out
    csv_path = tmp_path / "gyro.csv"
    assert cli_main(["export-pinout", str(p), "--unit", "GYRO1", "-o", str(csv_path)]) == 0
    assert csv_path.read_text() == out and "Wrote" in capsys.readouterr().out
    xlsx = tmp_path / "gyro.xlsx"
    assert cli_main(["export-pinout", str(p), "--unit", "GYRO1", "--output", str(xlsx)]) == 0
    assert xlsx.read_bytes()[:2] == b"PK"
    assert cli_main(["export-pinout", str(p), "--unit", "NOPE"]) == 2
    assert "does not exist" in capsys.readouterr().err
    assert (
        cli_main(["export-pinout", str(p), "--unit", "PCDU1"]) == 2
    )  # (new_project has no such unit)
    capsys.readouterr()
    assert (
        cli_main(
            [
                "export-pinout",
                str(p),
                "--unit",
                "GYRO1",
                "-o",
                str(tmp_path / "no" / "such" / "x.csv"),
            ]
        )
        == 2
    )


def test_a_unit_without_connectors_has_nothing_to_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = folder(tmp_path)
    assert cli_main(["export-pinout", str(p), "--unit", "GYRO1"]) == 1
    assert "no connectors" in capsys.readouterr().err


def test_what_export_pinout_writes_import_pinout_reads(tmp_path: Path) -> None:
    """The round trip: a device exported from one project is rebuilt in another (the Part column
    names the connector part, the Connector column the connectors)."""
    proj, cid = with_connector()
    History(proj).execute("rename", devices.ops_rename_pin(proj, cid, "1", "A1"))
    History(proj).execute("fill", devices.fill_from_type(proj, cid, ["A1", "2"], "power_primary"))
    (tmp_path / "a").mkdir()
    src = folder(tmp_path / "a", proj)
    out = tmp_path / "gyro.csv"
    assert cli_main(["export-pinout", str(src), "--unit", "GYRO1", "-o", str(out)]) == 0
    (tmp_path / "b").mkdir()
    dst = folder(tmp_path / "b", device())
    assert cli_main(["import-pinout", str(dst), str(out), "--unit", "GYRO1"]) == 0
    a = load_project(src).project.connectors["GYRO1-J01"]
    b = load_project(dst).project.connectors["GYRO1-J01"]
    assert [(x.id, x.signal) for x in b.pins] == [(x.id, x.signal) for x in a.pins]
    assert b.part_id == a.part_id
    # and the workbook (its first sheet is the About sheet; it is passed over)
    book = tmp_path / "gyro.xlsx"
    assert cli_main(["export-pinout", str(src), "--unit", "GYRO1", "-o", str(book)]) == 0
    (tmp_path / "c").mkdir()
    third = folder(tmp_path / "c", device())
    assert cli_main(["import-pinout", str(third), str(book), "--unit", "GYRO1"]) == 0
    c = load_project(third).project.connectors["GYRO1-J01"]
    assert [(x.id, x.signal) for x in c.pins] == [(x.id, x.signal) for x in a.pins]
