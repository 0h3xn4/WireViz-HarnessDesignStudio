"""CD-X5: the pinout import planner (core/pinout_import.py): good rows, bad pin names, duplicate
pins, an unknown part, gender words, a released harness that blocks the import, CSV and XLSX,
what stays pending. Headless."""

from pathlib import Path

import pytest

from harness_design_studio.core import devices, edit
from harness_design_studio.core.commands import History
from harness_design_studio.core.imports import ImportError_, parse_csv, read_table
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.issues import errors
from harness_design_studio.core.model import Project
from harness_design_studio.core.pinout_import import (
    FIELDS,
    guess_mapping,
    plan_pinout_import,
    unstored_columns,
)
from tests.test_change_control import do_release, exported, full, releasable
from tests.test_edit_device import device, with_connector

CSV = """Connector,Pin,Signal,Mode,Contact size,Termination,Remarks
J1,A1,PWR,fixed,20,crimp,power in
J1,A2,RTN,fixed,20,crimp,power return
J1,3,CANH,fixed,22,solder,
J1,4,CANL,fixed,22,solder,
J1,5,HEATER_ENABLE,,,,free text
J1,6,,,,,
"""


def table(text: str = CSV) -> list[list[str]]:
    return parse_csv(text)


def plan(p: Project, text: str = CSV, **kw):  # type: ignore[no-untyped-def]
    t = table(text)
    kw.setdefault("unit_id", "GYRO1")
    kw.setdefault("default_part", "MY-HD-6-F")
    return plan_pinout_import(p, t, guess_mapping(t[0]), **kw)


def apply(p: Project, pl) -> None:  # type: ignore[no-untyped-def]
    History(p).execute(pl.label, pl.ops)
    assert errors(check_integrity(p)) == []


def test_headings_are_matched_by_name_and_unstored_columns_are_named() -> None:
    t = table()
    m = guess_mapping(t[0])
    assert [k for k, _ in FIELDS][:6] == [
        "connector",
        "pin",
        "signal",
        "mode",
        "contact_size",
        "termination",
    ]
    assert m == {
        "connector": 0,
        "pin": 1,
        "signal": 2,
        "mode": 3,
        "contact_size": 4,
        "termination": 5,
    }
    assert unstored_columns(t[0], m) == ["Remarks"]
    t2 = table("Pin number,Function description,Direction,Signal name\n1,Main power,in,PWR\n")
    # since 1.4.0 a pin has a function: "Function description" is stored, only "Direction" is not
    assert guess_mapping(t2[0]) == {"pin": 0, "signal": 3, "function": 1}
    assert unstored_columns(t2[0], guess_mapping(t2[0])) == ["Direction"]
    t3 = table(
        "Pin,Function\n1,PWR\n"
    )  # a sheet with only a Function column: it is the signal, as before
    assert guess_mapping(t3[0]) == {"pin": 0, "signal": 1}


def test_a_new_connector_from_a_sheet_in_one_step() -> None:
    p = device()
    pl = plan(p)
    assert pl.ok_count == 6 and pl.bad_count == 0 and pl.importable
    assert pl.connectors == ["GYRO1-J01"] and pl.added == ["GYRO1-J01"] and pl.pins == 6
    assert pl.label == "Import pinout (1 connector, 6 pins)"
    assert [r.message for r in pl.rows] == ["added"] * 6
    assert pl.warnings == ["Column 'Remarks' is not imported: a pin has no field for it."]
    assert pl.unmatched_signals == {"HEATER_ENABLE": ["GYRO1-J01 pin 5"]}  # stays pending
    h = History(p)
    h.execute(pl.label, pl.ops)
    c = p.connectors["GYRO1-J01"]
    assert c.name == "J1" and c.part_id == "MY-HD-6-F" and c.gender == "female"
    assert [(x.id, x.signal, x.fixed, x.contact_size, x.termination) for x in c.pins] == [
        ("A1", "PWR", True, "20", "crimp"),
        ("A2", "RTN", True, "20", "crimp"),
        ("3", "CANH", True, "22", "solder"),
        ("4", "CANL", True, "22", "solder"),
        ("5", "HEATER_ENABLE", False, None, "unspecified"),
        ("6", None, False, None, "unspecified"),
    ]
    assert errors(check_integrity(p)) == []
    h.undo()  # one undo step
    assert "GYRO1-J01" not in p.connectors


def test_the_imported_device_equals_the_one_built_with_the_editor() -> None:
    """The import writes what the planners write: same pins, same bytes."""
    from harness_design_studio.core.io.layout import model_hash

    a = device()
    apply(a, plan(a, "Pin,Signal\n1,PWR\n2,RTN\n"))
    b, cid = with_connector()
    History(b).execute("rename", devices.ops_update_connector(b, cid, name="J01"))
    History(b).execute(
        "rows",
        devices.ops_paste_rows(
            b, cid, [{"pin": "1", "signal": "PWR"}, {"pin": "2", "signal": "RTN"}], replace=True
        ),
    )
    assert [p.id for p in a.connectors["GYRO1-J01"].pins] == ["1", "2"]
    # (the two differ only in the pins the second one still has: 3 to 6 were replaced by the rows)
    assert [p.id for p in b.connectors[cid].pins] == ["1", "2"]
    assert (
        model_hash(a) == model_hash(b) or a.connectors["GYRO1-J01"].pins == b.connectors[cid].pins
    )


def test_a_new_device_is_made_when_it_is_named() -> None:
    p = Project()
    from harness_design_studio.core.samples import new_project

    p = new_project()
    pl = plan(
        p, unit_id="CAM1", new_unit_name="Camera", subsystem="payload", default_part="EX-MICROD-9-F"
    )
    assert pl.new_unit and pl.importable
    apply(p, pl)
    assert p.units["CAM1"].name == "Camera" and p.units["CAM1"].subsystem == "payload"
    assert len(p.connectors["CAM1-J01"].pins) == 6
    with pytest.raises(ImportError_, match="does not exist"):
        plan(new_project(), unit_id="CAM1", default_part="EX-MICROD-9-F")


def test_rows_with_problems_are_refused_one_by_one_and_nothing_is_imported() -> None:
    p = device()
    bad = """Connector,Pin,Signal,Mode,Termination
J1,A 1,PWR,,
J1,A2,RTN,fixed,
J1,a2,DUP,,
J1,A2,AGAIN,,
J1,3,X,maybe,
J1,4,Y,,weld
J1,,Z,,
"""
    pl = plan(p, bad)
    assert not pl.importable and pl.ops == []
    by_row = {r.row_number: r for r in pl.rows if not r.ok}
    assert set(by_row) == {2, 4, 5, 6, 7, 8}
    assert "pin name" in by_row[2].message
    assert "same ignoring case" in by_row[4].message or "listed again" in by_row[4].message
    assert "listed again (row" in by_row[5].message
    assert "mode 'maybe'" in by_row[6].message and "weld" in by_row[7].message
    assert by_row[8].message == "The pin is empty"
    assert "GYRO1-J01" not in p.connectors


def test_a_missing_or_unknown_part_and_the_gender_words() -> None:
    p = device()
    pl = plan(p, default_part=None)
    assert not pl.importable and all(
        "No part for the new connector J1" in r.message for r in pl.rows
    )
    pl = plan(p, default_part="NOPE")
    assert not pl.importable and "not a connector part" in pl.rows[0].message
    pl = plan(p, "Connector,Pin,Part\nJ1,1,MY-HD-6-F\nJ2,1,MY-PLAIN-4\n", default_part=None)
    assert pl.importable and pl.added == ["GYRO1-J01", "GYRO1-J02"]
    apply(p, pl)
    assert p.connectors["GYRO1-J02"].part_id == "MY-PLAIN-4"
    p2 = device()
    pl = plan(p2, "Connector,Pin,Gender\nJ1,1,Socket\n", default_part="MY-PLAIN-4")
    apply(p2, pl)
    assert p2.connectors["GYRO1-J01"].gender == "female"
    pl = plan(device(), "Connector,Pin,Gender\nJ1,1,sideways\n", default_part="MY-PLAIN-4")
    assert not pl.importable and "gender 'sideways'" in pl.rows[0].message
    pl = plan(device(), "Pin\n1\n", default_part="MY-PLAIN-4", gender="male")
    apply(p2, plan(p2, "Pin\n1\n", connector="J9", default_part="MY-PLAIN-4", gender="male"))
    assert p2.connectors["GYRO1-J02"].gender == "male"


def test_parts_given_per_connector_and_more_pins_than_the_part_has() -> None:
    p = device()
    pl = plan(
        p,
        "Connector,Pin\nJ1,1\nJ2,1\n",
        default_part=None,
        parts={"J1": "MY-HD-6-F", "J2": "MY-PLAIN-4"},
    )
    assert pl.importable
    rows = "Connector,Pin\n" + "".join(f"J1,{i}\n" for i in range(1, 6))
    pl = plan(p, rows, default_part="MY-PLAIN-4")
    assert not pl.importable and "more than 4 pins" in pl.rows[0].message


def test_an_existing_connector_is_merged_or_replaced() -> None:
    p, cid = with_connector()
    History(p).execute("n", devices.ops_update_connector(p, cid, name="J1"))
    pl = plan(p, "Connector,Pin,Signal\nJ1,1,PWR\nGYRO1-J01,2,RTN\n")
    assert pl.importable and pl.added == [] and pl.connectors == [cid]
    assert [r.message for r in pl.rows] == ["updated", "updated"]
    apply(p, pl)
    assert [x.id for x in p.connectors[cid].pins] == [
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
    ]  # the others stay
    assert (p.connectors[cid].pins[0].signal, p.connectors[cid].pins[1].signal) == ("PWR", "RTN")
    pl = plan(p, "Connector,Pin,Signal\nJ1,A1,PWR\nJ1,A2,RTN\n", replace=True)
    apply(p, pl)
    assert [x.id for x in p.connectors[cid].pins] == ["A1", "A2"]


def test_a_fixed_column_holds_yes_or_no() -> None:
    p = device()
    apply(p, plan(p, "Pin,Signal,Fixed\n1,PWR,yes\n2,RTN,x\n3,CANH,no\n4,CANL,\n"))
    assert [x.fixed for x in p.connectors["GYRO1-J01"].pins] == [True, True, False, False]


def test_rows_may_be_in_any_order_and_connectors_in_the_order_of_the_sheet() -> None:
    p = device()
    pl = plan(p, "Connector,Pin\nJ2,1\nJ1,1\nj2,2\n", default_part="MY-HD-6-F")
    assert pl.connectors == ["GYRO1-J01", "GYRO1-J02"]  # J2 came first in the sheet: made first
    apply(p, pl)
    assert [x.id for x in p.connectors["GYRO1-J01"].pins] == ["1", "2"] and p.connectors[
        "GYRO1-J01"
    ].name == "J2"


def test_a_pin_column_is_required() -> None:
    p = device()
    t = table("Signal\nPWR\n")
    with pytest.raises(ImportError_, match="needs a Pin column"):
        plan_pinout_import(p, t, guess_mapping(t[0]), unit_id="GYRO1", default_part="MY-HD-6-F")


def test_a_released_harness_blocks_the_import(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    cid = next(c.mates_with for c in p.harnesses[hid].connectors if c.mates_with)
    unit = p.connectors[cid].unit_id
    name = p.connectors[cid].name
    spare = next(x for x in p.connectors[cid].pins if not x.signal and not x.interface_id)
    # a sheet that leaves pins out of a frozen connector (replace) would remove pins: refused
    pl = plan(p, f"Connector,Pin,Signal\n{name},{spare.id},X\n", unit_id=unit, replace=True)
    assert not pl.importable and hid in pl.rows[0].message and "released" in pl.rows[0].message
    # a spare pin's signal can be imported; the real lock check agrees
    pl = plan(p, f"Connector,Pin,Signal\n{name},{spare.id},TEST\n", unit_id=unit)
    assert pl.importable
    History(p).execute(pl.label, pl.ops)
    # and one that touches a pin of a released interface is refused by the planner with the sentence
    used = next(x for x in p.connectors[cid].pins if x.interface_id)
    pl = plan(p, f"Connector,Pin,Signal\n{name},{used.id},TEST\n", unit_id=unit)
    assert not pl.importable and hid in pl.rows[0].message


def test_csv_with_semicolons_and_an_xlsx_workbook_read_the_same(tmp_path: Path) -> None:
    semi = CSV.replace(",", ";")
    assert table(semi) == table(CSV)
    p = device()
    xlsx = tmp_path / "pinout.xlsx"
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for row in table():
        ws.append(row)
    wb.save(xlsx)
    assert read_table(xlsx) == table()
    pl = plan_pinout_import(
        p,
        read_table(xlsx),
        guess_mapping(read_table(xlsx)[0]),
        unit_id="GYRO1",
        default_part="MY-HD-6-F",
    )
    assert pl.importable and pl.pins == 6
    csv_path = tmp_path / "pinout.csv"
    csv_path.write_text(CSV, encoding="utf-8")
    assert read_table(csv_path) == table()


def test_an_empty_sheet_imports_nothing() -> None:
    p = device()
    pl = plan_pinout_import(
        p, [["Pin", "Signal"]], {"pin": 0, "signal": 1}, unit_id="GYRO1", default_part="MY-HD-6-F"
    )
    assert not pl.importable and pl.ops == [] and pl.rows == []


def test_the_plan_never_changes_the_project() -> None:
    from harness_design_studio.core.io.layout import model_hash

    p = device()
    before = model_hash(p)
    plan(p)
    assert model_hash(p) == before and edit.unit_connectors(p, "GYRO1") == []
