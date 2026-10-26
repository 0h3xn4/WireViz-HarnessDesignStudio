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
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QPainter, QPainterPath, QPainterPathStroker
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from harness_design_studio.core import routing
from harness_design_studio.core.links import (
    derived_interfaces,
    link_caption,
    link_ends,
    link_path,
)
from harness_design_studio.core.model import Link, Project
from harness_design_studio.gui import strings

if TYPE_CHECKING:
    from harness_design_studio.gui.canvas import DiagramScene, UnitItem

OUT = 36.0  # how far a line leaves a device before it turns
HIT_WIDTH = 12.0  # how wide a click on the line still counts
CHIP_PAD_X = 8.0
CHIP_PAD_Y = 3.0
END_GAP = 4.0  # between the edge of a device and the box of its connector


def connection_route(
    a: tuple[float, float], side_a: str, b: tuple[float, float], side_b: str
) -> list[tuple[float, float]]:
    """The corners of a line from point `a` (on the `side_a` edge of its device, "left" or
    "right") to point `b`. Facing edges (right of the left device, left of the right one) meet in
    the gap between the devices; any other pair of edges goes round: out of both edges by `OUT`
    and across at the height between the two points."""
    (xa, ya), (xb, yb) = a, b
    if side_a == "right" and side_b == "left" and xb > xa:
        mid = (xa + xb) / 2
        return [a, (mid, ya), (mid, yb), b]
    if side_a == "left" and side_b == "right" and xb < xa:
        mid = (xa + xb) / 2
        return [a, (mid, ya), (mid, yb), b]
    out_a = xa + OUT if side_a == "right" else xa - OUT
    out_b = xb + OUT if side_b == "right" else xb - OUT
    if side_a == side_b:  # one channel for both ends, clear of both devices
        out_a = out_b = max(out_a, out_b) if side_a == "right" else min(out_a, out_b)
        return [a, (out_a, ya), (out_a, yb), b]
    mid_y = (ya + yb) / 2
    return [a, (out_a, ya), (out_a, mid_y), (out_b, mid_y), (out_b, yb), b]


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


class ConnectionItem(QGraphicsPathItem):
    """The drawn line and label of one `Link`."""

    def __init__(self, scene: "DiagramScene", link_id: str, unit_w: float) -> None:
        super().__init__()
        self.dscene = scene
        self.link_id = link_id
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
    def _ends(self) -> tuple["UnitItem", "UnitItem", str, str] | None:
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

    def _anchor(self, unit: "UnitItem", connector_id: str, side: str) -> tuple[float, float]:
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
        route = connection_route(self._anchor(ua, ida, sa), sa, self._anchor(ub, idb, sb), sb)
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
        return super().boundingRect().adjusted(-160, -30, 160, 30)

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
        caption = link.name or link_caption(link)
        lines = [caption] + ([self.text] if self.text else [])
        text_w = max(sc.text_width(font, t) for t in lines)
        line_h = painter.fontMetrics().height()
        w = text_w + 2 * CHIP_PAD_X
        h = line_h * len(lines) + 2 * CHIP_PAD_Y
        c = self._label_spot()
        self._chip = QRectF(c.x() - w / 2, c.y() - h / 2, w, h)
        painter.setBrush(QBrush(th.color("bg")))
        painter.setPen(sc.pen(token, 3 if selected else 1.5))
        painter.drawRoundedRect(self._chip, 6, 6)
        painter.setPen(th.color("text"))
        for k, t in enumerate(lines):
            painter.setPen(th.color("text" if k == 0 else "text-muted"))
            painter.drawText(
                QRectF(self._chip.x(), self._chip.y() + CHIP_PAD_Y + k * line_h, w, line_h),
                int(Qt.AlignmentFlag.AlignCenter),
                t,
            )
        self._paint_ends(painter, link, token, selected)
        if self.hasFocus():
            painter.setPen(sc.pen("focus", 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self._chip.adjusted(-3, -3, 3, 3), 8, 8)

    def ends_shown(self) -> bool:
        """The connector boxes are drawn in the Expert mode and when View > Show connectors on
        connections is on."""
        return self.dscene.connection_ends or self.dscene.ctl.mode == "expert"

    def _paint_ends(self, painter: QPainter, link: Link, token: str, selected: bool) -> None:
        """A small box at each end of the line: the connector name, and how many of its pins the
        connection pairs. Drawn beside the edge of the device the line leaves."""
        if not self.ends_shown():
            self._end_rects = []
            return
        sc = self.dscene
        th = sc.theme
        font = sc.px_font(th.type("small"))
        painter.setFont(font)
        line_h = painter.fontMetrics().height()
        rects: list[QRectF] = []
        for end, (x, y), toward in zip(
            link_ends(sc.ctl.project, link),
            (self.poly[0], self.poly[-1]),
            (self.poly[1], self.poly[-2]),
            strict=True,
        ):
            pins = end.pins
            second = strings.LINK_END_PINS[0 if pins == 1 else 1].format(end.used, pins)
            text_w = max(sc.text_width(font, end.name), sc.text_width(font, second))
            w, h = text_w + 2 * CHIP_PAD_X, 2 * line_h + 2 * CHIP_PAD_Y
            right = toward[0] >= x  # the line leaves towards the right: the box sits to its right
            rect = QRectF(x + END_GAP if right else x - END_GAP - w, y - h / 2, w, h)
            rects.append(rect)
            painter.setBrush(QBrush(th.color("bg")))
            painter.setPen(sc.pen(token, 3 if selected else 1.5))
            painter.drawRoundedRect(rect, 4, 4)
            for k, t in enumerate((end.name, second)):
                painter.setPen(th.color("text" if k == 0 else "text-muted"))
                painter.drawText(
                    QRectF(rect.x(), rect.y() + CHIP_PAD_Y + k * line_h, w, line_h),
                    int(Qt.AlignmentFlag.AlignCenter),
                    t,
                )
        self._end_rects = rects

    # ---- the pointer ------------------------------------------------------------------------
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.dscene.ctl.tool == "connect":
            event.ignore()  # the Connect tool picks the device under the pointer
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self.dscene.ctl.select_link(self.link_id)
        event.accept()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.dscene.ctl.tool == "select":
            self.dscene.ctl.select_link(self.link_id)
            self.dscene.ctl.request_open("link", self.link_id)
        event.accept()

    def keyPressEvent(self, event: object) -> None:
        key = event.key()  # type: ignore[attr-defined]
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.dscene.ctl.select_link(self.link_id)
            if key != Qt.Key.Key_Space:
                self.dscene.ctl.request_open("link", self.link_id)
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

    def hoverLeaveEvent(self, event: object) -> None:
        self._hover = False
        self.update()


def derived_texts(project: Project) -> dict[str, str]:
    """For each link, what its pairs carry in one line ("CAN, 2 wires; Primary power, 2 wires")."""
    out: dict[str, list[str]] = {}
    for d in derived_interfaces(project):
        out.setdefault(d.link_id, []).append(d.label)
    return {k: "; ".join(v) for k, v in out.items()}


__all__ = ["ConnectionItem", "connection_route", "derived_texts", "sides"]
