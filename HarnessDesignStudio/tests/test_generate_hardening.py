"""Generation must not crash, hang or invent values on bad input (October audit B-1, B-2, B-4, I-1)."""

from collections.abc import Iterator
from typing import Any

import pytest

from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.generate.engine import (
    GenerationPlan,
    generate_project,
    plan_generation,
)
from harness_design_studio.core.generate.pins import Request, allocate
from harness_design_studio.core.generate.sizing import ampacity_table, size_wire
from harness_design_studio.core.model import (
    ConfigFile,
    Connector,
    Endpoint,
    InterfaceInstance,
    Pin,
    Project,
    Unit,
    evolve,
)
from harness_design_studio.core.samples import mini3, new_project, sat15, sat15_full
from harness_design_studio.core.verify import verify_project
from tests.watchdog import watchdog

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


def iface(p: Project, iid: str, type_id: str, a: str = "A", b: str = "B", **kw: Any) -> None:
    p.interfaces[iid] = InterfaceInstance(
        id=iid, name=iid, type_id=type_id,
        endpoints=[Endpoint(unit_id=a, connector_id=f"{a}-J01"), Endpoint(unit_id=b, connector_id=f"{b}-J01")],
        **kw,
    )  # fmt: skip


def set_cfg(p: Project, name: str, **values: object) -> None:
    old = p.config[name]
    p.config[name] = ConfigFile(
        name=name, placeholder=old.placeholder, values={**old.values, **values}
    )


@pytest.fixture
def timeout() -> Iterator[None]:
    with watchdog(20, "generation did not finish"):
        yield


def codes(plan: GenerationPlan, severity: str | None = None) -> set[str]:
    return {f.code for f in plan.report.findings if severity in (None, f.severity)}


# ---- B-1: a plan with only errors is not "nothing to change" -------------------------------------


def test_a_plan_whose_only_result_is_a_pin_error_is_not_empty() -> None:
    p = two_units(n_pins=4)
    iface(p, "IF-1", "rs422")
    generate_project(p)
    iface(p, "IF-2", "rs422")  # the connectors are full now
    plan = plan_generation(p)
    assert plan.report.errors and "pin_allocation" in codes(plan, "error")
    assert not plan.empty
    text = plan.report.plain_summary()
    assert "Nothing needs to change" not in text
    assert "IF-2" in text and "too few free pins" in text


def test_a_plan_without_errors_is_still_empty_when_nothing_changes() -> None:
    p = sat15()
    generate_project(p)
    plan = plan_generation(p)
    assert plan.empty and plan.report.plain_summary() == "Nothing needs to change."


# ---- B-2: invalid configuration ------------------------------------------------------------------

GOOD_TABLE = {"26": 1.0, "24": 2.0, "22": 3.0, "20": 5.0, "18": 7.0, "16": 10.0}


def sized_gauges(plan: GenerationPlan) -> set[int | None]:
    # interfaces that carry a current are sized from the configuration (the others use defaults)
    return {w.gauge_awg for h in plan.harnesses.values() for w in h.wires if w.length_m}


def current_gauges(p: Project, plan: GenerationPlan) -> set[int | None]:
    currents = {i.id for i in p.interfaces.values() if i.max_current_a is not None}
    return {
        w.gauge_awg for h in plan.harnesses.values() for w in h.wires if w.interface_id in currents
    }


def test_the_good_configuration_sizes_wires() -> None:
    p = sat15_full()
    assert None not in current_gauges(p, plan_generation(p))


@pytest.mark.parametrize(
    ("file", "values", "key"),
    [
        ("derating", {"bundle_derating": 3.0}, "derating.bundle_derating"),
        ("derating", {"bundle_derating": "0.6"}, "derating.bundle_derating"),
        ("derating", {"temperature_derating": 5.0}, "derating.temperature_derating"),
        ("derating", {"temperature_derating": -1}, "derating.temperature_derating"),
        (
            "derating",
            {"ampacity_a_by_awg": {"26": 9.0, "24": 2.0, "22": 3.0, "20": 5.0}},
            "derating.ampacity_a_by_awg",
        ),
        ("derating", {"ampacity_a_by_awg": {"50": 9.0, "20": 5.0}}, "derating.ampacity_a_by_awg"),
        ("derating", {"ampacity_a_by_awg": {"-1": 9.0, "20": 5.0}}, "derating.ampacity_a_by_awg"),
        ("derating", {"max_voltage_drop_v": "1.0"}, "derating.max_voltage_drop_v"),
        ("derating", {"max_voltage_drop_v": -2}, "derating.max_voltage_drop_v"),
        (
            "generation",
            {"conductor_resistivity_ohm_m": 0},
            "generation.conductor_resistivity_ohm_m",
        ),
    ],
)
def test_invalid_sizing_values_are_reported_and_leave_the_gauge_pending(
    file: str, values: dict[str, object], key: str
) -> None:
    p = sat15_full()
    set_cfg(p, file, **values)
    plan = plan_generation(p)  # must not raise
    invalid = [f for f in plan.report.findings if f.code == "config_invalid"]
    assert invalid and all(f.severity == "error" for f in invalid)
    assert any(key.split(".")[1] in f.message for f in invalid)
    gauges = current_gauges(p, plan)
    if file == "derating" and key.split(".")[1] in (
        "bundle_derating", "temperature_derating", "ampacity_a_by_awg"
    ):  # fmt: skip
        assert gauges == {None}  # pending, never a value made up from a bad one


@pytest.mark.parametrize("gap", [-1, -30, 0.5, "2", float("inf"), True, [1]])
def test_an_invalid_power_signal_gap_is_reported_and_ignored(gap: object) -> None:
    p = two_units()
    iface(p, "IF-1", "power_primary", max_current_a=1.0)
    iface(p, "IF-2", "rs422")
    iface(p, "IF-3", "can")
    set_cfg(p, "generation", power_signal_gap_pins=gap)
    plan = plan_generation(p)
    assert any(
        f.code == "config_invalid" and "power_signal_gap_pins" in f.message
        for f in plan.report.findings
    )
    apply_ops(p, plan.ops)
    assert verify_project(p).ok


@pytest.mark.parametrize("gap", [-1, 0.5, "1", float("inf")])
def test_an_invalid_power_return_gap_is_reported_and_ignored(gap: object) -> None:
    p = two_units()
    iface(p, "IF-1", "power_primary", max_current_a=1.0)
    iface(p, "IF-2", "rs422")
    set_cfg(p, "generation", power_return_gap_pins=gap)
    plan = plan_generation(p)
    assert any(
        f.code == "config_invalid" and "power_return_gap_pins" in f.message
        for f in plan.report.findings
    )
    apply_ops(p, plan.ops)
    assert verify_project(p).ok


@pytest.mark.parametrize("value", ["", None, 5, "r" * 300, "re\x00d", {"a": 1}, ["red"]])
def test_an_invalid_wire_colour_is_reported_and_no_colour_is_set(value: object) -> None:
    p = sat15()
    set_cfg(p, "generation", wire_colour_by_signal={"PWR": value})
    plan = plan_generation(p)
    assert any(
        f.code == "config_invalid" and "wire_colour" in f.message for f in plan.report.findings
    )
    assert {w.colour for h in plan.harnesses.values() for w in h.wires if w.signal == "PWR"} == {
        None
    }


@pytest.mark.parametrize("value", ["red", ["PWR"], 3])
def test_a_wire_colour_setting_that_is_not_a_table_is_reported(value: object) -> None:
    p = sat15()
    set_cfg(p, "generation", wire_colour_by_signal=value)
    plan = plan_generation(p)
    assert any(
        f.code == "config_invalid" and "wire_colour" in f.message for f in plan.report.findings
    )


def test_a_valid_wire_colour_is_used() -> None:
    p = sat15()
    set_cfg(p, "generation", wire_colour_by_signal={"PWR": "red"})
    plan = plan_generation(p)
    assert "wire_colour_by_signal" not in " ".join(f.message for f in plan.report.findings)
    assert {w.colour for h in plan.harnesses.values() for w in h.wires if w.signal == "PWR"} == {
        "red"
    }


def test_a_number_given_as_text_is_reported_not_silently_ignored() -> None:
    p = sat15_full()
    set_cfg(p, "generation", service_loop_m="0.1")
    plan = plan_generation(p)
    assert any(
        f.code == "config_invalid" and "service_loop_m" in f.message for f in plan.report.findings
    )


@pytest.mark.parametrize("bad", [float("inf"), float("nan"), 41, -1, 20.5, "20"])
def test_an_invalid_default_gauge_is_reported_and_ignored(bad: object) -> None:
    p = sat15()
    set_cfg(p, "generation", default_gauge_awg=bad)
    plan = plan_generation(p)
    assert any(
        f.code == "config_invalid" and "default_gauge_awg" in f.message
        for f in plan.report.findings
    )
    assert {w.gauge_awg for h in plan.harnesses.values() for w in h.wires} == {None}


def test_a_valid_configuration_gives_no_config_finding() -> None:
    plan = plan_generation(sat15_full())
    assert "config_invalid" not in codes(plan)


def test_sizing_refuses_gauges_outside_the_supported_range() -> None:
    assert ampacity_table({"50": 9.0, "20": 5.0}) is None
    assert ampacity_table({"-1": 9.0}) is None
    assert ampacity_table({"20": 5.0}) == {20: 5.0}
    s = size_wire(
        {"ampacity_a_by_awg": {"50": 9.0, "20": 5.0}, "bundle_derating": 0.6,
         "temperature_derating": 0.9, "max_voltage_drop_v": 1.0},
        {"conductor_resistivity_ohm_m": 1.7e-8},
        current_a=1.0, length_m=1.0, path_conductors=1,
    )  # fmt: skip
    assert s.awg is None and "derating.ampacity_a_by_awg" in s.pending


# ---- B-4: naming templates -----------------------------------------------------------------------


def with_naming(**templates: str) -> Project:
    p = sat15()
    p.config["naming"] = ConfigFile(name="naming", placeholder=False, values=templates)
    return p


@pytest.mark.parametrize(
    ("kind", "template"),
    [
        ("harness", "W{n.foo}"),
        ("harness", "W{n[0]}"),
        ("harness", "COM{n}"),
        ("harness", "H{n!s:.1}"),  # repeats from n = 10: used to loop forever
        ("harness", "Wé{n}"),
        ("harness", "W{n}."),
        ("harness", "H{n:0>70}"),
        ("cable_connector", "{harness}-{n[0]}"),
        ("cable_connector", "{harness}-{n!s:.1}"),
        ("wire", "{harness.foo}-{n}"),
        ("wire", "{harness}-{n!s:.1}"),
        ("wire", "aux"),
        ("shield", "{harness}-{n.x}"),
        ("shield", "{harness}-{n:.1}"),
        ("branch", "{harness}-B"),
        ("segment", "COM1"),
    ],
)
def test_a_bad_naming_template_falls_back_and_is_reported(
    timeout: None, kind: str, template: str
) -> None:
    p = with_naming(**{kind: template})
    plan = plan_generation(p)  # no exception, no endless loop
    assert any(
        f.code == "naming" and f"naming.{kind}" in f.message for f in plan.report.findings
    ), [(f.code, f.message) for f in plan.report.findings]
    reference = plan_generation(sat15())
    assert sorted(plan.harnesses) == sorted(reference.harnesses)  # the default pattern was used
    apply_ops(p, plan.ops)
    assert verify_project(p).ok


def test_a_template_that_is_only_invalid_for_some_numbers_is_reported_when_it_happens(
    timeout: None,
) -> None:
    # "W{n:03d}" is fine; "{n}W" starts with a digit for every harness
    p = with_naming(harness="{n}W")
    plan = plan_generation(p)
    assert any(f.code == "naming" and "naming.harness" in f.message for f in plan.report.findings)
    assert all(h.startswith("W") for h in plan.harnesses)


def test_the_engine_gives_up_on_a_template_that_runs_out_of_names() -> None:
    from types import SimpleNamespace

    from harness_design_studio.core.generate.engine import _first_free
    from harness_design_studio.core.generate.naming import Namer

    namer = Namer({"harness": "H{n!s:.1}"})  # distinct up to 9, then H1, H2, ... again
    ctx = SimpleNamespace(namer=namer)
    taken = {f"H{k}" for k in range(1, 10)}
    n, name = _first_free(ctx, "harness", 10, namer.harness, taken)  # type: ignore[arg-type]
    assert name == f"W{n:03d}" and name not in taken
    assert namer.warnings == ["naming.harness"] and "harness" not in namer.templates


def test_a_good_template_is_used_without_a_finding() -> None:
    p = with_naming(harness="HN{n:03d}", wire="{harness}.w{n}")
    plan = plan_generation(p)
    assert "naming" not in codes(plan)
    assert all(h.startswith("HN") for h in plan.harnesses)
    assert all(w.id.startswith(f"{h.id}.w") for h in plan.harnesses.values() for w in h.wires)


# ---- I-1: fixed pinouts --------------------------------------------------------------------------


def fixed_mini3() -> Project:
    p = mini3()
    box = p.connectors["OBC-J01"]
    named = {"1": "RX-", "2": "RX+", "3": "TX-", "4": "TX+"}
    pins = [
        Pin(id=x.id, signal=named[x.id], fixed=True) if x.id in named else Pin(id=x.id)
        for x in box.pins
    ]
    p.connectors["OBC-J01"] = evolve(box, pins=pins)
    return p


def pin_claims(p: Project, cid: str) -> list[tuple[str | None, str | None]]:
    return [(x.interface_id, x.signal) for x in p.connectors[cid].pins if x.interface_id]


def second_rs422(p: Project) -> None:
    base = p.interfaces["IF-TM-RW1"]
    p.interfaces["IF-X"] = evolve(
        base,
        id="IF-X",
        endpoints=[
            evolve(base.endpoints[0], connector_id="OBC-J01"),
            evolve(base.endpoints[1], unit_id="PCDU", connector_id="PCDU-J03"),
        ],
    )


def test_two_interfaces_never_share_a_fixed_pin() -> None:
    p = fixed_mini3()
    generate_project(p)
    second_rs422(p)
    plan = plan_generation(p)
    assert any(
        f.severity == "error"
        and f.object_id == "IF-X"
        and "OBC-J01 has a fixed pinout" in f.message
        for f in plan.report.findings
    ), [f.message for f in plan.report.findings]  # the error names THIS connector
    apply_ops(p, plan.ops)
    claims = pin_claims(p, "OBC-J01")
    assert len(claims) == len(set(claims))
    assert not any(iid == "IF-X" for iid, _s in claims)


def test_allocation_never_gives_one_fixed_pin_to_two_requests() -> None:
    p = fixed_mini3()
    t = p.interface_types["rs422"]
    out = allocate(p.connectors["OBC-J01"], [Request("IF-TM-RW1", t), Request("IF-X", t)], {}, 0)
    assert len(set(out.pins.values())) == len(out.pins)
    assert {i for i, _m in out.errors} == {"IF-X"}
    assert all("OBC-J01" in m for _i, m in out.errors)


def test_a_locked_fixed_pin_is_not_offered_to_another_interface() -> None:
    p = fixed_mini3()
    box = p.connectors["OBC-J01"]
    locked = [evolve(x, locked=True) if x.id == "4" else x for x in box.pins]  # TX+, nobody's
    t = p.interface_types["rs422"]
    out = allocate(evolve(box, pins=locked), [Request("IF-A", t)], {}, 0)
    assert not out.pins and [i for i, _m in out.errors] == ["IF-A"]


def test_an_interface_that_cannot_be_placed_on_a_fixed_connector_takes_no_pins() -> None:
    p = fixed_mini3()
    box = p.connectors["OBC-J01"]
    no_tx = [Pin(id=x.id) if x.id == "4" else x for x in box.pins]  # no pin named TX+
    full = p.interface_types["rs422"]
    rx_only = evolve(full, id="rx", signals=[s for s in full.signals if s.name.startswith("RX")])
    out = allocate(
        evolve(box, pins=no_tx), [Request("IF-A", full), Request("IF-B", rx_only)], {}, 0
    )
    assert [i for i, _m in out.errors] == ["IF-A"]  # IF-A first (by ID), and it gave its pins back
    assert {k[0] for k in out.pins} == {"IF-B"} and sorted(out.pins.values()) == ["1", "2"]


def test_a_locked_pin_that_already_carries_a_signal_is_not_placed_again_on_a_fixed_connector() -> (
    None
):
    p = fixed_mini3()
    generate_project(p)
    box = p.connectors["OBC-J01"]
    pins = [
        evolve(x, signal="TX+", interface_id="IF-TM-RW1", locked=True, fixed=False)
        if x.id == "5"
        else x
        for x in box.pins
    ]
    p.connectors["OBC-J01"] = evolve(box, pins=pins)
    plan = plan_generation(p)
    apply_ops(p, plan.ops)
    carrying = [
        x.id
        for x in p.connectors["OBC-J01"].pins
        if (x.interface_id, x.signal) == ("IF-TM-RW1", "TX+")
    ]
    assert carrying == ["5"]
    assert verify_project(p).ok
    assert plan_generation(p).empty


def test_allocation_uses_a_held_pin_on_a_fixed_connector() -> None:
    p = fixed_mini3()
    t = p.interface_types["rs422"]
    out = allocate(
        p.connectors["OBC-J01"], [Request("IF-TM-RW1", t)], {}, 0, {("IF-TM-RW1", "TX+"): "5"}
    )
    assert out.pins[("IF-TM-RW1", "TX+")] == "5"
    assert sorted(set(out.pins.values())) == ["1", "2", "3", "5"]
    assert not out.errors


def test_a_locked_fixed_pin_keeps_its_interface_and_the_harness_stays() -> None:
    p = fixed_mini3()
    generate_project(p)
    before = {w.id for h in p.harnesses.values() for w in h.wires}
    box = p.connectors["OBC-J01"]
    p.connectors["OBC-J01"] = evolve(
        box, pins=[evolve(x, locked=True) if x.id == "4" else x for x in box.pins]
    )
    plan = plan_generation(p)
    assert not plan.report.errors, [f.message for f in plan.report.errors]
    apply_ops(p, plan.ops)
    pin4 = next(x for x in p.connectors["OBC-J01"].pins if x.id == "4")
    assert (pin4.interface_id, pin4.signal, pin4.locked) == ("IF-TM-RW1", "TX+", True)
    assert {w.id for h in p.harnesses.values() for w in h.wires} == before
    assert verify_project(p).ok
