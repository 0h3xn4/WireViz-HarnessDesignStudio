"""Regression tests for the third round of editor findings of the October audit (offscreen Qt):
project flows, import dialog, toasts, filters, disk changes, jobs, recovery journal, accessibility."""

import errno
import os
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from harness_design_studio.core import edit  # noqa: E402
from harness_design_studio.core.commands import Delete  # noqa: E402
from harness_design_studio.core.errors import TransactionError  # noqa: E402
from harness_design_studio.core.generate.engine import plan_generation  # noqa: E402
from harness_design_studio.core.io.saver import save_project  # noqa: E402
from harness_design_studio.core.issues import Issue  # noqa: E402
from harness_design_studio.core.recovery import journal_path  # noqa: E402
from harness_design_studio.core.samples import (  # noqa: E402
    mini3,
    new_project,
    sat15,
    sat15_full,
)
from harness_design_studio.core.templates import TEMPLATES  # noqa: E402
from harness_design_studio.core.vcs.diff import Diff  # noqa: E402
from harness_design_studio.gui import drc_process, strings  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.dialogs import (  # noqa: E402
    DiffDialog,
    HistoryDialog,
    ImportDialog,
    IssuesDialog,
)
from tests.gui_helpers import DialogScript, make_window  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    w = make_window(tmp_path / "ui")
    qtbot.addWidget(w)
    return w


def _saved(tmp_path: Path, name: str = "proj") -> Path:
    folder = tmp_path / name
    save_project(mini3(), folder)
    return folder


def _answer(log: list[str], choice: int, which: int = 0) -> Callable[[str, str, list[str]], int]:
    """An `ask_choice` that records the title (which=0) or body (which=1) and answers `choice`."""

    def ask(title: str, body: str, _buttons: list[str]) -> int:
        log.append((title, body)[which])
        return choice

    return ask


def _fail(*_a: object) -> int:
    raise AssertionError("no question was expected")


# ---- F1-9: a bad name is explained, not raised ---------------------------------------------------


@pytest.mark.parametrize("name", ["N" * 300, "bad\x07name"])
def test_new_project_with_an_invalid_name_says_so(win, tmp_path, name) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "new"
    win.ask_folder = lambda _t: str(folder)
    win.ask_text = lambda _t, _l, _d: name
    win.new_project_flow()
    assert not (folder / "project.json").exists()
    shown = win.toasts.messages[-1]
    assert shown and "validation error" not in shown and "Traceback" not in shown


def test_new_example_with_an_invalid_name_says_so(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "ex"
    win.ask_choice = lambda _t, _x, _b: 0
    win.ask_folder = lambda _t: str(folder)
    win.ask_text = lambda _t, _l, _d: "N" * 300
    assert TEMPLATES
    win.new_from_example_flow()
    assert not (folder / "project.json").exists()
    assert "validation error" not in win.toasts.messages[-1]


# ---- F1-11: the import dialog never keeps an old plan --------------------------------------------


def _two_computers(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl._install(new_project("t"), None, None)
    win.ctl.add_unit("computer")
    win.ctl.add_unit("computer")
    assert sorted(win.ctl.project.units) == ["OBC1", "OBC2"]


GOOD_CSV = "Interface,Type,From unit,To unit,Redundancy\nIF-900,rs422,OBC1,OBC2,nominal\n"


def test_import_ok_is_off_once_the_text_is_no_longer_readable(win) -> None:  # type: ignore[no-untyped-def]
    _two_computers(win)
    dlg = ImportDialog(win, win.ctl.project, win.theme, lambda: None)
    dlg.text.setPlainText(GOOD_CSV)
    assert dlg.plan.ok_count == 1 and dlg.ok.isEnabled()
    dlg.text.setPlainText(GOOD_CSV + "IF-901,rs422,OBC,RW1,nominal,1,5,extra,wide\n" + '"open\n')
    assert dlg.plan.ok_count == 0 and not dlg.ok.isEnabled()
    assert dlg.preview.rowCount() == 0 and dlg.summary.text().startswith("✕")


def test_import_reads_xlsx_through_the_sheet_reader_and_names_the_sheet(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "Links"
    for row in (
        ["Interface", "Type", "From unit", "To unit", "Redundancy"],
        ["IF-900", "rs422", "OBC1", "OBC2", "nominal"],
    ):
        sheet.append(row)
    path = tmp_path / "links.xlsx"
    book.save(path)
    _two_computers(win)
    dlg = ImportDialog(win, win.ctl.project, win.theme, lambda: str(path))
    dlg.open_file()
    assert "links.xlsx" in dlg.file_label.text() and "Links" in dlg.file_label.text()
    assert dlg.plan.ok_count == 1


# ---- F1-13: a repeated message with a new Undo ----------------------------------------------------


def test_a_repeated_message_with_a_new_undo_replaces_the_old_one(win) -> None:  # type: ignore[no-untyped-def]
    c = win.ctl
    zones = len(c.project.zones)
    c.run("zone 1", edit.ops_add_zone(c.project, "Za"), message="Done.")
    c.run("zone 2", edit.ops_add_zone(c.project, "Zb"), message="Done.")
    buttons = [b for b in win.toasts.findChildren(QPushButton, "toast-undo") if b.isVisible()]
    assert len(buttons) == 1
    buttons[0].click()
    assert len(c.project.zones) == zones + 1 and c.project.zones[-1] == "Za"


# ---- F1-14: the filter's value list follows generate and undo --------------------------------------


def test_bundle_filter_values_follow_generation_and_its_undo(win) -> None:  # type: ignore[no-untyped-def]
    c = win.ctl
    c._install(sat15(), None, None)
    win.filter_combo.setCurrentIndex(3)  # by bundle
    assert win.filter_value.count() == 0
    c.apply_generation(plan_generation(c.project))
    assert win.filter_value.count() == len(c.project.harnesses) > 0
    assert win.view.dscene.filter is not None
    c.undo()
    assert win.filter_value.count() == 0
    assert win.view.dscene.filter is None
    assert all(it.opacity() == 1 for it in win.view.dscene.link_items.values())


# ---- F1-16: the connect menu does not leak actions -------------------------------------------------


def _connect_actions(win) -> list[str]:  # type: ignore[no-untyped-def]
    return [a.objectName() for a in win.actions() if a.objectName().startswith("menu-connect-")]


def test_rebuilding_the_connect_menu_leaves_no_old_actions(win) -> None:  # type: ignore[no-untyped-def]
    c = win.ctl
    c._install(new_project("x"), None, None)
    for _ in range(3):
        c.run("remove type", [Delete("interface_types", "can")])
        c.undo()
    c.run("remove type", [Delete("interface_types", "can")])
    names = _connect_actions(win)
    assert "menu-connect-can" not in names
    assert len(names) == len(win.menu_connect.actions()) == len(c.project.interface_types)


def test_a_stale_connect_entry_does_nothing_harmful(win) -> None:  # type: ignore[no-untyped-def]
    c = win.ctl
    c._install(new_project("x"), None, None)
    entry = next(e for e in win.palette_entries() if e.label == "CAN")
    c.run("remove type", [Delete("interface_types", "can")])
    entry.run()
    assert c.tool == "select" and c.connect_type is None
    assert c.connect_hint() == ""


# ---- F1-17 / F1-18: disk changes -------------------------------------------------------------------


@pytest.mark.parametrize("how", ["deleted", "project_json_removed"])
def test_a_project_that_vanished_is_reported_not_raised(win, tmp_path, how) -> None:  # type: ignore[no-untyped-def]
    folder = _saved(tmp_path)
    assert win.open_project(folder)
    asked: list[str] = []
    win.ask_choice = _answer(asked, 0)  # Reload
    if how == "deleted":
        win.ctl.release()
        shutil.rmtree(folder)
    else:
        (folder / "project.json").unlink()
    win.check_disk()  # must not raise
    assert "reload" in win.toasts.messages[-1].lower()
    win.check_disk()  # and does not ask again about the same files
    assert len(asked) == 1
    assert win.ctl.project.meta.name  # the open project is still there


def test_keep_my_version_is_remembered_until_the_files_change_again(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = _saved(tmp_path)
    assert win.open_project(folder)
    asked: list[str] = []
    win.ask_choice = _answer(asked, 1)  # Keep my version
    target = folder / "logical" / "units" / "aocs.json"
    target.write_text(target.read_text() + " ")
    win.check_disk()
    win.check_disk()
    assert len(asked) == 1
    target.write_text(target.read_text() + " ")
    win.check_disk()
    assert len(asked) == 2


# ---- F1-19: a failing job shows its reason, not "cancelled" -----------------------------------------


def test_generation_that_fails_shows_the_reason(win, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("plan exploded")

    monkeypatch.setattr("harness_design_studio.gui.main_window.plan_generation", boom)
    win.ctl._install(sat15(), None, None)
    win.generate_flow()
    shown = win.toasts.messages[-1]
    assert "plan exploded" in shown and "cancel" not in shown.lower()


def test_export_that_fails_shows_the_reason(win, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("build exploded")

    folder = tmp_path / "full"
    save_project(sat15_full(), folder)
    assert win.open_project(folder)
    monkeypatch.setattr("harness_design_studio.gui.main_window.build_outputs", boom)
    win.export_flow()
    shown = win.toasts.messages[-1]
    assert "build exploded" in shown and "cancel" not in shown.lower()


# ---- F1-20: a plan made for an older state is refused -----------------------------------------------


def test_a_stale_generation_plan_is_not_applied(win) -> None:  # type: ignore[no-untyped-def]
    c = win.ctl
    c._install(sat15(), None, None)
    plan = plan_generation(c.project)
    iid = sorted(c.project.interfaces)[0]
    c.select("interface", iid)
    c.delete_selected()
    seen: list[str] = []
    c.message.connect(lambda t, _u: seen.append(t))
    assert c.apply_generation(plan) is False
    assert seen[-1] == strings.GEN_STALE and not c.project.harnesses


def test_an_edit_made_while_planning_stops_the_apply(win) -> None:  # type: ignore[no-untyped-def]
    c = win.ctl
    c._install(sat15(), None, None)
    real = win._compute_plan

    def plan_then_edit():  # type: ignore[no-untyped-def]
        plan = real()
        c.move_unit(sorted(c.project.units)[0], 777, 777)  # an edit during the run
        return plan

    win.compute_plan = plan_then_edit
    DialogScript(win)
    win.generate_flow()
    assert win.toasts.messages[-1] == strings.GEN_STALE and not c.project.harnesses


def test_the_plan_is_computed_on_a_private_copy(win, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    c = win.ctl
    c._install(sat15(), None, None)
    seen: list[object] = []
    real = plan_generation

    def spy(project, *a, **k):  # type: ignore[no-untyped-def]
        seen.append(project)
        return real(project, *a, **k)

    monkeypatch.setattr("harness_design_studio.gui.main_window.plan_generation", spy)
    DialogScript(win, accept=False)
    win.generate_flow()
    assert seen and seen[0] is not c.project


def test_an_export_built_before_an_edit_is_not_written(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "full"
    save_project(sat15_full(), folder)
    assert win.open_project(folder)
    real = win._compute_outputs

    def build_then_edit():  # type: ignore[no-untyped-def]
        result = real()
        win.ctl.move_unit(sorted(win.ctl.project.units)[0], 555, 555)
        return result

    win.compute_outputs = build_then_edit
    win.export_flow()
    assert win.toasts.messages[-1] == strings.CHANGES_DURING_JOB
    assert not (folder / "outputs").exists()


# ---- F1-21 / F1-22 / F1-25: opening ------------------------------------------------------------------


def test_a_project_on_read_only_media_opens_read_only(win, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    folder = _saved(tmp_path)
    real = os.open

    def deny(path, flags, *a, **k):  # type: ignore[no-untyped-def]
        if str(path).endswith(".takeover"):
            raise PermissionError(errno.EROFS, "Read-only file system")
        return real(path, flags, *a, **k)

    monkeypatch.setattr(os, "open", deny)
    win.ask_choice = _fail  # type: ignore[assignment]
    assert win.open_project(folder)
    assert win.ctl.read_only and win.ctl.root == folder
    assert "read-only" in win.toasts.messages[-1].lower()


def test_opening_a_folder_that_is_no_project_leaves_nothing_behind(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "plain"
    folder.mkdir()
    assert win.open_project(folder) is False
    assert list(folder.iterdir()) == []
    assert ".harness" not in win.toasts.messages[-1]


def test_opening_the_folder_that_is_open_keeps_its_lock(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = _saved(tmp_path)
    assert win.open_project(folder)
    win.ask_choice = _fail  # type: ignore[assignment]
    assert win.open_project(folder)
    assert not win.ctl.read_only and (folder / ".harness.lock").exists()
    assert win.toasts.messages[-1] == strings.ALREADY_OPEN
    win.ask_folder = lambda _t: str(folder)
    win.open_flow()
    assert not win.ctl.read_only and (folder / ".harness.lock").exists()


# ---- F1-23 / F1-24 / A-5: status and journal ----------------------------------------------------------


def test_status_does_not_promise_an_autosave_that_cannot_happen(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    win.ctl.add_unit("sensor")  # the sample has no folder
    assert win.status_saved.text() == strings.UNSAVED_NO_JOURNAL
    folder = _saved(tmp_path)
    assert win.open_project(folder)
    win.ctl.add_unit("sensor")
    assert win.status_saved.text() == strings.UNSAVED


def test_discarding_changes_on_close_removes_the_journal(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = _saved(tmp_path)
    assert win.open_project(folder)
    win.ctl.add_unit("sensor")
    win.ctl.write_journal_now()
    assert journal_path(folder).exists()
    win.ask_choice = lambda _t, _x, _b: 1  # Discard
    win.close()
    assert not journal_path(folder).exists()


def _journalled(win, qtbot, tmp_path: Path, *, pulled: bool) -> str:  # type: ignore[no-untyped-def]
    """Leave a journal behind, optionally change the files like a Git pull, and return the text
    of the question the next window asks when it opens the project."""
    folder = _saved(tmp_path)
    first = make_window(tmp_path / "ui1")
    qtbot.addWidget(first)
    assert first.open_project(folder)
    first.ctl.add_unit("sensor")
    first.ctl.write_journal_now()
    first.ctl.release()
    if pulled:
        target = folder / "logical" / "units" / "aocs.json"
        target.write_text(target.read_text() + " ")
    asked: list[str] = []
    win.ask_choice = _answer(asked, 1, which=1)
    assert win.open_project(folder)
    return asked[0]


def test_a_journal_older_than_the_files_warns_before_restoring(win, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert _journalled(win, qtbot, tmp_path, pulled=True) == strings.RESTORE_BODY_CHANGED


def test_a_journal_of_the_current_files_asks_the_plain_question(win, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert _journalled(win, qtbot, tmp_path, pulled=False) == strings.RESTORE_BODY


# ---- undo and redo -----------------------------------------------------------------------------------


def test_a_redo_that_is_refused_says_why(win, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    c = win.ctl
    c.add_unit("sensor")
    c.undo()
    seen: list[str] = []
    c.message.connect(lambda t, _u: seen.append(t))

    def refuse() -> str:
        raise TransactionError("This harness is released.", ["Make a new revision first."])

    monkeypatch.setattr(c.history, "redo", refuse)
    c.redo()
    assert seen == ["This harness is released. Make a new revision first."]


def test_a_release_that_was_saved_cannot_be_undone_and_the_menu_says_why(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.core.io.loader import load_project

    folder = tmp_path / "full"
    save_project(sat15_full(), folder)
    assert win.open_project(folder)
    win.ctl.today = lambda: "2026-03-01"
    hid = next(
        h.id
        for h in sorted(win.ctl.project.harnesses.values(), key=lambda x: x.id)
        if all(w.gauge_awg and w.length_m for w in h.wires)
    )
    win.tabs.setCurrentWidget(win.harness_panel)
    win.harness_panel.export_btn.click()
    win.harness_panel.select_harness(hid)

    def fill(d) -> None:  # type: ignore[no-untyped-def]
        d.by.setText("Ada")
        d.checker.setText("Bob")
        d.comment.setPlainText("First release for the CDR")
        d.placeholder_reason.setText("Test project: values are placeholders")
        d.parts_reason.setText("Test project: example parts")

    DialogScript(win, fill)
    win.change_flow("release", hid)
    assert win.ctl.project.baselines, win.toasts.messages[-3:]
    assert win.save_flow()
    win.ctl.undo()
    assert win.ctl.project.baselines
    assert not win.act_undo.isEnabled()
    assert win.act_undo.toolTip() == win.ctl.history.undo_blocked
    assert load_project(folder).project.baselines


# ---- C-14: a stuck check never holds up opening or closing --------------------------------------------

_HANG = (
    "import sys\n"
    "sys.stdin.buffer.read()\n"  # reads the project, never answers
)


def _stuck_controller(monkeypatch) -> EditorController:  # type: ignore[no-untyped-def]
    monkeypatch.delenv(drc_process.DISABLE_ENV, raising=False)
    monkeypatch.setattr(drc_process, "worker_command", lambda: [sys.executable, "-c", _HANG])
    monkeypatch.setattr(drc_process, "CHECK_TIMEOUT_S", 40.0)
    drc_process._shared.close()
    c = EditorController()
    c._install(sat15(), None, None)
    c._drc_timer.stop()
    c._start_drc()
    deadline = time.monotonic() + 15
    while not drc_process._shared.alive and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    time.sleep(0.3)
    return c


def test_release_does_not_wait_for_a_stuck_check(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    c = _stuck_controller(monkeypatch)
    try:
        start = time.monotonic()
        c.release()
        assert time.monotonic() - start < 15
    finally:
        drc_process._shared.close()


def test_opening_another_project_does_not_wait_for_a_stuck_check(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    c = _stuck_controller(monkeypatch)
    try:
        start = time.monotonic()
        c._install(mini3(), None, None)
        assert time.monotonic() - start < 15
        c.release()
    finally:
        drc_process._shared.close()


# ---- F1-26: accessible names ---------------------------------------------------------------------------


def test_lists_in_dialogs_and_the_bottom_tabs_have_accessible_names(win) -> None:  # type: ignore[no-untyped-def]
    issues = IssuesDialog(win, [Issue("error", "x", "Something is wrong")], False)
    history = HistoryDialog(win, "Log", [["h"]])
    diff = DiffDialog(win, "Changes", Diff(), ["A"], "A")
    for widget in (issues.list, history.list, diff.list, diff.baseline, win.tabs):
        assert widget.accessibleName().strip(), widget.objectName()


# ---- F1-27: the warning line is typed, not matched on its English text ------------------------------------


def test_the_no_free_connector_hint_is_a_warning_whatever_its_wording(win, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    c = win.ctl
    c._install(new_project("x"), None, None)
    uid = c.add_unit("computer")
    assert uid
    monkeypatch.setattr(strings, "CONNECT_NONE_FREE", "Nobody can take {}.")
    c.begin_connect("can")
    c.pick(uid)
    assert c.connect_hint() == "Nobody can take CAN."
    assert win.hint.property("error") is True
    c.end_connect()
    assert win.hint.property("error") is False


# ---- F1-28: tests that were missing --------------------------------------------------------------------------


def test_moving_a_unit_redraws_the_links_that_follow_it(win) -> None:  # type: ignore[no-untyped-def]
    c = win.ctl
    c._install(mini3(), None, None)
    seen: list[object] = []
    c.changed.connect(seen.append)
    unit = "OBC"
    c.move_unit(unit, 500, 500)
    delta = seen[-1]
    attached = {
        i.id for i in c.project.interfaces.values() if unit in [e.unit_id for e in i.endpoints]
    }
    assert attached
    assert delta.units == {unit}  # type: ignore[attr-defined]
    assert delta.interfaces == attached and delta.followers == attached  # type: ignore[attr-defined]
