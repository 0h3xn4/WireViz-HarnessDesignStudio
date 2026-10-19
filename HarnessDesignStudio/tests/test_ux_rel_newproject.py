# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SH-18: one New project dialog (folder, name, what to start from) with the problems said next to the
field, instead of a chain of three pop-ups."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from harness_design_studio.core import templates  # noqa: E402
from harness_design_studio.core.templates import TEMPLATES  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.new_project_dialog import (  # noqa: E402
    BLANK,
    NewProjectDialog,
    NewProjectRequest,
    check_folder,
    check_name,
)
from tests.test_accessibility import unnamed  # noqa: E402
from tests.ux_rel import themed  # noqa: E402


def make(qtbot, **kw) -> NewProjectDialog:
    dlg = NewProjectDialog(themed(), **kw)
    qtbot.addWidget(dlg)
    dlg.show()
    return dlg


def test_it_starts_empty_with_the_templates_of_the_command_line(qtbot) -> None:
    dlg = make(qtbot)
    assert [dlg.model.item(r).data(Qt.ItemDataRole.UserRole) for r in range(dlg.model.rowCount())] == [t.name for t in TEMPLATES]  # fmt: skip
    assert dlg.template() == BLANK and dlg.model.item(0).text() == strings.NP_EMPTY_TITLE
    assert dlg.summary.text() == TEMPLATES[0].summary
    assert not dlg.ok.isEnabled() and dlg.request() is None
    assert (
        dlg.hint.isVisible()
        and "choose a folder" in dlg.hint.text()
        and "give it a name" in dlg.hint.text()
    )
    assert not dlg.folder_error.isVisible()  # nothing typed yet, so nothing to complain about


def test_the_name_follows_the_folder_until_it_is_typed(qtbot, tmp_path: Path) -> None:
    dlg = make(qtbot)
    dlg.folder.setText(str(tmp_path / "wheel-test"))
    assert dlg.name.text() == "wheel-test"
    assert dlg.ok.isEnabled()
    dlg.name.setFocus()
    QTest.keyClicks(dlg.name, "X")  # typed by a person
    typed = dlg.name.text()
    dlg.folder.setText(str(tmp_path / "other"))
    assert dlg.name.text() == typed  # no longer overwritten
    assert dlg.request() == NewProjectRequest(tmp_path / "other", typed, BLANK)


def test_problems_are_said_next_to_the_field(qtbot, tmp_path: Path) -> None:
    dlg = make(qtbot)
    full = tmp_path / "full"
    full.mkdir()
    (full / "x.txt").write_text("x")
    dlg.folder.setText(str(full))
    assert dlg.folder_error.isVisible() and dlg.folder_error.text() == strings.CHOOSE_EMPTY_NEW
    assert dlg.folder.property("invalid") is True and not dlg.ok.isEnabled()
    assert "use a folder that is new or empty" in dlg.hint.text()
    assert dlg.ok.toolTip() == dlg.hint.text()
    taken = tmp_path / "taken"
    taken.mkdir()
    (taken / "project.json").write_text("{}")
    dlg.folder.setText(str(taken))
    assert dlg.folder_error.text() == strings.FOLDER_HAS_PROJECT
    afile = tmp_path / "afile"
    afile.write_text("x")
    dlg.folder.setText(str(afile))
    assert dlg.folder_error.text() == strings.NP_ERR_FOLDER_FILE
    link = tmp_path / "link"
    link.symlink_to(full)
    dlg.folder.setText(str(link))
    assert dlg.folder_error.text() == strings.NP_ERR_FOLDER_LINK
    dlg.folder.setText(str(tmp_path / "fine" / "deeper"))  # a folder that does not exist yet
    assert not dlg.folder_error.isVisible() and dlg.ok.isEnabled()
    dlg.name.setText("   ")
    assert dlg.name_error.isVisible() and dlg.name_error.text() == strings.NP_ERR_NAME_NONE
    assert not dlg.ok.isEnabled()
    dlg.name.setText("x" * 201)
    assert dlg.name_error.text() == strings.NP_ERR_NAME_LONG.format(201)
    dlg.name.setText("line\nbreak")
    assert dlg.name_error.text() == strings.NP_ERR_NAME_CHARS
    dlg.name.setText("Good name")
    assert not dlg.name_error.isVisible() and dlg.ok.isEnabled()


def test_a_folder_that_cannot_be_written_is_refused(qtbot, tmp_path: Path) -> None:
    import os

    if sys.platform == "win32" or os.geteuid() == 0:
        pytest.skip("needs POSIX permissions and a user who is not root")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        assert "Nothing can be written" in check_folder(str(locked / "new"))
    finally:
        locked.chmod(0o700)
    assert check_folder("") == strings.NP_ERR_FOLDER_NONE
    assert check_name("ok") == ""


def test_browse_uses_the_folder_chooser(qtbot, tmp_path: Path) -> None:
    dlg = make(qtbot, ask_folder=lambda title: str(tmp_path / "chosen"))
    dlg.browse.click()
    assert dlg.folder.text() == str(tmp_path / "chosen") and dlg.name.text() == "chosen"


def test_choosing_an_example_changes_the_request_and_the_summary(qtbot, tmp_path: Path) -> None:
    dlg = make(qtbot, start_folder=tmp_path / "proj", template="flatsat")
    assert dlg.template() == "flatsat" and "23 flight and ground units" in dlg.summary.text()
    assert dlg.request() == NewProjectRequest(tmp_path / "proj", "proj", "flatsat")
    assert dlg.select_template("first-steps") and dlg.request().template == "first-steps"  # type: ignore[union-attr]
    assert not dlg.select_template("nope")


def test_the_request_creates_a_blank_and_an_example_project(qtbot, tmp_path: Path) -> None:
    """The window's two ways to create fit the request exactly (no extra question needed)."""
    blank = NewProjectRequest(tmp_path / "a", "Alpha", BLANK)
    ctl = EditorController()
    ctl.new_project(blank.folder, blank.name)
    assert ctl.project.meta.name == "Alpha" and (blank.folder / "project.json").is_file()
    ex = NewProjectRequest(tmp_path / "b", "Bravo", "first-steps")
    templates.create_project(ex.folder, ex.template, ex.name)
    ctl2 = EditorController()
    ctl2.open_path(ex.folder)
    assert ctl2.project.meta.name == "Bravo" and len(ctl2.project.units) == 3


def test_keyboard_only(qtbot, tmp_path: Path) -> None:
    dlg = make(qtbot)
    dlg.activateWindow()
    qtbot.waitActive(dlg)
    QApplication.processEvents()
    dlg.folder.setFocus()
    QTest.keyClicks(dlg.folder, str(tmp_path / "kbd"))
    QTest.keyClick(dlg.folder, Qt.Key.Key_Tab)  # to Choose folder…
    assert QApplication.focusWidget() is dlg.browse
    QTest.keyClick(dlg.browse, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is dlg.name
    QTest.keyClick(dlg.name, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is dlg.templates
    QTest.keyClick(dlg.templates, Qt.Key.Key_Down)
    assert dlg.template() == TEMPLATES[1].name
    # Enter creates (the primary button is the default)
    QTest.keyClick(dlg.name, Qt.Key.Key_Return)
    assert dlg.result() == QDialog.DialogCode.Accepted
    assert dlg.request() == NewProjectRequest(tmp_path / "kbd", "kbd", TEMPLATES[1].name)


def test_escape_cancels_and_names_exist(qtbot, tmp_path: Path) -> None:
    dlg = make(qtbot)
    assert unnamed(dlg) == []
    for b in (dlg.browse, dlg.ok, dlg.cancel):
        assert b.toolTip()
    dlg.activateWindow()
    qtbot.waitActive(dlg)
    QTest.keyClick(dlg, Qt.Key.Key_Escape)
    assert dlg.result() == QDialog.DialogCode.Rejected
