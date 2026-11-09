# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The two assumptions of the bill of materials that became settings (A-BOM-CONTACTS and
A-BOM-NO-ALLOWANCE): the default of each is today's behaviour (nothing is added), a changed value
changes the quantity as a hand calculation says, and the explanation lists the extra lines."""

import math
from pathlib import Path

import pytest

from harness_design_studio.core import configcheck, settings, templates
from harness_design_studio.core.derive import explain_part, render
from harness_design_studio.core.generate.mass import pins_in_use
from harness_design_studio.core.model import ConfigFile, Project, evolve
from harness_design_studio.core.outputs import tables


@pytest.fixture
def flat(tmp_path: Path) -> Project:
    return templates.create_project(tmp_path / "flat", "flatsat")


def _with_model(project: Project, **values: object) -> None:
    project.config["model"] = ConfigFile(name="model", placeholder=False, values=dict(values))


def _quantity(project: Project, part_id: str, unit: str) -> float:
    harnesses = [project.harnesses[i] for i in sorted(project.harnesses)]
    for row in tables.bom(project, harnesses)[1:]:
        if row[0] == part_id and row[7] == unit:
            return float(row[6])
    raise AssertionError((part_id, unit))


def _contacts(project: Project, part_id: str = "EX-CONTACT") -> list[int]:
    """Put a contact part on every pin of every connector; return, for each harness in ID order,
    how many pins have a wire."""
    counts: list[int] = []
    for hid in sorted(project.harnesses):
        h = project.harnesses[hid]
        in_use = pins_in_use(h)
        connectors = [
            evolve(c, pins=[evolve(p, contact_part=part_id) for p in c.pins]) for c in h.connectors
        ]
        counts.append(sum(1 for c in connectors for p in c.pins if (c.id, p.id) in in_use))
        project.harnesses[hid] = evolve(h, connectors=connectors)
    return counts


def test_the_defaults_add_nothing_and_are_registered_as_zero(flat: Project) -> None:
    for key in ("bom_wire_allowance_fraction", "bom_contact_spare_fraction"):
        e = settings.effective(flat, "model", key)
        assert e.value == 0.0 and e.origin == "default"
    _contacts(flat)
    harnesses = [flat.harnesses[i] for i in sorted(flat.harnesses)]
    kinds = {c.kind for c in tables.bom_contributions(flat, harnesses)}
    assert kinds == {"connector", "contact", "wire"}


def test_a_wire_allowance_adds_that_fraction_of_the_wire_metres(flat: Project) -> None:
    base = _quantity(flat, "EX-WIRE-SINGLE", "m")
    assert base == 165.2  # the figure of docs/models/bom.md
    _with_model(flat, bom_wire_allowance_fraction=0.1)
    assert not [i for i in configcheck.validate(flat) if (i.object_id or "").startswith("model.")]
    assert math.isclose(_quantity(flat, "EX-WIRE-SINGLE", "m"), 165.2 * 1.1, abs_tol=1e-9)
    # the connectors are not given an allowance, and the mass does not change
    assert _quantity(flat, "EX-MICROD-9-M", "ea") == 47
    (derived,) = explain_part(flat, "EX-WIRE-SINGLE")
    assert math.isclose(derived.value or 0.0, 165.2 * 1.1, abs_tol=1e-9)
    assert "model.bom_wire_allowance_fraction" in derived.equation
    assert any(i.name == "Allowance on the wire" and i.value == 0.1 for i in derived.inputs)
    parts = [s.value for s in derived.steps[:-1]]
    assert math.isclose(sum(parts), derived.value or 0.0, abs_tol=1e-9)
    assert any("wire allowances" in s.label and "× 0.1" in s.expression for s in derived.steps)
    assert "A-BOM-NO-ALLOWANCE" in derived.assumptions and "A-BOM-NO-ALLOWANCE" in render(derived)


def test_spare_contacts_are_a_fraction_of_the_contacts_rounded_up_for_each_harness(
    flat: Project,
) -> None:
    counts = _contacts(flat)
    used = sum(counts)
    assert used > 10 and len([n for n in counts if n]) > 2
    (before,) = explain_part(flat, "EX-CONTACT")
    assert before.value == used and "model.bom_contact_spare_fraction" not in before.equation
    _with_model(flat, bom_contact_spare_fraction=0.1)
    spares = sum(math.ceil(round(n * 0.1, 9)) for n in counts)  # rounded up for each harness
    assert spares > math.ceil(round(used * 0.1, 9))  # not rounded up once for the whole system
    assert _quantity(flat, "EX-CONTACT", "ea") == used + spares
    (after,) = explain_part(flat, "EX-CONTACT")
    assert after.value == used + spares
    assert any(i.name == "Spare contacts" and i.value == 0.1 for i in after.inputs)
    first = next(n for n in counts if n)
    assert any(
        "spare contacts" in s.label and s.expression == f"{first} contact(s) × 0.1, rounded up"
        for s in after.steps
    )
    assert "A-BOM-CONTACTS" in after.assumptions
    # a whole number of spares is not rounded up again by float noise: 100 x 0.07 is 7, not 8
    assert math.ceil(round(100 * 0.07, 9)) == 7 and math.ceil(100 * 0.07) == 8


def test_a_value_outside_its_range_is_refused_with_its_name(flat: Project) -> None:
    for key, value in (("bom_wire_allowance_fraction", -0.1), ("bom_contact_spare_fraction", 1.5)):
        _with_model(flat, **{key: value})
        issues = [i for i in configcheck.validate(flat) if i.object_id == f"model.{key}"]
        assert issues and key in issues[0].message


def test_the_two_assumptions_are_settings_now() -> None:
    from harness_design_studio.core.assumptions import ASSUMPTIONS

    assert ASSUMPTIONS["A-BOM-CONTACTS"].kind == "setting"
    assert ASSUMPTIONS["A-BOM-NO-ALLOWANCE"].kind == "setting"
    keys = {
        s.key for s in settings.SETTINGS if s.assumption in {"A-BOM-CONTACTS", "A-BOM-NO-ALLOWANCE"}
    }
    assert keys == {"bom_wire_allowance_fraction", "bom_contact_spare_fraction"}
