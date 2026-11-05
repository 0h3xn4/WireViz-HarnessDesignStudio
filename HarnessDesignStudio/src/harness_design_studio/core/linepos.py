"""Where a label sits on a line: a position along a polyline, in pure geometry (no Qt).

The pill of an interface, the label of a connection and the connector box at each end of a
connection belong to their line: they slide along it and never leave it. Where one sits is a
fraction `t` of the length of the line, 0 at its first corner point and 1 at its last, so that it
keeps its relative place when the devices move and the line gets longer, shorter or changes its
corners. `diagram/marks.json` stores that `t` (`core.model.DiagramMark`).

- `point_at` and `project` convert between `t` and a point of the line (the corners count: the
  length is the sum of the straight pieces);
- `clamp_t` keeps a label of a given half width inside the line, and in the middle when the line
  is too short to hold it;
- `grab_offset` and `slide` are a drag: the label follows the projection of the pointer onto the
  line, keeping the distance along the line at which it was taken hold of;
- `from_offset` reads a mark of an earlier version (a free offset from the automatic place) as the
  nearest point of the line.

Nothing here depends on the editor, so it is tested on its own (`tests/test_linepos.py`).
"""

import math
from collections.abc import Sequence

Point = tuple[float, float]

START = 0.0  # t at the first corner point of a line
END = 1.0  # t at its last
MIDDLE = 0.5  # the default place of a label: half way along the line
ROUND_TO = 4  # decimals of a stored t (a ten-thousandth of the length)
HORIZONTAL = "horizontal"
VERTICAL = "vertical"
SLANTED = "slanted"
CORNER = "corner"


def _pieces(poly: Sequence[Point]) -> list[tuple[Point, Point, float]]:
    return [
        (p, q, math.hypot(q[0] - p[0], q[1] - p[1])) for p, q in zip(poly, poly[1:], strict=False)
    ]


def length(poly: Sequence[Point]) -> float:
    """The length of the line: the sum of its straight pieces (0 for fewer than two points)."""
    return sum(n for _p, _q, n in _pieces(poly))


def clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def point_at_distance(poly: Sequence[Point], s: float) -> Point:
    """The point `s` along the line from its first point; before the start and after the end it is
    the first and the last point. A line of one point (or none: (0, 0)) is that point."""
    if not poly:
        return (0.0, 0.0)
    left = max(s, 0.0)
    for p, q, n in _pieces(poly):
        if n > 0.0 and left <= n:
            k = left / n
            return (p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k)
        left -= n
    return tuple(poly[-1])  # type: ignore[return-value]


def point_at(poly: Sequence[Point], t: float) -> Point:
    """The point at fraction `t` of the length of the line (`t` outside 0 to 1 gives an end)."""
    return point_at_distance(poly, clamp(t, START, END) * length(poly))


def project_distance(poly: Sequence[Point], p: Point) -> tuple[float, Point, float]:
    """The point of the line nearest to `p`: (how far along the line it is, the point, how far `p`
    is from it). Where two pieces are equally near, the earlier one. A line with no piece is its
    first point at distance 0."""
    if not poly:
        return 0.0, (0.0, 0.0), 0.0
    best: tuple[float, Point, float] | None = None
    start = 0.0
    for a, b, n in _pieces(poly):
        if n > 0.0:
            k = clamp(
                ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (n * n), 0, 1
            )
            foot = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            away = math.hypot(p[0] - foot[0], p[1] - foot[1])
            if best is None or away < best[2] - 1e-9:
                best = (start + k * n, foot, away)
        start += n
    if best is None:
        first = tuple(poly[0])
        return 0.0, first, math.hypot(p[0] - first[0], p[1] - first[1])  # type: ignore[return-value]
    return best


def project(poly: Sequence[Point], p: Point) -> tuple[float, Point, float]:
    """The point of the line nearest to `p`: (its `t`, the point, how far `p` is from it)."""
    total = length(poly)
    s, foot, away = project_distance(poly, p)
    return (s / total if total > 0.0 else START), foot, away


def clamp_distance(total: float, s: float, margin: float) -> float:
    """`s` kept `margin` away from both ends of a line of length `total`; a line shorter than two
    margins holds the label in its middle."""
    if total <= 2 * margin:
        return total / 2
    return clamp(s, margin, total - margin)


def clamp_t(poly: Sequence[Point], t: float, margin: float) -> float:
    """`t` kept inside the line so that a label of half width `margin` stays on it: at least
    `margin` from either end, and in the middle when the line is shorter than the label. Called
    each time the label is drawn (the stored `t` is not changed, so a line that gets longer again
    gives the label its place back)."""
    total = length(poly)
    if total <= 0.0:
        return START
    return clamp_distance(total, clamp(t, START, END) * total, margin) / total


def place(poly: Sequence[Point], t: float, margin: float) -> Point:
    """Where the centre of a label with the stored position `t` is drawn: on the line, kept inside
    it (`clamp_t`)."""
    return point_at(poly, clamp_t(poly, t, margin))


def grab_offset(poly: Sequence[Point], pointer: Point, centre: Point) -> float:
    """How far along the line (positive: further from the start) the centre of a label is from the
    point where the pointer took hold of it, so that a label taken by its edge does not jump."""
    return project_distance(poly, centre)[0] - project_distance(poly, pointer)[0]


def slide(poly: Sequence[Point], pointer: Point, grab: float, margin: float) -> float:
    """The `t` of a label that is dragged: the projection of the pointer onto the line, plus the
    `grab` it was taken by (`grab_offset`), kept inside the line (`clamp_t`) however far from the
    line the pointer is, rounded to `ROUND_TO` decimals."""
    total = length(poly)
    if total <= 0.0:
        return START
    s = clamp_distance(total, project_distance(poly, pointer)[0] + grab, margin)
    return round(s / total, ROUND_TO)


def from_offset(poly: Sequence[Point], automatic: Point, dx: float, dy: float) -> float:
    """The `t` for a mark of an earlier version: a free offset (`dx`, `dy`) from the `automatic`
    place of the label, read as the nearest point of the line to where that offset put it."""
    return round(project(poly, (automatic[0] + dx, automatic[1] + dy))[0], ROUND_TO)


def direction_at(poly: Sequence[Point], t: float, margin: float = 0.0) -> str:
    """How the line runs where a label with the position `t` sits: "horizontal", "vertical",
    "slanted", or "corner" when the label's point is at a bend (the pieces on either side differ).
    A cursor for the drag is chosen from it."""
    total = length(poly)
    pieces = [(p, q) for p, q, n in _pieces(poly) if n > 0.0]
    if not pieces or total <= 0.0:
        return HORIZONTAL
    s = clamp_distance(total, clamp(t, START, END) * total, margin)
    kinds: list[str] = []
    at = 0.0
    for p, q in pieces:
        n = math.hypot(q[0] - p[0], q[1] - p[1])
        if at - 1e-6 <= s <= at + n + 1e-6:
            kinds.append(HORIZONTAL if p[1] == q[1] else VERTICAL if p[0] == q[0] else SLANTED)
        at += n
    unique = set(kinds)
    return next(iter(unique)) if len(unique) == 1 else CORNER
