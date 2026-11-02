"""A derivation says how a number was made, and it cannot disagree with that number (D-191, step 1).

For every wire of the packaged examples and of the situations of `tools.numbers_snapshot` (a hand
override, the ECSS profile, a lower ampacity, a bundle table of one's own) the derived current limit
and voltage drop are the numbers `sizing` and the design rules produce, to the last digit; they can be
recomputed from the inputs the record shows; and the verdict of the check is the verdict of the rule.
`explain` prints them, and `--json` prints the same as data."""

import json
import math
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import templates
from harness_design_studio.core.assumptions import ASSUMPTIONS
from harness_design_studio.core.derive import Derivation, explain_wire, render
from harness_design_studio.core.drc import run as run_drc
from harness_design_studio.core.drc.base import cfg
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.generate.lengths import wire_length
from harness_design_studio.core.generate.sizing import (
    derated_limit,
    voltage_drop_v,
    wire_current_limit,
)
from harness_design_studio.core.model import Project
from tools.numbers_snapshot import SCENARIOS

SCENARIO_NAMES = [
    "first-steps",
    "flatsat",
    "small-satellite",
    "flatsat-override",
    "flatsat-tight",
    "flatsat-own-bundle-table",
    "flatsat-ecss",
]


def build(name: str, folder: Path) -> Project:
    example, change = SCENARIOS[name]
    project = templates.create_project(folder / name, example)
    if not project.harnesses:
        generate_project(project)
    if change is not None:
        change(project)
    return project


def by_name(d: Derivation, name: str) -> float:
    value = next(i.value for i in d.inputs if i.name.startswith(name))
    assert isinstance(value, int | float)
    return float(value)


@pytest.fixture(scope="module")
def projects() -> Iterator[dict[str, Project]]:
    with tempfile.TemporaryDirectory(prefix="derive-") as tmp:
        yield {name: build(name, Path(tmp)) for name in SCENARIO_NAMES}


def test_the_derived_numbers_are_the_numbers_of_sizing_and_the_rules(
    projects: dict[str, Project],
) -> None:
    seen_current = seen_drop = 0
    for name, project in projects.items():
        derating = cfg(project, "derating")
        for h in project.harnesses.values():
            for w in h.wires:
                _length, current, drop = explain_wire(project, w.id)
                assert current.id == "wire-current-limit" and drop.id == "wire-voltage-drop"
                expected = wire_current_limit(derating, w.gauge_awg, len(h.wires))
                assert current.value == expected, (name, w.id)
                if current.value is not None:
                    seen_current += 1
                    # the record can be recomputed from the inputs it shows
                    base, k, t = (
                        by_name(current, "Base ampacity"),
                        by_name(current, "Bundle factor"),
                        by_name(current, "Temperature"),
                    )
                    assert derated_limit(base, k, t) == current.value
                if drop.value is not None:
                    seen_drop += 1
                    i, rho, length, awg, n = (
                        by_name(drop, x)
                        for x in ("Current", "Resistivity", "Length", "Gauge", "Conductors")
                    )
                    assert voltage_drop_v(i, rho, length, int(awg), int(n)) == drop.value
                    assert math.isclose(drop.steps[-1].value, drop.value, rel_tol=1e-12)
    assert seen_current > 150 and seen_drop > 150  # (the test looks at real wires, not at none)


def test_the_verdict_of_a_derivation_is_the_verdict_of_the_rule(
    projects: dict[str, Project],
) -> None:
    for name in ("flatsat-tight", "flatsat-override", "flatsat"):
        project = projects[name]
        failing = {(f.rule, f.object_id) for f in run_drc(project) if f.severity == "error"}
        for h in project.harnesses.values():
            for w in h.wires:
                _length, current, drop = explain_wire(project, w.id)
                if current.check is not None:
                    assert (not current.check.passes) == (("current-over-wire", w.id) in failing), (
                        name,
                        w.id,
                    )
                if drop.check is not None:
                    assert (not drop.check.passes) == (("voltage-drop", w.id) in failing), (
                        name,
                        w.id,
                    )
    tight = [
        d
        for w in projects["flatsat-tight"].harnesses["W001"].wires
        for d in explain_wire(projects["flatsat-tight"], w.id)
    ]
    assert any(d.check is not None and not d.check.passes for d in tight)  # a failing check exists


def test_a_table_of_ones_own_is_named_as_such_in_the_reference(
    projects: dict[str, Project],
) -> None:
    own = explain_wire(projects["flatsat-own-bundle-table"], "W001-001")[1]
    assert "not the standard's table" in own.reference and "Table 6-41" not in own.reference
    ecss = explain_wire(projects["flatsat-ecss"], "W001-001")[1]
    assert "Table 6-41" in ecss.reference and "equals the standard's" in ecss.reference


def test_what_is_not_set_is_named_and_no_number_is_made_up(projects: dict[str, Project]) -> None:
    first = projects["first-steps"]
    wire = first.harnesses["W001"].wires[0].id
    length, current, drop = explain_wire(first, wire)
    assert current.value is None and current.missing
    assert any("derating." in m or "gauge" in m for m in current.missing)
    assert drop.value is None and drop.missing
    assert "Not decided yet" in render(current)


def test_every_assumption_a_derivation_cites_is_described(projects: dict[str, Project]) -> None:
    for d in explain_wire(projects["flatsat"], "W001-001"):
        assert d.assumptions and set(d.assumptions) <= set(ASSUMPTIONS)
        data = d.to_dict()
        assert [a["id"] for a in data["assumptions"]] == list(d.assumptions)
        assert json.loads(json.dumps(data)) == data  # plain data, in a stable shape


def test_explain_prints_the_numbers_the_tool_stored(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    templates.create_project(tmp_path / "flat", "flatsat")
    assert main(["explain", str(tmp_path / "flat"), "W001-001"]) == 0
    out = capsys.readouterr().out
    assert (
        "Length: 3.45 m" in out
        and "Derated current limit: 1.08 A" in out
        and "Voltage drop: 0.458359 V" in out
    )
    assert "config/derating.json: ampacity_a_by_awg" in out and "A-ROUND-TRIP" in out
    assert main(["explain", str(tmp_path / "flat"), "W001-001", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [d["id"] for d in data] == ["wire-length", "wire-current-limit", "wire-voltage-drop"]
    assert math.isclose(data[2]["value"], 0.458359, rel_tol=1e-6) and data[0]["value"] == 3.45
    assert main(["explain", str(tmp_path / "flat"), "NO-SUCH-WIRE"]) == 2
    assert "does not exist" in capsys.readouterr().err


def test_the_derived_length_is_the_length_the_tool_uses(projects: dict[str, Project]) -> None:
    seen = {"generated": 0, "entered": 0}
    for name, project in projects.items():
        for h in project.harnesses.values():
            for w in h.wires:
                length = explain_wire(project, w.id)[0]
                assert length.id == "wire-length"
                assert length.value == wire_length(h, w), (name, w.id)
                text = render(length)
                if length.value is None:
                    assert length.missing and "Not decided yet" in text
                elif "generated: the path" in text:
                    seen["generated"] += 1
                    seg, extra, total = (s.value for s in length.steps[:3])
                    assert math.isclose(seg + extra, total) and total == length.value
                    # every segment of the path is shown with its length
                    segs = [i.value for i in length.inputs if i.name.startswith("Segment")]
                    assert math.isclose(float(sum(x for x in segs if isinstance(x, float))), seg)
                elif "entered by hand and locked" in text:
                    seen["entered"] += 1
    assert seen["generated"] > 100 and seen["entered"] >= 1


def test_a_length_typed_by_hand_is_said_to_be_typed(projects: dict[str, Project]) -> None:
    project = projects["flatsat-override"]
    typed = [
        w for h in project.harnesses.values() for w in h.wires if w.locked and w.length_m == 1.0
    ]
    assert typed
    length = explain_wire(project, typed[0].id)[0]
    assert length.inputs[0].name == "Length stored on the wire"
    assert "entered by hand and locked" in render(length)


def test_a_missing_segment_length_is_named(projects: dict[str, Project]) -> None:
    from harness_design_studio.core.model import evolve

    project = projects["flatsat"]
    h = project.harnesses["W001"]
    w = h.wires[0]
    cut = evolve(
        h,
        wires=[evolve(w, length_m=None)] + list(h.wires[1:]),
        segments=[evolve(s, length_m=None) for s in h.segments],
    )
    project.harnesses["W001"] = cut
    try:
        length = explain_wire(project, w.id)[0]
        assert length.value is None
        assert any("routing segment" in m for m in length.missing)
    finally:
        project.harnesses["W001"] = h
