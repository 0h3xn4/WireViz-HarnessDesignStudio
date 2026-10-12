"""Generation: logical interfaces in, physical harnesses out, as a plan that can be previewed.

`plan_generation` never changes the project. It returns the operations (one transaction), a
report of what is kept, added, changed and removed, and provenance explaining every decision.
Everything is sorted by stable IDs and nothing depends on time, so the same inputs always give
the same bytes. Released harnesses are frozen; locked pins and wires are never moved.
"""

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, cast

from pydantic import TypeAdapter, ValidationError

from harness_design_studio import __version__
from harness_design_studio.core import configcheck
from harness_design_studio.core.commands import Delete, Op, Put, SetGeneration
from harness_design_studio.core.describe import part_gender
from harness_design_studio.core.edit import clone_with
from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.model import (
    BranchPoint,
    Connector,
    GenerationRecord,
    Harness,
    InterfaceInstance,
    Pin,
    Project,
    Segment,
    ShieldGroup,
    Wire,
    evolve,
)
from harness_design_studio.core.model.base import Name
from harness_design_studio.core.vcs.snapshot import carried_interfaces

from .lengths import path_length
from .naming import Namer, namer_for
from .pins import Allocation, Request, allocate
from .segmentation import Group, orient, segment
from .sizing import size_wire
from .wiring import links_of


class GenerationCancelled(HarnessError):
    """The user cancelled; nothing was changed."""


@dataclass
class Finding:
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    object_id: str | None = None


@dataclass
class RegenReport:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    frozen: list[str] = field(default_factory=list)  # released harnesses left exactly as they are
    kept_locks: list[str] = field(
        default_factory=list
    )  # "connector.pin" that stayed where the user put it
    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    def plain_summary(self) -> str:
        """The same counts as `summary`, in a sentence for people (only what is not zero)."""

        def n(count: int, one: str, many: str) -> str:
            return f"{count} {one if count == 1 else many}"

        parts = []
        if self.added:
            parts.append(f"create {n(len(self.added), 'harness plan', 'harness plans')}")
        if self.changed:
            parts.append(f"update {n(len(self.changed), 'harness plan', 'harness plans')}")
        if self.removed:
            parts.append(f"remove {n(len(self.removed), 'harness plan', 'harness plans')}")
        if parts:
            text = "This will " + ", ".join(parts) + "."
        elif self.errors:
            text = "Nothing could be generated."
        else:
            text = "Nothing needs to change."
        if self.unchanged and parts:
            text += f" {n(len(self.unchanged), 'plan stays', 'plans stay')} as it is."
        if self.frozen:
            text += f" {n(len(self.frozen), 'released harness is', 'released harnesses are')} left untouched."
        if self.kept_locks:
            text += f" {n(len(self.kept_locks), 'locked pin stays', 'locked pins stay')} where you put it."
        if self.errors:
            shown = [f.message for f in self.errors[:3]]
            more = len(self.errors) - len(shown)
            text += f" {n(len(self.errors), 'problem needs', 'problems need')} your attention: "
            text += " ".join(shown) + (f" ... and {more} more." if more else "")
        return text

    def summary(self) -> str:
        return (
            f"{len(self.added)} added, {len(self.changed)} changed, {len(self.unchanged)} unchanged, "
            f"{len(self.removed)} removed, {len(self.frozen)} frozen (released); "
            f"{len(self.kept_locks)} locked pin(s) kept"
        )


@dataclass
class GenerationPlan:
    ops: list[Op]
    report: RegenReport
    record: GenerationRecord
    harnesses: dict[str, Harness]

    @property
    def empty(self) -> bool:
        """True if applying the plan would change nothing but (possibly) the record and the plan
        has no error to show: a plan whose only result is an error is not "up to date"."""
        return all(isinstance(op, SetGeneration) for op in self.ops) and not self.report.errors


# ---- inputs and status ---------------------------------------------------------------------------


def input_hash(project: Project) -> str:
    """Hash of everything generation reads. Outputs (generated pins, wires) are excluded."""

    def dump(objs: Any) -> list[object]:
        return [o.model_dump(mode="json") for o in sorted(objs, key=lambda x: x.id)]

    boxes = []
    for c in sorted(project.connectors.values(), key=lambda x: x.id):
        d = c.model_dump(mode="json")
        d["pins"] = [
            {
                **p.model_dump(mode="json"),
                "interface_id": None,
                "signal": p.signal if (p.locked or p.fixed or p.interface_id is None) else None,
            }
            for p in c.pins
        ]
        boxes.append(d)
    generated = [h for h in project.harnesses.values() if h.generated]
    payload = {
        "units": dump(project.units.values()),
        "interfaces": dump(project.interfaces.values()),
        "interface_types": dump(project.interface_types.values()),
        "parts": dump(project.parts.values()),
        "zones": list(project.zones),
        "config": {n: c.model_dump(mode="json") for n, c in sorted(project.config.items())},
        "box_connectors": boxes,
        "locked_wires": sorted(
            (w.model_dump(mode="json") for h in generated for w in h.wires if w.locked),
            key=lambda d: d["id"],
        ),
        "segment_lengths": {
            h.id: sorted((s.id, s.length_m) for s in h.segments) for h in generated
        },
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def generation_status(project: Project) -> str:
    """ "none" (never generated), "current" or "stale" (the model changed since)."""
    if project.generation is None:
        return "none"
    return "current" if project.generation.input_hash == input_hash(project) else "stale"


# ---- helpers ---------------------------------------------------------------------------------------


def _opposite(gender: str) -> Any:
    return {"male": "female", "female": "male"}.get(gender, "unspecified")


def _cfg(project: Project, name: str) -> dict[str, object]:
    c = project.config.get(name)
    return dict(c.values) if c is not None else {}


def _num(v: object) -> float | None:
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None


def _whole(v: object, low: int, high: int | None = None) -> bool:
    x = _num(v)
    return x is not None and math.isfinite(x) and x == int(x) and low <= x <= (high or math.inf)


def _checked_config(
    project: Project, report: RegenReport
) -> tuple[dict[str, object], dict[str, object]]:
    """The generation and derating values, with every invalid one reported as an error finding and
    left out, so it counts as unset (the result is "pending"; no value is made up from it)."""
    values = {"generation": _cfg(project, "generation"), "derating": _cfg(project, "derating")}
    gen = values["generation"]

    def bad(key: str, why: str) -> None:
        msg = f"config/generation.json: {key} {why}."
        report.findings.append(Finding("error", "config_invalid", msg))
        gen.pop(key, None)

    for issue in configcheck.validate(project):
        report.findings.append(Finding("error", "config_invalid", issue.message))
        file, _dot, key = (issue.object_id or "").partition(".")
        values.get(file, {}).pop(key, None)
    if gen.get("power_return_gap_pins") is not None and not _whole(gen["power_return_gap_pins"], 0):
        bad("power_return_gap_pins", "must be a whole number of 0 or more")
    if gen.get("default_gauge_awg") is not None and not _whole(gen["default_gauge_awg"], 0, 40):
        bad("default_gauge_awg", "must be a whole number from 0 to 40")
    colours = gen.get("wire_colour_by_signal")
    if colours is not None and not isinstance(colours, dict):
        bad(
            "wire_colour_by_signal",
            'must be a table of signal and colour, for example {"PWR": "red"}',
        )
    elif isinstance(colours, dict):
        kept = {}
        for sig in sorted(colours):
            try:
                ok = isinstance(colours[sig], str) and bool(
                    TypeAdapter(Name).validate_python(colours[sig])
                )
            except ValidationError:
                ok = False
            if ok:
                kept[sig] = colours[sig]
            else:
                msg = f"config/generation.json: wire_colour_by_signal for '{sig}' must be a colour name (text, 1 to 200 characters)."
                report.findings.append(Finding("error", "config_invalid", msg))
        gen["wire_colour_by_signal"] = kept
    return gen, values["derating"]


@dataclass
class _Ctx:
    project: Project
    namer: Namer
    gen: dict[str, object]
    der: dict[str, object]
    report: RegenReport
    prov: dict[str, list[str]]
    alloc: dict[str, Allocation]  # box connector id -> allocation
    failed: set[str]  # interface ids that could not be allocated
    next_n: int
    used_ids: set[str]

    def note(self, key: str, line: str) -> None:
        self.prov.setdefault(key, []).append(line)

    def finding(self, severity: str, code: str, message: str, obj: str | None = None) -> None:
        self.report.findings.append(Finding(severity, code, message, obj))


# ---- planning ------------------------------------------------------------------------------------


def plan_generation(
    project: Project,
    cancel: Callable[[], bool] | None = None,
    progress: Callable[[float, str], None] | None = None,
) -> GenerationPlan:
    def tick(frac: float, text: str) -> None:
        if cancel is not None and cancel():
            raise GenerationCancelled("Generation was cancelled. Nothing was changed.")
        if progress is not None:
            progress(frac, text)

    report = RegenReport()
    gen, der = _checked_config(project, report)
    seg = segment(project)
    namer = namer_for(project)
    prev = project.generation
    ctx = _Ctx(
        project, namer, gen, der, report, {}, {}, set(),
        max(1, prev.next_harness_number if prev else 1), set(project.harnesses),
    )  # fmt: skip
    for note in seg.notes:
        ctx.finding("warning", "segmentation", note)
    for s in seg.skipped:
        ctx.finding(
            s.severity,
            "interface_skipped",
            f"{s.interface_id} was not generated: {s.reason}.",
            s.interface_id,
        )

    old_by_key = {h.group_key: h for h in project.harnesses.values() if h.generated}
    frozen = {h.id for h in old_by_key.values() if h.status == "released"}
    frozen_ifaces = {i for h in old_by_key.values() if h.id in frozen for i in h.interfaces}
    frozen_ifaces |= {
        w.interface_id
        for h in project.harnesses.values()
        if not h.generated
        for w in h.wires
        if w.interface_id
    }  # manual harnesses own their pins
    tick(0.02, "Segmenting")

    frozen_owned = {
        iid: h.id for h in old_by_key.values() if h.id in frozen for iid in carried_interfaces(h)
    }
    live: list[Group] = []
    for g in seg.groups:
        if old_by_key.get(g.key) and old_by_key[g.key].id in frozen:
            continue
        # an interface a released harness already carries must not be wired a second time, even
        # when a change (redundancy, segmentation mode) moved it into a different group
        mine = tuple(i for i in g.interface_ids if i not in frozen_owned)
        for iid in g.interface_ids:
            if iid in frozen_owned:
                ctx.finding(
                    "warning",
                    "frozen_changed",
                    f"{iid} is carried by {frozen_owned[iid]}, which is released, so it was not wired again. A new revision of {frozen_owned[iid]} is needed.",
                    iid,
                )
        if mine:
            live.append(replace(g, interface_ids=mine))
    _allocate_pins(ctx, live, frozen_ifaces, tick)

    new_harnesses: dict[str, Harness] = {}
    for n, group in enumerate(live):
        tick(0.2 + 0.7 * n / max(1, len(live)), f"Building {group.label}")
        h = _build_harness(ctx, group, old_by_key.get(group.key))
        if h is not None:
            new_harnesses[h.id] = h

    # report: frozen, removed, added/changed/unchanged
    for g in seg.groups:
        old = old_by_key.get(g.key)
        if old is not None and old.id in frozen:
            report.frozen.append(old.id)
            if tuple(sorted(old.interfaces)) != tuple(sorted(g.interface_ids)):
                ctx.finding(
                    "warning",
                    "frozen_changed",
                    f"{old.id} is released, so it was not updated although its interfaces changed. A new revision is needed.",
                    old.id,
                )
    kept_keys = {g.key for g in seg.groups}
    for old in old_by_key.values():
        if old.id in frozen and old.group_key not in kept_keys:
            report.frozen.append(old.id)
            ctx.finding(
                "warning",
                "frozen_orphan",
                f"{old.id} is released but its interfaces no longer exist; it was kept.",
                old.id,
            )
    report.frozen = sorted(set(report.frozen))
    ops: list[Op] = []
    for old in sorted(old_by_key.values(), key=lambda x: x.id):
        if old.id not in new_harnesses and old.id not in frozen:
            report.removed.append(old.id)
            ops.append(Delete("harnesses", old.id))
    for hid in sorted(new_harnesses):
        h = new_harnesses[hid]
        existing = project.harnesses.get(hid)
        if existing is None:
            report.added.append(hid)
        elif existing != h:
            report.changed.append(hid)
        else:
            report.unchanged.append(hid)
        if existing != h:
            ops.append(Put("harnesses", h))
    ops += _connector_ops(ctx, frozen_ifaces)
    report.kept_locks = sorted(
        f"{c.id}.{p.id}"
        for c in project.connectors.values()
        for p in c.pins
        if p.locked and p.signal
    )
    tick(0.95, "Recording provenance")
    scratch = clone_with(project, ops)
    kept_prov = _frozen_provenance(project, old_by_key, frozen, frozen_ifaces)
    provenance = {**kept_prov, **ctx.prov}
    record = GenerationRecord(
        input_hash=input_hash(scratch),
        generator_version=__version__,
        next_harness_number=ctx.next_n,
        placeholders_used=sorted(n for n, c in project.config.items() if c.placeholder),
        provenance={k: provenance[k] for k in sorted(provenance)},
    )
    if project.generation != record:
        ops.append(SetGeneration(record))
    for w in namer.warnings:  # after the names were made: a template can fail while it is used
        ctx.finding(
            "warning", "naming", f"The naming template '{w}' is not valid; the default was used."
        )
    report.findings.sort(
        key=lambda f: (
            {"error": 0, "warning": 1, "info": 2}[f.severity],
            f.code,
            f.object_id or "",
            f.message,
        )
    )
    return GenerationPlan(ops, report, record, new_harnesses)


def _frozen_provenance(
    project: Project,
    old_by_key: dict[str, Harness],
    frozen: set[str],
    frozen_ifaces: set[str],
) -> dict[str, list[str]]:
    """Released harnesses are not regenerated, so the earlier explanation of their wires, pins and
    connectors is carried over; dropping it would make 'Why is it like this?' go blank."""
    prev = project.generation.provenance if project.generation else {}
    ids: set[str] = set()
    for h in old_by_key.values():
        if h.id in frozen:
            ids |= {h.id} | {c.id for c in h.connectors} | {w.id for w in h.wires}
    pins = {
        f"pin:{c.id}.{pin.id}"
        for c in project.connectors.values()
        for pin in c.pins
        if pin.interface_id in frozen_ifaces
    }
    return {
        k: v
        for k, v in prev.items()
        if k in pins or (k.split(":", 1)[-1] in ids and not k.startswith("pin:"))
    }


def _allocate_pins(
    ctx: _Ctx, groups: list[Group], frozen_ifaces: set[str], tick: Callable[[float, str], None]
) -> None:
    p = ctx.project
    requests: dict[str, list[Request]] = {}
    for g in groups:
        for iid in g.interface_ids:
            i = p.interfaces[iid]
            for e in i.endpoints:
                if e.connector_id is None:  # filtered out by segmentation already
                    continue
                requests.setdefault(e.connector_id, []).append(
                    Request(iid, p.interface_types[i.type_id])
                )
    gap = int(_num(ctx.gen.get("power_signal_gap_pins")) or 0)
    if ctx.gen.get("power_signal_gap_pins") is None:
        ctx.note("rules", "pin-allocation: power-to-signal pin gap is a placeholder (0 used)")
    ret_gap = int(_num(ctx.gen.get("power_return_gap_pins")) or 0)
    for k, cid in enumerate(sorted(requests)):
        tick(0.05 + 0.15 * k / max(1, len(requests)), f"Allocating pins of {cid}")
        box = p.connectors[cid]
        previous = {
            (pin.interface_id, pin.signal): pin.id
            for pin in box.pins
            if pin.interface_id and pin.signal and not pin.locked
        }

        # pins that must stay: locked, frozen-owned, or typed in by a person without a lock
        def keep(pin: Pin) -> Pin:
            if pin.fixed:  # a fixed pin is free for its signal unless a released harness uses it
                return (
                    evolve(pin, locked=True)
                    if pin.interface_id in frozen_ifaces
                    else evolve(pin, interface_id=None)
                )
            if (
                pin.locked
                or pin.interface_id in frozen_ifaces
                or (pin.signal and pin.interface_id is None)
            ):
                return evolve(pin, locked=True)
            return pin

        pinned = [keep(pin) for pin in box.pins]
        work = evolve(box, pins=pinned)
        held = {
            (pin.interface_id, pin.signal): pin.id
            for pin in box.pins
            if pin.locked
            and pin.interface_id
            and pin.signal
            and pin.interface_id not in frozen_ifaces
        }
        res = allocate(
            work,
            requests[cid],
            {k2: v for k2, v in previous.items() if k2[0] not in frozen_ifaces},
            gap,
            held,
            ret_gap,
        )
        ctx.alloc[cid] = res
        for iid, msg in res.errors:
            ctx.failed.add(iid)
            ctx.finding("error", "pin_allocation", f"{iid}: {msg}.", iid)
        for iid, msg in res.warnings:
            ctx.finding("warning", "pin_adjacency", f"{iid}: {msg}.", iid)


def _connector_ops(ctx: _Ctx, frozen_ifaces: set[str]) -> list[Op]:
    """Box connectors whose pin assignments changed (generated assignments are rewritten)."""
    ops: list[Op] = []
    p = ctx.project
    touched = set(ctx.alloc) | {
        c.id for c in p.connectors.values() if any(pin.interface_id for pin in c.pins)
    }
    for cid in sorted(touched):
        box = p.connectors[cid]
        res = ctx.alloc.get(cid)
        assigned = {}
        if res is not None:
            for (iid, sig), pid in res.pins.items():
                if iid not in ctx.failed:
                    assigned[pid] = (iid, sig)
        pins: list[Pin] = []
        for pin in box.pins:
            if pin.fixed:
                if pin.interface_id in frozen_ifaces:
                    pins.append(pin)
                elif pin.locked:  # the person's choice stays, whatever the plan says
                    if pin.interface_id is not None and pin.interface_id not in p.interfaces:
                        pin = evolve(pin, interface_id=None)  # its interface is gone
                    pins.append(pin)
                elif pin.id in assigned:
                    pins.append(evolve(pin, interface_id=assigned[pin.id][0]))
                    for line in res.reasons.get(pin.id, []) if res else []:
                        ctx.note(f"pin:{cid}.{pin.id}", line)
                else:
                    pins.append(evolve(pin, interface_id=None) if pin.interface_id else pin)
                continue
            if (
                pin.locked
                or pin.interface_id in frozen_ifaces
                or (pin.signal and pin.interface_id is None)
            ):
                if pin.interface_id is not None and pin.interface_id not in p.interfaces:
                    pin = evolve(
                        pin, interface_id=None
                    )  # its interface is gone; the pin stays locked
                pins.append(pin)
            elif pin.id in assigned:
                iid, sig = assigned[pin.id]
                pins.append(evolve(pin, signal=sig, interface_id=iid))
                for line in res.reasons.get(pin.id, []) if res else []:
                    ctx.note(f"pin:{cid}.{pin.id}", line)
            elif pin.interface_id is not None or pin.signal is not None:
                pins.append(evolve(pin, signal=None, interface_id=None))
            else:
                pins.append(pin)
        if pins != box.pins:
            ops.append(Put("connectors", evolve(box, pins=pins)))
    return ops


def _pin_of(ctx: _Ctx, connector_id: str, interface_id: str, signal: str) -> str | None:
    res = ctx.alloc.get(connector_id)
    return res.pins.get((interface_id, signal)) if res else None


def _build_harness(ctx: _Ctx, group: Group, old: Harness | None) -> Harness | None:
    p = ctx.project
    ifaces = [
        i for iid in group.interface_ids if iid not in ctx.failed for i in [p.interfaces[iid]]
    ]
    if not ifaces:
        return None
    zones = None
    if group.mode == "per_zone_pair":
        zones = group.zones
    start_n = ctx.next_n
    hid = old.id if old else _new_harness_id(ctx)
    ends: dict[str, list[str]] = {"X": [], "Y": []}
    oriented: dict[str, tuple[str, str]] = {}
    for i in ifaces:
        x, y = orient(p, i, group.mode, zones)
        oriented[i.id] = (x.connector_id or "", y.connector_id or "")
        ends["X"].append(x.connector_id or "")
        ends["Y"].append(y.connector_id or "")
    ends = {k: sorted(set(v)) for k, v in ends.items()}
    old_cables = {c.mates_with: c for c in (old.connectors if old else []) if c.mates_with}
    used_cables = {c.id for c in old_cables.values()}
    cables: dict[str, Connector] = {}
    n = 1
    for side in ("X", "Y"):
        for box_id in ends[side]:
            if box_id in cables:
                continue
            box = p.connectors[box_id]
            if box_id in old_cables:
                cid = old_cables[box_id].id
            else:
                n, cid = _first_free(
                    ctx, "cable_connector", n, lambda k: ctx.namer.cable_connector(hid, k),
                    used_cables, ctx.used_ids,
                )  # fmt: skip
                used_cables.add(cid)
            part = p.parts.get(box.part_id)
            mate = part.mates_with if part is not None and part.mates_with else box.part_id
            if mate not in p.parts:
                ctx.finding(
                    "warning",
                    "no_mating_part",
                    f"{box.part_id} has no mating part in the library; {box_id}'s cable end uses the same part.",
                    box_id,
                )
                mate = box.part_id
            cables[box_id] = Connector(
                id=cid, name=cid.rsplit("-", 1)[-1], role="cable", part_id=mate, gender=_opposite(box.gender if box.gender != "unspecified" else part_gender(part)),
                keying=box.keying, mates_with=box_id, pins=[Pin(id=pin.id, contact_size=pin.contact_size, termination=pin.termination) for pin in box.pins],
            )  # fmt: skip
            ctx.note(
                f"connector:{cid}",
                f"mating: cable end for {box_id} ({box.unit_id}); part {mate} mates with {box.part_id}",
            )
    # ---- routing: branch points and segments, keeping user-entered lengths
    old_len = {(s.from_node, s.to_node): s.length_m for s in (old.segments if old else [])}
    branches: list[BranchPoint] = []
    segments: list[Segment] = []
    end_node: dict[str, str] = {}
    for k, side in enumerate(("X", "Y"), start=1):
        conns = [cables[b].id for b in ends[side]]
        if len(conns) == 1:
            end_node[side] = conns[0]
        else:
            bid = ctx.namer.branch(hid, k)
            branches.append(BranchPoint(id=bid, name=f"Branch {side}"))
            end_node[side] = bid
    pairs = [(end_node["X"], end_node["Y"])]
    for side in ("X", "Y"):
        if end_node[side] not in {cables[b].id for b in ends[side]}:
            pairs += [(cables[b].id, end_node[side]) for b in ends[side]]
    for sn, (a, b) in enumerate(pairs, start=1):
        segments.append(
            Segment(
                id=ctx.namer.segment(hid, sn), from_node=a, to_node=b, length_m=old_len.get((a, b))
            )
        )
    # A saved project lists the parts of a harness sorted by ID as text (L1, L10, L11, ..., L2, and
    # S10 before S2). Generating in the same order keeps a reloaded harness equal to a regenerated
    # one; a harness with ten or more segments or shields was reported as changed on every
    # generation.
    segments.sort(key=lambda s: s.id)
    # ---- wires
    old_wires = {}
    for w in old.wires if old else []:
        src = next(
            (c.mates_with for c in (old.connectors if old else []) if c.id == w.from_connector), ""
        )
        old_wires[f"{w.interface_id}|{w.signal}|{src}"] = w
    used_wires = {w.id for w in old_wires.values()}
    wire_n = 1
    wires: list[Wire] = []
    skeleton = Harness(
        id=hid,
        name=group.label,
        connectors=list(cables.values()),
        branch_points=branches,
        segments=segments,
    )
    loop = _num(ctx.gen.get("service_loop_m"))
    if ctx.gen.get("service_loop_m") is None:
        ctx.note(
            f"harness:{hid}",
            "lengths: service loop is a placeholder (0 used); lengths exclude service loops",
        )
    bundle_wires = sum(len(links_of(p.interface_types[i.type_id])[0]) for i in ifaces)
    for i in ifaces:
        itype = p.interface_types[i.type_id]
        links, notes = links_of(itype)
        for note in notes:
            ctx.finding("warning", "wiring", note, i.id)
        bx, by = oriented[i.id]
        part_id = _wire_part(ctx, itype.construction, i.id)
        for link in links:
            src_box, dst_box = (bx, by) if link.from_end == "X" else (by, bx)
            pin_src = _pin_of(ctx, src_box, i.id, link.from_signal)
            pin_dst = _pin_of(ctx, dst_box, i.id, link.to_signal)
            if pin_src is None or pin_dst is None:
                continue
            key = f"{i.id}|{link.label}|{src_box}"
            prev_w = old_wires.get(key)
            if prev_w is not None:
                wid = prev_w.id
            else:
                wire_n, wid = _first_free(
                    ctx, "wire", wire_n, lambda k: ctx.namer.wire(hid, k), used_wires, ctx.used_ids
                )
                used_wires.add(wid)
            length = path_length(skeleton, cables[src_box].id, cables[dst_box].id)
            if length is not None and loop is not None:
                length += 2 * loop
            wire = Wire(
                id=wid, signal=link.label, from_connector=cables[src_box].id, from_pin=pin_src, to_connector=cables[dst_box].id,
                to_pin=pin_dst, part_id=part_id, interface_id=i.id, length_m=length,
            )  # fmt: skip
            if prev_w is not None and prev_w.locked:
                wire = evolve(
                    prev_w,
                    from_pin=pin_src,
                    to_pin=pin_dst,
                    from_connector=wire.from_connector,
                    to_connector=wire.to_connector,
                    signal=link.label,
                    interface_id=i.id,
                )
                ctx.note(
                    f"wire:{wid}",
                    "override: the wire is locked, so its gauge, part, colour and length were kept",
                )
            else:
                wire = _size(ctx, wire, i, itype.category, bundle_wires)
            wires.append(wire)
            ctx.note(
                f"wire:{wid}",
                f"wiring: {link.label} of {i.id} connects {src_box} pin {pin_src} to {dst_box} pin {pin_dst} ({link.from_end} drives)",
            )
    if not wires:
        ctx.finding("warning", "no_wires", f"{group.label} produced no wires.")
        if old is None:  # give the number back, or every run would use up one more
            ctx.next_n = start_n
            ctx.used_ids.discard(hid)
        return None
    wires.sort(key=lambda w: w.id)
    shields = _shields(ctx, hid, ifaces, wires, old)
    interfaces = sorted(i.id for i in ifaces)
    ctx.note(
        f"harness:{hid}",
        f"segmentation: {', '.join(interfaces)} share a harness because they have the same {_describe(group)} and chain ({group.chain})",
    )
    built = Harness(
        id=hid, name=group.label, revision=old.revision if old else "A", status=old.status if old else "draft",
        connectors=sorted(cables.values(), key=lambda c: c.id), wires=sorted(wires, key=lambda x: x.id),
        shields=sorted(shields, key=lambda x: x.id), branch_points=sorted(branches, key=lambda x: x.id),
        segments=segments,
        generated=True, group_key=group.key, interfaces=interfaces, notes=old.notes if old else "",
        author=old.author if old else None, checker=old.checker if old else None,
        approver=old.approver if old else None, released_on=old.released_on if old else None,
    )  # fmt: skip
    if old is not None and old.status == "in_review":
        meta = {"status", "checker", "approver", "released_on", "author"}
        if built.model_dump(exclude=meta) != old.model_dump(exclude=meta):
            ctx.finding(
                "info",
                "review_reset",
                f"{hid} changed while in review, so it is a draft again and needs a new review.",
                hid,
            )
            built = evolve(built, status="draft", checker=None)
    return built


def _describe(group: Group) -> str:
    return {
        "per_connector_pair": "pair of unit connectors",
        "per_unit_pair": "pair of units",
        "per_zone_pair": "pair of zones",
    }[group.mode]


def _first_free(
    ctx: _Ctx, kind: str, start: int, make: Callable[[int], str], *taken: set[str]
) -> tuple[int, str]:
    """The first number from `start` whose name is in none of `taken`, and that name. A template
    that cannot give a free name within as many tries as there are names in use (it repeats
    itself) is dropped for the default pattern, which always can."""
    tries = 1 + sum(len(t) for t in taken)
    for n in range(start, start + tries):
        name = make(n)
        if not any(name in t for t in taken):
            return n, name
    ctx.namer.use_default(kind)
    n = start
    while any(make(n) in t for t in taken):
        n += 1
    return n, make(n)


def _new_harness_id(ctx: _Ctx) -> str:
    n, hid = _first_free(ctx, "harness", ctx.next_n, ctx.namer.harness, ctx.used_ids)
    ctx.next_n = n + 1
    ctx.used_ids.add(hid)
    return hid


def _wire_part(ctx: _Ctx, construction: str, iid: str) -> str | None:
    table = ctx.gen.get("wire_part_by_construction")
    part = table.get(construction) if isinstance(table, dict) else None
    if (
        not isinstance(part, str)
        or part not in ctx.project.parts
        or ctx.project.parts[part].category != "wire"
    ):
        ctx.finding(
            "warning",
            "wire_part",
            f"No wire part is configured for {construction} wires (generation.wire_part_by_construction).",
            iid,
        )
        return None
    return part


def _size(
    ctx: _Ctx, wire: Wire, i: InterfaceInstance, category: str, bundle_wires: int | None = None
) -> Wire:
    conductors = 2 if category in ("power", "ground") else 1
    sizing = size_wire(
        ctx.der,
        ctx.gen,
        current_a=i.max_current_a,
        length_m=wire.length_m,
        path_conductors=conductors,
        bundle_wires=bundle_wires,
    )
    for line in sizing.notes:
        ctx.note(f"gauge:{wire.id}", f"wire-sizing: {line}")
    if sizing.pending:
        ctx.note(
            f"gauge:{wire.id}", f"wire-sizing: undecided, waiting for {', '.join(sizing.pending)}"
        )
    if sizing.error:
        ctx.finding("error", "wire_sizing", f"{wire.id}: {sizing.error}.", wire.id)
    out = wire if sizing.awg is None else evolve(wire, gauge_awg=sizing.awg)
    if out.gauge_awg is None and i.max_current_a is None:
        # no current to size for: the interface type's default, else the general default
        itype = ctx.project.interface_types.get(i.type_id)
        default = itype.default_gauge_awg if itype and itype.default_gauge_awg is not None else None
        if default is None:
            general = _num(ctx.gen.get("default_gauge_awg"))
            default = int(general) if general is not None and general == int(general) else None
        if default is not None:
            out = evolve(out, gauge_awg=default)
            ctx.note(
                f"gauge:{wire.id}",
                f"wire-sizing: {i.type_id} has no current to size for, so the default gauge AWG {default} from the configuration was used",
            )
    colours = ctx.gen.get("wire_colour_by_signal")  # the owner's own rule; absent: no colour
    if isinstance(colours, dict) and out.colour is None and out.signal:
        # a wire between two different signal names is labelled "TX+/RX+": the first one counts
        key = next((k for k in (out.signal, *out.signal.split("/")) if k in colours), None)
        if key is not None:
            out = evolve(out, colour=str(colours[key]))
    _check_contacts(ctx, out, i)
    return out


def _check_contacts(ctx: _Ctx, wire: Wire, i: InterfaceInstance) -> None:
    """Current against the contact rating of both box connectors (rating and factor from config)."""
    current = i.max_current_a
    factor = _num(ctx.der.get("contact_current_factor"))
    key = str(ctx.der.get("contact_rating_key", "contact_current_a"))
    if current is None:
        return
    for end in i.endpoints:
        box = ctx.project.connectors.get(end.connector_id or "")
        part = ctx.project.parts.get(box.part_id) if box else None
        rating = part.ratings.get(key) if part else None
        if rating is None or factor is None:
            ctx.note(
                f"gauge:{wire.id}",
                f"contact-check: not done for {end.connector_id} (contact rating or derating factor is a placeholder)",
            )
        elif current > rating * factor:
            ctx.finding(
                "error",
                "contact_overload",
                f"{wire.id}: {current:g} A exceeds the derated contact rating of {end.connector_id}.",
                wire.id,
            )


def _shields(
    ctx: _Ctx, hid: str, ifaces: list[InterfaceInstance], wires: list[Wire], old: Harness | None
) -> list[ShieldGroup]:
    p = ctx.project
    ends = [ctx.gen.get("shield_end_a"), ctx.gen.get("shield_end_b")]
    valid = {"backshell_360", "pigtail", "floating"}
    a, b = (cast(Any, e if isinstance(e, str) and e in valid else "floating") for e in ends)
    if ends[0] is None or ends[1] is None:
        ctx.note(
            f"harness:{hid}",
            "shielding: shield termination is a placeholder (floating used); the grounding concept decides it",
        )
    out: list[ShieldGroup] = []
    n = 1

    def add(kind: str, members: list[Wire]) -> None:
        nonlocal n
        if members:
            out.append(
                ShieldGroup(
                    id=ctx.namer.shield(hid, n),
                    kind=cast(Any, kind),
                    wire_ids=sorted(w.id for w in members),
                    end_a=a,
                    end_b=b,
                )
            )
            n += 1

    for i in ifaces:
        t = p.interface_types[i.type_id]
        mine = [w for w in wires if w.interface_id == i.id]
        if t.construction in ("single",):
            continue
        if t.construction == "coax":
            for w in mine:
                add("coax", [w])
            continue
        if t.construction == "quad":
            add("quad", mine)
            continue
        pair_of = {
            s.name: (s.pair or ("power" if t.category in ("power", "ground") else None))
            for s in t.signals
        }
        groups: dict[str, list[Wire]] = {}
        for w in mine:
            src = w.signal.split("/")[0] if w.signal else ""
            name = pair_of.get(src)
            if name is not None:
                groups.setdefault(f"{name}|{w.from_connector}", []).append(w)
        kind = "shielded_pair" if t.shielding == "per_pair" else "twisted_pair"
        for key in sorted(groups):
            add(kind, groups[key])
        if t.shielding == "overall":
            add("overall_shield", mine)
    return out


# ---- convenience -----------------------------------------------------------------------------------


def generate_project(project: Project) -> GenerationPlan:
    """Plan, apply (not undoable) and verify. For scripts and tests; the GUI uses History."""
    from harness_design_studio.core.commands import apply_ops

    plan = plan_generation(project)
    apply_ops(project, plan.ops)
    return plan
