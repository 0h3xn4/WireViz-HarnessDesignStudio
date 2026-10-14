"""Regression tests for the generation and KiCad findings of the October audit."""

from pathlib import Path

import pytest

from harness_design_studio.core import edit
from harness_design_studio.core.commands import History, SetConfig
from harness_design_studio.core.generate.engine import generate_project, plan_generation
from harness_design_studio.core.generate.explain import explain_wire
from harness_design_studio.core.kicad import (
    NetlistError,
    clean_net,
    parse_netlist,
    plan_netlist_import,
)
from harness_design_studio.core.model import ConfigFile, Pin, Project, evolve
from harness_design_studio.core.samples import mini3, sat15, sat15_full
from harness_design_studio.core.verify import verify_project
from tests.test_change_control import do_release, exported, releasable


def _pins_used_twice(p: Project) -> list[str]:
    seen: dict[tuple[str, str], str] = {}
    out = []
    for h in p.harnesses.values():
        for w in h.wires:
            for end in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
                box = next((c.mates_with for c in h.connectors if c.id == end[0]), None)
                if box:
                    key = (box, end[1])
                    if key in seen and seen[key] != w.interface_id and w.interface_id:
                        out.append(f"{box}.{end[1]}")
                    seen[key] = w.interface_id or ""
    return out


def test_a_released_interface_is_not_wired_a_second_time(tmp_path: Path) -> None:
    p = sat15_full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    iid = sorted(p.harnesses[hid].interfaces)[0]
    # what a hand edit or a merge can do: the interface moves into another group
    p.interfaces[iid] = evolve(p.interfaces[iid], redundancy="redundant")
    generate_project(p)
    owners = [h.id for h in p.harnesses.values() if iid in {w.interface_id for w in h.wires}]
    assert owners == [hid]
    assert not plan_generation(p).ops or all(
        type(o).__name__ == "SetGeneration" for o in plan_generation(p).ops
    )


def test_a_locked_generated_pin_keeps_its_wire() -> None:
    p = sat15()
    generate_project(p)
    box = next(c for c in p.connectors.values() if any(x.interface_id for x in c.pins))
    pin = next(x for x in box.pins if x.interface_id and x.signal)
    p.connectors[box.id] = evolve(
        box, pins=[evolve(x, locked=True) if x.id == pin.id else x for x in box.pins]
    )
    generate_project(p)
    after = next(x for x in p.connectors[box.id].pins if x.id == pin.id)
    assert (after.interface_id, after.signal, after.locked) == (pin.interface_id, pin.signal, True)
    used = [
        x
        for x in p.connectors[box.id].pins
        if (x.interface_id, x.signal) == (pin.interface_id, pin.signal)
    ]
    assert len(used) == 1  # not stranded: the signal is on one pin only
    assert verify_project(p).ok


def test_a_locked_pin_of_a_deleted_interface_is_released() -> None:
    p = sat15()
    generate_project(p)
    box = next(c for c in p.connectors.values() if any(x.interface_id for x in c.pins))
    pin = next(x for x in box.pins if x.interface_id)
    p.connectors[box.id] = evolve(
        box, pins=[evolve(x, locked=True) if x.id == pin.id else x for x in box.pins]
    )
    History(p).execute("del", edit.ops_delete_interface(p, pin.interface_id or ""))
    generate_project(p)
    after = next(x for x in p.connectors[box.id].pins if x.id == pin.id)
    assert after.interface_id is None


def _naming(p: Project, **values: str) -> None:
    History(p).execute(
        "naming", [SetConfig(ConfigFile(name="naming", placeholder=False, values=values))]
    )


def test_a_harness_template_without_a_number_does_not_hang_and_is_reported() -> None:
    import signal

    def alarm(*_a: object) -> None:
        raise AssertionError("generation did not finish")

    previous = signal.signal(signal.SIGALRM, alarm)
    signal.alarm(20)
    try:
        p = sat15()
        _naming(p, harness="HARN")
        plan = plan_generation(p)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
    assert any(f.code == "naming" for f in plan.report.findings)
    assert len(plan.harnesses) > 1


def test_wire_and_connector_templates_cannot_make_duplicate_ids() -> None:
    p = sat15()
    _naming(p, wire="w{n}", cable_connector="P{n}")
    generate_project(p)
    wires = [w.id for h in p.harnesses.values() for w in h.wires]
    cables = [c.id for h in p.harnesses.values() for c in h.connectors]
    assert len(wires) == len(set(wires)) and len(cables) == len(set(cables))
    assert verify_project(p).ok


def test_generating_again_is_a_no_op_even_when_a_group_makes_no_wires() -> None:
    from harness_design_studio.core.commands import apply_ops

    p = sat15()
    generate_project(p)
    tid = p.interfaces[sorted(p.interfaces)[0]].type_id
    p.interface_types[tid] = evolve(p.interface_types[tid], signals=[])  # a group without wires
    numbers = []
    for _ in range(3):
        plan = plan_generation(p)
        numbers.append(plan.record.next_harness_number)
        apply_ops(p, plan.ops)
    assert len(set(numbers)) == 1  # no number is used up per run
    assert plan_generation(p).ops == []


def test_released_wires_keep_their_explanation_after_regenerating(tmp_path: Path) -> None:
    p = sat15_full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    h = p.harnesses[hid]
    w = h.wires[0]
    before = explain_wire(p, h, w)
    assert before
    generate_project(p)
    assert explain_wire(p, p.harnesses[hid], w) == before


def test_zone_names_with_the_key_separator_stay_apart() -> None:
    from harness_design_studio.core.generate.segmentation import segment

    p = sat15()
    History(p).execute(
        "mode",
        [
            SetConfig(
                ConfigFile(name="segmentation", placeholder=False, values={"mode": "per_zone_pair"})
            )
        ],
    )
    keys = [g.key for g in segment(p).groups]
    assert len(keys) == len(set(keys))
    for u in list(p.units.values())[:2]:
        p.units[u.id] = evolve(u, zone="a|b")
    groups = segment(p).groups
    assert all(g.zones is not None for g in groups)
    assert len({g.key for g in groups}) == len(groups)


def test_the_default_gauge_is_used_when_there_is_no_current_to_size_for() -> None:
    p = sat15()
    History(p).execute(
        "gauge",
        [
            SetConfig(
                ConfigFile(
                    name="generation",
                    placeholder=False,
                    values={**p.config["generation"].values, "default_gauge_awg": 24},
                )
            )
        ],
    )
    generate_project(p)
    signal_wires = [
        w
        for h in p.harnesses.values()
        for w in h.wires
        if w.interface_id and p.interfaces[w.interface_id].max_current_a is None
    ]
    assert signal_wires and all(w.gauge_awg == 24 for w in signal_wires)


def test_mixed_classes_on_one_connector_pair_are_reported() -> None:
    from harness_design_studio.core.generate.segmentation import segment

    p = mini3()
    History(p).execute(
        "seg",
        [
            SetConfig(
                ConfigFile(
                    name="segregation",
                    placeholder=False,
                    values={"category_pairs_to_separate": [["data", "discrete"]]},
                )
            )
        ],
    )
    base = p.interfaces["IF-TM-RW1"]
    for n, t in (("IF-X1", "rs422"), ("IF-X2", "discrete")):
        eps = [
            evolve(base.endpoints[0], connector_id="OBC-J01"),
            evolve(base.endpoints[1], unit_id="PCDU", connector_id="PCDU-J03"),
        ]
        p.interfaces[n] = evolve(base, id=n, type_id=t, endpoints=eps)
    assert any("mixes interface classes" in n for n in segment(p).notes)


# ---- fixed pins ---------------------------------------------------------------------------------


def _fixed_project() -> Project:
    p = mini3()
    box = p.connectors["OBC-J01"]  # carries IF-TM-RW1 (RS-422) on pins in the order TX+ TX- RX+ RX-
    named = {"1": "RX-", "2": "RX+", "3": "TX-", "4": "TX+"}
    pins = [
        Pin(id=x.id, signal=named[x.id], fixed=True) if x.id in named else Pin(id=x.id)
        for x in box.pins
    ]
    p.connectors["OBC-J01"] = evolve(box, pins=pins)
    return p


def test_fixed_pins_decide_where_each_signal_goes() -> None:
    p = _fixed_project()
    generate_project(p)
    used = {x.signal: x.id for x in p.connectors["OBC-J01"].pins if x.interface_id == "IF-TM-RW1"}
    assert used == {"RX-": "1", "RX+": "2", "TX-": "3", "TX+": "4"}
    assert verify_project(p).ok


def test_a_new_interface_never_lands_on_unnamed_pins_of_a_fixed_connector() -> None:
    p = _fixed_project()
    generate_project(p)
    first = {x.signal: x.id for x in p.connectors["OBC-J01"].pins if x.interface_id == "IF-TM-RW1"}
    # a second RS-422 needs four more named pins; there are none, so it is an error, not pin 5
    base = p.interfaces["IF-TM-RW1"]
    p.interfaces["IF-X"] = evolve(
        base,
        id="IF-X",
        endpoints=[
            evolve(base.endpoints[0], connector_id="OBC-J01"),
            evolve(base.endpoints[1], unit_id="PCDU", connector_id="PCDU-J03"),
        ],
    )
    plan = plan_generation(p)
    assert any(f.code == "pin_allocation" and f.object_id == "IF-X" for f in plan.report.findings)
    again = {x.signal: x.id for x in p.connectors["OBC-J01"].pins if x.interface_id == "IF-TM-RW1"}
    assert again == first


def test_a_fixed_pin_without_a_signal_is_never_given_to_an_interface() -> None:
    p = mini3()
    box = p.connectors["OBC-J01"]
    p.connectors["OBC-J01"] = evolve(
        box, pins=[evolve(x, fixed=True) if x.id == "1" else x for x in box.pins]
    )
    generate_project(p)
    pins = {x.id: x for x in p.connectors["OBC-J01"].pins}
    assert pins["1"].interface_id is None  # B-22: it used to carry the interface without a signal
    assert {x.id for x in pins.values() if x.interface_id == "IF-TM-RW1"} == {"2", "3", "4", "5"}
    assert verify_project(p).ok


def test_a_branch_template_cannot_give_a_branch_the_id_of_a_cable_connector() -> None:
    p = sat15()
    names = ConfigFile(name="naming", placeholder=False, values={"branch": "{harness}-P{n}"})
    mode = ConfigFile(name="segmentation", placeholder=False, values={"mode": "per_zone_pair"})
    History(p).execute("naming", [SetConfig(names), SetConfig(mode)])
    generate_project(p)
    branches = [(h, b.id) for h in p.harnesses.values() for b in h.branch_points]
    assert branches  # B-22: the branch used to be W001-P1, the id of the first cable connector
    assert all(b not in {c.id for c in h.connectors} for h, b in branches)
    assert verify_project(p).ok


# ---- KiCad ------------------------------------------------------------------------------------

NET = (
    b'(export (version "E") (components'
    b' (comp (ref "J1") (value "C") (footprint "F"))) (nets'
    b' (net (code "1") (name "{name}") (node (ref "J1") (pin "{pin}") (pintype "passive")))))'
)


def _net(name: str = "/CAN_H", pin: str = "1") -> bytes:
    return NET.replace(b"{name}", name.encode()).replace(b"{pin}", pin.encode())


@pytest.mark.parametrize(
    "raw,want",
    [
        ("/sub/Net-(J1-Pad2)", None),
        ("/sub/unconnected-(J1-Pad3)", None),
        ("/sub/28V", "28V"),
        ("A/B", "A/B"),
        ("/Net-(J1-Pad9)", None),
        ("GND", "GND"),
    ],
)
def test_sub_sheet_unnamed_nets_are_not_signals(raw: str, want: str | None) -> None:
    assert clean_net(raw) == want


def test_a_byte_order_mark_and_utf16_are_read() -> None:
    assert "J1" in parse_netlist(b"\xef\xbb\xbf" + _net()).components
    assert "J1" in parse_netlist(b"\xff\xfe" + _net().decode().encode("utf-16-le")).components


def test_unknown_xml_encoding_is_a_netlist_error() -> None:
    with pytest.raises(NetlistError):
        parse_netlist(b'<?xml version="1.0" encoding="nope"?><export/>')


def test_duplicate_references_are_refused() -> None:
    dup = b'(export (components (comp (ref "J1")) (comp (ref "J1"))) (nets))'
    with pytest.raises(NetlistError):
        parse_netlist(dup)


def test_bad_pin_numbers_names_and_pin_counts_are_row_errors_not_crashes() -> None:
    p = mini3()
    part = next(x for x in p.parts.values() if x.category == "connector" and x.pin_count)
    for name, pin, why in (
        ("/CAN_H", "1.", "Pin number"),
        ("/" + "x" * 300, "1", "net name"),
        ("/CAN_H", str((part.pin_count or 0) + 5), "has only"),
    ):
        plan = plan_netlist_import(p, parse_netlist(_net(name, pin)), "OBC", parts={"J1": part.id})
        assert not plan.rows[0].ok and why in plan.rows[0].message, (why, plan.rows[0])


# ---- segregation settings behave as documented (B-17) -------------------------------------------


def _three_between_obc_and_rw1(**segregation: object) -> Project:
    p = mini3()
    set_seg = ConfigFile(name="segregation", placeholder=False, values=dict(segregation))
    History(p).execute("seg", [SetConfig(set_seg)])
    base = p.interfaces["IF-TM-RW1"]
    for n, t, chain in (
        ("IF-X1", "rs422", "nominal"),
        ("IF-X2", "discrete", "nominal"),
        ("IF-X3", "analog", "nominal"),
        ("IF-X4", "rs485", "redundant"),
    ):
        p.interfaces[n] = evolve(base, id=n, type_id=t, redundancy=chain)
    del p.interfaces["IF-TM-RW1"]
    return p


def _group_ids(p: Project, mode: str) -> list[list[str]]:
    from harness_design_studio.core.generate.segmentation import segment

    set_mode = ConfigFile(name="segmentation", placeholder=False, values={"mode": mode})
    History(p).execute("mode", [SetConfig(set_mode)])
    return sorted(sorted(g.interface_ids) for g in segment(p).groups)


def test_nominal_and_redundant_may_share_a_harness_when_the_setting_is_off() -> None:
    kept = _group_ids(
        _three_between_obc_and_rw1(forbid_nominal_with_redundant=True), "per_connector_pair"
    )
    assert kept == [["IF-X1", "IF-X2", "IF-X3"], ["IF-X4"]]
    mixed = _group_ids(
        _three_between_obc_and_rw1(forbid_nominal_with_redundant=False), "per_connector_pair"
    )
    assert mixed == [["IF-X1", "IF-X2", "IF-X3", "IF-X4"]]


def test_only_the_listed_category_pairs_are_kept_apart() -> None:
    pairs = [["data", "discrete"]]
    got = _group_ids(_three_between_obc_and_rw1(category_pairs_to_separate=pairs), "per_unit_pair")
    # analog is in no pair and stays with the data interface; only discrete is separated from data
    assert got == [["IF-X1", "IF-X3"], ["IF-X2"], ["IF-X4"]]


def test_category_pairs_with_a_chain_of_conflicts_keep_every_pair_apart() -> None:
    pairs = [["data", "discrete"], ["discrete", "analog"]]
    got = _group_ids(_three_between_obc_and_rw1(category_pairs_to_separate=pairs), "per_unit_pair")
    assert got == [["IF-X1", "IF-X3"], ["IF-X2"], ["IF-X4"]]  # data and analog may share


def test_the_mass_table_says_what_the_mass_covers() -> None:
    # B-21: "Complete: yes" must not read as a claim about shielding, sleeving or backshells
    from harness_design_studio.core.outputs.tables import mass_length

    p = sat15()
    header = mass_length(p, sorted(p.harnesses.values(), key=lambda h: h.id))[0]
    assert header[5] == "Mass of wires and cable connectors (g)"


# ---- the explanations say only what was decided (B-16) -------------------------------------------


def _explained(p: Project, signal: str) -> list[str]:
    lines = [
        line
        for h in p.harnesses.values()
        for w in h.wires
        if w.signal == signal
        for line in explain_wire(p, h, w)
    ]
    assert lines, signal
    return lines


def test_a_passive_signal_is_not_said_to_be_driven_by_an_end() -> None:
    p = sat15()
    generate_project(p)
    pwr = [line for line in _explained(p, "PWR") if line.startswith("wiring:")]
    assert pwr and all("drives" not in line for line in pwr)
    tx = [line for line in _explained(p, "TX+/RX+") if line.startswith("wiring:")]
    assert tx and all("drives)" in line for line in tx)


def test_the_pin_lines_of_a_wire_name_the_connector_they_are_about() -> None:
    p = mini3()
    generate_project(p)
    h = next(h for h in p.harnesses.values() if any(w.signal == "TX+/RX+" for w in h.wires))
    w = next(w for w in h.wires if w.signal == "TX+/RX+")
    lines = [x for x in explain_wire(p, h, w) if "pin-allocation:" in x]
    assert len(lines) == 2 and len(set(lines)) == 2
    assert lines[0].startswith("OBC-J01 pin ") and lines[1].startswith("RW1-J02 pin ")


def test_a_locked_pin_keeps_its_reason_in_the_explanation() -> None:
    p = mini3()
    generate_project(p)
    box = p.connectors["OBC-J01"]
    pin = next(x for x in box.pins if x.interface_id == "IF-TM-RW1")
    p.connectors["OBC-J01"] = evolve(
        box, pins=[evolve(x, locked=True) if x.id == pin.id else x for x in box.pins]
    )
    generate_project(p)
    text = " ".join(_explained(p, "TX+/RX+"))
    assert f"stays on pin {pin.id} because the pin is locked" in text


def test_a_missing_mating_part_is_not_explained_as_mating_with_itself() -> None:
    p = mini3()
    part_id = p.connectors["OBC-J01"].part_id
    p.parts[part_id] = evolve(p.parts[part_id], mates_with=None)
    generate_project(p)
    lines = [
        line
        for key, v in p.generation.provenance.items()  # type: ignore[union-attr]
        for line in v
        if key.startswith("connector:") and "mating:" in line
    ]
    assert lines and not any(f"part {part_id} mates with {part_id}" in line for line in lines)
    assert any("no mating part" in line for line in lines)
