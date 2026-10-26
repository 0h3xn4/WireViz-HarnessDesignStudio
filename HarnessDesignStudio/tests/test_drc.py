"""M4: every design rule has a positive test (it fires) and a negative test (it stays quiet)."""

import time
from collections.abc import Callable

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import checks, drc, edit
from harness_design_studio.core.commands import History, Put, apply_ops
from harness_design_studio.core.drc.report import render_markdown, stale_waivers
from harness_design_studio.core.drc.rules import RULES
from harness_design_studio.core.generate.engine import generate_project, plan_generation
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import (
    Harness,
    Pin,
    Project,
    Segment,
    Wire,
    evolve,
)
from harness_design_studio.core.model.config import ConfigFile
from harness_design_studio.core.samples import sat15, stress_project
from tests.helpers import time_limit

_BASE: Project | None = None


def base() -> Project:
    """A generated sat15 (built once); each test gets its own shallow copy."""
    global _BASE
    if _BASE is None:
        _BASE = sat15()
        generate_project(_BASE)
    return edit.clone_with(_BASE, [])


def set_cfg(p: Project, name: str, **values: object) -> None:
    old = p.config[name]
    p.config[name] = ConfigFile(
        name=name, placeholder=old.placeholder, values={**old.values, **values}
    )


def put_harness(p: Project, h: Harness, **kw: object) -> Harness:
    new = evolve(h, **kw)
    apply_ops(p, [Put("harnesses", new)])
    return new


def harness_with_category(p: Project, category: str) -> Harness:
    for h in sorted(p.harnesses.values(), key=lambda x: x.id):
        if h.generated and any(
            p.interface_types[p.interfaces[i].type_id].category == category for i in h.interfaces
        ):
            return h
    raise AssertionError(category)


def interface_of(p: Project, category: str, *, redundancy: str = "nominal") -> str:
    for i in sorted(p.interfaces.values(), key=lambda x: x.id):
        if p.interface_types[i.type_id].category == category and i.redundancy == redundancy:
            return i.id
    raise AssertionError(category)


def harness_with_real_shield(p: Project) -> Harness:
    """A harness with a shield that exists (a plain twisted pair has none)."""
    return next(
        h
        for h in sorted(p.harnesses.values(), key=lambda x: x.id)
        if any(s.kind != "twisted_pair" for s in h.shields)
    )


def wire_of(p: Project, category: str) -> tuple[Harness, Wire]:
    h = harness_with_category(p, category)
    w = next(
        w
        for w in h.wires
        if p.interface_types[p.interfaces[w.interface_id or ""].type_id].category == category
    )
    return h, w


def retarget_wire(p: Project, h: Harness, w: Wire, interface_id: str) -> None:
    put_harness(
        p, h, wires=[evolve(x, interface_id=interface_id) if x.id == w.id else x for x in h.wires]
    )


def full_config(p: Project) -> None:
    set_cfg(p, "derating", ampacity_a_by_awg={"24": 2.0, "20": 5.0, "18": 7.0},
            bundle_derating=0.5, temperature_derating=1.0, contact_current_factor=0.5,
            max_voltage_drop_v=1000.0, spare_pin_fraction=0.0)  # fmt: skip
    set_cfg(p, "generation", conductor_resistivity_ohm_m=1.7e-8, shield_end_a="backshell_360",
            shield_end_b="floating")  # fmt: skip
    set_cfg(p, "segregation", category_pairs_to_separate=[["power", "analog"]])
    set_cfg(p, "emc", conflicting_class_pairs=[["A", "B"]])


def fire(rule_id: str, p: Project) -> list[checks.Finding]:
    rule = next(r for r in RULES if r.id == rule_id)
    return rule.run(p)


# Test-only numbers below exercise the arithmetic; they are not engineering data.


def pos_duplicate_id() -> Project:
    p = base()
    h = next(iter(p.harnesses.values()))
    box = next(iter(p.connectors.values()))
    put_harness(p, h, connectors=[*h.connectors, evolve(h.connectors[0], id=box.id)])
    return p


def pos_wire_dangling() -> Project:
    p = base()
    h, w = wire_of(p, "data")
    put_harness(
        p, h, wires=[evolve(x, to_connector="NOPE") if x.id == w.id else x for x in h.wires]
    )
    return p


def pos_model_inconsistent() -> Project:
    p = base()
    c = next(c for c in p.connectors.values() if c.pins)
    pins = [evolve(c.pins[0], interface_id="GONE"), *c.pins[1:]]
    apply_ops(p, [Put("connectors", evolve(c, pins=pins))])
    return p


def pos_signal_unassigned() -> Project:
    p = base()
    h, w = wire_of(p, "data")
    i = p.interfaces[w.interface_id or ""]
    c = p.connectors[i.endpoints[0].connector_id or ""]
    pins = [
        evolve(x, signal=None, interface_id=None) if x.interface_id == i.id else x for x in c.pins
    ]
    apply_ops(p, [Put("connectors", evolve(c, pins=pins))])
    return p


def pos_pin_floating() -> Project:
    p = base()
    h = next(h for h in p.harnesses.values() if h.generated)
    c = h.connectors[0]
    extra = Pin(id="Z9", signal="LOOSE")
    conns = [evolve(c, pins=[*c.pins, extra]), *h.connectors[1:]]
    put_harness(p, h, connectors=conns)
    return p


def pos_pin_shared() -> Project:
    p = base()
    h = next(h for h in p.harnesses.values() if h.generated)
    w = h.wires[0]
    twin = evolve(
        w, id="W-SHARED", signal=None, interface_id=None, manual=True, from_pin=w.from_pin,
        to_pin=h.wires[1].to_pin if h.wires[1].to_connector == w.to_connector else w.to_pin,
    )  # fmt: skip
    put_harness(p, h, wires=[*h.wires, twin])
    return p


def pos_mate_mismatch() -> Project:
    p = base()
    h = next(h for h in p.harnesses.values() if h.generated)
    c = h.connectors[0]
    box = p.connectors[c.mates_with or ""]
    apply_ops(p, [Put("connectors", evolve(box, gender="male"))])  # sample units have no gender yet
    put_harness(p, h, connectors=[evolve(c, gender="male"), *h.connectors[1:]])
    return p


def pos_direction_conflict() -> Project:
    p = base()
    h = next(
        x
        for x in sorted(p.harnesses.values(), key=lambda x: x.id)
        if any("/" in (w.signal or "") for w in x.wires)
    )
    w = next(w for w in h.wires if "/" in (w.signal or ""))
    src = next(c for c in h.connectors if c.id == w.from_connector)
    dst = next(c for c in h.connectors if c.id == w.to_connector)
    src_sig = next(x.signal for x in p.connectors[src.mates_with or ""].pins if x.id == w.from_pin)
    box = p.connectors[dst.mates_with or ""]
    pins = [evolve(x, signal=src_sig) if x.id == w.to_pin else x for x in box.pins]
    apply_ops(p, [Put("connectors", evolve(box, pins=pins))])
    return p


def pos_current_over_contact() -> Project:
    p = base()
    full_config(p)
    i = p.interfaces[interface_of(p, "power")]
    apply_ops(p, [Put("interfaces", evolve(i, max_current_a=3.0))])
    for cid in [e.connector_id or "" for e in i.endpoints]:
        part = p.parts[p.connectors[cid].part_id]
        apply_ops(p, [Put("parts", evolve(part, ratings={"contact_current_a": 5.0}))])
    return p


def pos_current_over_wire() -> Project:
    p = base()
    full_config(p)
    h, w = wire_of(p, "power")
    i = p.interfaces[w.interface_id or ""]
    apply_ops(p, [Put("interfaces", evolve(i, max_current_a=10.0))])
    put_harness(p, h, wires=[evolve(x, gauge_awg=20) if x.id == w.id else x for x in h.wires])
    return p


def pos_voltage_drop() -> Project:
    p = base()
    full_config(p)
    set_cfg(p, "derating", max_voltage_drop_v=0.1)
    h, w = wire_of(p, "power")
    i = p.interfaces[w.interface_id or ""]
    apply_ops(p, [Put("interfaces", evolve(i, max_current_a=3.0))])
    put_harness(
        p, h, wires=[evolve(x, gauge_awg=20, length_m=10.0) if x.id == w.id else x for x in h.wires]
    )
    return p


def pos_spare_pins_low() -> Project:
    p = base()
    set_cfg(p, "derating", spare_pin_fraction=1.0)
    return p


def pos_shield_unterminated() -> Project:
    p = base()
    set_cfg(p, "generation", shield_end_a="backshell_360", shield_end_b="floating")
    h = harness_with_real_shield(p)
    put_harness(p, h, shields=[evolve(s, end_a="floating", end_b="floating") for s in h.shields])
    return p


def pos_shield_wrong_end() -> Project:
    p = base()
    set_cfg(p, "generation", shield_end_a="backshell_360", shield_end_b="floating")
    h = harness_with_real_shield(p)
    put_harness(
        p, h, shields=[evolve(s, end_a="floating", end_b="backshell_360") for s in h.shields]
    )
    return p


def pos_chains_mixed() -> Project:
    p = base()
    h, w = wire_of(p, "power")
    other = next(i.id for i in p.interfaces.values() if i.redundancy == "redundant")
    retarget_wire(p, h, w, other)
    return p


def pos_pyro_mixed() -> Project:
    p = base()
    h, w = wire_of(p, "discrete")
    itype = p.interface_types[p.interfaces[w.interface_id or ""].type_id]
    apply_ops(p, [Put("interface_types", evolve(itype, category="pyro"))])
    retarget_wire(p, h, w, interface_of(p, "power"))
    return p


def pos_category_mixed() -> Project:
    p = base()
    set_cfg(p, "segregation", category_pairs_to_separate=[["power", "data"]])
    h, w = wire_of(p, "power")
    retarget_wire(p, h, w, interface_of(p, "data"))
    return p


def pos_emc_mixed() -> Project:
    p = base()
    set_cfg(p, "emc", conflicting_class_pairs=[["A", "B"]])
    h, w = wire_of(p, "power")
    other = interface_of(p, "data")
    t_power = p.interface_types[p.interfaces[w.interface_id or ""].type_id]
    t_data = p.interface_types[p.interfaces[other].type_id]
    apply_ops(p, [Put("interface_types", evolve(t_power, emc_class="A")),
                  Put("interface_types", evolve(t_data, emc_class="B"))])  # fmt: skip
    retarget_wire(p, h, w, other)
    return p


def pos_released_modified() -> Project:
    p = base()
    h = next(x for x in p.harnesses.values() if x.generated)
    put_harness(p, h, status="released")  # released but no baseline
    return p


def pos_config_invalid() -> Project:
    p = base()
    set_cfg(p, "derating", bundle_derating=7)
    return p


def pos_lookalike() -> Project:
    return base()


def pos_unapproved() -> Project:
    return base()


def pos_unchecked() -> Project:
    return base()


def pos_segment_loop() -> Project:
    p = base()
    h = next(x for x in sorted(p.harnesses.values(), key=lambda x: x.id) if x.generated)
    a, b = h.connectors[0].id, h.connectors[1].id
    segs = [Segment(id="S1", from_node=a, to_node="BP1"), Segment(id="S2", from_node="BP1", to_node=b),
            Segment(id="S3", from_node=b, to_node=a)]  # fmt: skip
    put_harness(p, h, segments=segs)
    return p


def neg_all_clean(rule_id: str) -> Project:
    """A project where `rule_id` has nothing to report."""
    p = base()
    full_config(p)
    if rule_id == "part-unapproved":
        for part in list(p.parts.values()):
            apply_ops(p, [Put("parts", evolve(part, approval="approved", unverified=False))])
    if rule_id == "connector-lookalike":
        for c in list(p.connectors.values()):
            apply_ops(p, [Put("connectors", evolve(c, keying=c.id))])
    if rule_id in ("shield-unterminated", "shield-wrong-end"):
        for h in list(p.harnesses.values()):
            put_harness(
                p,
                h,
                shields=[evolve(s, end_a="backshell_360", end_b="floating") for s in h.shields],
            )
    return p


# ---- rules from the supplied standards (D-131); the numbers below are test inputs ---------------


def set_part(p: Project, part_id: str, **ratings: float) -> None:
    part = p.parts[part_id]
    apply_ops(p, [Put("parts", evolve(part, ratings={**part.ratings, **ratings}))])


def pos_connector_voltage() -> Project:
    p = base()
    set_cfg(p, "derating", connector_voltage_factor_rated=0.75)
    h, w = wire_of(p, "power")
    i = p.interfaces[w.interface_id or ""]
    apply_ops(p, [Put("interfaces", evolve(i, voltage_v=100.0))])
    conn = p.connectors[i.endpoints[0].connector_id or ""]
    set_part(p, conn.part_id, rated_voltage_v=50.0)
    return p


def pos_wire_voltage() -> Project:
    p = base()
    set_cfg(p, "derating", wire_voltage_factor=0.5)
    h, w = wire_of(p, "power")
    i = p.interfaces[w.interface_id or ""]
    apply_ops(p, [Put("interfaces", evolve(i, voltage_v=40.0))])
    set_part(p, w.part_id or "", rated_voltage_v=50.0)
    return p


def pos_temperature_margin() -> Project:
    p = base()
    set_cfg(p, "derating", max_ambient_temperature_c=100.0, connector_temperature_margin_c=30.0)
    h, w = wire_of(p, "power")
    i = p.interfaces[w.interface_id or ""]
    conn = p.connectors[i.endpoints[0].connector_id or ""]
    set_part(p, conn.part_id, max_temp_c=120.0)
    return p


def pos_mating_cycles() -> Project:
    p = base()
    set_cfg(p, "derating", max_mating_cycles=50)
    h, w = wire_of(p, "power")
    i = p.interfaces[w.interface_id or ""]
    set_part(p, p.connectors[i.endpoints[0].connector_id or ""].part_id, mating_cycles=20.0)
    return p


def pos_connector_manufacturer() -> Project:
    p = base()
    h = next(h for h in sorted(p.harnesses.values(), key=lambda x: x.id) if h.connectors)
    cable = h.connectors[0]
    box = p.connectors[cable.mates_with or ""]
    for pid, name in ((cable.part_id, "Maker A"), (box.part_id, "Maker B")):
        apply_ops(p, [Put("parts", evolve(p.parts[pid], manufacturer=name))])
    return p


def pos_wire_specification() -> Project:
    p = base()
    h, w = wire_of(p, "power")
    apply_ops(
        p, [Put("parts", evolve(p.parts[w.part_id or ""], approval="approved", specification=None))]
    )
    return p


def pos_power_return_adjacent() -> Project:
    p = base()
    set_cfg(p, "generation", power_return_gap_pins=1)
    return p


def pos_bundle_current() -> Project:
    p = base()
    full_config(p)
    set_cfg(p, "derating", bundle_factor_by_count={"1": 1.0, "10": 0.5, "300": 0.12})
    h, w = wire_of(p, "power")
    i = p.interfaces[w.interface_id or ""]
    apply_ops(p, [Put("interfaces", evolve(i, max_current_a=4.0))])
    put_harness(p, h, wires=[evolve(x, gauge_awg=20) if x.id == w.id else x for x in h.wires])
    return p


def pos_shield_bonding() -> Project:
    p = base()
    set_cfg(p, "emc", shield_bonding="both_ends_backshell")
    h = harness_with_real_shield(p)
    put_harness(p, h, shields=[evolve(s, end_a="pigtail", end_b="floating") for s in h.shields])
    return p


def pos_shield_parts() -> Project:
    p = base()
    set_cfg(p, "emc", shield_bonding="both_ends_backshell")
    h = harness_with_real_shield(p)
    set_part(p, h.connectors[0].part_id, conductive_finish=0.0)
    return p


def pos_emc_class_split() -> Project:
    p = base()
    set_cfg(p, "emc", same_class_one_bundle=True)
    for tid in {
        i.type_id
        for i in p.interfaces.values()
        if {e.unit_id for e in i.endpoints} == {"OBC1", "PCDU1"}
    }:
        apply_ops(p, [Put("interface_types", evolve(p.interface_types[tid], emc_class="A"))])
    return p


# REQ-DRC-05: the four rules that review connections (link-unpaired, link-direction,
# link-signal-mismatch, link-power-return) have a positive case here and stay quiet on a clean project.
def _linked(a: str, b: str, pairs: list[tuple[str, str]]) -> Project:
    from harness_design_studio.core.model import Link, PinPair
    from tests.helpers import pinout_project

    p: Project = pinout_project()
    p.links["L1"] = Link(
        id="L1", a_connector=a, b_connector=b, pairs=[PinPair(a_pin=x, b_pin=y) for x, y in pairs]
    )
    return p


def pos_link_unpaired() -> Project:
    return _linked("OBC-J01", "RW1-J02", [("2", "4"), ("3", "1"), ("4", "2")])  # TX+ left out


def pos_link_direction() -> Project:
    return _linked("OBC-J01", "RW1-J02", [("1", "1"), ("2", "4"), ("3", "1")])  # TX+ with TX+


def pos_link_signal_mismatch() -> Project:
    return _linked("OBC-J01", "RW1-J02", [("1", "2")])  # TX+ with TX-


def pos_link_power_return() -> Project:
    return _linked("PCDU-J02", "OBC-J02", [("1", "1")])  # PWR and no RTN


POSITIVE: dict[str, Callable[[], Project]] = {
    "link-unpaired": pos_link_unpaired,
    "link-direction": pos_link_direction,
    "link-signal-mismatch": pos_link_signal_mismatch,
    "link-power-return": pos_link_power_return,
    "duplicate-id": pos_duplicate_id,
    "wire-dangling": pos_wire_dangling,
    "model-inconsistent": pos_model_inconsistent,
    "signal-unassigned": pos_signal_unassigned,
    "pin-floating": pos_pin_floating,
    "pin-shared": pos_pin_shared,
    "mate-mismatch": pos_mate_mismatch,
    "direction-conflict": pos_direction_conflict,
    "current-over-contact": pos_current_over_contact,
    "current-over-wire": pos_current_over_wire,
    "voltage-drop": pos_voltage_drop,
    "spare-pins-low": pos_spare_pins_low,
    "shield-unterminated": pos_shield_unterminated,
    "shield-wrong-end": pos_shield_wrong_end,
    "chains-mixed": pos_chains_mixed,
    "pyro-mixed": pos_pyro_mixed,
    "category-mixed": pos_category_mixed,
    "emc-mixed": pos_emc_mixed,
    "config-invalid": pos_config_invalid,
    "released-modified": pos_released_modified,
    "connector-lookalike": pos_lookalike,
    "part-unapproved": pos_unapproved,
    "unchecked-config": pos_unchecked,
    "segment-loop": pos_segment_loop,
    "connector-voltage": pos_connector_voltage,
    "wire-voltage": pos_wire_voltage,
    "temperature-margin": pos_temperature_margin,
    "mating-cycles": pos_mating_cycles,
    "connector-manufacturer": pos_connector_manufacturer,
    "wire-specification": pos_wire_specification,
    "power-return-adjacent": pos_power_return_adjacent,
    "bundle-current": pos_bundle_current,
    "shield-bonding": pos_shield_bonding,
    "shield-parts": pos_shield_parts,
    "emc-class-split": pos_emc_class_split,
}


def test_every_rule_has_a_positive_case_and_unique_id() -> None:
    ids = [r.id for r in RULES]
    assert len(ids) == len(set(ids))
    assert set(POSITIVE) == set(ids)


@pytest.mark.parametrize("rule_id", [r.id for r in RULES])
def test_rule_fires_on_a_violation(rule_id: str) -> None:
    found = fire(rule_id, POSITIVE[rule_id]())
    assert found, rule_id
    rule = next(r for r in RULES if r.id == rule_id)
    for f in found:
        assert f.rule == rule_id and f.severity == rule.severity
        assert f.title and f.why and f.object_id
        assert f.can_waive == (rule.severity == "warning")


@pytest.mark.parametrize("rule_id", [r.id for r in RULES])
def test_rule_stays_quiet_on_a_clean_project(rule_id: str) -> None:
    assert fire(rule_id, neg_all_clean(rule_id)) == [], rule_id


def test_clean_negative_cases_do_not_mask_other_rules() -> None:
    """With the full test configuration the unmodified sample has no design rule errors."""
    p = neg_all_clean("none")
    apply_ops(p, plan_generation(p).ops)  # the test configuration changed generation inputs
    assert not [f for f in drc.run(p) if f.severity == "error"]


def test_verifier_mismatch_surfaces_as_error_with_fix() -> None:
    p = base()
    h = next(x for x in p.harnesses.values() if x.generated and len(x.wires) > 1)
    put_harness(p, h, wires=h.wires[1:])
    found = [f for f in drc.run(p) if f.rule == "verify-mismatch"]
    assert found and found[0].severity == "error" and not found[0].can_waive
    ops, message = checks.fix_ops(p, found[0])
    History(p).execute("fix", ops)
    assert not [f for f in drc.run(p) if f.rule == "verify-mismatch"]
    assert "Regenerated" in message


def test_one_click_fix_for_unassigned_signal() -> None:
    p = pos_signal_unassigned()
    f = next(x for x in drc.run(p) if x.rule == "signal-unassigned")
    assert f.fix_label
    ops, _ = checks.fix_ops(p, f)
    History(p).execute("fix", ops)
    assert not [x for x in drc.run(p) if x.rule == "signal-unassigned"]


def test_fix_refuses_when_regeneration_would_change_nothing() -> None:
    p = base()
    f = checks.Finding("verify-mismatch.x", "verify-mismatch", "error", "x", "t", "w")
    with pytest.raises(edit.EditError):
        checks.fix_ops(p, f)


def test_rules_without_fix_say_so() -> None:
    p = pos_mate_mismatch()
    f = next(x for x in drc.run(p) if x.rule == "mate-mismatch")
    with pytest.raises(edit.EditError):
        checks.fix_ops(p, f)


# ---- waivers and the report ----------------------------------------------------------------------


def test_waived_warning_is_marked_and_appears_in_the_report_with_its_justification() -> None:
    p = base()
    f = next(x for x in drc.run(p) if x.rule == "connector-lookalike")
    History(p).execute("waive", [checks.waive_op(f, "Keyed by the cable clamps, see ICD 4.2")])
    again = drc.run(p)
    waived = [x for x in again if x.id == f.id]
    assert waived and waived[0].waiver is not None
    text = render_markdown(p)
    assert "Keyed by the cable clamps, see ICD 4.2" in text and "Waived findings" in text


def test_errors_cannot_be_waived() -> None:
    p = pos_mate_mismatch()
    f = next(x for x in drc.run(p) if x.rule == "mate-mismatch")
    with pytest.raises(edit.EditError):
        checks.waive_op(f, "this is fine, trust me")


def test_waiver_survives_save_and_load(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.core.io.loader import load_project

    p = base()
    f = next(x for x in drc.run(p) if x.rule == "connector-lookalike")
    History(p).execute("waive", [checks.waive_op(f, "Accepted by the design review")])
    save_project(p, tmp_path / "p")
    q = load_project(tmp_path / "p").project
    assert any(x.waiver for x in drc.run(q) if x.id == f.id)


def test_stale_waivers_are_listed() -> None:
    p = base()
    f = next(x for x in drc.run(p) if x.rule == "part-unapproved")
    History(p).execute("waive", [checks.waive_op(f, "Pending approval, tracked in RID-12")])
    for part in list(p.parts.values()):
        apply_ops(p, [Put("parts", evolve(part, approval="approved", unverified=False))])
    assert f.id in stale_waivers(p, drc.run(p))
    assert "Waivers without a matching finding" in render_markdown(p)


def test_report_is_deterministic_and_states_placeholders() -> None:
    a, b = render_markdown(base()), render_markdown(base())
    assert a == b
    assert "Placeholder configuration in use" in a and "not checked" in a.lower()


def test_checks_find_does_not_include_design_rules() -> None:
    p = base()
    assert not {f.rule for f in checks.find(p)} & {r.id for r in RULES}


def test_apply_waivers_ignores_findings_that_cannot_be_waived() -> None:
    p = pos_mate_mismatch()
    f = next(x for x in drc.run(p) if x.rule == "mate-mismatch")
    p.waivers[f.id] = __import__("harness_design_studio.core.model", fromlist=["Waiver"]).Waiver(
        id=f.id, rule=f.rule, object_id=f.object_id, justification="not allowed to count"
    )
    assert next(x for x in drc.run(p) if x.id == f.id).waiver is None


# ---- CLI, performance -----------------------------------------------------------------------------


def test_cli_drc_exit_code_and_output(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    save_project(base(), tmp_path / "ok")
    assert cli_main(["drc", str(tmp_path / "ok")]) == 0
    assert "# Design rule check" in capsys.readouterr().out
    save_project(pos_mate_mismatch(), tmp_path / "bad")
    assert cli_main(["drc", str(tmp_path / "bad")]) == 1


@pytest.mark.perf
def test_drc_on_the_stress_project_is_fast_enough_for_background_runs() -> None:
    p = stress_project()
    generate_project(p)
    t0 = time.perf_counter()
    found = drc.run(p)
    assert time.perf_counter() - t0 < time_limit(5)
    assert not [f for f in found if f.severity == "error"]


def test_sat15_drc_report_matches_golden(capsys) -> None:  # type: ignore[no-untyped-def]
    from pathlib import Path

    folder = Path(__file__).parent / "fixtures" / "projects" / "sat15"
    cli_main(["drc", str(folder)])
    golden = (Path(__file__).parent / "fixtures" / "drc" / "sat15.md").read_text(encoding="utf-8")
    assert capsys.readouterr().out == golden


def test_regression_lookalike_rule_copes_with_mixed_keying() -> None:
    """Found by fuzzing: connectors of one unit and part, some keyed and some not, made the rule raise."""
    p = base()
    unit = next(
        u
        for u in p.units
        if len(
            [c for c in p.connectors.values() if c.unit_id == u and c.part_id == "EX-MICROD-9-F"]
        )
        >= 3
    )
    conns = [c for c in p.connectors.values() if c.unit_id == unit and c.part_id == "EX-MICROD-9-F"]
    apply_ops(
        p,
        [
            Put("connectors", evolve(conns[0], keying="A")),
            Put("connectors", evolve(conns[1], keying=None)),
        ],
    )
    hits = list(next(r for r in RULES if r.id == "connector-lookalike").check(p))
    assert all(h.object_id for h in hits)  # it answers, with findings that point at an object


def test_cited_requirements_exist_in_the_extracted_lists() -> None:
    """REQ-STD-01: a rule can only cite a requirement that is in compliance/requirements."""
    import csv
    from pathlib import Path

    folder = Path(__file__).resolve().parent.parent / "compliance" / "requirements"
    known: set[str] = set()
    for f in folder.glob("*.csv"):
        if f.name != "overrides.csv":
            with f.open(newline="", encoding="utf-8") as fh:
                known |= {row["ID"] for row in csv.DictReader(fh)}
    for rule in RULES:
        for source in rule.sources:
            assert source in known, f"{rule.id} cites unknown {source}"


def test_wire_current_check_uses_the_bundle_table_like_the_sizing() -> None:
    """With both bundle settings set, the table replaces the single factor everywhere, so the
    wire current check and the wire sizing agree (the single factor alone was used before)."""
    from harness_design_studio.core.drc.rules import _wire_current_limit

    p = base()
    h = next(x for x in sorted(p.harnesses.values(), key=lambda x: x.id) if x.wires)
    w = h.wires[0]
    p.harnesses[h.id] = h = evolve(h, wires=[evolve(w, gauge_awg=20), *h.wires[1:]])
    w = h.wires[0]
    set_cfg(
        p, "derating",
        ampacity_a_by_awg={str(w.gauge_awg): 10.0}, bundle_derating=1.0, temperature_derating=1.0,
    )  # fmt: skip
    single = _wire_current_limit(p, w, h)
    assert single == 10.0
    set_cfg(p, "derating", bundle_factor_by_count={"1": 1.0, "300": 0.12})
    limit = _wire_current_limit(p, w, h)
    from harness_design_studio.core.generate.sizing import bundle_k

    expected = bundle_k({"1": 1.0, "300": 0.12}, len(h.wires))
    assert expected is not None and limit == pytest.approx(10.0 * expected)
