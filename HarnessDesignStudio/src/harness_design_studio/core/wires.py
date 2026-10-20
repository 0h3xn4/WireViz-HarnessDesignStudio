"""Editing one wire: gauge, type, colour, length, label and note.

    ops = plan_wire_edit(project, ["W001-0001", "W001-0002"], {"gauge_awg": 22, "colour": "red"})
    ops = plan_wire_reset(project, ["W001-0001"])          # give the wire back to generation

Wires are generated, and generation puts them back the way the design says. A person's choice
stays when it is typed here: gauge, type, colour and length lock the wire (`Wire.locked`, which
generation honours); the label (text for the wire labels instead of the signal name) and the note
are always kept. A released harness cannot be edited; the plans say so in plain words before the
transaction would refuse them. Nothing here invents a value: a field is what the person typed.
"""

from collections.abc import Iterable, Mapping, Sequence

from pydantic import ValidationError

from .commands import Op, Put
from .edit import EditError
from .model import Harness, Project, Wire
from .model.base import evolve

EDITABLE: tuple[str, ...] = ("gauge_awg", "part_id", "colour", "length_m", "label", "note")
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
    unknown = sorted(set(changes) - set(EDITABLE))
    if unknown:
        raise EditError(
            f"A wire has no field '{unknown[0]}'; the fields are {', '.join(EDITABLE)}."
        )
    clean = {field: _clean(project, field, value) for field, value in changes.items()}
    return _apply(project, list(wire_ids), Change(clean))


class _Reset(Change):
    def __init__(self) -> None:
        super().__init__({})

    def __call__(self, w: Wire) -> Wire:
        return evolve(w, locked=False) if w.locked else w


def plan_wire_reset(project: Project, wire_ids: Iterable[str]) -> list[Op]:
    """Ops that unlock the wires, so the next generation gives them the gauge, type, colour and
    length of the design again. A label and a note stay."""
    return _apply(project, list(wire_ids), _Reset())
