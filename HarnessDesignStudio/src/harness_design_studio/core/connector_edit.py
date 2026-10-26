"""Editing a cable connector of a harness: its part, gender, keying and name, and its pins.

    ops = plan_edit_connector(project, "W001", "W001-P1", part_id="EX-DSUB-9-F", gender="female")
    ops = plan_edit_connector(project, "W001", "W001-P1", keying="A")           # empty clears it
    ops = plan_edit_pin(project, "W001", "W001-P1", "3", signal="HEATER +", role="power")
    ops = plan_rename_pin(project, "W001", "W001-P1", "3", "A3")                 # wires follow
    ops = plan_add_pins(project, "W001", "W001-P1", ["10", "11"])
    ops = plan_delete_pin(project, "W001", "W001-P1", "11")
    ops = plan_reset_connector(project, "W001", "W001-P2")                       # give it back

A harness that a person made (`Harness.generated` False) takes every one of these. A harness that
Generate made rebuilds its cable connectors from the device connectors they plug into, so an edit
of the part, gender, keying or the details of a pin (signal, role, function, termination, contact
size) marks the connector as the person's (`Connector.locked`): Generate then keeps those values,
as it keeps the gauge of a locked wire. The pins themselves (their IDs) and the contact of each
pin (set on the device's pin, as before) still follow the device. The name, the pin IDs, the
number of pins and the contact of such a connector come from the device, so changing them here is
refused with the reason; `plan_reset_connector` gives the connector back to Generate. A connector
that Generate cannot keep (its device connector is gone) is named in the finding
`locked_data_lost`. Nothing here invents a value: a field is what the person typed.

The functions are pure; they return `Op`s that `History.execute` runs as one undo step (a plan that
changes nothing returns no ops), or raise `EditError` with a plain sentence. A released harness
refuses, with the same words as the wire editor.
"""

from collections.abc import Sequence
from typing import get_args

from .commands import Op, Put
from .describe import part_gender
from .devices import check_contact_part, check_pin
from .edit import EditError
from .manual_harness import _text, _writable
from .model import Connector, Harness, Pin, Project, evolve
from .model.base import MAX_PIN_COUNT
from .model.physical import Gender, PinRole, Termination
from .wires import released_text

GENDERS: tuple[str, ...] = get_args(Gender)
PIN_ROLES: tuple[str, ...] = tuple(r for r in get_args(PinRole) if r)
TERMINATIONS: tuple[str, ...] = get_args(Termination)
CONNECTOR_FIELDS: tuple[str, ...] = ("part_id", "gender", "keying", "name")
PIN_EDIT_FIELDS: tuple[str, ...] = (
    "signal",
    "role",
    "function",
    "termination",
    "contact_size",
    "contact_part",
)
_GENERATED_NAME = (
    "The name of {c} comes from its ID while {h} is made by Generate. Rename the connector in a "
    "harness you made, or use its label (the Labels form of the Edit wire tab)."
)
_GENERATED_CONTACT = (
    "{h} is made by Generate, which copies the contact from the pin of the device. Set it on the "
    "device's pin in the Devices tab (column Cable contact), then Generate again."
)
_GENERATED_PINS = (
    "The pins of {c} follow the device connector it plugs into while {h} is made by Generate. "
    "Add, rename or delete the pin on the device in the Devices tab, then Generate again."
)


def _open(project: Project, harness_id: str) -> Harness:
    """The harness, if a person may change a connector of it: it exists and is not released."""
    _writable(project)
    h = project.harnesses.get(harness_id)
    if h is None:
        raise EditError(f"Harness '{harness_id}' does not exist.")
    if h.status == "released":
        raise EditError(released_text(h))
    return h


def _connector(h: Harness, connector_id: str) -> Connector:
    c = next((x for x in h.connectors if x.id == connector_id), None)
    if c is None:
        raise EditError(f"'{connector_id}' is not a connector of {h.id}.")
    return c


def _put(h: Harness, new: Connector) -> list[Op]:
    return [
        Put("harnesses", evolve(h, connectors=[new if c.id == new.id else c for c in h.connectors]))
    ]


def suggested_gender(project: Project, part_id: str) -> str:
    """The gender the library says a connector part has ("unspecified" when it does not say)."""
    return part_gender(project.parts.get(part_id))


def plan_edit_connector(
    project: Project, harness_id: str, connector_id: str, **changes: object
) -> list[Op]:
    """Ops that set `part_id` (a connector part of the library), `gender` (male, female or
    unspecified), `keying` (words; empty clears it) and `name` of a cable connector. The pins are
    not touched (a part with another pin count shows in the checks). On a harness made by Generate
    the connector becomes the person's (`locked`) so that Generate keeps the values; `name` is
    refused there."""
    h = _open(project, harness_id)
    c = _connector(h, connector_id)
    unknown = sorted(set(changes) - set(CONNECTOR_FIELDS))
    if unknown:
        raise EditError(
            f"A connector has no field '{unknown[0]}' to set here; "
            f"use {', '.join(CONNECTOR_FIELDS)}."
        )
    clean: dict[str, object] = {}
    for key, value in changes.items():
        if key == "part_id":
            part = project.parts.get(str(value))
            if part is None or part.category != "connector":
                raise EditError(f"'{value}' is not a connector part in the library.")
            clean[key] = part.id
        elif key == "gender":
            if value not in GENDERS:
                raise EditError(f"A gender is one of {', '.join(GENDERS)}.")
            clean[key] = value
        elif key == "keying":
            clean[key] = _text(value, "The keying")
        else:
            if h.generated:
                raise EditError(_GENERATED_NAME.format(c=connector_id, h=h.id))
            name = _text(value, "A connector name")
            if name is None:
                raise EditError("A connector needs a name.")
            if any(
                x.id != connector_id and x.name.casefold() == name.casefold() for x in h.connectors
            ):
                raise EditError(f"{h.id} has a connector called '{name}' already.")
            clean[key] = name
    clean = {k: v for k, v in clean.items() if getattr(c, k) != v}
    if not clean:
        return []
    if h.generated:
        clean["locked"] = True
    return _put(h, evolve(c, **clean))


def _pin(c: Connector, pin_id: str) -> Pin:
    p = next((x for x in c.pins if x.id == pin_id), None)
    if p is None:
        raise EditError(f"{c.id} has no pin '{pin_id}'.")
    return p


def plan_edit_pin(
    project: Project, harness_id: str, connector_id: str, pin_id: str, **changes: object
) -> list[Op]:
    """Ops that set the `signal` (the name of what the pin carries), `role` (power, return, ground,
    signal, shield or spare; empty means none), `function`, `termination`, `contact_size` and
    `contact_part` of a pin of a cable connector. Empty text clears a value. On a harness made by
    Generate the connector becomes the person's (`locked`) so that Generate keeps these values."""
    h = _open(project, harness_id)
    c = _connector(h, connector_id)
    unknown = sorted(set(changes) - set(PIN_EDIT_FIELDS))
    if unknown:
        raise EditError(
            f"A pin has no field '{unknown[0]}' to set here; use {', '.join(PIN_EDIT_FIELDS)}."
        )
    pin = _pin(c, pin_id)
    clean: dict[str, object] = {}
    for key, value in changes.items():
        if key == "termination":
            if value not in TERMINATIONS:
                raise EditError(f"A termination is one of {', '.join(TERMINATIONS)}.")
            clean[key] = value
        elif key == "contact_part":
            if h.generated:
                raise EditError(_GENERATED_CONTACT.format(h=h.id))
            clean[key] = check_contact_part(project, value)
        elif key == "role":
            text = (str(value) if value is not None else "").strip()
            if text and text not in PIN_ROLES:
                raise EditError(f"A pin role is one of {', '.join(PIN_ROLES)}, or empty.")
            clean[key] = text
        else:
            what = {
                "signal": "The signal",
                "function": "The function",
                "contact_size": "The contact size",
            }[key]
            clean[key] = _text(value, what)
    clean = {k: v for k, v in clean.items() if getattr(pin, k) != v}
    if not clean:
        return []
    pins = [evolve(p, **clean) if p.id == pin_id else p for p in c.pins]
    return _put(h, evolve(c, pins=pins, **({"locked": True} if h.generated else {})))


def _own_pins(h: Harness, c: Connector) -> None:
    if h.generated:
        raise EditError(_GENERATED_PINS.format(c=c.id, h=h.id))


def plan_add_pins(
    project: Project, harness_id: str, connector_id: str, pin_ids: Sequence[str]
) -> list[Op]:
    """Ops that add pins (their IDs, no duplicates) to a cable connector of a harness that a person
    made. The part's pin count, when it has one, is the most the connector can hold."""
    h = _open(project, harness_id)
    c = _connector(h, connector_id)
    _own_pins(h, c)
    new_ids = [check_pin(i) for i in pin_ids]
    if not new_ids:
        raise EditError("Give the ID of at least one pin to add.")
    have = {p.id.casefold() for p in c.pins}
    for pid in new_ids:
        if pid.casefold() in have:
            raise EditError(f"{connector_id} has a pin '{pid}' already.")
        have.add(pid.casefold())
    part = project.parts.get(c.part_id)
    limit = (part.pin_count if part is not None else None) or MAX_PIN_COUNT
    if len(c.pins) + len(new_ids) > limit:
        raise EditError(
            f"{c.part_id} has {limit} pins; {connector_id} would have "
            f"{len(c.pins) + len(new_ids)}. Choose a part with more pins first."
        )
    return _put(h, evolve(c, pins=[*c.pins, *(Pin(id=i) for i in new_ids)]))


def plan_delete_pin(project: Project, harness_id: str, connector_id: str, pin_id: str) -> list[Op]:
    """Ops that remove a pin from a cable connector of a harness that a person made. A pin with
    wires cannot go: the plan names them, so they are deleted or moved first."""
    h = _open(project, harness_id)
    c = _connector(h, connector_id)
    _own_pins(h, c)
    _pin(c, pin_id)
    wires = sorted(
        w.id
        for w in h.wires
        if (w.from_connector, w.from_pin) == (connector_id, pin_id)
        or (w.to_connector, w.to_pin) == (connector_id, pin_id)
    )
    if wires:
        shown = ", ".join(wires[:4]) + (f" and {len(wires) - 4} more" if len(wires) > 4 else "")
        raise EditError(
            f"Pin {pin_id} of {connector_id} has wires ({shown}). "
            "Delete them, or move their ends, first."
        )
    return _put(h, evolve(c, pins=[p for p in c.pins if p.id != pin_id]))


def plan_rename_pin(
    project: Project, harness_id: str, connector_id: str, pin_id: str, new_id: str
) -> list[Op]:
    """Ops that give a pin of a cable connector of a harness that a person made another ID. The
    wires on it follow, in the same step."""
    h = _open(project, harness_id)
    c = _connector(h, connector_id)
    _own_pins(h, c)
    _pin(c, pin_id)
    target = check_pin(new_id)
    if target == pin_id:
        return []
    if any(p.id.casefold() == target.casefold() for p in c.pins):
        raise EditError(f"{connector_id} has a pin '{target}' already.")

    def move(w, side: str):  # type: ignore[no-untyped-def]
        if (getattr(w, f"{side}_connector"), getattr(w, f"{side}_pin")) == (connector_id, pin_id):
            return evolve(w, **{f"{side}_pin": target})
        return w

    wires = [move(move(w, "from"), "to") for w in h.wires]
    new = evolve(c, pins=[evolve(p, id=target) if p.id == pin_id else p for p in c.pins])
    return [
        Put(
            "harnesses",
            evolve(
                h,
                connectors=[new if x.id == connector_id else x for x in h.connectors],
                wires=wires,
            ),
        )
    ]


def plan_reset_connector(project: Project, harness_id: str, connector_id: str) -> list[Op]:
    """Ops that give an edited cable connector of a generated harness back to Generate: it takes
    its part, gender, keying and pin details from the device connector again at the next Generate
    (nothing changes before that). A connector that is not locked returns no ops."""
    h = _open(project, harness_id)
    c = _connector(h, connector_id)
    if not c.locked:
        return []
    return _put(h, evolve(c, locked=False))


def is_edited(project: Project, harness_id: str, connector_id: str) -> bool:
    """True when the connector is one that a person edited on a generated harness (it is kept)."""
    h = project.harnesses.get(harness_id)
    c = next((x for x in (h.connectors if h else []) if x.id == connector_id), None)
    return c is not None and c.locked


__all__ = [
    "CONNECTOR_FIELDS",
    "GENDERS",
    "PIN_EDIT_FIELDS",
    "PIN_ROLES",
    "TERMINATIONS",
    "is_edited",
    "plan_add_pins",
    "plan_delete_pin",
    "plan_edit_connector",
    "plan_edit_pin",
    "plan_rename_pin",
    "plan_reset_connector",
    "suggested_gender",
]
