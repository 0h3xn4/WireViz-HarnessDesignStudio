"""Every derivation of a project as data: one JSON file and one CSV file (D-191, step 5a).

`explain` shows how one number was made. This writes how every number was made, for a person who
wants to check a colleague's result from a file, or to put the equations and limits into a
spreadsheet or a script. The files carry what the derivations carry: the quantity, the value and
unit, the equation, the inputs with their units and sources, the steps, the check (actual, limit,
margin, verdict), the assumptions and what is missing. They carry no time, user name or path, so the
same design written twice gives the same bytes.
"""

import csv
import io
import json
from typing import Any

from harness_design_studio import __version__
from harness_design_studio.core.derive import (
    Derivation,
    contact_current_derivation,
    explain_harness,
    explain_part,
    explain_wire,
)
from harness_design_studio.core.model import Project
from harness_design_studio.core.outputs.tables import bom_contributions, data_num

FORMAT = 1
CSV_HEADER = [
    "Kind", "Subject", "Quantity", "Value", "Unit", "Equation", "Actual", "Limit", "Margin",
    "Verdict", "Assumptions", "Missing",
]  # fmt: skip


def explain_all(project: Project) -> list[Derivation]:
    """Every derivation of the project, in a fixed order: for each harness (by ID) its mass, then
    its wires in order (length, current limit, voltage drop, mass); then the parts of the bill of
    materials (by ID and unit); then the contacts of each interface at each of its connectors."""
    found: list[Derivation] = []
    for hid in sorted(project.harnesses):
        found += explain_harness(project, hid)
        for w in project.harnesses[hid].wires:
            found += explain_wire(project, w.id)
    harnesses = [project.harnesses[i] for i in sorted(project.harnesses)]
    for pid in sorted({c.part_id for c in bom_contributions(project, harnesses)}):
        found += explain_part(project, pid)
    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        for e in i.endpoints:
            if e.connector_id and e.connector_id in project.connectors:
                found.append(contact_current_derivation(project, i.id, e.connector_id))
    return found


def to_json_bytes(project: Project, derivations: list[Derivation]) -> bytes:
    """The derivations as JSON: the format number, the tool version (the results depend on it) and
    the derivations as `Derivation.to_dict` gives them."""
    doc: dict[str, Any] = {
        "format": FORMAT,
        "tool_version": __version__,
        "project": project.meta.name,
        "derivations": [d.to_dict() for d in derivations],
    }
    return (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def to_csv_bytes(derivations: list[Derivation]) -> bytes:
    """One row for each derivation, with the check in columns: what a spreadsheet filters on."""
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for d in derivations:
        c = d.check
        writer.writerow(
            [
                d.id, d.subject, d.quantity, data_num(d.value), d.unit, d.equation,
                data_num(c.actual) if c else "", data_num(c.limit) if c else "",
                data_num(c.margin) if c else "",
                ("pass" if c.passes else "fail") if c else "",
                ";".join(d.assumptions), "; ".join(d.missing),
            ]
        )  # fmt: skip
    return out.getvalue().encode("utf-8")
