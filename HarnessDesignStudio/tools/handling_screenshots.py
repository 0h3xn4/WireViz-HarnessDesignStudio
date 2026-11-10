# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: allow-untyped-calls, no-warn-unused-ignores, disable-error-code=misc
"""Pictures of the diagram handling of 1.14 to 1.16 and of the windows that came with it, in the real
editor (offscreen, light theme) for the manual: the cable in hand, the plug snapped on a port, a
loose end, the Kind list in the Inspector, the Role button with Quick mode, the Quick window, the
Export window with the open data, the window *How this was calculated* with its Model page line and
the written block diagram of the flatsat example. Usage:

    QT_QPA_PLATFORM=offscreen python -m tools.handling_screenshots [OUTPUT_FOLDER]   (default: docs/img)

The cable pictures use a mouse that works in scene coordinates (real mouse events on the diagram's
viewport), on a project of three devices with named pins; no project path is on show."""

from __future__ import annotations

import re
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox

from harness_design_studio.core import templates
from harness_design_studio.core.derive import explain_object
from harness_design_studio.gui import cable as cb
from harness_design_studio.gui.explain_dialog import ExplainDialog
from harness_design_studio.gui.main_window import MainWindow
from tools import tab_screenshots as tabs
from tools import ui_screenshots as shots

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "docs" / "img"
LEFT = Qt.MouseButton.LeftButton
SPOTS = {"OBC": (60.0, 70.0), "PCDU": (60.0, 330.0), "RW1": (520.0, 190.0)}
WINDOW = (1280, 720)


def main(out: Path = DEFAULT_OUT, only: str = "") -> int:
    _ = QApplication.instance() or QApplication([])
    out.mkdir(parents=True, exist_ok=True)
    steps: dict[str, Callable[[Path], None]] = {
        "cable": _cable_pictures,
        "quick": _quick_pictures,
        "kind": _kind_picture,
        "export": _export_window_picture,
        "explain": _explain_pictures,
        "diagram": _written_diagram_pictures,
    }
    for name, step in steps.items():
        if only in ("", name):
            step(out)
    print(f"wrote the pictures of the diagram handling to {out}")
    return 0


# ---- the mouse, in scene coordinates ----------------------------------------------------------


class Mouse:
    """Real mouse events on the viewport of the diagram, given in scene coordinates."""

    def __init__(self, win: MainWindow) -> None:
        self.win = win
        self.view = win.view
        self.scene = win.view.dscene

    def at(self, p: QPointF) -> QPoint:
        return self.view.mapFromScene(p)

    def press(self, p: QPointF) -> None:
        QTest.mousePress(self.view.viewport(), LEFT, pos=self.at(p))
        QApplication.processEvents()

    def move(self, p: QPointF) -> None:
        QTest.mouseMove(self.view.viewport(), pos=self.at(p))
        QApplication.processEvents()

    def release(self, p: QPointF) -> None:
        QTest.mouseRelease(self.view.viewport(), LEFT, pos=self.at(p))
        QApplication.processEvents()

    def port(self, unit: str, connector: str) -> cb.Port:
        ports = self.scene.cable.ports_of(self.scene.unit_items[unit])
        return next(p for p in ports if p.connector_id == connector)

    @staticmethod
    def grab_spot(port: cb.Port) -> QPointF:
        """A point of a port where a press picks a cable up (inside the card edge)."""
        return QPointF(port.x + (-4.0 if port.side == "right" else 4.0), port.y)

    @staticmethod
    def drop_spot(port: cb.Port) -> QPointF:
        return QPointF(port.x + 2.0, port.y + 1.0)


def _pinout_window(name: str, *, quick: bool = False) -> MainWindow:
    """Three devices with named pins (`tab_screenshots._pinout_project`) in Expert mode, at 100 %."""
    win = tabs._window(name, "blank", "electrical", WINDOW)
    win.ctl._install(tabs._pinout_project(), None, None)
    if quick:
        win.act_quick.trigger()
    win.go_to("diagram")
    if not quick:
        win.act_expert.trigger()  # (Quick mode keeps the Guided mode: one port on each device)
    for uid, (x, y) in SPOTS.items():
        win.ctl.move_unit(uid, x, y)
    win.dock_right.hide()
    win.dock_left.hide()
    shots._settle(win, 600)
    win.view.zoom_100()
    win.view.centerOn(QPointF(420, 260))
    shots._settle(win, 400)
    return win


def _cable_pictures(out: Path) -> None:
    """The cable in hand, the plug snapped on a port, and a loose end."""
    win = _pinout_window("harness-cable")
    mouse = Mouse(win)
    a, b = mouse.port("OBC", "OBC-J01"), mouse.port("RW1", "RW1-J02")
    mouse.press(mouse.grab_spot(a))
    for k in range(1, 5):  # a drag: the cable follows the pointer
        mouse.move(QPointF(a.x + 48 * k, a.y + 38 * k))
    tabs._save(win, out / "cable-in-hand.png")
    mouse.move(mouse.drop_spot(b))
    tabs._save(win, out / "cable-snaps-on-port.png")
    mouse.release(QPointF(a.x + 240, a.y + 330))  # on empty ground: a loose end stays
    shots._wait(400)
    tabs._save(win, out / "cable-loose-end.png")
    mouse.scene.cable.cable.cancel()
    win.close()


def _quick_pictures(out: Path) -> None:
    """Quick mode: the whole window (Role button, the Quick marker, Export diagram) and the Role
    button with its menu open."""
    win = _pinout_window("harness-quick", quick=True)
    win.ctl.add_link("OBC-J01", "RW1-J02", [("1", "3"), ("2", "4"), ("3", "1"), ("4", "2")])
    win.ctl.add_link("PCDU-J01", "RW1-J01", [("1", "1"), ("2", "2")])
    win.dock_left.show()
    shots._settle(win, 400)
    win.view.fit()
    shots._settle(win, 400)
    tabs._save(win, out / "quick-mode-window.png")
    menu = win.role_btn.menu()
    assert menu is not None
    menu.popup(win.role_btn.mapToGlobal(QPoint(0, win.role_btn.height())))
    shots._wait(500)
    top = win.topbar.grab()
    box = QRect(
        win.topbar.mapFromGlobal(menu.mapToGlobal(QPoint(0, 0))), menu.size()
    )  # (the menu is a window of its own)
    canvas = QPixmap(win.topbar.width(), box.bottom() + 8)
    canvas.fill(win.palette().window().color())
    painter = QPainter(canvas)
    painter.drawPixmap(0, 0, top)
    painter.drawPixmap(box.topLeft(), menu.grab())
    painter.end()
    canvas.copy(560, 0, canvas.width() - 560, canvas.height()).save(
        str(out / "role-button-menu.png")
    )
    print("role-button-menu.png")
    menu.close()
    win.close()


def _kind_picture(out: Path) -> None:
    """The Inspector of a device with its Kind list open (Automatic first, then the kinds)."""
    win = tabs._window("harness-kind", "flatsat", "electrical", (1440, 900))
    win.go_to("diagram")
    win.ctl.select("unit", "PDU2")
    shots._settle(win, 600)
    box = win.findChild(QComboBox, "unit-kind")
    assert box is not None
    dock = win.dock_right
    box.setMaxVisibleItems(box.count())  # all the kinds at once, without the scroll bar
    box.showPopup()
    shots._wait(500)
    popup = box.view().window()
    grabbed = dock.grab()
    # (the offscreen platform puts the popup anywhere: draw it under the box, where it opens)
    at = box.mapTo(dock, QPoint(0, box.height()))
    both = QRect(QPoint(0, 0), grabbed.size()).united(QRect(at, popup.size()))
    canvas = QPixmap(both.size())
    canvas.fill(win.palette().window().color())
    painter = QPainter(canvas)
    painter.drawPixmap(0, 0, grabbed)
    painter.drawPixmap(at, popup.grab())
    painter.end()
    canvas.save(str(out / "kind-list-inspector.png"))
    print("kind-list-inspector.png")
    box.hidePopup()
    win.close()


def _export_window_picture(out: Path) -> None:
    """The Export window with the box *Include the open data* ticked, after an export."""
    win = tabs._generated("harness-export-data", "systems", tabs.MAIN)

    def dialog(d: Any) -> int:
        d.show()
        d.resize(1000, 720)
        d.open_data.setChecked(True)
        shots._wait(300)
        d.export_btn.click()
        waited = 0
        while d.export_result is None and waited < 60000:
            shots._wait(200)
            waited += 200
        shots._wait(800)
        tabs._save(d, out / "export-window-open-data.png")
        return 0

    old = win.run_dialog
    win.run_dialog = dialog  # type: ignore[assignment]
    try:
        win.export_dialog_flow()
    finally:
        win.run_dialog = old  # type: ignore[assignment]
    win.close()


def _explain_pictures(out: Path) -> None:
    """The window *How this was calculated* for a wire, and the *Why* tab with *Show the calculation*
    open, with the line *Model page:* under each calculation."""
    win = tabs._window("harness-explain", "flatsat", "electrical", (1440, 900))
    found = explain_object(win.ctl.project, "W001-001")
    assert found
    dlg = ExplainDialog(win, win.theme, found)
    dlg.show()
    dlg.resize(900, 560)
    shots._wait(500)
    tabs._save(dlg, out / "explain-window-model-page.png")
    dlg.close()
    win.go_to("diagram")
    win.inspector.show_tab("why")  # the same calculation in the Why tab (Show the calculation)
    panel = win.inspector.why
    panel.show_object("wire", "W001-001")
    assert panel.explain_button is not None
    panel.explain_button.click()
    win.dock_right.show()
    win.dock_right.resize(460, 900)
    shots._settle(win, 600)
    tabs._save(win.dock_right, out / "why-tab-model-page.png")
    win.close()


def _written_diagram_pictures(out: Path) -> None:
    """The block diagram that `export` writes (`system/block_diagram.svg`) for the flatsat example, with the looks of the devices, as a picture."""
    from harness_design_studio.core.outputs.build import write_outputs

    with tempfile.TemporaryDirectory() as tmp:
        project = templates.create_project(Path(tmp) / "flatsat", "flatsat")
        written = Path(tmp) / "outputs"
        write_outputs(project, written)
        _rasterise(
            written / "system" / "block_diagram.svg", out / "written-block-diagram.png", 1600
        )


def _rasterise(svg: Path, png: Path, width: int, *, crop: bool = False) -> None:
    """Draw an SVG sheet with Qt's renderer on a white ground. The SVG names `Courier New`, which
    Qt does not map by itself, so a copy with a monospace face that is installed is drawn."""
    from PySide6.QtSvg import QSvgRenderer

    text = re.sub(r"Courier New, Courier, monospace", "Liberation Mono", svg.read_text("utf-8"))
    renderer = QSvgRenderer(text.encode("utf-8"))
    size = renderer.defaultSize()
    height = round(width * size.height() / size.width())
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image.save(str(png))


if __name__ == "__main__":
    args = sys.argv[1:]
    raise SystemExit(main(Path(args[0]) if args else DEFAULT_OUT, args[1] if len(args) > 1 else ""))
