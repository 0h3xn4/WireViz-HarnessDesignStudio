"""D-191, S10: the definition of done of the transparency work, as acceptance tests.

The audit (`docs/transparency_audit.md`, section 7) tested four things and found that three failed or
passed in part. This file asks the same four again, of the tool as it is now:

(a) any number can be traced to its inputs and logic in under a minute (the 16 numbers have their own
    test, `test_trace_16_numbers.py`; here three of them are asked again, cold, and timed);
(b) any assumption, constant, margin or rule can be changed without editing code: five built-in
    choices (the round trip of the voltage drop, the service loops, the bundle basis, the drop model,
    what blocks "Ready to build") and a rule of an extension file are changed with
    `settings --set` or by editing the file, and the result AND its explanation change as a hand
    calculation says;
(c) a colleague's result is reproduced from an exported file alone, on all four examples, by a script
    that imports nothing of the tool;
(d) a result is explained in a review: for one finding of each rule that compares a number with a
    limit, `explain_finding` gives the actual value, the limit, the margin, the source of every input
    and the assumptions, with nothing unknown.
"""

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from harness_design_studio import api
from harness_design_studio.core import templates
from harness_design_studio.core.derive import Derivation, render
from harness_design_studio.core.derive_rules import INFO, LIMIT
from harness_design_studio.core.drc.standard_rules import emc_class_bundles
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import Project, evolve
from tests.helpers import within
from tests.test_open_data import EXAMPLES, engineer, load_script
from tests.test_s1_rules import _flat, _rule, _set
from tools import trace_numbers
from tools.trace_numbers import command

ROOT = Path(__file__).resolve().parents[1]
WIRE = "W001-001"


# ---- (a) a number in under a minute ------------------------------------------------------------------


@pytest.mark.perf
def test_a_numbers_asked_cold_are_traced_in_under_a_minute(tmp_path: Path) -> None:
    folders = trace_numbers.make_projects(tmp_path)
    for n in (2, 9, 16):  # a calculation, a finding with its limit, a number that is not decided
        row = trace_numbers.ROWS[n - 1]
        got = trace_numbers.resolve(row, trace_numbers.Session(folders[row.project]))
        assert got.complete, (n, got.problems)
        within(got.seconds, 60, f"number {n}: {row.number}")


# ---- (b) change an assumption without editing code ---------------------------------------------------


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("dod-base") / "flatsat"
    api.create_project(folder, "flatsat")
    return folder


@pytest.fixture
def work(base: Path, tmp_path: Path) -> Path:
    folder = tmp_path / "flatsat"
    shutil.copytree(base, folder)
    return folder


def _derivation(folder: Path, obj: str, kind: str) -> Derivation:
    return next(d for d in api.explain(folder, obj) if d.id == kind)


def _input(d: Derivation, name: str) -> Any:
    return next(i for i in d.inputs if i.name.startswith(name))


def _set_value(folder: Path, assignment: str) -> None:
    command("settings", str(folder), "--set", assignment)


def _drop(current: float, rho: float, length: float, awg: int, conductors: int) -> float:
    """The voltage drop, from the definition of the gauge and Ohm's law, written out here."""
    diameter_mm = float(0.127 * 92 ** ((36 - awg) / 39))
    area_m2 = math.pi / 4 * diameter_mm**2 * 1e-6
    return current * rho * length / area_m2 * conductors


def test_b1_the_conductors_counted_in_the_drop_are_a_setting(work: Path) -> None:
    before = _derivation(work, WIRE, "wire-voltage-drop")
    assert before.value == pytest.approx(_drop(0.8, 1.7e-8, 3.45, 24, 2), rel=1e-9)
    assert _input(before, "Conductors counted").value == 2
    _set_value(work, "model.return_path_conductors=1")
    after = _derivation(work, WIRE, "wire-voltage-drop")
    assert after.value == pytest.approx(_drop(0.8, 1.7e-8, 3.45, 24, 1), rel=1e-9)
    assert before.value is not None and after.value == pytest.approx(before.value / 2, rel=1e-9)
    n = _input(after, "Conductors counted")
    assert (
        n.value == 1 and "return_path_conductors" in n.source
    )  # the explanation names the setting
    listed = json.loads(command("settings", str(work), "--json"))["settings"]
    row = next(s for s in listed if s["id"] == "model.return_path_conductors")
    assert row["value"] == 1 and row["origin"] == "project" and row["default"] == 2


def test_b2_the_service_loops_are_a_setting(work: Path) -> None:
    before = _derivation(work, WIRE, "wire-length")
    path = math.fsum(float(i.value) for i in before.inputs if i.name.startswith("Segment"))  # type: ignore[arg-type]
    assert before.value == pytest.approx(path + 2 * 0.1)
    _set_value(work, "model.service_loops_per_wire=3")
    assert api.generate(work).ok
    after = _derivation(work, WIRE, "wire-length")
    assert after.value == pytest.approx(path + 3 * 0.1)
    assert any(
        "3 × 0.1" in s.expression for s in after.steps
    )  # the explanation shows the new count
    _set_value(work, "model.service_loops_per_wire=0")
    assert api.generate(work).ok
    none = _derivation(work, WIRE, "wire-length")
    assert none.value == pytest.approx(path) and any("0 × 0.1" in s.expression for s in none.steps)


def test_b3_the_bundle_basis_is_a_setting(work: Path) -> None:
    wire = "W002-001"  # 26 wires in its harness, 2 of which carry a current
    _set_value(
        work,
        "derating.bundle_factor_by_count=" + json.dumps({"1": 1, "5": 0.7, "20": 0.5, "100": 0.4}),
    )
    before = _derivation(work, wire, "wire-current-limit")
    ampacity, temperature = 10.0, 0.9  # AWG 16 of the example table, and its temperature factor
    assert _input(before, "Base ampacity").value == ampacity
    assert before.value == pytest.approx(
        ampacity * 0.4 * temperature
    )  # 26 wires: the entry up to 100
    _set_value(work, 'model.bundle_basis="loaded_wires"')
    after = _derivation(work, wire, "wire-current-limit")
    assert after.value == pytest.approx(ampacity * 0.7 * temperature)  # 2 wires: the entry up to 5
    k = _input(after, "Bundle factor K")
    assert k.value == 0.7 and "carry a current" in k.source  # the explanation says what was counted


def test_b4_the_drop_model_is_a_setting(work: Path) -> None:
    _set_value(work, "derating.max_ambient_temperature_c=60")
    before = _derivation(work, WIRE, "wire-voltage-drop")
    _set_value(work, 'model.drop_model="dc_at_ambient"')
    after = _derivation(work, WIRE, "wire-voltage-drop")
    factor = 1 + 0.00393 * (
        60 - 20
    )  # the copper coefficient and the 20 degC reference of the defaults
    assert before.value is not None
    assert after.value == pytest.approx(before.value * factor, rel=1e-9)
    assert after.value == pytest.approx(_drop(0.8, 1.7e-8 * factor, 3.45, 24, 2), rel=1e-9)
    rho = _input(after, "Resistivity")
    assert rho.value == pytest.approx(1.7e-8 * factor) and "dc_at_ambient" in render(after)


def test_b5_what_blocks_ready_to_build_is_a_setting(work: Path) -> None:
    before = _derivation(work, "W001", "readiness")
    assert (before.text or "").startswith("yes")
    _set_value(
        work, 'model.readiness_blocking=["Wires without a length", "Wires without strip lengths"]'
    )
    after = _derivation(work, "W001", "readiness")
    assert (after.text or "").startswith("no")
    strip = next(
        d
        for d in api.explain(work, "W001")
        if d.id == "readiness-check" and "strip lengths" in d.subject
    )
    assert (
        strip.value == 18
    )  # the 18 wires of W001 have no strip length (hand count of the wire list)
    assert "Wires without strip lengths" in render(
        after
    )  # the explanation names the blocking check
    _set_value(work, 'model.readiness_blocking=["Wires without strip lengths"]')
    only = _derivation(work, "W001", "readiness")
    assert (only.text or "").startswith("no")


def _write_extension(folder: Path, thinnest: int) -> None:
    source = ROOT / "docs" / "examples" / "extensions" / "minimum-wire-gauge-power.json"
    doc = json.loads(source.read_text(encoding="utf-8"))
    doc["parameters"]["thinnest_awg"]["value"] = thinnest
    target = folder / "extensions"
    target.mkdir(exist_ok=True)
    (target / source.name).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    (target / "enabled.json").write_text(
        json.dumps(
            {
                "format": "harness-design-studio-extensions-enabled",
                "format_version": 1,
                "declarative": [source.name],
                "plugins": [],
            }
        ),
        encoding="utf-8",
    )


def test_b6_a_rule_of_an_extension_file_is_changed_by_editing_the_file(work: Path) -> None:
    finding = f"x-min-gauge-power.{WIRE}"
    _write_extension(work, 22)  # power wires may be AWG 22 or thicker; the flatsat's are AWG 24
    (d,) = api.explain_finding(work, finding)
    assert d.check is not None and not d.check.passes
    assert (d.check.actual, d.check.limit, d.check.margin) == (24, 22, -2)  # hand: 22 - 24
    shown = render(d)
    assert (
        "over the limit by 2 AWG" in shown and "by 2 AWG (" not in shown
    )  # a difference has no mm2
    _write_extension(work, 23)
    (d,) = api.explain_finding(work, finding)
    assert d.check is not None and (d.check.limit, d.check.margin) == (23, -1)
    _write_extension(work, 24)  # at the limit is not over it: no finding
    assert finding not in {f.id for f in api.run_checks(work).findings}
    # nothing of the tool was edited, and the file is named in the explanation of the other values
    _write_extension(work, 22)
    assert finding in {f.id for f in api.run_checks(work).findings}


# ---- (c) a colleague's result from an exported file alone -------------------------------------------


@pytest.fixture(scope="module")
def exported(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Each example, with example values where it ships without (as `test_open_data` does), exported."""
    base_dir = tmp_path_factory.mktemp("dod-open-data")
    flat = templates.create_project(base_dir / "flatsat", "flatsat")
    out: dict[str, Path] = {}
    for name in EXAMPLES:
        project = flat if name == "flatsat" else templates.create_project(base_dir / name, name)
        if name != "flatsat":
            engineer(project, flat)
        folder = base_dir / f"data-{name}"
        api.export_data(project, folder)
        out[name] = folder
    return out


@pytest.mark.slow
@pytest.mark.parametrize("name", EXAMPLES)
def test_c_a_result_is_reproduced_from_the_exported_files_alone(
    name: str, exported: dict[str, Path], tmp_path: Path
) -> None:
    alone = tmp_path / "from-a-colleague"
    shutil.copytree(
        exported[name], alone
    )  # only the files a colleague would send: no project beside them
    script = load_script()
    result = script.reproduce(alone)
    assert result["differences"] == [], (name, result["differences"][:3])
    seen = result["recomputed"]
    assert (
        seen["limits"] > 0 and seen["drops"] > 0 and seen["gauges"] > 0 and seen["bom_lines"] > 0
    ), (name, seen)
    done = subprocess.run(
        [sys.executable, "-I", str(ROOT / "docs" / "examples" / "open-data" / "reproduce.py"), str(alone)],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr


# ---- (d) a result explained in a review --------------------------------------------------------------


def _situation(rule_id: str, folder: Path) -> Project:
    """A project in which the rule has a finding, made only by setting values and editing the design."""
    if rule_id in ("current-over-wire", "bundle-current"):
        name = "flatsat-tight" if rule_id == "current-over-wire" else "flatsat-own-bundle-table"
        project = _flat(folder, name)
        if rule_id == "bundle-current":
            table = dict(project.config["derating"].values.get("ampacity_a_by_awg") or {})
            table.update({"22": 0.4, "24": 0.3})
            _set(project, "derating", ampacity_a_by_awg=table)
        return project
    project = _flat(folder)
    if rule_id == "voltage-drop":
        _set(project, "derating", max_voltage_drop_v=0.3)
    elif rule_id == "current-over-contact":
        _set(project, "derating", contact_current_factor=0.05)
    elif rule_id == "spare-pins-low":
        _set(project, "derating", spare_pin_fraction=0.6)
    elif rule_id == "connector-voltage":
        _set(
            project,
            "derating",
            connector_voltage_factor_withstand=0.25,
            connector_voltage_factor_rated=0.75,
        )
        for pid in {c.part_id for c in project.connectors.values()}:
            ratings = {
                **project.parts[pid].ratings,
                "dielectric_withstand_v": 200.0,
                "rated_voltage_v": 100.0,
            }
            project.parts[pid] = evolve(project.parts[pid], ratings=ratings)
        for i in project.interfaces.values():
            project.interfaces[i.id] = evolve(i, voltage_v=60.0)  # the limit is 50 V
    elif rule_id == "wire-voltage":
        _set(project, "derating", wire_voltage_factor=0.5)
        for pid in {w.part_id for h in project.harnesses.values() for w in h.wires if w.part_id}:
            ratings = {**project.parts[pid].ratings, "rated_voltage_v": 100.0}
            project.parts[pid] = evolve(project.parts[pid], ratings=ratings)
        for i in project.interfaces.values():
            project.interfaces[i.id] = evolve(i, voltage_v=60.0)
    elif rule_id == "temperature-margin":
        _set(project, "derating", max_ambient_temperature_c=100.0, connector_temperature_margin_c=10.0, wire_temperature_margin_c=10.0)  # fmt: skip
        everything = {c.part_id for c in project.connectors.values()}
        everything |= {c.part_id for h in project.harnesses.values() for c in h.connectors}
        everything |= {w.part_id for h in project.harnesses.values() for w in h.wires if w.part_id}
        for pid in everything:
            project.parts[pid] = evolve(project.parts[pid], ratings={**project.parts[pid].ratings, "max_temp_c": 105.0})  # fmt: skip
    elif rule_id == "mating-cycles":
        _set(project, "derating", max_mating_cycles=50)
        parts = {c.part_id for c in project.connectors.values()}
        parts |= {c.part_id for h in project.harnesses.values() for c in h.connectors}
        for pid in parts:
            project.parts[pid] = evolve(project.parts[pid], ratings={**project.parts[pid].ratings, "mating_cycles": 10.0})  # fmt: skip
    elif rule_id == "power-return-adjacent":
        _set(project, "generation", power_return_gap_pins=1)
    elif rule_id == "pin-shared":
        h = project.harnesses[sorted(project.harnesses)[0]]
        wires = list(h.wires)
        wires[1] = evolve(wires[1], to_connector=wires[0].to_connector, to_pin=wires[0].to_pin)
        project.harnesses[h.id] = evolve(h, wires=wires)
    elif rule_id == "emc-class-split":
        _set(project, "segmentation", mode="per_connector_pair")
        generate_project(project)
        pair = ("OBC1", "PCDU1")
        for i in project.interfaces.values():
            if tuple(sorted(e.unit_id for e in i.endpoints)) == pair:
                project.interface_types[i.type_id] = evolve(
                    project.interface_types[i.type_id], emc_class="A"
                )
        _set(project, "emc", same_class_one_bundle=True)
        assert emc_class_bundles(project)
    else:
        raise AssertionError(rule_id)
    return project


LIMIT_RULES = sorted(r for r, info in INFO.items() if info.form == LIMIT)


def test_d_the_rules_with_a_limit_are_the_twelve_of_the_documentation() -> None:
    assert len(LIMIT_RULES) == 12 and set(LIMIT_RULES) >= {
        "current-over-wire",
        "voltage-drop",
        "current-over-contact",
    }


@pytest.mark.parametrize("rule_id", LIMIT_RULES)
def test_d_a_finding_of_each_limit_rule_is_explained_with_no_unknowns(
    rule_id: str, tmp_path: Path
) -> None:
    project = _situation(rule_id, tmp_path)
    assert any(h for h in _rule(rule_id).check(project)), rule_id  # the rule has a finding here
    result = api.run_checks(project)
    finding = next(f for f in result.findings if f.rule == rule_id)
    derivations = api.explain_finding(project, finding.id)
    assert derivations, rule_id
    d = derivations[0]
    c = d.check
    assert c is not None and not c.passes, (rule_id, render(d))
    assert c.unit, rule_id
    for number in (c.actual, c.limit, c.margin):
        assert isinstance(number, int | float) and math.isfinite(number), (rule_id, number)
    # the sign of the margin is the verdict: negative where the value is on the wrong side of its limit
    assert c.margin < 0, (rule_id, c.margin)
    assert d.equation and d.inputs and not d.missing, (rule_id, d.missing)
    for i in d.inputs:
        assert i.source and i.source.strip(), (rule_id, i.name)
        assert "unknown" not in i.source.lower() and "unknown" not in i.name.lower(), (
            rule_id,
            i.name,
        )
    assert all(i.value is not None for i in d.inputs), rule_id  # nothing the limit needs is unset
    text = render(d)
    assert "Check:" in text and "unknown" not in text.lower() and "None" not in text, (
        rule_id,
        text,
    )
    # what it rests on: an assumption of the registry, or, for a rule that has none built in, the
    # reference line that says where the limit comes from (pin-shared, wire-voltage, emc-class-split)
    assert d.assumptions or d.reference, rule_id
    assert ("Rests on:" in text) if d.assumptions else (f"Reference: {d.reference}" in text), (
        rule_id
    )
    data = d.to_dict()
    assert data["check"]["margin"] == c.margin and (data["assumptions"] or d.reference), rule_id
