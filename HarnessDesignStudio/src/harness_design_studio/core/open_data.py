# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Open data: every intermediate and final result of a design as JSON and CSV (D-191, S5).

`export-data` writes, for one project, the numbers behind the outputs in a form a script or a
spreadsheet can read without the tool: for each result a pair of files with the same rows,
`<name>.json` (with a `format` number, the tool version, the model hash, the columns with their
units, and the rows) and `<name>.csv` (one header row with the unit in the name, `Current (A)`,
then the rows). The tables are:

    wire_sizing               per wire: current, gauge, cross-section, ampacity, the derating
                              factors and the bundle size, the limit, the length, the resistivity,
                              the voltage drop, its limit and margins, the part
    segmentation_groups       per group of interfaces: the key, the mode, the chain, the harness
    segmentation_interfaces   per interface: its group, class, chain, devices, zones, connectors
    pin_allocation            per pin of every device connector and cable connector
    rule_results              per limit a rule compares: actual, limit, margin, verdict
    readiness                 per harness and check of *Ready to build*: what is open
    lengths                   per wire: the length and its basis
    segment_lengths           per routing segment that has a length (`import-lengths` reads it)
    parts                     the parts library (`import-parts` reads it)
    mass, mass_wires          per harness and per wire
    bom, bom_contributions    the bill of materials and every line that adds to it
    findings                  every finding with the numbers of its rule when it has them
    test_limits               per test of the test sheet: the limit and the voltage
    settings                  every setting in force: value, unit, origin

and three files of their own: `configuration.json` (the configuration files as the tool used them,
with their placeholder flags), `provenance.json` (the tool, the design, the library, the imported
files and the hash of every other file written) and, only when asked, `run_record.json` (written
by `core.run_record`, never part of this set).

Nothing in them is a time, a user name or a path, so the same design written twice gives the same
files. The numbers are the ones the tool used: they come from the same functions the generator and
the design rules call, so a file cannot disagree with an output. A number is written with 12
significant digits (no floating point noise: 0.30000000000000004 is 0.3), which is more than any
input of the design has; a script that recomputes from the files agrees to 9 decimals. The AWG
gauge is written as the plain gauge with its cross-section in a column of its own (`area_mm2`).
"""

import csv
import hashlib
import io
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness_design_studio import __version__
from harness_design_studio.core import checks, settings
from harness_design_studio.core.checks import Finding
from harness_design_studio.core.derive import (
    Derivation,
    _bundle,
    contact_current_derivation,
    wire_current_limit_derivation,
    wire_length_derivation,
    wire_voltage_drop_derivation,
)
from harness_design_studio.core.derive_rules import INFO, LIMIT, explain_rule
from harness_design_studio.core.drc import run as run_drc
from harness_design_studio.core.drc.base import cfg, number
from harness_design_studio.core.errors import SaveError
from harness_design_studio.core.generate import bundle
from harness_design_studio.core.generate.bundle import bundle_size
from harness_design_studio.core.generate.lengths import wire_length
from harness_design_studio.core.generate.mass import harness_mass, wire_mass_g
from harness_design_studio.core.generate.segmentation import _cfg as _seg_cfg
from harness_design_studio.core.generate.segmentation import _class_of, segment
from harness_design_studio.core.generate.sizing import (
    ampacity_table,
    exceeds,
    voltage_drop_v,
    wire_current_limit,
)
from harness_design_studio.core.io.fs import atomic_write_bytes
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.model import Harness, Project, Wire
from harness_design_studio.core.outputs import tables as out_tables
from harness_design_studio.core.outputs.buildsheet import TO_FIX, readiness
from harness_design_studio.core.outputs.stamp import _safe
from harness_design_studio.core.units import AWG_MAX, AWG_MIN, awg_to_area_mm2
from harness_design_studio.core.vcs.hashing import content_hash

FORMAT = 1
PROVENANCE = "provenance.json"
CONFIGURATION = "configuration.json"
SIGNIFICANT = 12  # digits of a number in the files

Cell = str | int | float | bool | list[Any] | dict[str, Any] | None


@dataclass(frozen=True)
class Col:
    """A column: its key in the JSON rows, its name, its unit and what it holds."""

    key: str
    name: str
    unit: str = ""
    what: str = ""

    @property
    def header(self) -> str:
        return f"{self.name} ({self.unit})" if self.unit else self.name


@dataclass
class DataTable:
    name: str  # the file name without the extension
    title: str
    about: str
    cols: tuple[Col, ...]
    rows: list[dict[str, Any]]


def num(v: float | int | None) -> float | int | None:
    """A number as the files write it: 12 significant digits, so that a sum carries no floating
    point noise; a whole number and None as they are."""
    if v is None or isinstance(v, bool | int):
        return v
    return float(f"{v:.{SIGNIFICANT}g}") + 0.0  # + 0.0 turns -0.0 into 0.0


def _verdict(passes: bool | None) -> str:
    return "not checked" if passes is None else "pass" if passes else "fail"


def _yes(flag: bool) -> str:
    return "yes" if flag else ""


# ---- wires: sizing, lengths, mass ---------------------------------------------------------------


def _all_wires(project: Project) -> list[tuple[Harness, Wire]]:
    return [(h, w) for hid in sorted(project.harnesses) for h in [project.harnesses[hid]]
            for w in sorted(h.wires, key=lambda x: x.id)]  # fmt: skip


WIRE_SIZING = (
    Col("harness", "Harness"),
    Col("wire", "Wire"),
    Col("signal", "Signal"),
    Col("interface", "Interface"),
    Col("category", "Category", what="the category of the interface type"),
    Col("current_a", "Current", "A", "Max current of the interface the wire carries"),
    Col("gauge_awg", "Gauge", "AWG"),
    Col("area_mm2", "Cross-section", "mm²", "of a solid round conductor of the gauge (D-AWG)"),
    Col("part", "Part"),
    Col("length_m", "Length", "m"),
    Col("resistivity_ohm_m", "Resistivity", "Ω·m"),
    Col("conductors_counted", "Conductors counted", "", "2 for the way out and back, else 1"),
    Col(
        "voltage_drop_v", "Voltage drop", "V", "current × resistivity × length / area × conductors"
    ),
    Col("max_voltage_drop_v", "Largest drop allowed", "V"),
    Col("drop_margin_v", "Drop margin", "V", "limit minus drop; positive: room left"),
    Col("drop_verdict", "Drop verdict"),
    Col("base_ampacity_a", "Base ampacity", "A", "of the gauge, from derating.ampacity_a_by_awg"),
    Col("bundle_wires", "Wires in the bundle", "", "the count the bundle factor is looked up for"),
    Col("bundle_factor", "Bundle factor K"),
    Col("temperature_factor", "Temperature factor"),
    Col("limit_a", "Derated current limit", "A", "base ampacity × K × temperature factor"),
    Col("current_margin_a", "Current margin", "A", "limit minus current; positive: room left"),
    Col("current_verdict", "Current verdict"),
    Col("locked", "Locked", "", "yes: kept when generating again"),
    Col("missing", "Missing", "", "what is not set, so that a number above is empty"),
)


def wire_sizing(project: Project) -> DataTable:
    derating = cfg(project, "derating")
    table = ampacity_table(derating.get("ampacity_a_by_awg"))
    temp = number(derating.get("temperature_derating"))
    max_drop = number(derating.get("max_voltage_drop_v"))
    rho, _why = settings.resistivity(project)
    basis = bundle.basis(project)
    rows: list[dict[str, Any]] = []
    for h, w in _all_wires(project):
        i = project.interfaces.get(w.interface_id or "")
        itype = project.interface_types.get(i.type_id) if i else None
        current = i.max_current_a if i is not None else None
        awg = w.gauge_awg
        in_range = awg is not None and AWG_MIN <= awg <= AWG_MAX
        length = wire_length(h, w)
        n_bundle = bundle_size(project, h, w)
        k, _k_input, _ref, _k_missing = _bundle(derating, n_bundle, h.id, basis)
        base = table.get(awg) if table is not None and awg is not None else None
        limit = wire_current_limit(derating, awg, n_bundle)
        conductors = settings.drop_conductors(project, itype.category) if itype else None
        drop = (
            voltage_drop_v(current, rho, length, awg, conductors)
            if (
                in_range and awg is not None and current is not None and rho is not None
                and length and conductors is not None
            )
            else None
        )  # fmt: skip
        drop_ok = None if drop is None or max_drop is None else not exceeds(drop, max_drop)
        cur_ok = None if limit is None or current is None else not exceeds(current, limit)
        derivs = (
            wire_current_limit_derivation(project, h, w),
            wire_voltage_drop_derivation(project, h, w),
        )
        missing = "; ".join(dict.fromkeys(m for d in derivs for m in d.missing))
        rows.append({
            "harness": h.id, "wire": w.id, "signal": w.signal or "",
            "interface": w.interface_id or "", "category": itype.category if itype else "",
            "current_a": num(current), "gauge_awg": awg,
            "area_mm2": num(awg_to_area_mm2(awg)) if in_range and awg is not None else None,
            "part": w.part_id or "", "length_m": num(length), "resistivity_ohm_m": num(rho),
            "conductors_counted": conductors if drop is not None else None,
            "voltage_drop_v": num(drop), "max_voltage_drop_v": num(max_drop),
            "drop_margin_v": num(None if drop is None or max_drop is None else max_drop - drop),
            "drop_verdict": _verdict(drop_ok), "base_ampacity_a": num(base),
            "bundle_wires": n_bundle, "bundle_factor": num(k), "temperature_factor": num(temp),
            "limit_a": num(limit),
            "current_margin_a": num(None if limit is None or current is None else limit - current),
            "current_verdict": _verdict(cur_ok), "locked": _yes(w.locked), "missing": missing,
        })  # fmt: skip
    return DataTable(
        "wire_sizing",
        "Wire sizing",
        "One row for each wire: the numbers behind its gauge, current limit and voltage drop.",
        WIRE_SIZING,
        rows,
    )


LENGTHS = (
    Col("harness", "Harness"),
    Col("wire", "Wire"),
    Col("length_m", "Length", "m", "the length the tables, the mass and the rules use"),
    Col("basis", "Basis", "", "where the length comes from"),
    Col("path_m", "Path through the segments", "m"),
    Col("service_loops_m", "Service loops", "m"),
    Col("stored_length_m", "Length stored on the wire", "m"),
    Col("missing", "Missing"),
)


def _step(d: Derivation, prefix: str) -> float | None:
    return next((s.value for s in d.steps if s.label.startswith(prefix)), None)


def lengths(project: Project) -> DataTable:
    rows: list[dict[str, Any]] = []
    for h, w in _all_wires(project):
        d = wire_length_derivation(project, h, w)
        basis = d.steps[-1].expression if d.value is not None and d.steps else ""
        rows.append({
            "harness": h.id, "wire": w.id, "length_m": num(d.value), "basis": basis,
            "path_m": num(_step(d, "Path through the segments")),
            "service_loops_m": num(_step(d, "Service loop")),
            "stored_length_m": num(w.length_m), "missing": "; ".join(d.missing),
        })  # fmt: skip
    return DataTable(
        "lengths", "Wire lengths and their basis",
        "One row for each wire: the length and where it comes from.", LENGTHS, rows,
    )  # fmt: skip


MASS = (
    Col("harness", "Harness"),
    Col("wires", "Wires"),
    Col("connectors", "Connectors"),
    Col("wire_length_known_m", "Wire length known", "m"),
    Col("wires_without_length", "Wires without length"),
    Col("mass_g", "Mass of what is known", "g", "the model of the project (model.mass_model)"),
    Col("margin_g", "Margin", "g"),
    Col("mass_with_margin_g", "Mass with margin", "g"),
    Col("complete", "Complete"),
    Col("missing", "Missing data"),
)


def mass(project: Project) -> DataTable:
    rows: list[dict[str, Any]] = []
    for hid in sorted(project.harnesses):
        h = project.harnesses[hid]
        r = harness_mass(project, h)
        lens = [wire_length(h, w) for w in h.wires]
        unknown = sum(1 for x in lens if x is None)
        rows.append({
            "harness": h.id, "wires": len(h.wires), "connectors": len(h.connectors),
            "wire_length_known_m": num(sum(x for x in lens if x is not None)),
            "wires_without_length": unknown, "mass_g": num(r.total_g), "margin_g": num(r.margin_g),
            "mass_with_margin_g": num(r.with_margin_g),
            "complete": "yes" if r.complete and unknown == 0 else "no",
            "missing": "; ".join(r.missing),
        })  # fmt: skip
    return DataTable("mass", "Mass of each harness", "One row for each harness.", MASS, rows)


MASS_WIRES = (
    Col("harness", "Harness"),
    Col("wire", "Wire"),
    Col("part", "Part"),
    Col("mass_per_m_g", "Mass per metre", "g/m"),
    Col("conductors", "Conductors of the part"),
    Col("length_m", "Length", "m"),
    Col("mass_g", "Mass", "g", "mass per metre × length / conductors of the part"),
)


def mass_wires(project: Project) -> DataTable:
    rows: list[dict[str, Any]] = []
    for h, w in _all_wires(project):
        part = project.parts.get(w.part_id) if w.part_id else None
        length = wire_length(h, w)
        per_m = part.mass_per_m_g if part is not None else None
        grams = (
            wire_mass_g(per_m, length, part.conductors)
            if part is not None and per_m is not None and length is not None
            else None
        )
        rows.append({
            "harness": h.id, "wire": w.id, "part": w.part_id or "", "mass_per_m_g": num(per_m),
            "conductors": part.conductors if part is not None else None,
            "length_m": num(length), "mass_g": num(grams),
        })  # fmt: skip
    return DataTable("mass_wires", "Mass of each wire", "One row for each wire.", MASS_WIRES, rows)


# ---- bill of materials -----------------------------------------------------------------------


BOM = (
    Col("part", "Part"),
    Col("category", "Category"),
    Col("manufacturer", "Manufacturer"),
    Col("part_number", "Part number"),
    Col("description", "Description"),
    Col("approval", "Approval"),
    Col("quantity", "Quantity", "", "a count for ea, metres for m (see unit)"),
    Col("unit", "Unit", "", "ea or m"),
    Col("wires_without_length", "Wires without length"),
    Col("used_in", "Used in"),
)


def bom(project: Project) -> DataTable:
    harnesses = [project.harnesses[i] for i in sorted(project.harnesses)]
    text = out_tables.bom(project, harnesses)
    rows: list[dict[str, Any]] = []
    for r in text[1:]:
        metres = r[7] == "m"
        rows.append({
            "part": r[0], "category": r[1], "manufacturer": r[2], "part_number": r[3],
            "description": r[4], "approval": r[5],
            "quantity": num(float(r[6])) if metres else int(r[6]), "unit": r[7],
            "wires_without_length": int(r[8]) if r[8] else None, "used_in": r[9],
        })  # fmt: skip
    return DataTable(
        "bom", "Bill of materials",
        "One row for each part and unit (the figures of the BOM file, as numbers).", BOM, rows,
    )  # fmt: skip


BOM_CONTRIBUTIONS = (
    Col("part", "Part"),
    Col("unit", "Unit", "", "ea or m"),
    Col("amount", "Amount", "", "a count for ea; metres for m (a wire: length over conductors)"),
    Col("harness", "Harness"),
    Col("kind", "Kind", "", "connector, contact, wire or accessory"),
    Col("source", "Source", "", "the connector, pin, wire or accessory"),
    Col("length_known", "Length known", "", "no: a wire without a length adds nothing"),
)  # fmt: skip


def bom_contributions(project: Project) -> DataTable:
    harnesses = [project.harnesses[i] for i in sorted(project.harnesses)]
    rows = [
        {
            "part": c.part_id, "unit": c.unit,
            "amount": num(c.amount) if c.unit == "m" else int(c.amount),
            "harness": c.harness_id, "kind": c.kind, "source": c.source,
            "length_known": "no" if c.unknown else "yes",
        }
        for c in out_tables.bom_contributions(project, harnesses)
    ]  # fmt: skip
    rows.sort(key=lambda r: (r["part"], r["unit"], r["harness"], r["kind"], r["source"]))
    return DataTable(
        "bom_contributions", "Everything that adds to the bill of materials",
        "One row for each thing the BOM counts; the BOM is the sum of these by part and unit.",
        BOM_CONTRIBUTIONS, rows,
    )  # fmt: skip


SEGMENT_LENGTHS = (
    Col("harness", "Harness"),
    Col("segment", "Segment"),
    Col("length_m", "Length", "m"),
    Col("from_node", "From node"),
    Col("to_node", "To node"),
)


def segment_lengths(project: Project) -> DataTable:
    """The lengths of the routing segments that have one, in the order `import-lengths` reads
    (harness, segment, length): this file can be imported again with `--unit m`."""
    rows: list[dict[str, Any]] = []
    for hid in sorted(project.harnesses):
        h = project.harnesses[hid]
        for sg in sorted(h.segments, key=lambda x: x.id):
            if sg.length_m is not None:
                rows.append({
                    "harness": h.id, "segment": sg.id, "length_m": num(sg.length_m),
                    "from_node": sg.from_node, "to_node": sg.to_node,
                })  # fmt: skip
    return DataTable(
        "segment_lengths", "Lengths of the routing segments",
        "One row for each segment that has a length: the input the wire lengths come from. "
        "`import-lengths DIR segment_lengths.csv --unit m` reads it back.",
        SEGMENT_LENGTHS, rows,
    )  # fmt: skip


PARTS = (
    Col("part", "Part"),
    Col("category", "Category"),
    Col("manufacturer", "Manufacturer"),
    Col("part_number", "Part number"),
    Col("description", "Description"),
    Col("specification", "Specification"),
    Col("approval", "Approval"),
    Col("pin_count", "Pin count"),
    Col("mass_g", "Mass", "g"),
    Col("mass_per_m_g", "Mass per metre", "g/m"),
    Col("mates_with", "Mates with"),
    Col("tool", "Tool"),
    Col("conductors", "Conductors"),
    Col("example_data", "Example data", "", "yes: example data nobody has checked"),
    Col("ratings", "Ratings", "", "name: value, as JSON in the CSV; import-parts does not read it"),
)


def parts_table(project: Project) -> DataTable:
    """The parts library as the calculations read it. `import-parts DIR parts.csv --approved
    approved --pending pending --rejected not_approved` reads it back."""
    rows = [
        {
            "part": p.id, "category": p.category, "manufacturer": p.manufacturer or "",
            "part_number": p.part_number or "", "description": p.description or "",
            "specification": p.specification or "", "approval": p.approval,
            "pin_count": p.pin_count, "mass_g": num(p.mass_g), "mass_per_m_g": num(p.mass_per_m_g),
            "mates_with": p.mates_with or "", "tool": p.tool or "", "conductors": p.conductors,
            "example_data": _yes(p.unverified),
            "ratings": {k: num(v) for k, v in sorted(p.ratings.items())},
        }
        for p in sorted(project.parts.values(), key=lambda x: x.id)
    ]  # fmt: skip
    return DataTable(
        "parts", "Parts library",
        "One row for each part of the library: masses, conductors, approval and ratings.",
        PARTS, rows,
    )  # fmt: skip


# ---- segmentation, pins -------------------------------------------------------------------------


SEG_GROUPS = (
    Col("group_key", "Group key"),
    Col("harness", "Harness", "", "the harness made for the group, if one was"),
    Col("label", "Name"),
    Col("mode", "Mode", "", "model: segmentation.mode"),
    Col("chain", "Chain", "", "nominal, redundant, or empty when they may share"),
    Col("zone_a", "Zone A"),
    Col("zone_b", "Zone B"),
    Col("interface_count", "Interfaces"),
    Col("interfaces", "Interface IDs"),
)


SEG_INTERFACES = (
    Col("interface", "Interface"),
    Col("group_key", "Group key"),
    Col("harness", "Harness"),
    Col("class", "Class", "", "main, pyro or the class of a category kept apart"),
    Col("redundancy", "Redundancy"),
    Col("category", "Category"),
    Col("from_device", "From device"),
    Col("from_zone", "From zone"),
    Col("from_connector", "From connector"),
    Col("to_device", "To device"),
    Col("to_zone", "To zone"),
    Col("to_connector", "To connector"),
    Col("skipped", "Not grouped because"),
)


def _zone(project: Project, end: Any) -> str:
    unit = project.units.get(end.unit_id) if end is not None else None
    return (unit.zone or "") if unit is not None else ""


def segmentation_tables(project: Project) -> list[DataTable]:
    seg = segment(project)
    seg_cfg, sep_cfg = _seg_cfg(project, "segmentation"), _seg_cfg(project, "segregation")
    harness_of_group = {h.group_key: h.id for h in project.harnesses.values() if h.group_key}
    group_of: dict[str, str] = {}
    group_rows: list[dict[str, Any]] = []
    for g in sorted(seg.groups, key=lambda x: x.key):
        for iid in g.interface_ids:
            group_of[iid] = g.key
        group_rows.append({
            "group_key": g.key, "harness": harness_of_group.get(g.key, ""), "label": g.label,
            "mode": g.mode, "chain": g.chain, "zone_a": g.zones[0] if g.zones else "",
            "zone_b": g.zones[1] if g.zones else "", "interface_count": len(g.interface_ids),
            "interfaces": ";".join(sorted(g.interface_ids)),
        })  # fmt: skip
    skipped = {s.interface_id: s.reason for s in seg.skipped}
    rows: list[dict[str, Any]] = []
    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        itype = project.interface_types.get(i.type_id)
        a, b = (i.endpoints[0], i.endpoints[1]) if len(i.endpoints) == 2 else (None, None)
        key = group_of.get(i.id, "")
        rows.append({
            "interface": i.id, "group_key": key, "harness": harness_of_group.get(key, ""),
            "class": _class_of(project, i, seg_cfg, sep_cfg) if itype and a and b else "",
            "redundancy": i.redundancy, "category": itype.category if itype else "",
            "from_device": a.unit_id if a else "",
            "from_zone": _zone(project, a),
            "from_connector": (a.connector_id or "") if a else "",
            "to_device": b.unit_id if b else "",
            "to_zone": _zone(project, b),
            "to_connector": (b.connector_id or "") if b else "",
            "skipped": skipped.get(i.id, ""),
        })  # fmt: skip
    return [
        DataTable(
            "segmentation_groups", "Segmentation: groups of interfaces",
            "One row for each group of interfaces that share a harness.", SEG_GROUPS, group_rows,
        ),
        DataTable(
            "segmentation_interfaces", "Segmentation: each interface",
            "One row for each interface: the group it falls in and what decided it.",
            SEG_INTERFACES, rows,
        ),
    ]  # fmt: skip


PIN_ALLOCATION = (
    Col("scope", "Scope", "", "device: a connector of a device; harness: a cable connector"),
    Col("harness", "Harness"),
    Col("connector", "Connector"),
    Col("role", "Role"),
    Col("mates_with", "Mates with"),
    Col("part", "Part"),
    Col("pin", "Pin"),
    Col("signal", "Signal"),
    Col("interface", "Interface"),
    Col("wires", "Wires"),
    Col("spare", "Spare", "", "yes: no wire, signal or interface on the pin"),
)


def pin_allocation(project: Project) -> DataTable:
    rows: list[dict[str, Any]] = []

    def add(scope: str, harness: str, text: list[list[str]]) -> None:
        for r in text[1:]:
            rows.append({
                "scope": scope, "harness": harness, "connector": r[0], "role": r[1],
                "mates_with": r[2], "part": r[3], "pin": r[4], "signal": r[5],
                "interface": r[6], "wires": r[7], "spare": "yes" if r[8] == "yes" else "",
            })  # fmt: skip

    add("device", "", out_tables.box_pinouts(project))
    for hid in sorted(project.harnesses):
        add("harness", hid, out_tables.pinouts(project, project.harnesses[hid]))
    return DataTable(
        "pin_allocation", "Pin allocation",
        "One row for each pin of every device connector and every cable connector.",
        PIN_ALLOCATION, rows,
    )  # fmt: skip


# ---- the design rules ---------------------------------------------------------------------------


RULE_RESULTS = (
    Col("rule", "Rule"),
    Col("object", "Object"),
    Col("quantity", "Quantity"),
    Col("actual", "Actual", "", "in the unit of the next columns"),
    Col("limit", "Limit"),
    Col("margin", "Margin", "", "limit minus actual for an upper limit; positive: room left"),
    Col("unit", "Unit"),
    Col("verdict", "Verdict", "", "pass, fail or not checked"),
    Col("missing", "Missing", "", "what is not set, so that the rule could not compare"),
)


def _rule_row(rule: str, obj: str, d: Derivation) -> dict[str, Any]:
    c = d.check
    return {
        "rule": rule, "object": obj, "quantity": d.quantity,
        "actual": num(c.actual) if c else None, "limit": num(c.limit) if c else num(d.value),
        "margin": num(c.margin) if c else None, "unit": c.unit if c else d.unit,
        "verdict": _verdict(c.passes if c else None), "missing": "; ".join(d.missing),
    }  # fmt: skip


def rule_rows(project: Project, findings: list[Finding]) -> list[dict[str, Any]]:
    """The limits the rules compare, for every wire and interface the first three rules apply to
    (whether or not they found anything), and for every object a finding of a rule with a limit is
    about."""
    rows: list[dict[str, Any]] = []
    for h, w in _all_wires(project):
        rows.append(
            _rule_row("current-over-wire", w.id, wire_current_limit_derivation(project, h, w))
        )
        rows.append(_rule_row("voltage-drop", w.id, wire_voltage_drop_derivation(project, h, w)))
    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        for e in i.endpoints:
            if e.connector_id and e.connector_id in project.connectors:
                d = contact_current_derivation(project, i.id, e.connector_id)
                rows.append(_rule_row("current-over-contact", f"{i.id}.{e.connector_id}", d))
    seen: set[tuple[str, str]] = set()
    for f in findings:
        info = INFO.get(f.rule)
        key = (f.rule, f.object_id)
        if info is None or info.form != LIMIT or info.build is None or key in seen:
            continue
        seen.add(key)
        for d in explain_rule(project, f.rule, f.object_id, findings):
            rows.append(_rule_row(f.rule, f.object_id, d))
    return rows


def _findings(project: Project) -> list[Finding]:
    return sorted(
        [*checks.find(project), *run_drc(project)],
        key=lambda f: ({"error": 0, "warning": 1, "info": 2}[f.severity], f.id),
    )


FINDINGS = (
    Col("finding", "Finding"),
    Col("rule", "Rule"),
    Col("severity", "Severity"),
    Col("object", "Object"),
    Col("statement", "Statement"),
    Col("waived", "Waived"),
    Col("justification", "Justification"),
    Col("requirement", "Requirement"),
    Col("actual", "Actual", "", "of the rule's limit, when the rule has one (see rule_results)"),
    Col("limit", "Limit"),
    Col("margin", "Margin"),
    Col("unit", "Unit"),
)


def _joined(rule_by_key: dict[tuple[str, str], dict[str, Any]], f: Finding) -> dict[str, Any]:
    r = rule_by_key.get((f.rule, f.object_id))
    if r is None or r["actual"] is None:
        return {"actual": None, "limit": None, "margin": None, "unit": ""}
    return {k: r[k] for k in ("actual", "limit", "margin", "unit")}


def rules_and_findings(project: Project) -> list[DataTable]:
    found = _findings(project)
    results = rule_rows(project, found)
    by_key = {(r["rule"], r["object"]): r for r in results}
    rows = [
        {
            "finding": f.id, "rule": f.rule, "severity": f.severity, "object": f.object_id,
            "statement": f.title, "waived": "yes" if f.waiver else "",
            "justification": f.waiver.justification if f.waiver else "",
            "requirement": " ".join(f.sources), **_joined(by_key, f),
        }
        for f in found
    ]  # fmt: skip
    return [
        DataTable(
            "rule_results", "Rule results: actual, limit, margin and verdict",
            "One row for each limit a design rule compares a number with.", RULE_RESULTS, results,
        ),
        DataTable(
            "findings", "Findings of the design rule check",
            "Every finding, waived ones included, with the numbers of its rule when it has them.",
            FINDINGS, rows,
        ),
    ]  # fmt: skip


# ---- readiness, tests ---------------------------------------------------------------------------


READINESS = (
    Col("harness", "Harness"),
    Col("check", "Check"),
    Col("open", "Open", "", "how many items are open"),
    Col("blocking", "Blocks", "", "yes: an open item makes Ready to build no"),
    Col("status", "Status"),
    Col("items", "Open items"),
    Col("ready", "Ready to build", "", "of the harness: yes when no check that blocks is open"),
    Col("todo", "What to do"),
)


def readiness_table(project: Project) -> DataTable:
    rows: list[dict[str, Any]] = []
    for hid in sorted(project.harnesses):
        h = project.harnesses[hid]
        cs = readiness(project, h)
        ready = "no" if any(c.status == TO_FIX for c in cs) else "yes"
        for c in cs:
            rows.append({
                "harness": h.id, "check": c.label, "open": c.open,
                "blocking": "yes" if c.blocking else "no", "status": c.status,
                "items": ";".join(c.items), "ready": ready, "todo": c.todo,
            })  # fmt: skip
    return DataTable(
        "readiness", "Readiness checks of the build workbook",
        "One row for each check of each harness: what is open and whether it blocks.",
        READINESS, rows,
    )  # fmt: skip


TEST_LIMITS = (
    Col("harness", "Harness"),
    Col("test", "Test"),
    Col("type", "Type"),
    Col("from", "From"),
    Col("to", "To"),
    Col("expected", "Expected"),
    Col("limit", "Limit", "", "empty while the limit is not set (the sheet shows TBD)"),
    Col("limit_unit", "Limit unit"),
    Col("test_voltage_v", "Test voltage", "V"),
    Col("wires", "Wires"),
)


def test_limits_table(project: Project) -> DataTable:
    continuity = out_tables.limit_value(project, "test_continuity_max_ohm")
    isolation = out_tables.limit_value(project, "test_isolation_min_mohm")
    volts = out_tables.limit_value(project, "test_isolation_voltage_v")
    rows: list[dict[str, Any]] = []
    for hid in sorted(project.harnesses):
        h = project.harnesses[hid]
        for r in out_tables.tests(project, h)[1:]:
            is_cont = r[1] == "continuity"
            rows.append({
                "harness": h.id, "test": r[0], "type": r[1], "from": r[2], "to": r[3],
                "expected": r[4], "limit": num(continuity if is_cont else isolation),
                "limit_unit": "ohm max" if is_cont else "Mohm min",
                "test_voltage_v": None if is_cont else num(volts), "wires": r[7],
            })  # fmt: skip
    return DataTable(
        "test_limits", "Tests and their limits",
        "One row for each test of the test sheet of each harness.", TEST_LIMITS, rows,
    )  # fmt: skip


# ---- settings, configuration --------------------------------------------------------------------


SETTINGS = (
    Col("id", "Setting", "", "file.key"),
    Col("file", "File"),
    Col("key", "Key"),
    Col("label", "Name"),
    Col("value", "Value", "", "as the tool uses it; a table or a list as JSON in the CSV"),
    Col("unit", "Unit"),
    Col("origin", "Origin", "", "project (set in the files), default (the tool's own) or unset"),
    Col("placeholder", "Placeholder", "", "yes: the file that holds it is not reviewed"),
    Col("default", "Default"),
    Col("used_by", "Used by"),
    Col("source", "Source"),
)


def settings_table(project: Project) -> DataTable:
    rows = [
        {
            "id": r.setting.id, "file": r.setting.file, "key": r.setting.key,
            "label": r.setting.label, "value": r.value, "unit": r.setting.unit,
            "origin": r.origin, "placeholder": _yes(r.placeholder), "default": r.setting.default,
            "used_by": r.setting.used_by, "source": r.setting.source,
        }
        for r in settings.rows(project)
    ]  # fmt: skip
    overridden = sum(1 for _h, w in _all_wires(project) if w.overrides)
    if overridden:  # values set by hand in place of the design's (S4); the reasons are in the wires
        rows.append(
            {
                "id": "overrides.wires", "file": "", "key": "overrides",
                "label": "Wires with a value set by hand", "value": overridden, "unit": "",
                "origin": "project", "placeholder": _yes(False), "default": 0,
                "used_by": "wire gauge, type, colour and length", "source": "harness files",
            }
        )  # fmt: skip
    return DataTable(
        "settings", "Settings in force",
        "Every setting the results depend on, with the value in force and where it comes from.",
        SETTINGS, rows,
    )  # fmt: skip


def configuration_bytes(project: Project) -> bytes:
    """`configuration.json`: the configuration files as the tool used them."""
    doc = {
        "format": FORMAT,
        "about": "The files config/*.json of the project as the tool read them, with the "
        "placeholder flag of each (placeholder: the values are not reviewed).",
        "files": [
            {"name": name, "placeholder": c.placeholder, "values": c.values}
            for name, c in sorted(project.config.items())
        ],
    }
    return _json(doc)


# ---- writing ------------------------------------------------------------------------------------


def _json(doc: dict[str, Any]) -> bytes:
    return (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def _csv_cell(v: Cell) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, str):
        return _safe(v)
    if isinstance(v, int | float):
        return repr(v)
    return json.dumps(v, ensure_ascii=False)


def table_json(table: DataTable, project: Project, mhash: str) -> bytes:
    """One JSON document: the format number, what the table is, the columns with their units, and
    the rows, one to a line (a long table stays a file a person can open)."""

    def line(item: object) -> str:
        return "  " + json.dumps(item, ensure_ascii=False)

    head = {
        "format": FORMAT,
        "table": table.name,
        "title": table.title,
        "about": table.about,
        "tool_version": __version__,
        "model_hash": mhash,
    }
    columns = [
        {"key": c.key, "name": c.name, "unit": c.unit, "header": c.header, "what": c.what}
        for c in table.cols
    ]
    rows = [{c.key: r[c.key] for c in table.cols} for r in table.rows]
    parts = [f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in head.items()]
    for key, items in (("columns", columns), ("rows", rows)):
        body = ",\n".join(line(i) for i in items)
        parts.append(f' "{key}": [\n{body}\n ]' if items else f' "{key}": []')
    return ("{\n" + ",\n".join(parts) + "\n}\n").encode("utf-8")


def table_csv(table: DataTable) -> bytes:
    out = io.StringIO(newline="")
    w = csv.writer(out, lineterminator="\n")
    w.writerow([c.header for c in table.cols])
    for r in table.rows:
        w.writerow([_csv_cell(r[c.key]) for c in table.cols])
    return out.getvalue().encode("utf-8")


def all_tables(project: Project) -> list[DataTable]:
    """Every table, in the order of the module text."""
    found = rules_and_findings(project)
    return [
        wire_sizing(project),
        *segmentation_tables(project),
        pin_allocation(project),
        found[0],
        readiness_table(project),
        lengths(project),
        segment_lengths(project),
        parts_table(project),
        mass(project),
        mass_wires(project),
        bom(project),
        bom_contributions(project),
        found[1],
        test_limits_table(project),
        settings_table(project),
    ]


def _imports(project: Project) -> list[dict[str, Any]]:
    """The files the project imported (`Project.import_records`, kept since S6), by ID: what the
    file was called, its SHA-256, what kind of import it was and how many rows it read, dropped and
    converted. No path: the name of the file only."""
    return [
        {
            "id": r.id, "kind": r.kind, "source_name": r.source_name, "sha256": r.sha256,
            "rows_read": r.rows_read, "rows_dropped": r.dropped_count,
            "values_converted": r.converted_count, "unit": r.unit, "tool_version": r.tool_version,
        }
        for _key, r in sorted(project.import_records.items())
    ]  # fmt: skip


def provenance_bytes(project: Project, files: dict[str, bytes], mhash: str) -> bytes:
    """`provenance.json`: the tool, the design, the library, the imported files and the hash of
    every other file of the set, so that a colleague can tell the files are the ones that were
    written."""
    approvals: dict[str, int] = defaultdict(int)
    for part in project.parts.values():
        approvals[part.approval] += 1
    doc = {
        "format": FORMAT,
        "tool": "harness-design-studio",
        "tool_version": __version__,
        "project": project.meta.name,
        "model_hash": mhash,
        "content_hash": content_hash(project),
        "placeholder_config": project.placeholder_configs(),
        "library": {
            "name": project.library_info.name,
            "version": project.library_info.version,
            "source": project.library_info.source,
            "date": project.library_info.date,
            "parts": len(project.parts),
            "parts_by_approval": dict(sorted(approvals.items())),
        },
        "design": {
            "units": len(project.units),
            "interfaces": len(project.interfaces),
            "harnesses": len(project.harnesses),
            "wires": sum(len(h.wires) for h in project.harnesses.values()),
            # only whether: journal.json holds a time and a name, so it is not part of this set
            "journal": "present" if project.journal is not None else "absent",
        },
        "imports": _imports(project),
        "files": [
            {"path": p, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
            for p, b in sorted(files.items())
        ],
        "notes": [
            "No file of this set holds a time, a user name or a path. The record of a run "
            "(run_record.json) is written only when asked and is not part of this set.",
            "The gauge is the plain AWG number; its cross-section is the column area_mm2.",
        ],
    }
    if project.extensions is not None:  # S8: only a project that enables extensions lists them
        from harness_design_studio.core.extensions.manager import provenance

        if listed := provenance(project):
            doc["extensions"] = listed
    return _json(doc)


def data_files(project: Project) -> dict[str, bytes]:
    """Every file of the open data of a project, by file name: the same design gives the same
    bytes. Pure: nothing is read from or written to disk."""
    out_tables.clear_cache()
    mhash = model_hash(project)
    files: dict[str, bytes] = {}
    for t in all_tables(project):
        files[f"{t.name}.json"] = table_json(t, project, mhash)
        files[f"{t.name}.csv"] = table_csv(t)
    files[CONFIGURATION] = configuration_bytes(project)
    files["README.txt"] = _readme().encode("utf-8")  # JSON and CSV here have no comment line
    files[PROVENANCE] = provenance_bytes(project, files, mhash)
    return files


def _readme() -> str:
    """The notice for the open data: its files cannot hold a comment (D-210)."""
    from harness_design_studio import __version__
    from harness_design_studio.core import legal_texts

    return (
        "Harness Design Studio: the open data of a design\n"
        "================================================\n\n"
        f"{legal_texts.output_notice('harness-design-studio', __version__)}\n\n"
        f"{legal_texts.DISCLAIMER}\n\n{legal_texts.INTENDED_USE}\n\n"
        "These JSON and CSV files hold the numbers behind the outputs. They have no comment "
        "line, so this file is where the notice is. Pending and placeholder values stay marked "
        "in them (pending, PLACEHOLDER, not checked).\n"
    )


def write_data(project: Project, folder: Path | str) -> dict[str, bytes]:
    """Write the open data into `folder` (made when missing) and return the files by name. Files
    of an earlier export are replaced; nothing else in the folder is touched. Nothing is written
    behind a link."""
    return write_files(data_files(project), folder)


def write_files(files: dict[str, bytes], folder: Path | str) -> dict[str, bytes]:
    """Write files made by `data_files` into `folder` (see `write_data`); the editor makes them off
    its main thread and writes them here."""
    root = Path(folder)
    if root.is_symlink():
        raise SaveError("The data folder is a link, so nothing was written.")
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SaveError(f"The data folder cannot be created ({exc.strerror}).") from exc
    if any((root / name).is_symlink() for name in files):
        raise SaveError("A file of the data set is a link, so nothing was written.")
    try:
        for name, data in sorted(files.items()):
            atomic_write_bytes(root / name, data, backup=False, root=root, durable=False)
    except OSError as exc:
        raise SaveError(f"The data could not be written ({exc.strerror}).") from exc
    return files
