# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""Quick mode, Add device: only a name (a kind when wanted), a connector from the start so that
Connect always works, the diagram stays in front. The five-step journey of the manual page
*Make a block diagram in five minutes*: New project, Add device, Add device, Connect, Export
diagram. Without Quick mode the dialog is the one it always was."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication, QLineEdit  # noqa: E402

from harness_design_studio.core import edit  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.devices_dialogs import (  # noqa: E402
    NewDeviceDialog,
    QuickDeviceDialog,
)
from tests.gui_helpers import (  # noqa: E402
    DialogScript,
    click_unit,
    make_window,
    new_project_answers,
)


def window(tmp_path, *, quick=True):
    win = make_window(tmp_path)
    win.ctl._install(new_project("Rig"), None, None)
    if quick:
        win.act_quick.trigger()
    QApplication.processEvents()
    return win


def add(win, name: str, kind: str = ""):
    def fill(dlg: QuickDeviceDialog) -> None:
        dlg.name.setText(name)
        if kind:
            dlg.kind.setCurrentIndex(dlg.kind.findData(kind))

    DialogScript(win, fill)
    win.act_add_device.trigger()
    return win.ctl.selection.id if win.ctl.selection else None


def test_the_quick_dialog_asks_for_a_name_and_a_kind_only(qtbot, tmp_path) -> None:
    win = window(tmp_path)
    script = DialogScript(win, accept=False)
    win.act_add_device.trigger()
    dlg = script.seen[0]
    assert isinstance(dlg, QuickDeviceDialog)
    assert [w.accessibleName() for w in dlg.findChildren(QLineEdit)] == [strings.NEWDEV_NAME]
    assert dlg.kind.itemText(0) == strings.QD_NEWDEV_NONE and dlg.kind.count() > 1
    assert dlg.ok is not None and not dlg.ok.isEnabled()  # (a name is needed)
    dlg.name.setText("Star tracker")
    assert dlg.ok.isEnabled() and dlg.values() == {"name": "Star tracker", "unit_id": "STAR1"}
    assert dlg.template_id() == ""
    assert win.ctl.project.units == {}  # (cancelled: nothing was added)


def test_without_quick_the_dialog_is_the_one_it_always_was(qtbot, tmp_path) -> None:
    win = window(tmp_path, quick=False)
    script = DialogScript(win, accept=False)
    win.act_add_device.trigger()
    assert isinstance(script.seen[0], NewDeviceDialog)
    assert script.seen[0].device_id.accessibleName() == strings.NEWDEV_ID


def test_a_device_gets_a_starter_connector_in_one_undo_step(qtbot, tmp_path) -> None:
    win = window(tmp_path)
    before = win.ctl.history.revision
    uid = add(win, "Star tracker")
    assert uid == "STAR1" and win.ctl.history.revision == before + 1
    p = win.ctl.project
    assert p.units[uid].name == "Star tracker"
    boxes = edit.unit_connectors(p, uid)
    assert [(c.part_id, len(c.pins)) for c in boxes] == [("EX-DSUB-9-M", 9)]
    assert win.area() == "model"
    win.ctl.undo()
    assert uid not in win.ctl.project.units and not win.ctl.project.connectors


def test_a_kind_gives_the_connectors_of_its_template(qtbot, tmp_path) -> None:
    win = window(tmp_path)
    tid = next(iter(edit.TEMPLATES))
    uid = add(win, "Main computer", tid)
    p = win.ctl.project
    assert p.units[uid].name == "Main computer"
    assert len(edit.unit_connectors(p, uid)) == len(edit.TEMPLATES[tid].connectors) > 0


def test_two_devices_of_the_same_name_get_two_ids(qtbot, tmp_path) -> None:
    win = window(tmp_path)
    assert (add(win, "Camera"), add(win, "Camera")) == ("CAMERA1", "CAMERA2")


def test_a_device_added_in_quick_mode_can_be_connected_at_once(qtbot, tmp_path) -> None:
    win = window(tmp_path)
    a, b = add(win, "OBC"), add(win, "Star tracker")
    script = DialogScript(win)
    lid = win.quick_link_flow(a, b)
    assert lid and script.seen == [] and win.ctl.project.links[lid].pairs  # (pin by number)
    assert strings.QL_CONNECTED.format(a=a, b=b) in win.toasts.messages[-1]


def test_the_five_steps_of_the_manual_page(qtbot, tmp_path) -> None:
    """New project -> Add device -> Add device -> Connect -> Export diagram, in Quick mode, with
    no folder chosen for the export, no Generate and no check."""
    win = make_window(tmp_path)
    win.act_quick.trigger()
    folder = tmp_path / "rig"
    folder.mkdir()
    new_project_answers(win, folder, "Test rig")
    win.act_new.trigger()
    assert win.ctl.project.meta.name == "Test rig" and win.area() == "model"
    a, b = add(win, "Power supply"), add(win, "Flight computer")
    win.ctl.begin_link()
    DialogScript(win)
    click_unit(win, a)
    click_unit(win, b)
    QApplication.processEvents()
    assert list(win.ctl.project.links) == ["L1"]
    target = tmp_path / "diagram.svg"
    win.ask_save_path = lambda t, n, f: str(target)
    win.topbar.export_diagram_btn.click()
    assert target.is_file() and target.with_suffix(".pdf").is_file() and target.with_suffix(".png").is_file()  # fmt: skip
    assert b"L1" in target.read_bytes()
    assert not (folder / "outputs").exists()  # (no Generate, no export of the outputs folder)
