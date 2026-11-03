"""Every derivation of a project as data: one JSON file and one CSV file (D-191, step 5a).

`explain` shows how one number was made. This writes how every number was made, for a person who
wants to check a colleague's result from a file, or to put the equations and limits into a
spreadsheet or a script. The files carry what the derivations carry: the quantity, the value and
unit, the equation, the inputs with their units and sources, the steps, the check (actual, limit,
margin, verdict), the assumptions and what is missing. They carry no time, user name or path, so the
same design written twice gives the same bytes.

Format 3 (S5, D2): an input that is a wire gauge (unit AWG) has the key `area_mm2`: its
cross-section.

Format 2 (S1, D-191): a derivation whose result is a text (a label, a colour, a pin, a group, the
answer to Ready to build) has the key `text` in the JSON and a last column *Text* in the CSV; the
kinds of derivation are listed in `core.derive_kinds`, and the limits of the design rules
(`rule-limit`, `rule-check`) follow the others for each finding of the project.
"""

import csv
import io
import json
from typing import Any

from harness_design_studio import __version__
from harness_design_studio.core import checks
from harness_design_studio.core.derive import (
    EXPLAINABLE_RULES,
    Derivation,
    contact_current_derivation,
    explain_harness_all,
    explain_part,
    explain_wire_all,
)
from harness_design_studio.core.derive_rules import explain_rule
from harness_design_studio.core.drc import run as run_drc
from harness_design_studio.core.model import Project
from harness_design_studio.core.outputs.tables import bom_contributions, data_num

FORMAT = 3
CSV_HEADER = [
    "Kind", "Subject", "Quantity", "Value", "Unit", "Equation", "Actual", "Limit", "Margin",
    "Verdict", "Assumptions", "Missing", "Text",
]  # fmt: skip


# the rules whose derivation of their own is written with the wire or the interface they are about
_FIRST_RULES = frozenset({"current-over-wire", "voltage-drop", "current-over-contact"})


def explain_all(project: Project) -> list[Derivation]:
    """Every derivation of the project, in a fixed order: for each harness (by ID) everything that
    explains the harness (its mass, whether it is ready to build and the checks behind that, its
    test limits, why it is a harness of its own, its shield groups, its connectors), then its wires
    in order (length, current limit, voltage drop, mass, label, colour, shield group, pins); then
    the parts of the bill of materials (by ID and unit); then the contacts of each interface at
    each of its connectors; then, for each finding, the limit or the comparison of its rule."""
    found: list[Derivation] = []
    for hid in sorted(project.harnesses):
        found += explain_harness_all(project, hid)
        for w in project.harnesses[hid].wires:
            found += explain_wire_all(project, w.id)
    harnesses = [project.harnesses[i] for i in sorted(project.harnesses)]
    for pid in sorted({c.part_id for c in bom_contributions(project, harnesses)}):
        found += explain_part(project, pid)
    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        for e in i.endpoints:
            if e.connector_id and e.connector_id in project.connectors:
                found.append(contact_current_derivation(project, i.id, e.connector_id))
    findings = [*checks.find(project), *run_drc(project)]
    seen: set[tuple[str, str]] = set()
    for f in findings:
        key = (f.rule, f.object_id)
        if f.rule in _FIRST_RULES or key in seen or f.rule not in EXPLAINABLE_RULES:
            continue
        seen.add(key)
        found += explain_rule(project, f.rule, f.object_id, findings)
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
                ";".join(d.assumptions), "; ".join(d.missing), d.text,
            ]
        )  # fmt: skip
    return out.getvalue().encode("utf-8")
