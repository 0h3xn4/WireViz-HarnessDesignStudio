"""The application icon (the logo of docs/img/logo.svg), painted in code.

It is drawn with QPainter rather than loaded from the SVG because the packaged program ships
without the Qt SVG module. Keep the shapes in step with docs/img/logo.svg and
packaging/ubuntu/harness-design-studio.svg.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from harness_design_studio.gui.theme.tokens import BRAND

SIZES = (16, 24, 32, 48, 64, 128, 256)
PURPLE = BRAND["purple"]
AMBER = BRAND["amber"]
WHITE = BRAND["white"]


def _pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 64.0, size / 64.0)  # the logo is drawn on a 64 x 64 grid
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(PURPLE))
    p.drawRoundedRect(QRectF(0, 0, 64, 64), 10, 10)
    p.setBrush(QColor(WHITE))
    p.drawRoundedRect(QRectF(8, 12, 16, 12), 2, 2)
    p.drawRoundedRect(QRectF(40, 40, 16, 12), 2, 2)
    p.setBrush(Qt.BrushStyle.NoBrush)
    wire = QPainterPath(QPointF(24, 18))
    wire.cubicTo(QPointF(36, 18), QPointF(28, 46), QPointF(40, 46))
    p.setPen(QPen(QColor(WHITE), 3))
    p.drawPath(wire)
    core = QPainterPath(QPointF(24, 22))
    core.cubicTo(QPointF(32, 22), QPointF(32, 42), QPointF(40, 42))
    pen = QPen(QColor(AMBER), 2)
    pen.setDashPattern([2.0, 1.0])  # SVG "4 2" in units of the pen width
    p.setPen(pen)
    p.drawPath(core)
    p.end()
    return pm


def app_icon() -> QIcon:
    """The logo at 16 to 256 pixels (needs a QGuiApplication)."""
    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(_pixmap(size))
    return icon
