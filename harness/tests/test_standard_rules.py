"""REQ-STD-03, REQ-STD-04, REQ-STD-05: REQ-STD-03: rules from the supplied standards. Boundaries, quiet cases and "not checked" messages.

Numbers are test inputs, not engineering data.
"""

from __future__ import annotations

from typing import Any

from harness_design_studio.core import drc
from harness_design_studio.core.commands import Put, apply_ops
from harness_design_studio.core.drc import standard_rules as sr
from harness_design_studio.core.model import Project, evolve
from tests import test_drc as t


def hits(rule: str, p: Project) -> list[str]:
    return [f.object_id for f in t.fire(rule, p)]


def test_connector_voltage_uses_the_lower_of_the_two_limits() -> None:
    p = t.base()
    t.set_cfg(
        p, "derating", connector_voltage_factor_withstand=0.25, connector_voltage_factor_rated=0.75
    )
    t.set_part(p, "EX-MICROD-9-F", rated_voltage_v=100.0, dielectric_withstand_v=200.0)
    assert sr.connector_voltage_limit(p, "EX-MICROD-9-F") == 50.0  # min(0.25 x 200, 0.75 x 100)
    t.set_part(p, "EX-MICROD-9-F", rated_voltage_v=60.0)
    assert sr.connector_voltage_limit(p, "EX-MICROD-9-F") == 45.0


def test_voltage_exactly_at_the_limit_passes() -> None:
    p = t.pos_wire_voltage()
    h, w = t.wire_of(p, "power")
    i = p.interfaces[w.interface_id or ""]
    apply_ops(p, [Put("interfaces", evolve(i, voltage_v=25.0))])  # 0.5 x 50 V
    assert hits("wire-voltage", p) == []


def test_temperature_exactly_at_the_limit_passes() -> None:
    p = t.pos_temperature_margin()
    t.set_cfg(p, "derating", max_ambient_temperature_c=90.0)  # 120 - 30
    assert hits("temperature-margin", p) == []


def test_mating_cycles_at_the_limit_pass() -> None:
    p = t.pos_mating_cycles()
    h, w = t.wire_of(p, "power")
    i = p.interfaces[w.interface_id or ""]
    t.set_part(p, p.connectors[i.endpoints[0].connector_id or ""].part_id, mating_cycles=50.0)
    assert hits("mating-cycles", p) == []


def test_same_manufacturer_passes() -> None:
    p = t.pos_connector_manufacturer()
    for part in list(p.parts.values()):
        if part.manufacturer == "Maker B":
            apply_ops(p, [Put("parts", evolve(part, manufacturer="Maker A"))])
    assert hits("connector-manufacturer", p) == []


def test_specification_present_passes() -> None:
    p = t.pos_wire_specification()
    h, w = t.wire_of(p, "power")
    part = p.parts[w.part_id or ""]
    apply_ops(p, [Put("parts", evolve(part, specification="detail specification"))])
    assert hits("wire-specification", p) == []


def test_power_return_with_a_gap_passes_when_the_gap_is_zero() -> None:
    p = t.pos_power_return_adjacent()
    t.set_cfg(p, "generation", power_return_gap_pins=0)
    assert hits("power-return-adjacent", p) == []


def test_bundle_factor_takes_the_next_listed_count() -> None:
    p = t.base()
    t.set_cfg(p, "derating", bundle_factor_by_count={"1": 1.0, "10": 0.57, "300": 0.12})
    assert sr.bundle_factor(p, 1) == 1.0
    assert sr.bundle_factor(p, 2) == 0.57  # never a better factor than the standard gives
    assert sr.bundle_factor(p, 10) == 0.57
    assert sr.bundle_factor(p, 11) == 0.12
    assert sr.bundle_factor(p, 301) is None


def test_bundle_current_at_the_limit_passes() -> None:
    p = t.pos_bundle_current()
    h, w = t.wire_of(p, "power")
    i = p.interfaces[w.interface_id or ""]
    n = len(h.wires)
    k = sr.bundle_factor(p, n)
    assert k is not None
    apply_ops(p, [Put("interfaces", evolve(i, max_current_a=5.0 * k))])
    assert hits("bundle-current", p) == []


def test_rules_are_silent_without_their_numbers() -> None:
    p = t.base()
    for rule in (
        "connector-voltage", "wire-voltage", "temperature-margin", "mating-cycles",
        "power-return-adjacent", "bundle-current",
    ):  # fmt: skip
        assert hits(rule, p) == [], rule


def test_missing_ratings_are_reported_as_not_checked() -> None:
    p = t.base()
    t.set_cfg(
        p,
        "derating",
        connector_voltage_factor_rated=0.75,
        wire_voltage_factor=0.5,
        max_mating_cycles=50,
        bundle_factor_by_count={"1": 1.0, "300": 0.12},
    )
    h, w = t.wire_of(p, "power")
    i = p.interfaces[w.interface_id or ""]
    apply_ops(p, [Put("interfaces", evolve(i, voltage_v=28.0))])
    text = " ".join(f.title for f in drc.run(p) if f.rule == "unchecked-config")
    assert "Connector working voltage was not checked" in text
    assert "Wire voltage was not checked" in text
    assert "Mating cycles were not checked" in text
    assert "Table 6-42" in text  # L is not applied, and the report says so


def test_every_finding_names_its_requirement() -> None:
    for pos in (t.pos_bundle_current, t.pos_wire_voltage):
        for f in (x for x in drc.run(pos()) if x.rule in ("bundle-current", "wire-voltage")):
            assert f.sources and "ECSS-Q-ST-30-11_" in f.why_cited


def test_sizing_uses_the_bundle_table_instead_of_the_single_factor() -> None:
    from harness_design_studio.core.generate.sizing import size_wire

    der = {
        "ampacity_a_by_awg": {"24": 2.0, "20": 5.0, "18": 7.0},
        "temperature_derating": 1.0,
        "max_voltage_drop_v": 1000.0,
        "bundle_factor_by_count": {"1": 1.0, "10": 0.5, "300": 0.12},
    }
    gen: dict[str, object] = {"conductor_resistivity_ohm_m": 1.7e-8}
    kw: dict[str, Any] = {"current_a": 3.0, "length_m": 1.0, "path_conductors": 1}
    one = size_wire(der, gen, **kw, bundle_wires=1)
    ten = size_wire(der, gen, **kw, bundle_wires=10)
    assert one.awg == 20  # 5 A x 1.0 carries 3 A
    assert ten.awg == 18  # 5 A x 0.5 = 2.5 A is not enough, 7 A x 0.5 = 3.5 A is
    assert any("bundle factor K 0.5 for 10 wires" in n for n in ten.notes)
    big = size_wire(der, gen, **kw, bundle_wires=301)
    assert big.awg is None and any("no entry for 301 wires" in x for x in big.pending)
    # no table: the single factor still decides, exactly as before
    single = size_wire(
        {
            "ampacity_a_by_awg": {"20": 5.0},
            "bundle_derating": 0.6,
            "temperature_derating": 1.0,
            "max_voltage_drop_v": 1000.0,
        },
        gen,
        current_a=2.9,
        length_m=1.0,
        path_conductors=1,
        bundle_wires=10,
    )
    assert single.awg == 20 and not any("Table 6-41" in n for n in single.notes)


def test_generation_leaves_an_unassigned_contact_between_power_and_return() -> None:
    from harness_design_studio.core.generate.engine import generate_project, plan_generation
    from harness_design_studio.core.samples import sat15
    from harness_design_studio.core.verify import verify_project

    p = sat15()
    t.set_cfg(p, "generation", power_return_gap_pins=1)
    generate_project(p)
    assert [f for f in drc.run(p) if f.rule == "power-return-adjacent"] == []
    assert verify_project(p).ok
    box = p.connectors["OBC1-J01"]
    used = [x.signal for x in box.pins]
    assert used[:3] == ["PWR", None, "RTN"]  # pin 2 stays unassigned
    assert plan_generation(p).empty  # a second run changes nothing (REQ-GEN-01)


def test_without_the_setting_power_and_return_stay_adjacent_as_before() -> None:
    from harness_design_studio.core.generate.engine import generate_project
    from harness_design_studio.core.samples import sat15

    p = sat15()
    generate_project(p)
    used = [x.signal for x in p.connectors["OBC1-J01"].pins]
    assert used[:2] == ["PWR", "RTN"]


def test_shield_bonded_at_both_ends_passes() -> None:
    from harness_design_studio.core.model import ShieldGroup  # noqa: F401

    p = t.pos_shield_bonding()
    for h in list(p.harnesses.values()):
        t.put_harness(
            p,
            h,
            shields=[evolve(s, end_a="backshell_360", end_b="backshell_360") for s in h.shields],
        )
    assert hits("shield-bonding", p) == []


def test_emc_class_split_passes_when_classes_differ() -> None:
    p = t.pos_emc_class_split()
    a, b = sorted(
        {
            i.type_id
            for i in p.interfaces.values()
            if {e.unit_id for e in i.endpoints} == {"OBC1", "PCDU1"}
        }
    )[:2]
    apply_ops(p, [Put("interface_types", evolve(p.interface_types[b], emc_class="B"))])
    assert hits("emc-class-split", p) == []


def test_emc_class_is_in_the_wire_list_and_the_labels_only_when_classes_exist() -> None:
    from harness_design_studio.core.outputs.build import build_outputs

    p = t.base()
    plain = build_outputs(p).files
    head = next(v for k, v in plain.items() if k.endswith("/wirelist.csv")).decode().splitlines()
    assert "EMC class" not in head[1]  # byte-identical wire lists for projects without classes
    for tid in list(p.interface_types):
        apply_ops(p, [Put("interface_types", evolve(p.interface_types[tid], emc_class="A"))])
    files = build_outputs(p).files
    wl = next(v for k, v in files.items() if k.endswith("/wirelist.csv")).decode().splitlines()
    assert wl[1].endswith("EMC class") and wl[2].endswith(",A")
    labels = next(v for k, v in files.items() if k.endswith("/labels.csv")).decode()
    assert "[EMC A]" in labels


def test_the_output_verifier_catches_a_wrong_emc_class() -> None:
    from harness_design_studio.core.outputs.build import build_outputs
    from harness_design_studio.core.outputs.verify import verify_outputs

    p = t.base()
    for tid in list(p.interface_types):
        apply_ops(p, [Put("interface_types", evolve(p.interface_types[tid], emc_class="A"))])
    files = dict(build_outputs(p).files)
    assert verify_outputs(p, files).ok
    key = next(k for k in files if k.endswith("/wirelist.csv"))
    lines = files[key].decode().splitlines()
    lines[2] = lines[2][:-1] + "B"
    files[key] = ("\n".join(lines) + "\n").encode()
    codes = [i.code for i in verify_outputs(p, files).issues]
    assert "out_wire_differs" in codes


def test_shield_parts_pass_with_finish_and_unknown_is_reported() -> None:
    p = t.pos_shield_parts()
    h = t.harness_with_real_shield(p)
    t.set_part(p, h.connectors[0].part_id, conductive_finish=1.0)
    assert hits("shield-parts", p) == []
    t.set_part(p, h.connectors[0].part_id, conductive_finish=0.0)
    assert hits("shield-parts", p)


def test_missing_shield_ratings_are_reported_as_not_checked() -> None:
    p = t.base()
    t.set_cfg(p, "emc", shield_bonding="both_ends_backshell")
    text = " ".join(f.title for f in drc.run(p) if f.rule == "unchecked-config")
    assert "Shield finish and sheath were not checked" in text
    assert "routing geometry" in text  # bundle separation is named as not checked


def test_multipactor_is_named_as_not_checked_when_there_is_rf() -> None:
    p = t.base()
    t.set_cfg(p, "derating", rf_power_factor=0.75)
    has_rf = any(x.category == "rf" for x in p.interface_types.values())
    text = " ".join(f.title for f in drc.run(p) if f.rule == "unchecked-config")
    assert ("multipactor" in text) == has_rf


def test_a_plain_twisted_pair_is_not_a_shield_and_never_raises_shield_findings() -> None:
    """Found by running a real-size project through the tool: with a grounding concept of
    floating ends, every twisted pair (which has no shield) was reported as an unconnected shield."""
    p = t.base()
    t.set_cfg(p, "generation", shield_end_a="floating", shield_end_b="floating")
    t.set_cfg(p, "emc", shield_bonding="both_ends_backshell")
    for h in list(p.harnesses.values()):
        t.put_harness(
            p,
            h,
            shields=[
                evolve(s, end_a="floating", end_b="floating") if s.kind == "twisted_pair" else s
                for s in h.shields
            ],
        )
    plain = {s.id for h in p.harnesses.values() for s in h.shields if s.kind == "twisted_pair"}
    assert plain
    for rule in ("shield-unterminated", "shield-wrong-end", "shield-bonding", "shield-parts"):
        assert not any(f.object_id.split(".")[-1] in plain for f in t.fire(rule, p)), rule


# ---- a temperature error belongs to the harness that uses the part (audit C-5) --------------------


def _temperature_blockers(p: Project, harness_id: str) -> list[Any]:
    from harness_design_studio.core.vcs.release import release_blockers

    blockers = release_blockers(
        p,
        harness_id,
        by="x",
        comment="release it please now",
        when="2026-01-01",
        outputs_folder=None,
    )
    return [b for b in blockers if b.code == "rule_error" and "temperature" in b.message]


def test_connector_temperature_error_blocks_the_harness_using_the_part() -> None:
    p = t.pos_temperature_margin()
    h, w = t.wire_of(p, "power")
    assert _temperature_blockers(p, h.id)
    others = [x for x in p.harnesses if x != h.id]
    assert any(not _temperature_blockers(p, x) for x in others)  # not every harness is blocked


def test_wire_temperature_error_blocks_the_harness_using_the_wire_part() -> None:
    p = t.base()
    t.set_cfg(p, "derating", max_ambient_temperature_c=100.0, wire_temperature_margin_c=30.0)
    h, w = t.wire_of(p, "power")
    t.set_part(p, w.part_id or "", max_temp_c=120.0)
    found = hits("temperature-margin", p)
    assert w.id in found
    assert _temperature_blockers(p, h.id)


def test_temperature_findings_name_the_connector_or_wire_that_uses_the_part() -> None:
    p = t.pos_temperature_margin()
    for f in t.fire("temperature-margin", p):
        assert drc.locate(p, f.object_id) is not None, f.object_id


# ---- checks that could not run say so (audit C-6, C-7, C-18) -------------------------------------


def _notes(p: Project) -> str:
    return " | ".join(f.title for f in drc.run(p) if f.rule == "unchecked-config")


def _power_wire_with_current(p: Project, amps: float = 3.0, **wire_fields: Any) -> Any:
    h, w = t.wire_of(p, "power")
    i = p.interfaces[w.interface_id or ""]
    apply_ops(p, [Put("interfaces", evolve(i, max_current_a=amps))])
    t.put_harness(p, h, wires=[evolve(x, **wire_fields) if x.id == w.id else x for x in h.wires])
    return p.harnesses[h.id], w


def test_a_bundle_table_without_an_entry_for_the_wire_count_is_named_as_not_checked() -> None:
    p = t.base()
    t.full_config(p)
    t.set_cfg(p, "derating", bundle_factor_by_count={"1": 1.0})
    h, w = _power_wire_with_current(p, 500.0, gauge_awg=20)
    assert len(h.wires) > 1
    assert hits("bundle-current", p) == [] and hits("current-over-wire", p) == []
    text = _notes(p)
    assert "bundle factors has no entry" in text
    assert f"{h.id} ({len(h.wires)} wires)" in text


def test_a_bundle_table_that_covers_every_harness_adds_no_such_note() -> None:
    p = t.base()
    t.full_config(p)
    t.set_cfg(p, "derating", bundle_factor_by_count={"300": 0.5})
    _power_wire_with_current(p, 1.0, gauge_awg=20)
    assert "bundle factors has no entry" not in _notes(p)


def test_wires_without_a_gauge_are_named_as_not_checked_for_current() -> None:
    p = t.base()
    t.full_config(p)
    h, w = _power_wire_with_current(p, 500.0, gauge_awg=None)
    assert hits("current-over-wire", p) == []
    text = _notes(p)
    assert "Wire current was not checked for" in text and "without a gauge" in text


def test_voltage_drop_names_wires_without_gauge_or_length() -> None:
    p = t.base()
    t.full_config(p)
    t.set_cfg(p, "derating", max_voltage_drop_v=0.0001)
    h, w = _power_wire_with_current(p, 3.0, gauge_awg=None, length_m=None)
    t.put_harness(p, h, wires=[evolve(x, length_m=None) for x in h.wires], segments=[])
    text = _notes(p)
    assert "Voltage drop was not checked for" in text
    assert "without a gauge" in text and "without a length" in text


def test_voltage_drop_with_everything_known_adds_no_such_note() -> None:
    p = t.base()
    t.full_config(p)
    t.set_cfg(p, "derating", max_voltage_drop_v=1000.0)
    h, _w = _power_wire_with_current(p, 3.0)
    t.put_harness(p, h, wires=[evolve(x, gauge_awg=20, length_m=2.0) for x in h.wires])
    assert "Voltage drop was not checked for" not in _notes(p)


def test_voltage_drop_is_checked_for_gauge_zero() -> None:
    p = t.base()
    t.full_config(p)
    t.set_cfg(p, "derating", max_voltage_drop_v=0.0001)
    h, w = _power_wire_with_current(p, 3.0, gauge_awg=0, length_m=50.0)
    assert w.id in hits("voltage-drop", p)


def test_temperature_margins_that_are_not_set_are_named() -> None:
    p = t.base()
    t.set_cfg(p, "derating", max_ambient_temperature_c=100.0)
    text = _notes(p)
    assert "connector_temperature_margin_c" in text and "wire_temperature_margin_c" in text


def test_parts_without_a_maximum_temperature_are_named_as_not_checked() -> None:
    p = t.base()
    t.set_cfg(
        p,
        "derating",
        max_ambient_temperature_c=100.0,
        connector_temperature_margin_c=30.0,
        wire_temperature_margin_c=30.0,
    )
    text = _notes(p)
    h, w = t.wire_of(p, "power")
    assert "Temperature margin was not checked for connector part(s)" in text
    assert f"Temperature margin was not checked for wire part(s) {w.part_id}" in text
    assert "no max_temp_c rating" in text
