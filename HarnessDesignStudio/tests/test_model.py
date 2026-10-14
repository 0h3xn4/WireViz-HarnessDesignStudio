"""REQ-MODEL-02: strict, immutable model objects."""

import pytest
from pydantic import ValidationError

from harness_design_studio.core.model import Pin, Unit, Wire, evolve
from harness_design_studio.core.model.config import default_configs


def test_strict_types_no_coercion() -> None:
    with pytest.raises(ValidationError):
        Unit(id="A", name="n", subsystem="s", mass_relevant="yes")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Wire(id="W1", from_connector="A", from_pin=1, to_connector="B", to_pin="1")  # type: ignore[arg-type]


def test_unknown_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        Unit.model_validate({"id": "A", "name": "n", "subsystem": "s", "bogus": 1})


def test_nan_rejected() -> None:
    with pytest.raises(ValidationError):
        Wire(
            id="W1",
            from_connector="A",
            from_pin="1",
            to_connector="B",
            to_pin="1",
            length_m=float("nan"),
        )


def test_frozen() -> None:
    u = Unit(id="A", name="n", subsystem="s")
    with pytest.raises(ValidationError):
        u.name = "x"  # type: ignore[misc]


def test_evolve_validates_and_rejects_unknown() -> None:
    u = Unit(id="A", name="n", subsystem="s")
    assert evolve(u, name="m").name == "m"
    with pytest.raises(ValidationError):
        evolve(u, id="1bad")
    with pytest.raises(TypeError):
        evolve(u, nope=1)


def test_pin_ids() -> None:
    with pytest.raises(ValidationError):
        Pin(id="1\n")
    assert Pin(id="A1").id == "A1"
    assert Pin(id="12").id == "12"
    with pytest.raises(ValidationError):
        Pin(id="")
    with pytest.raises(ValidationError):
        Pin(id="x" * 17)


def test_default_configs_are_marked_placeholder() -> None:
    cfg = default_configs()
    assert cfg["derating"].placeholder and cfg["emc"].placeholder

    def numbers(node: object) -> list[float]:
        if isinstance(node, bool):
            return []
        if isinstance(node, int | float):
            return [float(node)]
        if isinstance(node, dict):
            return [n for v in node.values() for n in numbers(v)]
        if isinstance(node, list):
            return [n for v in node for n in numbers(v)]
        return []

    for name in ("derating", "generation", "emc"):  # no invented numbers from standards
        assert numbers(cfg[name].values) == [], name
    assert not cfg["naming"].placeholder
