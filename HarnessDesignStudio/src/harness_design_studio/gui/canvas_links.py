"""Connections on the diagram: a line between the two devices of a `core.links.Link`.

A connection joins a connector of one device to a connector of another, pin by pin. It is drawn
as a dash-dotted line (an interface is a solid line) from the edge of the first device that faces
the second to the edge of the second, with a label that reads the two connectors, for example
"OBC-J01 - RW1-J02", and, below it, what the pairs carry (CAN, power ...: derived from the pins,
`core.links.derived_interfaces`). It is its own small item and does not take part in the routing
of the interfaces, so a diagram without connections is drawn exactly as before.

With View > Show connectors on connections, or in the Expert mode, a small box at each end of the
line names the connector and how many of its pins the connection pairs (`core.links.link_ends`);
the tooltip also names the way through the harness once one was made from the connection
(`core.links.link_path`). Nothing is drawn or computed for the boxes while they are off.

`connection_route` needs no Qt state and is tested on its own.
"""

import html
from collections.abc import Mapping
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QBrush, QFontMetrics, QPainter, QPainterPath, QPainterPathStroker
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from harness_design_studio.core import linepos, routing
from harness_design_studio.core.links import (
    derived_interfaces,
    link_caption,
    link_ends,
    link_path,
)
from harness_design_studio.core.model import Link, Project, mark_is_along
from harness_design_studio.gui import strings

if TYPE_CHECKING:
    from harness_design_studio.gui.canvas import DiagramScene, UnitItem

OUT = 36.0  # how far a line leaves a device before it turns
HIT_WIDTH = 12.0  # how wide a click on the line still counts
CHIP_PAD_X = 8.0
CHIP_PAD_Y = 3.0
END_GAP = 4.0  # between the edge of a device and the box of its connector
CHIP_MAX_W = 240.0  # a longer label is cut with an ellipsis (the tooltip has the whole text)
END_MAX_W = 112.0  # the same for the connector boxes at the two ends
LABEL_GAP = 4.0  # between two boxes of one connection, and between a box and a device
REACH_X = 2 * CHIP_MAX_W + 3 * LABEL_GAP  # how far from its line the tool may have to put a label:
REACH_Y = 160.0  # three steps of (half a box and a gap) across, of (a box and a gap) down


def _channel(x: float, edge: float, side: str) -> float:
    """A vertical piece of a line at `x`, kept at least `END_GAP` out of the device edge `edge`."""
    return max(x, edge + END_GAP) if side == "right" else min(x, edge - END_GAP)


def connection_route(
    a: tuple[float, float],
    side_a: str,
    b: tuple[float, float],
    side_b: str,
    bend: float = 0.0,
) -> list[tuple[float, float]]:
    """The corners of a line from point `a` (on the `side_a` edge of its device, "left" or
    "right") to point `b`. Facing edges (right of the left device, left of the right one) meet in
    the gap between the devices; any other pair of edges goes round: out of both edges by `OUT`
    and across at the height between the two points. `bend` is how far the person moved the
    vertical piece (or pieces) across; it never goes into a device."""
    (xa, ya), (xb, yb) = a, b
    if (side_a, side_b) in (("right", "left"), ("left", "right")) and (xb - xa) * (
        1 if side_a == "right" else -1
    ) > 0:
        lo, hi = min(xa, xb) + END_GAP, max(xa, xb) - END_GAP
        mid = (xa + xb) / 2
        if lo < hi:
            mid = min(max(mid + bend, lo), hi)
        return [a, (mid, ya), (mid, yb), b]
    out_a = _channel((xa + OUT if side_a == "right" else xa - OUT) + bend, xa, side_a)
    out_b = _channel((xb + OUT if side_b == "right" else xb - OUT) + bend, xb, side_b)
    if side_a == side_b:  # one channel for both ends, clear of both devices
        out_a = out_b = max(out_a, out_b) if side_a == "right" else min(out_a, out_b)
        return [a, (out_a, ya), (out_a, yb), b]
    mid_y = (ya + yb) / 2
    return [a, (out_a, ya), (out_a, mid_y), (out_b, mid_y), (out_b, yb), b]


DRAG_PX = 4.0  # how far the pointer goes (in screen pixels) before a click is a drag
HOME_PX = 1.0  # a label let go this close to where it was taken is where it was
NO_SHIFT = QPointF(0.0, 0.0)
SLIDE_CURSORS = {  # the cursor over a label that slides along a line, by how the line runs there
    linepos.HORIZONTAL: Qt.CursorShape.SizeHorCursor,
    linepos.VERTICAL: Qt.CursorShape.SizeVerCursor,
}


class ChipDrag:
    """What the things drawn on a line do when they are dragged: the label (an interface or a
    connection), the connector box at each end of a connection, and the bend of a connection.

    A label sits ON its line and slides along it: while it is dragged it is at the point of the
    line nearest to the pointer, however far the pointer is from the line (`core.linepos`), and
    where it is let go it stays, as a fraction `t` of the length of the line (`DiagramMark`), so it
    keeps its relative place when devices move and the line changes. The bend and the vertical
    piece of a route are offsets across, as before. A thing follows the pointer once the pointer
    went `DRAG_PX`. The item says what can be dragged (`drag_slots`: the name of each mark, where it
    is drawn now, and whether it moves across only); a press anywhere else is the item's own
    business (a click on the line selects it, nothing more)."""

    dscene: DiagramScene
    poly: list[tuple[float, float]]  # the corner points of the line as drawn
    mark_ids: tuple[str, ...] = ()  # the marks this item may have, the main label first
    _shifts: dict[str, QPointF]  # the offsets (bend, route) by mark
    _along: dict[str, float]  # the places of the labels on the line (t) by mark
    _slot = ""  # the mark of the thing under the pointer since the press
    _press: QPointF | None = None  # the scene point of that press
    _base = NO_SHIFT  # the shift of the thing at the press
    _grab = 0.0  # how far along the line the label's centre is from the point taken hold of
    _home = NO_SHIFT  # where the centre of the label was at the press
    _dragging = False
    _cursor_shape: Qt.CursorShape | None = None  # the override cursor while a label is dragged

    def drag_slots(self) -> list[tuple[str, QRectF, bool]]:
        raise NotImplementedError

    def margin_of(self, mark_id: str) -> float:
        """How far from either end of the line the centre of the label `mark_id` stays: half its
        width and a little air, so that it does not touch the device the line leaves."""
        raise NotImplementedError

    def centre_of(self, mark_id: str) -> QPointF:
        """Where the centre of the label `mark_id` is drawn (or will be, at the next paint)."""
        raise NotImplementedError

    def _read_marks(self) -> tuple[dict[str, QPointF], dict[str, float]]:
        """What the project says now: the offsets of the pieces of the line and the places of the
        labels on it (a mark of an earlier version, a free offset of a label, is not read here:
        the diagram turns it into a place first, `adopt_legacy_marks`)."""
        sc = self.dscene
        shifts = {m: sc.mark_shift(m) for m in self.mark_ids if not mark_is_along(m)}
        along = {m: t for m in self.mark_ids if (t := sc.mark_along(m)) is not None}
        return shifts, along

    def reload_marks(self) -> None:
        """Take the marks of the project (it was opened, or a label was moved, put back, undone)."""
        shifts, along = self._read_marks()
        if shifts != getattr(self, "_shifts", None) or along != getattr(self, "_along", None):
            piece_moved = shifts != getattr(self, "_shifts", None)
            self._shifts, self._along = shifts, along
            self.prepareGeometryChange()  # type: ignore[attr-defined]
            if piece_moved:
                self.shifts_changed()
            self.along_changed()
            self.update()  # type: ignore[attr-defined]

    def shifts_changed(self) -> None:
        """The item hook for a change of an offset (a bend moves the line)."""

    def along_changed(self) -> None:
        """The item hook for a label that moved along its line."""

    def limit_shift(self, mark_id: str, shift: QPointF) -> QPointF:
        """The item hook for a move being dragged: what the thing may be moved to (its own limits)."""
        return shift

    def shift_of(self, mark_id: str) -> QPointF:
        shifts: dict[str, QPointF] = getattr(self, "_shifts", {})
        return shifts.get(mark_id, NO_SHIFT)

    def along_of(self, mark_id: str) -> float | None:
        """Where the person put the label `mark_id` on its line (None: where the tool put it)."""
        along: dict[str, float] = getattr(self, "_along", {})
        return along.get(mark_id)

    def on_line(self, mark_id: str, automatic: QRectF) -> QRectF:
        """The box of a label: `automatic`, the place the tool gave it, or, when the person put it
        somewhere, the same box centred on its place on the line (kept inside the line)."""
        t = self.along_of(mark_id)
        if t is None or len(self.poly) < 2:
            return automatic
        box = QRectF(automatic)
        box.moveCenter(QPointF(*linepos.place(self.poly, t, self.margin_of(mark_id))))
        return box

    def legacy_places(self) -> dict[str, float]:
        """The place on the line of every label that has a mark of an earlier version (a free
        offset from its automatic place): the nearest point of the line (`linepos.from_offset`),
        for `DiagramScene.adopt_legacy_marks`. Nothing when the line is not drawn yet."""
        return {}

    def hover_cursor(self, at: QPointF) -> Qt.CursorShape | None:
        """The cursor over a thing that can be dragged at scene point `at`: a label slides along
        its line (horizontal or vertical arrows where the line runs so, else the move cursor); a
        bend moves across. None elsewhere, and while nothing can be dragged."""
        ctl = self.dscene.ctl
        if ctl.tool != "select" or ctl.read_only:
            return None
        for mark_id, rect, across in self.drag_slots():
            if not rect.contains(at):
                continue
            if across:
                return Qt.CursorShape.SizeHorCursor
            return self._slide_cursor(mark_id, rect.center())
        return None

    def _slide_cursor(self, mark_id: str, centre: QPointF) -> Qt.CursorShape:
        t = self.along_of(mark_id)
        if t is None:
            t = linepos.project(self.poly, (centre.x(), centre.y()))[0]
        way = linepos.direction_at(self.poly, t, self.margin_of(mark_id))
        return SLIDE_CURSORS.get(way, Qt.CursorShape.SizeAllCursor)

    def show_cursor_at(self, at: QPointF) -> None:
        """Set the item's cursor for the pointer at scene point `at` (the hover of the item)."""
        shape = self.hover_cursor(at)
        if shape is None:
            self.unsetCursor()  # type: ignore[attr-defined]
        else:
            self.setCursor(shape)  # type: ignore[attr-defined]

    def chip_press(self, at: QPointF) -> None:
        """A press at scene point `at` on one of the things may become a drag (not while Connect is
        the tool, or in a project that cannot be changed)."""
        ctl = self.dscene.ctl
        self._dragging, self._press, self._slot = False, None, ""
        if ctl.tool != "select" or ctl.read_only:
            return
        for mark_id, rect, _across in self.drag_slots():
            if not rect.contains(at):
                continue
            if mark_is_along(mark_id):
                if len(self.poly) < 2:
                    return  # no line, so nothing to slide along
                centre = self.centre_of(mark_id)
                self._home = QPointF(centre)
                self._grab = linepos.grab_offset(
                    self.poly, (at.x(), at.y()), (centre.x(), centre.y())
                )
            self._slot, self._press, self._base = mark_id, at, QPointF(self.shift_of(mark_id))
            return

    def chip_move(self, at: QPointF, away: int) -> bool:
        """Follow the pointer (now at scene point `at`, `away` screen pixels from where it was
        pressed); returns whether this is a drag."""
        if self._press is None:
            return False
        if not self._dragging:
            if away < DRAG_PX:
                return True  # still a click
            self._dragging = True
        if mark_is_along(self._slot):
            t = linepos.slide(self.poly, (at.x(), at.y()), self._grab, self.margin_of(self._slot))
            self._set_along(self._slot, t)
            self._show_drag_cursor()
            return True
        across = next((x for m, _r, x in self.drag_slots() if m == self._slot), False)
        delta = at - self._press
        self._set_shift(self._slot, self._base + (QPointF(delta.x(), 0.0) if across else delta))
        return True

    def _set_along(self, mark_id: str, t: float) -> None:
        along = dict(getattr(self, "_along", {}))
        if along.get(mark_id) != t:
            along[mark_id] = t
            self._along = along
            self.prepareGeometryChange()  # type: ignore[attr-defined]
            self.along_changed()
            self.update()  # type: ignore[attr-defined]

    def _set_shift(self, mark_id: str, shift: QPointF) -> None:
        shift = self.limit_shift(mark_id, shift)
        shifts = dict(getattr(self, "_shifts", {}))
        if shifts.get(mark_id, NO_SHIFT) != shift:
            shifts[mark_id] = shift
            self._shifts = shifts
            self.prepareGeometryChange()  # type: ignore[attr-defined]
            self.shifts_changed()
            self.update()  # type: ignore[attr-defined]

    def _show_drag_cursor(self) -> None:
        """While a label is dragged the pointer is often off the item: the cursor is the
        application's, and says which way the label slides."""
        shape = self._slide_cursor(self._slot, self.centre_of(self._slot))
        if self._cursor_shape is None:
            QApplication.setOverrideCursor(shape)
        elif shape != self._cursor_shape:
            QApplication.changeOverrideCursor(shape)
        self._cursor_shape = shape

    def chip_release(self) -> bool:
        """Keep the thing where it was let go (one undoable step); returns whether it was a drag."""
        dragged, slot = self._dragging, self._slot
        self._press, self._dragging, self._slot = None, False, ""
        if self._cursor_shape is not None:
            QApplication.restoreOverrideCursor()
            self._cursor_shape = None
        if not dragged:
            return False
        ctl = self.dscene.ctl
        if mark_is_along(slot):
            t = self.along_of(slot)
            gone = self.centre_of(slot) - self._home
            if t is not None and gone.manhattanLength() >= HOME_PX:
                ctl.slide_mark(slot, t)
            else:
                self.reload_marks()  # (let go where it was taken: nothing was moved)
            return True
        shift = self.shift_of(slot)
        ctl.move_mark(slot, shift.x(), shift.y())
        return True


def free_rect(
    size: QSizeF, spots: list[QPointF], avoid: list[QRectF], steps: tuple[float, float]
) -> QRectF:
    """A box of `size` centred on the first of `spots` that touches none of `avoid`; the spots are
    tried as they are and then moved by `steps` (across, down) up to three times in every
    direction. When every try touches something, the one that touches the least."""
    best, best_area = QRectF(), -1.0
    shifts = [(0.0, 0.0)] + [
        (dx * steps[0] * k, dy * steps[1] * k)
        for k in (1, 2, 3)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
    ]
    for dx, dy in shifts:
        for spot in spots:
            rect = QRectF(
                spot.x() + dx - size.width() / 2,
                spot.y() + dy - size.height() / 2,
                size.width(),
                size.height(),
            )
            area = 0.0
            for other in avoid:
                hit = rect.intersected(other)
                area += max(0.0, hit.width()) * max(0.0, hit.height())
            if area == 0.0:
                return rect
            if best_area < 0 or area < best_area:
                best, best_area = rect, area
    return best


def sides(lane_a: int, lane_b: int, lanes: int, default_a: str, default_b: str) -> tuple[str, str]:
    """The edge each device leaves from: the one that faces the other device; two devices in one
    lane both use the edge away from the middle of the diagram (when a lane there has room)."""
    if lane_a == lane_b:
        within = routing.same_lane_side(lane_a, lanes, default_a)
        return within, within
    return (
        routing.side_toward(lane_a, lane_b, default_a),
        routing.side_toward(lane_b, lane_a, default_b),
    )


class ConnectionItem(ChipDrag, QGraphicsPathItem):
    """The drawn line and label of one `Link`."""

    def __init__(self, scene: DiagramScene, link_id: str, unit_w: float) -> None:
        super().__init__()
        self.dscene = scene
        self.link_id = link_id
        # the marks of this line: its label, the box at each end, and the bend of its route
        self.mark_ids = (
            f"link:{link_id}",
            f"end:{link_id}:0",
            f"end:{link_id}:1",
            f"bend:{link_id}",
        )
        self._shifts, self._along = self._read_marks()
        self._auto: dict[str, QRectF] = {}  # the box of each label where the tool puts it
        self.unit_w = unit_w
        self.poly: list[tuple[float, float]] = []
        self.text = ""  # what the pairs carry, "CAN, 2 wires"
        self._chip = QRectF()
        self._end_rects: list[QRectF] = []  # the connector boxes at the two ends (when shown)
        self._hover = False
        self.setZValue(1.2)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)

    # ---- geometry ---------------------------------------------------------------------------
    def _ends(self) -> tuple[UnitItem, UnitItem, str, str] | None:
        sc = self.dscene
        link = sc.ctl.project.links.get(self.link_id)
        if link is None:
            return None
        project = sc.ctl.project
        ca = project.connectors.get(link.a_connector)
        cb = project.connectors.get(link.b_connector)
        if ca is None or cb is None or not ca.unit_id or not cb.unit_id:
            return None
        ua, ub = sc.unit_items.get(ca.unit_id), sc.unit_items.get(cb.unit_id)
        if ua is None or ub is None:
            return None
        return ua, ub, ca.id, cb.id

    def _anchor(self, unit: UnitItem, connector_id: str, side: str) -> tuple[float, float]:
        x = unit.pos().x() + (self.unit_w if side == "right" else 0.0)
        ids = [c.id for c in unit.connectors()]
        if self.dscene.ctl.mode == "expert" and connector_id in ids:
            return x, unit.pos().y() + unit.port_y(ids.index(connector_id))
        return x, unit.pos().y() + unit.height() / 2

    def update_path(self) -> None:
        """Take the line the devices now allow. Repaints only when the line moved."""
        ends = self._ends()
        if ends is None:
            if not self.path().isEmpty():
                self.prepareGeometryChange()
                self.setPath(QPainterPath())
            self.poly = []
            return
        ua, ub, ida, idb = ends
        sa, sb = sides(ua.lane(), ub.lane(), self.dscene.zone_count, ua.side(), ub.side())
        bend = self.shift_of(self.mark_ids[3]).x()
        route = connection_route(self._anchor(ua, ida, sa), sa, self._anchor(ub, idb, sb), sb, bend)
        if route == self.poly and not self.path().isEmpty():
            return
        self.poly = route
        path = QPainterPath(QPointF(*route[0]))
        for x, y in route[1:]:
            path.lineTo(x, y)
        self.prepareGeometryChange()
        self.setPath(path)

    def _label_spot(self) -> QPointF:
        """The middle of the longest piece of the line."""
        best, spot = -1.0, QPointF(*self.poly[0])
        for (x0, y0), (x1, y1) in zip(self.poly, self.poly[1:], strict=False):
            length = abs(x1 - x0) + abs(y1 - y0)
            if length > best:
                best, spot = length, QPointF((x0 + x1) / 2, (y0 + y1) / 2)
        return spot

    def boundingRect(self) -> QRectF:
        """The line and the room its labels may take: on the line once the person has put them
        there, and where the tool finds room (up to three steps off the line) until then."""
        return super().boundingRect().adjusted(-REACH_X, -REACH_Y, REACH_X, REACH_Y)

    def shifts_changed(self) -> None:
        self.update_path()  # (the bend moves the line)

    def drag_slots(self) -> list[tuple[str, QRectF, bool]]:
        """What can be dragged, the label and the boxes first (they lie over the line): where each
        is drawn now. The bend is the longest vertical piece of the line, moved across only."""
        label, end_a, end_b, bend = self.mark_ids
        slots = [(label, self._chip, False)]
        slots += [(m, r, False) for m, r in zip((end_a, end_b), self._end_rects, strict=False)]
        pieces = [
            (abs(y1 - y0), QRectF(x0 - HIT_WIDTH / 2, min(y0, y1), HIT_WIDTH, abs(y1 - y0)))
            for (x0, y0), (x1, y1) in zip(self.poly, self.poly[1:], strict=False)
            if x0 == x1 and abs(y1 - y0) > 2 * HIT_WIDTH
        ]
        if pieces:
            slots.append((bend, max(pieces, key=lambda p: p[0])[1], True))
        return slots

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(HIT_WIDTH)
        path = stroker.createStroke(self.path())
        if not self._chip.isEmpty():
            path.addRect(self._chip)
        for rect in self._end_rects:
            path.addRect(rect)
        return path

    # ---- painting ---------------------------------------------------------------------------
    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        sc = self.dscene
        link = sc.ctl.project.links.get(self.link_id)
        if link is None or self.path().isEmpty() or not self.poly:
            return
        th = sc.theme
        selected = sc.ctl.selected_link == self.link_id
        state = sc.states.of("link", self.link_id)
        if selected:
            token, width = "primary", 4.0
        elif state.errors:
            token, width = "error", 3.0
        elif state.warnings:
            token, width = "warning", 3.0
        else:
            token, width = "text-muted", 2.5
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(sc.pen(token, width, Qt.PenStyle.DashDotLine))
        painter.drawPath(self.path())
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        if lod < 0.35 and not selected and not self._hover:
            self._end_rects = []
            return  # from far away the line alone says enough
        font = sc.px_font(th.type("small"))
        painter.setFont(font)
        fm = QFontMetrics(font)
        lines, self._chip, ends = self._boxes(link, fm)
        lines = [
            fm.elidedText(t, Qt.TextElideMode.ElideRight, int(CHIP_MAX_W - 2 * CHIP_PAD_X))
            for t in lines
        ]
        line_h = fm.height()
        painter.setBrush(QBrush(th.color("bg")))
        painter.setPen(sc.pen(token, 3 if selected else 1.5))
        painter.drawRoundedRect(self._chip, 6, 6)
        for k, t in enumerate(lines):
            painter.setPen(th.color("text" if k == 0 else "text-muted"))
            painter.drawText(
                QRectF(
                    self._chip.x(),
                    self._chip.y() + CHIP_PAD_Y + k * line_h,
                    self._chip.width(),
                    line_h,
                ),
                int(Qt.AlignmentFlag.AlignCenter),
                t,
            )
        for rect, texts in ends:
            painter.setBrush(QBrush(th.color("bg")))
            painter.setPen(sc.pen(token, 3 if selected else 1.5))
            painter.drawRoundedRect(rect, 4, 4)
            for k, t in enumerate(texts):
                painter.setPen(th.color("text" if k == 0 else "text-muted"))
                painter.drawText(
                    QRectF(rect.x(), rect.y() + CHIP_PAD_Y + k * line_h, rect.width(), line_h),
                    int(Qt.AlignmentFlag.AlignCenter),
                    t,
                )
        if self.hasFocus():
            painter.setPen(sc.pen("focus", 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self._chip.adjusted(-3, -3, 3, 3), 8, 8)

    def _metrics(self) -> QFontMetrics:
        sc = self.dscene
        return QFontMetrics(sc.px_font(sc.theme.type("small")))

    def _boxes(
        self, link: Link, fm: QFontMetrics, offsets: Mapping[str, QPointF] | None = None
    ) -> tuple[list[str], QRectF, list[tuple[QRectF, list[str]]]]:
        """Where the label and the two connector boxes go: the lines of the label, its box, and
        each connector box with its texts. A box is where the tool puts it (`_auto` keeps that
        place), and, when the person put it somewhere, centred on its place on the line. `offsets`
        (the free offsets of an earlier version) moves the boxes by them instead, to turn them
        into a place on the line."""
        shown = self.ends_shown()
        caption = link.name or link_caption(link)
        lines = [caption] + ([self.text] if self.text else [])
        ends: list[tuple[QRectF, list[str]]] = []
        for mark, (rect, texts) in zip(
            self.mark_ids[1:3],
            self._end_boxes(link, fm) if shown or offsets is not None else [],
            strict=False,
        ):
            self._auto[mark] = rect
            ends.append((self._placed(mark, rect, offsets), texts))
        self._end_rects = [rect for rect, _t in ends] if shown else []
        chip = self._chip_rect(fm, lines)
        self._auto[self.mark_ids[0]] = chip
        return lines, self._placed(self.mark_ids[0], chip, offsets), ends

    def _placed(
        self, mark_id: str, automatic: QRectF, offsets: Mapping[str, QPointF] | None
    ) -> QRectF:
        if offsets is not None:
            return automatic.translated(offsets.get(mark_id, NO_SHIFT))
        return self.on_line(mark_id, automatic)

    def _auto_box(self, mark_id: str) -> QRectF:
        """The box of a label where the tool puts it (worked out now when it was never drawn)."""
        if mark_id not in self._auto:
            link = self.dscene.ctl.project.links.get(self.link_id)
            if link is not None and self.poly:
                self._boxes(link, self._metrics())
        return self._auto.get(mark_id, QRectF())

    def margin_of(self, mark_id: str) -> float:
        gap = END_GAP if mark_id in self.mark_ids[1:3] else LABEL_GAP
        return self._auto_box(mark_id).width() / 2 + gap

    def centre_of(self, mark_id: str) -> QPointF:
        return self.on_line(mark_id, self._auto_box(mark_id)).center()

    def legacy_places(self) -> dict[str, float]:
        """The place on the line of the label and the connector boxes that have a free offset of
        an earlier version: the nearest point of the line to where the offset put each."""
        legacy = self.dscene.legacy_offsets(self.mark_ids)
        link = self.dscene.ctl.project.links.get(self.link_id)
        if not legacy or link is None or len(self.poly) < 2:
            return {}
        self._boxes(link, self._metrics(), legacy)
        out: dict[str, float] = {}
        for mark, off in legacy.items():
            box = self._auto.get(mark)
            if box is not None:
                out[mark] = linepos.from_offset(
                    self.poly, (box.center().x(), box.center().y()), off.x(), off.y()
                )
        return out

    def ends_shown(self) -> bool:
        """The connector boxes are drawn in the Expert mode and when View > Show connectors on
        connections is on."""
        return self.dscene.connection_ends or self.dscene.ctl.mode == "expert"

    def _end_boxes(self, link: Link, fm: QFontMetrics) -> list[tuple[QRectF, list[str]]]:
        """A small box at each end of the line: the connector name, and how many of its pins the
        connection pairs. Drawn beside the edge of the device the line leaves, cut to a width that
        leaves room for the other box, and moved down when the two would touch."""
        line_h = fm.height()
        out: list[tuple[QRectF, list[str]]] = []
        for end, (x, y), toward in zip(
            link_ends(self.dscene.ctl.project, link),
            (self.poly[0], self.poly[-1]),
            (self.poly[1], self.poly[-2]),
            strict=True,
        ):
            pins = end.pins
            second = strings.LINK_END_PINS[0 if pins == 1 else 1].format(end.used, pins)
            room = int(END_MAX_W - 2 * CHIP_PAD_X)
            texts = [
                fm.elidedText(t, Qt.TextElideMode.ElideRight, room) for t in (end.name, second)
            ]
            w = max(fm.horizontalAdvance(t) for t in texts) + 2 * CHIP_PAD_X
            h = 2 * line_h + 2 * CHIP_PAD_Y
            right = toward[0] >= x  # the line leaves towards the right: the box sits to its right
            rect = QRectF(x + END_GAP if right else x - END_GAP - w, y - h / 2, w, h)
            if out and rect.adjusted(-LABEL_GAP, -LABEL_GAP, LABEL_GAP, LABEL_GAP).intersects(
                out[0][0]
            ):
                rect.moveTop(out[0][0].bottom() + LABEL_GAP)
            out.append((rect, texts))
        return out

    def _chip_rect(self, fm: QFontMetrics, lines: list[str]) -> QRectF:
        """Where the label sits: in the middle of the longest piece of the line when that is clear
        of the end boxes and the devices, otherwise the nearest place that is."""
        w = min(CHIP_MAX_W, max(fm.horizontalAdvance(t) for t in lines) + 2 * CHIP_PAD_X)
        h = fm.height() * len(lines) + 2 * CHIP_PAD_Y
        pieces = sorted(
            zip(self.poly, self.poly[1:], strict=False),
            key=lambda ab: -(abs(ab[1][0] - ab[0][0]) + abs(ab[1][1] - ab[0][1])),
        )
        spots = [QPointF((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in pieces]
        around = QRectF(self.path().boundingRect()).adjusted(-CHIP_MAX_W, -60, CHIP_MAX_W, 60)
        avoid = [r.adjusted(-LABEL_GAP, -LABEL_GAP, LABEL_GAP, LABEL_GAP) for r in self._end_rects]
        for item in self.dscene.items(around):
            if getattr(item, "unit_id", None):  # a device card
                avoid.append(
                    item.sceneBoundingRect().adjusted(-LABEL_GAP, -LABEL_GAP, LABEL_GAP, LABEL_GAP)
                )
        return free_rect(QSizeF(w, h), spots, avoid, (w / 2 + LABEL_GAP, h + LABEL_GAP))

    # ---- the pointer ------------------------------------------------------------------------
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.dscene.ctl.tool == "connect":
            event.ignore()  # the Connect tool picks the device under the pointer
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self.dscene.ctl.select_link(self.link_id)
        if event.button() == Qt.MouseButton.LeftButton:
            self.chip_press(event.scenePos())
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        away = event.screenPos() - event.buttonDownScreenPos(Qt.MouseButton.LeftButton)
        if self.chip_move(event.scenePos(), away.manhattanLength()):
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if not self.chip_release():
            super().mouseReleaseEvent(event)
        event.accept()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.dscene.ctl.tool == "select":
            self.dscene.ctl.select_link(self.link_id)
            self.dscene.ctl.request_open("link", self.link_id)
        event.accept()

    def activate(self, *, open_plan: bool = False) -> None:
        """Enter or Space on the focused line: select the connection (Enter also asks for the Link
        connectors window). The view calls this when Space is let go."""
        self.dscene.ctl.select_link(self.link_id)
        if open_plan:
            self.dscene.ctl.request_open("link", self.link_id)

    def keyPressEvent(self, event: object) -> None:
        key = event.key()  # type: ignore[attr-defined]
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activate(open_plan=key != Qt.Key.Key_Space)
            event.accept()  # type: ignore[attr-defined]
            return
        super().keyPressEvent(event)  # type: ignore[arg-type]

    def tooltip_html(self) -> str:
        """Name, the two ends, what the pairs carry, how many pairs, the harness made from it and
        what the review says (rich text)."""
        project = self.dscene.ctl.project
        link = project.links.get(self.link_id)
        if link is None:
            return ""
        st = self.dscene.states.of("link", self.link_id)
        rows = [
            (strings.LINK_TIP_ENDS, link_caption(link)),
            (strings.LINK_TIP_PAIRS, str(len(link.pairs))),
        ]
        if self.text:
            rows.append((strings.LINK_TIP_CARRIES, self.text))
        rows.append(
            (
                strings.LINK_TIP_HARNESS,
                link.harness_id or strings.LINK_TIP_NO_HARNESS,
            )
        )
        path = link_path(project, link)
        if path:
            rows.append((strings.LINK_TIP_PATH, " - ".join(path)))
        says = st.sentence()
        if says:
            rows.append((strings.LINK_TIP_CHECKS, says))
        body = "".join(
            f"<tr><td style='padding-right:8px'><b>{html.escape(k)}</b></td>"
            f"<td>{html.escape(v)}</td></tr>"
            for k, v in rows
        )
        head = f"<b>{html.escape(link.name or link.id)}</b> ({html.escape(link.id)})"
        return f"{head}<table>{body}</table><i>{html.escape(strings.LINK_TIP_OPEN)}</i>"

    def hoverEnterEvent(self, event: object) -> None:
        self.setToolTip(self.tooltip_html())
        self._hover = True
        self.update()

    def hoverMoveEvent(self, event: object) -> None:
        self.show_cursor_at(event.scenePos())  # type: ignore[attr-defined]

    def hoverLeaveEvent(self, event: object) -> None:
        self._hover = False
        self.unsetCursor()
        self.update()


def derived_texts(project: Project) -> dict[str, str]:
    """For each link, what its pairs carry in one line ("CAN, 2 wires; Primary power, 2 wires")."""
    out: dict[str, list[str]] = {}
    for d in derived_interfaces(project):
        out.setdefault(d.link_id, []).append(d.label)
    return {k: "; ".join(v) for k, v in out.items()}


__all__ = ["ConnectionItem", "connection_route", "derived_texts", "sides"]
