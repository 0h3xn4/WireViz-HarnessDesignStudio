"""REQ-MODEL-01: identifiers and SI helpers."""

import math

import pytest
from pydantic import ValidationError

from harness_design_studio.core.model import Unit
from harness_design_studio.core.units import awg_to_area_mm2, awg_to_diameter_mm, format_awg


@pytest.mark.parametrize("good", ["OBC", "W001-001", "a.b", "X_1", "A" * 64])
def test_valid_ids(good: str) -> None:
    assert Unit(id=good, name="n", subsystem="s").id == good


@pytest.mark.parametrize(
    "bad", ["", "1abc", "-x", "a b", "a/b", "ä", "x.", "CON", "con.1", "LPT1", "A" * 65, "a\n"]
)
def test_invalid_ids(bad: str) -> None:
    with pytest.raises(ValidationError):
        Unit(id=bad, name="n", subsystem="s")


def test_control_chars_rejected_in_names() -> None:
    with pytest.raises(ValidationError):
        Unit(id="A", name="bad\x00name", subsystem="s")
    assert Unit(id="A", name="Антенна ✓", subsystem="s").name == "Антенна ✓"


def test_awg_definition() -> None:
    assert awg_to_diameter_mm(36) == pytest.approx(0.127)
    assert awg_to_diameter_mm(0) == pytest.approx(8.251, abs=1e-3)
    assert awg_to_area_mm2(20) == pytest.approx(math.pi / 4 * awg_to_diameter_mm(20) ** 2)
    assert "mm²" in format_awg(22)
    with pytest.raises(ValueError):
        awg_to_area_mm2(41)
