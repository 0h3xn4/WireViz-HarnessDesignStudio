"""Custom devices down to each pin: the plans the Devices view and the pinout import call.

A device is a unit with its box connectors and their pins. Everything here writes fields the model
already has (docs/ux-custom-devices-audit.md); nothing is added to the file format, the design
rules or the outputs. Like `edit`, the functions are pure: they return lists of `Op` that
`History.execute` runs as one undo step, or raise `EditError` with a plain sentence.

The lock hole of the audit (CD-G15) is closed here, in the planners only: the pin set (ids and
count) of a box connector that a released cable connector mates with is frozen, and so is every
pin that carries a released interface. `check_locks` itself is not changed.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, get_args

from pydantic import TypeAdapter, ValidationError

from . import edit
from .commands import Delete, Op, Put
from .describe import part_gender
from .edit import EditError, unit_connectors
from .ids import check_pin_id
from .issues import Severity
from .model import (
    Connector,
    Harness,
    InterfaceInstance,
    InterfaceType,
    Part,
    Pin,
    Placement,
    Project,
    SignalDef,
    Unit,
    evolve,
)
from .model.base import MAX_PIN_COUNT, Name
from .model.logical import Category, Construction, Direction, Shielding, Side
from .model.physical import Gender, Termination
from .outputs.stamp import Table
from .outputs.tables import box_pinouts
from .vcs.lockview import LockRef, field_lock_reason, lock_reason, locked_objects
from .vcs.snapshot import carried_interfaces

PinMode = Literal["free", "fixed", "locked"]
PIN_MODES: tuple[PinMode, ...] = get_args(PinMode)
PIN_FIELDS = frozenset(
    {"signal", "contact_size", "termination", "fixed", "locked", "function", "contact_part"}
)
CONNECTOR_FIELDS = frozenset({"name", "gender", "keying", "carries", "notes", "label"})
_GENDERS: tuple[str, ...] = get_args(Gender)
_TERMINATIONS: tuple[str, ...] = get_args(Termination)
_NAME = TypeAdapter(Name)


# ---- small helpers -----------------------------------------------------------------------------


def _writable(project: Project) -> None:
    if project.read_only:
        raise EditError("This project is read-only (saved by a newer tool version). Use Save as.")


def _box(project: Project, connector_id: str) -> Connector:
    c = project.connectors.get(connector_id)
    if c is None or c.role != "box" or c.unit_id is None:
        raise EditError(f"'{connector_id}' is not a connector of a device.")
    return c


def _connector_part(project: Project, part_id: str) -> Part:
    part = project.parts.get(part_id)
    if part is None or part.category != "connector":
        raise EditError(f"'{part_id}' is not a connector part in the library.")
    return part


def _text(value: object, what: str) -> str | None:
    """Free text of a cell: outer spaces go, an empty cell is None, 1 to 200 characters."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise EditError(f"{what} must be text.")
    text = value.strip()
    if not text:
        return None
    try:
        return _NAME.validate_python(text, strict=True)
    except ValidationError as exc:
        raise EditError(f"{what} can have 1 to 200 characters and no control characters.") from exc


def contact_part_choices(project: Project) -> list[str]:
    """The IDs of the contact parts of the project library, sorted: the choices for a pin's contact."""
    return sorted(p.id for p in project.parts.values() if p.category == "contact")


def check_contact_part(project: Project, value: object, what: str = "A contact") -> str | None:
    """The ID of a library part of category contact, or None for an empty cell; else an EditError."""
    text = _text(value, what)
    if text is not None:
        part = project.parts.get(text)
        if part is None or part.category != "contact":
            raise EditError(f"'{text}' is not a contact part of the library (category contact).")
    return text


def check_pin(pin_id: str) -> str:
    """The pin name, or an EditError: letters, digits, '_', '-' or '.', 1 to 16 characters."""
    try:
        return check_pin_id(pin_id)
    except ValueError:
        shown = pin_id if len(pin_id) <= 20 else pin_id[:20] + "..."
        raise EditError(
            f"'{shown}' cannot be used as a pin name: use letters, digits, '_', '-' or '.', "
            "1 to 16 characters."
        ) from None


def pin_mode(pin: Pin) -> PinMode:
    """Locked wins over fixed (a pin that is both stays where the person put it)."""
    return "locked" if pin.locked else "fixed" if pin.fixed else "free"


def _mode_flags(mode: object) -> dict[str, bool]:
    if mode not in PIN_MODES:
        raise EditError(f"A pin mode is one of {', '.join(PIN_MODES)}.")
    return {"fixed": mode == "fixed", "locked": mode == "locked"}


def _limit(project: Project, c: Connector, part_id: str | None = None) -> int:
    """The most pins this connector may have: the part's pin count, else the model's limit."""
    part = project.parts.get(part_id or c.part_id)
    return part.pin_count if part is not None and part.pin_count else MAX_PIN_COUNT


def _numeric(pin_id: str) -> int | None:
    return int(pin_id) if pin_id.isdigit() else None


def _next_numbers(taken: Iterable[str], count: int, after: str | None = None) -> list[str]:
    """`count` pin names that are plain numbers and free (ignoring case), counting on from the
    pin `after` or from the highest number in use."""
    used = {t.casefold() for t in taken}
    start = _numeric(after) if after is not None and _numeric(after) is not None else None
    if start is None:
        start = max((n for t in used if (n := _numeric(t)) is not None), default=0)
    out: list[str] = []
    n = start
    while len(out) < count:
        n += 1
        if str(n).casefold() not in used:
            out.append(str(n))
    return out


def _unique_ids(ids: Sequence[str], what: str = "pin") -> None:
    seen: dict[str, str] = {}
    for pid in ids:
        key = pid.casefold()
        if key in seen:
            same = "" if seen[key] == pid else f" (ignoring case, as '{seen[key]}')"
            raise EditError(f"The {what} '{pid}' is listed twice{same}.")
        seen[key] = pid


# ---- locks (closing CD-G15 in the planners) ----------------------------------------------------


def _released(project: Project) -> list[Harness]:
    return [
        h for h in sorted(project.harnesses.values(), key=lambda x: x.id) if h.status == "released"
    ]


def _ref(h: Harness) -> list[LockRef]:
    return [LockRef(h.id, h.revision)]


def pin_set_frozen(project: Project, connector_id: str) -> str | None:
    """The sentence that says why the pin set (ids and count) and the design fields (part, gender,
    keying) of this box connector cannot change, or None. Frozen: a connector that a cable
    connector of a released harness mates with, and a connector with a pin that carries an
    interface of a released harness. The sentence is the one `check_locks` gives for the connector."""
    c = project.connectors.get(connector_id)
    if c is None:
        return None
    for h in _released(project):
        carried = carried_interfaces(h)
        if any(k.mates_with == connector_id for k in h.connectors) or any(
            p.interface_id in carried for p in c.pins if p.interface_id
        ):
            return lock_reason(
                project, "box_connector", connector_id, {("box_connector", connector_id): _ref(h)}
            )
    return None


def pin_lock_reason(project: Project, connector_id: str, pin_id: str) -> str | None:
    """Why this one pin cannot be edited at all (it carries an interface of a released harness),
    or None. A spare pin of a frozen connector stays editable; only its name and existence are
    frozen (`pin_set_frozen`)."""
    c = project.connectors.get(connector_id)
    pin = next((p for p in c.pins if p.id == pin_id), None) if c is not None else None
    if pin is None or pin.interface_id is None:
        return None
    for h in _released(project):
        if pin.interface_id in carried_interfaces(h):
            key = ("box_pin", f"{connector_id}.{pin_id}")
            return lock_reason(project, "box_pin", f"{connector_id}.{pin_id}", {key: _ref(h)})
    return None


def _pin_users(project: Project, connector_id: str) -> dict[str, list[str]]:
    """Pin -> the harnesses that were made by hand or are released and have a wire on it. (A
    generated draft harness only becomes out of date; it is rebuilt by the next Generate.)"""
    out: dict[str, list[str]] = defaultdict(list)
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        if h.generated and h.status != "released":
            continue
        cables = {k.id for k in h.connectors if k.mates_with == connector_id}
        for w in h.wires:
            for cid, pin in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
                if (cid == connector_id or cid in cables) and h.id not in out[pin]:
                    out[pin].append(h.id)
    return out


def _outdated_harnesses(project: Project, connector_id: str) -> tuple[str, ...]:
    """Generated draft harnesses that have a cable end on this connector: the next Generate
    rebuilds them."""
    return tuple(
        sorted(
            h.id
            for h in project.harnesses.values()
            if h.generated
            and h.status != "released"
            and any(k.mates_with == connector_id for k in h.connectors)
        )
    )


def _blocked_by_text(hids: Sequence[str]) -> str:
    return (
        f"{', '.join(hids)} (made by hand or released) has wires on it. "
        "Delete that harness, or start a new revision of it, first."
    )


# ---- connectors --------------------------------------------------------------------------------


def next_connector_name(project: Project, unit_id: str) -> tuple[str, str]:
    """(connector id, name) of the next connector of a unit: `<unit>-J01` and `J01`, the first
    number that is free as a name of this unit and as a connector ID in the whole project."""
    ids = {c.casefold() for c in project.connectors}
    ids |= {c.id.casefold() for h in project.harnesses.values() for c in h.connectors}
    names = {c.name.casefold() for c in unit_connectors(project, unit_id)}
    k = 1
    while f"J{k:02d}".casefold() in names or f"{unit_id}-J{k:02d}".casefold() in ids:
        k += 1
    return f"{unit_id}-J{k:02d}", f"J{k:02d}"


def _check_carries(project: Project, carries: Iterable[str]) -> list[str]:
    out: list[str] = []
    for t in carries:
        if t not in project.interface_types:
            raise EditError(f"Interface type '{t}' does not exist.")
        if t not in out:
            out.append(t)
    return out


def _gender(value: object) -> Gender:
    if value not in _GENDERS:
        raise EditError(f"A gender is one of {', '.join(_GENDERS)}.")
    return value  # type: ignore[return-value]


def _check_connector_name(project: Project, unit_id: str, name: str, own: str | None) -> str:
    text = _text(name, "A connector name")
    if text is None:
        raise EditError("A connector needs a name.")
    for c in unit_connectors(project, unit_id):
        if c.id != own and c.name.casefold() == text.casefold():
            raise EditError(f"{unit_id} already has a connector called '{text}'.")
    return text


def ops_add_connector(
    project: Project,
    unit_id: str,
    *,
    part_id: str,
    name: str | None = None,
    gender: str | None = None,
    keying: str | None = None,
    carries: Iterable[str] = (),
    pin_ids: Sequence[str] | None = None,
) -> tuple[list[Op], str]:
    """Add a box connector to a unit. The ID is the next free `<unit>-Jnn`. The pins are the ones
    given, else `1` to `N` of the part's pin count (none when the part has no count). The gender
    is the one the part's description says unless given."""
    _writable(project)
    if unit_id not in project.units:
        raise EditError(f"Device '{unit_id}' does not exist.")
    part = _connector_part(project, part_id)
    cid, default_name = next_connector_name(project, unit_id)
    cname = _check_connector_name(project, unit_id, name, None) if name else default_name
    if pin_ids is None:
        ids = [str(i) for i in range(1, (part.pin_count or 0) + 1)]
    else:
        ids = [check_pin(p) for p in pin_ids]
        _unique_ids(ids)
    if len(ids) > (part.pin_count or MAX_PIN_COUNT):
        raise EditError(f"{part_id} has {part.pin_count} pins; {len(ids)} were given.")
    connector = Connector(
        id=cid,
        name=cname,
        role="box",
        part_id=part_id,
        unit_id=unit_id,
        gender=_gender(gender) if gender is not None else part_gender(part),
        keying=_text(keying, "The keying"),
        carries=_check_carries(project, carries),
        pins=[Pin(id=i) for i in ids],
    )
    return [Put("connectors", connector)], cid


def ops_update_connector(project: Project, connector_id: str, **changes: object) -> list[Op]:
    """Change name, gender, keying, carries or notes of a box connector. Gender and keying are
    refused while a release uses the connector (`pin_set_frozen`)."""
    _writable(project)
    c = _box(project, connector_id)
    bad = set(changes) - CONNECTOR_FIELDS
    if bad:
        raise EditError(f"These connector fields cannot be changed here: {', '.join(sorted(bad))}.")
    new: dict[str, object] = {}
    for key, value in changes.items():
        if key == "name":
            new[key] = _check_connector_name(project, c.unit_id or "", str(value), c.id)
        elif key == "gender":
            new[key] = _gender(value)
        elif key == "keying":
            new[key] = _text(value, "The keying")
        elif key == "label":
            new[key] = _text(value, "The label")
        elif key == "carries":
            if isinstance(value, str) or not isinstance(value, Iterable):
                raise EditError("Carries is a list of interface types.")
            new[key] = _check_carries(project, value)
        else:
            if not isinstance(value, str):
                raise EditError("Notes must be text.")
            new[key] = value
    new = {k: v for k, v in new.items() if getattr(c, k) != v}
    if not new:
        return []
    locked = [k for k in ("gender", "keying") if k in new]
    if locked and (why := pin_set_frozen(project, connector_id)):
        raise EditError(f"The {' and '.join(locked)} of {connector_id} cannot change. {why}")
    return [Put("connectors", evolve(c, **new))]


def _pin_is_empty(p: Pin) -> bool:
    return (
        p.signal is None
        and p.interface_id is None
        and not p.fixed
        and not p.locked
        and p.contact_size is None
        and p.function is None
        and p.contact_part is None
        and p.termination == "unspecified"
    )


@dataclass(frozen=True)
class PartChange:
    """What changing the part of a connector does, for the question asked before it is done."""

    connector_id: str
    part_id: str
    old_pin_count: int
    new_pin_count: int | None  # the part's pin count (None: the part has no count; nothing to do)
    add: tuple[str, ...]  # pins that are added
    remove: tuple[str, ...]  # trailing spare pins that are removed
    blocked: tuple[str, ...]  # pins that would have to go but carry data
    gender: Gender | None  # the gender the part says when it differs from the connector's
    frozen: str | None  # why the connector cannot change at all

    @property
    def resizes(self) -> bool:
        return bool(self.add or self.remove)


def plan_change_part(project: Project, connector_id: str, part_id: str) -> PartChange:
    """Preview of `ops_change_part`: pins to add or remove and the gender the part says."""
    c = _box(project, connector_id)
    part = _connector_part(project, part_id)
    count = part.pin_count
    pins = list(c.pins)
    add: list[str] = []
    remove: list[str] = []
    blocked: list[str] = []
    if count is not None and len(pins) < count:
        add = _next_numbers((p.id for p in pins), count - len(pins))
    elif count is not None and len(pins) > count:
        users = _pin_users(project, connector_id)
        tail = pins[count:]
        blocked = [p.id for p in tail if not _pin_is_empty(p) or p.id in users]
        if not blocked:
            remove = [p.id for p in tail]
    g = part_gender(part)
    return PartChange(
        connector_id,
        part_id,
        len(pins),
        count,
        tuple(add),
        tuple(remove),
        tuple(blocked),
        g if g != "unspecified" and g != c.gender else None,
        pin_set_frozen(project, connector_id),
    )


def ops_change_part(
    project: Project,
    connector_id: str,
    part_id: str,
    *,
    resize: bool = True,
    regender: bool = True,
) -> list[Op]:
    """Change the part of a box connector and, as asked, give it the pin count of the new part
    (pins are added after the highest number, spare pins are taken off the end) and the gender the
    new part says. One step. A part with no pin count leaves the pins alone; a part with fewer
    pins than the connector has is refused when the pins that would go are in use."""
    _writable(project)
    c = _box(project, connector_id)
    plan = plan_change_part(project, connector_id, part_id)
    if part_id == c.part_id and not (resize and plan.resizes) and not (regender and plan.gender):
        return []
    if plan.frozen:
        raise EditError(f"The part of {connector_id} cannot change. {plan.frozen}")
    if plan.blocked and (resize or plan.new_pin_count is not None):
        raise EditError(
            f"{part_id} has {plan.new_pin_count} pins and {connector_id} has {plan.old_pin_count}; "
            f"pin {', '.join(plan.blocked)} would have to go but is in use. "
            "Delete or clear it first, or choose a part with more pins."
        )
    pins = list(c.pins)
    if resize:
        if plan.remove:
            pins = pins[: len(pins) - len(plan.remove)]
        pins += [Pin(id=i) for i in plan.add]
    changes: dict[str, object] = {"part_id": part_id, "pins": pins}
    if regender and plan.gender is not None:
        changes["gender"] = plan.gender
    return [Put("connectors", evolve(c, **changes))]


@dataclass(frozen=True)
class ConnectorImpact:
    interfaces: tuple[str, ...]  # interfaces that end on it; they lose their connector
    outdated_harnesses: tuple[str, ...]  # generated drafts: rebuilt by the next Generate
    blocked_by_harnesses: tuple[str, ...]  # made by hand or released, with wires on it
    frozen: str | None


def connector_delete_impact(project: Project, connector_id: str) -> ConnectorImpact:
    _box(project, connector_id)
    ifs = tuple(
        sorted(
            i.id
            for i in project.interfaces.values()
            if any(e.connector_id == connector_id for e in i.endpoints)
        )
    )
    users = _pin_users(project, connector_id)
    blocked = tuple(sorted({h for hs in users.values() for h in hs}))
    return ConnectorImpact(
        ifs,
        _outdated_harnesses(project, connector_id),
        blocked,
        pin_set_frozen(project, connector_id),
    )


def ops_delete_connector(project: Project, connector_id: str) -> list[Op]:
    """Delete a box connector. The interfaces that end on it keep their unit and lose the
    connector (the Guided mode picks another, Expert mode asks); waivers about it go."""
    from .edit import _waiver_deletes  # same rule as for a unit

    _writable(project)
    impact = connector_delete_impact(project, connector_id)
    if impact.frozen:
        raise EditError(f"{connector_id} cannot be deleted. {impact.frozen}")
    if impact.blocked_by_harnesses:
        raise EditError(
            f"{connector_id} cannot be deleted: {_blocked_by_text(impact.blocked_by_harnesses)}"
        )
    ops: list[Op] = []
    for iid in impact.interfaces:
        i = project.interfaces[iid]
        eps = [
            e.model_copy(update={"connector_id": None, "auto": False})
            if e.connector_id == connector_id
            else e
            for e in i.endpoints
        ]
        ops.append(Put("interfaces", evolve(i, endpoints=eps)))
    ops += _waiver_deletes(project, {connector_id})
    ops.append(Delete("connectors", connector_id))
    return ops


# ---- pins --------------------------------------------------------------------------------------


def _find_pin(c: Connector, pin_id: str) -> tuple[int, Pin]:
    for k, p in enumerate(c.pins):
        if p.id == pin_id:
            return k, p
    raise EditError(f"{c.id} has no pin '{pin_id}'.")


def _edit_pin(pin: Pin, changes: Mapping[str, object], project: Project | None = None) -> Pin:
    """The pin with these fields changed (`mode` stands for fixed and locked). Retyping the signal
    of a pin that was allocated to an interface takes the pin over: the assignment goes. A
    `contact_part` is checked against the library of `project`."""
    bad = set(changes) - PIN_FIELDS - {"mode"}
    if bad:
        raise EditError(f"These pin fields cannot be changed here: {', '.join(sorted(bad))}.")
    new: dict[str, object] = {}
    for key, value in changes.items():
        if key == "mode":
            new.update(_mode_flags(value))
        elif key in ("signal", "contact_size", "function"):
            what = {
                "signal": "A signal",
                "contact_size": "A contact size",
                "function": "A function",
            }
            new[key] = _text(value, what[key])
        elif key == "termination":
            if value not in _TERMINATIONS:
                raise EditError(f"A termination is one of {', '.join(_TERMINATIONS)}.")
            new[key] = value
        elif key == "contact_part":
            new[key] = (
                check_contact_part(project, value)
                if project is not None
                else _text(value, "A contact")
            )
        else:
            if not isinstance(value, bool):
                raise EditError(f"'{key}' is yes or no.")
            new[key] = value
    if "signal" in new and new["signal"] != pin.signal and pin.interface_id is not None:
        new["interface_id"] = None
    new = {k: v for k, v in new.items() if getattr(pin, k) != v}
    return evolve(pin, **new) if new else pin


def ops_set_pin(project: Project, connector_id: str, pin_id: str, **changes: object) -> list[Op]:
    """Change one pin: `signal`, `contact_size`, `termination`, `function`, `contact_part` (a
    contact part of the library), `fixed`, `locked`, or `mode` ("free", "fixed", "locked") for the
    last two together. Refused for a pin that carries an interface of a released harness. Nothing
    to do gives no ops."""
    _writable(project)
    c = _box(project, connector_id)
    k, pin = _find_pin(c, pin_id)
    new = _edit_pin(pin, changes, project)
    if new is pin:
        return []
    if why := pin_lock_reason(project, connector_id, pin_id):
        raise EditError(f"Pin {pin_id} of {connector_id} cannot change. {why}")
    pins = list(c.pins)
    pins[k] = new
    return [Put("connectors", c.model_copy(update={"pins": pins}))]


def ops_set_contacts(
    project: Project, connector_id: str, pin_ids: Collection[str], contact_part: str | None
) -> list[Op]:
    """Set the contact part of several pins of a box connector in one `Put` (the bulk fill of the
    *Cable contact* column); None or an empty text clears it. The part must be a contact part of
    the library. A pin that carries an interface of a released harness refuses the change."""
    _writable(project)
    c = _box(project, connector_id)
    part = check_contact_part(project, contact_part)
    wanted = list(dict.fromkeys(pin_ids))
    if not wanted:
        raise EditError("No pin is selected.")
    for pid in wanted:
        _find_pin(c, pid)
    pins = []
    for p in c.pins:
        if p.id in wanted and p.contact_part != part:
            if why := pin_lock_reason(project, connector_id, p.id):
                raise EditError(f"Pin {p.id} of {connector_id} cannot change. {why}")
            p = evolve(p, contact_part=part)
        pins.append(p)
    if pins == c.pins:
        return []
    return [Put("connectors", c.model_copy(update={"pins": pins}))]


@dataclass(frozen=True)
class PinImpact:
    """What deleting or renaming pins touches, for the line shown before it is done."""

    pin_ids: tuple[str, ...]
    interfaces: tuple[tuple[str, tuple[str, ...]], ...]  # (interface, its pins among these)
    outdated_harnesses: tuple[str, ...]
    blocked_by_harnesses: tuple[str, ...]
    frozen: str | None
    locked: tuple[tuple[str, str], ...]  # (pin, reason): pins of a released interface

    def sentence(self) -> str:
        """ "used by IF-011 on pins 3 and 4; W003 will be out of date" (empty when nothing)."""
        parts = []
        for iid, pins in self.interfaces:
            joined = " and ".join([", ".join(pins[:-1]), pins[-1]]) if len(pins) > 1 else pins[0]
            parts.append(f"used by {iid} on pin{'s' if len(pins) > 1 else ''} {joined}")
        if self.outdated_harnesses:
            parts.append(f"{', '.join(self.outdated_harnesses)} will be out of date")
        return "; ".join(parts)


def pin_impact(project: Project, connector_id: str, pin_ids: Collection[str]) -> PinImpact:
    c = _box(project, connector_id)
    wanted = [p for p in c.pins if p.id in pin_ids]
    by_if: dict[str, list[str]] = defaultdict(list)
    for p in wanted:
        if p.interface_id:
            by_if[p.interface_id].append(p.id)
    users = _pin_users(project, connector_id)
    blocked = sorted({h for p in wanted for h in users.get(p.id, [])})
    locked = tuple(
        (p.id, why) for p in wanted if (why := pin_lock_reason(project, connector_id, p.id))
    )
    outdated = _outdated_harnesses(project, connector_id) if wanted else ()
    return PinImpact(
        tuple(p.id for p in wanted),
        tuple((i, tuple(v)) for i, v in sorted(by_if.items())),
        outdated,
        tuple(blocked),
        pin_set_frozen(project, connector_id),
        locked,
    )


def next_pin_ids(
    project: Project, connector_id: str, count: int = 1, after: str | None = None
) -> list[str]:
    """The names `ops_add_pins` gives to new pins: the next free numbers, counted on from the pin
    `after` (or from the highest number), ignoring case."""
    c = _box(project, connector_id)
    return _next_numbers((p.id for p in c.pins), count, after)


def ops_add_pins(
    project: Project,
    connector_id: str,
    pin_ids: Sequence[str] | None = None,
    *,
    count: int = 1,
    after: str | None = None,
) -> list[Op]:
    """Add pins. Without names they are the next free numbers, counted on from `after` (or from
    the highest number). They go after the pin `after`, else at the end. Refused above the part's
    pin count and for a connector whose pin set is frozen."""
    _writable(project)
    c = _box(project, connector_id)
    if why := pin_set_frozen(project, connector_id):
        raise EditError(f"Pins cannot be added to {connector_id}. {why}")
    at = len(c.pins) if after is None else _find_pin(c, after)[0] + 1
    ids = (
        [check_pin(p) for p in pin_ids]
        if pin_ids is not None
        else _next_numbers((p.id for p in c.pins), count, after)
    )
    if not ids:
        return []
    _unique_ids([p.id for p in c.pins] + ids)
    limit = _limit(project, c)
    if len(c.pins) + len(ids) > limit:
        raise EditError(
            f"{connector_id} cannot have more than {limit} pins "
            f"({c.part_id} has {limit}); it has {len(c.pins)}."
        )
    pins = [*c.pins[:at], *(Pin(id=i) for i in ids), *c.pins[at:]]
    return [Put("connectors", c.model_copy(update={"pins": pins}))]


def ops_delete_pins(project: Project, connector_id: str, pin_ids: Collection[str]) -> list[Op]:
    """Delete pins. Refused for a frozen connector, for a pin that carries a released interface
    and for a pin that a harness made by hand (or released) has a wire on."""
    _writable(project)
    c = _box(project, connector_id)
    missing = sorted(set(pin_ids) - {p.id for p in c.pins})
    if missing:
        raise EditError(f"{connector_id} has no pin '{missing[0]}'.")
    if not pin_ids:
        return []
    impact = pin_impact(project, connector_id, pin_ids)
    if impact.frozen:
        raise EditError(f"Pins cannot be deleted from {connector_id}. {impact.frozen}")
    if impact.locked:
        raise EditError(impact.locked[0][1])
    if impact.blocked_by_harnesses:
        raise EditError(
            f"Pin {', '.join(impact.pin_ids)} cannot be deleted: "
            f"{_blocked_by_text(impact.blocked_by_harnesses)}"
        )
    pins = [p for p in c.pins if p.id not in pin_ids]
    return [Put("connectors", c.model_copy(update={"pins": pins}))]


def ops_rename_pin(project: Project, connector_id: str, old: str, new: str) -> list[Op]:
    """Rename a pin; its signal, mode and interface stay. The new name must be free ignoring
    case (renaming `A1` to `a1` is fine). Refused where deleting the pin would be."""
    _writable(project)
    c = _box(project, connector_id)
    k, pin = _find_pin(c, old)
    new = check_pin(new)
    if new == old:
        return []
    if any(p.id.casefold() == new.casefold() for p in c.pins if p.id != old):
        raise EditError(
            f"{connector_id} already has a pin '{new}' (names are the same ignoring case)."
        )
    impact = pin_impact(project, connector_id, {old})
    if impact.frozen:
        raise EditError(f"Pins of {connector_id} cannot be renamed. {impact.frozen}")
    if impact.locked:
        raise EditError(impact.locked[0][1])
    if impact.blocked_by_harnesses:
        raise EditError(
            f"Pin {old} cannot be renamed: {_blocked_by_text(impact.blocked_by_harnesses)}"
        )
    pins = list(c.pins)
    pins[k] = evolve(pin, id=new)
    return [Put("connectors", c.model_copy(update={"pins": pins}))]


def ops_set_pinout(project: Project, connector_id: str, pins: Sequence[Pin]) -> list[Op]:
    """Replace the whole pin list in one `Put`: for a paste, a fill or an import. Checked as the
    single edits are: names usable and unique ignoring case, not more than the part has, a frozen
    connector keeps its pin ids, pins of a released interface stay as they are, and no pin a
    harness made by hand uses is dropped."""
    _writable(project)
    c = _box(project, connector_id)
    new = list(pins)
    if new == c.pins:
        return []
    ids = [p.id for p in new]
    for pid in ids:
        check_pin(pid)
    _unique_ids(ids)
    limit = _limit(project, c)
    if len(new) > limit:
        raise EditError(
            f"{connector_id} cannot have more than {limit} pins; {len(new)} were given."
        )
    old_by_id = {p.id: p for p in c.pins}
    gone = sorted(set(old_by_id) - set(ids))
    added = sorted(set(ids) - set(old_by_id))
    if (gone or added) and (why := pin_set_frozen(project, connector_id)):
        raise EditError(f"The pins of {connector_id} cannot be added, removed or renamed. {why}")
    for p in new:
        before = old_by_id.get(p.id)
        if (
            before is not None
            and before != p
            and (why := pin_lock_reason(project, connector_id, p.id))
        ):
            raise EditError(f"Pin {p.id} of {connector_id} cannot change. {why}")
    if gone:
        impact = pin_impact(project, connector_id, gone)
        if impact.locked:
            raise EditError(impact.locked[0][1])
        if impact.blocked_by_harnesses:
            raise EditError(
                f"Pin {', '.join(gone)} cannot be removed: "
                f"{_blocked_by_text(impact.blocked_by_harnesses)}"
            )
    return [Put("connectors", c.model_copy(update={"pins": new}))]


# ---- rows from a spreadsheet (paste and import) ------------------------------------------------

ROW_COLUMNS = ("pin", "signal", "mode", "contact_size", "termination", "function", "contact_part")


@dataclass(frozen=True)
class RowIssue:
    row: int  # 1-based position in the rows given
    pin: str
    reason: str

    def text(self) -> str:
        return f"row {self.row}: {self.reason}"


@dataclass(frozen=True)
class PinRowsPlan:
    pins: tuple[Pin, ...]  # the pin list the rows give (when `issues` is empty)
    issues: tuple[RowIssue, ...]
    added: tuple[str, ...]
    changed: tuple[str, ...]
    removed: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


_MODE_WORDS = {
    "": None, "free": "free", "auto": "free", "fixed": "fixed", "locked": "locked", "lock": "locked",
}  # fmt: skip
_TERM_WORDS = {
    "": "unspecified",
    "crimp": "crimp",
    "solder": "solder",
    "unspecified": "unspecified",
}


def plan_pin_rows(
    project: Project,
    connector_id: str,
    rows: Sequence[Mapping[str, str]],
    *,
    replace: bool = False,
    row_numbers: Sequence[int] | None = None,
) -> PinRowsPlan:
    """Pin rows (keys of `ROW_COLUMNS`; only the keys present are written) merged into the pins
    of a connector: a row whose `pin` exists changes that pin, any other adds a pin at the end.
    With `replace` the pins that no row names are dropped (an import of a whole pinout). Every
    row that cannot be used gets a reason; nothing is raised for a bad row. `row_numbers` says what
    each row is called in the file it came from (default 1, 2, 3 ...)."""
    c = _box(project, connector_id)
    order = [p.id for p in c.pins]
    by_id: dict[str, Pin] = {p.id: p for p in c.pins}
    fold = {p.id.casefold(): p.id for p in c.pins}
    seen: dict[str, int] = {}
    issues: list[RowIssue] = []
    added: list[str] = []
    changed: list[str] = []
    named: list[str] = []
    for k, row in enumerate(rows):
        n = row_numbers[k] if row_numbers is not None else k + 1
        raw = (row.get("pin") or "").strip()
        try:
            pid = check_pin(raw) if raw else None
        except EditError as exc:
            issues.append(RowIssue(n, raw, str(exc)))
            continue
        if pid is None:
            issues.append(RowIssue(n, "", "the pin name is empty"))
            continue
        if pid.casefold() in seen:
            issues.append(
                RowIssue(n, pid, f"pin '{pid}' is listed again (row {seen[pid.casefold()]})")
            )
            continue
        seen[pid.casefold()] = n
        key = fold.get(pid.casefold())
        if key is not None and key != pid:
            issues.append(RowIssue(n, pid, f"pin '{pid}' is the same as '{key}' ignoring case"))
            continue
        changes: dict[str, object] = {}
        try:
            if "signal" in row:
                changes["signal"] = row["signal"]
            if "contact_size" in row:
                changes["contact_size"] = row["contact_size"]
            if "function" in row:
                changes["function"] = row["function"]
            if "contact_part" in row:
                changes["contact_part"] = row["contact_part"]
            if "mode" in row:
                word = _MODE_WORDS.get(row["mode"].strip().casefold(), "?")
                if word == "?":
                    raise EditError(f"the mode '{row['mode']}' is not free, fixed or locked")
                if word is not None:
                    changes["mode"] = word
            if "termination" in row:
                word2 = _TERM_WORDS.get(row["termination"].strip().casefold())
                if word2 is None:
                    raise EditError(
                        f"the termination '{row['termination']}' is not crimp or solder"
                    )
                changes["termination"] = word2
            base = by_id.get(pid) or Pin(id=pid)
            new = _edit_pin(base, changes, project)
        except EditError as exc:
            issues.append(RowIssue(n, pid, str(exc).rstrip(".")))
            continue
        named.append(pid)
        if pid in by_id:
            if new != by_id[pid]:
                changed.append(pid)
        else:
            order.append(pid)
            added.append(pid)
        by_id[pid] = new
    removed: list[str] = []
    if replace:
        removed = [p for p in order if p not in named]
        order = list(named)  # the order of the sheet
    if not issues and len(order) > _limit(project, c):
        issues.append(
            RowIssue(0, "", f"{connector_id} cannot have more than {_limit(project, c)} pins; "
                     f"these rows make {len(order)}")
        )  # fmt: skip
    return PinRowsPlan(
        tuple(by_id[i] for i in order), tuple(issues), tuple(added), tuple(changed), tuple(removed)
    )


def ops_paste_rows(
    project: Project,
    connector_id: str,
    rows: Sequence[Mapping[str, str]],
    *,
    replace: bool = False,
) -> list[Op]:
    """`plan_pin_rows` as one `Put` (one undo step); an EditError names the first bad row."""
    plan = plan_pin_rows(project, connector_id, rows, replace=replace)
    if plan.issues:
        more = f" (and {len(plan.issues) - 1} more)" if len(plan.issues) > 1 else ""
        raise EditError(plan.issues[0].text() + more)
    return ops_set_pinout(project, connector_id, plan.pins)


# ---- interface types on the pins ---------------------------------------------------------------


def suggest_carries(project: Project, connector_id: str) -> list[str]:
    """Interface types whose signals are all on the pins of this connector, sorted by ID."""
    c = _box(project, connector_id)
    have = {p.signal for p in c.pins if p.signal}
    return sorted(
        t.id
        for t in project.interface_types.values()
        if t.signals and {s.name for s in t.signals} <= have
    )


def fill_from_type(
    project: Project,
    connector_id: str,
    pin_ids: Sequence[str],
    type_id: str,
    *,
    fixed: bool = True,
) -> list[Op]:
    """Put the signals of an interface type on the selected pins, in the order of the type and
    of the pins given (CANH, CANL, CANGND). The pins become fixed (the device defines them) unless
    `fixed` is false; an earlier assignment to an interface goes. One `Put`."""
    _writable(project)
    c = _box(project, connector_id)
    t = project.interface_types.get(type_id)
    if t is None:
        raise EditError(f"Interface type '{type_id}' does not exist.")
    if len(pin_ids) != len(t.signals):
        raise EditError(
            f"{t.name} has {len(t.signals)} signal{'s' if len(t.signals) != 1 else ''} "
            f"({', '.join(s.name for s in t.signals)}); {len(pin_ids)} pin"
            f"{'s are' if len(pin_ids) != 1 else ' is'} selected."
        )
    _unique_ids(list(pin_ids))
    by_signal = dict(zip(pin_ids, (s.name for s in t.signals), strict=True))
    pins = []
    for p in c.pins:
        if p.id in by_signal:
            if why := pin_lock_reason(project, connector_id, p.id):
                raise EditError(f"Pin {p.id} of {connector_id} cannot change. {why}")
            p = _edit_pin(p, {"signal": by_signal[p.id], "mode": "fixed" if fixed else "free"})
            if p.interface_id is not None:
                p = evolve(p, interface_id=None)
        pins.append(p)
    missing = sorted(set(pin_ids) - {p.id for p in c.pins})
    if missing:
        raise EditError(f"{connector_id} has no pin '{missing[0]}'.")
    return [Put("connectors", c.model_copy(update={"pins": pins}))]


# ---- what the pins mean (derived, never guessed) -----------------------------------------------


def _types_with_signal(project: Project) -> dict[str, list[InterfaceType]]:
    out: dict[str, list[InterfaceType]] = defaultdict(list)
    for t in project.interface_types.values():
        for s in t.signals:
            out[s.name].append(t)
    return out


def derive_meaning(
    project: Project,
    connector: Connector,
    pin: Pin,
    index: Mapping[str, list[InterfaceType]] | None = None,
) -> tuple[str, str, str]:
    """(direction, category, note) of a pin, from the interface type of its signal. The pin's own
    interface decides when it has one; otherwise the signal name must belong to the interface
    types this connector carries (all types when it carries none) and they must agree. When
    nothing can be said, direction and category are empty and the note says why."""
    if not pin.signal:
        return "", "", "No signal on this pin."
    iface = project.interfaces.get(pin.interface_id) if pin.interface_id else None
    if iface is not None and iface.type_id in project.interface_types:
        t = project.interface_types[iface.type_id]
        for s in t.signals:
            if s.name == pin.signal:
                return s.direction, t.category, f"From {t.name} ({iface.id})."
        return "", "", f"{pin.signal} is not a signal of {t.name}, the type of {iface.id}."
    index = index if index is not None else _types_with_signal(project)
    types = index.get(pin.signal, [])
    if connector.carries:
        narrowed = [t for t in types if t.id in connector.carries]
        types = narrowed or types
    if not types:
        return "", "", f"No interface type has a signal called '{pin.signal}'."
    meanings = {
        (next(s.direction for s in t.signals if s.name == pin.signal), t.category) for t in types
    }
    if len(meanings) > 1:
        return "", "", f"Several interface types use '{pin.signal}' with different meanings."
    direction, category = next(iter(meanings))
    return direction, category, f"From {', '.join(sorted(t.name for t in types))}."


# ---- the pin table as the view reads it --------------------------------------------------------


@dataclass(frozen=True)
class PinRow:
    pin: str
    signal: str
    mode: PinMode
    interface_id: str
    direction: str  # derived from the interface type, or empty
    category: str  # derived, or empty
    note: str  # why direction and category are empty, or where they come from
    wires: tuple[str, ...]  # wires of any harness that end on this pin through a cable end
    contact_size: str
    termination: str
    spare: bool  # no signal, no interface, no wire (the "Spare" column of the export)
    auto: bool  # allocated by Generate (an interface, not locked, not fixed)
    lock: str | None  # why the pin cannot be edited (a released interface uses it)
    severity: Severity | None  # the worst inline problem about this pin
    function: str = ""  # a person's words for what the pin does
    contact_part: str = ""  # the contact the cable side uses here (a library part)


_RANK: dict[Severity, int] = {"error": 0, "warning": 1, "info": 2}


def wire_index(project: Project) -> dict[tuple[str, str], list[str]]:
    """(box connector, pin) -> the wires that end on it through a cable end (as `box_pinouts`)."""
    attached: dict[tuple[str, str], list[str]] = defaultdict(list)
    for h in project.harnesses.values():
        mates = {c.id: c.mates_with for c in h.connectors}
        for w in h.wires:
            for cid, pin in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
                if mates.get(cid):
                    attached[(mates[cid] or "", pin)].append(w.id)
    return attached


def pin_rows(
    project: Project,
    connector_id: str,
    *,
    problems: Sequence[PinProblem] | None = None,
) -> list[PinRow]:
    """One row per pin, in the order of the connector, with the derived columns."""
    c = _box(project, connector_id)
    attached = wire_index(project)
    index = _types_with_signal(project)
    found = problems if problems is not None else pinout_problems(project, connector_id)
    worst: dict[str, Severity] = {}
    for pr in found:
        if pr.pin_id is not None and (
            pr.pin_id not in worst or _RANK[pr.severity] < _RANK[worst[pr.pin_id]]
        ):
            worst[pr.pin_id] = pr.severity
    frozen = _frozen_pins(project, c)
    out = []
    for p in c.pins:
        wires = tuple(sorted(attached.get((c.id, p.id), [])))
        direction, category, note = derive_meaning(project, c, p, index)
        out.append(
            PinRow(
                p.id,
                p.signal or "",
                pin_mode(p),
                p.interface_id or "",
                direction,
                category,
                note,
                wires,
                p.contact_size or "",
                p.termination,
                not (wires or p.interface_id or p.signal),
                p.interface_id is not None and not p.locked and not p.fixed,
                frozen.get(p.id),
                worst.get(p.id),
                p.function or "",
                p.contact_part or "",
            )
        )
    return out


def _frozen_pins(project: Project, c: Connector) -> dict[str, str]:
    """Pin -> the lock sentence, for the pins of a released interface (one scan of the releases)."""
    out: dict[str, str] = {}
    pinned = [p for p in c.pins if p.interface_id]
    if not pinned:
        return out
    for h in _released(project):
        carried = carried_interfaces(h)
        for p in pinned:
            if p.id not in out and p.interface_id in carried:
                key = ("box_pin", f"{c.id}.{p.id}")
                out[p.id] = lock_reason(project, "box_pin", f"{c.id}.{p.id}", {key: _ref(h)}) or ""
    return out


def pinout_table(project: Project, unit_id: str) -> Table:
    """The rows `system/box_pinouts.csv` will hold for this device, header first."""
    if unit_id not in project.units:
        raise EditError(f"Device '{unit_id}' does not exist.")
    return box_pinouts(project, {c.id for c in unit_connectors(project, unit_id)})


# ---- inline checks (editor only; not design rules) ---------------------------------------------


@dataclass(frozen=True)
class PinProblem:
    check: str  # "CD-K1" ... "CD-K8"
    code: str
    severity: Severity
    message: str
    connector_id: str
    pin_id: str | None = None


def _fixed_pinout(c: Connector) -> bool:
    return any(p.fixed and p.signal for p in c.pins)


def _interface_has_end(i: InterfaceInstance, unit_id: str | None, connector_id: str) -> bool:
    return any(
        e.connector_id == connector_id or (e.connector_id is None and e.unit_id == unit_id)
        for e in i.endpoints
    )


def pinout_problems(project: Project, connector_id: str) -> list[PinProblem]:
    """The inline notes about one box connector (CD-K1 to CD-K8), worst first, then in pin order.
    None of them is a design rule; they are shown under the pin table."""
    c = _box(project, connector_id)
    out: list[PinProblem] = []
    pos = {p.id: k for k, p in enumerate(c.pins)}

    def add(check: str, code: str, sev: Severity, msg: str, pin: str | None = None) -> None:
        out.append(PinProblem(check, code, sev, msg, c.id, pin))

    part = project.parts.get(c.part_id)
    # CD-K1: names that clash
    firsts: dict[str, str] = {}
    for p in c.pins:
        key = p.id.casefold()
        if key not in firsts:
            firsts[key] = p.id
        elif firsts[key] == p.id:
            add("CD-K1", "pin_listed_twice", "error", f"Pin {p.id} is listed more than once.", p.id)
        else:
            add("CD-K1", "pin_same_ignoring_case", "error", f"Pins {firsts[key]} and {p.id} are the same name ignoring case.", p.id)  # fmt: skip
        try:
            check_pin_id(p.id)
        except ValueError:
            add("CD-K1", "pin_name_unusable", "error", f"Pin '{p.id}' is not a usable pin name.", p.id)  # fmt: skip
    # CD-K2: count against the part
    if part is not None and part.pin_count is not None:
        if len(c.pins) > part.pin_count:
            add("CD-K2", "too_many_pins", "error", f"{len(c.pins)} pins but {part.id} has only {part.pin_count}.")  # fmt: skip
        elif len(c.pins) < part.pin_count:
            add("CD-K2", "pins_missing", "info", f"{len(c.pins)} of {part.pin_count} pins defined.")
    # CD-K3 and CD-K4: signals
    by_signal: dict[str, list[str]] = defaultdict(list)
    for p in c.pins:
        if p.signal:
            by_signal[p.signal].append(p.id)
    for sig, pins in by_signal.items():
        if len(pins) > 1:
            add("CD-K3", "signal_on_two_pins", "warning", f"The signal {sig} is on pins {', '.join(pins)}.", pins[1])  # fmt: skip
    known = {s.name for t in project.interface_types.values() for s in t.signals}
    folded = {k.casefold(): k for k in known}
    for p in c.pins:
        if p.signal and p.signal not in known and p.interface_id is None:
            near = folded.get(p.signal.casefold())
            hint = f" Did you mean {near}?" if near else ""
            add("CD-K4", "signal_unknown", "info", f"No interface type has a signal called '{p.signal}', so nothing can connect to pin {p.id}.{hint}", p.id)  # fmt: skip
    # CD-K5 and CD-K8: interface types on a fixed pinout
    if _fixed_pinout(c):
        have = set(by_signal)
        complete = {
            t.id
            for t in project.interface_types.values()
            if t.signals and {s.name for s in t.signals} <= have
        }
        explained = {
            s.name for t in project.interface_types.values() if t.id in complete for s in t.signals
        }
        for t in sorted(project.interface_types.values(), key=lambda x: x.id):
            names = [s.name for s in t.signals]
            present = [n for n in names if n in have]
            if t.id in complete or not present or set(present) <= explained:
                continue
            gone = [n for n in names if n not in have]
            first = by_signal[present[0]][0]
            add("CD-K5", "interface_incomplete", "warning", f"{', '.join(present)} of {t.name} {'is' if len(present) == 1 else 'are'} here but {', '.join(gone)} has no pin on {c.id}.", first)  # fmt: skip
        for tid in c.carries:
            carried_t = project.interface_types.get(tid)
            if carried_t is not None and tid not in complete:
                gone = [s.name for s in carried_t.signals if s.name not in have]
                add("CD-K8", "carries_incomplete", "warning", f"{c.id} is meant for {carried_t.name}, but its pins have no {', '.join(gone)}.")  # fmt: skip
    # CD-K6: a locked pin and its interface
    for p in c.pins:
        if not (p.locked and p.interface_id):
            continue
        i = project.interfaces.get(p.interface_id)
        if i is None:
            add("CD-K6", "locked_pin_interface_missing", "error", f"Pin {p.id} is locked to {p.interface_id}, which does not exist.", p.id)  # fmt: skip
            continue
        if not _interface_has_end(i, c.unit_id, c.id):
            add("CD-K6", "locked_pin_wrong_connector", "error", f"Pin {p.id} is locked to {i.id}, which does not end on {c.id}.", p.id)  # fmt: skip
        itype = project.interface_types.get(i.type_id)
        if itype is not None and p.signal not in {s.name for s in itype.signals}:
            add("CD-K6", "locked_pin_wrong_signal", "error", f"Pin {p.id} is locked to {i.id} with the signal {p.signal or '(none)'}, which is not a signal of {itype.name}.", p.id)  # fmt: skip
    # CD-K7: gender nobody states
    if c.gender == "unspecified" and part_gender(part) == "unspecified":
        add("CD-K7", "gender_unspecified", "warning", f"The gender of {c.id} is not set and {c.part_id} does not say it, so the cable end cannot be checked to fit.")  # fmt: skip
    out.sort(key=lambda x: (_RANK[x.severity], pos.get(x.pin_id or "", len(pos)), x.check))
    return out


# ---- the state of a device ---------------------------------------------------------------------

DeviceStateName = Literal["draft", "in_use", "locked", "read_only"]


@dataclass(frozen=True)
class DeviceState:
    state: DeviceStateName
    sentence: str  # one sentence for the chip's tooltip and the banner
    interfaces: tuple[str, ...]  # interfaces that end on the device
    harnesses: tuple[str, ...]  # harnesses that carry them or have a cable end on it
    released_by: tuple[LockRef, ...]  # released harnesses that lock it (by ID)


def device_state(project: Project, unit_id: str) -> DeviceState:
    """Draft (no interface ends on the device), In use (one does, or a harness plugs into it),
    Locked (a released harness uses it) or Read-only (the project cannot be changed). Worked out
    from the project each time; the file holds no state."""
    unit = project.units.get(unit_id)
    if unit is None:
        raise EditError(f"Device '{unit_id}' does not exist.")
    conns = {c.id for c in unit_connectors(project, unit_id)}
    ifs = tuple(
        sorted(
            i.id
            for i in project.interfaces.values()
            if any(e.unit_id == unit_id for e in i.endpoints)
        )
    )
    harnesses = sorted(
        h.id
        for h in project.harnesses.values()
        if carried_interfaces(h) & set(ifs) or any(c.mates_with in conns for c in h.connectors)
    )
    locked = locked_objects(project)
    refs: list[LockRef] = []
    for kind, oid in [("unit", unit_id)] + [("box_connector", cid) for cid in sorted(conns)]:
        for r in locked.get((kind, oid), []):
            if r not in refs:
                refs.append(r)
    refs.sort()
    if project.read_only:
        state: DeviceStateName = "read_only"
        sentence = "This project is read-only (saved by a newer tool version). Use Save as."
    elif refs:
        state = "locked"
        sentence = lock_reason(project, "unit", unit_id, locked) or next(
            (
                why
                for cid in sorted(conns)
                if (why := lock_reason(project, "box_connector", cid, locked))
            ),
            "",
        )
    elif ifs or harnesses:
        state = "in_use"
        users = ", ".join(ifs[:3]) + (f" and {len(ifs) - 3} more" if len(ifs) > 3 else "")
        sentence = (
            f"{unit_id} is used by {users or ', '.join(harnesses)}. Changing its pins makes the "
            "harness plans out of date."
        )
    else:
        state = "draft"
        sentence = f"No interface ends on {unit_id} yet; everything can change."
    return DeviceState(state, sentence, ifs, tuple(harnesses), tuple(refs))


# ---- a new device (CD-C1) ----------------------------------------------------------------------

DEVICE_FIELDS = frozenset({"name", "subsystem", "side", "notes"})
_SIDES: tuple[str, ...] = get_args(Side)


def default_subsystem(project: Project) -> str:
    """The subsystem most units have (the first by name on a tie), else "general": what a new
    device gets until its owner types another."""
    counts: dict[str, int] = defaultdict(int)
    for u in project.units.values():
        counts[u.subsystem] += 1
    return sorted(counts, key=lambda k: (-counts[k], k))[0] if counts else "general"


def suggest_device_id(project: Project, name: str) -> str:
    """A short upper-case ID for a new device named `name`: the letters and digits of its first
    word plus the first number that is free in the project ("Star tracker" gives STAR1, then
    STAR2; a word that ends in a digit is used as it is when it is free). Empty while the name has no letter or digit to start from."""
    folded = unicodedata.normalize("NFKD", name or "")
    words = [re.sub(r"[^A-Za-z0-9]", "", w) for w in folded.split()]
    stem = ""
    for word in words:
        word = word.lstrip("0123456789")
        if word:
            stem = word[:8].upper()
            break
    if not stem:
        return ""
    taken = edit._taken(set(project.units)) | edit._connector_owners(project)
    if stem[-1].isdigit() and stem.casefold() not in taken:
        return stem  # ("Gyro 3" is GYRO3, not GYRO31)
    return edit.next_unit_id(project, stem)[0]


def check_new_device(project: Project, unit_id: str, name: str) -> str:
    """Why a device cannot be added with this ID and name, in a plain sentence, or "" when it
    can: the sentence the new-device dialog shows under its fields."""
    if not (name or "").strip():
        return "A device needs a name."
    try:
        _text(name, "A device name")
    except EditError as exc:
        return str(exc)
    uid = (unit_id or "").strip()
    if not uid:
        return "A device needs an ID."
    try:
        edit._check_new_id(uid)
    except EditError as exc:
        return str(exc)
    if uid.casefold() in edit._taken(set(project.units)):
        return f"ID {uid} is already used by another device."
    if uid.casefold() in edit._connector_owners(project):
        return f"ID {uid} is already used as the start of connector IDs."
    return ""


def ops_add_device(
    project: Project,
    *,
    unit_id: str | None = None,
    name: str | None = None,
    subsystem: str | None = None,
    side: str = "nominal",
    zone: str | None = None,
    x: float | None = None,
    y: float | None = None,
) -> tuple[list[Op], str]:
    """Add a device: a unit with no connectors yet, placed in a free slot of its lane. The ID is
    the next free `DEV<n>` unless given; the subsystem is `default_subsystem` unless given."""
    _writable(project)
    if unit_id is None:
        uid, n = edit.next_unit_id(project, "DEV")
        label = f"Device {n}"
    else:
        uid, label = unit_id, f"Device {unit_id}"
        edit._check_new_id(uid)
        if uid.casefold() in edit._taken(set(project.units)) | edit._connector_owners(project):
            raise EditError(f"ID {uid} is already used.")
    if side not in _SIDES:
        raise EditError(f"A chain is one of {', '.join(_SIDES)}.")
    if zone is not None and zone not in edit.effective_zones(project):
        raise EditError(f"Zone '{zone}' does not exist.")
    if x is None or y is None:
        x, y = edit.free_slot(project, zone, edit.expert_height(0))
    unit = Unit(
        id=uid,
        name=_text(name, "A device name") or label,
        subsystem=_text(subsystem, "A subsystem") or default_subsystem(project),
        zone=zone or edit.zone_of_x(project, x) or None,
        side=side,  # type: ignore[arg-type]
    )
    return [Put("units", unit), Put("placements", Placement(id=uid, x=x, y=y))], uid


def ops_update_device(project: Project, unit_id: str, **changes: object) -> list[Op]:
    """Change the name, subsystem, chain or notes of a device. Subsystem and chain are design
    fields: refused with the reason while a release uses the device."""
    _writable(project)
    unit = project.units.get(unit_id)
    if unit is None:
        raise EditError(f"Device '{unit_id}' does not exist.")
    bad = set(changes) - DEVICE_FIELDS
    if bad:
        raise EditError(f"These device fields cannot be changed here: {', '.join(sorted(bad))}.")
    new: dict[str, object] = {}
    for key, value in changes.items():
        if key in ("name", "subsystem"):
            text = _text(value, "A device name" if key == "name" else "A subsystem")
            if text is None:
                raise EditError(
                    "A device needs a name." if key == "name" else "A device needs a subsystem."
                )
            new[key] = text
        elif key == "side":
            if value not in _SIDES:
                raise EditError(f"A chain is one of {', '.join(_SIDES)}.")
            new[key] = value
        else:
            if not isinstance(value, str):
                raise EditError("Notes must be text.")
            new[key] = value
    new = {k: v for k, v in new.items() if getattr(unit, k) != v}
    for key in new:
        if why := field_lock_reason(project, "unit", unit_id, key):
            raise EditError(f"The {key} of {unit_id} cannot change. {why}")
    return [Put("units", evolve(unit, **new))] if new else []


# ---- interface on pins (CD-C7) -----------------------------------------------------------------


def ops_assign_pins(
    project: Project,
    connector_id: str,
    pin_ids: Sequence[str],
    interface_id: str,
    signals: Sequence[str] | None = None,
) -> list[Op]:
    """Put an interface on pins: each pin becomes locked, with the interface and one signal of its
    type (the type's signals in order unless `signals` names one per pin). The interface must end
    on this device; an end without a connector gets this one in the same step. A connector carries
    one interface in the editor, so a connector another interface ends on is refused."""
    _writable(project)
    c = _box(project, connector_id)
    i = project.interfaces.get(interface_id)
    if i is None:
        raise EditError(f"Interface '{interface_id}' does not exist.")
    t = project.interface_types.get(i.type_id)
    if t is None:
        raise EditError(f"Interface type '{i.type_id}' does not exist.")
    ends = [k for k, e in enumerate(i.endpoints) if e.unit_id == c.unit_id]
    if not ends:
        raise EditError(f"{interface_id} does not end on {c.unit_id}.")
    fill: int | None = None  # the end that gets this connector
    if not any(i.endpoints[k].connector_id == connector_id for k in ends):
        fill = next((k for k in ends if i.endpoints[k].connector_id is None), None)
        if fill is None:
            raise EditError(
                f"{interface_id} ends on {i.endpoints[ends[0]].connector_id}, not on {connector_id}."
            )
        used = edit.interface_using(project, connector_id)
        if used is not None and used.id != interface_id:
            raise EditError(
                f"{connector_id} already carries {used.id}. One interface per connector."
            )
        if not edit.carries(c, i.type_id):
            raise EditError(f"{connector_id} is not meant for {t.name}.")
        if why := field_lock_reason(project, "interface", interface_id, "endpoints"):
            raise EditError(f"{interface_id} cannot change. {why}")
    names = list(signals) if signals is not None else [s.name for s in t.signals]
    if len(pin_ids) != len(names):
        raise EditError(
            f"{t.name} needs {len(names)} pin{'s' if len(names) != 1 else ''} "
            f"({', '.join(names)}); {len(pin_ids)} {'is' if len(pin_ids) == 1 else 'are'} selected."
        )
    _unique_ids(list(pin_ids))
    for sig in names:
        if sig not in {s.name for s in t.signals}:
            raise EditError(f"{sig} is not a signal of {t.name}.")
    if len(set(names)) != len(names):
        raise EditError("A signal can be on one pin only.")
    mapping = dict(zip(pin_ids, names, strict=True))
    missing = sorted(set(pin_ids) - {p.id for p in c.pins})
    if missing:
        raise EditError(f"{connector_id} has no pin '{missing[0]}'.")
    pins = []
    for p in c.pins:
        if p.id in mapping:
            if why := pin_lock_reason(project, connector_id, p.id):
                raise EditError(f"Pin {p.id} of {connector_id} cannot change. {why}")
            p = evolve(p, signal=mapping[p.id], interface_id=interface_id, locked=True, fixed=False)
        pins.append(p)
    ops: list[Op] = [Put("connectors", c.model_copy(update={"pins": pins}))]
    if fill is not None:
        eps = [
            e.model_copy(update={"connector_id": connector_id, "auto": False}) if k == fill else e
            for k, e in enumerate(i.endpoints)
        ]
        ops.append(Put("interfaces", evolve(i, endpoints=eps)))
    return ops


def ops_unassign_pins(project: Project, connector_id: str, pin_ids: Sequence[str]) -> list[Op]:
    """Take pins off their interface: the pin goes back to free, with no signal and no interface.
    A pin with no interface is left as it is."""
    _writable(project)
    c = _box(project, connector_id)
    missing = sorted(set(pin_ids) - {p.id for p in c.pins})
    if missing:
        raise EditError(f"{connector_id} has no pin '{missing[0]}'.")
    pins = []
    changed = False
    for p in c.pins:
        if p.id in pin_ids and p.interface_id is not None:
            if why := pin_lock_reason(project, connector_id, p.id):
                raise EditError(f"Pin {p.id} of {connector_id} cannot change. {why}")
            p = evolve(p, signal=None, interface_id=None, locked=False)
            changed = True
        pins.append(p)
    return [Put("connectors", c.model_copy(update={"pins": pins}))] if changed else []


# ---- pasted cells (CD-C6) ----------------------------------------------------------------------

GRID_COLUMNS = ROW_COLUMNS  # the columns a pasted block can fill


def rows_from_grid(
    project: Project,
    connector_id: str,
    start_pin: str | None,
    columns: Sequence[str],
    grid: Sequence[Sequence[str]],
) -> list[dict[str, str]]:
    """Cells from a spreadsheet as pin rows for `ops_paste_rows`. `columns` names what each pasted
    column is (keys of `ROW_COLUMNS`). With a `pin` column every row names its pin (new names add
    pins); without one the rows go to the pins from `start_pin` downwards, one pin per row."""
    c = _box(project, connector_id)
    bad = [k for k in columns if k not in GRID_COLUMNS]
    if bad:
        raise EditError(f"'{bad[0]}' is not a column that can be pasted.")
    out: list[dict[str, str]] = []
    ids = [p.id for p in c.pins]
    if "pin" in columns:
        for line in grid:
            out.append({k: (line[n] if n < len(line) else "") for n, k in enumerate(columns)})
        return out
    if start_pin is None or start_pin not in ids:
        raise EditError("Pick the pin the paste starts at.")
    first = ids.index(start_pin)
    if first + len(grid) > len(ids):
        room = len(ids) - first
        raise EditError(
            f"The paste has {len(grid)} row{'s' if len(grid) != 1 else ''} but only {room} "
            f"pin{'s' if room != 1 else ''} from {start_pin} down."
        )
    for n, line in enumerate(grid):
        row = {k: (line[m] if m < len(line) else "") for m, k in enumerate(columns)}
        row["pin"] = ids[first + n]
        out.append(row)
    return out


# ---- parts the editor makes: always pending and unverified, never approved (CD-C9) -------------

PART_FIELDS = frozenset(
    {
        "manufacturer",
        "part_number",
        "specification",
        "description",
        "pin_count",
        "mates_with",
        "notes",
    }
)


def _new_part_id(project: Project, part_id: str) -> str:
    edit._check_new_id(part_id)
    if part_id.casefold() in {p.casefold() for p in project.parts}:
        raise EditError(f"A part called '{part_id}' already exists.")
    return part_id


def _pin_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_PIN_COUNT:
        raise EditError(f"A pin count is a whole number from 1 to {MAX_PIN_COUNT}.")
    return value


def _part_description(pin_count: int, gender: str | None, description: str | None) -> str | None:
    """What the person typed, else the pin count and the gender they chose (so the gender of a
    connector made from this part can be read from the part, as for every other part)."""
    text = _text(description, "A description")
    if text is None and gender in ("male", "female"):
        return f"{pin_count}-pin connector, {gender}"
    return text


def ops_add_part(
    project: Project,
    *,
    part_id: str,
    pin_count: int,
    gender: str | None = None,
    manufacturer: str | None = None,
    part_number: str | None = None,
    description: str | None = None,
    mates_with: str | None = None,
) -> list[Op]:
    """Add a connector part to the library: approval `pending`, `unverified` true. The tool never
    approves a part; that is a decision for the people who own the parts list."""
    _writable(project)
    pid = _new_part_id(project, part_id)
    n = _pin_count(pin_count)
    if gender is not None and gender not in ("male", "female"):
        raise EditError("A part is male or female.")
    if mates_with is not None:
        _connector_part(project, mates_with)
    part = Part(
        id=pid,
        category="connector",
        approval="pending",
        unverified=True,
        pin_count=n,
        manufacturer=_text(manufacturer, "A manufacturer"),
        part_number=_text(part_number, "A part number"),
        description=_part_description(n, gender, description),
        mates_with=mates_with,
    )
    ops: list[Op] = [Put("parts", part)]
    if mates_with is not None:  # the other half names this one too
        ops.append(Put("parts", evolve(project.parts[mates_with], mates_with=pid)))
    return ops


def _swap_gender(text: str, other: str) -> str:
    """The description of the mating half: `male` and `female` change places; a description that
    names neither gets `, <other>` added, so the gender can be read from it."""
    swapped = re.sub(
        r"\b(fe)?male\b",
        lambda m: "male" if m.group(0).lower().startswith("fe") else "female",
        text,
        flags=re.IGNORECASE,
    )
    return swapped if swapped != text else f"{text}, {other}"


def _mate_id(part_id: str, gender: str) -> str:
    """`X-F` -> `X-M` (and back) when the ID ends in the letter of its gender, else `X-M`/`X-F`."""
    mine, theirs = ("F", "M") if gender == "female" else ("M", "F")
    if part_id.upper().endswith(f"-{mine}"):
        return f"{part_id[:-1]}{theirs}"
    return f"{part_id}-{theirs}"


def ops_add_part_pair(
    project: Project,
    *,
    part_id: str,
    pin_count: int,
    gender: str = "female",
    mate_id: str | None = None,
    manufacturer: str | None = None,
    part_number: str | None = None,
    description: str | None = None,
) -> list[Op]:
    """Add a connector part and its mating half in one step: opposite genders, `mates_with` both
    ways, both `pending` and `unverified`. The mate's ID is the same with the other letter (`X-F` and `X-M`) unless given."""
    _writable(project)
    if gender not in ("male", "female"):
        raise EditError("A part is male or female.")
    other = "male" if gender == "female" else "female"
    pid = _new_part_id(project, part_id)
    mid = _new_part_id(project, mate_id or _mate_id(pid, gender))
    if mid.casefold() == pid.casefold():
        raise EditError("The mating part needs its own ID.")
    n = _pin_count(pin_count)
    maker = _text(manufacturer, "A manufacturer")
    text = _part_description(n, gender, description)
    mate_text = _swap_gender(text, other) if text else f"{n}-pin connector, {other}"
    here = Part(
        id=pid, category="connector", approval="pending", unverified=True, pin_count=n,
        manufacturer=maker, part_number=_text(part_number, "A part number"), mates_with=mid,
        description=text,
    )  # fmt: skip
    there = Part(
        id=mid, category="connector", approval="pending", unverified=True, pin_count=n,
        manufacturer=maker, mates_with=pid, description=mate_text,
    )  # fmt: skip
    return [Put("parts", here), Put("parts", there)]


def ops_update_part(project: Project, part_id: str, **changes: object) -> list[Op]:
    """Change a part's maker, part number, specification, description, pin count, mating part or
    notes; never its approval. Refused while a release uses the part, and for a pin count below the
    pins a connector of this part already has."""
    _writable(project)
    part = project.parts.get(part_id)
    if part is None:
        raise EditError(f"Part '{part_id}' does not exist.")
    bad = set(changes) - PART_FIELDS
    if bad:
        raise EditError(f"These part fields cannot be changed here: {', '.join(sorted(bad))}.")
    new: dict[str, object] = {}
    for key, value in changes.items():
        if key == "pin_count":
            new[key] = _pin_count(value)
        elif key == "mates_with":
            if value is not None:
                _connector_part(project, str(value))
            new[key] = value
        elif key == "notes":
            if not isinstance(value, str):
                raise EditError("Notes must be text.")
            new[key] = value
        else:
            new[key] = _text(value, f"The {key.replace('_', ' ')}")
    new = {k: v for k, v in new.items() if getattr(part, k) != v}
    count = new.get("pin_count")
    if isinstance(count, int):
        for c in project.connectors.values():
            if c.part_id == part_id and len(c.pins) > count:
                raise EditError(f"{c.id} has {len(c.pins)} pins; {part_id} cannot have fewer.")
    for key in new:
        if why := field_lock_reason(project, "part", part_id, key):
            raise EditError(f"The {key.replace('_', ' ')} of {part_id} cannot change. {why}")
    return [Put("parts", evolve(part, **new))] if new else []


# ---- interface types the editor makes: unverified (CD-C10) -------------------------------------

TYPE_FIELDS = frozenset(
    {"name", "category", "signals", "construction", "shielding", "impedance_ohm", "emc_class",
     "default_gauge_awg", "notes"}
)  # fmt: skip
SignalSpec = tuple[str, str, str | None]  # name, direction, pair
_DIRECTIONS: tuple[str, ...] = get_args(Direction)
_CHOICES: dict[str, tuple[str, ...]] = {
    "category": get_args(Category),
    "construction": get_args(Construction),
    "shielding": get_args(Shielding),
}


def parse_signal_lines(text: str) -> list[SignalSpec]:
    """Lines of `NAME [direction [pair]]` (direction `out`, `in`, `bidir` or `passive`, default
    `passive`) as signal specs for `ops_add_interface_type`; blank lines are skipped."""
    out: list[SignalSpec] = []
    for n, line in enumerate(text.splitlines(), start=1):
        words = line.split()
        if not words:
            continue
        if len(words) > 3:
            raise EditError(f"Line {n}: write a name, then a direction, then a pair name.")
        direction = words[1] if len(words) > 1 else "passive"
        if direction not in _DIRECTIONS:
            raise EditError(f"Line {n}: a direction is one of {', '.join(_DIRECTIONS)}.")
        out.append((words[0], direction, words[2] if len(words) > 2 else None))
    return out


def _signals(specs: Iterable[SignalSpec | SignalDef]) -> list[SignalDef]:
    out: list[SignalDef] = []
    for spec in specs:
        name, direction, pair = (
            (spec.name, spec.direction, spec.pair) if isinstance(spec, SignalDef) else spec
        )
        text = _text(name, "A signal name")
        if text is None:
            raise EditError("A signal needs a name.")
        if direction not in _DIRECTIONS:
            raise EditError(f"A direction is one of {', '.join(_DIRECTIONS)}.")
        out.append(SignalDef(name=text, direction=direction, pair=_text(pair, "A pair name")))  # type: ignore[arg-type]
    if not out:
        raise EditError("An interface type needs at least one signal.")
    names = [s.name for s in out]
    for n in names:
        if names.count(n) > 1:
            raise EditError(f"The signal {n} is listed twice.")
    return out


def ops_add_interface_type(
    project: Project,
    *,
    type_id: str,
    name: str,
    category: str,
    signals: Iterable[SignalSpec],
    construction: str = "single",
    shielding: str = "none",
) -> list[Op]:
    """Add an interface type: its signals with direction and pair, marked `unverified` (nobody
    has confirmed it). The ID is free ignoring case."""
    _writable(project)
    edit._check_new_id(type_id)
    if type_id.casefold() in {t.casefold() for t in project.interface_types}:
        raise EditError(f"An interface type called '{type_id}' already exists.")
    label = _text(name, "A name")
    if label is None:
        raise EditError("An interface type needs a name.")
    for key, value in (
        ("category", category),
        ("construction", construction),
        ("shielding", shielding),
    ):
        if value not in _CHOICES[key]:
            raise EditError(f"A {key} is one of {', '.join(_CHOICES[key])}.")
    t = InterfaceType(
        id=type_id,
        name=label,
        category=category,  # type: ignore[arg-type]
        signals=_signals(signals),
        construction=construction,  # type: ignore[arg-type]
        shielding=shielding,  # type: ignore[arg-type]
        unverified=True,
    )
    return [Put("interface_types", t)]


def ops_update_interface_type(project: Project, type_id: str, **changes: object) -> list[Op]:
    """Change an interface type's name, category, signals, construction, shielding, impedance, EMC
    class, default gauge or notes. Refused while a release uses the type."""
    _writable(project)
    t = project.interface_types.get(type_id)
    if t is None:
        raise EditError(f"Interface type '{type_id}' does not exist.")
    bad = set(changes) - TYPE_FIELDS
    if bad:
        raise EditError(
            f"These interface type fields cannot be changed here: {', '.join(sorted(bad))}."
        )
    new: dict[str, object] = {}
    for key, value in changes.items():
        if key == "signals":
            if isinstance(value, str) or not isinstance(value, Iterable):
                raise EditError("Signals are a list.")
            new[key] = _signals(value)
        elif key == "name":
            text = _text(value, "A name")
            if text is None:
                raise EditError("An interface type needs a name.")
            new[key] = text
        else:
            if key in _CHOICES and value not in _CHOICES[key]:
                raise EditError(f"A {key} is one of {', '.join(_CHOICES[key])}.")
            new[key] = value
    new = {k: v for k, v in new.items() if getattr(t, k) != v}
    for key in new:
        if why := field_lock_reason(project, "interface_type", type_id, key):
            raise EditError(f"The {key.replace('_', ' ')} of {type_id} cannot change. {why}")
    return [Put("interface_types", evolve(t, **new))] if new else []


__all__ = [
    "CONNECTOR_FIELDS",
    "PIN_FIELDS",
    "PIN_MODES",
    "ROW_COLUMNS",
    "ConnectorImpact",
    "DeviceState",
    "PartChange",
    "PinImpact",
    "PinMode",
    "PinProblem",
    "PinRow",
    "PinRowsPlan",
    "RowIssue",
    "check_contact_part",
    "check_pin",
    "connector_delete_impact",
    "contact_part_choices",
    "derive_meaning",
    "device_state",
    "fill_from_type",
    "next_connector_name",
    "GRID_COLUMNS",
    "DEVICE_FIELDS",
    "PART_FIELDS",
    "TYPE_FIELDS",
    "SignalSpec",
    "check_new_device",
    "default_subsystem",
    "ops_add_device",
    "suggest_device_id",
    "ops_update_device",
    "ops_assign_pins",
    "ops_unassign_pins",
    "ops_add_part",
    "ops_add_part_pair",
    "ops_update_part",
    "ops_add_interface_type",
    "ops_update_interface_type",
    "parse_signal_lines",
    "rows_from_grid",
    "next_pin_ids",
    "ops_add_connector",
    "ops_add_pins",
    "ops_change_part",
    "ops_delete_connector",
    "ops_delete_pins",
    "ops_paste_rows",
    "ops_rename_pin",
    "ops_set_contacts",
    "ops_set_pin",
    "ops_set_pinout",
    "ops_update_connector",
    "pin_impact",
    "pin_lock_reason",
    "pin_mode",
    "pin_rows",
    "pin_set_frozen",
    "pinout_problems",
    "pinout_table",
    "plan_change_part",
    "plan_pin_rows",
    "suggest_carries",
    "wire_index",
]
