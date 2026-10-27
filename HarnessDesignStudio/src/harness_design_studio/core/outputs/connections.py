"""The connection list of a project (ICD style): which pin of which connector of which device is
joined to which pin of which other device, from the links a person made (M2 of the workshop
feedback; release 1.9, W2).

Two files, written only for a project that has links, so every other project keeps byte-identical
outputs: `system/connections.csv` (one row per pair of pins) and `system/connections.xlsx` (the
same rows as a sheet to hand over, a sheet with one line per connection, and the stamp). A link is
the source of truth; the harness made from it, if any, is only named. Nothing is invented: a pin
without a signal has an empty signal and role, an interface type is named only when the signals of
the pair belong to one (`core/links.py` `derived_interfaces`). The columns are documented in
`docs/OUTPUTS.md`.
"""

import io
from typing import Any

from harness_design_studio.core.links import derived_interfaces, effective_role, natural_key
from harness_design_studio.core.model import Connector, Pin, Project

from .buildsheet import _cell, _finish, _header, _Layout
from .exports import _FIXED, normalise_xlsx
from .stamp import Stamp, Table
from .tables import device_of
from .xlsx_env import Workbook

CONNECTIONS_CSV = "system/connections.csv"
CONNECTIONS_XLSX = "system/connections.xlsx"
SHEETS = ("Connections", "Summary", "About")

HEADER = [
    "Connection", "Name", "From device", "From connector", "From pin", "From signal", "From role",
    "To device", "To connector", "To pin", "To signal", "To role", "Interface", "Harness", "Note",
]  # fmt: skip
SUMMARY_HEADER = [
    "Connection", "Name", "From device", "From connector", "To device", "To connector", "Pairs",
    "Carries", "Harness", "Note",
]  # fmt: skip

_TAB = "2F6B8A"


def interface_names(project: Project) -> dict[tuple[str, str, str], str]:
    """(link, pin of the first connector, pin of the second) -> the interface type the pair
    belongs to, by name ("CAN", or "RS-422 or Ethernet" when several fit equally). A pair no
    type explains is not in the result."""
    out: dict[tuple[str, str, str], str] = {}
    for di in derived_interfaces(project):
        if not di.type_id:
            continue
        names = " or ".join(
            project.interface_types[t].name for t in (di.alternatives or (di.type_id,))
        )
        for pair in di.pairs:
            out[(di.link_id, pair.a_pin, pair.b_pin)] = names
    return out


def carried_labels(project: Project) -> dict[str, str]:
    """Link -> what it carries as the screen words it ("CAN, 2 wires; Power, 2 wires")."""
    out: dict[str, list[str]] = {}
    for di in derived_interfaces(project):
        out.setdefault(di.link_id, []).append(di.label)
    return {link: "; ".join(labels) for link, labels in out.items()}


def _pin(connector: Connector | None, pin_id: str) -> Pin | None:
    return next((p for p in connector.pins if p.id == pin_id), None) if connector else None


def connection_rows(project: Project) -> Table:
    """The rows of `system/connections.csv`: the header, then one row for each pair of pins of
    each link (links by ID, pairs by the natural order of the first pin). A link with no pair has
    one row with the pin cells empty, so no link is ever left out."""
    names = interface_names(project)
    rows: Table = [list(HEADER)]
    for link in sorted(project.links.values(), key=lambda x: x.id):
        a = project.connectors.get(link.a_connector)
        b = project.connectors.get(link.b_connector)
        ends = [link.id, link.name, device_of(project, link.a_connector), link.a_connector]
        to = [device_of(project, link.b_connector), link.b_connector]
        tail = [link.harness_id or "", link.note]
        pairs = sorted(link.pairs, key=lambda p: (natural_key(p.a_pin), natural_key(p.b_pin)))
        if not pairs:
            rows.append([*ends, "", "", "", *to, "", "", "", "", *tail])
        for pair in pairs:
            pa, pb = _pin(a, pair.a_pin), _pin(b, pair.b_pin)
            rows.append([
                *ends, pair.a_pin, (pa.signal or "") if pa else "",
                effective_role(pa, project, a) if pa else "",
                *to, pair.b_pin, (pb.signal or "") if pb else "",
                effective_role(pb, project, b) if pb else "",
                names.get((link.id, pair.a_pin, pair.b_pin), ""), *tail,
            ])  # fmt: skip
    return rows


def summary_rows(project: Project) -> Table:
    """One row for each link: its ends, how many pairs it has, what it carries, its harness."""
    labels = carried_labels(project)
    rows: Table = [list(SUMMARY_HEADER)]
    for link in sorted(project.links.values(), key=lambda x: x.id):
        rows.append([
            link.id, link.name, device_of(project, link.a_connector), link.a_connector,
            device_of(project, link.b_connector), link.b_connector, str(len(link.pairs)),
            labels.get(link.id, ""), link.harness_id or "", link.note,
        ])  # fmt: skip
    return rows


def _sheet(wb: Any, name: str, table: Table, stamp: Stamp, *, centre: tuple[int, ...] = ()) -> None:
    ws = wb.create_sheet(name)
    lay = _Layout({})
    body: list[list[Any]] = [_header(ws, lay, table[0])]
    for row in table[1:]:
        for n, text in enumerate(row, start=1):
            lay.see(n, text)
        body.append([
            _cell(ws, text, centre=n in centre, bold=n == 1) for n, text in enumerate(row, start=1)
        ])  # fmt: skip
    _finish(ws, lay, stamp, body, tab=_TAB, freeze="A2")


def connections_workbook(project: Project, stamp: Stamp) -> bytes:
    """`system/connections.xlsx`: the sheet *Connections* (the rows of the CSV file), the sheet
    *Summary* (one line for each link) and *About* (the stamp, read the same way as in the other
    workbooks). No formulas; the same model gives the same bytes."""
    wb = Workbook(write_only=True)
    wb.properties.creator = "harness-design-studio"
    wb.properties.title = f"{stamp.line} connections"
    wb.properties.created = wb.properties.modified = _FIXED
    _sheet(wb, "Connections", connection_rows(project), stamp, centre=(5, 10))
    _sheet(wb, "Summary", summary_rows(project), stamp, centre=(7,))
    about = wb.create_sheet("About")
    about.append(["Generated by", stamp.line])
    about.append(["Model hash", stamp.model_hash])
    raw = io.BytesIO()
    wb.save(raw)
    return normalise_xlsx(raw.getvalue())


__all__ = [
    "CONNECTIONS_CSV", "CONNECTIONS_XLSX", "HEADER", "SHEETS", "SUMMARY_HEADER", "carried_labels",
    "connection_rows", "connections_workbook", "interface_names", "summary_rows",
]  # fmt: skip
