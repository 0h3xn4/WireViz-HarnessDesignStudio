"""The cables a person drew on the diagram: saved loose ends and plugged ends (M4c, D-201).

`core.cable_ends.drawn_ends` says which ends there are; this module draws each one as an item of
the scene (`DiagramScene.end_items`, by connector ID): a line out of the port the harness plugs into
and, for a **loose end**, a plug with a dashed outline and the words *open end* at the place the
diagram gives it (`cable.loose_spot`) moved by the mark `pos:<connector id>`; for an end that is
**plugged** into another device, a line to that port with a dot at each end. A press on the plug of a
loose end is the cable layer's (`gui/canvas_cable.py`: a click selects it, a drag moves it or plugs
it in); a press on the line selects the end. The tooltip says what the end is. Nothing here changes
the project; the items read it and are rebuilt when a harness changes.
"""

import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QFontMetrics, QPainter, QPainterPath, QPainterPathStroker
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from harness_design_studio.core.cable_ends import CableEnd, pos_mark
from harness_design_studio.core.origin import harness_origin
from harness_design_studio.gui import cable as cb
from harness_design_studio.gui import strings

if TYPE_CHECKING:
    from harness_design_studio.gui.canvas import DiagramScene

PLUG_LEN, PLUG_HALF_W = 16.0, 7.0  # the open plug of a loose end (scene units)
LINE_W = 2.5  # the cable line, as wide as the line of a connection
PICK_W = 10.0  # how wide the line is for a press and the tooltip
PAD = 24.0  # room around the line for the plug, the words and the selection ring


class CableEndItem(QGraphicsItem):
    """One end of a cable drawn by hand: its line and, when loose, its open plug."""

    def __init__(self, scene: DiagramScene, end: CableEnd) -> None:
        super().__init__()
        self.dscene = scene
        self.end = end
        self.points: list[tuple[float, float]] = []
        self.spot = (0.0, 0.0)  # where the end is (the plug of a loose end, the port of a plugged)
        self._path = QPainterPath()
        self._bounds = QRectF()
        self._hit = QPainterPath()
        self.setZValue(1.3)  # over the lines of connections, under the cards
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.update_path()

    @property
    def connector_id(self) -> str:
        return self.end.connector_id

    # ---- geometry ---------------------------------------------------------------------------
    def anchor(self) -> cb.Port:
        """The port the cable comes out of, as it stands now."""
        e = self.end
        return self.dscene.cable.port_now(cb.Port(e.anchor_unit, e.anchor))

    def home(self) -> tuple[float, float]:
        """Where a loose end hangs before the mark moves it."""
        return cb.loose_spot(self.anchor(), self.end.index)

    def set_end(self, end: CableEnd) -> None:
        if end != self.end:
            self.end = end
        self.update_path()

    def update_path(self) -> None:
        """Follow the devices and the mark; repaint only when something moved."""
        e = self.end
        a = self.anchor()
        if e.loose:
            hx, hy = self.home()
            shift = self.dscene.mark_shift(pos_mark(e.connector_id))
            spot = (hx + shift.x(), hy + shift.y())
        else:
            spot = self.dscene.cable.port_now(cb.Port(e.target_unit, e.target)).at
        pts = cb.route(a, spot)
        if pts == self.points and spot == self.spot:
            return
        self.prepareGeometryChange()
        self.points, self.spot = pts, spot
        path = QPainterPath(QPointF(*pts[0]))
        for x, y in pts[1:]:
            path.lineTo(x, y)
        self._path = path
        stroker = QPainterPathStroker()
        stroker.setWidth(PICK_W)
        hit = stroker.createStroke(path)
        if e.loose:
            hit.addRect(self.plug_rect())
        self._hit = hit
        self._bounds = path.boundingRect().adjusted(-PAD, -PAD, PAD + 60.0, PAD)
        self.update()

    def plug_rect(self) -> QRectF:
        """Where the open plug of a loose end is (around its spot), for a press and a ring."""
        x, y = self.spot
        r = PLUG_LEN
        return QRectF(x - r, y - r, 2 * r, 2 * r)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return self._bounds

    def shape(self) -> QPainterPath:
        return self._hit

    # ---- what it says -----------------------------------------------------------------------
    def tooltip(self) -> str:
        e = self.end
        project = self.dscene.ctl.project
        h = project.harnesses.get(e.harness_id)
        name = h.name if h is not None else e.harness_id
        if e.loose:
            return strings.LOOSE_TIP.format(
                harness=e.harness_id, name=name, end=e.connector_id, pins=e.pins,
                port=self._port_name(e.anchor),
            )  # fmt: skip
        origin = harness_origin(project, e.harness_id)
        return strings.DRAWN_CABLE_TIP.format(
            harness=e.harness_id, name=name, a=self._port_name(e.anchor),
            b=self._port_name(e.target), origin=strings.ORIGIN_WORDS[origin],
        )  # fmt: skip

    def _port_name(self, box_id: str) -> str:
        c = self.dscene.ctl.project.connectors.get(box_id)
        return f"{c.unit_id} {c.name}" if c is not None and c.unit_id else box_id

    # ---- painting ---------------------------------------------------------------------------
    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        if not self.points:
            return
        sc = self.dscene
        th = sc.theme
        selected = sc.ctl.selected_end == self.end.connector_id
        layer = sc.cable
        carried = layer.cable.active and layer.cable.end_id == self.end.connector_id
        token = "primary" if selected else "text-muted"
        width = 4.0 if selected else LINE_W
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if carried:  # the end is in hand: where it was waits as a ghost
            painter.setOpacity(0.35)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(sc.pen(token, width))
        painter.drawPath(self._path)
        painter.setPen(sc.pen(token, 2))
        painter.setBrush(QBrush(th.color("bg")))
        x0, y0 = self.points[0]
        painter.drawEllipse(QPointF(x0, y0), cb.PLUG_DOT, cb.PLUG_DOT)
        if not self.end.loose:
            x1, y1 = self.points[-1]
            painter.drawEllipse(QPointF(x1, y1), cb.PLUG_DOT, cb.PLUG_DOT)
            return
        self._paint_open_plug(painter, token)
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        if lod >= 0.35 or selected:
            font = sc.px_font(th.type("small"))
            painter.setFont(font)
            fm = QFontMetrics(font)
            text = strings.LOOSE_CAPTION.format(name=self.end.name)
            x, y = self.spot
            painter.setPen(th.color("text-muted"))
            painter.drawText(QPointF(x - fm.horizontalAdvance(text) / 2, y + PLUG_LEN + 6), text)
        if selected:
            painter.setPen(sc.pen("focus", 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.plug_rect().adjusted(-2, -2, 2, 2))

    def _paint_open_plug(self, painter: QPainter, token: str) -> None:
        """The plug at a loose end, pointing the way the cable arrives, with a dashed outline and no
        contacts: an end with no connector chosen yet (the drawing of M4b draws it dashed too)."""
        dx, dy = cb.plug_direction(self.points)
        x, y = self.spot
        painter.save()
        painter.translate(x, y)
        painter.rotate(math.degrees(math.atan2(dy, dx)))
        body = QRectF(-PLUG_LEN / 2, -PLUG_HALF_W, PLUG_LEN, 2 * PLUG_HALF_W)
        painter.setBrush(QBrush(self.dscene.theme.color("bg")))
        painter.setPen(self.dscene.pen(token, 2, Qt.PenStyle.DashLine))
        painter.drawRoundedRect(body, 3, 3)
        painter.restore()

    # ---- the pointer ------------------------------------------------------------------------
    def hoverEnterEvent(self, event: object) -> None:  # noqa: N802
        self.setToolTip(self.tooltip())
        super().hoverEnterEvent(event)  # type: ignore[arg-type]

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        """A press on the line picks the end (the plug of a loose end is the cable layer's)."""
        self.dscene.ctl.select_end(self.end.connector_id)
        event.accept()


__all__ = ["CableEndItem"]
