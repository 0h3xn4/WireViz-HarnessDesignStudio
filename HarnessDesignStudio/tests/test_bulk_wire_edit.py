# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""REQ-WIRE-08. Workshop feedback M3: the same gauge, type, colour and length on all wires of a harness,
the selected wires, or the wires of one signal, in one undo step; the wires are locked against Generate
exactly as one edited wire is."""

import pytest

from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.generate.engine import generate_project, plan_generation
from harness_design_studio.core.io.layout import model_hash, serialize
from harness_design_studio.core.model import Part, evolve
from harness_design_studio.core.samples import sat15
from harness_design_studio.core.wires import (
    BULK_FIELDS,
    bulk_targets,
    plan_bulk_wire_edit,
    plan_wire_edit,
    signals_of,
    wires_changed,
)


@pytest.fixture
def project():
    p = sat15()
    generate_project(p)
    p.parts["EX-WIRE-22"] = Part(id="EX-WIRE-22", category="wire")
    return p


def wires(p, hid="W009"):
    return {w.id: w for w in p.harnesses[hid].wires}


def test_all_wires_of_a_harness_get_the_values_and_are_locked(project):
    ops = plan_bulk_wire_edit(
        project,
        "W009",
        {"gauge_awg": "22", "colour": "red", "length_m": "1,5", "part_id": "EX-WIRE-22"},
    )
    assert len(ops) == 1
    apply_ops(project, ops)
    for w in wires(project).values():
        assert (w.gauge_awg, w.colour, w.length_m, w.part_id, w.locked) == (
            22,
            "red",
            1.5,
            "EX-WIRE-22",
            True,
        )
    assert all(not w.locked for w in wires(project, "W010").values())  # (other harnesses stay)


def test_it_is_the_same_result_as_editing_each_wire(project):
    other = sat15()
    generate_project(other)
    other.parts["EX-WIRE-22"] = Part(id="EX-WIRE-22", category="wire")
    apply_ops(project, plan_bulk_wire_edit(project, "W009", {"gauge_awg": 24, "colour": "blue"}))
    apply_ops(
        other, plan_wire_edit(other, sorted(wires(other)), {"gauge_awg": 24, "colour": "blue"})
    )
    assert serialize(project) == serialize(other)


def test_the_selected_wires_only(project):
    ids = sorted(wires(project))
    ops = plan_bulk_wire_edit(project, "W009", {"colour": "green"}, wire_ids=ids[:2])
    apply_ops(project, ops)
    got = wires(project)
    assert [got[i].colour for i in ids] == ["green", "green", None, None]
    assert [got[i].locked for i in ids] == [True, True, False, False]
    with pytest.raises(EditError, match="is not a wire of W009"):
        plan_bulk_wire_edit(project, "W009", {"colour": "green"}, wire_ids=["W001-0001"])


def test_the_wires_of_one_signal(project):
    assert signals_of(project, "W009") == ["TX+/RX+", "TX-/RX-"]
    ids = bulk_targets(project, "W009", signal="TX+/RX+")
    assert len(ids) == 2
    apply_ops(project, plan_bulk_wire_edit(project, "W009", {"gauge_awg": 26}, signal="TX+/RX+"))
    got = wires(project)
    assert {i: got[i].gauge_awg for i in got} == {i: (26 if i in ids else None) for i in got}
    with pytest.raises(EditError, match="no wire with the signal 'NOPE'"):
        plan_bulk_wire_edit(project, "W009", {"gauge_awg": 26}, signal="NOPE")


def test_only_empty_fills_the_gaps_and_leaves_what_is_there(project):
    first = sorted(wires(project))[0]
    apply_ops(project, plan_wire_edit(project, [first], {"colour": "red"}))
    apply_ops(
        project,
        plan_bulk_wire_edit(project, "W009", {"colour": "blue", "gauge_awg": 22}, only_empty=True),
    )
    got = wires(project)
    assert got[first].colour == "red" and got[first].gauge_awg == 22
    assert {w.colour for i, w in got.items() if i != first} == {"blue"}
    again = plan_bulk_wire_edit(
        project, "W009", {"colour": "blue", "gauge_awg": 22}, only_empty=True
    )
    assert again == []  # nothing is empty any more


def test_one_undo_step(project):
    before = model_hash(project)
    hist = History(project)
    hist.execute("bulk", plan_bulk_wire_edit(project, "W009", {"colour": "green"}))
    assert {w.colour for w in wires(project).values()} == {"green"}
    hist.undo()
    assert model_hash(project) == before
    hist.redo()
    assert {w.locked for w in wires(project).values()} == {True}


def test_generation_keeps_the_values_and_a_second_plan_is_empty(project):
    apply_ops(project, plan_bulk_wire_edit(project, "W009", {"gauge_awg": 22, "colour": "green"}))
    apply_ops(project, plan_generation(project).ops)
    assert {(w.gauge_awg, w.colour, w.locked) for w in wires(project).values()} == {
        (22, "green", True)
    }
    assert plan_generation(project).ops == []


def test_how_many_wires_change_is_told_before_it_happens(project):
    ops = plan_bulk_wire_edit(project, "W009", {"colour": "green"})
    assert wires_changed(project, ops) == 4
    first = sorted(wires(project))[0]
    apply_ops(project, plan_wire_edit(project, [first], {"colour": "green"}))
    assert wires_changed(project, plan_bulk_wire_edit(project, "W009", {"colour": "green"})) == 3
    assert plan_bulk_wire_edit(project, "W009", {"colour": "green"}, wire_ids=[first]) == []


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({}, "Enter a gauge"),
        ({"gauge_awg": "abc"}, "whole number"),
        ({"gauge_awg": ""}, "cannot be cleared"),
        ({"length_m": "far"}, "metres"),
        ({"part_id": "NOPE"}, "not a wire part"),
        ({"label": "x"}, "label, the note and the ends"),
    ],
)
def test_a_wrong_value_says_why_and_changes_nothing(project, changes, words):
    before = model_hash(project)
    with pytest.raises(EditError, match=words):
        plan_bulk_wire_edit(project, "W009", changes)
    assert model_hash(project) == before
    assert BULK_FIELDS == ("gauge_awg", "part_id", "colour", "length_m")


def test_a_released_harness_an_unknown_harness_and_an_empty_one_refuse(project):
    project.harnesses["W009"] = evolve(project.harnesses["W009"], status="released")
    with pytest.raises(EditError, match="released"):
        plan_bulk_wire_edit(project, "W009", {"colour": "green"})
    with pytest.raises(EditError, match="does not exist"):
        plan_bulk_wire_edit(project, "W999", {"colour": "green"})
    with pytest.raises(EditError, match="does not exist"):
        signals_of(project, "W999")
    project.harnesses["W010"] = evolve(project.harnesses["W010"], wires=[], shields=[])
    with pytest.raises(EditError, match="has no wires"):
        plan_bulk_wire_edit(project, "W010", {"colour": "green"})
