"""Boundaries of the design rules and of wire sizing (audit C-16, I-3, B-3, C-15).

For every limit: a value exactly at the limit passes, a hair above it fails. The numbers are test
inputs, not engineering data.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from harness_design_studio.core.commands import Put, apply_ops
from harness_design_studio.core.generate.sizing import (
    derated_limit,
    exceeds,
    size_wire,
    voltage_drop_v,
)
from harness_design_studio.core.model import Project, evolve
from tests import test_drc as t

RHO = 1.7e-8
HAIR = 1e-6  # far above float rounding (1e-9), far below any real design margin


def set_current(p: Project, interface_id: str, amps: float) -> None:
    apply_ops(p, [Put("interfaces", evolve(p.interfaces[interface_id], max_current_a=amps))])


def hit_objects(rule: str, p: Project) -> list[str]:
    return [f.object_id for f in t.fire(rule, p)]


# ---- the shared comparison ----------------------------------------------------------------------


def test_exceeds_is_exact_at_the_limit_and_true_just_above() -> None:
    assert not exceeds(2.5, 2.5)
    assert not exceeds(0.44999999999999996, 0.45)  # rounding noise of 0.6 * 0.75 is not "over"
    assert not exceeds(0.45, 0.44999999999999996)
    assert exceeds(2.5 * (1 + HAIR), 2.5)
    assert exceeds(float("inf"), 1.0)
    assert not exceeds(float("nan"), 1.0)
    assert not exceeds(0.0, 0.0)


# ---- contact current ----------------------------------------------------------------------------


@pytest.mark.parametrize(("current", "fires"), [(2.5, False), (2.5 * (1 + HAIR), True)])
def test_contact_current_at_the_limit_passes_and_above_fails(current: float, fires: bool) -> None:
    p = t.pos_current_over_contact()  # contact rating 5 A, factor 0.5: limit 2.5 A
    i = p.interfaces[t.interface_of(p, "power")]
    set_current(p, i.id, current)
    assert any(o.startswith(f"{i.id}.") for o in hit_objects("current-over-contact", p)) is fires


def test_contact_current_finding_points_at_the_interface_and_connector() -> None:
    p = t.pos_current_over_contact()
    i = p.interfaces[t.interface_of(p, "power")]
    expected = {f"{i.id}.{e.connector_id}" for e in i.endpoints}
    assert expected <= set(hit_objects("current-over-contact", p))


# ---- wire current -------------------------------------------------------------------------------


def wire_setup(
    ampacity: float, bundle: float, temperature: float, current: float
) -> tuple[Project, str]:
    p = t.base()
    t.full_config(p)
    t.set_cfg(p, "derating", ampacity_a_by_awg={"24": ampacity / 2, "20": ampacity, "18": ampacity * 2},
              bundle_derating=bundle, temperature_derating=temperature)  # fmt: skip
    h, w = t.wire_of(p, "power")
    set_current(p, w.interface_id or "", current)
    t.put_harness(p, h, wires=[evolve(x, gauge_awg=20) if x.id == w.id else x for x in h.wires])
    return p, w.id


@pytest.mark.parametrize(("current", "fires"), [(2.0, False), (2.0 * (1 + HAIR), True)])
def test_wire_current_at_the_derated_limit_passes_and_above_fails(
    current: float, fires: bool
) -> None:
    p, wid = wire_setup(5.0, 0.5, 0.8, current)  # 5 A x 0.5 x 0.8 = 2 A
    assert (wid in hit_objects("current-over-wire", p)) is fires


def test_wire_current_applies_the_temperature_factor() -> None:
    p, wid = wire_setup(5.0, 1.0, 0.5, 3.0)  # 3 A is under 5 A x 1.0 but over 5 A x 1.0 x 0.5
    assert wid in hit_objects("current-over-wire", p)


@pytest.mark.parametrize(
    ("ampacity", "bundle", "temperature", "current"),
    [(1.0, 0.6, 0.75, 0.45), (1.5, 0.6, 0.6, 0.54), (1.5, 0.9, 0.9, 1.215)],
)
def test_the_exact_derated_limit_passes_in_sizing_and_in_the_rule(
    ampacity: float, bundle: float, temperature: float, current: float
) -> None:
    """Audit B-3 / C-15: 0.6 x 0.75 is 0.44999999999999996 in floats; both must still accept 0.45."""
    p, wid = wire_setup(ampacity, bundle, temperature, current)
    assert wid not in hit_objects("current-over-wire", p)
    s = size_wire(
        {"ampacity_a_by_awg": {"20": ampacity}, "bundle_derating": bundle,
         "temperature_derating": temperature, "max_voltage_drop_v": 1e9},
        {"conductor_resistivity_ohm_m": RHO},
        current_a=current, length_m=1.0, path_conductors=1,
    )  # fmt: skip
    assert s.error is None and s.awg == 20


def test_sizing_and_the_rule_agree_on_decimal_exact_limits() -> None:
    values = [Decimal(x) for x in ("0.5", "0.6", "0.7", "0.75", "0.8", "0.9")]
    amps = [Decimal(x) for x in ("1.0", "1.5", "2.7", "5.0", "7.5")]
    for a in amps:
        for b in values:
            for c in values:
                limit = float(a * b * c)  # the exact decimal product, rounded once
                assert not exceeds(limit, derated_limit(float(a), float(b), float(c))), (a, b, c)


def test_one_hair_above_the_limit_is_refused_by_sizing_too() -> None:
    s = size_wire(
        {"ampacity_a_by_awg": {"20": 2.0}, "bundle_derating": 1.0, "temperature_derating": 1.0},
        {},
        current_a=2.0 * (1 + HAIR), length_m=None, path_conductors=1,
    )  # fmt: skip
    assert s.error and "no listed gauge" in s.error


# ---- voltage drop -------------------------------------------------------------------------------


def drop_setup(category: str, limit_factor: float) -> tuple[Project, str]:
    """A wire of `category` whose limit is `limit_factor` x the drop of one conductor."""
    p = t.base()
    t.full_config(p)
    h, w = t.wire_of(p, category)
    set_current(p, w.interface_id or "", 3.0)
    t.put_harness(
        p, h, wires=[evolve(x, gauge_awg=20, length_m=10.0) if x.id == w.id else x for x in h.wires]
    )
    one_way = voltage_drop_v(3.0, RHO, 10.0, 20, 1)
    t.set_cfg(p, "derating", max_voltage_drop_v=one_way * limit_factor)
    return p, w.id


def test_voltage_drop_of_a_power_wire_counts_the_return_conductor() -> None:
    p, wid = drop_setup("power", 2.0)  # exactly the out-and-back drop: passes
    assert wid not in hit_objects("voltage-drop", p)
    p, wid = drop_setup("power", 2.0 * (1 - HAIR))
    assert wid in hit_objects("voltage-drop", p)
    p, wid = drop_setup("power", 1.5)  # a limit between one and two conductors still fires
    assert wid in hit_objects("voltage-drop", p)


def test_voltage_drop_of_a_signal_wire_counts_one_conductor() -> None:
    p, wid = drop_setup("data", 1.0)
    assert wid not in hit_objects("voltage-drop", p)
    p, wid = drop_setup("data", 1.0 * (1 - HAIR))
    assert wid in hit_objects("voltage-drop", p)
    p, wid = drop_setup("data", 1.5)  # a doubled drop would fire here
    assert wid not in hit_objects("voltage-drop", p)


def test_sizing_accepts_a_voltage_drop_exactly_at_the_limit() -> None:
    drop20 = voltage_drop_v(3.0, RHO, 10.0, 20, 2)
    table = {"22": 50.0, "20": 50.0, "18": 50.0}
    der = {"ampacity_a_by_awg": table, "bundle_derating": 1.0, "temperature_derating": 1.0}

    def chosen(limit: float) -> int | None:
        return size_wire(
            {**der, "max_voltage_drop_v": limit},
            {"conductor_resistivity_ohm_m": RHO},
            current_a=3.0,
            length_m=10.0,
            path_conductors=2,
        ).awg

    assert chosen(drop20) == 20
    assert chosen(drop20 * (1 - HAIR)) == 18


# ---- spare pins ---------------------------------------------------------------------------------


def test_spare_pins_exactly_at_the_required_share_pass() -> None:
    p = t.base()
    c = next(
        c
        for c in sorted(p.connectors.values(), key=lambda x: x.id)
        if any(x.interface_id for x in c.pins)
        and any(x.interface_id is None and not x.signal for x in c.pins)
    )
    spare = sum(1 for x in c.pins if x.interface_id is None and not x.signal)
    share = spare / len(c.pins)
    t.set_cfg(p, "derating", spare_pin_fraction=share)
    assert c.id not in hit_objects("spare-pins-low", p)
    t.set_cfg(p, "derating", spare_pin_fraction=share + 0.5 / len(c.pins))  # needs half a pin more
    assert c.id in hit_objects("spare-pins-low", p)


# ---- mating halves ------------------------------------------------------------------------------


def mate_setup() -> tuple[Project, str, str]:
    p = t.base()
    h = next(x for x in sorted(p.harnesses.values(), key=lambda x: x.id) if x.generated)
    c = h.connectors[0]
    return p, c.id, c.mates_with or ""


def set_keying(p: Project, cable_id: str, box_id: str, cable_key: str, box_key: str) -> None:
    h = next(x for x in p.harnesses.values() if any(c.id == cable_id for c in x.connectors))
    t.put_harness(
        p,
        h,
        connectors=[evolve(c, keying=cable_key) if c.id == cable_id else c for c in h.connectors],
    )
    apply_ops(p, [Put("connectors", evolve(p.connectors[box_id], keying=box_key))])


def mate_text(p: Project, cable_id: str) -> str:
    return " ".join(f.title for f in t.fire("mate-mismatch", p) if f.object_id == cable_id)


def test_mate_mismatch_notices_different_keying() -> None:
    p, cable_id, box_id = mate_setup()
    set_keying(p, cable_id, box_id, "A", "A")
    assert "keying" not in mate_text(p, cable_id)
    set_keying(p, cable_id, box_id, "A", "B")
    assert "keying differs" in mate_text(p, cable_id)


def test_mate_mismatch_notices_a_different_pin_count() -> None:
    p, cable_id, box_id = mate_setup()
    assert "pins against" not in mate_text(p, cable_id)
    h = next(x for x in p.harnesses.values() if any(c.id == cable_id for c in x.connectors))
    t.put_harness(
        p,
        h,
        connectors=[evolve(c, pins=c.pins[:-1]) if c.id == cable_id else c for c in h.connectors],
    )
    text = mate_text(p, cable_id)
    assert (
        f"{len(p.connectors[box_id].pins) - 1} pins against {len(p.connectors[box_id].pins)}"
        in text
    )
