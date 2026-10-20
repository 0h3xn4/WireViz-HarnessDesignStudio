"""The design rules. One function per rule, registered in `RULES` (order = report order).

Rules that need engineering numbers (derating, grounding concept, EMC classes, spare pins) check
nothing while those configuration values are placeholders; `unchecked-config` then says so, so a
clean report can never be mistaken for a passed check.
"""

import hashlib
from collections import Counter, defaultdict
from collections.abc import Iterator

from harness_design_studio.core.configcheck import validate as validate_config
from harness_design_studio.core.generate.lengths import loop_segments, wire_length
from harness_design_studio.core.generate.sizing import (
    ampacity_table,
    bundle_k,
    derated_limit,
    exceeds,
    voltage_drop_v,
)
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.model import Connector, Harness, InterfaceInstance, Project, Wire
from harness_design_studio.core.vcs.consistency import release_integrity
from harness_design_studio.core.verify import passthrough_signals

from .base import Hit, Rule, cfg, flag, number
from .standard_rules import STANDARD_RULES
from .standard_rules import unchecked as standard_unchecked

# ---- helpers ---------------------------------------------------------------------------------------


def _wire_interfaces(project: Project, h: Harness) -> set[str]:
    return {w.interface_id for w in h.wires if w.interface_id} | set(h.interfaces)


def _end_signal(project: Project, h: Harness, connector_id: str, pin_id: str) -> str | None:
    """Signal at a wire end: from the mated box connector's pin, else the pin's own signal."""
    cable = next((c for c in h.connectors if c.id == connector_id), None)
    if cable is None:
        return None
    box = project.connectors.get(cable.mates_with or "")
    for conn in (box, cable):
        pin = next((p for p in conn.pins if p.id == pin_id), None) if conn else None
        if pin is not None and pin.signal:
            return pin.signal
    return None


def _has_harnesses(project: Project) -> bool:
    return bool(project.harnesses)


# ---- structure -------------------------------------------------------------------------------------


def _duplicate_ids(project: Project) -> Iterator[Hit]:
    seen = Counter(c.id for c in project.connectors.values())
    seen.update(c.id for h in project.harnesses.values() for c in h.connectors)
    for cid, n in sorted(seen.items()):
        if n > 1:
            yield Hit(cid, f"The connector ID {cid} is used {n} times")
    wires = Counter(w.id for h in project.harnesses.values() for w in h.wires)
    for wid, n in sorted(wires.items()):
        if n > 1:
            yield Hit(wid, f"The wire ID {wid} is used {n} times")
    for c in sorted(project.connectors.values(), key=lambda x: x.id):
        for pid, n in sorted(Counter(p.id for p in c.pins).items()):
            if n > 1:
                yield Hit(f"{c.id}.{pid}", f"Connector {c.id} has pin {pid} {n} times")


def _dangling_wires(project: Project) -> Iterator[Hit]:
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        pins = {c.id: {p.id for p in c.pins} for c in h.connectors}
        for w in h.wires:
            for end, cid, pid in (
                ("from", w.from_connector, w.from_pin),
                ("to", w.to_connector, w.to_pin),
            ):
                if cid not in pins:
                    yield Hit(
                        w.id,
                        f"Wire {w.id} ends on connector {cid}, which is not in {h.id}",
                        key=f"{w.id}.{end}",
                    )
                elif pid not in pins[cid]:
                    yield Hit(
                        w.id,
                        f"Wire {w.id} ends on pin {pid} of {cid}, which does not exist",
                        key=f"{w.id}.{end}",
                    )


def _segment_loop(project: Project) -> Iterator[Hit]:
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        loops = loop_segments(h)
        if loops:
            yield Hit(
                h.id,
                f"The routing segments of {h.id} form a loop (segment {loops[0]} closes it): a wire "
                "would have two possible routes, so its length is not defined and is left unknown",
            )


def _signal_unassigned(project: Project) -> Iterator[Hit]:
    if not _has_harnesses(project):
        return
    routed = {i for h in project.harnesses.values() for i in _wire_interfaces(project, h)}
    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        if i.id not in routed or i.type_id not in project.interface_types:
            continue
        for e in i.endpoints:
            conn = project.connectors.get(e.connector_id or "")
            if conn is None:
                continue
            have = {p.signal for p in conn.pins if p.interface_id == i.id}
            for s in project.interface_types[i.type_id].signals:
                if s.name not in have:
                    yield Hit(
                        f"{i.id}.{conn.id}.{s.name}",
                        f"Signal {s.name} of {i.id} has no pin on {conn.id}",
                        "Regenerate harnesses",
                    )


def _floating_pins(project: Project) -> Iterator[Hit]:
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        used = {(w.from_connector, w.from_pin) for w in h.wires}
        used |= {(w.to_connector, w.to_pin) for w in h.wires}
        for c in h.connectors:
            for p in c.pins:
                if p.signal and (c.id, p.id) not in used:
                    yield Hit(
                        f"{c.id}.{p.id}",
                        f"Pin {p.id} of {c.id} is named {p.signal} but no wire is attached",
                    )


def _pin_shared(project: Project) -> Iterator[Hit]:
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        on_pin: dict[tuple[str, str], list[str]] = {}
        for w in h.wires:
            on_pin.setdefault((w.from_connector, w.from_pin), []).append(w.id)
            on_pin.setdefault((w.to_connector, w.to_pin), []).append(w.id)
        for (cid, pid), ids in sorted(on_pin.items()):
            if len(ids) > 1:
                yield Hit(
                    h.id,  # the harness is found at once; a pin ID would be searched for among all wires
                    f"Pin {pid} of {cid} carries {len(ids)} wires ({', '.join(sorted(ids))})",
                    key=f"{h.id}.{cid}.{pid}",
                )


def _model_inconsistent(project: Project) -> Iterator[Hit]:
    for n, issue in enumerate(i for i in check_integrity(project) if i.severity != "error"):
        # one object can have several problems; the message tells them apart
        digest = hashlib.sha256(issue.message.encode()).hexdigest()[:6]
        yield Hit(
            issue.object_id or f"{issue.code}-{n}", issue.message,
            key=f"{issue.object_id or issue.code}.{issue.code}.{digest}",
        )  # fmt: skip


# ---- connectors ------------------------------------------------------------------------------------


def _mate_mismatch(project: Project) -> Iterator[Hit]:
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        for c in h.connectors:
            box = project.connectors.get(c.mates_with or "")
            if c.mates_with is None:
                continue
            if box is None:
                yield Hit(c.id, f"{c.id} should plug into {c.mates_with}, which does not exist")
                continue
            problems = []
            if {c.gender, box.gender} <= {"male", "female"} and c.gender == box.gender:
                problems.append(f"both are {c.gender}")
            part = project.parts.get(box.part_id)
            if part is not None and part.mates_with and part.mates_with != c.part_id:
                problems.append(
                    f"{c.part_id} is not the mating part ({part.mates_with}) of {box.part_id}"
                )
            if len(c.pins) != len(box.pins):
                problems.append(f"{len(c.pins)} pins against {len(box.pins)}")
            if c.keying != box.keying:
                problems.append("keying differs")
            if problems:
                yield Hit(c.id, f"{c.id} does not fit {box.id}: {'; '.join(problems)}")


def _lookalike(project: Project) -> Iterator[Hit]:
    groups: dict[tuple[str, str, str | None, str, int], list[Connector]] = defaultdict(list)
    in_use = {e.connector_id for i in project.interfaces.values() for e in i.endpoints}
    for c in project.connectors.values():
        if c.unit_id and c.id in in_use:  # unused connectors cannot be mis-mated
            groups[(c.unit_id, c.part_id, c.keying, c.gender, len(c.pins))].append(c)
    for (unit, part, _k, _g, _n), conns in sorted(
        groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or "", kv[0][3], kv[0][4])
    ):
        if len(conns) > 1:
            ids = sorted(c.id for c in conns)
            names = ", ".join(ids[:3]) + (f" and {len(ids) - 3} more" if len(ids) > 3 else "")
            yield Hit(
                ids[0],
                f"{names} on {unit} are identical ({part}, same keying) and could be plugged in the wrong place",
            )


def _unapproved_parts(project: Project) -> Iterator[Hit]:
    used: dict[str, set[str]] = defaultdict(set)
    for c in project.connectors.values():
        used[c.part_id].add(c.id)
    for h in project.harnesses.values():
        for c in h.connectors:
            used[c.part_id].add(c.id)
        for w in h.wires:
            if w.part_id:
                used[w.part_id].add(w.id)
    for pid in sorted(used):
        part = project.parts.get(pid)
        if part is None:
            yield Hit(pid, f"Part {pid} is used but is not in the parts list")
        elif part.approval != "approved":
            state = "rejected" if part.approval == "not_approved" else "not approved yet"
            yield Hit(pid, f"Part {pid} is {state} but is used ({len(used[pid])} place(s))")
        elif part.unverified:  # the release gate counts these too (unapproved_parts)
            yield Hit(
                pid,
                f"Part {pid} is marked as unverified example data but is used ({len(used[pid])} place(s))",
            )


# ---- signals ---------------------------------------------------------------------------------------


def _direction_conflict(project: Project) -> Iterator[Hit]:
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        for w in h.wires:
            i = project.interfaces.get(w.interface_id or "")
            itype = project.interface_types.get(i.type_id) if i else None
            if itype is None or not {"out", "in"} <= {s.direction for s in itype.signals}:
                continue  # one-directional types (analog, discrete) cannot be judged by direction
            dirs = {s.name: s.direction for s in itype.signals}
            na = _end_signal(project, h, w.from_connector, w.from_pin) or ""
            nb = _end_signal(project, h, w.to_connector, w.to_pin) or ""
            if na == nb and na in passthrough_signals(
                [(s.name, s.direction) for s in itype.signals]
            ):
                continue  # the verifier expects this wire straight through (an unpaired signal)
            a, b = dirs.get(na), dirs.get(nb)
            if a == b and a in ("out", "in"):
                what = (
                    "two outputs (driver against driver)"
                    if a == "out"
                    else "two inputs (nothing drives the wire)"
                )
                yield Hit(w.id, f"Wire {w.id} joins {what}")


# ---- ratings ---------------------------------------------------------------------------------------


def _contact_rating(project: Project, conn: Connector) -> float | None:
    key = str(cfg(project, "derating").get("contact_rating_key") or "contact_current_a")
    part = project.parts.get(conn.part_id)
    return part.ratings.get(key) if part else None


def _bundle_table_given(d: dict[str, object]) -> bool:
    """The table of bundle factors replaces the single factor (as in sizing)."""
    return isinstance(d.get("bundle_factor_by_count"), dict) and bool(
        d.get("bundle_factor_by_count")
    )


def _derated_limit_ready(project: Project) -> bool:
    d = cfg(project, "derating")
    return (
        ampacity_table(d.get("ampacity_a_by_awg")) is not None
        and (number(d.get("bundle_derating")) is not None or _bundle_table_given(d))
        and number(d.get("temperature_derating")) is not None
    )


def _current_over_contact(project: Project) -> Iterator[Hit]:
    factor = number(cfg(project, "derating").get("contact_current_factor"))
    if factor is None:
        return
    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        if i.max_current_a is None:
            continue
        for e in i.endpoints:
            conn = project.connectors.get(e.connector_id or "")
            rating = _contact_rating(project, conn) if conn else None
            if (
                conn is not None
                and rating is not None
                and exceeds(i.max_current_a, rating * factor)
            ):
                yield Hit(
                    f"{i.id}.{conn.id}",
                    f"{i.id} carries {i.max_current_a:g} A but contacts of {conn.id} allow {rating * factor:g} A after derating",
                )


def _wire_current_limit(project: Project, w: Wire, h: Harness | None = None) -> float | None:
    """Ampacity of the wire's gauge after derating. When the table of bundle factors is set it
    replaces the single factor, as in wire sizing, so the check and the sizing agree."""
    d = cfg(project, "derating")
    table = ampacity_table(d.get("ampacity_a_by_awg"))
    bundle, temp = number(d.get("bundle_derating")), number(d.get("temperature_derating"))
    by_count = d.get("bundle_factor_by_count")
    if isinstance(by_count, dict) and by_count and h is not None:
        bundle = bundle_k(by_count, len(h.wires))
    if table is None or bundle is None or temp is None or w.gauge_awg not in table:
        return None
    return derated_limit(table[w.gauge_awg], bundle, temp)


def _current_over_wire(project: Project) -> Iterator[Hit]:
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        for w in h.wires:
            i = project.interfaces.get(w.interface_id or "")
            limit = _wire_current_limit(project, w, h)
            if (
                i
                and i.max_current_a is not None
                and limit is not None
                and exceeds(i.max_current_a, limit)
            ):
                yield Hit(
                    w.id,
                    f"Wire {w.id} (AWG {w.gauge_awg}) carries {i.max_current_a:g} A but allows {limit:g} A after derating",
                )


def _voltage_drop(project: Project) -> Iterator[Hit]:
    limit = number(cfg(project, "derating").get("max_voltage_drop_v"))
    rho = number(cfg(project, "generation").get("conductor_resistivity_ohm_m"))
    if limit is None or rho is None:
        return
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        for w in h.wires:
            i = project.interfaces.get(w.interface_id or "")
            itype = project.interface_types.get(i.type_id) if i else None
            length = wire_length(h, w)
            if not (
                i and itype and i.max_current_a is not None and length and w.gauge_awg is not None
            ):
                continue
            if not 0 <= w.gauge_awg <= 40:  # a hand-edited gauge must not stop the whole check
                yield Hit(
                    w.id, f"Wire {w.id} has AWG {w.gauge_awg}, which is not a wire size (0 to 40)"
                )
                continue
            n = 2 if itype.category in ("power", "ground") else 1
            drop = voltage_drop_v(i.max_current_a, rho, length, w.gauge_awg, n)
            if exceeds(drop, limit):
                yield Hit(w.id, f"Wire {w.id} drops {drop:.3g} V, more than the {limit:g} V limit")


def _spare_pins(project: Project) -> Iterator[Hit]:
    fraction = number(cfg(project, "derating").get("spare_pin_fraction"))
    if fraction is None:
        return
    for c in sorted(project.connectors.values(), key=lambda x: x.id):
        if not c.pins or not any(p.interface_id for p in c.pins):
            continue
        spare = sum(1 for p in c.pins if p.interface_id is None and not p.signal)
        if exceeds(fraction * len(c.pins), spare):
            yield Hit(
                c.id,
                f"{c.id} has {spare} spare pin(s) of {len(c.pins)}, fewer than the required {fraction:.0%}",
            )


# ---- shields ---------------------------------------------------------------------------------------


def _shield_unterminated(project: Project) -> Iterator[Hit]:
    g = cfg(project, "generation")
    if g.get("shield_end_a") is None and g.get("shield_end_b") is None:
        return  # no grounding concept yet: "not checked" is reported instead
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        for s in h.shields:
            if s.kind == "twisted_pair":
                continue  # a twisted pair has no shield to terminate
            if s.end_a == "floating" and s.end_b == "floating":
                yield Hit(
                    f"{h.id}.{s.id}", f"Shield {s.id} in {h.id} is not connected at either end"
                )


def _shield_wrong_end(project: Project) -> Iterator[Hit]:
    g = cfg(project, "generation")
    want = (g.get("shield_end_a"), g.get("shield_end_b"))
    if None in want:
        return
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        for s in h.shields:
            if s.kind == "twisted_pair":
                continue  # a twisted pair has no shield to ground
            if (s.end_a, s.end_b) != want:
                yield Hit(
                    f"{h.id}.{s.id}",
                    f"Shield {s.id} in {h.id} is {s.end_a}/{s.end_b} but the grounding concept says {want[0]}/{want[1]}",
                )


# ---- segregation -----------------------------------------------------------------------------------


def _carried(project: Project, h: Harness) -> list[InterfaceInstance]:
    return [
        project.interfaces[i]
        for i in sorted(_wire_interfaces(project, h))
        if i in project.interfaces
    ]


def _chains_mixed(project: Project) -> Iterator[Hit]:
    if not flag(cfg(project, "segregation"), "forbid_nominal_with_redundant"):
        return
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        if {i.redundancy for i in _carried(project, h)} >= {"nominal", "redundant"}:
            yield Hit(h.id, f"{h.id} carries both nominal and redundant interfaces")
    for c in sorted(project.connectors.values(), key=lambda x: x.id):
        sides = {
            project.interfaces[p.interface_id].redundancy
            for p in c.pins
            if p.interface_id in project.interfaces
        }
        if {"nominal", "redundant"} <= sides:
            yield Hit(c.id, f"Connector {c.id} carries both nominal and redundant interfaces")


def _pyro_mixed(project: Project) -> Iterator[Hit]:
    if not flag(cfg(project, "segregation"), "forbid_pyro_with_other"):
        return

    def cats(ids: list[InterfaceInstance]) -> set[str]:
        return {
            project.interface_types[i.type_id].category
            for i in ids
            if i.type_id in project.interface_types
        }

    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        c = cats(_carried(project, h))
        if "pyro" in c and len(c) > 1:
            yield Hit(h.id, f"{h.id} mixes pyro (firing) lines with other interfaces")
    for conn in sorted(project.connectors.values(), key=lambda x: x.id):
        c = cats(
            [
                project.interfaces[p.interface_id]
                for p in conn.pins
                if p.interface_id in project.interfaces
            ]
        )
        if "pyro" in c and len(c) > 1:
            yield Hit(
                conn.id, f"Connector {conn.id} mixes pyro (firing) lines with other interfaces"
            )


def _category_pairs(project: Project) -> list[tuple[str, str]]:
    raw = cfg(project, "segregation").get("category_pairs_to_separate")
    pairs = (
        [tuple(p) for p in raw if isinstance(p, list) and len(p) == 2]
        if isinstance(raw, list)
        else []
    )
    return [(str(a), str(b)) for a, b in pairs]


def _category_mixed(project: Project) -> Iterator[Hit]:
    pairs = _category_pairs(project)
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        cats = {
            project.interface_types[i.type_id].category
            for i in _carried(project, h)
            if i.type_id in project.interface_types
        }
        for a, b in pairs:
            if a in cats and b in cats:
                yield Hit(
                    f"{h.id}.{a}+{b}",
                    f"{h.id} mixes {a} and {b} interfaces, which the project keeps apart",
                )


def _emc_pairs(project: Project) -> list[tuple[str, str]]:
    raw = cfg(project, "emc").get("conflicting_class_pairs")
    pairs = (
        [tuple(p) for p in raw if isinstance(p, list) and len(p) == 2]
        if isinstance(raw, list)
        else []
    )
    return [(str(a), str(b)) for a, b in pairs]


def _emc_mixed(project: Project) -> Iterator[Hit]:
    pairs = _emc_pairs(project)
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        classes = {
            project.interface_types[i.type_id].emc_class
            for i in _carried(project, h)
            if i.type_id in project.interface_types
        }
        for a, b in pairs:
            if a in classes and b in classes:
                yield Hit(f"{h.id}.{a}+{b}", f"{h.id} mixes EMC classes {a} and {b}")


def _config_invalid(project: Project) -> Iterator[Hit]:
    for issue in validate_config(project):
        yield Hit(issue.object_id or issue.code, issue.message)


def _released_modified(project: Project) -> Iterator[Hit]:
    for issue in release_integrity(project):
        yield Hit(issue.object_id or issue.code, issue.message)


# ---- what could not be checked ---------------------------------------------------------------------


def _carries_current(project: Project, w: Wire) -> bool:
    i = project.interfaces.get(w.interface_id or "")
    return i is not None and i.max_current_a is not None


def _current_gaps(project: Project, table: dict[int, float] | None) -> Iterator[Hit]:
    """Wires the current checks skipped for lack of a bundle factor or a gauge."""
    if table is None:
        return  # the placeholder note already says that no current limit was checked
    d = cfg(project, "derating")
    by_count = d.get("bundle_factor_by_count")
    if isinstance(by_count, dict) and by_count:
        short = [
            f"{h.id} ({len(h.wires)} wires)"
            for h in sorted(project.harnesses.values(), key=lambda x: x.id)
            if any(_carries_current(project, w) for w in h.wires)
            and bundle_k(by_count, len(h.wires)) is None
        ]
        if short:
            yield Hit(
                "bundle-factor",
                f"Wire and bundle current were not checked for {', '.join(short)}: the table of bundle factors has no entry for that many wires",
            )
    no_gauge = sorted(
        w.id
        for h in project.harnesses.values()
        for w in h.wires
        if w.gauge_awg is None and _carries_current(project, w)
    )
    if no_gauge:
        yield Hit(
            "wire-gauge",
            f"Wire current was not checked for {len(no_gauge)} wire(s) without a gauge (first: {no_gauge[0]})",
        )


def _voltage_drop_gaps(project: Project) -> Iterator[Hit]:
    """Wires the voltage-drop check skipped for lack of a gauge or a length."""
    limit = number(cfg(project, "derating").get("max_voltage_drop_v"))
    rho = number(cfg(project, "generation").get("conductor_resistivity_ohm_m"))
    if limit is None or rho is None:
        return  # the placeholder note already says that the check did not run
    no_gauge: list[str] = []
    no_length: list[str] = []
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        for w in h.wires:
            i = project.interfaces.get(w.interface_id or "")
            if not (i and i.type_id in project.interface_types and i.max_current_a is not None):
                continue
            if w.gauge_awg is None:
                no_gauge.append(w.id)
            if wire_length(h, w) is None:
                no_length.append(w.id)
    if no_gauge or no_length:
        parts = []
        if no_gauge:
            parts.append(f"{len(no_gauge)} wire(s) without a gauge (first: {no_gauge[0]})")
        if no_length:
            parts.append(f"{len(no_length)} wire(s) without a length (first: {no_length[0]})")
        yield Hit("voltage-drop-wires", f"Voltage drop was not checked for {' and '.join(parts)}")


def _unchecked(project: Project) -> Iterator[Hit]:
    d, g = cfg(project, "derating"), cfg(project, "generation")
    has_current = any(i.max_current_a is not None for i in project.interfaces.values())
    if has_current and (
        number(d.get("contact_current_factor")) is None or not _derated_limit_ready(project)
    ):
        yield Hit(
            "derating",
            "Current and derating limits were not checked: the derating values are still placeholders",
        )
    table = ampacity_table(d.get("ampacity_a_by_awg"))
    if table is not None:
        missing_gauges = sorted(
            {
                w.gauge_awg
                for h in project.harnesses.values()
                for w in h.wires
                if w.gauge_awg is not None
                and w.gauge_awg not in table
                and (i := project.interfaces.get(w.interface_id or "")) is not None
                and i.max_current_a is not None
            }
        )
        if missing_gauges:
            yield Hit(
                "derating-gauge",
                f"Wire current was not checked for AWG {', '.join(str(g) for g in missing_gauges)}: the ampacity table has no value for it",
            )
    yield from _current_gaps(project, table)
    if number(d.get("contact_current_factor")) is not None:
        unrated = sorted(
            {
                box.part_id
                for i in project.interfaces.values()
                if i.max_current_a is not None
                for e in i.endpoints
                if (box := project.connectors.get(e.connector_id or "")) is not None
                and _contact_rating(project, box) is None
            }
        )
        if unrated:
            yield Hit(
                "contact-rating",
                f"Contact current was not checked for {', '.join(unrated)}: the part has no contact rating",
            )
    if has_current and (
        number(d.get("max_voltage_drop_v")) is None
        or number(g.get("conductor_resistivity_ohm_m")) is None
    ):
        yield Hit(
            "voltage-drop",
            "Voltage drop was not checked: the limit or the conductor resistivity is still a placeholder",
        )
    yield from _voltage_drop_gaps(project)
    if any(h.shields for h in project.harnesses.values()) and None in (
        g.get("shield_end_a"),
        g.get("shield_end_b"),
    ):
        yield Hit(
            "grounding",
            "Shield grounding was not checked against a concept: it is still a placeholder",
        )
    if project.interfaces and not _category_pairs(project):
        yield Hit(
            "separation",
            "Power, signal and sensitive-analog separation was not checked: the category pairs are still a placeholder",
        )
    if project.harnesses and not _emc_pairs(project):
        yield Hit(
            "emc", "EMC class separation was not checked: the EMC rules are still a placeholder"
        )
    if (
        any(c.pins for c in project.connectors.values())
        and number(d.get("spare_pin_fraction")) is None
    ):
        yield Hit(
            "spare-pins",
            "Spare pins were not checked: the required fraction is still a placeholder",
        )
    yield from standard_unchecked(project)


RULES: tuple[Rule, ...] = (
    Rule("duplicate-id", "error", "Duplicate IDs",
         "Two objects with the same ID make every table, label and drawing ambiguous.",
         "Rename one of them.", _duplicate_ids),
    Rule("wire-dangling", "error", "Dangling wires",
         "A wire that ends nowhere cannot be built or tested.",
         "Connect the wire end to an existing pin or delete the wire.", _dangling_wires),
    Rule("model-inconsistent", "warning", "Model consistency",
         "The logical and physical parts of the model disagree, so later outputs may be wrong.",
         "Open the object and correct the mismatch.", _model_inconsistent),
    Rule("segment-loop", "error", "Routing loops",
         "A loop in the routing segments gives a wire two possible routes, so its length is not defined.",
         "Remove or merge a segment so the segments form a tree.", _segment_loop),
    Rule("signal-unassigned", "warning", "Unassigned signals",
         "A signal without a pin never reaches a wire.",
         "Regenerate the harnesses, or assign the pin by hand.", _signal_unassigned),
    Rule("pin-floating", "warning", "Floating pins",
         "A named pin with no wire looks connected on the drawing but carries nothing.",
         "Attach a wire or clear the signal name.", _floating_pins),
    Rule("pin-shared", "warning", "Several wires on one pin",
         "Two wires in one contact need a crimp that holds both, and a fault on that pin is harder to find.",
         "Move one wire to a spare pin or splice the wires; waive it with a reason if the design needs it.",
         _pin_shared),
    Rule("mate-mismatch", "error", "Mating halves",
         "Connectors that do not fit, or fit only by force, damage hardware.",
         "Choose the mating part, opposite gender and the same pin count and keying.", _mate_mismatch, sources=("ECSS-Q-ST-30-11_0140054",)),
    Rule("direction-conflict", "error", "Signal directions",
         "Two drivers fight each other, or nothing drives a receiver.",
         "Swap the wire to the correct pin of the interface.", _direction_conflict),
    Rule("current-over-contact", "error", "Contact current",
         "An overloaded contact overheats.", "Use a larger contact or split the load over more pins.",
         _current_over_contact, sources=("ECSS-Q-ST-30-11_0140050",)),
    Rule("current-over-wire", "error", "Wire current",
         "An overloaded wire overheats.", "Choose a larger gauge.", _current_over_wire, sources=("ECSS-Q-ST-30-11_0140217",)),
    Rule("voltage-drop", "error", "Voltage drop",
         "Too much drop leaves the load under-supplied.", "Choose a larger gauge or shorten the run.",
         _voltage_drop),
    Rule("spare-pins-low", "warning", "Spare pins",
         "Without spares there is no room for late changes.", "Use a connector with more pins.",
         _spare_pins),
    Rule("shield-unterminated", "warning", "Shield termination",
         "A shield connected at neither end does not shield.", "Terminate the shield at one or both ends.",
         _shield_unterminated),
    Rule("shield-wrong-end", "warning", "Shield grounding",
         "The grounding concept decides which end of a shield is grounded.", "Change the shield ends.",
         _shield_wrong_end, sources=("ECSS-E-ST-20-07_0080041", "ECSS-E-ST-20-07_0080042")),
    Rule("chains-mixed", "error", "Nominal and redundant chains",
         "A shared harness or connector lets one failure hit both chains.",
         "Move one chain to its own harness or connector.", _chains_mixed),
    Rule("pyro-mixed", "error", "Pyro lines",
         "Firing lines next to other wires risk accidental firing.",
         "Give the pyro lines their own harness and connector.", _pyro_mixed),
    Rule("category-mixed", "warning", "Category separation",
         "Noisy and sensitive interfaces in one bundle couple into each other.",
         "Split them into separate harnesses.", _category_mixed, sources=("ECSS-E-ST-20-07_0080034",)),
    Rule("emc-mixed", "warning", "EMC classes",
         "EMC classes that must stay apart couple when bundled.", "Split them into separate harnesses.",
         _emc_mixed, sources=("ECSS-E-ST-20-07_0080034",)),
    Rule("connector-lookalike", "warning", "Look-alike connectors",
         "Identical connectors on one unit can be swapped by mistake.",
         "Use different keying or a different insert on one of them.", _lookalike, sources=("ECSS-Q-ST-30-11_0140054",)),
    Rule("part-unapproved", "warning", "Approved parts",
         "Only approved parts may be built into flight hardware.",
         "Approve the part in the parts list, or choose an approved one.", _unapproved_parts, sources=("ESCC3901-4.4",)),
    *STANDARD_RULES,
    Rule("config-invalid", "error", "Engineering values",
         "A value outside its possible range (a factor above 1, a table that falls as the wire grows) would silently produce wrong gauges and checks.",
         "Correct the value in config/*.json; `harness-design-studio config DIR` lists what is missing or invalid.", _config_invalid),
    Rule("released-modified", "error", "Released items",
         "A released harness must match its baseline exactly; otherwise the released drawings no longer describe what is stored.",
         "Restore the harness from its baseline, or start a new revision for the change.", _released_modified),
    Rule("unchecked-config", "info", "Checks not run",
         "A rule that needs a number nobody has entered, or an analysis outside the tool, cannot say anything, and silence must not look like a pass.",
         "Fill in the missing value (see docs/PLACEHOLDERS.md), or do the analysis the note names and record it in the design review.", _unchecked),
)  # fmt: skip
