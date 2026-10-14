"""Each check of the independent verifier fires on its own mutation, and the verifier
and the design rule check never raise on a damaged project (a missing check cannot go unnoticed)."""

from collections.abc import Callable

import pytest

from harness_design_studio.core import drc, edit
from harness_design_studio.core.commands import Op, Put, apply_ops
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import Harness, Project, Wire, evolve
from harness_design_studio.core.samples import sat15
from harness_design_studio.core.verify import verify_project

_BASE: Project | None = None


def fresh() -> Project:
    """A generated sat15 (built once) with a harness whose first wires carry PWR and RTN."""
    global _BASE
    if _BASE is None:
        _BASE = sat15()
        generate_project(_BASE)
    return edit.clone_with(_BASE, [])


def power_harness(p: Project) -> Harness:
    h = p.harnesses["W001"]
    assert [w.signal for w in h.wires[:2]] == ["PWR", "RTN"]
    return h


def codes(p: Project) -> set[str]:
    return {i.code for i in verify_project(p).errors}


def put_wires(p: Project, h: Harness, wires: list[Wire]) -> None:
    apply_ops(p, [Put("harnesses", evolve(h, wires=wires))])


def with_spare_pin(p: Project, h: Harness, from_signal: str, to_signal: str) -> Wire:
    """A third wire on the spare pin 3 of both unit connectors, carrying the given signals."""
    iface = h.wires[0].interface_id
    label = from_signal if from_signal == to_signal else f"{from_signal}/{to_signal}"
    ops: list[Op] = []
    for cable, sig in zip(h.connectors, (from_signal, to_signal), strict=True):
        box = p.connectors[cable.mates_with or ""]
        pins = [evolve(q, signal=sig, interface_id=iface) if q.id == "3" else q for q in box.pins]
        ops.append(Put("connectors", evolve(box, pins=pins)))
    apply_ops(p, ops)
    return evolve(
        h.wires[0],
        id="W001-099",
        signal=label,
        from_connector=h.connectors[0].id,
        from_pin="3",
        to_connector=h.connectors[1].id,
        to_pin="3",
    )


# ---- one test per check -------------------------------------------------------------------------


def test_wire_from_a_pin_to_itself_is_an_error_not_a_crash() -> None:
    p = fresh()
    h = power_harness(p)
    a = h.wires[0]
    put_wires(p, h, [evolve(a, to_connector=a.from_connector, to_pin=a.from_pin), *h.wires[1:]])
    assert "wire_same_pin" in codes(p)
    found = [f for f in drc.run(p) if f.rule == "verify-mismatch"]
    assert any("W001-001" in f.title and "same pin" in f.title for f in found)
    assert all(f.severity == "error" for f in found)


def test_wire_between_two_pins_of_the_same_end_is_an_error_not_a_crash() -> None:
    p = fresh()
    h = power_harness(p)
    with_spare_pin(p, h, "PWR", "PWR")  # pin 3 of both unit connectors now carries PWR too
    bad = evolve(h.wires[0], to_connector=h.connectors[0].id, to_pin="3")
    put_wires(p, p.harnesses["W001"], [bad, *h.wires[1:]])
    assert "wire_same_end" in codes(p)
    assert any(f.rule == "verify-mismatch" for f in drc.run(p))


def test_exchanged_pins_of_two_wires_are_an_error() -> None:
    p = fresh()
    h = power_harness(p)
    a, b = h.wires[0], h.wires[1]
    swapped = [
        evolve(a, from_pin=b.from_pin, to_pin=b.to_pin),
        evolve(b, from_pin=a.from_pin, to_pin=a.to_pin),
        *h.wires[2:],
    ]
    put_wires(p, h, swapped)
    assert "wire_signal_mismatch" in codes(p)
    assert any(f.rule == "verify-mismatch" for f in drc.run(p))


def test_a_changed_wire_signal_is_an_error() -> None:
    p = fresh()
    h = power_harness(p)
    put_wires(p, h, [evolve(h.wires[0], signal="RTN"), *h.wires[1:]])
    assert "wire_signal_mismatch" in codes(p)


def test_a_wire_without_a_signal_label_is_not_checked_against_the_pinout() -> None:
    p = fresh()
    h = power_harness(p)
    put_wires(p, h, [evolve(h.wires[0], signal=None), *h.wires[1:]])
    assert codes(p) == set()


def test_a_changed_signal_on_the_cable_pin_is_an_error() -> None:
    p = fresh()
    h = power_harness(p)
    c = h.connectors[0]
    pins = [evolve(q, signal="XXX") if q.id == "1" else q for q in c.pins]
    apply_ops(
        p, [Put("harnesses", evolve(h, connectors=[evolve(c, pins=pins), *h.connectors[1:]]))]
    )
    assert "cable_pin_mismatch" in codes(p)


def test_a_changed_interface_on_the_cable_pin_is_an_error() -> None:
    p = fresh()
    h = power_harness(p)
    c = h.connectors[0]
    pins = [evolve(q, interface_id="IF-001") if q.id == "1" else q for q in c.pins]
    apply_ops(
        p, [Put("harnesses", evolve(h, connectors=[evolve(c, pins=pins), *h.connectors[1:]]))]
    )
    assert "cable_pin_mismatch" in codes(p)


def test_cable_pins_that_repeat_the_pinout_are_clean() -> None:
    p = fresh()
    h = power_harness(p)
    fixed = []
    for c in h.connectors:
        box = p.connectors[c.mates_with or ""]
        by_id = {q.id: q for q in box.pins}
        pins = [
            evolve(q, signal=by_id[q.id].signal, interface_id=by_id[q.id].interface_id)
            for q in c.pins
        ]
        fixed.append(evolve(c, pins=pins))
    apply_ops(p, [Put("harnesses", evolve(h, connectors=fixed))])
    assert codes(p) == set()


def test_two_wires_on_one_pin_are_reported() -> None:
    p = fresh()
    h = power_harness(p)
    a, b = h.wires[0], h.wires[1]
    put_wires(p, h, [a, evolve(b, to_pin=a.to_pin), *h.wires[2:]])
    assert "pin_reused" in codes(p)


def test_a_signal_wired_twice_is_reported() -> None:
    p = fresh()
    h = power_harness(p)
    extra = with_spare_pin(p, h, "PWR", "PWR")
    put_wires(p, p.harnesses["W001"], [*h.wires, extra])
    assert "signal_duplicated" in codes(p)


def test_a_wire_the_interface_type_does_not_define_is_reported() -> None:
    p = fresh()
    h = power_harness(p)
    extra = with_spare_pin(p, h, "PWR", "RTN")
    put_wires(p, p.harnesses["W001"], [*h.wires, extra])
    assert "wire_extra" in codes(p)


def test_a_wire_on_a_missing_pin_is_reported() -> None:
    p = fresh()
    h = power_harness(p)
    put_wires(p, h, [evolve(h.wires[0], to_pin="ZZ"), *h.wires[1:]])
    assert "wire_pin_missing" in codes(p)


def test_a_missing_wire_is_reported_as_a_missing_signal() -> None:
    p = fresh()
    h = power_harness(p)
    put_wires(p, h, h.wires[1:])
    assert "signal_missing" in codes(p)


def test_a_wire_on_an_unknown_connector_is_reported() -> None:
    p = fresh()
    h = power_harness(p)
    put_wires(p, h, [evolve(h.wires[0], to_connector="NOPE"), *h.wires[1:]])
    assert "wire_end_missing" in codes(p)


def test_a_clean_project_has_no_errors() -> None:
    assert codes(fresh()) == set()


# ---- the verifier and the rule check never raise on a damaged project -----------------------------


def _same_pin(h: Harness) -> list[Wire]:
    a = h.wires[0]
    return [evolve(a, to_connector=a.from_connector, to_pin=a.from_pin), *h.wires[1:]]


def _same_connector(h: Harness) -> list[Wire]:
    a = h.wires[0]
    return [evolve(a, to_connector=a.from_connector, to_pin="2"), *h.wires[1:]]


WIRE_MUTATIONS: dict[str, Callable[[Harness], list[Wire]]] = {
    "same pin": _same_pin,
    "same connector": _same_connector,
    "missing pin": lambda h: [evolve(h.wires[0], to_pin="ZZ"), *h.wires[1:]],
    "missing connector": lambda h: [evolve(h.wires[0], from_connector="NOPE"), *h.wires[1:]],
    "no wires": lambda h: [],
    "duplicate wire": lambda h: [*h.wires, evolve(h.wires[0], id="W001-DUP")],
    "unknown interface": lambda h: [evolve(h.wires[0], interface_id="IF-NOPE"), *h.wires[1:]],
    "no interface": lambda h: [evolve(h.wires[0], interface_id=None), *h.wires[1:]],
    "no signal": lambda h: [evolve(h.wires[0], signal=None), *h.wires[1:]],
    "exchanged pins": lambda h: [
        evolve(h.wires[0], from_pin="2", to_pin="2"),
        evolve(h.wires[1], from_pin="1", to_pin="1"),
    ],
    "one end exchanged": lambda h: [
        evolve(h.wires[0], to_pin="2"),
        evolve(h.wires[1], to_pin="1"),
    ],
    "both wires on one pin": lambda h: [evolve(w, from_pin="1", to_pin="1") for w in h.wires],
}


@pytest.mark.parametrize("name", sorted(WIRE_MUTATIONS))
def test_verifier_and_rule_check_never_raise_on_a_damaged_wire(name: str) -> None:
    p = fresh()
    h = power_harness(p)
    put_wires(p, h, WIRE_MUTATIONS[name](h))
    report = verify_project(p)
    assert not report.ok or name in {"no signal"}
    drc.run(p)
