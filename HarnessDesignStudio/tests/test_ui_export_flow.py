# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined"
"""Workshop feedback M1: export is clear and one step. A project with no folder first asks where to
save it and goes straight on to the export dialog; every blocker says what it is, inline; the
Harness tab shows its reason beside the Export button."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core import recovery, templates  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.model import QuarantinedItem  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.export_dialog import ExportDialog  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.next_step import NextInputs, next_step  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402


@pytest.fixture
def unsaved(qtbot, tmp_path: Path):
    """The flatsat in memory only: harnesses, no folder (as the sample or a never saved project)."""
    folder = tmp_path / "flatsat"
    templates.create_project(folder, "flatsat")
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(load_project(folder).project, None, None)
    win.set_area("model")
    QApplication.processEvents()
    assert win.ctl.outputs_folder() is None and win.ctl.project.harnesses
    return win


def chooser(win: MainWindow, target: Path | None, asked: list[str]):
    def ask(title: str) -> str | None:
        asked.append(title)
        return None if target is None else str(target)

    win.ask_folder = ask  # type: ignore[assignment]


def opens_dialog(win: MainWindow) -> list[ExportDialog]:
    seen: list[ExportDialog] = []

    def run(dlg) -> int:
        assert isinstance(dlg, ExportDialog)
        seen.append(dlg)
        return 0

    win.run_dialog = run  # type: ignore[assignment]
    return seen


def press(win: MainWindow, way: str) -> None:
    if way == "menu":
        win.act_export.trigger()
    elif way == "topbar":
        win.topbar.export_btn.click()
    elif way == "harness":
        win.go_to("harness")
        win.harness_view.action_buttons["export"].click()
    elif way == "next":
        win.next_page._actions["build_sheets"]()
    else:
        win.export_dialog_flow()


WAYS = ["menu", "topbar", "harness", "next", "flow"]


# ---- no folder: save first, then straight on --------------------------------------------------


@pytest.mark.parametrize("way", WAYS)
def test_export_without_a_folder_saves_first_and_goes_on(unsaved, tmp_path, way: str) -> None:
    asked: list[str] = []
    target = tmp_path / "saved"
    chooser(unsaved, target, asked)
    seen = opens_dialog(unsaved)
    press(unsaved, way)
    assert asked == [strings.EXPORT_SAVE_AS_FOLDER]
    assert unsaved.ctl.root == target and (target / "project.json").is_file()
    assert len(seen) == 1
    dlg = seen[0]
    assert dlg.folder.text() == str(target / "outputs")
    assert dlg.blocker() is None and dlg.export_btn.isEnabled()  # (nothing in the way any more)


def test_the_export_really_runs_after_the_save(unsaved, tmp_path, qtbot) -> None:
    asked: list[str] = []
    chooser(unsaved, tmp_path / "saved", asked)
    unsaved.run_dialog = lambda dlg: (dlg.run(), 1)[1]  # type: ignore[assignment]
    unsaved.act_export.trigger()
    qtbot.waitUntil(lambda: not unsaved.ctl.drc_busy(), timeout=20000)
    assert (tmp_path / "saved" / "outputs" / "manifest.json").is_file() or list(
        (tmp_path / "saved" / "outputs").rglob("*.csv")
    )
    assert any("files written" in m for m in unsaved.toasts.messages)


def test_a_cancelled_chooser_stops_there(unsaved, tmp_path) -> None:
    asked: list[str] = []
    chooser(unsaved, None, asked)
    seen = opens_dialog(unsaved)
    unsaved.act_export.trigger()
    assert asked == [strings.EXPORT_SAVE_AS_FOLDER] and not seen
    assert unsaved.ctl.root is None


def test_a_saved_project_does_not_ask_again(unsaved, tmp_path) -> None:
    asked: list[str] = []
    chooser(unsaved, tmp_path / "saved", asked)
    seen = opens_dialog(unsaved)
    unsaved.act_export.trigger()
    unsaved.act_export.trigger()
    assert len(asked) == 1 and len(seen) == 2


def test_a_chooser_that_cannot_save_says_so_and_stops(unsaved, tmp_path) -> None:
    blocked = tmp_path / "file"
    blocked.write_text("not a folder")
    asked: list[str] = []
    chooser(unsaved, blocked, asked)
    seen = opens_dialog(unsaved)
    unsaved.act_export.trigger()
    assert asked and not seen and unsaved.ctl.root is None
    assert unsaved.toasts.messages  # (the person is told, inline as a toast, never a message box)


# ---- each blocker says what it is, inline -----------------------------------------------------


def test_read_only_asks_for_no_folder_and_says_why(unsaved, tmp_path) -> None:
    unsaved.ctl.project.read_only = True
    asked: list[str] = []
    chooser(unsaved, tmp_path / "x", asked)
    seen = opens_dialog(unsaved)
    unsaved.act_export.trigger()
    assert not asked and len(seen) == 1
    assert seen[0].notice.text() == strings.EXPORT_READ_ONLY and not seen[0].export_btn.isEnabled()


def test_a_damaged_project_names_the_files_and_says_what_to_do(unsaved, tmp_path) -> None:
    unsaved.ctl.project.quarantine_files = {f"logical/units/u{i}.json": b"{" for i in range(7)} | {
        "harnesses/W001/harness.json": b"["
    }
    asked: list[str] = []
    chooser(unsaved, tmp_path / "x", asked)
    seen = opens_dialog(unsaved)
    unsaved.act_export.trigger()
    assert not asked
    dlg = seen[0]
    text = dlg.notice.text()
    assert text.startswith(strings.EXPORT_DAMAGED) and "Show project problems" in text
    names = recovery.damaged_files(unsaved.ctl.project)
    assert len(names) == 8
    for name in names[:5]:
        assert name in text
    assert names[5] not in text and strings.EXP_DAMAGED_MORE.format(3) in text
    assert not dlg.export_btn.isEnabled()


def test_a_few_damaged_files_are_all_listed_without_a_more_line(unsaved) -> None:
    unsaved.ctl.project.quarantine.append(
        QuarantinedItem("logical/units/a.json", "unit", "bad", {})
    )
    unsaved.ctl.project.quarantine_files = {"b.json": b"{"}
    seen = opens_dialog(unsaved)
    unsaved.export_dialog_flow()
    text = seen[0].notice.text()
    assert "logical/units/a.json" in text and "b.json" in text and "more" not in text.split("\n", 1)[1]  # fmt: skip


def test_a_project_without_a_folder_offers_save_project_in_the_dialog(qtbot, tmp_path) -> None:
    from harness_design_studio.gui.controller import EditorController
    from harness_design_studio.gui.theme import ThemeManager

    ctl = EditorController()
    dlg = ExportDialog(ctl, ThemeManager(), ask_folder=lambda t: str(tmp_path / "s"))
    qtbot.addWidget(dlg)
    dlg.show()
    assert "no folder yet" in dlg.notice.text() and dlg.notice.action.text() == strings.EXP_SAVE_PROJECT  # fmt: skip
    assert not dlg.export_btn.isEnabled()


def test_a_project_without_a_harness_says_so(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl.new_project(tmp_path / "blank", "Blank")
    assert win.ctl.outputs_folder() is not None and not win.ctl.project.harnesses
    seen = opens_dialog(win)
    win.act_export.trigger()
    assert seen[0].notice.text() == strings.EXPORT_NO_HARNESSES and not seen[0].export_btn.isEnabled()  # fmt: skip


def test_no_harness_and_no_folder_asks_for_no_folder(qtbot, tmp_path) -> None:
    from harness_design_studio.core.samples import new_project

    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(new_project(), None, None)
    asked: list[str] = []
    chooser(win, tmp_path / "x", asked)
    seen = opens_dialog(win)
    win.act_export.trigger()
    assert not asked and len(seen) == 1  # (nothing to export: saving would not help)


# ---- the Harness tab --------------------------------------------------------------------------


def test_the_harness_tab_button_is_not_greyed_for_no_folder_and_says_what_it_does(unsaved) -> None:
    unsaved.go_to("harness")
    view = unsaved.harness_view
    view.refresh()
    b = view.action_buttons["export"]
    assert b.isEnabled()
    assert view.export_reason.isVisibleTo(view) and view.export_reason.text() == strings.HV_EXPORT_SAVES_FIRST  # fmt: skip
    assert strings.HV_EXPORT_SAVES_FIRST_TIP in b.toolTip()
    assert view.export_reason.accessibleName()


def test_the_harness_tab_button_shows_its_reason_beside_it_when_read_only(unsaved) -> None:
    unsaved.ctl.project.read_only = True
    unsaved.go_to("harness")
    view = unsaved.harness_view
    view.refresh()
    b = view.action_buttons["export"]
    assert not b.isEnabled()
    assert view.export_reason.isVisibleTo(view) and view.export_reason.text() == strings.HV_EXPORT_READ_ONLY  # fmt: skip
    assert strings.HV_EXPORT_READ_ONLY in b.toolTip() or strings.WHY_READ_ONLY in b.toolTip()
    layout = view.action_bar
    assert layout.indexOf(view.export_reason) == layout.indexOf(b) + 1  # right beside the button


def test_the_harness_tab_has_no_reason_when_nothing_is_in_the_way(unsaved, tmp_path) -> None:
    unsaved.ctl.save_as(tmp_path / "saved")
    unsaved.go_to("harness")
    view = unsaved.harness_view
    view.refresh()
    assert view.action_buttons["export"].isEnabled() and not view.export_reason.isVisibleTo(view)


# ---- the Next step note -----------------------------------------------------------------------


def test_the_next_step_note_says_what_really_happens() -> None:
    assert "asks where to save the project" in strings.NEXT_SHEETS_FOLDER
    assert "choose a folder for the files" not in strings.NEXT_SHEETS_FOLDER
    f = NextInputs(
        units=2, interfaces=1, harnesses=1, generation="current", checked=True, outputs="none",
        has_folder=False,
    )  # fmt: skip
    step = next_step(f)
    assert step.key == "build_sheets" and step.note == strings.NEXT_SHEETS_FOLDER
