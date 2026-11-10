# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""D-191, S3: the models the tool can choose between. The default of each is what the tool did
before; every alternative is checked against a hand calculation, and the explanation says which
model was used."""

from pathlib import Path

import pytest

from harness_design_studio.core import settings, templates
from harness_design_studio.core.derive import explain_wire
from harness_design_studio.core.drc import run as run_drc
from harness_design_studio.core.generate import bundle
from harness_design_studio.core.generate.bundle import BundleWire, bundle_counts, bundle_size
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.generate.sizing import bundle_k
from harness_design_studio.core.model import ConfigFile, Project

TABLE = {"1": 1.0, "2": 0.9, "5": 0.8, "10": 0.7, "20": 0.6, "40": 0.5}


def with_model(project: Project, **values: object) -> None:
    project.config["model"] = ConfigFile(name="model", placeholder=False, values=dict(values))


def with_table(project: Project) -> None:
    d = project.config["derating"]
    project.config["derating"] = ConfigFile(
        name="derating",
        placeholder=d.placeholder,
        values={**d.values, "bundle_factor_by_count": TABLE},
    )


# ---- the bundle of a wire ----------------------------------------------------------------


def test_the_bundle_bases_count_as_a_hand_calculation_does() -> None:
    wires = [
        BundleWire("A", True, ("s1", "s2")),
        BundleWire("B", True, ("s1",)),
        BundleWire("C", False, ("s3",)),
        BundleWire("D", True, None),  # no path known
    ]
    assert bundle_counts("all_wires", wires) == {"A": 4, "B": 4, "C": 4, "D": 4}
    # three wires carry a current
    assert bundle_counts("loaded_wires", wires) == {"A": 3, "B": 3, "C": 3, "D": 3}
    # segment s1 carries A and B; s2 only A; s3 only C; D has no path: every wire
    assert bundle_counts("busiest_segment", wires) == {"A": 2, "B": 2, "C": 1, "D": 4}
    assert bundle_counts("busiest_segment", []) == {}


def test_the_default_basis_is_every_wire_and_reproduces_the_numbers(tmp_path: Path) -> None:
    project = templates.create_project(tmp_path / "flat", "flatsat")
    assert bundle.basis(project) == "all_wires"
    for h in project.harnesses.values():
        assert {bundle_size(project, h, w) for w in h.wires} <= {len(h.wires)}


def test_a_basis_that_is_not_known_falls_back_to_every_wire(tmp_path: Path) -> None:
    project = templates.create_project(tmp_path / "flat", "flatsat")
    with_model(project, bundle_basis="nonsense")
    assert bundle.basis(project) == "all_wires"


@pytest.mark.parametrize("name", ["loaded_wires", "busiest_segment"])
def test_generation_the_rules_and_the_explanation_use_the_same_bundle(
    tmp_path: Path, name: str
) -> None:
    project = templates.create_project(tmp_path / "flat", "flatsat")
    with_table(project)
    with_model(project, bundle_basis=name)
    generate_project(project)
    differs = 0
    for h in project.harnesses.values():
        for w in h.wires:
            n = bundle_size(project, h, w)
            differs += n != len(h.wires)
            derivation = explain_wire(project, w.id)[1]
            k = bundle_k(TABLE, n)
            if derivation.value is None:
                continue
            k_input = next(i for i in derivation.inputs if i.name == "Bundle factor K")
            assert k_input.value == k, (w.id, n)
            assert bundle.BASIS_TEXT[name] in k_input.source or name == "all_wires"
    # in a generated harness every wire runs through the one trunk, so the busiest segment is the
    # whole harness; the basis that counts only loaded wires changes the flatsat
    assert (differs > 0) == (name == "loaded_wires")
    # what generation sized does not trip the rule that uses the same count
    assert not [f for f in run_drc(project) if f.rule in ("current-over-wire", "bundle-current")]


def test_a_smaller_bundle_can_make_a_wire_thinner(tmp_path: Path) -> None:
    every = templates.create_project(tmp_path / "a", "flatsat")
    with_table(every)
    generate_project(every)
    loaded = templates.create_project(tmp_path / "b", "flatsat")
    with_table(loaded)
    with_model(loaded, bundle_basis="loaded_wires")
    generate_project(loaded)
    gauges_every = {w.id: w.gauge_awg for h in every.harnesses.values() for w in h.wires}
    gauges_loaded = {w.id: w.gauge_awg for h in loaded.harnesses.values() for w in h.wires}
    assert gauges_every.keys() == gauges_loaded.keys()
    # fewer wires in the bundle never asks for a thicker wire, and in the flatsat it changes some
    assert all((gauges_loaded[k] or 99) >= (gauges_every[k] or 0) for k in gauges_every)
    assert gauges_loaded != gauges_every


def test_the_setting_is_checked(tmp_path: Path) -> None:
    from harness_design_studio.core import configcheck

    project = templates.create_project(tmp_path / "flat", "flatsat")
    with_model(project, bundle_basis="every")
    messages = [i.message for i in configcheck.validate(project)]
    assert any(
        "bundle_basis must be one of all_wires, loaded_wires, busiest_segment" in m
        for m in messages
    )
    assert settings.effective(project, "model", "bundle_basis").origin == "project"


# ---- the length of a generated wire --------------------------------------------------------


def _wire_with_construction(project: Project, construction: str):  # type: ignore[no-untyped-def]
    for h in project.harnesses.values():
        for w in h.wires:
            i = project.interfaces.get(w.interface_id or "")
            if i and project.interface_types[i.type_id].construction == construction:
                return h, w
    return None


def test_the_length_model_adds_take_up_and_allowance_as_a_hand_calculation_does(
    tmp_path: Path,
) -> None:
    project = templates.create_project(tmp_path / "flat", "flatsat")
    single = _wire_with_construction(project, "single")
    twisted = _wire_with_construction(project, "twisted_pair") or _wire_with_construction(
        project, "twisted_shielded_pair"
    )
    assert single is not None and twisted is not None  # both kinds are in the flatsat
    before = {w.id: w.length_m for h in project.harnesses.values() for w in h.wires}
    assert before[single[1].id] == 3.45 or before[single[1].id] is not None
    with_model(
        project,
        length_model="path_loops_allowance_twist",
        cut_allowance_m=0.05,
        twist_takeup_fraction=0.1,
    )
    generate_project(project)
    after = {w.id: w.length_m for h in project.harnesses.values() for w in h.wires}
    for _h, w in [single] + ([twisted] if twisted else []):
        i = project.interfaces[w.interface_id or ""]
        was = before[w.id] or 0.0  # path + 2 x 0.1 as generated before
        is_twisted = (
            project.interface_types[i.type_id].construction in settings.TWISTED_CONSTRUCTIONS
        )
        want = was * (1.1 if is_twisted else 1.0) + 0.05
        assert abs((after[w.id] or 0.0) - want) < 1e-9, (w.id, was, after[w.id], want)
        length = explain_wire(project, w.id)[0]
        assert abs((length.value or 0.0) - want) < 1e-9
        assert "cut allowance" in length.equation and any(
            s.label == "Cut allowance" for s in length.steps
        )
        assert any(s.label.startswith("Take-up of twisting") for s in length.steps) == is_twisted


# ---- the voltage drop ----------------------------------------------------------------------


def _power_wire(project: Project):  # type: ignore[no-untyped-def]
    for h in project.harnesses.values():
        for w in h.wires:
            i = project.interfaces.get(w.interface_id or "")
            if i and i.max_current_a and w.gauge_awg and w.length_m:
                return h, w, i
    raise AssertionError("no wire with a current")


def test_the_ambient_drop_model_corrects_the_resistivity_as_a_hand_calculation_does(
    tmp_path: Path,
) -> None:
    from harness_design_studio.core.generate.sizing import voltage_drop_v

    project = templates.create_project(tmp_path / "flat", "flatsat")
    h, w, i = _power_wire(project)
    plain = explain_wire(project, w.id)[2].value
    d = project.config["derating"]
    project.config["derating"] = ConfigFile(
        name="derating", placeholder=True, values={**d.values, "max_ambient_temperature_c": 50.0}
    )
    with_model(project, drop_model="dc_at_ambient")
    rho = 1.7e-8 * (1 + 0.00393 * (50.0 - 20.0))
    assert abs(settings.resistivity(project)[0] - rho) < 1e-18  # type: ignore[operator]
    corrected = explain_wire(project, w.id)[2]
    category = project.interface_types[i.type_id].category
    n = settings.drop_conductors(project, category)
    want = voltage_drop_v(i.max_current_a or 0.0, rho, w.length_m or 0.0, w.gauge_awg or 0, n)
    assert corrected.value is not None and plain is not None
    assert abs(corrected.value - want) < 1e-12 and corrected.value > plain
    assert abs(corrected.value / plain - (1 + 0.00393 * 30)) < 1e-9
    resistivity = next(x for x in corrected.inputs if x.name.startswith("Resistivity"))
    assert "dc_at_ambient" in resistivity.source and "ρ(T)" in corrected.equation


def test_the_ambient_drop_model_names_the_temperature_it_needs(tmp_path: Path) -> None:
    project = templates.create_project(tmp_path / "flat", "flatsat")
    _h, w, _i = _power_wire(project)
    with_model(project, drop_model="dc_at_ambient")  # the flatsat has no hottest ambient
    d = explain_wire(project, w.id)[2]
    assert d.value is None and any("max_ambient_temperature_c" in m for m in d.missing)
    from harness_design_studio.core.drc.by_rule import GATES

    assert ("derating", "max_ambient_temperature_c") in GATES["voltage-drop"](project)


# ---- the mass of a harness -----------------------------------------------------------------


def test_the_full_bom_mass_adds_contacts_and_accessories_as_a_hand_calculation_does(
    tmp_path: Path,
) -> None:
    from harness_design_studio.core.generate.mass import harness_mass, pins_in_use
    from harness_design_studio.core.model import Accessory, Part, evolve

    project = templates.create_project(tmp_path / "flat", "flatsat")
    h = project.harnesses["W001"]
    cable = h.connectors[0]
    pins = [evolve(p, contact_part="T-CONTACT") for p in cable.pins]
    sleeve = Accessory(id="A1", kind="sleeving", part_id="T-SLEEVE", length_mm=200, quantity=3)
    label = Accessory(id="A2", kind="label", part_id="T-LABEL", quantity=4)
    project.parts["T-CONTACT"] = Part(id="T-CONTACT", category="contact", mass_g=0.5)
    project.parts["T-SLEEVE"] = Part(id="T-SLEEVE", category="sleeving", mass_per_m_g=2.0)
    project.parts["T-LABEL"] = Part(id="T-LABEL", category="label", mass_g=0.1)
    project.harnesses["W001"] = evolve(
        h, connectors=[evolve(cable, pins=pins), *h.connectors[1:]], accessories=[sleeve, label]
    )
    h = project.harnesses["W001"]
    base = harness_mass(project, h).total_g
    with_model(project, mass_model="full_bom")
    full = harness_mass(project, h)
    wired = sum(1 for p in cable.pins if (cable.id, p.id) in pins_in_use(h))
    extra = 0.5 * wired + 2.0 * (200 * 3 / 1000) + 0.1 * 4
    assert abs(full.total_g - (base + extra)) < 1e-9 and not full.missing
    from harness_design_studio.core.derive import explain_harness

    (d,) = explain_harness(project, "W001")
    assert d.value == full.total_g and any("full_bom" in s.label for s in d.steps)
    project.parts["T-LABEL"] = Part(id="T-LABEL", category="label")  # no mass: named, not guessed
    assert any("T-LABEL" in m for m in harness_mass(project, h).missing)


# ---- the order of the pins -----------------------------------------------------------------


def test_the_categories_allocated_first_are_a_setting(tmp_path: Path) -> None:
    from harness_design_studio.core.generate.pins import DEFAULT_ORDER, Request, allocate
    from harness_design_studio.core.model import Connector, Pin

    project = templates.create_project(tmp_path / "flat", "flatsat")
    power = next(t for t in project.interface_types.values() if t.category == "power")
    other = next(
        t for t in project.interface_types.values() if t.category not in ("power", "ground")
    )
    connector = Connector(
        id="U-J01", name="J01", role="box", part_id="EX-DSUB-9-F", unit_id="U", gender="female",
        pins=[Pin(id=str(k)) for k in range(1, 25)],
    )  # fmt: skip
    requests = [Request("IF-O", other), Request("IF-P", power)]
    default = allocate(connector, requests, {}, gap_pins=0)
    first = min(int(v) for (iid, _), v in default.pins.items() if iid == "IF-P")
    assert (
        DEFAULT_ORDER == ("power", "ground") and first == 1
    )  # as before: power takes the first pins
    flipped = allocate(connector, requests, {}, gap_pins=0, categories=(other.category,))
    assert min(int(v) for (iid, _), v in flipped.pins.items() if iid == "IF-O") == 1
    assert min(int(v) for (iid, _), v in flipped.pins.items() if iid == "IF-P") > 1


# ---- the answer Ready to build -------------------------------------------------------------


def test_the_checks_that_block_are_a_setting(tmp_path: Path) -> None:
    from harness_design_studio.core.outputs.buildsheet import readiness

    project = templates.create_project(tmp_path / "flat", "flatsat")
    h = project.harnesses["W001"]
    by_label = {c.label: c.blocking for c in readiness(project, h)}
    assert [k for k, v in by_label.items() if v] == [
        "Wires without a length",
        "Wires without a gauge",
        "Wires without a colour",
        "Wires without a part",
    ]  # as before
    with_model(project, readiness_blocking=["Wires without strip lengths"])
    changed = {c.label: c.blocking for c in readiness(project, h)}
    assert [k for k, v in changed.items() if v] == ["Wires without strip lengths"]
