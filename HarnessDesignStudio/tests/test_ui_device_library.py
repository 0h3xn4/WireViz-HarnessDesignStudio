# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""1.4.0 M5: the Devices tab saves a device to a library file and adds devices from one."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QDialog  # noqa: E402

from harness_design_studio.core.device_library import read_library  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.devices_dialogs import LibraryDialog  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402
from tests.test_ux_devices import custom  # noqa: E402


def window(qtbot, tmp_path: Path):
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(custom(), None, None)
    win.go_actions["devices"].trigger()
    return win


def test_save_to_library_writes_the_device_and_adds_to_an_existing_file(qtbot, tmp_path: Path):
    win = window(qtbot, tmp_path)
    lib = tmp_path / "lib.json"
    asked: dict[str, str] = {}

    def ask(title, suggested, filters):
        asked.update(title=title, suggested=suggested, filters=filters)
        return str(lib)

    win.ask_save_path = ask
    win.devices_view.lib_save_btn.click()
    assert asked["suggested"] == "GYRO1.json" and asked["title"] == strings.DV_LIB_SAVE_TITLE
    data = read_library(lib)
    assert [d["unit"]["id"] for d in data["devices"]] == ["GYRO1"]
    pins = [p["id"] for c in data["devices"][0]["connectors"] for p in c["pins"]]
    assert "A1" in pins and data["parts"]
    win.devices_view.lib_save_btn.click()  # again: replaced, not doubled
    assert len(read_library(lib)["devices"]) == 1


def test_add_from_library_is_one_undo_step_and_shows_the_new_device(qtbot, tmp_path: Path):
    win = window(qtbot, tmp_path)
    lib = tmp_path / "lib.json"
    win.ask_save_path = lambda *_: str(lib)
    win.devices_view.lib_save_btn.click()

    win.ctl._install(new_project(), None, None)  # a different, empty project
    win.go_actions["devices"].trigger()
    win.ask_open_path = lambda *_: str(lib)
    seen: list[LibraryDialog] = []

    def accept(dlg: QDialog) -> int:
        assert isinstance(dlg, LibraryDialog)
        seen.append(dlg)
        assert dlg.selected() == ["GYRO1"] and dlg.ok is not None and dlg.ok.isEnabled()
        assert "GYRO1" in dlg.preview.text()
        assert unnamed(dlg) == []
        return QDialog.DialogCode.Accepted

    win.run_dialog = accept
    win.devices_view.lib_add_btn.click()
    assert seen and "GYRO1" in win.ctl.project.units
    assert win.devices_view.unit_id() == "GYRO1"
    assert win.ctl.project.connectors["GYRO1-J01"].pins
    win.ctl.undo()
    assert "GYRO1" not in win.ctl.project.units

    win.ctl.redo()
    win.devices_view.lib_add_btn.click()  # the device exists now: the next free ID
    assert "GYRO1-2" in win.ctl.project.units


def test_the_dialog_keeps_ok_off_until_a_device_is_ticked(qtbot, tmp_path: Path):
    win = window(qtbot, tmp_path)
    lib = tmp_path / "lib.json"
    win.ask_save_path = lambda *_: str(lib)
    win.devices_view.lib_save_btn.click()
    dlg = LibraryDialog(win, win.theme, win.ctl.project, read_library(lib))
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.ok is not None
    item = dlg.devices.item(0)
    from PySide6.QtCore import Qt

    item.setCheckState(Qt.CheckState.Unchecked)
    assert not dlg.ok.isEnabled() and dlg.notice.isVisible()
    item.setCheckState(Qt.CheckState.Checked)
    assert dlg.ok.isEnabled()


def test_a_file_that_is_not_a_library_is_said_in_words_and_changes_nothing(qtbot, tmp_path: Path):
    win = window(qtbot, tmp_path)
    junk = tmp_path / "junk.json"
    junk.write_text("[]")
    win.ask_open_path = lambda *_: str(junk)
    errors: list[str] = []
    win._error = errors.append  # type: ignore[method-assign]
    before = set(win.ctl.project.units)
    win.devices_view.lib_add_btn.click()
    assert errors and "not a device library" in errors[0]
    assert set(win.ctl.project.units) == before


def test_read_only_projects_refuse_to_add(qtbot, tmp_path: Path):
    win = window(qtbot, tmp_path)
    called: list[int] = []
    win.ask_open_path = lambda *_: called.append(1)  # type: ignore[assignment,return-value]
    win.ctl.project.read_only = True
    win.devices_view.lib_add_btn.click()
    assert not called
