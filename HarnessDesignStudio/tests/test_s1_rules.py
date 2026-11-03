"""D-191, S1: every design rule has an explanation, and the limit it shows is the limit the rule used.

The rules of the registry that compare a number with a limit give a derivation with the equation,
the inputs, the steps and the check: actual, limit and margin. The verdict of that check must be the
verdict of the rule for every object (a finding exists exactly when the check fails). A rule that has
no numeric limit says so: "this rule is a yes/no check: it compares X with Y". A test walks the whole
registry and fails for a rule that has no explanation, so none can be forgotten."""

import copy
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_design_studio.core import checks, templates
from harness_design_studio.core.derive import (
    EXPLAINABLE_RULES,
    LOGICAL_RULES,
    OTHER_RULES,
    Derivation,
    explain_finding,
    render,
)
from harness_design_studio.core.derive_rules import INFO, LIMIT, YES_NO, compares
from harness_design_studio.core.drc import RULES
from harness_design_studio.core.drc import run as run_drc
from harness_design_studio.core.drc.standard_rules import (
    _temperature_users,
    emc_class_bundles,
)
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import ConfigFile, Project, evolve
from tools.numbers_snapshot import SCENARIOS

DOCS = Path(__file__).resolve().parent.parent / "docs"
FIRST_THREE = ("current-over-wire", "voltage-drop", "current-over-contact")
ALL_RULES = [r.id for r in RULES] + list(OTHER_RULES)
LOWER_LIMITS = (
    "spare-pins-low",
    "mating-cycles",
    "power-return-adjacent",
)  # the value must be at least


def _set(project: Project, file: str, **values: object) -> None:
    base = project.config[file]
    project.config[file] = ConfigFile(
        name=file, placeholder=False, values={**copy.deepcopy(base.values), **values}
    )


def _flat(folder: Path, name: str = "flatsat") -> Project:
    example, change = SCENARIOS[name]
    project = templates.create_project(folder / name, example)
    if not project.harnesses:
        generate_project(project)
    if change is not None:
        change(project)
    return project


@pytest.fixture(scope="module")
def flat() -> Iterator[Project]:
    with tempfile.TemporaryDirectory(prefix="s1-rules-") as tmp:
        yield _flat(Path(tmp))


@pytest.fixture
def work(tmp_path: Path) -> Project:
    return _flat(tmp_path)


# ---- the registry: no rule without an explanation --------------------------------------------


def test_every_rule_of_the_registry_has_an_explanation() -> None:
    assert len(RULES) == 39
    assert set(INFO) == set(ALL_RULES), "a rule is missing in derive_rules.INFO, or one is stale"
    assert frozenset(ALL_RULES) == EXPLAINABLE_RULES
    for rule_id in ALL_RULES:
        info = INFO[rule_id]
        assert info.form in (LIMIT, YES_NO) and info.compares, rule_id
        if info.form == LIMIT and rule_id not in FIRST_THREE:
            assert info.build is not None, rule_id  # a limit rule must derive its limit
        if info.form == YES_NO:
            assert compares(rule_id).startswith("this rule is a yes/no check: it compares ")


def test_the_logical_rules_are_the_ones_of_the_rule_documentation() -> None:
    from tools.gen_rule_docs import LOGICAL

    assert tuple(row[0] for row in LOGICAL) == LOGICAL_RULES


def test_a_rule_that_has_no_limit_says_so_for_every_finding_of_the_examples(tmp_path: Path) -> None:
    """Every finding of the packaged examples and of the situations of the numbers snapshot can be
    explained, and a yes/no rule says what it compares."""
    seen_rules: set[str] = set()
    for name in ("flatsat", "first-steps", "small-satellite", "flatsat-tight", "flatsat-override"):
        project = _flat(tmp_path, name)
        findings = [*checks.find(project), *run_drc(project)]
        for f in findings:
            found = explain_finding(project, f.rule, f.object_id)
            assert found, (name, f.rule, f.object_id)
            seen_rules.add(f.rule)
            d = found[0]
            if INFO[f.rule].form == YES_NO:
                assert d.id == "rule-check" and d.equation == compares(f.rule)
                assert d.check is None and d.text
                assert "this rule is a yes/no check" in render(d)
            elif f.rule not in FIRST_THREE:
                assert d.id == "rule-limit" and d.check is not None
            if d.check is not None:
                assert not d.check.passes, (name, f.rule, f.object_id)
    assert len(seen_rules) >= 4  # (the examples carry real findings, not none)


def test_a_yes_no_rule_shows_the_finding_the_configuration_and_what_it_saw(work: Project) -> None:
    _set(work, "emc", shield_bonding="both_ends_backshell")
    findings = [f for f in run_drc(work) if f.rule == "shield-bonding"]
    assert findings
    (d,) = explain_finding(work, "shield-bonding", findings[0].object_id)
    assert d.id == "rule-check" and d.text == findings[0].title
    names = {i.name for i in d.inputs}
    assert {"Shield group", "Ends of the group", "Grounding concept", "Bonding required"} <= names
    assert any(i.name.startswith("Statement of the finding") for i in d.inputs)
    assert "ECSS-E-ST-20-07_0080041" in d.reference  # requirement IDs by ID, no text of a standard


def test_a_limit_rule_whose_object_is_gone_gives_nothing(work: Project) -> None:
    for rule_id in ("spare-pins-low", "connector-voltage", "wire-voltage", "temperature-margin",
                    "mating-cycles", "power-return-adjacent", "bundle-current", "pin-shared",
                    "emc-class-split"):  # fmt: skip
        assert explain_finding(work, rule_id, "NO-SUCH.OBJECT") == [], rule_id
    assert explain_finding(work, "no-such-rule", "W001-001") == []


# ---- the rules with a number: the verdict of the derivation is the verdict of the rule ---------


def _rule(rule_id: str):  # type: ignore[no-untyped-def]
    return next(r for r in RULES if r.id == rule_id)


def _agree(
    project: Project, rule_id: str, candidates: list[str], unchecked: bool = False
) -> dict[str, int]:
    """For every candidate object: the check of the derivation fails exactly when the rule has a
    finding on the object. Returns how many passed and failed, and checks the numbers shown."""
    flagged = {h.object_id for h in _rule(rule_id).check(project)}
    seen = {"pass": 0, "fail": 0}
    for oid in candidates:
        found = explain_finding(project, rule_id, oid)
        assert found, (rule_id, oid)
        d = found[0]
        if d.check is None and unchecked:  # no current, or no limit: the rule says nothing either
            assert d.missing or d.value is None, (rule_id, oid)
            assert oid not in flagged, (rule_id, oid)
            continue
        assert d.id == "rule-limit" and d.check is not None, (rule_id, oid, render(d))
        c = d.check
        assert (not c.passes) == (oid in flagged), (rule_id, oid, c.text)
        assert d.value == c.limit and c.unit
        lower = rule_id in LOWER_LIMITS  # a minimum: the margin is what the value has over it
        assert c.margin == pytest.approx((c.actual - c.limit) if lower else (c.limit - c.actual))
        seen["pass" if c.passes else "fail"] += 1
    assert flagged <= set(candidates), (rule_id, flagged - set(candidates))
    return seen


def test_spare_pins(work: Project) -> None:
    ids = [c.id for c in work.connectors.values()]
    _set(work, "derating", spare_pin_fraction=0.6)
    seen = _agree(work, "spare-pins-low", ids)
    assert seen["fail"] > 0 and seen["pass"] > 0
    d = explain_finding(
        work, "spare-pins-low", next(iter(_rule("spare-pins-low").check(work))).object_id
    )[0]
    assert d.assumptions == ("A-SPARE-PINS",) and d.check is not None
    assert d.steps[0].value == pytest.approx(0.6 * float(d.inputs[1].value or 0))  # fraction x pins
    # a fraction that is not set gives no limit and says what to set
    _set(work, "derating", spare_pin_fraction=None)
    (none,) = explain_finding(work, "spare-pins-low", ids[0])
    assert none.value is None and "derating.spare_pin_fraction" in none.missing[0]


def test_connector_voltage(work: Project) -> None:
    _set(
        work,
        "derating",
        connector_voltage_factor_withstand=0.25,
        connector_voltage_factor_rated=0.75,
    )
    for pid in {c.part_id for c in work.connectors.values()}:
        work.parts[pid] = evolve(
            work.parts[pid],
            ratings={
                **work.parts[pid].ratings,
                "dielectric_withstand_v": 200.0,
                "rated_voltage_v": 100.0,
            },
        )
    ifaces = sorted(work.interfaces.values(), key=lambda i: i.id)
    for n, i in enumerate(ifaces):
        work.interfaces[i.id] = evolve(i, voltage_v=40.0 if n % 2 else 60.0)  # limit is 50 V
    ids = [f"{i.id}.{e.connector_id}" for i in ifaces for e in i.endpoints if e.connector_id]
    seen = _agree(work, "connector-voltage", ids)
    assert seen["fail"] > 0 and seen["pass"] > 0
    d = explain_finding(work, "connector-voltage", ids[0])[0]
    assert d.value == 50.0 and [s.value for s in d.steps[:2]] == [
        50.0,
        75.0,
    ]  # the lower limit counts
    assert d.assumptions == ("A-CONNECTOR-VOLTAGE",)


def test_wire_voltage(work: Project) -> None:
    _set(work, "derating", wire_voltage_factor=0.5)
    for pid in {w.part_id for h in work.harnesses.values() for w in h.wires if w.part_id}:
        work.parts[pid] = evolve(
            work.parts[pid], ratings={**work.parts[pid].ratings, "rated_voltage_v": 100.0}
        )
    for n, i in enumerate(sorted(work.interfaces.values(), key=lambda i: i.id)):
        work.interfaces[i.id] = evolve(i, voltage_v=40.0 if n % 2 else 60.0)
    ids = [w.id for h in work.harnesses.values() for w in h.wires]
    seen = _agree(work, "wire-voltage", ids)
    assert seen["fail"] > 0 and seen["pass"] > 0


def test_temperature(work: Project) -> None:
    _set(work, "derating", max_ambient_temperature_c=100.0, connector_temperature_margin_c=10.0,
         wire_temperature_margin_c=10.0)  # fmt: skip
    cp = sorted(
        {c.part_id for c in work.connectors.values()}
        | {c.part_id for h in work.harnesses.values() for c in h.connectors}
    )
    for n, pid in enumerate(cp):
        work.parts[pid] = evolve(
            work.parts[pid],
            ratings={**work.parts[pid].ratings, "max_temp_c": 105.0 if n % 2 else 125.0},
        )
    wp = sorted({w.part_id for h in work.harnesses.values() for w in h.wires if w.part_id})
    for n, pid in enumerate(wp):
        work.parts[pid] = evolve(
            work.parts[pid],
            ratings={**work.parts[pid].ratings, "max_temp_c": 105.0 if n % 2 == 0 else 125.0},
        )
    ids = [o for what in ("connector", "wire") for o, _p in _temperature_users(work, what)]
    seen = _agree(work, "temperature-margin", ids)
    assert seen["fail"] > 0 and seen["pass"] > 0
    d = explain_finding(work, "temperature-margin", ids[0])[0]
    assert d.assumptions == ("A-AMBIENT-ONLY",) and d.unit == "degC"


def test_mating_cycles(work: Project) -> None:
    _set(work, "derating", max_mating_cycles=50)
    parts = sorted(
        {c.part_id for c in work.connectors.values()}
        | {c.part_id for h in work.harnesses.values() for c in h.connectors}
    )
    for n, pid in enumerate(parts):
        work.parts[pid] = evolve(
            work.parts[pid],
            ratings={**work.parts[pid].ratings, "mating_cycles": 10.0 if n % 2 else 500.0},
        )
    seen = _agree(work, "mating-cycles", [f"mating-cycles.{p}" for p in parts])
    assert seen["fail"] > 0 and seen["pass"] > 0


def test_power_and_return_pins(work: Project) -> None:
    _set(work, "generation", power_return_gap_pins=1)
    hits = list(_rule("power-return-adjacent").check(work))
    assert hits, "the generated power pairs sit side by side"
    ids = [h.object_id for h in hits]
    seen = _agree(work, "power-return-adjacent", ids)
    assert seen == {"pass": 0, "fail": len(ids)}
    # a return two pins away, with a free contact between, is not a finding, and the derivation agrees
    conn = next(c for c in work.connectors.values() if any(p.interface_id for p in c.pins))
    power = [p for p in conn.pins if p.interface_id and p.signal]
    first, second = power[0], power[1]
    pins = list(conn.pins)
    k0, k1 = pins.index(first), pins.index(second)
    assert k1 == k0 + 1
    moved = evolve(second, signal=None, interface_id=None)
    pins[k1] = evolve(pins[k1], signal=None, interface_id=None)
    pins[k1 + 1] = evolve(pins[k1 + 1], signal=second.signal, interface_id=second.interface_id)
    work.connectors[conn.id] = evolve(conn, pins=pins)
    del moved
    object_id = f"{conn.id}.{first.id}+{pins[k1 + 1].id}"
    assert object_id not in {h.object_id for h in _rule("power-return-adjacent").check(work)}
    (d,) = explain_finding(work, "power-return-adjacent", object_id)
    assert d.check is not None and d.check.passes and d.check.actual == 1 and d.check.limit == 1


def test_bundle_current(tmp_path: Path) -> None:
    project = _flat(tmp_path, "flatsat-own-bundle-table")
    table = dict(project.config["derating"].values.get("ampacity_a_by_awg") or {})
    table.update({"22": 0.4, "24": 0.3})
    _set(project, "derating", ampacity_a_by_awg=table)
    ids = [w.id for h in project.harnesses.values() for w in h.wires]
    seen = _agree(project, "bundle-current", ids, unchecked=True)
    assert seen["fail"] > 0 and seen["pass"] > 0
    wire = next(iter(_rule("bundle-current").check(project))).object_id
    d = explain_finding(project, "bundle-current", wire)[0]
    assert d.assumptions == ("A-BUNDLE-ALL", "A-BUNDLE-CURRENT")
    assert any(i.name == "Temperature factor" for i in d.inputs)


def test_pin_shared_and_emc_class_split(tmp_path: Path) -> None:
    project = _flat(tmp_path)
    ids = sorted(project.harnesses)
    assert _agree(project, "pin-shared", ids) == {"pass": len(ids), "fail": 0}
    h = project.harnesses[ids[0]]
    first, second = h.wires[0], h.wires[1]
    wires = list(h.wires)
    wires[1] = evolve(second, to_connector=first.to_connector, to_pin=first.to_pin)
    project.harnesses[h.id] = evolve(h, wires=wires)
    seen = _agree(project, "pin-shared", ids)
    assert seen["fail"] == 1 and seen["pass"] == len(ids) - 1
    d = explain_finding(project, "pin-shared", h.id)[0]
    assert d.check is not None and d.check.actual == 2 and d.check.limit == 1
    assert d.steps and first.id in d.steps[0].expression

    # one EMC class between two devices in two harnesses: per connector pair, two interfaces
    split = _flat(tmp_path / "split")
    _set(split, "segmentation", mode="per_connector_pair")
    generate_project(split)
    pair = ("OBC1", "PCDU1")
    mine = [
        i
        for i in split.interfaces.values()
        if tuple(sorted(e.unit_id for e in i.endpoints)) == pair
    ]
    assert len(mine) >= 2
    for t in {i.type_id for i in mine}:
        split.interface_types[t] = evolve(split.interface_types[t], emc_class="A")
    _set(split, "emc", same_class_one_bundle=True)
    keys = [f"emc-class.{c}.{a}.{b}" for (c, a, b) in emc_class_bundles(split)]
    assert keys
    seen = _agree(split, "emc-class-split", keys)
    assert seen["fail"] >= 1


def _numeric_rules() -> list[str]:
    return [r for r in ALL_RULES if INFO[r].form == LIMIT]


def test_the_table_of_the_page_is_the_table_of_the_code() -> None:
    from tools.gen_rule_limit_docs import TARGET, render_page

    current = TARGET.read_text(encoding="utf-8")
    assert render_page(current) == current, "run: python -m tools.gen_rule_limit_docs"


def test_the_rules_with_a_limit_are_listed_in_the_documentation() -> None:
    page = (DOCS / "models" / "rule-limits.md").read_text(encoding="utf-8")
    for rule_id in ALL_RULES:
        assert f"`{rule_id}`" in page, rule_id
    assert len(_numeric_rules()) == 12  # 3 explained since step 1 and 9 new
    for rule_id in _numeric_rules():
        assert INFO[rule_id].compares in page, rule_id


def test_the_derivations_of_the_rules_are_data(work: Project) -> None:
    _set(work, "derating", spare_pin_fraction=0.6)
    oid = next(iter(_rule("spare-pins-low").check(work))).object_id
    (d,) = explain_finding(work, "spare-pins-low", oid)
    data = d.to_dict()
    assert data["id"] == "rule-limit" and data["check"]["passes"] is False
    assert set(data["check"]) == {"actual", "limit", "unit", "passes", "margin", "text"}
    assert isinstance(d, Derivation)
