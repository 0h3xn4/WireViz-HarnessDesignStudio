# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""REQ-LIB-05. 1.8.1 trust fixes of the library (audit A-4, A-5, A-6, A-7, A-26): the contact
parts travel with a device, a renamed device can be saved and added again, one malformed file
never hides the good ones, and saving never replaces a different device (or lowers the approval
of a part) without being told to."""

import json
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import device_library as dl
from harness_design_studio.core import devices as D
from harness_design_studio.core import edit as E
from harness_design_studio.core import subsystem_library as sl
from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.library_folder import (
    LibraryConflict,
    LibraryEntry,
    describe_entry,
    load_entry,
    save_devices,
    scan_folder,
)
from harness_design_studio.core.links import plan_add_link
from harness_design_studio.core.model import Part, Pin
from tests.helpers import pinout_project


def with_contact_part():
    p = pinout_project()
    p.parts["CT-22"] = Part(id="CT-22", category="contact", approval="approved")
    c = p.connectors["OBC-J01"]
    first = c.pins[0].model_copy(update={"contact_part": "CT-22"})
    p.connectors["OBC-J01"] = c.model_copy(update={"pins": [first, *c.pins[1:]]})
    return p


# ---- A-4: contact parts ----------------------------------------------------------------------


def test_a_device_with_a_contact_part_can_be_added_from_the_library():
    data = dl.export_devices(with_contact_part(), ["OBC"])
    assert "CT-22" in [x["id"] for x in data["parts"]]
    q = pinout_project()
    plan = dl.plan_device_import(q, data)
    assert plan.ok_count == 1
    History(q).execute("add", plan.ops)  # (used to raise TransactionError)
    assert q.parts["CT-22"].category == "contact"
    new_id = plan.rows[0].new_id
    pins = [p for c in q.connectors.values() if c.unit_id == new_id for p in c.pins]
    assert [p.contact_part for p in pins].count("CT-22") == 1


def test_a_contact_part_the_project_has_is_never_replaced_and_the_difference_is_noted():
    data = dl.export_devices(with_contact_part(), ["OBC"])
    q = pinout_project()
    q.parts["CT-22"] = Part(id="CT-22", category="contact", approval="not_approved")
    plan = dl.plan_device_import(q, data)
    assert [o for o in plan.ops if getattr(o, "collection", "") == "parts"] == []
    assert any("CT-22" in n and "project's is kept" in n for n in plan.notes)
    History(q).execute("add", plan.ops)
    assert q.parts["CT-22"].approval == "not_approved"


def test_a_contact_part_missing_from_the_file_is_left_off_the_pin_with_a_note():
    data = dl.export_devices(with_contact_part(), ["OBC"])
    data["parts"] = [x for x in data["parts"] if x["id"] != "CT-22"]
    q = pinout_project()
    plan = dl.plan_device_import(q, data)
    assert plan.ok_count == 1 and any("CT-22" in n and "without it" in n for n in plan.notes)
    History(q).execute("add", plan.ops)  # consistent: no pin names a part that is not there


def test_a_subsystem_with_a_contact_part_can_be_added():
    p = with_contact_part()
    apply_ops(p, plan_add_link(p, "OBC-J01", "RW1-J02")[0])
    data = sl.export_subsystem(p, ["OBC", "RW1"], "Wheel drive")
    q = pinout_project()
    plan = sl.plan_subsystem_import(q, data)
    assert plan.ok, plan.problem
    History(q).execute("add", plan.ops)
    assert "CT-22" in q.parts


# ---- A-5: connector IDs ----------------------------------------------------------------------


def test_a_renamed_device_with_a_connector_named_in_words_can_be_added_again():
    p = pinout_project()
    part_id = p.connectors["OBC-J01"].part_id
    apply_ops(p, D.ops_add_connector(p, "OBC", part_id=part_id, name="Main data port")[0])
    apply_ops(p, E.ops_rename_unit(p, "OBC", "OBC9"))
    assert any(c.id.startswith("OBC-") for c in p.connectors.values() if c.unit_id == "OBC9")
    data = dl.export_devices(p, ["OBC9"])
    q = pinout_project()
    plan = dl.plan_device_import(q, data)
    assert plan.ok_count == 1, plan.rows[0].message
    History(q).execute("add", plan.ops)
    ids = sorted(plan.rows[0].connector_ids.values())
    assert ids and all(i.startswith("OBC9-") and " " not in i for i in ids)


def test_a_connector_id_that_is_not_prefixed_by_the_device_id_keeps_its_tail():
    p = pinout_project()
    c = p.connectors.pop("OBC-J01")
    p.connectors["J1"] = c.model_copy(update={"id": "J1", "name": "Main data port"})
    plan = dl.plan_device_import(pinout_project(), dl.export_devices(p, ["OBC"]))
    assert plan.ok_count == 1
    assert plan.rows[0].connector_ids["J1"] == "OBC-2-J1"


def test_two_connectors_with_the_same_tail_are_numbered_not_refused():
    p = pinout_project()
    p.connectors["X-J01"] = p.connectors["OBC-J02"].model_copy(update={"id": "X-J01"})
    data = dl.export_devices(p, ["OBC"])
    plan = dl.plan_device_import(pinout_project(), data)
    assert plan.ok_count == 1
    assert len(set(plan.rows[0].connector_ids.values())) == len(plan.rows[0].connector_ids)


def test_a_device_id_too_long_for_its_connector_ids_says_so_in_words():
    p = pinout_project()
    long_id = "U" * 63
    p.units[long_id] = p.units["OBC"].model_copy(update={"id": long_id})
    cid = "U" * 40 + "-J1"
    p.connectors[cid] = p.connectors["OBC-J02"].model_copy(update={"id": cid, "unit_id": long_id})
    plan = dl.plan_device_import(pinout_project(), dl.export_devices(p, [long_id]))
    msg = plan.rows[0].message
    assert not plan.rows[0].ok and "too long" in msg and "64" in msg
    assert "cannot be used or is taken" not in msg


# ---- A-6 / A-26: one bad file never hides the good ones ----------------------------------------

DEVICE = {"unit": {"id": "X", "name": "X", "subsystem": "s"}, "connectors": []}
SHAPES = {
    "connectors-int": {"format": dl.FORMAT, "version": 1, "devices": [{**DEVICE, "connectors": 5}]},
    "unit-string": {
        "format": dl.FORMAT,
        "version": 1,
        "devices": [{"unit": "X", "connectors": []}],
    },
    "unit-list": {
        "format": dl.FORMAT,
        "version": 1,
        "devices": [{"unit": ["X"], "connectors": []}],
    },
    "device-string": {"format": dl.FORMAT, "version": 1, "devices": ["X"]},
    "pins-int": {
        "format": dl.FORMAT,
        "version": 1,
        "devices": [{**DEVICE, "connectors": [{"id": "X-J1", "pins": 3}]}],
    },
    "pins-null": {
        "format": dl.FORMAT,
        "version": 1,
        "devices": [{**DEVICE, "connectors": [{"id": "X-J1", "pins": None}]}],
    },
    "sub-connectors-null": {
        "format": sl.FORMAT,
        "version": 1,
        "name": "n",
        "devices": [{**DEVICE, "connectors": None}],
    },
    "sub-unit-string": {
        "format": sl.FORMAT,
        "version": 1,
        "name": "n",
        "devices": [{"unit": "X", "connectors": []}],
    },
    "sub-device-string": {"format": sl.FORMAT, "version": 1, "name": "n", "devices": ["X"]},
    "sub-pairs-int": {
        "format": sl.FORMAT,
        "version": 1,
        "name": "n",
        "devices": [DEVICE],
        "connections": [{"id": "L1", "pairs": 4}],
    },
    "sub-name-list": {"format": sl.FORMAT, "version": 1, "name": ["n"], "devices": [DEVICE]},
    "top-list": [1, 2],
    "format-list": {"format": [dl.FORMAT]},
    "version-text": {"format": dl.FORMAT, "version": "1"},
    "devices-dict": {"format": dl.FORMAT, "version": 1, "devices": {}},
}
PYTHON_WORDS = ("Error", "Exception", "Traceback", "TypeError", "AttributeError", "NoneType")


NOT_LIBRARY_FILES = ("top-list", "format-list")  # other JSON: skipped, not damaged


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_a_file_of_a_wrong_shape_is_a_problem_in_words_never_a_crash(name, tmp_path: Path):
    save_devices(tmp_path, pinout_project(), ["OBC"])
    (tmp_path / "bad.json").write_text(json.dumps(SHAPES[name]))
    scan = scan_folder(tmp_path)  # never raises
    assert [e.id for e in scan.entries if e.kind == "device"] == ["OBC"]
    if name in NOT_LIBRARY_FILES:
        assert scan.skipped == 1 and not scan.problems
    else:
        assert [q.file for q in scan.problems] == ["bad.json"], scan.problems
        assert not any(w in scan.problems[0].message for w in PYTHON_WORDS)
    data = SHAPES[name]
    if isinstance(data, dict):  # the readers of loaded data do not raise either
        dl.device_names(data)
        dl.merge_library(None, {"devices": data.get("devices", [])})
        for kind in ("device", "subsystem"):
            entry = LibraryEntry(kind, "k", "X", "n", "", "bad.json")
            describe_entry(data, entry)


def test_a_folder_with_one_bad_and_two_good_files_lists_the_two_good_ones(tmp_path: Path):
    p = pinout_project()
    save_devices(tmp_path, p, ["OBC"])
    save_devices(tmp_path, p, ["RW1"])
    (tmp_path / "bad.json").write_text(json.dumps(SHAPES["connectors-int"]))
    scan = scan_folder(tmp_path)
    assert sorted(e.id for e in scan.entries) == ["OBC", "RW1"]
    assert [q.file for q in scan.problems] == ["bad.json"]


def test_a_bad_device_in_a_file_is_one_problem_and_its_neighbours_are_listed(tmp_path: Path):
    p = pinout_project()
    data = dl.export_devices(p, ["OBC", "RW1"])
    data["devices"][0]["connectors"] = 5
    (tmp_path / "devices.json").write_text(json.dumps(data))
    scan = scan_folder(tmp_path)
    assert [e.id for e in scan.entries] == ["RW1"]
    assert len(scan.problems) == 1 and "OBC" in scan.problems[0].message


def test_merge_and_names_survive_records_of_the_wrong_shape():
    assert dl.device_names({"devices": [{"unit": "x"}, {"unit": ["y"]}, {}]}) == [("", "")] * 3
    existing = {"format": dl.FORMAT, "version": 1, "devices": [{"unit": {"id": "A"}}]}
    merged = dl.merge_library(existing, {"devices": [{"unit": "x"}, "y"]})
    assert len(merged["devices"]) == 2  # (no AttributeError)


def test_the_messages_about_damaged_files_use_no_python_names(tmp_path: Path):
    (tmp_path / "binary.json").write_bytes(b"\xff\xfe\x00\x01")
    (tmp_path / "deep.json").write_text("[" * 100000)
    (tmp_path / "cut.json").write_text('{"format": ')
    (tmp_path / "twice.json").write_text('{"format": "x", "format": "y"}')
    scan = scan_folder(tmp_path)
    said = {q.file: q.message for q in scan.problems}
    assert set(said) == {"binary.json", "deep.json", "cut.json", "twice.json"}
    for text in said.values():
        assert not any(w in text for w in ("UnicodeDecodeError", "RecursionError", "JSONDecode"))
    assert "UTF-8" in said["binary.json"] and "too deeply" in said["deep.json"]
    assert "line 1" in said["cut.json"] and "'format' twice" in said["twice.json"]


def test_a_library_file_with_a_key_twice_is_refused_with_words(tmp_path: Path):
    f = tmp_path / "d.json"
    f.write_text('{"format": "harness-device-library", "version": 1, "version": 2}')
    with pytest.raises(dl.DeviceLibraryError, match="'version' twice"):
        dl.read_library(f)
    s = tmp_path / "s.json"
    s.write_text('{"format": "harness-subsystem-library", "name": "a", "name": "b"}')
    with pytest.raises(sl.SubsystemError, match="'name' twice"):
        sl.read_subsystem(s)


# ---- A-7 / D4: saving never replaces a different device silently ---------------------------------


def changed_obc():
    """OBC as another project has it: pin 1 has another signal, one more pin function."""
    p = pinout_project()
    c = p.connectors["OBC-J01"]
    pin = c.pins[0].model_copy(update={"signal": "OTHER"})
    p.connectors["OBC-J01"] = c.model_copy(update={"pins": [pin, *c.pins[1:]]})
    return p


def test_saving_a_different_device_with_the_same_id_is_refused(tmp_path: Path):
    save_devices(tmp_path, pinout_project(), ["OBC"])
    before = (tmp_path / "OBC.json").read_bytes()
    with pytest.raises(LibraryConflict) as err:
        save_devices(tmp_path, changed_obc(), ["OBC"])
    assert (tmp_path / "OBC.json").read_bytes() == before  # nothing was written
    (conflict,) = err.value.conflicts
    assert (conflict.unit_id, conflict.pins, conflict.suggested_id) == ("OBC", 1, "OBC-2")
    assert "OBC.json" in str(err.value) and "1 pin" in str(err.value)
    assert "Python" not in str(err.value)


def test_saving_the_same_device_again_is_not_a_conflict(tmp_path: Path):
    p = pinout_project()
    save_devices(tmp_path, p, ["OBC"])
    before = (tmp_path / "OBC.json").read_bytes()
    save_devices(tmp_path, p, ["OBC"])
    assert (tmp_path / "OBC.json").read_bytes() == before


def test_replace_replaces(tmp_path: Path):
    save_devices(tmp_path, pinout_project(), ["OBC"])
    save_devices(tmp_path, changed_obc(), ["OBC"], replace=True)
    pins = dl.read_library(tmp_path / "OBC.json")["devices"][0]["connectors"][0]["pins"]
    assert pins[0]["signal"] == "OTHER"


def test_save_under_a_new_id_keeps_the_old_device_and_adds_the_new_one(tmp_path: Path):
    save_devices(tmp_path, pinout_project(), ["OBC"])
    p = changed_obc()
    with pytest.raises(LibraryConflict) as err:
        save_devices(tmp_path, p, ["OBC"])
    new = err.value.conflicts[0].suggested_id
    save_devices(tmp_path, p, ["OBC"], new_ids={"OBC": new})
    data = dl.read_library(tmp_path / "OBC.json")
    assert [d["unit"]["id"] for d in data["devices"]] == ["OBC", "OBC-2"]
    old, added = data["devices"]
    assert old["connectors"][0]["pins"][0].get("signal") != "OTHER"
    assert added["connectors"][0]["pins"][0]["signal"] == "OTHER"
    assert all(
        c["id"].startswith("OBC-2-") and c["unit_id"] == "OBC-2" for c in added["connectors"]
    )
    q = pinout_project()  # and the new one can be added to a project
    plan = dl.plan_device_import(q, data, ["OBC-2"])
    assert plan.ok_count == 1
    History(q).execute("add", plan.ops)
    # the project that saved it was not touched
    assert "OBC-2" not in p.units


def test_a_part_never_gets_a_lower_approval_in_the_file(tmp_path: Path):
    p1 = pinout_project()
    part_id = p1.connectors["OBC-J01"].part_id
    p1.parts[part_id] = p1.parts[part_id].model_copy(update={"approval": "approved"})
    save_devices(tmp_path, p1, ["OBC"])
    p2 = changed_obc()
    p2.parts[part_id] = p2.parts[part_id].model_copy(update={"approval": "not_approved"})
    notes: list[str] = []
    save_devices(tmp_path, p2, ["OBC"], replace=True, notes=notes)
    parts = {x["id"]: x for x in dl.read_library(tmp_path / "OBC.json")["parts"]}
    assert parts[part_id]["approval"] == "approved"
    assert any(part_id in n and "approved" in n and "kept" in n for n in notes)


def test_a_part_that_is_raised_is_taken_and_a_part_that_differs_is_kept_without_replace(tmp_path):
    p1 = pinout_project()
    part_id = p1.connectors["OBC-J01"].part_id
    save_devices(tmp_path, p1, ["OBC"])
    p2 = pinout_project()  # the same device, but another project's idea of the part
    p2.parts[part_id] = p2.parts[part_id].model_copy(update={"notes": "other"})
    notes: list[str] = []
    save_devices(tmp_path, p2, ["OBC"], notes=notes)
    parts = {x["id"]: x for x in dl.read_library(tmp_path / "OBC.json")["parts"]}
    assert parts[part_id].get("notes", "") != "other" and any("file's is kept" in n for n in notes)


def test_several_devices_in_conflict_are_all_named(tmp_path: Path):
    p = changed_obc()
    save_devices(tmp_path, pinout_project(), ["OBC", "RW1"])
    c = p.connectors["RW1-J02"]
    p.connectors["RW1-J02"] = c.model_copy(update={"pins": [Pin(id="1", signal="ZZ"), *c.pins[1:]]})
    with pytest.raises(LibraryConflict) as err:
        save_devices(tmp_path, p, ["OBC", "RW1"])
    assert [c.unit_id for c in err.value.conflicts] == ["OBC", "RW1"]
    assert "these devices" in str(err.value)


def test_a_device_in_a_file_written_by_the_same_tool_compares_equal_after_a_round_trip(tmp_path):
    p = with_contact_part()
    save_devices(tmp_path, p, ["OBC"])
    save_devices(tmp_path, p, ["OBC"])  # does not raise


def test_load_entry_and_describe_still_work_for_a_saved_device(tmp_path: Path):
    save_devices(tmp_path, pinout_project(), ["OBC"])
    entry = scan_folder(tmp_path).entries[0]
    assert describe_entry(load_entry(tmp_path, entry), entry)


# ---- the command line ----------------------------------------------------------------------------


def test_export_devices_refuses_to_replace_a_different_device_unless_told(tmp_path: Path, capsys):
    one, two = tmp_path / "one", tmp_path / "two"
    save_project(pinout_project(), one)
    save_project(changed_obc(), two)
    lib = tmp_path / "lib.json"
    assert cli_main(["export-devices", str(one), str(lib), "--unit", "OBC"]) == 0
    before = lib.read_bytes()
    capsys.readouterr()
    assert cli_main(["export-devices", str(two), str(lib), "--unit", "OBC"]) == 2
    err = capsys.readouterr().err
    assert lib.read_bytes() == before
    assert "lib.json" in err and "OBC" in err and "1 pin" in err and "--replace" in err
    assert cli_main(["export-devices", str(two), str(lib), "--unit", "OBC", "--replace"]) == 0
    assert dl.read_library(lib)["devices"][0]["connectors"][0]["pins"][0]["signal"] == "OTHER"
    assert cli_main(["export-devices", str(two), str(lib), "--unit", "OBC"]) == 0  # the same again
