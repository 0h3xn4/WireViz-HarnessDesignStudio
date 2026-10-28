# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,arg-type,misc"
"""REQ-IO-02, audit A-12. `evolve` used to dump the whole object to plain data and validate it again,
so a changed harness was a second full copy of the harness and every undo step kept two. Now the
fields that do not change keep their objects. The result must be the same as the old way for every
object in the examples and every single-field change, and the copy must share what did not change."""

import random
from typing import Any

import pytest

from harness_design_studio.core import wires
from harness_design_studio.core.commands import History
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import Entity, evolve
from harness_design_studio.core.samples import mini3, sat15
from tests.test_integrity_tracker import hand_made


def evolve_by_dumping(obj: Entity, **changes: Any) -> Entity:
    """`evolve` as release 1.8.1 had it."""
    data = obj.model_dump()
    unknown = set(changes) - set(type(obj).model_fields)
    if unknown:
        raise TypeError(f"{type(obj).__name__} has no field(s) {sorted(unknown)}")
    data.update(changes)
    return type(obj).model_validate(data)


def every_entity() -> list[Entity]:
    found: list[Entity] = []
    for build in (mini3, sat15, hand_made):
        p = build()
        if not p.harnesses:
            generate_project(p)
        for name in ("units", "interfaces", "interface_types", "connectors", "harnesses", "parts", "links", "placements"):  # fmt: skip
            found.extend(getattr(p, name).values())
        for h in p.harnesses.values():
            found.extend([*h.connectors, *h.wires, *h.accessories, *h.shields, *h.segments])
        found.extend(c.pins[0] for c in p.connectors.values() if c.pins)
    return found


def test_evolve_gives_what_dumping_and_validating_gave() -> None:
    rng = random.Random(12)
    entities = every_entity()
    by_type: dict[type, list[Entity]] = {}
    for e in entities:
        by_type.setdefault(type(e), []).append(e)
    checked = 0
    for obj in entities:
        assert evolve(obj) == evolve_by_dumping(obj) == obj
        peers = by_type[type(obj)]
        for field in rng.sample(
            sorted(type(obj).model_fields), min(4, len(type(obj).model_fields))
        ):
            if field == "id":
                continue
            value = getattr(rng.choice(peers), field)  # a value that is valid for the field
            new, was = evolve(obj, **{field: value}), evolve_by_dumping(obj, **{field: value})
            assert new == was
            assert new.model_dump() == was.model_dump()
            assert new.model_dump_json() == was.model_dump_json()
            checked += 1
    assert checked > 500


def test_the_copy_shares_what_the_change_did_not_touch() -> None:
    p = sat15()
    generate_project(p)
    h = max(p.harnesses.values(), key=lambda x: len(x.wires))
    renamed = evolve(h, name="renamed")
    assert all(a is b for a, b in zip(renamed.wires, h.wires, strict=True))
    assert all(a is b for a, b in zip(renamed.connectors, h.connectors, strict=True))
    assert (
        renamed.wires is not h.wires
    )  # the list is the copy's own: no change reaches the original


def test_an_edit_adds_a_wire_not_a_harness_to_the_undo_history() -> None:
    p = sat15()
    generate_project(p)
    h = max(p.harnesses.values(), key=lambda x: len(x.wires))
    history = History(p)
    wire = h.wires[0]
    history.execute("note", wires.plan_wire_edit(p, [wire.id], {"note": "a note"}))
    now = p.harnesses[h.id]
    still = sum(1 for a, b in zip(now.wires, h.wires, strict=True) if a is b)
    assert still == len(h.wires) - 1  # one wire is new, every other one is the very same object
    assert now.connectors[0] is h.connectors[0]


def test_unknown_fields_are_still_refused() -> None:
    with pytest.raises(TypeError, match="no field"):
        evolve(next(iter(mini3().units.values())), colour="red")
