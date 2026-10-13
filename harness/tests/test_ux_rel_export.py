# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SC-12 / SH-27: the export dialog. One dialog: output folder, harness x document tree, progress with
Cancel, the list of files written with Reveal / Open / a drawing picture, inline notices instead of
pop-ups. Driven offscreen on the flatsat example (113 files)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings, Qt, QUrl  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from harness_design_studio.core import edit  # noqa: E402
from harness_design_studio.core.commands import Put  # noqa: E402
from harness_design_studio.core.model import evolve  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.core.verify import VerifyReport  # noqa: E402
from harness_design_studio.gui import export_docs, strings  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.export_dialog import (  # noqa: E402
    ExportDialog,
    ExportResult,
    human_size,
    open_url,
    reveal_url,
)
from harness_design_studio.gui.main_window import OutputsWorker  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402
from tests.ux_rel import (  # noqa: E402
    app,
    collect,
    dict_rows,
    flatsat_controller,
    outputs_of,
    settings,
    themed,
)


@pytest.fixture(scope="module")
def done(tmp_path_factory):
    """One real export of flatsat, shared by the tests that only read its result."""
    app()
    tmp = tmp_path_factory.mktemp("export")
    ctl = flatsat_controller(tmp)
    opened: list[QUrl] = []

    def opener(url: QUrl) -> bool:
        opened.append(url)
        return True

    dlg = ExportDialog(ctl, themed(), settings=settings(tmp), opener=opener)
    dlg.resize(1100, 700)
    dlg.show()
    dlg.activateWindow()
    QTest.qWaitForWindowActive(dlg)
    exported = collect(dlg.exported)
    result = dlg.run()
    assert result is not None
    yield SimpleNamespace(ctl=ctl, dlg=dlg, res=result, opened=opened, tmp=tmp, exported=exported)
    dlg.close()


def recorder(opened: list[QUrl]):  # type: ignore[no-untyped-def]
    """An opener that remembers the URLs it was given."""

    def opener(url: QUrl) -> bool:
        opened.append(url)
        return True

    return opener


def activate(widget) -> None:
    """Make the window the active one so keys reach the focused widget (as for a person)."""
    widget.show()
    widget.activateWindow()
    QTest.qWaitForWindowActive(widget)
    QApplication.processEvents()


@pytest.fixture
def clean(done):
    """The shared dialog with everything ticked and nothing opened yet."""
    activate(done.dlg)
    done.dlg.set_all_checked(True)
    done.dlg.notice.clear()
    done.opened.clear()
    return done


class FakeWorker(OutputsWorker):
    """Finishes at once with a given result (a real set built earlier) and report."""

    def __init__(self, project, built=None, report=None, error=None) -> None:
        super().__init__(project)
        self._built, self._report, self._error = built, report, error

    def run(self) -> None:
        self.result, self.report, self.error = self._built, self._report, self._error
        self.progressed.emit(0.5, "Half way")


def fake_factory(built, report=None, error=None):
    return lambda project: FakeWorker(project, built, report or VerifyReport(), error)


def select(dlg: ExportDialog, rel: str) -> None:
    assert dlg.result_panel.select_file(rel), rel


# ---- the layout of the documents --------------------------------------------------------------


def test_every_written_file_is_a_known_document_and_every_document_type_occurs(done) -> None:
    files = done.res.files
    assert done.res.count == 113 and len(files) > 100
    for f in files:
        assert f.doc.key in export_docs.DOCS, f.rel  # never the file name fallback
    for hid in done.ctl.project.harnesses:
        keys = {f.doc.key for f in files if f.doc.scope == hid}
        assert keys == {d.key for d in export_docs.HARNESS_DOCS}, hid
    assert {f.doc.key for f in files if f.doc.scope == "system"} == {d.key for d in export_docs.SYSTEM_DOCS}  # fmt: skip
    manifest = next(f for f in files if f.rel == "manifest.json")
    assert manifest.doc.scope == "" and manifest.doc.key == "manifest"


def test_an_unknown_file_still_gets_a_name_and_nothing_crashes() -> None:
    doc = export_docs.classify("harnesses/W001/new_thing.txt")
    assert doc.scope == "W001" and doc.label == "new_thing.txt" and doc.key == "harnesses/W001/new_thing.txt"  # fmt: skip
    assert export_docs.classify("odd").scope == ""
    assert export_docs.sheet_ref("harnesses/W001/wirelist.csv") is None
    assert export_docs.sheet_ref("harnesses/W001/drawing_A3_s2.svg") == ("harness", "W001", "A3", 1)
    assert export_docs.sheet_ref("harnesses/W001/drawing_A4.pdf") == ("harness", "W001", "A4", 0)
    assert export_docs.sheet_ref("system/block_diagram.svg") == ("system", "block_diagram")
    assert not export_docs.is_safe("../x") and not export_docs.is_safe("/etc/x") and not export_docs.is_safe("manifest.json")  # fmt: skip


# ---- what blocks an export, said in the dialog ------------------------------------------------


def test_an_unsaved_project_is_explained_inline_with_a_save_action(qtbot, tmp_path: Path) -> None:
    ctl = EditorController()
    dlg = ExportDialog(ctl, themed(), ask_folder=lambda title: str(tmp_path / "saved"))
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.folder.isReadOnly() and dlg.folder.text() == strings.EXP_FOLDER_UNSAVED
    assert dlg.notice.isVisible() and "no folder yet" in dlg.notice.text()
    assert dlg.notice.action.isVisible() and dlg.notice.action.text() == strings.EXP_SAVE_PROJECT
    assert not dlg.export_btn.isEnabled()
    assert dlg.start() is False and not dlg.running
    dlg.notice.action.click()  # Save project…
    assert ctl.root == tmp_path / "saved" and (tmp_path / "saved" / "project.json").is_file()
    assert dlg.folder.text() == str(tmp_path / "saved" / "outputs")
    assert strings.EXPORT_NO_HARNESSES in dlg.notice.text()  # the next thing in the way
    assert not dlg.notice.action.isVisible()


def test_read_only_damaged_and_empty_projects_say_why(qtbot, tmp_path: Path) -> None:
    ctl = flatsat_controller(tmp_path)
    dlg = ExportDialog(ctl, themed())
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.blocker() is None and dlg.export_btn.isEnabled() and not dlg.notice.isVisible()
    ctl.project.read_only = True
    dlg.refresh()
    assert dlg.notice.text() == strings.EXPORT_READ_ONLY and not dlg.export_btn.isEnabled()
    ctl.project.read_only = False
    ctl.project.quarantine_files = {"x.json": b"{"}
    dlg.refresh()
    assert dlg.notice.text() == strings.EXPORT_DAMAGED
    ctl.project.quarantine_files = {}
    dlg.refresh()
    assert not dlg.notice.isVisible() and dlg.export_btn.isEnabled()
    empty = EditorController()
    empty.root = tmp_path / "somewhere"
    empty.project = new_project("x")
    d2 = ExportDialog(empty, themed())
    qtbot.addWidget(d2)
    assert d2.notice.text() == strings.EXPORT_NO_HARNESSES


# ---- the tree -----------------------------------------------------------------------------------


def test_the_tree_offers_harness_by_document_with_everything_ticked(qtbot, tmp_path: Path) -> None:
    ctl = flatsat_controller(tmp_path)
    dlg = ExportDialog(ctl, themed())
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.folder.text() == str(tmp_path / "flatsat" / "outputs")
    top = [dlg.model.item(r) for r in range(dlg.model.rowCount())]
    assert [t.data(Qt.ItemDataRole.UserRole) for t in top] == [*sorted(ctl.project.harnesses), "system"]  # fmt: skip
    assert top[0].text().startswith("W001  ")
    assert top[0].rowCount() == len(export_docs.HARNESS_DOCS)
    assert top[-1].text() == strings.EXP_SYSTEM and top[-1].rowCount() == len(
        export_docs.SYSTEM_DOCS
    )
    assert all(t.checkState() == Qt.CheckState.Checked for t in top)
    assert dlg.checked_documents() == {(s, d.key) for s, docs in export_docs.planned_layout(ctl.project.harnesses) for d in docs}  # fmt: skip
    assert strings.EXP_FULL_NOTE in dlg.note.text()  # says the whole set is always written
    # a harness node follows its children (tri-state)
    assert dlg.set_checked("W001", "bom", False)
    assert top[0].checkState() == Qt.CheckState.PartiallyChecked
    assert not dlg.set_checked("W999", None, False)


# ---- running and the result ---------------------------------------------------------------------


def test_the_export_writes_the_full_set_and_lists_every_file(done) -> None:
    folder = outputs_of(done.ctl)
    res = done.res
    assert isinstance(res, ExportResult) and res.folder == folder
    assert len(done.exported) == 1 and done.exported[0][0] is res
    panel = done.dlg.result_panel
    assert panel.model.rowCount() == 113 and panel.table.proxy.rowCount() == 113
    on_disk = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    assert on_disk == sorted(f.rel for f in res.files)
    for f in res.files:
        assert f.path.is_file() and f.path.stat().st_size == f.size
    # the independent check passed and the folder is current
    assert done.ctl.outputs_state() == "current"
    assert done.dlg.pages.currentWidget() is panel
    assert done.dlg.export_btn.text() == strings.EXP_AGAIN
    assert "113 files written" in panel.summary.text() and res.stamp in panel.summary.text()
    # columns: path, document, harness, size (a number, shown in kB)
    first = dict_rows(panel.model)[0]
    assert set(first) >= {"rel", "doc", "scope", "size"}
    size_col = panel.model.column_index("size")
    assert panel.model.text_at(0, size_col) == human_size(int(first["size"]))
    assert human_size(512) == "512 B" and human_size(12_300) == "12.3 kB" and human_size(2_500_000) == "2.5 MB"  # fmt: skip


def test_reveal_and_open_build_the_right_urls(clean) -> None:
    dlg, folder = clean.dlg, outputs_of(clean.ctl)
    panel = dlg.result_panel
    assert panel.reveal_selected() is None  # nothing selected yet
    select(dlg, "harnesses/W001/wirelist.csv")
    assert panel.reveal_btn.isEnabled() and panel.open_btn.isEnabled()
    assert panel.path_label.text() == str(folder / "harnesses" / "W001" / "wirelist.csv")
    panel.reveal_btn.click()
    assert clean.opened[-1] == QUrl.fromLocalFile(str(folder / "harnesses" / "W001"))
    assert clean.opened[-1] == reveal_url(folder / "harnesses" / "W001" / "wirelist.csv")
    panel.open_btn.click()
    assert clean.opened[-1] == QUrl.fromLocalFile(str(folder / "harnesses" / "W001" / "wirelist.csv"))  # fmt: skip
    assert clean.opened[-1] == open_url(folder / "harnesses" / "W001" / "wirelist.csv")
    panel.folder_btn.click()
    assert clean.opened[-1] == QUrl.fromLocalFile(str(folder))
    assert clean.opened[-1].isLocalFile() and clean.opened[-1].toLocalFile() == str(folder)


def test_enter_opens_and_ctrl_enter_reveals_from_the_keyboard(clean) -> None:
    dlg, folder = clean.dlg, outputs_of(clean.ctl)
    select(dlg, "system/bom.csv")
    table = dlg.result_panel.table
    table.setFocus()
    QTest.keyClick(table, Qt.Key.Key_Return)
    assert clean.opened[-1] == QUrl.fromLocalFile(str(folder / "system" / "bom.csv"))
    QTest.keyClick(table, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert clean.opened[-1] == QUrl.fromLocalFile(str(folder / "system"))
    assert dlg.isVisible() and not dlg.running  # Enter in the list did not press the default button


def test_a_drawing_shows_a_picture_and_a_table_does_not(clean) -> None:
    dlg = clean.dlg
    panel = dlg.result_panel
    select(dlg, "harnesses/W001/drawing_A3_s1.svg")
    assert panel.previewing() and panel.sheet_view.sheet is not None
    assert "W001" in "".join(getattr(t, "s", "") for t in panel.sheet_view.sheet.items)
    image = panel.sheet_view.grab().toImage()
    colours = {image.pixel(x, y) for x in range(0, image.width(), 7) for y in range(0, image.height(), 7)}  # fmt: skip
    assert len(colours) > 3  # it is a drawing, not an empty box
    select(dlg, "harnesses/W001/drawing_A4.pdf")
    assert panel.previewing()
    select(dlg, "system/block_diagram.svg")
    assert panel.previewing()
    select(dlg, "harnesses/W001/wirelist.csv")
    assert not panel.previewing() and panel.preview_note.text() == strings.EXP_PREVIEW_NONE


def test_the_ticks_choose_what_the_result_list_shows(clean) -> None:
    dlg, panel = clean.dlg, clean.dlg.result_panel
    assert panel.model.rowCount() == 113 and not panel.showing.isVisible()
    dlg.set_checked("W002", None, False)
    shown = {r["rel"] for r in dict_rows(panel.model)}
    assert not any(rel.startswith("harnesses/W002/") for rel in shown)
    assert any(rel.startswith("harnesses/W001/") for rel in shown)
    assert "manifest.json" in shown  # part of what was written, always listed
    assert panel.showing.isVisible() and f"of {clean.res.count} files" in panel.showing.text()
    select(dlg, "harnesses/W001/drawing_A3_s1.svg")
    dlg.set_checked("W003", None, False)
    assert [f.rel for f in panel.selected_files()] == ["harnesses/W001/drawing_A3_s1.svg"]  # kept
    assert panel.previewing()
    dlg.set_all_checked(True)
    dlg.set_checked("system", "sys_bom", False)
    assert "system/bom.csv" not in {r["rel"] for r in dict_rows(panel.model)}
    dlg.none_btn.click()
    assert {r["rel"] for r in dict_rows(panel.model)} == {"manifest.json"}
    assert dlg.selected_paths() == set()
    dlg.all_btn.click()
    assert panel.model.rowCount() == 113 and len(dlg.selected_paths()) == 112


def test_copy_selection_copies_the_ticked_files_byte_for_byte_without_the_manifest(clean, tmp_path) -> None:  # fmt: skip
    dlg, folder = clean.dlg, outputs_of(clean.ctl)
    dlg.none_btn.click()
    dlg.set_checked("W001", None, True)
    dlg.set_checked("system", "sys_changelog", True)
    wanted = sorted(f.rel for f in clean.res.files if f.doc.scope == "W001") + ["system/changelog.csv"]  # fmt: skip
    assert dlg.copy_btn.isVisible() and dlg.copy_btn.isEnabled()
    target = tmp_path / "copy"
    n = dlg.copy_selection(target)
    assert n == len(wanted) == 14
    copied = sorted(p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file())
    assert copied == wanted and "manifest.json" not in copied
    for rel in wanted:
        assert (target / rel).read_bytes() == (folder / rel).read_bytes()
    assert dlg.notice.isVisible() and "Copied" in dlg.notice.text() and "manifest" in dlg.notice.text()  # fmt: skip
    dlg.notice.action.click()  # the notice offers to reveal the copy
    assert clean.opened[-1] == QUrl.fromLocalFile(str(target))
    # the original outputs are untouched and still current
    assert clean.ctl.outputs_state() == "current"


def test_copy_refuses_a_folder_that_is_not_empty_and_an_empty_selection(clean, tmp_path) -> None:
    dlg = clean.dlg
    full = tmp_path / "full"
    full.mkdir()
    (full / "mine.txt").write_text("keep me")
    assert dlg.copy_selection(full) == 0
    assert dlg.notice.text() == strings.EXP_COPY_NOT_EMPTY
    assert [p.name for p in full.iterdir()] == ["mine.txt"]
    dlg.none_btn.click()
    assert dlg.copy_selection(tmp_path / "x") == 0
    assert dlg.notice.text() == strings.EXP_COPY_NONE and not (tmp_path / "x").exists()


def test_the_copy_button_asks_for_a_folder_through_the_hook(clean, tmp_path) -> None:
    dlg = clean.dlg
    dlg.ask_folder = lambda title: str(tmp_path / "chosen")
    dlg.set_all_checked(False)
    dlg.set_checked("system", "sys_mating", True)
    dlg.copy_btn.click()
    assert (tmp_path / "chosen" / "system" / "mating_matrix.csv").is_file()


# ---- failure, cancel, edits, open after -----------------------------------------------------------


def test_a_failed_independent_check_is_a_persistent_notice_and_writes_nothing(done, qtbot, tmp_path) -> None:  # fmt: skip
    ctl = flatsat_controller(tmp_path)
    report = VerifyReport()
    for n in range(9):
        report.error("out_wire", f"The wire list of W00{n} does not match the design")
    dlg = ExportDialog(ctl, themed(), worker_factory=fake_factory(done.res.built, report))
    qtbot.addWidget(dlg)
    dlg.show()
    failed = collect(dlg.failed)
    modal = QApplication.activeModalWidget()
    assert dlg.run() is None
    assert dlg.notice.isVisible() and dlg.notice.severity == "error"
    text = dlg.notice.text()
    assert "found 9 problem(s)" in text and "nothing was written" in text
    assert "The wire list of W000 does not match the design" in text
    assert "… and 3 more" in text  # six are listed, the rest counted
    assert len(failed) == 1
    assert not (outputs_of(ctl) / "manifest.json").exists()
    assert QApplication.activeModalWidget() is modal  # no pop-up appeared
    assert dlg.export_btn.isEnabled() and dlg.pages.currentIndex() == 0
    # the notice stays until the next export works
    dlg.worker_factory = fake_factory(done.res.built)
    assert dlg.run() is not None and not dlg.notice.isVisible()
    assert (outputs_of(ctl) / "manifest.json").is_file()


def test_a_write_error_is_a_notice_too(done, qtbot, tmp_path, monkeypatch) -> None:
    from harness_design_studio.core.errors import SaveError

    ctl = flatsat_controller(tmp_path)
    dlg = ExportDialog(ctl, themed(), worker_factory=fake_factory(done.res.built))
    qtbot.addWidget(dlg)

    def boom(*a, **k):
        raise SaveError("The outputs folder (or a folder in it) is a link, so nothing was written.")

    monkeypatch.setattr("harness_design_studio.gui.export_dialog.write_outputs", boom)
    assert dlg.run() is None
    assert "is a link" in dlg.notice.text() and dlg.notice.severity == "error"


def test_cancel_stops_the_export_and_writes_nothing(qtbot, tmp_path) -> None:
    ctl = flatsat_controller(tmp_path)
    dlg = ExportDialog(ctl, themed())
    qtbot.addWidget(dlg)
    dlg.show()
    cancelled = collect(dlg.cancelled)
    assert dlg.start() and dlg.running and dlg.pages.currentIndex() == 1
    assert not dlg.export_btn.isEnabled() and not dlg.tree.isEnabled()
    dlg.cancel_btn.click()
    qtbot.waitUntil(lambda: not dlg.running, timeout=30000)
    assert len(cancelled) == 1
    assert dlg.notice.text() == strings.EXPORT_CANCELLED
    assert not (outputs_of(ctl) / "manifest.json").exists()
    assert dlg.export_btn.isEnabled() and dlg.tree.isEnabled()


def test_closing_while_it_runs_cancels_it(qtbot, tmp_path) -> None:
    ctl = flatsat_controller(tmp_path)
    dlg = ExportDialog(ctl, themed())
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.start()
    dlg.reject()
    assert not dlg.running and not dlg.isVisible()
    assert not (outputs_of(ctl) / "manifest.json").exists()


def test_an_edit_during_the_export_drops_the_result(done, qtbot, tmp_path) -> None:
    ctl = flatsat_controller(tmp_path)
    dlg = ExportDialog(ctl, themed(), worker_factory=fake_factory(done.res.built))
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.start()
    unit = next(iter(ctl.project.units.values()))
    assert ctl.run("rename", [Put("units", evolve(unit, name="Renamed"))])
    qtbot.waitUntil(lambda: not dlg.running, timeout=10000)
    assert dlg.notice.text() == strings.EXP_NOTE_CHANGED
    assert not (outputs_of(ctl) / "manifest.json").exists()


def test_open_after_export_opens_the_folder_and_is_remembered(done, qtbot, tmp_path) -> None:
    ctl = flatsat_controller(tmp_path)
    store = settings(tmp_path)
    opened: list[QUrl] = []
    dlg = ExportDialog(
        ctl, themed(), settings=store, worker_factory=fake_factory(done.res.built),
        opener=recorder(opened),
    )  # fmt: skip
    qtbot.addWidget(dlg)
    assert not dlg.open_after.isChecked()
    assert dlg.run() is not None and opened == []  # not unless asked
    dlg.open_after.setChecked(True)
    assert dlg.run() is not None
    assert opened == [QUrl.fromLocalFile(str(ctl.outputs_folder()))]
    store.sync()
    again = ExportDialog(ctl, themed(), settings=QSettings(store.fileName(), QSettings.Format.IniFormat))  # fmt: skip
    qtbot.addWidget(again)
    assert again.open_after.isChecked()


# ---- keyboard and names ------------------------------------------------------------------------


def test_keyboard_only_journey(done, qtbot, tmp_path) -> None:
    ctl = flatsat_controller(tmp_path)
    opened: list[QUrl] = []
    dlg = ExportDialog(
        ctl,
        themed(),
        worker_factory=fake_factory(done.res.built),
        opener=recorder(opened),  # fmt: skip
    )
    qtbot.addWidget(dlg)
    dlg.resize(1100, 700)
    activate(dlg)
    # Tab walks the controls in reading order: tree, select all/none, open-after, close, export
    seen: list[str] = []
    dlg.tree.setFocus()
    for _ in range(8):
        w = QApplication.focusWidget()
        if w is not None:
            seen.append(w.objectName())
        QTest.keyClick(w or dlg, Qt.Key.Key_Tab)
    assert seen[0] == "export-tree"
    assert {"export-select-all", "export-select-none", "export-open-after", "export-close", "export-run"} <= set(seen)  # fmt: skip
    # Space on the tree toggles the tick of the current item
    dlg.tree.setFocus()
    dlg.tree.setCurrentIndex(dlg.model.index(0, 0))
    QTest.keyClick(dlg.tree, Qt.Key.Key_Space)
    assert dlg.model.item(0).checkState() == Qt.CheckState.Unchecked
    QTest.keyClick(dlg.tree, Qt.Key.Key_Space)
    assert dlg.model.item(0).checkState() == Qt.CheckState.Checked
    # Enter starts the export (the primary button is the default), Esc would close
    exported = collect(dlg.exported)
    dlg.export_btn.setFocus()
    QTest.keyClick(dlg.export_btn, Qt.Key.Key_Space)
    qtbot.waitUntil(lambda: bool(exported), timeout=20000)
    # then the list: arrows and Enter
    dlg.result_panel.table.setFocus()
    QTest.keyClick(dlg.result_panel.table, Qt.Key.Key_Down)
    QTest.keyClick(dlg.result_panel.table, Qt.Key.Key_Return)
    assert opened and opened[-1].isLocalFile()


def test_every_control_has_a_name_before_and_after_an_export(done, qtbot, tmp_path) -> None:
    ctl = flatsat_controller(tmp_path)
    dlg = ExportDialog(ctl, themed(), worker_factory=fake_factory(done.res.built))
    qtbot.addWidget(dlg)
    dlg.resize(1100, 700)
    dlg.show()
    assert unnamed(dlg) == []
    dlg.notice.show_notice("error", "x", details=["y"], button="Z")
    assert unnamed(dlg) == []
    assert dlg.run() is not None
    assert unnamed(dlg) == []
    for b in (dlg.export_btn, dlg.copy_btn, dlg.close_btn, dlg.all_btn, dlg.none_btn, dlg.cancel_btn, dlg.result_panel.reveal_btn, dlg.result_panel.open_btn, dlg.result_panel.folder_btn):  # fmt: skip
        assert b.toolTip(), b.objectName()
    assert isinstance(dlg, QDialog)


def test_no_edit_was_needed_on_the_model(done) -> None:
    """The dialog reads the project; the export never changes the design."""
    assert edit.clone_with(done.ctl.project, []) is not None
    assert not done.ctl.dirty
