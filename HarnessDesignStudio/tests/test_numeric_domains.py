"""A-6 / D-9 / B-18 / K-19: impossible numbers are refused by the model, and a damaged project
file holding one is set aside on load (reported, never rendered as a 'complete' result)."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.model import (
    GenerationRecord,
    InterfaceInstance,
    InterfaceType,
    Part,
    ProjectMeta,
    Segment,
    Wire,
)
from tests.helpers import copy_project, edit_json

FIXTURES = Path(__file__).parent / "fixtures" / "projects"


def _wire(**kw: Any) -> Wire:
    return Wire(id="W1", from_connector="A", from_pin="1", to_connector="B", to_pin="1", **kw)


def _iface(**kw: Any) -> InterfaceInstance:
    return InterfaceInstance(id="I1", name="n", type_id="T", endpoints=[], **kw)


BAD: list[Any] = [
    lambda: _wire(gauge_awg=999),
    lambda: _wire(gauge_awg=-5),
    lambda: _wire(gauge_awg=41),
    lambda: _wire(length_m=-1.0),
    lambda: _wire(length_m=10000.5),
    lambda: Segment(id="S1", from_node="A", to_node="B", length_m=-0.1),
    lambda: _iface(max_current_a=0.0),
    lambda: _iface(max_current_a=-3.0),
    lambda: _iface(voltage_v=0.0),
    lambda: _iface(voltage_v=-28.0),
    lambda: InterfaceType(id="T", name="n", category="power", signals=[], default_gauge_awg=99),
    lambda: InterfaceType(id="T", name="n", category="power", signals=[], default_gauge_awg=-3),
    lambda: InterfaceType(id="T", name="n", category="data", signals=[], impedance_ohm=0.0),
    lambda: Part(id="P", category="connector", pin_count=0),
    lambda: Part(id="P", category="connector", pin_count=-3),
    lambda: Part(id="P", category="connector", pin_count=1001),
    lambda: Part(id="P", category="wire", mass_g=-1.0),
    lambda: Part(id="P", category="wire", mass_per_m_g=-0.5),
    lambda: Part(id="P", category="wire", ratings={"contact_current_a": -1.0}),
    lambda: GenerationRecord(input_hash="x", generator_version="1", next_harness_number=0),
    lambda: GenerationRecord(input_hash="x", generator_version="1", next_harness_number=-5),
    lambda: ProjectMeta(schema_version=0),
    lambda: ProjectMeta(schema_version=-1),
]


@pytest.mark.parametrize("make", BAD)
def test_impossible_numbers_are_refused(make: Any) -> None:
    with pytest.raises(ValidationError):
        make()


def test_limits_themselves_are_accepted() -> None:
    assert _wire(gauge_awg=0, length_m=0.0).length_m == 0.0
    assert _wire(gauge_awg=40, length_m=10000.0).gauge_awg == 40
    assert Part(id="P", category="connector", pin_count=1).pin_count == 1
    assert Part(id="P", category="connector", pin_count=1000).pin_count == 1000
    assert Part(id="P", category="wire", mass_g=0.0, mass_per_m_g=0.0).mass_g == 0.0
    assert _iface(max_current_a=0.001, voltage_v=0.001).voltage_v == 0.001
    assert ProjectMeta(schema_version=1).schema_version == 1


def test_a_wire_with_a_negative_length_in_a_file_is_set_aside_on_load(tmp_path: Path) -> None:
    root = copy_project(FIXTURES / "mini3", tmp_path / "p")
    target = next(p for p in sorted((root / "physical" / "harnesses").glob("*.json")))

    def poison(d: dict[str, Any]) -> None:
        d["wires"][0]["length_m"] = -3.5

    edit_json(target, poison)
    result = load_project(root)
    assert any(i.code == "quarantined" for i in result.issues)
    assert result.project.recovered
    assert json.loads(target.read_text())["wires"][0]["length_m"] == -3.5  # file untouched


def test_a_negative_schema_version_is_not_read_as_current(tmp_path: Path) -> None:
    root = copy_project(FIXTURES / "mini3", tmp_path / "p")

    def poison(d: dict[str, Any]) -> None:
        d["schema_version"] = -1

    edit_json(root / "project.json", poison)
    result = load_project(root)
    assert result.project.recovered
    assert any("project settings" in i.message for i in result.issues)
