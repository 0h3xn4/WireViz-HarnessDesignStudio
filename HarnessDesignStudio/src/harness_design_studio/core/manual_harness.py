"""A harness that a person builds from nothing: a new harness, its cable connectors and their pins.

    ops, hid = plan_new_harness(project, "Heater harness")
    ops, cid = plan_add_connector(project, hid, part_id="EX-DSUB-9-M")    # free-standing
    ops, cid = plan_add_connector(project, hid, mates_with="OBC1-J01")    # plugs into a unit
    ops = plan_set_pin(project, hid, cid, "3", function="HEATER +", termination="solder")
    ops = plan_delete_connector(project, hid, cid)
    made = plan_cable_from_port(project, "OBC1-J01")               # a cable with a loose end
    ops = plan_plug_loose_end(project, made.harness_id, made.loose_id, "RW1-J02")  # decide it
    ops = plan_unplug(project, made.harness_id, made.loose_id)     # loose again

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

A loose end (M4, D-201) is the end of a cable that is not on a connector yet: a connector of the
harness with the role `loose`, pins that wires attach to, no `mates_with`, and the library part
`TBD-CONNECTOR`, which the plans add to the project on first use. Plugging it into a port or giving
it a connector part decides it (role `cable`); unplugging a connector makes it loose again.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import get_args

from pydantic import TypeAdapter, ValidationError

from .commands import Op, Put, apply_ops
from .describe import part_gender
from .devices import check_contact_part, check_pin, connector_part
from .edit import EditError, clone_with
from .generate.naming import namer_for
from .model import Connector, Harness, Part, Pin, PinPair, Project, evolve
from .model.base import MAX_PIN_COUNT, Name
from .model.physical import LOOSE_ROLE, TBD_PART_ID, Termination
from .origin import harness_link
from .wires import plan_add_wires, released_text, used_ids

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
    part = connector_part(project, part_id)
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


# ---- the loose end (M4a, D-200, D-201) ---------------------------------------------------------
# A loose end is an ordinary Connector of the harness with the role `loose`, pins that wires attach
# to, no `mates_with`, and the library part TBD-CONNECTOR. Every consumer of `from_connector` /
# `to_connector` therefore sees a connector like any other. It is a connector a person has not
# decided yet: plugging it into a port or giving it a connector part decides it (role `cable`).

LOOSE = LOOSE_ROLE


def tbd_part() -> Part:
    """The library part a loose end stands on until a person chooses: a connector part, approval
    pending, unverified, with no pin count and no mass (nothing is invented). It is not a part
    anyone buys or approves: the pickers do not list it (`devices.connector_parts_to_choose`) and
    the checks word it as a choice not made yet."""
    return Part(
        id=TBD_PART_ID,
        category="connector",
        description="Connector not chosen yet (loose end)",
        approval="pending",
        unverified=True,
    )


def _tbd_ops(project: Project) -> list[Op]:
    """The op that adds the TBD part when the project has none (it is added on first use and put
    back when a person has taken it away)."""
    return [] if TBD_PART_ID in project.parts else [Put("parts", tbd_part())]


def loose_ends(h: Harness) -> list[Connector]:
    """The loose ends of a harness, by ID."""
    return sorted((c for c in h.connectors if c.role == LOOSE), key=lambda c: c.id)


def _next_connector_id(project: Project, harness_id: str) -> str:
    namer = namer_for(project)
    taken = used_ids(project)
    n = 1
    while namer.cable_connector(harness_id, n) in taken:
        n += 1
    return namer.cable_connector(harness_id, n)


def plan_add_loose_end(
    project: Project,
    harness_id: str,
    *,
    pin_ids: Sequence[str],
    signals: dict[str, str] | None = None,
    name: str | None = None,
    label: str | None = None,
) -> tuple[list[Op], str]:
    """Ops that add a loose end to a harness a person made, with the pins `pin_ids` (and the signal
    names in `signals`, pin -> signal, which the plug later pairs by), and its ID. The library part
    TBD-CONNECTOR is added to the project on first use."""
    _writable(project)
    h = _own(project, harness_id)
    ids = _pin_ids(None, list(pin_ids), MAX_PIN_COUNT)
    if not ids:
        raise EditError("A loose end needs at least one pin.")
    cid = _next_connector_id(project, harness_id)
    cname = _text(name, "A connector name") or cid.rsplit("-", 1)[-1]
    if any(c.name.casefold() == cname.casefold() for c in h.connectors):
        raise EditError(f"{harness_id} has a connector called '{cname}' already.")
    sigs = signals or {}
    conn = Connector(
        id=cid,
        name=cname,
        role=LOOSE,
        part_id=TBD_PART_ID,
        label=_text(label, "The label"),
        pins=[Pin(id=i, signal=_text(sigs.get(i), "A signal name")) for i in ids],
    )
    return [*_tbd_ops(project), Put("harnesses", evolve(h, connectors=[*h.connectors, conn]))], cid


@dataclass(frozen=True)
class CableFromPort:
    """The result of `plan_cable_from_port`: the ops and the IDs they make."""

    ops: list[Op]
    harness_id: str
    near_id: str  # the cable connector that plugs into the port
    loose_id: str  # the loose end


def plan_cable_from_port(
    project: Project,
    box_connector_id: str,
    *,
    name: str | None = None,
    pin_ids: Iterable[str] | None = None,
) -> CableFromPort:
    """Ops that make a new harness (a person's: its origin is `drawn`) holding a cable with one end
    plugged into a port (a connector of a device) and the other end loose: what the diagram does
    when a cable is dragged from a port and dropped on empty ground. One wire runs from each of the
    port's pins `pin_ids` (default: the pins that have a signal, else all of them) to the same pin
    number of the loose end, which carries the port pin's signal name. Nothing else is invented."""
    _writable(project)
    box = project.connectors.get(box_connector_id)
    if box is None or box.role != "box":
        raise EditError(f"'{box_connector_id}' is not a connector of a device.")
    chosen = list(pin_ids) if pin_ids is not None else [p.id for p in box.pins if p.signal]
    if pin_ids is None and not chosen:
        chosen = [p.id for p in box.pins]
    have = {p.id for p in box.pins}
    for pid in chosen:
        if pid not in have:
            raise EditError(f"{box_connector_id} has no pin '{pid}'.")
    if not chosen:
        raise EditError(f"{box_connector_id} has no pins to run a cable from.")
    title = name
    if title is None:
        n = 1
        while any(h.name.casefold() == f"cable {n}".casefold() for h in project.harnesses.values()):
            n += 1
        title = f"Cable {n}"
    scratch = clone_with(project, [])  # the later steps need the IDs the earlier ones make
    ops_h, hid = plan_new_harness(scratch, title)
    apply_ops(scratch, ops_h)
    ops_n, near = plan_add_connector(scratch, hid, mates_with=box_connector_id)
    apply_ops(scratch, ops_n)
    sigs = {p.id: p.signal for p in box.pins if p.signal and p.id in chosen}
    ops_l, loose = plan_add_loose_end(scratch, hid, pin_ids=chosen, signals=sigs)
    apply_ops(scratch, ops_l)
    ops_w = plan_add_wires(scratch, hid, [(near, pid, loose, pid, sigs.get(pid)) for pid in chosen])
    apply_ops(scratch, ops_w)
    return CableFromPort(
        [*_tbd_ops(project), Put("harnesses", scratch.harnesses[hid])], hid, near, loose
    )


@dataclass(frozen=True)
class PlugProposal:
    """How the pins of a loose end would meet the pins of a port. `by` is `signal`, `number` or
    `none`; `pairs` are (pin of the loose end, pin of the port). `disagreements` name the pairs
    met by number whose signal names disagree (a plug refuses them unless a person pairs the
    pins)."""

    pairs: tuple[PinPair, ...]
    by: str
    unpaired_loose: tuple[str, ...]
    unpaired_port: tuple[str, ...]
    notes: tuple[str, ...]
    disagreements: tuple[str, ...] = ()


def _loose_and_port(
    project: Project, harness_id: str, loose_id: str, box_id: str
) -> tuple[Harness, Connector, Connector]:
    h = _own(project, harness_id)
    loose = next((c for c in h.connectors if c.id == loose_id), None)
    if loose is None:
        raise EditError(f"'{loose_id}' is not a connector of {harness_id}.")
    if loose.role != LOOSE:
        raise EditError(f"{loose_id} is not a loose end.")
    box = project.connectors.get(box_id)
    if box is None or box.role != "box":
        raise EditError(f"'{box_id}' is not a connector of a device.")
    if any(c.mates_with == box_id for c in h.connectors):
        raise EditError(f"{harness_id} has a connector for {box_id} already.")
    return h, loose, box


def propose_plug(project: Project, harness_id: str, loose_id: str, box_id: str) -> PlugProposal:
    """Pair the pins of a loose end with the pins of a port: by signal name (the logic of
    `links.propose_pairs`, TX to RX included), else by pin number (`pairing.pair_by_number`), else
    not at all. A pair met by number whose two pins carry different names is named in
    `disagreements`. It only proposes; `plan_plug_loose_end` does the work."""
    from .links import counterparts_of, name_relation, propose_pairs_between
    from .pairing import pair_by_number_between

    _h, loose, box = _loose_and_port(project, harness_id, loose_id, box_id)
    by = "signal"
    prop = propose_pairs_between(project, loose, box)
    if not prop.pairs:
        prop = pair_by_number_between(project, loose, box)
        by = "number" if prop.pairs else "none"
    notes = list(prop.notes)
    disagreements: list[str] = []
    if by == "number":  # met by number only: say where the names disagree
        table = counterparts_of(project)
        lp = {p.id: p for p in loose.pins}
        bp = {p.id: p for p in box.pins}
        for pair in prop.pairs:
            a, b = lp[pair.a_pin].signal, bp[pair.b_pin].signal
            if a and b and not name_relation(a, b, table):
                disagreements.append(
                    f"Pin {pair.a_pin} of {loose.id} carries {a}, but pin {pair.b_pin} of "
                    f"{box.id} is named {b}."
                )
    notes.extend(disagreements)
    return PlugProposal(
        prop.pairs, by, prop.unpaired_a, prop.unpaired_b, tuple(notes), tuple(disagreements)
    )


def plan_plug_loose_end(
    project: Project,
    harness_id: str,
    loose_id: str,
    box_id: str,
    pairs: Iterable[tuple[str, str]] | None = None,
) -> list[Op]:
    """Ops that plug a loose end into a port. The connector keeps its ID; it becomes a cable
    connector with `mates_with` = the port, the mating part (unless a person had chosen a part), the
    opposite gender and the keying of the port, and the pins of the port. The wires follow their
    pins: a pin paired with a port pin takes that pin's number (and the wires with it); a pin with
    no partner keeps its number and its wires, and the plan refuses when that number is taken by
    another pin.

    `pairs` (loose pin, port pin) default to `propose_plug`: by signal name, else by pin number; a
    pin the proposal leaves over meets the free port pin of its own number when their names do not
    differ (so an end unplugged and plugged in again keeps its spare pins). The plan refuses,
    with the reason, to plug by number where the two pins carry different names, and to plug when
    no pin can be paired; pair the pins yourself (`pairs`) to override that."""
    _writable(project)
    h, loose, box = _loose_and_port(project, harness_id, loose_id, box_id)
    if pairs is None:
        prop = propose_plug(project, harness_id, loose_id, box_id)
        if prop.disagreements:
            raise EditError(
                " ".join(prop.disagreements)
                + " They would be met by number only. Pair the pins yourself, or change a name."
            )
        if not prop.pairs:
            raise EditError(
                f"No pin of {loose_id} can be paired with a free pin of {box_id}, by name or by "
                "number. Pair the pins yourself."
            )
        chosen = [(p.a_pin, p.b_pin) for p in prop.pairs]
    else:
        chosen = list(pairs)
    loose_pins = {p.id: p for p in loose.pins}
    box_pins = {p.id: p for p in box.pins}
    mapping: dict[str, str] = {}
    for lp, bp in chosen:
        if lp not in loose_pins:
            raise EditError(f"{loose_id} has no pin '{lp}'.")
        if bp not in box_pins:
            raise EditError(f"{box_id} has no pin '{bp}'.")
        if lp in mapping or bp in mapping.values():
            raise EditError("A pin can be in one pair only.")
        mapping[lp] = bp
    if pairs is None:
        # a pin left over by the proposal meets the port pin of the same number when that one is
        # free and the two names do not differ (an end that was plugged in and unplugged again
        # has every pin of the port, the spare ones too: M4c)
        claimed = set(mapping.values())
        for pin in loose.pins:
            port_pin = box_pins.get(pin.id)
            if pin.id in mapping or port_pin is None or pin.id in claimed:
                continue
            if pin.signal and port_pin.signal and pin.signal != port_pin.signal:
                continue
            mapping[pin.id] = pin.id
            claimed.add(pin.id)
    new_pins: list[Pin] = []
    for port_pin in box.pins:  # every position of the port, as plan_add_connector does
        src = next((lp for lp, b in mapping.items() if b == port_pin.id), None)
        keep = loose_pins[src] if src is not None else None
        new_pins.append(
            Pin(
                id=port_pin.id,
                signal=keep.signal if keep else None,
                contact_size=port_pin.contact_size,
                termination=port_pin.termination,
                function=(keep.function if keep and keep.function else port_pin.function),
                contact_part=port_pin.contact_part,
            )
        )
    taken = {p.id for p in new_pins}
    for pin in loose.pins:
        if pin.id in mapping:
            continue
        if pin.id in taken:
            raise EditError(
                f"Pin {pin.id} of {loose_id} has no partner on {box_id}, and {box_id} has a pin "
                f"{pin.id} that another pin takes. Pair it, or renumber it first."
            )
        mapping[pin.id] = pin.id
        taken.add(pin.id)
        new_pins.append(pin)
    box_part = project.parts.get(box.part_id)
    part_id = loose.part_id
    if part_id == TBD_PART_ID:
        declared = box_part.mates_with if box_part is not None else None
        part_id = declared if declared in project.parts else box.part_id
    part = project.parts.get(part_id)
    limit = (part.pin_count if part is not None else None) or MAX_PIN_COUNT
    if len(new_pins) > limit:
        raise EditError(f"{part_id} has {limit} pins; the connector would have {len(new_pins)}.")
    own = part_gender(part) if part is not None else "unspecified"
    opposite = {"male": "female", "female": "male"}
    gender = (
        opposite.get(box.gender, "unspecified")
        if box.gender != "unspecified"
        else opposite.get(part_gender(box_part), own)
    )
    plugged = evolve(
        loose,
        role="cable",
        part_id=part_id,
        gender=gender,
        keying=box.keying,
        mates_with=box_id,
        pins=new_pins,
    )
    wires = [
        evolve(
            w,
            from_pin=mapping.get(w.from_pin, w.from_pin)
            if w.from_connector == loose_id
            else w.from_pin,
            to_pin=mapping.get(w.to_pin, w.to_pin) if w.to_connector == loose_id else w.to_pin,
        )
        for w in h.wires
    ]
    return [
        Put(
            "harnesses",
            evolve(
                h,
                connectors=[plugged if c.id == loose_id else c for c in h.connectors],
                wires=wires,
            ),
        )
    ]


def plan_unplug(project: Project, harness_id: str, connector_id: str) -> list[Op]:
    """Ops that turn a plugged cable connector back into a loose end: `mates_with` is cleared, the
    pins and the wires stay, the role is `loose` and the part goes back to TBD-CONNECTOR (gender and
    keying go back to unspecified: the person chooses the part again when the end is decided).

    A harness made from a connection (a Link names it) keeps both its ends plugged into the two
    devices of the connection, so it refuses; delete the connection, or the harness, instead."""
    _writable(project)
    h = _own(project, harness_id)
    c = next((x for x in h.connectors if x.id == connector_id), None)
    if c is None:
        raise EditError(f"'{connector_id}' is not a connector of {harness_id}.")
    if c.mates_with is None:
        raise EditError(f"{connector_id} is not plugged into a device.")
    made_from = harness_link(project, harness_id)
    if made_from is not None:
        raise EditError(
            f"{harness_id} was made from the connection {made_from}, so both of its ends stay "
            f"plugged into the two devices. Delete the connection {made_from}, or draw a new "
            "cable from a port."
        )
    loose = evolve(
        c, role=LOOSE, mates_with=None, part_id=TBD_PART_ID, gender="unspecified", keying=None
    )
    return [
        *_tbd_ops(project),
        Put(
            "harnesses",
            evolve(h, connectors=[loose if x.id == connector_id else x for x in h.connectors]),
        ),
    ]


def plan_resolve_loose_end(
    project: Project, harness_id: str, connector_id: str, part_id: str
) -> list[Op]:
    """Ops that give a loose end its connector part and make it an ordinary free-standing cable
    connector (role `cable`, plugged into nothing): the end is decided, not plugged in. Choosing
    the part in the connector editor (`connector_edit.plan_edit_connector`) does the same."""
    _writable(project)
    h = _own(project, harness_id)
    c = next((x for x in h.connectors if x.id == connector_id), None)
    if c is None or c.role != LOOSE:
        raise EditError(f"'{connector_id}' is not a loose end of {harness_id}.")
    part = connector_part(project, part_id)
    if part.pin_count is not None and len(c.pins) > part.pin_count:
        raise EditError(f"{part_id} has {part.pin_count} pins; {connector_id} has {len(c.pins)}.")
    new = evolve(c, role="cable", part_id=part_id, gender=part_gender(part))
    return [
        Put(
            "harnesses",
            evolve(h, connectors=[new if x.id == connector_id else x for x in h.connectors]),
        )
    ]


def is_own(project: Project, harness_id: str) -> bool:
    """True when the harness was made by a person (not by Generate) and may take connectors."""
    h = project.harnesses.get(harness_id)
    return h is not None and not h.generated and h.status != "released"


__all__ = [
    "LOOSE",
    "TBD_PART_ID",
    "CableFromPort",
    "PlugProposal",
    "loose_ends",
    "plan_add_loose_end",
    "plan_cable_from_port",
    "plan_plug_loose_end",
    "plan_resolve_loose_end",
    "plan_unplug",
    "propose_plug",
    "tbd_part",
    "PIN_FIELDS",
    "ROLES",
    "is_own",
    "plan_add_connector",
    "plan_delete_connector",
    "plan_new_harness",
    "plan_set_pin",
]
