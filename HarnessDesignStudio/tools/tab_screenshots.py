# mypy: allow-untyped-calls, no-warn-unused-ignores, disable-error-code=misc
"""Pictures of the Edit wire tab and of the Devices tab (1.4.0) for the user manual.

Opens the real Qt editor offscreen on the flatsat example in a 1760 x 1000 window and saves two
PNGs: `edit-wire-tab.png` (Drawings area, a wire selected, the Edit wire tab open) and
`devices-tab.png` (the Devices tab of the first unit). Usage:

    QT_QPA_PLATFORM=offscreen python -m tools.tab_screenshots [OUTPUT_FOLDER]   (default: docs/img)
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication

from tools import ui_screenshots as shots

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "docs" / "img"
WIDTH, HEIGHT = 1760, 1000
WIRE_ROW = 2  # a wire of the first harness that has a gauge, a type and a colour


def main(out: Path = DEFAULT_OUT) -> int:
    _ = QApplication.instance() or QApplication([])
    out.mkdir(parents=True, exist_ok=True)
    win = shots._fresh(Path(tempfile.gettempdir()) / "harness-tab-shots", "light")
    win.resize(WIDTH, HEIGHT)
    shots._settle(win)
    win.go_to("harness")
    shots._settle(win)
    view = win.harness_view
    table = view.wire_table
    selection = table.selectionModel()
    index = table.proxy.mapFromSource(table.proxy.sourceModel().index(WIRE_ROW, 0))
    if selection is not None:
        selection.select(
            index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        selection.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
    view.side_tabs.setCurrentIndex(1)  # the Edit wire tab
    shots._wait(600)
    win.grab().save(str(out / "edit-wire-tab.png"))
    win.go_to("devices")
    shots._settle(win)
    win.devices_view.show_unit(sorted(win.ctl.project.units)[0])
    shots._wait(600)
    win.grab().save(str(out / "devices-tab.png"))
    print(f"wrote edit-wire-tab.png and devices-tab.png to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT))
