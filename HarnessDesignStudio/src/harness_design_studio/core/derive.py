"""How a number of the design was made: the equation, the inputs with their units and where each
came from, the intermediate results, the assumptions it rests on and what it is checked against.

This is the explanation behind the Why lines and the findings (D-191, step 1). It computes nothing
of its own that a result depends on: every value is produced by the same functions that the
generator and the design rules call (`sizing.wire_current_limit`, `sizing.voltage_drop_v`,
`lengths.wire_length`), so a derivation cannot disagree with the number it explains. The steps are
for the reader and are formatted, never fed back.

Five derivations exist so far: for a wire, its length, the derated current limit, the voltage drop
and its share of the mass; for a harness, its mass; for a part, its line of the bill of materials.
Readiness and the limits of the other rules follow.
"""

import math
from dataclasses import dataclass, field
from typing import Any

from harness_design_studio.core.assumptions import describe
from harness_design_studio.core.drc.base import cfg, number
from harness_design_studio.core.drc.rules import contact_rating, contact_rating_key
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.generate.lengths import path_trail, wire_length
from harness_design_studio.core.generate.mass import harness_mass, wire_mass_g
from harness_design_studio.core.generate.sizing import (
    ampacity_table,
    bundle_k,
    derated_limit,
    exceeds,
    voltage_drop_v,
    wire_current_limit,
)
from harness_design_studio.core.model import Harness, Project, Wire
from harness_design_studio.core.outputs.tables import BomContribution, bom_contributions
from harness_design_studio.core.units import AWG_MAX, AWG_MIN, awg_to_area_mm2, format_awg
from harness_design_studio.core.wires import find_wire


@dataclass(frozen=True)
class Input:
    name: str
    value: float | int | str | None
    unit: str
    source: str  # where it comes from: a key of config/*.json, a field of the design, the program


@dataclass(frozen=True)
class Step:
    label: str
    expression: str  # the numbers put into the equation, as text
    value: float
    unit: str


@dataclass(frozen=True)
class Check:
    """What the result is compared with: the actual value, the limit, the margin and the verdict."""

    actual: float
    limit: float
    unit: str
    passes: bool
    margin: float  # limit minus actual for an upper limit (positive: room left)
    text: str


@dataclass(frozen=True)
class Derivation:
    id: str  # the kind of derivation: "wire-current-limit", "wire-voltage-drop"
    subject: str  # what it is about: "Wire W001-001"
    quantity: str
    value: float | None  # None while an input is missing
    unit: str
    equation: str
    inputs: tuple[Input, ...] = ()
    steps: tuple[Step, ...] = ()
    check: Check | None = None
    assumptions: tuple[str, ...] = ()  # IDs of `core.assumptions`
    reference: str = ""
    missing: tuple[str, ...] = field(default_factory=tuple)  # what is not set yet, by name

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "quantity": self.quantity,
            "value": self.value,
            "unit": self.unit,
            "equation": self.equation,
            "inputs": [
                {"name": i.name, "value": i.value, "unit": i.unit, "source": i.source}
                for i in self.inputs
            ],
            "steps": [
                {"label": s.label, "expression": s.expression, "value": s.value, "unit": s.unit}
                for s in self.steps
            ],
            "check": None
            if self.check is None
            else {
                "actual": self.check.actual,
                "limit": self.check.limit,
                "unit": self.check.unit,
                "passes": self.check.passes,
                "margin": self.check.margin,
                "text": self.check.text,
            },
            "assumptions": [
                {"id": a.id, "title": a.title, "text": a.text, "kind": a.kind, "where": a.where}
                for a in describe(self.assumptions)
            ],
            "reference": self.reference,
            "missing": list(self.missing),
        }


def _g(x: float) -> str:
    return f"{x:g}"


def _unit(u: str) -> str:
    return f" {u}" if u else ""


def render(d: Derivation) -> str:
    """The derivation as text for a person: the number first, then how it was made."""
    out: list[str] = []
    head = d.quantity if d.value is None else f"{d.quantity}: {_g(d.value)}{_unit(d.unit)}"
    out.append(f"{d.subject}. {head}")
    out.append(f"  Equation: {d.equation}")
    if d.missing:
        out.append("  Not decided yet, because these are not set: " + "; ".join(d.missing))
    if d.inputs:
        out.append("  Inputs:")
        for i in d.inputs:
            value = (
                "not set"
                if i.value is None
                else f"{i.value if isinstance(i.value, str) else _g(i.value)}{_unit(i.unit)}"
            )
            out.append(f"    {i.name} = {value}   [{i.source}]")
    if d.steps:
        out.append("  Steps:")
        out.extend(f"    {s.label}: {s.expression} = {_g(s.value)}{_unit(s.unit)}" for s in d.steps)
    if d.check is not None:
        out.append(f"  Check: {d.check.text}")
    if d.assumptions:
        out.append("  Rests on:")
        for a in describe(d.assumptions):
            out.append(f"    {a.id} ({a.kind}) {a.title}. {a.text} [{a.where}]")
    if d.reference:
        out.append(f"  Reference: {d.reference}")
    return "\n".join(out)


def _bundle(
    derating: dict[str, object], wires_in_harness: int | None, harness_id: str
) -> tuple[float | None, Input | None, str, str | None]:
    """The bundle factor as `wire_current_limit` takes it: from the table when one is set, else
    the single factor. Returns (K, input, reference text, what is missing)."""
    from harness_design_studio.core.standard_profiles import BUNDLE_K

    single = number(derating.get("bundle_derating"))
    by_count = derating.get("bundle_factor_by_count")
    if isinstance(by_count, dict) and by_count and wires_in_harness is not None:
        k = bundle_k(by_count, wires_in_harness)
        if k is None:
            return (
                None,
                None,
                "",
                f"derating.bundle_factor_by_count (no entry for {wires_in_harness} wires)",
            )
        standard = by_count == BUNDLE_K
        source = (
            f"config/derating.json: bundle_factor_by_count, next listed count at or above "
            f"{wires_in_harness} wires, harness {harness_id} (A-BUNDLE-ALL)"
        )
        ref = (
            "Bundle factor K: ECSS-Q-ST-30-11C, Table 6-41 (the table of the project equals the "
            "standard's). "
            if standard
            else "Bundle factor K: the table of the project (config/derating.json), which is not "
            "the standard's table. "
        )
        return k, Input("Bundle factor K", k, "", source), ref, None
    if single is None:
        return None, None, "", "derating.bundle_derating"
    return (
        single,
        Input(
            "Bundle factor K",
            single,
            "",
            "config/derating.json: bundle_derating (one factor for every bundle)",
        ),
        "Bundle factor K: the one factor of the project. ",
        None,
    )


def wire_current_limit_derivation(project: Project, h: Harness, w: Wire) -> Derivation:
    """The current the wire's gauge may carry after derating, and what the wire carries."""
    derating = cfg(project, "derating")
    table = ampacity_table(derating.get("ampacity_a_by_awg"))
    temp = number(derating.get("temperature_derating"))
    wires = len(h.wires)
    k, k_input, k_ref, k_missing = _bundle(derating, wires, h.id)
    missing: list[str] = []
    if table is None:
        missing.append("derating.ampacity_a_by_awg")
    elif w.gauge_awg is None:
        missing.append(f"the gauge of wire {w.id}")
    elif w.gauge_awg not in table:
        missing.append(f"derating.ampacity_a_by_awg has no entry for AWG {w.gauge_awg}")
    if k_missing:
        missing.append(k_missing)
    if temp is None:
        missing.append("derating.temperature_derating")
    subject = f"Wire {w.id}"
    equation = "limit = base ampacity of the gauge × bundle factor K × temperature factor"
    assumptions = ("A-AMPACITY-AWG", "A-BUNDLE-ALL", "A-TEMP-FACTOR")
    limit = (
        wire_current_limit(derating, w.gauge_awg, wires)
        if not missing and w.gauge_awg is not None
        else None
    )
    if (
        limit is None
        or table is None
        or k is None
        or k_input is None
        or temp is None
        or w.gauge_awg is None
    ):
        return Derivation(
            "wire-current-limit", subject, "Derated current limit", None, "A", equation,
            assumptions=assumptions, missing=tuple(missing),
        )  # fmt: skip
    awg = w.gauge_awg
    base = table[awg]
    factor = k * temp
    inputs = [
        Input(
            f"Base ampacity of {format_awg(awg) if AWG_MIN <= awg <= AWG_MAX else f'AWG {awg}'}",
            base, "A", f'config/derating.json: ampacity_a_by_awg["{awg}"]',
        ),
        k_input,
        Input("Temperature factor", temp, "", "config/derating.json: temperature_derating"),
    ]  # fmt: skip
    steps = [
        Step("Combined factor", f"K × temperature = {_g(k)} × {_g(temp)}", factor, ""),
        Step(
            "Derated limit",
            f"base × combined factor = {_g(base)} × {_g(factor)}",
            derated_limit(base, k, temp),
            "A",
        ),
    ]
    check = None
    i = project.interfaces.get(w.interface_id or "")
    if i is not None and i.max_current_a is not None:
        inputs.append(
            Input("Current carried", i.max_current_a, "A", f"interface {i.id}: Max current")
        )
        ok = not exceeds(i.max_current_a, limit)
        check = Check(
            i.max_current_a, limit, "A", ok, limit - i.max_current_a,
            f"the wire carries {_g(i.max_current_a)} A and the limit is {_g(limit)} A: "
            + (f"within the limit, {_g(limit - i.max_current_a)} A to spare" if ok else f"over the limit by {_g(i.max_current_a - limit)} A"),
        )  # fmt: skip
    return Derivation(
        "wire-current-limit", subject, "Derated current limit", limit, "A", equation,
        tuple(inputs), tuple(steps), check, assumptions,
        k_ref + "Base ampacity table and temperature factor: the project's own values "
        "(config/derating.json); the project records no source for them.",
    )  # fmt: skip


def wire_voltage_drop_derivation(project: Project, h: Harness, w: Wire) -> Derivation:
    """The voltage drop over the wire at the current of its interface, against the limit."""
    derating, generation = cfg(project, "derating"), cfg(project, "generation")
    limit = number(derating.get("max_voltage_drop_v"))
    rho = number(generation.get("conductor_resistivity_ohm_m"))
    i = project.interfaces.get(w.interface_id or "")
    itype = project.interface_types.get(i.type_id) if i else None
    length = wire_length(h, w)
    subject = f"Wire {w.id}"
    equation = "ΔV = I × ρ × L / A × n"
    assumptions = ("A-DC-SOLID", "A-ROUND-TRIP")
    missing: list[str] = []
    if i is None or i.max_current_a is None:
        missing.append("the current of the interface (set Max current on the interface)")
    if rho is None:
        missing.append("generation.conductor_resistivity_ohm_m")
    if limit is None:
        missing.append("derating.max_voltage_drop_v")
    if not length:
        missing.append("the length of the wire (enter routing segment lengths)")
    if w.gauge_awg is None:
        missing.append(f"the gauge of wire {w.id}")
    elif not AWG_MIN <= w.gauge_awg <= AWG_MAX:
        missing.append(f"a gauge of {AWG_MIN} to {AWG_MAX} (the wire has AWG {w.gauge_awg})")
    current = i.max_current_a if i is not None else None
    if (
        missing
        or i is None
        or current is None
        or itype is None
        or rho is None
        or not length
        or w.gauge_awg is None
    ):
        return Derivation(
            "wire-voltage-drop", subject, "Voltage drop", None, "V", equation,
            assumptions=assumptions, missing=tuple(missing),
        )  # fmt: skip
    n = 2 if itype.category in ("power", "ground") else 1
    awg = w.gauge_awg
    area = awg_to_area_mm2(awg)
    drop = voltage_drop_v(current, rho, length, awg, n)
    own = w.length_m is not None
    inputs = [
        Input("Current I", current, "A", f"interface {i.id}: Max current"),
        Input("Resistivity ρ", rho, "Ω·m", "config/generation.json: conductor_resistivity_ohm_m"),
        Input(
            "Length L", length, "m",
            f"the length of wire {w.id} itself" if own else f"the routing segments of harness {h.id} between its connectors",
        ),
        Input("Gauge", awg, "AWG", f"wire {w.id}"),
        Input(
            "Conductors counted n", n, "",
            f"category '{itype.category}' of interface type {itype.id}: 2 for power and ground, 1 otherwise (A-ROUND-TRIP)",
        ),
    ]  # fmt: skip
    resistance = rho * length / (area * 1e-6) * n
    steps = [
        Step("Cross-section A", f"π/4 × d², d = 0.127 mm × 92^((36 − {awg})/39)", area, "mm²"),
        Step("Resistance of the conductors counted", f"ρ × L / A × n = {_g(rho)} × {_g(length)} / {_g(area * 1e-6)} × {n}", resistance, "Ω"),
        Step("Voltage drop", f"I × resistance = {_g(current)} × {_g(resistance)}", current * resistance, "V"),
    ]  # fmt: skip
    check = None
    if limit is not None:
        ok = not exceeds(drop, limit)
        check = Check(
            drop, limit, "V", ok, limit - drop,
            f"the drop is {_g(drop)} V and the limit is {_g(limit)} V: "
            + (f"within the limit, {_g(limit - drop)} V to spare" if ok else f"over the limit by {_g(drop - limit)} V"),
        )  # fmt: skip
    return Derivation(
        "wire-voltage-drop", subject, "Voltage drop", drop, "V", equation,
        tuple(inputs), tuple(steps), check, assumptions,
        "Resistance of a solid round conductor; the cross-section follows the AWG definition "
        "(core/units.py). The resistivity and the limit are the project's own values "
        "(config/generation.json, config/derating.json); the project records no source for them.",
    )  # fmt: skip


def wire_length_derivation(project: Project, h: Harness, w: Wire) -> Derivation:
    """Where the length of the wire comes from: the routing segments of its path and the service
    loops generation added, or a length stored on the wire itself."""
    generation = cfg(project, "generation")
    loop = number(generation.get("service_loop_m"))
    subject = f"Wire {w.id}"
    equation = "L = sum of the routing segments between its connectors + 2 × service loop"
    assumptions = ("A-PATH-UNIQUE", "A-SERVICE-LOOP")
    length = wire_length(h, w)
    trail = path_trail(h, w.from_connector, w.to_connector) if h.segments else None
    known = trail is not None and all(x is not None for _, x in trail)
    seg_sum = float(sum(x for _, x in trail if x is not None)) if trail and known else None
    if w.length_m is None and length is None:
        missing = [
            "the length of the wire (enter routing segment lengths, or set a length on the wire)"
        ]
        if not h.segments:
            missing = [
                "the length of the wire: the harness has no routing segments, and the wire has no length of its own"
            ]
        elif trail is None:
            missing = [
                "a unique path between the connectors of the wire (the segments form a loop or do not connect them: see the rule segment-loop)"
            ]
        elif not known:
            missing = [
                "the length of every routing segment on the path: "
                + ", ".join(sid for sid, x in trail if x is None)
            ]
        return Derivation(
            "wire-length", subject, "Length", None, "m", equation,
            assumptions=assumptions, missing=tuple(missing),
        )  # fmt: skip
    if (
        length is None
    ):  # a length is stored but the wire function disagrees: never happens, kept honest
        return Derivation(
            "wire-length", subject, "Length", None, "m", equation, assumptions=assumptions
        )
    inputs: list[Input] = []
    steps: list[Step] = []
    if trail is not None and known and seg_sum is not None:
        for sid, x in trail:
            inputs.append(
                Input(f"Segment {sid}", x, "m", f"routing segment {sid} of harness {h.id}")
            )
        inputs.append(
            Input(
                "Service loop",
                loop,
                "m",
                "config/generation.json: service_loop_m"
                if loop is not None
                else "config/generation.json: service_loop_m is not set (0 used)",
            )
        )
        steps.append(
            Step(
                "Path through the segments",
                " + ".join(_g(x) for _, x in trail if x is not None) or "0",
                seg_sum,
                "m",
            )
        )
        extra = 2 * (loop or 0.0)
        steps.append(Step("Service loops, one at each end", f"2 × {_g(loop or 0.0)}", extra, "m"))
        steps.append(Step("Generated length", f"{_g(seg_sum)} + {_g(extra)}", seg_sum + extra, "m"))
    if w.length_m is None:
        basis = "the routing segments of its path (no length is stored on the wire; no service loop is added here)"
        value = length
        if seg_sum is not None:
            steps = steps[:1]
    elif seg_sum is not None and math.isclose(
        w.length_m, seg_sum + 2 * (loop or 0.0), rel_tol=0, abs_tol=1e-9
    ):
        basis = "generated: the path through the segments plus two service loops"
        value = w.length_m
    else:
        basis = (
            "entered by hand and locked, so generation keeps it"
            if w.locked
            else "a length stored on the wire that does not equal its path plus two service loops (entered, imported, or the segments changed since)"
        )
        value = w.length_m
        inputs.insert(0, Input("Length stored on the wire", w.length_m, "m", f"wire {w.id}"))
    steps.append(Step("Length used by the tables, mass and rules", basis, value, "m"))
    return Derivation(
        "wire-length", subject, "Length", value, "m", equation,
        tuple(inputs), tuple(steps), None, assumptions,
        "Segment lengths are entered or imported by the engineer (the project records no source "
        "for them). The service loop is the project's own value; the tool adds no bend radius, "
        "tolerance or allowance for the connector.",
    )  # fmt: skip


def wire_mass_derivation(project: Project, h: Harness, w: Wire) -> Derivation:
    """The mass of the wire: its part's mass per metre times its length, over the part's conductors."""
    subject = f"Wire {w.id}"
    equation = "m = mass per metre of the wire part × L / conductors of the part"
    assumptions = ("A-MASS-CONDUCTORS", "A-MASS-SCOPE")
    part = project.parts.get(w.part_id) if w.part_id else None
    length = wire_length(h, w)
    missing: list[str] = []
    if part is None:
        missing.append(f"the wire part of wire {w.id} (set its type)")
    elif part.mass_per_m_g is None:
        missing.append(f"the mass per metre of wire part {part.id}")
    if length is None:
        missing.append(f"the length of wire {w.id}")
    if missing or part is None or part.mass_per_m_g is None or length is None:
        return Derivation(
            "wire-mass", subject, "Mass", None, "g", equation,
            assumptions=assumptions, missing=tuple(missing),
        )  # fmt: skip
    value = wire_mass_g(part.mass_per_m_g, length, part.conductors)
    inputs = (
        Input("Mass per metre", part.mass_per_m_g, "g/m", f"wire part {part.id}: mass_per_m_g"),
        Input("Length L", length, "m", "see the derivation of the length"),
        Input("Conductors of the part", part.conductors, "", f"wire part {part.id}: conductors"),
    )
    steps = (
        Step(
            "Mass of this wire",
            f"{_g(part.mass_per_m_g)} × {_g(length)} / {part.conductors}",
            value, "g",
        ),
    )  # fmt: skip
    return Derivation(
        "wire-mass", subject, "Mass", value, "g", equation, inputs, steps, None, assumptions,
        "The masses are those of the project's parts library; the project records no source "
        "for a mass unless the part's note says so.",
    )  # fmt: skip


def harness_mass_derivation(project: Project, h: Harness) -> Derivation:
    """The mass of a harness: every connector, the wires by part, the margin."""
    report = harness_mass(project, h)
    subject = f"Harness {h.id}"
    equation = (
        "m = sum of the connector masses + sum over wires of (mass per metre × L / conductors)"
    )
    assumptions = ("A-MASS-SCOPE", "A-MASS-CONDUCTORS")
    inputs: list[Input] = []
    steps: list[Step] = []
    conn_sum = 0.0
    for c in h.connectors:
        part = project.parts.get(c.part_id)
        inputs.append(
            Input(
                f"Connector {c.id}",
                None if part is None else part.mass_g,
                "g",
                f"part {c.part_id}: mass_g",
            )
        )
        if part is not None and part.mass_g is not None:
            conn_sum += part.mass_g
    steps.append(
        Step(f"Connectors ({len(h.connectors)})", "sum of the connector masses", conn_sum, "g")
    )
    by_part: dict[str, tuple[int, float, float]] = {}
    unknown = 0
    for w in h.wires:
        part = project.parts.get(w.part_id) if w.part_id else None
        length = wire_length(h, w)
        if part is None or part.mass_per_m_g is None or length is None:
            unknown += 1
            continue
        n, total_len, mass = by_part.get(part.id, (0, 0.0, 0.0))
        by_part[part.id] = (
            n + 1, total_len + length, mass + wire_mass_g(part.mass_per_m_g, length, part.conductors),
        )  # fmt: skip
    wire_sum = 0.0
    for pid in sorted(by_part):
        n, total_len, mass = by_part[pid]
        part = project.parts[pid]
        inputs.append(
            Input(
                f"Wire part {pid}: {n} wires, {_g(total_len)} m in all",
                part.mass_per_m_g, "g/m",
                f"part {pid}: mass_per_m_g (conductors {part.conductors})",
            )
        )  # fmt: skip
        steps.append(
            Step(
                f"Wires of part {pid} ({n})",
                f"sum of mass per metre × L / {part.conductors}",
                mass,
                "g",
            )
        )
        wire_sum += mass
    steps.append(Step("Total of what is known", "connectors + wires", conn_sum + wire_sum, "g"))
    margin = None
    if "generation" in project.config:
        value = project.config["generation"].values.get("mass_margin_fraction")
        if isinstance(value, int | float) and not isinstance(value, bool):
            margin = float(value)
    inputs.append(
        Input(
            "Mass margin fraction", margin, "",
            "config/generation.json: mass_margin_fraction" if margin is not None else "config/generation.json: mass_margin_fraction is not set",
        )
    )  # fmt: skip
    if margin is not None:
        steps.append(Step("Margin", f"total × {_g(margin)}", report.total_g * margin, "g"))
        steps.append(
            Step(
                "With margin", f"{_g(report.total_g)} + margin", report.total_g * (1 + margin), "g"
            )
        )
    missing = tuple(report.missing)
    note = (
        "A part has no mass or a wire no length: the total counts only what is known."
        if missing
        else ""
    )
    return Derivation(
        "harness-mass", subject, "Mass (total of what is known)" if missing else "Mass", report.total_g, "g",
        equation, tuple(inputs), tuple(steps), None, assumptions,
        ("The masses are those of the project's parts library. " + note).strip(),
        missing,
    )  # fmt: skip


_KINDS = {
    "connector": "connectors",
    "contact": "contacts",
    "wire": "wires",
    "accessory": "accessories",
}


def part_bom_derivation(project: Project, part_id: str, unit: str) -> Derivation:
    """Why the bill of materials has the quantity it has for a part, in `ea` or in `m`: every
    harness and every kind of thing that adds to it, counted by the function that writes the BOM."""
    harnesses = [project.harnesses[i] for i in sorted(project.harnesses)]
    mine = [
        c for c in bom_contributions(project, harnesses) if c.part_id == part_id and c.unit == unit
    ]
    part = project.parts.get(part_id)
    subject = f"Part {part_id}"
    is_m = unit == "m"
    equation = (
        "quantity = sum of the lengths of its wires / conductors of the part + the lengths of its accessories"
        if is_m
        else "quantity = connectors + contacts (one for each pin with a wire) + accessories, by quantity"
    )
    assumptions = (
        ("A-BOM-NO-ALLOWANCE", "A-BOM-CONTACTS")
        if "contact" in {c.kind for c in mine}
        else ("A-BOM-NO-ALLOWANCE",)
    )
    missing: list[str] = []
    if part is None:
        missing.append(
            f"part {part_id} is not in the parts list: its category, mass and approval are unknown"
        )
    unknown = [c for c in mine if c.unknown]
    if unknown:
        shown = ", ".join(c.source for c in unknown[:6]) + (", ..." if len(unknown) > 6 else "")
        missing.append(
            f"{len(unknown)} wire(s) of this part have no length and add nothing: {shown}"
        )
    value = 0.0
    for c in mine:
        if not c.unknown:
            value += c.amount
    inputs: list[Input] = []
    if part is not None:
        inputs.append(Input("Category", part.category, "", f"parts library: {part_id}"))
        inputs.append(Input("Approval", part.approval, "", f"parts library: {part_id}"))
        if part.category == "wire" or is_m:
            inputs.append(
                Input(
                    "Conductors of the part",
                    part.conductors,
                    "",
                    f"parts library: {part_id}: conductors",
                )
            )
    steps: list[Step] = []
    groups: dict[tuple[str, str], list[BomContribution]] = {}
    for c in mine:
        groups.setdefault((c.harness_id, c.kind), []).append(c)
    for (hid, kind), items in groups.items():
        total = 0.0
        for c in items:
            if not c.unknown:
                total += c.amount
        if kind == "wire":
            known = [c for c in items if not c.unknown]
            conductors = part.conductors if part is not None else 1
            expression = f"{len(known)} wire(s), their lengths summed, / {conductors}"
        else:
            expression = f"{len(items)} {_KINDS[kind]}" + (
                " (by their quantity)" if kind == "accessory" and not is_m else ""
            )
        steps.append(Step(f"Harness {hid}: {_KINDS[kind]}", expression, total, unit))
    steps.append(Step("Quantity in the bill of materials", "sum of the lines above", value, unit))
    return Derivation(
        "part-bom", subject, f"BOM quantity ({unit})", value, unit, equation,
        tuple(inputs), tuple(steps), None, assumptions,
        "The quantity is the one the file system/bom.csv has for this part and unit; the lengths of "
        "the wires are explained on the wire length page.",
        tuple(missing),
    )  # fmt: skip


def contact_current_derivation(
    project: Project, interface_id: str, connector_id: str
) -> Derivation:
    """The current an interface carries at a connector, against what the contacts of that
    connector's part allow after derating: the check of the rule `current-over-contact`."""
    subject = f"Interface {interface_id} at connector {connector_id}"
    equation = "limit = contact rating of the connector part × contact current factor"
    assumptions = ("A-CONTACT-SHARED",)
    i = project.interfaces.get(interface_id)
    conn = project.connectors.get(connector_id)
    factor = number(cfg(project, "derating").get("contact_current_factor"))
    key = contact_rating_key(project)
    rating = contact_rating(project, conn) if conn is not None else None
    missing: list[str] = []
    if i is None or i.max_current_a is None:
        missing.append("the current of the interface (set Max current on the interface)")
    if conn is None:
        missing.append(f"connector {connector_id}")
    elif rating is None:
        missing.append(
            f"the rating '{key}' of the connector part {conn.part_id} (a rating of the part in the library)"
        )
    if factor is None:
        missing.append("derating.contact_current_factor")
    if (
        missing
        or i is None
        or conn is None
        or i.max_current_a is None
        or rating is None
        or factor is None
    ):
        return Derivation(
            "contact-current", subject, "Contact current limit", None, "A", equation,
            assumptions=assumptions, missing=tuple(missing),
        )  # fmt: skip
    limit = rating * factor
    ok = not exceeds(i.max_current_a, limit)
    inputs = (
        Input("Current of the interface", i.max_current_a, "A", f"interface {i.id}: Max current"),
        Input(
            f"Contact rating '{key}'", rating, "A",
            f"connector part {conn.part_id}: ratings.{key} (the key is config/derating.json: contact_rating_key)",
        ),
        Input("Contact current factor", factor, "", "config/derating.json: contact_current_factor"),
    )  # fmt: skip
    steps = (Step("Limit after derating", f"{_g(rating)} × {_g(factor)}", limit, "A"),)
    check = Check(
        i.max_current_a, limit, "A", ok, limit - i.max_current_a,
        f"the interface carries {_g(i.max_current_a)} A and the contacts allow {_g(limit)} A: "
        + (f"within the limit, {_g(limit - i.max_current_a)} A to spare" if ok else f"over the limit by {_g(i.max_current_a - limit)} A"),
    )  # fmt: skip
    return Derivation(
        "contact-current", subject, "Contact current limit", limit, "A", equation,
        inputs, steps, check, assumptions,
        "The rating is a value of the parts library of the project and the factor is the project's "
        "own (config/derating.json); the project records no source for either.",
    )  # fmt: skip


def explain_part(project: Project, part_id: str) -> list[Derivation]:
    """The lines of the bill of materials for a part: one for each unit it is counted in."""
    harnesses = [project.harnesses[i] for i in sorted(project.harnesses)]
    units = sorted({c.unit for c in bom_contributions(project, harnesses) if c.part_id == part_id})
    if not units:
        raise EditError(f"'{part_id}' is not a wire, a harness or a part used in a harness.")
    return [part_bom_derivation(project, part_id, u) for u in units]


# The rules whose finding has a calculation behind it, and what the object of the finding is.
EXPLAINABLE_RULES = frozenset({"current-over-wire", "voltage-drop", "current-over-contact"})


def explain_finding(project: Project, rule_id: str, object_id: str) -> list[Derivation]:
    """The calculation behind one finding: the derivation of the limit the rule checked, for the
    object the finding names (a wire for `current-over-wire` and `voltage-drop`, INTERFACE.CONNECTOR
    for `current-over-contact`). Another rule, or an object that is gone, gives none."""
    try:
        if rule_id in ("current-over-wire", "voltage-drop"):
            h, w = find_wire(project, object_id)
            if rule_id == "current-over-wire":
                return [wire_current_limit_derivation(project, h, w)]
            return [wire_voltage_drop_derivation(project, h, w)]
        if rule_id == "current-over-contact":
            left, _, right = object_id.partition(".")
            if right:
                return [contact_current_derivation(project, left, right)]
    except EditError:
        return []
    return []


def explain_harness(project: Project, harness_id: str) -> list[Derivation]:
    """Every derivation that exists for the harness."""
    h = project.harnesses.get(harness_id)
    if h is None:
        raise EditError(f"Harness '{harness_id}' does not exist.")
    return [harness_mass_derivation(project, h)]


def explain_object(project: Project, object_id: str) -> list[Derivation]:
    """A harness, a wire, a part used in a harness, or the contacts of an interface at a connector
    (INTERFACE.CONNECTOR, the object of a `current-over-contact` finding), by its ID."""
    if object_id in project.harnesses:
        return explain_harness(project, object_id)
    if any(w.id == object_id for h in project.harnesses.values() for w in h.wires):
        return explain_wire(project, object_id)
    left, _, right = object_id.partition(".")
    if right and left in project.interfaces and right in project.connectors:
        return [contact_current_derivation(project, left, right)]
    return explain_part(project, object_id)


def explain_wire(project: Project, wire_id: str) -> list[Derivation]:
    """Every derivation that exists for the wire, in the order a reader asks: how long is it, how
    much current may it carry, then how much voltage does it drop."""
    h, w = find_wire(project, wire_id)
    return [
        wire_length_derivation(project, h, w),
        wire_current_limit_derivation(project, h, w),
        wire_voltage_drop_derivation(project, h, w),
        wire_mass_derivation(project, h, w),
    ]
