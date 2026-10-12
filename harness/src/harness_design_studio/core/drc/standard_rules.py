"""Rules that apply requirements of the supplied standards (D-131).

Each rule stays silent until its values exist (a standard profile, or the engineer's own numbers)
and the parts carry the ratings it needs; `unchecked` then says what was not checked, so silence
never looks like a pass. Part ratings are keys of `Part.ratings`:

  rated_voltage_v, dielectric_withstand_v   connector and wire working-voltage limits
  max_temp_c                                maximum rated temperature
  mating_cycles                             rated mating and de-mating cycles of a connector
  shield_insulated, conductive_finish       1 for yes (wire shield sheath, connector finish)

Requirement IDs are in compliance/requirements; each rule names the ones it serves.
"""

from __future__ import annotations

from collections.abc import Iterator

from harness_design_studio.core.generate.sizing import ampacity_table, bundle_k, exceeds
from harness_design_studio.core.model import Connector, Harness, Project

from .base import Hit, Rule, cfg, number

Q = "ECSS-Q-ST-30-11_"
E = "ECSS-E-ST-20-07_"
ESCC = "ESCC3901-4.4"


def _connector_parts(project: Project) -> list[str]:
    ids = {c.part_id for c in project.connectors.values()}
    ids |= {c.part_id for h in project.harnesses.values() for c in h.connectors}
    return sorted(i for i in ids if i in project.parts)


def _wire_parts(project: Project) -> list[str]:
    ids = {w.part_id for h in project.harnesses.values() for w in h.wires if w.part_id}
    return sorted(i for i in ids if i in project.parts)


def _rating(project: Project, part_id: str, key: str) -> float | None:
    part = project.parts.get(part_id)
    return part.ratings.get(key) if part else None


def connector_voltage_limit(project: Project, part_id: str) -> float | None:
    """Working voltage allowed by Table 6-10: the lower of the two limits that are known."""
    d = cfg(project, "derating")
    limits = []
    f1, f2 = (
        number(d.get("connector_voltage_factor_withstand")),
        number(d.get("connector_voltage_factor_rated")),
    )
    dwv, rated = (
        _rating(project, part_id, "dielectric_withstand_v"),
        _rating(project, part_id, "rated_voltage_v"),
    )
    if f1 is not None and dwv is not None:
        limits.append(f1 * dwv)
    if f2 is not None and rated is not None:
        limits.append(f2 * rated)
    return min(limits) if limits else None


def _connector_voltage(project: Project) -> Iterator[Hit]:
    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        if i.voltage_v is None:
            continue
        for e in i.endpoints:
            conn = project.connectors.get(e.connector_id or "")
            limit = connector_voltage_limit(project, conn.part_id) if conn else None
            if conn is not None and limit is not None and exceeds(i.voltage_v, limit):
                yield Hit(
                    f"{i.id}.{conn.id}",
                    f"{i.id} works at {i.voltage_v:g} V but {conn.id} ({conn.part_id}) allows {limit:g} V after derating",
                )


def _wire_voltage(project: Project) -> Iterator[Hit]:
    factor = number(cfg(project, "derating").get("wire_voltage_factor"))
    if factor is None:
        return
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        for w in h.wires:
            i = project.interfaces.get(w.interface_id or "")
            rated = _rating(project, w.part_id or "", "rated_voltage_v")
            if (
                i
                and i.voltage_v is not None
                and rated is not None
                and exceeds(i.voltage_v, factor * rated)
            ):
                yield Hit(
                    w.id,
                    f"Wire {w.id} works at {i.voltage_v:g} V but {w.part_id} allows {factor * rated:g} V after derating",
                )


def _temperature_users(project: Project, what: str) -> Iterator[tuple[str, str]]:
    """(object ID, part ID) of every connector or wire that uses a part, in a stable order. The
    finding is placed on the use, so the release gate can tell which harness it blocks."""
    if what == "connector":
        for conn in sorted(project.connectors.values(), key=lambda x: x.id):
            yield conn.id, conn.part_id
        for h in sorted(project.harnesses.values(), key=lambda x: x.id):
            for cable in h.connectors:
                yield cable.id, cable.part_id
    else:
        for h in sorted(project.harnesses.values(), key=lambda x: x.id):
            for w in h.wires:
                if w.part_id:
                    yield w.id, w.part_id


def _temperature(project: Project) -> Iterator[Hit]:
    d = cfg(project, "derating")
    ambient = number(d.get("max_ambient_temperature_c"))
    if ambient is None:
        return
    for margin_key, what in (
        ("connector_temperature_margin_c", "connector"),
        ("wire_temperature_margin_c", "wire"),
    ):
        margin = number(d.get(margin_key))
        if margin is None:
            continue
        seen: set[str] = set()
        for oid, pid in _temperature_users(project, what):
            top = _rating(project, pid, "max_temp_c")
            if top is not None and exceeds(ambient, top - margin) and oid not in seen:
                seen.add(oid)
                yield Hit(
                    oid,
                    f"The hottest ambient temperature ({ambient:g} degC) is above {top - margin:g} degC, "
                    f"the limit for {what} part {pid} used by {oid} (maximum {top:g} degC, margin {margin:g} degC), "
                    "before any self-heating of the conductor",
                )


def _mating_cycles(project: Project) -> Iterator[Hit]:
    limit = number(cfg(project, "derating").get("max_mating_cycles"))
    if limit is None:
        return
    for pid in _connector_parts(project):
        rated = _rating(project, pid, "mating_cycles")
        if rated is not None and rated < limit:
            yield Hit(
                f"mating-cycles.{pid}",
                f"{pid} is rated for {rated:g} mating cycles, fewer than the {limit:g} that the programme may use",
            )


def _manufacturer(project: Project) -> Iterator[Hit]:
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        for c in h.connectors:
            box = project.connectors.get(c.mates_with or "")
            a, b = project.parts.get(c.part_id), project.parts.get(box.part_id) if box else None
            if a and b and a.manufacturer and b.manufacturer and a.manufacturer != b.manufacturer:
                yield Hit(
                    c.id,
                    f"{c.id} ({a.manufacturer}) mates with {box.id if box else ''} ({b.manufacturer}): a connector and its mate should come from one manufacturer",
                )


def _wire_specification(project: Project) -> Iterator[Hit]:
    for pid in _wire_parts(project):
        p = project.parts[pid]
        if p.approval == "approved" and not p.specification:
            yield Hit(
                f"wire-spec.{pid}",
                f"The approved wire part {pid} cites no specification, so its qualification cannot be traced",
            )


def _adjacent_power_return(project: Project) -> Iterator[Hit]:
    """Power and return pins side by side (30-11C 6.11.3 a), only when a gap is required."""
    gap = number(cfg(project, "generation").get("power_return_gap_pins"))
    if gap is None or not 1 <= gap <= 1000:  # also rules out nan and inf
        return
    for conn in sorted(project.connectors.values(), key=lambda x: x.id):
        yield from _power_pairs(project, conn, int(gap))
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        for c in h.connectors:
            yield from _power_pairs(project, c, int(gap))


def _power_pairs(project: Project, conn: Connector, gap: int) -> Iterator[Hit]:
    """Any two power or ground pins of different signals that have fewer than `gap` unassigned
    contacts between them (only pairs with at most `gap` contacts between are looked at)."""
    order = list(conn.pins)

    def is_power(k: int) -> bool:
        i = project.interfaces.get(order[k].interface_id or "")
        itype = project.interface_types.get(i.type_id) if i else None
        return itype is not None and itype.category in ("power", "ground")

    for k, p in enumerate(order):
        if not p.signal or not is_power(k):
            continue
        for m in range(k + 1, min(k + 2 + gap, len(order))):
            q = order[m]
            if not q.signal or q.signal == p.signal or not is_power(m):
                continue
            free = sum(1 for x in order[k + 1 : m] if x.interface_id is None and not x.signal)
            if free < gap:
                yield Hit(
                    f"{conn.id}.{p.id}+{q.id}",
                    f"{conn.id}: {p.signal} (pin {p.id}) and {q.signal} (pin {q.id}) have {free} unassigned contact(s) between them, fewer than the {gap} required",
                )


def unchecked(project: Project) -> Iterator[Hit]:
    """What the optional rules could not check (listed under `unchecked-config`)."""
    d = cfg(project, "derating")
    if (
        number(d.get("connector_voltage_factor_withstand")) is not None
        or number(d.get("connector_voltage_factor_rated")) is not None
    ):
        no_rating = sorted(
            {
                conn.part_id
                for i in project.interfaces.values()
                if i.voltage_v is not None
                for e in i.endpoints
                if (conn := project.connectors.get(e.connector_id or "")) is not None
                and connector_voltage_limit(project, conn.part_id) is None
            }
        )
        if no_rating:
            yield Hit(
                "connector-voltage",
                f"Connector working voltage was not checked for {', '.join(no_rating)}: the part has no rated or withstand voltage",
            )
    if number(d.get("wire_voltage_factor")) is not None:
        bad = [p for p in _wire_parts(project) if _rating(project, p, "rated_voltage_v") is None]
        if bad:
            yield Hit(
                "wire-voltage",
                f"Wire voltage was not checked for {', '.join(bad)}: the part has no rated voltage",
            )
    if number(d.get("max_mating_cycles")) is not None:
        bad = [p for p in _connector_parts(project) if _rating(project, p, "mating_cycles") is None]
        if bad:
            yield Hit(
                "mating-cycles",
                f"Mating cycles were not checked for {', '.join(bad)}: the part has no rated cycles. The number of times a connector is really mated is a record kept by people",
            )
    if number(d.get("max_ambient_temperature_c")) is None and (
        number(d.get("wire_temperature_margin_c")) is not None
        or number(d.get("connector_temperature_margin_c")) is not None
    ):
        yield Hit(
            "temperature",
            "Temperature margins were not checked: the hottest ambient temperature (derating.max_ambient_temperature_c) is not set",
        )
    if number(d.get("max_ambient_temperature_c")) is not None:
        for key, what, parts in (
            ("connector_temperature_margin_c", "Connector", _connector_parts(project)),
            ("wire_temperature_margin_c", "Wire", _wire_parts(project)),
        ):
            if number(d.get(key)) is None:
                yield Hit(
                    f"temperature-{what.lower()}-margin",
                    f"{what} temperature margin was not checked: the margin (derating.{key}) is not set",
                )
                continue
            bad = [p for p in parts if _rating(project, p, "max_temp_c") is None]
            if bad:
                yield Hit(
                    f"temperature-{what.lower()}-parts",
                    f"Temperature margin was not checked for {what.lower()} part(s) {', '.join(bad)}: the part has no max_temp_c rating",
                )
    if number(d.get("wire_temperature_margin_c")) is not None and project.harnesses:
        yield Hit(
            "thermal-analysis",
            "Wire surface temperature under load was not checked: it needs a thermal analysis outside the tool (ECSS-Q-ST-30-11C 6.32.4 b, c)",
        )
    emc = cfg(project, "emc")
    if project.harnesses and (
        emc.get("shield_bonding") is not None or emc.get("same_class_one_bundle") is not None
    ):
        yield Hit(
            "bundle-separation",
            "Separation of bundles of different categories (5 cm or a metallic screen), the DC resistance of shield and housing bonds, and individual shields on external cables were not checked: the model holds no routing geometry or measurements (ECSS-E-ST-20-07C 4.2.13.1 c, 4.2.13.2 a, d, e)",
        )
    if cfg(project, "emc").get("shield_bonding") is not None:
        bad = sorted(
            {
                pid
                for _h, kind, pid in _shielded_parts(project)[0]
                if _rating(
                    project, pid, "conductive_finish" if kind == "connector" else "shield_insulated"
                )
                is None
            }
        )
        if bad:
            yield Hit(
                "shield-parts",
                f"Shield finish and sheath were not checked for {', '.join(bad)}: the part has no conductive_finish or shield_insulated rating",
            )
    rf_types = [t for t in project.interface_types.values() if t.category == "rf"]
    if rf_types and number(d.get("rf_power_factor")) is not None:
        yield Hit(
            "multipactor",
            "RF power and the 6 dB margin before multipactor were not checked: they need an RF analysis outside the tool (ECSS-Q-ST-30-11C 6.12.3 b)",
        )
    if _bundle_table_set(project) and project.harnesses:
        yield Hit(
            "partial-load",
            "The extra factor L for partially loaded bundles (Table 6-42) is not applied: the tool does not know which wires carry current at the same time. The bundle check is the conservative one (L = 1)",
        )


def _bundle_table_set(project: Project) -> bool:
    return isinstance(cfg(project, "derating").get("bundle_factor_by_count"), dict)


def bundle_factor(project: Project, count: int) -> float | None:
    """K from Table 6-41 for a bundle of `count` wires (see `sizing.bundle_k`)."""
    return bundle_k(cfg(project, "derating").get("bundle_factor_by_count"), count)


def bundle_wire_count(h: Harness) -> int:
    return len(h.wires)


def _bundle_current(project: Project) -> Iterator[Hit]:
    """IBW = ISW x K (30-11C 6.32.5.1). ISW is the ampacity table of the project; the bundle is
    every wire of the harness (conservative; L of Table 6-42 is not applied)."""
    table = ampacity_table(cfg(project, "derating").get("ampacity_a_by_awg"))
    if table is None or not _bundle_table_set(project):
        return
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        k = bundle_factor(project, bundle_wire_count(h))
        if k is None:
            continue
        for w in h.wires:
            i = project.interfaces.get(w.interface_id or "")
            if i is None or i.max_current_a is None or w.gauge_awg not in table:
                continue
            limit = table[w.gauge_awg] * k
            if exceeds(i.max_current_a, limit):
                yield Hit(
                    w.id,
                    f"Wire {w.id} (AWG {w.gauge_awg}) carries {i.max_current_a:g} A but a bundle of {bundle_wire_count(h)} wires ({h.id}) allows {limit:g} A (single wire {table[w.gauge_awg]:g} A x K {k:g})",
                )


def _shield_bonding(project: Project) -> Iterator[Hit]:
    """Shields bonded at both ends through the connector body or backshell (20-07C 4.2.13.2 d, e)."""
    if cfg(project, "emc").get("shield_bonding") != "both_ends_backshell":
        return
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        for s in h.shields:
            if s.kind == "twisted_pair":
                continue  # a twisted pair has no shield to bond
            if (s.end_a, s.end_b) != ("backshell_360", "backshell_360"):
                yield Hit(
                    f"{h.id}.{s.id}",
                    f"Shield {s.id} in {h.id} is {s.end_a}/{s.end_b}; it must be bonded at both ends through the connector body or backshell",
                )


def _shielded_parts(project: Project) -> tuple[list[tuple[str, str, str]], list[str]]:
    """(harness, kind, part) triples the shield-parts rule looks at, and parts it cannot judge."""
    seen: list[tuple[str, str, str]] = []
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        if not any(s.kind != "twisted_pair" for s in h.shields):
            continue  # no real shield in this harness
        seen += [(h.id, "connector", c.part_id) for c in h.connectors]
        by_id = {w.id: w for w in h.wires}
        for sh in h.shields:
            if sh.kind in ("overall_shield", "twisted_pair"):
                continue  # overshields need no insulating sheath (4.2.13.2 b); a twisted pair has no shield
            for wid in sh.wire_ids:
                if wid in by_id and by_id[wid].part_id:
                    seen.append((h.id, "wire", by_id[wid].part_id or ""))
    return sorted(set(seen)), []


def _shield_parts(project: Project) -> Iterator[Hit]:
    """Connectors for shielded wires have a conductive finish; shields have an insulating sheath."""
    if cfg(project, "emc").get("shield_bonding") is None:
        return
    for hid, kind, pid in _shielded_parts(project)[0]:
        key = "conductive_finish" if kind == "connector" else "shield_insulated"
        value = _rating(project, pid, key)
        if value is not None and value == 0:
            what = (
                "has no conductive finish"
                if kind == "connector"
                else "has no insulating sheath over the shield"
            )
            yield Hit(f"shield-parts.{hid}.{pid}", f"{pid} in {hid} {what}")


def _emc_class_split(project: Project) -> Iterator[Hit]:
    """Wires of one EMC class between the same two units belong in one bundle (20-07C 4.2.13.1 b)."""
    if cfg(project, "emc").get("same_class_one_bundle") is not True:
        return
    carried: dict[tuple[str, str, str], set[str]] = {}
    for h in project.harnesses.values():
        for iid in h.interfaces:
            i = project.interfaces.get(iid)
            t = project.interface_types.get(i.type_id) if i else None
            if i is None or t is None or not t.emc_class or len(i.endpoints) != 2:
                continue
            a, b = sorted(e.unit_id for e in i.endpoints)
            carried.setdefault((t.emc_class, a, b), set()).add(h.id)
    for (cls, a, b), ids in sorted(carried.items()):
        if len(ids) > 1:
            yield Hit(
                f"emc-class.{cls}.{a}.{b}",
                f"Interfaces of EMC class {cls} between {a} and {b} run in {len(ids)} bundles ({', '.join(sorted(ids))}); one class should be one bundle",
            )


STANDARD_RULES: tuple[Rule, ...] = (
    Rule("connector-voltage", "error", "Connector working voltage",
         "A connector worked close to its voltage rating can arc or break down.",
         "Use a connector with a higher voltage rating or lower the working voltage.",
         _connector_voltage, sources=(Q + "0140051", Q + "0140058")),
    Rule("wire-voltage", "error", "Wire working voltage",
         "A wire worked close to its voltage rating can break down.",
         "Use a wire with a higher voltage rating or lower the working voltage.",
         _wire_voltage, sources=(Q + "0140213",)),
    Rule("temperature-margin", "error", "Temperature margin",
         "A part used close to its maximum temperature ages faster and fails earlier.",
         "Use a part with a higher temperature rating or reduce the ambient temperature.",
         _temperature, sources=(Q + "0140051", Q + "0140213")),
    Rule("mating-cycles", "warning", "Mating cycles",
         "A connector mated more often than it is rated for wears out.",
         "Choose a connector rated for at least the permitted number of cycles.",
         _mating_cycles, sources=(Q + "0140056", Q + "0140061")),
    Rule("connector-manufacturer", "warning", "One manufacturer per connector pair",
         "Halves from different manufacturers may not mate within the specified tolerances.",
         "Use mating halves from the same manufacturer.",
         _manufacturer, sources=(Q + "0140055",)),
    Rule("wire-specification", "warning", "Wire specification",
         "An approved wire that cites no specification cannot be traced to a qualification.",
         "Enter the detail specification the wire is procured to in the part.",
         _wire_specification, sources=(ESCC,)),
    Rule("shield-bonding", "warning", "Shield bonding",
         "A shield that is not bonded to the housing at both ends through the connector does not shield reliably.",
         "Terminate the shield with a 360 degree backshell at both ends.",
         _shield_bonding, sources=(E + "0080041", E + "0080042")),
    Rule("shield-parts", "warning", "Shield parts",
         "A connector without a conductive finish cannot bond a shield, and a shield without an insulating sheath can ground uncontrolled.",
         "Choose a connector with a conductive finish and a wire with an insulated shield.",
         _shield_parts, sources=(E + "0080039", E + "0080040")),
    Rule("emc-class-split", "warning", "One bundle per EMC class",
         "Wires of one EMC category spread over several bundles make the segregation of categories harder to keep.",
         "Carry the interfaces of one class between two units in one harness.",
         _emc_class_split, sources=(E + "0080035",)),
    Rule("power-return-adjacent", "warning", "Power and return pins",
         "Power and return on neighbouring contacts raise the risk of a short circuit.",
         "Leave at least one contact unassigned between them (regenerate the harness).",
         _adjacent_power_return, sources=(Q + "0140052",)),
    Rule("bundle-current", "error", "Bundle current",
         "A wire in a large bundle heats more than a single wire and must carry less.",
         "Choose a larger gauge or split the bundle.",
         _bundle_current, sources=(Q + "0140217", Q + "0140218")),
)  # fmt: skip
