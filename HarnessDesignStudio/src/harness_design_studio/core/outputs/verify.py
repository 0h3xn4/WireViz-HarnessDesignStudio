"""Output verifier v2: re-reads the finished artefacts (CSV, SVG, PDF, YAML, JSON, XLSX, manifest)
and compares them with the model. It does not import the table or drawing builders; it parses
the bytes and derives what they must contain straight from the project, so a bug in a builder
cannot hide itself."""

import csv
import hashlib
import html
import io
import json
import re
import zipfile
import zlib
from collections import Counter, defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from harness_design_studio import __version__
from harness_design_studio.core import checks, configcheck, drc
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.model import Connector, Harness, Pin, Project, Wire
from harness_design_studio.core.verify import VerifyReport, link_issues

from .stamp import parse_csv

MANIFEST = "manifest.json"
HARNESS_FILES = (
    "wirelist.csv",
    "pinouts.csv",
    "bom.csv",
    "mass_length.csv",
    "tests.csv",
    "labels.csv",
    "wireviz.yaml",
)  # plus accessories.csv for a harness that has accessories (D-170)
SYSTEM_FILES = (
    "bom.csv", "mass_length.csv", "mating_matrix.csv", "traceability.csv", "box_pinouts.csv",
    "drc_findings.csv", "drc_report.md", "changelog.csv", "revision_report.md", "export.json", "provenance.json", "system.xlsx",
    "block_diagram.svg",
    "block_diagram.pdf", "harness_overview.svg", "harness_overview.pdf",
)  # fmt: skip


def read_folder(folder: Path | str) -> dict[str, bytes]:
    root = Path(folder)
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.is_symlink() and not p.name.endswith(".tmp")
    }


def _table(files: dict[str, bytes], rel: str) -> list[list[str]] | None:
    return parse_csv(files[rel]) if rel in files else None


def _svg_text(data: bytes) -> str:
    return " ".join(re.findall(r"<text[^>]*>([^<]*)</text>", data.decode()))


def _pdf_pages(data: bytes) -> int:
    return len(re.findall(rb"/Type /Page /", data))


def _unescape(s: str) -> str:
    return s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


DAMAGE = (
    ValueError,
    KeyError,
    IndexError,
    TypeError,
    AttributeError,
    RecursionError,
    EOFError,
    OSError,
    zipfile.BadZipFile,
    NotImplementedError,  # zipfile: a damaged header names a zip version or method it lacks
    zlib.error,
    csv.Error,
)


def _guard(r: VerifyReport, what: str, fn: Callable[[], None]) -> None:
    """Damaged or unexpected file content is a finding, never a crash."""
    try:
        fn()
    except DAMAGE as exc:
        r.error(
            "out_unreadable",
            f"{what} could not be read ({type(exc).__name__}): it is damaged or not what the tool wrote.",
            what,
        )


def verify_outputs(project: Project, files: dict[str, bytes]) -> VerifyReport:
    r = VerifyReport()
    current = model_hash(project)
    short = current[:12]
    _guard(r, MANIFEST, lambda: _manifest(r, files, current))
    for rel in sorted(files):
        if rel != MANIFEST:
            _guard(r, rel, lambda rel=rel: _stamp(r, rel, files[rel], short))  # type: ignore[misc]
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        _guard(r, f"harnesses/{h.id}", lambda h=h: _harness(r, project, h, files))  # type: ignore[misc]
    _guard(r, "system", lambda: _system(r, project, files))
    # a harness made from a link must still carry the link's pairs: outputs of a harness that
    # drifted from its link would describe something else than the agreed pinout
    r.issues.extend(link_issues(project))
    return r


def _manifest(r: VerifyReport, files: dict[str, bytes], current: str) -> None:
    raw = files.get(MANIFEST)
    if raw is None:
        return  # an in-memory set has no manifest; a folder always does
    try:
        doc = json.loads(raw)
        listed = {f["path"]: (f["sha256"], f["bytes"]) for f in doc["files"]}
    except (ValueError, KeyError, TypeError):
        r.error("out_manifest", "The manifest cannot be read.", MANIFEST)
        return
    if doc.get("model_hash") != current:
        r.error("out_stale", "The outputs were made from an older version of the design.", MANIFEST)
        r.stale = True
    for rel, (digest, size) in sorted(listed.items()):
        data = files.get(rel)
        if data is None:
            r.error("out_missing", f"{rel} is listed in the manifest but missing.", rel)
        elif hashlib.sha256(data).hexdigest() != digest or len(data) != size:
            r.error("out_modified", f"{rel} was changed after it was exported.", rel)
    for rel in sorted(set(files) - set(listed) - {MANIFEST}):
        r.warning("out_unlisted", f"{rel} is not listed in the manifest.", rel)


def _stamp(r: VerifyReport, rel: str, data: bytes, short: str) -> None:
    if rel.endswith((".csv", ".yaml")):
        first = data.split(b"\n", 1)[0].decode()
        ok = first.startswith("# harness-design-studio ") and first.endswith(f"model {short}")
    elif rel.endswith(".md"):
        ok = (
            data.startswith(b"<!-- harness-design-studio ")
            and f"model {short}".encode() in data.split(b"\n", 1)[0]
        )
    elif rel.endswith(".svg"):
        ok = (
            re.search(
                rb"<desc>harness-design-studio [^<]* model " + short.encode() + rb"</desc>", data
            )
            is not None
        )
    elif rel.endswith(".pdf"):
        ok = f"model {short}".encode() in data
    elif rel.endswith(".json"):
        ok = f'"model_hash": "{short}'.encode() in data
    elif rel.endswith(".xlsx"):
        ok = _xlsx_hash(data) == short
    else:
        return
    if not ok:
        r.error("out_stamp", f"{rel} does not carry the current generator and model stamp.", rel)


def _xlsx_sheets(data: bytes) -> dict[str, list[list[str]]]:
    """Read the inline-string cells of a workbook straight from its XML (fast, no spreadsheet
    library): sheet name -> rows."""
    out: dict[str, list[list[str]]] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = re.findall(r'<sheet [^>]*name="([^"]*)"', z.read("xl/workbook.xml").decode())
        for n, name in enumerate(names, start=1):
            xml = z.read(f"xl/worksheets/sheet{n}.xml").decode()
            rows = []
            for row in re.findall(r"<row [^>]*>(.*?)</row>", xml, flags=re.S):
                rows.append(
                    [
                        html.unescape("".join(re.findall(r"<t[^>]*>([^<]*)</t>", c)))
                        for c in re.findall(r"<c [^>]*?(?:/>|>.*?</c>)", row, flags=re.S)
                    ]
                )
            out[html.unescape(name)] = rows
    return out


def _xlsx_hash(data: bytes) -> str:
    rows = _xlsx_sheets(data).get("About", [])
    return rows[1][1][:12] if len(rows) > 1 and len(rows[1]) > 1 else ""


def _xlsx_rows(data: bytes, sheet: str) -> list[list[str]]:
    return _xlsx_sheets(data).get(sheet, [])


def _harness(r: VerifyReport, project: Project, h: Harness, files: dict[str, bytes]) -> None:
    base = f"harnesses/{h.id}"
    for name in HARNESS_FILES:
        if f"{base}/{name}" not in files:
            r.error("out_missing", f"{base}/{name} was not generated.", h.id)
    if h.accessories and f"{base}/accessories.csv" not in files:
        r.error("out_missing", f"{base}/accessories.csv was not generated.", h.id)
    if not h.accessories and f"{base}/accessories.csv" in files:
        r.error("out_accessories", f"{h.id} has no accessories but a file lists some.", h.id)
    wl = _table(files, f"{base}/wirelist.csv")
    if wl:
        expected = {w.id: w for w in h.wires}
        rows = wl[1:]
        got = Counter(row[0] for row in rows)
        for wid in sorted(expected):
            if got[wid] == 0:
                r.error("out_wire_missing", f"Wire {wid} is not in the wire list of {h.id}.", wid)
            elif got[wid] > 1:
                r.error(
                    "out_wire_duplicated",
                    f"Wire {wid} appears {got[wid]} times in the wire list of {h.id}.",
                    wid,
                )
        for wid in sorted(set(got) - set(expected)):
            r.error(
                "out_wire_extra",
                f"The wire list of {h.id} has {wid}, which is not in the design.",
                wid,
            )
        for row in rows:
            w = expected.get(row[0])
            if w is None:
                continue
            want = [
                w.from_connector,
                w.from_pin,
                w.to_connector,
                w.to_pin,
                "pending" if w.gauge_awg is None else str(w.gauge_awg),
            ]
            if row[3:8] != want:
                r.error(
                    "out_wire_differs",
                    f"Wire {w.id} in the wire list does not match the design (ends or gauge).",
                    w.id,
                )
            if w.length_m is not None and (not row[10] or abs(float(row[10]) - w.length_m) > 1e-9):
                r.error(
                    "out_wire_differs",
                    f"Wire {w.id} has a different length in the wire list.",
                    w.id,
                )
        r.wires_checked += len(h.wires)
    po = _table(files, f"{base}/pinouts.csv")
    if po:
        pins = {(row[0], row[4]) for row in po[1:]}
        want_pins = {(c.id, p.id) for c in h.connectors for p in c.pins}
        if pins != want_pins:
            r.error(
                "out_pinout",
                f"The pinout table of {h.id} lists different pins than the design.",
                h.id,
            )
        used: dict[tuple[str, str], set[str]] = defaultdict(set)
        for w in h.wires:
            used[(w.from_connector, w.from_pin)].add(w.id)
            used[(w.to_connector, w.to_pin)].add(w.id)
        for row in po[1:]:
            if set(filter(None, row[7].split(";"))) != used.get((row[0], row[4]), set()):
                r.error(
                    "out_pinout",
                    f"Pin {row[0]}.{row[4]} lists the wrong wires in the pinout table.",
                    h.id,
                )
                break
    ts = _table(files, f"{base}/tests.csv")
    if ts:
        cont = [row for row in ts[1:] if row[1] == "continuity"]
        iso = [row for row in ts[1:] if row[1] == "isolation"]
        if sorted(row[7] for row in cont) != sorted(w.id for w in h.wires):
            r.error(
                "out_tests", f"{h.id} does not have exactly one continuity test per wire.", h.id
            )
        if len(iso) != len(h.wires) + len(h.shields):
            r.error(
                "out_tests", f"{h.id} does not have one isolation test per wire and shield.", h.id
            )
    lb = _table(files, f"{base}/labels.csv")
    if lb and len(lb) - 1 != len(h.connectors) + 2 * len(h.wires) + (1 if h.label else 0):
        r.error("out_labels", f"{h.id} has the wrong number of labels.", h.id)
    yml = files.get(f"{base}/wireviz.yaml")
    if yml is not None:
        text = yml.decode()
        if len(re.findall(r"^  - - ", text, flags=re.M)) != len(h.wires):
            r.error(
                "out_yaml", f"The WireViz file of {h.id} has the wrong number of connections.", h.id
            )
    x = files.get(f"{base}/{h.id}.xlsx")
    if x is not None:
        ids = [row[0] for row in _xlsx_rows(x, "Wire list")[1:]]
        if sorted(ids) != sorted(w.id for w in h.wires):
            r.error(
                "out_xlsx", f"The workbook of {h.id} lists different wires than the design.", h.id
            )
    _harness_cells(r, project, h, files)
    _harness_tables(r, project, h, files)
    _build_workbook(r, project, h, files)
    if _has_drawings(files):  # D-169: the drawings are optional, but all or none of the harnesses
        _drawings(r, project, h, files)


# ---- cell-level expectations, derived from the project alone ------------------------------------


def _length(h: Harness, wire_id: str) -> float | None:
    """A wire's own length, else the sum of the segments on the path between its connectors
    (worked out here, not imported from the table builders)."""
    return _length_of(h, next(x for x in h.wires if x.id == wire_id))


def _length_of(h: Harness, w: Wire) -> float | None:
    if w.length_m is not None:
        return w.length_m
    adj: dict[str, list[tuple[str, float | None]]] = defaultdict(list)
    for s in h.segments:
        adj[s.from_node].append((s.to_node, s.length_m))
        adj[s.to_node].append((s.from_node, s.length_m))
    seen = {w.from_connector}
    stack: list[tuple[str, list[float | None]]] = [(w.from_connector, [])]
    while stack:
        node, trail = stack.pop()
        if node == w.to_connector:
            return None if any(x is None for x in trail) else sum(x for x in trail if x is not None)
        for nxt, ln in adj[node]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, [*trail, ln]))
    return None


def _saved_order(h: Harness) -> dict[str, Any]:
    """A harness as the JSON export shows it: its lists in ID order (as in the saved files)."""
    data = h.model_dump(mode="json")
    for key in (
        "connectors",
        "wires",
        "splices",
        "shields",
        "branch_points",
        "segments",
        "accessories",
    ):
        if key in data:  # a sparse list (accessories) is left out while it is empty
            data[key] = sorted(data[key], key=lambda x: x["id"])
    return data


def _same_number(cell: str, expected: float | None) -> bool:
    if expected is None:
        return cell == ""
    try:
        return abs(float(cell) - expected) <= 1e-5 * max(1.0, abs(expected))
    except ValueError:
        return False


def _mass(project: Project, h: Harness) -> tuple[float, bool]:
    """Mass of the parts whose mass is known, and whether every mass and length was known."""
    total, complete = 0.0, True
    for c in h.connectors:
        part = project.parts.get(c.part_id)
        if part is None or part.mass_g is None:
            complete = False
        else:
            total += part.mass_g
    for w in h.wires:
        part = project.parts.get(w.part_id) if w.part_id else None
        length = _length_of(h, w)
        if part is None or part.mass_per_m_g is None or length is None:
            complete = False
        else:
            total += part.mass_per_m_g * length
    return total, complete


def _margin(project: Project) -> float | None:
    cfg = project.config.get("generation")
    value = cfg.values.get("mass_margin_fraction") if cfg else None
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _harness_cells(r: VerifyReport, project: Project, h: Harness, files: dict[str, bytes]) -> None:
    base = f"harnesses/{h.id}"
    shield_of = {wid: s.id for s in h.shields for wid in s.wire_ids}
    wl = _table(files, f"{base}/wirelist.csv")
    if wl:
        by_id = {w.id: w for w in h.wires}
        has_strip = any(
            x.strip_a_mm is not None or x.strip_b_mm is not None
            for g in project.harnesses.values()
            for x in g.wires
        )
        if (len(wl[0]) >= 2 and wl[0][-2:] == _STRIP_HEADER) != has_strip:
            r.error(
                "out_wire_differs",
                f"The wire list of {h.id} has the wrong columns for the strip lengths.",
                h.id,
            )
        for row in wl[1:]:
            w = by_id.get(row[0])
            if w is None or len(row) < 13:
                continue
            wrong = []
            has_emc = any(t.emc_class for t in project.interface_types.values())
            has_text = any(x.label or x.note for g in project.harnesses.values() for x in g.wires)
            if has_strip:
                at = 13 + (1 if has_emc else 0) + (2 if has_text else 0)
                if len(row) < at + 2 or not (
                    _same_number(row[at], w.strip_a_mm) and _same_number(row[at + 1], w.strip_b_mm)
                ):
                    wrong.append("strip length")
            if has_emc:
                i = project.interfaces.get(w.interface_id or "")
                t = project.interface_types.get(i.type_id) if i else None
                if len(row) < 14 or row[13] != ((t.emc_class if t else None) or ""):
                    wrong.append("EMC class")
            if has_text:
                at = 13 + (1 if has_emc else 0)
                if len(row) < at + 2 or (row[at], row[at + 1]) != (w.label or "", w.note):
                    wrong.append("label or note")
            if row[1] != (w.signal or ""):
                wrong.append("signal")
            if row[2] != (w.interface_id or ""):
                wrong.append("interface")
            if row[8] != (w.part_id or ""):
                wrong.append("part")
            if row[9] != (w.colour or ""):
                wrong.append("colour")
            if not _same_number(row[10], _length_of(h, w)):
                wrong.append("length")
            if row[11] != shield_of.get(w.id, ""):
                wrong.append("shield group")
            if bool(row[12]) != w.locked:
                wrong.append("locked")
            if wrong:
                r.error(
                    "out_wire_differs",
                    f"Wire {w.id} in the wire list of {h.id} differs from the design: {', '.join(wrong)}.",
                    w.id,
                )
    ts = _table(files, f"{base}/tests.csv")
    if ts:
        by_id = {w.id: w for w in h.wires}
        for row in ts[1:]:
            w = by_id.get(row[7]) if row[1] == "continuity" else None
            if w is not None and (
                row[2] != f"{w.from_connector}.{w.from_pin}"
                or row[3] != f"{w.to_connector}.{w.to_pin}"
            ):
                r.error(
                    "out_tests",
                    f"The continuity test of {w.id} in {h.id} tests the wrong pins.",
                    w.id,
                )
    lb = _table(files, f"{base}/labels.csv")
    if lb:
        want = {c.id for c in h.connectors} | {f"{w.id}-{s}" for w in h.wires for s in "AB"}
        if h.label:
            want.add(h.id)
        if {row[0] for row in lb[1:]} != want:
            r.error(
                "out_labels", f"The labels of {h.id} are not the connectors and wire ends.", h.id
            )
    ml = _table(files, f"{base}/mass_length.csv")
    if ml and len(ml) >= 2:
        _mass_row(r, project, h, ml[1], h.id)
    yml = files.get(f"{base}/wireviz.yaml")
    if yml is not None:
        text = yml.decode()
        listed = set(re.findall(r'^  "([^"]+)":$', text, flags=re.M))
        if listed != {c.id for c in h.connectors} | {w.id for w in h.wires}:
            r.error(
                "out_yaml",
                f"The WireViz file of {h.id} lists different parts than the design.",
                h.id,
            )
    x = files.get(f"{base}/{h.id}.xlsx")
    if x is not None and wl and _xlsx_rows(x, "Wire list") != wl:
        r.error("out_xlsx", f"The workbook of {h.id} differs from its wire list.", h.id)


def _mass_row(r: VerifyReport, project: Project, h: Harness, row: list[str], what: str) -> None:
    if len(row) != 10:
        r.error(
            "out_mass", f"The mass and length row of {what} has the wrong number of columns.", what
        )
        return
    total, complete = _mass(project, h)
    lengths = [_length_of(h, w) for w in h.wires]
    known = sum(x for x in lengths if x is not None)
    unknown = sum(1 for x in lengths if x is None)
    margin = _margin(project)
    ok = (
        row[1] == str(len(h.wires))
        and row[2] == str(len(h.connectors))
        and _same_number(row[3], known)
        and row[4] == str(unknown)
        and _same_number(row[5], total)
        and _same_number(row[6], None if margin is None else total * margin)
        and _same_number(row[7], None if margin is None else total * (1 + margin))
        and row[8] == ("yes" if complete and unknown == 0 else "no")
        and row[9] == _missing_mass_data(project, h)
    )
    if not ok:
        r.error("out_mass", f"The mass and length of {what} do not match the design.", what)


def _drawings(r: VerifyReport, project: Project, h: Harness, files: dict[str, bytes]) -> None:
    base = f"harnesses/{h.id}"
    svgs = sorted(k for k in files if re.fullmatch(re.escape(base) + r"/drawing_A3_s\d+\.svg", k))
    if not svgs:
        r.error("out_missing", f"{h.id} has no drawing.", h.id)
        return
    nums = sorted(int(re.search(r"_s(\d+)\.svg", k).group(1)) for k in svgs)  # type: ignore[union-attr]
    if nums != list(range(1, len(nums) + 1)):
        r.error(
            "out_drawing", f"The drawing sheets of {h.id} are not numbered 1 to {len(nums)}.", h.id
        )
    text = " ".join(_svg_text(files[k]) for k in svgs)
    words = set(text.split())
    for wid in sorted(w.id for w in h.wires):
        if _unescape(wid) not in words:
            r.error("out_drawing", f"Wire {wid} is missing from the drawing of {h.id}.", wid)
    for c in h.connectors:
        if c.id not in words and c.id not in text:
            r.error("out_drawing", f"Connector {c.id} is missing from the drawing of {h.id}.", c.id)
    if "sheet" in configcheck.titleblock_fields(project):  # a title block may leave it out
        for k in svgs:
            sheet = re.search(r"_s(\d+)\.svg", k).group(1)  # type: ignore[union-attr]
            if f"{sheet} / {len(svgs)}" not in _svg_text(files[k]):
                r.error(
                    "out_drawing", f"The title block of {k} shows the wrong sheet number.", h.id
                )
    a3 = files.get(f"{base}/drawing_A3.pdf")
    if a3 is not None and _pdf_pages(a3) != len(svgs):
        r.error(
            "out_drawing",
            f"The A3 PDF of {h.id} has a different number of sheets than the SVG files.",
            h.id,
        )
    for size in ("A3", "A4"):
        pdf = files.get(f"{base}/drawing_{size}.pdf")
        if pdf is not None:
            for w in h.wires:
                if w.id.encode() not in pdf:
                    r.error(
                        "out_drawing",
                        f"Wire {w.id} is missing from the {size} PDF of {h.id}.",
                        w.id,
                    )
                    break
    _drawing_pins(r, project, h, svgs, files)
    for size in ("A3", "A4"):
        pdf = files.get(f"{base}/drawing_{size}.pdf")
        if pdf is not None:
            wired = {(w.from_connector) for w in h.wires} | {w.to_connector for w in h.wires}
            for c in h.connectors:
                # a connector with no wire is not drawn as a box: its pins are in the spare-pin line
                needle = b"(" + c.id.encode() + b") Tj" if c.id in wired else c.id.encode()
                if needle not in pdf:
                    r.error("out_drawing", f"Connector {c.id} is missing from the {size} PDF of {h.id}.", c.id)  # fmt: skip
                    break
    if a3 is not None:
        _pdf_matches_svgs(r, f"The A3 PDF of {h.id}", a3, [files[k] for k in svgs], h.id)
    if a3 is not None or files.get(f"{base}/drawing_A4.pdf") is not None:
        _unencodable(r, f"the PDF drawings of {h.id}", [files[k] for k in svgs], h.id)


_TEXT = re.compile(r"<text ([^>]*)>([^<]*)</text>")


def _svg_items(data: bytes) -> list[tuple[str, str]]:
    """(data-ref label or "", text) of every text element of a drawing."""
    out = []
    for attrs, content in _TEXT.findall(data.decode()):
        ref = re.search(r'data-ref="([^"]*)"', attrs)
        out.append((html.unescape(ref[1]) if ref else "", html.unescape(content)))
    return out


def _drawn_signal(project: Project, h: Harness, cid: str, pin: str) -> str:
    """The signal a pin row shows: the cable connector's, else the box connector's it mates with."""
    conn = next((c for c in h.connectors if c.id == cid), None)
    box = project.connectors.get(conn.mates_with or "") if conn else None
    for c in (conn, box):
        sig = next((p.signal for p in (c.pins if c else []) if p.id == pin and p.signal), None)
        if sig:
            return sig
    return ""


def _drawing_pins(
    r: VerifyReport, project: Project, h: Harness, svgs: list[str], files: dict[str, bytes]
) -> None:
    """Every pin row of the drawing shows the right pin number and signal, and every wire end is
    drawn. (The drawing labels each pin and signal text with `data-ref` so it can be found.)"""
    real = {(c.id, p.id) for c in h.connectors for p in c.pins}
    drawn: set[tuple[str, str]] = set()
    bad: list[str] = []
    for k in svgs:
        for ref, text in _svg_items(files[k]):
            kind, _s, rest = ref.partition("/")
            if kind not in ("pin", "sig"):
                continue
            cid, _s, pin = rest.partition("/")
            if (cid, pin) not in real:
                bad.append(f"{cid}.{pin} is not a pin of the design")
            elif kind == "pin":
                drawn.add((cid, pin))
                if text != pin:
                    bad.append(f"pin {cid}.{pin} is drawn as '{text}'")
            else:
                want = _drawn_signal(project, h, cid, pin)
                cut = text.endswith("~") and len(text) < len(want) and want.startswith(text[:-1])
                if text != want and not cut:
                    bad.append(f"the signal of {cid}.{pin} is drawn as '{text}'")
    for w in h.wires:
        for end in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
            if end not in drawn:
                bad.append(f"pin {end[0]}.{end[1]} of wire {w.id} is not drawn")
    for text in dict.fromkeys(bad[:3]):
        r.error("out_drawing", f"The drawing of {h.id} is wrong: {text}.", h.id)
    if len(bad) > 3:
        r.error("out_drawing", f"The drawing of {h.id} has {len(bad) - 3} more wrong pins.", h.id)


def _pdf_texts(data: bytes) -> list[bytes]:
    """The strings the pages of a PDF of this tool show (uncompressed content streams)."""
    found = re.findall(rb"\(((?:\\.|[^\\()])*)\) Tj", data)
    return sorted(re.sub(rb"\\(.)", rb"\1", t) for t in found)


def _pdf_matches_svgs(r: VerifyReport, what: str, pdf: bytes, svgs: list[bytes], obj: str) -> None:
    """A PDF drawing carries the same texts as the SVG sheets it was made with (as Windows-1252)."""
    want = sorted(
        text.encode("cp1252", "replace") for svg in svgs for _ref, text in _svg_items(svg)
    )
    if _pdf_texts(pdf) != want:
        r.error("out_drawing", f"{what} does not show the same texts as the SVG drawing.", obj)


def _unencodable(r: VerifyReport, what: str, svgs: list[bytes], obj: str) -> None:
    """PDF text is Windows-1252; other characters turn into '?'. Say which, once."""
    chars = sorted(
        {ch for svg in svgs for _ref, text in _svg_items(svg) for ch in text if _no_cp1252(ch)}
    )
    if chars:
        names = ", ".join(f"{c} (U+{ord(c):04X})" for c in chars[:8])
        more = f" and {len(chars) - 8} more" if len(chars) > 8 else ""
        r.warning(
            "out_pdf_chars",
            f"These characters cannot be shown in {what} and appear as '?' there: {names}{more}. "
            "The SVG drawings show them correctly.",
            obj,
        )


def _no_cp1252(ch: str) -> bool:
    try:
        ch.encode("cp1252")
    except UnicodeEncodeError:
        return True
    return False


def _provenance(r: VerifyReport, project: Project, files: dict[str, bytes]) -> None:
    """The provenance file must say which design it was made from and which settings were
    placeholders, derived here from the project and not from the builder."""
    raw = files.get("system/provenance.json")
    if raw is None:
        return
    try:
        doc = json.loads(raw)
    except ValueError:
        r.error("out_provenance", "system/provenance.json is not valid JSON.", "provenance")
        return
    if not isinstance(doc, dict) or doc.get("format") != "harness-design-studio-provenance":
        r.error("out_provenance", "system/provenance.json has the wrong format.", "provenance")
        return
    settings = doc.get("settings", {})
    placeholders = sorted(n for n, c in project.config.items() if c.placeholder)
    listed = (
        sorted(n for n, v in settings.items() if isinstance(v, dict) and v.get("placeholder"))
        if isinstance(settings, dict)
        else []
    )
    if listed != placeholders:
        r.error(
            "out_provenance",
            "system/provenance.json does not list the placeholder settings of the design.",
            "provenance",
        )
    approvals = Counter(p.approval for p in project.parts.values())
    info = project.library_info
    want: dict[str, object] = {
        "tool_version": __version__,
        "model_hash": model_hash(project),
        "project": project.meta.name,
        "library": {
            "name": info.name, "version": info.version, "source": info.source, "date": info.date,
            "parts": len(project.parts), "parts_by_approval": dict(sorted(approvals.items())),
            "unverified_parts": sum(p.unverified for p in project.parts.values()),
        },
        "settings": {
            name: {"placeholder": cfg.placeholder, "values_sha256_16": _values_hash(cfg.values)}
            for name, cfg in sorted(project.config.items())
        },
        "design": {
            "units": len(project.units),
            "interfaces": len(project.interfaces),
            "harnesses": len(project.harnesses),
            "wires": sum(len(h.wires) for h in project.harnesses.values()),
            "released_harnesses": sum(h.status == "released" for h in project.harnesses.values()),
        },
    }  # fmt: skip
    wrong = [key for key, value in want.items() if doc.get(key) != value]
    if wrong:
        r.error(
            "out_provenance",
            f"system/provenance.json differs from the design: {', '.join(wrong)}.",
            "provenance",
        )


def _values_hash(values: dict[str, object]) -> str:
    text = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _system(r: VerifyReport, project: Project, files: dict[str, bytes]) -> None:
    for name in SYSTEM_FILES:
        if f"system/{name}" not in files:
            r.error("out_missing", f"system/{name} was not generated.", name)
    wires = [w for h in project.harnesses.values() for w in h.wires]
    _provenance(r, project, files)
    ml = _table(files, "system/mass_length.csv")
    if ml and (ml[-1][0] != "TOTAL" or ml[-1][1] != str(len(wires))):
        r.error(
            "out_mass", "The system mass and length table does not count every wire.", "mass_length"
        )
    elif ml:
        _mass_total(r, project, ml[-1])
        by_h = {row[0]: row for row in ml[1:-1]}
        if set(by_h) != set(project.harnesses):
            r.error(
                "out_mass",
                "The system mass table does not list exactly the harnesses.",
                "mass_length",
            )
        for hid, row in sorted(by_h.items()):
            if hid in project.harnesses:
                _mass_row(r, project, project.harnesses[hid], row, hid)
    harnesses = sorted(project.harnesses.values(), key=lambda x: x.id)
    bm = _table(files, "system/bom.csv")
    if bm:
        _compare_rows(r, "out_bom", "The system BOM", bm, _BOM_HEADER,
                      _bom_rows(project, harnesses), (0, 7), "bom")  # fmt: skip
    mm = _table(files, "system/mating_matrix.csv")
    if mm:
        boxes = {row[0] for row in mm[1:]}
        if boxes != set(project.connectors):
            r.error(
                "out_matrix",
                "The mating matrix does not list exactly the box connectors.",
                "mating_matrix",
            )
        pairs = {(row[0], row[4]) for row in mm[1:] if row[4]}
        for h in project.harnesses.values():
            for c in h.connectors:
                if c.mates_with and (c.mates_with, c.id) not in pairs:
                    r.error("out_matrix", f"{c.id} is missing from the mating matrix.", c.id)
        _compare_rows(r, "out_matrix", "The mating matrix", mm, _MATING_HEADER,
                      _mating_rows(project), (0, 4, 7), "mating_matrix")  # fmt: skip
    tr = _table(files, "system/traceability.csv")
    if tr:
        routed = {w.interface_id for w in wires if w.interface_id}
        if {row[0] for row in tr[1:]} != set(project.interfaces):
            r.error(
                "out_trace",
                "The traceability matrix does not list exactly the interfaces.",
                "traceability",
            )
        for row in tr[1:]:
            if (row[7] == "yes") != (row[0] in routed):
                r.error("out_trace", f"{row[0]} is marked wrongly as routed or not routed.", row[0])
        _compare_rows(r, "out_trace", "The traceability matrix", tr, _TRACE_HEADER,
                      _trace_rows(project), (0,), "traceability")  # fmt: skip
    bp = _table(files, "system/box_pinouts.csv")
    if bp:
        attached: dict[tuple[str, str], list[str]] = defaultdict(list)
        for h in project.harnesses.values():
            mates = {c.id: c.mates_with for c in h.connectors}
            for w in h.wires:
                for cid, pin in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
                    if mates.get(cid):
                        attached[(mates[cid] or "", pin)].append(w.id)
        boxes_sorted = sorted(project.connectors.values(), key=lambda c: c.id)
        _compare_rows(r, "out_box_pinouts", "The box connector pinouts", bp, _pinout_header(project),
                      _pin_rows(boxes_sorted, attached, _uses_function(project), _uses_termination(project), _uses_contact(project), _uses_direction(project)), (0, 4), "box_pinouts")  # fmt: skip
    _system_workbook(r, project, files)
    ex = files.get("system/export.json")
    if ex is not None:
        try:
            doc = json.loads(ex)
            same = (
                doc["model_hash"] == model_hash(project)
                and len(doc["units"]) == len(project.units)
                and len(doc["interfaces"]) == len(project.interfaces)
                and ("links" in doc) == bool(project.links)
                and sum(len(h["wires"]) for h in doc["harnesses"]) == len(wires)
                and {h["id"]: h for h in doc["harnesses"]}
                == {h.id: _saved_order(h) for h in project.harnesses.values()}
                and all(
                    {o["id"]: o for o in doc[key]}
                    == {o.id: o.model_dump(mode="json") for o in objs}
                    for key, objs in (
                        ("units", project.units.values()),
                        ("interface_types", project.interface_types.values()),
                        ("interfaces", project.interfaces.values()),
                        ("box_connectors", project.connectors.values()),
                        ("parts", project.parts.values()),
                        *((("links", project.links.values()),) if project.links else ()),
                    )
                )
            )
        except (ValueError, KeyError, TypeError):
            same = False
        if not same:
            r.error("out_json", "The JSON export does not match the design.", "export.json")
    for name, ids, what in (
        ("block_diagram", sorted(project.units), "unit"),
        ("harness_overview", sorted(project.harnesses), "harness"),
    ):
        svg = files.get(f"system/{name}.svg")
        if svg is not None:
            text = _svg_text(svg)
            words = set(text.split())
            missing = [i for i in ids if i not in words and name == "block_diagram"]
            if missing:
                r.error(
                    "out_diagram",
                    f"The {name.replace('_', ' ')} is missing {what} {missing[0]}.",
                    name,
                )
    fd = _table(files, "system/drc_findings.csv")
    if fd:
        found = [*checks.find(project), *drc.run(project)]
        want_rows = [
            [f.id, f.rule, f.severity, f.object_id or "", f.title, "yes" if f.waiver else "",
             f.waiver.justification if f.waiver else "", " ".join(f.sources)]
            for f in found
        ]  # fmt: skip
        if fd[0] != _FINDING_HEADER or len(fd) - 1 != len(found):
            r.error(
                "out_drc", "The DRC findings table does not list every finding.", "drc_findings"
            )
        elif Counter(map(tuple, fd[1:])) != Counter(map(tuple, want_rows)):
            r.error(
                "out_drc",
                "The DRC findings table has a finding whose text, severity or waiver differs "
                "from the design.",
                "drc_findings",
            )
    cl = _table(files, "system/changelog.csv")
    if cl and sorted(row[0] for row in cl[1:]) != sorted(project.changelog):
        r.error(
            "out_changelog",
            "The change log table does not list exactly the change log entries.",
            "changelog",
        )
    rr = files.get("system/revision_report.md")
    if rr is not None:
        words = set(rr.decode().replace("`", " ").replace("(", " ").split())
        for hid in sorted({b.harness_id for b in project.baselines.values()}):
            if hid not in words:
                r.error("out_changelog", f"The revision report does not mention {hid}.", hid)
    md = files.get("system/drc_report.md")
    if md is not None and "Waived:" not in md.decode():
        r.error("out_drc", "The DRC report is incomplete.", "drc_report")


# ---- row-by-row comparison of the tables with the design --------------------------------------
# Every cell of every table is derived here from the project (the wording of the cells is the
# documented format in docs/OUTPUTS.md), then compared with what was written.

Cell = str | float | None  # a float (or None, meaning "no value") is compared as a number


def _cell_ok(got: str, want: Cell) -> bool:
    return got == want if isinstance(want, str) else _same_number(got, want)


def _compare_rows(
    r: VerifyReport,
    code: str,
    what: str,
    got: list[list[str]],
    header: list[str],
    want: list[list[Cell]],
    keycols: tuple[int, ...],
    obj: str,
) -> None:
    """Report the first differences between a written table and the rows the design requires:
    wrong column headings, missing, extra or repeated rows, and cells with the wrong content."""
    if got[0] != header:
        r.error(code, f"{what} has the wrong column headings.", obj)
        return
    expected = {tuple(str(row[i]) for i in keycols): row for row in want}
    seen: set[tuple[str, ...]] = set()
    problems: list[str] = []
    for row in got[1:]:
        if len(row) != len(header):
            problems.append("a row has the wrong number of cells")
            continue
        key = tuple(row[i] for i in keycols)
        name = "/".join(k for k in key if k) or "(empty key)"
        exp = expected.get(key)
        if exp is None:
            problems.append(f"{name} is not in the design")
        elif key in seen:
            problems.append(f"{name} appears twice")
        else:
            seen.add(key)
            cols = [
                header[i]
                for i, (g, e) in enumerate(zip(row, exp, strict=True))
                if not _cell_ok(g, e)
            ]
            if cols:
                problems.append(f"{name} ({', '.join(cols)})")
    problems += [
        f"{'/'.join(k for k in key if k)} is missing" for key in sorted(set(expected) - seen)
    ]
    if problems:
        more = f" and {len(problems) - 3} more" if len(problems) > 3 else ""
        r.error(code, f"{what} differs from the design: {'; '.join(problems[:3])}{more}.", obj)


_STRIP_HEADER = ["Strip A (mm)", "Strip B (mm)"]
_PINOUT_HEADER = [
    "Connector", "Role", "Mates with", "Part", "Pin", "Signal", "Interface", "Wires", "Spare",
]  # fmt: skip


def _pinout_header(project: Project) -> list[str]:
    return [
        *_PINOUT_HEADER,
        *(["Function"] if _uses_function(project) else []),
        *(["Termination"] if _uses_termination(project) else []),
        *(["Contact"] if _uses_contact(project) else []),
        *(["Direction"] if _uses_direction(project) else []),
    ]


def _all_pins(project: Project) -> list[Pin]:
    return [p for c in project.connectors.values() for p in c.pins] + [
        p for h in project.harnesses.values() for c in h.connectors for p in c.pins
    ]


def _uses_function(project: Project) -> bool:
    return any(p.function for p in _all_pins(project))


def _uses_termination(project: Project) -> bool:
    return any(p.termination != "unspecified" for p in _all_pins(project))


def _uses_contact(project: Project) -> bool:
    return any(p.contact_part for p in _all_pins(project))


def _uses_direction(project: Project) -> bool:
    return any(p.direction for p in _all_pins(project))


_DIRECTION_TEXT = {"": "", "in": "in", "out": "out", "bidir": "bidirectional"}


def _pin_rows(
    connectors: list[Connector],
    attached: dict[tuple[str, str], list[str]],
    function: bool = False,
    termination: bool = False,
    contact: bool = False,
    direction: bool = False,
) -> list[list[Cell]]:
    rows: list[list[Cell]] = []
    for c in connectors:
        for p in c.pins:
            wires = sorted(attached.get((c.id, p.id), []))
            rows.append([
                c.id, c.role, c.mates_with or "", c.part_id, p.id, p.signal or "",
                p.interface_id or "", ";".join(wires),
                "no" if wires or p.interface_id or p.signal else "yes",
                *([p.function or ""] if function else []),
                *([p.termination] if termination else []),
                *([p.contact_part or ""] if contact else []),
                *([_DIRECTION_TEXT[p.direction]] if direction else []),
            ])  # fmt: skip
    return rows


def _harness_attached(h: Harness) -> dict[tuple[str, str], list[str]]:
    attached: dict[tuple[str, str], list[str]] = defaultdict(list)
    for w in h.wires:
        attached[(w.from_connector, w.from_pin)].append(w.id)
        attached[(w.to_connector, w.to_pin)].append(w.id)
    return attached


_BOM_HEADER = [
    "Part", "Category", "Manufacturer", "Part number", "Description", "Approval",
    "Quantity", "Unit", "Wires without length", "Used in",
]  # fmt: skip


def _bom_rows(project: Project, harnesses: list[Harness]) -> list[list[Cell]]:
    """One line per part and unit. Connector parts, the contact part of each pin in use (one per
    pin) and accessory parts without a length count `ea` (an accessory by its quantity); wire parts
    and accessory parts with a length add up metres (length_mm x quantity / 1000)."""
    counts: Counter[str] = Counter()
    metres: dict[str, float] = defaultdict(float)
    unknown: Counter[str] = Counter()
    used: dict[str, set[str]] = defaultdict(set)
    wire_parts: set[str] = set()
    acc_parts: set[str] = set()
    for h in harnesses:
        pins_used: set[tuple[str, str]] = set()
        for w in h.wires:
            pins_used |= {(w.from_connector, w.from_pin), (w.to_connector, w.to_pin)}
        for c in h.connectors:
            counts[c.part_id] += 1
            used[c.part_id].add(h.id)
            for p in c.pins:
                if p.contact_part and (c.id, p.id) in pins_used:
                    counts[p.contact_part] += 1
                    used[p.contact_part].add(h.id)
        for w in h.wires:
            pid = w.part_id or "(no part)"
            wire_parts.add(pid)
            used[pid].add(h.id)
            length = _length_of(h, w)
            if length is None:
                unknown[pid] += 1
            else:
                metres[pid] += length
        for a in h.accessories:
            if a.part_id:
                used[a.part_id].add(h.id)
                if a.length_mm is None:
                    counts[a.part_id] += a.quantity
                else:
                    acc_parts.add(a.part_id)
                    metres[a.part_id] += a.length_mm * a.quantity / 1000
    lines = sorted({*((p, "ea") for p in counts), *((p, "m") for p in wire_parts | acc_parts)})
    rows: list[list[Cell]] = []
    for pid, unit in lines:
        part = project.parts.get(pid)
        approval = (
            "missing from parts list"
            if part is None
            else part.approval + (" (example data)" if part.unverified else "")
        )
        rows.append([
            pid, part.category if part else "unknown", (part.manufacturer or "") if part else "",
            (part.part_number or "") if part else "", (part.description or "") if part else "",
            approval, metres[pid] if unit == "m" else str(counts[pid]), unit,
            str(unknown[pid]) if unit == "m" and pid in wire_parts else "",
            ";".join(sorted(used[pid])),
        ])  # fmt: skip
    return rows


_ACCESSORY_HEADER = [
    "Accessory", "Kind", "Part", "Target", "Position", "Length (mm)", "Quantity", "Note",
]  # fmt: skip


def _accessory_rows(h: Harness) -> list[list[Cell]]:
    return [
        [a.id, a.kind, a.part_id or "", a.target or "", a.position or "", a.length_mm,
         str(a.quantity), a.note]
        for a in h.accessories
    ]  # fmt: skip


def _limit(project: Project, key: str, unit: str) -> str:
    cfg = project.config.get("generation")
    v = cfg.values.get(key) if cfg else None
    return (
        f"{v:g} {unit}"
        if isinstance(v, int | float) and not isinstance(v, bool)
        else "TBD (placeholder)"
    )


_TEST_HEADER = ["Test", "Type", "From", "To", "Expected", "Limit", "Test voltage", "Wire"]


def _test_rows(project: Project, h: Harness) -> list[list[Cell]]:
    cont = _limit(project, "test_continuity_max_ohm", "ohm max")
    iso = _limit(project, "test_isolation_min_mohm", "Mohm min")
    volts = _limit(project, "test_isolation_voltage_v", "V")
    wires = sorted(h.wires, key=lambda x: x.id)
    rows: list[list[Cell]] = []
    for w in wires:
        rows.append(["", "continuity", f"{w.from_connector}.{w.from_pin}", f"{w.to_connector}.{w.to_pin}", "continuous", cont, "", w.id])  # fmt: skip
    for w in wires:
        rows.append(["", "isolation", f"{w.from_connector}.{w.from_pin}", "all other wires and shields", "isolated", iso, volts, w.id])  # fmt: skip
    for s in sorted(h.shields, key=lambda x: x.id):
        rows.append(["", "isolation", f"shield {s.id}", "all wires", "isolated", iso, volts, ";".join(sorted(s.wire_ids))])  # fmt: skip
    for n, row in enumerate(rows, start=1):
        row[0] = f"T{n:03d}"
    return rows


_LABEL_HEADER = ["Label", "Kind", "Text", "Quantity"]


def _emc_class(project: Project, w: Wire) -> str:
    i = project.interfaces.get(w.interface_id or "")
    t = project.interface_types.get(i.type_id) if i else None
    return (t.emc_class if t else None) or ""


def _label_rows(project: Project, h: Harness) -> list[list[Cell]]:
    rows: list[list[Cell]] = [[h.id, "harness", h.label, "1"]] if h.label else []
    for c in h.connectors:
        box = project.connectors.get(c.mates_with or "")
        name = c.label or ((box.label or "") if box is not None else "")
        mates = f"{c.id} mates {c.mates_with or '-'}"
        rows.append([c.id, "connector", f"{name} ({mates})" if name else mates, "1"])
    for w in h.wires:
        wname = w.label or w.signal
        head = f"{w.id} {wname}" if wname else w.id
        emc = _emc_class(project, w)
        tag = f" [EMC {emc}]" if emc else ""
        rows.append([f"{w.id}-A", "wire", f"{head} to {w.to_connector}.{w.to_pin}{tag}", "1"])
        rows.append([f"{w.id}-B", "wire", f"{head} to {w.from_connector}.{w.from_pin}{tag}", "1"])
    return rows


def _missing_mass_data(project: Project, h: Harness) -> str:
    """The text of the "Missing data" column: what is needed to complete the mass."""
    missing: set[str] = set()
    for c in h.connectors:
        part = project.parts.get(c.part_id)
        if part is None or part.mass_g is None:
            missing.add(f"mass of connector part {c.part_id}")
    for w in h.wires:
        part = project.parts.get(w.part_id) if w.part_id else None
        if part is None or part.mass_per_m_g is None:
            missing.add(f"mass per metre of wire part {w.part_id or '(none)'}")
        elif _length_of(h, w) is None:
            missing.add(f"length of wire {w.id}")
    return "; ".join(sorted(missing))


def _mating_rows(project: Project) -> list[list[Cell]]:
    mated: dict[str, list[tuple[str, Connector]]] = defaultdict(list)
    for h in project.harnesses.values():
        for c in h.connectors:
            if c.mates_with:
                mated[c.mates_with].append((h.id, c))
    rows: list[list[Cell]] = []
    for b in project.connectors.values():
        pairs = mated.get(b.id, [])
        if not pairs:
            rows.append([b.id, b.unit_id or "", b.part_id, b.gender, "", "", "", ""])
        for hid, c in pairs:
            rows.append([b.id, b.unit_id or "", b.part_id, b.gender, c.id, c.part_id, c.gender, hid])  # fmt: skip
    return rows


def _trace_rows(project: Project) -> list[list[Cell]]:
    carried: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for h in project.harnesses.values():
        for w in h.wires:
            if w.interface_id:
                carried[w.interface_id].append((h.id, w.id))
    rows: list[list[Cell]] = []
    for i in project.interfaces.values():
        ends = [f"{e.unit_id}/{e.connector_id or '-'}" for e in i.endpoints]
        wires = sorted(w for _h, w in carried.get(i.id, []))
        rows.append([
            i.id, i.name, i.type_id, ends[0] if ends else "", ends[1] if len(ends) > 1 else "",
            ";".join(sorted({hid for hid, _w in carried.get(i.id, [])})), ";".join(wires),
            "yes" if wires else "no",
        ])  # fmt: skip
    return rows


def _harness_tables(r: VerifyReport, project: Project, h: Harness, files: dict[str, bytes]) -> None:
    """Pinouts, BOM, tests and labels of one harness, cell by cell."""
    base = f"harnesses/{h.id}"
    po = _table(files, f"{base}/pinouts.csv")
    if po:
        conns = sorted(h.connectors, key=lambda c: c.id)
        _compare_rows(r, "out_pinout", f"The pinout table of {h.id}", po, _pinout_header(project),
                      _pin_rows(conns, _harness_attached(h), _uses_function(project), _uses_termination(project), _uses_contact(project), _uses_direction(project)), (0, 4), h.id)  # fmt: skip
    bm = _table(files, f"{base}/bom.csv")
    if bm:
        _compare_rows(r, "out_bom", f"The BOM of {h.id}", bm, _BOM_HEADER,
                      _bom_rows(project, [h]), (0, 7), h.id)  # fmt: skip
    ac = _table(files, f"{base}/accessories.csv")
    if ac:
        if [row[0] for row in ac[1:]] != sorted(a.id for a in h.accessories):
            r.error("out_accessories", f"The accessories of {h.id} are not in ID order.", h.id)
        _compare_rows(r, "out_accessories", f"The accessories of {h.id}", ac, _ACCESSORY_HEADER,
                      _accessory_rows(h), (0,), h.id)  # fmt: skip
    ts = _table(files, f"{base}/tests.csv")
    if ts:
        _compare_rows(r, "out_tests", f"The test list of {h.id}", ts, _TEST_HEADER,
                      _test_rows(project, h), (0,), h.id)  # fmt: skip
    lb = _table(files, f"{base}/labels.csv")
    if lb:
        _compare_rows(r, "out_labels", f"The labels of {h.id}", lb, _LABEL_HEADER,
                      _label_rows(project, h), (0,), h.id)  # fmt: skip
    yml = files.get(f"{base}/wireviz.yaml")
    if yml is not None:
        _yaml_values(r, h, yml.decode())
    x = files.get(f"{base}/{h.id}.xlsx")
    if x is not None:
        sheets = _xlsx_sheets(x)
        for name, rel in (
            ("Pinouts", "pinouts.csv"), ("BOM", "bom.csv"), ("Mass and length", "mass_length.csv"),
            ("Tests", "tests.csv"), ("Labels", "labels.csv"), ("Accessories", "accessories.csv"),
        ):  # fmt: skip
            table = _table(files, f"{base}/{rel}")
            if table and sheets.get(name) != table:
                r.error("out_xlsx", f"The '{name}' sheet of the workbook of {h.id} differs from {rel}.", h.id)  # fmt: skip
        if ("Accessories" in sheets) != bool(h.accessories):
            r.error("out_xlsx", f"The workbook of {h.id} has an Accessories sheet only when the harness has accessories.", h.id)  # fmt: skip


def _has_drawings(files: dict[str, bytes]) -> bool:
    """True when the set was written with the harness drawings (decision D-169 makes them optional;
    a set either has the drawings of every harness or of none)."""
    return any(re.fullmatch(r"harnesses/[^/]+/drawing_A3_s\d+\.svg", k) for k in files)


# ---- the build workbook (decision D-169) --------------------------------------------------------

_BUILD_SHEETS = [
    "Start here", "Cut list", "Connectors", "Parts", "Accessories", "Labels", "Tests", "About"
]  # fmt: skip
_BUILD_CUT_HEADER = [
    "Cut (x)", "Wire", "Colour", "AWG", "Part", "Length (m)", "Strip A (mm)", "Strip B (mm)",
    "From", "To", "Signal or label", "Shield group", "Note",
]  # fmt: skip
_BUILD_CONNECTOR_HEADER = [
    "Pin", "Signal", "Function", "Wire", "Colour", "AWG", "Goes to", "Termination", "Contact size",
    "Contact", "Tool", "Terminated (x)", "Inserted (x)", "Checked (x)",
]  # fmt: skip
_BUILD_NO_ACCESSORIES = "No accessories entered."
_BUILD_HARNESS_TARGET = "(harness)"
_BUILD_TEST_TAIL = ["Measured", "Result", "Initials", "Date"]
_TO_FILL = "to fill in"


def _xlsx_values(data: bytes) -> dict[str, list[list[str]]]:
    """Every sheet of a workbook as rows of text, read with the spreadsheet library (the build
    workbook holds numbers and styles, which the plain reader of `_xlsx_sheets` does not see):
    numbers are written with `repr`, an empty cell is ''."""
    from .xlsx_env import load_workbook

    out: dict[str, list[list[str]]] = {}
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append(
                ["" if v is None else repr(v) if isinstance(v, float) else str(v) for v in row]
            )
        out[ws.title] = rows
    wb.close()
    return out


def _cut_key(h: Harness, w: Wire) -> tuple[int, int, str, int, float, str]:
    """The order of the cut list: thick before thin, then colour, then length; unknown last."""
    length = _length_of(h, w)
    return (
        0 if w.gauge_awg is not None else 1,
        w.gauge_awg if w.gauge_awg is not None else 0,
        (w.colour or "~").lower(),
        0 if length is not None else 1,
        length if length is not None else 0.0,
        w.id,
    )


def _build_expected_checks(project: Project, h: Harness) -> dict[str, int]:
    """The open counts of the *Start here* sheet, worked out from the model alone."""
    used: set[tuple[str, str]] = set()
    for w in h.wires:
        used.add((w.from_connector, w.from_pin))
        used.add((w.to_connector, w.to_pin))
    parts = {c.part_id for c in h.connectors} | {w.part_id for w in h.wires if w.part_id}
    return {
        "Wires without a length": sum(1 for w in h.wires if _length_of(h, w) is None),
        "Wires without a gauge": sum(1 for w in h.wires if w.gauge_awg is None),
        "Wires without a colour": sum(1 for w in h.wires if not w.colour),
        "Wires without a part": sum(1 for w in h.wires if not w.part_id),
        "Pins in use without a termination": sum(
            1
            for c in h.connectors
            for p in c.pins
            if (c.id, p.id) in used and p.termination == "unspecified"
        ),
        "Wires without strip lengths": sum(
            1 for w in h.wires if w.strip_a_mm is None or w.strip_b_mm is None
        ),
        "Pins in use without a contact part": sum(
            1 for c in h.connectors for p in c.pins if (c.id, p.id) in used and not p.contact_part
        ),
        "Parts that are not approved": sum(
            1
            for pid in parts
            if pid not in project.parts or project.parts[pid].approval != "approved"
        ),
    }


def _build_workbook(r: VerifyReport, project: Project, h: Harness, files: dict[str, bytes]) -> None:
    """The build workbook of one harness against the design: the sheets, the cut list (every wire
    once, in cut order, with its values), the pins of every connector, the parts, labels and tests
    (the same rows as the CSV tables, plus empty columns to fill in) and the counts of *Start here*."""
    rel = f"harnesses/{h.id}/{h.id}_build.xlsx"
    data = files.get(rel)
    if data is None:
        r.error("out_missing", f"{rel} was not generated.", h.id)
        return
    what = f"The build workbook of {h.id}"
    sheets = _xlsx_values(data)
    if list(sheets) != _BUILD_SHEETS:
        r.error("out_build", f"{what} does not have the sheets {', '.join(_BUILD_SHEETS)}.", h.id)
        return
    _build_cut(r, h, what, sheets["Cut list"])
    _build_connectors(r, project, h, what, sheets["Connectors"])
    parts = sheets["Parts"]
    _compare_rows(r, "out_build", f"{what} (Parts)", parts, _BOM_HEADER,
                  _bom_rows(project, [h]), (0, 7), h.id)  # fmt: skip
    _build_accessories(r, h, what, sheets["Accessories"])
    labels = sheets["Labels"]
    if labels and labels[0] == ["Done (x)", *_LABEL_HEADER]:
        _compare_rows(r, "out_build", f"{what} (Labels)", [row[1:] for row in labels], _LABEL_HEADER,
                      _label_rows(project, h), (0,), h.id)  # fmt: skip
        if any(row[0] for row in labels[1:]):
            r.error("out_build", f"{what} has ticks in the Labels sheet before anything was done.", h.id)  # fmt: skip
    else:
        r.error("out_build", f"{what} (Labels) has the wrong column headings.", h.id)
    tests = sheets["Tests"]
    if tests and tests[0] == [*_TEST_HEADER, *_BUILD_TEST_TAIL]:
        _compare_rows(r, "out_build", f"{what} (Tests)", [row[:8] for row in tests], _TEST_HEADER,
                      _test_rows(project, h), (0,), h.id)  # fmt: skip
        if any(any(row[8:]) for row in tests[1:]):
            r.error("out_build", f"{what} has results in the Tests sheet before any test was run.", h.id)  # fmt: skip
    else:
        r.error("out_build", f"{what} (Tests) has the wrong column headings.", h.id)
    _build_start(r, project, h, what, sheets["Start here"])


def _build_cut(r: VerifyReport, h: Harness, what: str, rows: list[list[str]]) -> None:
    if not rows or rows[0] != _BUILD_CUT_HEADER:
        r.error("out_build", f"{what} (Cut list) has the wrong column headings.", h.id)
        return
    body = [row for row in rows[1:-1] if any(row)]
    total_row = rows[-1] if len(rows) > 1 else []
    order = [w.id for w in sorted(h.wires, key=lambda w: _cut_key(h, w))]
    if [row[1] for row in body] != order:
        r.error("out_build", f"{what} (Cut list) does not list the wires once each in cut order.", h.id)  # fmt: skip
        return
    shields = {wid: s.id for s in h.shields for wid in s.wire_ids}
    by_id = {w.id: w for w in h.wires}
    bad: list[str] = []
    known = 0.0
    for row in body:
        w = by_id[row[1]]
        length = _length_of(h, w)
        if length is not None:
            known += length
        colour_ok = row[2].startswith(w.colour) if w.colour else row[2] == _TO_FILL
        strip_ok = all(
            (cell == _TO_FILL) if v is None else _same_number(cell, v)
            for cell, v in ((row[6], w.strip_a_mm), (row[7], w.strip_b_mm))
        )
        gauge_ok = row[3] == _TO_FILL if w.gauge_awg is None else row[3] == str(w.gauge_awg)
        length_ok = row[5] == _TO_FILL if length is None else _same_number(row[5], length)
        part_ok = row[4] == (w.part_id or _TO_FILL)
        ends_ok = row[8] == f"{w.from_connector}.{w.from_pin}" and row[9] == f"{w.to_connector}.{w.to_pin}"  # fmt: skip
        name_ok = row[10] == (w.label or w.signal or "")
        extra_ok = row[11] == shields.get(w.id, "") and row[12] == w.note and row[0] == ""
        if not (
            colour_ok and gauge_ok and length_ok and strip_ok and part_ok and ends_ok and name_ok
            and extra_ok
        ):  # fmt: skip
            bad.append(w.id)
    if bad:
        more = f" and {len(bad) - 3} more" if len(bad) > 3 else ""
        r.error("out_build", f"{what} (Cut list) does not match the design for {', '.join(bad[:3])}{more}.", h.id)  # fmt: skip
    if (
        not total_row
        or total_row[1] != f"{len(h.wires)} wires"
        or not _same_number(total_row[5], known)
    ):
        r.error("out_build", f"{what} (Cut list) has the wrong totals.", h.id)


def _build_connectors(
    r: VerifyReport, project: Project, h: Harness, what: str, rows: list[list[str]]
) -> None:
    if not rows or rows[0] != _BUILD_CONNECTOR_HEADER:
        r.error("out_build", f"{what} (Connectors) has the wrong column headings.", h.id)
        return
    attached: dict[tuple[str, str], set[str]] = defaultdict(set)
    for w in h.wires:
        attached[(w.from_connector, w.from_pin)].add(w.id)
        attached[(w.to_connector, w.to_pin)].add(w.id)
    blocks: dict[str, list[list[str]]] = {}
    current: list[list[str]] | None = None
    for row in rows[1:]:
        if not any(row):
            current = None
            continue
        head = row[0].split("   ·   ")[0] if "   ·   " in row[0] else ""
        if head and not any(row[1:]):
            current = blocks.setdefault(head, [])
        elif current is not None:
            current.append(row)
    if set(blocks) != {c.id for c in h.connectors}:
        r.error("out_build", f"{what} (Connectors) has different connectors than the design.", h.id)
        return
    for c in h.connectors:
        pins = blocks[c.id]
        if [row[0] for row in pins] != [p.id for p in c.pins]:
            r.error("out_build", f"{what} (Connectors) lists different pins for {c.id}.", c.id)
            continue
        for row, p in zip(pins, c.pins, strict=True):
            want = attached.get((c.id, p.id), set())
            listed = set(filter(None, row[3].split("; "))) - {"(spare)", "(no wire)"}
            spare = not want and not p.interface_id and not p.signal
            marker = "(spare)" if spare else "(no wire)"
            if listed != want or (not want and row[3] != marker):
                r.error("out_build", f"Pin {c.id}.{p.id} lists the wrong wires in the build workbook.", c.id)  # fmt: skip
                break
            part = project.parts.get(p.contact_part or "")
            want_contact = p.contact_part or (_TO_FILL if want else "")
            want_tool = (part.tool or "") if part is not None else ""
            if (row[9], row[10]) != (want_contact, want_tool):
                r.error("out_build", f"Pin {c.id}.{p.id} shows the wrong contact or tool in the build workbook.", c.id)  # fmt: skip
                break


def _build_accessories(r: VerifyReport, h: Harness, what: str, rows: list[list[str]]) -> None:
    """The Accessories sheet: a tick column and the rows of accessories.csv; with none, the header
    and one line that says so."""
    if not rows or rows[0] != ["Done (x)", *_ACCESSORY_HEADER]:
        r.error("out_build", f"{what} (Accessories) has the wrong column headings.", h.id)
        return
    body = rows[1:]
    if not h.accessories:
        if len(body) != 1 or body[0][0] != _BUILD_NO_ACCESSORIES or any(body[0][1:]):
            r.error("out_build", f"{what} (Accessories) should say that none are entered.", h.id)
        return
    want = [
        [*row[:3], row[3] or _BUILD_HARNESS_TARGET, *row[4:]]
        for row in sorted(_accessory_rows(h), key=lambda row: str(row[0]))
    ]
    _compare_rows(r, "out_build", f"{what} (Accessories)", [row[1:] for row in rows], _ACCESSORY_HEADER,
                  want, (0,), h.id)  # fmt: skip
    if [row[1] for row in body] != [str(row[0]) for row in want]:
        r.error("out_build", f"{what} (Accessories) is not in ID order.", h.id)
    if any(row[0] for row in body):
        r.error("out_build", f"{what} has ticks in the Accessories sheet before anything was done.", h.id)  # fmt: skip


def _build_start(
    r: VerifyReport, project: Project, h: Harness, what: str, rows: list[list[str]]
) -> None:
    table = {row[0]: row for row in rows if len(row) >= 3 and row[2] in ("OK", "TO FIX", "NOTE")}
    want = _build_expected_checks(project, h)
    for label, open_n in want.items():
        row = table.get(label)
        if row is None or row[1] != str(open_n) or (row[2] == "OK") != (open_n == 0):
            r.error("out_build", f"{what} (Start here) shows a wrong count for '{label}'.", h.id)
            return
    ready = next((row[1] for row in rows if row and row[0] == "Ready to build"), None)
    blocking = sum(want[k] for k in list(want)[:4])
    names = sorted(n for n, c in project.config.items() if c.placeholder)  # worked out here
    want_ready = "no" if blocking else "yes"
    if want_ready == "yes" and names:
        want_ready = f"yes (values rest on placeholder configuration: {', '.join(names)})"
        listed = next((row[1] for row in rows if row and row[0] == "Placeholder files"), None)
        if listed != ", ".join(f"config/{n}.json" for n in names):
            r.error("out_build", f"{what} (Start here) does not list the placeholder files.", h.id)
    if ready != want_ready:
        r.error("out_build", f"{what} (Start here) shows the wrong 'Ready to build' answer.", h.id)


def _yaml_values(r: VerifyReport, h: Harness, text: str) -> None:
    """The values in the WireViz file: pins of each connector, gauge, colour and length of each
    wire, and the two ends of every connection."""
    section, cur = "", ""
    blocks: dict[str, dict[str, dict[str, str]]] = {"connectors": {}, "cables": {}}
    links: list[list[str]] = []
    for line in text.splitlines()[1:]:
        if line in ("connectors:", "cables:", "connections:"):
            section = line[:-1]
        elif section in blocks:
            head = re.fullmatch(r'  ("(?:[^"\\]|\\.)*"):', line)
            item = re.fullmatch(r"    (\w+): (.*)", line)
            if head:
                cur = json.loads(head[1])
                blocks[section][cur] = {}
            elif item and cur in blocks[section]:
                blocks[section][cur][item[1]] = item[2]
        elif section == "connections":
            if line.startswith("  - - "):
                links.append([line[6:]])
            elif line.startswith("    - ") and links:
                links[-1].append(line[6:])
    wrong: list[str] = []

    def q(s: str) -> str:
        return json.dumps(s, ensure_ascii=False)

    for c in h.connectors:
        got = blocks["connectors"].get(c.id, {})
        if got.get("pincount") != str(len(c.pins)):
            wrong.append(f"pin count of {c.id}")
        if got.get("pinlabels") != "[" + ", ".join(q(p.id) for p in c.pins) + "]":
            wrong.append(f"pin names of {c.id}")
        if got.get("type") != q(c.part_id):
            wrong.append(f"part of {c.id}")
    for w in h.wires:
        got = blocks["cables"].get(w.id, {})
        if got.get("gauge") != (None if w.gauge_awg is None else q(f"{w.gauge_awg} AWG")):
            wrong.append(f"gauge of {w.id}")
        if got.get("colors") != (f"[{q(w.colour)}]" if w.colour else None):
            wrong.append(f"colour of {w.id}")
        length = _length_of(h, w)
        shown = got.get("length")
        if length is None:
            if shown is not None:
                wrong.append(f"length of {w.id}")
        elif shown is None or not _same_number(shown, length):
            wrong.append(f"length of {w.id}")
    want = Counter(
        (q(w.from_connector), q(w.from_pin), q(w.id), q(w.to_connector), q(w.to_pin))
        for w in h.wires
    )
    got_links: Counter[tuple[str, ...]] = Counter()
    for link in links:
        m = [re.fullmatch(r'("(?:[^"\\]|\\.)*"): \[(.*)\]', x) for x in link]
        if len(link) == 3 and all(m):
            ends = [x for x in m if x is not None]
            got_links[(ends[0][1], ends[0][2], ends[1][1], ends[2][1], ends[2][2])] += 1
    if got_links != want:
        wrong.append("the connections")
    if wrong:
        r.error(
            "out_yaml",
            f"The WireViz file of {h.id} differs from the design: {', '.join(wrong[:3])}"
            + (f" and {len(wrong) - 3} more" if len(wrong) > 3 else "")
            + ".",
            h.id,
        )


_MATING_HEADER = [
    "Box connector", "Unit", "Part", "Gender", "Cable connector", "Cable part", "Cable gender",
    "Harness",
]  # fmt: skip
_TRACE_HEADER = ["Interface", "Name", "Type", "From", "To", "Harnesses", "Wires", "Routed"]
_FINDING_HEADER = [
    "Finding", "Rule", "Severity", "Object", "Statement", "Waived", "Justification", "Requirement",
]  # fmt: skip


def _mass_total(r: VerifyReport, project: Project, row: list[str]) -> None:
    """The TOTAL row of the system mass and length table."""
    if not project.harnesses:
        return
    hs = list(project.harnesses.values())
    mass, all_complete = 0.0, True
    known, unknown = 0.0, 0
    for h in hs:
        m, complete = _mass(project, h)
        mass += m
        lengths = [_length_of(h, w) for w in h.wires]
        known += sum(x for x in lengths if x is not None)
        unknown += sum(1 for x in lengths if x is None)
        all_complete = all_complete and complete
    all_complete = all_complete and unknown == 0
    margin = _margin(project)
    ok = (
        len(row) == 10
        and row[2] == str(sum(len(h.connectors) for h in hs))
        and _same_number(row[3], known)
        and row[4] == str(unknown)
        and _same_number(row[5], mass)
        and _same_number(row[6], None if margin is None else mass * margin)
        and _same_number(row[7], None if margin is None else mass * (1 + margin))
        and row[8] == ("yes" if all_complete else "no")
        and row[9] == ("" if all_complete else "totals count only what is known")
    )
    if not ok:
        r.error("out_mass", "The TOTAL row of the system mass table does not match the design.", "mass_length")  # fmt: skip


def _system_workbook(r: VerifyReport, project: Project, files: dict[str, bytes]) -> None:
    """The system workbook carries the same tables as the CSV files; the PDFs of the system
    diagrams carry the texts of their SVGs."""
    x = files.get("system/system.xlsx")
    if x is not None:
        sheets = _xlsx_sheets(x)
        for name, rel in (
            ("BOM", "bom.csv"), ("Mass and length", "mass_length.csv"),
            ("Mating matrix", "mating_matrix.csv"), ("Traceability", "traceability.csv"),
            ("Box pinouts", "box_pinouts.csv"), ("DRC findings", "drc_findings.csv"),
            ("Change log", "changelog.csv"),
        ):  # fmt: skip
            table = _table(files, f"system/{rel}")
            if table and sheets.get(name) != table:
                r.error("out_xlsx", f"The '{name}' sheet of system.xlsx differs from {rel}.", "system.xlsx")  # fmt: skip
    for name in ("block_diagram", "harness_overview"):
        svg, pdf = files.get(f"system/{name}.svg"), files.get(f"system/{name}.pdf")
        if svg is not None and pdf is not None:
            _pdf_matches_svgs(r, f"The PDF of the {name.replace('_', ' ')}", pdf, [svg], name)
            _unencodable(r, f"the PDF of the {name.replace('_', ' ')}", [svg], name)
