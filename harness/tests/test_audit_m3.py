"""Audit round 2 (medium findings C-4, C-8..C-12, C-17..C-23, K-5, D-11, B-13): rules, verifier,
profiles and configuration checks."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import checks, configcheck, drc, standard_profiles
from harness_design_studio.core.commands import History, Put, apply_ops
from harness_design_studio.core.drc import standard_rules as sr
from harness_design_studio.core.generate.engine import plan_generation
from harness_design_studio.core.generate.lengths import loop_segments, path_length
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import (
    ConfigFile,
    Harness,
    Pin,
    Project,
    Segment,
    SignalDef,
    evolve,
)
from harness_design_studio.core.samples import mini3
from harness_design_studio.core.verify import verify_project
from tests import test_drc as t


def codes(p: Project) -> set[str]:
    return {i.code for i in verify_project(p).errors}


def real_shield_harness(p: Project) -> Harness:
    return t.harness_with_real_shield(p)


# ---- C-4: shield groups ---------------------------------------------------------------------------


def test_removing_the_shield_groups_of_a_shielded_type_is_a_verifier_error() -> None:
    p = t.base()
    assert "shield_missing" not in codes(p)
    h = next(
        x
        for x in sorted(p.harnesses.values(), key=lambda x: x.id)
        if any(s.kind != "twisted_pair" for s in x.shields)
    )
    t.put_harness(p, h, shields=[])
    assert "shield_missing" in codes(p)
    assert any(f.rule == "verify-mismatch" and "shield group" in f.title for f in drc.run(p))


def test_a_twisted_pair_group_does_not_count_as_a_shield() -> None:
    p = t.base()
    h = real_shield_harness(p)
    t.put_harness(
        p,
        h,
        shields=[
            evolve(s, kind="twisted_pair") if s.kind != "twisted_pair" else s for s in h.shields
        ],
    )
    assert "shield_missing" in codes(p)


# ---- C-8, C-9, C-20: profiles ---------------------------------------------------------------------


def test_a_profile_marks_a_reviewed_file_as_placeholder_again() -> None:
    p = mini3()
    d = p.config["derating"]
    p.config["derating"] = ConfigFile(name="derating", placeholder=False, values=dict(d.values))
    plan = standard_profiles.plan_profile(p, "ecss-q-st-30-11c")
    derating = next(c for c in plan.configs if c.name == "derating")
    assert derating.placeholder is True
    assert "derating" in plan.marked


def test_a_file_the_profile_does_not_change_keeps_its_review_mark() -> None:
    p = mini3()
    for name in ("derating", "generation"):
        c = p.config[name]
        p.config[name] = ConfigFile(name=name, placeholder=False, values=dict(c.values))
    first = standard_profiles.plan_profile(p, "ecss-q-st-30-11c")
    for c in first.configs:
        p.config[c.name] = c
    second = standard_profiles.plan_profile(p, "ecss-q-st-30-11c")
    assert second.configs == [] and second.marked == ()


def test_cli_profile_leaves_no_reviewed_file_with_profile_values(tmp_path: Path) -> None:
    proj = tmp_path / "p"
    assert main(["new", str(proj), "--template", "first-steps"]) == 0
    loaded = load_project(proj).project
    c = loaded.config["derating"]
    loaded.config["derating"] = ConfigFile(
        name="derating", placeholder=False, values=dict(c.values)
    )
    save_project(loaded, proj)
    main(["config", str(proj), "--apply-profile", "ecss-q-st-30-11c"])
    after = load_project(proj).project
    assert after.config["derating"].values["wire_voltage_factor"] == 0.5
    assert after.config["derating"].placeholder is True


def _with_derating(p: Project, **values: object) -> Project:
    d = p.config["derating"]
    p.config["derating"] = ConfigFile(
        name="derating", placeholder=True, values={**d.values, **values}
    )
    return p


@pytest.mark.parametrize("table", [{"1": 1.5, "2": 1.2}, {"1": 2.0}, {"1": 1.0001}])
def test_a_bundle_factor_above_one_is_refused(table: dict[str, float]) -> None:
    msgs = [
        i.message
        for i in configcheck.validate(_with_derating(mini3(), bundle_factor_by_count=table))
    ]
    assert any("bundle_factor_by_count" in m for m in msgs)


def test_a_bundle_factor_of_exactly_one_is_accepted_and_l_keeps_its_own_bound() -> None:
    p = _with_derating(
        mini3(),
        bundle_factor_by_count={"1": 1.0, "2": 0.9},
        partial_load_factor={
            "below_25_percent": 1.2,
            "25_to_50_percent": 1.1,
            "above_50_percent": 1,
        },
    )
    assert [i for i in configcheck.validate(p) if "factor" in i.message] == []


def test_the_profile_tables_are_copies() -> None:
    p = mini3()
    plan = standard_profiles.plan_profile(p, "ecss-q-st-30-11c")
    d = next(c for c in plan.configs if c.name == "derating")
    table = d.values["bundle_factor_by_count"]
    assert table is not standard_profiles.BUNDLE_K
    assert isinstance(table, dict)
    table["1"] = 99
    assert standard_profiles.BUNDLE_K["1"] == 1


# ---- C-10: pass-through signals ---------------------------------------------------------------------


def test_an_unpaired_directional_signal_is_not_a_direction_conflict() -> None:
    p = t.base()
    tid = next(
        i.type_id for i in p.interfaces.values() if p.interface_types[i.type_id].id == "rs422"
    )
    typ = p.interface_types[tid]
    apply_ops(
        p,
        [
            Put(
                "interface_types",
                evolve(typ, signals=[*typ.signals, SignalDef(name="CLK", direction="out")]),
            )
        ],
    )
    apply_ops(p, plan_generation(p).ops)
    clk = [w for h in p.harnesses.values() for w in h.wires if w.signal == "CLK"]
    assert clk, "the generator wires the extra signal straight through"
    assert verify_project(p).ok
    assert t.fire("direction-conflict", p) == []


# ---- C-11: finding IDs -------------------------------------------------------------------------------


def test_both_dangling_ends_of_a_wire_get_their_own_finding() -> None:
    p = t.pos_wire_dangling()
    h, w = t.wire_of(p, "data")
    t.put_harness(
        p,
        h,
        wires=[evolve(x, from_connector="NOPE2") if x.id == w.id else x for x in h.wires],
    )
    found = t.fire("wire-dangling", p)
    assert len(found) == 2 and len({f.id for f in found}) == 2


def test_waiving_one_of_two_problems_of_one_connector_leaves_the_other() -> None:
    p = t.base()
    c = next(c for c in p.connectors.values() if len(c.pins) >= 2)
    pins = [evolve(x, interface_id="GONE") if k < 2 else x for k, x in enumerate(c.pins)]
    apply_ops(p, [Put("connectors", evolve(c, pins=pins))])
    found = [f for f in drc.run(p) if f.rule == "model-inconsistent" and f.object_id == c.id]
    assert len(found) >= 2 and len({f.id for f in found}) == len(found)
    History(p).execute("waive", [checks.waive_op(found[0], "Known, tracked in RID-1234")])
    after = [f for f in drc.run(p) if f.rule == "model-inconsistent" and f.object_id == c.id]
    assert [f.waiver is not None for f in after].count(True) == 1


@pytest.mark.parametrize("rule_id", sorted(t.POSITIVE))
def test_finding_ids_are_unique(rule_id: str) -> None:
    ids = [f.id for f in drc.run(t.POSITIVE[rule_id]())]
    assert len(ids) == len(set(ids))


# ---- C-12: power and return --------------------------------------------------------------------------


def _connector_with(
    p: Project, layout: list[tuple[str | None, str | None]]
) -> tuple[Project, object]:
    """A box connector whose pins are (interface, signal) pairs in order; None = unassigned."""
    power = t.interface_of(p, "power")
    other = t.interface_of(p, "data")
    c = next(iter(p.connectors.values()))
    ids = {"P": power, "D": other}
    pins = [
        Pin(id=str(k + 1), signal=sig, interface_id=ids.get(kind or ""))
        for k, (kind, sig) in enumerate(layout)
    ]
    return p, evolve(c, pins=pins)


def test_power_and_return_with_an_assigned_pin_between_are_too_close() -> None:
    p, c = _connector_with(t.base(), [("P", "PWR"), ("D", "X"), ("P", "RTN")])
    hits = list(sr._power_pairs(p, c, 1))  # type: ignore[arg-type]
    assert [h.object_id.split(".")[1] for h in hits] == ["1+3"]


def test_an_unassigned_contact_between_power_and_return_is_enough() -> None:
    p, c = _connector_with(t.base(), [("P", "PWR"), (None, None), ("P", "RTN")])
    assert list(sr._power_pairs(p, c, 1)) == []  # type: ignore[arg-type]
    assert len(list(sr._power_pairs(p, c, 2))) == 1  # type: ignore[arg-type]


def test_power_pins_of_different_interfaces_are_looked_at() -> None:
    p = t.base()
    first = t.interface_of(p, "power")
    second = next(
        i.id
        for i in sorted(p.interfaces.values(), key=lambda x: x.id)
        if i.id != first and p.interface_types[i.type_id].category == "power"
    )
    c = next(iter(p.connectors.values()))
    pins = [
        Pin(id="1", signal="PWR", interface_id=first),
        Pin(id="2", signal="RTN", interface_id=second),
    ]
    assert len(list(sr._power_pairs(p, evolve(c, pins=pins), 1))) == 1


def test_a_nan_gap_does_not_crash_the_rule() -> None:
    p = t.base()
    t.set_cfg(p, "generation", power_return_gap_pins=math.nan)
    assert t.fire("power-return-adjacent", p) == []


# ---- C-17, C-19, K-5 ---------------------------------------------------------------------------------


def test_an_approved_but_unverified_part_is_reported_like_the_release_gate_does() -> None:
    p = t.base()
    for part in list(p.parts.values()):
        apply_ops(p, [Put("parts", evolve(part, approval="approved", unverified=True))])
    found = t.fire("part-unapproved", p)
    assert found and all("unverified" in f.title for f in found)
    for part in list(p.parts.values()):
        apply_ops(p, [Put("parts", evolve(part, unverified=False))])
    assert t.fire("part-unapproved", p) == []


def test_the_derating_note_is_not_shown_when_the_bundle_table_replaces_the_single_factor() -> None:
    p = t.base()
    t.full_config(p)
    t.set_cfg(p, "derating", bundle_derating=None, bundle_factor_by_count={"1": 1.0, "300": 0.12})
    i = p.interfaces[t.interface_of(p, "power")]
    apply_ops(p, [Put("interfaces", evolve(i, max_current_a=1.0))])
    notes = [f.id for f in t.fire("unchecked-config", p)]
    assert "unchecked-config.derating" not in notes


def test_a_stale_generation_has_its_own_explanation() -> None:
    p = t.base()
    t.set_cfg(p, "generation", service_loop_m=0.123)  # a generation input changed after generating
    found = [f for f in drc.run(p) if "outputs_outdated" in f.id]
    assert found
    assert "wires do not match" not in found[0].why
    assert "generate" in found[0].why.lower()
    assert found[0].id == next(f.id for f in drc.run(p) if "outputs_outdated" in f.id)  # stable
    assert ".design." in found[0].id


# ---- C-21, C-22, C-23 ------------------------------------------------------------------------------


def _messages(p: Project) -> str:
    return " | ".join(i.message for i in configcheck.validate(p))


def test_more_configuration_values_are_checked() -> None:
    p = mini3()
    d = p.config["derating"]
    g = p.config["generation"]
    s = p.config["segregation"]
    e = p.config["emc"]
    p.config["derating"] = ConfigFile(
        name="derating", placeholder=True,
        values={**d.values, "max_ambient_temperature_c": "hot", "contact_rating_key": ""},
    )  # fmt: skip
    p.config["generation"] = ConfigFile(
        name="generation", placeholder=True, values={**g.values, "default_gauge_awg": 200}
    )
    p.config["segregation"] = ConfigFile(
        name="segregation", placeholder=True,
        values={**s.values, "forbid_pyro_with_other": "yes", "category_pairs_to_separate": [["a", "a"]]},
    )  # fmt: skip
    p.config["emc"] = ConfigFile(
        name="emc", placeholder=True,
        values={**e.values, "classes": "A", "conflicting_class_pairs": [["A", "B"], ["B", "A"]]},
    )  # fmt: skip
    msgs = _messages(p)
    for key in ("max_ambient_temperature_c", "contact_rating_key", "default_gauge_awg",
                "forbid_pyro_with_other", "category_pairs_to_separate", "classes",
                "conflicting_class_pairs"):  # fmt: skip
        assert key in msgs, key


def test_a_temperature_below_absolute_zero_is_refused() -> None:
    p = _with_derating(mini3(), max_ambient_temperature_c=-500)
    assert "max_ambient_temperature_c" in _messages(p)
    p = _with_derating(mini3(), max_ambient_temperature_c=-40)
    assert "max_ambient_temperature_c" not in _messages(p)


def test_findings_of_parts_can_be_located() -> None:
    p = t.pos_shield_parts()
    f = t.fire("shield-parts", p)[0]
    assert drc.locate(p, f.object_id) is not None
    p = t.pos_emc_class_split()
    f = t.fire("emc-class-split", p)[0]
    assert drc.locate(p, f.object_id) is not None


# ---- D-11, B-13: routing loops --------------------------------------------------------------------------


def _harness_with_segments(segments: list[Segment]) -> Harness:
    return evolve(mini3().harnesses[next(iter(mini3().harnesses))], segments=segments)


def test_a_tree_of_segments_has_one_path_and_no_loop() -> None:
    h = _harness_with_segments(
        [Segment(id="S1", from_node="A", to_node="B", length_m=1.0),
         Segment(id="S2", from_node="B", to_node="C", length_m=2.0)]
    )  # fmt: skip
    assert path_length(h, "A", "C") == 3.0
    assert loop_segments(h) == []


def test_a_loop_has_no_single_path_and_is_reported() -> None:
    h = _harness_with_segments(
        [Segment(id="S1", from_node="A", to_node="B", length_m=1.0),
         Segment(id="S2", from_node="B", to_node="C", length_m=2.0),
         Segment(id="S3", from_node="A", to_node="C", length_m=9.0),
         Segment(id="S4", from_node="C", to_node="D", length_m=1.0)]
    )  # fmt: skip
    assert path_length(h, "A", "C") is None  # two routes: 3 m or 9 m
    assert path_length(h, "C", "D") == 1.0  # a path outside the loop stays defined
    assert loop_segments(h) == ["S3"]


def test_a_parallel_segment_is_a_loop() -> None:
    h = _harness_with_segments(
        [Segment(id="S1", from_node="A", to_node="B", length_m=1.0),
         Segment(id="S2", from_node="A", to_node="B", length_m=2.0)]
    )  # fmt: skip
    assert path_length(h, "A", "B") is None
    assert loop_segments(h) == ["S2"]


def test_the_rule_reports_the_loop_on_the_harness() -> None:
    found = t.fire("segment-loop", t.pos_segment_loop())
    assert [f.object_id for f in found] == [
        next(h.id for h in t.pos_segment_loop().harnesses.values() if len(h.segments) == 3)
    ]
