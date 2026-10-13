"""Pictograms for the diagram: what a link carries and what a connector looks like.

Meaning must be readable at a glance, so it is drawn, not spelled: every kind of link has its own
small picture (a bolt for power, a wave for an analog signal, a bus for CAN, ...), and every family
of connector has its own outline (D-shaped, circular, RJ45, coax) with its pin dots.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF

from harness_design_studio.gui.tokens import style_category

LINK_GLYPH_W = 18.0
LINK_GLYPH_H = 14.0


def _line(p: QPainter, x1: float, y1: float, x2: float, y2: float) -> None:
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _poly(p: QPainter, pts: list[tuple[float, float]]) -> None:
    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))


def _path(p: QPainter, pts: list[tuple[float, float]]) -> None:
    path = QPainterPath(QPointF(*pts[0]))
    for x, y in pts[1:]:
        path.lineTo(x, y)
    p.drawPath(path)


# Each picture is drawn in a 18 x 14 box with the pen and brush already set.
def _bolt(p: QPainter) -> None:
    _poly(p, [(10, 0), (3, 8), (8, 8), (6, 14), (15, 5), (10, 5), (13, 0)])


def _ground(p: QPainter) -> None:
    _line(p, 9, 0, 9, 7)
    _line(p, 2, 7, 16, 7)
    _line(p, 5, 10, 13, 10)
    _line(p, 7.5, 13, 10.5, 13)


def _heater(p: QPainter) -> None:
    _path(p, [(0, 7), (3, 7), (5, 1), (8, 13), (11, 1), (14, 13), (15, 7), (18, 7)])


def _can(p: QPainter) -> None:  # a bus with a terminator at each end
    _line(p, 1, 4, 17, 4)
    _line(p, 1, 10, 17, 10)
    _line(p, 1, 2, 1, 12)
    _line(p, 17, 2, 17, 12)


def _diff(p: QPainter) -> None:  # a differential pair: two lines, opposite arrows
    _line(p, 1, 4, 16, 4)
    _line(p, 1, 10, 16, 10)
    _poly(p, [(17, 4), (12, 1), (12, 7)])
    _poly(p, [(1, 10), (6, 7), (6, 13)])


def _lvds(p: QPainter) -> None:  # a differential pair closed by a termination resistor
    _line(p, 1, 3, 17, 3)
    _line(p, 1, 11, 17, 11)
    _line(p, 12, 3, 12, 4.5)
    p.drawRect(QRectF(10.5, 4.5, 3, 5))
    _line(p, 12, 9.5, 12, 11)


def _multidrop(p: QPainter) -> None:  # a bus with three drops
    _line(p, 1, 4, 17, 4)
    for x in (3, 9, 15):
        _line(p, x, 4, x, 12)
        p.drawEllipse(QPointF(x, 12), 1.6, 1.6)


def _stubs(p: QPainter) -> None:  # a dual bus with stubs
    _line(p, 1, 3, 17, 3)
    _line(p, 1, 6, 17, 6)
    for x in (5, 13):
        _line(p, x, 6, x, 13)


def _network(p: QPainter) -> None:  # a node linked to three more
    _line(p, 9, 7, 2, 2)
    _line(p, 9, 7, 16, 2)
    _line(p, 9, 7, 9, 13)
    p.drawEllipse(QPointF(9, 7), 3, 3)
    for x, y in ((2, 2), (16, 2), (9, 13)):
        p.drawRect(QRectF(x - 1.5, y - 1.5, 3, 3))


def _ethernet(p: QPainter) -> None:  # two boxes joined, the plug shape of RJ45
    p.drawRect(QRectF(1, 3, 6, 8))
    p.drawRect(QRectF(11, 3, 6, 8))
    _line(p, 7, 7, 11, 7)


def _clock(p: QPainter) -> None:  # clock and data
    _path(p, [(1, 5), (4, 5), (4, 1), (8, 1), (8, 5), (11, 5), (11, 1), (15, 1), (15, 5), (17, 5)])
    _path(p, [(1, 13), (6, 13), (6, 9), (13, 9), (13, 13), (17, 13)])


def _sine(p: QPainter) -> None:
    path = QPainterPath(QPointF(0, 7))
    path.cubicTo(3, -2, 6, -2, 9, 7)
    path.cubicTo(12, 16, 15, 16, 18, 7)
    p.drawPath(path)


def _square(p: QPainter) -> None:
    _path(p, [(0, 11), (4, 11), (4, 3), (9, 3), (9, 11), (14, 11), (14, 3), (18, 3)])


def _pyro(p: QPainter) -> None:  # a spark
    _poly(
        p,
        [
            (9, 0),
            (11, 5),
            (17, 3),
            (13, 8),
            (17, 13),
            (11, 11),
            (9, 14),
            (7, 11),
            (1, 13),
            (5, 8),
            (1, 3),
            (7, 5),
        ],
    )


def _thermo(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(7, 0.5, 4, 9), 2, 2)
    p.drawEllipse(QPointF(9, 11), 3, 3)


def _coax(p: QPainter) -> None:  # a ring around a core, with waves
    p.drawEllipse(QPointF(9, 7), 6, 6)
    p.setBrush(p.pen().color())
    p.drawEllipse(QPointF(9, 7), 2, 2)


_GLYPHS = {
    "power_primary": _bolt,
    "power_secondary": _bolt,
    "ground": _ground,
    "heater": _heater,
    "can": _can,
    "rs422": _diff,
    "rs485": _multidrop,
    "mil1553b": _stubs,
    "spacewire": _network,
    "ethernet": _ethernet,
    "lvds": _lvds,
    "i2c": _clock,
    "analog": _sine,
    "discrete": _square,
    "pyro": _pyro,
    "thermistor": _thermo,
    "rf_coax": _coax,
}
_BY_CATEGORY = {
    "power": _bolt,
    "ground": _ground,
    "data": _can,
    "analog": _sine,
    "discrete": _square,
    "pyro": _pyro,
    "rf": _coax,
}


def draw_link_glyph(
    p: QPainter, x: float, y: float, type_id: str, category: str, color: QColor, scale: float = 1.0
) -> None:
    """The picture of a kind of link, its top left corner at (x, y)."""
    draw = _GLYPHS.get(type_id) or _BY_CATEGORY.get(style_category(category), _can)
    p.save()
    p.translate(x, y)
    p.scale(scale, scale)
    p.setPen(
        QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    )
    p.setBrush(QBrush(color) if draw in (_bolt, _pyro) else Qt.BrushStyle.NoBrush)
    draw(p)
    p.restore()


# ---- units: the picture on a card (what kind of equipment it is) --------------------------------
# Each is drawn in the same 18 x 14 box as the link pictures, from the key `describe.unit_glyph` gives.
def _u_computer(p: QPainter) -> None:  # a chip: body with pins on every side
    p.drawRoundedRect(QRectF(3.5, 2.5, 11, 9), 1.5, 1.5)
    for x in (6.5, 9, 11.5):
        _line(p, x, 0.5, x, 2.5)
        _line(p, x, 11.5, x, 13.5)
    for y in (5, 9):
        _line(p, 1.5, y, 3.5, y)
        _line(p, 14.5, y, 16.5, y)


def _u_power(p: QPainter) -> None:  # a battery with its plus
    p.drawRoundedRect(QRectF(1, 3, 13, 8), 1.5, 1.5)
    p.drawRect(QRectF(14, 5.5, 2.5, 3))
    _line(p, 4.5, 7, 8.5, 7)
    _line(p, 6.5, 5, 6.5, 9)


def _u_comms(p: QPainter) -> None:  # an antenna with waves
    _line(p, 9, 6, 9, 13.5)
    p.drawEllipse(QPointF(9, 5), 1.2, 1.2)
    for r in (3.5, 6.5):
        rect = QRectF(9 - r, 5 - r, 2 * r, 2 * r)
        p.drawArc(rect, 40 * 16, 100 * 16)
        p.drawArc(rect, 140 * 16, 100 * 16)


def _u_thermal(p: QPainter) -> None:  # a thermometer
    p.drawRoundedRect(QRectF(7, 0.5, 4, 9), 2, 2)
    p.drawEllipse(QPointF(9, 11), 3, 3)
    _line(p, 9, 4, 9, 9)


def _u_payload(p: QPainter) -> None:  # a camera
    p.drawRoundedRect(QRectF(1, 3, 16, 10), 2, 2)
    p.drawEllipse(QPointF(9, 8), 3, 3)
    _line(p, 5, 1.5, 8, 1.5)


def _u_mechanism(p: QPainter) -> None:  # a gear
    p.drawEllipse(QPointF(9, 7), 3, 3)
    for k in range(8):
        a = math.radians(k * 45)
        _line(
            p,
            9 + 4.2 * math.cos(a),
            7 + 4.2 * math.sin(a),
            9 + 6.4 * math.cos(a),
            7 + 6.4 * math.sin(a),
        )


def _u_sensor(p: QPainter) -> None:  # a target
    p.drawEllipse(QPointF(9, 7), 4.5, 4.5)
    p.drawEllipse(QPointF(9, 7), 1, 1)
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        _line(p, 9 + dx * 4.5, 7 + dy * 4.5, 9 + dx * 6.8, 7 + dy * 6.8)


def _u_actuator(p: QPainter) -> None:  # a wheel with spokes
    p.drawEllipse(QPointF(9, 7), 6.2, 6.2)
    p.drawEllipse(QPointF(9, 7), 1.2, 1.2)
    for k in range(3):
        a = math.radians(90 + k * 120)
        _line(
            p,
            9 + 1.2 * math.cos(a),
            7 + 1.2 * math.sin(a),
            9 + 6.2 * math.cos(a),
            7 + 6.2 * math.sin(a),
        )


def _u_egse(p: QPainter) -> None:  # a plug
    p.drawRoundedRect(QRectF(5, 5, 8, 5), 1.5, 1.5)
    _line(p, 7, 1, 7, 5)
    _line(p, 11, 1, 11, 5)
    _line(p, 9, 10, 9, 13.5)


def _u_unit(p: QPainter) -> None:  # an equipment box
    p.drawRoundedRect(QRectF(2, 2, 14, 10), 2, 2)
    _line(p, 2, 5.5, 16, 5.5)


_UNIT_GLYPHS = {
    "computer": _u_computer,
    "power": _u_power,
    "comms": _u_comms,
    "thermal": _u_thermal,
    "payload": _u_payload,
    "mechanism": _u_mechanism,
    "pyro": _pyro,
    "sensor": _u_sensor,
    "actuator": _u_actuator,
    "egse": _u_egse,
    "unit": _u_unit,
}


def draw_unit_glyph(
    p: QPainter, x: float, y: float, kind: str, color: QColor, scale: float = 1.0
) -> None:
    """The picture of a kind of equipment (a key of `describe.UNIT_GLYPHS`), its top left corner at
    (x, y) in an 18 x 14 box; an unknown key draws the plain equipment box."""
    draw = _UNIT_GLYPHS.get(kind, _u_unit)
    p.save()
    p.translate(x, y)
    p.scale(scale, scale)
    p.setPen(
        QPen(color, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    )
    p.setBrush(QBrush(color) if draw is _pyro else Qt.BrushStyle.NoBrush)
    draw(p)
    p.restore()


# ---- connectors ------------------------------------------------------------------------------
CONNECTOR_W = 46.0
CONNECTOR_H = 22.0


def _dots(p: QPainter, rect: QRectF, pins: int, filled: bool, ink: QColor, rows: int = 2) -> None:
    """Pin dots in rows inside `rect`: filled for a male (pins), hollow for a female (sockets)."""
    pins = max(pins, 1)
    shown = min(pins, 40 if rows == 2 else 8)
    per = [(shown + 1) // 2, shown // 2] if rows == 2 else [shown]
    r = 1.1 if per[0] <= 9 else 0.85
    p.save()
    p.setBrush(ink if filled else QColor(0, 0, 0, 0))
    p.setPen(QPen(ink, 0.8))
    for k, count in enumerate(per):
        if count == 0:
            continue
        y = rect.top() + rect.height() * (k + 0.5) / len(per)
        for j in range(count):
            p.drawEllipse(QPointF(rect.left() + rect.width() * (j + 0.5) / count, y), r, r)
    p.restore()


def draw_connector(
    p: QPainter,
    x: float,
    y: float,
    family: str,
    pins: int,
    gender: str,
    color: QColor,
    bg: QColor,
    scale: float = 1.0,
) -> None:
    """A connector's outline (30 x 16), its top left corner at (x, y): the family shows in the
    shape, the pin count in the dots, the gender in the whole look: a male (pins) is solid, a female
    (sockets) an outline, a gender that is not set a dashed outline."""
    p.save()
    p.translate(x, y)
    p.scale(scale, scale)
    p.setPen(
        QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    )
    male = gender == "male"
    if gender not in (
        "male",
        "female",
    ):  # gender not set: a dashed outline, neither solid nor plain
        p.setPen(
            QPen(
                color, 1.6, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
            )
        )
    p.setBrush(QBrush(color if male else bg))  # a male is drawn solid, a female as an outline
    detail = bg if male else color  # what is drawn inside the shell
    if family in ("dsub", "microd"):
        # a flange with two screw holes, and in front of it the shell with its two rows of pins:
        # the D-sub shell is a tapered D, the Micro-D shell a small rounded block
        w = min(38.0, 26.0 + 0.5 * pins) if family == "dsub" else min(36.0, 18.0 + 0.6 * pins)
        x0 = (CONNECTOR_W - w) / 2
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(QRectF(x0 - 5, 3, w + 10, 16), 3, 3)  # the flange, never filled
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(color, 1.0))
        p.drawEllipse(QPointF(x0 - 2, 11), 1.3, 1.3)  # the screw holes
        p.drawEllipse(QPointF(x0 + w + 2, 11), 1.3, 1.3)
        p.setPen(
            QPen(
                color,
                1.6,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        p.setBrush(QBrush(color if male else bg))
        if family == "dsub":
            _poly(p, [(x0, 5), (x0 + w, 5), (x0 + w - 4.5, 17.5), (x0 + 4.5, 17.5)])
            _dots(p, QRectF(x0 + 7, 7.4, w - 14, 8), pins, male, detail)
        else:
            p.drawRoundedRect(QRectF(x0, 5, w, 12.5), 2.5, 2.5)
            p.setPen(QPen(detail, 0.7))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(x0 + 2.2, 7, w - 4.4, 8.5), 1.5, 1.5)
            _dots(p, QRectF(x0 + 4, 8.2, w - 8, 6.2), pins, male, detail)
    elif family == "circular":
        p.translate(3, 3)
        p.translate(5, 0)  # a round shell with a key and pins on the ring
        p.drawEllipse(QPointF(15, 8), 7.2, 7.2)
        p.setPen(QPen(color, 1.6))
        _line(p, 15, 0.8, 15, 3)  # the key
        p.setPen(QPen(detail, 1.0))
        p.setBrush(detail if male else QColor(0, 0, 0, 0))
        for k in range(min(max(pins, 3), 8)):
            import math

            a = 2 * math.pi * k / min(max(pins, 3), 8)
            p.drawEllipse(QPointF(15 + 4 * math.sin(a), 8 - 4 * math.cos(a)), 1.0, 1.0)
        p.setPen(QPen(color, 1.6))
        _line(p, 3, 8, 7.8, 8)  # a coupling nut either side
        _line(p, 22.2, 8, 27, 8)
    elif family == "rj45":
        p.translate(3, 3)
        p.translate(5, 0)  # the plug: a box with a latch and a row of contacts
        p.drawRect(QRectF(7, 3, 16, 12))
        p.drawRect(QRectF(11, 0.8, 8, 2.2))
        p.setPen(QPen(detail, 1.0))
        for k in range(8):
            _line(p, 9 + k * 1.7 + 0.5, 6, 9 + k * 1.7 + 0.5, 12)
        p.setPen(QPen(color, 1.6))
        _line(p, 1, 9, 7, 9)
        _line(p, 23, 9, 29, 9)
    elif family == "coax":
        p.translate(3, 3)
        p.translate(5, 0)  # concentric rings, a solid centre pin for a plug
        p.drawEllipse(QPointF(15, 8), 7.2, 7.2)
        p.setPen(QPen(detail, 1.0))
        p.setBrush(detail if male else QColor(0, 0, 0, 0))
        p.drawEllipse(QPointF(15, 8), 2.6, 2.6)
        p.setPen(QPen(color, 1.6))
        _line(p, 1, 8, 7.8, 8)
        _line(p, 22.2, 8, 29, 8)
    else:  # an unknown family: a plain box with its dots
        p.translate(3, 3)
        p.translate(5, 0)
        p.drawRoundedRect(QRectF(1, 1, 28, 14), 3, 3)
        _dots(p, QRectF(5, 4, 20, 8), pins, male, detail)
    p.restore()


ROW_START = 10.0  # from the edge of the unit to the designator
ROW_NAME_W = 24.0
ROW_COUNT_W = 14.0
ROW_MARGIN = 8.0  # kept free on the inner side, next to the line down the middle


def port_row(width: float, right: bool, has_count: bool) -> dict[str, tuple[float, float]]:
    """Where the parts of a port row go, as (left, right) in the unit's coordinates: from the
    edge inwards the designator, the connector and the pin count. Every part stays on its own
    side of the middle line."""
    parts: list[tuple[str, float, float]] = [
        ("name", ROW_NAME_W, 2.0),
        ("connector", CONNECTOR_W, 3.0),
    ]
    if has_count:
        parts.append(("count", ROW_COUNT_W, 0.0))
    out: dict[str, tuple[float, float]] = {}
    cursor = width - ROW_START if right else ROW_START
    for name, w, gap in parts:
        out[name] = (cursor - w, cursor) if right else (cursor, cursor + w)
        cursor += -(w + gap) if right else w + gap
    return out


def row_fits(width: float, rows: dict[str, tuple[float, float]], right: bool) -> bool:
    """True when every part is inside its half of the unit, clear of the middle line."""
    middle = width / 2
    if right:
        return all(x0 >= middle + ROW_MARGIN and x1 <= width - 2 for x0, x1 in rows.values())
    return all(x0 >= 2 and x1 <= middle - ROW_MARGIN for x0, x1 in rows.values())
