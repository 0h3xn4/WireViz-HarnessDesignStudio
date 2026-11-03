# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""Transparency work, step 6 (D-193): the import wizard keeps the import record with the import, the
list of earlier imports on its first page marks a source that changed, the Next step page says so in
one quiet line, and nothing shows while the project has no import record."""

import shutil
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QWizard  # noqa: E402

from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.import_wizard import ImportWizard  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from harness_design_studio.resources import examples_path  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402
from tests.ux_rel import dict_rows, flatsat_controller, themed  # noqa: E402

LENGTHS = "harness,segment,length\nW001,W001-L1,850\nW002,W002-L1,900\n"


@pytest.fixture
def ctl(qtbot, tmp_path: Path):
    themed()
    return flatsat_controller(tmp_path)


def make(qtbot, ctl, kind: str, path: Path | None = None) -> ImportWizard:
    w = ImportWizard(ctl, themed(), pick_file=lambda k, f: str(path) if path else None, kind=kind)
    qtbot.addWidget(w)
    w.show()
    return w


def to_the_end(w: ImportWizard) -> None:
    for _ in range(3):
        button = w.button(QWizard.WizardButton.NextButton)
        assert button.isEnabled()
        button.click()
    w.button(QWizard.WizardButton.FinishButton).click()


def lengths_file(tmp_path: Path, text: str = LENGTHS) -> Path:
    f = tmp_path / "lengths.csv"
    f.write_text(text, encoding="utf-8")
    return f


def test_nothing_shows_while_the_project_has_no_import_record(qtbot, ctl, tmp_path) -> None:
    w = make(qtbot, ctl, "lengths", lengths_file(tmp_path))
    assert ctl.project.import_records == {}
    assert not w.file_page.history.isVisible() and not w.file_page.history_head.isVisible()
    assert unnamed(w) == []


def test_the_import_and_its_record_are_one_undo_step(qtbot, ctl, tmp_path) -> None:
    f = lengths_file(tmp_path)
    w = make(qtbot, ctl, "lengths", f)
    w.browse()
    revision = ctl.history.revision
    to_the_end(w)
    assert ctl.history.revision == revision + 1  # one step for the lengths and their record
    (rec,) = ctl.project.import_records.values()
    assert rec.id == "lengths:lengths.csv" and rec.rows_read == 2 and rec.unit == "mm"
    assert rec.unit_given and rec.converted_count == 2 and rec.source_path is None
    ctl.undo()
    assert ctl.project.import_records == {}  # the record goes with the import
    ctl.redo()
    assert list(ctl.project.import_records) == ["lengths:lengths.csv"]


def test_the_apply_page_says_what_is_kept(qtbot, ctl, tmp_path) -> None:
    w = make(qtbot, ctl, "lengths", lengths_file(tmp_path))
    w.browse()
    for _ in range(3):
        w.button(QWizard.WizardButton.NextButton).click()
    assert strings.IMP_APPLY_RECORD in w.apply_page.detail.text()


def test_columns_that_are_not_read_and_an_assumed_unit_are_said_on_the_check_page(
    qtbot, ctl, tmp_path
) -> None:
    f = tmp_path / "parts.csv"
    f.write_text(
        "part number,category,description,approval status,mass,Notes\n"
        "ZZ-1,connector,A connector,Approved,2.5,hand\n",
        encoding="utf-8",
    )
    w = make(qtbot, ctl, "parts", f)
    w.browse()
    w.button(QWizard.WizardButton.NextButton).click()
    w.map_page.word_edits["approved"].setText("Approved")
    w.replan()
    w.button(QWizard.WizardButton.NextButton).click()
    notes = w.check_page.notes.text()
    assert "Columns not read: Notes" in notes and "Unit: mass in g (assumed)." in notes
    w.button(QWizard.WizardButton.NextButton).click()
    w.button(QWizard.WizardButton.FinishButton).click()
    (rec,) = ctl.project.import_records.values()
    assert rec.columns_ignored == ["Notes"] and rec.unit == "g" and not rec.unit_given


def test_the_list_of_earlier_imports_marks_a_source_that_changed(qtbot, ctl, tmp_path) -> None:
    assert ctl.root is not None
    inside = ctl.root / "lengths.csv"  # inside the project folder: its path is kept
    inside.write_text(LENGTHS, encoding="utf-8")
    w = make(qtbot, ctl, "lengths", inside)
    w.browse()
    to_the_end(w)
    assert next(iter(ctl.project.import_records.values())).source_path == "lengths.csv"
    again = make(qtbot, ctl, "lengths")
    page = again.file_page
    assert page.history.isVisible() and page.history_head.isVisible()
    (row,) = dict_rows(page.history_model)
    assert row["file"] == "lengths.csv" and row["rows"] == 2 and row["source"] == ""  # quiet
    inside.write_text(LENGTHS.replace("900", "950"), encoding="utf-8")
    page.refresh_history()
    (row,) = dict_rows(page.history_model)
    assert row["source"] == strings.IMP_HISTORY_CHANGED
    inside.unlink()
    page.refresh_history()
    assert dict_rows(page.history_model)[0]["source"] == strings.IMP_HISTORY_MISSING
    assert unnamed(again) == []


@pytest.fixture
def win(qtbot, tmp_path):
    w = MainWindow(
        QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat),
        ThemeManager(),
        first_run=False,
    )
    qtbot.addWidget(w)
    w.show()
    return w


def test_the_next_step_page_says_so_once_in_a_quiet_line(qtbot, win, tmp_path) -> None:
    root = tmp_path / "flatsat"
    shutil.copytree(examples_path() / "projects" / "flatsat", root)  # type: ignore[operator]
    assert win.open_project(root)
    note = win.next_page.imports_note
    assert note.isHidden() and win._imports_changed_text() == ""  # default screen: clean
    f = root / "lengths.csv"
    f.write_text(LENGTHS, encoding="utf-8")
    w = make(qtbot, win.ctl, "lengths", f)
    w.browse()
    to_the_end(w)
    win._show_status(path=False)
    assert note.isHidden()  # imported, and the file is as it was
    f.write_text(LENGTHS + "W001,W001-L1,1\n", encoding="utf-8")
    win._show_status(path=False)
    assert not note.isHidden() and "lengths.csv" in note.text()
    assert note.accessibleName() == strings.NEXT_IMPORTS_NAME
    f.write_text(LENGTHS, encoding="utf-8")  # back to the recorded content
    win._show_status(path=False)
    assert note.isHidden()
    win.ctl.save()
