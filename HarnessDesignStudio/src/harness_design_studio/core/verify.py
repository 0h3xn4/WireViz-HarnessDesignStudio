"""Independent output verifier. A separate code path from `generate/`: it shares no logic with it.

It reads the project as data (exactly what is saved), re-derives from the logical layer alone what
the harnesses must contain, and compares. If generation has a bug, this is where it shows.
Checks: every logical signal appears end to end exactly once; both ends of every wire agree with
the pinout tables (pins, the wire's signal label and the cable connector's own pin table); no pin
is used twice; a shielded type has a shield group covering its wires; harness bookkeeping matches
its wires; outputs are not stale. Wire gauge, colour and part are not checked (they are design
choices, see the design rules). It never raises.
"""

from collections import Counter
from dataclasses import dataclass, field

from .generation_status import generation_status
from .issues import Issue
from .model import Connector, Harness, Project, Wire

Endpoint = tuple[int, str]  # (end index of the interface, signal name at that end)
Connection = frozenset[Endpoint]


@dataclass
class VerifyReport:
    issues: list[Issue] = field(default_factory=list)
    interfaces_checked: int = 0
    wires_checked: int = 0
    stale: bool = False

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        state = "outdated, " if self.stale else ""
        return (
            f"{state}{self.interfaces_checked} interfaces and {self.wires_checked} wires checked: "
            f"{len(self.errors)} error(s)"
        )

    def error(self, code: str, message: str, obj: str | None = None) -> None:
        self.issues.append(Issue("error", code, message, None, obj))

    def warning(self, code: str, message: str, obj: str | None = None) -> None:
        self.issues.append(Issue("warning", code, message, None, obj))


def _pairing(signals: list[tuple[str, str]]) -> tuple[list[str], list[str], set[str]]:
    """Outputs, inputs and the directional signals that pass straight through (no partner)."""
    outs = [n for n, d in signals if d == "out"]
    ins = [n for n, d in signals if d == "in"]
    paired = min(len(outs), len(ins)) if (outs and ins) else 0
    return outs[:paired], ins[:paired], {*outs[paired:], *ins[paired:]}


def passthrough_signals(signals: list[tuple[str, str]]) -> set[str]:
    """Unpaired directional signals (more outputs than inputs or the reverse): they connect to
    the same name at the other end. The design rules use this too, so both agree."""
    return _pairing(signals)[2]


def expected_connections(signals: list[tuple[str, str]]) -> Counter[Connection]:
    """Connections an interface of this type needs, as unordered pairs of (end, signal).

    End 0/1 are the interface's first/second endpoint. An `out` signal at one end connects to the
    `in` signal at the same position in the other end; `passive`/`bidir` connect to the same name.
    """
    outs, ins, leftover = _pairing(signals)
    need: Counter[Connection] = Counter()
    for k in range(len(outs)):
        need[frozenset({(0, outs[k]), (1, ins[k])})] += 1
        need[frozenset({(1, outs[k]), (0, ins[k])})] += 1
    for name, direction in signals:  # unpaired directional signals pass straight through
        if direction in ("passive", "bidir") or name in leftover:
            need[frozenset({(0, name), (1, name)})] += 1
    return need


def _cable_index(project: Project) -> dict[str, tuple[Harness, Connector]]:
    return {c.id: (h, c) for h in project.harnesses.values() for c in h.connectors}


def _check_wire_ends(
    project: Project, rep: VerifyReport, cables: dict[str, tuple[Harness, Connector]]
) -> tuple[dict[tuple[str, str], list[str]], dict[tuple[str, str], list[str]]]:
    """Wire ends exist, mate with real unit connectors, and no pin is used twice."""
    cable_use: dict[tuple[str, str], list[str]] = {}
    box_use: dict[tuple[str, str], list[str]] = {}
    for h in project.harnesses.values():
        for w in h.wires:
            rep.wires_checked += 1
            same_pin = (w.from_connector, w.from_pin) == (w.to_connector, w.to_pin)
            if same_pin:
                rep.error(
                    "wire_same_pin",
                    f"Wire {w.id} starts and ends on the same pin ({w.from_pin} of {w.from_connector}).",
                    w.id,
                )
            for side, cid, pid in (
                ("from", w.from_connector, w.from_pin),
                ("to", w.to_connector, w.to_pin),
            ):
                if not (same_pin and side == "to"):  # one pin used once, reported above
                    cable_use.setdefault((cid, pid), []).append(w.id)
                owner = cables.get(cid)
                if owner is None or owner[0].id != h.id:
                    rep.error(
                        "wire_end_missing",
                        f"Wire {w.id} {side} end is on {cid}, which is not part of harness {h.id}.",
                        w.id,
                    )
                    continue
                cable = owner[1]
                if pid not in {p.id for p in cable.pins}:
                    rep.error(
                        "wire_pin_missing",
                        f"Wire {w.id} {side} end uses pin {pid}, which {cid} does not have.",
                        w.id,
                    )
                if cable.mates_with in project.connectors:
                    if not (same_pin and side == "to"):
                        box_use.setdefault((str(cable.mates_with), pid), []).append(w.id)
                elif h.generated:
                    rep.error(
                        "mate_missing",
                        f"Cable connector {cid} does not plug into an existing unit connector.",
                        cid,
                    )
        if h.generated:
            carried = sorted({w.interface_id for w in h.wires if w.interface_id})
            if sorted(h.interfaces) != carried:
                rep.error(
                    "harness_interfaces",
                    f"Harness {h.id} lists interfaces {sorted(h.interfaces)} but its wires carry {carried}.",
                    h.id,
                )
    return cable_use, box_use


def _wire_connection(
    project: Project,
    rep: VerifyReport,
    cables: dict[str, tuple[Harness, Connector]],
    iface_id: str,
    w: Wire,
) -> Connection | None:
    """The (end, signal) pair a wire really joins, read from the pinout tables. None if inconsistent."""
    i = project.interfaces[iface_id]
    ends: list[Endpoint] = []
    for cid, pid in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
        owner = cables.get(cid)
        box = project.connectors.get(owner[1].mates_with or "") if owner else None
        if box is None:
            return None
        idx = next(
            (
                k
                for k, e in enumerate(i.endpoints)
                if e.connector_id == box.id and e.unit_id == box.unit_id
            ),
            None,
        )
        if idx is None:
            rep.error(
                "wrong_endpoint",
                f"Wire {w.id} ends on {box.id}, which is not an end of interface {i.id}.",
                w.id,
            )
            return None
        pin = next((p for p in box.pins if p.id == pid), None)
        if pin is None or pin.signal is None or pin.interface_id != i.id:
            rep.error(
                "pinout_mismatch",
                f"Wire {w.id}: pin {pid} of {box.id} is not allocated to {i.id} in the pinout table.",
                w.id,
            )
            return None
        cable_pin = next((p for p in owner[1].pins if p.id == pid), None) if owner else None
        if cable_pin is not None and (
            cable_pin.signal not in (None, pin.signal)
            or cable_pin.interface_id not in (None, pin.interface_id)
        ):
            rep.error(
                "cable_pin_mismatch",
                f"Wire {w.id}: pin {pid} of cable connector {cid} is marked "
                f"{cable_pin.signal or 'no signal'} of {cable_pin.interface_id or 'no interface'}, "
                f"but pin {pid} of {box.id} carries {pin.signal} of {pin.interface_id}.",
                w.id,
            )
            return None
        ends.append((idx, pin.signal))
    if ends[0] == ends[1]:
        if (w.from_connector, w.from_pin) != (w.to_connector, w.to_pin):  # else reported earlier
            rep.error(
                "wire_same_end",
                f"Wire {w.id} joins two pins at the same end of interface {i.id}, both carrying {ends[0][1]}.",
                w.id,
            )
        return None
    label = _wire_label(ends[0][1], ends[1][1])
    if w.signal is not None and w.signal not in label:
        rep.error(
            "wire_signal_mismatch",
            f"Wire {w.id} is labelled {w.signal}, but its pins carry {ends[0][1]} and {ends[1][1]} "
            f"in the pinout tables of {i.id}.",
            w.id,
        )
    return frozenset(ends)


def _wire_label(a: str, b: str) -> set[str]:
    """Labels a wire between signals `a` and `b` may carry: the shared name, or one of the two orders."""
    return {a} if a == b else {f"{a}/{b}", f"{b}/{a}"}


def _check_shields(project: Project, rep: VerifyReport) -> None:
    """A type with shielding has a shield group covering its wires (overall: every wire; per
    pair: at least one wire, as signals without a pair are not shielded). The groups' ends and
    kinds are checked by design rules, not here."""
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        if not h.generated:
            continue
        covered = {wid for sh in h.shields if sh.kind != "twisted_pair" for wid in sh.wire_ids}
        for iid in sorted({w.interface_id for w in h.wires if w.interface_id}):
            i = project.interfaces.get(iid)
            itype = project.interface_types.get(i.type_id) if i else None
            if itype is None or itype.shielding == "none":
                continue
            ids = sorted(w.id for w in h.wires if w.interface_id == iid)
            missing = ids if not covered.intersection(ids) else []
            if itype.shielding == "overall":
                missing = [w for w in ids if w not in covered]
            if missing:
                rep.error(
                    "shield_missing",
                    f"Interface {iid} ({itype.id}) is shielded ({itype.shielding.replace('_', ' ')}) but no shield group of {h.id} covers "
                    f"{', '.join(missing[:3])}{' and others' if len(missing) > 3 else ''}.",
                    h.id,
                )


def verify_project(project: Project) -> VerifyReport:
    rep = VerifyReport()
    cables = _cable_index(project)
    cable_use, box_use = _check_wire_ends(project, rep, cables)
    drawn = {w.id for h in project.harnesses.values() for w in h.wires if w.manual}
    for label, use in (("", cable_use), ("unit connector ", box_use)):
        for (cid, pid), users in sorted(use.items()):
            if len(users) > 1:
                text = (
                    f"Pin {pid} of {label}{cid} is used by {len(users)} wires: "
                    f"{', '.join(sorted(users))}."
                )
                if drawn.intersection(users):  # a person put a wire there: said, not an error
                    rep.warning("pin_shared", text, cid)
                else:
                    rep.error("pin_reused", text, cid)

    by_interface: dict[str, list[Wire]] = {}
    for h in project.harnesses.values():
        for w in h.wires:
            if w.interface_id is not None:
                by_interface.setdefault(w.interface_id, []).append(w)

    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        itype = project.interface_types.get(i.type_id)
        if (
            itype is None
            or len(i.endpoints) != 2
            or any(e.connector_id not in project.connectors for e in i.endpoints)
        ):
            continue  # not routable (reported elsewhere)
        rep.interfaces_checked += 1
        need = expected_connections([(s.name, s.direction) for s in itype.signals])
        found: Counter[Connection] = Counter()
        unreadable = 0
        for w in by_interface.get(i.id, []):
            conn = _wire_connection(project, rep, cables, i.id, w)
            if conn is None:
                unreadable += 1
            else:
                found[conn] += 1
        for conn, n in sorted(need.items(), key=lambda kv: sorted(kv[0])):
            have = found.get(conn, 0)
            a, b = sorted(conn)
            text = f"{a[1]} (end {a[0] + 1}) to {b[1]} (end {b[0] + 1})"
            if have == 0 and not unreadable:
                rep.error("signal_missing", f"Interface {i.id}: {text} has no wire.", i.id)
            elif have > n:
                rep.error(
                    "signal_duplicated",
                    f"Interface {i.id}: {text} has {have} wires, expected {n}.",
                    i.id,
                )
        for conn in sorted(set(found) - set(need), key=lambda c: sorted(c)):
            a, b = sorted(conn)
            rep.error(
                "wire_extra",
                f"Interface {i.id} has a wire {a[1]} to {b[1]} that its type does not define.",
                i.id,
            )
    _check_shields(project, rep)
    for iid in sorted(set(by_interface) - set(project.interfaces)):
        rep.warning("wire_orphan", f"Wires trace to interface {iid}, which no longer exists.", iid)

    has_outputs = project.generation is not None or any(
        h.generated for h in project.harnesses.values()
    )
    if has_outputs and generation_status(project) != "current":
        rep.stale = True
        rep.error(
            "outputs_outdated",
            "The model changed after the harness plans were generated. Generate again before releasing.",
        )
    return rep
