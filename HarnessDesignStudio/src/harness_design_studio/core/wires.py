"""Editing wires: gauge, type, colour, length, label and note of a generated wire, and wires that a
person draws between two pins.

    ops = plan_wire_edit(project, ["W001-0001", "W001-0002"], {"gauge_awg": 22, "colour": "red"})
    ops = plan_wire_reset(project, ["W001-0001"])          # give the wire back to generation
    ops = plan_add_wire(project, "W001", "W001-J1", "3", "W001-J2", "5", signal="HEATER")
    ops = plan_delete_wire(project, "W001-0099")           # only a wire that a person drew

Wires are generated, and generation puts them back the way the design says. A person's choice
stays when it is typed here: gauge, type, colour and length lock the wire (`Wire.locked`, which
generation honours); the label (text for the wire labels instead of the signal name) and the note
are always kept. A released harness cannot be edited; the plans say so in plain words before the
transaction would refuse them. Nothing here invents a value: a field is what the person typed.

A wire drawn by a person (`Wire.manual`) joins two pins of the cable connectors of one harness. It
has no interface, generation keeps it exactly as it is (and says so when it cannot: the connector
or pin is gone), and its ends can be moved. Two wires may share a pin; the design rule
`pin-shared` points it out. The ends of a generated wire follow the interface and the pin
assignment of the devices, so they are changed there.
"""

from collections.abc import Iterable, Mapping, Sequence

from pydantic import ValidationError

from .commands import Op, Put
from .edit import EditError
from .model import Harness, Project, Wire
from .model.base import evolve

EDITABLE: tuple[str, ...] = ("gauge_awg", "part_id", "colour", "length_m", "label", "note")
ENDS: tuple[str, ...] = (
    "from_connector",
    "from_pin",
    "to_connector",
    "to_pin",
)  # manual wires only
LOCKING: frozenset[str] = frozenset({"gauge_awg", "part_id", "colour", "length_m"})
_WHAT = {
    "gauge_awg": "The wire gauge (AWG)",
    "part_id": "The wire type",
    "colour": "The colour",
    "length_m": "The length",
    "label": "The label",
    "note": "The note",
}


def find_wire(project: Project, wire_id: str) -> tuple[Harness, Wire]:
    """The harness and the wire called `wire_id`, or an EditError."""
    for h in project.harnesses.values():
        for w in h.wires:
            if w.id == wire_id:
                return h, w
    raise EditError(f"Wire '{wire_id}' does not exist.")


def wire_part_choices(project: Project) -> list[str]:
    """The IDs of the wire parts of the project library, sorted: the choices for a wire type."""
    return sorted(p.id for p in project.parts.values() if p.category == "wire")


def _released(h: Harness) -> str:
    return f"{h.id} is released (revision {h.revision}); start a new revision to change it."


def _gauge(value: object) -> int:
    if isinstance(value, str):
        text = value.strip()
        if not text.lstrip("-").isdigit():
            raise EditError("The wire gauge (AWG) must be a whole number, for example 22.")
        return int(text)
    if isinstance(value, bool) or not isinstance(value, int):
        raise EditError("The wire gauge (AWG) must be a whole number, for example 22.")
    return value


def _length(value: object) -> float:
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            raise EditError("The length must be a number of metres, for example 1.5.") from None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise EditError("The length must be a number of metres, for example 1.5.")
    return float(value)


def _clean(project: Project, field: str, value: object) -> object:
    """The value of one field as the model wants it. An empty text clears an optional field."""
    if isinstance(value, str):
        value = value.strip()
        if value == "" and field != "note":
            value = None
    if value is None:
        if field in LOCKING:
            raise EditError(
                f"{_WHAT[field]} cannot be cleared on one wire. Use Reset to give the wire back "
                "to generation (it then takes its gauge, type, colour and length from the design)."
            )
        return "" if field == "note" else None
    if field == "gauge_awg":
        return _gauge(value)
    if field == "length_m":
        return _length(value)
    if field == "part_id":
        if value not in wire_part_choices(project):
            raise EditError(f"'{value}' is not a wire part of the library.")
        return value
    return value


class Change:
    """The new version of one wire (a callable, so `_apply` stays small)."""

    def __init__(self, changes: Mapping[str, object]) -> None:
        self.changes = dict(changes)

    def __call__(self, w: Wire) -> Wire:
        changes = {k: v for k, v in self.changes.items() if getattr(w, k) != v}
        if not changes:
            return w
        if LOCKING & changes.keys():
            changes["locked"] = True
        try:
            return evolve(w, **changes)
        except ValidationError as exc:
            msg = exc.errors()[0].get("msg", "not valid")
            raise EditError(f"Wire {w.id}: {msg}.") from exc


def _apply(project: Project, wire_ids: Sequence[str], make: Change) -> list[Op]:
    """One `Put` per harness whose wires changed; nothing when no wire changed."""
    wanted = list(dict.fromkeys(wire_ids))
    if not wanted:
        raise EditError("No wire is selected.")
    found = {wid: find_wire(project, wid) for wid in wanted}
    ops: list[Op] = []
    for hid in sorted({h.id for h, _w in found.values()}):
        h = project.harnesses[hid]
        edited = {wid for wid, (fh, _w) in found.items() if fh.id == hid}
        new_wires = [make(w) if w.id in edited else w for w in h.wires]
        if new_wires == h.wires:
            continue
        if h.status == "released":
            raise EditError(_released(h))
        ops.append(Put("harnesses", evolve(h, wires=new_wires)))
    return ops


def plan_wire_edit(
    project: Project, wire_ids: Iterable[str], changes: Mapping[str, object]
) -> list[Op]:
    """Ops that set `changes` ({field: value}, fields of `EDITABLE`) on each wire. Gauge, type,
    colour and length lock the wire against generation; an empty label or colour clears it."""
    unknown = sorted(set(changes) - set(EDITABLE) - set(ENDS))
    if unknown:
        raise EditError(
            f"A wire has no field '{unknown[0]}'; the fields are {', '.join(EDITABLE)}."
        )
    ids = list(wire_ids)
    ends = {k: v for k, v in changes.items() if k in ENDS}
    if ends:
        for wid in dict.fromkeys(ids):
            if not find_wire(project, wid)[1].manual:
                raise EditError(
                    f"The pins of wire {wid} follow its interface. Change the pin in the Devices "
                    "tab, or draw a wire of your own."
                )
        if len(set(ids)) > 1:
            raise EditError("The pins of several wires cannot be set in one step.")
    clean = {
        field: (value if field in ENDS else _clean(project, field, value))
        for field, value in changes.items()
    }
    ops = _apply(project, ids, Change(clean))
    if ends:
        _check_ends(project, ops, ids[0])
    return ops


class _Reset(Change):
    def __init__(self) -> None:
        super().__init__({})

    def __call__(self, w: Wire) -> Wire:
        return evolve(w, locked=False) if w.locked else w


def plan_wire_reset(project: Project, wire_ids: Iterable[str]) -> list[Op]:
    """Ops that unlock the wires, so the next generation gives them the gauge, type, colour and
    length of the design again. A label and a note stay."""
    return _apply(project, list(wire_ids), _Reset())


# ---- wires that a person draws -----------------------------------------------------------------


def pin_choices(project: Project, harness_id: str) -> dict[str, list[str]]:
    """The pins of each cable connector of a harness: {connector ID: [pin ID, ...]}."""
    h = project.harnesses.get(harness_id)
    if h is None:
        raise EditError(f"Harness '{harness_id}' does not exist.")
    return {c.id: [p.id for p in c.pins] for c in sorted(h.connectors, key=lambda c: c.id)}


def _check_end(h: Harness, connector_id: str, pin_id: str, what: str) -> None:
    conn = next((c for c in h.connectors if c.id == connector_id), None)
    if conn is None:
        raise EditError(f"{what}: '{connector_id}' is not a connector of {h.id}.")
    if pin_id not in {p.id for p in conn.pins}:
        raise EditError(f"{what}: connector {connector_id} has no pin '{pin_id}'.")


def _check_ends(project: Project, ops: list[Op], wire_id: str) -> None:
    """The ends of a wire after the ops are real pins of its harness, and not one pin twice."""
    h, _w = find_wire(project, wire_id)
    new = next((op.obj for op in ops if isinstance(op, Put) and isinstance(op.obj, Harness)), None)
    if new is None or new.id != h.id:
        return
    w = next(x for x in new.wires if x.id == wire_id)
    _check_end(new, w.from_connector, w.from_pin, "From")
    _check_end(new, w.to_connector, w.to_pin, "To")
    if (w.from_connector, w.from_pin) == (w.to_connector, w.to_pin):
        raise EditError("A wire cannot start and end on the same pin.")


def _used_ids(project: Project) -> set[str]:
    ids: set[str] = set(project.units) | set(project.interfaces) | set(project.connectors)
    ids |= set(project.parts) | set(project.harnesses)
    for h in project.harnesses.values():
        ids |= {c.id for c in h.connectors} | {w.id for w in h.wires}
        ids |= {s.id for s in h.shields} | {b.id for b in h.branch_points}
        ids |= {s.id for s in h.segments} | {s.id for s in h.splices}
    return ids


def new_wire_id(project: Project, harness_id: str) -> str:
    """The first free wire ID of the harness, named by the project's naming pattern."""
    from .generate.naming import namer_for

    namer = namer_for(project)
    taken = _used_ids(project)
    n = 1
    while namer.wire(harness_id, n) in taken:
        n += 1
    return namer.wire(harness_id, n)


def plan_add_wire(
    project: Project,
    harness_id: str,
    from_connector: str,
    from_pin: str,
    to_connector: str,
    to_pin: str,
    *,
    signal: str | None = None,
    **fields: object,
) -> list[Op]:
    """Ops that add a wire between two pins of the cable connectors of a harness. `fields` may hold
    gauge_awg, part_id, colour, length_m, label and note, which are checked like an edit. The wire
    is marked as yours; generation keeps it as it is."""
    h = project.harnesses.get(harness_id)
    if h is None:
        raise EditError(f"Harness '{harness_id}' does not exist.")
    if h.status == "released":
        raise EditError(_released(h))
    _check_end(h, from_connector, from_pin, "From")
    _check_end(h, to_connector, to_pin, "To")
    if (from_connector, from_pin) == (to_connector, to_pin):
        raise EditError("A wire cannot start and end on the same pin.")
    unknown = sorted(set(fields) - set(EDITABLE))
    if unknown:
        raise EditError(
            f"A wire has no field '{unknown[0]}'; the fields are {', '.join(EDITABLE)}."
        )
    clean = {k: _clean_new(project, k, v) for k, v in fields.items()}
    sig = signal.strip() if isinstance(signal, str) and signal.strip() else None
    try:
        wire = Wire(
            id=new_wire_id(project, harness_id),
            signal=sig,
            from_connector=from_connector,
            from_pin=from_pin,
            to_connector=to_connector,
            to_pin=to_pin,
            manual=True,
            **{k: v for k, v in clean.items() if v not in (None, "")},  # type: ignore[arg-type]
        )
    except ValidationError as exc:
        raise EditError(
            f"The wire is not valid: {exc.errors()[0].get('msg', 'not valid')}."
        ) from exc
    return [Put("harnesses", evolve(h, wires=[*h.wires, wire]))]


def _clean_new(project: Project, field: str, value: object) -> object:
    """Like `_clean`, but an empty value of a field the new wire does not need is just left out."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return _clean(project, field, value)


def plan_delete_wire(project: Project, wire_id: str) -> list[Op]:
    """Ops that delete a wire that a person drew. A generated wire is removed by changing the
    design (its interface), not here."""
    return plan_delete_wires(project, [wire_id])


def plan_delete_wires(project: Project, wire_ids: Iterable[str]) -> list[Op]:
    """Ops that delete several wires that a person drew, one `Put` for each harness."""
    ids = list(dict.fromkeys(wire_ids))
    if not ids:
        raise EditError("No wire is selected.")
    found = {wid: find_wire(project, wid) for wid in ids}
    for wid, (_h, w) in found.items():
        if not w.manual:
            raise EditError(
                f"Wire {wid} was generated from interface {w.interface_id or 'the design'}. "
                "Delete the interface, or change the pins in the Devices tab; Generate then "
                "drops it."
            )
    ops: list[Op] = []
    for hid in sorted({h.id for h, _w in found.values()}):
        h = project.harnesses[hid]
        if h.status == "released":
            raise EditError(_released(h))
        gone = {wid for wid, (fh, _w) in found.items() if fh.id == hid}
        shields = [
            evolve(s, wire_ids=[i for i in s.wire_ids if i not in gone])
            for s in h.shields
            if set(s.wire_ids) - gone
        ]
        ops.append(
            Put(
                "harnesses",
                evolve(h, wires=[x for x in h.wires if x.id not in gone], shields=shields),
            )
        )
    return ops
