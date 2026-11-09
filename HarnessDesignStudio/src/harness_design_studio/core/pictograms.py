# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The pictograms of the device kinds and the outlines of the badges, as plain path data (no Qt).

Each pictogram is drawn in a box of 16 x 16 units as a list of path commands, `("M", (x, y))`,
`("L", (x, y))`, `("C", (x1, y1, x2, y2, x, y))` and `("Z", ())`. They are written once, here, and
read by both painters: `gui/device_looks.py` turns the commands into a `QPainterPath` for the
window, and `core/outputs/looks.py` puts them in a `Shape` of the drawing model that
`core/outputs/canvas.py` writes as an SVG path and as PDF operators for the written block diagram.
So the picture in the window and the picture in the file come from the same numbers and cannot
drift.

Circles and arcs are cubic curves (the usual four-curve approximation, so no arc flags have to
be written), and every coordinate is rounded to `DECIMALS` places when it is made: the sines and
cosines the stars, wheels and hexagons need may differ in the last binary digit between platforms,
and rounding first makes the same file on Linux and on Windows (the files then write three
decimals, `core/outputs/canvas.py`). The geometry here is the one the window has always drawn
(release 1.15.0 and the device looks); nothing in it depends on a theme or a setting.
"""

import math
from typing import Final

Cmd = tuple[str, tuple[float, ...]]
Path = tuple[Cmd, ...]

BOX: Final = 16.0  # a pictogram is drawn in a box of this many units on each side
STROKE: Final = 1.5  # the line of a pictogram, in those units
DECIMALS: Final = 4  # every coordinate is rounded to this many decimals when it is made
KAPPA: Final = 0.5522847498307936  # the control point distance of a quarter circle (4/3 tan(pi/8))
FILLED: Final = (
    "star_tracker",
    "pyro",
)  # drawn solid: a line drawing of a star is too thin to read
FULL_TURN: Final = 360.0
QUARTER_TURN: Final = 90.0
SHAPES: Final = ("square", "circle", "hexagon", "octagon")
BADGE_CORNER: Final = 0.2  # the corner radius of the square badge, in sides
OCTAGON_CUT: Final = 0.3  # the corner cut of the octagon badge, in sides


def _r(v: float) -> float:
    return round(v, DECIMALS) + 0.0  # (+ 0.0 turns a negative zero into zero)


class Builder:
    """Collects the commands of one picture."""

    def __init__(self) -> None:
        self.cmds: list[Cmd] = []

    def move(self, x: float, y: float) -> None:
        self.cmds.append(("M", (_r(x), _r(y))))

    def to(self, x: float, y: float) -> None:
        self.cmds.append(("L", (_r(x), _r(y))))

    def cubic(self, x1: float, y1: float, x2: float, y2: float, x: float, y: float) -> None:
        self.cmds.append(("C", tuple(_r(v) for v in (x1, y1, x2, y2, x, y))))

    def close(self) -> None:
        self.cmds.append(("Z", ()))

    # -- shapes (each starts a subpath of its own)
    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.move(x1, y1)
        self.to(x2, y2)

    def poly(self, pts: list[tuple[float, float]]) -> None:
        self.move(*pts[0])
        for x, y in pts[1:]:
            self.to(x, y)
        self.close()

    def rect(self, x: float, y: float, w: float, h: float) -> None:
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])

    def rrect(self, x: float, y: float, w: float, h: float, r: float) -> None:
        """A rectangle with round corners of radius `r`."""
        k = KAPPA * r
        self.move(x + r, y)
        self.to(x + w - r, y)
        self.cubic(x + w - r + k, y, x + w, y + r - k, x + w, y + r)
        self.to(x + w, y + h - r)
        self.cubic(x + w, y + h - r + k, x + w - r + k, y + h, x + w - r, y + h)
        self.to(x + r, y + h)
        self.cubic(x + r - k, y + h, x, y + h - r + k, x, y + h - r)
        self.to(x, y + r)
        self.cubic(x, y + r - k, x + r - k, y, x + r, y)
        self.close()

    def arc(
        self, cx: float, cy: float, rx: float, ry: float, start: float, span: float, *, move: bool
    ) -> None:
        """An elliptical arc from `start` degrees, turning `span` degrees counter-clockwise on the
        screen (0 is three o'clock), as Qt's `drawArc` does; `move` starts a subpath there."""
        n = max(1, math.ceil(abs(span) / QUARTER_TURN - 1e-9))
        step = math.radians(span) / n
        a = math.radians(start)

        def point(t: float) -> tuple[float, float]:
            return cx + rx * math.cos(t), cy - ry * math.sin(t)

        if move:
            self.move(*point(a))
        for _ in range(n):
            b = a + step
            k = 4 / 3 * math.tan((b - a) / 4)
            (x0, y0), (x1, y1) = point(a), point(b)
            c1 = (x0 - k * rx * math.sin(a), y0 - k * ry * math.cos(a))
            c2 = (x1 + k * rx * math.sin(b), y1 + k * ry * math.cos(b))
            self.cubic(c1[0], c1[1], c2[0], c2[1], x1, y1)
            a = b

    def ellipse(self, cx: float, cy: float, rx: float, ry: float) -> None:
        self.arc(cx, cy, rx, ry, 0.0, FULL_TURN, move=True)
        self.close()

    def dot(self, cx: float, cy: float, r: float) -> None:
        self.ellipse(cx, cy, r, r)

    def curve(
        self, x0: float, y0: float, c: tuple[float, float, float, float], x1: float, y1: float
    ) -> None:
        self.move(x0, y0)
        self.cubic(c[0], c[1], c[2], c[3], x1, y1)

    def done(self) -> Path:
        return tuple(self.cmds)


def _polar(b: Builder, cx: float, cy: float, r1: float, r2: float, deg: float) -> None:
    a = math.radians(deg)
    b.line(
        cx + r1 * math.cos(a), cy + r1 * math.sin(a), cx + r2 * math.cos(a), cy + r2 * math.sin(a)
    )


def _star(b: Builder, cx: float, cy: float, r_out: float, r_in: float, n: int) -> None:
    pts: list[tuple[float, float]] = []
    for k in range(2 * n):
        r = r_out if k % 2 == 0 else r_in
        a = math.radians(-QUARTER_TURN + k * 180 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    b.poly(pts)


# ---- the pictograms: one per kind, in a box of 16 x 16 --------------------------------------


def _computer(b: Builder) -> None:  # a chip: a body with pins on every side
    b.rrect(3.5, 3.5, 9, 9, 1.2)
    for v in (6, 8, 10):
        b.line(v, 1.5, v, 3.5)
        b.line(v, 12.5, v, 14.5)
        b.line(1.5, v, 3.5, v)
        b.line(12.5, v, 14.5, v)


def _interface_unit(b: Builder) -> None:  # one input fanning out to three outputs
    b.rrect(1.5, 4, 5, 8, 1)
    for y in (3.5, 8, 12.5):
        b.line(6.5, 8, 11.5, y)
        b.dot(13, y, 1.3)


def _battery(b: Builder) -> None:  # a cell with its terminal, a plus and a minus
    b.rrect(1.5, 4.5, 11.5, 7, 1.2)
    b.rect(13, 6.5, 1.8, 3)
    b.line(3.6, 8, 6.6, 8)
    b.line(5.1, 6.5, 5.1, 9.5)
    b.line(8.8, 8, 10.8, 8)


def _solar_array(b: Builder) -> None:  # a tilted panel of cells on a stem
    b.poly([(1.5, 10.5), (4.5, 3.5), (14.5, 3.5), (11.5, 10.5)])
    b.line(3, 7, 13, 7)
    b.line(7.8, 3.5, 4.8, 10.5)
    b.line(11.2, 3.5, 8.2, 10.5)
    b.line(6.5, 10.5, 6.5, 14.5)


def _power_unit(b: Builder) -> None:  # one input, a bus and three outputs
    b.line(1.5, 8, 5, 8)
    b.line(5, 3, 5, 13)
    for y in (3, 8, 13):
        b.line(5, y, 11.5, y)
        b.rect(11.5, y - 1.3, 2.6, 2.6)


def _reaction_wheel(b: Builder) -> None:  # a rim, a hub and three spokes
    b.dot(8, 8, 6.3)
    b.dot(8, 8, 1.4)
    for k in range(3):
        _polar(b, 8, 8, 1.4, 6.3, 90 + k * 120)


def _magnetorquer(b: Builder) -> None:  # a rod wound with a coil
    b.rect(1.5, 6, 13, 4)
    for x in (3.5, 6.5, 9.5, 12.5):
        b.line(x - 1, 3.5, x + 1, 12.5)


def _thruster(b: Builder) -> None:  # a chamber, a bell and a plume
    b.rect(5.5, 1.5, 5, 4)
    b.poly([(5.5, 5.5), (10.5, 5.5), (13, 10), (3, 10)])
    for x in (5.5, 8, 10.5):
        b.line(x, 11.5, x, 14.5)


def _star_tracker(b: Builder) -> None:  # a five-pointed star
    _star(b, 8, 8.5, 6.8, 2.8, 5)


def _sun_sensor(b: Builder) -> None:  # the sun: a disc with rays
    b.dot(8, 8, 3)
    for k in range(8):
        _polar(b, 8, 8, 4.8, 6.9, k * 45)


def _gyro(b: Builder) -> None:  # three axes from one point
    b.line(8, 8, 14.5, 8)
    b.line(8, 8, 8, 1.5)
    b.line(8, 8, 3, 13)
    for x, y in ((14.5, 8), (8, 1.5), (3, 13)):
        b.dot(x, y, 1.1)
    b.dot(8, 8, 1.1)


def _sensor(b: Builder) -> None:  # a target
    b.dot(8, 8, 4.8)
    b.dot(8, 8, 1.1)
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        b.line(8 + dx * 4.8, 8 + dy * 4.8, 8 + dx * 7.2, 8 + dy * 7.2)


def _transceiver(b: Builder) -> None:  # a radio box that sends waves
    b.rrect(2.5, 9, 11, 5.5, 1.2)
    b.line(8, 9, 8, 6)
    b.dot(8, 5, 1)
    for r in (3.4, 6):
        b.arc(8, 5, r, r, 35, 110, move=True)


def _antenna(b: Builder) -> None:  # a dish on a stem
    b.arc(8, 5, 6, 6, 190, 160, move=True)
    b.line(8, 11, 8, 14.5)
    b.line(5, 14.5, 11, 14.5)
    b.line(8, 9, 8, 4.5)
    b.dot(8, 4, 0.9)


def _payload(b: Builder) -> None:  # a camera
    b.rrect(1.5, 4.5, 13, 9, 1.5)
    b.dot(8, 9, 3)
    b.rect(10.5, 2.5, 3, 2)


def _heater(b: Builder) -> None:  # a plate with three rising curls of heat
    b.rect(2, 11.5, 12, 3)
    for x in (4.5, 8, 11.5):
        b.curve(x, 10, (x - 2.2, 8, x + 2.2, 6), x, 4)


def _pyro(b: Builder) -> None:  # a spark
    _star(b, 8, 8, 7, 2.6, 8)


def _mechanism(b: Builder) -> None:  # a gear
    b.dot(8, 8, 3.2)
    for k in range(8):
        _polar(b, 8, 8, 4.6, 6.9, k * 45)
    b.dot(8, 8, 5)


def _ground_support(b: Builder) -> None:  # a terminal with a prompt
    b.rrect(1.5, 2.5, 13, 8.5, 1.2)
    b.line(8, 11, 8, 13.5)
    b.line(5, 13.5, 11, 13.5)
    b.line(4.2, 5, 6.4, 6.8)
    b.line(6.4, 6.8, 4.2, 8.6)
    b.line(8, 8.6, 10.8, 8.6)


def _device(b: Builder) -> None:  # a plain equipment box
    b.rrect(2, 2.5, 12, 11, 1.8)
    b.line(2, 6.2, 14, 6.2)


_DRAW = {
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


def _build() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for key, draw in _DRAW.items():
        b = Builder()
        draw(b)
        out[key] = b.done()
    return out


PICTOGRAMS: Final[dict[str, Path]] = _build()


# ---- the outline of a badge ---------------------------------------------------------------------


def shape_path(shape: str, x: float, y: float, w: float, h: float) -> Path:
    """The outline of a badge in the rectangle (x, y, w, h): `square` (rounded), `circle`,
    `hexagon` (points left and right) or `octagon`; `rect` is a plain rectangle; an unknown name
    gives the square."""
    b = Builder()
    cx, cy, rx, ry = x + w / 2, y + h / 2, w / 2, h / 2
    if shape == "circle":
        b.ellipse(cx, cy, rx, ry)
    elif shape == "hexagon":
        b.poly(
            [
                (cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))
                for a in range(0, int(FULL_TURN), 60)
            ]
        )
    elif shape == "octagon":
        dx, dy = w * OCTAGON_CUT, h * OCTAGON_CUT
        r, bt = x + w, y + h
        b.poly(
            [(x + dx, y), (r - dx, y), (r, y + dy), (r, bt - dy), (r - dx, bt), (x + dx, bt),
             (x, bt - dy), (x, y + dy)]
        )  # fmt: skip
    elif shape == "rect":  # a plain rectangle: the band of a card
        b.rect(x, y, w, h)
    else:
        b.rrect(x, y, w, h, w * BADGE_CORNER)
    return b.done()


def placed(path: Path, scale: float, dx: float, dy: float) -> Path:
    """`path` scaled by `scale` and moved by (dx, dy): how a picture of the 16-unit box gets into
    a badge. The result is rounded again, so the numbers a file writes are the same everywhere."""
    out: list[Cmd] = []
    for op, pts in path:
        moved = tuple(_r(v * scale + (dx if k % 2 == 0 else dy)) for k, v in enumerate(pts))
        out.append((op, moved))
    return tuple(out)
