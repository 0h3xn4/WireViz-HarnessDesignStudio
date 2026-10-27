# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""1.4.0 M5: a device library file: devices with their pinouts reused across projects (D-165)."""

from pathlib import Path

import pytest

from harness_design_studio.core import devices
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.device_library import (
    DeviceLibraryError,
    check_library,
    device_names,
    export_devices,
    merge_library,
    plan_device_import,
    read_library,
    write_library,
)
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import Project
from harness_design_studio.core.samples import sat15


@pytest.fixture
def project():
    p = sat15()
    generate_project(p)
    return p


def unit_with_pins(p):
    return next(
        u for u in sorted(p.units) if any(c.unit_id == u and c.pins for c in p.connectors.values())
    )


def test_an_export_holds_the_device_its_pinouts_parts_and_types(project):
    uid = unit_with_pins(project)
    data = export_devices(project, [uid])
    assert data["format"] == "harness-device-library" and data["version"] == 1
    assert device_names(data) == [(uid, project.units[uid].name)]
    conns = data["devices"][0]["connectors"]
    assert conns and all(c["unit_id"] == uid for c in conns)
    part_ids = {p["id"] for p in data["parts"]}
    assert {c["part_id"] for c in conns} <= part_ids
    carried = {t for c in conns for t in c.get("carries", [])}
    assert carried <= {t["id"] for t in data["interface_types"]}


def test_what_generation_allocated_does_not_travel_but_the_design_does(project):
    uid = unit_with_pins(project)
    cid = next(c.id for c in project.connectors.values() if c.unit_id == uid and c.pins)
    pid = project.connectors[cid].pins[0].id
    apply_ops(
        project,
        devices.ops_set_pin(project, cid, pid, function="Battery sense", contact_size="20"),
    )
    data = export_devices(project, [uid])
    pins = {
        p["id"]: p for c in data["devices"][0]["connectors"] if c["id"] == cid for p in c["pins"]
    }
    assert pins[pid]["function"] == "Battery sense" and pins[pid]["contact_size"] == "20"
    every = [p for c in data["devices"][0]["connectors"] for p in c["pins"]]
    assert every and all(p["interface_id"] is None and not p["locked"] for p in every)
    assert data["devices"][0]["unit"]["zone"] is None


def test_import_into_an_empty_project_gives_the_same_device(project):
    uid = unit_with_pins(project)
    data = export_devices(project, [uid])
    fresh = Project()
    plan = plan_device_import(fresh, data)
    assert [(r.ok, r.new_id) for r in plan.rows] == [(True, uid)]
    apply_ops(fresh, plan.ops)
    assert set(fresh.units) == {uid}
    got = sorted(c.id for c in fresh.connectors.values())
    want = sorted(c.id for c in project.connectors.values() if c.unit_id == uid)
    assert got == want
    for cid in got:
        a = [(p.id, p.function, p.contact_size, p.termination, p.fixed) for p in fresh.connectors[cid].pins]  # fmt: skip
        b = [(p.id, p.function, p.contact_size, p.termination, p.fixed) for p in project.connectors[cid].pins]  # fmt: skip
        assert a == b
    assert not [i for i in fresh.connectors[got[0]].pins if i.interface_id]
    # every part and type the device names is there, so the project is whole
    for c in fresh.connectors.values():
        assert c.part_id in fresh.parts
        assert set(c.carries) <= set(fresh.interface_types)


def test_a_device_that_is_already_in_the_project_is_added_under_a_free_id(project):
    uid = unit_with_pins(project)
    data = export_devices(project, [uid])
    before = set(project.units)
    plan = plan_device_import(project, data)
    assert plan.rows[0].ok and plan.rows[0].new_id == f"{uid}-2"
    assert any("is taken" in n for n in plan.notes)
    apply_ops(project, plan.ops)
    assert set(project.units) == before | {f"{uid}-2"}
    assert all(c.id.startswith(f"{uid}-2-") for c in project.connectors.values() if c.unit_id == f"{uid}-2")  # fmt: skip
    again = plan_device_import(project, data)
    assert again.rows[0].new_id == f"{uid}-3"


def test_a_part_the_project_has_is_kept_as_the_project_has_it(project):
    uid = unit_with_pins(project)
    data = export_devices(project, [uid])
    data["parts"][0]["description"] = "Changed in the file"
    fresh = Project()
    fresh.parts.update(project.parts)
    fresh.interface_types.update(project.interface_types)
    plan = plan_device_import(fresh, data)
    assert plan.rows[0].ok
    assert any("differs" in n for n in plan.notes)
    assert not [op for op in plan.ops if op.collection == "parts"]  # type: ignore[union-attr]


def test_one_bad_device_does_not_stop_the_others(project):
    ids = sorted({c.unit_id for c in project.connectors.values() if c.unit_id and c.pins})[:2]
    data = export_devices(project, ids)
    data["devices"][0]["connectors"][0]["part_id"] = "NO-SUCH-PART"
    data["parts"] = [p for p in data["parts"] if p["id"] != "NO-SUCH-PART"]
    plan = plan_device_import(Project(), data)
    assert [r.ok for r in plan.rows] == [False, True]
    assert "NO-SUCH-PART" in plan.rows[0].message
    fresh = Project()
    apply_ops(fresh, plan.ops)
    assert set(fresh.units) == {ids[1]}


def test_only_the_chosen_devices_are_added(project):
    ids = sorted({c.unit_id for c in project.connectors.values() if c.unit_id and c.pins})[:2]
    data = export_devices(project, ids)
    plan = plan_device_import(Project(), data, [ids[1], "GHOST"])
    assert [(r.unit_id, r.ok) for r in plan.rows] == [(ids[1], True), ("GHOST", False)]
    assert plan.rows[1].message == "The file has no such device."


def test_the_file_round_trips_and_merges_in_a_stable_order(project, tmp_path: Path):
    ids = sorted({c.unit_id for c in project.connectors.values() if c.unit_id and c.pins})[:2]
    first = export_devices(project, [ids[1]])
    f = tmp_path / "lib.json"
    write_library(f, first)
    both = merge_library(read_library(f), export_devices(project, [ids[0]]))
    write_library(f, both)
    assert [i for i, _ in device_names(read_library(f))] == sorted(ids)
    assert (tmp_path / "lib.json.bak").exists()
    text = f.read_text()
    write_library(f, read_library(f))
    assert f.read_text() == text  # writing what was read changes nothing
    # the same device again replaces it instead of doubling
    again = merge_library(read_library(f), export_devices(project, [ids[0]]))
    assert len(again["devices"]) == 2


@pytest.mark.parametrize(
    "bad,match",
    [
        ({}, "not a device library"),
        ({"format": "harness-device-library"}, "version"),
        ({"format": "harness-device-library", "version": 2}, "newer program"),
        ({"format": "harness-device-library", "version": 1, "devices": {}}, "list of records"),
        ({"format": "harness-device-library", "version": 1, "parts": [1]}, "list of records"),
    ],
)
def test_a_file_that_is_not_a_library_is_refused(bad, match):
    with pytest.raises(DeviceLibraryError, match=match):
        check_library(bad)


def test_unreadable_files_are_refused_in_words(tmp_path: Path):
    with pytest.raises(DeviceLibraryError, match="could not be read"):
        read_library(tmp_path / "missing.json")
    with pytest.raises(DeviceLibraryError, match="regular file"):
        read_library(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(DeviceLibraryError, match="not valid JSON"):
        read_library(bad)
    bad.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(DeviceLibraryError, match="not valid UTF-8"):
        read_library(bad)


def test_a_device_with_wrong_values_is_a_row_with_a_reason_not_a_crash(project):
    uid = unit_with_pins(project)
    data = export_devices(project, [uid])
    data["devices"][0]["unit"]["name"] = 12
    data["devices"].append({"unit": "x", "connectors": 5})
    data["devices"].append({"unit": {"id": "ZZ", "name": "Z", "subsystem": "s"}, "connectors": [1]})
    plan = plan_device_import(Project(), data)
    assert [r.ok for r in plan.rows] == [False, False, False]
    assert all(r.message for r in plan.rows)
    assert plan.ops == []


def test_a_connector_of_another_device_is_refused(project):
    ids = sorted({c.unit_id for c in project.connectors.values() if c.unit_id and c.pins})[:2]
    data = export_devices(project, ids)
    data["devices"][0]["connectors"][0]["unit_id"] = ids[1]
    plan = plan_device_import(Project(), data, [ids[0]])
    assert not plan.rows[0].ok and "not a box connector of this device" in plan.rows[0].message


def test_an_imported_device_makes_a_whole_project_that_saves_loads_and_generates(
    project, tmp_path: Path
):
    from harness_design_studio.core.commands import History
    from harness_design_studio.core.integrity import check_integrity
    from harness_design_studio.core.io.loader import load_project
    from harness_design_studio.core.io.saver import save_project
    from harness_design_studio.core.templates import create_project

    dest = tmp_path / "new"
    target = create_project(dest, "blank")
    uid = unit_with_pins(project)
    plan = plan_device_import(target, export_devices(project, [uid]))
    assert plan.rows[0].ok
    History(target).execute("Add device from a library file", plan.ops)
    save_project(target, dest)
    loaded = load_project(dest)
    assert not loaded.has_errors
    assert uid in loaded.project.units
    assert not [i for i in check_integrity(loaded.project) if i.severity == "error"]
    generate_project(
        loaded.project
    )  # a device alone has no interfaces: nothing to connect, no crash
