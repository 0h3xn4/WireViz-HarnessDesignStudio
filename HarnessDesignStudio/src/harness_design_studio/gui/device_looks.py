"""How a device card looks like the equipment it is: a pictogram in a coloured badge and a band on
the left edge (the kinds and their families are in `gui/device_kinds.py`).

Three cues say the same thing, so no one of them carries it alone: the **pictogram** (one per kind,
drawn here with QPainter paths in a 16 x 16 box, no image files), the **accent colour** of the family
(tokens `device.*`, in both themes) and the **shape** of the badge (square, circle, hexagon or
octagon by family). The words say it again in the tooltip, the inspector and the legend. A device the
table does not know keeps a plain outlined box in the muted colour, as before.

The canvas calls three functions and nothing else: `paint_header` (a card with all its details),
`paint_overview` (a box seen from far away, where the badge is drawn at a size that stays readable on
the screen) and `draw_badge` (the legend and the manual).
"""

import math
from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPaintEvent, QPen, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from harness_design_studio.gui import strings
from harness_design_studio.gui.device_kinds import GENERIC, OVERVIEW_TINT, Looks, sentence
from harness_design_studio.gui.theme import ThemeManager

BOX = 16.0  # a pictogram is drawn in a box of this many units on each side
STROKE = 1.5  # its line, in those units
BAND_W = 5.0  # the band on the left edge of a card
BADGE_PX = 18.0  # the badge of a box seen from far away, in screen pixels
BAND_PX = 5.0  # and its band
MIN_BOX_PX = 56.0  # a box narrower than this on the screen gets the band and no badge


class Colours(Protocol):
    """What the painters need of the theme: `ThemeManager.color`."""

    def color(self, token: str) -> QColor: ...


# ---- pictograms: one per kind, in a 16 x 16 box, the pen and brush already set ------------------


def _line(p: QPainter, x1: float, y1: float, x2: float, y2: float) -> None:
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _poly(p: QPainter, pts: list[tuple[float, float]]) -> None:
    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))


def _dot(p: QPainter, x: float, y: float, r: float) -> None:
    p.drawEllipse(QPointF(x, y), r, r)


def _computer(p: QPainter) -> None:  # a chip: a body with pins on every side
    p.drawRoundedRect(QRectF(3.5, 3.5, 9, 9), 1.2, 1.2)
    for v in (6, 8, 10):
        _line(p, v, 1.5, v, 3.5)
        _line(p, v, 12.5, v, 14.5)
        _line(p, 1.5, v, 3.5, v)
        _line(p, 12.5, v, 14.5, v)


def _interface_unit(p: QPainter) -> None:  # one input fanning out to three outputs
    p.drawRoundedRect(QRectF(1.5, 4, 5, 8), 1, 1)
    for y in (3.5, 8, 12.5):
        _line(p, 6.5, 8, 11.5, y)
        _dot(p, 13, y, 1.3)


def _battery(p: QPainter) -> None:  # a cell with its terminal, a plus and a minus
    p.drawRoundedRect(QRectF(1.5, 4.5, 11.5, 7), 1.2, 1.2)
    p.drawRect(QRectF(13, 6.5, 1.8, 3))
    _line(p, 3.6, 8, 6.6, 8)
    _line(p, 5.1, 6.5, 5.1, 9.5)
    _line(p, 8.8, 8, 10.8, 8)


def _solar_array(p: QPainter) -> None:  # a tilted panel of cells on a stem
    _poly(p, [(1.5, 10.5), (4.5, 3.5), (14.5, 3.5), (11.5, 10.5)])
    _line(p, 3, 7, 13, 7)
    _line(p, 7.8, 3.5, 4.8, 10.5)
    _line(p, 11.2, 3.5, 8.2, 10.5)
    _line(p, 6.5, 10.5, 6.5, 14.5)


def _power_unit(p: QPainter) -> None:  # one input, a bus and three outputs
    _line(p, 1.5, 8, 5, 8)
    _line(p, 5, 3, 5, 13)
    for y in (3, 8, 13):
        _line(p, 5, y, 11.5, y)
        p.drawRect(QRectF(11.5, y - 1.3, 2.6, 2.6))


def _reaction_wheel(p: QPainter) -> None:  # a rim, a hub and three spokes
    _dot(p, 8, 8, 6.3)
    _dot(p, 8, 8, 1.4)
    for k in range(3):
        a = math.radians(90 + k * 120)
        _line(
            p,
            8 + 1.4 * math.cos(a),
            8 + 1.4 * math.sin(a),
            8 + 6.3 * math.cos(a),
            8 + 6.3 * math.sin(a),
        )


def _magnetorquer(p: QPainter) -> None:  # a rod wound with a coil
    p.drawRect(QRectF(1.5, 6, 13, 4))
    for x in (3.5, 6.5, 9.5, 12.5):
        _line(p, x - 1, 3.5, x + 1, 12.5)


def _thruster(p: QPainter) -> None:  # a chamber, a bell and a plume
    p.drawRect(QRectF(5.5, 1.5, 5, 4))
    _poly(p, [(5.5, 5.5), (10.5, 5.5), (13, 10), (3, 10)])
    for x in (5.5, 8, 10.5):
        _line(p, x, 11.5, x, 14.5)


def _star(p: QPainter, cx: float, cy: float, r_out: float, r_in: float, n: int) -> None:
    pts: list[tuple[float, float]] = []
    for k in range(2 * n):
        r = r_out if k % 2 == 0 else r_in
        a = math.radians(-90 + k * 180 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    _poly(p, pts)


def _star_tracker(p: QPainter) -> None:  # a five-pointed star
    _star(p, 8, 8.5, 6.8, 2.8, 5)


def _sun_sensor(p: QPainter) -> None:  # the sun: a disc with rays
    _dot(p, 8, 8, 3)
    for k in range(8):
        a = math.radians(k * 45)
        _line(
            p,
            8 + 4.8 * math.cos(a),
            8 + 4.8 * math.sin(a),
            8 + 6.9 * math.cos(a),
            8 + 6.9 * math.sin(a),
        )


def _gyro(p: QPainter) -> None:  # three axes from one point
    _line(p, 8, 8, 14.5, 8)
    _line(p, 8, 8, 8, 1.5)
    _line(p, 8, 8, 3, 13)
    for x, y in ((14.5, 8), (8, 1.5), (3, 13)):
        _dot(p, x, y, 1.1)
    _dot(p, 8, 8, 1.1)


def _sensor(p: QPainter) -> None:  # a target
    _dot(p, 8, 8, 4.8)
    _dot(p, 8, 8, 1.1)
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        _line(p, 8 + dx * 4.8, 8 + dy * 4.8, 8 + dx * 7.2, 8 + dy * 7.2)


def _transceiver(p: QPainter) -> None:  # a radio box that sends waves
    p.drawRoundedRect(QRectF(2.5, 9, 11, 5.5), 1.2, 1.2)
    _line(p, 8, 9, 8, 6)
    _dot(p, 8, 5, 1)
    for r in (3.4, 6):
        rect = QRectF(8 - r, 5 - r, 2 * r, 2 * r)
        p.drawArc(rect, 35 * 16, 110 * 16)


def _antenna(p: QPainter) -> None:  # a dish on a stem
    p.drawArc(QRectF(2, -1, 12, 12), 190 * 16, 160 * 16)
    _line(p, 8, 11, 8, 14.5)
    _line(p, 5, 14.5, 11, 14.5)
    _line(p, 8, 9, 8, 4.5)
    _dot(p, 8, 4, 0.9)


def _payload(p: QPainter) -> None:  # a camera
    p.drawRoundedRect(QRectF(1.5, 4.5, 13, 9), 1.5, 1.5)
    _dot(p, 8, 9, 3)
    p.drawRect(QRectF(10.5, 2.5, 3, 2))


def _heater(p: QPainter) -> None:  # a plate with three rising curls of heat
    p.drawRect(QRectF(2, 11.5, 12, 3))
    for x in (4.5, 8, 11.5):
        path = QPainterPath(QPointF(x, 10))
        path.cubicTo(x - 2.2, 8, x + 2.2, 6, x, 4)
        p.drawPath(path)


def _pyro(p: QPainter) -> None:  # a spark
    _star(p, 8, 8, 7, 2.6, 8)


def _mechanism(p: QPainter) -> None:  # a gear
    _dot(p, 8, 8, 3.2)
    for k in range(8):
        a = math.radians(k * 45)
        _line(
            p,
            8 + 4.6 * math.cos(a),
            8 + 4.6 * math.sin(a),
            8 + 6.9 * math.cos(a),
            8 + 6.9 * math.sin(a),
        )
    _dot(p, 8, 8, 5)


def _ground_support(p: QPainter) -> None:  # a terminal with a prompt
    p.drawRoundedRect(QRectF(1.5, 2.5, 13, 8.5), 1.2, 1.2)
    _line(p, 8, 11, 8, 13.5)
    _line(p, 5, 13.5, 11, 13.5)
    _line(p, 4.2, 5, 6.4, 6.8)
    _line(p, 6.4, 6.8, 4.2, 8.6)
    _line(p, 8, 8.6, 10.8, 8.6)


def _device(p: QPainter) -> None:  # a plain equipment box
    p.drawRoundedRect(QRectF(2, 2.5, 12, 11), 1.8, 1.8)
    _line(p, 2, 6.2, 14, 6.2)


PICTOGRAMS: dict[str, Callable[[QPainter], None]] = {
    "computer": _computer,
    "interface_unit": _interface_unit,
    "battery": _battery,
    "solar_array": _solar_array,
    "power_unit": _power_unit,
    "reaction_wheel": _reaction_wheel,
    "magnetorquer": _magnetorquer,
    "thruster": _thruster,
    "star_tracker": _star_tracker,
    "sun_sensor": _sun_sensor,
    "gyro": _gyro,
    "sensor": _sensor,
    "transceiver": _transceiver,
    "antenna": _antenna,
    "payload": _payload,
    "heater": _heater,
    "pyro": _pyro,
    "mechanism": _mechanism,
    "ground_support": _ground_support,
    "device": _device,
}
FILLED = ("star_tracker", "pyro")  # drawn solid: a line drawing of a star is too thin to read


def draw_pictogram(p: QPainter, kind: str, rect: QRectF, ink: QColor) -> None:
    """The picture of a kind (a key of `PICTOGRAMS`; an unknown one draws the plain box) in the
    square `rect`, in `ink`."""
    draw = PICTOGRAMS.get(kind, _device)
    side = min(rect.width(), rect.height())
    scale = side / BOX
    p.save()
    p.translate(rect.center().x() - side / 2, rect.center().y() - side / 2)
    p.scale(scale, scale)
    p.setPen(
        QPen(ink, STROKE, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    )
    p.setBrush(QBrush(ink) if kind in FILLED else Qt.BrushStyle.NoBrush)
    draw(p)
    p.restore()


# ---- the badge: a shape by family, filled with the accent ----------------------------------------


def shape_path(shape: str, rect: QRectF) -> QPainterPath:
    """The outline of a badge in `rect`: `square` (rounded), `circle`, `hexagon` (points left and
    right) or `octagon`."""
    path = QPainterPath()
    cx, cy = rect.center().x(), rect.center().y()
    rx, ry = rect.width() / 2, rect.height() / 2
    if shape == "circle":
        path.addEllipse(rect)
    elif shape == "hexagon":
        pts = [
            (cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))
            for a in range(0, 360, 60)
        ]
        path.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
        path.closeSubpath()
    elif shape == "octagon":
        cut = 0.3
        dx, dy = rect.width() * cut, rect.height() * cut
        lx, t, r, b = rect.left(), rect.top(), rect.right(), rect.bottom()
        pts = [
            (lx + dx, t),
            (r - dx, t),
            (r, t + dy),
            (r, b - dy),
            (r - dx, b),
            (lx + dx, b),
            (lx, b - dy),
            (lx, t + dy),
        ]
        path.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
        path.closeSubpath()
    else:
        path.addRoundedRect(rect, rect.width() * 0.2, rect.height() * 0.2)
    return path


def blend(base: QColor, over: QColor, share: float) -> QColor:
    """`over` laid over `base` with `share` of it (0 to 1)."""
    out = QColor(base)
    out.setRgbF(
        base.redF() * (1 - share) + over.redF() * share,
        base.greenF() * (1 - share) + over.greenF() * share,
        base.blueF() * (1 - share) + over.blueF() * share,
    )
    return out


def accent_of(th: Colours, looks: Looks) -> QColor | None:
    """The accent of the device's family, or None for a device that is only a box."""
    token = looks.token
    return th.color(token) if token else None


def draw_badge(
    painter: QPainter, th: Colours, looks: Looks, rect: QRectF, ground: str = "surface"
) -> None:
    """The badge of a device in `rect`: the family's shape filled with its accent and the pictogram
    of the kind in the text colour of an accent fill; a plain device gets an outline and a muted
    pictogram. `ground` is the token of what lies behind (for the plain device's hairline)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    accent = accent_of(th, looks)
    inner = rect.adjusted(
        rect.width() * 0.17, rect.height() * 0.17, -rect.width() * 0.17, -rect.height() * 0.17
    )
    path = shape_path(looks.family.shape, rect.adjusted(0.5, 0.5, -0.5, -0.5))
    if accent is None:
        painter.setPen(QPen(th.color("text-muted"), 1.2))
        painter.setBrush(QBrush(th.color(ground)))
        painter.drawPath(path)
        draw_pictogram(painter, looks.kind.key, inner, th.color("text-muted"))
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(accent))
        painter.drawPath(path)
        draw_pictogram(painter, looks.kind.key, inner, th.color("accent.text"))
    painter.restore()


# ---- the card ---------------------------------------------------------------------------------


def paint_header(painter: QPainter, th: Colours, looks: Looks, body: QRectF, badge: QRectF) -> None:
    """The look of a card with all its details, over the header the canvas has drawn: a band down
    the left edge in the accent and the badge in `badge`. The header itself is not tinted, because
    the small muted text on it (tags, counts) is 4.5:1 on the plain header and would not be on a
    tinted one. A device that is only a box gets the badge outline and nothing else."""
    accent = accent_of(th, looks)
    if accent is not None:
        clip = QPainterPath()
        clip.addRoundedRect(body.adjusted(1, 1, -1, -1), 7, 7)
        painter.save()
        painter.setClipPath(clip, Qt.ClipOperation.IntersectClip)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(accent))
        painter.drawRect(QRectF(body.left(), body.top(), BAND_W + 1, body.height()))
        painter.restore()
    draw_badge(painter, th, looks, badge, ground="bg.hover")


def paint_overview(
    painter: QPainter, th: Colours, looks: Looks, width: float, height: float, lod: float
) -> float:
    """The look of a box seen from far away (the canvas has drawn the plain box): a faint tint of the
    accent, a band on the left edge about `BAND_PX` screen pixels wide and, if the box is wide
    enough, the badge about `BADGE_PX` pixels. Returns where the ID may start (item units)."""
    lod = max(lod, 0.01)
    accent = accent_of(th, looks)
    band = 0.0
    if accent is not None:
        band = min(width * 0.12, BAND_PX / lod)
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        tint = QColor(accent)
        tint.setAlphaF(OVERVIEW_TINT)
        painter.setBrush(QBrush(tint))
        painter.drawRect(QRectF(0, 0, width, height))
        painter.setBrush(QBrush(accent))
        painter.drawRect(QRectF(0, 0, band, height))
        painter.restore()
    if width * lod < MIN_BOX_PX:
        return max(8.0, min(band + 3 / lod, width * 0.2))
    side = min(BADGE_PX / lod, height * 0.8)
    pad = 3 / lod
    draw_badge(painter, th, looks, QRectF(band + pad, (height - side) / 2, side, side))
    return band + pad + side + 4 / lod


def plain(looks: Looks) -> bool:
    """True for a device the table could not place (the plain box)."""
    return looks.kind is GENERIC


# ---- the inspector's line: the badge and the words ----------------------------------------------


class BadgeView(QWidget):
    """A badge as a widget (it repaints when the theme changes)."""

    def __init__(self, theme: ThemeManager, looks: Looks, side: int = 28) -> None:
        super().__init__()
        self.theme, self.looks = theme, looks
        self.setFixedSize(side, side)
        self.setAccessibleName(looks.kind.label)
        theme.changed.connect(self.update)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        draw_badge(painter, self.theme, self.looks, QRectF(self.rect()), ground="bg")
        painter.end()


def looks_line(theme: ThemeManager, looks: Looks, name: str, unit_id: str) -> QWidget:
    """The badge of a device with `Looks like: Battery (from the name BAT1)` beside it, for the
    inspector; the tooltip says how to change it."""
    row = QWidget()
    row.setObjectName("unit-looks")
    row.setAccessibleName(strings.LOOKS_NAME)
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 4, 0, 4)
    lay.addWidget(BadgeView(theme, looks), 0, Qt.AlignmentFlag.AlignTop)
    text = QLabel(sentence(looks, name, unit_id))
    text.setObjectName("unit-looks-text")
    text.setWordWrap(True)
    text.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
    row.setToolTip(strings.LOOKS_HOW)
    lay.addWidget(text, 1)
    return row
