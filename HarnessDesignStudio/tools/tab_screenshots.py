# mypy: allow-untyped-calls, no-warn-unused-ignores, disable-error-code=misc
"""Pictures of the editor for the user manual: the Edit wire tab, the Devices tab (1.4.0), the
Connectors tab (1.5.0) and, since 1.7.0, the Next step page, the Simple and the Full workspace, the
Accessories tab and the Export window.

Opens the real Qt editor offscreen (light theme, Simple workspace) on the flatsat example in a
1760 x 1000 window, where the tabs have room to show their names, and saves `edit-wire-tab.png`
(Drawings area, a wire selected, the Edit wire tab open) and `devices-tab.png` (the Devices tab of
the first unit). Then it starts a project from nothing, makes a harness by hand with two connectors
and three wires, and saves `connectors-tab.png` (the Connectors tab). Then, in a 1440 x 900 window
on the tutorial project (`first-steps`, generated): `next-step-new-project.png` (an empty project),
`next-step-fix-problems.png` (one check fails), `next-step-export.png` (its parts approved, so
every check passes or waits for a value), `simple-workspace.png` and `full-workspace.png` (the
checked project in each workspace), `export-window.png` and `export-window-done.png` (the Export
window before and after an export with the PDF drawings). Last, with three accessories added,
`accessories-tab.png` (1760 x 1000). The time of the last check, which the status bar shows, is
cleared before each picture. Usage:

    QT_QPA_PLATFORM=offscreen python -m tools.tab_screenshots [OUTPUT_FOLDER]   (default: docs/img)
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication

from harness_design_studio.core.build_data import plan_set_accessory
from harness_design_studio.core.commands import Put
from harness_design_studio.core.generate.engine import plan_generation
from harness_design_studio.core.manual_harness import (
    plan_add_connector,
    plan_new_harness,
    plan_set_pin,
)
from harness_design_studio.core.model import evolve
from harness_design_studio.core.wires import plan_add_wire
from harness_design_studio.gui.main_window import MainWindow
from tools import ui_screenshots as shots

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "docs" / "img"
WIDTH, HEIGHT = 1760, 1000
MAIN = (1440, 900)  # the size of docs/ux/qt/02-guided-main.png
WIRE_ROW = 2  # a wire of the first harness that has a gauge, a type and a colour


def main(out: Path = DEFAULT_OUT) -> int:
    _ = QApplication.instance() or QApplication([])
    out.mkdir(parents=True, exist_ok=True)
    win = _window("harness-tab-shots", "flatsat", "simple", (WIDTH, HEIGHT))
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
    _save(win, out / "edit-wire-tab.png")
    win.go_to("devices")
    shots._settle(win)
    win.devices_view.show_unit(sorted(win.ctl.project.units)[0])
    shots._wait(600)
    _save(win, out / "devices-tab.png")
    _by_hand(win, out)
    win.close()
    _next_step_pictures(out)
    _workspace_pictures(out)
    print(f"wrote the pictures of the tabs, workspaces and windows to {out}")
    return 0


def _window(name: str, example: str, workspace: str, size: tuple[int, int]) -> MainWindow:
    """The editor on an example, in a fixed folder (the status bar shows the path), in the Full or
    the Simple workspace. A fresh settings file would give Simple, so the choice is made here."""
    win = shots._fresh(Path(tempfile.gettempdir()) / name, "light", example)
    win.set_workspace(workspace)
    win.resize(*size)
    shots._settle(win)
    return win


def _save(win: object, path: Path) -> None:
    """Grab a window or a dialog without the time of the last check (it differs on every run)."""
    owner = win if isinstance(win, MainWindow) else win.parent()  # type: ignore[attr-defined]
    owner.jobs.finish("")
    owner._last_check = ""
    shots._wait(300)
    win.grab().save(str(path))  # type: ignore[attr-defined]
    print(path.name)


def _generated(
    name: str, workspace: str, size: tuple[int, int], approve: bool = True
) -> MainWindow:
    """The tutorial project (`first-steps`), generated and checked, in the given workspace. With
    `approve` its parts are approved first, as the tutorial does with a parts file, so no check
    fails; without it the check of the approved parts list fails, as it does in the tutorial."""
    win = _window(name, "first-steps", workspace, size)
    if approve:
        parts = win.ctl.project.parts
        ops = [
            Put(
                "parts",
                evolve(
                    x,
                    approval="approved",
                    unverified=False,
                    specification=x.specification or "EXAMPLE-SPEC-1",
                ),
            )
            for x in parts.values()
        ]
        win.ctl.run("step", ops)
    win.ctl.apply_generation(plan_generation(win.ctl.project))
    win.ctl.save()
    win.go_to("diagram")
    win.ctl.run_drc_now()
    shots._settle(win, 700)
    win.view.fit()
    return win


def _show_next(win: MainWindow, out: Path, name: str) -> None:
    win._show_area("next")
    shots._settle(win, 700)
    _save(win, out / name)


def _next_step_pictures(out: Path) -> None:
    """The Next step page: an empty project, a project whose checks fail, a checked one."""
    win = _window("harness-next-new", "blank", "simple", MAIN)
    _show_next(win, out, "next-step-new-project.png")
    win.close()
    win = _generated("harness-next-fix", "simple", MAIN, approve=False)
    _show_next(win, out, "next-step-fix-problems.png")
    win.close()
    win = _generated("harness-next-export", "simple", MAIN)
    _show_next(win, out, "next-step-export.png")
    win.close()


def _workspace_pictures(out: Path) -> None:
    """The same project in both workspaces, then the Accessories tab and the Export window."""
    for workspace in ("simple", "full"):
        win = _generated("harness-workspace", workspace, MAIN)
        win.view.fit()
        _save(win, out / f"{workspace}-workspace.png")
        win.close()
    win = _generated("harness-export", "simple", MAIN)
    _export_pictures(win, out)  # (before the accessories, so the counts are the manual's)
    win.close()
    win = _generated("harness-accessories", "simple", (WIDTH, HEIGHT))
    hid = sorted(win.ctl.project.harnesses)[0]
    h = win.ctl.project.harnesses[hid]
    wire = h.wires[0].id
    connector = h.connectors[0].id
    for acc in (
        {"id": "ACC-001", "kind": "sleeving", "target": wire, "position": "whole wire"},
        {
            "id": "ACC-002",
            "kind": "heat_shrink",
            "target": connector,
            "position": "50 mm from the connector",
            "length_mm": 30,
            "quantity": 2,
            "note": "part not chosen yet",
        },
        {"id": "ACC-003", "kind": "label", "position": "on the harness, near the first connector"},
    ):
        win.ctl.run("step", plan_set_accessory(win.ctl.project, hid, acc))
    win.go_to("harness")
    shots._settle(win)
    win.harness_view.refresh()
    win.harness_view.select_harness(hid)
    win.harness_view.side_tabs.setCurrentIndex(3)  # the Accessories tab
    win.harness_view.splitter.setSizes([160, 640])  # room for the table and the form of the tab
    win.harness_view.left_splitter.setSizes([260, 260, 1150])
    table = win.harness_view.accessory_editor.table
    table.setColumnWidth(4, 300)  # Position
    table.setColumnWidth(5, 120)  # Length (mm)
    shots._wait(800)
    _save(win, out / "accessories-tab.png")
    win.close()


def _export_pictures(win: MainWindow, out: Path) -> None:
    """The Export window before and after an export with the PDF drawings."""

    def dialog(d: Any) -> int:
        d.show()
        d.resize(1000, 720)
        shots._wait(500)
        _save(d, out / "export-window.png")
        d.drawings.setChecked(True)
        d.export_btn.click()
        waited = 0
        while d.export_result is None and waited < 60000:
            shots._wait(200)
            waited += 200
        shots._wait(800)
        _save(d, out / "export-window-done.png")
        return 0

    old = win.run_dialog
    win.run_dialog = dialog  # type: ignore[assignment]
    try:
        win.export_dialog_flow()
    finally:
        win.run_dialog = old  # type: ignore[assignment]


def _by_hand(win, out: Path) -> None:  # type: ignore[no-untyped-def]
    """A project from nothing with a harness made by hand: two connectors and three wires."""
    folder = Path(tempfile.gettempdir()) / "harness-by-hand" / "heater"
    shutil.rmtree(folder.parent, ignore_errors=True)
    folder.parent.mkdir(parents=True)
    win.ctl.new_project(folder, "Heater harness")
    p = win.ctl.project
    ops, hid = plan_new_harness(p, "Heater harness")
    win.ctl.run("step", ops)
    ids = []
    for part, name in (("EX-DSUB-9-M", "Panel end"), ("EX-DSUB-9-F", "Heater end")):
        ops, cid = plan_add_connector(p, hid, part_id=part, name=name)
        win.ctl.run("step", ops)
        ids.append(cid)
    a, b = ids
    for pin, signal, colour in (
        ("1", "HEATER +", "red"),
        ("2", "HEATER -", "black"),
        ("3", "SENSE", "blue"),
    ):
        win.ctl.run("step", plan_add_wire(p, hid, a, pin, b, pin, signal=signal, colour=colour))
    win.ctl.run(
        "step", plan_set_pin(p, hid, a, "1", function="Heater supply", termination="solder")
    )
    win.go_to("harness")
    shots._settle(win)
    win.harness_view.refresh()
    win.harness_view.select_harness(hid)
    win.harness_view.show_connectors()
    shots._wait(800)
    _save(win, out / "connectors-tab.png")


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT))
