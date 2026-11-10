# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
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
from harness_design_studio.core.derive import (
    Derivation,
    explain_harness,
    explain_object,
    explain_wire,
    render,
)
from harness_design_studio.core.drc import run as run_drc
from harness_design_studio.core.drc.base import cfg
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.generate.lengths import wire_length
from harness_design_studio.core.generate.mass import harness_mass, wire_mass_g
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
                _length, current, drop, _mass = explain_wire(project, w.id)
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
                _length, current, drop, _mass = explain_wire(project, w.id)
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
    length, current, drop, mass = explain_wire(first, wire)
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
    assert [d["id"] for d in data][:5] == [
        "wire-length",
        "gauge",
        "wire-current-limit",
        "wire-voltage-drop",
        "wire-mass",
    ]
    assert [d["id"] for d in data][5:] == [  # then what S1 added: label, colour, shield, two pins
        "wire-label",
        "wire-colour",
        "shield-group",
        "pin-allocation",
        "pin-allocation",
    ]
    assert math.isclose(data[3]["value"], 0.458359, rel_tol=1e-6) and data[0]["value"] == 3.45
    assert main(["explain", str(tmp_path / "flat"), "NO-SUCH-WIRE"]) == 2
    assert "is not a wire, a harness or a part" in capsys.readouterr().err


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


def test_the_mass_of_a_harness_is_the_mass_of_the_tables(projects: dict[str, Project]) -> None:
    seen = 0
    for name, project in projects.items():
        for h in project.harnesses.values():
            report = harness_mass(project, h)
            (d,) = explain_harness(project, h.id)
            assert d.id == "harness-mass" and d.value == report.total_g, (name, h.id)
            assert list(d.missing) == report.missing
            # the steps the reader sees add up to the number
            parts = [s.value for s in d.steps if s.label.startswith(("Connectors", "Wires of"))]
            assert math.isclose(sum(parts), report.total_g, rel_tol=1e-9, abs_tol=1e-9)
            for s in d.steps:
                if s.label == "With margin":
                    assert report.with_margin_g is not None
                    assert math.isclose(s.value, report.with_margin_g, rel_tol=1e-9)
            seen += report.total_g > 0
    assert seen >= 5


def test_the_mass_of_a_wire_is_the_share_the_harness_counts(projects: dict[str, Project]) -> None:
    project = projects["flatsat"]
    for h in project.harnesses.values():
        total = 0.0
        for w in h.wires:
            mass = explain_wire(project, w.id)[3]
            assert mass.id == "wire-mass"
            part = project.parts[w.part_id or ""]
            length = wire_length(h, w)
            assert length is not None and part.mass_per_m_g is not None
            assert mass.value == wire_mass_g(part.mass_per_m_g, length, part.conductors)
            total += mass.value or 0.0
        connectors = sum(project.parts[c.part_id].mass_g or 0.0 for c in h.connectors)
        assert math.isclose(total + connectors, harness_mass(project, h).total_g, rel_tol=1e-9)


def test_what_a_mass_leaves_out_is_said_and_a_missing_mass_is_named(
    projects: dict[str, Project],
) -> None:
    from harness_design_studio.core.model import evolve

    project = projects["flatsat"]
    text = render(explain_harness(project, "W001")[0])
    assert "A-MASS-SCOPE" in text and "accessories" in text and "A-MASS-CONDUCTORS" in text
    h = project.harnesses["W001"]
    part_id = h.wires[0].part_id or ""
    original = project.parts[part_id]
    project.parts[part_id] = evolve(original, mass_per_m_g=None)
    try:
        (d,) = explain_harness(project, "W001")
        assert any("mass per metre" in m for m in d.missing)
        assert d.quantity.startswith("Mass (total of what is known)")
        wire_mass = explain_wire(project, h.wires[0].id)[3]
        assert wire_mass.value is None and wire_mass.missing
    finally:
        project.parts[part_id] = original


def test_explain_takes_a_wire_or_a_harness(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    templates.create_project(tmp_path / "flat", "flatsat")
    assert main(["explain", str(tmp_path / "flat"), "W001"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Harness W001. Mass:") and "Connector W001-P1" in out
    project = templates.create_project(tmp_path / "again", "flatsat")
    assert explain_object(project, "W001")[0].id == "harness-mass"
    assert [d.id for d in explain_harness(project, "W001")] == ["harness-mass"]
    assert main(["explain", str(tmp_path / "flat"), "NOPE"]) == 2


# ---- the bill of materials ---------------------------------------------------------------


def _bom_rows(project: Project) -> dict[tuple[str, str], list[str]]:
    from harness_design_studio.core.outputs.tables import bom

    rows = bom(project, [project.harnesses[i] for i in sorted(project.harnesses)])
    return {(r[0], r[7]): r for r in rows[1:]}


def test_the_quantity_explained_is_the_quantity_of_the_bom(projects: dict[str, Project]) -> None:
    from harness_design_studio.core.derive import explain_part
    from harness_design_studio.core.outputs.tables import data_num

    lines = 0
    for name, project in projects.items():
        for (pid, unit), row in _bom_rows(project).items():
            derived = next(d for d in explain_part(project, pid) if d.unit == unit)
            assert derived.id == "part-bom"
            assert data_num(derived.value) == row[6], (name, pid, unit)
            # the lines the reader sees add up to the quantity
            parts = [s.value for s in derived.steps[:-1]]
            assert math.isclose(sum(parts), derived.value or 0.0, rel_tol=1e-9, abs_tol=1e-9)
            if unit == "m" and row[8] not in ("", "0"):
                assert any("have no length" in m for m in derived.missing), (name, pid)
            lines += 1
    assert lines > 15


def test_contacts_and_accessories_are_counted_as_the_bom_counts_them(
    projects: dict[str, Project],
) -> None:
    from harness_design_studio.core.derive import explain_part
    from harness_design_studio.core.model import Accessory, evolve

    project = projects["flatsat"]
    h = project.harnesses["W001"]
    cable = h.connectors[0]
    wired = {w.from_pin for w in h.wires if w.from_connector == cable.id} | {
        w.to_pin for w in h.wires if w.to_connector == cable.id
    }
    pins = [evolve(p, contact_part="EX-CONTACT") for p in cable.pins]
    sleeve = Accessory(id="A1", kind="sleeving", part_id="EX-SLEEVE", length_mm=200, quantity=3)
    label = Accessory(id="A2", kind="label", part_id="EX-LABEL", quantity=4)
    patched = evolve(
        h,
        connectors=[evolve(cable, pins=pins), *h.connectors[1:]],
        accessories=[sleeve, label],
    )
    project.harnesses["W001"] = patched
    try:
        (contacts,) = explain_part(project, "EX-CONTACT")
        assert contacts.value == len(wired) and contacts.unit == "ea"
        assert "A-BOM-CONTACTS" in contacts.assumptions
        (metres,) = explain_part(project, "EX-SLEEVE")
        assert metres.unit == "m" and math.isclose(metres.value or 0.0, 0.2 * 3)
        (each,) = explain_part(project, "EX-LABEL")
        assert each.unit == "ea" and each.value == 4
        for pid in ("EX-CONTACT", "EX-SLEEVE", "EX-LABEL"):
            for unit in {d.unit for d in explain_part(project, pid)}:
                assert (pid, unit) in _bom_rows(project)
    finally:
        project.harnesses["W001"] = h


def test_explain_takes_a_part_and_says_when_it_is_not_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    templates.create_project(tmp_path / "flat", "flatsat")
    assert main(["explain", str(tmp_path / "flat"), "EX-WIRE-SINGLE"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Part EX-WIRE-SINGLE. BOM quantity (m):") and "A-BOM-NO-ALLOWANCE" in out
    assert main(["explain", str(tmp_path / "flat"), "NOT-A-THING"]) == 2
    assert "is not a wire, a harness or a part" in capsys.readouterr().err


# ---- the contacts of an interface ----------------------------------------------------------


def test_the_contact_verdict_is_the_verdict_of_the_rule(projects: dict[str, Project]) -> None:
    from harness_design_studio.core.derive import contact_current_derivation
    from harness_design_studio.core.model import ConfigFile

    project = projects["flatsat"]
    base = project.config["derating"]
    seen = {"pass": 0, "fail": 0}
    try:
        for factor in (0.5, 0.3):  # as shipped, and low enough that 5 A is too much
            project.config["derating"] = ConfigFile(
                name="derating",
                placeholder=False,
                values={**base.values, "contact_current_factor": factor},
            )
            failing = {f.object_id for f in run_drc(project) if f.rule == "current-over-contact"}
            for i in project.interfaces.values():
                for e in i.endpoints:
                    if e.connector_id is None or i.max_current_a is None:
                        continue
                    d = contact_current_derivation(project, i.id, e.connector_id)
                    if d.check is None:
                        continue
                    assert (not d.check.passes) == (f"{i.id}.{e.connector_id}" in failing)
                    seen["pass" if d.check.passes else "fail"] += 1
                    assert d.value == (d.inputs[1].value or 0) * factor  # type: ignore[operator]
    finally:
        project.config["derating"] = base
    assert seen["pass"] > 0 and seen["fail"] > 0


def test_a_finding_object_can_be_explained_and_what_is_missing_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_design_studio.core.derive import contact_current_derivation

    project = templates.create_project(tmp_path / "flat", "flatsat")
    i = sorted(project.interfaces.values(), key=lambda x: x.id)[0]
    cid = i.endpoints[0].connector_id or ""
    assert main(["explain", str(tmp_path / "flat"), f"{i.id}.{cid}"]) == 0
    assert "Contact current limit:" in capsys.readouterr().out
    gone = contact_current_derivation(project, i.id, "NO-SUCH-CONNECTOR")
    assert gone.value is None and gone.missing
    first = templates.create_project(tmp_path / "first", "first-steps")
    fi = sorted(first.interfaces.values(), key=lambda x: x.id)[0]
    fc = fi.endpoints[0].connector_id or ""
    d = contact_current_derivation(first, fi.id, fc)
    assert d.value is None and any("derating.contact_current_factor" in m for m in d.missing)


# ---- every derivation as files -------------------------------------------------------------


def test_every_derivation_is_written_as_json_and_csv_and_the_same_design_gives_the_same_bytes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import csv as csv_mod

    from harness_design_studio.core.derive_export import CSV_HEADER, explain_all
    from harness_design_studio.core.io.loader import load_project

    templates.create_project(tmp_path / "flat", "flatsat")
    assert main(["explain", str(tmp_path / "flat"), "--all", "--out", str(tmp_path / "a")]) == 0
    assert "derivations written" in capsys.readouterr().out
    assert main(["explain", str(tmp_path / "flat"), "--all", "--out", str(tmp_path / "b")]) == 0
    for name in ("derivations.json", "derivations.csv"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    project = load_project(tmp_path / "flat").project
    found = explain_all(project)
    doc = json.loads((tmp_path / "a" / "derivations.json").read_text(encoding="utf-8"))
    assert doc["format"] == 3 and doc["tool_version"] and len(doc["derivations"]) == len(found)
    assert doc["derivations"] == [d.to_dict() for d in found]
    with (tmp_path / "a" / "derivations.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv_mod.reader(fh))
    assert rows[0] == CSV_HEADER and len(rows) == len(found) + 1
    by = {(r[0], r[1]): r for r in rows[1:]}
    length = by[("wire-length", "Wire W001-001")]
    assert length[3] == "3.45" and length[4] == "m"
    limit = by[("wire-current-limit", "Wire W001-001")]
    assert limit[6:10] == ["0.8", "1.08", "0.28", "pass"]
    # no time, user or path in the files
    text = (tmp_path / "a" / "derivations.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in text and "T00:" not in text


def test_the_ways_of_calling_explain_that_make_no_sense_are_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    templates.create_project(tmp_path / "flat", "flatsat")
    flat = str(tmp_path / "flat")
    assert main(["explain", flat]) == 2
    assert main(["explain", flat, "W001", "--all", "--out", str(tmp_path / "o")]) == 2
    assert main(["explain", flat, "--all"]) == 2
    assert main(["explain", flat, "W001", "--out", str(tmp_path / "o")]) == 2
    err = capsys.readouterr().err
    assert "give either OBJECT or --all" in err and "--all needs --out" in err
    assert "--out goes with --all" in err and not (tmp_path / "o").exists()
