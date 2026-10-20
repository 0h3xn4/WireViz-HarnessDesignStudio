# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""1.4.0 M3: a function (free text) on every pin: edit, paste, import, generation, outputs."""

import json

import pytest

from harness_design_studio.core import devices
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.io.layout import serialize
from harness_design_studio.core.model import Pin
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import sat15


@pytest.fixture
def project():
    p = sat15()
    generate_project(p)
    return p


def a_box_pin(p):
    c = next(c for c in sorted(p.connectors.values(), key=lambda c: c.id) if c.pins)
    return c.id, c.pins[0].id


def test_function_is_not_written_while_empty_and_is_once_set(project):
    cid, pid = a_box_pin(project)
    files = serialize(project)
    assert not any(b'"function"' in data for data in files.values())
    apply_ops(project, devices.ops_set_pin(project, cid, pid, function="Battery voltage sense"))
    text = "".join(d.decode() for d in serialize(project).values())
    assert text.count('"function": "Battery voltage sense"') >= 1


def test_a_function_can_be_set_cleared_and_is_text(project):
    cid, pid = a_box_pin(project)
    apply_ops(project, devices.ops_set_pin(project, cid, pid, function="  Heater 1  "))
    assert next(p for p in project.connectors[cid].pins if p.id == pid).function == "Heater 1"
    apply_ops(project, devices.ops_set_pin(project, cid, pid, function=""))
    assert next(p for p in project.connectors[cid].pins if p.id == pid).function is None
    with pytest.raises(EditError, match="function"):
        devices.ops_set_pin(project, cid, pid, function=5)


def test_a_pasted_block_can_fill_the_function_column(project):
    cid, pid = a_box_pin(project)
    apply_ops(
        project,
        devices.ops_paste_rows(project, cid, [{"pin": pid, "function": "Sun sensor 1"}]),
    )
    assert next(p for p in project.connectors[cid].pins if p.id == pid).function == "Sun sensor 1"


def test_the_pin_rows_of_the_device_view_carry_the_function(project):
    cid, pid = a_box_pin(project)
    apply_ops(project, devices.ops_set_pin(project, cid, pid, function="Status"))
    rows = {r.pin: r for r in devices.pin_rows(project, cid)}
    assert rows[pid].function == "Status"


def test_generation_copies_the_function_to_the_cable_pin(project):
    cid, pid = a_box_pin(project)
    h = next(
        h for h in project.harnesses.values() if any(c.mates_with == cid for c in h.connectors)
    )
    apply_ops(project, devices.ops_set_pin(project, cid, pid, function="Command input"))
    from harness_design_studio.core.generate.engine import plan_generation

    apply_ops(project, plan_generation(project).ops)
    cable = next(c for c in project.harnesses[h.id].connectors if c.mates_with == cid)
    assert next(p for p in cable.pins if p.id == pid).function == "Command input"


def test_the_pinout_tables_get_a_function_column_only_when_used(project):
    files = dict(build_outputs(project).files)
    head = files["system/box_pinouts.csv"].decode().splitlines()[1]  # [0] is the provenance line
    assert not head.endswith("Function")
    cid, pid = a_box_pin(project)
    apply_ops(project, devices.ops_set_pin(project, cid, pid, function="Status, ok"))
    files = dict(build_outputs(project).files)
    lines = files["system/box_pinouts.csv"].decode().splitlines()
    assert lines[1].endswith(",Function")
    assert any(f"{cid}," in line and line.endswith('"Status, ok"') for line in lines)
    assert verify_outputs(project, files).ok


def test_the_verifier_catches_a_wrong_function_in_the_pinout(project):
    cid, pid = a_box_pin(project)
    apply_ops(project, devices.ops_set_pin(project, cid, pid, function="Status"))
    files = dict(build_outputs(project).files)
    assert verify_outputs(project, files).ok
    files["system/box_pinouts.csv"] = files["system/box_pinouts.csv"].replace(b"Status", b"Other")
    assert "out_box_pinouts" in [i.code for i in verify_outputs(project, files).issues]


def test_an_import_stores_the_function_column_beside_the_signal(tmp_path, project):
    from harness_design_studio.core.pinout_import import guess_mapping, plan_pinout_import

    table = [["Connector", "Pin", "Signal", "Function"], ["J90", "1", "PWR", "Main bus power"]]
    mapping = guess_mapping(table[0])
    assert mapping["signal"] == 2 and mapping["function"] == 3
    unit = next(iter(project.units))
    part = next(
        p.id
        for p in project.parts.values()
        if p.category == "connector" and (p.pin_count or 0) >= 1
    )
    plan = plan_pinout_import(project, table, mapping, unit_id=unit, default_part=part)
    assert plan.importable, [r.message for r in plan.rows]
    apply_ops(project, plan.ops)
    conn = next(c for c in project.connectors.values() if c.name == "J90")
    pin = next(p for p in conn.pins if p.id == "1")
    assert (pin.signal, pin.function) == ("PWR", "Main bus power")


def test_a_pin_without_a_function_still_equals_the_old_file_shape():
    assert "function" not in Pin(id="1").model_dump(mode="json")
    assert json.loads(Pin(id="1", function="x").model_dump_json())["function"] == "x"


# ---- labels of connectors and of the harness --------------------------------------------------


def test_labels_of_a_harness_and_its_connectors_are_set_kept_and_printed(project):
    from harness_design_studio.core.generate.engine import plan_generation
    from harness_design_studio.core.wires import plan_set_labels

    h = next(h for h in sorted(project.harnesses.values(), key=lambda h: h.id) if h.connectors)
    cable = h.connectors[0].id
    apply_ops(
        project,
        plan_set_labels(project, h.id, harness="AOCS bus A", connectors={cable: "Rate sensor end"}),
    )
    got = project.harnesses[h.id]
    assert got.label == "AOCS bus A"
    assert next(c for c in got.connectors if c.id == cable).label == "Rate sensor end"
    apply_ops(project, plan_generation(project).ops)  # generation keeps both
    again = project.harnesses[h.id]
    assert again.label == "AOCS bus A"
    assert next(c for c in again.connectors if c.id == cable).label == "Rate sensor end"
    files = dict(build_outputs(project).files)
    labels = files[f"harnesses/{h.id}/labels.csv"].decode()
    assert f"{h.id},harness,AOCS bus A,1" in labels
    assert f"Rate sensor end ({cable} mates" in labels
    assert verify_outputs(project, files).ok


def test_a_cable_connector_prints_the_label_of_its_box_connector_when_it_has_none(project):
    h = next(h for h in sorted(project.harnesses.values(), key=lambda h: h.id) if h.connectors)
    cable = h.connectors[0]
    box = project.connectors[cable.mates_with]
    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import evolve

    apply_ops(project, [Put("connectors", evolve(box, label="Payload J1"))])
    labels = dict(build_outputs(project).files)[f"harnesses/{h.id}/labels.csv"].decode()
    assert f"Payload J1 ({cable.id} mates {box.id})" in labels


def test_a_box_connector_label_is_edited_through_the_device_plans(project):
    cid, _pid = a_box_pin(project)
    apply_ops(project, devices.ops_update_connector(project, cid, label="  J1 power  "))
    assert project.connectors[cid].label == "J1 power"
    apply_ops(project, devices.ops_update_connector(project, cid, label=""))
    assert project.connectors[cid].label is None


def test_labels_need_an_unreleased_harness_and_a_connector_of_it(project):
    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import evolve
    from harness_design_studio.core.wires import plan_set_labels

    h = next(h for h in sorted(project.harnesses.values(), key=lambda h: h.id) if h.connectors)
    with pytest.raises(EditError, match="not a connector"):
        plan_set_labels(project, h.id, connectors={"NOPE": "x"})
    with pytest.raises(EditError, match="does not exist"):
        plan_set_labels(project, "NOPE", harness="x")
    assert plan_set_labels(project, h.id, harness="") == []
    apply_ops(project, [Put("harnesses", evolve(h, status="released"))])
    with pytest.raises(EditError, match="released"):
        plan_set_labels(project, h.id, harness="x")


def test_label_fields_are_not_written_while_empty(project):
    files = serialize(project)  # (a library part of the category "label" is not a label field)
    text = "".join(d.decode() for k, d in files.items() if k.startswith(("physical/", "logical/")))
    assert '"label"' not in text


# ---- soldering: the termination in the pinout tables -------------------------------------------


def test_the_pinout_tables_say_crimp_or_solder_only_when_a_pin_does(project):
    files = dict(build_outputs(project).files)
    assert not files["system/box_pinouts.csv"].decode().splitlines()[1].endswith("Termination")
    cid, pid = a_box_pin(project)
    apply_ops(project, devices.ops_set_pin(project, cid, pid, termination="solder"))
    from harness_design_studio.core.generate.engine import plan_generation

    apply_ops(project, plan_generation(project).ops)
    files = dict(build_outputs(project).files)
    box = files["system/box_pinouts.csv"].decode().splitlines()
    assert box[1].endswith("Termination")
    row = next(line for line in box if line.startswith(f"{cid},") and f",{pid}," in line)
    assert row.endswith(",solder")
    cable_rows = [
        line
        for k, v in files.items()
        if k.endswith("/pinouts.csv")
        for line in v.decode().splitlines()
        if line.endswith(",solder")
    ]
    assert cable_rows  # the cable end copies the termination of the pin it plugs into
    assert verify_outputs(project, files).ok


def test_the_function_and_the_termination_columns_come_in_that_order(project):
    cid, pid = a_box_pin(project)
    apply_ops(
        project, devices.ops_set_pin(project, cid, pid, function="Status", termination="crimp")
    )
    head = dict(build_outputs(project).files)["system/box_pinouts.csv"].decode().splitlines()[1]
    assert head.endswith(",Spare,Function,Termination")
