# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""How a device card looks like the equipment it is: a pictogram in a coloured badge and a band on
the left edge (the kinds and their families are in `gui/device_kinds.py`).

Three cues say the same thing, so no one of them carries it alone: the **pictogram** (one per kind,
drawn here with QPainter paths in a 16 x 16 box, no image files), the **accent colour** of the family
(tokens `device.*`, in both themes) and the **shape** of the badge (square, circle, hexagon or
octagon by family). The words say it again in the tooltip, the inspector and the legend. A device the
table does not know keeps a plain outlined box in the muted colour, as before.

The pictograms and the outlines are path data in `core/pictograms.py`, read here and by the written
block diagram (`core/outputs/looks.py`), so the window and the files cannot drift.

The canvas calls three functions and nothing else: `paint_header` (a card with all its details),
`paint_overview` (a box seen from far away, where the badge is drawn at a size that stays readable on
the screen) and `draw_badge` (the legend and the manual).
"""

from typing import Protocol

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from harness_design_studio.core import pictograms
from harness_design_studio.core.pictograms import FILLED, Path
from harness_design_studio.core.pictograms import PICTOGRAMS as PICTOGRAM_DATA
from harness_design_studio.gui import strings
from harness_design_studio.gui.device_kinds import GENERIC, OVERVIEW_TINT, Looks, sentence
from harness_design_studio.gui.theme import ThemeManager

BOX = pictograms.BOX  # a pictogram is drawn in a box of this many units on each side
STROKE = pictograms.STROKE  # its line, in those units
BAND_W = 5.0  # the band on the left edge of a card
BADGE_PX = 18.0  # the badge of a box seen from far away, in screen pixels
BAND_PX = 5.0  # and its band
MIN_BOX_PX = 56.0  # a box narrower than this on the screen gets the band and no badge


class Colours(Protocol):
    """What the painters need of the theme: `ThemeManager.color`."""

    def color(self, token: str) -> QColor: ...


# ---- pictograms: the path data of core/pictograms.py (the same the written diagram draws) ------


def qpath(path: Path) -> QPainterPath:
    """The path data of `core/pictograms.py` as a `QPainterPath`."""
    out = QPainterPath()
    for op, pts in path:
        if op == "M":
            out.moveTo(pts[0], pts[1])
        elif op == "L":
            out.lineTo(pts[0], pts[1])
        elif op == "C":
            out.cubicTo(pts[0], pts[1], pts[2], pts[3], pts[4], pts[5])
        else:
            out.closeSubpath()
    return out


def shape_pen(colour: str | None, width: float) -> QPen | Qt.PenStyle:
    """The line of a `Shape` of a written diagram (round ends and joins, as the SVG and the PDF
    write it), or no pen."""
    if not colour:
        return Qt.PenStyle.NoPen
    return QPen(
        QColor(colour), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )  # fmt: skip


PICTOGRAMS: dict[str, QPainterPath] = {key: qpath(path) for key, path in PICTOGRAM_DATA.items()}


def draw_pictogram(p: QPainter, kind: str, rect: QRectF, ink: QColor) -> None:
    """The picture of a kind (a key of `PICTOGRAMS`; an unknown one draws the plain box) in the
    square `rect`, in `ink`."""
    shape = PICTOGRAMS.get(kind, PICTOGRAMS[GENERIC.key])
    side = min(rect.width(), rect.height())
    scale = side / BOX
    p.save()
    p.translate(rect.center().x() - side / 2, rect.center().y() - side / 2)
    p.scale(scale, scale)
    p.setPen(
        QPen(ink, STROKE, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    )
    p.setBrush(QBrush(ink) if kind in FILLED else Qt.BrushStyle.NoBrush)
    p.drawPath(shape)
    p.restore()


# ---- the badge: a shape by family, filled with the accent ----------------------------------------


def shape_path(shape: str, rect: QRectF) -> QPainterPath:
    """The outline of a badge in `rect`: `square` (rounded), `circle`, `hexagon` (points left and
    right) or `octagon` (the outlines are `core/pictograms.py`'s)."""
    return qpath(pictograms.shape_path(shape, rect.x(), rect.y(), rect.width(), rect.height()))


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
