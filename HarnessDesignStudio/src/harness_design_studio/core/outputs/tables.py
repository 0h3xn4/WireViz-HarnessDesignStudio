"""Tables derived from the model: wire list, pinouts, BOM, mass and length, tests, labels,
matrices. Each function returns `Table` (header row first). No design numbers are invented:
unknown values are written as "pending", "unknown" or "TBD (placeholder)".

Build data (1.7.0, decision D-170) shows only where it is used, so a project that uses none of it
keeps byte-identical tables: the wire list gets `Strip A (mm)` and `Strip B (mm)` as its last
columns when any wire has a strip length (after the optional EMC class, Label and Note columns);
the pinout tables get `Contact` as their last column when any pin has a contact part (after
`Function` and `Termination`); a harness with accessories gets `accessories.csv`. The BOM counts
each contact part once per pin in use of the harness (unit `ea`) and each accessory part by its
`quantity` (unit `ea`); an accessory with a length counts metres instead,
sum(length_mm x quantity) / 1000 (unit `m`), together with the wire length of the same part. A part
used both ways has one line per unit (`ea` first, then `m`); the key of a line is part and unit."""

from collections import defaultdict
from collections.abc import Collection, Iterator
from decimal import Decimal

from harness_design_studio.core.generate.lengths import clear_length_cache, wire_length
from harness_design_studio.core.generate.mass import harness_mass
from harness_design_studio.core.model import Connector, Harness, Link, Pin, Project, Wire

from .stamp import Table

PENDING = "pending"
TBD = "TBD (placeholder)"


def num(v: float | None) -> str:
    """A number for display text on drawings (6 significant digits)."""
    return "" if v is None else f"{v:.6g}"


def data_num(v: float | None) -> str:
    """A number for the data files (tables, YAML): the shortest text that reads back as the same
    value, without an exponent, rounded to 9 decimals so sums carry no floating point noise
    (0.30000000000000004). The verifier compares these cells with the model."""
    if v is None:
        return ""
    r = round(v, 9) + 0.0  # + 0.0 turns -0.0 into 0.0
    text = repr(r)
    if "e" in text or "E" in text:
        text = format(Decimal(text), "f")
    return text[:-2] if text.endswith(".0") else text


def clear_cache() -> None:
    clear_length_cache()


def shield_of(h: Harness) -> dict[str, str]:
    return {wid: s.id for s in h.shields for wid in s.wire_ids}


def emc_class_of(project: Project, w: Wire) -> str:
    """EMC class of the interface type a wire carries (ECSS-E-ST-20-07C 4.2.13.1 d)."""
    i = project.interfaces.get(w.interface_id or "")
    t = project.interface_types.get(i.type_id) if i else None
    return (t.emc_class or "") if t else ""


def uses_emc_classes(project: Project) -> bool:
    return any(t.emc_class for t in project.interface_types.values())


def requirement_of(project: Project, w: Wire) -> str:
    """Requirement ID of the interface a wire carries (empty for a wire with no interface)."""
    i = project.interfaces.get(w.interface_id or "")
    return (i.requirement_id or "") if i else ""


def uses_requirements(project: Project) -> bool:
    """True when any interface carries a requirement ID (release 1.10): the wire list and the
    traceability matrix then get a Requirement column; a project without one keeps its files."""
    return any(i.requirement_id for i in project.interfaces.values())


def uses_wire_text(project: Project) -> bool:
    """True when a person gave any wire a label or a note (1.4.0)."""
    return any(w.label or w.note for h in project.harnesses.values() for w in h.wires)


def uses_strip_lengths(project: Project) -> bool:
    """True when a person gave any wire a strip length at either end (1.7.0)."""
    return any(
        w.strip_a_mm is not None or w.strip_b_mm is not None
        for h in project.harnesses.values()
        for w in h.wires
    )


def connector_label(project: Project, c: Connector) -> str:
    """What the label of a connector prints first: the person's label of the connector, else the one
    of the box connector it plugs into, else nothing (the ID is in the text anyway)."""
    if c.label:
        return c.label
    box = project.connectors.get(c.mates_with or "")
    return (box.label or "") if box is not None else ""


def wire_name(w: Wire) -> str:
    """What the labels of a wire print after its ID: the person's label, else the signal."""
    return w.label or w.signal or ""


def wire_list(project: Project, h: Harness) -> Table:
    """The EMC class column exists only when the project defines EMC classes, the Requirement
    column only when an interface has a requirement ID, and the Label and Note columns only when a
    person gave a wire one, so projects that do not use them keep byte-identical wire lists."""
    shields = shield_of(h)
    emc = uses_emc_classes(project)
    req = uses_requirements(project)
    text = uses_wire_text(project)
    strip = uses_strip_lengths(project)
    rows: Table = [[
        "Wire", "Signal", "Interface", "From connector", "From pin", "To connector", "To pin",
        "AWG", "Part", "Colour", "Length (m)", "Shield group", "Locked",
        *(["EMC class"] if emc else []), *(["Requirement"] if req else []),
        *(["Label", "Note"] if text else []),
        *(["Strip A (mm)", "Strip B (mm)"] if strip else []),
    ]]  # fmt: skip
    for w in sorted(h.wires, key=lambda x: x.id):
        rows.append([
            w.id, w.signal or "", w.interface_id or "", w.from_connector, w.from_pin,
            w.to_connector, w.to_pin, PENDING if w.gauge_awg is None else str(w.gauge_awg),
            w.part_id or "", w.colour or "", data_num(wire_length(h, w)), shields.get(w.id, ""),
            "yes" if w.locked else "", *([emc_class_of(project, w)] if emc else []),
            *([requirement_of(project, w)] if req else []),
            *([w.label or "", w.note] if text else []),
            *([data_num(w.strip_a_mm), data_num(w.strip_b_mm)] if strip else []),
        ])  # fmt: skip
    return rows


def _all_pins(project: Project) -> Iterator[Pin]:
    for c in project.connectors.values():
        yield from c.pins
    for h in project.harnesses.values():
        for c in h.connectors:
            yield from c.pins


def uses_pin_function(project: Project) -> bool:
    """True when a person gave any pin a function (1.4.0)."""
    return any(p.function for p in _all_pins(project))


def uses_termination(project: Project) -> bool:
    """True when any pin says how a wire is joined to it (crimp or solder, 1.4.0)."""
    return any(p.termination != "unspecified" for p in _all_pins(project))


def uses_contact_parts(project: Project) -> bool:
    """True when a person named a contact part for any pin (1.7.0)."""
    return any(p.contact_part for p in _all_pins(project))


def uses_pin_direction(project: Project) -> bool:
    """True when a person set the direction of any pin (1.9.0)."""
    return any(p.direction for p in _all_pins(project))


def _pin_rows(
    c: Connector,
    attached: dict[tuple[str, str], list[str]],
    fn: bool,
    term: bool,
    contact: bool = False,
    direction: bool = False,
    carried: dict[tuple[str, str], tuple[str, str]] | None = None,
) -> Table:
    """The rows of one connector; `fn`, `term`, `contact` and `direction` say whether the Function,
    Termination, Contact and Direction columns exist (worked out once per table, since each looks
    at every pin of the project). `carried` (cable connectors, release 1.10) gives the signal and
    the interface of the wires at a pin, which fill the Signal and Interface cells of a pin that
    has none of its own."""
    rows: Table = []
    for p in c.pins:
        wires = attached.get((c.id, p.id), [])
        sig, itf = (carried or {}).get((c.id, p.id), ("", ""))
        rows.append([
            c.id, c.role, c.mates_with or "", c.part_id, p.id, p.signal or sig,
            p.interface_id or itf,
            ";".join(sorted(wires)), "no" if wires or p.interface_id or p.signal else "yes",
            *([p.function or ""] if fn else []), *([p.termination] if term else []),
            *([p.contact_part or ""] if contact else []),
            *([_DIRECTION_WORD[p.direction]] if direction else []),
        ])  # fmt: skip
    return rows


PINOUT_HEADER = [
    "Connector",
    "Role",
    "Mates with",
    "Part",
    "Pin",
    "Signal",
    "Interface",
    "Wires",
    "Spare",
]


# How the Direction column of a pinout table writes the direction of a pin (an empty cell: not set)
_DIRECTION_WORD = {"": "", "in": "in", "out": "out", "bidir": "bidirectional"}


def _header(fn: bool, term: bool, contact: bool = False, direction: bool = False) -> list[str]:
    return [
        *PINOUT_HEADER,
        *(["Function"] if fn else []),
        *(["Termination"] if term else []),
        *(["Contact"] if contact else []),
        *(["Direction"] if direction else []),
    ]


def wire_signals(h: Harness) -> dict[tuple[str, str], tuple[str, str]]:
    """(connector, pin) -> (signals, interfaces) of the wires that end there, each a sorted list of
    the different non-empty values joined with `;` (the way the Wires column joins wire IDs)."""
    found: dict[tuple[str, str], tuple[set[str], set[str]]] = defaultdict(lambda: (set(), set()))
    for w in h.wires:
        for end in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
            if w.signal:
                found[end][0].add(w.signal)
            if w.interface_id:
                found[end][1].add(w.interface_id)
    return {k: (";".join(sorted(s)), ";".join(sorted(i))) for k, (s, i) in found.items()}


def pinouts(project: Project, h: Harness) -> Table:
    attached: dict[tuple[str, str], list[str]] = defaultdict(list)
    for w in h.wires:
        attached[(w.from_connector, w.from_pin)].append(w.id)
        attached[(w.to_connector, w.to_pin)].append(w.id)
    carried = wire_signals(h)
    fn, term, contact, direction = (
        uses_pin_function(project), uses_termination(project), uses_contact_parts(project),
        uses_pin_direction(project),
    )  # fmt: skip
    rows = [_header(fn, term, contact, direction)]
    for c in sorted(h.connectors, key=lambda x: x.id):
        rows += _pin_rows(c, attached, fn, term, contact, direction, carried)
    return rows


def box_pinouts(project: Project, connector_ids: Collection[str] | None = None) -> Table:
    """The rows of `system/box_pinouts.csv`; `connector_ids` keeps only those box connectors
    (the Devices view shows one device's rows exactly as they are exported)."""
    attached: dict[tuple[str, str], list[str]] = defaultdict(list)
    for h in project.harnesses.values():
        mates = {c.id: c.mates_with for c in h.connectors}
        for w in h.wires:
            for cid, pin in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
                if mates.get(cid):
                    attached[(mates[cid] or "", pin)].append(w.id)
    fn, term, contact, direction = (
        uses_pin_function(project), uses_termination(project), uses_contact_parts(project),
        uses_pin_direction(project),
    )  # fmt: skip
    rows = [_header(fn, term, contact, direction)]
    for c in sorted(project.connectors.values(), key=lambda x: x.id):
        if connector_ids is None or c.id in connector_ids:
            rows += _pin_rows(c, attached, fn, term, contact, direction)
    return rows


BOM_HEADER = [
    "Part", "Category", "Manufacturer", "Part number", "Description", "Approval",
    "Quantity", "Unit", "Wires without length", "Used in",
]  # fmt: skip


def pins_in_use(h: Harness) -> set[tuple[str, str]]:
    """The (connector, pin) pairs of the harness that have a wire attached."""
    used: set[tuple[str, str]] = set()
    for w in h.wires:
        used.add((w.from_connector, w.from_pin))
        used.add((w.to_connector, w.to_pin))
    return used


def bom(project: Project, harnesses: list[Harness]) -> Table:
    """One line per part and unit: connector parts, contact parts (one per pin in use) and accessory
    parts without a length count `ea`; wire parts and accessory parts with a length add up metres."""
    counts: dict[str, int] = defaultdict(int)
    metres: dict[str, float] = defaultdict(float)
    metre_parts: set[str] = set()
    wire_parts: set[str] = set()
    unknown: dict[str, int] = defaultdict(int)
    used: dict[str, set[str]] = defaultdict(set)
    for h in harnesses:
        in_use = pins_in_use(h)
        for c in h.connectors:
            counts[c.part_id] += 1
            used[c.part_id].add(h.id)
            for p in c.pins:
                if p.contact_part and (c.id, p.id) in in_use:
                    counts[p.contact_part] += 1
                    used[p.contact_part].add(h.id)
        for w in h.wires:
            pid = w.part_id or "(no part)"
            used[pid].add(h.id)
            wire_parts.add(pid)
            length = wire_length(h, w)
            if length is None:
                unknown[pid] += 1
            else:
                metres[pid] += length
        for a in h.accessories:
            if not a.part_id:
                continue
            used[a.part_id].add(h.id)
            if a.length_mm is None:
                counts[a.part_id] += a.quantity
            else:
                metres[a.part_id] += a.length_mm * a.quantity / 1000
                metre_parts.add(a.part_id)
    metre_parts |= wire_parts
    rows = [BOM_HEADER]
    for pid, unit in sorted({*((p, "ea") for p in counts), *((p, "m") for p in metre_parts)}):
        part = project.parts.get(pid)
        is_m = unit == "m"
        rows.append([
            pid, part.category if part else "unknown", (part.manufacturer or "") if part else "",
            (part.part_number or "") if part else "", (part.description or "") if part else "",
            ("missing from parts list" if part is None else part.approval + (" (example data)" if part.unverified else "")),
            data_num(metres[pid]) if is_m else str(counts[pid]), unit,
            str(unknown[pid]) if pid in wire_parts and is_m else "", ";".join(sorted(used[pid])),
        ])  # fmt: skip
    return rows


ACCESSORY_HEADER = ["Accessory", "Kind", "Part", "Target", "Position", "Length (mm)", "Quantity", "Note"]  # fmt: skip


def accessories(h: Harness) -> Table:
    """The accessories of a harness (sleeving, heat shrink, labels, backshells), sorted by ID.
    The file is written only for a harness that has some."""
    rows: Table = [ACCESSORY_HEADER]
    for a in sorted(h.accessories, key=lambda x: x.id):
        rows.append([
            a.id, a.kind, a.part_id or "", a.target or "", a.position or "",
            data_num(a.length_mm), str(a.quantity), a.note,
        ])  # fmt: skip
    return rows


MASS_HEADER = [
    "Harness", "Wires", "Connectors", "Wire length known (m)", "Wires without length",
    "Mass of wires and cable connectors (g)", "Margin (g)", "Mass with margin (g)", "Complete", "Missing data",
]  # fmt: skip


def mass_length(project: Project, harnesses: list[Harness]) -> Table:
    rows = [MASS_HEADER]
    tot_len = tot_mass = 0.0
    tot_unknown = tot_wires = tot_conn = 0
    complete = True
    margins: list[float | None] = []
    for h in harnesses:
        r = harness_mass(project, h)
        lengths = [wire_length(h, w) for w in h.wires]
        known = sum(x for x in lengths if x is not None)
        unk = sum(1 for x in lengths if x is None)
        rows.append([
            h.id, str(len(h.wires)), str(len(h.connectors)), data_num(known), str(unk),
            data_num(r.total_g), data_num(r.margin_g), data_num(r.with_margin_g),
            "yes" if r.complete and unk == 0 else "no", "; ".join(r.missing),
        ])  # fmt: skip
        tot_len += known
        tot_mass += r.total_g
        tot_unknown += unk
        tot_wires += len(h.wires)
        tot_conn += len(h.connectors)
        complete = complete and r.complete and unk == 0
        margins.append(r.margin_g)
    margin = None if any(m is None for m in margins) else sum(m for m in margins if m is not None)
    rows.append([
        "TOTAL", str(tot_wires), str(tot_conn), data_num(tot_len), str(tot_unknown),
        data_num(tot_mass), data_num(margin),
        data_num(None if margin is None else tot_mass + margin),
        "yes" if complete else "no", "totals count only what is known" if not complete else "",
    ])  # fmt: skip
    return rows


def _cfg(project: Project, key: str) -> object:
    c = project.config.get("generation")
    return c.values.get(key) if c else None


def _limit(project: Project, key: str, unit: str) -> str:
    v = _cfg(project, key)
    return f"{v:g} {unit}" if isinstance(v, int | float) and not isinstance(v, bool) else TBD


def tests(project: Project, h: Harness) -> Table:
    cont = _limit(project, "test_continuity_max_ohm", "ohm max")
    iso = _limit(project, "test_isolation_min_mohm", "Mohm min")
    volts = _limit(project, "test_isolation_voltage_v", "V")
    rows: Table = [["Test", "Type", "From", "To", "Expected", "Limit", "Test voltage", "Wire"]]
    n = 0
    for w in sorted(h.wires, key=lambda x: x.id):
        n += 1
        rows.append([f"T{n:03d}", "continuity", f"{w.from_connector}.{w.from_pin}", f"{w.to_connector}.{w.to_pin}", "continuous", cont, "", w.id])  # fmt: skip
    for w in sorted(h.wires, key=lambda x: x.id):
        n += 1
        rows.append([f"T{n:03d}", "isolation", f"{w.from_connector}.{w.from_pin}", "all other wires and shields", "isolated", iso, volts, w.id])  # fmt: skip
    for s in sorted(h.shields, key=lambda x: x.id):
        n += 1
        rows.append([f"T{n:03d}", "isolation", f"shield {s.id}", "all wires", "isolated", iso, volts, ";".join(sorted(s.wire_ids))])  # fmt: skip
    return rows


def labels(project: Project, h: Harness) -> Table:
    rows: Table = [["Label", "Kind", "Text", "Quantity"]]
    if h.label:
        rows.append([h.id, "harness", h.label, "1"])
    for c in sorted(h.connectors, key=lambda x: x.id):
        name = connector_label(project, c)
        mates = f"{c.id} mates {c.mates_with or '-'}"
        rows.append([f"{c.id}", "connector", f"{name} ({mates})" if name else mates, "1"])
    for w in sorted(h.wires, key=lambda x: x.id):
        far = f"{w.to_connector}.{w.to_pin}"
        near = f"{w.from_connector}.{w.from_pin}"
        emc = emc_class_of(project, w)
        tag = f" [EMC {emc}]" if emc else ""  # personnel can see the category (20-07C 4.2.13.1 d)
        name = wire_name(w)
        head = f"{w.id} {name}" if name else w.id  # a signal name keeps its own spacing
        rows.append([f"{w.id}-A", "wire", f"{head} to {far}{tag}", "1"])
        rows.append([f"{w.id}-B", "wire", f"{head} to {near}{tag}", "1"])
    return rows


def mating_matrix(project: Project) -> Table:
    """Every box connector with the cable connector that plugs into it (if any)."""
    mated: dict[str, list[tuple[str, Connector]]] = defaultdict(list)
    for h in project.harnesses.values():
        for c in h.connectors:
            if c.mates_with:
                mated[c.mates_with].append((h.id, c))
    rows: Table = [
        [
            "Box connector",
            "Unit",
            "Part",
            "Gender",
            "Cable connector",
            "Cable part",
            "Cable gender",
            "Harness",
        ]
    ]
    for b in sorted(project.connectors.values(), key=lambda x: x.id):
        pairs = sorted(mated.get(b.id, []), key=lambda t: (t[1].id, t[0])) or [("", None)]  # type: ignore[list-item]
        for hid, c in pairs:
            rows.append(
                [
                    b.id,
                    b.unit_id or "",
                    b.part_id,
                    b.gender,
                    c.id if c else "",
                    c.part_id if c else "",
                    c.gender if c else "",
                    hid,
                ]
            )
    return rows


def device_of(project: Project, connector_id: str) -> str:
    """The device a connector belongs to ("" when the connector or its device is gone)."""
    c = project.connectors.get(connector_id)
    return (c.unit_id or "") if c is not None else ""


def carried_types(project: Project) -> dict[str, list[str]]:
    """Link -> the IDs of the interface types its pairs belong to (`links.derived_interfaces`;
    sorted, without repeats). A link whose pairs no type explains is not in the result."""
    from harness_design_studio.core.links import derived_interfaces  # (links imports this module)

    out: dict[str, set[str]] = {}
    for di in derived_interfaces(project):
        if di.type_id:
            out.setdefault(di.link_id, set()).update(di.alternatives or (di.type_id,))
    return {link: sorted(ids) for link, ids in out.items()}


def link_wires(project: Project, link: Link) -> list[str]:
    """The wires of the link's harness that join its two cable connectors (the ones that plug into
    the link's device connectors), by ID. Empty while no harness was made from the link."""
    h = project.harnesses.get(link.harness_id or "")
    if h is None:
        return []
    cable = {c.mates_with: c.id for c in h.connectors if c.mates_with}
    ends = {cable.get(link.a_connector), cable.get(link.b_connector)}
    if None in ends or len(ends) != 2:
        return []
    return sorted(w.id for w in h.wires if {w.from_connector, w.to_connector} == ends)


TRACE_HEADER = ["Interface", "Name", "Type", "From", "To", "Harnesses", "Wires", "Routed"]
# A project with connections lists them under the interfaces: the first column then holds either
# an interface or a connection (its ID), and the last column says which. Projects without
# connections keep the eight columns above, byte for byte. A project in which an interface has a
# requirement ID gets a column Requirement after Routed (before Kind); a connection has none.
TRACE_HEADER_LINKS = ["Interface or connection", *TRACE_HEADER[1:], "Kind"]


def traceability(project: Project) -> Table:
    carried: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for h in project.harnesses.values():
        for w in h.wires:
            if w.interface_id:
                carried[w.interface_id].append((h.id, w.id))
    head = list(TRACE_HEADER_LINKS if project.links else TRACE_HEADER)
    req = uses_requirements(project)
    if req:
        head.insert(8, "Requirement")
    rows: Table = [head]
    kind = ["interface"] if project.links else []
    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        ends = [f"{e.unit_id}/{e.connector_id or '-'}" for e in i.endpoints]
        hs = sorted({h for h, _ in carried.get(i.id, [])})
        ws = sorted(w for _, w in carried.get(i.id, []))
        rows.append([i.id, i.name, i.type_id, ends[0] if ends else "", ends[1] if len(ends) > 1 else "", ";".join(hs), ";".join(ws), "yes" if ws else "no", *([i.requirement_id or ""] if req else []), *kind])  # fmt: skip
    types = carried_types(project)
    for link in sorted(project.links.values(), key=lambda x: x.id):
        wires = link_wires(project, link)
        rows.append([
            link.id, link.name or f"{link.a_connector} - {link.b_connector}",
            ";".join(types.get(link.id, [])),
            f"{device_of(project, link.a_connector) or '-'}/{link.a_connector}",
            f"{device_of(project, link.b_connector) or '-'}/{link.b_connector}",
            link.harness_id if link.harness_id in project.harnesses else "", ";".join(wires),
            "yes" if wires else "no", *([""] if req else []), "connection",
        ])  # fmt: skip
    return rows
