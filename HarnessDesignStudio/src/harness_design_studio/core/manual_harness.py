"""A harness that a person builds from nothing: a new harness, its cable connectors and their pins.

    ops, hid = plan_new_harness(project, "Heater harness")
    ops, cid = plan_add_connector(project, hid, part_id="EX-DSUB-9-M")    # free-standing
    ops, cid = plan_add_connector(project, hid, mates_with="OBC1-J01")    # plugs into a unit
    ops = plan_set_pin(project, hid, cid, "3", function="HEATER +", termination="solder")
    ops = plan_delete_connector(project, hid, cid)

Generation makes a harness from interfaces. These plans make one without any: the wires between its
connectors are drawn with `wires.plan_add_wire`, and from there on it is a harness like any other
(checks, outputs, review, release). `Harness.generated` stays False, so Generate leaves it, its
connectors and its wires exactly as they are; a harness that Generate made keeps its connectors from
the design, and refuses a connector added here (Generate would replace it).

A cable connector made here either plugs into a connector of a unit (`mates_with`, which fills the
mating part, the opposite gender, the keying and the pins from the unit's connector, as Generate
does) or stands alone (a part of the library and its pins `1` to `N`, or the pins given). Nothing is
invented: a value that is not typed stays empty. The functions are pure; they return `Op`s that
`History.execute` runs as one undo step, or raise `EditError` with a plain sentence.
"""

from collections.abc import Sequence
from typing import get_args

from pydantic import TypeAdapter, ValidationError

from .commands import Op, Put
from .describe import part_gender
from .devices import check_contact_part, check_pin
from .edit import EditError
from .generate.naming import namer_for
from .model import Connector, Harness, Pin, Project, evolve
from .model.base import MAX_PIN_COUNT, Name
from .model.physical import Termination
from .wires import released_text, used_ids

ROLES: tuple[str, ...] = ("cable", "inline", "feedthrough", "test")
PIN_FIELDS: tuple[str, ...] = ("function", "termination", "contact_size", "contact_part")
_TERMINATIONS: tuple[str, ...] = get_args(Termination)
_NAME = TypeAdapter(Name)


def _text(value: object, what: str) -> str | None:
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


def _writable(project: Project) -> None:
    if project.read_only:
        raise EditError("This project is read-only (saved by a newer tool version). Use Save as.")


def _own(project: Project, harness_id: str) -> Harness:
    """The harness, if a person may change its connectors: it exists, is a draft or in review, and
    was not made by Generate."""
    h = project.harnesses.get(harness_id)
    if h is None:
        raise EditError(f"Harness '{harness_id}' does not exist.")
    if h.status == "released":
        raise EditError(released_text(h))
    if h.generated:
        raise EditError(
            f"{harness_id} is made by Generate, which gives it the connectors of the design. "
            "Add connectors to a harness you made with New harness."
        )
    return h


def plan_new_harness(
    project: Project, name: str, *, label: str | None = None
) -> tuple[list[Op], str]:
    """Ops that add an empty draft harness called `name`, and its ID: the first free one of the
    project's naming pattern (`W001`, `W002`, ...)."""
    _writable(project)
    title = _text(name, "A harness name")
    if title is None:
        raise EditError("A harness needs a name.")
    if any(h.name.casefold() == title.casefold() for h in project.harnesses.values()):
        raise EditError(f"A harness called '{title}' exists already; use another name.")
    namer = namer_for(project)
    taken = used_ids(project)
    n = 1
    while namer.harness(n) in taken:
        n += 1
    hid = namer.harness(n)
    h = Harness(id=hid, name=title, generated=False, label=_text(label, "The label"))
    return [Put("harnesses", h)], hid


def _pin_ids(count: int | None, given: Sequence[str] | None, limit: int) -> list[str]:
    if given is None:
        return [str(i) for i in range(1, (count or 0) + 1)]
    ids = [check_pin(p) for p in given]
    seen: set[str] = set()
    for pid in ids:
        if pid.casefold() in seen:
            raise EditError(f"The pin '{pid}' is listed twice.")
        seen.add(pid.casefold())
    if len(ids) > limit:
        raise EditError(f"The part has {limit} pins; {len(ids)} were given.")
    return ids


def plan_add_connector(
    project: Project,
    harness_id: str,
    *,
    part_id: str | None = None,
    mates_with: str | None = None,
    role: str = "cable",
    name: str | None = None,
    pin_ids: Sequence[str] | None = None,
    label: str | None = None,
) -> tuple[list[Op], str]:
    """Ops that add a cable connector to a harness that a person made, and its ID (the project's
    naming pattern: `W001-P1`, `W001-P2`, ...).

    With `mates_with` (a connector of a unit) the connector plugs into it: its part is the mating
    part of the library (else the same part), its gender is the opposite, and its keying and pins
    are those of the unit's connector, unless `part_id` or `pin_ids` say otherwise. Without it,
    `part_id` (a connector part of the library) is needed; the pins are `1` to the part's pin count,
    or `pin_ids`. `role` is cable, inline, feedthrough or test."""
    _writable(project)
    h = _own(project, harness_id)
    if role not in ROLES:
        raise EditError(f"A connector role is one of {', '.join(ROLES)}.")
    box: Connector | None = None
    if mates_with is not None:
        if role != "cable":
            raise EditError("Only a cable connector plugs into the connector of a device.")
        box = project.connectors.get(mates_with)
        if box is None or box.role != "box":
            raise EditError(f"'{mates_with}' is not a connector of a device.")
        if any(c.mates_with == mates_with for c in h.connectors):
            raise EditError(f"{harness_id} has a connector for {mates_with} already.")
        box_part = project.parts.get(box.part_id)
        if part_id is None:
            declared = box_part.mates_with if box_part is not None else None
            part_id = declared if declared in project.parts else box.part_id
    if part_id is None:
        raise EditError("Choose the connector part, or the connector of a device it plugs into.")
    part = project.parts.get(part_id)
    if part is None or part.category != "connector":
        raise EditError(f"'{part_id}' is not a connector part in the library.")
    limit = part.pin_count or MAX_PIN_COUNT
    if pin_ids is None and box is not None:
        pins = [
            Pin(
                id=p.id,
                contact_size=p.contact_size,
                termination=p.termination,
                function=p.function,
                contact_part=p.contact_part,
            )
            for p in box.pins
        ]
    else:
        pins = [Pin(id=i) for i in _pin_ids(part.pin_count, pin_ids, limit)]
    if len(pins) > limit:
        raise EditError(f"{part_id} has {limit} pins; the connector would have {len(pins)}.")
    namer = namer_for(project)
    taken = used_ids(project)
    n = 1
    while namer.cable_connector(harness_id, n) in taken:
        n += 1
    cid = namer.cable_connector(harness_id, n)
    cname = _text(name, "A connector name") or cid.rsplit("-", 1)[-1]
    if any(c.name.casefold() == cname.casefold() for c in h.connectors):
        raise EditError(f"{harness_id} has a connector called '{cname}' already.")
    gender = "unspecified"
    keying = None
    if box is not None:
        own = part_gender(part)
        opposite = {"male": "female", "female": "male"}
        gender = (
            opposite.get(box.gender, "unspecified")
            if box.gender != "unspecified"
            else opposite.get(part_gender(project.parts.get(box.part_id)), own)
        )
        keying = box.keying
    else:
        gender = part_gender(part)
    connector = Connector(
        id=cid,
        name=cname,
        role=role,  # type: ignore[arg-type]
        part_id=part_id,
        gender=gender,  # type: ignore[arg-type]
        keying=keying,
        mates_with=mates_with,
        label=_text(label, "The label"),
        pins=pins,
    )
    return [Put("harnesses", evolve(h, connectors=[*h.connectors, connector]))], cid


def plan_delete_connector(project: Project, harness_id: str, connector_id: str) -> list[Op]:
    """Ops that remove a cable connector of a harness that a person made. A connector with wires
    cannot go: the plan names them, so they are deleted or moved first."""
    _writable(project)
    h = _own(project, harness_id)
    if not any(c.id == connector_id for c in h.connectors):
        raise EditError(f"'{connector_id}' is not a connector of {harness_id}.")
    wires = sorted(w.id for w in h.wires if connector_id in (w.from_connector, w.to_connector))
    if wires:
        shown = ", ".join(wires[:4]) + (f" and {len(wires) - 4} more" if len(wires) > 4 else "")
        raise EditError(
            f"{connector_id} has wires ({shown}). Delete them, or move their ends, first."
        )
    return [
        Put(
            "harnesses",
            evolve(h, connectors=[c for c in h.connectors if c.id != connector_id]),
        )
    ]


def plan_set_pin(
    project: Project, harness_id: str, connector_id: str, pin_id: str, **changes: object
) -> list[Op]:
    """Ops that set the function, termination (crimp, solder or unspecified), contact size or
    contact part (a contact part of the library) of a pin of a cable connector of a harness that a
    person made. Empty text clears a value."""
    _writable(project)
    h = _own(project, harness_id)
    conn = next((c for c in h.connectors if c.id == connector_id), None)
    if conn is None:
        raise EditError(f"'{connector_id}' is not a connector of {harness_id}.")
    unknown = sorted(set(changes) - set(PIN_FIELDS))
    if unknown:
        raise EditError(
            f"A pin has no field '{unknown[0]}' to set here; use {', '.join(PIN_FIELDS)}."
        )
    if not any(p.id == pin_id for p in conn.pins):
        raise EditError(f"{connector_id} has no pin '{pin_id}'.")
    clean: dict[str, object] = {}
    for key, value in changes.items():
        if key == "termination":
            if value not in _TERMINATIONS:
                raise EditError(f"A termination is one of {', '.join(_TERMINATIONS)}.")
            clean[key] = value
        elif key == "contact_part":
            clean[key] = check_contact_part(project, value)
        else:
            clean[key] = _text(value, "The function" if key == "function" else "The contact size")
    pins = [evolve(p, **clean) if p.id == pin_id else p for p in conn.pins]
    new = evolve(conn, pins=pins)
    return [
        Put(
            "harnesses",
            evolve(h, connectors=[new if c.id == connector_id else c for c in h.connectors]),
        )
    ]


def is_own(project: Project, harness_id: str) -> bool:
    """True when the harness was made by a person (not by Generate) and may take connectors."""
    h = project.harnesses.get(harness_id)
    return h is not None and not h.generated and h.status != "released"


__all__ = [
    "PIN_FIELDS",
    "ROLES",
    "is_own",
    "plan_add_connector",
    "plan_delete_connector",
    "plan_new_harness",
    "plan_set_pin",
]
