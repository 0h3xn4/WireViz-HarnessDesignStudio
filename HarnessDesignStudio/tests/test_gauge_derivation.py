"""The choice of a gauge as a derivation (audit R1, owner decision 14): `explain DIR WIRE` shows the
gauges the search tried, the current limit of each after derating, the drop of each, which is the first
that passes and what it rests on. It replays the search with the function generation calls, so the gauge
it names is the gauge the generator chose (compared here on the four packaged examples); a gauge a
person set says so. It is computed on demand: `explain --all` and `derivations.json` do not contain it."""

import copy
import json
import math
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import templates
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.derive import Derivation, explain_object, explain_wire, render
from harness_design_studio.core.derive_export import explain_all
from harness_design_studio.core.derive_gauge import gauge_derivation
from harness_design_studio.core.derive_kinds import KINDS, ON_DEMAND, page_of
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import ConfigFile, Project, evolve
from harness_design_studio.core.wires import find_wire, plan_override

EXAMPLES = ("first-steps", "minimal-satellite", "small-satellite", "flatsat")
RHO = 1.7e-8  # the resistivity of the flatsat example (config/generation.json)


def _set(project: Project, file: str, **values: object) -> None:
    base = project.config.get(file) or ConfigFile(name=file, placeholder=False, values={})
    project.config[file] = ConfigFile(
        name=file, placeholder=False, values={**copy.deepcopy(base.values), **values}
    )


@pytest.fixture(scope="module")
def flat() -> Iterator[Project]:
    with tempfile.TemporaryDirectory(prefix="gauge-") as tmp:
        yield templates.create_project(Path(tmp) / "flat", "flatsat")


def _gauge(project: Project, wid: str) -> Derivation:
    h, w = find_wire(project, wid)
    return gauge_derivation(project, h, w)


def _area_mm2(awg: int) -> float:
    d = 0.127 * 92 ** ((36 - awg) / 39)  # the AWG definition, by hand
    return float(math.pi / 4 * d * d)


# ---- a hand calculation: W004-003 of the flatsat example -------------------------------------


def test_the_candidates_of_a_flatsat_wire_are_the_ones_worked_out_by_hand(flat: Project) -> None:
    # W004-003 carries 5 A (IF-003, power). Derating: K 0.6, temperature 0.9, so the factor is 0.54.
    # Base ampacity of AWG 26, 24, 22, 20, 18, 16: 1, 2, 3, 5, 7, 10 A. Limits: 0.54, 1.08, 1.62, 2.7,
    # 3.78, 5.4 A. The first that carries 5 A is AWG 16 (5.4 A). Its drop over 3.2 m, two conductors:
    # 5 A × 1.7e-8 Ω·m × 3.2 m / A(16) × 2 = 0.41568 V, within the limit of 1 V: AWG 16.
    d = _gauge(flat, "W004-003")
    assert d.id == "gauge" and d.value == 16 and d.unit == "AWG" and d.known and not d.missing
    tries = [s for s in d.steps if s.label.startswith("Try AWG") and " for 5 A" in s.label]
    assert [s.label.split(":")[0] for s in tries] == [
        f"Try AWG {a} for 5 A" for a in (26, 24, 22, 20, 18, 16)
    ]
    for step, limit in zip(tries, (0.54, 1.08, 1.62, 2.7, 3.78, 5.4), strict=True):
        assert step.value == pytest.approx(limit, abs=1e-12) and step.unit == "A"
    assert [s.label.endswith("carries it") for s in tries] == [False] * 5 + [True]
    drops = [s for s in d.steps if "for the drop" in s.label]
    assert len(drops) == 1 and drops[0].label.startswith("Try AWG 16 for the drop, limit 1 V")
    assert drops[0].value == pytest.approx(5 * RHO * 3.2 / (_area_mm2(16) * 1e-6) * 2, rel=1e-9)
    assert drops[0].value == pytest.approx(0.415681, abs=1e-6)
    assert d.check is not None and d.check.passes
    assert d.check.actual == 5 and d.check.limit == pytest.approx(5.4) and d.check.margin > 0.39
    assert set(d.assumptions) == {
        "A-AMPACITY-AWG", "A-BUNDLE-ALL", "A-TEMP-FACTOR", "A-DC-SOLID", "A-ROUND-TRIP",
    }  # fmt: skip
    names = {i.name: i for i in d.inputs}
    assert names["Current carried"].value == 5 and names["Voltage drop limit"].value == 1
    assert names["Bundle factor K"].value == 0.6 and names["Temperature factor"].value == 0.9
    text = render(d)
    assert "Gauge: 16 AWG (1.31 mm²)" in text and "AWG 16 (1.31 mm²) carries 5.4 A" in text
    assert "The wire has AWG 16 (1.31 mm²), the gauge of this search" in text


def test_the_drop_moves_the_gauge_up_and_every_gauge_tried_is_shown(flat: Project) -> None:
    # a 0.8 A wire of 3.45 m (W001-001): AWG 24 carries it (1.08 A). A drop limit of 0.4 V is not kept
    # by AWG 24 (0.458 V) but by AWG 22: 0.8 × 1.7e-8 × 3.45 / A(22) × 2 = 0.288 V.
    project = copy.deepcopy(flat)
    _set(project, "derating", max_voltage_drop_v=0.4)
    d = _gauge(project, "W001-001")
    drops = [s for s in d.steps if "for the drop" in s.label]
    assert [s.label.split(" for the drop")[0] for s in drops] == ["Try AWG 24", "Try AWG 22"]
    by_hand = [0.8 * RHO * 3.45 / (_area_mm2(a) * 1e-6) * 2 for a in (24, 22)]
    assert [s.value for s in drops] == pytest.approx(by_hand, rel=1e-9)
    assert by_hand[0] > 0.4 > by_hand[1]
    assert drops[0].label.endswith("over the limit") and drops[1].label.endswith("within the limit")
    assert d.value == 22
    # and it is the gauge that generation chooses for the same settings
    generate_project(project)
    assert find_wire(project, "W001-001")[1].gauge_awg == 22


def test_no_gauge_that_carries_the_current_is_said_with_every_gauge_tried(flat: Project) -> None:
    project = copy.deepcopy(flat)
    _, w = find_wire(project, "W004-003")
    project.interfaces[w.interface_id or ""] = evolve(
        project.interfaces[w.interface_id or ""], max_current_a=500.0
    )
    d = _gauge(project, "W004-003")
    assert d.value is None and d.text.startswith("none: no listed gauge carries 500 A")
    assert all(s.label.endswith("too small") for s in d.steps if s.label.startswith("Try AWG"))
    assert d.known  # the answer is "none", with the reason


def test_a_value_that_is_not_set_is_named_as_for_the_other_derivations(flat: Project) -> None:
    project = copy.deepcopy(flat)
    _set(project, "derating", temperature_derating=None)
    d = _gauge(project, "W004-003")
    assert d.value is None and d.missing == ("derating.temperature_derating",)
    assert "Not decided yet, because these are not set" in render(d)


# ---- the same gauge as generation, on all four packaged examples --------------------------------


@pytest.mark.parametrize("example", EXAMPLES)
def test_the_gauge_of_the_derivation_is_the_gauge_generation_chose(
    example: str, tmp_path: Path
) -> None:
    project = templates.create_project(tmp_path / example, example)
    if not project.harnesses:
        generate_project(project)
    checked = decided = 0
    for h in project.harnesses.values():
        for w in h.wires:
            if w.manual or w.locked:
                continue
            d = gauge_derivation(project, h, w)
            assert d.id == "gauge" and d.subject == f"Wire {w.id}"
            assert d.value == w.gauge_awg, (example, w.id, d.value, w.gauge_awg)
            checked += 1
            decided += d.value is not None
            if d.value is not None:  # the limit shown is the limit the rule current-over-wire uses
                assert d.check is not None and d.check.passes
    assert checked > 0
    if example == "flatsat":
        assert decided > 30  # the wires with a current are sized, the others have no gauge


# ---- a gauge a person set ------------------------------------------------------------------------


def test_a_gauge_set_with_a_reason_says_so_and_shows_what_the_search_gives(flat: Project) -> None:
    project = copy.deepcopy(flat)
    apply_ops(project, plan_override(project, "W004-003", "gauge_awg", 14, "customer harness spec"))
    d = _gauge(project, "W004-003")
    assert d.value == 14
    how = next(s for s in d.steps if s.label == "How the gauge was decided")
    assert how.text == "set by the engineer, reason: customer harness spec"
    names = {i.name: i for i in d.inputs}
    assert (
        names["Gauge on the wire"].value == 14 and names["Gauge the search gives now"].value == 16
    )
    assert "customer harness spec" in names["Gauge on the wire"].source
    assert not any(s.label.startswith("Try AWG") for s in d.steps)  # the search was not run for it


def test_a_locked_gauge_and_a_wire_drawn_by_hand_say_so(flat: Project) -> None:
    project = copy.deepcopy(flat)
    h, w = find_wire(project, "W004-003")
    project.harnesses[h.id] = evolve(
        h, wires=[evolve(x, locked=True) if x.id == w.id else x for x in h.wires]
    )
    d = _gauge(project, "W004-003")
    how = next(s for s in d.steps if s.label == "How the gauge was decided")
    assert "locked" in how.text and "no reason recorded" in d.inputs[0].source
    h, w = find_wire(project, "W004-002")
    project.harnesses[h.id] = evolve(
        h, wires=[evolve(x, manual=True) if x.id == w.id else x for x in h.wires]
    )
    how = next(
        s for s in _gauge(project, "W004-002").steps if s.label == "How the gauge was decided"
    )
    assert "drawn by a person" in how.text


def test_another_override_leaves_the_gauge_to_the_search(flat: Project) -> None:
    project = copy.deepcopy(flat)
    apply_ops(project, plan_override(project, "W004-003", "colour", "pink", "customer request"))
    d = _gauge(project, "W004-003")
    assert d.value == 16 and any(s.label.startswith("Try AWG") for s in d.steps)


def test_a_stale_gauge_is_named_as_such(flat: Project) -> None:
    project = copy.deepcopy(flat)
    _set(project, "derating", ampacity_a_by_awg={**flat.config["derating"].values["ampacity_a_by_awg"], "18": 10.0})  # fmt: skip
    d = _gauge(
        project, "W004-003"
    )  # the wire still has the AWG 16 of the first generation; 18 carries 5.4 A now
    assert d.value == 18 and "gives AWG 18: generate again" in d.reference


# ---- where it is printed ----------------------------------------------------------------------------


def test_explain_prints_it_for_a_wire_and_the_files_do_not_contain_it(flat: Project) -> None:
    ids = [d.id for d in explain_object(flat, "W004-003")]
    assert ids[:3] == ["wire-length", "gauge", "wire-current-limit"]
    assert [d.id for d in explain_wire(flat, "W004-003")].count("gauge") == 0  # on demand only
    assert "gauge" not in {d.id for d in explain_all(flat)}


def test_the_kind_has_its_page_and_is_on_demand() -> None:
    assert page_of("gauge") == "wire-sizing.md" and ON_DEMAND == {"gauge"} <= set(KINDS)
    text = (Path(__file__).resolve().parent.parent / "docs" / "models" / "wire-sizing.md").read_text(encoding="utf-8")  # fmt: skip
    assert "`gauge`" in text and "W004-003" in text and "0.415681" in text


def test_explain_json_has_the_shape_of_a_derivation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    templates.create_project(tmp_path / "flat", "flatsat")
    assert main(["explain", str(tmp_path / "flat"), "W004-003", "--json"]) == 0
    found = json.loads(capsys.readouterr().out)
    g = next(d for d in found if d["id"] == "gauge")
    assert list(g) == [
        "id", "subject", "quantity", "value", "unit", "equation", "inputs", "steps", "check",
        "assumptions", "reference", "missing",
    ]  # fmt: skip
    assert g["value"] == 16 and g["unit"] == "AWG"
    assert g["check"]["limit"] == pytest.approx(5.4) and g["check"]["actual"] == 5
    assert [s["value"] for s in g["steps"] if s["label"].startswith("Try AWG")][
        :6
    ] == pytest.approx([0.54, 1.08, 1.62, 2.7, 3.78, 5.4])
    assert next(i for i in g["inputs"] if i["name"] == "Current carried")["unit"] == "A"
