# mypy: allow-untyped-calls, no-warn-unused-ignores, disable-error-code=misc
"""Pictures of the editor for the user manual: the Edit wire tab, the Devices tab (1.4.0), the
Connectors tab (1.5.0) and, since 1.7.0, the Next step page, the Simple and the Full workspace, the
Accessories tab and the Export window.

Opens the real Qt editor offscreen (light theme, Simple workspace) on the flatsat example in a
1760 x 1000 window, where the tabs have room to show their names, and saves `edit-wire-tab.png`
(Drawings area, a wire selected, the Edit wire tab open) and `devices-tab.png` (the Devices tab of
the first device). Then it starts a project from nothing, makes a harness by hand with two connectors
and three wires, and saves `connectors-tab.png` (the Connectors tab). Then, in a 1440 x 900 window
on the tutorial project (`first-steps`, generated): `next-step-new-project.png` (an empty project),
`next-step-fix-problems.png` (one check fails), `next-step-export.png` (its parts approved, so
every check passes or waits for a value), `simple-workspace.png` and `full-workspace.png` (the
checked project in each workspace), `export-window.png` and `export-window-done.png` (the Export
window before and after an export with the PDF drawings). With two accessories added,
`accessories-tab.png` (1760 x 1000). Then, on the tutorial project, `add-device-dialog.png` (the
Add device dialog with Star tracker typed and the ID STAR1 suggested) and
`problem-notices-setting.png` (the View menu with Show problem notices). Last, on a small project
of three devices with named pins (no interface, no harness), `link-connectors-window.png` (the
window Link connectors with the pairs proposed by signal name for the computer and the reaction
wheel) and `connections-diagram.png` (two connections on the diagram, the Connections group in
the project tree). Since milestone M3: `edit-all-wires-window.png` (the window Edit all wires, a
gauge and a colour typed) and `connections-ends.png` (a connection in the Guided mode with the
connector boxes at its ends). Since milestone M4: `library-window.png` (the library window with a
subsystem chosen) and `library-save-window.png` (the window Save to library with a name typed).
The time of the last check, which the status bar shows, is cleared
before each picture. Usage:

    QT_QPA_PLATFORM=offscreen python -m tools.tab_screenshots [OUTPUT_FOLDER]   (default: docs/img)
    QT_QPA_PLATFORM=offscreen python -m tools.tab_screenshots [OUTPUT_FOLDER] editing
        (only connectors-tab.png, which has the Edit connector section now, and the two M3 pictures)
    QT_QPA_PLATFORM=offscreen python -m tools.tab_screenshots [OUTPUT_FOLDER] library
        (only the two library pictures)
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QItemSelectionModel, QPoint
from PySide6.QtWidgets import QApplication, QMenu

from harness_design_studio.core.build_data import plan_set_accessory
from harness_design_studio.core.commands import Op, Put, apply_ops
from harness_design_studio.core.generate.engine import plan_generation
from harness_design_studio.core.library_folder import save_devices, save_subsystem
from harness_design_studio.core.links import plan_add_link
from harness_design_studio.core.manual_harness import (
    plan_add_connector,
    plan_new_harness,
    plan_set_pin,
)
from harness_design_studio.core.model import Pin, Project, evolve
from harness_design_studio.core.samples import mini3
from harness_design_studio.core.wires import plan_add_wire
from harness_design_studio.gui.devices_dialogs import NewDeviceDialog
from harness_design_studio.gui.harness_edit_dialogs import BulkWireDialog
from harness_design_studio.gui.library_window import SaveToLibraryDialog
from harness_design_studio.gui.link_dialog import LinkDialog
from harness_design_studio.gui.main_window import MainWindow
from tools import ui_screenshots as shots

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "docs" / "img"
WIDTH, HEIGHT = 1760, 1000
MAIN = (1440, 900)  # the size of docs/ux/qt/02-guided-main.png
WIRE_ROW = 2  # a wire of the first harness that has a gauge, a type and a colour


def main(out: Path = DEFAULT_OUT, only: str = "") -> int:
    _ = QApplication.instance() or QApplication([])
    out.mkdir(parents=True, exist_ok=True)
    if only == "library":
        _library_pictures(out)
        print(f"wrote the pictures of the library to {out}")
        return 0
    if only == "editing":
        win = _window("harness-tab-shots", "flatsat", "simple", (WIDTH, HEIGHT))
        _by_hand(win, out)
        win.close()
        _editing_pictures(out)
        print(f"wrote the pictures of the editing windows to {out}")
        return 0
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
    _workshop_pictures(out)
    _connection_pictures(out)
    _editing_pictures(out)
    _library_pictures(out)
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
        ops: list[Op] = [
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
    for acc in (  # the two rows of the accessories file in the manual
        {"id": "ACC-001", "kind": "sleeving", "target": wire, "position": "whole wire"},
        {
            "id": "ACC-002",
            "kind": "heat_shrink",
            "target": connector,
            "position": "50 mm from the P1 end",
            "length_mm": 30,
            "quantity": 2,
            "note": "part not chosen yet",
        },
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


def _workshop_pictures(out: Path) -> None:
    """The Add device dialog (a name typed, the ID suggested) and the View menu with the setting
    Show problem notices, both in the Full workspace on the tutorial project."""
    win = _generated("harness-add-device", "full", MAIN)
    dlg = NewDeviceDialog(win, win.theme, win.ctl.project)
    dlg.show()
    dlg.resize(460, dlg.sizeHint().height())
    dlg.name.setText("Star tracker")  # the ID follows: STAR1
    shots._wait(500)
    _save(dlg, out / "add-device-dialog.png")
    dlg.close()
    menu = next(m for m in win.menuBar().findChildren(QMenu) if m.title() == "&View")
    menu.popup(win.mapToGlobal(QPoint(380, 40)))
    shots._wait(500)
    win.jobs.finish("")
    win._last_check = ""
    menu.grab().save(str(out / "problem-notices-setting.png"))
    print("problem-notices-setting.png")
    menu.close()
    win.close()


def _pinout_project() -> Project:
    """Three devices (a computer, a power unit and a reaction wheel) with named pins and no
    interface and no harness: the data connectors carry TX+, TX-, RX+, RX- and the power connectors
    PWR and RTN. Example data, no engineering values."""
    p = mini3()
    p.harnesses, p.interfaces, p.baselines = {}, {}, {}
    p.meta = evolve(p.meta, name="Wheel link", description="Example data.")
    data = [Pin(id=str(k + 1), signal=s) for k, s in enumerate(("TX+", "TX-", "RX+", "RX-"))]
    power = [Pin(id="1", signal="PWR"), Pin(id="2", signal="RTN")]
    for cid, pins in (
        ("OBC-J01", [*data, Pin(id="5")]),  # a pin with no signal is not asked about
        ("RW1-J02", [*data, Pin(id="5")]),
        ("PCDU-J01", power),
        ("RW1-J01", power),
    ):
        p.connectors[cid] = evolve(p.connectors[cid], pins=pins)
    for uid, x, y in (("OBC", 30.0, 40.0), ("PCDU", 30.0, 380.0), ("RW1", 470.0, 150.0)):
        p.placements[uid] = evolve(p.placements[uid], x=x, y=y)  # room for the labels of the lines
    return p


def _connection_pictures(out: Path) -> None:
    """The window Link connectors with the pairs proposed for the computer and the reaction wheel,
    and the diagram with two connections beside the Connections group of the project tree."""
    win = _window("harness-links", "blank", "full", MAIN)
    win.ctl._install(_pinout_project(), None, None)
    shots._settle(win)
    dlg = LinkDialog(win, win.theme, win.ctl.project, a_unit="OBC", b_unit="RW1")
    dlg.show()
    dlg.resize(dlg.width(), dlg.sizeHint().height())
    shots._wait(500)
    _save(dlg, out / "link-connectors-window.png")
    dlg.close()
    win.ctl.add_link("OBC-J01", "RW1-J02", [("1", "3"), ("2", "4"), ("3", "1"), ("4", "2")])
    win.ctl.add_link("PCDU-J01", "RW1-J01", [("1", "1"), ("2", "2")])
    win.go_to("diagram")
    win.act_expert.trigger()  # the lines then end at the connectors they join
    win.left_tabs.setCurrentIndex(win.left_tabs.index_of("tree"))
    win.view.fit()
    shots._settle(win, 700)
    win.ctl.select_link("L1")
    shots._wait(500)
    _save(win, out / "connections-diagram.png")
    win.close()


def _editing_pictures(out: Path) -> None:
    """The window Edit all wires on a generated harness of the tutorial project (a gauge and a
    colour typed), and a connection with the connector boxes at its ends (Guided mode)."""
    win = _generated("harness-bulk-edit", "full", MAIN)
    hid = sorted(win.ctl.project.harnesses)[0]
    dlg = BulkWireDialog(win, win.theme, win.ctl.project, hid)
    dlg.show()
    dlg.gauge.setText("22")
    dlg.colour.setCurrentText("red")
    dlg.resize(dlg.width(), dlg.sizeHint().height())
    shots._wait(500)
    _save(dlg, out / "edit-all-wires-window.png")
    dlg.close()
    win.close()
    win = _window("harness-links", "blank", "full", MAIN)
    win.ctl._install(_pinout_project(), None, None)
    shots._settle(win)
    win.ctl.add_link("OBC-J01", "RW1-J02", [("1", "3"), ("2", "4"), ("3", "1"), ("4", "2")])
    win.ctl.create_harness_from_link("L1")
    win.go_to("diagram")
    win.act_connection_ends.trigger()  # View > Show connectors on connections
    win.left_tabs.setCurrentIndex(win.left_tabs.index_of("tree"))
    win.view.fit()
    shots._settle(win, 700)
    win.ctl.select_link("L1")
    shots._wait(500)
    _save(win, out / "connections-ends.png")
    win.close()


def _library_pictures(out: Path) -> None:
    """The library window on a folder with two devices and a subsystem (the subsystem chosen), and
    the window Save to library with the computer and the reaction wheel selected."""
    folder = Path(tempfile.gettempdir()) / "harness-library"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    source = _pinout_project()
    ops, _ = plan_add_link(
        source, "OBC-J01", "RW1-J02", [("1", "3"), ("2", "4"), ("3", "1"), ("4", "2")]
    )
    apply_ops(source, ops)
    ops, _ = plan_add_link(source, "PCDU-J01", "RW1-J01", [("1", "1"), ("2", "2")])
    apply_ops(source, ops)
    save_devices(folder, source, ["PCDU"])
    save_devices(folder, source, ["RW1"])
    save_subsystem(
        folder,
        source,
        ["OBC", "RW1", "PCDU"],
        "Wheel drive",
        "The computer, the power unit and a reaction wheel, with the two connections between them",
    )  # noqa: E501
    win = _window("harness-library", "blank", "full", MAIN)
    win.set_library_folder(str(folder))
    win.open_library_flow()
    lib = win.library_window
    if lib is None:
        raise RuntimeError("the library window did not open")
    lib.resize(1160, 600)
    lib.jobs.wait_idle()
    sub = next(e for e in lib._shown if e.kind == "subsystem")
    lib.select_entry(sub.key)
    lib.jobs.wait_idle()
    shots._wait(500)
    _save(lib, out / "library-window.png")
    lib.close()
    win.ctl._install(source, None, None)
    win.ctl.select_many([("unit", "OBC"), ("unit", "RW1"), ("unit", "PCDU")])
    dlg = SaveToLibraryDialog(win, win.theme, source, ["OBC", "RW1", "PCDU"], str(folder))
    dlg.show()
    dlg.name.setText("Wheel drive 2")
    dlg.description.setText("The same three devices, saved again under another name")
    dlg.resize(max(dlg.width(), 560), dlg.sizeHint().height())
    shots._wait(500)
    _save(dlg, out / "library-save-window.png")
    dlg.close()
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
    raise SystemExit(
        main(
            Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT,
            sys.argv[2] if len(sys.argv) > 2 else "",
        )
    )
