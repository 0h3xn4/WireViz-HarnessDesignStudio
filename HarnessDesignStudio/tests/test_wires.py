# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""1.4.0 M1: editing one wire (gauge, type, colour, length, label, note) and what generation keeps."""

import json

import pytest

from harness_design_studio.core.commands import History, Put, apply_ops
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.generate.engine import generate_project, plan_generation
from harness_design_studio.core.io.layout import model_hash, serialize
from harness_design_studio.core.model import Part, Wire, evolve
from harness_design_studio.core.samples import sat15
from harness_design_studio.core.wires import (
    EDITABLE,
    find_wire,
    plan_wire_edit,
    plan_wire_reset,
    wire_part_choices,
)


@pytest.fixture
def project():
    p = sat15()
    generate_project(p)
    p.parts["EX-WIRE-22"] = Part(id="EX-WIRE-22", category="wire")
    return p


def first_wire(p) -> Wire:
    return next(w for h in p.harnesses.values() for w in h.wires)


def regenerate(p) -> None:
    apply_ops(p, plan_generation(p).ops)


def test_new_fields_are_not_written_while_they_have_their_default(project):
    """A project that does not use labels and notes keeps byte-identical files."""
    w = first_wire(project)
    assert "label" not in w.model_dump(mode="json")
    assert "note" not in w.model_dump(mode="json")
    for name, data in serialize(project).items():
        if name.startswith("physical/harnesses/"):
            wires = json.loads(data)["wires"]
            assert wires and all("label" not in x and "note" not in x for x in wires)


def test_a_label_and_a_note_are_written_once_they_are_set(project):
    h, w = find_wire(project, first_wire(project).id)
    History(project).execute(
        "edit wire", plan_wire_edit(project, [w.id], {"label": "Bus A", "note": "twist"})
    )
    data = json.loads(serialize(project)[f"physical/harnesses/{h.id}.json"])
    got = next(x for x in data["wires"] if x["id"] == w.id)
    assert (got["label"], got["note"]) == ("Bus A", "twist")


def test_editing_gauge_type_colour_and_length_locks_the_wire(project):
    w = first_wire(project)
    ops = plan_wire_edit(
        project,
        [w.id],
        {"gauge_awg": "22", "part_id": "EX-WIRE-22", "colour": "red", "length_m": "1,5"},
    )
    apply_ops(project, ops)
    got = find_wire(project, w.id)[1]
    assert (got.gauge_awg, got.part_id, got.colour, got.length_m, got.locked) == (
        22,
        "EX-WIRE-22",
        "red",
        1.5,
        True,
    )


def test_generation_keeps_what_a_person_typed(project):
    w = first_wire(project)
    apply_ops(
        project,
        plan_wire_edit(
            project, [w.id], {"gauge_awg": 20, "colour": "blue", "label": "L", "note": "n"}
        ),
    )
    regenerate(project)
    got = find_wire(project, w.id)[1]
    assert (got.gauge_awg, got.colour, got.label, got.note, got.locked) == (
        20,
        "blue",
        "L",
        "n",
        True,
    )


def test_a_label_or_note_alone_does_not_lock_the_wire_and_survives_generation(project):
    w = first_wire(project)
    apply_ops(project, plan_wire_edit(project, [w.id], {"label": "Heater", "note": "check"}))
    assert find_wire(project, w.id)[1].locked is False
    regenerate(project)
    got = find_wire(project, w.id)[1]
    assert (got.label, got.note, got.locked) == ("Heater", "check", False)


def test_reset_gives_the_wire_back_to_generation_and_keeps_label_and_note(project):
    w = first_wire(project)
    apply_ops(project, plan_wire_edit(project, [w.id], {"gauge_awg": 20, "note": "keep me"}))
    apply_ops(project, plan_wire_reset(project, [w.id]))
    assert find_wire(project, w.id)[1].locked is False
    regenerate(project)
    got = find_wire(project, w.id)[1]
    assert got.gauge_awg is None  # sat15 has placeholder values: the generated gauge is pending
    assert got.note == "keep me"


def test_several_wires_in_one_step_and_one_undo(project):
    ids = [w.id for h in project.harnesses.values() for w in h.wires][:3]
    before = model_hash(project)
    hist = History(project)
    hist.execute("edit wires", plan_wire_edit(project, ids, {"colour": "green"}))
    assert {find_wire(project, i)[1].colour for i in ids} == {"green"}
    hist.undo()
    assert model_hash(project) == before


def test_an_unchanged_edit_gives_no_ops(project):
    w = first_wire(project)
    assert plan_wire_edit(project, [w.id], {"note": ""}) == []
    assert plan_wire_reset(project, [w.id]) == []


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"gauge_awg": "abc"}, "whole number"),
        ({"gauge_awg": 99}, "Wire"),
        ({"gauge_awg": ""}, "Reset"),
        ({"length_m": "far"}, "metres"),
        ({"length_m": -1}, "Wire"),
        ({"part_id": "NOPE"}, "not a wire part"),
        ({"speed": 1}, "no field"),
    ],
)
def test_a_wrong_value_says_why_and_changes_nothing(project, changes, words):
    w = first_wire(project)
    before = model_hash(project)
    with pytest.raises(EditError, match=words):
        plan_wire_edit(project, [w.id], changes)
    assert model_hash(project) == before


def test_an_unknown_wire_and_an_empty_selection_are_refused(project):
    with pytest.raises(EditError, match="does not exist"):
        plan_wire_edit(project, ["NOPE"], {"note": "x"})
    with pytest.raises(EditError, match="No wire"):
        plan_wire_edit(project, [], {"note": "x"})


def test_a_released_harness_cannot_be_edited(project):
    h, w = find_wire(project, first_wire(project).id)
    apply_ops(project, [Put("harnesses", evolve(h, status="released"))])
    with pytest.raises(EditError, match="released"):
        plan_wire_edit(project, [w.id], {"colour": "red"})
    with pytest.raises(EditError, match="released"):
        plan_wire_reset(project, [w.id]) if w.locked else plan_wire_edit(
            project, [w.id], {"note": "x"}
        )


def test_choices_and_fields(project):
    assert "EX-WIRE-22" in wire_part_choices(project)
    assert set(EDITABLE) == {"gauge_awg", "part_id", "colour", "length_m", "label", "note"}


def test_a_wire_whose_interface_is_gone_is_reported_not_lost_silently(project):
    from harness_design_studio.core.commands import Delete

    h, w = find_wire(project, first_wire(project).id)
    apply_ops(project, plan_wire_edit(project, [w.id], {"note": "important"}))
    victim = w.interface_id
    assert victim
    # unreleased: removing the interface drops its wires on the next generation, with a warning
    apply_ops(project, [Delete("interfaces", victim)])
    plan = plan_generation(project)
    text = " ".join(f.message for f in plan.report.findings)
    assert "label or note" in text and w.id in text


# ---- outputs ----------------------------------------------------------------------------------


def _files(p):
    from harness_design_studio.core.outputs.build import build_outputs

    return dict(build_outputs(p).files)


def _csv(files, hid, name):
    return files[f"harnesses/{hid}/{name}"].decode().splitlines()


def test_label_and_note_columns_exist_only_when_a_wire_has_one(project):
    h, w = find_wire(project, first_wire(project).id)
    assert "Label" not in _csv(_files(project), h.id, "wirelist.csv")[1]  # byte-identical as before
    apply_ops(
        project, plan_wire_edit(project, [w.id], {"label": "Bus A", "note": "twist, 2 turns"})
    )
    wl = _csv(_files(project), h.id, "wirelist.csv")
    assert wl[1].endswith("Label,Note")
    row = next(r for r in wl[2:] if r.startswith(w.id + ","))
    assert row.endswith('Bus A,"twist, 2 turns"')


def test_the_wire_labels_print_the_label_instead_of_the_signal(project):
    h, w = find_wire(project, first_wire(project).id)
    apply_ops(project, plan_wire_edit(project, [w.id], {"label": "Bus A"}))
    labels = "\n".join(_csv(_files(project), h.id, "labels.csv"))
    assert f"{w.id} Bus A to" in labels
    assert f"{w.id} {w.signal} to" not in labels


def test_the_verifier_accepts_edited_wires_and_catches_a_changed_note(project):
    from harness_design_studio.core.outputs.verify import verify_outputs

    h, w = find_wire(project, first_wire(project).id)
    apply_ops(project, plan_wire_edit(project, [w.id], {"label": "Bus A", "note": "twist"}))
    files = _files(project)
    assert verify_outputs(project, files).ok
    key = f"harnesses/{h.id}/wirelist.csv"
    files[key] = files[key].replace(b"twist", b"untwist")
    codes = [i.code for i in verify_outputs(project, files).issues]
    assert "out_wire_differs" in codes
