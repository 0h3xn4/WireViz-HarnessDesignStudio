"""Icon set: vector icons painted with QPainter, from Lucide geometry (ISC licence, see below).

The packaged program leaves out QtSvg, so no SVG file is loaded at run time: each icon is a few
path strings in Lucide's 24 x 24 grid, turned into a `QPainterPath` once. They are drawn as strokes
with round caps, in any colour and size, and recolour from the theme tokens.

    icon("undo", theme)                      -> QIcon (follows light / dark and the UI scale)
    icon("pass", theme, "success")           -> QIcon in a state colour
    pixmap("lock", 16, colour)               -> QPixmap
    draw_icon(painter, "search", rect, colour)
    icon_button(button, "zoom-in", theme, "Zoom in", "Ctrl+=")   -> icon, name and tooltip

Every icon button gets a tooltip that names the action and its shortcut (`tooltip_text`).

Lucide (https://lucide.dev), ISC licence:
    Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT);
    all other copyright (c) for Lucide are held by Lucide Contributors 2022.
    Permission to use, copy, modify, and/or distribute this software for any purpose with or
    without fee is hereby granted, provided that the above copyright notice and this permission
    notice appear in all copies. THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
    WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
    FITNESS.
The icons derived from Feather (chevrons, x, search, info, lock, clock, zoom, maximize) are also
under the MIT licence of Feather (Cole Bemis); the full texts are in docs/DECISIONS.md (D-146).
Geometry taken from lucide-static 1.56.0.
"""

import math
import re
from typing import Final

from PySide6.QtCore import QEvent, QObject, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QIconEngine,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QAbstractButton, QDockWidget, QToolButton

from harness_design_studio.gui.theme import ThemeManager

GRID: Final = 24.0  # Lucide's drawing grid

# name -> path strings in the 24 x 24 grid (the comment names the Lucide icon)
ICONS: Final[dict[str, tuple[str, ...]]] = {
    # undo-2
    "undo": (
        "M9 14 4 9l5-5",
        "M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11",
    ),
    # redo-2
    "redo": (
        "m15 14 5-5-5-5",
        "M20 9H9.5A5.5 5.5 0 0 0 4 14.5A5.5 5.5 0 0 0 9.5 20H13",
    ),
    # wand-sparkles
    "generate": (
        "m21.64 3.64-1.28-1.28a1.21 1.21 0 0 0-1.72 0L2.36 18.64a1.21 1.21 0 0 0 0 1.72l1.28 1.28a1.2 1.2 0 0 0 1.72 0L21.64 5.36a1.2 1.2 0 0 0 0-1.72",
        "m14 7 3 3",
        "M5 6v4",
        "M19 14v4",
        "M10 2v2",
        "M7 8H3",
        "M21 16h-4",
        "M11 3H9",
    ),
    # list-checks
    "check": (
        "M13 5h8",
        "M13 12h8",
        "M13 19h8",
        "m3 17 2 2 4-4",
        "m3 7 2 2 4-4",
    ),
    # file-output
    "export": (
        "M4.226 20.925A2 2 0 0 0 6 22h12a2 2 0 0 0 2-2V8a2.4 2.4 0 0 0-.706-1.706l-3.588-3.588A2.4 2.4 0 0 0 14 2H6a2 2 0 0 0-2 2v3.127",
        "M14 2v5a1 1 0 0 0 1 1h5",
        "m5 11-3 3",
        "m5 17-3-3h10",
    ),
    # file-input
    "import": (
        "M4 11V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.706.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-1",
        "M14 2v5a1 1 0 0 0 1 1h5",
        "M2 15h10",
        "m9 18 3-3-3-3",
    ),
    # zoom-in
    "zoom-in": (
        "M3 11a8 8 0 1 0 16 0a8 8 0 1 0 -16 0",
        "M21 21L16.65 16.65",
        "M11 8L11 14",
        "M8 11L14 11",
    ),
    # zoom-out
    "zoom-out": (
        "M3 11a8 8 0 1 0 16 0a8 8 0 1 0 -16 0",
        "M21 21L16.65 16.65",
        "M8 11L14 11",
    ),
    # maximize
    "fit": (
        "M8 3H5a2 2 0 0 0-2 2v3",
        "M21 8V5a2 2 0 0 0-2-2h-3",
        "M3 16v3a2 2 0 0 0 2 2h3",
        "M16 21h3a2 2 0 0 0 2-2v-3",
    ),
    # search
    "search": (
        "m21 21-4.34-4.34",
        "M3 11a8 8 0 1 0 16 0a8 8 0 1 0 -16 0",
    ),
    # lock
    "lock": (
        "M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-7a2 2 0 0 1 2 -2z",
        "M7 11V7a5 5 0 0 1 10 0v4",
    ),
    # lock-open
    "unlock": (
        "M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-7a2 2 0 0 1 2 -2z",
        "M7 11V7a5 5 0 0 1 9.9-1",
    ),
    # package-check
    "release": (
        "M12 22V12",
        "m16 17 2 2 4-4",
        "M21 11.127V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.729l7 4a2 2 0 0 0 2 .001l1.32-.753",
        "M3.29 7 12 12l8.71-5",
        "m7.5 4.27 8.997 5.148",
    ),
    # eye
    "review": (
        "M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0",
        "M9 12a3 3 0 1 0 6 0a3 3 0 1 0 -6 0",
    ),
    # pencil-line
    "revise": (
        "M13 21h8",
        "m15 5 4 4",
        "M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z",
    ),
    # folder-open
    "folder-open": (
        "m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2",
    ),
    # folder-search
    "reveal": (
        "M10.7 20H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v4.1",
        "m21 21-1.9-1.9",
        "M14 17a3 3 0 1 0 6 0a3 3 0 1 0 -6 0",
    ),
    # triangle-alert
    "warning": (
        "m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3",
        "M12 9v4",
        "M12 17h.01",
    ),
    # octagon-x
    "error": (
        "m15 9-6 6",
        "M2.586 16.726A2 2 0 0 1 2 15.312V8.688a2 2 0 0 1 .586-1.414l4.688-4.688A2 2 0 0 1 8.688 2h6.624a2 2 0 0 1 1.414.586l4.688 4.688A2 2 0 0 1 22 8.688v6.624a2 2 0 0 1-.586 1.414l-4.688 4.688a2 2 0 0 1-1.414.586H8.688a2 2 0 0 1-1.414-.586z",
        "m9 9 6 6",
    ),
    # info
    "info": (
        "M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0",
        "M12 16v-4",
        "M12 8h.01",
    ),
    # circle-check
    "pass": (
        "M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0",
        "m16 9-5.5 5.5L8 12",
    ),
    # circle-x
    "fail": (
        "M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0",
        "m15 9-6 6",
        "m9 9 6 6",
    ),
    # circle-dashed
    "not-checked": (
        "M10.1 2.182a10 10 0 0 1 3.8 0",
        "M13.9 21.818a10 10 0 0 1-3.8 0",
        "M17.609 3.721a10 10 0 0 1 2.69 2.7",
        "M2.182 13.9a10 10 0 0 1 0-3.8",
        "M20.279 17.609a10 10 0 0 1-2.7 2.69",
        "M21.818 10.1a10 10 0 0 1 0 3.8",
        "M3.721 6.391a10 10 0 0 1 2.7-2.69",
        "M6.391 20.279a10 10 0 0 1-2.69-2.7",
    ),
    # clock
    "pending": (
        "M2 12a10 10 0 1 0 20 0a10 10 0 1 0 -20 0",
        "M12 6v6l4 2",
    ),
    # refresh-cw
    "stale": (
        "M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8",
        "M21 3v5h-5",
        "M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16",
        "M8 16H3v5",
    ),
    # file-pen
    "draft": (
        "M12.659 22H18a2 2 0 0 0 2-2V8a2.4 2.4 0 0 0-.706-1.706l-3.588-3.588A2.4 2.4 0 0 0 14 2H6a2 2 0 0 0-2 2v9.34",
        "M14 2v5a1 1 0 0 0 1 1h5",
        "M10.378 12.622a1 1 0 0 1 3 3.003L8.36 20.637a2 2 0 0 1-.854.506l-2.867.837a.5.5 0 0 1-.62-.62l.836-2.869a2 2 0 0 1 .506-.853z",
    ),
    # rotate-ccw
    "revised": (
        "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8",
        "M3 3v5h5",
    ),
    # refresh-cw
    "refresh": (
        "M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8",
        "M21 3v5h-5",
        "M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16",
        "M8 16H3v5",
    ),
    # chevron-up
    "chevron-up": ("m18 15-6-6-6 6",),
    # chevron-down
    "chevron-down": ("m6 9 6 6 6-6",),
    # chevron-left
    "chevron-left": ("m15 18-6-6 6-6",),
    # chevron-right
    "chevron-right": ("m9 18 6-6-6-6",),
    # x
    "close": (
        "M18 6 6 18",
        "m6 6 12 12",
    ),
    # funnel
    "filter": (
        "M10 20a1 1 0 0 0 .553.895l2 1A1 1 0 0 0 14 21v-7a2 2 0 0 1 .517-1.341L21.74 4.67A1 1 0 0 0 21 3H3a1 1 0 0 0-.742 1.67l7.225 7.989A2 2 0 0 1 10 14z",
    ),
    # list-tree
    "tree": (
        "M8 5h13",
        "M13 12h8",
        "M13 19h8",
        "M3 10a2 2 0 0 0 2 2h3",
        "M3 5v12a2 2 0 0 0 2 2h3",
    ),
    # list
    "list": (
        "M3 5h.01",
        "M3 12h.01",
        "M3 19h.01",
        "M8 5h13",
        "M8 12h13",
        "M8 19h13",
    ),
    # table
    "table": (
        "M12 3v18",
        "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2z",
        "M3 9h18",
        "M3 15h18",
    ),
    # workflow
    "diagram": (
        "M5 3h4a2 2 0 0 1 2 2v4a2 2 0 0 1 -2 2h-4a2 2 0 0 1 -2 -2v-4a2 2 0 0 1 2 -2z",
        "M7 11v4a2 2 0 0 0 2 2h4",
        "M15 13h4a2 2 0 0 1 2 2v4a2 2 0 0 1 -2 2h-4a2 2 0 0 1 -2 -2v-4a2 2 0 0 1 2 -2z",
    ),
    # cable
    "harness": (
        "M17 19a1 1 0 0 1-1-1v-2a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2a1 1 0 0 1-1 1z",
        "M17 21v-2",
        "M19 14V6.5a1 1 0 0 0-7 0v11a1 1 0 0 1-7 0V10",
        "M21 21v-2",
        "M3 5V3",
        "M4 10a2 2 0 0 1-2-2V6a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2a2 2 0 0 1-2 2z",
        "M7 5V3",
    ),
    # file-clock
    "releases": (
        "M16 22h2a2 2 0 0 0 2-2V8a2.4 2.4 0 0 0-.706-1.706l-3.588-3.588A2.4 2.4 0 0 0 14 2H6a2 2 0 0 0-2 2v2.85",
        "M14 2v5a1 1 0 0 0 1 1h5",
        "M8 14v2.2l1.6 1",
        "M2 16a6 6 0 1 0 12 0a6 6 0 1 0 -12 0",
    ),
    # ---- project tree (SH-6): kinds of object ----
    # cpu
    "unit": (
        "M12 20v2",
        "M12 2v2",
        "M17 20v2",
        "M17 2v2",
        "M2 12h2",
        "M2 17h2",
        "M2 7h2",
        "M20 12h2",
        "M20 17h2",
        "M20 7h2",
        "M7 20v2",
        "M7 2v2",
        "M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2z",
        "M9 8h6a1 1 0 0 1 1 1v6a1 1 0 0 1 -1 1h-6a1 1 0 0 1 -1 -1v-6a1 1 0 0 1 1 -1z",
    ),
    # plug
    "interface": (
        "M12 22v-5",
        "M15 8V2",
        "M17 8a1 1 0 0 1 1 1v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1z",
        "M9 8V2",
    ),
    # package
    "part": (
        "M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z",
        "M12 22V12",
        "M3.29 7 12 12 20.71 7",
        "m7.5 4.27 9 5.15",
    ),
    # shapes
    "interface-type": (
        "M8.3 10a.7.7 0 0 1-.626-1.079L11.4 3a.7.7 0 0 1 1.198-.043L16.3 8.9a.7.7 0 0 1-.572 1.1Z",
        "M4 14h5a1 1 0 0 1 1 1v5a1 1 0 0 1 -1 1h-5a1 1 0 0 1 -1 -1v-5a1 1 0 0 1 1 -1z",
        "M14 17.5a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0 -7 0",
    ),
    # sliders-horizontal
    "config": (
        "M10 5H3",
        "M12 19H3",
        "M14 3v4",
        "M16 17v4",
        "M21 12h-9",
        "M21 19h-5",
        "M21 5h-7",
        "M8 10v4",
        "M8 12H3",
    ),
    # plus
    "plus": ("M5 12h14", "M12 5v14"),
}

ICON_NAMES: Final[tuple[str, ...]] = tuple(ICONS)

_TOKEN = re.compile(r"\s*,?\s*([MmLlHhVvCcSsQqTtAaZz])")
_NUMBER = re.compile(r"\s*,?\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)")
_FLAG = re.compile(r"\s*,?\s*([01])")
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def _arc(
    path: QPainterPath,
    p1: tuple[float, float],
    radii: tuple[float, float],
    rotation: float,
    large: bool,
    sweep: bool,
    p2: tuple[float, float],
) -> None:
    """Add an SVG elliptical arc (end-point form) to a path as cubic curves."""
    (x1, y1), (x2, y2) = p1, p2
    rx, ry = abs(radii[0]), abs(radii[1])
    if (x1, y1) == (x2, y2):
        return
    if rx == 0 or ry == 0:
        path.lineTo(x2, y2)
        return
    phi = math.radians(rotation)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    scale = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if scale > 1:
        rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(0.0, num / den)) * (-1 if large == sweep else 1)
    cxp, cyp = coef * rx * y1p / ry, -coef * ry * x1p / rx
    cx, cy = cp * cxp - sp * cyp + (x1 + x2) / 2, sp * cxp + cp * cyp + (y1 + y2) / 2
    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    theta = math.atan2(uy, ux)
    delta = math.atan2(vy, vx) - theta
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi
    n = max(1, math.ceil(abs(delta) / (math.pi / 2) - 1e-9))
    step = delta / n
    k = 4 / 3 * math.tan(step / 4)

    def point(angle: float, dr: float = 0.0) -> tuple[float, float]:
        ex, ey = rx * math.cos(angle), ry * math.sin(angle)
        tx, ty = -rx * math.sin(angle), ry * math.cos(angle)
        return (
            cx + cp * (ex + dr * tx) - sp * (ey + dr * ty),
            cy + sp * (ex + dr * tx) + cp * (ey + dr * ty),
        )

    for i in range(n):
        a0, a1 = theta + i * step, theta + (i + 1) * step
        c1, c2, end = point(a0, k), point(a1, -k), point(a1)
        path.cubicTo(QPointF(*c1), QPointF(*c2), QPointF(*end))


def parse_path(d: str) -> QPainterPath:
    """An SVG path string (M L H V C S Q T A Z, absolute and relative) as a `QPainterPath`."""
    path = QPainterPath()
    pos, n = 0, len(d)
    cmd = ""
    cur = start = (0.0, 0.0)
    last_c: tuple[float, float] | None = None  # last cubic control point (for S)
    last_q: tuple[float, float] | None = None  # last quadratic control point (for T)

    def number() -> float:
        nonlocal pos
        m = _NUMBER.match(d, pos)
        if m is None:
            raise ValueError(f"bad icon path at {pos}: {d!r}")
        pos = m.end()
        return float(m.group(1))

    def flag() -> bool:
        nonlocal pos
        m = _FLAG.match(d, pos)
        if m is None:
            raise ValueError(f"bad arc flag at {pos}: {d!r}")
        pos = m.end()
        return m.group(1) == "1"

    first = True
    while True:
        m = _TOKEN.match(d, pos)
        if m is not None:
            cmd, pos = m.group(1), m.end()
            first = True
        elif d[pos:].strip() == "":
            break
        elif not cmd or cmd in "Zz":
            raise ValueError(f"bad icon path at {pos}: {d!r}")
        rel = cmd.islower()
        up = cmd.upper()
        ox, oy = cur if rel else (0.0, 0.0)
        if up == "Z":
            path.closeSubpath()
            cur = start
            last_c = last_q = None
            cmd = "Z" if cmd == "Z" else "z"
            if d[pos:].strip() == "":
                break
            continue
        if up == "M":
            x, y = number() + ox, number() + oy
            if first:
                path.moveTo(x, y)
                start = (x, y)
            else:
                path.lineTo(x, y)
            cur, last_c, last_q = (x, y), None, None
            cmd = "l" if rel else "L"  # further pairs after a moveto are line-tos
        elif up == "L":
            cur = (number() + ox, number() + oy)
            path.lineTo(*cur)
            last_c = last_q = None
        elif up == "H":
            cur = (number() + ox, cur[1])
            path.lineTo(*cur)
            last_c = last_q = None
        elif up == "V":
            cur = (cur[0], number() + oy)
            path.lineTo(*cur)
            last_c = last_q = None
        elif up == "C":
            c1 = (number() + ox, number() + oy)
            c2 = (number() + ox, number() + oy)
            end = (number() + ox, number() + oy)
            path.cubicTo(QPointF(*c1), QPointF(*c2), QPointF(*end))
            cur, last_c, last_q = end, c2, None
        elif up == "S":
            c1 = (2 * cur[0] - last_c[0], 2 * cur[1] - last_c[1]) if last_c else cur
            c2 = (number() + ox, number() + oy)
            end = (number() + ox, number() + oy)
            path.cubicTo(QPointF(*c1), QPointF(*c2), QPointF(*end))
            cur, last_c, last_q = end, c2, None
        elif up == "Q":
            q = (number() + ox, number() + oy)
            end = (number() + ox, number() + oy)
            path.quadTo(QPointF(*q), QPointF(*end))
            cur, last_c, last_q = end, None, q
        elif up == "T":
            q = (2 * cur[0] - last_q[0], 2 * cur[1] - last_q[1]) if last_q else cur
            end = (number() + ox, number() + oy)
            path.quadTo(QPointF(*q), QPointF(*end))
            cur, last_c, last_q = end, None, q
        else:  # "A"
            rx, ry, rot = number(), number(), number()
            large, sweep = flag(), flag()
            end = (number() + ox, number() + oy)
            _arc(path, cur, (rx, ry), rot, large, sweep, end)
            cur, last_c, last_q = end, None, None
        first = False
        if pos >= n:
            break
    return path


_PATHS: dict[str, QPainterPath] = {}


def icon_path(name: str) -> QPainterPath:
    """The outline of an icon in the 24 x 24 grid (cached)."""
    path = _PATHS.get(name)
    if path is None:
        path = QPainterPath()
        for part in ICONS[name]:
            path.addPath(parse_path(part))
        _PATHS[name] = path
    return path


def stroke_width(size_px: float) -> float:
    """Line width in px for an icon of this size: Lucide's 2/24 of the size, never thinner than
    1.5 px, so small icons stay legible."""
    return max(1.5, size_px * 2 / GRID)


def draw_icon(
    painter: QPainter,
    name: str,
    rect: QRectF | tuple[float, float, float, float],
    colour: QColor,
    *,
    stroke: float | None = None,
) -> None:
    """Paint an icon centred in `rect`, as large as fits, in `colour`. `stroke` is the line width
    in px (default: `stroke_width` of the size)."""
    r = rect if isinstance(rect, QRectF) else QRectF(*rect)
    size = min(r.width(), r.height())
    if size <= 0:
        return
    scale = size / GRID
    width = stroke if stroke is not None else stroke_width(size)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(r.center().x() - size / 2, r.center().y() - size / 2)
    painter.scale(scale, scale)
    pen = QPen(colour, width / scale)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(icon_path(name))
    painter.restore()


def pixmap(name: str, size: int, colour: QColor, dpr: float = 1.0) -> QPixmap:
    """An icon as a square pixmap of `size` logical px."""
    pm = QPixmap(round(size * dpr), round(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    draw_icon(p, name, QRectF(0, 0, size, size), colour)
    p.end()
    return pm


class ThemedIconEngine(QIconEngine):
    """Paints one icon at whatever size and in whatever colour the theme says at that moment, so a
    `QIcon` made once follows light / dark and the UI scale. Normal and active use `role`,
    disabled the muted tone, selected (a highlighted row or menu entry) `on-primary`; with
    `checked_role` the on-state uses that token (a checked button has a primary fill)."""

    def __init__(
        self, name: str, theme: ThemeManager, role: str = "text", checked_role: str | None = None
    ) -> None:
        super().__init__()
        if name not in ICONS:
            raise KeyError(f"no icon named {name!r}")
        self.name, self.theme, self.role, self.checked_role = name, theme, role, checked_role

    def _colour(self, mode: QIcon.Mode, state: QIcon.State) -> QColor:
        if mode == QIcon.Mode.Selected:
            return self.theme.color("on-primary")
        if state == QIcon.State.On and self.checked_role:
            return self.theme.color(self.checked_role)
        if mode == QIcon.Mode.Disabled:
            c = self.theme.color("text-muted" if self.role == "text" else self.role)
            c.setAlphaF(0.55)
            return c
        return self.theme.color(self.role)

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State) -> None:
        draw_icon(painter, self.name, QRectF(rect), self._colour(mode, state))

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        pm = QPixmap(size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        self.paint(p, QRect(0, 0, size.width(), size.height()), mode, state)
        p.end()
        return pm

    def actualSize(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QSize:  # noqa: N802
        side = min(size.width(), size.height())
        return QSize(side, side)

    def clone(self) -> "ThemedIconEngine":
        return ThemedIconEngine(self.name, self.theme, self.role, self.checked_role)


def icon(
    name: str, theme: ThemeManager, role: str = "text", *, checked_role: str | None = None
) -> QIcon:
    """A `QIcon` for the named icon in a token colour (default: the text colour)."""
    return QIcon(ThemedIconEngine(name, theme, role, checked_role))


def tooltip_text(label: str, shortcut: str | None = None) -> str:
    """ "Zoom in (Ctrl+=)": what the control does and the key that does the same."""
    return f"{label} ({shortcut})" if shortcut else label


def icon_button(
    button: QAbstractButton,
    name: str,
    theme: ThemeManager,
    label: str,
    shortcut: str | None = None,
    *,
    text: str | None = None,
    role: str = "text",
    checked_role: str | None = None,
) -> None:
    """Give a button an icon, an accessible name and a tooltip with its shortcut. With `text` the
    icon sits beside it; without, the button shows the icon only (and gets a square minimum)."""
    button.setIcon(icon(name, theme, role, checked_role=checked_role))
    # a visible text must be part of the accessible name (label in name)
    button.setAccessibleName(label if text is None or text.lower() in label.lower() else text)
    button.setToolTip(tooltip_text(label, shortcut))
    if text is not None:
        button.setText(text)
        if isinstance(button, QToolButton):
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    else:
        button.setText("")
        if isinstance(button, QToolButton):
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setProperty("iconOnly", True)
    button.style().unpolish(button)
    button.style().polish(button)


class _DockButtons(QObject):
    """Keeps the icon and tooltip of a dock's title-bar buttons through style changes (a new style
    sheet resets the buttons Qt makes itself)."""

    def __init__(self, dock: QDockWidget, theme: ThemeManager, close_label: str) -> None:
        super().__init__(dock)
        self.dock, self.theme, self.close_label = dock, theme, close_label
        self.apply()
        theme.changed.connect(self.apply)
        dock.installEventFilter(self)

    def apply(self) -> None:
        close = self.dock.findChild(QAbstractButton, "qt_dockwidget_closebutton")
        if close is not None:
            close.setIcon(icon("close", self.theme))
            close.setToolTip(self.close_label)
            close.setAccessibleName(self.close_label)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.Polish):
            self.apply()
        return False


def style_dock_buttons(dock: QDockWidget, theme: ThemeManager, close_label: str) -> None:
    """Give the close button of a dock widget the theme's close icon, an accessible name and a
    tooltip ("Close panel")."""
    _DockButtons(dock, theme, close_label)
