"""The build data a technician needs: strip lengths, contacts, accessories and crimp tools.

    ops = plan_set_strip(project, "W001", ["W001-0001"], strip_a_mm=6, strip_b_mm=None)
    ops = plan_set_strip_all(project, "W001", strip_a_mm=6, strip_b_mm=6)
    ops = plan_set_contacts(project, "W010", "W010-P1", ["1", "2"], "EX-CONTACT-22")
    ops = plan_set_accessory(project, "W001", Accessory(id="ACC-001", kind="sleeving", ...))
    ops = plan_delete_accessory(project, "W001", "ACC-001")
    ops = plan_set_part_tool(project, "EX-CONTACT-22", "Crimp tool X, setting 4")

All of it is optional and a person's: the strip length at each end of a wire (`Wire.strip_a_mm`,
`strip_b_mm`), the contact part on a pin of a cable connector (`Pin.contact_part`), the crimp tool
of a contact part (`Part.tool`) and the accessories of a harness (`Harness.accessories`: sleeving,
heat shrink, labels, backshells, with what they sit on, where and how much). Nothing is computed
from them and nothing here invents a value; the tool does not check that a contact fits a pin or
that a strip length is sensible.

Generation keeps what is entered here: strip lengths like a wire's label and note (they do not lock
the wire), the accessories whose connector or wire still exists, and it copies a unit pin's contact
to the cable pin. So the contact of a pin of a generated harness is set on the unit's pin (Devices
tab, `devices.ops_set_pin`), and `plan_set_contacts` is for a harness that a person made. The
functions are pure: they return `Op`s that `History.execute` runs as one undo step, or raise
`EditError` with a plain sentence. A released harness cannot be edited; the plans say so first.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Final, get_args

from pydantic import TypeAdapter, ValidationError

from .commands import Op, Put
from .devices import check_contact_part
from .edit import EditError
from .model import Accessory, Harness, Part, Project, Wire, evolve
from .model.base import MAX_LENGTH_MM, Name, Text
from .model.physical import AccessoryKind
from .wires import released_text

ACCESSORY_KINDS: tuple[str, ...] = get_args(AccessoryKind)
MAX_QUANTITY: Final = 9999
_NAME = TypeAdapter(Name)
_TEXT = TypeAdapter(Text)


class _Unset:
    """The value of a keyword that was not given (None means: clear the value)."""

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = _Unset()
Strip = float | int | str | None | _Unset


# ---- small helpers -----------------------------------------------------------------------------


def _writable(project: Project) -> None:
    if project.read_only:
        raise EditError("This project is read-only (saved by a newer tool version). Use Save as.")


def _harness(project: Project, harness_id: str) -> Harness:
    """The harness, if a person may change it: it exists and is a draft or in review."""
    _writable(project)
    h = project.harnesses.get(harness_id)
    if h is None:
        raise EditError(f"Harness '{harness_id}' does not exist.")
    if h.status == "released":
        raise EditError(released_text(h))
    return h


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


def _note(value: object) -> str:
    """The note of an accessory: free text like the note of a wire (up to 5,000 characters, no
    control characters), may be empty."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise EditError("The note must be text.")
    try:
        return _TEXT.validate_python(value.strip(), strict=True)
    except ValidationError as exc:
        raise EditError(
            "The note can have up to 5000 characters and no control characters."
        ) from exc


def _mm(value: object, what: str) -> float | None:
    """A length in millimetres from a number or a text (a decimal comma is read); empty is None.
    0 to 100,000, as a guard against a typing slip, not as a design limit."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            raise EditError(f"{what} must be a number of millimetres, for example 6.") from None
    elif isinstance(value, bool) or not isinstance(value, int | float):
        raise EditError(f"{what} must be a number of millimetres, for example 6.")
    else:
        number = float(value)
    if not 0 <= number <= MAX_LENGTH_MM:
        raise EditError(f"{what} must be between 0 and {MAX_LENGTH_MM:,.0f} mm.")
    return number


# ---- strip lengths -----------------------------------------------------------------------------


def _strip_changes(strip_a_mm: Strip, strip_b_mm: Strip) -> dict[str, float | None]:
    changes: dict[str, float | None] = {}
    if not isinstance(strip_a_mm, _Unset):
        changes["strip_a_mm"] = _mm(strip_a_mm, "The strip length at the From end")
    if not isinstance(strip_b_mm, _Unset):
        changes["strip_b_mm"] = _mm(strip_b_mm, "The strip length at the To end")
    if not changes:
        raise EditError("Give a strip length for the From end, the To end or both (empty clears).")
    return changes


def plan_set_strip(
    project: Project,
    harness_id: str,
    wire_ids: Iterable[str],
    *,
    strip_a_mm: Strip = UNSET,
    strip_b_mm: Strip = UNSET,
) -> list[Op]:
    """Ops that set the strip length (mm) at the From end (`strip_a_mm`) and the To end
    (`strip_b_mm`) of the listed wires of a harness; None or an empty text clears an end, a value
    not given stays. The wire is not locked against generation: like a note, the length is kept."""
    h = _harness(project, harness_id)
    changes = _strip_changes(strip_a_mm, strip_b_mm)
    wanted = list(dict.fromkeys(wire_ids))
    if not wanted:
        raise EditError("No wire is selected.")
    have = {w.id for w in h.wires}
    for wid in wanted:
        if wid not in have:
            raise EditError(f"'{wid}' is not a wire of {harness_id}.")
    chosen = set(wanted)

    def make(w: Wire) -> Wire:
        new = {k: v for k, v in changes.items() if getattr(w, k) != v}
        return evolve(w, **new) if new else w

    wires = [make(w) if w.id in chosen else w for w in h.wires]
    return [Put("harnesses", evolve(h, wires=wires))] if wires != h.wires else []


def plan_set_strip_all(
    project: Project,
    harness_id: str,
    *,
    strip_a_mm: Strip = UNSET,
    strip_b_mm: Strip = UNSET,
) -> list[Op]:
    """`plan_set_strip` for every wire of the harness (the same length on all of them)."""
    h = _harness(project, harness_id)
    if not h.wires:
        raise EditError(f"{harness_id} has no wires.")
    return plan_set_strip(
        project, harness_id, [w.id for w in h.wires], strip_a_mm=strip_a_mm, strip_b_mm=strip_b_mm
    )


# ---- contacts and crimp tools ------------------------------------------------------------------


def plan_set_contacts(
    project: Project,
    harness_id: str,
    connector_id: str,
    pin_ids: Sequence[str] | None,
    contact_part: str | None,
) -> list[Op]:
    """Ops that set the contact part (a part of category contact; None or empty clears it) on the
    pins `pin_ids` of a cable connector of a harness that a person made, or on all its pins when
    `pin_ids` is None. A harness that Generate made takes the contact from the unit's pin."""
    h = _harness(project, harness_id)
    if h.generated:
        raise EditError(
            f"{harness_id} is made by Generate, which copies the contact from the pin of the "
            "unit. Set it on the unit's pin in the Devices tab (column Cable contact), then "
            "Generate again."
        )
    conn = next((c for c in h.connectors if c.id == connector_id), None)
    if conn is None:
        raise EditError(f"'{connector_id}' is not a connector of {harness_id}.")
    part = check_contact_part(project, contact_part)
    if pin_ids is None:
        wanted = [p.id for p in conn.pins]
    else:
        wanted = list(dict.fromkeys(pin_ids))
        have = {p.id for p in conn.pins}
        for pid in wanted:
            if pid not in have:
                raise EditError(f"{connector_id} has no pin '{pid}'.")
    if not wanted:
        raise EditError(f"{connector_id} has no pins.")
    pins = [
        evolve(p, contact_part=part) if p.id in wanted and p.contact_part != part else p
        for p in conn.pins
    ]
    if pins == conn.pins:
        return []
    new = evolve(conn, pins=pins)
    return [
        Put(
            "harnesses",
            evolve(h, connectors=[new if c.id == connector_id else c for c in h.connectors]),
        )
    ]


def _released_users(project: Project, part_id: str) -> list[str]:
    """Released harnesses that use the part as the contact of a pin or in an accessory."""
    return sorted(
        h.id
        for h in project.harnesses.values()
        if h.status == "released"
        and (
            any(p.contact_part == part_id for c in h.connectors for p in c.pins)
            or any(a.part_id == part_id for a in h.accessories)
        )
    )


def plan_set_part_tool(project: Project, part_id: str, tool: str | None) -> list[Op]:
    """Ops that set the crimp tool (or its setting, free text) of a contact part; None or an empty
    text clears it. It is refused while a released harness uses the part."""
    _writable(project)
    part: Part | None = project.parts.get(part_id)
    if part is None:
        raise EditError(f"Part '{part_id}' does not exist.")
    if part.category != "contact":
        raise EditError(f"{part_id} is not a contact part, so it has no crimp tool.")
    text = _text(tool, "The tool")
    users = _released_users(project, part_id)
    if text != part.tool and users:
        raise EditError(
            f"Part {part_id} is used by {users[0]}, which is released; start a new revision "
            "of it to change the tool."
        )
    return [Put("parts", evolve(part, tool=text))] if text != part.tool else []


# ---- accessories -------------------------------------------------------------------------------


def plan_next_accessory_id(h: Harness) -> str:
    """The first free accessory ID of the harness: `ACC-001`, `ACC-002`, ..."""
    taken = {a.id for a in h.accessories}
    n = 1
    while f"ACC-{n:03d}" in taken:
        n += 1
    return f"ACC-{n:03d}"


def check_accessory(
    project: Project, harness_id: str, given: Accessory | Mapping[str, object]
) -> Accessory:
    """The accessory of a harness as the model wants it (texts trimmed, an empty cell as None,
    numbers read from text), or an EditError that says what is wrong."""
    h = _harness(project, harness_id)
    data = given.model_dump() if isinstance(given, Accessory) else dict(given)
    unknown = sorted(set(data) - set(Accessory.model_fields))
    if unknown:
        raise EditError(
            f"An accessory has no field '{unknown[0]}'; the fields are "
            f"{', '.join(Accessory.model_fields)}."
        )
    aid = _text(data.get("id"), "The accessory ID")
    if aid is None:
        raise EditError("An accessory needs an ID, for example ACC-001.")
    kind = data.get("kind")
    if kind not in ACCESSORY_KINDS:
        raise EditError(f"An accessory kind is one of {', '.join(ACCESSORY_KINDS)}.")
    target = _text(data.get("target"), "The target")
    if target is not None and target not in {c.id for c in h.connectors} | {w.id for w in h.wires}:
        raise EditError(f"'{target}' is not a connector or a wire of {h.id}.")
    part_id = _text(data.get("part_id"), "The part")
    if part_id is not None and part_id not in project.parts:
        raise EditError(f"'{part_id}' is not a part of the library.")
    quantity = data.get("quantity", 1)
    if isinstance(quantity, str):
        quantity = quantity.strip() or 1
        if isinstance(quantity, str) and not quantity.isdigit():
            raise EditError(f"The quantity must be a whole number from 1 to {MAX_QUANTITY}.")
        quantity = int(quantity)
    if (
        isinstance(quantity, bool)
        or not isinstance(quantity, int)
        or not 1 <= quantity <= MAX_QUANTITY
    ):
        raise EditError(f"The quantity must be a whole number from 1 to {MAX_QUANTITY}.")
    try:
        return Accessory(
            id=aid,
            kind=kind,  # type: ignore[arg-type]
            part_id=part_id,
            target=target,
            position=_text(data.get("position"), "The position"),
            length_mm=_mm(data.get("length_mm"), "The length"),
            quantity=quantity,
            note=_note(data.get("note")),
        )
    except ValidationError as exc:
        why = str(exc.errors()[0].get("msg", "not valid")).removeprefix("Value error, ")
        raise EditError(f"The accessory is not valid: {why}.") from exc


def plan_set_accessory(
    project: Project, harness_id: str, accessory: Accessory | Mapping[str, object]
) -> list[Op]:
    """Ops that add an accessory to a harness, or replace the one with the same ID. The target is a
    connector or a wire of the harness (None: the harness itself), the part (if any) is in the
    library, the length is 0 to 100,000 mm and the quantity 1 to 9,999. A mapping with the fields
    of `Accessory` is checked like an `Accessory`. The list stays sorted by ID, as it is saved."""
    h = _harness(project, harness_id)
    new = check_accessory(project, harness_id, accessory)
    others = [a for a in h.accessories if a.id != new.id]
    accessories = sorted([*others, new], key=lambda a: a.id)
    return (
        [Put("harnesses", evolve(h, accessories=accessories))]
        if accessories != h.accessories
        else []
    )


def plan_delete_accessory(project: Project, harness_id: str, accessory_id: str) -> list[Op]:
    """Ops that remove an accessory from a harness."""
    h = _harness(project, harness_id)
    if not any(a.id == accessory_id for a in h.accessories):
        raise EditError(f"'{accessory_id}' is not an accessory of {harness_id}.")
    return [
        Put("harnesses", evolve(h, accessories=[a for a in h.accessories if a.id != accessory_id]))
    ]


__all__ = [
    "ACCESSORY_KINDS",
    "UNSET",
    "check_accessory",
    "plan_delete_accessory",
    "plan_next_accessory_id",
    "plan_set_accessory",
    "plan_set_contacts",
    "plan_set_part_tool",
    "plan_set_strip",
    "plan_set_strip_all",
]
