"""A tiny deterministic drawing model rendered to SVG and PDF (vector, no dependencies).

Units are millimetres, origin top-left, y down. All text uses one monospaced font (Courier in
PDF), so text widths are exact (every character is 0.6 em wide) and layout never guesses.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from harness_design_studio.core.pictograms import Path


def escape(s: str) -> str:
    """XML text escaping (not xml.sax.saxutils: that imports network modules at import time)."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


CHAR_EM = 0.6  # Courier advance width per em: a published constant of the font
SHEETS = {"A4": (297.0, 210.0), "A3": (420.0, 297.0)}  # landscape, mm


def text_width(s: str, size: float) -> float:
    return len(s) * size * CHAR_EM


def fit(s: str, width: float, size: float) -> str:
    """Shorten `s` with an ellipsis so it fits in `width` mm."""
    n = max(1, int(width / (size * CHAR_EM)))
    return s if len(s) <= n else s[: max(1, n - 1)] + "~"


def fit_size(s: str, width: float, size: float, floor: float) -> float:
    """The font size (at most `size`, at least `floor`) at which `s` fits in `width` mm. Used for
    IDs, which are shrunk and never cut."""
    if text_width(s, size) <= width:
        return size
    return max(floor, math.floor(width / (len(s) * CHAR_EM) * 100 - 1e-6) / 100)


@dataclass(frozen=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    width: float = 0.3
    dash: tuple[float, float] | None = None
    color: str = "#000000"


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float
    width: float = 0.3
    fill: str | None = None
    dash: tuple[float, float] | None = None
    color: str = "#000000"


@dataclass(frozen=True)
class Text:
    x: float
    y: float  # baseline
    s: str
    size: float = 2.8
    bold: bool = False
    anchor: str = "start"  # start | middle | end
    color: str = "#000000"
    ref: str = ""  # an optional label for the output check, written as data-ref in the SVG

    @property
    def left(self) -> float:
        w = text_width(self.s, self.size)
        return self.x - (w / 2 if self.anchor == "middle" else w if self.anchor == "end" else 0.0)


@dataclass(frozen=True)
class Curve:
    """An S-shaped curve from (x1, y1) to (x2, y2) that leaves and arrives horizontally (a wire)."""

    x1: float
    y1: float
    x2: float
    y2: float
    width: float = 0.3
    color: str = "#000000"


@dataclass(frozen=True)
class Shape:
    """A path of straight lines and cubic curves (`core/pictograms.py`), filled, stroked or both,
    in millimetres on the sheet: what a pictogram and a badge of the block diagram are. A stroke
    has round ends and joins. No text, so the output checks that read texts do not see it."""

    path: Path
    fill: str | None = None
    stroke: str | None = None
    width: float = 0.3


Item = Line | Rect | Text | Curve | Shape


@dataclass
class Sheet:
    width: float
    height: float
    items: list[Item] = field(default_factory=list)
    title: str = ""
    # In-memory only, never written to SVG or PDF: which items draw which design object, as
    # (kind, id) -> indexes into `items`. Kinds: "wire", "connector", "pin" (id "connector/pin")
    # and "shield". The editor's drawing preview uses it to link the picture and the tables.
    marks: dict[tuple[str, str], list[int]] = field(default_factory=dict, compare=False, repr=False)

    def add(self, *items: Item) -> None:
        self.items.extend(items)

    def mark(self, kind: str, ident: str, start: int) -> None:
        """Say that the items added since `start` (an earlier `len(self.items)`) draw this object."""
        if len(self.items) > start:
            self.marks.setdefault((kind, ident), []).extend(range(start, len(self.items)))


def item_bounds(it: Item) -> tuple[float, float, float, float]:
    """(left, top, right, bottom) in mm of what one item draws, with half its line width."""
    if isinstance(it, Text):
        return it.left, it.y - it.size, it.left + text_width(it.s, it.size), it.y + it.size * 0.25
    if isinstance(it, Rect):
        pad = it.width / 2
        return it.x - pad, it.y - pad, it.x + it.w + pad, it.y + it.h + pad
    if isinstance(it, Shape):
        xs = [v for _op, pts in it.path for v in pts[0::2]]
        ys = [v for _op, pts in it.path for v in pts[1::2]]
        pad = it.width / 2 if it.stroke else 0.0
        return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad
    pad = it.width / 2
    return (
        min(it.x1, it.x2) - pad,
        min(it.y1, it.y2) - pad,
        max(it.x1, it.x2) + pad,
        max(it.y1, it.y2) + pad,
    )


def _is_frame(it: Item, sheet: Sheet) -> bool:
    """The border `system.py` draws first: a rectangle 2 mm inside the sheet, with no fill."""
    return (
        isinstance(it, Rect)
        and it.fill is None
        and (it.x, it.y) == (2, 2)
        and abs(it.w - (sheet.width - 4)) < 1e-6
        and abs(it.h - (sheet.height - 4)) < 1e-6
    )


def fit_sheet(sheet: Sheet, margin_mm: float = 8.0) -> Sheet:
    """A copy of `sheet` cut down to its content: the width and the height end `margin_mm` after
    the last thing drawn (never larger than before), and the border, if the sheet has one, is
    redrawn to match. Nothing moves: every item keeps its place, so the picture is the same and
    only the empty paper right and below is gone. Used where a picture is made to be looked at
    (the editor's Export diagram), never for the files of the normal export, whose sheet sizes are
    part of what is written."""
    rest = [it for it in sheet.items if not _is_frame(it, sheet)]
    if not rest:
        return sheet
    right = max(item_bounds(it)[2] for it in rest) + margin_mm
    bottom = max(item_bounds(it)[3] for it in rest) + margin_mm
    width, height = min(sheet.width, right), min(sheet.height, bottom)
    items: list[Item] = []
    for it in sheet.items:
        if isinstance(it, Rect) and _is_frame(it, sheet):
            it = Rect(it.x, it.y, width - 4, height - 4, width=it.width, color=it.color)
        items.append(it)
    return Sheet(width, height, items, title=sheet.title, marks=dict(sheet.marks))


def _n(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _dash(d: tuple[float, float] | None) -> str:
    return f' stroke-dasharray="{_n(d[0])} {_n(d[1])}"' if d else ""


def path_data(path: Path) -> str:
    """The `d` of an SVG path: absolute commands, every number written by `_n` (three decimals at
    most, no exponent, no locale), so the same path gives the same text on every platform."""
    return " ".join(op if not pts else f"{op} " + " ".join(_n(v) for v in pts) for op, pts in path)


def _svg_shape(it: Shape) -> str:
    stroke = (
        f' stroke="{it.stroke}" stroke-width="{_n(it.width)}" stroke-linecap="round"'
        ' stroke-linejoin="round"'
        if it.stroke
        else ""
    )
    return f'<path d="{path_data(it.path)}" fill="{it.fill or "none"}"{stroke}/>'


def to_svg(sheet: Sheet, metadata: str) -> bytes:
    """One sheet as a standalone SVG. `metadata` is plain text (the stamp) stored in <desc>."""
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(sheet.width)}mm" height="{_n(sheet.height)}mm" '
        f'viewBox="0 0 {_n(sheet.width)} {_n(sheet.height)}" font-family="Courier New, Courier, monospace">',
        f"<title>{escape(sheet.title)}</title>",
        f"<desc>{escape(metadata)}</desc>",
        f'<rect x="0" y="0" width="{_n(sheet.width)}" height="{_n(sheet.height)}" fill="#ffffff"/>',
    ]
    for it in sheet.items:
        if isinstance(it, Line):
            out.append(
                f'<line x1="{_n(it.x1)}" y1="{_n(it.y1)}" x2="{_n(it.x2)}" y2="{_n(it.y2)}" '
                f'stroke="{it.color}" stroke-width="{_n(it.width)}"{_dash(it.dash)}/>'
            )
        elif isinstance(it, Curve):
            xm = (it.x1 + it.x2) / 2
            out.append(
                f'<path d="M {_n(it.x1)} {_n(it.y1)} C {_n(xm)} {_n(it.y1)} {_n(xm)} {_n(it.y2)} '
                f'{_n(it.x2)} {_n(it.y2)}" fill="none" stroke="{it.color}" stroke-width="{_n(it.width)}"/>'
            )
        elif isinstance(it, Shape):
            out.append(_svg_shape(it))
        elif isinstance(it, Rect):
            out.append(
                f'<rect x="{_n(it.x)}" y="{_n(it.y)}" width="{_n(it.w)}" height="{_n(it.h)}" '
                f'fill="{it.fill or "none"}" stroke="{it.color}" stroke-width="{_n(it.width)}"{_dash(it.dash)}/>'
            )
        else:
            weight = ' font-weight="bold"' if it.bold else ""
            ref = f' data-ref="{escape(it.ref).replace(chr(34), "&quot;")}"' if it.ref else ""
            out.append(
                f'<text x="{_n(it.x)}" y="{_n(it.y)}" font-size="{_n(it.size)}"{weight} '
                f'text-anchor="{it.anchor}" fill="{it.color}"{ref}>{escape(it.s)}</text>'
            )
    out.append("</svg>")
    return ("\n".join(out) + "\n").encode()


# ---- PDF -------------------------------------------------------------------------------------------

_PT = 72.0 / 25.4


def _rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return " ".join(_n(int(h[i : i + 2], 16) / 255) for i in (0, 2, 4))


def _pdf_text(s: str) -> bytes:
    raw = s.encode("cp1252", "replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


_PDF_OPS = {"M": "m", "L": "l", "C": "c", "Z": "h"}


def _pdf_shape(it: Shape, h: float, pt: Callable[[float], str]) -> bytes:
    colours = (f"{_rgb(it.stroke)} RG " if it.stroke else "") + (
        f"{_rgb(it.fill)} rg " if it.fill else ""
    )
    line = f"{pt(it.width)} w 1 J 1 j [] 0 d " if it.stroke else ""
    body = " ".join(
        " ".join(pt(v) if k % 2 == 0 else pt(h - v) for k, v in enumerate(pts))
        + (" " if pts else "")
        + _PDF_OPS[op]
        for op, pts in it.path
    )
    paint = "B" if it.fill and it.stroke else "f" if it.fill else "S"
    return f"q {colours}{line}{body} {paint} Q".encode()


def _page_stream(sheet: Sheet) -> bytes:
    h = sheet.height
    ops: list[bytes] = []

    def pt(v: float) -> str:
        return _n(v * _PT)

    for it in sheet.items:
        if isinstance(it, Line):
            ops.append(f"q {_rgb(it.color)} RG {pt(it.width)} w".encode())
            ops.append(
                (f"[{pt(it.dash[0])} {pt(it.dash[1])}] 0 d" if it.dash else "[] 0 d").encode()
            )
            ops.append(f"{pt(it.x1)} {pt(h - it.y1)} m {pt(it.x2)} {pt(h - it.y2)} l S Q".encode())
        elif isinstance(it, Curve):
            xm = (it.x1 + it.x2) / 2
            ops.append(f"q {_rgb(it.color)} RG {pt(it.width)} w [] 0 d".encode())
            ops.append(
                f"{pt(it.x1)} {pt(h - it.y1)} m {pt(xm)} {pt(h - it.y1)} {pt(xm)} {pt(h - it.y2)} "
                f"{pt(it.x2)} {pt(h - it.y2)} c S Q".encode()
            )
        elif isinstance(it, Shape):
            ops.append(_pdf_shape(it, h, pt))
        elif isinstance(it, Rect):
            fill = f"{_rgb(it.fill)} rg " if it.fill else ""
            paint = "B" if it.fill else "S"
            ops.append(f"q {_rgb(it.color)} RG {fill}{pt(it.width)} w".encode())
            ops.append(
                (f"[{pt(it.dash[0])} {pt(it.dash[1])}] 0 d" if it.dash else "[] 0 d").encode()
            )
            ops.append(
                f"{pt(it.x)} {pt(h - it.y - it.h)} {pt(it.w)} {pt(it.h)} re {paint} Q".encode()
            )
        else:
            font = "F2" if it.bold else "F1"
            ops.append(
                f"BT /{font} {_n(it.size * _PT)} Tf {_rgb(it.color)} rg {pt(it.left)} {pt(h - it.y)} Td (".encode()
                + _pdf_text(it.s)
                + b") Tj ET"
            )
    return b"\n".join(ops) + b"\n"


def to_pdf(sheets: list[Sheet], title: str, metadata: str) -> bytes:
    """A multi-page vector PDF. No dates, IDs or compression, so equal input gives equal bytes."""
    objs: list[bytes] = []

    def add(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    catalog = add(b"")  # 1
    pages_obj = add(b"")  # 2
    f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    f2 = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>"
    )
    info = add(
        b"<< /Title ("
        + _pdf_text(title)
        + b") /Subject ("
        + _pdf_text(metadata)
        + b") /Producer (harness-design-studio) >>"
    )
    kids: list[int] = []
    for sheet in sheets:
        stream = _page_stream(sheet)
        content = add(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream"
        )
        w, h = _n(sheet.width * _PT), _n(sheet.height * _PT)
        page = add(
            f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {w} {h}] /Contents {content} 0 R "
            f"/Resources << /Font << /F1 {f1} 0 R /F2 {f2} 0 R >> >> >>".encode()
        )
        kids.append(page)
    objs[catalog - 1] = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode()
    objs[pages_obj - 1] = (
        f"<< /Type /Pages /Count {len(kids)} /Kids [{' '.join(f'{k} 0 R' for k in kids)}] >>".encode()
    )
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root {catalog} 0 R /Info {info} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
