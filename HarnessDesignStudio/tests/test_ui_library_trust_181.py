# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,type-arg,no-any-return"
"""REQ-LIB-06. 1.8.1 (audit D4, D18): "Save to library" asks before it replaces a different device
of the same ID (Replace / Save as a new ID / Cancel) in the library window and in the Devices tab;
the library list has a File column; plain counts and a sentence said once. Offscreen."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QDialog  # noqa: E402

from harness_design_studio.core import device_library as dl  # noqa: E402
from harness_design_studio.core.library_folder import save_devices  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.library_window import (  # noqa: E402
    LibraryConflictDialog,
    SaveToLibraryDialog,
)
from tests.helpers import pinout_project  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402
from tests.test_ui_library_window import opened, window  # noqa: E402


def changed_obc():
    p = pinout_project()
    c = p.connectors["OBC-J01"]
    pin = c.pins[0].model_copy(update={"signal": "OTHER"})
    p.connectors["OBC-J01"] = c.model_copy(update={"pins": [pin, *c.pins[1:]]})
    return p


def signal_of(path: Path, uid: str) -> str:
    data = dl.read_library(path)
    dev = next(d for d in data["devices"] if d["unit"]["id"] == uid)
    return dev["connectors"][0]["pins"][0].get("signal", "")


@pytest.fixture
def lib_with_obc(tmp_path: Path) -> Path:
    lib = tmp_path / "lib"
    lib.mkdir()
    save_devices(lib, pinout_project(), ["OBC"])
    return lib


def start_save(qtbot, tmp_path: Path, folder: Path):
    win, lib = opened(qtbot, tmp_path, folder)
    win.ctl._install(changed_obc(), None, None)
    win.ctl.select_many([("unit", "OBC")])
    return win, lib


def answer_save(lib, choice: str, log: list):
    """Script the two dialogs of the save: the Save window (as devices), then the question."""

    def run(dlg):
        log.append(dlg)
        if isinstance(dlg, SaveToLibraryDialog):
            assert "OBC.json" in dlg.info.text()  # the target file is shown
            return QDialog.DialogCode.Accepted
        assert isinstance(dlg, LibraryConflictDialog)
        assert unnamed(dlg) == []
        {"replace": dlg.replace_btn, "new": dlg.new_btn, "cancel": dlg.cancel_btn}[choice].click()
        return dlg.result()

    lib.run_dialog = run


def test_the_save_window_names_the_file_the_devices_go_to(qtbot, tmp_path, lib_with_obc):
    win, lib = start_save(qtbot, tmp_path, lib_with_obc)
    dlg = SaveToLibraryDialog(lib, lib.theme, win.ctl.project, ["OBC"], str(lib_with_obc))
    qtbot.addWidget(dlg)
    assert strings.LIB_SAVE_TARGET.format("OBC.json") in dlg.info.text()


def test_cancel_changes_nothing(qtbot, tmp_path, lib_with_obc):
    win, lib = start_save(qtbot, tmp_path, lib_with_obc)
    before = (lib_with_obc / "OBC.json").read_bytes()
    log: list = []
    answer_save(lib, "cancel", log)
    lib.save_btn.click()
    assert [type(d).__name__ for d in log] == ["SaveToLibraryDialog", "LibraryConflictDialog"]
    text = log[1].text.text()
    assert "OBC is in the library already" in text and "OBC.json" in text and "1 pin" in text
    assert log[1].new_btn.text() == "Save as OBC-2"
    assert (lib_with_obc / "OBC.json").read_bytes() == before
    assert not lib.result_notice.isVisibleTo(lib)


def test_replace_replaces(qtbot, tmp_path, lib_with_obc):
    win, lib = start_save(qtbot, tmp_path, lib_with_obc)
    answer_save(lib, "replace", [])
    lib.save_btn.click()
    assert signal_of(lib_with_obc / "OBC.json", "OBC") == "OTHER"
    assert "Saved OBC to OBC.json" in lib.result_notice.text()


def test_save_as_a_new_id_keeps_both(qtbot, tmp_path, lib_with_obc):
    win, lib = start_save(qtbot, tmp_path, lib_with_obc)
    answer_save(lib, "new", [])
    lib.save_btn.click()
    path = lib_with_obc / "OBC.json"
    assert signal_of(path, "OBC") != "OTHER" and signal_of(path, "OBC-2") == "OTHER"
    assert "OBC-2" in lib.result_notice.text()
    assert lib.jobs.wait_idle()
    assert {e.id for e in lib._shown} >= {"OBC", "OBC-2"}
    assert "OBC-2" not in win.ctl.project.units  # the project is not touched


def test_the_same_device_again_is_not_asked_about(qtbot, tmp_path, lib_with_obc):
    win, lib = opened(qtbot, tmp_path, lib_with_obc)
    win.ctl._install(pinout_project(), None, None)
    win.ctl.select_many([("unit", "OBC")])
    log: list = []
    answer_save(lib, "cancel", log)
    lib.save_btn.click()
    assert [type(d).__name__ for d in log] == ["SaveToLibraryDialog"]


def test_the_devices_tab_asks_too(qtbot, tmp_path):
    win = window(qtbot, tmp_path)
    win.ctl._install(changed_obc(), None, None)
    win.ctl.select("unit", "OBC")
    target = tmp_path / "lib.json"
    save_devices(tmp_path, pinout_project(), ["OBC"])
    (tmp_path / "OBC.json").rename(target)
    before = target.read_bytes()
    win.ask_save_path = lambda *_: str(target)
    asked: list = []

    def run(choice):
        def go(dlg):
            asked.append(dlg)
            {"replace": dlg.replace_btn, "new": dlg.new_btn, "cancel": dlg.cancel_btn}[
                choice
            ].click()
            return dlg.result()

        return go

    win.run_dialog = run("cancel")
    win.save_device_to_library_flow("OBC")
    assert len(asked) == 1 and target.read_bytes() == before
    win.run_dialog = run("new")
    win.save_device_to_library_flow("OBC")
    assert signal_of(target, "OBC-2") == "OTHER" and signal_of(target, "OBC") != "OTHER"
    win.run_dialog = run("replace")  # (the file still has the old OBC)
    win.save_device_to_library_flow("OBC")
    assert signal_of(target, "OBC") == "OTHER"


def test_the_list_has_a_file_column_so_equal_looking_entries_differ(qtbot, tmp_path, lib_with_obc):
    sub = lib_with_obc / "team"
    sub.mkdir()
    save_devices(sub, changed_obc(), ["OBC"])
    win, lib = opened(qtbot, tmp_path, lib_with_obc)
    assert lib.list_model.columnCount() == 5
    files = [lib.list_model.text_at(r, lib.list_model.column_index("file")) for r in range(2)]
    assert sorted(files) == ["OBC.json", "team/OBC.json"]


def test_the_counts_use_words_and_a_missing_folder_is_said_once(qtbot, tmp_path):
    win, lib = opened(qtbot, tmp_path, tmp_path / "unplugged-drive")
    assert "does not exist" in lib.folder_notice.text()
    assert "does not exist" not in lib.empty_hint.text()
    assert lib.empty_hint.text() == strings.LIB_EMPTY_UNREADABLE_HINT


def test_one_damaged_file_and_several_are_counted_in_words(qtbot, tmp_path, lib_with_obc):
    (lib_with_obc / "a.json").write_text("{nope")
    win, lib = opened(qtbot, tmp_path, lib_with_obc)
    assert "1 file in the folder could not be used" in lib.folder_notice.text()
    (lib_with_obc / "b.json").write_text("{nope")
    lib.refresh_btn.click()
    assert lib.jobs.wait_idle()
    text = lib.folder_notice.text()
    assert "2 files in the folder could not be used" in text and "(s)" not in text
    assert "line 1" in text  # where, not a Python name
    for word in ("JSONDecodeError", "UnicodeDecodeError", "RecursionError"):
        assert word not in text
