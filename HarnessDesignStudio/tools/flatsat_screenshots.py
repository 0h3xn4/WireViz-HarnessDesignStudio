# mypy: allow-untyped-calls, no-warn-unused-ignores
"""Pictures of the flatsat example in the real editor (offscreen) for docs/FLATSAT_EXAMPLE.md:
the whole diagram, the same diagram with one unit in focus, and for docs/user-manual/telling-devices-apart.md
a close-up of four cards (TRX1, OBC1, RW1, RW2) and the key to the looks of devices. Usage: python -m tools.flatsat_screenshots"""

import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QRectF, QSettings, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from harness_design_studio.core import templates
from harness_design_studio.gui import device_kinds, device_looks
from harness_design_studio.gui.main_window import MainWindow
from harness_design_studio.gui.theme import ThemeManager

OUT = Path(__file__).resolve().parents[1] / "docs" / "img"


def _wait(ms: int) -> None:
    """Let the event loop run (a sleep, so background threads are not starved)."""
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.02)


def kinds_picture(theme: ThemeManager) -> QImage:
    """The key to the looks of devices: the badge of every kind with its name, six to a row, on the
    colour of a card (the real painters, `gui/device_looks.py`)."""
    kinds = (*device_kinds.KINDS, device_kinds.GENERIC)
    cols, cell_w, cell_h, side, pad = 3, 250, 40, 28, 10
    rows = -(-len(kinds) // cols)
    image = QImage(cols * cell_w + pad, rows * cell_h + pad, QImage.Format.Format_RGB32)
    image.fill(theme.color("bg.surface"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setFont(theme.font("base"))
    for k, kind in enumerate(kinds):
        x, y = pad + (k % cols) * cell_w, pad + (k // cols) * cell_h
        device_looks.draw_badge(
            painter, theme, device_kinds.Looks(kind, "", ""), QRectF(x, y, side, side),
            ground="bg.surface",
        )  # fmt: skip
        painter.setPen(theme.color("text"))
        painter.drawText(
            QRectF(x + side + 10, y, cell_w - side - 20, side),
            Qt.AlignmentFlag.AlignVCenter,
            kind.label,
        )
    painter.end()
    return image


def main() -> int:
    QApplication.instance() or QApplication(sys.argv)
    tmp = Path(tempfile.mkdtemp())
    templates.create_project(tmp / "flatsat", "flatsat")
    win = MainWindow(
        QSettings(str(tmp / "ui.ini"), QSettings.Format.IniFormat), ThemeManager(), first_run=False
    )
    win.resize(1600, 1000)  # a big window, so the diagram and its legend have room
    win.show()
    for dock in (win.dock_left, win.dock_right):
        dock.hide()  # the pictures are of the diagram only
    _wait(300)
    assert win.open_project(tmp / "flatsat")
    _wait(1500)  # the marks on the diagram are worked out a moment after the project opens
    win.view.fit()
    _wait(500)
    win.view.grab().save(str(OUT / "flatsat-overview.png"))
    win.ctl.select("unit", "PDU2")
    _wait(500)
    win.view.grab().save(str(OUT / "flatsat-focus.png"))
    win.ctl.select(None)
    win.act_legend.setChecked(False)  # the close-up is of cards, not of the key
    win.view.set_legend_wanted(False)
    close = QRectF()
    for uid in ("TRX1", "OBC1", "RW1", "RW2"):
        close = close.united(win.view.dscene.unit_items[uid].sceneBoundingRect())
    win.view.fitInView(close.adjusted(-60, -40, 60, 40), Qt.AspectRatioMode.KeepAspectRatio)
    _wait(500)
    win.view.grab().save(str(OUT / "device-looks-close.png"))
    kinds_picture(win.theme).save(str(OUT / "device-looks-kinds.png"))
    print("flatsat-overview.png, flatsat-focus.png, device-looks-close.png, device-looks-kinds.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
