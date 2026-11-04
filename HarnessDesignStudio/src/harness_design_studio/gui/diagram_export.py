"""Export diagram: the system block diagram as SVG, PDF and PNG, without a project folder.

    sheet = diagram_sheet(project)            # None while the project has no device to draw
    written = write_diagram(project, Path("/tmp/flatsat"))   # flatsat.svg, flatsat.pdf, flatsat.png

The three files come from one `Sheet` (`core.outputs.system.block_diagram`): the SVG and the PDF are
the vector files `core.outputs.canvas` writes for the outputs folder, the PNG is painted from the
same sheet with QPainter (the packaged program leaves out QtSvg, see `gui/icons.py`). Nothing here
needs a harness, a check, a verify pass or resolved placeholders, and nothing is written into the
project: it is a picture of the devices and the connections as they stand.
"""

import re
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPainterPath, QPen

from harness_design_studio.core.io.fs import atomic_write_bytes
from harness_design_studio.core.model import Project
from harness_design_studio.core.outputs import system
from harness_design_studio.core.outputs.canvas import (
    Curve,
    Line,
    Rect,
    Sheet,
    Text,
    fit_sheet,
    to_pdf,
    to_svg,
)
from harness_design_studio.core.outputs.stamp import Stamp, stamp_of
from harness_design_studio.gui.theme.tokens import LIGHT, OVERVIEW_FONT_PX

SUFFIXES = (".svg", ".pdf", ".png")
PX_PER_MM = 6.0  # about 150 dpi, at least
MIN_LONG_SIDE_PX = 2000  # a small diagram is drawn bigger so that it is still sharp on a slide
MARGIN_MM = 8.0  # the paper left round the content
MAX_SIDE_PX = 9000  # a big diagram is drawn smaller rather than not at all
PAPER = LIGHT["paper"]  # the sheet is white whatever the theme


def diagram_sheet(project: Project, stamp: Stamp | None = None) -> Sheet | None:
    """The block diagram of the project as it stands, or None when there is nothing to draw (no
    device). Interfaces and connections between two connectors are drawn; a project with only
    devices is drawn as boxes."""
    if not project.units:
        return None
    return fit_sheet(system.block_diagram(project, stamp or stamp_of(project)), MARGIN_MM)


def safe_stem(name: str) -> str:
    """A file name stem from a project name: letters, digits, dash and underscore."""
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return stem or "diagram"


def suggested_name(project: Project) -> str:
    return f"{safe_stem(project.meta.name)}_block_diagram.svg"


def stem_of(path: str | Path) -> Path:
    """The path without .svg, .pdf or .png (any other ending belongs to the name)."""
    p = Path(path)
    return p.with_suffix("") if p.suffix.lower() in SUFFIXES else p


def _pen(color: str, width: float, dash: tuple[float, float] | None) -> QPen:
    pen = QPen(QColor(color), width)
    if dash:
        pen.setDashPattern([dash[0] / max(width, 0.1), dash[1] / max(width, 0.1)])
    return pen


def render_png(sheet: Sheet) -> bytes:
    """The sheet painted on white paper, as PNG bytes."""
    long_side = max(sheet.width, sheet.height)
    scale = min(max(PX_PER_MM, MIN_LONG_SIDE_PX / long_side), 12.0, MAX_SIDE_PX / long_side)
    image = QImage(
        max(1, round(sheet.width * scale)), max(1, round(sheet.height * scale)),
        QImage.Format.Format_RGB32,
    )  # fmt: skip
    image.fill(QColor(PAPER))
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(scale, scale)
        base = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        for it in sheet.items:
            if isinstance(it, Line):
                painter.setPen(_pen(it.color, it.width, it.dash))
                painter.drawLine(QPointF(it.x1, it.y1), QPointF(it.x2, it.y2))
            elif isinstance(it, Curve):
                painter.setPen(_pen(it.color, it.width, None))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                path = QPainterPath(QPointF(it.x1, it.y1))
                xm = (it.x1 + it.x2) / 2
                path.cubicTo(QPointF(xm, it.y1), QPointF(xm, it.y2), QPointF(it.x2, it.y2))
                painter.drawPath(path)
            elif isinstance(it, Rect):
                painter.setPen(_pen(it.color, it.width, it.dash))
                painter.setBrush(QColor(it.fill) if it.fill else Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(it.x, it.y, it.w, it.h))
            elif isinstance(it, Text):
                font = QFont(base)  # one size; the painter is scaled to the text size
                font.setPixelSize(OVERVIEW_FONT_PX)
                font.setBold(it.bold)
                painter.save()
                painter.translate(it.left, it.y)
                painter.scale(it.size / OVERVIEW_FONT_PX, it.size / OVERVIEW_FONT_PX)
                painter.setFont(font)
                painter.setPen(QColor(it.color))
                painter.drawText(QPointF(0, 0), it.s)
                painter.restore()
    finally:
        painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")  # type: ignore[call-overload]  # (the stubs ask for bytes, Qt takes str)
    buffer.close()
    return bytes(data.data())


def diagram_files(sheet: Sheet, metadata: str) -> dict[str, bytes]:
    """suffix -> bytes of the three files."""
    return {
        ".svg": to_svg(sheet, metadata),
        ".pdf": to_pdf([sheet], sheet.title, metadata),
        ".png": render_png(sheet),
    }


def write_diagram(project: Project, target: str | Path) -> list[Path]:
    """Write the block diagram as `<stem>.svg`, `.pdf` and `.png` (`target` may carry one of the
    three endings). Returns the files written; an empty list while there is nothing to draw. A
    file that exists is replaced, with no backup copy beside it."""
    stamp = stamp_of(project)
    sheet = diagram_sheet(project, stamp)
    if sheet is None:
        return []
    stem = stem_of(target)
    written: list[Path] = []
    for suffix, data in diagram_files(sheet, stamp.line).items():
        path = stem.with_name(stem.name + suffix)
        atomic_write_bytes(path, data, backup=False, durable=False)
        written.append(path)
    return written
