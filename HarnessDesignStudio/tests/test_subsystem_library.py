# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""REQ-LIB-05, REQ-EDIT-03. M4 of the workshop feedback: the subsystem library file, the library
folder and the number of devices. No Qt: export, read, plan, never overwrite, one undo step, the
damaged file named in words, files byte-identical while nothing of it is used."""

import json
import os
import sys
from pathlib import Path

import pytest

from harness_design_studio.core import device_library as dl
from harness_design_studio.core import subsystem_library as sl
from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.copies import (
    copy_ids,
    device_count,
    is_copy,
    plan_copies,
)
from harness_design_studio.core.edit import EditError, ops_add_unit
from harness_design_studio.core.io.layout import model_hash, serialize
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.library_folder import (
    LibraryError,
    describe_entry,
    load_entry,
    save_devices,
    save_subsystem,
    scan_folder,
)
from harness_design_studio.core.links import plan_add_link
from harness_design_studio.core.model import evolve
from harness_design_studio.core.samples import mini3
from harness_design_studio.core.starter import starter_interface_types, starter_parts
from harness_design_studio.core.templates import create_project
from tests.helpers import pinout_project

RS = ("OBC-J01", "RW1-J02")


@pytest.fixture
def project():
    """mini3 with labelled pins and one connection OBC-J01 - RW1-J02 (L1) and the power link
    PCDU-J02 - OBC-J02 (L2)."""
    p = pinout_project()
    for a, b in (RS, ("PCDU-J02", "OBC-J02")):
        ops, _ = plan_add_link(p, a, b)
        apply_ops(p, ops)
    return p


def blank_project(tmp_path: Path):
    create_project(tmp_path / "blank", "blank")
    return load_project(tmp_path / "blank").project


def test_a_blank_project_has_no_subsystems(tmp_path: Path):
    """Workshop point 17: subsystems live in the library, not in a blank project."""
    from harness_design_studio.core.templates import TEMPLATES

    p = blank_project(tmp_path)
    assert not p.units and not p.links and not p.connectors
    assert {u.subsystem for u in p.units.values()} == set()
    assert any(t.name == "blank" for t in TEMPLATES)
    assert not (tmp_path / "blank" / "logical" / "units").exists()
    assert not (tmp_path / "blank" / "logical" / "links.json").exists()


# ---- the file --------------------------------------------------------------------------------


def test_export_keeps_the_connections_between_the_devices_only(project):
    data = sl.export_subsystem(project, ["OBC", "RW1"], "Wheel drive", "OBC and a wheel")
    assert data["format"] == sl.FORMAT and data["version"] == sl.VERSION
    assert [d["unit"]["id"] for d in data["devices"]] == ["OBC", "RW1"]
    assert [c["id"] for c in data["connections"]] == ["L1"]  # L2 leaves for PCDU
    assert sl.left_out_connections(project, ["OBC", "RW1"]) == 1
    assert sl.connections_between(project, ["OBC", "RW1"]) == 1
    assert data["parts"] and data["name"] == "Wheel drive"
    wanted = sum(1 for c in project.connectors.values() if c.unit_id in ("OBC", "RW1"))
    assert sl.subsystem_summary(data) == (2, wanted, 1)


def test_a_harness_made_from_a_connection_is_not_part_of_the_file(project):
    link = project.links["L1"]
    project.links["L1"] = evolve(link, harness_id="W1")
    data = sl.export_subsystem(project, ["OBC", "RW1"], "Wheel drive")
    assert "harness_id" not in data["connections"][0]


def test_write_read_round_trip_is_stable(project, tmp_path: Path):
    data = sl.export_subsystem(project, ["OBC", "RW1"], "Wheel drive", "d", "n")
    path = tmp_path / sl.default_file_name("Wheel drive")
    assert path.name == "subsystem-wheel-drive.json"
    sl.write_subsystem(path, data)
    first = path.read_bytes()
    assert sl.read_subsystem(path) == data
    sl.write_subsystem(path, sl.read_subsystem(path))
    assert path.read_bytes() == first and first.endswith(b"\n")


def test_nothing_to_export_and_unknown_devices(project):
    with pytest.raises(sl.SubsystemError, match="needs a name"):
        sl.export_subsystem(project, ["OBC"], "  ")
    with pytest.raises(dl.DeviceLibraryError, match="at least one"):
        sl.export_subsystem(project, [], "x")
    with pytest.raises(dl.DeviceLibraryError, match="does not exist"):
        sl.export_subsystem(project, ["NOPE"], "x")


@pytest.mark.parametrize(
    ("content", "words"),
    [
        ("not json", "not valid JSON"),
        ("[]", "not a subsystem library"),
        (json.dumps({"format": dl.FORMAT, "version": 1}), "not a subsystem library"),
        (json.dumps({"format": sl.FORMAT}), "valid version"),
        (json.dumps({"format": sl.FORMAT, "version": 9, "name": "x"}), "reads version 1"),
        (json.dumps({"format": sl.FORMAT, "version": 1}), "no name"),
        (json.dumps({"format": sl.FORMAT, "version": 1, "name": "x"}), "no devices"),
        (json.dumps({"format": sl.FORMAT, "version": 1, "name": "x", "devices": 3}), "list of rec"),
    ],
)
def test_a_damaged_file_is_named_in_plain_words(tmp_path: Path, content: str, words: str):
    path = tmp_path / "s.json"
    path.write_text(content)
    with pytest.raises(sl.SubsystemError, match=words):
        sl.read_subsystem(path)


def test_a_missing_file_and_a_folder(tmp_path: Path):
    with pytest.raises(sl.SubsystemError, match="could not be read"):
        sl.read_subsystem(tmp_path / "none.json")
    with pytest.raises(sl.SubsystemError, match="not a regular file"):
        sl.read_subsystem(tmp_path)


# ---- adding a subsystem ----------------------------------------------------------------------


def subsystem(project, name="Wheel drive"):
    return sl.export_subsystem(project, ["OBC", "RW1"], name, "OBC and a wheel")


def test_import_adds_devices_and_connections_in_one_undo_step(project, tmp_path: Path):
    data = subsystem(project)
    target = blank_project(tmp_path)
    plan = sl.plan_subsystem_import(target, data)
    assert plan.ok and plan.device_count == 2 and plan.connections == 1
    hist = History(target)
    before = model_hash(target)
    hist.execute("Add a subsystem", plan.ops)
    assert set(target.units) == {"OBC", "RW1"}
    assert {u.subsystem for u in target.units.values()} == {"Wheel drive"}
    assert set(target.links) == {"L1"}
    link = target.links["L1"]
    assert (link.a_connector, link.b_connector) == RS and link.pairs
    assert set(target.placements) == {"OBC", "RW1"}
    assert target.units["OBC"].zone == target.units["RW1"].zone  # one lane
    assert all(c.part_id in target.parts for c in target.connectors.values())
    hist.undo()
    assert model_hash(target) == before and not target.units and not target.links
    hist.redo()
    assert set(target.units) == {"OBC", "RW1"}


def test_a_clash_renames_and_never_overwrites(project):
    data = subsystem(project)
    target = pinout_project()
    original = {k: v for k, v in target.units.items()}
    plan = sl.plan_subsystem_import(target, data)
    assert plan.ok
    assert plan.new_ids == {"OBC": "OBC-2", "RW1": "RW1-2"}
    assert any("OBC is taken" in n for n in plan.notes)
    apply_ops(target, plan.ops)
    assert {k: target.units[k] for k in original} == original  # untouched
    link = target.links["L1"]
    assert (link.a_connector, link.b_connector) == ("OBC-2-J01", "RW1-2-J02")
    assert target.connectors["OBC-J01"].pins == pinout_project().connectors["OBC-J01"].pins


def test_a_taken_connection_id_gets_the_next_free_one(project):
    data = subsystem(project)
    first = pinout_project()
    for _ in range(2):
        plan = sl.plan_subsystem_import(first, data)
        assert plan.ok
        apply_ops(first, plan.ops)
    assert {"L1", "L2"} <= set(first.links)
    assert any("connection L1 is added as" in n for n in plan.notes)


def test_importing_twice_into_a_blank_project_names_every_thing_once(project, tmp_path: Path):
    data = subsystem(project)
    target = blank_project(tmp_path)
    for _ in range(2):
        apply_ops(target, sl.plan_subsystem_import(target, data).ops)
    assert set(target.units) == {"OBC", "RW1", "OBC-2", "RW1-2"}
    assert len(target.links) == 2
    pins = {pn for k in target.links.values() for pr in k.pairs for pn in (pr.a_pin, pr.b_pin)}
    assert pins  # both connections have pairs of their own devices
    assert len({k.a_connector for k in target.links.values()}) == 2


def test_it_is_all_or_nothing(project, tmp_path: Path):
    data = subsystem(project)
    broken = json.loads(json.dumps(data))
    broken["connections"][0]["pairs"][0]["a_pin"] = "99"  # a pin the connector does not have
    target = blank_project(tmp_path)
    plan = sl.plan_subsystem_import(target, broken)
    assert not plan.ok and not plan.ops and "L1" in plan.problem
    assert not target.units  # nothing was added

    outside = json.loads(json.dumps(data))
    outside["connections"][0]["b_connector"] = "GHOST-J01"
    plan = sl.plan_subsystem_import(target, outside)
    assert not plan.ok and "not both connectors" in plan.problem

    bad_device = json.loads(json.dumps(data))
    bad_device["devices"][1]["connectors"][0]["role"] = "cable"
    plan = sl.plan_subsystem_import(target, bad_device)
    assert not plan.ok and "RW1" in plan.problem and not plan.ops


def test_a_read_only_project_refuses(project, tmp_path: Path):
    target = blank_project(tmp_path)
    target.read_only = True
    plan = sl.plan_subsystem_import(target, subsystem(project))
    assert not plan.ok and "read-only" in plan.problem


def test_the_connection_note_and_name_travel(project, tmp_path: Path):
    project.links["L1"] = evolve(project.links["L1"], name="RS-422 to the wheel", note="check")
    target = blank_project(tmp_path)
    apply_ops(target, sl.plan_subsystem_import(target, subsystem(project)).ops)
    assert target.links["L1"].name == "RS-422 to the wheel" and target.links["L1"].note == "check"


def test_the_files_of_a_project_do_not_change_while_the_library_is_unused(tmp_path: Path):
    p = mini3()
    save_project(p, tmp_path / "a")
    before = serialize(p)
    sl.export_subsystem(p, ["OBC", "RW1"], "x")  # only reading
    scan_folder(tmp_path)
    save_project(p, tmp_path / "b")
    assert serialize(p) == before
    assert not (tmp_path / "b" / "logical" / "links.json").exists()
    assert (tmp_path / "a" / "logical" / "units").exists()


# ---- the library folder ----------------------------------------------------------------------


def test_the_folder_lists_devices_and_subsystems(project, tmp_path: Path):
    lib = tmp_path / "lib"
    lib.mkdir()
    save_devices(lib, project, ["OBC"])
    save_devices(lib, project, ["RW1", "PCDU"])
    save_subsystem(lib, project, ["OBC", "RW1"], "Wheel drive", "OBC and a wheel")
    (lib / "package.json").write_text('{"name": "x"}')  # another JSON file: skipped
    sub = lib / "team" / "more"
    sub.mkdir(parents=True)
    save_devices(sub, project, ["OBC"])
    (lib / ".git").mkdir()
    (lib / ".git" / "x.json").write_text("{")  # hidden folders are not looked into
    scan = scan_folder(lib)
    assert not scan.error and not scan.problems and scan.skipped == 1
    kinds = [(e.kind, e.id or e.name) for e in scan.entries]
    assert kinds.count(("subsystem", "Wheel drive")) == 1
    assert [e.id for e in scan.entries if e.kind == "device"].count("OBC") == 2
    sub_e = next(e for e in scan.entries if e.kind == "subsystem")
    assert (sub_e.devices, sub_e.connections) == (
        2,
        1,
    ) and sub_e.file == "subsystem-wheel-drive.json"
    dev = next(e for e in scan.entries if e.id == "PCDU")
    assert dev.file == "devices.json" and dev.connectors == 3 and dev.pins > 0
    rows = describe_entry(load_entry(lib, dev), dev)
    assert rows and {"connector", "pin", "signal", "function"} == set(rows[0])
    rows = describe_entry(load_entry(lib, sub_e), sub_e)
    assert [r["kind"] for r in rows] == ["Device", "Device", "Connection"]


def test_a_folder_that_cannot_be_used_says_why(tmp_path: Path):
    scan = scan_folder(tmp_path / "gone")
    assert "does not exist" in scan.error and "drive" in scan.error and not scan.entries
    f = tmp_path / "file.txt"
    f.write_text("x")
    assert "is not a folder" in scan_folder(f).error
    empty = tmp_path / "empty"
    empty.mkdir()
    scan = scan_folder(empty)
    assert not scan.error and not scan.entries


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0, reason="root can read every folder"
)
def test_an_unreadable_folder_says_so(tmp_path: Path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        assert "may not" in scan_folder(locked).error
    finally:
        locked.chmod(0o700)


def test_a_damaged_file_does_not_hide_the_others(project, tmp_path: Path):
    lib = tmp_path / "lib"
    lib.mkdir()
    save_devices(lib, project, ["OBC"])
    (lib / "broken.json").write_text("{not json")
    (lib / "future.json").write_text(json.dumps({"format": sl.FORMAT, "version": 7, "name": "n"}))
    (lib / "empty-sub.json").write_text(
        json.dumps({"format": sl.FORMAT, "version": 1, "name": "n"})
    )
    scan = scan_folder(lib)
    assert [e.id for e in scan.entries] == ["OBC"]
    said = {p.file: p.message for p in scan.problems}
    assert "not valid JSON" in said["broken.json"]
    assert "reads version 1" in said["future.json"]
    assert "no devices" in said["empty-sub.json"]
    assert str(scan.problems[0]).startswith(scan.problems[0].file + ": ")


def test_scanning_writes_nothing(project, tmp_path: Path):
    lib = tmp_path / "lib"
    lib.mkdir()
    save_subsystem(lib, project, ["OBC", "RW1"], "Wheel drive")
    snapshot = {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in lib.iterdir()}
    scan_folder(lib)
    load_entry(lib, scan_folder(lib).entries[0])
    assert {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in lib.iterdir()} == snapshot


def test_symlinks_are_not_followed(project, tmp_path: Path):
    lib = tmp_path / "lib"
    lib.mkdir()
    outside = tmp_path / "outside.json"
    save_devices(tmp_path, project, ["OBC"])
    (tmp_path / "OBC.json").rename(outside)
    try:
        (lib / "link.json").symlink_to(outside)
    except OSError:
        pytest.skip("no symbolic links here")
    assert not scan_folder(lib).entries


def test_saving_needs_a_usable_folder_and_never_replaces_a_subsystem(project, tmp_path: Path):
    with pytest.raises(LibraryError, match="does not exist"):
        save_devices(tmp_path / "gone", project, ["OBC"])
    lib = tmp_path / "lib"
    lib.mkdir()
    path = save_subsystem(lib, project, ["OBC", "RW1"], "Wheel drive")
    first = path.read_bytes()
    with pytest.raises(LibraryError, match="Choose another name"):
        save_subsystem(lib, project, ["OBC"], "Wheel drive")
    assert path.read_bytes() == first
    # saving a device again replaces that device in its own file and keeps the others
    save_devices(lib, project, ["OBC", "RW1"])
    save_devices(lib, project, ["OBC", "PCDU"])
    ids = [d["unit"]["id"] for d in dl.read_library(lib / "devices.json")["devices"]]
    assert ids == ["OBC", "PCDU", "RW1"]


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0, reason="root can write everywhere"
)
def test_a_folder_that_cannot_be_written_says_so(project, tmp_path: Path):
    lib = tmp_path / "ro"
    lib.mkdir()
    lib.chmod(0o500)
    try:
        with pytest.raises(LibraryError, match="may not write"):
            save_devices(lib, project, ["OBC"])
    finally:
        lib.chmod(0o700)


def test_a_device_file_of_the_library_still_adds_as_before(project, tmp_path: Path):
    lib = tmp_path / "lib"
    lib.mkdir()
    save_devices(lib, project, ["OBC"])
    entry = scan_folder(lib).entries[0]
    plan = dl.plan_device_import(blank_project(tmp_path), load_entry(lib, entry), [entry.id])
    assert plan.ok_count == 1 and plan.rows[0].connector_ids["OBC-J01"] == "OBC-J01"


# ---- a number of the same device -------------------------------------------------------------


def with_device(tmp_path: Path):
    p = blank_project(tmp_path)
    apply_ops(p, ops_add_unit(p, "computer")[0])
    return p, "OBC1"


def test_ids_of_the_copies():
    assert copy_ids("OBC1", 1) == []
    assert copy_ids("OBC1", 2) == ["OBC1-R"]
    assert copy_ids("OBC1", 4) == ["OBC1-R", "OBC1-3", "OBC1-4"]


def test_two_devices_are_exactly_the_redundant_copy(tmp_path: Path):
    from harness_design_studio.core.edit import ops_redundant_copy

    a, uid = with_device(tmp_path)
    b, _ = with_device(tmp_path / "b")
    apply_ops(a, plan_copies(a, uid, 2).ops)
    apply_ops(b, ops_redundant_copy(b, uid).ops)
    assert serialize(a) == serialize(b)  # the same files whichever way the copy was made
    assert device_count(a, uid) == 2 and is_copy(a, "OBC1-R")


def test_more_than_two_devices(tmp_path: Path):
    p, uid = with_device(tmp_path)
    plan = plan_copies(p, uid, 4)
    assert plan.new_ids == ("OBC1-R", "OBC1-3", "OBC1-4") and plan.count == 4
    hist = History(p)
    before = model_hash(p)
    hist.execute("Make 4 of OBC1", plan.ops)
    assert device_count(p, uid) == 4
    assert {p.units[i].side for i in plan.new_ids} == {"redundant"}
    assert len({(pl.x, pl.y) for pl in p.placements.values()}) == 4  # none on top of another
    assert p.connectors["OBC1-3-J01"].unit_id == "OBC1-3"
    hist.undo()  # one step
    assert model_hash(p) == before and device_count(p, uid) == 1


def test_the_number_only_grows_and_says_so(tmp_path: Path):
    p, uid = with_device(tmp_path)
    with pytest.raises(EditError, match="already 1 of these"):
        plan_copies(p, uid, 1)
    apply_ops(p, plan_copies(p, uid, 3).ops)
    with pytest.raises(EditError, match="already 3.*delete a copy"):
        plan_copies(p, uid, 2)
    apply_ops(p, plan_copies(p, uid, 4).ops)
    assert sorted(i for i in p.units if i.startswith("OBC1")) == [
        "OBC1", "OBC1-3", "OBC1-4", "OBC1-R",
    ]  # fmt: skip
    with pytest.raises(EditError, match="between 1 and 10"):
        plan_copies(p, uid, 11)
    with pytest.raises(EditError, match="is a copy"):
        plan_copies(p, "OBC1-R", 3)
    with pytest.raises(EditError, match="does not exist"):
        plan_copies(p, "GHOST", 2)
    with pytest.raises(EditError, match="whole number"):
        plan_copies(p, uid, True)


def test_a_gap_is_filled_first(tmp_path: Path):
    from harness_design_studio.core.commands import Delete

    p, uid = with_device(tmp_path)
    apply_ops(p, plan_copies(p, uid, 4).ops)
    apply_ops(
        p, [Delete("connectors", c) for c in [k for k in p.connectors if k.startswith("OBC1-3-")]]
    )
    apply_ops(p, [Delete("placements", "OBC1-3"), Delete("units", "OBC1-3")])
    assert device_count(p, uid) == 3
    plan = plan_copies(p, uid, 4)
    assert plan.new_ids == ("OBC1-3",)


def test_links_are_mirrored_onto_the_copies_where_a_connector_is_free(tmp_path: Path):
    p = mini3()
    uid = "OBC"
    plan = plan_copies(p, uid, 2)
    apply_ops(p, plan.ops)
    assert "OBC-R" in p.units
    assert all(
        i.id.endswith("-R")
        for i in p.interfaces.values()
        if "OBC-R" in {e.unit_id for e in i.endpoints}
    )  # noqa: E501
    assert starter_parts() and starter_interface_types()
