# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg"
"""REQ-GUI-24 (the kind of a device, set by hand). Owner decision after the device looks: *do you
want to set a device's kind by hand? yes*. A device (the model's `Unit`) has an optional field
`kind`, one of the IDs of `core/device_kinds.py`, written only when it is set. Without it the kind
is read from the name, the ID, the subsystem and the links as before; the ID `device` forces the
plain box. A project that sets no kind has the same bytes, the same model hash and the same outputs
as before; one that sets a kind has it in its model hash (it is design data a person typed)."""

import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from harness_design_studio.cli.main import main
from harness_design_studio.core import device_kinds as dk
from harness_design_studio.core import device_library, edit, journal, schemas, templates
from harness_design_studio.core.commands import History
from harness_design_studio.core.io import layout
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Unit, evolve
from harness_design_studio.core.model.logical import DeviceKind
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import mini3, sat15
from harness_design_studio.core.vcs.lockview import cosmetic_fields

# The model hashes of three projects as they were before the field existed (release 1.15.0 and the
# device looks): the field must not move them.
HASH_MINI3 = "96af3561a17d17ef46e574fccb94aa841453bf779ed9c826aa56db8c496bbde8"
HASH_SAT15 = "abb178f717365cb52205240d39494f47cb3d737d48228a9e930a12ccc0a49fe0"
HASH_FLATSAT = "05048f43a772957311b07099015a6e04d9c9511ead8276d5ba6b54e4d74dee2b"


def with_kind(project, uid: str, kind: str | None):
    project.units[uid] = evolve(project.units[uid], kind=kind)
    return project


# ---- the field -----------------------------------------------------------------------------------


def test_the_model_list_of_kinds_is_the_table_of_kinds() -> None:
    assert set(get_args(DeviceKind)) == set(dk.KIND_IDS)
    assert len(dk.KIND_IDS) == 20 and "device" in dk.KIND_IDS  # 19 kinds and the plain box
    assert [k.key for k in dk.KINDS] + ["device"] == list(dk.KIND_IDS)


def test_the_field_is_optional_and_sparse() -> None:
    u = Unit(id="A1", name="Box", subsystem="x")
    assert u.kind is None and "kind" not in u.model_dump(mode="json")
    assert "kind" not in Unit(id="A1", name="Box", subsystem="x", kind=None).model_dump(mode="json")
    k = Unit(id="A1", name="Box", subsystem="x", kind="battery")
    assert k.model_dump(mode="json")["kind"] == "battery"
    assert Unit.model_validate(k.model_dump(mode="json")) == k


@pytest.mark.parametrize("bad", ["Battery", "bat", "", "plain", "generic", 3])
def test_an_unknown_kind_is_refused_and_the_message_names_the_kinds(bad) -> None:
    with pytest.raises(ValidationError) as exc:
        Unit(id="A1", name="Box", subsystem="x", kind=bad)
    text = str(exc.value)
    assert "kind" in text and "'battery'" in text and "'reaction_wheel'" in text
    assert "'device'" in text  # the plain box is one of the allowed values


def test_a_project_file_with_an_unknown_kind_is_refused_with_the_allowed_ids(tmp_path) -> None:
    templates.create_project(tmp_path / "p", "flatsat")
    path = next((tmp_path / "p" / "logical" / "units").glob("*.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["units"][0]["kind"] = "teapot"
    path.write_text(json.dumps(data), encoding="utf-8")
    result = load_project(tmp_path / "p")
    assert result.has_errors
    bad = next(i for i in result.issues if i.code == "quarantined")  # the device is set aside
    assert bad.location == path.relative_to(tmp_path / "p").as_posix()
    assert "kind: Input should be 'computer'" in bad.message and "'device'" in bad.message
    assert all(f"'{k}'" in bad.message for k in dk.KIND_IDS)  # it says what is allowed


def test_the_edit_refuses_an_unknown_kind_naming_the_allowed_ones() -> None:
    p = mini3()
    with pytest.raises(edit.EditError) as exc:
        edit.ops_update_unit(p, "RW1", kind="teapot")
    text = str(exc.value)
    assert "'teapot' is not a kind of device" in text
    assert all(k in text for k in dk.KIND_IDS)
    with pytest.raises(edit.EditError):
        edit.ops_update_unit(p, "RW1", kind=3)


# ---- nothing changes for a project that sets no kind ----------------------------------------------


def test_a_project_without_a_kind_has_the_model_hash_it_had_before(tmp_path) -> None:
    assert layout.model_hash(mini3()) == HASH_MINI3
    assert layout.model_hash(sat15()) == HASH_SAT15
    templates.create_project(tmp_path / "f", "flatsat")
    project = load_project(tmp_path / "f").project
    # the record of the generation names the tool that generated it, and that is in the hash: give
    # it the version the pinned hash was made with, so that a new release does not move this test
    assert project.generation is not None
    project.generation = evolve(project.generation, generator_version="1.15.0")
    assert layout.model_hash(project) == HASH_FLATSAT
    assert all(u.kind is None for u in project.units.values())


def test_no_file_of_a_project_without_a_kind_names_one(tmp_path) -> None:
    templates.create_project(tmp_path / "f", "flatsat")
    project = load_project(tmp_path / "f").project
    files = layout.serialize(project)
    assert not [rel for rel, data in files.items() if b'"kind"' in data and "units" in rel]
    # an explicit None is the same bytes as the field never set
    other = load_project(tmp_path / "f").project
    other.units["RW1"] = evolve(other.units["RW1"], kind=None)
    assert layout.serialize(other) == files


def test_the_outputs_of_a_project_without_a_kind_carry_no_kind() -> None:
    files = build_outputs(mini3()).files
    doc = json.loads(files["system/export.json"])
    assert all("kind" not in u for u in doc["units"])


# ---- a project that sets one -------------------------------------------------------------------


def test_a_kind_is_saved_loaded_and_part_of_the_model_hash(tmp_path) -> None:
    templates.create_project(tmp_path / "f", "flatsat")
    project = load_project(tmp_path / "f").project
    before = layout.model_hash(project)
    with_kind(project, "BAT1", "heater")
    assert layout.model_hash(project) != before
    save_project(project, tmp_path / "f")
    again = load_project(tmp_path / "f").project
    assert again.units["BAT1"].kind == "heater"
    assert layout.model_hash(again) == layout.model_hash(project)
    unit_files = [
        json.loads(d)
        for rel, d in layout.serialize(again).items()
        if rel.startswith("logical/units/")
    ]
    kinds = {u["id"]: u["kind"] for f in unit_files for u in f["units"] if "kind" in u}
    assert kinds == {"BAT1": "heater"}  # only the device that has one writes it
    with_kind(again, "BAT1", None)  # and back: the same bytes and hash as before
    assert layout.model_hash(again) == before


def test_the_export_json_and_the_verifier_carry_the_kind(tmp_path) -> None:
    p = with_kind(mini3(), "RW1", "magnetorquer")
    files = build_outputs(p).files
    doc = json.loads(files["system/export.json"])
    assert {u["id"]: u.get("kind") for u in doc["units"]}["RW1"] == "magnetorquer"
    assert sum("kind" in u for u in doc["units"]) == 1
    report = verify_outputs(p, files)
    assert report.errors == [], [e.message for e in report.errors]


def test_a_kind_travels_in_a_device_library_file(tmp_path) -> None:
    p = with_kind(mini3(), "RW1", "magnetorquer")
    data = device_library.export_devices(p, ["RW1", "OBC"])
    units = {d["unit"]["id"]: d["unit"] for d in data["devices"]}
    assert units["RW1"]["kind"] == "magnetorquer" and "kind" not in units["OBC"]
    plan = device_library.plan_device_import(mini3(), data)
    put = {
        op.obj.id: op.obj for op in plan.ops if hasattr(op.obj, "kind") and hasattr(op.obj, "side")
    }
    assert put["RW1-2"].kind == "magnetorquer" and put["OBC-2"].kind is None


def test_a_kind_change_is_allowed_after_a_release() -> None:
    assert "kind" in cosmetic_fields(
        "unit"
    )  # like the name and the notes: it is a look, not wiring


# ---- manual and inferred --------------------------------------------------------------------------


def test_a_kind_set_by_hand_wins_over_the_name() -> None:
    p = mini3()
    auto = dk.looks_for(p, "RW1")
    assert (auto.kind.key, auto.source) == ("reaction_wheel", "name")
    hand = dk.looks_for(with_kind(p, "RW1", "battery"), "RW1")
    assert (hand.kind.key, hand.source, hand.family.key) == ("battery", "manual", "power")
    assert dk.automatic_looks(p, "RW1").kind.key == "reaction_wheel"  # what Automatic would pick
    with_kind(p, "RW1", None)
    assert dk.looks_for(p, "RW1") == auto  # back to reading it


def test_the_plain_box_can_be_forced() -> None:
    p = with_kind(mini3(), "RW1", "device")
    looks = dk.looks_for(p, "RW1")
    assert (looks.kind, looks.source, looks.generic) == (dk.GENERIC, "manual", True)
    assert looks.token == ""  # no accent, no band: the plain outlined box


def test_the_other_devices_keep_reading_their_kind() -> None:
    p = mini3()
    before = {u: dk.looks_for(p, u) for u in p.units}
    with_kind(p, "RW1", "battery")
    after = {u: dk.looks_for(p, u) for u in p.units}
    assert {u for u in p.units if before[u] != after[u]} == {"RW1"}


def test_the_legend_kinds_follow_the_manual_kind() -> None:
    p = mini3()
    assert "reaction_wheel" in dk.used_kinds(p)
    for uid in p.units:
        if dk.looks_for(p, uid).kind.key == "reaction_wheel":
            with_kind(p, uid, "antenna")
    used = dk.used_kinds(p)
    assert "antenna" in used and "reaction_wheel" not in used


# ---- editing: one undo step, the journal, the schema -----------------------------------------------


def test_setting_and_clearing_the_kind_is_one_undo_step_each() -> None:
    p = mini3()
    history = History(p)
    start = layout.model_hash(p)
    history.execute("kind", edit.ops_update_unit(p, "RW1", kind="antenna"))
    assert p.units["RW1"].kind == "antenna"
    history.execute("kind", edit.ops_update_unit(p, "RW1", kind=None))
    assert p.units["RW1"].kind is None and layout.model_hash(p) == start
    history.undo()
    assert p.units["RW1"].kind == "antenna"
    history.undo()
    assert p.units["RW1"].kind is None and layout.model_hash(p) == start
    history.redo()
    assert p.units["RW1"].kind == "antenna"


def test_an_empty_text_means_automatic() -> None:
    p = with_kind(mini3(), "RW1", "antenna")
    History(p).execute("kind", edit.ops_update_unit(p, "RW1", kind="  "))
    assert p.units["RW1"].kind is None
    assert edit.parse_device_kind("gyro") == "gyro" and edit.parse_device_kind(None) is None


def test_the_other_fields_still_edit_with_the_kind_beside_them() -> None:
    p = mini3()
    History(p).execute("x", edit.ops_update_unit(p, "RW1", name="Wheel A", kind="gyro", notes="n"))
    u = p.units["RW1"]
    assert (u.name, u.kind, u.notes) == ("Wheel A", "gyro", "n")


def test_the_change_journal_records_the_kind(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(journal, "now", lambda: "2026-11-05T10:00:00Z")
    monkeypatch.setattr(journal, "author", lambda: "Ann Engineer")
    templates.create_project(tmp_path / "j", "flatsat", journal=True)
    project = load_project(tmp_path / "j").project
    History(project).execute("kind", edit.ops_update_unit(project, "BAT1", kind="heater"))
    save_project(project, tmp_path / "j")
    entries = load_project(tmp_path / "j").project.journal
    row = next(e for e in entries if e.field == "kind")
    assert (row.object, row.old, row.new) == ("device:BAT1", None, "heater")


def test_the_json_schema_of_the_units_file_lists_the_kinds() -> None:
    doc = json.dumps(schemas.schemas()["units"])
    assert '"kind"' in doc and all(f'"{k}"' in doc for k in dk.KIND_IDS)
    props = schemas.schemas()["units"]["$defs"]["Unit"]["properties"]
    assert "kind" not in schemas.schemas()["units"]["$defs"]["Unit"].get("required", [])
    assert sorted(props["kind"]["anyOf"][0]["enum"]) == sorted(dk.KIND_IDS)


def test_the_schema_command_writes_the_kind(tmp_path) -> None:
    assert main(["schema", str(tmp_path / "s")]) == 0
    text = (tmp_path / "s" / "units.schema.json").read_text(encoding="utf-8")
    assert "reaction_wheel" in text


def test_the_command_line_has_no_command_that_edits_one_device() -> None:
    """There is no `set`/`edit` command for a device in the command line (devices come in with
    `import-devices`, `import-subsystem` and the editor), so there is nothing to add `kind` to; a
    kind travels with the device library and subsystem files instead."""
    from harness_design_studio.cli.main import build_parser

    parser = build_parser()
    names = set(next(a for a in parser._actions if a.dest == "command").choices)
    assert not {n for n in names if n in {"set-device", "edit-device", "set-unit", "edit-unit"}}


def test_the_table_has_no_qt_in_it() -> None:
    """`core` may not import Qt: the written block diagram reads this module."""
    assert "PySide6" not in Path(dk.__file__).read_text(encoding="utf-8")
