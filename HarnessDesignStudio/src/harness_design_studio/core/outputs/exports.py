"""Exports: WireViz-style YAML per harness, a documented JSON file for the whole project, and
XLSX workbooks. All deterministic (no dates, sorted keys and rows)."""

import io
import json
import re
import zipfile
from datetime import datetime
from typing import Any

from harness_design_studio.core.generate.lengths import wire_length
from harness_design_studio.core.model import Harness, Project

from .errors import OutputsError
from .stamp import Stamp, Table
from .tables import data_num
from .xlsx_env import ILLEGAL_CHARACTERS_RE, Workbook, WriteOnlyCell

JSON_FORMAT = "harness-design-studio-export"
JSON_VERSION = 1


def _q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # JSON strings are valid YAML double-quoted scalars


def wireviz_yaml(project: Project, h: Harness, stamp: Stamp) -> bytes:
    """Best-effort WireViz input: each wire is its own one-conductor cable. Not validated here
    against the WireViz program (see docs/OUTPUTS.md)."""
    out = [f"# {stamp.line}", "metadata:", f"  title: {_q(h.id + ' ' + h.name)}", "connectors:"]
    for c in sorted(h.connectors, key=lambda x: x.id):
        out.append(f"  {_q(c.id)}:")
        out.append(f"    pincount: {len(c.pins)}")
        out.append(f"    pinlabels: [{', '.join(_q(p.id) for p in c.pins)}]")
        if c.part_id:
            out.append(f"    type: {_q(c.part_id)}")
    out.append("cables:")
    wires = sorted(h.wires, key=lambda x: x.id)
    for w in wires:
        out.append(f"  {_q(w.id)}:")
        out.append("    wirecount: 1")
        if w.gauge_awg is not None:
            out.append(f"    gauge: {_q(str(w.gauge_awg) + ' AWG')}")
        if w.colour:
            out.append(f"    colors: [{_q(w.colour)}]")
        length = wire_length(h, w)
        if length is not None:
            out.append(f"    length: {data_num(length)}")
    out.append("connections:")
    for w in wires:
        out.append(f"  - - {_q(w.from_connector)}: [{_q(w.from_pin)}]")
        out.append(f"    - {_q(w.id)}: [1]")
        out.append(f"    - {_q(w.to_connector)}: [{_q(w.to_pin)}]")
    return ("\n".join(out) + "\n").encode()


def json_export(project: Project, stamp: Stamp) -> bytes:
    """The whole model as one documented JSON file (docs/OUTPUTS.md)."""

    def dump(objs: object) -> list[object]:
        return [o.model_dump(mode="json") for o in sorted(objs, key=lambda x: x.id)]  # type: ignore[call-overload]

    def harness_dump(h: Harness) -> dict[str, Any]:
        """As saved: the lists of a harness are in ID order, whatever order it was built in."""
        data = h.model_dump(mode="json")
        for key in ("connectors", "wires", "splices", "shields", "branch_points", "segments"):
            data[key] = sorted(data[key], key=lambda x: x["id"])
        return data

    doc = {
        "format": JSON_FORMAT,
        "format_version": JSON_VERSION,
        "generator": {"name": "harness-design-studio", "version": stamp.version},
        "model_hash": stamp.model_hash,
        "project": {"name": project.meta.name, "description": project.meta.description},
        "placeholder_config": sorted(n for n, c in project.config.items() if c.placeholder),
        "units": dump(project.units.values()),
        "interface_types": dump(project.interface_types.values()),
        "interfaces": dump(project.interfaces.values()),
        "box_connectors": dump(project.connectors.values()),
        "harnesses": [
            harness_dump(h) for h in sorted(project.harnesses.values(), key=lambda x: x.id)
        ],
        "parts": dump(project.parts.values()),
    }
    return (json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


_FIXED = datetime(2000, 1, 1)


def _reason(exc: Exception) -> str:
    """Why a workbook failed, in a few plain words (no design data, no paths)."""
    if isinstance(exc, OSError) and exc.strerror:
        return exc.strerror
    text = str(exc).splitlines()[0][:80] if str(exc) else ""
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def xlsx_bytes(sheets: dict[str, Table], stamp: Stamp) -> bytes:
    """A workbook with one sheet per table plus an About sheet carrying the stamp. The zip is
    rewritten with fixed timestamps so equal input gives equal bytes. Text that looks like a
    formula is stored as text. Any failure of the spreadsheet library (a full temporary folder,
    for example) is reported as an `OutputsError` that says why."""
    try:
        return _xlsx_bytes(sheets, stamp)
    except Exception as exc:  # the library raises many kinds (OSError, lxml, zipfile)
        raise OutputsError(
            f"The Excel workbook could not be built ({_reason(exc)}). Nothing was written."
        ) from exc


def _xlsx_bytes(sheets: dict[str, Table], stamp: Stamp) -> bytes:
    wb = Workbook(write_only=True)
    wb.properties.creator = "harness-design-studio"
    wb.properties.created = wb.properties.modified = _FIXED
    wb.properties.title = stamp.line

    def cells(ws: Any, row: list[str]) -> list[Any]:
        out: list[Any] = []
        for v in row:
            v = ILLEGAL_CHARACTERS_RE.sub("", v)  # a control character would abort the workbook
            c = WriteOnlyCell(ws, value=v)
            if v[:1] in ("=", "+", "-", "@", "\t", "\r"):
                c.data_type = "s"
            out.append(c)
        return out

    about = wb.create_sheet("About")
    about.append(["Generated by", stamp.line])
    about.append(["Model hash", stamp.model_hash])
    for name, table in sheets.items():
        ws = wb.create_sheet(name[:31])
        for row in table:
            ws.append(cells(ws, row))
    raw = io.BytesIO()
    wb.save(raw)
    return normalise_xlsx(raw.getvalue())


def normalise_xlsx(raw: bytes) -> bytes:
    """The same workbook with its zip rewritten: entries in name order, fixed timestamps, and the
    creation and modification time pinned, so equal input gives equal bytes."""
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw)) as src,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst,
    ):
        for name in sorted(src.namelist()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            data = src.read(name)
            if name == "docProps/core.xml":  # openpyxl stamps the save time; pin it
                data = re.sub(
                    rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*",
                    rb"\g<1>2000-01-01T00:00:00Z",
                    data,
                )
            dst.writestr(info, data)
    return out.getvalue()
