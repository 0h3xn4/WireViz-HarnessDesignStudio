"""Links: the pinout is the truth (M2 of the workshop feedback, `docs/ait/WORKSHOP_FEEDBACK_PLAN.md`).

A link joins a connector of one device to a connector of another, pin to pin. The tool proposes
the pairs from the signal names on the pins (never from their position), a person looks at them
and changes them, and only then are they saved. What a link carries (CAN, power ...) is worked out
from the pins when it is shown (`derived_interfaces`), never stored; a person never "includes an
interface". The review (`check_link`) says what looks wrong without changing anything, and
`plan_create_harness` makes a harness that a person owns from a link.

    proposal = propose_pairs(project, "OBC-J01", "RW1-J02")        # pairs + what is left over
    ops, link_id = plan_add_link(project, "OBC-J01", "RW1-J02")    # pairs default to the proposal
    ops = plan_set_pairs(project, link_id, [("1", "3"), ("2", "4")])
    ops, harness_id = plan_create_harness(project, link_id)        # cable connectors and wires
    findings = check_link(project, project.links[link_id])

The `plan_*` functions are pure: they return `Op`s that `History.execute` runs as one undo step,
or raise `EditError` with a plain sentence that says what to do. Nothing here is invented: no
length, gauge or colour is set on a wire made from a link (they stay "pending", as for any wire a
person draws), and the pairing rules read only the names and directions the project already has.
"""

import re
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass

from pydantic import TypeAdapter, ValidationError

from . import counterparts
from .commands import Delete, Op, Put, apply_ops
from .counterparts import Counterparts
from .devices import derive_meaning, derive_meaning_types, ops_set_pin
from .edit import EditError, clone_with
from .ids import check_id
from .integrity import mating_plugs
from .issues import Severity
from .manual_harness import plan_add_connector, plan_new_harness
from .model import Connector, InterfaceType, Link, Pin, PinPair, Project, evolve
from .model.base import Label
from .vcs.lockview import lock_reason
from .verify import direction_judged, passthrough_signals
from .wires import plan_add_wires, used_ids

# The words that are the two ends of one line (TX and RX, MOSI and MISO ...) are a setting of the
# project, `config/naming.json` `signal_counterparts`; the table the tool ships with is in
# `counterparts.py`. Two EQUAL names with a transmit word (or two with a receive word) are never
# paired by the proposal: they look like transmit to transmit. Equal names pair as well (PWR/PWR,
# RTN/RTN, CANH/CANH).

_LABEL = TypeAdapter(Label)
_ANY_CONNECTOR = Connector(id="any", name="any", role="box", part_id="any")


# ---- small helpers -----------------------------------------------------------------------------


def natural_key(pin_id: str) -> tuple[tuple[int, int, str], ...]:
    """Pins in the order a person reads them: 2 before 10, A2 before A10."""
    parts = re.split(r"(\d+)", pin_id)
    return tuple((0, int(p), "") if p.isdigit() else (1, 0, p.casefold()) for p in parts if p)


def _name(signal: str | None) -> str:
    return (signal or "").strip().casefold()


def counterparts_of(project: Project) -> Counterparts:
    """The table of words that are the two ends of one line for this project:
    `signal_counterparts` of `config/naming.json` when it is set and valid, else the table the
    tool ships with (`counterparts.DEFAULT_COUNTERPARTS`)."""
    cfg = project.config.get(counterparts.CONFIG_FILE)
    return counterparts.from_config(cfg.values if cfg is not None else None)


def name_relation(a: str | None, b: str | None, table: Counterparts | None = None) -> str:
    """ "equal" when two signal names are the same, "counterpart" when they are the two ends of one
    line (TX and RX, UART_TX and UART_RX, SPW_DOUT+ and SPW_DIN+, TX_P and RX_P, MOSI and MISO),
    else "". Case is ignored; an empty name matches nothing. `table` is the project's table of
    counterpart words (`counterparts_of`); without it the table the tool ships with is used."""
    x, y = _name(a), _name(b)
    if not x or not y:
        return ""
    if x == y:
        return "equal"
    if (table or counterparts.DEFAULT).are_counterparts(x, y):
        return "counterpart"
    return ""


def same_side(a: str | None, b: str | None, table: Counterparts | None = None) -> str:
    """ "transmit" or "receive" when two EQUAL signal names both carry a transmit word (TX, TXD,
    DOUT, MOSI ...) or both a receive word (RX, RXD, DIN, MISO ...): joined, they would put a
    transmitter on a transmitter. "" otherwise."""
    x, y = _name(a), _name(b)
    if not x or x != y:
        return ""
    t = table or counterparts.DEFAULT
    parts = t.split(x)
    return t.side[parts[1]] if parts else ""


def _pair_side(a: Pin, b: Pin, table: Counterparts) -> str:
    """`same_side` of two pins, unless both have a direction of their own: then the names are not
    guessed from, the directions decide (a vendor that names every pin from its own point of view
    gives TX on both sides and says `out` on one and `in` on the other)."""
    if a.direction and b.direction:
        return ""
    return same_side(a.signal, b.signal, table)


def _signal_index(project: Project) -> dict[str, list[InterfaceType]]:
    out: dict[str, list[InterfaceType]] = defaultdict(list)
    for t in project.interface_types.values():
        for s in t.signals:
            out[s.name].append(t)
    return out


def _direction(
    project: Project,
    connector: Connector,
    pin: Pin,
    index: dict[str, list[InterfaceType]],
) -> str:
    """out, in, bidir or passive from the pin, else from the interface types, or "" when it is not
    known. The direction a person set on the pin (`Pin.direction`) wins over everything else: it is
    never guessed from a name and never exempted. Otherwise it is "" where the design rule
    `direction-conflict` does not judge the directions: a signal of a one-directional type (analog
    SIG+/SIG-, discrete SIG, LVDS D+/D-, pyro FIRE+/FIRE-, I2C SCL list `out` at both ends) and a
    directional signal with no partner in its type (it runs straight through to the same name)."""
    if pin.direction:
        return pin.direction
    direction, _category, _note, types = derive_meaning_types(project, connector, pin, index)
    if direction not in ("out", "in"):
        return direction
    for t in types:
        pairs = [(s.name, s.direction) for s in t.signals]
        if direction_judged(pairs) and (pin.signal or "") not in passthrough_signals(pairs):
            return direction
    return ""


def _conflict(da: str, db: str) -> str:
    """Why two known directions do not fit ("" when they do): output against output, or input
    against input."""
    if da == db == "out":
        return "both are outputs"
    if da == db == "in":
        return "both are inputs"
    return ""


def effective_role(
    pin: Pin,
    project: Project,
    connector: Connector | None = None,
    index: Mapping[str, list[InterfaceType]] | None = None,
) -> str:
    """What a pin is for: the role a person gave it, else the one derived from the signal name.
    "power" for a signal of an interface type of the power category (not RTN), "return" for RTN,
    "ground" for GND or a type of the ground category, "signal" for any other signal, and "" for a
    pin with no signal. Pass the connector when it is known (the types it carries narrow the
    meaning of a name), and `index` (signal name -> interface types) when many pins are asked in a
    row, so the types are not indexed again for each."""
    if pin.role:
        return pin.role
    if not pin.signal:
        return ""
    name = pin.signal.strip().upper()
    if name == "RTN":
        return "return"
    if name == "GND":
        return "ground"
    category = derive_meaning(project, connector or _ANY_CONNECTOR, pin, index)[1]
    if category == "power":
        return "power"
    if category == "ground":
        return "ground"
    return "signal"


def _pin_ref(connector_id: str, pin_id: str) -> str:
    return f"{connector_id}.{pin_id}"


def link_caption(link: Link) -> str:
    """How a link is named on screen: its two connectors, "OBC-J01 - RW1-J02" (the same text in
    the project tree, on the diagram and in the windows)."""
    return f"{link.a_connector} - {link.b_connector}"


LinkPins = dict[str, dict[str, list[str]]]  # connector -> pin -> the links that pair it (first two)


def link_pin_index(project: Project, connectors: Collection[str] | None = None) -> LinkPins:
    """For each connector (only `connectors` when given) the pins that links pair, each with the
    IDs of the links that pair it, by link ID (the first two are kept: the first link that is not
    the one being looked at is all that is ever asked). One pass over the links, however many
    connectors are asked about."""
    out: LinkPins = {}
    for link in sorted(project.links.values(), key=lambda x: x.id):
        for conn, side in ((link.a_connector, "a"), (link.b_connector, "b")):
            if connectors is not None and conn not in connectors:
                continue
            owners = out.setdefault(conn, {})
            for pair in link.pairs:
                found = owners.setdefault(pair.a_pin if side == "a" else pair.b_pin, [])
                if link.id not in found and len(found) < 2:
                    found.append(link.id)
    return out


def _taken(index: LinkPins, connector_id: str, except_link: str | None = None) -> dict[str, str]:
    """Pin of a connector -> the first link (by ID) that pairs it, leaving `except_link` out."""
    out: dict[str, str] = {}
    for pin, ids in index.get(connector_id, {}).items():
        first = next((i for i in ids if i != except_link), None)
        if first is not None:
            out[pin] = first
    return out


def pins_in_links(
    project: Project, connector_id: str, *, except_link: str | None = None
) -> dict[str, str]:
    """Pin of a connector -> the first link (by ID) that pairs it."""
    return _taken(link_pin_index(project, {connector_id}), connector_id, except_link)


def links_of_connector(project: Project, connector_id: str) -> list[Link]:
    """The links that join this connector, by ID."""
    return [
        x
        for x in sorted(project.links.values(), key=lambda x: x.id)
        if connector_id in (x.a_connector, x.b_connector)
    ]


def _writable(project: Project) -> None:
    if project.read_only:
        raise EditError("This project is read-only (saved by a newer tool version). Use Save as.")


def _device_connector(project: Project, connector_id: str) -> Connector:
    c = project.connectors.get(connector_id)
    if c is None or c.role != "box":
        raise EditError(f"'{connector_id}' is not a connector of a device in this project.")
    if c.unit_id is None or c.unit_id not in project.units:
        raise EditError(f"{connector_id} does not belong to a device that exists.")
    return c


def _two_devices(project: Project, a_id: str, b_id: str) -> tuple[Connector, Connector]:
    a = _device_connector(project, a_id)
    b = _device_connector(project, b_id)
    if a.unit_id == b.unit_id:
        raise EditError(
            f"{a_id} and {b_id} are on the same device ({a.unit_id}). "
            "A link joins connectors of two different devices."
        )
    return a, b


# ---- pairing by signal name --------------------------------------------------------------------


@dataclass(frozen=True)
class Proposal:
    """The pairing the tool proposes for two connectors. `unpaired_a` and `unpaired_b` are the pins
    (in reading order) that no pair uses and no other link has; `notes` say, in plain words, what
    was not paired and why."""

    pairs: tuple[PinPair, ...]
    unpaired_a: tuple[str, ...]
    unpaired_b: tuple[str, ...]
    notes: tuple[str, ...]


class _NameIndex:
    """The free pins of one connector looked up by what their names say, so a pin of the other
    connector finds its candidates without being compared with every pin: `equal` (name -> the
    positions of the pins with that name) and `ends` ((the word that would meet it, the words
    after it) -> the positions of the pins whose name has that word, with the words before it).
    Positions are indexes into the list the index was made from, in reading order."""

    def __init__(self, pins: Sequence[Pin], table: Counterparts) -> None:
        self.equal: dict[str, list[int]] = defaultdict(list)
        self.ends: dict[tuple[str, tuple[str, ...]], list[tuple[int, tuple[str, ...]]]] = (
            defaultdict(list)
        )
        for k, pin in enumerate(pins):
            name = _name(pin.signal)
            if not name:
                continue
            self.equal[name].append(k)
            if (parts := table.split(name)) is not None:
                self.ends[(parts[1], parts[2])].append((k, parts[0]))

    def related(self, name: str, table: Counterparts, kind: str) -> list[int]:
        """Positions, in reading order, of the pins whose name is `kind` ("equal" or
        "counterpart") to `name` (in lower case)."""
        if kind == "equal":
            return self.equal.get(name, [])
        parts = table.split(name)
        if parts is None:
            return []
        before, word, after = parts
        found = self.ends.get((table.counter[word], after), [])
        return [k for k, other in found if before == other or not before or not other]


def propose_pairs(project: Project, a_connector_id: str, b_connector_id: str) -> Proposal:
    """Pair the pins of two device connectors by signal name only: equal names, or the two ends of
    one line (TX and RX, TXD and RXD, TX+ and RX+, TX_P and RX_P, DOUT and DIN, MOSI and MISO, SDO
    and SDI, with or without a prefix such as UART_ or SPW_, in both orders; the words are the
    project's table, `config/naming.json` `signal_counterparts`). Two equal names that
    both look like transmit (TX, DOUT, MOSI ...) or both like receive are never paired: they are
    left unpaired and named in the notes, because a transmitter on a transmitter is the mistake a
    vendor's own-point-of-view names hide. A direction a person set on a pin (`Pin.direction`)
    decides before any name does, also for two equal names; where it is not set the directions of
    the interface types decide where they are known: an output goes to an
    input, bidirectional and passive pins go with anything, output against output and input
    against input are not paired and are named in the notes. A pin is used once; a pin with no
    signal is left unpaired; a pin another link pairs is not offered. The result depends only on
    the pins (taken in reading order), so it is the same every time. The pins are looked up by
    name, so the work grows with the number of pins, not with its square."""
    a, b = _two_devices(project, a_connector_id, b_connector_id)
    index = _signal_index(project)
    table = counterparts_of(project)
    notes: list[str] = []
    free: dict[str, list[Pin]] = {}
    owners = link_pin_index(project, {a.id, b.id})
    for conn in (a, b):
        taken = _taken(owners, conn.id)
        if taken:
            have = {p.id for p in conn.pins}
            by_link: dict[str, list[str]] = defaultdict(list)
            for pid in sorted(taken, key=natural_key):
                if pid in have:
                    by_link[taken[pid]].append(pid)
            for lid, pids in sorted(by_link.items()):
                notes.append(
                    f"Pin{'s' if len(pids) > 1 else ''} {', '.join(pids)} of {conn.id} "
                    f"{'are' if len(pids) > 1 else 'is'} already paired in link {lid}."
                )
        wired = [p for p in conn.pins if p.interface_id and p.id not in taken]
        if wired:
            notes.append(
                f"Pin{'s' if len(wired) > 1 else ''} {', '.join(p.id for p in sorted(wired, key=lambda p: natural_key(p.id)))} of "
                f"{conn.id} {'are' if len(wired) > 1 else 'is'} used by an interface that "
                "Generate wires, so not offered."
            )
        free[conn.id] = sorted(
            (p for p in conn.pins if p.id not in taken and not p.interface_id),
            key=lambda p: natural_key(p.id),
        )
    dirs = {
        (conn.id, p.id): _direction(project, conn, p, index) for conn in (a, b) for p in conn.pins
    }
    fa, fb = free[a.id], free[b.id]
    names_b = _NameIndex(fb, table)
    used_a: set[int] = set()
    used_b: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for wanted in ("counterpart", "equal"):  # TX to RX first, then the same name
        for ka, pa in enumerate(fa):
            if ka in used_a or not pa.signal:
                continue
            for kb in names_b.related(_name(pa.signal), table, wanted):
                pb = fb[kb]
                if kb in used_b:
                    continue
                if _pair_side(pa, pb, table):
                    continue  # transmit to transmit (or receive to receive): left to a person
                if _conflict(dirs[(a.id, pa.id)], dirs[(b.id, pb.id)]):
                    continue
                pairs.append((ka, kb))
                used_a.add(ka)
                used_b.add(kb)
                break
    for ka, pa in enumerate(
        fa
    ):  # names that fit, stopped by what they look like or by the directions
        if ka in used_a or not pa.signal:
            continue
        name = _name(pa.signal)
        fits = sorted(
            {*names_b.related(name, table, "equal"), *names_b.related(name, table, "counterpart")}
        )
        for kb in fits:
            pb = fb[kb]
            if kb in used_b:
                continue
            where = (
                f"{pa.signal} on pin {pa.id} of {a.id} and {pb.signal} on pin {pb.id} of "
                f"{b.id} were not paired: "
            )
            if why := _conflict(dirs[(a.id, pa.id)], dirs[(b.id, pb.id)]):
                notes.append(f"{where}{why}.")
            elif side := _pair_side(pa, pb, table):
                notes.append(
                    f"{where}they look like {side} to {side}. If one device names its pins "
                    "from the other's point of view, pair them yourself."
                )
    chosen = sorted(
        (PinPair(a_pin=fa[ka].id, b_pin=fb[kb].id) for ka, kb in pairs),
        key=lambda p: natural_key(p.a_pin),
    )
    return Proposal(
        tuple(chosen),
        tuple(p.id for k, p in enumerate(fa) if k not in used_a),
        tuple(p.id for k, p in enumerate(fb) if k not in used_b),
        tuple(notes),
    )


# ---- the planners ------------------------------------------------------------------------------

PairLike = PinPair | tuple[str, str]


def _as_pairs(pairs: Iterable[PairLike]) -> list[PinPair]:
    out: list[PinPair] = []
    for p in pairs:
        if isinstance(p, PinPair):
            out.append(p)
            continue
        try:
            out.append(PinPair(a_pin=p[0], b_pin=p[1]))
        except (ValidationError, IndexError, TypeError) as exc:
            raise EditError(
                "A pair is a pin of the first connector and a pin of the second, "
                "for example 1 and 3."
            ) from exc
    return out


def _check_pairs(
    project: Project, a: Connector, b: Connector, pairs: Sequence[PinPair], link_id: str | None
) -> None:
    """A pin exists, belongs to one pair, and is in no other link."""
    have_a = {p.id for p in a.pins}
    have_b = {p.id for p in b.pins}
    owners = link_pin_index(project, {a.id, b.id})
    other_a = _taken(owners, a.id, link_id)
    other_b = _taken(owners, b.id, link_id)
    seen_a: set[str] = set()
    seen_b: set[str] = set()
    for pair in pairs:
        for conn, pid, have, other, seen in (
            (a, pair.a_pin, have_a, other_a, seen_a),
            (b, pair.b_pin, have_b, other_b, seen_b),
        ):
            if pid not in have:
                raise EditError(f"{conn.id} has no pin '{pid}'.")
            if pid in seen:
                raise EditError(
                    f"Pin {pid} of {conn.id} is in two pairs. A pin can be in one pair only."
                )
            if pid in other:
                raise EditError(
                    f"Pin {pid} of {conn.id} is already paired in link {other[pid]}. "
                    "A pin can be in one link only; change that link first."
                )
            seen.add(pid)


def _label(text: str) -> str:
    clean = text.strip()
    try:
        return _LABEL.validate_python(clean, strict=True)
    except ValidationError as exc:
        raise EditError(
            "A link name can have up to 200 characters and no control characters."
        ) from exc


def _next_link_id(project: Project) -> str:
    taken = {i.casefold() for i in used_ids(project)} | {i.casefold() for i in project.links}
    n = 1
    while f"l{n}" in taken:
        n += 1
    return f"L{n}"


def _known_link(project: Project, link_id: str) -> Link:
    link = project.links.get(link_id)
    if link is None:
        raise EditError(f"Link '{link_id}' does not exist.")
    return link


def _unlocked(project: Project, link_id: str) -> None:
    if why := lock_reason(project, "link", link_id):
        raise EditError(f"Link {link_id} cannot change. {why}")


def _refuse_if_built(
    project: Project, a: Connector, b: Connector, pairs: Sequence[PinPair]
) -> None:
    """A link must not meet something that is already built: a cable plug of another harness on
    one of its device connectors, or a pin that an interface allocated (Generate wires it)."""
    plugs = mating_plugs(project.harnesses.values())
    for conn in (a, b):
        if found := plugs.get(conn.id):
            hid, cid = found[0]
            raise EditError(
                f"{conn.id} has a cable plug on it already: {cid} of harness {hid}. A connector "
                "takes one plug. Open that harness, or delete it first."
            )
    for conn, ids in ((a, [x.a_pin for x in pairs]), (b, [x.b_pin for x in pairs])):
        pins = {p.id: p for p in conn.pins}
        for pid in ids:
            if (pin := pins.get(pid)) is not None and pin.interface_id:
                raise EditError(
                    f"Pin {pid} of {conn.id} is used by interface {pin.interface_id}, which "
                    "Generate wires. Pair another pin, or change that interface first."
                )


def plan_add_link(
    project: Project,
    a_connector: str,
    b_connector: str,
    pairs: Iterable[PairLike] | None = None,
    name: str = "",
    link_id: str | None = None,
) -> tuple[list[Op], str]:
    """Ops that add a link between two connectors of two different devices, and its ID (the next
    free `L1`, `L2` ... unless `link_id` is given). Without `pairs` the pairing is the proposal of
    `propose_pairs`. A pin must exist, be in one pair and be in no other link."""
    _writable(project)
    a, b = _two_devices(project, a_connector, b_connector)
    chosen = (
        list(propose_pairs(project, a_connector, b_connector).pairs)
        if pairs is None
        else _as_pairs(pairs)
    )
    _check_pairs(project, a, b, chosen, None)
    _refuse_if_built(project, a, b, chosen)
    if link_id is None:
        lid = _next_link_id(project)
    else:
        try:
            lid = check_id(link_id)
        except ValueError as exc:
            raise EditError(f"The link ID '{link_id}' {exc}.") from exc
        if lid.casefold() in {i.casefold() for i in used_ids(project) | set(project.links)}:
            raise EditError(f"The ID {lid} is used already; choose another.")
    link = Link(id=lid, name=_label(name), a_connector=a.id, b_connector=b.id, pairs=chosen)
    return [Put("links", link)], lid


def plan_set_pairs(project: Project, link_id: str, pairs: Iterable[PairLike]) -> list[Op]:
    """Ops that replace the pairing of a link. Refused when the harness made from the link is
    released. (A harness already made from the link is not changed; edit its wires there.)"""
    _writable(project)
    link = _known_link(project, link_id)
    _unlocked(project, link_id)
    a, b = _two_devices(project, link.a_connector, link.b_connector)
    chosen = _as_pairs(pairs)
    _check_pairs(project, a, b, chosen, link_id)
    if chosen == link.pairs:
        return []
    return [Put("links", evolve(link, pairs=chosen))]


def plan_rename_link(project: Project, link_id: str, name: str) -> list[Op]:
    """Ops that set the label of a link (empty clears it)."""
    _writable(project)
    link = _known_link(project, link_id)
    _unlocked(project, link_id)
    label = _label(name)
    return [] if label == link.name else [Put("links", evolve(link, name=label))]


def plan_delete_link(project: Project, link_id: str) -> list[Op]:
    """Ops that delete a link. The harness made from it stays (it belongs to its owner now).
    Refused when that harness is released."""
    _writable(project)
    _known_link(project, link_id)
    _unlocked(project, link_id)
    return [Delete("links", link_id)]


def plan_set_roles(project: Project, roles: Mapping[tuple[str, str], str]) -> list[Op]:
    """Ops that give pins a role, `{(connector, pin): role}` ("" takes it from the signal name
    again). Each pin is planned on a copy that has the earlier ones, so several pins of one
    connector make one change each without undoing one another. Pins that already have the role
    make no op."""
    scratch = clone_with(project, [])
    out: list[Op] = []
    for (cid, pid), role in sorted(roles.items(), key=lambda kv: (kv[0][0], natural_key(kv[0][1]))):
        ops = ops_set_pin(scratch, cid, pid, role=role)
        apply_ops(scratch, ops)
        out.extend(ops)
    return out


def _wire_signal(a: Pin, b: Pin) -> str | None:
    """The signal of a wire between two pins, written as Generate writes it: one name when both
    pins have it, "TX+/RX+" when they differ, the one that is there when only one has a name."""
    x = (a.signal or "").strip()
    y = (b.signal or "").strip()
    if x and y and x != y:
        return f"{x}/{y}"[:200]
    return x or y or None


def plan_create_harness(project: Project, link_id: str) -> tuple[list[Op], str]:
    """Ops that make a harness, which a person owns (`generated` is False, so Generate leaves it
    alone), from a link, and its ID: a cable connector that mates with each device connector (as
    `manual_harness.plan_add_connector` makes them), one wire drawn by hand for each pair with the
    signal of the pins, and the link now names the harness. No length, gauge or colour is set;
    they stay pending, as for any wire a person draws. One undo step. Refused when the link has
    no pairs, has a harness already, does not pass its review for a missing connector or pin, or when
    a device connector of the link has a cable plug of another harness on it, or a paired pin is
    allocated to an interface. Done in one pass: the review reads the links once and the wires are
    added together, so a link of 1,000 pairs takes seconds less than one wire after the other."""
    _writable(project)
    link = _known_link(project, link_id)
    if link.harness_id:
        raise EditError(
            f"Link {link_id} has the harness {link.harness_id} already. "
            "Open that harness, or delete it first to make another."
        )
    if not link.pairs:
        raise EditError(f"Link {link_id} has no pairs yet. Pair the pins first.")
    for f in check_link(project, link):
        if f.code in ("link_dangling", "link_pin_reused"):
            raise EditError(f.message)
    a, b = _two_devices(project, link.a_connector, link.b_connector)
    _refuse_if_built(project, a, b, link.pairs)
    title = link.name or f"{a.unit_id} to {b.unit_id}"
    names = {h.name.casefold() for h in project.harnesses.values()}
    unique, n = title, 1
    while unique.casefold() in names:
        n += 1
        unique = f"{title} ({link_id})" if n == 2 else f"{title} ({link_id}-{n - 1})"
    scratch = clone_with(project, [])  # each step is planned on a copy that has the previous ones
    ops, hid = plan_new_harness(scratch, unique)
    apply_ops(scratch, ops)
    cable: dict[str, str] = {}
    for box in (a, b):
        ops, cid = plan_add_connector(scratch, hid, mates_with=box.id)
        apply_ops(scratch, ops)
        cable[box.id] = cid
    pins_a = {p.id: p for p in a.pins}
    pins_b = {p.id: p for p in b.pins}
    ops = plan_add_wires(  # all the wires in one pass, with the IDs one after the other would get
        scratch,
        hid,
        [
            (
                cable[a.id],
                pair.a_pin,
                cable[b.id],
                pair.b_pin,
                _wire_signal(pins_a[pair.a_pin], pins_b[pair.b_pin]),
            )
            for pair in link.pairs
        ],
    )
    apply_ops(scratch, ops)
    return [
        Put("harnesses", scratch.harnesses[hid]),
        Put("links", evolve(link, harness_id=hid)),
    ], hid


@dataclass(frozen=True)
class LinkEnd:
    """One end of a link for the diagram: the device connector, its name, its number of pins and how
    many of them the link pairs."""

    connector_id: str
    name: str
    pins: int
    used: int


def link_ends(project: Project, link: Link) -> tuple[LinkEnd, LinkEnd]:
    """The two ends of a link, A then B (display only). A connector that is gone shows its ID and
    no pins."""

    def end(connector_id: str, pins_used: set[str]) -> LinkEnd:
        c = project.connectors.get(connector_id)
        if c is None:
            return LinkEnd(connector_id, connector_id, 0, 0)
        return LinkEnd(connector_id, c.name, len(c.pins), len(pins_used & {p.id for p in c.pins}))

    return (
        end(link.a_connector, {p.a_pin for p in link.pairs}),
        end(link.b_connector, {p.b_pin for p in link.pairs}),
    )


def link_path(project: Project, link: Link) -> list[str]:
    """The way a link runs once a harness was made from it: the connector of the first device, the
    cable connector that plugs into it, the cable connector at the other end, the connector of the
    second device. Empty while no harness exists. A cable connector that is not found (it was
    deleted) is left out; the result keeps the order."""
    h = project.harnesses.get(link.harness_id or "")
    if h is None:
        return []
    path = [link.a_connector]
    for box in (link.a_connector, link.b_connector):
        cable = next((c.id for c in h.connectors if c.mates_with == box), None)
        if cable is not None:
            path.append(cable)
    path.append(link.b_connector)
    return path


# ---- what a link carries (display only) --------------------------------------------------------


@dataclass(frozen=True)
class DerivedInterface:
    """A group of the pairs of one link that belong to one interface type, for display. Never
    stored. `label` reads like "CAN, 2 wires". When several types fit equally (RS-422 and Ethernet
    have the same signals) `type_id` is the first by ID and `alternatives` lists all of them; a
    group no type explains has an empty `type_id`."""

    link_id: str
    type_id: str
    label: str
    pairs: tuple[PinPair, ...]
    alternatives: tuple[str, ...] = ()


def _wires(n: int) -> str:
    return f"{n} wire{'s' if n != 1 else ''}"


def derived_interfaces(project: Project) -> list[DerivedInterface]:
    """For each link, its pairs grouped by the interface type whose signals contain the signals of
    the pins. A type is taken for the pairs it explains most of (ties go to the type with fewer signals,
    then to the first by ID); types that explain exactly the same pairs are named in the label. Sorted by link, then by group."""
    out: list[DerivedInterface] = []
    for link in sorted(project.links.values(), key=lambda x: x.id):
        a = project.connectors.get(link.a_connector)
        b = project.connectors.get(link.b_connector)
        if a is None or b is None:
            continue
        pa = {p.id: p for p in a.pins}
        pb = {p.id: p for p in b.pins}
        remaining = [p for p in link.pairs if p.a_pin in pa and p.b_pin in pb]
        fits: dict[int, set[str]] = {}
        for k, pair in enumerate(remaining):
            sa, sb = pa[pair.a_pin].signal, pb[pair.b_pin].signal
            fits[k] = {
                t.id
                for t in project.interface_types.values()
                if sa and sb and {sa, sb} <= {s.name for s in t.signals}
            }
        todo = set(fits)
        while True:
            count: dict[str, int] = defaultdict(int)
            for k in todo:
                for tid in fits[k]:
                    count[tid] += 1
            if not count:
                break

            def size(tid: str) -> int:
                return len(project.interface_types[tid].signals)

            first = min(count, key=lambda tid: (-count[tid], size(tid), tid))
            members = [k for k in sorted(todo) if first in fits[k]]
            chosen = sorted(  # types that explain exactly the same pairs and are as small
                tid
                for tid in count
                if size(tid) == size(first)
                and [k for k in sorted(todo) if tid in fits[k]] == members
            )
            names = " or ".join(project.interface_types[t].name for t in chosen)
            out.append(
                DerivedInterface(
                    link.id,
                    chosen[0],
                    f"{names}, {_wires(len(members))}",
                    tuple(remaining[k] for k in members),
                    tuple(chosen),
                )
            )
            todo -= set(members)
        if todo:
            rest = [remaining[k] for k in sorted(todo)]
            out.append(
                DerivedInterface(
                    link.id, "", f"No interface type, {_wires(len(rest))}", tuple(rest)
                )
            )
    return out


# ---- the review --------------------------------------------------------------------------------


@dataclass(frozen=True)
class LinkFinding:
    """One thing the review of a link found. `pin` is "CONNECTOR.PIN" when it is about one pin."""

    code: str
    severity: Severity
    message: str
    link_id: str
    pin: str | None = None


def _words(direction: str) -> str:
    return "an output" if direction == "out" else "an input"


def _is_power_loop(
    project: Project, powered: Sequence[PinPair], pa: Mapping[str, Pin], pb: Mapping[str, Pin]
) -> bool:
    """True when the power pairs of a link are a two-wire loop that carries its own return: both
    signals of an interface type of the power category that has no RTN or GND (a heater pair,
    HTR+ and HTR-) are paired, at both ends. Such a pair needs no extra return pin."""
    names_a = {_name(pa[p.a_pin].signal) for p in powered}
    names_b = {_name(pb[p.b_pin].signal) for p in powered}
    for t in project.interface_types.values():
        sig = {_name(s.name) for s in t.signals}
        if (
            t.category == "power"
            and len(sig) >= 2
            and not sig & {"rtn", "gnd"}
            and sig <= names_a
            and sig <= names_b
        ):
            return True
    return False


@dataclass(frozen=True)
class _Review:
    """What the review of any link needs, worked out once for all of them: the interface types by
    signal name, the project's table of counterpart words, and the links that pair each pin."""

    types: dict[str, list[InterfaceType]]
    table: Counterparts
    owners: LinkPins


def _review_of(project: Project, connectors: Collection[str] | None) -> _Review:
    return _Review(
        _signal_index(project), counterparts_of(project), link_pin_index(project, connectors)
    )


def check_link(project: Project, link: Link) -> list[LinkFinding]:
    """Review a link without changing anything. The codes:
    `link_dangling` (error: a connector or pin of the link is gone), `link_pin_reused` (error: a pin
    in two pairs or in two links), `link_direction_conflict` (error: output against output, or
    input against input), `link_signal_mismatch` (warning: the names on a pair differ and are not
    the two ends of one line), `link_pin_unpaired` (warning: a pin with a signal that no pair of
    this link or of another link uses), `link_power_without_return` (warning: a power pair and no
    return pair on the link; a heater pair, HTR+ and HTR-, is a two-wire loop and has its own
    return). A pin with the role "spare" is never reported as unpaired. The directions a person set on
    pins (`Pin.direction`) decide `link_direction_conflict` before the interface types do, and
    two pins that both have one are not warned about for equal transmit or receive names."""
    return _check_link(project, link, _review_of(project, {link.a_connector, link.b_connector}))


def _check_link(project: Project, link: Link, review: _Review) -> list[LinkFinding]:
    out: list[LinkFinding] = []
    lid = link.id
    ends = [
        (project.connectors.get(link.a_connector), link.a_connector),
        (project.connectors.get(link.b_connector), link.b_connector),
    ]
    for conn, cid in ends:
        if conn is None or conn.role != "box":
            out.append(LinkFinding("link_dangling", "error", f"Link {lid} joins connector {cid}, which no longer exists. Delete the link, or make it again with another connector.", lid, cid))  # fmt: skip
    a, b = ends[0][0], ends[1][0]
    if a is None or b is None:
        return out
    pa = {p.id: p for p in a.pins}
    pb = {p.id: p for p in b.pins}
    index, table = review.types, review.table
    seen_a: set[str] = set()
    seen_b: set[str] = set()
    other_a = _taken(review.owners, a.id, lid)
    other_b = _taken(review.owners, b.id, lid)
    good: list[PinPair] = []
    for pair in link.pairs:
        missing = False
        for conn, pid, known in ((a, pair.a_pin, pa), (b, pair.b_pin, pb)):
            if pid not in known:
                missing = True
                out.append(LinkFinding("link_dangling", "error", f"Link {lid} pairs pin {pid} of {conn.id}, but that pin no longer exists. Change the pairing of the link.", lid, _pin_ref(conn.id, pid)))  # fmt: skip
        for conn, pid, seen, other in (
            (a, pair.a_pin, seen_a, other_a),
            (b, pair.b_pin, seen_b, other_b),
        ):
            if pid in seen:
                out.append(LinkFinding("link_pin_reused", "error", f"Pin {pid} of {conn.id} is in two pairs of link {lid}. Keep one pair for it.", lid, _pin_ref(conn.id, pid)))  # fmt: skip
            elif pid in other:
                out.append(LinkFinding("link_pin_reused", "error", f"Pin {pid} of {conn.id} is paired in link {other[pid]} and in link {lid}. Keep it in one link.", lid, _pin_ref(conn.id, pid)))  # fmt: skip
            seen.add(pid)
        if not missing:
            good.append(pair)
    for pair in good:
        x, y = pa[pair.a_pin], pb[pair.b_pin]
        where = f"pin {x.id} of {a.id} with pin {y.id} of {b.id}"
        if bool(x.signal) != bool(y.signal):
            which = (x, a) if not x.signal else (y, b)
            named = x if x.signal else y
            out.append(LinkFinding("link_signal_mismatch", "warning", f"Link {lid} pairs {where}, but pin {which[0].id} of {which[1].id} has no signal while the other is named {named.signal}. Name the pin, or change the pairing.", lid, _pin_ref(a.id, x.id)))  # fmt: skip
        elif x.signal and y.signal and not name_relation(x.signal, y.signal, table):
            out.append(LinkFinding("link_signal_mismatch", "warning", f"Link {lid} pairs {where}, but their signals differ ({x.signal} and {y.signal}). Check the pairing, or rename a signal.", lid, _pin_ref(a.id, x.id)))  # fmt: skip
        dx, dy = _direction(project, a, x, index), _direction(project, b, y, index)
        if (side := _pair_side(x, y, table)) and not _conflict(dx, dy):
            out.append(LinkFinding("link_signal_mismatch", "warning", f"Link {lid} pairs {where}, and both are named {x.signal}, which looks like {side} to {side}. A transmit pin should meet a receive pin. Check the pairing, or the names.", lid, _pin_ref(a.id, x.id)))  # fmt: skip
        if why := _conflict(dx, dy):
            fight = (
                "Two outputs drive against each other."
                if dx == "out"
                else "Nothing drives the pair."
            )
            out.append(LinkFinding("link_direction_conflict", "error", f"Link {lid} pairs {where}, and {why} ({x.signal} is {_words(dx)}, {y.signal} is {_words(dy)}). {fight} Pair the pin with one that fits, or correct the signal.", lid, _pin_ref(a.id, x.id)))  # fmt: skip
    in_pair_a = {p.a_pin for p in good}
    in_pair_b = {p.b_pin for p in good}
    for conn, known, paired, other in (
        (a, pa, in_pair_a, other_a),
        (b, pb, in_pair_b, other_b),
    ):
        for pid in sorted(known, key=natural_key):
            pin = known[pid]
            if (
                pin.signal
                and pid not in paired
                and pid not in other
                and effective_role(pin, project, conn, index) != "spare"
            ):
                far = b if conn is a else a
                out.append(LinkFinding("link_pin_unpaired", "warning", f"Pin {pid} of {conn.id} is named {pin.signal} but is not paired in link {lid}. Pair it with a pin of {far.id}, or set its role to Spare if it is not used.", lid, _pin_ref(conn.id, pid)))  # fmt: skip
    roles = [
        {
            effective_role(pa[p.a_pin], project, a, index),
            effective_role(pb[p.b_pin], project, b, index),
        }
        for p in good
    ]
    powered = [p for p, r in zip(good, roles, strict=True) if "power" in r]
    if (
        powered
        and not any("return" in r for r in roles)
        and not _is_power_loop(project, powered, pa, pb)
    ):
        shown = ", ".join(f"{p.a_pin}-{p.b_pin}" for p in powered[:4])
        out.append(LinkFinding("link_power_without_return", "warning", f"Link {lid} pairs power (pins {shown}) but no return. Pair the return pin (RTN), or set the role of the return pin to Return.", lid, _pin_ref(a.id, powered[0].a_pin)))  # fmt: skip
    return out


def check_links(project: Project) -> list[LinkFinding]:
    """The review of every link, by link ID (the interface types, the counterpart table and the
    pins the links pair are worked out once, not for each link)."""
    if not project.links:
        return []
    review = _review_of(project, None)
    return [f for x in sorted(project.links.values(), key=lambda x: x.id) for f in _check_link(project, x, review)]  # fmt: skip


__all__ = [
    "DerivedInterface",
    "LinkEnd",
    "LinkFinding",
    "Proposal",
    "check_link",
    "check_links",
    "counterparts_of",
    "derived_interfaces",
    "effective_role",
    "link_caption",
    "link_ends",
    "link_pin_index",
    "link_path",
    "links_of_connector",
    "name_relation",
    "natural_key",
    "pins_in_links",
    "plan_add_link",
    "plan_create_harness",
    "plan_delete_link",
    "plan_rename_link",
    "plan_set_pairs",
    "plan_set_roles",
    "propose_pairs",
]
