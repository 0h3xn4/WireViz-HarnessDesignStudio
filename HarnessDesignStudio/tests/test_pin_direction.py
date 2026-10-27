# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""REQ-IO-02, REQ-DRC-05. Release 1.9 (W3): a pin can say which way its signal runs (`Pin.direction`:
in, out, bidirectional; empty = not set). It is sparse (left out of the files while empty), a
column of the pinout tables only while some pin has one, read by the import, shown by the Devices
data model and in the JSON Schema. (That it decides the link checks: test_links_direction.py.) No Qt."""

from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import devices, schemas
from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.imports import parse_csv
from harness_design_studio.core.io.layout import serialize
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Pin
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.tables import box_pinouts, pinouts
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.pinout_import import guess_mapping, plan_pinout_import
from tests.helpers import pinout_project
from tests.test_edit_device import with_connector


def errors_of(p, files):
    return [i for i in verify_outputs(p, files).issues if i.severity == "error"]


def codes(findings):
    return sorted({f.code for f in findings})


def set_pins(p, cid, *pins):
    p.connectors[cid] = p.connectors[cid].model_copy(update={"pins": list(pins)})


def pairs_of(r):
    return [(x.a_pin, x.b_pin) for x in r.pairs]


# ---- the field ----------------------------------------------------------------------------------


def test_a_pin_has_no_direction_until_one_is_set_and_the_file_says_nothing_about_it():
    assert Pin(id="1").direction == ""
    assert "direction" not in Pin(id="1").model_dump()
    assert Pin(id="1", direction="out").model_dump()["direction"] == "out"
    with pytest.raises(ValueError):
        Pin(id="1", direction="sideways")  # type: ignore[arg-type]


def test_a_project_without_directions_is_written_as_before_and_with_one_the_field_appears():
    p = pinout_project()
    assert all(  # (the interface types name a direction for each signal; the connectors do not)
        b'"direction"' not in data
        for rel, data in serialize(p).items()
        if rel.startswith("physical/")
    )
    c = p.connectors["OBC-J01"]
    p.connectors["OBC-J01"] = c.model_copy(
        update={"pins": [c.pins[0].model_copy(update={"direction": "in"}), *c.pins[1:]]}
    )
    holding = [
        rel
        for rel, data in serialize(p).items()
        if rel.startswith("physical/") and b'"direction": "in"' in data
    ]
    assert len(holding) == 1 and holding[0].startswith("physical/connectors/")


def test_a_saved_direction_is_loaded_again(tmp_path: Path):
    p, cid = with_connector()
    apply_ops(p, devices.ops_set_pin(p, cid, "2", direction="out"))
    save_project(p, tmp_path / "p")
    q = load_project(tmp_path / "p").project
    assert [x.direction for x in q.connectors[cid].pins] == ["", "out", "", "", "", ""]


def test_the_json_schema_of_a_connector_lists_the_directions():
    pin = schemas.schemas()["connectors"]["$defs"]["Pin"]["properties"]["direction"]
    assert set(pin["enum"]) == {"", "in", "out", "bidir"} and pin["default"] == ""


# ---- setting it ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("typed", "stored"),
    [("in", "in"), ("Input", "in"), ("OUT", "out"), ("output", "out"), ("bidirectional", "bidir"),
     ("I/O", "bidir"), ("inout", "bidir"), ("", ""), (None, ""), ("Passive", ""), ("n/a", "")],
)  # fmt: skip
def test_the_words_a_person_may_type(typed, stored):
    assert devices.parse_pin_direction(typed) == stored


def test_an_unknown_direction_is_refused_with_the_words_that_work():
    with pytest.raises(EditError, match="in, out, bidirectional"):
        devices.parse_pin_direction("Power")


def test_set_and_clear_a_direction_in_one_undo_step():
    p, cid = with_connector()
    h = History(p)
    h.execute("Direction", devices.ops_set_pin(p, cid, "1", direction="Input"))
    assert p.connectors[cid].pins[0].direction == "in"
    assert devices.ops_set_pin(p, cid, "1", direction="in") == []  # nothing to do
    h.execute("Clear", devices.ops_set_pin(p, cid, "1", direction=""))
    assert p.connectors[cid].pins[0].direction == ""
    h.undo()
    assert p.connectors[cid].pins[0].direction == "in"


def test_a_pin_with_only_a_direction_is_not_empty():
    p, cid = with_connector()
    apply_ops(p, devices.ops_set_pin(p, cid, "3", direction="out"))
    assert not devices._pin_is_empty(p.connectors[cid].pins[2])


def test_the_pin_rows_of_the_devices_tab_show_the_direction_that_was_set():
    p, cid = with_connector()
    apply_ops(p, devices.ops_set_pin(p, cid, "1", signal="PWR", direction="in"))
    apply_ops(p, devices.ops_set_pin(p, cid, "2", signal="TX+"))
    rows = devices.pin_rows(p, cid)
    assert (rows[0].direction, rows[0].direction_set) == ("in", True)
    assert "set on the pin" in rows[0].note
    assert rows[1].direction_set is False and rows[1].direction in ("out", "bidir", "passive", "in")
    assert rows[2].direction == "" and rows[2].direction_set is False


def test_pasted_rows_may_carry_a_direction():
    p, cid = with_connector()
    rows = [{"pin": "1", "direction": "output"}, {"pin": "2", "direction": "bidirectional"}]
    apply_ops(p, devices.ops_paste_rows(p, cid, rows))
    assert [x.direction for x in p.connectors[cid].pins[:3]] == ["out", "bidir", ""]
    with pytest.raises(EditError, match="row 1"):
        devices.ops_paste_rows(p, cid, [{"pin": "1", "direction": "power"}])


# ---- the pinout tables --------------------------------------------------------------------------


def test_the_direction_column_exists_only_when_a_pin_has_a_direction():
    p = pinout_project()
    assert "Direction" not in box_pinouts(p)[0] and "Direction" not in pinouts(p, p.harnesses["W001"])[0]  # fmt: skip
    apply_ops(p, devices.ops_set_pin(p, "OBC-J01", "1", direction="out"))
    apply_ops(p, devices.ops_set_pin(p, "OBC-J01", "2", direction="bidir"))
    table = box_pinouts(p)
    col = table[0].index("Direction")
    assert col == len(table[0]) - 1  # the last column, after the older optional ones
    by_pin = {(r[0], r[4]): r[col] for r in table[1:]}
    assert by_pin[("OBC-J01", "1")] == "out" and by_pin[("OBC-J01", "2")] == "bidirectional"
    assert by_pin[("OBC-J01", "3")] == "" and by_pin[("RW1-J02", "1")] == ""
    assert "Direction" in pinouts(p, p.harnesses["W001"])[0]


def test_the_written_files_pass_the_verifier_with_and_without_directions():
    p = pinout_project()
    assert errors_of(p, build_outputs(p, drawings=False).files) == []
    apply_ops(p, devices.ops_set_pin(p, "OBC-J01", "4", direction="in"))
    files = build_outputs(p, drawings=False).files
    assert b"Direction" in files["system/box_pinouts.csv"]
    assert errors_of(p, files) == []


def test_the_verifier_notices_a_wrong_direction_cell():
    p = pinout_project()
    apply_ops(p, devices.ops_set_pin(p, "OBC-J01", "4", direction="in"))
    files = dict(build_outputs(p, drawings=False).files)
    assert b",in\n" in files["system/box_pinouts.csv"]
    files["system/box_pinouts.csv"] = files["system/box_pinouts.csv"].replace(b",in\n", b",out\n")
    assert any(i.code == "out_box_pinouts" for i in verify_outputs(p, files).issues)


def test_a_direction_goes_out_and_back_through_a_file(tmp_path: Path, capsys):
    p, cid = with_connector()
    apply_ops(p, devices.ops_set_pin(p, cid, "1", signal="PWR", direction="in"))
    apply_ops(p, devices.ops_set_pin(p, cid, "2", signal="RTN"))
    apply_ops(p, devices.ops_set_pin(p, cid, "3", signal="TX+", direction="bidir"))
    root = tmp_path / "p"
    save_project(p, root)
    for ending in (".csv", ".tsv", ".xlsx"):
        out = tmp_path / f"pins{ending}"
        assert cli_main(["export-pinout", str(root), "--unit", "GYRO1", "-o", str(out)]) == 0
        q = tmp_path / f"q{ending[1:]}"
        from tests.test_edit_device import device

        save_project(device(), q)
        capsys.readouterr()
        argv = ["import-pinout", str(q), str(out), "--unit", "GYRO1", "--default-part", "MY-HD-6-F"]
        assert cli_main(argv) == 0, capsys.readouterr()
        pins = load_project(q).project.connectors["GYRO1-J01"].pins
        assert [(x.id, x.direction) for x in pins][:3] == [("1", "in"), ("2", ""), ("3", "bidir")]


def test_a_sheet_with_a_direction_column_imports_it_and_a_bad_word_refuses_the_row():
    p, _cid = with_connector()
    table = parse_csv("Pin,Signal,Direction\n1,PWR,Input\n2,TX,Output\n3,X,N/A\n4,Y,\n")
    plan = plan_pinout_import(p, table, guess_mapping(table[0]), unit_id="GYRO1", connector="J01")
    assert plan.importable and plan.warnings == []
    History(p).execute(plan.label, plan.ops)
    assert [x.direction for x in p.connectors["GYRO1-J01"].pins[:4]] == ["in", "out", "", ""]
    bad = parse_csv("Pin,Signal,Direction\n1,PWR,Power\n")
    refused = plan_pinout_import(p, bad, guess_mapping(bad[0]), unit_id="GYRO1", connector="J01")
    assert not refused.importable
    assert "in, out, bidirectional" in refused.rows[0].message


def test_a_device_library_file_keeps_the_directions():
    from harness_design_studio.core.device_library import (
        check_library,
        export_devices,
        plan_device_import,
    )
    from harness_design_studio.core.model import Project

    p, cid = with_connector()
    apply_ops(p, devices.ops_set_pin(p, cid, "1", signal="PWR", direction="in"))
    data = export_devices(p, ["GYRO1"])
    check_library(data)
    pins = data["devices"][0]["connectors"][0]["pins"]
    assert pins[0]["direction"] == "in" and "direction" not in pins[1]  # sparse in the file too
    fresh = Project()
    apply_ops(fresh, plan_device_import(fresh, data).ops)
    assert [x.direction for x in fresh.connectors[cid].pins][:2] == ["in", ""]
