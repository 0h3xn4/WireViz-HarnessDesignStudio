"""The cable in hand on the diagram: ports, the rubber band, the loose end and the pointer.

`gui/cable.py` decides (state machine, snapping, what a port accepts); this module looks things up
on the scene (where the ports are, what lies under the pointer), draws the cable in the view's
foreground and does what the decision says: it asks for a connection through the same signal the
Connect tool uses (`EditorController.linkRequested`: the window *Link connectors*, or at once in
Quick mode), moves the end of a connection (`EditorController.move_link_end`, one undo step), or
leaves a **saved loose end** (M4c, D-201): a cable let go on empty ground becomes a harness drawn
by hand with one end plugged into the port and the other end loose where it was let go
(`EditorController.leave_loose_end`, one undo step; `gui/canvas_ends.py` draws it). A saved loose
end is picked up again by its plug: dropped on a port it plugs in
(`EditorController.plug_loose_end`), dropped on empty ground it moves (the mark `pos:`, outside the
model hash), a click selects it. Esc puts away what is in hand and changes nothing.

Only the end of a *connection* let go on empty ground stays a draft of this window (a connection
always joins two connectors): it is not in the project, the model hash or any file, and saving
the project, a click on empty ground or Esc drop it.

The press, move and release come from `DiagramView`, which asks `press_at` first: a press that is
not on a port, on the plug of a connection or on a loose end is not ours and the diagram goes on
as before (devices are moved, labels dragged, the rubber band drawn).
"""

import math
from dataclasses import replace
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QPainter, QPainterPath, QPen

from harness_design_studio.core import cable_ends, describe
from harness_design_studio.gui import cable as cb
from harness_design_studio.gui.canvas_ends import CableEndItem
from harness_design_studio.gui import strings
from harness_design_studio.gui.theme import ThemeManager

if TYPE_CHECKING:
    from harness_design_studio.gui.canvas import DiagramScene, DiagramView, UnitItem
    from harness_design_studio.gui.controller import EditorController

PORT_W, PORT_H = 14.0, 14.0  # the square of a port on a card (as `UnitItem.port_rect`)
GRAB_IN = 10.0  # how far into the card the grab zone of a port reaches
GRAB_OUT = 2.0  # ... and how far out (the plug of a connection owns the rest)
GRAB_HALF_H = 9.0  # half the height of the grab zone
PLUG_LEN, PLUG_HALF_W = 12.0, 5.0  # the plug end drawn on a cable
RING = 3.0  # how far a highlight ring stands off a port
BAND_W = 3.0  # the width of the cable line
TICK_MS = 30  # the view scrolls this often while a cable is near its edge
GROW = 200.0  # the scene grows this far past a carried cable (scene units)
Spot = tuple[float, float]


def _xy(p: QPointF) -> Spot:
    return (p.x(), p.y())


class CableLayer:
    """The cable of one diagram (`DiagramScene.cable`)."""

    def __init__(self, scene: DiagramScene) -> None:
        self.scene = scene
        self.view: DiagramView | None = None  # set by `attach`
        self.cable = cb.Cable()
        self.occ: cb.Occupancy | None = None
        self.hover: cb.Port | None = None  # the port under the pointer, at rest
        self._unit_ok: dict[str, bool] = {}
        self._old: tuple[str, str] = ("", "")  # (device, connector) a picked-up end came from
        self._vpos = QPoint()  # the pointer, in view coordinates
        self._grown = False
        self._tick: QTimer | None = None  # scrolls the view at its edge; owned by the view
        scene.ctl.projectSaved.connect(self.forget)
        scene.ctl.changed.connect(self._model_changed)
        scene.ctl.connectChanged.connect(self._tool_changed)

    def attach(self, view: DiagramView) -> None:
        """The view this layer works for (its scale, scroll bars and cursor). The timer belongs to
        the view, so it goes with it."""
        self.view = view
        self._tick = QTimer(view)
        self._tick.setInterval(TICK_MS)
        self._tick.timeout.connect(self._scroll_tick)

    # ---- asking ------------------------------------------------------------------------------
    @property
    def ctl(self) -> EditorController:
        return self.scene.ctl

    @property
    def active(self) -> bool:
        return self.cable.active

    @property
    def busy(self) -> bool:
        return self.cable.busy or self.cable.draft is not None

    def scale(self) -> float:
        return self.view.zoom_scale() if self.view is not None else 1.0

    def enabled(self) -> bool:
        """Cables are picked up with the Select tool, in a project that can change, once the cards
        are big enough to show their ports."""
        from harness_design_studio.gui.canvas import METRICS

        return (
            self.ctl.tool == "select"
            and not self.ctl.read_only
            and self.scale() >= METRICS.overview_lod
        )

    def moving(self, link_id: str) -> bool:
        """The connection whose end is in hand (or loose): it is drawn as a ghost until the end is
        plugged in again."""
        c = self.cable
        return bool(link_id) and (
            (c.active and c.replaces == link_id)
            or (c.draft is not None and c.draft.replaces == link_id)
        )

    # ---- ports -------------------------------------------------------------------------------
    def ports_of(self, item: UnitItem) -> list[cb.Port]:
        """The ports of a card where it stands: one for each connector in Expert mode, one for the
        device in Guided mode (the tool picks the connector there, as when two devices are
        clicked)."""
        from harness_design_studio.gui.canvas import W

        pos = item.pos()
        if self.ctl.mode == "expert":
            out = []
            for k, c in enumerate(item.connectors()):
                side = item.port_side(str(c.id))
                x = pos.x() + (W if side == "right" else 0.0)
                out.append(cb.Port(item.unit_id, str(c.id), x, pos.y() + item.port_y(k), side))
            return out
        side = item.side()
        x = pos.x() + (W if side == "right" else 0.0)
        return [cb.Port(item.unit_id, "", x, pos.y() + item.height() / 2, side)]

    @staticmethod
    def port_rect(port: cb.Port) -> QRectF:
        """The square a port is drawn as, in scene coordinates."""
        return QRectF(port.x - PORT_W / 2, port.y - PORT_H / 2, PORT_W, PORT_H)

    def port_now(self, port: cb.Port) -> cb.Port:
        """The port as it stands now (a card may have moved since the cable was picked up)."""
        item = self.scene.unit_items.get(port.unit_id)
        if item is None:
            return port
        ports = self.ports_of(item)
        found = next((p for p in ports if p.key == port.key), None)
        if found is not None:
            return found
        return replace(ports[0], connector_id=port.connector_id) if ports else port

    def _items_near(self, at: QPointF, reach: float) -> list[UnitItem]:
        from harness_design_studio.gui.canvas import UnitItem

        region = QRectF(at.x() - reach, at.y() - reach, 2 * reach, 2 * reach)
        return [i for i in self.scene.items(region) if isinstance(i, UnitItem)]

    def ports_near(self, at: QPointF, reach: float) -> list[cb.Port]:
        out: list[cb.Port] = []
        for item in sorted(self._items_near(at, reach), key=lambda i: i.unit_id):
            out += self.ports_of(item)
        return out

    def landing(self, at: QPointF) -> cb.Landing:
        """What is under a carried cable end: a port (snapped), a card, or nothing."""
        scale = self.scale()
        port = cb.nearest(self.ports_near(at, cb.SNAP_PX / scale + PORT_W), _xy(at), scale)
        if port is not None:
            return cb.Landing("port", port, port.unit_id)
        for item in self._items_near(at, 1.0):
            if item.shape().translated(item.pos()).contains(at):
                return cb.Landing("card", unit_id=item.unit_id)
        return cb.Landing()

    # ---- what a start spot is ----------------------------------------------------------------
    def start_spot(self, at: QPointF) -> tuple[str, object] | None:
        """What a press at scene point `at` would pick up: ("draft", Draft), ("saved", the item of
        a saved loose end), ("plug", (link ID, end, the port of the other end)) or ("port",
        Port); None for anything else. The loose ends come first, then the plug of a connection,
        then a port."""
        scale = self.scale()
        d = self.cable.draft
        if d is not None and self._near(at, d.end, cb.PLUG_PX + 4.0, scale):
            return ("draft", d)
        saved = self._saved_at(at, scale)
        if saved is not None:
            return ("saved", saved)
        plug = self._plug_at(at, scale)
        if plug is not None:
            return ("plug", plug)
        for p in self.ports_near(at, GRAB_IN + 4.0):
            if self._grab_zone(p).contains(at):
                return ("port", p)
        return None

    def _saved_at(self, at: QPointF, scale: float) -> CableEndItem | None:
        """The saved loose end whose plug is under the point (the nearest, by ID on a tie)."""
        best: CableEndItem | None = None
        best_d = 0.0
        for cid, item in sorted(self.scene.end_items.items()):
            if not item.end.loose or not self._near(at, item.spot, cb.PLUG_PX + 6.0, scale):
                continue
            d = (at.x() - item.spot[0]) ** 2 + (at.y() - item.spot[1]) ** 2
            if best is None or d < best_d:
                best, best_d = item, d
        return best

    @staticmethod
    def _near(at: QPointF, spot: Spot, radius_px: float, scale: float) -> bool:
        r = radius_px / max(scale, 1e-9)
        return (at.x() - spot[0]) ** 2 + (at.y() - spot[1]) ** 2 <= r * r

    @staticmethod
    def _grab_zone(port: cb.Port) -> QRectF:
        """Where a press on a port picks up a new cable: the inner part of its square."""
        top = port.y - GRAB_HALF_H
        if port.side == "right":
            return QRectF(port.x - GRAB_IN, top, GRAB_IN + GRAB_OUT, 2 * GRAB_HALF_H)
        return QRectF(port.x - GRAB_OUT, top, GRAB_IN + GRAB_OUT, 2 * GRAB_HALF_H)

    def _plug_at(self, at: QPointF, scale: float) -> tuple[str, str, cb.Port] | None:
        """The plugged-in end of a connection under the point: (connection, "a" or "b", the port of
        the OTHER end, which stays where it is when this one is picked up)."""
        project = self.ctl.project
        expert = self.ctl.mode == "expert"
        for lid, line in sorted(self.scene.connection_items.items()):
            poly, link = line.poly, project.links.get(lid)
            if link is None or len(poly) < 2:
                continue
            for first, end in ((True, "a"), (False, "b")):
                if not self._near(at, cb.plug_spot(poly, first), cb.PLUG_PX, scale):
                    continue
                there = project.connectors.get(link.b_connector if end == "a" else link.a_connector)
                if there is None or not there.unit_id:
                    return None
                x, y = poly[-1] if first else poly[0]
                nxt = poly[-2] if first else poly[1]
                side = "right" if nxt[0] > x else "left"
                return (lid, end, cb.Port(there.unit_id, there.id if expert else "", x, y, side))
        return None

    # ---- the gesture: press, move, release ---------------------------------------------------
    def press_at(self, at: QPointF, vpos: QPoint) -> bool:
        """The left button went down at scene point `at`. True when the cable took it."""
        c = self.cable
        self._vpos = vpos
        if not self.enabled():
            return False
        if c.state == cb.HOLD:  # a click puts the held cable down
            landing, reason, unchanged = self._decide(at)
            self._finish(
                c.put_down(_xy(at), landing, refused=reason, unchanged=unchanged), _xy(at)
            )
            return True
        spot = self.start_spot(at)
        if spot is None:
            return False
        kind, what = spot
        project = self.ctl.project
        if kind == "draft" and isinstance(what, cb.Draft):
            self.occ = cb.Occupancy.of(project, ignoring=what.replaces)
            self._old = self._old_of(what.replaces, what.replaces_end)
            c.grab_draft(_xy(at))
        elif kind == "saved" and isinstance(what, CableEndItem):
            self.occ = cb.Occupancy.of(project)
            self._old = ("", "")
            c.press(what.anchor(), _xy(at), start=cb.SAVED, end_id=what.connector_id)
        elif kind == "plug" and isinstance(what, tuple):
            lid, end, anchor = what
            self.occ = cb.Occupancy.of(project, ignoring=lid)
            self._old = self._old_of(lid, end)
            c.press(anchor, _xy(at), start=cb.REPLUG, replaces=lid, end=end)
        elif isinstance(what, cb.Port):
            self.occ = cb.Occupancy.of(project)
            self._old = ("", "")
            c.press(what, _xy(at))
        else:
            return False
        self._unit_ok.clear()
        if self.view is not None:
            self.view.setFocus()
        return True

    def _old_of(self, link_id: str, end: str) -> tuple[str, str]:
        link = self.ctl.project.links.get(link_id)
        if link is None:
            return ("", "")
        cid = link.a_connector if end == "a" else link.b_connector
        conn = self.ctl.project.connectors.get(cid)
        return ((conn.unit_id or "") if conn else "", cid)

    def _decide(self, at: QPointF) -> tuple[cb.Landing, str, bool]:
        """What is under the cable end at `at`, why it refuses (or ""), and whether the end is back
        on the connector it came from (or the cable on its own port): nothing to do then."""
        landing = self.landing(at)
        anchor = self.cable.anchor
        target: cb.Port | None = None
        if landing.kind == "port":
            target = landing.port
        elif landing.kind == "card":
            target = cb.Port(landing.unit_id)
        reason = ""
        unchanged = False
        if target is not None and anchor is not None:
            if self.occ is not None:
                reason = cb.refusal(self.ctl.project, self.occ, anchor, target)
            if self.cable.replaces:
                same = target.key == self._old or (
                    not target.connector_id and target.unit_id == self._old[0]
                )
                unchanged = same and not reason
            elif landing.kind == "port" and target.key == anchor.key:
                unchanged, reason = True, ""
        return landing, reason, unchanged

    def on_move(self, at: QPointF, vpos: QPoint) -> bool:
        """The pointer moved. True when the cable used the move (the diagram does nothing else)."""
        c = self.cable
        self._vpos = vpos
        if c.state == cb.IDLE:
            self._hover_at(at)
            return False
        if c.state == cb.PRESSED and not c.move(_xy(at), scale=self.scale()):
            return True
        self._carry(at)
        return True

    def _carry(self, at: QPointF) -> None:
        c = self.cable
        c.move(_xy(at), scale=self.scale())
        c.over(self.landing(at))
        self._grow(at)
        self._cursor(Qt.CursorShape.ClosedHandCursor)
        self._say_hint()
        self._start_ticks()
        self._repaint()

    def on_release(self, at: QPointF) -> bool:
        """The left button came up. True when it ended a gesture of the cable."""
        c = self.cable
        if c.state not in (cb.PRESSED, cb.CARRY):
            return False
        landing, reason, unchanged = self._decide(at)
        self._finish(c.release(_xy(at), landing, refused=reason, unchanged=unchanged), _xy(at))
        return True

    def follow(self) -> None:
        """The view scrolled under a carried cable: the end stays under the pointer."""
        if self.view is not None and self.cable.active:
            self._carry(self.view.mapToScene(self._vpos))

    def _scroll_tick(self) -> None:
        view = self.view
        if view is None or not (self.cable.active or view.unit_drag):
            self._stop_ticks()
            return
        port = view.viewport()
        dx, dy = cb.edge_scroll(port.width(), port.height(), (self._vpos.x(), self._vpos.y()))
        if dx or dy:
            h, v = view.horizontalScrollBar(), view.verticalScrollBar()
            h.setValue(h.value() + round(dx))
            v.setValue(v.value() + round(dy))
            if self.cable.active:
                self.follow()

    def drag_scroll(self, vpos: QPoint) -> None:
        """A device is being dragged: note the pointer; the view scrolls at its edge."""
        self._vpos = vpos
        self._start_ticks()

    def _start_ticks(self) -> None:
        if self._tick is not None and not self._tick.isActive():
            self._tick.start()

    def _stop_ticks(self) -> None:
        if self._tick is not None:
            self._tick.stop()

    # ---- ending ------------------------------------------------------------------------------
    def escape(self) -> bool:
        """Esc: put away what is in hand and drop the loose end. True when there was either."""
        if not self.busy:
            return False
        self.cable.cancel()
        self._after()
        return True

    def forget(self) -> None:
        """Drop everything silently (the project was saved or replaced)."""
        if not self.busy:
            return
        self.cable.cancel()
        self._after()

    def drop_on_empty(self) -> None:
        """A click on empty ground: a loose end is thrown away."""
        if self.cable.drop_draft():
            self._after()

    def _tool_changed(self) -> None:
        """The Connect tool was picked: it has its own two clicks, so a cable in hand is put away."""
        if self.ctl.tool != "select":
            self.forget()

    def _model_changed(self, delta: object) -> None:
        """A new project drops everything; a loose end whose device or connector went is dropped,
        and one that replaced a connection that is gone becomes a plain new cable."""
        self._unit_ok.clear()
        if getattr(delta, "full", False):
            self.forget()
            return
        c, project = self.cable, self.ctl.project
        if c.start == cb.SAVED and c.end_id not in self.scene.end_items:  # (undone meanwhile)
            self.forget()
            return
        anchor = c.anchor if c.busy else (c.draft.anchor if c.draft else None)
        if anchor is None:
            return
        if anchor.unit_id not in project.units or (
            anchor.connector_id and anchor.connector_id not in project.connectors
        ):
            self.forget()
            return
        d = c.draft
        if d is not None and d.replaces and d.replaces not in project.links:
            c.draft = replace(d, replaces="", replaces_end="")

    # ---- results -----------------------------------------------------------------------------
    def _finish(self, out: cb.Outcome, at: Spot = (0.0, 0.0)) -> None:
        self._after(say=False)
        ctl = self.ctl
        if out.kind == "click":
            if out.start == cb.NEW and out.anchor is not None:
                ctl.select("unit", out.anchor.unit_id)
            elif out.start == cb.REPLUG:
                ctl.select_link(out.replaces)
            elif out.start == cb.SAVED:
                ctl.select_end(out.end_id)
        elif out.kind == "loose" and not out.replaces and out.anchor is not None:
            self.cable.drop_draft()  # the cable is saved instead: a harness with a loose end
            self._leave(out.anchor, at)
        elif out.kind == "place":
            item = self.scene.end_items.get(out.end_id)
            if item is not None:
                hx, hy = item.home()
                ctl.move_loose_end(out.end_id, at[0] - hx, at[1] - hy)
        elif out.kind == "plug":
            t = out.target
            ctl.plug_loose_end(
                out.end_id,
                connector_id=t.connector_id if t is not None else "",
                unit_id=t.unit_id if t is not None else out.target_unit,
            )
        elif out.kind == "connect" and out.anchor is not None:
            a, b = out.anchor, out.target
            b_unit, b_conn = (b.unit_id, b.connector_id) if b is not None else (out.target_unit, "")
            ctl.linkRequested.emit(a.unit_id, a.connector_id, b_unit, b_conn)
        elif out.kind == "replug":
            t = out.target
            ctl.move_link_end(
                out.replaces,
                out.end,
                t.connector_id if t is not None else "",
                t.unit_id if t is not None else out.target_unit,
            )
        elif out.kind == "refused":
            ctl.message.emit(self._refusal_text(out), False)
        self._say_hint()

    def _leave(self, anchor: cb.Port, at: Spot) -> None:
        """A new cable let go on empty ground: a harness drawn by hand from the port, its far end
        loose where the cable was let go (one undo step). In Guided and Quick mode the port is the
        device's, and the cable goes into its first connector that has no cable on it."""
        project = self.ctl.project
        box = anchor.connector_id or cable_ends.free_port(project, anchor.unit_id) or ""
        if not box:
            self.ctl.message.emit(strings.LOOSE_NO_PORT.format(unit=anchor.unit_id), False)
            return
        plugs = self.occ.plugs if self.occ is not None else cb.Occupancy.of(project).plugs
        if box in plugs:
            conn = project.connectors.get(box)
            name = conn.name if conn is not None else box
            self.ctl.message.emit(strings.CABLE_REFUSED_PLUGGED.format(name=name), False)
            return
        home = cb.loose_spot(self.port_now(cb.Port(anchor.unit_id, box)), 0)
        self.ctl.leave_loose_end(box, (at[0] - home[0], at[1] - home[1]))

    def _refusal_text(self, out: cb.Outcome) -> str:
        project = self.ctl.project
        unit = out.target.unit_id if out.target is not None else out.target_unit
        cid = out.target.connector_id if out.target is not None else ""
        name = project.connectors[cid].name if cid in project.connectors else unit
        if out.reason == cb.SAME_DEVICE:
            return strings.CABLE_REFUSED_SAME.format(unit=unit)
        if out.reason == cb.PLUGGED:
            return strings.CABLE_REFUSED_PLUGGED.format(name=cid or unit)
        return strings.CABLE_REFUSED_FULL.format(name=name)

    def _after(self, *, say: bool = True) -> None:
        """Back to rest (or to holding a cable): the pointer, the hint and the scene extent."""
        self.occ = None if not self.cable.busy else self.occ
        self.hover = None
        self._unit_ok.clear()
        if not (self.cable.active or (self.view is not None and self.view.unit_drag)):
            self._stop_ticks()
        self._cursor(Qt.CursorShape.ClosedHandCursor if self.cable.active else None)
        if say:
            self.ctl.cableHint.emit("")
        if self._grown and not self.cable.active:
            self._grown = False
            self.scene._update_extent()
        self._repaint()
        self.scene.update()

    def _say_hint(self) -> None:
        c, ctl = self.cable, self.ctl
        if c.active and c.start == cb.SAVED:
            text = strings.CABLE_HINT_SAVED.format(end=c.end_id)
        elif c.active and c.replaces:
            text = strings.CABLE_HINT_REPLUG.format(link=c.replaces)
        elif c.state == cb.HOLD:
            text = strings.CABLE_HINT_HELD
        elif c.active:
            text = strings.CABLE_HINT_PORTS if ctl.mode == "expert" else strings.CABLE_HINT_DEVICES
        elif c.draft is not None:
            text = strings.CABLE_HINT_LOOSE
        else:
            text = ""
        ctl.cableHint.emit(text)

    def _repaint(self) -> None:
        if self.view is not None:
            self.view.viewport().update()

    def _cursor(self, shape: Qt.CursorShape | None) -> None:
        view = self.view
        if view is None:
            return
        if shape is None:
            view.reset_cursor()
        else:
            view.viewport().setCursor(shape)

    def _grow(self, at: QPointF) -> None:
        self._grown = True
        self.scene.grow_to(QRectF(at.x() - GROW, at.y() - GROW, 2 * GROW, 2 * GROW))

    # ---- hover at rest -----------------------------------------------------------------------
    def _hover_at(self, at: QPointF) -> None:
        port: cb.Port | None = None
        shape: Qt.CursorShape | None = None
        if self.enabled():
            spot = self.start_spot(at)
            if spot is not None:
                shape = Qt.CursorShape.OpenHandCursor
                if spot[0] == "port" and isinstance(spot[1], cb.Port):
                    port = spot[1]
        if port != self.hover:
            old, self.hover = self.hover, port
            for p in (old, port):
                if p is not None and (item := self.scene.unit_items.get(p.unit_id)) is not None:
                    item.update()
        self._cursor(shape)

    # ---- how a port looks and what it says ---------------------------------------------------
    def port_style(self, port: cb.Port) -> str:
        """How to draw a port now: "" (as it is), "hover", "from" (where the cable comes from),
        "ok" (takes the cable in hand), "no" (does not), "snap" (the cable end is on it) or
        "snap-no" (on it, and it refuses)."""
        c = self.cable
        if c.active and c.anchor is not None and self.occ is not None:
            reason = cb.refusal(self.ctl.project, self.occ, c.anchor, port)
            if c.target is not None and c.target.key == port.key:
                return "snap-no" if reason else "snap"
            if port.unit_id == c.anchor.unit_id:
                return "from" if port.key == c.anchor.key or not c.anchor.connector_id else "no"
            return "no" if reason else "ok"
        if self.hover is not None and self.hover.key == port.key:
            return "hover"
        return ""

    def unit_state(self, unit_id: str) -> str:
        """The card's state while a cable is in hand, as the Connect tool shows it: "from" for the
        device the cable comes from, "ok" for one with a port that takes it, "no" for the rest."""
        c = self.cable
        if c.anchor is None or self.occ is None:
            return ""
        if unit_id == c.anchor.unit_id:
            return "from"
        ok = self._unit_ok.get(unit_id)
        if ok is None:
            item = self.scene.unit_items.get(unit_id)
            ports = self.ports_of(item) if item is not None else []
            ok = any(not cb.refusal(self.ctl.project, self.occ, c.anchor, p) for p in ports)
            self._unit_ok[unit_id] = ok
        return "ok" if ok else "no"

    def tip_for(self, port: cb.Port) -> str:
        """The tooltip of a port: its name, kind and free pins (or, for a device, its connectors)."""
        project = self.ctl.project
        occ = self.occ or cb.Occupancy.of(project)
        if port.connector_id and port.connector_id in project.connectors:
            conn = project.connectors[port.connector_id]
            family, pins, _gender = describe.connector_family(project, port.connector_id)
            kind = f"{family} {pins}" if pins else family
            free, total = occ.free_pins(project, port.connector_id)
            if not total:
                return strings.CABLE_PORT_TIP_NO_PINS.format(name=conn.name, kind=kind)
            return strings.CABLE_PORT_TIP.format(name=conn.name, kind=kind, free=free, pins=total)
        conns, free, total = occ.device_free(project, port.unit_id)
        if not conns:
            return strings.CABLE_DEVICE_TIP_NONE.format(unit=port.unit_id)
        return strings.CABLE_DEVICE_TIP.format(unit=port.unit_id, n=conns, free=free, pins=total)

    # ---- drawing -----------------------------------------------------------------------------
    def paint(self, painter: QPainter) -> None:
        """The cable in hand, or the loose end, over everything (the view's foreground)."""
        shown = self.cable.shown()
        if shown is None:
            return
        c, th = self.cable, self.scene.theme
        anchor = self.port_now(shown[0])
        reason = ""
        if c.active and c.target is not None and c.anchor is not None and self.occ is not None:
            reason = cb.refusal(self.ctl.project, self.occ, c.anchor, c.target)
        token = "error" if reason else "primary"
        pts = cb.route(anchor, shown[1])
        path = QPainterPath(QPointF(*pts[0]))
        for x, y in pts[1:]:
            path.lineTo(x, y)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(
            th.color(token), BAND_W, Qt.PenStyle.SolidLine if c.active else Qt.PenStyle.DashLine
        )
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.setBrush(QBrush(th.color(token)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(*anchor.at), cb.PLUG_DOT, cb.PLUG_DOT)
        _paint_plug(painter, pts, token, th)
        painter.restore()


def _paint_plug(painter: QPainter, pts: list[Spot], token: str, th: ThemeManager) -> None:
    """A small plug at the loose end, pointing the way the cable arrives."""
    dx, dy = cb.plug_direction(pts)
    x, y = pts[-1]
    painter.translate(x, y)
    painter.rotate(math.degrees(math.atan2(dy, dx)))
    body = QRectF(-PLUG_LEN, -PLUG_HALF_W, PLUG_LEN, 2 * PLUG_HALF_W)
    painter.setBrush(QBrush(th.color("bg")))
    painter.setPen(QPen(th.color(token), 2))
    painter.drawRoundedRect(body, 2, 2)
    painter.drawLine(QPointF(0, -PLUG_HALF_W / 2), QPointF(PLUG_HALF_W, -PLUG_HALF_W / 2))
    painter.drawLine(QPointF(0, PLUG_HALF_W / 2), QPointF(PLUG_HALF_W, PLUG_HALF_W / 2))
