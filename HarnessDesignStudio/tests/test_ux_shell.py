# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SH-1, SH-2, SH-9 to SH-14, SH-18, SH-24, SH-26 (ux/shell): the app shell. A top bar with the status
chip, persistent banners, the status bar, saved layout, the command palette, shortcuts, F6, main tabs
with slots for views that are written elsewhere, and the 1280 x 720 / 4K layouts. Offscreen, on the
flatsat example in a real window."""

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QDialog,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
)

from harness_design_studio import __version__  # noqa: E402
from harness_design_studio.core import drc, templates  # noqa: E402
from harness_design_studio.core.commands import History, Put  # noqa: E402
from harness_design_studio.core.model import Unit  # noqa: E402
from harness_design_studio.core.samples import mini3  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.command_palette import (  # noqa: E402
    CommandPalette,
    PaletteEntry,
    rank_entries,
)
from harness_design_studio.gui.devices_view import DevicesView  # noqa: E402
from harness_design_studio.gui.export_dialog import ExportDialog  # noqa: E402
from harness_design_studio.gui.harness_view import HarnessView  # noqa: E402
from harness_design_studio.gui.import_wizard import ImportWizard  # noqa: E402
from harness_design_studio.gui.inspector import Inspector  # noqa: E402
from harness_design_studio.gui.lists_panel import ListsPanel  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.new_project_dialog import NewProjectDialog  # noqa: E402
from harness_design_studio.gui.project_tree import ProjectTree  # noqa: E402
from harness_design_studio.gui.shell import (  # noqa: E402
    BannerStack,
    ElidedLabel,
    EmptyStateWidget,
    SlotTabs,
    auto_scale,
    refusal_harness,
)
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from harness_design_studio.gui.topbar import ShellStatus, chip_for  # noqa: E402
from tests.gui_helpers import DialogScript, make_window  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402


def _flatsat(tmp_path: Path) -> Path:
    folder = tmp_path / "flatsat"
    templates.create_project(folder, "flatsat")
    return folder


@pytest.fixture
def flat(qtbot, tmp_path):
    """The shipped flatsat example in a real window, its first check finished."""
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._drc_timer.setInterval(30)
    win.ctl.open_path(_flatsat(tmp_path))
    qtbot.waitUntil(lambda: win.ctl.drc_current, timeout=20000)
    win._update_hash()
    yield win
    win.ctl.wait_drc()


def quiet(win: MainWindow, qtbot) -> None:
    """Wait until no check is running or about to run, then read the status again."""
    qtbot.waitUntil(lambda: not win.ctl.drc_busy(), timeout=20000)
    win._update_hash()


def capture(seen: list[QDialog], answer: int = 0) -> Callable[[QDialog], int]:
    """A `run_dialog` that remembers the dialog and answers without showing it."""

    def run(dlg: QDialog) -> int:
        seen.append(dlg)
        return answer

    return run


def edit_something(win: MainWindow) -> None:
    """A change that matters to the harness plans (a unit gets another name)."""
    assert win.ctl.update_unit("OBC1", name="Main computer")
    win._update_hash()


# ---- pure rules --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "state", "text"),
    [
        (ShellStatus(generation="none"), "draft", strings.CHIP_NOT_GENERATED),
        (ShellStatus(generation="stale", has_harnesses=True), "stale", strings.CHIP_PLANS_STALE),
        (
            ShellStatus(generation="current", outputs="stale", has_harnesses=True),
            "stale",
            strings.CHIP_OUTPUTS_STALE,
        ),
        (
            ShellStatus(generation="current", outputs="modified", has_harnesses=True),
            "stale",
            strings.CHIP_OUTPUTS_CHANGED,
        ),
        (
            ShellStatus(generation="current", outputs="current", has_harnesses=True),
            "pass",
            strings.CHIP_UP_TO_DATE,
        ),
        (
            ShellStatus(generation="current", outputs="none", has_harnesses=True),
            "pass",
            strings.CHIP_PLANS_CURRENT,
        ),
        (
            ShellStatus(generation="current", outputs="current", has_harnesses=True, checking=True),
            "info",
            strings.CHIP_CHECKING,
        ),
        (
            ShellStatus(generation="stale", has_harnesses=True, checking=True),
            "stale",
            strings.CHIP_PLANS_STALE,
        ),  # out of date outranks a running check
        (ShellStatus(generation="stale", running="generate"), "info", strings.CHIP_GENERATING),
        (ShellStatus(generation="current", running="export"), "info", strings.CHIP_EXPORTING),
    ],
)
def test_the_chip_rule(status, state, text) -> None:
    assert chip_for(status)[:2] == (state, text)


def test_a_refusal_names_the_released_harness_to_revise() -> None:
    text = (
        "This change was blocked because it touches released items. "
        "Unit PDU2 is used by W001, which is released. W001 is released (revision A); "
        "start a new revision to change it."
    )
    assert refusal_harness(text) == "W001"
    cfg = "Configuration 'derating' is used by the checks of the released harness(es) W003, W004."
    assert refusal_harness(cfg) == "W003"
    assert refusal_harness("This project is read-only.") is None


def test_the_ui_scale_follows_the_screen_unless_the_system_already_scaled() -> None:
    assert auto_scale(2160) == 200 and auto_scale(1800) == 150 and auto_scale(1440) == 125
    assert auto_scale(1080) == 100 and auto_scale(720) == 100
    assert auto_scale(2160, 2.0) == 100  # the system already doubled everything


def test_history_names_the_step_a_redo_would_run() -> None:
    h = History(mini3())
    h.execute("a", [Put("units", Unit(id="A1", name="n", subsystem="s"))])
    assert h.next_redo_label is None
    h.undo()
    assert h.next_redo_label == "a"


# ---- the palette ranks and never cuts ----------------------------------------------------------


def test_palette_ranks_prefix_first_and_has_no_cap() -> None:
    entries = [PaletteEntry(f"Go to unit U{i}", lambda: None) for i in range(60)]
    entries.insert(10, PaletteEntry("Regenerate everything", lambda: None))
    entries.append(PaletteEntry("Generate harnesses", lambda: None))
    ranked = [e.label for e in rank_entries(entries, "gene")]
    assert ranked[0] == "Generate harnesses"  # a label that starts with the text comes first
    assert ranked[1] == "Regenerate everything"
    assert len(rank_entries(entries, "")) == 62  # nothing is cut off at 14
    assert len(rank_entries(entries, "go to unit")) == 60


def test_palette_finds_every_command(flat) -> None:
    labels = [e.label for e in flat.palette_entries()]
    for needle in (
        "Generate harnesses",
        "Run checks",
        "Export…",
        "Release harness…",
        "Start new revision…",
        "Reset layout",
        "Go to Diagram",
        "Go to Checks",
        "Go to Releases",
        "Import approved parts…",
        "Import segment lengths…",
        "Import KiCad netlist…",
        "Engineering values…",
        "New interface…",
        "Go to harness W001",
    ):
        assert any(label.startswith(needle) for label in labels), needle
    dlg = CommandPalette(flat, flat.palette_entries())
    dlg.input.setText("generate")
    assert dlg.shown_labels()[0] == "Generate harnesses"
    dlg.input.setText("")
    assert len(dlg.shown_labels()) > 14  # no cap
    dlg.input.setText("zzzzqq")
    assert dlg.shown_labels() == []  # and a plain sentence when nothing matches
    dlg.deleteLater()


def test_palette_runs_a_command_and_the_shortcut_is_shown(flat) -> None:
    entries = {e.label: e for e in flat.palette_entries()}
    assert entries["Generate harnesses"].hint == "Ctrl+G"
    assert entries["Export…"].hint == "Ctrl+E"
    called: list[str] = []
    flat.act_reset_layout.triggered.connect(lambda *_: called.append("reset"))
    entries["Reset layout"].run()
    assert called == ["reset"]


# ---- top bar: the chip follows the design, keyboard only ---------------------------------------


def test_the_top_bar_shows_the_project_the_hash_and_the_state(flat) -> None:
    bar = flat.topbar
    assert bar.name_label.text() == flat.ctl.project.meta.name
    assert len(bar.hash_label.text()) == 8 and bar.hash_label.text() == flat.status_hash.text()
    assert bar.hash_label.property("mono") is True
    assert bar.generate_btn.property("primary") is True
    assert not bar.check_btn.property("primary") and not bar.export_btn.property("primary")
    assert bar.chip_text() == strings.CHIP_PLANS_CURRENT  # flatsat ships generated, not exported
    assert bar.dirty_label.text() == strings.TB_CLEAN


def test_the_top_bar_folds_parts_away_instead_of_widening_the_window(qtbot, flat) -> None:
    from harness_design_studio.gui.topbar import TopBar

    bar = TopBar(flat.theme)
    qtbot.addWidget(bar)
    bar.apply(
        ShellStatus(
            name="A rather long project name for a narrow window",
            model_hash="1a2b3c4d",
            dirty=True,
            generation="stale",
            has_harnesses=True,
        )
    )
    bar.show()
    bar.resize(1000, bar.height())
    assert bar.level() == 0 and "Unsaved changes" in bar.dirty_label.text()
    bar.resize(300, bar.height())
    assert bar.level() == 3  # the smallest: a dirty dot, no hash, Check and Export as icons
    assert bar.dirty_label.text() == "●" and bar.hash_label.isHidden()
    assert bar.check_btn.text() == "" and bar.check_btn.accessibleName() == strings.TB_CHECK
    assert bar.check_btn.toolTip() and bar.export_btn.toolTip()  # still named on hover
    assert bar.generate_btn.text() == strings.TB_GENERATE  # Generate keeps its word
    bar.resize(1000, bar.height())
    assert bar.level() == 0 and not bar.hash_label.isHidden()  # and it all comes back
    # the window itself is never made wider by what the bar says (it was 1150 px before the shell)
    edit_something(flat)
    flat.go_to("checks")  # with the results of the check loaded in the Checks tab
    size = flat.minimumSizeHint()
    assert size.width() <= 1160 + 72 and size.height() <= 520  # (the navigation rail adds 72 px)


def test_only_generate_is_primary_and_the_toggles_are_neutral(flat) -> None:
    primary = [
        b.objectName() or b.text()
        for b in flat.findChildren(QPushButton)
        if b.property("primary") and b.isVisibleTo(flat)
    ]
    assert primary == ["generate"]
    for toggle in (flat.mode_guided, flat.mode_expert, flat.tool_select, flat.tool_connect):
        assert toggle.property("toggle") is True and toggle.styleSheet() == ""
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    css = app.styleSheet()  # a rule of the theme, not a style in a widget
    assert 'QToolButton[toggle="true"]:checked' in css


def test_the_chip_goes_stale_after_an_edit_and_the_banner_generates_again(flat, qtbot) -> None:
    assert not flat.alerts.is_showing("stale")
    edit_something(flat)
    assert flat.topbar.chip_text() == strings.CHIP_PLANS_STALE
    assert flat.topbar.chip.state() == "stale"
    assert flat.topbar.dirty_label.property("dirty") is True
    banner = flat.alerts.banner("stale")
    assert banner is not None and flat.alerts.is_showing("stale")
    assert strings.BN_PLANS_STALE in banner.text()
    assert banner.action_texts() == [strings.BN_GENERATE]
    DialogScript(flat, accept=True)
    banner.buttons[0].click()  # the banner's own Generate button
    quiet(flat, qtbot)
    assert flat.ctl.generation_status() == "current"
    assert flat.topbar.chip_text() == strings.CHIP_PLANS_CURRENT
    assert not flat.alerts.is_showing("stale")


def test_the_banner_can_be_dismissed_until_the_design_changes_again(flat) -> None:
    edit_something(flat)
    banner = flat.alerts.banner("stale")
    assert banner is not None
    banner.dismiss.click()
    assert not flat.alerts.is_showing("stale")
    assert flat.topbar.chip_text() == strings.CHIP_PLANS_STALE  # the chip never hides
    flat.ctl.update_unit("OBC1", name="Main computer 2")
    flat._update_hash()
    assert flat.alerts.is_showing("stale")


def test_export_opens_from_the_top_bar_and_lists_the_files(flat, qtbot) -> None:
    seen: list[QDialog] = []

    def run(dlg: QDialog) -> int:
        seen.append(dlg)
        assert isinstance(dlg, ExportDialog)
        result = dlg.run()
        assert result is not None and result.count > 20
        paths = [f.rel for f in result.files]
        assert any(p.endswith(".svg") for p in paths) and any("wire" in p for p in paths)
        return int(QDialog.DialogCode.Accepted)

    flat.run_dialog = run
    flat.topbar.export_btn.click()
    assert len(seen) == 1
    quiet(flat, qtbot)
    assert flat.topbar.chip_text() == strings.CHIP_UP_TO_DATE
    assert any("files written" in m for m in flat.toasts.messages)
    edit_something(flat)  # and the exported files go stale with the design
    assert flat.topbar.chip_text() == strings.CHIP_PLANS_STALE


def test_outputs_stale_chip_and_banner_have_an_export_button(flat, qtbot) -> None:
    flat.run_dialog = lambda dlg: (dlg.run(), 1)[1]
    flat.act_export.trigger()
    quiet(flat, qtbot)
    assert flat.topbar.chip_text() == strings.CHIP_UP_TO_DATE
    assert not flat.alerts.is_showing("stale")
    flat.ctl.outputs_state = lambda: "stale"  # type: ignore[method-assign]
    flat._outputs_epoch += 1  # (what an edit that leaves the plans alone would make it read)
    flat._update_hash()
    assert flat.topbar.chip_text() == strings.CHIP_OUTPUTS_STALE
    banner = flat.alerts.banner("stale")
    assert banner is not None and banner.action_texts() == [strings.BN_EXPORT]
    assert strings.BN_OUTPUTS_STALE in banner.text()


def test_top_bar_works_from_the_keyboard(flat, qtbot) -> None:
    flat.show()
    flat.activateWindow()
    bar = flat.topbar
    for button in (bar.generate_btn, bar.check_btn, bar.export_btn):
        assert button.focusPolicy() & Qt.FocusPolicy.TabFocus
        assert button.accessibleName() and button.toolTip()
    order: list[QWidget] = []
    w: QWidget | None = bar.generate_btn
    for _ in range(40):
        w = w.nextInFocusChain() if w is not None else None
        if w in (bar.check_btn, bar.export_btn) and w is not None:
            order.append(w)
        if len(order) == 2:
            break
    assert order == [bar.check_btn, bar.export_btn]  # Tab goes Generate, Check, Export
    asked: list[str] = []
    flat.ctl.check_now = lambda: asked.append("check")  # type: ignore[method-assign]
    bar.check_btn.setFocus()
    QTest.keyClick(bar.check_btn, Qt.Key.Key_Space)  # Space presses the focused button
    assert asked == ["check"]
    seen: list[QDialog] = []
    flat.run_dialog = capture(seen)
    bar.export_btn.setFocus()
    QTest.keyClick(bar.export_btn, Qt.Key.Key_Space)
    assert len(seen) == 1 and isinstance(seen[0], ExportDialog)


def test_shortcuts_run_generate_check_and_export(flat) -> None:
    for act, key in (
        (flat.act_generate, "Ctrl+G"),
        (flat.act_export, "Ctrl+E"),
        (flat.act_check, "F5"),
        (flat.act_new_interface, "Ctrl+I"),
        (flat.act_next_pane, "F6"),
        (flat.act_prev_pane, "Shift+F6"),
        (flat.go_actions["diagram"], "Ctrl+1"),
        (flat.go_actions["checks"], "Ctrl+4"),
        (flat.go_actions["releases"], "Ctrl+5"),
        (flat.go_actions["devices"], "Ctrl+6"),
    ):
        assert act.shortcut().toString() == key
        assert key in act.toolTip() or act.toolTip() == "", (act.text(), act.toolTip())
    assert "Ctrl+G" in flat.topbar.generate_btn.toolTip()
    assert "Ctrl+E" in flat.topbar.export_btn.toolTip() and "F5" in flat.topbar.check_btn.toolTip()


def _menu_actions(flat: MainWindow) -> set[QAction]:
    found: set[QAction] = set()

    def walk(actions: list[QAction]) -> None:
        for a in actions:
            found.add(a)
            menu = a.menu()
            if isinstance(menu, QMenu):
                walk(menu.actions())

    walk(flat.menuBar().actions())
    return found


def test_every_shortcut_is_in_a_menu_and_the_connect_tool_is_in_edit(flat) -> None:
    in_menus = _menu_actions(flat)
    assert flat.act_connect_tool in in_menus
    missing = [
        a.text()
        for a in flat.actions()
        if not a.shortcut().isEmpty() and a.text().strip() and a not in in_menus
    ]
    assert missing == []


def test_tooltips_say_what_the_control_does_and_its_key(flat) -> None:
    for act in (flat.act_generate, flat.act_export, flat.act_check):
        assert f"({act.shortcut().toString()})" in act.toolTip(), act.text()
    assert "(Ctrl+Z)" in flat.act_undo.toolTip()
    for button in flat.findChildren(QToolButton):
        if button.property("iconOnly") and button.isVisibleTo(flat):
            assert button.toolTip(), button.accessibleName()


def test_undo_and_redo_say_which_step_they_run(flat) -> None:
    assert flat.act_undo.text() == strings.UNDO or flat.act_undo.text().startswith("Undo ")
    flat.ctl.update_unit("OBC1", name="Another name")
    label = flat.ctl.history.next_undo_label
    assert label and flat.act_undo.text() == f"Undo {label}"
    assert "Ctrl+Z" in flat.act_undo.toolTip()
    flat.act_undo.trigger()
    assert flat.act_redo.text() == f"Redo {label}"
    assert flat.act_undo.text() == strings.UNDO or flat.act_undo.text().startswith("Undo ")
    flat.act_redo.trigger()
    assert flat.act_redo.text() == strings.REDO


# ---- banners and refusals persist --------------------------------------------------------------


def test_a_failed_generation_is_a_banner_until_the_next_success(flat) -> None:
    def failing_plan() -> None:
        flat.job_error = "the design has a loop"

    flat.compute_plan = failing_plan
    flat.generate_flow()
    banner = flat.alerts.banner("job")
    assert banner is not None and flat.alerts.is_showing("job")
    assert "the design has a loop" in banner.text() and "Nothing was changed" in banner.text()
    assert banner.action_texts() == [strings.BN_RETRY]
    assert strings.GEN_FAILED.format("the design has a loop") == flat.toasts.messages[-1]
    flat.compute_plan = flat._compute_plan  # the next attempt works
    DialogScript(flat, accept=True)
    edit_something(flat)
    flat.generate_flow()
    assert not flat.alerts.is_showing("job")


def test_a_failed_export_check_is_a_banner(flat, tmp_path) -> None:
    flat._export_failed("the independent check found 2 problems")
    banner = flat.alerts.banner("job")
    assert banner is not None and "independent check" in banner.text()
    banner.dismiss.click()  # or the person dismisses it
    assert not flat.alerts.is_showing("job")


def test_a_lock_refusal_stays_with_a_start_new_revision_button(flat) -> None:
    refused = (
        "This change was blocked because it touches released items. "
        "W001 is released (revision A); start a new revision to change it."
    )
    seen: list[QDialog] = []
    flat.run_dialog = capture(seen)
    flat.ctl.message.emit(refused, False)
    buttons = flat.toasts.findChildren(QPushButton, "toast-action")
    assert [b.text() for b in buttons if b.isVisibleTo(flat.toasts)] == [strings.BN_START_REVISION]
    assert len(flat.toasts._persistent) == 1  # it has no timer: it stays until closed
    buttons[0].click()  # opens the new-revision dialog of the harness the refusal names
    assert len(seen) == 1 and seen[0].windowTitle() == strings.NEW_REV_TITLE.format("W001")
    flat.ctl.message.emit("Moved OBC1.", True)  # the next successful change clears refusals
    assert flat.toasts._persistent == []


# ---- status bar --------------------------------------------------------------------------------


def test_status_bar_shows_path_rules_generation_and_the_pending_link(flat, tmp_path) -> None:
    flat.show()
    assert flat.status_path.full_text() == str(flat.ctl.root)
    assert flat.status_path.property("mono") is True
    rules, version = len(drc.RULES), __version__
    assert flat.status_rules.text() == f"{rules} rules · v{version}"
    record = flat.ctl.project.generation
    assert record is not None
    assert flat.status_generated.text() == f"Generated at model {record.input_hash[:8]}"
    assert flat.pending_link.isVisibleTo(flat) and "values pending" in flat.pending_link.text()
    flat.pending_link.click()
    assert flat.main_tabs.currentWidget() is flat.checks_panel
    assert flat.checks_panel.result_filter() == "unchecked"


def test_the_path_is_cut_in_the_middle_in_a_narrow_window(qtbot) -> None:
    label = ElidedLabel("/home/someone/projects/spacecraft/flatsat/harnesses")
    qtbot.addWidget(label)
    label.resize(120, 20)
    label.show()
    shown = label.shown_text()
    assert (
        "…" in shown and shown.startswith("/home") and shown.endswith("nesses")
    )  # the middle goes
    assert label.full_text() == label.toolTip()


# ---- main tabs and slots -----------------------------------------------------------------------


def test_main_tabs_and_their_shortcuts(flat) -> None:
    tabs = flat.main_tabs
    assert [n for n in tabs.names() if tabs.is_installed(n)] == [
        "diagram",
        "harness",
        "lists",
        "checks",
        "releases",
        "devices",
    ]  # fmt: skip (every view is a tab; an area shows its own, see test_ui_areas.py)
    flat.go_actions["checks"].trigger()
    assert tabs.currentWidget() is flat.checks_panel
    flat.go_actions["releases"].trigger()
    assert tabs.currentWidget() is flat.releases_panel
    flat.go_actions["harness"].trigger()
    assert tabs.currentWidget() is flat.harness_view
    flat.go_actions["lists"].trigger()
    assert tabs.currentWidget() is flat.lists_panel
    flat.go_actions["devices"].trigger()
    assert tabs.currentWidget() is flat.devices_view
    flat.go_actions["diagram"].trigger()
    assert tabs.currentWidget() is flat.diagram_page


def test_the_views_that_exist_are_plugged_into_their_slots(flat) -> None:
    assert isinstance(flat.view_widget("harness"), HarnessView)
    assert isinstance(flat.view_widget("lists"), ListsPanel)
    assert isinstance(flat.view_widget("devices"), DevicesView)
    assert isinstance(flat.view_widget("tree"), ProjectTree)
    assert isinstance(flat.view_widget("inspector"), Inspector)
    assert flat.inspector.props is flat.props  # the properties form lives inside the inspector
    assert flat.left_tabs.currentWidget() is flat.project_tree
    assert flat.dock_left.windowTitle() == strings.TAB_PROJECT
    assert flat.inspector.problems_panel() is flat.problems
    assert flat.view_installed("harness") and not flat.view_installed(
        "why"
    )  # (the inspector has it)


def test_a_view_that_is_installed_gets_its_tab_and_the_signals(flat) -> None:
    class FakeHarnessView(QWidget):
        from PySide6.QtCore import Signal

        showRequested = Signal(str)
        changeRequested = Signal(str, str)
        exportRequested = Signal()

        def __init__(self) -> None:
            super().__init__()
            self.chosen: list[tuple[str, str | None]] = []

        def select_harness(self, hid: str) -> None:
            self.chosen.append((hid, None))

        def select_wire(self, wire: str) -> None:
            self.chosen.append(("", wire))

    view = FakeHarnessView()
    flat.install_view("harness", view)  # another widget can replace a view
    assert flat.view_installed("harness") and flat.view_widget("harness") is view
    flat.go_actions["harness"].trigger()
    assert flat.main_tabs.currentWidget() is view
    seen: list[tuple[str, str]] = []
    flat.change_flow = lambda action, hid: seen.append((action, hid))  # type: ignore[method-assign]
    view.changeRequested.emit("release", "W001")
    assert seen == [("release", "W001")]
    # double-click on a link in the diagram opens the Harness tab with that wire selected
    flat.main_tabs.show_slot("diagram")
    iid = sorted(flat.ctl.project.interfaces)[0]
    flat.ctl.request_open("interface", iid)
    assert flat.main_tabs.currentWidget() is view
    assert view.chosen and view.chosen[0][0] in flat.ctl.project.harnesses


def test_double_click_on_a_link_opens_the_harness_tab(flat) -> None:
    iid = sorted(flat.ctl.project.interfaces)[0]
    flat.ctl.request_open("interface", iid)
    assert flat.main_tabs.currentWidget() is flat.harness_view
    assert flat.harness_view.harness_id() in flat.ctl.project.harnesses


def test_slots_that_have_no_view_yet_keep_an_empty_state(flat) -> None:
    assert flat.view_slots() == [
        "devices", "harness", "inspector", "lists", "problems", "tree", "why",
    ]  # fmt: skip
    for name in ("why", "problems"):
        assert isinstance(flat.view_widget(name), EmptyStateWidget)
        w = QLabel(name)
        flat.install_view(name, w)
        assert flat.view_widget(name) is w and flat.view_installed(name)


def test_the_inspector_slot_keeps_the_old_panel_alive_when_replaced(flat) -> None:
    props = flat.props
    flat.install_view("inspector", QLabel("new"))
    assert flat.view_widget("inspector").text() == "new"  # type: ignore[attr-defined]
    assert props.objectName() is not None  # the replaced panel is not deleted


# ---- what the new views ask the window for -----------------------------------------------------


def test_the_harness_view_asks_for_generate_export_and_change_control(flat) -> None:
    view = flat.harness_view
    calls: list[tuple[str, ...]] = []
    flat.act_generate.trigger = lambda: calls.append(("generate",))  # type: ignore[method-assign]
    flat.change_flow = lambda a, h: calls.append((a, h))  # type: ignore[method-assign]
    flat.export_dialog_flow = lambda: calls.append(("export",))  # type: ignore[method-assign]
    view.generateRequested.emit()
    view.reviewRequested.emit("W001")
    view.releaseRequested.emit("W001")
    view.reviseRequested.emit("W001")
    assert calls == [("generate",), ("review", "W001"), ("release", "W001"), ("revise", "W001")]
    view.whyRequested.emit("harness", "W001")  # opens the Why tab of the inspector
    assert flat.inspector.tabs.currentWidget() is flat.inspector.why


def test_the_lists_tab_exports_a_table_through_the_save_hook(flat, tmp_path) -> None:
    asked: list[tuple[str, str, str]] = []
    target = tmp_path / "wires.csv"

    def ask(title: str, suggested: str, filters: str) -> str:
        asked.append((title, suggested, filters))
        return str(target)

    flat.ask_save_path = ask
    flat.go_to("lists")
    flat.lists_panel.exportTableRequested.emit("wirelist", "csv")
    assert asked and asked[0][1] == "wirelist.csv" and "csv" in asked[0][2].lower()
    assert target.exists() and target.stat().st_size > 0
    assert any("wires.csv" in m for m in flat.toasts.messages)
    flat.ask_save_path = lambda *_a: None  # cancelled: nothing is written
    flat.lists_panel.exportTableRequested.emit("wirelist", "xlsx")
    assert not (tmp_path / "wirelist.xlsx").exists()


def test_the_project_tree_opens_imports_adds_and_points_the_inspector(flat) -> None:
    tree = flat.project_tree
    wizard: list[str] = []
    flat.import_wizard_flow = wizard.append  # type: ignore[method-assign]
    seen: list[str] = []
    flat.import_interfaces_flow = lambda: seen.append("interfaces")  # type: ignore[method-assign]  # (the wizard, D-156)
    for kind in ("interfaces", "parts", "lengths", "engineering", "netlist"):
        tree.importRequested.emit(kind)
    assert seen == ["interfaces"] and wizard == ["parts", "lengths", "values", "netlist"]
    flat.new_interface_flow = lambda: seen.append("new-interface")  # type: ignore[method-assign]
    tree.addRequested.emit("interface")
    assert seen[-1] == "new-interface"
    tree.selectionRequested.emit("harness", "W001")  # something the canvas cannot select
    assert flat.inspector.current() == ("harness", "W001")
    tree.openRequested.emit("harness", "W001")
    assert flat.main_tabs.currentWidget() is flat.harness_view
    assert flat.harness_view.harness_id() == "W001"


def test_the_inspector_asks_for_a_revision_and_shows_objects(flat) -> None:
    asked: list[tuple[str, str]] = []
    flat.change_flow = lambda a, h: asked.append((a, h))  # type: ignore[method-assign]
    flat.inspector.reviseRequested.emit("W001")
    assert asked == [("revise", "W001")]
    flat.inspector.showRequested.emit("unit", "OBC1")
    assert flat.ctl.selection is not None and flat.ctl.selection.id == "OBC1"


def test_slot_tabs_hide_until_installed_and_hide_a_lone_bar(qtbot) -> None:
    theme = ThemeManager()
    tabs = SlotTabs()
    qtbot.addWidget(tabs)
    tabs.add_slot("a", "A", QLabel("a"))
    tabs.add_slot("b", "B", EmptyStateWidget(theme, "B", "text"), installed=False)
    tabs.show()
    assert tabs.visible_names() == ["a"] and not tabs.tabBar().isVisibleTo(tabs)
    old = tabs.install("b", QLabel("b"))
    assert isinstance(old, EmptyStateWidget)
    assert tabs.visible_names() == ["a", "b"] and tabs.tabBar().isVisibleTo(tabs)
    assert tabs.show_slot("b") and tabs.currentIndex() == 1


def test_an_empty_state_says_what_the_view_is_for(qtbot) -> None:
    theme = ThemeManager()
    w = EmptyStateWidget(theme, "Lists", "Wire list and BOM appear here.", button="Generate")
    qtbot.addWidget(w)
    assert "Wire list" in w.text() and w.button is not None and w.button.accessibleName()
    assert "Lists" in w.accessibleName()


def test_banner_stack_keeps_a_banner_until_cleared(qtbot) -> None:
    stack = BannerStack(ThemeManager())
    qtbot.addWidget(stack)
    stack.show()
    hit: list[str] = []
    b = stack.show_banner("x", "error", "It failed", details=["why"], actions=[("Again", lambda: hit.append("a"))])  # fmt: skip
    b.buttons[0].click()
    assert hit == ["a"] and stack.keys() == ["x"] and "why" in b.text()
    stack.show_banner("x", "warning", "Changed")  # the same key replaces its content
    assert b.action_texts() == [] and stack.keys() == ["x"]
    stack.clear("x")
    assert stack.keys() == []


# ---- layout: saved, reset, panels, 1280 x 720, 4K ----------------------------------------------


def test_the_dock_layout_round_trips_through_the_settings(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.dock_left.hide()
    win._save_settings()
    win.settings.sync()
    win.ctl.release()
    win2 = MainWindow(QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat), ThemeManager(), first_run=False)  # fmt: skip
    qtbot.addWidget(win2)
    win2.resize(1440, 900)
    win2.show()
    assert win2._have_saved_state
    assert win2.dock_left.isHidden()
    assert not win2.dock_right.isHidden()


def test_a_layout_saved_with_the_bottom_panel_is_ignored(qtbot, tmp_path) -> None:
    """The saved dock layout carries a version; the one from before the bottom panel was retired
    (version 1) names a dock that no longer exists, so it is dropped and the default layout used."""
    from PySide6.QtCore import QByteArray

    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.settings.setValue("ui/state", QByteArray(win.saveState(1)))  # (the old version number)
    win.settings.sync()
    win.ctl.release()
    win2 = MainWindow(QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat), ThemeManager(), first_run=False)  # fmt: skip
    qtbot.addWidget(win2)
    win2.resize(1440, 900)
    win2.show()
    assert not win2._have_saved_state
    assert not hasattr(win2, "dock_bottom")
    assert win2.findChild(type(win2.dock_left), "dock-bottom") is None


def test_reset_layout_brings_the_panels_back_and_forgets_the_saved_layout(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.dock_left.hide()
    win.dock_right.hide()
    win._save_settings()
    assert win.settings.contains("ui/state")
    win.act_reset_layout.trigger()
    assert not win.settings.contains("ui/state")
    assert not win.dock_left.isHidden() and not win.dock_right.isHidden()
    assert win.main_tabs.currentWidget() is win.diagram_page
    assert win.act_reset_layout in win.findChildren(QAction)


def test_f6_cycles_through_the_panels_and_shift_f6_goes_back(flat) -> None:
    flat.resize(1440, 900)
    flat.auto_layout()
    flat.show()
    flat.activateWindow()
    QApplication.processEvents()
    flat.view.setFocus()
    flat._pane = 0
    names = [flat.cycle_panes(1) for _ in range(3)]
    assert names == [strings.PANE_TREE, strings.PANE_INSPECTOR, strings.PANE_CANVAS]
    assert flat.pane_of_focus() == 0
    back = [flat.cycle_panes(-1) for _ in range(2)]
    assert back == [strings.PANE_INSPECTOR, strings.PANE_TREE]
    flat.dock_right.hide()  # a hidden panel is skipped
    flat.view.setFocus()
    flat._pane = 0
    seen = {flat.cycle_panes(1) for _ in range(3)}
    assert strings.PANE_INSPECTOR not in seen


def test_f6_key_runs_the_action(flat) -> None:
    flat.show()
    flat.activateWindow()
    flat.view.setFocus()
    flat._pane = 0
    flat.act_next_pane.trigger()
    assert flat._pane == 1


@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080), (3840, 2160)])
@pytest.mark.parametrize("theme_name", ["light", "dark"])
def test_the_diagram_keeps_most_of_the_window(qtbot, tmp_path, size, theme_name) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl.open_path(_flatsat(tmp_path))
    win.set_theme_mode(theme_name)
    if size[0] > 3000:
        win.set_scale(200)  # what a 4K screen starts with
    win.resize(*size)
    QApplication.processEvents()
    win.auto_layout()
    QApplication.processEvents()
    share = win.view.height() / win.height()
    assert share >= 0.55, (size, theme_name, share)
    shot = win.grab()
    assert shot.width() > 0 and not shot.isNull()


def test_a_short_window_hides_no_panel_for_lack_of_height(qtbot, tmp_path) -> None:
    """The bottom panel is gone, so only the width decides which side panels show: a 1440 x 700
    window keeps both, and the diagram has the whole height between them."""
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.resize(1440, 900)
    win.auto_layout()
    assert not win.dock_left.isHidden() and not win.dock_right.isHidden()
    win.resize(1440, 700)
    QApplication.processEvents()
    assert not win.dock_left.isHidden() and not win.dock_right.isHidden()
    assert win.view.height() / win.height() >= 0.55


def test_the_first_ui_scale_comes_from_the_screen(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(MainWindow, "_screen_scale", lambda self: 200)
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    assert win.theme.scale == 2.0 and win.scale_actions[200].isChecked()
    assert not win.settings.contains("ui/scale")  # not saved: it follows the screen until chosen


# ---- flows -------------------------------------------------------------------------------------


def test_new_project_is_one_dialog_with_the_discard_question_first(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    order: list[str] = []
    win.ctl.add_zone("Zone for dirt")  # a change that must be saved or discarded first
    assert win.ctl.dirty

    def discard(*_a: object) -> int:
        order.append("discard")
        return 1

    win.ask_choice = discard  # type: ignore[assignment]
    folder = tmp_path / "newproj"

    def fill(dlg: QDialog) -> int:
        order.append("dialog")
        assert isinstance(dlg, NewProjectDialog)
        dlg.folder.setText(str(folder))
        dlg.name.setText("Brand new")
        return int(QDialog.DialogCode.Accepted)

    win.run_dialog = fill
    win.new_project_flow()
    assert order == ["discard", "dialog"]  # _confirm_discard first, then ONE dialog
    assert win.ctl.project.meta.name == "Brand new" and win.ctl.root == folder


def test_new_from_example_starts_with_an_example_and_opens_it(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    folder = tmp_path / "fromexample"
    chosen: list[str] = []

    def fill(dlg: QDialog) -> int:
        assert isinstance(dlg, NewProjectDialog)
        chosen.append(dlg.template())
        dlg.folder.setText(str(folder))
        dlg.name.setText("From example")
        return int(QDialog.DialogCode.Accepted)

    win.run_dialog = fill
    win.new_from_example_flow()
    assert chosen and chosen[0] != "blank"
    assert win.ctl.root == folder and win.ctl.project.meta.name == "From example"


def test_cancelling_the_new_project_dialog_changes_nothing(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    before = win.ctl.root
    DialogScript(win, accept=False)
    win.new_project_flow()
    assert win.ctl.root == before


def test_import_submenu_opens_the_wizard_for_each_kind(flat) -> None:
    texts = [a.text() for a in flat.menu_import.actions()]
    assert texts[0] == strings.A_IMPORT and len(texts) == 6
    assert any("KiCad netlist" in t for t in texts)
    assert any("device pinout" in t for t in texts)
    seen: list[QDialog] = []
    flat.run_dialog = capture(seen)
    for kind in ("parts", "lengths", "values", "pinout", "netlist"):
        flat.import_actions[kind].trigger()
    wizards = [d for d in seen if isinstance(d, ImportWizard)]
    assert [w.kind for w in wizards] == ["parts", "lengths", "values", "pinout", "netlist"]
    assert unnamed(wizards[0]) == []


def test_release_and_revise_go_through_the_change_dialogs(flat) -> None:
    seen: list[QDialog] = []
    flat.run_dialog = capture(seen)
    flat.change_flow("release", "W001")
    dlg = seen[-1]
    assert dlg.findChild(QLabel, "change-locks-summary") is not None
    summary = dlg.findChild(QLabel, "change-locks-summary")
    assert summary is not None and not summary.isHidden()  # the locks are listed
    # the menu entry picks "the" harness: with several releasable ones it opens the Releases tab
    flat.act_release.trigger()
    assert flat.main_tabs.currentWidget() is flat.releases_panel
    assert strings.NO_HARNESS_FOR_ACTION in flat.toasts.messages
    flat.releases_panel.select_harness("W001")
    flat.act_release.trigger()
    assert seen[-1].windowTitle() == strings.RELEASE_TITLE.format("W001")


def test_engineering_values_open_from_the_palette_and_the_checks_tab(flat) -> None:
    entries = {e.label: e for e in flat.palette_entries()}
    entries["Engineering values…"].run()
    dlg = flat.checks_panel.config_dialog()
    assert dlg is not None
    dlg.close()


def test_check_runs_on_demand_and_says_how_it_went(flat, qtbot) -> None:
    flat.toasts.messages.clear()
    flat.act_check.trigger()
    qtbot.waitUntil(lambda: any(m.startswith("Checks finished") for m in flat.toasts.messages), timeout=20000)  # fmt: skip
    assert "not checked" in flat.toasts.messages[-1]
    assert flat.topbar.chip_text() != strings.CHIP_CHECKING


def test_a_job_shows_as_running_in_the_chip(flat) -> None:
    flat._set_busy("generate")
    assert flat.topbar.chip_text() == strings.CHIP_GENERATING
    assert not flat.topbar.generate_btn.isEnabled()  # no second job while one runs
    flat._set_busy(None)
    assert flat.topbar.generate_btn.isEnabled()
    assert flat.topbar.chip_text() != strings.CHIP_GENERATING


def test_the_hash_is_cached_by_model_state(flat, monkeypatch) -> None:
    calls = []
    import harness_design_studio.gui.main_window as mw
    from harness_design_studio.core.io.layout import model_hash as real

    def counted(p):
        calls.append(1)
        return real(p)

    monkeypatch.setattr(mw, "model_hash", counted)
    flat._update_hash()
    flat._update_hash()
    flat._update_hash()
    assert calls == []  # nothing changed since the last reading: no second hash
    edit_something(flat)
    assert len(calls) == 1
    flat._update_hash()
    assert len(calls) == 1


def test_the_new_widgets_have_names(flat) -> None:
    flat.show()
    for tab in range(flat.main_tabs.count()):
        flat.main_tabs.setCurrentIndex(tab)
        assert unnamed(flat) == [], tab
    edit_something(flat)
    assert unnamed(flat) == []  # with the banner showing
