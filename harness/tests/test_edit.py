"""REQ-EDIT-01: block-diagram edit operations (headless): positive and negative cases."""

import pytest

from harness_design_studio.core import edit
from harness_design_studio.core.commands import Delete, History, Put
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.issues import errors
from harness_design_studio.core.model import Connector, Harness, Project, Wire, evolve
from harness_design_studio.core.samples import mini3, new_project


def run(p: Project, label: str, ops: list) -> None:  # type: ignore[type-arg]
    History(p).execute(label, ops)
    assert errors(check_integrity(p)) == []


def test_add_unit_creates_connectors_pins_and_placement() -> None:
    p = new_project()
    ops, uid = edit.ops_add_unit(p, "computer")
    run(p, "add", ops)
    assert uid == "OBC1" and p.units[uid].name == "Computer 1" and p.units[uid].zone == "panel-A"
    conns = edit.unit_connectors(p, uid)
    assert [c.id for c in conns] == ["OBC1-J01", "OBC1-J02", "OBC1-J03", "OBC1-J04"]
    assert [c.part_id for c in conns] == [
        "EX-MICROD-25-F",  # four interface types
        "EX-MICROD-9-F",  # power
        "EX-MICROD-15-F",  # two interface types
        "EX-RJ45-F",  # Ethernet
    ]
    assert len(conns[0].pins) == 25  # from the library part's pin count
    assert p.placements[uid].x == edit.lane_x(0)


def test_add_units_never_overlap_and_ids_are_unique() -> None:
    p = new_project()
    for t in (
        "computer",
        "power",
        "actuator",
        "sensor",
        "payload",
        "transceiver",
        "pyro",
        "computer",
        "power",
    ):
        ops, _ = edit.ops_add_unit(p, t)
        run(p, "add", ops)
    pos = [(v.x, v.y) for v in p.placements.values()]
    for i, a in enumerate(pos):
        for b in pos[i + 1 :]:
            assert abs(a[0] - b[0]) >= edit.UNIT_W or abs(a[1] - b[1]) >= edit.UNIT_FOOTPRINT_H - 20
    assert len(p.units) == 9 and {"OBC1", "OBC2", "PCDU1", "PCDU2"} <= set(p.units)


def test_add_unit_errors() -> None:
    p = new_project()
    with pytest.raises(edit.EditError, match="Unknown unit template"):
        edit.ops_add_unit(p, "nope")
    p.parts.clear()
    with pytest.raises(edit.EditError, match="lacks"):
        edit.ops_add_unit(p, "computer")


def test_next_ids_ignore_case() -> None:
    p = mini3()
    assert edit.next_unit_id(p, "rw") == ("rw2", 2)  # "RW1" exists, case-insensitively
    assert edit.next_interface_id(p) == "IF-001"
    ops, iid = edit.ops_add_interface(p, "rs422", "OBC", "PCDU")
    assert iid == "IF-001"
    assert edit.next_interface_id(p, {"if-001"}) == "IF-002"


def test_zone_helpers() -> None:
    p = new_project()
    assert edit.effective_zones(p) == ["panel-A", "panel-B"]
    assert edit.zone_of_x(p, 30) == "panel-A" and edit.zone_of_x(p, 480) == "panel-B"
    assert edit.zone_of_x(p, 99999) == "panel-B" and edit.zone_of_x(p, -500) == "panel-A"
    run(p, "zone", edit.ops_add_zone(p, "deck"))
    assert edit.effective_zones(p) == ["panel-A", "panel-B", "deck"]
    with pytest.raises(edit.EditError, match="already exists"):
        edit.ops_add_zone(p, "PANEL-a")
    with pytest.raises(edit.EditError, match="needs a name"):
        edit.ops_add_zone(p, "  ")
    ops, uid = edit.ops_add_unit(p, "sensor", edit.lane_x(2), 40)
    run(p, "add", ops)
    assert p.units[uid].zone == "deck"


def test_zone_from_unit_not_in_list_is_effective() -> None:
    p = mini3()
    p.units["OBC"] = evolve(p.units["OBC"], zone="attic")
    assert "attic" in edit.effective_zones(p)


def test_position_of_unplaced_unit_uses_free_slot() -> None:
    p = mini3()
    del p.placements["OBC"]
    x, y = edit.position_of(p, "OBC")
    assert (x, y) != (p.placements["PCDU"].x, p.placements["PCDU"].y)


def test_move_unit_updates_zone() -> None:
    p = mini3()
    run(p, "move", edit.ops_move_unit(p, "OBC", edit.lane_x(1), 100))
    assert p.units["OBC"].zone == "panel-B" and p.placements["OBC"].y == 100
    run(p, "nudge", edit.ops_move_unit(p, "OBC", edit.lane_x(1), 120))
    assert p.placements["OBC"].y == 120


def test_compat_rules_unit_level() -> None:
    p = mini3()
    assert edit.unit_compat(p, "rs422", "OBC").ok
    assert not edit.unit_compat(p, "nope", "OBC").ok
    c = edit.unit_compat(p, "rs422", "OBC", source_unit="OBC")
    assert not c.ok and "itself" in c.why
    c = edit.unit_compat(p, "can", "PCDU")  # PCDU connectors carry power and discrete/rs422
    assert not c.ok and c.short == "No free CAN connector" and "unit template" in c.why
    c = edit.unit_compat(p, "rs422", "RW1")  # RW1-J02 already carries IF-TM-RW1
    assert not c.ok


def test_compat_rules_connector_level() -> None:
    p = mini3()
    assert not edit.connector_compat(p, "rs422", "GHOST").ok
    assert not edit.connector_compat(p, "rs422", "W001-P1").ok  # not a unit connector
    assert "already carries IF-PWR-RW1" in edit.connector_compat(p, "power_primary", "RW1-J01").why
    p.connectors["OBC-J01"] = evolve(p.connectors["OBC-J01"], carries=["rs422"])
    c = edit.connector_compat(p, "power_primary", "PCDU-J01")  # busy first
    assert not c.ok
    p.connectors["PCDU-J01"] = evolve(p.connectors["PCDU-J01"], carries=["rs422"])
    del p.interfaces["IF-PWR-RW1"]
    wrong = edit.connector_compat(p, "power_primary", "PCDU-J01")
    assert not wrong.ok and "does not carry Primary power" in wrong.why
    assert edit.connector_compat(p, "rs422", "PCDU-J01", source_unit="OBC").ok
    assert not edit.connector_compat(p, "rs422", "PCDU-J01", source_unit="PCDU").ok


def test_add_interface_guided_marks_auto_and_expert_does_not() -> None:
    p = new_project()
    for t in ("computer", "actuator"):
        run(p, "add", edit.ops_add_unit(p, t)[0])
    ops, iid = edit.ops_add_interface(p, "rs422", "OBC1", "RW1")
    run(p, "if", ops)
    i = p.interfaces[iid]
    assert [e.auto for e in i.endpoints] == [True, True] and i.redundancy == "nominal"
    assert i.endpoints[0].connector_id == "OBC1-J01" and i.endpoints[1].connector_id == "RW1-J02"
    ops2, iid2 = edit.ops_add_interface(p, "power_primary", "OBC1", "RW1", "OBC1-J02", "RW1-J01")
    run(p, "if2", ops2)
    assert [e.auto for e in p.interfaces[iid2].endpoints] == [False, False]
    assert iid2 == "IF-002"


def test_add_interface_errors() -> None:
    p = mini3()
    with pytest.raises(edit.EditError, match="does not exist"):
        edit.ops_add_interface(p, "rs422", "OBC", "GHOST")
    with pytest.raises(edit.EditError, match="itself"):
        edit.ops_add_interface(p, "rs422", "OBC", "OBC")
    with pytest.raises(edit.EditError, match="no free"):
        edit.ops_add_interface(p, "can", "OBC", "PCDU")
    with pytest.raises(edit.EditError, match="already carries"):
        edit.ops_add_interface(p, "power_primary", "PCDU", "RW1", "PCDU-J01", "RW1-J01")
    with pytest.raises(edit.EditError, match="no free"):
        edit.ops_add_interface(
            p, "rs422", "OBC", "PCDU", avoid_connectors={"PCDU-J03", "PCDU-J01", "PCDU-J02"}
        )


def test_confirm_interface() -> None:
    p = new_project()
    for t in ("computer", "actuator"):
        run(p, "add", edit.ops_add_unit(p, t)[0])
    run(p, "if", edit.ops_add_interface(p, "rs422", "OBC1", "RW1")[0])
    run(p, "confirm", edit.ops_confirm_interface(p, "IF-001"))
    assert not any(e.auto for e in p.interfaces["IF-001"].endpoints)


def test_delete_unit_cascades_and_undoes() -> None:
    p = mini3()
    h = History(p)
    start = model_hash(p)
    impact = edit.delete_impact(p, "OBC")
    assert impact.interfaces == ("IF-TM-RW1",) and len(impact.connectors) == 3
    h.execute("delete", edit.ops_delete_unit(p, "OBC"))
    assert "OBC" not in p.units and "OBC" not in p.placements and "IF-TM-RW1" not in p.interfaces
    assert not [c for c in p.connectors.values() if c.unit_id == "OBC"]
    h.undo()
    assert model_hash(p) == start


def test_delete_blocked_when_harness_wires_trace_to_the_unit() -> None:
    p = mini3()  # W001 wires belong to IF-PWR-RW1, which RW1 and PCDU use
    for uid in ("RW1", "PCDU"):
        with pytest.raises(edit.EditError, match="W001 was made by hand"):
            edit.ops_delete_unit(p, uid)
    with pytest.raises(edit.EditError, match="W001 was made by hand"):
        edit.ops_delete_interface(p, "IF-PWR-RW1")


def test_delete_blocked_by_harness_wires_and_unknown() -> None:
    p = mini3()
    h = p.harnesses["W001"]
    w = Wire(
        id="W001-009", from_connector="OBC-J01", from_pin="5", to_connector="W001-P1", to_pin="1"
    )
    p.harnesses["W001"] = evolve(h, wires=[*h.wires, w])
    with pytest.raises(edit.EditError, match="W001 was made by hand"):
        edit.ops_delete_unit(p, "OBC")
    with pytest.raises(edit.EditError, match="does not exist"):
        edit.ops_delete_unit(p, "GHOST")
    with pytest.raises(edit.EditError, match="does not exist"):
        edit.ops_delete_interface(p, "GHOST")
    run(p, "del if", edit.ops_delete_interface(p, "IF-TM-RW1"))


def test_rename_unit_cascades() -> None:
    p = mini3()
    run(p, "rename", edit.ops_rename_unit(p, "RW1", "WHEEL1"))
    assert "RW1" not in p.units and p.units["WHEEL1"].name == "Reaction wheel 1"
    assert p.placements["WHEEL1"].x == 470 and "RW1" not in p.placements
    assert all(c.unit_id == "WHEEL1" for c in edit.unit_connectors(p, "WHEEL1"))
    assert {e.unit_id for e in p.interfaces["IF-PWR-RW1"].endpoints} == {"PCDU", "WHEEL1"}
    assert edit.ops_rename_unit(p, "OBC", "OBC") == []
    with pytest.raises(edit.EditError, match="already used"):
        edit.ops_rename_unit(p, "OBC", "pcdu")
    with pytest.raises(edit.EditError, match="does not exist"):
        edit.ops_rename_unit(p, "GHOST", "X")
    with pytest.raises(Exception, match="start with a letter"):
        edit.ops_rename_unit(p, "OBC", "1bad")


def test_redundant_copy_mirrors_interfaces() -> None:
    p = mini3()
    result = edit.ops_redundant_copy(p, "RW1")
    run(p, "redundant", result.ops)
    assert result.twin_id == "RW1-R" and p.units["RW1-R"].side == "redundant"
    assert p.units["RW1-R"].zone != p.units["RW1"].zone  # placed in the other lane
    assert {"IF-PWR-RW1-R", "IF-TM-RW1-R"} <= set(p.interfaces)
    assert all(i.redundancy == "redundant" for k, i in p.interfaces.items() if k.endswith("-R"))
    assert result.skipped == ()
    with pytest.raises(edit.EditError, match="already has a redundant copy"):
        edit.ops_redundant_copy(p, "RW1")
    with pytest.raises(edit.EditError, match="already on the redundant"):
        edit.ops_redundant_copy(p, "RW1-R")
    with pytest.raises(edit.EditError, match="does not exist"):
        edit.ops_redundant_copy(p, "GHOST")


def test_redundant_copy_skips_interfaces_without_free_connector() -> None:
    p = mini3()
    for cid in (
        "OBC-J01",
        "OBC-J03",
    ):  # the OBC connectors that could carry rs422/can are taken away
        p.connectors[cid] = evolve(p.connectors[cid], carries=["discrete"])
    result = edit.ops_redundant_copy(p, "RW1")
    assert "IF-TM-RW1" in result.skipped
    run(p, "redundant", result.ops)
    assert "IF-TM-RW1-R" not in p.interfaces


def test_complete_chain_creates_twin_and_rewires() -> None:
    p = mini3()
    run(p, "redundant", edit.ops_redundant_copy(p, "RW1").ops)
    ops, tid = edit.ops_complete_chain(p, "IF-PWR-RW1-R")
    run(p, "fix", ops)
    assert tid == "PCDU-R" and p.units["PCDU-R"].side == "redundant"
    ends = {e.unit_id for e in p.interfaces["IF-PWR-RW1-R"].endpoints}
    assert ends == {"PCDU-R", "RW1-R"}
    with pytest.raises(edit.EditError, match="no nominal end"):
        edit.ops_complete_chain(p, "IF-PWR-RW1-R")


def test_complete_chain_without_free_connector() -> None:
    p = mini3()
    run(p, "redundant", edit.ops_redundant_copy(p, "RW1").ops)
    for c in edit.unit_connectors(p, "PCDU"):
        p.connectors[c.id] = evolve(c, carries=["discrete"])
    run(p, "twin", [Put("units", evolve(p.units["PCDU"], id="PCDU-R", side="redundant"))])
    p.connectors["PCDU-R-J01"] = Connector(
        id="PCDU-R-J01",
        name="J01",
        role="box",
        part_id="EX-DSUB-9-F",
        unit_id="PCDU-R",
        carries=["discrete"],
    )
    with pytest.raises(edit.EditError, match="no free"):
        edit.ops_complete_chain(p, "IF-PWR-RW1-R")


def test_clone_with_does_not_touch_original() -> None:
    p = mini3()
    h0 = model_hash(p)
    q = edit.clone_with(p, [Delete("interfaces", "IF-TM-RW1")])
    assert "IF-TM-RW1" not in q.interfaces and model_hash(p) == h0


def test_add_unit_rolls_back_when_harness_blocks_delete() -> None:
    p = mini3()
    h = History(p)
    with pytest.raises(TransactionError):
        h.execute("bad", [Delete("units", "OBC")])  # raw delete leaves interfaces dangling
    assert "OBC" in p.units


def test_harness_object_import_is_used() -> None:
    assert Harness(id="H1", name="h").status == "draft"


def test_unit_templates_follow_the_baseline_standards() -> None:
    """D-130: RS-422, RS-485 and CAN; Micro-D 9 to 31 pin; Ethernet on RJ45; SMA for RF."""
    from harness_design_studio.core.starter import starter_interface_types, starter_parts

    parts = {x.id: x for x in starter_parts()}
    types = {x.id for x in starter_interface_types()}
    assert {"rs422", "rs485", "can", "ethernet"} <= types
    assert {f"EX-MICROD-{n}-{g}" for n in (9, 15, 21, 25, 31) for g in "MF"} <= set(parts)
    assert {"EX-RJ45-M", "EX-RJ45-F", "EX-SMA-M", "EX-SMA-F"} <= set(parts)
    assert parts["EX-MICROD-31-F"].mates_with == "EX-MICROD-31-M"
    for template in edit.TEMPLATES.values():
        for conn in template.connectors:
            assert conn.part_id in parts, (template.id, conn.part_id)
            assert set(conn.carries) <= types
            if conn.carries == ("rf_coax",):
                assert conn.part_id == "EX-SMA-F"
            elif conn.carries == ("ethernet",):
                assert conn.part_id == "EX-RJ45-F"
            else:
                assert conn.part_id.startswith("EX-MICROD-"), (template.id, conn.part_id)
                assert parts[conn.part_id].pin_count and parts[conn.part_id].pin_count >= 9  # type: ignore[operator]
    sizes = {edit.TEMPLATES["power"].connectors[0].part_id: 9, "EX-MICROD-15-F": 15}
    assert edit._box_part(("rs422",)) == "EX-MICROD-9-F"
    assert edit._box_part(("rs422", "can")) == "EX-MICROD-15-F"
    assert edit._box_part(("rs422", "rs485", "can")) == "EX-MICROD-21-F"
    assert edit._box_part(("rs422", "rs485", "can", "discrete")) == "EX-MICROD-25-F"
    assert edit._box_part(("rs422", "rs485", "can", "discrete", "analog")) == "EX-MICROD-31-F"
    assert edit._box_part(("power_primary",)) == "EX-MICROD-9-F"
    assert sizes
