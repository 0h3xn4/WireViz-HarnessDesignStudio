"""Tables derived from the model: wire list, pinouts, BOM, mass and length, tests, labels,
matrices. Each function returns `Table` (header row first). No design numbers are invented:
unknown values are written as "pending", "unknown" or "TBD (placeholder)"."""

from collections import defaultdict
from collections.abc import Collection
from decimal import Decimal

from harness_design_studio.core.generate.lengths import clear_length_cache, wire_length
from harness_design_studio.core.generate.mass import harness_mass
from harness_design_studio.core.model import Connector, Harness, Project, Wire

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


def uses_wire_text(project: Project) -> bool:
    """True when a person gave any wire a label or a note (1.4.0)."""
    return any(w.label or w.note for h in project.harnesses.values() for w in h.wires)


def wire_name(w: Wire) -> str:
    """What the labels of a wire print after its ID: the person's label, else the signal."""
    return w.label or w.signal or ""


def wire_list(project: Project, h: Harness) -> Table:
    """The EMC class column exists only when the project defines EMC classes, and the Label and
    Note columns only when a person gave a wire one, so projects that do not use them keep
    byte-identical wire lists."""
    shields = shield_of(h)
    emc = uses_emc_classes(project)
    text = uses_wire_text(project)
    rows: Table = [[
        "Wire", "Signal", "Interface", "From connector", "From pin", "To connector", "To pin",
        "AWG", "Part", "Colour", "Length (m)", "Shield group", "Locked",
        *(["EMC class"] if emc else []), *(["Label", "Note"] if text else []),
    ]]  # fmt: skip
    for w in sorted(h.wires, key=lambda x: x.id):
        rows.append([
            w.id, w.signal or "", w.interface_id or "", w.from_connector, w.from_pin,
            w.to_connector, w.to_pin, PENDING if w.gauge_awg is None else str(w.gauge_awg),
            w.part_id or "", w.colour or "", data_num(wire_length(h, w)), shields.get(w.id, ""),
            "yes" if w.locked else "", *([emc_class_of(project, w)] if emc else []),
            *([w.label or "", w.note] if text else []),
        ])  # fmt: skip
    return rows


def _pin_rows(project: Project, c: Connector, attached: dict[tuple[str, str], list[str]]) -> Table:
    rows: Table = []
    for p in c.pins:
        wires = attached.get((c.id, p.id), [])
        rows.append([
            c.id, c.role, c.mates_with or "", c.part_id, p.id, p.signal or "", p.interface_id or "",
            ";".join(sorted(wires)), "no" if wires or p.interface_id or p.signal else "yes",
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


def pinouts(project: Project, h: Harness) -> Table:
    attached: dict[tuple[str, str], list[str]] = defaultdict(list)
    for w in h.wires:
        attached[(w.from_connector, w.from_pin)].append(w.id)
        attached[(w.to_connector, w.to_pin)].append(w.id)
    rows = [PINOUT_HEADER]
    for c in sorted(h.connectors, key=lambda x: x.id):
        rows += _pin_rows(project, c, attached)
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
    rows = [PINOUT_HEADER]
    for c in sorted(project.connectors.values(), key=lambda x: x.id):
        if connector_ids is None or c.id in connector_ids:
            rows += _pin_rows(project, c, attached)
    return rows


BOM_HEADER = [
    "Part", "Category", "Manufacturer", "Part number", "Description", "Approval",
    "Quantity", "Unit", "Wires without length", "Used in",
]  # fmt: skip


def bom(project: Project, harnesses: list[Harness]) -> Table:
    counts: dict[str, int] = defaultdict(int)
    metres: dict[str, float] = defaultdict(float)
    unknown: dict[str, int] = defaultdict(int)
    used: dict[str, set[str]] = defaultdict(set)
    for h in harnesses:
        for c in h.connectors:
            counts[c.part_id] += 1
            used[c.part_id].add(h.id)
        for w in h.wires:
            pid = w.part_id or "(no part)"
            used[pid].add(h.id)
            length = wire_length(h, w)
            if length is None:
                unknown[pid] += 1
            else:
                metres[pid] += length
            metres.setdefault(pid, 0.0)
    rows = [BOM_HEADER]
    for pid in sorted({*counts, *metres}):
        part = project.parts.get(pid)
        is_wire = pid in metres
        rows.append([
            pid, part.category if part else "unknown", (part.manufacturer or "") if part else "",
            (part.part_number or "") if part else "", (part.description or "") if part else "",
            ("missing from parts list" if part is None else part.approval + (" (example data)" if part.unverified else "")),
            data_num(metres[pid]) if is_wire else str(counts[pid]), "m" if is_wire else "ea",
            str(unknown[pid]) if is_wire else "", ";".join(sorted(used[pid])),
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
    for c in sorted(h.connectors, key=lambda x: x.id):
        rows.append([f"{c.id}", "connector", f"{c.id} mates {c.mates_with or '-'}", "1"])
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


def traceability(project: Project) -> Table:
    carried: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for h in project.harnesses.values():
        for w in h.wires:
            if w.interface_id:
                carried[w.interface_id].append((h.id, w.id))
    rows: Table = [["Interface", "Name", "Type", "From", "To", "Harnesses", "Wires", "Routed"]]
    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        ends = [f"{e.unit_id}/{e.connector_id or '-'}" for e in i.endpoints]
        hs = sorted({h for h, _ in carried.get(i.id, [])})
        ws = sorted(w for _, w in carried.get(i.id, []))
        rows.append([i.id, i.name, i.type_id, ends[0] if ends else "", ends[1] if len(ends) > 1 else "", ";".join(hs), ";".join(ws), "yes" if ws else "no"])  # fmt: skip
    return rows
