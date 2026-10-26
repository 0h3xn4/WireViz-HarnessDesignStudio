# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr"
"""REQ-GUI-08. Workshop feedback M1: a new device asks for its name (and ID and subsystem) before it exists."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core import devices  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.devices_dialogs import NewDeviceDialog  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.gui_helpers import DialogScript, make_window  # noqa: E402


def dialog(qtbot, project=None) -> NewDeviceDialog:
    _ = QApplication.instance() or QApplication([])
    dlg = NewDeviceDialog(None, ThemeManager(), project or new_project())
    qtbot.addWidget(dlg)
    dlg.show()
    return dlg


def type_into(widget, text: str) -> None:
    QTest.keyClicks(widget, text)


# ---- the dialog -------------------------------------------------------------------------------


def test_the_dialog_asks_for_a_name_first(qtbot) -> None:
    dlg = dialog(qtbot)
    assert dlg.windowTitle() == strings.NEWDEV_TITLE == "Add device"
    assert dlg.name.placeholderText() == "for example Star tracker"
    assert dlg.focusWidget() is dlg.name  # (the name is focused)
    for w in (dlg.name, dlg.device_id, dlg.subsystem):
        assert w.accessibleName() and w.toolTip()
    assert dlg.ok.text() == "Add device" and not dlg.ok.isEnabled()
    assert dlg.notice.isVisibleTo(dlg) and "needs a name" in dlg.notice.text()


def test_the_id_follows_the_name_until_it_is_edited(qtbot) -> None:
    dlg = dialog(qtbot)
    type_into(dlg.name, "Star tracker")
    assert dlg.device_id.text() == "STAR1" and dlg.ok.isEnabled()
    assert not dlg.notice.isVisibleTo(dlg)
    type_into(dlg.name, " 2")  # the name goes on: the ID follows (the first word is the stem)
    assert dlg.device_id.text() == "STAR1"
    dlg.name.clear()
    assert dlg.device_id.text() == "" and not dlg.ok.isEnabled()
    type_into(dlg.name, "Gyro")
    assert dlg.device_id.text() == "GYRO1"
    # the person edits the ID: the name no longer overwrites it
    dlg.device_id.selectAll()
    type_into(dlg.device_id, "IMU")
    assert dlg.device_id.text() == "IMU"
    type_into(dlg.name, " unit")
    dlg.name.setText("Something else")
    assert dlg.device_id.text() == "IMU" and dlg.ok.isEnabled()
    assert dlg.values() == {"name": "Something else", "unit_id": "IMU", "subsystem": "general"}


def test_each_reason_shows_inline_and_keeps_ok_off(qtbot) -> None:
    p = new_project()
    ops, _ = devices.ops_add_device(p, unit_id="OBC1", name="Computer", subsystem="avionics")
    from harness_design_studio.core.commands import History

    History(p).execute("add", ops)
    dlg = dialog(qtbot, p)
    dlg.name.setText("Camera")
    assert dlg.ok.isEnabled()
    dlg.device_id.setText("")
    assert not dlg.ok.isEnabled() and "needs an ID" in dlg.notice.text()
    dlg.device_id.setText("1abc")
    assert not dlg.ok.isEnabled() and "cannot be used as an ID" in dlg.notice.text()
    dlg.device_id.setText("OBC1")
    assert not dlg.ok.isEnabled() and "already used" in dlg.notice.text()
    dlg.device_id.setText("obc1")
    assert not dlg.ok.isEnabled() and "already used" in dlg.notice.text()
    dlg.device_id.setText("CAM1")
    assert dlg.ok.isEnabled() and not dlg.notice.isVisibleTo(dlg)
    dlg.name.setText("   ")
    assert not dlg.ok.isEnabled() and "needs a name" in dlg.notice.text()


def test_the_suggested_id_is_unique_and_the_subsystem_offers_the_projects(qtbot) -> None:
    p = new_project()
    from harness_design_studio.core.commands import History

    for uid, sub in (("STAR1", "aocs"), ("OBC1", "avionics"), ("OBC2", "avionics")):
        ops, _ = devices.ops_add_device(p, unit_id=uid, name=uid, subsystem=sub)
        History(p).execute("add", ops)
    dlg = dialog(qtbot, p)
    dlg.name.setText("Star tracker")
    assert dlg.device_id.text() == "STAR2"
    items = [dlg.subsystem.itemText(i) for i in range(dlg.subsystem.count())]
    assert items == ["aocs", "avionics"] and dlg.subsystem.currentText() == "avionics"
    assert dlg.subsystem.isEditable()
    dlg.subsystem.setCurrentText("  ")
    assert dlg.values()["subsystem"] is None  # (empty: the default is used)


# ---- the flow ---------------------------------------------------------------------------------


def named(name: str, uid: str | None = None, subsystem: str | None = None):
    def fill(dlg):
        dlg.name.setText(name)
        if uid is not None:
            dlg.device_id.setText(uid)
        if subsystem is not None:
            dlg.subsystem.setCurrentText(subsystem)

    return fill


def test_ok_adds_the_named_device_as_one_undo_step_and_opens_it(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(new_project(), None, None)
    win.activateWindow()
    qtbot.waitUntil(win.isActiveWindow)
    script = DialogScript(win, named("Star tracker", subsystem="aocs"))
    win.add_device_flow()
    assert isinstance(script.seen[0], NewDeviceDialog)
    u = win.ctl.project.units["STAR1"]
    assert (u.name, u.subsystem) == ("Star tracker", "aocs") and "STAR1" in win.ctl.project.placements  # fmt: skip
    assert win.ctl.history.next_undo_label == "Add device STAR1"
    assert win.devices_view.unit_id() == "STAR1" and win.devices_view.name.hasFocus()
    win.ctl.undo()
    assert "STAR1" not in win.ctl.project.units and win.ctl.history.next_undo_label is None


def test_cancel_adds_nothing(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(new_project(), None, None)
    DialogScript(win, named("Nothing"), accept=False)
    win.add_device_flow()
    assert not win.ctl.project.units and win.ctl.history.next_undo_label is None


def test_a_read_only_project_refuses_before_asking(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(new_project(), None, None)
    win.ctl.project.read_only = True
    script = DialogScript(win, named("Nope"))
    win.add_device_flow()
    assert not script.seen and not win.ctl.project.units


@pytest.mark.parametrize("way", ["menu", "shortcut", "tool", "empty", "next", "palette"])
def test_every_way_to_add_a_device_asks_for_the_name(qtbot, tmp_path: Path, way: str) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl.new_project(tmp_path / "blank", "Blank")
    win.set_area("model")
    QApplication.processEvents()
    script = DialogScript(win, named("Reaction wheel"))
    if way == "menu":
        win.act_add_device.trigger()
    elif way == "shortcut":
        assert win.act_add_device.shortcut().toString() == "Ctrl+Shift+N"
        win.activateWindow()
        win.view.setFocus()
        QTest.keyClick(win, Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)  # fmt: skip
    elif way == "tool":
        win.set_workspace("simple")
        win.set_area("model")
        win.tool_add_device.click()
    elif way == "empty":
        assert win.view.empty_add.isVisibleTo(win.view)
        win.view.empty_add.click()
    elif way == "next":
        win.set_workspace("simple")
        win.set_area("next")
        assert win.next_page.key() == "add_device"
        win.next_page.button.click()
    else:
        entry = next(e for e in win.palette_entries() if e.label == strings.A_ADD_DEVICE)
        entry.run()
    QApplication.processEvents()
    assert len(script.seen) == 1 and isinstance(script.seen[0], NewDeviceDialog)
    assert list(win.ctl.project.units) == ["REACTION1"]
    assert win.ctl.project.units["REACTION1"].name == "Reaction wheel"


def test_the_template_path_keeps_its_own_names(qtbot, tmp_path: Path) -> None:
    from tests.gui_helpers import add_unit

    win = make_window(tmp_path)
    qtbot.addWidget(win)
    script = DialogScript(win, None)
    add_unit(win, "payload")
    assert not [d for d in script.seen if isinstance(d, NewDeviceDialog)]
    assert win.ctl.project.units


def test_the_dialog_is_a_modal_dialog_class() -> None:
    assert issubclass(NewDeviceDialog, QDialog)
