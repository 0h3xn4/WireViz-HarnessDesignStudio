"""Block-diagram canvas: zone lanes, unit boxes, interface links, minimap."""

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import partial

from PySide6.QtCore import QLineF, QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QContextMenuEvent,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QStyleOptionGraphicsItem,
    QToolButton,
    QToolTip,
    QWidget,
)

from harness_design_studio.core import describe, edit, routing
from harness_design_studio.core.model import Project
from harness_design_studio.gui import glyphs, strings
from harness_design_studio.gui.controller import Delta, EditorController, Selection
from harness_design_studio.gui.theme import ThemeManager
from harness_design_studio.gui.tokens import CATEGORIES, style_category


@dataclass(frozen=True)
class CanvasMetrics:
    """Every size, scale limit and timing of the canvas in one place (the numbers that used to be
    scattered through this module). A later change moves them into the theme's token groups."""

    unit_w: float = edit.UNIT_W
    header_h: float = 30.0
    port_row: float = edit.PORT_ROW
    grid: int = 10  # snap step in scene units
    chip_h: float = 22.0  # a link's label
    chip_compact_w: float = 22.0  # the label squeezed to its picture
    chip_compact_h: float = 18.0
    link_hit_width: float = 14.0  # how far from a link's line a click still picks it
    overview_lod: float = 0.45  # below this scale a unit is drawn as a box and its ID
    far_lod: float = 0.5  # below this scale links are plain lines
    twin_lod: float = 0.8  # a pair of signals is drawn as two lines only from this scale up
    legible_px: float = 12.0  # text of the overview boxes, in screen pixels
    min_scale: float = 0.02
    max_scale: float = 3.0
    min_fit_scale: float = 0.1  # "fit" never zooms out further than this (the diagram scrolls)
    min_open_scale: float = 0.22  # a project opens at least this large, so names can be read
    grid_min_scale: float = 0.5  # the grid shows from this scale up
    wheel_notch_px: float = 80.0  # one wheel notch scrolls this far
    wheel_zoom_per_notch: float = math.exp(120 / 240)
    drag_preview_ms: int = 25  # straight preview lines while dragging are redrawn this often
    minimap_size: tuple[int, int] = (190, 130)
    minimap_small_size: tuple[int, int] = (130, 90)
    minimap_small_below: int = 560  # viewport height under which the small map is used
    minimap_hide_below: int = 360  # ... and under which there is none
    legend_collapse_below: int = 640  # viewport height under which the legend starts collapsed


METRICS = CanvasMetrics()
W = METRICS.unit_w
HEADER_H = METRICS.header_h
PORT_ROW = METRICS.port_row
GRID = METRICS.grid


def facing_side(lane: int, lanes: int) -> str:
    """Connectors sit on the edge that faces the middle of the diagram."""
    return "right" if lane <= (lanes - 1) // 2 else "left"


def elide(fm: QFontMetrics, text: str, width: float, *, middle: bool = False) -> str:
    """The text cut to `width` with an ellipsis (in the middle for names that differ at the end)."""
    mode = Qt.TextElideMode.ElideMiddle if middle else Qt.TextElideMode.ElideRight
    return fm.elidedText(text, mode, max(1, int(width)))


class UnitItem(QGraphicsItem):
    def __init__(self, scene: "DiagramScene", unit_id: str) -> None:
        super().__init__()
        self.dscene = scene
        self.unit_id = unit_id
        self._press_pos: QPointF | None = None
        self._moved = False
        self._collapse_on_release = False  # a click without a drag on a multi-selection picks one
        self._refused = False  # the read-only message was shown for this press
        self._lane_key: tuple[float, int] | None = None
        self._lane = 0
        # The height is kept here, not read from the model: Qt must see the old rectangle until
        # prepareGeometryChange() has run, or its index loses the item (and the program crashes).
        self._h = scene.unit_height(unit_id)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(2)
        self._placing = False  # True while the scene puts the unit where the model says

    def place(self, x: float, y: float) -> None:
        """Put the unit where the model says (never clamped: the scene grows to hold it)."""
        self._placing = True
        try:
            self.setPos(x, y)
        finally:
            self._placing = False

    # ---- geometry ---------------------------------------------------------------------------
    @property
    def ctl(self) -> EditorController:
        return self.dscene.ctl

    def connectors(self) -> list:  # type: ignore[type-arg]
        return edit.unit_connectors(self.ctl.project, self.unit_id)

    def height(self) -> float:
        return self._h

    def set_height(self, height: float) -> None:
        """Take a new height: Qt is told first, while the old rectangle is still in effect."""
        if height != self._h:
            self.prepareGeometryChange()
            self._h = height
            self.update()

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
        return "no", strings.NO_FREE_CONNECTOR.format(name)

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
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        if lod < METRICS.overview_lod and not reason:
            self._paint_overview(painter, th, unit, state, lod)
            return
        selected = ctl.is_selected("unit", self.unit_id)
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
        painter.drawText(
            QRectF(10, 0, W - 80, HEADER_H),
            Qt.AlignmentFlag.AlignVCenter,
            elide(painter.fontMetrics(), unit.id, W - 80),
        )
        painter.setFont(small)
        painter.setPen(th.color("text-muted"))
        tag = (
            strings.TAG_FROM
            if state == "from"
            else (strings.TAG_REDUNDANT if unit.side == "redundant" else strings.TAG_NOMINAL)
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
                elide(QFontMetrics(small), unit.name, W - 20),
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
        self._paint_highlight(painter, th, body)
        if self.hasFocus():
            painter.setPen(QPen(th.color("focus"), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(body.adjusted(-4, -4, 4, 4), 10, 10)

    def _paint_highlight(self, painter: QPainter, th: ThemeManager, body: QRectF) -> None:
        """A search match: a dashed ring in the warning colour (the current one is thicker)."""
        mark = self.dscene.highlight_state("unit", self.unit_id)
        if not mark:
            return
        painter.setPen(
            QPen(th.color("warning"), 7 if mark == "current" else 4, Qt.PenStyle.DashLine)
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body.adjusted(-9, -9, 9, 9), 13, 13)

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
        self, painter: QPainter, th: ThemeManager, unit: object, state: str, lod: float
    ) -> None:
        """Zoomed far out: a plain box and the ID only (fast for diagrams with hundreds of units).
        The ID is sized in screen pixels, so it stays readable however far the view is zoomed out
        (it is cut to the box where the box is too small to hold it)."""
        selected = self.ctl.is_selected("unit", self.unit_id)
        pen = QPen(
            th.color("primary") if selected or state in ("ok", "from") else th.color("border"),
            4 if selected else 2,
        )
        painter.setPen(pen)
        painter.setBrush(QBrush(th.color("surface")))
        h = self.height()
        painter.drawRect(QRectF(0, 0, W, h))
        font = QFont(painter.font())
        font.setBold(True)
        wanted = METRICS.legible_px / max(lod, 0.01)
        font.setPixelSize(max(1, int(min(h * 0.85, max(22.0, wanted)))))
        painter.setFont(font)
        painter.setPen(th.color("text"))
        painter.drawText(
            QRectF(8, 0, W - 16, h),
            Qt.AlignmentFlag.AlignVCenter,
            elide(painter.fontMetrics(), self.unit_id, W - 16, middle=True),
        )
        self._paint_highlight(painter, th, QRectF(0, 0, W, h))

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
            painter.drawText(
                QRectF(row["name"][0], y - 9, glyphs.ROW_NAME_W, 18),
                align,
                elide(painter.fontMetrics(), c.name, glyphs.ROW_NAME_W, middle=True),
            )
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
        if event.button() != Qt.MouseButton.LeftButton:
            event.accept()  # (a right click opens the menu; the view does the rest)
            return
        self.setFocus()
        if ctl.tool == "connect":
            ctl.pick(self.unit_id, self.port_at(event.pos()))
            event.accept()
            return
        self._moved = self._refused = self._collapse_on_release = False
        if event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            ctl.toggle("unit", self.unit_id)  # Ctrl+click and Shift+click add or remove one
            self._press_pos = None
            event.accept()
            return
        if ctl.is_selected("unit", self.unit_id) and len(ctl.selected) > 1:
            # keep the selection so that it can be dragged together; a click alone picks this one
            self._collapse_on_release = True
            ctl.select_many(ctl.selected, primary=("unit", self.unit_id))
        else:
            ctl.select("unit", self.unit_id)
        self._press_pos = self.pos()
        self.dscene.begin_group_drag(self)
        if ctl.read_only:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.ctl.tool == "connect" or self._press_pos is None:
            event.accept()  # a press with the Connect tool picks the unit; it never drags it
            return
        if self.ctl.read_only:
            if not self._refused:
                self._refused = True
                self.ctl.refuse_read_only()  # a drag that did nothing says why
            event.accept()
            return
        super().mouseMoveEvent(event)
        self.dscene.drag_group_with(self)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        start = self._press_pos
        self._press_pos = None
        if start is None:
            return
        ctl = self.ctl
        moved = self.dscene.end_group_drag(self)
        if moved and not ctl.read_only:
            ctl.move_units(moved)
        elif self._collapse_on_release and self.pos() == start:
            ctl.select("unit", self.unit_id)
        self._collapse_on_release = False

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.ctl.tool == "select":
            self.ctl.select("unit", self.unit_id)
            self.ctl.request_open("unit", self.unit_id)
        event.accept()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: object) -> object:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and isinstance(
            value, QPointF
        ):
            if self.ctl.read_only and self._press_pos is not None:
                return self._press_pos
            if self._placing:
                return value  # where the model says: never moved to the grid
            x, y = value.x(), value.y()
            if self.dscene.snapping():
                x, y = round(x / GRID) * GRID, round(y / GRID) * GRID
            return QPointF(max(0.0, x), max(0.0, y))  # a drag cannot leave the top left corner
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.dscene.relink(self.unit_id)
        return super().itemChange(change, value)

    def hoverMoveEvent(self, event: object) -> None:
        _, reason = self._compat_reason()
        tip = reason
        cid = self.port_at(event.pos())  # type: ignore[attr-defined]  # (None unless Expert)
        if cid and self.ctl.tool == "connect" and self.ctl.connect_type:
            c = self.ctl.connector_compat(cid)
            tip = "" if c.ok else c.why
        if tip:
            QToolTip.showText(event.screenPos(), tip)  # type: ignore[attr-defined]
        else:
            u = self.ctl.project.units.get(self.unit_id)
            conn = self.ctl.project.connectors.get(cid) if cid else None
            full = f"{u.id}: {u.name}" if u else ""
            self.setToolTip(f"{full}\n{conn.name}" if conn else full)  # (the whole text, if elided)

    def activate(self, *, open_plan: bool = False) -> None:
        """Enter or Space on the unit: pick it with the Connect tool, otherwise select it (Enter
        also asks for it to be shown in the plans)."""
        ctl = self.ctl
        if ctl.tool == "connect":
            ctl.pick(self.unit_id, self._first_valid_port())
            return
        ctl.select("unit", self.unit_id)
        if open_plan:
            ctl.request_open("unit", self.unit_id)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        ctl = self.ctl
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activate(open_plan=key != Qt.Key.Key_Space)
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
        ):
            if ctl.read_only:
                ctl.refuse_read_only()
                event.accept()
                return
            dx, dy = nudge[key]  # type: ignore[index]
            ids = ctl.selected_ids("unit")
            if self.unit_id not in ids:
                ids = [self.unit_id]
            items = [self.dscene.unit_items[u] for u in ids if u in self.dscene.unit_items]
            ctl.move_units(
                {
                    it.unit_id: (max(0.0, it.pos().x() + dx), max(0.0, it.pos().y() + dy))
                    for it in items
                }
            )
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


def _spots_along(
    lo: float, hi: float, step: float, fixed: float, horizontal: bool
) -> list[QPointF]:
    """Positions between lo and hi on a horizontal piece at height `fixed` (or a vertical piece at
    x = `fixed`), the middle first, then alternately either side of it."""
    mid = (lo + hi) / 2
    ts = [mid]
    k = 1
    while mid - k * step >= lo - 0.01 and len(ts) < 25:
        ts += [mid - k * step, mid + k * step]
        k += 1
    return [QPointF(t, fixed) if horizontal else QPointF(fixed, t) for t in ts]


COMPACT_W = METRICS.chip_compact_w  # a link label that has to squeeze between other links
COMPACT_H = METRICS.chip_compact_h


class LinkItem(QGraphicsPathItem):
    def __init__(self, scene: "DiagramScene", interface_id: str) -> None:
        super().__init__()
        self.dscene = scene
        self.interface_id = interface_id
        self._chip = QRectF()
        self._chip_placed = False
        self._compact = False  # the picture alone, where the full label has no clear spot
        self._chip_values = 0  # how many characters of numbers the registered label was sized for
        self.ends: QLineF | None = None  # straight line between the two anchors (for the map)
        self.poly: list[tuple[float, float]] = []  # the corners of the route now drawn
        self._hover = False
        self._preview = False  # a straight line while one of its units is being dragged
        self._base_z = 1.0
        self.setZValue(1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption)  # exposedRect
        self.setAcceptHoverEvents(True)

    def update_path(self) -> bool:
        """Take the route the scene worked out for this link and the label spot. Returns False (and
        leaves the item alone, so it is not repainted) when nothing changed: renaming a unit must
        not repaint its links."""
        if self.dscene._batch:  # the scene redraws every changed link once the batch is done
            return False
        self._preview = False
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
        self._chip_values = len(describe.link_values(self.dscene.ctl.project, name))
        width = self._chip_width(self._chip_values * 6.5)
        center, crossed = self._pick_spot(route, width, METRICS.chip_h, name)
        self._compact = False
        if crossed:  # nowhere is clear: a smaller label, the picture alone, may still fit
            small, crossed_small = self._pick_spot(route, COMPACT_W, COMPACT_H, name)
            if crossed_small < crossed:
                center, self._compact = small, True
        if center is None:
            center = path.pointAtPercent(0.5)
        self._chip_center = center
        self._chip_placed = True
        w, h = (COMPACT_W, COMPACT_H) if self._compact else (width, METRICS.chip_h)
        self.dscene.chip_place(name, QRectF(center.x() - w / 2, center.y() - h / 2, w, h))
        return True

    def _pick_spot(
        self, route: list[tuple[float, float]], width: float, height: float, name: str
    ) -> tuple[QPointF | None, int]:
        """The first spot on the route where a label of this size overlaps no label and no other
        link, else the free spot that other links run through least; and how many run through it."""
        best: QPointF | None = None
        fewest = 0
        for spot in self._label_spots(route, width + 4):
            rect = QRectF(spot.x() - width / 2, spot.y() - height / 2, width, height)
            if not self.dscene.chip_free(rect, name):
                continue
            crossed = self.dscene.link_crossings(
                rect, name, fewest if best is not None else 1 << 30
            )
            if best is None or crossed < fewest:
                best, fewest = spot, crossed
            if crossed == 0:
                break
        return best, fewest

    def refresh_chip(self) -> None:
        """The numbers on the link changed: register a label of the new size (update_path does
        nothing inside a batch, and the route may be the same)."""
        i = self.dscene.ctl.project.interfaces.get(self.interface_id)
        if i is None or not self._chip_placed:
            return
        if len(describe.link_values(self.dscene.ctl.project, i.id)) != self._chip_values:
            self._chip_placed = False
            self.update_path()

    @staticmethod
    def _chip_width(text_w: float) -> float:
        """A chip is the picture of the link kind, and the numbers when there are any."""
        return 30.0 + (text_w + 6 if text_w else 0.0)

    @staticmethod
    def _label_spots(route: list[tuple[float, float]], need: float) -> list[QPointF]:
        """Where a label can sit: along a horizontal piece long enough to hold it (the middle
        first, then to either side), the pieces nearest the end first; then the same along the
        vertical pieces of some length."""
        pieces = list(zip(route, route[1:], strict=False))[::-1]
        wide: list[QPointF] = []
        tall: list[QPointF] = []
        for p, q in pieces:
            if p[1] == q[1] and abs(q[0] - p[0]) >= need:
                lo, hi = min(p[0], q[0]), max(p[0], q[0])
                wide += _spots_along(lo + need / 2, hi - need / 2, 12.0, p[1], True)
            elif p[0] == q[0] and abs(q[1] - p[1]) >= 28:
                lo, hi = min(p[1], q[1]), max(p[1], q[1])
                tall += _spots_along(lo + 14, hi - 14, 12.0, p[0], False)
        return wide + tall

    def shape(self) -> QPainterPath:
        """The line, and the label on it: a click on a label picks its own link."""
        stroker = QPainterPathStroker()
        stroker.setWidth(METRICS.link_hit_width)
        path = stroker.createStroke(self.path())
        chip = None if self._preview else self.dscene.chip_rect(self.interface_id)
        if chip is not None:
            path.addRect(chip)
        return path

    def boundingRect(self) -> QRectF:
        return super().boundingRect().adjusted(-120, -20, 120, 20)

    def set_preview(self, route: list[tuple[float, float]]) -> None:
        """Straight lines through the end points while a unit is dragged (no routing, no label)."""
        path = QPainterPath(QPointF(*route[0]))
        for x, y in route[1:]:
            path.lineTo(x, y)
        self._preview = True
        self.poly = []  # whatever the router says later differs from this: it is then redrawn
        self._chip_placed = False
        self.prepareGeometryChange()
        self.setPath(path)

    def raise_to(self, z: float) -> None:
        """Lift the link (a selected or focused one lies above the others)."""
        self._base_z = z
        z += 0.2 if self._hover else 0.0
        if self.zValue() != z:
            self.setZValue(z)

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        ctl = self.dscene.ctl
        sc = self.dscene
        i = ctl.project.interfaces.get(self.interface_id)
        if i is None or self.path().isEmpty():
            return
        exposed = option.exposedRect.adjusted(-10, -10, 10, 10)
        if not self.path().intersects(exposed) and not self._chip.intersects(exposed):
            chip = sc.chip_rect(self.interface_id)
            if chip is None or not chip.intersects(exposed):
                return  # the long box of a link is often dirty where the link itself is not
        t = ctl.project.interface_types.get(i.type_id)
        cat = style_category(t.category if t else "data")
        info = CATEGORIES[cat]
        weight = float(info["weight"])
        selected = ctl.is_selected("interface", i.id)
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        far = (lod < METRICS.far_lod or bool(sc._drag_units)) and not selected
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, not far)  # (plain while dragging)
        marked = i.id in ctl.diff_marks
        if marked:  # a wide, dotted halo in the warning colour (not colour alone: also dotted)
            painter.setPen(sc.pen("warning", weight + 8, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.path())
        found = sc.highlight_state("interface", i.id)
        if found:  # a search match: a wide dashed halo (the current one wider)
            painter.setPen(
                sc.pen("warning", weight + (12 if found == "current" else 8), Qt.PenStyle.DashLine)
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.path())
        # (a faded link is drawn as one line: nobody sees the gap, and it halves the paint)
        twin = (
            lod >= METRICS.twin_lod
            and not far
            and not self._preview
            and self.opacity() >= 0.5
            and t is not None
            and any(sig.pair for sig in t.signals)
        )
        style = Qt.PenStyle.DashLine if i.redundancy == "redundant" else Qt.PenStyle.SolidLine
        painter.setPen(
            sc.pen(f"cat-{cat}", weight + (2 if selected else 0) + (3.0 if twin else 0.0), style)
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())
        if twin:  # the gap between the two lines
            painter.setPen(sc.pen("bg", 1.4, style))
            painter.drawPath(self.path())
        if far or self._preview or self.opacity() < 0.5:
            return  # zoomed out, faded or being dragged: the line only, no label
        th = sc.theme
        color = th.color(f"cat-{cat}")
        c = self._chip_center
        font = sc.px_font(th.px(11))
        values = describe.link_values(ctl.project, i.id) if sc.label_full(i.id, self._hover) else ""
        if self._compact:
            values = ""
        text_w = sc.text_width(font, values) if values else 0
        width = METRICS.chip_compact_w if self._compact else self._chip_width(text_w)
        height = METRICS.chip_compact_h if self._compact else METRICS.chip_h
        rect = QRectF(c.x() - width / 2, c.y() - height / 2, width, height)
        self._chip = rect
        if not option.exposedRect.intersects(rect.adjusted(-4, -4, 4, 4)):
            return  # the label is outside what is being repainted
        painter.setBrush(QBrush(th.color("bg")))
        painter.setPen(sc.pen(f"cat-{cat}", 3 if selected else 2))
        painter.drawRoundedRect(rect, height / 2, height / 2)
        scale = 0.8 if self._compact else 1.0
        glyphs.draw_link_glyph(
            painter,
            rect.x() + (rect.width() - glyphs.LINK_GLYPH_W * scale) / 2
            if self._compact
            else rect.x() + 6,
            rect.y() + (rect.height() - glyphs.LINK_GLYPH_H * scale) / 2,
            i.type_id,
            t.category if t else "data",
            color,
            scale,
        )
        if values:
            painter.setFont(font)
            painter.setPen(th.color("text"))
            painter.drawText(
                QRectF(rect.x() + 26, rect.y(), text_w + 4, METRICS.chip_h),
                Qt.AlignmentFlag.AlignVCenter,
                values,
            )
        if self.hasFocus():
            painter.setPen(QPen(th.color("focus"), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 13, 13)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.dscene.ctl.tool == "connect":
            event.ignore()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            event.accept()
            return
        self.click(event.modifiers())
        event.accept()

    def click(self, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
        """A click on the line or its label: select it (Ctrl or Shift adds or removes it)."""
        self.setFocus()
        ctl = self.dscene.ctl
        if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            ctl.toggle("interface", self.interface_id)
        else:
            ctl.select("interface", self.interface_id)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.dscene.ctl.tool == "select":
            self.open_plan()
        event.accept()

    def open_plan(self) -> None:
        ctl = self.dscene.ctl
        ctl.select("interface", self.interface_id)
        ctl.request_open("interface", self.interface_id)

    def activate(self, *, open_plan: bool = False) -> None:
        if open_plan:
            self.open_plan()
        else:
            self.dscene.ctl.select("interface", self.interface_id)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activate(open_plan=event.key() != Qt.Key.Key_Space)
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
            self.setZValue(self._base_z + 0.2)  # the link under the pointer lies on top
            self.update()

    def hoverLeaveEvent(self, event: object) -> None:
        if self._hover:
            self._hover = False
            self.setZValue(self._base_z)
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
        # the name of the lane is sized in screen pixels, so it can be read when zoomed out
        lod = max(option.levelOfDetailFromTransform(painter.worldTransform()), 0.05)
        size = max(th.px(12), min(80, round(th.px(11) / lod)))
        font.setPixelSize(size)
        painter.setFont(font)
        painter.setPen(th.color("text-muted"))
        name = zones[self.index].upper() if self.index < len(zones) else ""
        painter.drawText(
            QRectF(10, 4, edit.LANE_WIDTH - 30, size + 8), Qt.AlignmentFlag.AlignVCenter, name
        )


class DiagramScene(QGraphicsScene):
    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl = ctl
        self.theme = theme
        self.unit_items: dict[str, UnitItem] = {}
        self.link_items: dict[str, LinkItem] = {}
        self._chips: dict[tuple[int, int], list[tuple[str, QRectF]]] = {}
        self._chip_rects: dict[str, QRectF] = {}
        self._segments: dict[tuple[int, int], list[tuple[str, QRectF]]] = {}  # route pieces
        self.zone_items: list[ZoneItem] = []
        self.lane_height = 700.0
        self._adj: dict[str, list[str]] = {}
        self._order: dict[str, int] = {}
        self.zone_count = len(edit.effective_zones(ctl.project))
        self._last_sel: set[Selection] = set()
        self._conn_link: dict[str, str] = {}  # box connector ID -> the interface that uses it
        self._slots: dict[str, dict[str, tuple[str, int, int]]] = {}
        self._routes: dict[str, list[tuple[float, float]]] | None = None
        self._batch = 0  # while above 0, routes are worked out once at the end
        self._focus_cache: tuple[object, tuple[set[str], set[str]] | None] | None = None
        self._route_key: object = None  # what the cached routes were worked out from
        self._route_cache: dict[str, list[tuple[float, float]]] | None = None
        self._routes_stale = False
        # view state, not part of the project: the Show filter (kind, the values it keeps)
        self.filter: tuple[str, str | frozenset[str]] | None = None
        self.snap_to_grid = True  # View > Snap to grid (Alt held while dragging bypasses it)
        self._highlight: dict[tuple[str, str], str] = {}  # search matches: "match" | "current"
        self._pens: dict[tuple[str, float, Qt.PenStyle], QPen] = {}
        self._fonts: dict[int, QFont] = {}
        self._metrics: dict[tuple[int, str], int] = {}
        self._group: dict[str, QPointF] = {}  # units being dragged together, where they started
        self._drag_units: set[str] = set()
        self._previewed = False
        self._preview_dirty = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(METRICS.drag_preview_ms)
        self._preview_timer.timeout.connect(self._preview_tick)
        ctl.changed.connect(self.apply)
        ctl.selectionChanged.connect(self._on_selection)
        ctl.marksChanged.connect(self.refresh_all)
        ctl.connectChanged.connect(self._repaint_units)
        ctl.modeChanged.connect(self.refresh_all)
        theme.changed.connect(self._theme_changed)
        self.rebuild()

    # ---- small helpers for painting (cached: a repaint asks for the same few pens and fonts) ----
    def _theme_changed(self) -> None:
        self._pens.clear()
        self._fonts.clear()
        self._metrics.clear()
        self.update()

    def pen(self, token: str, width: float, style: Qt.PenStyle = Qt.PenStyle.SolidLine) -> QPen:
        key = (token, width, style)
        pen = self._pens.get(key)
        if pen is None:
            pen = self._pens[key] = QPen(self.theme.color(token), width, style)
        return pen

    def px_font(self, pixel_size: int) -> QFont:
        font = self._fonts.get(pixel_size)
        if font is None:
            font = QFont(QApplication.font())
            font.setPixelSize(pixel_size)
            self._fonts[pixel_size] = font
        return font

    def text_width(self, font: QFont, text: str) -> int:
        key = (font.pixelSize(), text)
        got = self._metrics.get(key)
        if got is None:
            if len(self._metrics) > 2000:
                self._metrics.clear()
            got = self._metrics[key] = QFontMetrics(font).horizontalAdvance(text)
        return got

    def snapping(self) -> bool:
        """Whether a dragged unit lands on the grid (Alt held down switches it off for one drag)."""
        if not self.snap_to_grid:
            return False
        return not QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier

    # ---- search matches --------------------------------------------------------------------
    def set_highlight(
        self,
        items: Iterable[tuple[str, str]] | None,
        current: tuple[str, str] | None = None,
    ) -> None:
        """Mark units and links (kind, id) as matches of a search; `current` is drawn stronger.
        None clears the marks. Only the items whose mark changed are repainted."""
        new: dict[tuple[str, str], str] = {(k, i): "match" for k, i in (items or ())}
        if current is not None and current in new:
            new[current] = "current"
        old, self._highlight = self._highlight, new
        for key in {k for k in (*old, *new) if old.get(k) != new.get(k)}:
            item = (self.unit_items if key[0] == "unit" else self.link_items).get(key[1])
            if item is not None:
                item.update()

    def highlight_state(self, kind: str, id_: str) -> str:
        return self._highlight.get((kind, id_), "")

    # ---- dragging units: a group moves together; links of moved units are straight previews ----
    def begin_group_drag(self, item: "UnitItem") -> None:
        ids = self.ctl.selected_ids("unit")
        if item.unit_id not in ids:
            ids = [item.unit_id]
        self._group = {u: QPointF(self.unit_items[u].pos()) for u in ids if u in self.unit_items}
        self._drag_units = set(self._group)

    def drag_group_with(self, item: "UnitItem") -> None:
        start = self._group.get(item.unit_id)
        if start is None or len(self._group) < 2:
            return
        delta = item.pos() - start
        for uid, origin in self._group.items():
            other = self.unit_items.get(uid)
            if other is not None and other is not item and other.pos() != origin + delta:
                other.setPos(origin + delta)

    def end_group_drag(self, item: "UnitItem") -> dict[str, tuple[float, float]]:
        """The drag is over: full routing again, and where each unit that moved now is."""
        moved = {
            uid: (it.pos().x(), it.pos().y())
            for uid, origin in self._group.items()
            if (it := self.unit_items.get(uid)) is not None and it.pos() != origin
        }
        self._preview_timer.stop()
        self._group, self._drag_units = {}, set()
        if self._previewed or self._preview_dirty:
            self._previewed = self._preview_dirty = False
            self.reroute()
        return moved

    def _schedule_preview(self) -> None:
        if self._preview_timer.isActive():
            self._preview_dirty = True
            return
        self._run_preview()
        self._preview_timer.start()

    def _preview_tick(self) -> None:
        if self._preview_dirty and self._drag_units:
            self._run_preview()
            self._preview_timer.start()

    def _run_preview(self) -> None:
        """Straight lines for the links of the units being dragged; nothing else is routed."""
        self._preview_dirty = False
        self._previewed = True
        touched: set[str] = set()
        for uid in self._drag_units:
            touched.update(self._adj.get(uid, ()))
        for uid in {*self._drag_units, *(e for i in touched for e in self._ends_of(i))}:
            self._slots.pop(uid, None)
        project = self.ctl.project
        for iid in touched:
            link = self.link_items.get(iid)
            i = project.interfaces.get(iid)
            if link is None or i is None:
                continue
            a, b = (
                self.unit_items.get(i.endpoints[0].unit_id),
                self.unit_items.get(i.endpoints[1].unit_id),
            )
            if a is None or b is None:
                continue
            pa = a.anchor(i.endpoints[0].connector_id, iid, a.link_side(iid))
            pb = b.anchor(i.endpoints[1].connector_id, iid, b.link_side(iid))
            self.chip_forget(iid)
            link.set_preview([(pa.x(), pa.y()), (pb.x(), pb.y())])
            link.ends = QLineF(pa, pb)

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
        self._index_segments(self._route_cache)
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
        moved: list[QRectF] = []
        for iid, link in self.link_items.items():
            if link.poly != self.route(iid):
                link.update_path()
                moved += [
                    QRectF(QPointF(*p), QPointF(*q)).normalized().adjusted(-1, -1, 1, 1)
                    for p, q in zip(link.poly, link.poly[1:], strict=False)
                ]
        if not moved or len(moved) == sum(len(link.poly) - 1 for link in self.link_items.values()):
            return  # nothing moved, or everything did (a new diagram): every label was just placed
        for iid, link in self.link_items.items():  # a label that a moved link now runs through
            rect = self._chip_rects.get(iid)
            if rect is not None and any(m.intersects(rect.adjusted(-2, -2, 2, 2)) for m in moved):
                link._chip_placed = False
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

    def set_filter(self, kind: str | None, value: "str | Iterable[str] | None" = None) -> None:
        """Show only what matches and fade the rest: `kind` is "class" (a style category such as
        "power"), "connector" (a box connector ID) or "bundle" (a harness ID); `value` is one of
        them or several (anything that matches one is kept); None shows everything.
        Only opacity changes, so selection, editing and the model are untouched."""
        values = frozenset([value] if isinstance(value, str) else (value or ()))
        one = value if isinstance(value, str) else None  # (one value is kept as it was given)
        self.filter = (kind, one or values) if kind and values else None
        self._apply_filter()

    def set_category_filter(self, category: str | None) -> None:
        self.set_filter("class" if category else None, category)

    @property
    def category_filter(self) -> str | None:
        if self.filter and self.filter[0] == "class":
            return sorted(self.filter_values())[0]
        return None

    def filter_values(self) -> frozenset[str]:
        """The values the current filter keeps (empty when there is no filter)."""
        if self.filter is None:
            return frozenset()
        value = self.filter[1]
        return frozenset([value]) if isinstance(value, str) else value

    def _link_category(self, iid: str) -> str | None:
        p = self.ctl.project
        i = p.interfaces.get(iid)
        t = p.interface_types.get(i.type_id) if i else None
        return style_category(t.category) if t else None

    def matching_interfaces(self) -> set[str] | None:
        """IDs of the interfaces the current filter keeps; None when there is no filter."""
        if self.filter is None:
            return None
        kind, values = self.filter[0], self.filter_values()
        p = self.ctl.project
        if kind == "class":
            return {iid for iid in p.interfaces if self._link_category(iid) in values}
        if kind == "connector":
            return {
                i.id
                for i in p.interfaces.values()
                if any(e.connector_id in values for e in i.endpoints)
            }
        found: set[str] = set()
        for value in values:
            h = p.harnesses.get(value)
            if h is not None:
                found |= set(h.interfaces) | {w.interface_id for w in h.wires if w.interface_id}
        return found

    def focus_sets(self) -> tuple[set[str], set[str]] | None:
        """(interfaces, units) that stay in full colour because they belong to the selection, or
        None when nothing is selected (or the selection has no links): then nothing fades.
        Worked out once per selection and change (every link asks while it is painted)."""
        sel = self.ctl.selected
        if not sel:
            return None
        if self._focus_cache is not None and self._focus_cache[0] == sel:
            return self._focus_cache[1]
        links: set[str] = set()
        units: set[str] = set()
        for item in sel:
            more_links, more_units = routing.focus(self.ctl.project, item.kind, item.id)
            links |= more_links
            units |= more_units
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
            # focused links on top, a selected one above them
            lift = (
                1.6
                if self.ctl.is_selected("interface", iid)
                else (1.5 if focus is not None and iid in focus[0] else 1.0)
            )
            link.raise_to(lift)
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

    MAX_INDEXED_PIECES = 3000  # (labels are placed in a loop over all links: keep it fast)
    SEG_CELL = 32.0  # finer than CELL: a dense diagram has many route pieces in one big cell

    def _seg_cells(self, r: QRectF) -> list[tuple[int, int]]:
        c = self.SEG_CELL
        x0, x1 = int(r.left() // c), int(r.right() // c)
        y0, y1 = int(r.top() // c), int(r.bottom() // c)
        return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]

    def _index_segments(self, routes: dict[str, list[tuple[float, float]]]) -> None:
        """The straight pieces of every route in the grid, so that a label can keep clear of them."""
        self._segments.clear()
        if sum(len(r) for r in routes.values()) > self.MAX_INDEXED_PIECES:
            return  # too dense to keep every label clear: labels only avoid each other
        for iid, route in routes.items():
            for p, q in zip(route, route[1:], strict=False):
                box = QRectF(QPointF(*p), QPointF(*q)).normalized().adjusted(-1, -1, 1, 1)
                for cell in self._seg_cells(box):
                    self._segments.setdefault(cell, []).append((iid, box))

    def link_crossings(self, rect: QRectF, own: str, limit: int = 1 << 30) -> int:
        """How many pieces of other links run through `rect` (a label's box, with a little air);
        counting stops at `limit`."""
        pad = rect.adjusted(-2, -2, 2, 2)
        seen: set[tuple[str, float, float]] = set()
        for cell in self._seg_cells(pad):
            for other, box in self._segments.get(cell, ()):
                if other != own and box.intersects(pad):
                    seen.add((other, box.x(), box.y()))
                    if len(seen) >= limit:
                        return len(seen)
        return len(seen)

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
        self._group, self._drag_units = {}, set()
        self._previewed = self._preview_dirty = False
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
        if self.filter is not None or self.ctl.selected:
            self._apply_filter()

    def unit_height(self, uid: str) -> float:
        """The height a unit has now: expert mode, one row per connector; guided, one per link."""
        if self.ctl.mode == "expert":
            return edit.expert_height(len(edit.unit_connectors(self.ctl.project, uid)))
        return edit.guided_height(len(self.adjacent(uid)))

    def _heights(self) -> dict[str, float]:
        """The height of every unit now, in one pass over the project."""
        project = self.ctl.project
        if self.ctl.mode != "expert":
            return {uid: edit.guided_height(len(self.adjacent(uid))) for uid in project.units}
        rows = dict.fromkeys(project.units, 0)
        for c in project.connectors.values():
            if c.role == "box" and c.unit_id in rows:
                rows[c.unit_id] += 1
        return {uid: edit.expert_height(n) for uid, n in rows.items()}

    def _refresh_heights(self) -> None:
        """Bring every unit item to its height now (a link or connector may have come or gone
        without its unit being named in the change). Units that are gone keep the height Qt knows."""
        heights = self._heights()
        for uid, item in self.unit_items.items():
            if uid in heights:
                item.set_height(heights[uid])

    def _add_unit(self, uid: str) -> None:
        item = UnitItem(self, uid)
        x, y = edit.position_of(self.ctl.project, uid)
        self.addItem(item)
        item.place(x, y)
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
        bottom = left = top = right = 0.0
        for it in self.unit_items.values():
            pos = it.pos()
            bottom = max(bottom, pos.y() + it.height() + 60)
            left, top = min(left, pos.x() - 40), min(top, pos.y() - 40)
            right = max(right, pos.x() + W + 40)
        # in steps, so adding or undoing one unit rarely resizes the scene (which repaints it all)
        height = max(700.0, math.ceil((bottom + 40) / LANE_STEP) * LANE_STEP)
        if height != self.lane_height:
            for z in self.zone_items:
                z.prepareGeometryChange()
            self.lane_height = height
        width = max(1, len(self.zone_items)) * edit.LANE_WIDTH + 2 * edit.LANE_X0
        # a unit placed outside the lanes (by a file, or far out) keeps the scene big enough to
        # reach it; steps, so a drag nearby does not resize the scene each time
        width = max(width, math.ceil(right / LANE_STEP) * LANE_STEP)
        left = -math.ceil(-left / LANE_STEP) * LANE_STEP
        top = -math.ceil(-top / LANE_STEP) * LANE_STEP
        rect = QRectF(left, top, width - left, self.lane_height - top)
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
        self._refresh_heights()
        self._batch += 1  # several units and links change together: route once, at the end
        try:
            self._apply_units_and_links(delta)
        finally:
            self._batch -= 1
        if self._routes_key() != self._route_key:  # a rename or a note changes no route
            self._routes = None
            self._redraw_changed()
        for iid in delta.interfaces:  # new numbers need a bigger label in the registry
            link = self.link_items.get(iid)
            if link is not None and iid not in delta.followers:
                link.refresh_chip()
        self._update_extent()
        if self.filter is not None or self.ctl.selected:
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
                        item.place(x, y)
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
        run differently, so all routes are worked out again; only changed links are redrawn.
        While units are being dragged only straight preview lines are drawn (at most once per
        METRICS.drag_preview_ms); the routes are worked out when the mouse is released."""
        if self._drag_units:
            self._schedule_preview()
            return
        self.reroute()

    def refresh_all(self) -> None:
        self._focus_cache = None
        self._routes = None  # (worked out again only if what they depend on changed)
        self._refresh_heights()  # (the mode may have changed)
        for it in self.unit_items.values():
            it.prepareGeometryChange()
            it.update()
        for link in self.link_items.values():
            link.update_path()
        self._update_extent()  # (expert units are taller)
        self.update()

    def _repaint_units(self) -> None:
        for it in self.unit_items.values():
            it.update()

    def _on_selection(self) -> None:
        """Repaint only the items whose selected state changed (not the whole diagram)."""
        now = set(self.ctl.selected)
        for sel in now ^ self._last_sel:
            item = (self.unit_items if sel.kind == "unit" else self.link_items).get(sel.id)
            if item is not None:
                item.update()
        self._last_sel = now
        self._apply_filter()  # a selection puts its own links in focus and fades the rest

    def chip_rect(self, interface_id: str) -> QRectF | None:
        """Where the label of a link was placed, or None (not placed yet, or being dragged)."""
        return self._chip_rects.get(interface_id)

    def chip_at(self, pos: QPointF) -> "LinkItem | None":
        """The link whose label lies under a scene point (a label is part of its link)."""
        for cell in self._cells(QRectF(pos, pos)):
            for iid, rect in self._chips.get(cell, ()):
                if rect.contains(pos):
                    return self.link_items.get(iid)
        for link in self.link_items.values():  # a label drawn wider than it was reserved
            if not link._preview and link._chip.contains(pos):
                return link
        return None

    def _ends_of(self, interface_id: str) -> tuple[str, ...]:
        i = self.ctl.project.interfaces.get(interface_id)
        return tuple(e.unit_id for e in i.endpoints) if i is not None else ()


LANE_STEP = 256.0  # lane height grows in steps of this many pixels
MAP_DELAY_MS = 400  # the overview map repaints this long after the last change


class MiniMap(QWidget):
    """Small overview of the whole diagram; click or drag to move the main view there.

    It draws plain boxes and lines straight from the item positions instead of showing the scene a
    second time: painting 2,200 real items in a tiny view cost about 300 ms at stress size."""

    def __init__(self, main: "DiagramView") -> None:
        super().__init__(main)
        self.main = main
        self.setFixedSize(*METRICS.minimap_size)
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
        # thin and see-through: hundreds of links drawn in a solid colour made a black mass
        faint = QColor(theme.color("border"))
        faint.setAlpha(70 if len(scene.link_items) > 80 else 130)
        painter.setPen(QPen(faint, 0))
        painter.drawLines([ln for ln in (lk.ends for lk in scene.link_items.values()) if ln])
        edge = QColor(theme.color("border"))
        edge.setAlpha(190)
        painter.setBrush(theme.color("surface-2"))
        painter.setPen(QPen(edge, 0))
        painter.drawRects(
            [QRectF(it.pos().x(), it.pos().y(), W, it.height()) for it in scene.unit_items.values()]
        )
        view_rect = self.main.mapToScene(self.main.viewport().rect()).boundingRect()
        painter.setPen(QPen(theme.color("primary"), 2 / max(scale, 1e-6)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(view_rect)
        painter.resetTransform()
        painter.setPen(QPen(theme.color("border"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()

    def _centre_at(self, pos: QPointF) -> None:
        scale, dx, dy = self._scale()
        self.main.centerOn(QPointF((pos.x() - dx) / scale, (pos.y() - dy) / scale))
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._centre_at(event.position())
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:  # drag the view rectangle
            self._centre_at(event.position())
        event.accept()


class ZoomIndicator(QToolButton):
    """The zoom level of a view as a percentage; a click returns to 100 %. Place it anywhere (the
    window puts it between the zoom buttons)."""

    def __init__(self, view: "DiagramView") -> None:
        super().__init__()
        self.view = view
        self.setObjectName("zoom-level")
        self.setAccessibleName(strings.ZOOM_LEVEL_NAME)
        self.setToolTip(strings.ZOOM_LEVEL_TIP)
        self.setAutoRaise(True)
        self.clicked.connect(lambda _c=False: view.zoom_100())
        view.zoomChanged.connect(self._show)
        self._show(view.zoom_scale())

    def _show(self, scale: float) -> None:
        self.setText(strings.ZOOM_PERCENT.format(round(scale * 100)))


class EmptyHint(QWidget):
    """The words over an empty diagram. It paints only its text: no box, so the grid and the lanes
    stay visible behind it (a QLabel would get the solid background of the style sheet)."""

    def __init__(self, text: str, parent: QWidget, theme: ThemeManager) -> None:
        super().__init__(parent)
        self._theme = theme
        self._text = text
        self.setObjectName("empty-hint")
        self.setAccessibleName(strings.EMPTY_HINT_NAME)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        theme.changed.connect(self.update)

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        if text != self._text:
            self._text = text
            self.setAccessibleDescription(text)
            self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setPen(self._theme.color("text-muted"))
        painter.setFont(self.font())
        painter.drawText(
            self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._text
        )
        painter.end()


def find_matches(project: Project, query: str) -> list[tuple[str, str]]:
    """(kind, id) of the units and links that match every word of `query`: a word may be part of
    an ID, a name, a connector ID or name, or the name of the interface type. Units first, each
    kind in ID order."""
    words = query.casefold().split()
    if not words:
        return []
    names: dict[str, list[str]] = {}
    for c in project.connectors.values():
        if c.unit_id:
            names.setdefault(c.unit_id, []).extend((c.id, c.name))

    def hit(*texts: str) -> bool:
        hay = " ".join(texts).casefold()
        return all(w in hay for w in words)

    found: list[tuple[str, str]] = []
    for uid in sorted(project.units):
        u = project.units[uid]
        if hit(u.id, u.name, *names.get(uid, ())):
            found.append(("unit", uid))
    for iid in sorted(project.interfaces):
        i = project.interfaces[iid]
        t = project.interface_types.get(i.type_id)
        ends = [x for e in i.endpoints for x in (e.unit_id, e.connector_id or "")]
        if hit(i.id, i.name, t.name if t else i.type_id, *ends):
            found.append(("interface", iid))
    return found


class _SearchEdit(QLineEdit):
    previous = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.previous.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class SearchBar(QFrame):
    """Ctrl+F in the diagram: every unit and link that matches is marked, Enter goes to the next
    one (the view centres on it), Shift+Enter to the one before, Escape closes the bar."""

    def __init__(self, view: "DiagramView") -> None:
        super().__init__(view)
        self.view = view
        self.setObjectName("diagram-search")
        self.setProperty("card", True)
        self.setAccessibleName(strings.SEARCH_NAME)
        self.matches: list[tuple[str, str]] = []
        self.index = -1
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        self.edit = _SearchEdit()
        self.edit.setObjectName("diagram-search-edit")
        self.edit.setPlaceholderText(strings.SEARCH_PLACEHOLDER)
        self.edit.setAccessibleName(strings.SEARCH_NAME)
        self.edit.setToolTip(strings.SEARCH_TIP)
        self.edit.setClearButtonEnabled(True)
        self.edit.setMinimumWidth(220)
        self.count = QLabel("")
        self.count.setObjectName("diagram-search-count")
        self.count.setAccessibleName(strings.SEARCH_COUNT_NAME)
        self.prev_btn = self._button("search-prev", "▲", strings.SEARCH_PREV)
        self.next_btn = self._button("search-next", "▼", strings.SEARCH_NEXT)
        self.close_btn = self._button("search-close", "✕", strings.SEARCH_CLOSE)
        for w in (self.edit, self.count, self.prev_btn, self.next_btn, self.close_btn):
            lay.addWidget(w)
        self.edit.textChanged.connect(self._text_changed)
        self.edit.returnPressed.connect(lambda: self.step(1))
        self.edit.previous.connect(lambda: self.step(-1))
        self.prev_btn.clicked.connect(lambda _c=False: self.step(-1))
        self.next_btn.clicked.connect(lambda _c=False: self.step(1))
        self.close_btn.clicked.connect(lambda _c=False: self.close_bar())
        view.ctl.changed.connect(lambda _d: self._refresh())
        self.hide()

    def _button(self, name: str, text: str, tip: str) -> QToolButton:
        b = QToolButton()
        b.setObjectName(name)
        b.setText(text)
        b.setToolTip(tip)
        b.setAccessibleName(tip.split(" (")[0])
        return b

    def open_bar(self) -> None:
        self.show()
        self.view._layout_overlays()
        self.raise_()
        self.edit.setFocus()
        self.edit.selectAll()
        self._refresh()

    def close_bar(self) -> None:
        self.hide()
        self.view.dscene.set_highlight(None)
        self.view.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_bar()
            event.accept()
            return
        super().keyPressEvent(event)

    def _text_changed(self, _text: str) -> None:
        self.index = -1
        self._refresh()
        if self.matches:
            self.step(1)

    def _refresh(self) -> None:
        """Mark what matches now (the project may have changed under the open bar)."""
        if not self.isVisible():
            return
        current = self.matches[self.index] if 0 <= self.index < len(self.matches) else None
        self.matches = find_matches(self.view.ctl.project, self.edit.text())
        self.index = self.matches.index(current) if current in self.matches else -1
        self.view.dscene.set_highlight(self.matches, current)
        if not self.edit.text().strip():
            self.count.setText("")
        elif not self.matches:
            self.count.setText(strings.SEARCH_NONE)
        else:
            self.count.setText(strings.SEARCH_POSITION.format(self.index + 1, len(self.matches)))
        for b in (self.prev_btn, self.next_btn):
            b.setEnabled(bool(self.matches))

    def step(self, delta: int) -> None:
        """Go to the next (or previous) match, wrapping round, and centre the view on it."""
        if not self.matches:
            return
        self.index = (self.index + delta) % len(self.matches)
        kind, ident = self.matches[self.index]
        self.view.dscene.set_highlight(self.matches, (kind, ident))
        self.count.setText(strings.SEARCH_POSITION.format(self.index + 1, len(self.matches)))
        self.view.center_on_object(kind, ident)


class DiagramView(QGraphicsView):
    zoomChanged = Signal(float)  # the scale now (1.0 is 100 %)

    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        self.ctl = ctl
        self.theme = theme
        self.dscene = DiagramScene(ctl, theme)
        super().__init__(self.dscene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)  # panning and the rubber band are ours
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setAccessibleName(strings.CANVAS)
        self.setAccessibleDescription(strings.CANVAS_HELP)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.empty = EmptyHint(strings.EMPTY_CANVAS, self, theme)
        from harness_design_studio.gui.legend import LegendOverlay

        self.minimap = MiniMap(self)
        self.minimap_wanted = True  # the View menu can switch it off
        self.legend = LegendOverlay(theme, self)
        self.legend_wanted = True  # ... and so can it the legend
        self.search = SearchBar(self)
        self._fit_scale = 0.25
        self._space = False  # Space is held: a drag pans
        self._space_used = False
        self._pan_last: QPoint | None = None
        self._band_origin: QPointF | None = None
        self._band_origin_view = QPoint()
        self._band: QRectF | None = None
        self._band_base: tuple[object, ...] = ()
        self._band_hits: tuple[tuple[str, str], ...] = ()
        # the window gives the context menu the actions it mirrors (name -> QAction)
        self.menu_actions: dict[str, QAction] = {}
        self.exec_menu: Callable[[QMenu, QPoint], object] = lambda menu, at: menu.exec(at)
        self.last_menu: QMenu | None = None
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
        if len(self.ctl.selected) > 1:
            picked = strings.CANVAS_SELECTED_MANY.format(len(self.ctl.selected))
        else:
            picked = (
                strings.CANVAS_SELECTED.format(sel.kind, sel.id) if sel else strings.CANVAS_NONE
            )
        self.setAccessibleDescription(f"{picked} {strings.CANVAS_HELP}")

    def _restyle(self) -> None:
        self.setBackgroundBrush(QBrush(self.theme.color("bg")))
        self.viewport().update()

    def _on_changed(self, delta: object) -> None:
        self._announce()
        if getattr(delta, "full", False):
            QTimer.singleShot(0, lambda: self.fit(legible=True))  # a new project opens readable
        p = self.ctl.project
        self.legend.set_project(p)
        if not p.units:
            self.empty.setText(strings.EMPTY_CANVAS)
        elif not p.interfaces:
            self.empty.setText(strings.EMPTY_NO_LINKS)
        self.empty.setVisible(not p.units or not p.interfaces)
        self._layout_overlays()
        self._update_minimap_visibility()
        if getattr(delta, "full", False):
            # The map shares the scene, so a local edit repaints only the changed items there; it
            # is refitted when the scene rectangle changes. Forcing a repaint of the whole map on
            # every edit repainted every item and cost about half of an edit at stress size.
            self.minimap.refit()
            self.minimap.viewport().update()

    # ---- overlays: map, legend, search ------------------------------------------------------------
    def set_minimap_wanted(self, wanted: bool) -> None:
        self.minimap_wanted = wanted
        self._update_minimap_visibility()

    def set_legend_wanted(self, wanted: bool) -> None:
        self.legend_wanted = wanted
        self._layout_overlays()

    def set_snap(self, on: bool) -> None:
        self.dscene.snap_to_grid = on
        self.viewport().update()

    def _map_size(self) -> tuple[int, int] | None:
        """The size of the map for this window, or None when the window is too small for one."""
        h, w = self.viewport().height(), self.viewport().width()
        if h < METRICS.minimap_hide_below or w < 420:
            return None
        return (
            METRICS.minimap_size if h >= METRICS.minimap_small_below else METRICS.minimap_small_size
        )

    def _update_minimap_visibility(self) -> None:
        # it covers the bottom right corner, so a small view hides it (or shrinks it)
        size = self._map_size()
        if size is not None:
            self.minimap.setFixedSize(*size)
        self.minimap.setVisible(
            self.minimap_wanted and size is not None and len(self.ctl.project.units) > 0
        )

    def _layout_overlays(self) -> None:
        r = self.viewport().rect()
        # (the hint is a child of the view, not of the viewport: scrolling would carry it along)
        area = self.viewport().geometry()
        if self.ctl.project.units and not self.ctl.project.interfaces:
            self.empty.setGeometry(area.adjusted(60, 12, -60, -(area.height() - 60)))  # a top line
        else:
            self.empty.setGeometry(area.adjusted(60, 60, -60, -60))
        self.minimap.move(
            r.right() - self.minimap.width() - 12, r.bottom() - self.minimap.height() - 12
        )
        room = r.width() - 24 - (self.minimap.width() + 12 if self.minimap.isVisible() else 0)
        self.legend.place(r, max(160, min(room, 620)))
        self.legend.setVisible(self.legend_wanted and bool(self.ctl.project.units))
        self.search.adjustSize()
        self.search.move(r.right() - self.search.width() - 12, r.top() + 12)

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._update_minimap_visibility()
        self._layout_overlays()
        self.minimap.refit()

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self.minimap.viewport().update()

    # ---- zoom and pan ---------------------------------------------------------------------------
    def zoom_scale(self) -> float:
        return float(self.transform().m11())

    def _apply_scale(self, new: float, anchor: QPoint | None = None) -> None:
        """Set the scale; the scene point under `anchor` (default: the middle) stays where it is."""
        new = max(METRICS.min_scale, min(METRICS.max_scale, new))
        current = self.zoom_scale()
        if abs(new - current) > 1e-9:
            at = anchor if anchor is not None else self.viewport().rect().center()
            before = self.mapToScene(at)
            self.scale(new / current, new / current)
            moved = self.mapToScene(at) - before
            self.translate(moved.x(), moved.y())
        self._scale_changed()

    def _scale_changed(self) -> None:
        self.minimap.viewport().update()
        self.zoomChanged.emit(self.zoom_scale())

    def zoom_by(self, factor: float, anchor: QPoint | None = None) -> None:
        # a large diagram is fitted below 0.25; zooming out must never jump back in
        lowest = max(METRICS.min_scale, min(0.25, self._fit_scale * 0.9))
        self._apply_scale(max(lowest, self.zoom_scale() * factor), anchor)

    def zoom_100(self) -> None:
        """Show everything at its real size (Ctrl+0)."""
        self._apply_scale(1.0)

    def zoom_to_selection(self) -> None:
        """Fill the view with what is selected (Shift+F); with nothing selected, fit everything."""
        scene = self.dscene
        rect = QRectF()
        for sel in self.ctl.selected:
            item = (scene.unit_items if sel.kind == "unit" else scene.link_items).get(sel.id)
            if item is not None:
                rect = rect.united(item.sceneBoundingRect())
        if rect.isNull():
            self.fit()
            return
        self.fitInView(rect.adjusted(-80, -80, 80, 80), Qt.AspectRatioMode.KeepAspectRatio)
        if self.zoom_scale() > 1.5:
            self._apply_scale(1.0 if self.zoom_scale() > 1.5 else self.zoom_scale())
            self.centerOn(rect.center())
        self._scale_changed()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Ctrl+wheel zooms at the pointer. Plain wheel scrolls up and down, Shift+wheel sideways;
        a trackpad (pixel deltas) scrolls both ways. The wheel alone never zooms."""
        mods = event.modifiers()
        angle, pixels = event.angleDelta(), event.pixelDelta()
        if mods & Qt.KeyboardModifier.ControlModifier:
            delta = angle.y() or angle.x() or pixels.y()
            if delta:
                factor = METRICS.wheel_zoom_per_notch ** (delta / 120)
                self.zoom_by(factor, event.position().toPoint())
            event.accept()
            return
        if not pixels.isNull():
            dx, dy = float(pixels.x()), float(pixels.y())
        else:
            notch = METRICS.wheel_notch_px / 120
            dx, dy = angle.x() * notch, angle.y() * notch
            if mods & Qt.KeyboardModifier.ShiftModifier and not dx:
                dx, dy = dy, 0.0  # (some platforms already swap the axes)
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - round(dx))
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() - round(dy))
        event.accept()

    def content_rect(self) -> QRectF:
        """Bounding box of units and links (not the tall lane backgrounds)."""
        rect = QRectF()
        for it in (*self.dscene.unit_items.values(), *self.dscene.link_items.values()):
            rect = rect.united(it.sceneBoundingRect())
        return rect

    def fit(self, *, legible: bool = False) -> None:
        """Show the whole diagram (F). It never zooms out below METRICS.min_fit_scale, and a
        project that has just been opened (`legible`) not below METRICS.min_open_scale, so names
        can be read; a diagram too big for that is shown from its top left and scrolls."""
        self.resetTransform()
        rect = self.content_rect()
        if not rect.isNull():
            self.fitInView(rect.adjusted(-60, -60, 60, 60), Qt.AspectRatioMode.KeepAspectRatio)
            natural = self.zoom_scale()
            floor = METRICS.min_open_scale if legible else METRICS.min_fit_scale
            if natural > 1.2:
                self.resetTransform()
                self.centerOn(rect.center())
            elif natural < floor:
                self.resetTransform()
                self.scale(floor, floor)
                vp = self.viewport()
                self.centerOn(
                    QPointF(
                        rect.left() - 60 + vp.width() / (2 * floor),
                        rect.top() - 60 + vp.height() / (2 * floor),
                    )
                )
            self._fit_scale = natural
        self._scale_changed()

    # ---- mouse: pick, rubber band, pan -------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        button = event.button()
        if button == Qt.MouseButton.MiddleButton or (
            button == Qt.MouseButton.LeftButton and self._space
        ):
            self._pan_last = pos  # pan: no unit moves, nothing is picked
            self._space_used = True
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if button == Qt.MouseButton.LeftButton and self.ctl.tool == "select":
            item = self.itemAt(pos)
            at = self.mapToScene(pos)
            if not isinstance(item, UnitItem) and self.zoom_scale() >= METRICS.far_lod:
                link = self.dscene.chip_at(at)  # a label picks its own link, whatever lies under
                if link is not None:
                    link.click(event.modifiers())
                    event.accept()
                    return
            if item is None or isinstance(item, ZoneItem):
                self._begin_band(at, pos, event.modifiers())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.ctl.tool == "select"
            and not isinstance(self.itemAt(pos), UnitItem)
            and self.zoom_scale() >= METRICS.far_lod
        ):
            link = self.dscene.chip_at(self.mapToScene(pos))
            if link is not None:  # a double-click on a label opens its own link
                link.open_plan()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._pan_last is not None:
            d = pos - self._pan_last
            self._pan_last = pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - d.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - d.y())
            event.accept()
            return
        if self._band_origin is not None:
            if self._band is not None or (pos - self._band_origin_view).manhattanLength() >= 4:
                self._band = QRectF(self._band_origin, self.mapToScene(pos)).normalized()
                self._band_select()
                self.viewport().update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._pan_last is not None and event.button() in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.LeftButton,
        ):
            self._pan_last = None
            self._set_hand()
            event.accept()
            return
        if self._band_origin is not None and event.button() == Qt.MouseButton.LeftButton:
            self._band_origin = self._band = None
            self.viewport().update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _set_hand(self) -> None:
        if self._space:
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.viewport().unsetCursor()

    def _begin_band(self, at: QPointF, pos: QPoint, mods: Qt.KeyboardModifier) -> None:
        """A press on the background: it clears the selection and a drag draws a rubber band."""
        additive = bool(
            mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        )
        self._band_origin, self._band_origin_view, self._band = at, pos, None
        self._band_base = tuple(self.ctl.selected) if additive else ()
        self._band_hits = ()
        if not additive:
            self.ctl.select(None)

    def band_items(self, rect: QRectF) -> list[tuple[str, str]]:
        """The units a rectangle touches and the links it holds entirely."""
        scene = self.dscene
        found: list[tuple[str, str]] = [
            ("unit", uid)
            for uid, it in sorted(scene.unit_items.items())
            if rect.intersects(QRectF(it.pos().x(), it.pos().y(), W, it.height()))
        ]
        found += [
            ("interface", iid)
            for iid, link in sorted(scene.link_items.items())
            if link.poly and rect.contains(link.path().boundingRect())
        ]
        return found

    def _band_select(self) -> None:
        if self._band is None:
            return
        hits = tuple(self.band_items(self._band))
        if hits != self._band_hits:
            self._band_hits = hits
            self.ctl.select_many([*self._band_base, *hits])  # type: ignore[list-item]

    # ---- context menu ------------------------------------------------------------------------------
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        pos = event.pos()
        at = self.mapToScene(pos)
        item = self.itemAt(pos)
        kind: str | None = None
        ident: str | None = None
        if isinstance(item, UnitItem):
            kind, ident = "unit", item.unit_id
        else:
            link = item if isinstance(item, LinkItem) else self.dscene.chip_at(at)
            if link is not None:
                kind, ident = "interface", link.interface_id
        if kind and ident and not self.ctl.is_selected(kind, ident):
            self.ctl.select(kind, ident)  # the menu is about what was clicked
        menu = self.build_context_menu(kind, ident, at)
        self.last_menu = menu
        self.exec_menu(menu, event.globalPos())
        event.accept()

    def _mirror(self, menu: QMenu, name: str, text: str | None = None) -> QAction | None:
        """An entry that does what the window's action of that name does. An entry that cannot be
        used stays in the menu, greyed out, with the reason after its name and as its tooltip."""
        act = self.menu_actions.get(name)
        if act is None:
            return None
        label = (text or act.text()).replace("&", "")
        keys = act.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        entry = QAction(menu)
        entry.setText(label + (f"\t{keys}" if keys else ""))
        if not act.isEnabled():
            why = act.toolTip()
            entry.setEnabled(False)
            if why and why != act.text():
                entry.setText(f"{label} — {why}" + (f"\t{keys}" if keys else ""))
                entry.setToolTip(why)
        entry.triggered.connect(lambda _c=False: act.trigger())
        menu.addAction(entry)
        return entry

    def _entry(
        self, menu: QMenu, text: str, slot: Callable[[], None], why_not: str = ""
    ) -> QAction:
        entry = QAction(f"{text} — {why_not}" if why_not else text, menu)
        entry.setEnabled(not why_not)
        if why_not:
            entry.setToolTip(why_not)
        entry.triggered.connect(lambda _c=False: slot())
        menu.addAction(entry)
        return entry

    def build_context_menu(self, kind: str | None, ident: str | None, at: QPointF) -> QMenu:
        """The right-click menu for a unit, a link or the background, from the window's actions."""
        ctl = self.ctl
        menu = QMenu(self)
        menu.setObjectName("diagram-menu")
        menu.setToolTipsVisible(True)
        ro = strings.WHY_READ_ONLY if ctl.read_only else ""
        if kind == "unit" and ident:
            self._entry(menu, strings.CM_OPEN_PLAN, lambda: ctl.request_open("unit", ident))
            menu.addSeparator()
            self._mirror(menu, "duplicate")
            self._mirror(menu, "redundant")
            types = menu.addMenu(strings.CM_CONNECT_FROM)
            types.setToolTipsVisible(True)
            if ro:
                types.setEnabled(False)
                types.menuAction().setText(f"{strings.CM_CONNECT_FROM} — {ro}")
            for tid, t in sorted(ctl.project.interface_types.items()):
                self._entry(types, t.name, partial(self._connect_from, tid, ident))
            self._align_menus(menu)
            menu.addSeparator()
            self._mirror(menu, "delete")
        elif kind == "interface" and ident:
            self._entry(menu, strings.CM_OPEN_PLAN, lambda: ctl.request_open("interface", ident))
            i = ctl.project.interfaces.get(ident)
            if i is not None and any(e.auto for e in i.endpoints):
                self._entry(menu, strings.CONFIRM_AUTO, lambda: ctl.confirm_interface(ident), ro)
            menu.addSeparator()
            self._mirror(menu, "delete")
        else:
            add = menu.addMenu(strings.CM_ADD_HERE)
            add.setObjectName("diagram-menu-add")
            add.setToolTipsVisible(True)
            if ro:
                add.setEnabled(False)
                add.menuAction().setText(f"{strings.CM_ADD_HERE} — {ro}")
            for tid, tpl in edit.TEMPLATES.items():
                self._entry(add, tpl.label, partial(self._add_here, tid, at))
            menu.addSeparator()
            for name in ("select_all", "find", "fit", "zoom100", "zoom_selection", "arrange"):
                self._mirror(menu, name)
        return menu

    def _align_menus(self, menu: QMenu) -> None:
        enough = len(self.ctl.selected_ids("unit"))
        for title, names, need, why in (
            (
                strings.A_ALIGN,
                (
                    "align_left",
                    "align_hcenter",
                    "align_right",
                    "align_top",
                    "align_vmiddle",
                    "align_bottom",
                ),
                2,
                strings.WHY_NEED_TWO_UNITS,
            ),
            (
                strings.A_DISTRIBUTE,
                ("distribute_h", "distribute_v"),
                3,
                strings.WHY_NEED_THREE_UNITS,
            ),
        ):
            sub = menu.addMenu(title)
            sub.setToolTipsVisible(True)
            if self.ctl.read_only:
                sub.setEnabled(False)
                sub.menuAction().setText(f"{title} — {strings.WHY_READ_ONLY}")
            elif enough < need:
                sub.setEnabled(False)
                sub.menuAction().setText(f"{title} — {why}")
            for name in names:
                self._mirror(sub, name)

    def _connect_from(self, type_id: str, unit_id: str) -> None:
        ctl = self.ctl
        ctl.begin_connect(type_id)
        if ctl.mode == "guided":
            ctl.pick(unit_id)

    def _add_here(self, template_id: str, at: QPointF) -> None:
        x = max(0.0, round((at.x() - W / 2) / GRID) * GRID)
        y = max(0.0, round(at.y() / GRID) * GRID)
        uid = self.ctl.add_unit(template_id, x, y)
        if uid:
            self.focus_unit(uid)

    # ---- keys --------------------------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Space and not event.modifiers() & ~Qt.KeyboardModifier.ShiftModifier:
            if not event.isAutoRepeat():
                self._space, self._space_used = True, False
                self._set_hand()
            event.accept()  # (Space on a focused unit selects it when it is let go, below)
            return
        if key == Qt.Key.Key_Escape:
            if self.search.isVisible():
                self.search.close_bar()
                event.accept()
                return
            self.ctl.end_connect()
            if self.ctl.tool == "select":
                self.ctl.select(None)  # Escape also takes the focus off a selection
            event.accept()
            return
        if key == Qt.Key.Key_Delete and self.ctl.read_only and self.ctl.selected:
            self.ctl.refuse_read_only()  # (the Delete action is off in a read-only project)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            was_used = self._space_used
            self._space = False
            self._set_hand()
            item = self.dscene.focusItem()
            if not was_used and item is not None and hasattr(item, "activate"):
                item.activate()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event: object) -> None:
        self._space = False
        self._pan_last = None
        self._set_hand()
        super().focusOutEvent(event)  # type: ignore[arg-type]

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

    # ---- going to things ---------------------------------------------------------------------------
    def reveal(self, unit_id: str) -> None:
        """Scroll a unit into view without changing keyboard focus."""
        item = self.dscene.unit_items.get(unit_id)
        if item is not None:
            self.ensureVisible(item, 40, 40)

    def center_on_object(self, kind: str, ident: str) -> None:
        """Put a unit or the label of a link in the middle of the view (the zoom stays)."""
        scene = self.dscene
        if kind == "unit":
            unit = scene.unit_items.get(ident)
            if unit is not None:
                self.centerOn(unit)
            return
        link = scene.link_items.get(ident)
        if link is not None:
            chip = scene.chip_rect(ident)
            self.centerOn(
                chip.center() if chip is not None else link.path().boundingRect().center()
            )

    def focus_unit(self, unit_id: str) -> None:
        item = self.dscene.unit_items.get(unit_id)
        if item is not None:
            self.center_on_object("unit", unit_id)
            item.setFocus()

    def focus_link(self, interface_id: str) -> None:
        item = self.dscene.link_items.get(interface_id)
        if item is not None:
            self.center_on_object("interface", interface_id)
            item.setFocus()

    # ---- background and foreground -----------------------------------------------------------------
    def drawBackground(self, painter: QPainter, rect: QRectF | QRect) -> None:
        super().drawBackground(painter, rect)
        scale = self.zoom_scale()
        if not self.dscene.snap_to_grid or scale < METRICS.grid_min_scale:
            return
        step = GRID if scale >= 1.0 else 2 * GRID  # dots no closer than a few screen pixels
        x0, y0 = math.floor(rect.left() / step) * step, math.floor(rect.top() / step) * step
        cols, rows = int(rect.width() / step) + 2, int(rect.height() / step) + 2
        if cols * rows > 40000:
            return
        dot = QColor(self.theme.color("border"))
        dot.setAlpha(110)
        painter.setPen(QPen(dot, 0))
        painter.drawPoints(
            QPolygonF(
                [QPointF(x0 + c * step, y0 + r * step) for c in range(cols) for r in range(rows)]
            )
        )

    def drawForeground(self, painter: QPainter, rect: QRectF | QRect) -> None:
        super().drawForeground(painter, rect)
        if self._band is None:
            return
        fill = QColor(self.theme.color("primary"))
        fill.setAlpha(40)
        painter.setBrush(fill)
        painter.setPen(QPen(self.theme.color("primary"), 0, Qt.PenStyle.DashLine))
        painter.drawRect(self._band)
