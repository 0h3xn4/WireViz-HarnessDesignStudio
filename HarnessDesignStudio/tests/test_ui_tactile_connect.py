# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type,type-arg,assignment,index"
"""REQ-GUI-21. Owner feedback: connecting devices should feel tactile and free, as if picking up a
harness, dragging it to a port and plugging it in. In the block diagram a press on a port picks a
cable up; it follows the pointer as a rubber band, snaps to a port, and where it is let go it
connects (the window *Link connectors* for exactly those two connectors, or at once in Quick
mode), connects to the best connector of a device it is dropped on, or stays as a loose end (a
draft of the window: never saved, never in the model hash). The end of a connection can be picked
up and plugged in elsewhere. Esc puts everything away. Devices, labels and the rubber band keep
working as before."""

import os

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core import links as core_links  # noqa: E402
from harness_design_studio.core.io import layout  # noqa: E402
from harness_design_studio.core.io.saver import save_project  # noqa: E402
from harness_design_studio.gui import cable as cb  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.link_dialog import LinkDialog  # noqa: E402
from tests.gui_helpers import DialogScript, make_window  # noqa: E402
from tests.helpers import pinout_project  # noqa: E402

LEFT = Qt.MouseButton.LeftButton
SPOTS = {"OBC": (60.0, 70.0), "PCDU": (60.0, 330.0), "RW1": (520.0, 190.0)}


class World:
    """A window with three devices at known places, 100 % zoom, and a mouse that works in scene
    coordinates."""

    def __init__(self, tmp_path, *, quick: bool, mode: str, scroll: bool = True) -> None:
        self.win = make_window(tmp_path)
        p = pinout_project()
        p.harnesses.clear()
        p.interfaces.clear()
        self.win.ctl._install(p, None, None)
        if quick:
            self.win.act_quick.trigger()
        self.win.ctl.set_mode(mode)
        for uid, (x, y) in SPOTS.items():
            self.win.ctl.move_unit(uid, x, y)
        self.win.ctl.history._undo.clear()  # (the set-up is not what the tests count)
        self.view = self.win.view
        self.scene = self.view.dscene
        self.layer = self.scene.cable
        if not scroll:  # (a test of long drags must not depend on the timer that scrolls the view)
            self.layer._start_ticks = lambda: None  # type: ignore[method-assign]
        self.settle()
        self.view.zoom_100()
        self.view.centerOn(QPointF(400, 260))
        self.settle()

    # ---- looking --------------------------------------------------------------------------
    def settle(self) -> None:
        for _ in range(3):
            QApplication.processEvents()
        self.view.grab()

    @property
    def project(self):
        return self.win.ctl.project

    def steps(self) -> int:
        return len(self.win.ctl.history._undo)

    def port(self, unit: str, connector: str = "") -> cb.Port:
        """A port of a device where it is drawn (the connector's in Expert, else the device's)."""
        ports = self.layer.ports_of(self.scene.unit_items[unit])
        if connector and self.win.ctl.mode == "expert":
            return next(p for p in ports if p.connector_id == connector)
        return ports[0]

    def grab_spot(self, port: cb.Port) -> QPointF:
        """A point of a port where a press picks a new cable up (inside the card edge)."""
        inside = -4.0 if port.side == "right" else 4.0
        return QPointF(port.x + inside, port.y)

    def drop_spot(self, port: cb.Port) -> QPointF:
        return QPointF(port.x + 2.0, port.y + 1.0)

    # ---- the mouse ------------------------------------------------------------------------
    def at(self, scene_point: QPointF) -> QPoint:
        return self.view.mapFromScene(scene_point)

    def press(self, scene_point: QPointF) -> None:
        QTest.mousePress(self.view.viewport(), LEFT, pos=self.at(scene_point))
        QApplication.processEvents()

    def move(self, scene_point: QPointF) -> None:
        pos = self.at(scene_point)
        QTest.mouseMove(self.view.viewport(), pos=pos)
        QApplication.processEvents()
        if os.environ.get("HARNESS_REAL_PLATFORM"):
            # On a real platform `QTest.mouseMove` sets the cursor on the screen (`QCursor::setPos`)
            # and the window gets its move from the display a moment later: after a short wait on
            # xcb, not at all on the hosted Windows runner (REQ-GUI-26). With no button down the
            # move is then sent to the viewport as the display would have sent it. (With a button
            # down QTest sends the move itself.)
            QTest.qWait(40)
            if QApplication.mouseButtons() == Qt.MouseButton.NoButton:
                viewport = self.view.viewport()
                QApplication.sendEvent(
                    viewport,
                    QMouseEvent(
                        QEvent.Type.MouseMove,
                        QPointF(pos),
                        QPointF(viewport.mapToGlobal(pos)),
                        Qt.MouseButton.NoButton,
                        Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier,
                    ),
                )
                QApplication.processEvents()

    def release(self, scene_point: QPointF) -> None:
        QTest.mouseRelease(self.view.viewport(), LEFT, pos=self.at(scene_point))
        QApplication.processEvents()

    def click(self, scene_point: QPointF) -> None:
        self.press(scene_point)
        self.release(scene_point)

    def drag(self, a: QPointF, b: QPointF, *, release: bool = True, steps: int = 4) -> None:
        self.press(a)
        for k in range(1, steps + 1):
            self.move(a + (b - a) * k / steps)
        if release:
            self.release(b)

    def esc(self) -> None:
        QTest.keyClick(self.view, Qt.Key.Key_Escape)
        QApplication.processEvents()

    def plug(self, link_id: str, *, end: str) -> QPointF:
        """Where the plug of one end of a connection is drawn."""
        line = self.scene.connection_items[link_id]
        self.settle()
        return QPointF(*cb.plug_spot(line.poly, end == "a"))

    def status(self) -> str:
        return self.win.statusBar().currentMessage()


@pytest.fixture(params=[("expert", True), ("expert", False), ("guided", True), ("guided", False)])
def world(request, qtbot, tmp_path) -> World:
    mode, quick = request.param
    return World(tmp_path, quick=quick, mode=mode)


def expert(tmp_path, *, quick: bool = True) -> World:
    return World(tmp_path, quick=quick, mode="expert")


def best(w: World, a_unit: str = "OBC", b_unit: str = "RW1") -> tuple[str, str]:
    return core_links.best_connectors(w.project, a_unit, "", b_unit, "")


# ---- the ports ----------------------------------------------------------------------------------


def test_an_expert_card_has_a_port_for_every_connector_where_its_square_is_drawn(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path)
    item = w.scene.unit_items["OBC"]
    ports = w.layer.ports_of(item)
    assert [p.connector_id for p in ports] == ["OBC-J01", "OBC-J02", "OBC-J03"]
    for k, p in enumerate(ports):
        square = item.port_rect(k, p.connector_id).translated(item.pos())
        assert (p.x, p.y) == (square.center().x(), square.center().y())  # on the edge of the card
        assert p.side == item.port_side(p.connector_id)


def test_a_guided_card_has_one_port_for_the_device_on_its_facing_edge(qtbot, tmp_path) -> None:
    w = World(tmp_path, quick=True, mode="guided")
    item = w.scene.unit_items["OBC"]
    (port,) = w.layer.ports_of(item)
    assert (port.unit_id, port.connector_id) == ("OBC", "")
    assert port.y == item.pos().y() + item.height() / 2 and port.side == item.side()


def test_the_pointer_over_a_port_lights_it_and_shows_the_open_hand(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    p = w.port("OBC", "OBC-J01")
    w.move(w.grab_spot(p))
    assert w.layer.hover == p
    assert w.layer.port_style(p) == "hover"
    assert w.view.viewport().cursor().shape() == Qt.CursorShape.OpenHandCursor
    w.move(QPointF(700, 500))  # empty ground
    assert w.layer.hover is None
    assert w.view.viewport().cursor().shape() != Qt.CursorShape.OpenHandCursor


def test_the_tooltip_of_a_port_names_the_connector_its_kind_and_the_free_pins(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path)
    p = w.port("OBC", "OBC-J01")
    tip = w.layer.tip_for(p)
    assert "J01" in tip and "5 of 5 pins free" in tip and "Drag to pick up a cable" in tip
    w.win.ctl.add_link("OBC-J01", "RW1-J02", [("1", "3"), ("2", "4")])
    assert "3 of 5 pins free" in w.layer.tip_for(p)
    assert "3 connectors" in w.layer.tip_for(cb.Port("OBC"))  # the device as a whole


def test_ports_light_while_a_cable_is_in_hand_and_the_rest_dims(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    a = w.port("OBC", "OBC-J01")
    w.press(w.grab_spot(a))
    w.move(QPointF(400, 120))
    assert w.layer.port_style(a) == "from"
    assert w.layer.port_style(w.port("OBC", "OBC-J02")) == "no"  # the same device
    assert w.layer.port_style(w.port("RW1", "RW1-J01")) == "ok"
    assert w.layer.unit_state("RW1") == "ok" and w.layer.unit_state("OBC") == "from"
    w.release(QPointF(400, 120))


# ---- picking a cable up and plugging it in -------------------------------------------------------


def test_a_cable_from_a_port_to_a_port_connects_exactly_those_connectors_in_one_step(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path, quick=True)
    a, b = w.port("OBC", "OBC-J02"), w.port("PCDU", "PCDU-J02")
    w.drag(w.grab_spot(a), w.drop_spot(b))
    assert w.layer.cable.state == cb.IDLE
    (link,) = w.project.links.values()
    assert (link.a_connector, link.b_connector) == ("OBC-J02", "PCDU-J02")
    assert w.steps() == 1
    assert [(p.a_pin, p.b_pin) for p in link.pairs] == [("1", "1"), ("2", "2")]  # PWR and RTN
    w.win.ctl.undo()
    assert w.project.links == {} and w.steps() == 0


def test_the_same_drop_without_quick_opens_the_window_filled_in_for_those_two_connectors(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path, quick=False)
    script = DialogScript(w.win)
    a, b = w.port("OBC", "OBC-J01"), w.port("RW1", "RW1-J02")
    w.drag(w.grab_spot(a), w.drop_spot(b))
    (dlg,) = script.seen
    assert isinstance(dlg, LinkDialog) and dlg.windowTitle() == strings.LINK_TITLE
    assert (dlg.a_connector_id(), dlg.b_connector_id()) == ("OBC-J01", "RW1-J02")
    assert dlg.pairs() == [("1", "3"), ("2", "4"), ("3", "1"), ("4", "2")]
    assert w.steps() == 1 and len(w.project.links) == 1  # (accepted)


def test_a_cancelled_window_leaves_nothing_behind(qtbot, tmp_path) -> None:
    w = expert(tmp_path, quick=False)
    DialogScript(w.win, accept=False)
    w.drag(w.grab_spot(w.port("OBC", "OBC-J01")), w.drop_spot(w.port("RW1", "RW1-J02")))
    assert w.project.links == {} and w.steps() == 0 and w.layer.cable.draft is None


def test_a_cable_dropped_on_a_device_connects_to_its_best_connector(qtbot, world) -> None:
    w = world
    script = DialogScript(w.win)
    a = w.port("OBC", "OBC-J01")
    body = QPointF(520 + 100, 190 + 25)  # the header of RW1, no port
    w.drag(w.grab_spot(a), body)
    if script.seen:  # without Quick the window asks, filled in with the connector that was picked
        assert (script.seen[0].a_connector_id(), script.seen[0].b_connector_id()) == (
            "OBC-J01",
            "RW1-J02",
        )
    (link,) = w.project.links.values()
    assert (link.a_connector, link.b_connector) == (
        "OBC-J01",
        "RW1-J02",
    )  # the pair the names fit best
    assert w.steps() == 1


def test_in_guided_mode_a_cable_from_the_device_port_to_a_device_connects_the_best_pair(
    qtbot, tmp_path
) -> None:
    w = World(tmp_path, quick=True, mode="guided")
    a, expected = w.port("OBC"), best(w)
    w.drag(w.grab_spot(a), QPointF(520 + 100, 190 + 40))
    (link,) = w.project.links.values()
    assert (link.a_connector, link.b_connector) == expected
    assert w.steps() == 1


def test_the_snap_catches_a_port_a_few_pixels_away(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    b = w.port("RW1", "RW1-J02")
    a = w.port("OBC", "OBC-J01")
    w.press(w.grab_spot(a))
    w.move(QPointF(400, 120))
    w.move(QPointF(b.x - 9, b.y + 6))  # not on the square, near it
    assert w.layer.cable.target == b and w.layer.port_style(b) == "snap"
    assert w.layer.cable.shown()[1] == b.at  # the plug end sits on the port
    w.move(QPointF(b.x - 40, b.y + 40))
    assert w.layer.cable.target is None
    w.esc()


def test_a_press_on_the_card_still_moves_the_device_and_a_press_on_a_port_does_not(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path)
    w.drag(QPointF(100, 85), QPointF(160, 125))  # the header of OBC
    assert w.project.placements["OBC"].x == 120.0 and w.project.placements["OBC"].y == 110.0
    assert w.layer.cable.draft is None and w.project.links == {}
    before = w.project.placements["RW1"]
    p = w.port("RW1", "RW1-J01")
    w.drag(w.grab_spot(p), QPointF(700, 480))  # a cable, not the device
    assert w.project.placements["RW1"] == before


def test_a_click_on_a_port_selects_the_device_and_starts_no_cable(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    w.click(w.grab_spot(w.port("PCDU", "PCDU-J01")))
    assert (w.win.ctl.selection.kind, w.win.ctl.selection.id) == ("unit", "PCDU")
    assert w.layer.cable.state == cb.IDLE and w.layer.cable.draft is None and w.steps() == 0


def test_the_rubber_band_and_the_label_drag_still_work(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    w.drag(QPointF(20, 20), QPointF(340, 260))  # from empty ground: the rubber band
    assert {s.id for s in w.win.ctl.selected if s.kind == "unit"} == {"OBC"}
    lid = w.win.ctl.add_link("OBC-J01", "RW1-J02", [("1", "3")])
    w.settle()
    line = w.scene.connection_items[lid]
    w.drag(line._chip.center(), line._chip.center() + QPointF(0, 60))
    assert f"link:{lid}" in w.project.diagram_marks


def test_a_press_with_ctrl_or_shift_stays_a_selection_click(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    p = w.port("OBC", "OBC-J01")
    QTest.mousePress(
        w.view.viewport(), LEFT, Qt.KeyboardModifier.ShiftModifier, w.at(w.grab_spot(p))
    )
    assert w.layer.cable.state == cb.IDLE
    QTest.mouseRelease(
        w.view.viewport(), LEFT, Qt.KeyboardModifier.ShiftModifier, w.at(w.grab_spot(p))
    )


def test_the_connect_tool_and_the_window_and_quick_connect_still_work(qtbot, tmp_path) -> None:
    w = expert(tmp_path, quick=False)
    script = DialogScript(w.win)
    w.win.ctl.begin_link()
    w.press(QPointF(100, 85))  # the Connect tool picks devices: no cable
    w.release(QPointF(100, 85))
    assert w.layer.cable.state == cb.IDLE
    w.press(QPointF(600, 215))
    w.release(QPointF(600, 215))
    assert len(script.seen) == 1 and (
        script.seen[0].a_connector_id(),
        script.seen[0].b_connector_id(),
    ) == ("OBC-J01", "RW1-J02")
    w.win.ctl.end_connect()
    w.win.act_link_connectors.trigger()
    assert len(script.seen) == 2


def test_in_quick_mode_the_button_free_toast_still_offers_undo_and_edit_pairs(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path, quick=True)
    w.drag(w.grab_spot(w.port("OBC", "OBC-J01")), w.drop_spot(w.port("RW1", "RW1-J02")))
    assert strings.QL_CONNECTED.format(a="OBC", b="RW1") in w.win.toasts.messages[-1]


# ---- the hand, the status bar and Esc -------------------------------------------------------------


def test_the_status_bar_says_what_to_do_while_a_cable_is_in_hand_and_clears_when_it_is_put_down(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path)
    w.press(w.grab_spot(w.port("OBC", "OBC-J01")))
    w.move(QPointF(400, 150))
    assert w.status() == strings.CABLE_HINT_PORTS
    assert "Esc" in w.status() and "port" in w.status()
    assert w.view.viewport().cursor().shape() == Qt.CursorShape.ClosedHandCursor
    w.esc()
    assert w.status() == "" and w.layer.cable.state == cb.IDLE
    assert w.view.viewport().cursor().shape() != Qt.CursorShape.ClosedHandCursor


def test_guided_mode_says_device_and_not_port(qtbot, tmp_path) -> None:
    w = World(tmp_path, quick=True, mode="guided")
    w.press(w.grab_spot(w.port("OBC")))
    w.move(QPointF(400, 150))
    assert w.status() == strings.CABLE_HINT_DEVICES
    w.esc()


def test_esc_puts_the_cable_away_and_changes_nothing(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    h = layout.model_hash(w.project)
    w.press(w.grab_spot(w.port("OBC", "OBC-J01")))
    w.move(QPointF(400, 150))
    w.esc()
    w.release(QPointF(400, 150))  # (the button is let go afterwards: nothing happens)
    assert w.layer.cable.state == cb.IDLE and w.layer.cable.draft is None
    assert w.project.links == {} and w.steps() == 0 and layout.model_hash(w.project) == h
    assert w.win.ctl.selection is None or w.win.ctl.selection.kind == "unit"


def test_esc_without_a_cable_still_does_what_it_did(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    w.win.ctl.select("unit", "OBC")
    w.esc()
    assert w.win.ctl.selection is None


# ---- the loose end ----------------------------------------------------------------------------------


def make_loose(w: World, at: QPointF | None = None, connector: str = "OBC-J01") -> cb.Port:
    at = at or QPointF(420, 120)
    a = w.port("OBC", connector)
    w.drag(w.grab_spot(a), at)
    return a


def test_a_cable_let_go_on_empty_ground_stays_as_a_dashed_loose_end_with_a_plug(
    qtbot, world
) -> None:
    w = world
    h, steps = layout.model_hash(w.project), w.steps()
    a = make_loose(w, connector="OBC-J01")
    d = w.layer.cable.draft
    assert d is not None and d.anchor.unit_id == "OBC"
    assert d.end == pytest.approx((420.0, 120.0), abs=1.0)
    assert w.project.links == {} and w.steps() == steps and layout.model_hash(w.project) == h
    assert w.status() == strings.CABLE_HINT_LOOSE
    img = w.view.grab().toImage()
    spot = w.at(QPointF(*d.end))
    ratio = img.devicePixelRatio()  # (a screen scaled to 125 %: the image has more pixels than px)
    ink = {
        img.pixelColor(round((spot.x() + dx) * ratio), round((spot.y() + dy) * ratio)).name()
        for dx in range(-8, 3)
        for dy in range(-5, 6)
    }
    assert len(ink) > 1  # something is drawn at the loose end (the plug)
    assert a.unit_id == "OBC"


def test_a_loose_end_is_not_in_the_project_the_hash_or_any_file(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    make_loose(w)
    folder = tmp_path / "proj"
    folder.mkdir()
    h0 = layout.model_hash(w.project)
    save_project(w.project, folder)
    files = [p for p in folder.rglob("*") if p.is_file()]
    text = "".join(p.read_text(errors="ignore") for p in files)
    assert "loose" not in text.lower() and "draft" not in text.lower()
    assert not any("cable" in p.name or "draft" in p.name for p in files)
    assert layout.model_hash(w.project) == h0


def test_saving_the_project_drops_a_loose_end_silently(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    make_loose(w)
    assert w.layer.cable.draft is not None
    folder = tmp_path / "proj"
    w.win.ctl.save_as(folder)
    assert w.layer.cable.draft is None and w.status() == ""
    assert w.win.toasts.messages == [] or all("loose" not in m for m in w.win.toasts.messages)


def test_a_loose_end_is_picked_up_by_a_drag_and_plugged_into_a_port(qtbot, tmp_path) -> None:
    w = expert(tmp_path, quick=True)
    make_loose(w, QPointF(420, 120))
    b = w.port("RW1", "RW1-J02")
    w.drag(QPointF(420, 120), w.drop_spot(b))
    (link,) = w.project.links.values()
    assert (link.a_connector, link.b_connector) == ("OBC-J01", "RW1-J02")
    assert w.layer.cable.draft is None and w.steps() == 1


def test_a_click_on_the_loose_end_picks_it_up_and_the_next_click_on_a_port_plugs_it_in(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path, quick=True)
    make_loose(w, QPointF(420, 120))
    w.click(QPointF(420, 120))
    assert w.layer.cable.state == cb.HOLD and w.status() == strings.CABLE_HINT_HELD
    w.move(QPointF(500, 200))
    assert w.layer.cable.shown()[1][0] == pytest.approx(
        500.0, abs=1.0
    )  # it follows with no button down
    b = w.port("RW1", "RW1-J01")
    w.click(w.drop_spot(b))
    (link,) = w.project.links.values()
    assert (link.a_connector, link.b_connector) == ("OBC-J01", "RW1-J01")
    assert w.layer.cable.state == cb.IDLE and w.steps() == 1


def test_a_held_loose_end_clicked_on_empty_ground_stays_loose_there(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    make_loose(w, QPointF(420, 120))
    w.click(QPointF(420, 120))
    w.move(QPointF(380, 520))
    w.click(QPointF(380, 520))
    assert (
        w.layer.cable.draft.end == pytest.approx((380.0, 520.0), abs=1.0)
        and w.layer.cable.state == cb.IDLE
    )


def test_a_click_on_empty_ground_and_esc_drop_the_loose_end(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    make_loose(w)
    w.click(QPointF(700, 520))  # empty ground
    assert w.layer.cable.draft is None and w.status() == ""
    make_loose(w)
    w.esc()
    assert w.layer.cable.draft is None and w.status() == "" and w.project.links == {}


def test_a_loose_end_follows_its_device_when_the_device_moves(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    make_loose(w, QPointF(420, 120))
    w.win.ctl.move_unit("OBC", 60, 140)
    w.settle()
    anchor = w.layer.port_now(w.layer.cable.draft.anchor)
    assert anchor.y == w.port("OBC", "OBC-J01").y and anchor.y > 116


def test_a_loose_end_goes_when_its_device_is_deleted_or_a_project_is_opened(
    qtbot, tmp_path
) -> None:
    from harness_design_studio.core import edit

    w = expert(tmp_path)
    make_loose(w)
    w.win.ctl.run("Delete", edit.ops_delete_unit(w.project, "OBC"))
    assert w.layer.cable.draft is None
    w2 = expert(tmp_path / "second")
    make_loose(w2)
    p = pinout_project()
    p.harnesses.clear()
    w2.win.ctl._install(p, None, None)
    assert w2.layer.cable.draft is None


# ---- refusals ------------------------------------------------------------------------------------------


def test_a_port_of_the_same_device_refuses_with_a_message_and_makes_nothing(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path)
    w.drag(w.grab_spot(w.port("OBC", "OBC-J01")), w.drop_spot(w.port("OBC", "OBC-J03")))
    assert w.project.links == {} and w.steps() == 0
    assert w.win.toasts.messages[-1] == strings.CABLE_REFUSED_SAME.format(unit="OBC")


def test_a_connector_with_no_free_pin_refuses_with_a_message(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    w.win.ctl.add_link("OBC-J01", "RW1-J02", [(str(k), str(k)) for k in range(1, 6)])
    n = w.steps()
    w.drag(w.grab_spot(w.port("PCDU", "PCDU-J01")), w.drop_spot(w.port("RW1", "RW1-J02")))
    assert w.steps() == n and len(w.project.links) == 1
    assert w.win.toasts.messages[-1] == strings.CABLE_REFUSED_FULL.format(name="J02")


def test_the_cable_over_a_refusing_port_turns_red(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    w.press(w.grab_spot(w.port("OBC", "OBC-J01")))
    w.move(QPointF(300, 200))
    w.move(w.drop_spot(w.port("OBC", "OBC-J03")))
    assert w.layer.port_style(w.port("OBC", "OBC-J03")) == "snap-no"
    w.esc()


def test_a_read_only_project_picks_up_no_cable(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    w.project.read_only = True
    w.press(w.grab_spot(w.port("OBC", "OBC-J01")))
    w.move(QPointF(400, 150))
    assert w.layer.cable.state == cb.IDLE
    w.release(QPointF(400, 150))
    assert w.project.links == {}


# ---- picking up the end of a connection ---------------------------------------------------------------------


def linked(tmp_path, quick: bool = True) -> tuple[World, str]:
    w = expert(tmp_path, quick=quick)
    lid = w.win.ctl.add_link("OBC-J01", "RW1-J02", [("1", "3"), ("2", "4"), ("3", "1"), ("4", "2")])
    assert lid is not None
    w.settle()
    return w, lid


def test_the_end_of_a_connection_dragged_to_another_port_moves_it_in_one_undo_step(
    qtbot, tmp_path
) -> None:
    w, lid = linked(tmp_path)
    n = w.steps()
    target = w.port("PCDU", "PCDU-J01")
    w.drag(w.plug(lid, end="b"), w.drop_spot(target))
    link = w.project.links[lid]
    assert (link.id, link.a_connector, link.b_connector) == (lid, "OBC-J01", "PCDU-J01")
    assert w.steps() == n + 1 and len(w.project.links) == 1
    w.win.ctl.undo()
    assert (w.project.links[lid].a_connector, w.project.links[lid].b_connector) == (
        "OBC-J01",
        "RW1-J02",
    )
    assert w.steps() == n
    w.win.ctl.redo()
    assert w.project.links[lid].b_connector == "PCDU-J01"


def test_either_end_can_be_picked_up(qtbot, tmp_path) -> None:
    w, lid = linked(tmp_path)
    target = w.port("PCDU", "PCDU-J03")
    w.drag(w.plug(lid, end="a"), w.drop_spot(target))
    assert (w.project.links[lid].a_connector, w.project.links[lid].b_connector) == (
        "PCDU-J03",
        "RW1-J02",
    )


def test_an_end_dropped_on_a_device_goes_to_the_connector_the_tool_picks(qtbot, tmp_path) -> None:
    w, lid = linked(tmp_path)
    w.drag(w.plug(lid, end="b"), QPointF(60 + 100, 330 + 20))  # the header of PCDU
    assert w.project.connectors[w.project.links[lid].b_connector].unit_id == "PCDU"


def test_while_the_end_is_in_hand_the_old_connection_waits_as_a_ghost_and_stays_in_the_model(
    qtbot, tmp_path
) -> None:
    w, lid = linked(tmp_path)
    w.press(w.plug(lid, end="b"))
    w.move(QPointF(420, 330))
    assert w.layer.moving(lid) and w.status().startswith("Drop on another port to move this end of")
    assert lid in w.project.links
    w.esc()
    assert not w.layer.moving(lid)
    assert w.project.links[lid].b_connector == "RW1-J02" and w.steps() == 1


def test_an_end_let_go_on_empty_ground_becomes_a_loose_end_and_the_connection_stays(
    qtbot, tmp_path
) -> None:
    w, lid = linked(tmp_path)
    n = w.steps()
    w.drag(w.plug(lid, end="b"), QPointF(430, 380))
    d = w.layer.cable.draft
    assert (
        d is not None and d.replaces == lid and d.replaces_end == "b" and d.anchor.unit_id == "OBC"
    )
    assert w.project.links[lid].b_connector == "RW1-J02" and w.steps() == n  # nothing changed yet
    w.esc()  # Esc keeps the connection where it was
    assert w.layer.cable.draft is None and w.project.links[lid].b_connector == "RW1-J02"


def test_the_loose_end_of_a_picked_up_connection_plugs_in_later_and_moves_the_connection(
    qtbot, tmp_path
) -> None:
    w, lid = linked(tmp_path)
    n = w.steps()
    w.drag(w.plug(lid, end="b"), QPointF(430, 380))
    w.drag(QPointF(430, 380), w.drop_spot(w.port("PCDU", "PCDU-J01")))
    assert w.project.links[lid].b_connector == "PCDU-J01" and len(w.project.links) == 1
    assert w.steps() == n + 1 and w.layer.cable.draft is None


def test_an_end_put_back_on_its_own_port_changes_nothing(qtbot, tmp_path) -> None:
    w, lid = linked(tmp_path)
    n = w.steps()
    w.drag(w.plug(lid, end="b"), w.drop_spot(w.port("RW1", "RW1-J02")))
    assert w.steps() == n and w.project.links[lid].b_connector == "RW1-J02"
    assert w.layer.cable.draft is None


def test_an_end_cannot_be_plugged_into_the_device_at_the_other_end(qtbot, tmp_path) -> None:
    w, lid = linked(tmp_path)
    n = w.steps()
    w.drag(w.plug(lid, end="b"), w.drop_spot(w.port("OBC", "OBC-J03")))
    assert w.steps() == n and w.project.links[lid].b_connector == "RW1-J02"
    assert w.win.toasts.messages[-1] == strings.CABLE_REFUSED_SAME.format(unit="OBC")


def test_a_click_on_a_plug_selects_the_connection(qtbot, tmp_path) -> None:
    w, lid = linked(tmp_path)
    w.win.ctl.select_link(None)
    w.click(w.plug(lid, end="b"))
    assert w.win.ctl.selected_link == lid and w.layer.cable.state == cb.IDLE


def test_an_end_whose_harness_exists_is_refused_with_the_reason(qtbot, tmp_path) -> None:
    w, lid = linked(tmp_path)
    assert w.win.ctl.create_harness_from_link(lid)
    n = w.steps()
    w.settle()
    w.drag(w.plug(lid, end="b"), w.drop_spot(w.port("PCDU", "PCDU-J01")))
    assert w.steps() == n and w.project.links[lid].b_connector == "RW1-J02"
    assert "harness" in w.win.toasts.messages[-1]


def test_a_new_cable_from_a_port_that_has_a_connection_is_still_a_new_cable(
    qtbot, tmp_path
) -> None:
    w, lid = linked(tmp_path)
    w.drag(w.grab_spot(w.port("OBC", "OBC-J01")), w.drop_spot(w.port("PCDU", "PCDU-J01")))
    assert len(w.project.links) == 2 and w.project.links[lid].b_connector == "RW1-J02"


# ---- far apart, off the screen ---------------------------------------------------------------------------------


def test_a_cable_reaches_a_device_far_beyond_the_edge_of_the_view_by_scrolling(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path, quick=True)
    w.win.ctl.move_unit("RW1", 3200.0, 190.0)
    w.settle()
    assert (
        not w.view.mapToScene(w.view.viewport().rect()).boundingRect().contains(QPointF(3300, 250))
    )
    a = w.port("OBC", "OBC-J01")
    w.press(w.grab_spot(a))
    edge = w.view.viewport().width() - 6
    for k in range(1, 5):
        QTest.mouseMove(
            w.view.viewport(),
            pos=QPoint(
                w.at(w.grab_spot(a)).x() + (edge - w.at(w.grab_spot(a)).x()) * k // 4,
                w.at(QPointF(0, 130)).y(),
            ),
        )
        QApplication.processEvents()
    left = w.view.mapToScene(QPoint(0, 0)).x()
    rest = QPoint(edge, w.at(QPointF(0, 130)).y())
    for k in range(1000):  # the view scrolls while the cable rests at its edge
        QTest.qWait(10)
        if w.view.mapToScene(w.view.viewport().rect().bottomRight()).x() > 3330:
            break
        if k % 20 == 19:
            # On a real display (xcb under load) a move can reach the window late or not at all and
            # the pointer then seems to rest somewhere else: the cable is held at its edge again
            # (the same move, the button still down), as a hand that rests there would.
            QTest.mouseMove(w.view.viewport(), pos=rest)
    assert w.view.mapToScene(QPoint(0, 0)).x() > left + 500  # it scrolled
    b = w.port("RW1", "RW1-J02")
    assert w.view.mapToScene(w.view.viewport().rect().bottomRight()).x() > b.x
    spot = w.view.mapFromScene(w.drop_spot(b))
    QTest.mouseMove(w.view.viewport(), pos=spot)
    QApplication.processEvents()
    QTest.mouseRelease(w.view.viewport(), LEFT, pos=spot)
    QApplication.processEvents()
    (link,) = w.project.links.values()
    assert (link.a_connector, link.b_connector) == ("OBC-J01", "RW1-J02")


def test_the_scene_grows_ahead_of_a_carried_cable_and_shrinks_back_when_it_is_put_down(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path)
    rect = w.scene.sceneRect()
    w.press(w.grab_spot(w.port("OBC", "OBC-J01")))
    w.move(QPointF(600, 460))
    w.layer._carry(QPointF(rect.right() + 100, 300))  # far out to the right
    assert w.scene.sceneRect().right() > rect.right()
    w.esc()
    assert w.scene.sceneRect().right() <= rect.right()


def test_a_cable_far_from_the_diagram_is_still_drawn_and_picked_up_again(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    make_loose(w, QPointF(420, 120))
    w.win.ctl.move_unit("RW1", 6000.0, -900.0)
    w.settle()
    b = w.port("RW1", "RW1-J02")
    assert b.x >= 6000
    w.view.centerOn(QPointF(b.x, b.y))
    w.settle()
    w.view.centerOn(QPointF(420, 120))
    w.settle()
    w.click(QPointF(420, 120))
    assert w.layer.cable.state == cb.HOLD
    w.esc()
