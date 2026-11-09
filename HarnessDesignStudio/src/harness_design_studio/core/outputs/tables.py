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
used both ways has one line per unit (`ea` first, then `m`); the key of a line is part and unit.

A loose cable end (role `loose`, M4 of the 2.0 programme, D-201) is named as what it is, and only
where a harness has one, so every other table keeps its bytes: its part reads
`TBD-CONNECTOR (loose end)`, what it mates with `open end`, its label `W009-P2 open end`; the BOM
counts the ends on one line `(open end)` with the approval `to fill in` instead of a line for the
placeholder part; a test that names a pin of it says `(open end)` and expects nothing yet (`test
when the end is decided`); the mass never counts it (`generate/mass.py`). The independent verifier
(`verify.py`) words all of it again on its own."""

import math
from collections import defaultdict
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from decimal import Decimal

from harness_design_studio.core import label_format, settings
from harness_design_studio.core.deviations import (
    override_text,
    tests_cell,
    uses_overrides,
    wire_marks,
)
from harness_design_studio.core.generate.lengths import clear_length_cache, wire_length
from harness_design_studio.core.generate.mass import harness_mass, pins_in_use
from harness_design_studio.core.model import Connector, Harness, Link, Pin, Project, Wire
from harness_design_studio.core.model.physical import LOOSE_ROLE

from .stamp import Table

PENDING = "pending"
TBD = "TBD (placeholder)"
TO_FILL = "to fill in"  # the words of a value a person still has to give (the build workbook's too)
# A loose cable end (D-201 decision 2): what the tables say instead of a part and a mate.
OPEN_END = "open end"
LOOSE_PART_TAG = " (loose end)"  # after the placeholder part: `TBD-CONNECTOR (loose end)`
OPEN_END_PART = "(open end)"  # the BOM line that counts the ends, like `(no part)` for wires
OPEN_END_DESCRIPTION = "Connector not chosen yet (loose end)"
OPEN_END_TEST = "test when the end is decided"  # the Expected cell of a test at an open end


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


def is_open_end(c: Connector) -> bool:
    """True for a loose cable end: a connector of a harness that is not on a connector yet."""
    return c.role == LOOSE_ROLE


def part_text(c: Connector) -> str:
    """The part of a connector as the tables write it: `TBD-CONNECTOR (loose end)` for a loose end."""
    return c.part_id + LOOSE_PART_TAG if is_open_end(c) else c.part_id


def mates_text(c: Connector) -> str:
    """What a connector mates with as the tables write it: `open end` for a loose end."""
    return OPEN_END if is_open_end(c) else (c.mates_with or "")


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
    over = uses_overrides(project)
    rows: Table = [[
        "Wire", "Signal", "Interface", "From connector", "From pin", "To connector", "To pin",
        "AWG", "Part", "Colour", "Length (m)", "Shield group", "Locked",
        *(["EMC class"] if emc else []), *(["Requirement"] if req else []),
        *(["Label", "Note"] if text else []),
        *(["Strip A (mm)", "Strip B (mm)"] if strip else []),
        *(["Overrides"] if over else []),
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
            *([override_text(w)] if over else []),
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
            c.id, c.role, mates_text(c), part_text(c), p.id, p.signal or sig,
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


@dataclass(frozen=True)
class BomContribution:
    """One thing that adds to a line of the BOM: what, where it is, how much, in which unit.
    The BOM is the sum of these (`bom`), and the explanation of a line lists them (`core.derive`),
    so the two cannot disagree."""

    part_id: str
    unit: str  # "ea" or "m"
    amount: float  # a count for "ea", metres for "m"; 0 for a wire whose length is unknown
    harness_id: str
    # "connector", "contact", "wire" or "accessory"; "contact spare" and "wire allowance" only when
    # the setting model.bom_contact_spare_fraction or model.bom_wire_allowance_fraction is above 0
    kind: str
    source: str  # the ID of the connector, pin (connector.pin), wire or accessory
    unknown: bool = False  # a wire with no length: it adds nothing to the metres


def bom_contributions(project: Project, harnesses: list[Harness]) -> list[BomContribution]:
    """What the BOM counts, in the order it counts it: connector parts and contact parts (one per
    pin in use) in `ea`; wire parts in metres (the wire's length over the conductors of its part);
    accessory parts in `ea`, or in metres when they have a length. The two settings of
    `config/model.json` that are 0 by default add lines of their own: spare contacts (A-BOM-CONTACTS)
    and an allowance on the wire metres (A-BOM-NO-ALLOWANCE)."""
    found: list[BomContribution] = []
    spare_fraction = settings.number(project, "model", "bom_contact_spare_fraction")
    allowance = settings.number(project, "model", "bom_wire_allowance_fraction")
    for h in harnesses:
        in_use = pins_in_use(h)
        contacts: dict[str, int] = defaultdict(int)
        for c in h.connectors:
            # a loose end is counted as an end on the line `(open end)`, not as the placeholder part
            pid = OPEN_END_PART if is_open_end(c) else c.part_id
            found.append(BomContribution(pid, "ea", 1, h.id, "connector", c.id))
            for p in c.pins:
                if p.contact_part and (c.id, p.id) in in_use:
                    contacts[p.contact_part] += 1
                    found.append(
                        BomContribution(p.contact_part, "ea", 1, h.id, "contact", f"{c.id}.{p.id}")
                    )
        if spare_fraction > 0:
            for part_id, used in sorted(contacts.items()):
                # rounded to 9 decimals first, so 30 x 0.1 is 3 spares and not 4 (float noise)
                spares = math.ceil(round(used * spare_fraction, 9))
                if spares:
                    found.append(
                        BomContribution(part_id, "ea", spares, h.id, "contact spare", part_id)
                    )
        for w in h.wires:
            pid = w.part_id or "(no part)"
            length = wire_length(h, w)
            if length is None:
                found.append(BomContribution(pid, "m", 0.0, h.id, "wire", w.id, unknown=True))
            else:
                part = project.parts.get(pid)
                share = length / (part.conductors if part else 1)
                found.append(BomContribution(pid, "m", share, h.id, "wire", w.id))
                if allowance > 0:
                    found.append(
                        BomContribution(pid, "m", share * allowance, h.id, "wire allowance", w.id)
                    )
        for a in h.accessories:
            if not a.part_id:
                continue
            if a.length_mm is None:
                found.append(BomContribution(a.part_id, "ea", a.quantity, h.id, "accessory", a.id))
            else:
                metres = a.length_mm * a.quantity / 1000
                found.append(BomContribution(a.part_id, "m", metres, h.id, "accessory", a.id))
    return found


def bom(project: Project, harnesses: list[Harness]) -> Table:
    """One line per part and unit: connector parts, contact parts (one per pin in use) and accessory
    parts without a length count `ea`; wire parts and accessory parts with a length add up metres."""
    counts: dict[str, int] = defaultdict(int)
    metres: dict[str, float] = defaultdict(float)
    metre_parts: set[str] = set()
    wire_parts: set[str] = set()
    unknown: dict[str, int] = defaultdict(int)
    used: dict[str, set[str]] = defaultdict(set)
    for c in bom_contributions(project, harnesses):
        used[c.part_id].add(c.harness_id)
        if c.unit == "ea":
            counts[c.part_id] += int(c.amount)
            continue
        metre_parts.add(c.part_id)
        if c.kind == "wire":
            wire_parts.add(c.part_id)
        if c.unknown:
            unknown[c.part_id] += 1
        else:
            metres[c.part_id] += c.amount
    rows = [BOM_HEADER]
    for pid, unit in sorted({*((p, "ea") for p in counts), *((p, "m") for p in metre_parts)}):
        part = project.parts.get(pid)
        is_m = unit == "m"
        if pid == OPEN_END_PART and not is_m:  # the loose ends: no part to approve, one to choose
            rows.append([
                pid, "connector", "", "", OPEN_END_DESCRIPTION, TO_FILL, str(counts[pid]), unit,
                "", ";".join(sorted(used[pid])),
            ])  # fmt: skip
            continue
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


# The three test limits of the test sheet: the key of config/generation.json, the unit the sheet
# writes after the number, and what the limit is for.
TEST_LIMITS: tuple[tuple[str, str, str], ...] = (
    ("test_continuity_max_ohm", "ohm max", "continuity"),
    ("test_isolation_min_mohm", "Mohm min", "isolation"),
    ("test_isolation_voltage_v", "V", "isolation voltage"),
)


def limit_value(project: Project, key: str) -> float | None:
    """The number of a test limit, or None while the key is not set (the sheet shows TBD)."""
    v = _cfg(project, key)
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None


def _limit(project: Project, key: str, unit: str) -> str:
    v = limit_value(project, key)
    return f"{v:g} {unit}" if v is not None else TBD


def tests(project: Project, h: Harness, marks: bool = True) -> Table:
    """The tests of a harness. A last column `Deviations` exists only when a test is about a wire
    that has an override or a deviation (1.13): the field or rule and the reason. `marks=False`
    leaves the column out (for a reader that needs only the positions of the first 8 columns and
    must not run the checks again)."""
    cont = _limit(project, "test_continuity_max_ohm", "ohm max")
    iso = _limit(project, "test_isolation_min_mohm", "Mohm min")
    volts = _limit(project, "test_isolation_voltage_v", "V")
    rows: Table = [["Test", "Type", "From", "To", "Expected", "Limit", "Test voltage", "Wire"]]
    loose = {c.id for c in h.connectors if is_open_end(c)}  # a test there waits for the end

    def end(cid: str, pin: str) -> str:
        return f"{cid}.{pin}" + (f" ({OPEN_END})" if cid in loose else "")

    n = 0
    for w in sorted(h.wires, key=lambda x: x.id):
        n += 1
        expect = OPEN_END_TEST if {w.from_connector, w.to_connector} & loose else "continuous"
        rows.append([f"T{n:03d}", "continuity", end(w.from_connector, w.from_pin), end(w.to_connector, w.to_pin), expect, cont, "", w.id])  # fmt: skip
    for w in sorted(h.wires, key=lambda x: x.id):
        n += 1
        expect = OPEN_END_TEST if w.from_connector in loose else "isolated"
        rows.append([f"T{n:03d}", "isolation", end(w.from_connector, w.from_pin), "all other wires and shields", expect, iso, volts, w.id])  # fmt: skip
    for s in sorted(h.shields, key=lambda x: x.id):
        n += 1
        rows.append([f"T{n:03d}", "isolation", f"shield {s.id}", "all wires", "isolated", iso, volts, ";".join(sorted(s.wire_ids))])  # fmt: skip
    found = wire_marks(project, h) if marks else {}
    if found:
        cells = [tests_cell(found, row[7]) for row in rows[1:]]
        if any(cells):
            rows[0].append("Deviations")
            for row, cell in zip(rows[1:], cells, strict=True):
                row.append(cell)
    return rows


def _harness_of(project: Project, w: Wire) -> Harness | None:
    return next((h for h in project.harnesses.values() if w in h.wires), None)


def wire_label_texts(project: Project, w: Wire, h: Harness | None = None) -> tuple[str, str]:
    """The text of the two labels of a wire (end A and end B), by the label format in force
    (`model.label_format`, core/label_format.py). The standard text: the wire ID, its name (the
    person's label, else the signal), the far end and the EMC class when the project uses classes."""
    far = f"{w.to_connector}.{w.to_pin}"
    near = f"{w.from_connector}.{w.from_pin}"
    emc = emc_class_of(project, w)
    tag = f" [EMC {emc}]" if emc else ""  # personnel can see the category (20-07C 4.2.13.1 d)
    name = wire_name(w)
    head = f"{w.id} {name}" if name else w.id  # a signal name keeps its own spacing
    fmt = label_format.format_of(project)
    if fmt == "compact":
        return f"{w.id} to {far}", f"{w.id} to {near}"
    if fmt == "descriptive":
        i = project.interfaces.get(w.interface_id or "")
        head = f"{head} ({i.id} {i.name})" if i is not None else head
    if fmt == "custom" and (tpl := label_format.template_of(project, "wire")) is not None:
        owner = h or _harness_of(project, w)
        values = {
            "harness": owner.id if owner else "", "wire": w.id, "signal": w.signal or "",
            "name": name, "interface": w.interface_id or "", "emc": emc,
        }  # fmt: skip
        return (
            label_format.fill(tpl, {**values, "end": "A", "from": near, "to": far}),
            label_format.fill(tpl, {**values, "end": "B", "from": far, "to": near}),
        )
    return f"{head} to {far}{tag}", f"{head} to {near}{tag}"


def connector_label_text(project: Project, c: Connector, h: Harness | None = None) -> str:
    """The text of the label of a cable connector by the label format in force: its name and what
    it mates (a loose end: `W009-P2 open end`, and `{mates}` of a template is `open end`)."""
    name = connector_label(project, c)
    loose = is_open_end(c)
    mates = f"{c.id} {OPEN_END}" if loose else f"{c.id} mates {c.mates_with or '-'}"
    fmt = label_format.format_of(project)
    if fmt == "compact":
        return mates
    box = project.connectors.get(c.mates_with or "")
    if fmt == "descriptive" and box is not None and box.unit_id:
        mates = f"{mates} of {box.unit_id}"
    if fmt == "custom" and (tpl := label_format.template_of(project, "connector")) is not None:
        owner = h or next((x for x in project.harnesses.values() if c in x.connectors), None)
        return label_format.fill(
            tpl,
            {
                "harness": owner.id if owner else "", "connector": c.id, "name": name,
                "mates": OPEN_END if loose else (c.mates_with or "-"),
                "device": (box.unit_id or "") if box else "",
            },
        )  # fmt: skip
    return f"{name} ({mates})" if name else mates


def label_duplicates(project: Project, h: Harness) -> list[tuple[str, list[str]]]:
    """The label texts that two or more labels of the harness share: (text, the label IDs). The
    labels of one harness must read differently from one another, whatever the format; the standard
    and the compact text hold the wire ID, a custom template may leave it out."""
    seen: dict[str, list[str]] = {}
    for row in labels(project, h)[1:]:
        if row[1] != "harness":
            seen.setdefault(row[2], []).append(row[0])
    return [(text, ids) for text, ids in seen.items() if len(ids) > 1]


def labels(project: Project, h: Harness) -> Table:
    rows: Table = [["Label", "Kind", "Text", "Quantity"]]
    if h.label:
        rows.append([h.id, "harness", h.label, "1"])
    for c in sorted(h.connectors, key=lambda x: x.id):
        rows.append([f"{c.id}", "connector", connector_label_text(project, c, h), "1"])
    for w in sorted(h.wires, key=lambda x: x.id):
        text_a, text_b = wire_label_texts(project, w, h)
        rows.append([f"{w.id}-A", "wire", text_a, "1"])
        rows.append([f"{w.id}-B", "wire", text_b, "1"])
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
