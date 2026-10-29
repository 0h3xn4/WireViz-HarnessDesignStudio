"""Generation and editing findings of the October audit, medium round (B-5 to B-15, B-20, B-22)."""

from typing import Any

import pytest

from harness_design_studio.core import edit
from harness_design_studio.core.commands import Delete, History, Put, SetZones, apply_ops
from harness_design_studio.core.generate.engine import (
    generate_project,
    generation_status,
    plan_generation,
)
from harness_design_studio.core.generate.pins import Request, allocate
from harness_design_studio.core.model import (
    ConfigFile,
    Connector,
    Endpoint,
    Harness,
    InterfaceInstance,
    Pin,
    Project,
    SignalDef,
    Unit,
    Wire,
    evolve,
)
from harness_design_studio.core.samples import mini3, new_project, sat15
from harness_design_studio.core.verify import verify_project

# ---- helpers -------------------------------------------------------------------------------------


def two_units(n_pins: int = 25) -> Project:
    p = new_project("t")
    for uid, zone in (("A", "panel-A"), ("B", "panel-B")):
        p.units[uid] = Unit(id=uid, name=uid, subsystem="x", zone=zone, side="nominal")
        p.connectors[f"{uid}-J01"] = Connector(
            id=f"{uid}-J01", name="J01", role="box", part_id="EX-MICROD-25-F", unit_id=uid,
            gender="female", pins=[Pin(id=str(i)) for i in range(1, n_pins + 1)],
        )  # fmt: skip
    return p


def iface(p: Project, iid: str, type_id: str) -> None:
    p.interfaces[iid] = InterfaceInstance(
        id=iid, name=iid, type_id=type_id,
        endpoints=[Endpoint(unit_id="A", connector_id="A-J01"), Endpoint(unit_id="B", connector_id="B-J01")],
    )  # fmt: skip


def set_cfg(p: Project, name: str, **values: object) -> None:
    old = p.config[name]
    p.config[name] = ConfigFile(
        name=name, placeholder=old.placeholder, values={**old.values, **values}
    )


def finding_codes(p: Project) -> set[str]:
    return {f.code for f in plan_generation(p).report.findings}


# ---- B-5: a template that fails for some harness IDs ---------------------------------------------


def test_a_harness_template_whose_default_names_would_be_too_long_is_refused() -> None:
    p = sat15()
    p.config["naming"] = ConfigFile(
        name="naming", placeholder=False, values={"harness": "H{n:0>60}"}
    )
    plan = plan_generation(p)  # used to raise a validation error for the wire IDs
    assert any(f.code == "naming" and "naming.harness" in f.message for f in plan.report.findings)
    assert all(h.startswith("W") for h in plan.harnesses)


def test_a_wire_template_that_is_too_long_for_a_long_harness_id_is_reported() -> None:
    p = sat15()
    p.config["naming"] = ConfigFile(
        name="naming",
        placeholder=False,
        values={"harness": "H{n:0>30}", "wire": "{harness}-{harness}-{n}"},
    )
    plan = plan_generation(p)
    assert any(f.code == "naming" and "naming.wire" in f.message for f in plan.report.findings)
    apply_ops(p, plan.ops)
    assert verify_project(p).ok


# ---- B-7: locked power pins and the power-to-signal gap ------------------------------------------


def test_locked_power_pins_count_for_the_power_to_signal_gap() -> None:
    p = two_units()
    iface(p, "IF-1", "power_primary")
    iface(p, "IF-2", "rs422")
    set_cfg(p, "generation", power_signal_gap_pins=0)
    generate_project(p)
    for cid in ("A-J01", "B-J01"):  # the person locks the power pins where they are
        c = p.connectors[cid]
        pins = [evolve(x, locked=True) if x.interface_id == "IF-1" else x for x in c.pins]
        p.connectors[cid] = evolve(c, pins=pins)
    set_cfg(p, "generation", power_signal_gap_pins=6)
    apply_ops(p, plan_generation(p).ops)
    for cid in ("A-J01", "B-J01"):
        c = p.connectors[cid]
        power_last = max(k for k, x in enumerate(c.pins) if x.interface_id == "IF-1")
        first_signal = min(k for k, x in enumerate(c.pins) if x.interface_id == "IF-2")
        assert first_signal - power_last - 1 >= 6, cid


def test_allocate_leaves_the_gap_after_a_held_power_pin() -> None:
    conn = Connector(
        id="A-J01", name="J01", role="box", part_id="EX-MICROD-25-F", unit_id="A",
        pins=[Pin(id=str(i), locked=i in (1, 3)) for i in range(1, 21)],
    )  # fmt: skip
    p = sat15()
    power, serial = p.interface_types["power_primary"], p.interface_types["rs422"]
    held = {("P", power.signals[0].name): "1", ("P", power.signals[1].name): "3"}
    res = allocate(conn, [Request("P", power), Request("S", serial)], {}, 3, held)
    used = sorted(int(pid) for (iid, _s), pid in res.pins.items() if iid == "S")
    assert used and used[0] >= 3 + 1 + 3  # last power pin 3, gap of 3 pins


# ---- B-8: generation status and manual harnesses -------------------------------------------------


def manual_harness_for(p: Project, interface_id: str) -> Harness:
    g = next(h for h in p.harnesses.values() if h.generated and interface_id in h.interfaces)
    a, b = g.connectors[0], g.connectors[1]
    w0 = g.wires[0]
    return Harness(
        id="MAN1", name="manual",
        connectors=[
            Connector(id="MAN1-P1", name="P1", role="cable", part_id=a.part_id, mates_with=a.mates_with, pins=a.pins),
            Connector(id="MAN1-P2", name="P2", role="cable", part_id=b.part_id, mates_with=b.mates_with, pins=b.pins),
        ],
        wires=[Wire(id="MAN1-001", signal=w0.signal, from_connector="MAN1-P1", from_pin=w0.from_pin, to_connector="MAN1-P2", to_pin=w0.to_pin, interface_id=interface_id)],
    )  # fmt: skip


def test_status_is_stale_when_a_manual_harness_takes_over_an_interface() -> None:
    p = sat15()
    generate_project(p)
    assert generation_status(p) == "current"
    iid = next(h for h in p.harnesses.values() if h.generated).interfaces[0]
    apply_ops(p, [Put("harnesses", manual_harness_for(p, iid))])
    assert not plan_generation(p).empty  # the plan would remove the generated wires
    assert generation_status(p) == "stale"


def test_releasing_a_harness_does_not_make_the_status_stale() -> None:
    p = sat15()
    generate_project(p)
    h = next(iter(p.harnesses.values()))
    apply_ops(p, [Put("harnesses", evolve(h, status="released"))])
    assert (
        generation_status(p) == "current"
    )  # release bookkeeping is not an input (docs/developer/agent/core.md)


# ---- B-9: locked wires and entered lengths are not lost silently ---------------------------------


def one_interface_harness(p: Project) -> Harness:
    return next(x for x in p.harnesses.values() if len(x.interfaces) == 1 and len(x.wires) >= 2)


def lock_first_wire(p: Project, h: Harness) -> Wire:
    w = evolve(h.wires[0], locked=True, gauge_awg=22, length_m=1.5)
    apply_ops(p, [Put("harnesses", evolve(h, wires=[w, *h.wires[1:]]))])
    return w


def test_a_locked_wire_that_cannot_be_carried_over_is_named_in_a_finding() -> None:
    p = sat15()
    generate_project(p)
    h = one_interface_harness(p)
    w = lock_first_wire(p, h)
    assert w.interface_id is not None
    apply_ops(p, [Delete("interfaces", w.interface_id)])
    plan = plan_generation(p)
    lost = [f for f in plan.report.findings if f.code == "locked_data_lost"]
    assert len(lost) == 1 and w.id in lost[0].message and lost[0].object_id == h.id
    assert lost[0].severity == "warning"


def test_a_locked_wire_of_a_signal_that_vanished_is_named_in_a_finding() -> None:
    p = sat15()
    generate_project(p)
    h = one_interface_harness(p)
    w = lock_first_wire(p, h)
    assert w.interface_id is not None and w.signal is not None
    t = p.interface_types[p.interfaces[w.interface_id].type_id]
    gone = set(w.signal.split("/"))
    apply_ops(
        p, [Put("interface_types", evolve(t, signals=[s for s in t.signals if s.name not in gone]))]
    )
    lost = [f for f in plan_generation(p).report.findings if f.code == "locked_data_lost"]
    assert len(lost) == 1 and w.id in lost[0].message


def test_an_entered_segment_length_that_is_dropped_is_named_in_a_finding() -> None:
    p = sat15()
    generate_project(p)
    h = one_interface_harness(p)
    seg = evolve(h.segments[0], length_m=2.5)
    apply_ops(p, [Put("harnesses", evolve(h, segments=[seg, *h.segments[1:]]))])
    apply_ops(p, [Delete("interfaces", h.interfaces[0])])
    lost = [f for f in plan_generation(p).report.findings if f.code == "locked_data_lost"]
    assert len(lost) == 1 and seg.id in lost[0].message and "2.5" in lost[0].message


def test_nothing_is_reported_when_all_user_data_is_carried_over() -> None:
    p = sat15()
    generate_project(p)
    lock_first_wire(p, one_interface_harness(p))
    assert "locked_data_lost" not in finding_codes(p)


def test_renaming_a_unit_keeps_harness_ids_and_locked_wires_per_unit_pair() -> None:
    p = sat15()
    set_cfg(p, "segmentation", mode="per_unit_pair")
    generate_project(p)
    before = sorted(p.harnesses)
    h = next(x for x in p.harnesses.values() if len(x.wires) > 1)
    w = lock_first_wire(p, h)
    unit = next(
        c.unit_id for c in p.connectors.values() if c.id == h.connectors[0].mates_with and c.unit_id
    )
    History(p).execute("rename", edit.ops_rename_unit(p, unit, "RENAMED"))
    plan = plan_generation(p)
    assert plan.report.removed == [] and plan.report.added == []
    assert "locked_data_lost" not in {f.code for f in plan.report.findings}
    apply_ops(p, plan.ops)
    assert sorted(p.harnesses) == before
    kept = next(x for x in p.harnesses[h.id].wires if x.id == w.id)
    assert kept.locked and kept.gauge_awg == 22 and kept.length_m == 1.5
    assert verify_project(p).ok


# ---- B-10: a redundant copy does not carry the pin assignments over ------------------------------


def test_a_redundant_copy_starts_without_the_pin_assignments_of_the_original() -> None:
    p = sat15()
    generate_project(p)
    unit = next(
        u
        for u in sorted(p.units)
        if not u.endswith("-R")
        and f"{u}-R" not in p.units
        and any(x.interface_id for c in edit.unit_connectors(p, u) for x in c.pins)
    )
    locked_conn = edit.unit_connectors(p, unit)[0]
    pins = [
        evolve(x, signal="KEEP", interface_id=None, locked=True) if k == 0 else x
        for k, x in enumerate(locked_conn.pins)
    ]
    p.connectors[locked_conn.id] = evolve(locked_conn, pins=pins)
    History(p).execute("twin", edit.ops_redundant_copy(p, unit).ops)
    for c in edit.unit_connectors(p, f"{unit}-R"):
        assert not [x for x in c.pins if x.interface_id], c.id
        assert [x.signal for x in c.pins if x.signal] == (
            ["KEEP"] if c.id.endswith(locked_conn.id[-3:]) else []
        )


# ---- B-11: deleting a unit that a manual harness plugs into --------------------------------------


def test_delete_impact_finds_manual_harness_wires_that_end_on_the_unit() -> None:
    p = mini3()
    h = p.harnesses["W001"]
    p.harnesses["W001"] = evolve(h, wires=[evolve(w, interface_id=None) for w in h.wires])
    assert edit.delete_impact(p, "RW1").blocked_by_harnesses == ("W001",)
    with pytest.raises(edit.EditError, match="W001 was made by hand"):
        edit.ops_delete_unit(p, "RW1")


# ---- B-12: inputs generation cannot wire are skipped and reported --------------------------------


def skipped_reason(p: Project, iid: str) -> str:
    plan = plan_generation(p)
    found = [
        f for f in plan.report.findings if f.code == "interface_skipped" and f.object_id == iid
    ]
    assert found, [(f.code, f.message) for f in plan.report.findings]
    return found[0].message


def test_an_interface_with_both_ends_on_one_connector_is_skipped() -> None:
    p = two_units()
    iface(p, "IF-1", "rs422")
    p.interfaces["IF-2"] = InterfaceInstance(
        id="IF-2", name="loop", type_id="rs422",
        endpoints=[Endpoint(unit_id="A", connector_id="A-J01"), Endpoint(unit_id="A", connector_id="A-J01")],
    )  # fmt: skip
    assert "same connector" in skipped_reason(p, "IF-2")
    generate_project(p)
    assert not [w for h in p.harnesses.values() for w in h.wires if w.interface_id == "IF-2"]


def test_an_interface_type_with_a_repeated_signal_name_is_skipped() -> None:
    p = two_units()
    t = p.interface_types["rs422"]
    p.interface_types["rs422"] = evolve(t, signals=[*t.signals, SignalDef(name=t.signals[0].name)])
    iface(p, "IF-1", "rs422")
    assert t.signals[0].name in skipped_reason(p, "IF-1")
    generate_project(p)
    assert not p.harnesses


@pytest.mark.parametrize("ends", [0, 1])
def test_an_interface_with_too_few_ends_is_not_called_multi_drop(ends: int) -> None:
    p = two_units()
    p.interfaces["IF-1"] = InterfaceInstance(
        id="IF-1", name="x", type_id="rs422",
        endpoints=[Endpoint(unit_id="A", connector_id="A-J01")][:ends],
    )  # fmt: skip
    reason = skipped_reason(p, "IF-1")
    assert "multi-drop" not in reason and "needs two" in reason


# ---- B-14: zone names and projects without zones -------------------------------------------------


@pytest.mark.parametrize("name", ["a\x00b", "x" * 300])
def test_a_zone_name_the_model_would_refuse_is_rejected(name: str) -> None:
    with pytest.raises(edit.EditError, match="zone name"):
        edit.ops_add_zone(sat15(), name)


def test_a_project_without_zones_can_still_be_edited() -> None:
    p = new_project("t")
    History(p).execute("zones", [SetZones(())])
    assert edit.effective_zones(p) == [] and edit.zone_of_x(p, 100) == ""
    ops, a = edit.ops_add_unit(p, "computer")
    History(p).execute("add", ops)
    ops, b = edit.ops_add_unit(p, "power")
    History(p).execute("add", ops)
    assert p.units[a].zone is None
    History(p).execute("move", edit.ops_move_unit(p, a, 700, 300))
    History(p).execute("twin", edit.ops_redundant_copy(p, a).ops)
    assert f"{a}-R" in p.units
    History(p).execute("arrange", edit.ops_arrange(p))
    assert edit.position_of(p, b)[0] == edit.lane_x(0)


# ---- B-15: edit operations fail with an EditError ------------------------------------------------


def test_edit_operations_with_unknown_ids_raise_edit_error() -> None:
    p = mini3()
    calls: list[Any] = [
        lambda: edit.ops_move_unit(p, "GHOST", 0, 0),
        lambda: edit.ops_complete_chain(p, "GHOST"),
        lambda: edit.ops_set_endpoint_connector(p, "GHOST", 0, "OBC-J01"),
        lambda: edit.ops_set_connector_part(p, "GHOST", "EX-MICROD-9-F"),
        lambda: edit.ops_update_interface(p, "GHOST", name="x"),
        lambda: edit.ops_update_unit(p, "GHOST", name="x"),
        lambda: edit.position_of(p, "GHOST"),
    ]
    for call in calls:
        with pytest.raises(edit.EditError, match="does not exist"):
            call()
    q = mini3()
    del q.config["generation"]
    with pytest.raises(edit.EditError, match="does not exist"):
        edit.ops_set_wire_colours(q, {"PWR": "red"})


def test_edit_operations_with_bad_input_raise_edit_error() -> None:
    p = mini3()
    with pytest.raises(edit.EditError, match="cannot be used as an ID"):
        edit.ops_rename_unit(p, "OBC", "bad id!")
    with pytest.raises(edit.EditError, match="cannot be used as an ID"):
        edit.ops_add_unit(p, "computer", unit_id="9bad")
    iid = next(iter(p.interfaces))
    with pytest.raises(edit.EditError, match="already used"):
        edit.ops_add_interface(p, p.interfaces[iid].type_id, "OBC", "RW1", interface_id=iid)
    for index in (-1, 5):
        with pytest.raises(edit.EditError, match="no end number"):
            edit.ops_set_endpoint_connector(p, iid, index, "OBC-J01")
    assert edit.unit_compat(p, "rs422", "GHOST").short == "Unknown device"
    free = [c.id for c in edit.free_connectors(p, "PCDU", "rs422")]
    with pytest.raises(edit.EditError, match="not a connector of OBC"):
        edit.ops_add_interface(p, "rs422", "OBC", "RW1", free[0] if free else "PCDU-J01", None)


def test_the_in_use_message_names_the_connector_id() -> None:
    p = mini3()
    used = next(
        e.connector_id for i in p.interfaces.values() for e in i.endpoints if e.connector_id
    )
    assert used is not None and used in edit.connector_compat(p, "rs422", used).why


def test_waive_reason_message_mentions_control_characters() -> None:
    from harness_design_studio.core import checks

    f = next(f for f in checks.find(sat15()) if f.can_waive)
    with pytest.raises(edit.EditError, match="control characters"):
        checks.waive_op(f, "long enough reason\x00")


# ---- B-20: the compatibility checks do not scan every interface for every connector --------------


class CountingDict(dict[str, Any]):
    scans = 0

    def values(self) -> Any:
        CountingDict.scans += 1
        return super().values()


def test_compat_checks_scan_the_interfaces_once_per_call() -> None:
    p = sat15()
    p.interfaces = CountingDict(p.interfaces)  # type: ignore[assignment]
    CountingDict.scans = 0
    units = sorted(p.units)
    for u in units:
        edit.unit_compat(p, "rs422", u)
    assert CountingDict.scans <= len(units)


def test_the_used_connector_index_follows_changes() -> None:
    p = sat15()
    type_id, a, b = next(
        (t, ua, ub)
        for t in sorted(p.interface_types)
        for ua in sorted(p.units)
        for ub in sorted(p.units)
        if ua < ub and edit.free_connectors(p, ua, t) and edit.free_connectors(p, ub, t)
    )
    target = edit.free_connectors(p, a, type_id)[0].id
    assert edit.connector_compat(p, type_id, target).ok
    ops, _ = edit.ops_add_interface(p, type_id, a, b, target, None)
    history = History(p)
    history.execute("add", ops)
    assert not edit.connector_compat(p, type_id, target).ok
    history.undo()
    assert edit.connector_compat(p, type_id, target).ok


# ---- B-22: pins of an interface that failed halfway are given back -------------------------------


def test_pins_of_an_interface_that_failed_halfway_are_free_for_the_next_one() -> None:
    p = sat15()
    serial, can = p.interface_types["rs422"], p.interface_types["can"]
    # rs422 needs four pins, the connector has five: A takes four, B (needs four) fails after
    # placing nothing it can keep; C (can, two pins) must then still find the remaining pin
    conn = Connector(
        id="A-J01", name="J01", role="box", part_id="EX-MICROD-9-F", unit_id="A",
        pins=[Pin(id=str(i)) for i in range(1, 6)],
    )  # fmt: skip
    long = evolve(serial, signals=[*serial.signals, *[SignalDef(name=f"X{k}") for k in range(2)]])
    res = allocate(conn, [Request("B", long), Request("C", can)], {}, 0)
    assert [m for i, m in res.errors] and res.errors[0][0] == "B"
    assert not [k for k in res.pins if k[0] == "B"]
    assert len([k for k in res.pins if k[0] == "C"]) == len(can.signals)
