"""Block-diagram canvas: zone lanes, unit boxes, interface links, minimap."""

import math

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QLabel,
    QStyleOptionGraphicsItem,
    QToolTip,
    QWidget,
)

from harness_design_studio.core import describe, edit, routing
from harness_design_studio.gui import glyphs, strings
from harness_design_studio.gui.controller import Delta, EditorController
from harness_design_studio.gui.theme import ThemeManager
from harness_design_studio.gui.tokens import CATEGORIES, style_category

W = edit.UNIT_W
HEADER_H = 30
PORT_ROW = edit.PORT_ROW
GRID = 10


def facing_side(lane: int, lanes: int) -> str:
    """Connectors sit on the edge that faces the middle of the diagram."""
    return "right" if lane <= (lanes - 1) // 2 else "left"


class UnitItem(QGraphicsItem):
    def __init__(self, scene: "DiagramScene", unit_id: str) -> None:
        super().__init__()
        self.dscene = scene
        self.unit_id = unit_id
        self._press_pos: QPointF | None = None
        self._moved = False
        self._lane_key: tuple[float, int] | None = None
        self._lane = 0
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(2)

    # ---- geometry ---------------------------------------------------------------------------
    @property
    def ctl(self) -> EditorController:
        return self.dscene.ctl

    def connectors(self) -> list:  # type: ignore[type-arg]
        return edit.unit_connectors(self.ctl.project, self.unit_id)

    def height(self) -> float:
        if self.ctl.mode == "expert":
            return edit.expert_height(len(self.connectors()))
        return edit.guided_height(len(self.dscene.adjacent(self.unit_id)))

    def lane(self) -> int:
        key = (self.pos().x(), self.dscene.zone_count)
        if self._lane_key != key:
            self._lane_key = key
            self._lane = edit.lane_index(key[1], key[0])
        return self._lane

    def side(self) -> str:
        return facing_side(self.lane(), self.dscene.zone_count)

    def boundingRect(self) -> QRectF:
        return QRectF(-14, -30, W + 28, self.height() + 70)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(QRectF(-8, 0, W + 16, self.height()))
        return path

    def port_y(self, index: int) -> float:
        return 46 + index * PORT_ROW + PORT_ROW / 2 - 4

    def link_side(self, interface_id: str) -> str:
        """The edge a link leaves from: the one that faces the unit at its other end, so a link
        never runs through its own unit."""
        other = self.dscene.partner_item(self.unit_id, interface_id)
        if other is None:
            return self.side()
        within = routing.same_lane_side(self.lane(), self.dscene.zone_count, self.side())
        return routing.side_toward(self.lane(), other.lane(), within)

    def port_side(self, connector_id: str) -> str:
        """The edge a connector is drawn on: where its link leaves, else the lane's default edge."""
        iid = self.dscene.connector_link(connector_id)
        return self.link_side(iid) if iid is not None else self.side()

    def port_rect(self, index: int, connector_id: str | None = None) -> QRectF:
        if connector_id is None:
            conns = self.connectors()
            connector_id = str(conns[index].id) if 0 <= index < len(conns) else ""
        x = W - 7 if self.port_side(connector_id) == "right" else -7
        return QRectF(x, self.port_y(index) - 7, 14, 14)

    def port_at(self, pos: QPointF) -> str | None:
        if self.ctl.mode != "expert":
            return None
        for k, c in enumerate(self.connectors()):
            if self.port_rect(k, str(c.id)).adjusted(-6, -4, 6, 4).contains(pos) or QRectF(
                0, self.port_y(k) - 11, W, 22
            ).contains(pos):
                return str(c.id)
        return None

    def anchor(
        self, connector_id: str | None, interface_id: str, side: str | None = None
    ) -> QPointF:
        side = side or self.link_side(interface_id)
        x = self.pos().x() + (W if side == "right" else 0)
        h = self.height()
        if self.ctl.mode == "expert" and connector_id is not None:
            ids = [c.id for c in self.connectors()]
            if connector_id in ids:
                return QPointF(x, self.pos().y() + self.port_y(ids.index(connector_id)))
        _, k, count = self.dscene.slot(self.unit_id, interface_id)
        slot = (h - 44) / max(1, count)
        # links on a right edge sit a little lower than links on a left edge, so that two rows of
        # level units never put a link of one on the line of a link of the other
        shift = 5.0 if side == "right" else 0.0
        return QPointF(x, self.pos().y() + 36 + (k + 0.5) * slot + shift)

    # ---- state shown on the item ------------------------------------------------------------
    def _compat_reason(self) -> tuple[str, str]:
        """(state, reason): state is 'from', 'ok', 'no' or '' when the connect tool is idle."""
        ctl = self.ctl
        if ctl.tool != "connect" or ctl.connect_type is None:
            return "", ""
        if ctl.connect_from and ctl.connect_from.unit_id == self.unit_id:
            return "from", ""
        if ctl.mode == "guided":
            c = ctl.unit_compat(self.unit_id)
            return ("ok", "") if c.ok else ("no", c.short or c.why)
        if ctl.unit_has_valid_connector(self.unit_id):
            return "ok", ""
        name = ctl.project.interface_types[ctl.connect_type].name
        return "no", f"No free {name} connector"

    def _auto_connectors(self) -> set[str]:
        out: set[str] = set()
        for i in self.ctl.project.interfaces.values():
            out.update(
                e.connector_id
                for e in i.endpoints
                if e.auto and e.unit_id == self.unit_id and e.connector_id
            )
        return out

    # ---- painting ---------------------------------------------------------------------------
    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        th = self.dscene.theme
        ctl = self.ctl
        unit = ctl.project.units.get(self.unit_id)
        if unit is None:
            return
        state, reason = self._compat_reason()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        if option.levelOfDetailFromTransform(painter.worldTransform()) < 0.45 and not reason:
            self._paint_overview(painter, th, unit, state)
            return
        selected = (
            ctl.selection is not None
            and ctl.selection.kind == "unit"
            and ctl.selection.id == self.unit_id
        )
        faded = state == "no"
        base = painter.opacity()  # the item's own opacity (a filter or a focus fades the unit)
        painter.setOpacity(base * (0.55 if faded else 1.0))
        body = QRectF(0, 0, W, h)
        pen = QPen(th.color("border"), 2)
        if unit.side == "redundant":
            pen.setStyle(Qt.PenStyle.DashLine)
        if state == "ok":
            pen = QPen(th.color("primary"), 3)
        if state == "from":
            pen = QPen(th.color("primary"), 4, Qt.PenStyle.DashLine)
        if selected:
            pen = QPen(th.color("primary"), 4, pen.style())
        painter.setPen(pen)
        painter.setBrush(QBrush(th.color("surface")))
        painter.drawRoundedRect(body, 8, 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(th.color("surface-2")))
        painter.drawRoundedRect(QRectF(1, 1, W - 2, HEADER_H), 7, 7)
        painter.drawRect(QRectF(1, HEADER_H - 8, W - 2, 9))
        bold = QFont(painter.font())
        bold.setBold(True)
        small = QFont(painter.font())
        small.setPixelSize(th.px(11))
        painter.setFont(bold)
        painter.setPen(th.color("text"))
        painter.drawText(QRectF(10, 0, W - 80, HEADER_H), Qt.AlignmentFlag.AlignVCenter, unit.id)
        painter.setFont(small)
        painter.setPen(th.color("text-muted"))
        tag = (
            "FROM" if state == "from" else ("REDUNDANT" if unit.side == "redundant" else "NOMINAL")
        )
        painter.drawText(
            QRectF(W - 90, 0, 80, HEADER_H),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            tag,
        )
        if ctl.mode == "expert":
            self._paint_halves(painter, th, h)
            self._paint_ports(painter, small, th, state)
        else:
            painter.drawText(
                QRectF(10, 34, W - 20, 16),
                Qt.AlignmentFlag.AlignVCenter,
                QFontMetrics(small).elidedText(unit.name, Qt.TextElideMode.ElideRight, int(W - 20)),
            )
            self._paint_connector_row(painter, small, th)
        painter.setOpacity(base)
        if reason:
            painter.setPen(th.color("error"))
            painter.setFont(bold)
            painter.drawText(
                QRectF(0, h + 4, W + 12, 36),
                Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                f"✕ {reason}",
            )
        mark = ctl.diff_marks.get(self.unit_id)
        if mark:
            painter.setPen(QPen(th.color("warning"), 5, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(body.adjusted(-7, -7, 7, 7), 12, 12)
            painter.setFont(bold)
            painter.setPen(th.color("warning"))
            painter.drawText(QRectF(0, -24, W, 16), Qt.AlignmentFlag.AlignRight, mark.upper())
        if self.hasFocus():
            painter.setPen(QPen(th.color("focus"), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(body.adjusted(-4, -4, 4, 4), 10, 10)

    def _paint_halves(self, painter: QPainter, th: ThemeManager, h: float) -> None:
        """Expert mode: a line down the middle splits the unit into the left side (ports on the
        left edge) and the right side (ports on the right edge), the right one a little darker."""
        painter.setPen(Qt.PenStyle.NoPen)
        tint = QColor(th.color("surface-2"))
        tint.setAlpha(110)
        painter.setBrush(QBrush(tint))
        painter.drawRect(QRectF(W / 2, HEADER_H, W / 2 - 1, h - HEADER_H - 1))
        painter.setPen(QPen(th.color("border"), 1.2, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(W / 2, HEADER_H + 4), QPointF(W / 2, h - 5))

    def _paint_connector_row(self, painter: QPainter, small: QFont, th: ThemeManager) -> None:
        """Guided mode: the unit's connectors as little pictures (the same ones are counted)."""
        project = self.ctl.project
        counts: dict[tuple[str, int, str], int] = {}
        for c in self.connectors():
            key = describe.connector_family(project, str(c.id))
            counts[key] = counts.get(key, 0) + 1
        x = 10.0
        for (family, pins, gender), n in counts.items():
            if x + glyphs.CONNECTOR_W * 0.75 + (16 if n > 1 else 0) > W - 8:
                break  # no room for more: the unit's properties list them all
            glyphs.draw_connector(
                painter, x, 51, family, pins, gender, th.color("text"), th.color("surface"), 0.75
            )
            x += glyphs.CONNECTOR_W * 0.75 + 1
            if n > 1:
                painter.setPen(th.color("text-muted"))
                painter.drawText(QRectF(x, 50, 18, 20), Qt.AlignmentFlag.AlignVCenter, f"×{n}")
                x += 16
            x += 4

    def _paint_overview(
        self, painter: QPainter, th: ThemeManager, unit: object, state: str
    ) -> None:
        """Zoomed far out: a plain box and the ID only (fast for diagrams with hundreds of units)."""
        selected = (
            self.ctl.selection is not None
            and self.ctl.selection.kind == "unit"
            and self.ctl.selection.id == self.unit_id
        )
        pen = QPen(
            th.color("primary") if selected or state in ("ok", "from") else th.color("border"),
            4 if selected else 2,
        )
        painter.setPen(pen)
        painter.setBrush(QBrush(th.color("surface")))
        painter.drawRect(QRectF(0, 0, W, self.height()))
        font = QFont(painter.font())
        font.setBold(True)
        font.setPixelSize(22)
        painter.setFont(font)
        painter.setPen(th.color("text"))
        painter.drawText(
            QRectF(8, 0, W - 16, self.height()), Qt.AlignmentFlag.AlignVCenter, self.unit_id
        )

    def _paint_ports(self, painter: QPainter, small: QFont, th: ThemeManager, state: str) -> None:
        ctl = self.ctl
        auto = self._auto_connectors()
        painter.setFont(small)
        for k, c in enumerate(self.connectors()):
            rect = self.port_rect(k, str(c.id))
            right = self.port_side(str(c.id)) == "right"
            compat = (
                ctl.connector_compat(c.id)
                if state in ("ok", "no", "from") and ctl.connect_type
                else None
            )
            valid = bool(compat and compat.ok and state != "from")
            pen = QPen(th.color("border"), 2)
            if c.id in auto:
                pen = QPen(th.color("auto-fill"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QBrush(th.color("primary") if valid else th.color("bg")))
            painter.drawRoundedRect(rect, 3, 3)
            painter.setPen(
                th.color("text") if (compat is None or valid) else th.color("text-muted")
            )
            y = self.port_y(k)
            family, pins, gender = describe.connector_family(ctl.project, str(c.id))
            muted = compat is not None and not valid
            ink = th.color("text-muted") if muted else th.color("text")
            # from the edge inwards: the designator, the connector, the pin count; glyphs.port_row
            # keeps every part inside its half. What a link carries is drawn on the link.
            row = glyphs.port_row(W, right, pins > 1)
            align = Qt.AlignmentFlag.AlignVCenter | (
                Qt.AlignmentFlag.AlignRight if right else Qt.AlignmentFlag.AlignLeft
            )
            painter.setPen(ink)
            painter.drawText(QRectF(row["name"][0], y - 9, glyphs.ROW_NAME_W, 18), align, c.name)
            glyphs.draw_connector(
                painter, row["connector"][0], y - glyphs.CONNECTOR_H / 2, family, pins, gender, ink, th.color("surface")
            )  # fmt: skip
            if pins > 1:
                painter.drawText(
                    QRectF(row["count"][0], y - 9, glyphs.ROW_COUNT_W, 18), align, str(pins)
                )

    # ---- interaction ------------------------------------------------------------------------
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        ctl = self.ctl
        self.setFocus()
        if ctl.tool == "connect":
            ctl.pick(self.unit_id, self.port_at(event.pos()))
            event.accept()
            return
        ctl.select("unit", self.unit_id)
        self._press_pos = self.pos()
        self._moved = False
        if ctl.read_only:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        if self._press_pos is not None and self.pos() != self._press_pos and not self.ctl.read_only:
            self.ctl.move_unit(self.unit_id, self.pos().x(), self.pos().y())
        self._press_pos = None

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: object) -> object:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and isinstance(
            value, QPointF
        ):
            if self.ctl.read_only and self._press_pos is not None:
                return self._press_pos
            return QPointF(round(value.x() / GRID) * GRID, round(value.y() / GRID) * GRID)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.dscene.relink(self.unit_id)
        return super().itemChange(change, value)

    def hoverMoveEvent(self, event: object) -> None:
        _, reason = self._compat_reason()
        tip = reason
        if self.ctl.mode == "expert" and self.ctl.tool == "connect" and self.ctl.connect_type:
            cid = self.port_at(event.pos())  # type: ignore[attr-defined]
            if cid:
                c = self.ctl.connector_compat(cid)
                tip = "" if c.ok else c.why
        if tip:
            QToolTip.showText(event.screenPos(), tip)  # type: ignore[attr-defined]
        else:
            u = self.ctl.project.units.get(self.unit_id)
            self.setToolTip(f"{u.id}: {u.name}" if u else "")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        ctl = self.ctl
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if ctl.tool == "connect":
                ctl.pick(self.unit_id, self._first_valid_port())
            else:
                ctl.select("unit", self.unit_id)
            event.accept()
            return
        nudge = {
            Qt.Key.Key_Left: (-GRID, 0),
            Qt.Key.Key_Right: (GRID, 0),
            Qt.Key.Key_Up: (0, -GRID),
            Qt.Key.Key_Down: (0, GRID),
        }
        if (
            key in nudge
            and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            and ctl.tool == "select"
            and not ctl.read_only
        ):
            dx, dy = nudge[key]  # type: ignore[index]
            ctl.move_unit(self.unit_id, self.pos().x() + dx, self.pos().y() + dy)
            event.accept()
            return
        super().keyPressEvent(event)

    def _first_valid_port(self) -> str | None:
        if self.ctl.mode != "expert":
            return None
        return next((c.id for c in self.connectors() if self.ctl.connector_compat(c.id).ok), None)


def rounded_path(points: list[tuple[float, float]], radius: float = 8.0) -> QPainterPath:
    """A path through the corner points of a route with softly rounded corners."""
    path = QPainterPath(QPointF(*points[0]))
    for k in range(1, len(points) - 1):
        (x0, y0), (x1, y1), (x2, y2) = points[k - 1], points[k], points[k + 1]
        d_in, d_out = math.hypot(x1 - x0, y1 - y0), math.hypot(x2 - x1, y2 - y1)
        r = min(radius, d_in / 2, d_out / 2)
        if r <= 0:
            path.lineTo(x1, y1)
            continue
        path.lineTo(x1 - (x1 - x0) / d_in * r, y1 - (y1 - y0) / d_in * r)
        path.quadTo(x1, y1, x1 + (x2 - x1) / d_out * r, y1 + (y2 - y1) / d_out * r)
    path.lineTo(*points[-1])
    return path


class LinkItem(QGraphicsPathItem):
    def __init__(self, scene: "DiagramScene", interface_id: str) -> None:
        super().__init__()
        self.dscene = scene
        self.interface_id = interface_id
        self._chip = QRectF()
        self._chip_placed = False
        self.ends: QLineF | None = None  # straight line between the two anchors (for the map)
        self.poly: list[tuple[float, float]] = []  # the corners of the route now drawn
        self._hover = False
        self.setZValue(1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setAcceptHoverEvents(True)

    def update_path(self) -> bool:
        """Take the route the scene worked out for this link and the label spot. Returns False (and
        leaves the item alone, so it is not repainted) when nothing changed: renaming a unit must
        not repaint its links."""
        if self.dscene._batch:  # the scene redraws every changed link once the batch is done
            return False
        route = self.dscene.route(self.interface_id)
        if len(route) < 2:
            self.poly = []
            if not self.path().isEmpty():
                self.prepareGeometryChange()
                self.setPath(QPainterPath())
            self.ends = None
            return True
        self.poly = route
        self.ends = QLineF(QPointF(*route[0]), QPointF(*route[-1]))
        path = rounded_path(route)
        if path == self.path() and self._chip_placed:
            return False
        self.prepareGeometryChange()
        self.setPath(path)
        i = self.dscene.ctl.project.interfaces.get(self.interface_id)
        name = i.id if i is not None else self.interface_id
        width = self._chip_width(len(describe.link_values(self.dscene.ctl.project, name)) * 6.5)
        spots = self._label_spots(route, width + 12)
        center = spots[0] if spots else path.pointAtPercent(0.5)
        for spot in spots:  # the first spot on a straight piece where the label overlaps nothing
            if self.dscene.chip_free(QRectF(spot.x() - width / 2, spot.y() - 11, width, 22), name):
                center = spot
                break
        self._chip_center = center
        self._chip_placed = True
        self.dscene.chip_place(name, QRectF(center.x() - width / 2, center.y() - 11, width, 22))
        return True

    @staticmethod
    def _chip_width(text_w: float) -> float:
        """A chip is the picture of the link kind, and the numbers when there are any."""
        return 30.0 + (text_w + 6 if text_w else 0.0)

    @staticmethod
    def _label_spots(route: list[tuple[float, float]], need: float) -> list[QPointF]:
        """Where a label can sit: the middle of a horizontal piece long enough to hold it, the
        pieces nearest the end first; then the middle of a vertical piece of some length."""
        pieces = list(zip(route, route[1:], strict=False))[::-1]
        mid = [QPointF((p[0] + q[0]) / 2, (p[1] + q[1]) / 2) for p, q in pieces]
        wide = [
            m
            for m, (p, q) in zip(mid, pieces, strict=True)
            if p[1] == q[1] and abs(q[0] - p[0]) >= need
        ]
        tall = [
            m
            for m, (p, q) in zip(mid, pieces, strict=True)
            if p[0] == q[0] and abs(q[1] - p[1]) >= 28
        ]
        return wide + tall

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(14)
        return stroker.createStroke(self.path())

    def boundingRect(self) -> QRectF:
        return super().boundingRect().adjusted(-120, -20, 120, 20)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        ctl = self.dscene.ctl
        th = self.dscene.theme
        i = ctl.project.interfaces.get(self.interface_id)
        if i is None or self.path().isEmpty():
            return
        t = ctl.project.interface_types.get(i.type_id)
        cat = style_category(t.category if t else "data")
        info = CATEGORIES[cat]
        color = th.color(f"cat-{cat}")
        selected = (
            ctl.selection is not None
            and ctl.selection.kind == "interface"
            and ctl.selection.id == i.id
        )
        far = option.levelOfDetailFromTransform(painter.worldTransform()) < 0.5 and not selected
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, not far)
        marked = i.id in ctl.diff_marks
        if marked:  # a wide, dotted halo in the warning colour (not colour alone: also dotted)
            halo = QPen(th.color("warning"), float(info["weight"]) + 8, Qt.PenStyle.DotLine)
            painter.setPen(halo)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.path())
        # (a faded link is drawn as one line: nobody sees the gap, and it halves the paint)
        twin = (
            not far
            and self.opacity() >= 0.5
            and t is not None
            and any(sig.pair for sig in t.signals)
        )
        pen = QPen(color, float(info["weight"]) + (2 if selected else 0) + (3.0 if twin else 0.0))
        if i.redundancy == "redundant":
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())
        if twin:  # the gap between the two lines
            gap = QPen(th.color("bg"), 1.4)
            gap.setStyle(pen.style())
            painter.setPen(gap)
            painter.drawPath(self.path())
        if far or self.opacity() < 0.5:
            return  # zoomed out or faded: the line only, no label
        c = self._chip_center
        font = QFont(painter.font())
        font.setPixelSize(th.px(11))
        values = (
            describe.link_values(ctl.project, i.id)
            if self.dscene.label_full(i.id, self._hover)
            else ""
        )
        text_w = QFontMetrics(font).horizontalAdvance(values) if values else 0
        width = self._chip_width(text_w)
        rect = QRectF(c.x() - width / 2, c.y() - 11, width, 22)
        self._chip = rect
        painter.setBrush(QBrush(th.color("bg")))
        painter.setPen(QPen(color, 3 if selected else 2))
        painter.drawRoundedRect(rect, 11, 11)
        glyphs.draw_link_glyph(
            painter, rect.x() + 6, rect.y() + 4, i.type_id, t.category if t else "data", color
        )
        if values:
            painter.setFont(font)
            painter.setPen(th.color("text"))
            painter.drawText(
                QRectF(rect.x() + 26, rect.y(), text_w + 4, 22),
                Qt.AlignmentFlag.AlignVCenter,
                values,
            )
        if self.hasFocus():
            painter.setPen(QPen(th.color("focus"), 3))
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 13, 13)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.dscene.ctl.tool == "connect":
            event.ignore()
            return
        self.setFocus()
        self.dscene.ctl.select("interface", self.interface_id)
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.dscene.ctl.select("interface", self.interface_id)
            event.accept()
            return
        super().keyPressEvent(event)

    def hoverEnterEvent(self, event: object) -> None:
        project = self.dscene.ctl.project
        i = project.interfaces.get(self.interface_id)
        if i is not None:
            ends = " ↔ ".join(e.unit_id for e in i.endpoints)
            self.setToolTip(f"{i.name} ({i.id})\n{describe.link_caption(project, i.id)}\n{ends}")
        if not self._hover:
            self._hover = True
            self.update()

    def hoverLeaveEvent(self, event: object) -> None:
        if self._hover:
            self._hover = False
            self.update()


class ZoneItem(QGraphicsItem):
    def __init__(self, scene: "DiagramScene", index: int) -> None:
        super().__init__()
        self.dscene = scene
        self.index = index
        self.setZValue(-10)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, edit.LANE_WIDTH - 10, self.dscene.lane_height)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        th = self.dscene.theme
        zones = edit.effective_zones(self.dscene.ctl.project)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(th.color("surface-2"), 1))
        fill = QColor(th.color("surface"))
        fill.setAlpha(150)
        painter.setBrush(QBrush(fill))
        painter.drawRoundedRect(self.boundingRect(), 8, 8)
        font = QFont(painter.font())
        font.setBold(True)
        font.setPixelSize(th.px(12))
        painter.setFont(font)
        painter.setPen(th.color("text-muted"))
        name = zones[self.index].upper() if self.index < len(zones) else ""
        painter.drawText(QRectF(10, 4, 300, 20), Qt.AlignmentFlag.AlignVCenter, name)


class DiagramScene(QGraphicsScene):
    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl = ctl
        self.theme = theme
        self.unit_items: dict[str, UnitItem] = {}
        self.link_items: dict[str, LinkItem] = {}
        self._chips: dict[tuple[int, int], list[tuple[str, QRectF]]] = {}
        self._chip_rects: dict[str, QRectF] = {}
        self.zone_items: list[ZoneItem] = []
        self.lane_height = 700.0
        self._adj: dict[str, list[str]] = {}
        self._order: dict[str, int] = {}
        self.zone_count = len(edit.effective_zones(ctl.project))
        self._last_sel: object = None
        self._conn_link: dict[str, str] = {}  # box connector ID -> the interface that uses it
        self._slots: dict[str, dict[str, tuple[str, int, int]]] = {}
        self._routes: dict[str, list[tuple[float, float]]] | None = None
        self._batch = 0  # while above 0, routes are worked out once at the end
        self._focus_cache: tuple[object, tuple[set[str], set[str]] | None] | None = None
        self._route_key: object = None  # what the cached routes were worked out from
        self._route_cache: dict[str, list[tuple[float, float]]] | None = None
        self._routes_stale = False
        self.filter: tuple[str, str] | None = None  # view state, not part of the project
        ctl.changed.connect(self.apply)
        ctl.selectionChanged.connect(self._on_selection)
        ctl.marksChanged.connect(self.refresh_all)
        ctl.connectChanged.connect(self._repaint_units)
        ctl.modeChanged.connect(self.refresh_all)
        theme.changed.connect(lambda: self.update())
        self.rebuild()

    def adjacent(self, unit_id: str) -> list[str]:
        return self._adj.get(unit_id, [])

    def connector_link(self, connector_id: str) -> str | None:
        return self._conn_link.get(connector_id)

    def partner_item(self, unit_id: str, interface_id: str) -> "UnitItem | None":
        other = routing.partner(self.ctl.project, interface_id, unit_id)
        return self.unit_items.get(other) if other is not None else None

    def slots(self, unit_id: str) -> dict[str, tuple[str, int, int]]:
        """For every link of a unit: (edge, position among the links on that edge, their number).
        The links on one edge are ordered by the height of their other ends, so they do not cross."""
        got = self._slots.get(unit_id)
        if got is None:
            got = {}
            item = self.unit_items.get(unit_id)
            if item is not None:
                by_edge: dict[str, list[tuple[str, float]]] = {"left": [], "right": []}
                for iid in self._adj.get(unit_id, []):
                    other = self.partner_item(unit_id, iid)
                    y = other.pos().y() if other is not None else item.pos().y()
                    by_edge[item.link_side(iid)].append((iid, y))
                for edge, links in by_edge.items():
                    ordered = routing.order_links(links)
                    for k, iid in enumerate(ordered):
                        got[iid] = (edge, k, len(ordered))
            self._slots[unit_id] = got
        return got

    def slot(self, unit_id: str, interface_id: str) -> tuple[str, int, int]:
        return self.slots(unit_id).get(interface_id, ("right", 0, 1))

    # ---- routes: all links are routed together, so that they can share trunks -----------------
    def route(self, interface_id: str) -> list[tuple[float, float]]:
        if self._routes is None:
            self._routes = self._compute_routes()
        return self._routes.get(interface_id, [])

    def _geometry(self) -> routing.Geometry:
        lanes: dict[int, list[UnitItem]] = {}
        for it in self.unit_items.values():
            lanes.setdefault(it.lane(), []).append(it)
        edges: dict[int, tuple[float, float]] = {}
        blocks: dict[int, list[tuple[float, float]]] = {}
        for k in range(self.zone_count):
            items = lanes.get(k, [])
            if items:
                edges[k] = (min(i.pos().x() for i in items), max(i.pos().x() + W for i in items))
                blocks[k] = sorted((i.pos().y(), i.pos().y() + i.height()) for i in items)
            else:
                edges[k] = (edit.lane_x(k), edit.lane_x(k) + W)
                blocks[k] = []
        gaps: dict[int, tuple[float, float]] = {}
        for k in range(self.zone_count - 1):
            lo, hi = edges[k][1], edges[k + 1][0]
            if hi - lo < 40:  # units pushed against each other: keep a little room for the links
                lo, hi = (lo + hi) / 2 - 20, (lo + hi) / 2 + 20
            gaps[k] = (lo, hi)
        return routing.Geometry(gaps, edges, blocks)

    def _routes_key(self) -> object:
        """Everything the routes depend on: where the units are, how tall, the links (type,
        redundancy, ends) and the edge each leaves from. Cheap to build, so that an edit that
        changes none of it (a rename, a note, a voltage) does not work the routes out again."""
        links = tuple(
            (i.id, i.type_id, i.redundancy, tuple((e.unit_id, e.connector_id) for e in i.endpoints))
            for i in sorted(self.ctl.project.interfaces.values(), key=lambda x: x.id)
        )
        return (self._geometry_signature(), links)

    def _compute_routes(self) -> dict[str, list[tuple[float, float]]]:
        key = self._routes_key()
        if self._route_cache is not None and key == self._route_key:
            return self._route_cache
        self._slots.clear()  # the order of links on an edge follows where their other ends are
        links: list[routing.RouteLink] = []
        for iid in sorted(self.ctl.project.interfaces):
            i = self.ctl.project.interfaces[iid]
            a = self.unit_items.get(i.endpoints[0].unit_id)
            b = self.unit_items.get(i.endpoints[1].unit_id)
            if a is None or b is None:
                continue
            side_a, side_b = a.link_side(iid), b.link_side(iid)
            pa = a.anchor(i.endpoints[0].connector_id, iid, side_a)
            pb = b.anchor(i.endpoints[1].connector_id, iid, side_b)
            style = (self._link_category(iid) or "data") + (
                "-redundant" if i.redundancy == "redundant" else ""
            )
            links.append(
                routing.RouteLink(
                    iid, a.unit_id, b.unit_id, a.lane(), b.lane(),
                    (pa.x(), pa.y()), (pb.x(), pb.y()), side_a, style,
                )
            )  # fmt: skip
        self._route_key = key
        self._route_cache = routing.route_links(links, self._geometry())
        return self._route_cache

    def reroute(self) -> None:
        """Work out all routes again and redraw the links whose route changed (and only those)."""
        if self._batch:
            self._routes_stale = True
            return
        self._slots.clear()
        self._routes = None
        self._redraw_changed()

    def _redraw_changed(self) -> None:
        for iid, link in self.link_items.items():
            if link.poly != self.route(iid):
                link.update_path()

    # ---- filter by signal class, connector or bundle: the others fade, nothing is hidden --------------
    FADED_LINK = 0.15
    FADED_UNIT = 0.4
    LABEL_LIMIT = 30  # a diagram with more links shows a link's label only when it matters
    show_all_labels = False  # view setting (View menu): labels on every link, however many

    def label_full(self, interface_id: str, hovered: bool) -> bool:
        """The numbers (voltage, current) beside a link's picture: always on a diagram that is not
        dense, otherwise for the selected link, the links in focus and the link under the pointer."""
        return self.label_visible(interface_id, hovered)

    def label_visible(self, interface_id: str, hovered: bool) -> bool:
        """Labels on all links make a dense diagram unreadable, so above LABEL_LIMIT links a label
        shows for the selected link, the links in focus and the link under the pointer."""
        if self.show_all_labels or hovered or len(self.link_items) <= self.LABEL_LIMIT:
            return True
        sel = self.ctl.selection
        if sel is not None and sel.kind == "interface" and sel.id == interface_id:
            return True
        focus = self.focus_sets()
        return focus is not None and interface_id in focus[0]

    def set_filter(self, kind: str | None, value: str | None = None) -> None:
        """Show only what matches and fade the rest: `kind` is "class" (a style category such as
        "power"), "connector" (a box connector ID) or "bundle" (a harness ID); None shows everything.
        Only opacity changes, so selection, editing and the model are untouched."""
        self.filter = (kind, value) if kind and value else None
        self._apply_filter()

    def set_category_filter(self, category: str | None) -> None:
        self.set_filter("class" if category else None, category)

    @property
    def category_filter(self) -> str | None:
        return self.filter[1] if self.filter and self.filter[0] == "class" else None

    def _link_category(self, iid: str) -> str | None:
        p = self.ctl.project
        i = p.interfaces.get(iid)
        t = p.interface_types.get(i.type_id) if i else None
        return style_category(t.category) if t else None

    def matching_interfaces(self) -> set[str] | None:
        """IDs of the interfaces the current filter keeps; None when there is no filter."""
        if self.filter is None:
            return None
        kind, value = self.filter
        p = self.ctl.project
        if kind == "class":
            return {iid for iid in p.interfaces if self._link_category(iid) == value}
        if kind == "connector":
            return {
                i.id
                for i in p.interfaces.values()
                if any(e.connector_id == value for e in i.endpoints)
            }
        h = p.harnesses.get(value or "")
        if h is None:
            return set()
        return set(h.interfaces) | {w.interface_id for w in h.wires if w.interface_id}

    def focus_sets(self) -> tuple[set[str], set[str]] | None:
        """(interfaces, units) that stay in full colour because they belong to the selection, or
        None when nothing is selected (or the selection has no links): then nothing fades.
        Worked out once per selection and change (every link asks while it is painted)."""
        sel = self.ctl.selection
        if sel is None:
            return None
        if self._focus_cache is not None and self._focus_cache[0] == sel:
            return self._focus_cache[1]
        links, units = routing.focus(self.ctl.project, sel.kind, sel.id)
        found = (links, units) if links else None
        self._focus_cache = (sel, found)
        return found

    def _apply_filter(self) -> None:
        """Fade what the Show filter does not keep and what the selection does not concern.
        Only opacity changes (and only where it differs), so the model and editing are untouched."""
        keep = self.matching_interfaces()
        focus = self.focus_sets()
        for iid, link in self.link_items.items():
            on = (keep is None or iid in keep) and (focus is None or iid in focus[0])
            want = 1.0 if on else self.FADED_LINK
            if link.opacity() != want:
                link.setOpacity(want)
            lift = 1.5 if focus is not None and iid in focus[0] else 1.0  # focused links on top
            if link.zValue() != lift:
                link.setZValue(lift)
        for uid, item in self.unit_items.items():
            on = (keep is None or any(i in keep for i in self._adj.get(uid, []))) and (
                focus is None or uid in focus[1]
            )
            want = 1.0 if on else self.FADED_UNIT
            if item.opacity() != want:
                item.setOpacity(want)

    # ---- label placement: a coarse grid of placed link labels, so they do not overlap ------------
    CELL = 120.0

    def _cells(self, r: QRectF) -> list[tuple[int, int]]:
        x0, x1 = int(r.left() // self.CELL), int(r.right() // self.CELL)
        y0, y1 = int(r.top() // self.CELL), int(r.bottom() // self.CELL)
        return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]

    def chip_free(self, rect: QRectF, own: str) -> bool:
        pad = rect.adjusted(-3, -3, 3, 3)
        for cell in self._cells(pad):
            for other, r in self._chips.get(cell, ()):
                if other != own and r.intersects(pad):
                    return False
        return True

    def chip_forget(self, interface_id: str) -> None:
        rect = self._chip_rects.pop(interface_id, None)
        if rect is None:
            return
        for cell in self._cells(rect):
            self._chips[cell] = [c for c in self._chips.get(cell, []) if c[0] != interface_id]

    def chip_place(self, interface_id: str, rect: QRectF) -> None:
        self.chip_forget(interface_id)
        self._chip_rects[interface_id] = rect
        for cell in self._cells(rect):
            self._chips.setdefault(cell, []).append((interface_id, rect))

    def link_order(self, interface_id: str) -> int:
        return self._order.get(interface_id, 0)

    def _rebuild_adjacency(self) -> None:
        adj: dict[str, list[str]] = {}
        order: dict[str, int] = {}
        conn_link: dict[str, str] = {}
        for k, i in enumerate(sorted(self.ctl.project.interfaces.values(), key=lambda x: x.id)):
            order[i.id] = k
            for e in i.endpoints:
                adj.setdefault(e.unit_id, []).append(i.id)
                if e.connector_id is not None:
                    conn_link[e.connector_id] = i.id
        self._adj = adj
        self._order = order
        self._conn_link = conn_link
        self._slots.clear()

    def rebuild(self) -> None:
        self._focus_cache = None
        self.clear()
        self.unit_items.clear()
        self.link_items.clear()
        self._chips.clear()
        self._chip_rects.clear()
        self._slots.clear()
        self._routes = None
        self.zone_items.clear()
        self._rebuild_adjacency()
        self._sync_zones()
        project = self.ctl.project
        self._batch += 1  # units are placed one by one: route once they are all there
        try:
            for uid in sorted(project.units):
                self._add_unit(uid)
        finally:
            self._batch -= 1
        self._routes = None
        for iid in sorted(project.interfaces):
            self._add_link(iid)
        self._update_extent()
        if self.filter is not None or self.ctl.selection is not None:
            self._apply_filter()

    def _add_unit(self, uid: str) -> None:
        item = UnitItem(self, uid)
        x, y = edit.position_of(self.ctl.project, uid)
        self.addItem(item)
        item.setPos(x, y)
        self.unit_items[uid] = item

    def _add_link(self, iid: str) -> None:
        link = LinkItem(self, iid)
        self.addItem(link)
        self.link_items[iid] = link
        link.update_path()

    def _sync_zones(self) -> None:
        n = len(edit.effective_zones(self.ctl.project))
        self.zone_count = n
        while len(self.zone_items) > n:
            self.removeItem(self.zone_items.pop())
        while len(self.zone_items) < n:
            z = ZoneItem(self, len(self.zone_items))
            self.addItem(z)
            self.zone_items.append(z)
        for k, z in enumerate(self.zone_items):
            where = QPointF(edit.LANE_X0 + k * edit.LANE_WIDTH, 0)
            if z.pos() != where:
                z.setPos(where)
            # (a zone item is as tall as the diagram: repainting all of them on every edit made
            # each edit repaint every unit and link)

    def _update_extent(self) -> None:
        bottom = max(
            (it.pos().y() + it.height() + 60 for it in self.unit_items.values()), default=0
        )
        # in steps, so adding or undoing one unit rarely resizes the scene (which repaints it all)
        height = max(700.0, math.ceil((bottom + 40) / LANE_STEP) * LANE_STEP)
        if height != self.lane_height:
            self.lane_height = height
            for z in self.zone_items:
                z.prepareGeometryChange()
        width = max(1, len(self.zone_items)) * edit.LANE_WIDTH + 2 * edit.LANE_X0
        rect = QRectF(0, 0, width, self.lane_height)
        if rect != self.sceneRect():
            self.setSceneRect(rect)

    def apply(self, delta: Delta) -> None:
        self._focus_cache = None  # the model changed: the focus of the selection may have
        if delta.full:
            self.rebuild()
            return
        self._rebuild_adjacency()
        self._routes = None
        self._sync_zones()
        self._batch += 1  # several units and links change together: route once, at the end
        try:
            self._apply_units_and_links(delta)
        finally:
            self._batch -= 1
        if self._routes_key() != self._route_key:  # a rename or a note changes no route
            self._routes = None
            self._redraw_changed()
        self._update_extent()
        if self.filter is not None or self.ctl.selection is not None:
            self._apply_filter()

    def _geometry_signature(self) -> object:
        """Everything the routes depend on, except the links themselves: where the units are, how
        tall, which edge each link leaves from."""
        units = tuple(
            (uid, it.pos().x(), it.pos().y(), it.height())
            for uid, it in sorted(self.unit_items.items())
        )
        return (units, self.ctl.mode, self.zone_count, self._conn_link, self._adj)

    def _apply_units_and_links(self, delta: Delta) -> None:
        project = self.ctl.project
        for uid in delta.units:
            item = self.unit_items.get(uid)
            if uid in project.units:
                x, y = edit.position_of(project, uid)
                if item is None:
                    self._add_unit(uid)
                else:
                    item.prepareGeometryChange()
                    if (item.pos().x(), item.pos().y()) != (x, y):
                        item.setPos(x, y)
                    item.update()
            elif item is not None:
                self.removeItem(item)
                del self.unit_items[uid]
        for iid in delta.interfaces:
            link = self.link_items.get(iid)
            if iid in project.interfaces:
                if link is None:
                    self._add_link(iid)
                elif iid not in delta.followers:  # (a link that only follows its unit is redrawn
                    link.update_path()  # by the routes, if they changed)
                    link.update()  # its picture or numbers may have changed, though not its route
            elif link is not None:
                self.removeItem(link)
                self.chip_forget(iid)
                del self.link_items[iid]

    def relink(self, unit_id: str) -> None:
        """A unit moved or changed: its links, and every link that shares a trunk with them, may
        run differently, so all routes are worked out again; only changed links are redrawn."""
        self.reroute()

    def refresh_all(self) -> None:
        self._focus_cache = None
        self._routes = None  # (worked out again only if what they depend on changed)
        for it in self.unit_items.values():
            it.prepareGeometryChange()
            it.update()
        for link in self.link_items.values():
            link.update_path()
        self.update()

    def _repaint_units(self) -> None:
        for it in self.unit_items.values():
            it.update()

    def _on_selection(self) -> None:
        """Repaint only the previously and the newly selected item (not the whole diagram)."""
        for sel in (self._last_sel, self.ctl.selection):
            if sel is None:
                continue
            item = (self.unit_items if sel.kind == "unit" else self.link_items).get(sel.id)  # type: ignore[attr-defined]
            if item is not None:
                item.update()
        self._last_sel = self.ctl.selection
        self._apply_filter()  # a selection puts its own links in focus and fades the rest


LANE_STEP = 256.0  # lane height grows in steps of this many pixels
MAP_DELAY_MS = 400  # the overview map repaints this long after the last change


class MiniMap(QWidget):
    """Small overview of the whole diagram; click to centre the main view there.

    It draws plain boxes and lines straight from the item positions instead of showing the scene a
    second time: painting 2,200 real items in a tiny view cost about 300 ms at stress size."""

    def __init__(self, main: "DiagramView") -> None:
        super().__init__(main)
        self.main = main
        self.setFixedSize(190, 130)
        self.setAccessibleName(strings.MINIMAP)
        self.setToolTip(strings.MINIMAP)
        self._lag = QTimer(self)
        self._lag.setSingleShot(True)
        self._lag.setInterval(MAP_DELAY_MS)
        self._lag.timeout.connect(self._catch_up)
        main.scene().changed.connect(self._scene_changed)
        main.scene().sceneRectChanged.connect(lambda _r: self.update())

    def viewport(self) -> "MiniMap":
        return self  # (the earlier version was a graphics view; callers update its viewport)

    def refit(self) -> None:
        self.update()

    def _scene_changed(self, _regions: object) -> None:
        if self.isVisible():
            self._lag.start()  # restarts: the map catches up when the edits pause

    def _catch_up(self) -> None:
        if self.isVisible():
            self.update()

    def _scale(self) -> tuple[float, float, float]:
        """(scale, x offset, y offset) that fit the scene into the widget."""
        rect = self.main.scene().sceneRect()
        if not rect.isValid() or rect.isEmpty():
            return 1.0, 0.0, 0.0
        scale = min((self.width() - 2) / rect.width(), (self.height() - 2) / rect.height())
        return (
            scale,
            (self.width() - rect.width() * scale) / 2 - rect.x() * scale,
            (self.height() - rect.height() * scale) / 2 - rect.y() * scale,
        )

    def paintEvent(self, event: object) -> None:
        theme = self.main.theme
        scene = self.main.dscene
        painter = QPainter(self)
        painter.fillRect(self.rect(), theme.color("bg"))
        scale, dx, dy = self._scale()
        painter.translate(dx, dy)
        painter.scale(scale, scale)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.color("surface"))
        for k in range(len(scene.zone_items)):
            painter.drawRect(
                QRectF(
                    edit.LANE_X0 + k * edit.LANE_WIDTH, 0, edit.LANE_WIDTH - 10, scene.lane_height
                )
            )
        painter.setPen(QPen(theme.color("border"), 0))
        painter.drawLines([ln for ln in (lk.ends for lk in scene.link_items.values()) if ln])
        painter.setBrush(theme.color("surface"))
        painter.setPen(QPen(theme.color("text"), 0))
        painter.drawRects(
            [QRectF(it.pos().x(), it.pos().y(), W, it.height()) for it in scene.unit_items.values()]
        )
        view_rect = self.main.mapToScene(self.main.viewport().rect()).boundingRect()
        painter.setPen(QPen(theme.color("primary"), 0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(view_rect)
        painter.resetTransform()
        painter.setPen(QPen(theme.color("border"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        scale, dx, dy = self._scale()
        pos = event.position()
        self.main.centerOn(QPointF((pos.x() - dx) / scale, (pos.y() - dy) / scale))
        self.update()


class DiagramView(QGraphicsView):
    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        self.ctl = ctl
        self.theme = theme
        self.dscene = DiagramScene(ctl, theme)
        super().__init__(self.dscene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setAccessibleName(strings.CANVAS)
        self.setAccessibleDescription(strings.CANVAS_HELP)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.empty = QLabel(strings.EMPTY_CANVAS, self.viewport())
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setProperty("muted", True)
        self.empty.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.minimap = MiniMap(self)
        self.minimap_wanted = True  # the View menu can switch it off
        self._fit_scale = 0.25
        ctl.changed.connect(self._on_changed)
        ctl.selectionChanged.connect(self._announce)
        theme.changed.connect(self._restyle)
        self._on_changed(None)
        self._announce()

    def _announce(self) -> None:
        """Qt does not expose graphics items to screen readers, so the view itself says what it
        holds, what is selected, and where the full accessible alternative is."""
        p = self.ctl.project
        self.setAccessibleName(
            strings.CANVAS_NAME.format(
                strings.units_text(len(p.units)), strings.interfaces_text(len(p.interfaces))
            )
        )
        sel = self.ctl.selection
        picked = strings.CANVAS_SELECTED.format(sel.kind, sel.id) if sel else strings.CANVAS_NONE
        self.setAccessibleDescription(f"{picked} {strings.CANVAS_HELP}")

    def _restyle(self) -> None:
        self.setBackgroundBrush(QBrush(self.theme.color("bg")))
        self.viewport().update()

    def _on_changed(self, delta: object) -> None:
        self._announce()
        if getattr(delta, "full", False):
            QTimer.singleShot(0, self.fit)  # a newly opened project starts fitted to the window
        self.empty.setVisible(not self.ctl.project.units)
        self._layout_overlays()
        self._update_minimap_visibility()
        if getattr(delta, "full", False):
            # The map shares the scene, so a local edit repaints only the changed items there; it
            # is refitted when the scene rectangle changes. Forcing a repaint of the whole map on
            # every edit repainted every item and cost about half of an edit at stress size.
            self.minimap.refit()
            self.minimap.viewport().update()

    def set_minimap_wanted(self, wanted: bool) -> None:
        self.minimap_wanted = wanted
        self._update_minimap_visibility()

    def _update_minimap_visibility(self) -> None:
        # it covers the bottom right corner, so a small view hides it automatically
        room = self.viewport().height() >= 300 and self.viewport().width() >= 420
        self.minimap.setVisible(self.minimap_wanted and room and len(self.ctl.project.units) > 0)

    def _layout_overlays(self) -> None:
        r = self.viewport().rect()
        self.empty.setGeometry(r.adjusted(60, 60, -60, -60))
        self.minimap.move(
            r.right() - self.minimap.width() - 12, r.bottom() - self.minimap.height() - 12
        )

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._layout_overlays()
        self.minimap.refit()
        self._update_minimap_visibility()

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self.minimap.viewport().update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.1 if event.angleDelta().y() > 0 else 1 / 1.1
        self.zoom_by(factor)
        event.accept()

    def zoom_by(self, factor: float) -> None:
        current = self.transform().m11()
        # a large diagram is fitted below 0.25; zooming out must never jump back in
        lowest = max(0.02, min(0.25, self._fit_scale * 0.9))
        new = max(lowest, min(3.0, current * factor))
        self.scale(new / current, new / current)
        self.minimap.viewport().update()

    def content_rect(self) -> QRectF:
        """Bounding box of units and links (not the tall lane backgrounds)."""
        rect = QRectF()
        for it in (*self.dscene.unit_items.values(), *self.dscene.link_items.values()):
            rect = rect.united(it.sceneBoundingRect())
        return rect

    def fit(self) -> None:
        self.resetTransform()
        rect = self.content_rect()
        if not rect.isNull():
            self.fitInView(rect.adjusted(-60, -60, 60, 60), Qt.AspectRatioMode.KeepAspectRatio)
            if self.transform().m11() > 1.2:
                self.resetTransform()
                self.centerOn(rect.center())
            self._fit_scale = self.transform().m11()
        self.minimap.viewport().update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        if (item is None or isinstance(item, ZoneItem)) and self.ctl.tool == "select":
            self.ctl.select(None)  # a click on the background (a lane is background too)
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.ctl.end_connect()
            if self.ctl.tool == "select":
                self.ctl.select(None)  # Escape also takes the focus off a selection
            event.accept()
            return
        super().keyPressEvent(event)

    def focusNextPrevChild(self, next: bool) -> bool:  # noqa: A002, N802
        """Tab and Shift+Tab visit the units and links (Qt alone would skip them); past either end
        the focus leaves the diagram for the next or previous control."""
        if self.step_focus(backwards=not next):
            return True
        return super().focusNextPrevChild(next)

    def focus_order(self) -> list[QGraphicsItem]:
        """The items Tab visits: units by lane, then top to bottom, then links by ID. (Qt only
        tab-chains widgets, never plain graphics items, so the view does it.)"""
        scene = self.dscene
        units = sorted(
            scene.unit_items.values(),
            key=lambda it: (it.lane(), it.pos().y(), it.unit_id),
        )
        links = [scene.link_items[k] for k in sorted(scene.link_items)]
        return [*units, *links]

    def step_focus(self, *, backwards: bool = False) -> bool:
        """Move the focus to the next (or previous) unit or link and scroll it into view. Returns
        False at either end, so that Tab then leaves the diagram for the next control."""
        order = self.focus_order()
        if not order:
            return False
        current = self.dscene.focusItem()
        at = order.index(current) if current in order else -1
        nxt = (at - 1 if at >= 0 else len(order) - 1) if backwards else at + 1
        if not 0 <= nxt < len(order):
            return False
        item = order[nxt]
        item.setFocus(Qt.FocusReason.TabFocusReason)
        self.ensureVisible(item, 40, 40)
        return True

    def reveal(self, unit_id: str) -> None:
        """Scroll a unit into view without changing keyboard focus."""
        item = self.dscene.unit_items.get(unit_id)
        if item is not None:
            self.ensureVisible(item, 40, 40)

    def focus_unit(self, unit_id: str) -> None:
        item = self.dscene.unit_items.get(unit_id)
        if item is not None:
            self.ensureVisible(item)
            item.setFocus()
