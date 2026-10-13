"""Main window: top bar, banners, main tabs, project panel, inspector, bottom panels, status bar."""

import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from pydantic import ValidationError
from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QEventLoop,
    QSettings,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QCursor,
    QDesktopServices,
    QGuiApplication,
    QKeySequence,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio import __version__
from harness_design_studio.core import drc, edit
from harness_design_studio.core.commands import Op
from harness_design_studio.core.drc import by_rule
from harness_design_studio.core.errors import HarnessError, ProjectLockedError
from harness_design_studio.core.generate.engine import (
    GenerationCancelled,
    GenerationPlan,
    plan_generation,
)
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.model import Project
from harness_design_studio.core.outputs.build import (
    OutputsCancelled,
    OutputSet,
    build_outputs,
    write_outputs,
)
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.vcs.release import (
    plan_new_revision,
    plan_release,
    plan_submit_review,
    release_blockers,
    unapproved_parts,
)
from harness_design_studio.core.vcs.report import baselines_of, changelog_rows, working_diff
from harness_design_studio.core.verify import VerifyReport
from harness_design_studio.gui import strings
from harness_design_studio.gui.canvas import DiagramView, ZoomIndicator
from harness_design_studio.gui.checks_panel import ChecksPanel, PendingValuesLink
from harness_design_studio.gui.controller import (
    LIST_DELAY_MS,
    Delta,
    EditorController,
    NeedSaveAs,
    _plain,
    reason_of,
)
from harness_design_studio.gui.dialogs import (
    Banner,
    ChangeDialog,
    CommandPalette,
    ConfirmDialog,
    DiffDialog,
    GeneratePreviewDialog,
    GlossaryDialog,
    HistoryDialog,
    ImportDialog,
    IssuesDialog,
    NewInterfaceDialog,
    PaletteEntry,
    WaiverDialog,
    WireColoursDialog,
)
from harness_design_studio.gui.export_dialog import ExportDialog, ExportResult
from harness_design_studio.gui.harness_view import HarnessView
from harness_design_studio.gui.icons import icon, icon_button, style_dock_buttons, tooltip_text
from harness_design_studio.gui.import_kinds import KINDS
from harness_design_studio.gui.import_wizard import ImportWizard
from harness_design_studio.gui.inspector import Inspector
from harness_design_studio.gui.lists_panel import ListsPanel
from harness_design_studio.gui.new_project_dialog import (
    BLANK,
    NewProjectDialog,
    NewProjectRequest,
)
from harness_design_studio.gui.panels import (
    HarnessPanel,
    InterfaceTable,
    OutlinePanel,
    PalettePanel,
    ProblemsPanel,
    PropertiesPanel,
    TodoPanel,
    category_icon,
)
from harness_design_studio.gui.project_tree import ProjectTree
from harness_design_studio.gui.releases_panel import ReleasesPanel
from harness_design_studio.gui.shell import (
    BannerStack,
    ElidedLabel,
    EmptyStateWidget,
    SlotTabs,
    auto_scale,
    refusal_harness,
    shrinkable,
)
from harness_design_studio.gui.theme import MODES, ThemeManager, mark_mono
from harness_design_studio.gui.tokens import CATEGORIES
from harness_design_studio.gui.topbar import ShellStatus, TopBar
from harness_design_studio.gui.tour import Tour
from harness_design_studio.resources import guide_path

SCALES = (100, 125, 150, 200)
ARRANGE_IN_WORKER = 60  # a diagram with more units is arranged off the UI thread
STATE_VERSION = 1  # of the saved dock layout (`saveState`); change it when the docks change
WIDE_PX = 1150  # in UI-scale-free px: the right dock needs this much window width
MEDIUM_PX = 800  # ... and the left dock this much
TALL_PX = 800  # below this window height the bottom panel is hidden so the diagram keeps 55 %
MAIN_TABS = ("diagram", "harness", "lists", "checks", "releases")  # Ctrl+1 ... Ctrl+5


@dataclass
class ViewSlot:
    """Where a view goes: the tab widget that holds it and the name of its tab there."""

    tabs: SlotTabs
    name: str
    title: str


def _lower_first(text: str) -> str:
    """ "Approved parts" -> "approved parts", but "KiCad netlist" stays."""
    first = text.split(" ", 1)[0]
    return text[0].lower() + text[1:] if first[1:].islower() else text


def _exec(dialog: QDialog) -> int:
    return int(dialog.exec())


def _no_file() -> str | None:
    return None


class PlanWorker(QThread):
    """Computes a generation plan off the UI thread. It works on a private copy of the project, so
    edits made meanwhile cannot change what it reads (the window refuses a plan made for an
    earlier state)."""

    progressed = Signal(float, str)

    def __init__(self, project: Project) -> None:
        super().__init__()
        self._project = project
        self._cancelled = False
        self.plan: GenerationPlan | None = None
        self.error: str | None = None

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            self.plan = plan_generation(
                self._project, lambda: self._cancelled, lambda f, t: self.progressed.emit(f, t)
            )
        except GenerationCancelled:
            self.plan = None
        except Exception as exc:  # shown as the reason, never as "cancelled"
            self.plan = None
            self.error = reason_of(exc)


class ArrangeWorker(QThread):
    """Works out the tidy layout of a big diagram off the UI thread (it has no way to stop early)."""

    progressed = Signal(float, str)

    def __init__(self, project: Project) -> None:
        super().__init__()
        self._project = project
        self.ops: list[Op] | None = None
        self.error: str | None = None

    def cancel(self) -> None:
        return  # (the layout is one calculation; its result is simply not used)

    def run(self) -> None:
        try:
            self.ops = edit.ops_arrange(self._project)
        except Exception as exc:  # shown as the reason
            self.error = reason_of(exc)


class OutputsWorker(QThread):
    """Builds and independently verifies the output set off the UI thread (read-only)."""

    progressed = Signal(float, str)

    def __init__(self, project: Project) -> None:
        super().__init__()
        self._project = project
        self._cancelled = False
        self.result: OutputSet | None = None
        self.report: VerifyReport | None = None
        self.error: str | None = None

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            self.result = build_outputs(
                self._project,
                cancel=lambda: self._cancelled,
                progress=lambda f, t: self.progressed.emit(f, t),
            )
            self.progressed.emit(0.95, strings.PROGRESS_VERIFY)
            self.report = verify_outputs(self._project, self.result.files)
        except OutputsCancelled:
            self.result = None
        except Exception as exc:  # shown as the reason, never as "cancelled"
            self.result = self.report = None
            self.error = reason_of(exc)


class ToastHost(QWidget):
    """Short messages over the diagram; an optional Undo button; they never block.

    At most two are shown (the oldest goes first), a repeated message is not shown twice, a new
    message with an Undo button replaces the older one that had one, and every message has a
    close button."""

    MAX_VISIBLE = 2

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("toast-host")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.messages: list[str] = []
        self._frames: list[tuple[QFrame, str, bool]] = []  # frame, text, has an Undo button
        self._persistent: list[QFrame] = []  # shown until closed or until `clear_persistent`
        self.hide()

    def record(self, text: str) -> None:
        """Note a message that is shown somewhere else (a banner): it joins `messages`, which is
        the log of everything the person was told, without a second pop-up."""
        self.messages.append(text)

    def clear_persistent(self) -> None:
        """Take down the messages that stay until something succeeds (refusals, errors)."""
        for frame in list(self._persistent):
            self._remove(frame)

    def show_message(
        self,
        text: str,
        undo: Callable[[], None] | None = None,
        ms: int = 5000,
        *,
        action: tuple[str, Callable[[], None]] | None = None,
    ) -> None:
        self.messages.append(text)
        self._frames = [f for f in self._frames if self._alive(f[0])]
        if undo is None and action is None and any(t == text for _f, t, _u in self._frames):
            return  # the same message is already showing (one with a new Undo replaces the old)
        if undo is not None:  # an older Undo would now undo the wrong thing
            for frame, _t, has_undo in list(self._frames):
                if has_undo:
                    self._remove(frame)
        while len(self._frames) >= self.MAX_VISIBLE:
            self._remove(self._frames[0][0])
        frame = QFrame()
        frame.setObjectName("toast")
        frame.setProperty("card", True)
        row = QHBoxLayout(frame)
        label = QLabel(text)
        label.setWordWrap(True)
        host = self.parentWidget()
        width = max(240, min(720, (host.width() if host else 500) - 120))
        label.setFixedWidth(width)
        label.setMinimumHeight(label.heightForWidth(width))  # never cut a long message off
        row.addWidget(label, 1)
        if undo is not None:
            b = QPushButton(strings.UNDO)
            b.setObjectName("toast-undo")
            b.setAccessibleName(strings.UNDO)

            def do() -> None:
                undo()
                self._remove(frame)

            b.clicked.connect(do)
            row.addWidget(b)
        if action is not None:  # one more button that does something about the message
            act_b = QPushButton(action[0])
            act_b.setObjectName("toast-action")
            act_b.setAccessibleName(action[0])

            def act_do() -> None:
                self._remove(frame)
                action[1]()

            act_b.clicked.connect(act_do)
            row.addWidget(act_b)
        close = QPushButton("×")
        close.setObjectName("toast-close")
        close.setFlat(True)
        close.setAccessibleName(strings.TOAST_CLOSE)
        close.setToolTip(strings.TOAST_CLOSE)
        close.clicked.connect(lambda: self._remove(frame))
        row.addWidget(close)
        self.lay.addWidget(frame)
        frame.show()  # a widget added to a visible parent is otherwise shown only later
        self._frames.append((frame, text, undo is not None))
        self.adjustSize()
        self.show()
        self.raise_()
        if ms > 0:  # ms == 0: stays until the person closes it or the next success
            QTimer.singleShot(ms, lambda: self._expire(frame))
        else:
            self._persistent.append(frame)
        self.reposition()

    @staticmethod
    def _alive(frame: QFrame) -> bool:
        try:
            return frame.parent() is not None
        except RuntimeError:  # deleted with its window
            return False

    def _remove(self, frame: QFrame) -> None:
        with contextlib.suppress(RuntimeError):
            self._frames = [f for f in self._frames if f[0] is not frame]
            self._persistent = [f for f in self._persistent if f is not frame]
            self.lay.removeWidget(frame)
            frame.hide()
            frame.deleteLater()
            QTimer.singleShot(0, self._shrink)

    def _expire(self, frame: QFrame) -> None:
        # the window may have been closed while the message was showing
        self._remove(frame)

    def _shrink(self) -> None:
        with contextlib.suppress(RuntimeError):
            if not self._frames:
                self.hide()
            self.adjustSize()

    def reposition(self) -> None:
        p = self.parentWidget()
        if p is not None:
            self.adjustSize()
            self.move(max(8, (p.width() - self.width()) // 2), 8)


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: QSettings,
        theme: ThemeManager,
        *,
        journal_delay_ms: int = 1500,
        first_run: bool | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.theme = theme
        self.ctl = EditorController(journal_delay_ms)
        self.setObjectName("main-window")
        # Dialog hooks (tests replace these to drive the UI without blocking).
        self.run_dialog: Callable[[QDialog], int] = _exec
        self.ask_folder: Callable[[str], str | None] = self._ask_folder
        self.ask_text: Callable[[str, str, str], str | None] = self._ask_text
        self.ask_choice: Callable[[str, str, list[str]], int] = self._ask_choice
        self.ask_file: Callable[[], str | None] = _no_file
        self.open_url: Callable[[QUrl], bool] = QDesktopServices.openUrl
        self.compute_plan: Callable[[], GenerationPlan | None] = self._compute_plan
        self.compute_outputs: Callable[[], tuple[OutputSet, VerifyReport] | None] = (
            self._compute_outputs
        )
        self.palette_entries_extra: list[PaletteEntry] = []
        self.job_error: str | None = None  # why the last generation or export run failed
        # hooks for the import wizard's file chooser and the export dialog's worker (tests replace them)
        self.ask_import_file: Callable[[str, str], str | None] | None = None
        self.export_worker_factory: Callable[[Project], OutputsWorker] | None = None
        # file name for "Export table" of the Lists tab: (title, suggested name, filter) -> path
        self.ask_save_path: Callable[[str, str, str], str | None] = self._ask_save_path
        self.busy: str | None = None  # "generate" | "export" | "arrange" while a job runs
        self._view_slots: dict[str, ViewSlot] = {}
        self._facts_key: tuple[object, ...] | None = None
        self._facts_token: tuple[int, int] | None = None  # the state token of the last reading
        self._facts: tuple[str, str, str] = ("--------", "none", "none")
        self._facts_ms = 0.0  # what the last hash and status work cost (it sets the pause)
        self._outputs_epoch = 0  # bumped when files were written, to read the outputs state again
        self._dismissed_alert: tuple[bool, bool, str] | None = None
        self._check_asked = False  # the person pressed Check: say when it has finished
        self._shown = False
        self._have_saved_state = False
        self._layout_class: tuple[bool, bool, bool] | None = None
        self._bottom_auto_hidden = False
        self._pane = 0

        self._build_center()
        self._build_docks()
        self._build_actions()
        self._build_menus_and_toolbar()
        self._build_status()
        self.toasts = ToastHost(self.view)
        self._register_slots()
        self._install_default_views()
        self.tour = Tour(self, theme, self._tour_targets(), self._tour_reveals())
        self.tour.on_stop = lambda: self.settings.setValue("tour/done", True)

        self.ctl.message.connect(self._on_message)
        self.ctl.drcChanged.connect(self._update_tab_badges)
        self.ctl.drcStateChanged.connect(self._on_check_state)
        self.ctl.stateChanged.connect(self._on_state)
        self.ctl.changed.connect(self._on_changed)
        self.ctl.selectionChanged.connect(self._on_selection)
        self.ctl.openRequested.connect(self._open_requested)
        self.props.deleteRequested.connect(self.delete_flow)
        self.ctl.connectChanged.connect(self._on_connect)
        self.ctl.modeChanged.connect(self._on_mode)
        self.palette_panel.addUnit.connect(self._add_unit)
        self.palette_panel.connectType.connect(self._toggle_connect)
        self.palette_panel.importRequested.connect(self.import_flow)
        self.problems.showRequested.connect(self.show_object)
        self.problems.waiveRequested.connect(self.waive_flow)
        self.todo.activated.connect(self._todo_activated)
        self.table.newInterfaceRequested.connect(self.new_interface_flow)
        self.checks_panel.showRequested.connect(self.show_object)
        self.releases_panel.changeRequested.connect(self.change_flow)
        self.pending_link.filterRequested.connect(self.show_unchecked)
        self.topbar.generateClicked.connect(self.act_generate.trigger)
        self.topbar.checkClicked.connect(self.act_check.trigger)
        self.topbar.exportClicked.connect(self.act_export.trigger)
        self.alerts.dismissed.connect(self._alert_dismissed)
        shows = getattr(self.view, "showRequested", None)  # the canvas's "Show" plumbing
        if shows is not None:
            shows.connect(self.show_object)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.focusChanged.connect(self._focus_changed)

        self._hash_timer = QTimer(self)
        self._hash_timer.setSingleShot(True)
        self._hash_timer.setInterval(250)
        self._hash_timer.timeout.connect(self._update_hash)
        self._badge_timer = QTimer(self)
        self._badge_timer.setSingleShot(True)
        self._badge_timer.setInterval(LIST_DELAY_MS)
        self._badge_timer.timeout.connect(self._apply_tab_badges)

        self._default_state = self.saveState(STATE_VERSION)  # View > Reset layout goes back to it
        self._restore_settings()
        self._on_state()
        self._on_connect()
        self._on_selection()
        if first_run is None:
            first_run = not self.settings.value("tour/done", False, bool)
        self.ctl.open_sample()
        self._update_hash()
        if first_run:
            QTimer.singleShot(200, self.tour.start)

    # ---- construction ------------------------------------------------------------------------
    def _build_center(self) -> None:
        shell = QWidget()
        shell.setObjectName("shell")
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.topbar = TopBar(self.theme)
        self.generate_btn = self.topbar.generate_btn
        outer.addWidget(self.topbar)
        self.banner = Banner()
        outer.addWidget(self.banner)
        self.alerts = BannerStack(self.theme)
        outer.addWidget(self.alerts)
        # the diagram page: the tool row and the canvas
        centre = QWidget()
        centre.setObjectName("diagram-page")
        lay = QVBoxLayout(centre)
        lay.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        bar.setContentsMargins(
            self.theme.space(8), self.theme.space(4), self.theme.space(8), self.theme.space(4)
        )
        self.tool_select = QToolButton()
        self.tool_select.setText(strings.TOOL_SELECT)
        self.tool_select.setObjectName("tool-select")
        self.tool_select.setCheckable(True)
        self.tool_select.setChecked(True)
        self.tool_select.setProperty("toggle", True)
        self.tool_select.setToolTip(strings.TOOL_SELECT_TIP)
        self.tool_connect = QToolButton()
        self.tool_connect.setText(strings.TOOL_CONNECT)
        self.tool_connect.setObjectName("tool-connect")
        self.tool_connect.setCheckable(True)
        self.tool_connect.setProperty("toggle", True)
        self.tool_connect.setToolTip(strings.TOOL_CONNECT_TIP)
        self.tool_select.clicked.connect(lambda: self.ctl.end_connect())
        self.tool_connect.clicked.connect(lambda: self.ctl.begin_connect(self.ctl.connect_type))
        self._told_properties = False
        self.hint = QLabel("")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        self.hint.setAccessibleName(strings.HINT)
        self.redundant_btn = QPushButton(strings.REDUNDANT_COPY)
        self.redundant_btn.setObjectName("redundant-copy")
        self.redundant_btn.clicked.connect(self._redundant_selected)
        self.delete_btn = QPushButton(strings.DELETE)
        self.delete_btn.setObjectName("delete")
        self.delete_btn.setProperty("danger", True)
        self.delete_btn.clicked.connect(self.delete_flow)
        self.zoom_in_btn = QToolButton()
        icon_button(self.zoom_in_btn, "zoom-in", self.theme, strings.ZOOM_IN, "Ctrl+=")
        self.zoom_out_btn = QToolButton()
        icon_button(self.zoom_out_btn, "zoom-out", self.theme, strings.ZOOM_OUT, "Ctrl+-")
        self.fit_btn = QToolButton()
        icon_button(self.fit_btn, "fit", self.theme, strings.FIT, "F", text=strings.FIT)
        bar.addWidget(self.tool_select)
        bar.addWidget(self.tool_connect)
        bar.addWidget(self.hint, 1)
        self.view = DiagramView(self.ctl, self.theme)
        self.view.setObjectName("diagram")
        self.zoom_level = ZoomIndicator(self.view)  # "100 %"; View.zoomChanged(float) feeds it
        for w in (
            self.redundant_btn,
            self.delete_btn,
            self.zoom_out_btn,
            self.zoom_in_btn,
            self.fit_btn,
        ):
            bar.addWidget(w)
        lay.addLayout(bar)
        self.zoom_in_btn.clicked.connect(lambda: self.view.zoom_by(1.2))
        self.zoom_out_btn.clicked.connect(lambda: self.view.zoom_by(1 / 1.2))
        self.fit_btn.clicked.connect(lambda _c=False: self.view.fit())
        lay.addWidget(self.view, 1)
        self.legend = self.view.legend.bar  # (the key is an overlay of the view now)
        self.diagram_page = centre
        # the main views: Diagram, Harness, Lists, Checks, Releases (the first two that are still
        # to come are empty slots with their tab hidden; see `install_view`)
        self.main_tabs = SlotTabs()
        self.main_tabs.setObjectName("main-tabs")
        self.main_tabs.setAccessibleName(strings.SHELL_MAIN_TABS)
        self.checks_panel = ChecksPanel(self.ctl, self.theme, settings=self.settings)
        self.releases_panel = ReleasesPanel(self.ctl, self.theme, settings=self.settings)
        self.main_tabs.add_slot(
            "diagram",
            strings.TAB_DIAGRAM,
            centre,
            tip=strings.TAB_TIP.format(strings.TAB_DIAGRAM, 1),
            shrink=False,  # the diagram page keeps its own minimum (its tool row)
        )
        self.main_tabs.add_slot(
            "harness",
            strings.TAB_HARNESS,
            EmptyStateWidget(self.theme, strings.TAB_HARNESS, strings.EMPTY_VIEW_HARNESS, icon="harness"),
            installed=False,
            tip=strings.TAB_TIP.format(strings.TAB_HARNESS, 2),
        )  # fmt: skip
        self.main_tabs.add_slot(
            "lists",
            strings.TAB_LISTS,
            EmptyStateWidget(self.theme, strings.TAB_LISTS, strings.EMPTY_VIEW_LISTS, icon="list"),
            installed=False,
            tip=strings.TAB_TIP.format(strings.TAB_LISTS, 3),
        )  # fmt: skip
        self.main_tabs.add_slot("checks", strings.TAB_CHECKS, self.checks_panel, tip=strings.TAB_TIP.format(strings.TAB_CHECKS, 4))  # fmt: skip
        self.main_tabs.add_slot("releases", strings.TAB_RELEASES, self.releases_panel, tip=strings.TAB_TIP.format(strings.TAB_RELEASES, 5))  # fmt: skip
        outer.addWidget(self.main_tabs, 1)
        self.main_tabs.tabBar().setAccessibleName(strings.SHELL_MAIN_TABS)
        self.setCentralWidget(shell)

    def _build_docks(self) -> None:
        self.palette_panel = PalettePanel(self.ctl, self.theme)
        # left: the project tree (a slot, filled when it exists) and the palette
        self.left_tabs = SlotTabs()
        self.left_tabs.setObjectName("left-tabs")
        self.left_tabs.setAccessibleName(strings.SHELL_LEFT_TABS)
        self.left_tabs.add_slot(
            "tree",
            strings.TAB_PROJECT,
            EmptyStateWidget(self.theme, strings.TAB_PROJECT, strings.EMPTY_VIEW_TREE, icon="tree"),
            installed=False,
        )
        self.left_tabs.add_slot("palette", strings.TAB_PALETTE, self.palette_panel)
        self.dock_left = self._dock(
            strings.PALETTE,
            self.left_tabs,
            Qt.DockWidgetArea.LeftDockWidgetArea,
            "dock-palette",
        )
        self.left_tabs.currentChanged.connect(lambda _i: self._sync_dock_titles())
        # right: Inspector (the properties panel until the new one arrives), Why, Problems
        self.props = PropertiesPanel(self.ctl, self.theme)
        self.side_tabs = SlotTabs()
        self.side_tabs.setObjectName("side-tabs")
        self.side_tabs.setAccessibleName(strings.SHELL_RIGHT_TABS)
        self.side_tabs.add_slot("inspector", strings.TAB_INSPECTOR, self.props)
        self.side_tabs.add_slot(
            "why",
            strings.TAB_WHY,
            EmptyStateWidget(self.theme, strings.TAB_WHY, strings.EMPTY_VIEW_WHY, icon="info"),
            installed=False,
        )
        self.side_tabs.add_slot(
            "problems",
            strings.TAB_PROBLEMS,
            EmptyStateWidget(
                self.theme, strings.TAB_PROBLEMS, strings.EMPTY_VIEW_PROBLEMS, icon="warning"
            ),  # fmt: skip
            installed=False,
        )
        self.dock_right = self._dock(
            strings.TAB_INSPECTOR,
            self.side_tabs,
            Qt.DockWidgetArea.RightDockWidgetArea,
            "dock-properties",
        )
        self.problems = ProblemsPanel(self.ctl)
        self.todo = TodoPanel(self.ctl)
        self.table = InterfaceTable(self.ctl)
        self.outline = OutlinePanel(self.ctl)
        self.harness_panel = HarnessPanel(self.ctl)
        self.harness_panel.exportRequested.connect(self.export_flow)
        self.harness_panel.changeRequested.connect(self.change_flow)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("bottom-tabs")
        self.tabs.setAccessibleName(strings.BOTTOM_TABS)
        self.tabs.addTab(self.problems, strings.PROBLEMS)
        self.tabs.addTab(self.todo, strings.TODO)
        self.tabs.addTab(self.table, strings.INTERFACE_TABLE)
        self.tabs.addTab(self.harness_panel, strings.HARNESS_PLANS)
        self.tabs.addTab(self.outline, strings.OUTLINE)
        for page in (self.problems, self.todo, self.table, self.harness_panel, self.outline):
            shrinkable(page)  # a long line in a card must not widen the whole window
        self.dock_bottom = self._dock(
            strings.PROBLEMS_AND_STATUS,
            self.tabs,
            Qt.DockWidgetArea.BottomDockWidgetArea,
            "dock-bottom",
        )
        self.dock_left.setMinimumWidth(240)
        self.dock_right.setMinimumWidth(260)
        self.resizeDocks([self.dock_left, self.dock_right], [250, 310], Qt.Orientation.Horizontal)
        self.tabs.setMinimumHeight(90)  # without this the panels' own minimum takes ~430 px
        self.resizeDocks([self.dock_bottom], [170], Qt.Orientation.Vertical)

    def _dock(self, title: str, widget: QWidget, area: Qt.DockWidgetArea, name: str) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(name)
        dock.setWidget(widget)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.addDockWidget(area, dock)
        style_dock_buttons(dock, self.theme, strings.DOCK_CLOSE)
        return dock

    def _build_status(self) -> None:
        sb = self.statusBar()
        self.status_saved = QLabel(strings.ALL_SAVED)
        self.status_sel = QLabel("")
        self.status_counts = QLabel("")
        self.status_hash = QLabel("")  # the model hash reads in the monospace font
        self.status_hash.setObjectName("status-hash")
        self.status_hash.setAccessibleName(strings.STATUS_HASH)
        mark_mono(self.status_hash)
        for w in (self.status_saved, self.status_sel, self.status_counts, self.status_hash):
            sb.addWidget(w)
            w.setContentsMargins(self.theme.space(8), 0, self.theme.space(8), 0)
        # the project folder, in mono and cut in the middle when the window is narrow
        self.status_path = ElidedLabel("")
        self.status_path.setObjectName("status-path")
        self.status_path.setAccessibleName(strings.STATUS_PATH_NAME)
        mark_mono(self.status_path)
        self.status_path.setContentsMargins(self.theme.space(8), 0, self.theme.space(8), 0)
        sb.addWidget(self.status_path, 1)
        self.status_rules = QLabel(strings.STATUS_RULES.format(len(drc.RULES), __version__))
        self.status_rules.setObjectName("status-rules")
        self.status_rules.setAccessibleName(
            strings.STATUS_RULES.format(len(drc.RULES), __version__)
        )
        self.status_rules.setToolTip(strings.STATUS_RULES_TIP.format(len(drc.RULES), __version__))
        self.status_generated = QLabel("")
        self.status_generated.setObjectName("status-generated")
        mark_mono(self.status_generated)
        self.pending_link = PendingValuesLink(self.ctl, self.theme)
        self.pending_link.setObjectName("pending-values-link")
        for w in (self.status_rules, self.status_generated):
            w.setContentsMargins(self.theme.space(8), 0, self.theme.space(8), 0)
            sb.addPermanentWidget(w)
        sb.addPermanentWidget(self.pending_link)
        sb.addPermanentWidget(self.zoom_level)  # "100 %" (the view's zoomChanged feeds it)

    def _sync_dock_titles(self) -> None:
        self.dock_left.setWindowTitle(
            strings.TAB_PROJECT
            if self.left_tabs.currentWidget() is not self.palette_panel
            else strings.PALETTE  # fmt: skip
        )

    # ---- the slot registry: views that are written elsewhere plug in here --------------------------
    def _register_slots(self) -> None:
        """Name every place a later view goes. `install_view(name, widget)` fills one."""
        for name, tabs, title in (
            ("harness", self.main_tabs, strings.TAB_HARNESS),
            ("lists", self.main_tabs, strings.TAB_LISTS),
            ("tree", self.left_tabs, strings.TAB_PROJECT),
            ("inspector", self.side_tabs, strings.TAB_INSPECTOR),
            ("why", self.side_tabs, strings.TAB_WHY),
            ("problems", self.side_tabs, strings.TAB_PROBLEMS),
        ):
            self._view_slots[name] = ViewSlot(tabs, name, title)

    def view_slots(self) -> list[str]:
        """The names `install_view` accepts: harness, lists, tree, inspector, why, problems."""
        return sorted(self._view_slots)

    def view_installed(self, name: str) -> bool:
        """True when a real view (not the empty placeholder) fills the slot."""
        return self._view_slots[name].tabs.is_installed(name)

    def view_widget(self, name: str) -> QWidget:
        slot = self._view_slots[name]
        return slot.tabs.widget_of(name)

    def install_view(self, name: str, widget: QWidget, *, show: bool = False) -> None:
        """Plug a finished view into its slot: `harness` (HarnessView), `lists` (ListsPanel),
        `tree` (ProjectTree), `inspector` (Inspector), `why` (WhyPanel), `problems`. The tab shows
        from then on. A signal the widget has under one of the names `showRequested(str)`,
        `changeRequested(str, str)` or `exportRequested()` is connected to the window."""
        slot = self._view_slots[name]
        old = slot.tabs.widget_of(name)
        slot.tabs.install(name, widget, show=show)
        if not isinstance(old, EmptyStateWidget):  # a real panel it replaces stays alive, hidden
            old.hide()
        self._wire_view(widget)
        if name == "tree":
            slot.tabs.setCurrentWidget(widget)
            self._sync_dock_titles()
        self._update_view_actions()
        if hasattr(self, "_hash_timer"):  # (not while the window is still being built)
            self._update_hash()

    def _wire_view(self, widget: QWidget) -> None:
        """Connect the signals of a view that was plugged in. The views of this program are wired
        by `_wire_known_view`; any other widget may have `showRequested(str)`,
        `changeRequested(str, str)` or `exportRequested()`."""
        if self._wire_known_view(widget):
            return
        for signal_name, target in (
            ("showRequested", self.show_object),
            ("changeRequested", self.change_flow),
            ("exportRequested", self.export_dialog_flow),
        ):
            signal = getattr(widget, signal_name, None)
            if signal is not None:
                signal.connect(target)

    def _wire_known_view(self, widget: QWidget) -> bool:
        if isinstance(widget, HarnessView):
            widget.generateRequested.connect(lambda: self.act_generate.trigger())
            widget.exportRequested.connect(lambda: self.export_dialog_flow())
            widget.reviewRequested.connect(lambda hid: self.change_flow("review", hid))
            widget.releaseRequested.connect(lambda hid: self.change_flow("release", hid))
            widget.reviseRequested.connect(lambda hid: self.change_flow("revise", hid))
            widget.whyRequested.connect(lambda kind, ident: self._show_why(kind, ident))
            return True
        if isinstance(widget, ListsPanel):
            widget.generateRequested.connect(self.act_generate.trigger)
            widget.exportTableRequested.connect(lambda name, fmt: self.export_table_flow(name, fmt))
            return True
        if isinstance(widget, ProjectTree):
            widget.selectionRequested.connect(self._tree_selected)
            widget.openRequested.connect(self._tree_opened)
            widget.importRequested.connect(self._tree_import)
            widget.addRequested.connect(self._tree_add)
            return True
        if isinstance(widget, Inspector):
            widget.reviseRequested.connect(lambda hid: self.change_flow("revise", hid))
            widget.showRequested.connect(lambda _kind, ident: self.show_object(ident))
            return True
        return False

    def _install_default_views(self) -> None:
        """Plug in the views that exist: Harness, Lists, the project tree and the inspector (with
        its Why and Problems tabs; its Problems tab has a panel of its own, the one of the bottom
        panel stays where it is until that one is retired)."""
        self.harness_view = HarnessView(self.ctl, self.theme, self.settings)
        self.lists_panel = ListsPanel(self.ctl, self.theme, self.settings)
        self.project_tree = ProjectTree(self.ctl, self.theme, self.settings)
        # the properties panel leaves its tab for the inspector that wraps it
        self.side_tabs.install("inspector", EmptyStateWidget(self.theme, strings.TAB_INSPECTOR, ""))
        self.problems_side = ProblemsPanel(self.ctl)
        self.problems_side.showRequested.connect(self.show_object)
        self.problems_side.waiveRequested.connect(self.waive_flow)
        self.inspector = Inspector(
            self.ctl, self.theme, props=self.props, problems=self.problems_side
        )
        self.install_view("harness", self.harness_view)
        self.install_view("lists", self.lists_panel)
        self.install_view("tree", self.project_tree)
        self.install_view("inspector", self.inspector)

    # ---- what the new views ask for ----------------------------------------------------------------
    def _show_why(self, kind: str, ident: str) -> None:
        """The Why of a harness, wire, connector or pin: in the right dock's Why tab."""
        self.dock_right.show()
        self.inspector.show_object(kind, ident, tab="why")

    def _tree_selected(self, kind: str, ident: str) -> None:
        if kind not in ("unit", "interface"):  # (those the tree selects on the canvas itself)
            self.inspector.show_object(kind, ident)

    def _tree_opened(self, kind: str, ident: str) -> None:
        if kind in ("unit", "interface"):
            self.ctl.request_open(kind, ident)
        elif kind == "harness":
            self._go_to_harness(ident)
        else:
            self.inspector.show_object(kind, ident)

    def _tree_import(self, kind: str) -> None:
        if kind == "interfaces":
            self.import_flow()
        else:
            self.import_wizard_flow({"engineering": "values"}.get(kind, kind))

    def _tree_add(self, kind: str) -> None:
        if kind == "interface":
            self.new_interface_flow()
        else:
            self.menu_add.exec(QCursor.pos())  # which kind of unit

    def export_table_flow(self, name: str, fmt: str) -> None:
        """ "Export table" of the Lists tab: ask where, then write the rows as they are shown."""
        path = self.ask_save_path(
            strings.LISTS_EXPORT_TITLE, f"{name}.{fmt}", strings.LISTS_EXPORT_FILTER.get(fmt, "")
        )
        if not path:
            return
        try:
            written = self.lists_panel.export_to(Path(path), name)
        except (OSError, ValueError) as exc:
            self._error(self._explain(exc, Path(path).parent))
            return
        self.toasts.show_message(strings.LISTS_EXPORTED.format(written.name), None)

    @staticmethod
    def _ask_save_path(title: str, suggested: str, filters: str) -> str | None:
        path, _ = QFileDialog.getSaveFileName(None, title, suggested, filters)
        return path or None

    # ---- actions -------------------------------------------------------------------------------
    def _act(
        self,
        text: str,
        slot: Callable[[], None],
        shortcut: str | QKeySequence.StandardKey | None = None,
        *,
        checkable: bool = False,
        name: str = "",
        only_in: tuple[QWidget, ...] = (),
    ) -> QAction:
        """An action on the window. With `only_in`, the shortcut works only while one of those
        widgets has the keyboard focus (so a bare F or Delete cannot act from another panel)."""
        a = QAction(text, self)
        if name:
            a.setObjectName(name)
        if shortcut is not None:
            a.setShortcut(QKeySequence(shortcut))
            a.setShortcutContext(
                Qt.ShortcutContext.WidgetShortcut if only_in else Qt.ShortcutContext.WindowShortcut
            )
        a.setCheckable(checkable)
        a.triggered.connect(lambda _c=False: slot())
        self.addAction(a)
        for widget in only_in:
            widget.addAction(a)
        return a

    def _build_actions(self) -> None:
        a = self._act
        self.act_new = a(strings.A_NEW, self.new_project_flow, "Ctrl+N", name="act-new")
        self.act_new_example = a(
            strings.A_NEW_EXAMPLE, self.new_from_example_flow, name="act-new-example"
        )
        self.act_open = a(strings.A_OPEN, self.open_flow, "Ctrl+O", name="act-open")
        self.act_save = a(strings.A_SAVE, self._save_copy_noop, "Ctrl+S", name="act-save")
        self.act_save_as = a(strings.A_SAVE_AS, self._save_copy, "Ctrl+Shift+S", name="act-save-as")
        self.act_import = a(strings.A_IMPORT, self.import_flow, "Ctrl+Shift+I", name="act-import")
        self.act_quit = a(strings.A_QUIT, self._quit, "Ctrl+Q", name="act-quit")
        self.act_undo = a(strings.UNDO, self.ctl.undo, "Ctrl+Z", name="act-undo")
        self.act_redo = a(strings.REDO, self.ctl.redo, "Ctrl+Y", name="act-redo")
        self.act_redo.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self.act_redo2 = self.act_redo  # (the second key is a second shortcut of Redo)
        self.act_delete = a(
            strings.DELETE,
            self.delete_flow,
            "Delete",
            name="act-delete",
            only_in=(self.view, self.table.view, self.outline.tree),  # not from other panels
        )
        self.act_redundant = a(
            strings.REDUNDANT_COPY, self._redundant_selected, name="act-redundant"
        )
        self.act_connect_tool = a(
            strings.TOOL_CONNECT,
            lambda: self.ctl.begin_connect(self.ctl.connect_type),
            "C",
            name="act-connect",
        )
        self.act_select_tool = a(strings.TOOL_SELECT, self.ctl.end_connect, name="act-select")
        self.act_add_zone = a(strings.A_ADD_ZONE, self.add_zone_flow, name="act-add-zone")
        self.act_guided = a(
            strings.GUIDED, lambda: self.ctl.set_mode("guided"), checkable=True, name="act-guided"
        )
        self.act_expert = a(
            strings.EXPERT, lambda: self.ctl.set_mode("expert"), checkable=True, name="act-expert"
        )
        group = QActionGroup(self)
        group.addAction(self.act_guided)
        group.addAction(self.act_expert)
        self.act_guided.setChecked(True)
        self.act_dark = a(strings.A_DARK, self._toggle_dark, checkable=True, name="act-dark")
        self.theme_actions: dict[str, QAction] = {}
        tgroup = QActionGroup(self)
        for mode, label in (
            ("system", strings.A_THEME_SYSTEM),
            ("light", strings.A_THEME_LIGHT),
            ("dark", strings.A_THEME_DARK),
        ):
            act = a(
                label, partial(self.set_theme_mode, mode), checkable=True, name=f"act-theme-{mode}"
            )
            tgroup.addAction(act)
            self.theme_actions[mode] = act
        self.theme_actions[self.theme.mode].setChecked(True)
        self.act_minimap = a(
            strings.A_MINIMAP, self._toggle_minimap, checkable=True, name="act-minimap"
        )
        self.act_labels = a(
            strings.A_LABELS, self._toggle_labels, checkable=True, name="act-labels"
        )
        self.act_minimap.setChecked(True)
        self.scale_actions: dict[int, QAction] = {}
        sgroup = QActionGroup(self)
        for pct in SCALES:
            act = a(
                f"{pct}%", partial(self.set_scale, pct), checkable=True, name=f"act-scale-{pct}"
            )
            sgroup.addAction(act)
            self.scale_actions[pct] = act
        self.scale_actions[100].setChecked(True)
        self.act_zoom_in = a(
            strings.ZOOM_IN, lambda: self.view.zoom_by(1.2), "Ctrl+=", name="act-zoom-in"
        )
        self.act_zoom_out = a(
            strings.ZOOM_OUT, lambda: self.view.zoom_by(1 / 1.2), "Ctrl+-", name="act-zoom-out"
        )
        self.act_fit = a(
            strings.A_FIT_ALL, lambda: self.view.fit(), "F", name="act-fit", only_in=(self.view,)
        )
        self.act_arrange = a(
            strings.A_ARRANGE, self.arrange_flow, "Ctrl+Shift+L", name="act-arrange"
        )
        self._build_canvas_actions()
        self.act_wire_colours = a(
            strings.A_WIRE_COLOURS, self.wire_colours_flow, name="act-wire-colours"
        )
        self.act_commands = a(strings.A_COMMANDS, self.open_commands, "Ctrl+K", name="act-commands")
        self.act_guide = a(strings.A_GUIDE, self.guide_flow, "F1", name="act-guide")
        self.act_tour = a(
            strings.A_TOUR,
            self._start_tour,
            name="act-tour",
        )
        self.act_glossary = a(strings.A_GLOSSARY, self.glossary_flow, name="act-glossary")
        self.act_sample = a(strings.A_SAMPLE, self.sample_flow, name="act-sample")
        self.act_about = a(strings.A_ABOUT, self.about_flow, name="act-about")
        self.act_issues = a(strings.A_ISSUES, self.issues_flow, name="act-issues")
        self._build_shell_actions()

    # ---- shell actions: generate, check, export, change control, views, layout (ux/shell) ---------
    def _build_shell_actions(self) -> None:
        a = self._act
        self.act_generate = a(strings.A_GENERATE, self.generate_flow, "Ctrl+G", name="act-generate")
        self.act_check = a(strings.A_CHECK, self.check_flow, "F5", name="act-check")
        self.act_cancel_check = a(
            strings.A_CANCEL_CHECK, self.ctl.cancel_check, name="act-cancel-check"
        )
        self.act_export = a(strings.A_EXPORT, self.export_dialog_flow, "Ctrl+E", name="act-export")
        self.act_review = a(strings.A_REVIEW, partial(self.change_target, "review"), name="act-review")  # fmt: skip
        self.act_release = a(strings.A_RELEASE, partial(self.change_target, "release"), name="act-release")  # fmt: skip
        self.act_revise = a(strings.A_REVISE, partial(self.change_target, "revise"), name="act-revise")  # fmt: skip
        self.act_values = a(strings.A_VALUES, self.values_flow, name="act-values")
        self.act_new_interface = a(
            strings.A_NEW_INTERFACE, self.new_interface_flow, "Ctrl+I", name="act-new-interface"
        )
        self.act_reset_layout = a(
            strings.A_RESET_LAYOUT, self.reset_layout, name="act-reset-layout"
        )
        self.act_next_pane = a(strings.A_NEXT_PANE, partial(self._cycle, 1), "F6", name="act-next-pane")  # fmt: skip
        self.act_prev_pane = a(strings.A_PREV_PANE, partial(self._cycle, -1), "Shift+F6", name="act-prev-pane")  # fmt: skip
        self.go_actions: dict[str, QAction] = {}
        for k, (name, label) in enumerate(
            zip(
                MAIN_TABS,
                (
                    strings.A_GO_DIAGRAM,
                    strings.A_GO_HARNESS,
                    strings.A_GO_LISTS,
                    strings.A_GO_CHECKS,
                    strings.A_GO_RELEASES,
                ),  # fmt: skip
                strict=True,
            ),
            start=1,
        ):
            self.go_actions[name] = a(label, partial(self._go_tab, name), f"Ctrl+{k}", name=f"act-go-{name}")  # fmt: skip
        # File > Import: the existing dialog for interfaces, the wizard for the other kinds
        self.import_actions: dict[str, QAction] = {}
        for kind in KINDS:
            if kind.key == "interfaces":
                continue
            self.import_actions[kind.key] = a(
                f"{strings.A_IMPORT_PREFIX} {_lower_first(kind.title)}…",
                partial(self.import_wizard_flow, kind.key),
                name=f"act-import-{kind.key}",
            )
            self.import_actions[kind.key].setToolTip(kind.summary)
        self.act_import.setToolTip(strings.IMP_KIND_INTERFACES_TIP)

    # ---- canvas actions: selection, layout, navigation (one block, for the lead to merge) -----------
    def _build_canvas_actions(self) -> None:
        a, v = self._act, self.view
        self.act_select_all = a(
            strings.A_SELECT_ALL, self.ctl.select_all, "Ctrl+A", name="act-select-all", only_in=(v,)
        )
        self.act_duplicate = a(
            strings.A_DUPLICATE, self.duplicate_flow, "Ctrl+D", name="act-duplicate", only_in=(v,)
        )
        self.act_find = a(
            strings.A_FIND, v.search.open_bar, "Ctrl+F", name="act-find", only_in=(v,)
        )
        self.act_zoom_100 = a(strings.A_ZOOM_100, v.zoom_100, "Ctrl+0", name="act-zoom-100")
        self.act_zoom_selection = a(
            strings.A_ZOOM_SELECTION,
            v.zoom_to_selection,
            "Shift+F",
            name="act-zoom-selection",
            only_in=(v,),
        )
        self.act_legend = a(
            strings.A_LEGEND, self._toggle_legend, checkable=True, name="act-legend"
        )
        self.act_legend.setChecked(True)
        self.act_snap = a(strings.A_SNAP, self._toggle_snap, checkable=True, name="act-snap")
        self.act_snap.setChecked(True)
        self.align_actions: dict[str, QAction] = {}
        for mode, label in strings.ALIGN_NAMES.items():
            act = a(label, partial(self.align_flow, mode), name=f"act-align-{mode}")
            self.align_actions[mode] = act
        self.distribute_actions: dict[str, QAction] = {}
        for axis, label in strings.DISTRIBUTE_NAMES.items():
            act = a(label, partial(self.distribute_flow, axis), name=f"act-distribute-{axis}")
            self.distribute_actions[axis] = act
        for act, tip in (
            (self.act_select_all, strings.SELECT_ALL_TIP),
            (self.act_find, strings.FIND_TIP),
            (self.act_fit, strings.FIT_TIP),
            (self.act_zoom_100, strings.ZOOM_100_TIP),
            (self.act_zoom_selection, strings.ZOOM_SELECTION_TIP),
            (self.act_arrange, strings.ARRANGE_TIP),
        ):
            act.setToolTip(tip)
        v.menu_actions = {
            "delete": self.act_delete,
            "duplicate": self.act_duplicate,
            "redundant": self.act_redundant,
            "select_all": self.act_select_all,
            "find": self.act_find,
            "fit": self.act_fit,
            "zoom100": self.act_zoom_100,
            "zoom_selection": self.act_zoom_selection,
            "arrange": self.act_arrange,
            "distribute_h": self.distribute_actions["horizontal"],
            "distribute_v": self.distribute_actions["vertical"],
            **{f"align_{m}": act for m, act in self.align_actions.items()},
        }

    def _unit_heights(self) -> dict[str, float]:
        """The heights the units are drawn at now (Guided and Expert differ)."""
        return {uid: it.height() for uid, it in self.view.dscene.unit_items.items()}

    def align_flow(self, mode: str) -> None:
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        self.ctl.align_selected(mode, self._unit_heights())

    def distribute_flow(self, axis: str) -> None:
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        self.ctl.distribute_selected(axis, self._unit_heights())

    def duplicate_flow(self) -> None:
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        made = self.ctl.duplicate_selected()
        if made:
            self.view.focus_unit(made[-1])

    def arrange_flow(self) -> None:
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        project = self.ctl.project
        if len(project.units) > ARRANGE_IN_WORKER:  # a big diagram takes a second or more
            token = self.ctl.state_token
            worker = ArrangeWorker(edit.clone_with(project, []))
            self._run_worker(worker, strings.ARRANGING, "arrange-progress")
            if worker.ops is None:
                self.toasts.show_message(strings.GEN_FAILED.format(worker.error or ""), None)
                return
            if token != self.ctl.state_token:
                self.toasts.show_message(strings.CHANGES_DURING_JOB, None)
                return
            ops = worker.ops
        else:
            ops = edit.ops_arrange(project)
        if not ops:
            self.toasts.show_message(strings.ARRANGE_NOTHING, None)
            return
        self.ctl.run(strings.ARRANGE_LABEL, ops, message=strings.ARRANGE_DONE)

    def guide_flow(self) -> None:
        path = guide_path()
        if path is None:
            self.toasts.show_message(strings.GUIDE_MISSING, None)
            return
        self.open_url(QUrl.fromLocalFile(str(path)))

    def _start_tour(self) -> None:
        self.tour.start()

    def _build_menus_and_toolbar(self) -> None:
        mb = self.menuBar()
        f = mb.addMenu(strings.M_FILE)
        for act in (self.act_new, self.act_new_example, self.act_open, self.act_sample):
            f.addAction(act)
        f.addSeparator()
        for act in (self.act_save, self.act_save_as):
            f.addAction(act)
        self.menu_import = f.addMenu(strings.M_IMPORT)
        self.menu_import.addAction(self.act_import)
        for act in self.import_actions.values():
            self.menu_import.addAction(act)
        f.addAction(self.act_export)
        f.addSeparator()
        f.addAction(self.act_quit)
        e = mb.addMenu(strings.M_EDIT)
        for act in (
            self.act_undo,
            self.act_redo,
            self.act_select_all,
            self.act_duplicate,
            self.act_delete,
            self.act_redundant,
            self.act_find,
        ):
            e.addAction(act)
        e.addSeparator()
        e.addAction(self.act_new_interface)
        e.addAction(self.act_connect_tool)
        align_menu = e.addMenu(strings.A_ALIGN)
        for act in self.align_actions.values():
            align_menu.addAction(act)
        spread_menu = e.addMenu(strings.A_DISTRIBUTE)
        for act in self.distribute_actions.values():
            spread_menu.addAction(act)
        e.addAction(self.act_add_zone)
        e.addAction(self.act_wire_colours)
        self.menu_add = e.addMenu(strings.M_ADD_UNIT)
        for tid, tpl in edit.TEMPLATES.items():
            act = self._act(tpl.label, partial(self._add_unit, tid), name=f"menu-add-{tid}")
            self.menu_add.addAction(act)
        self.menu_connect = e.addMenu(strings.M_CONNECT_WITH)
        self._rebuild_connect_menu()
        v = mb.addMenu(strings.M_VIEW)
        v.addAction(self.act_guided)
        v.addAction(self.act_expert)
        v.addSeparator()
        theme_menu = v.addMenu(strings.A_THEME)
        for act in self.theme_actions.values():
            theme_menu.addAction(act)
        v.addAction(self.act_minimap)
        v.addAction(self.act_legend)
        v.addAction(self.act_snap)
        v.addAction(self.act_labels)
        scale_menu = v.addMenu(strings.A_SCALE)
        for act in self.scale_actions.values():
            scale_menu.addAction(act)
        v.addSeparator()
        for act in (
            self.act_zoom_in,
            self.act_zoom_out,
            self.act_fit,
            self.act_zoom_100,
            self.act_zoom_selection,
            self.act_arrange,
        ):
            v.addAction(act)
        v.addSeparator()
        for dock in (self.dock_left, self.dock_right, self.dock_bottom):
            v.addAction(dock.toggleViewAction())
        v.addAction(self.act_reset_layout)
        d = mb.addMenu(strings.M_DESIGN)
        self.menu_design = d
        for act in (self.act_generate, self.act_check, self.act_cancel_check, self.act_export):
            d.addAction(act)
        d.addSeparator()
        for act in (self.act_review, self.act_release, self.act_revise):
            d.addAction(act)
        d.addSeparator()
        d.addAction(self.act_values)
        g = mb.addMenu(strings.M_GO)
        self.menu_go = g
        for act in self.go_actions.values():
            g.addAction(act)
        g.addSeparator()
        g.addAction(self.act_next_pane)
        g.addAction(self.act_prev_pane)
        h = mb.addMenu(strings.M_HELP)
        for act in (
            self.act_guide,
            self.act_commands,
            self.act_tour,
            self.act_glossary,
            self.act_issues,
            self.act_about,
        ):
            h.addAction(act)

        tb = self.addToolBar(strings.TOOLBAR)
        tb.setObjectName("main-toolbar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.act_undo.setIcon(icon("undo", self.theme))
        self.act_redo.setIcon(icon("redo", self.theme))
        self.act_redo.setToolTip(tooltip_text(strings.REDO, "Ctrl+Y"))
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)
        for act in (self.act_undo, self.act_redo):  # reachable with Tab, not only by shortcut
            button = tb.widgetForAction(act)
            if button is not None:
                button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        tb.addSeparator()
        self.mode_guided = QToolButton()
        self.mode_guided.setObjectName("mode-guided")
        self.mode_guided.setText(strings.GUIDED)
        self.mode_guided.setCheckable(True)
        self.mode_guided.setProperty("toggle", True)
        self.mode_guided.setChecked(True)
        self.mode_guided.setToolTip(strings.GUIDED_TIP)
        self.mode_expert = QToolButton()
        self.mode_expert.setObjectName("mode-expert")
        self.mode_expert.setText(strings.EXPERT)
        self.mode_expert.setCheckable(True)
        self.mode_expert.setProperty("toggle", True)
        self.mode_expert.setToolTip(strings.EXPERT_TIP)
        self.mode_guided.clicked.connect(lambda: self._pick_mode("guided"))
        self.mode_expert.clicked.connect(lambda: self._pick_mode("expert"))
        tb.addWidget(self.mode_guided)
        tb.addWidget(self.mode_expert)
        tb.addSeparator()
        self.arrange_btn = QToolButton()
        self.arrange_btn.setObjectName("arrange-button")
        self.arrange_btn.setDefaultAction(self.act_arrange)
        self.arrange_btn.setText(strings.A_ARRANGE)
        self.arrange_btn.setToolTip(strings.ARRANGE_TIP)
        self.arrange_btn.setAccessibleName(strings.A_ARRANGE)
        tb.addWidget(self.arrange_btn)
        tb.addSeparator()
        self.search_btn = QPushButton(strings.SEARCH_BUTTON)
        self.search_btn.setObjectName("search-button")
        icon_button(
            self.search_btn,
            "search",
            self.theme,
            strings.A_COMMANDS,
            "Ctrl+K",
            text=strings.SEARCH_BUTTON,
        )
        self.search_btn.clicked.connect(self.open_commands)
        tb.addWidget(self.search_btn)
        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("filter-kind")
        self.filter_combo.setAccessibleName(strings.FILTER_LABEL)
        self.filter_combo.setToolTip(strings.FILTER_TIP)
        for label, kind in (
            (strings.FILTER_ALL, None),
            (strings.FILTER_CLASS, "class"),
            (strings.FILTER_CONNECTOR, "connector"),
            (strings.FILTER_BUNDLE, "bundle"),
        ):
            self.filter_combo.addItem(label, kind)
        self.filter_combo.currentIndexChanged.connect(self._filter_kind_changed)
        tb.addWidget(self.filter_combo)
        self.filter_value = QComboBox()
        self.filter_value.setObjectName("filter-value")
        self.filter_value.setAccessibleName(strings.FILTER_VALUE)
        self.filter_value.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.filter_value.currentIndexChanged.connect(self._filter_changed)
        self.filter_value_action = tb.addWidget(self.filter_value)
        self.filter_value_action.setVisible(False)  # a toolbar widget is shown through its action
        self._decorate_tooltips()

    def _decorate_tooltips(self) -> None:
        """Every action that has a shortcut says it in its tooltip: "text (shortcut)"."""
        for act, tip in (
            (self.act_generate, strings.GENERATE_TIP),
            (self.act_check, strings.TB_CHECK_TIP),
            (self.act_export, strings.TB_EXPORT_TIP),
            (self.act_reset_layout, strings.A_RESET_LAYOUT_TIP),
            (self.act_values, strings.A_VALUES_TIP),
        ):
            act.setToolTip(tip)
        for act in self.actions():
            key = act.shortcut().toString()
            if key and act.text().strip() and f"({key})" not in act.toolTip():
                act.setToolTip(tooltip_text(act.toolTip(), key))

    def _filter_options(self, kind: str) -> list[tuple[str, str]]:
        """(label, value) pairs for the second filter picker."""
        p = self.ctl.project
        if kind == "class":
            return [(i["label"], key) for key, i in CATEGORIES.items()]
        if kind == "connector":
            used = sorted(
                {
                    e.connector_id
                    for i in p.interfaces.values()
                    for e in i.endpoints
                    if e.connector_id
                }
            )
            return [(f"{c}  ({p.connectors[c].name})" if c in p.connectors else c, c) for c in used]
        return [
            (f"{h.id}  {h.name}", h.id) for h in sorted(p.harnesses.values(), key=lambda x: x.id)
        ]

    def _refresh_filter_values(self) -> None:
        kind = self.filter_combo.currentData()
        keep = self.filter_value.currentData()
        if kind:
            wanted = self._filter_options(kind)
            have = [
                (self.filter_value.itemText(k), self.filter_value.itemData(k))
                for k in range(self.filter_value.count())
            ]
            if wanted == have:
                return  # nothing to rebuild (edits are frequent)
        self.filter_value.blockSignals(True)
        self.filter_value.clear()
        if kind:
            for label, value in self._filter_options(kind):
                self.filter_value.addItem(label, value)
            at = self.filter_value.findData(keep)
            self.filter_value.setCurrentIndex(max(at, 0))
        self.filter_value.blockSignals(False)
        self.filter_value_action.setVisible(bool(kind) and self.filter_value.count() > 0)

    def _filter_kind_changed(self, _index: int) -> None:
        self._refresh_filter_values()
        self._filter_changed(0)

    def _filter_changed(self, _index: int) -> None:
        kind = self.filter_combo.currentData()
        self.view.dscene.set_filter(kind, self.filter_value.currentData() if kind else None)

    def _rebuild_connect_menu(self) -> None:
        for old in self.menu_connect.actions():  # `_act` also registered them on the window
            self.removeAction(old)
            old.deleteLater()
        self.menu_connect.clear()
        for tid, t in sorted(self.ctl.project.interface_types.items()):
            act = self._act(t.name, partial(self._toggle_connect, tid), name=f"menu-connect-{tid}")
            act.setIcon(category_icon(t.category, self.theme))
            self.menu_connect.addAction(act)

    def _tour_reveals(self) -> dict[str, Callable[[], None]]:
        """The steps about the palette and the interface types need the Palette tab in front."""

        def palette() -> None:
            self.left_tabs.setCurrentIndex(self.left_tabs.index_of("palette"))

        return {"palette": palette, "types": palette}

    def _tour_targets(self) -> dict[str, QWidget]:
        return {
            "palette": self.left_tabs,
            "canvas": self.view,
            "types": self.left_tabs,
            "bottom": self.tabs,
            "generate": self.generate_btn,
        }

    # ---- state reactions ---------------------------------------------------------------------
    def _on_message(self, text: str, undoable: bool) -> None:
        revision = self.ctl.history.revision

        def undo_that_change() -> None:
            # the toast's Undo is for the change it reports; once anything else happened it must
            # not undo something the user did not mean to undo
            if self.ctl.history.revision == revision:
                self.ctl.undo()
            else:
                self.toasts.show_message(strings.UNDO_STALE, None)

        if not undoable:
            if text == strings.GEN_STALE:  # a plan made for an older design: it stays until redone
                self._job_failed(text, retry=self.generate_flow)
                return
            hid = refusal_harness(text)
            if hid is not None:  # a refusal because of a release: it says how to go on
                self.toasts.show_message(
                    text,
                    None,
                    0,
                    action=(strings.BN_START_REVISION, partial(self.change_flow, "revise", hid)),
                )
                return
        else:
            self.toasts.clear_persistent()  # a change went through: old refusals are history
        self.toasts.show_message(text, undo_that_change if undoable else None)

    def _on_state(self) -> None:
        c = self.ctl
        ro = c.read_only
        self.setWindowTitle(f"{c.title} — {strings.APP_TITLE}")
        self.act_undo.setEnabled(c.history.can_undo and not ro)
        self.act_redo.setEnabled(c.history.can_redo and not ro)
        self.act_save.setEnabled(not ro)
        self.act_import.setEnabled(not ro)
        for act in self.import_actions.values():
            act.setEnabled(not ro)
        self.act_new_interface.setEnabled(not ro)
        self.act_generate.setEnabled(not ro)
        self.act_wire_colours.setEnabled(not ro)
        unsaved = strings.UNSAVED if c.autosaves else strings.UNSAVED_NO_JOURNAL
        self.status_saved.setText(unsaved if c.dirty else strings.ALL_SAVED)
        self._refresh_undo_actions()
        self._update_banner()
        self._update_selection_actions()
        self._update_view_actions()
        self.act_cancel_check.setEnabled(c.drc_busy())
        # a newly opened project is read at once; an edit waits for the pause (hashing takes time)
        opened = self._facts_token is None or self._facts_token[0] != c.state_token[0]
        self._show_status(path=True, compute=opened)
        self._hash_timer.start()
        self._update_tab_badges()

    def _refresh_undo_actions(self) -> None:
        """ "Undo Move PDU2" / "Redo Move PDU2": the menu says which step it would run."""
        h = self.ctl.history
        undo_label, redo_label = h.next_undo_label, h.next_redo_label
        self.act_undo.setText(strings.UNDO_LABELLED.format(undo_label) if undo_label else strings.UNDO)  # fmt: skip
        self.act_redo.setText(strings.REDO_LABELLED.format(redo_label) if redo_label else strings.REDO)  # fmt: skip
        blocked = h.undo_blocked  # a disabled Undo must say why
        self.act_undo.setToolTip(blocked or tooltip_text(self.act_undo.text(), "Ctrl+Z"))
        self.act_redo.setToolTip(tooltip_text(self.act_redo.text(), "Ctrl+Y"))

    def _quit(self) -> None:
        self.close()

    def _save_copy(self) -> None:
        self.save_as_flow()

    def _save_copy_noop(self) -> None:
        self.save_flow()

    def _update_banner(self) -> None:
        c = self.ctl
        if c.read_only:
            self.banner.show_message(strings.BANNER_READ_ONLY, strings.SAVE_COPY, self._save_copy)
        elif c.project.recovered:
            self.banner.show_message(
                strings.BANNER_RECOVERED, strings.SHOW_DETAILS, self.issues_flow
            )
        elif c.sample:
            self.banner.show_message(strings.BANNER_SAMPLE, strings.SAVE_COPY, self._save_copy)
        else:
            self.banner.hide()

    def _update_tab_badges(self) -> None:
        if self.ctl.findings_are_many():
            self._badge_timer.start()  # counting tens of thousands of findings waits for the redraw
        else:
            self._apply_tab_badges()

    def _apply_tab_badges(self) -> None:
        errors, warnings = self.problems.counts()
        label = strings.PROBLEMS + (f" ({errors + warnings})" if errors + warnings else "")
        self.tabs.setTabText(0, label)
        n = len(self.ctl.todos())
        self.tabs.setTabText(1, f"{strings.TODO} ({n})" if n else strings.TODO)

    def _update_hash(self) -> None:
        """Read the model hash and the plan and output states now (cached by model state: the
        hashing of a big design takes a moment, so it runs once per state, after a short pause)
        and show them in the top bar, the banner and the status bar."""
        p = self.ctl.project
        self.status_counts.setText(
            strings.STATUS_COUNTS_NOHASH.format(
                strings.units_text(len(p.units)), strings.interfaces_text(len(p.interfaces))
            )
        )
        self._show_status(path=False)

    def _status_facts(self, compute: bool = True) -> tuple[str, str, str]:
        """(short model hash, generation status, outputs state) for the current model state.
        With `compute` False the last reading is returned as it is (an edit must not wait for a
        hash; the pause timer reads it a moment later)."""
        c = self.ctl
        key = (c.state_token, str(c.root), self._outputs_epoch)
        if key == self._facts_key or not compute:
            return self._facts
        started = time.perf_counter()
        try:
            digest = model_hash(c.project)[:8]
        except (
            ValueError,
            HarnessError,
        ):  # text that cannot be encoded: the save says so, the hash is a label
            digest = "--------"
        try:
            generation = c.generation_status()
        except (ValueError, HarnessError):
            generation = "none"
        try:
            outputs = c.outputs_state()
        except (ValueError, HarnessError, OSError):
            outputs = "none"
        self._facts_key, self._facts = key, (digest, generation, outputs)
        self._facts_token = c.state_token
        self._facts_ms = (time.perf_counter() - started) * 1000
        # a slow design waits longer before the next reading (4x what this one cost, 250 ms to 2 s)
        self._hash_timer.setInterval(int(min(2000, max(250, 4 * self._facts_ms))))
        return self._facts

    def shell_status(self, compute: bool = True) -> ShellStatus:
        """What the top bar, the banner and the status bar show now."""
        c = self.ctl
        digest, generation, outputs = self._status_facts(compute)
        record = c.project.generation
        return ShellStatus(
            name=c.project.meta.name,
            model_hash=digest,
            dirty=c.dirty,
            read_only=c.read_only,
            generation=generation,
            outputs=outputs,
            running=self.busy,
            checking=c.drc_busy(),
            has_harnesses=bool(c.project.harnesses),
            generated_at=record.input_hash[:8] if record is not None else "",
        )

    def _show_status(self, *, path: bool, compute: bool = True) -> None:
        """Push the status into the top bar, the banner and the status bar."""
        status = self.shell_status(compute)
        self.topbar.apply(status)
        self.status_hash.setText(status.model_hash)
        if status.generated_at:
            self.status_generated.setText(strings.STATUS_GENERATED.format(status.generated_at))
            self.status_generated.setToolTip(strings.STATUS_GENERATED_TIP)
        else:
            self.status_generated.setText(strings.STATUS_NOT_GENERATED)
            self.status_generated.setToolTip(strings.STATUS_NOT_GENERATED_TIP)
        if path:
            root = self.ctl.root
            if root is not None:
                self.status_path.set_full_text(str(root))
            else:
                self.status_path.set_full_text(
                    strings.STATUS_PATH_SAMPLE if self.ctl.sample else strings.STATUS_PATH_NONE
                )
        self._update_alerts(status)

    def _update_alerts(self, status: ShellStatus) -> None:
        """The persistent notice when the plans or the exported files no longer match the design:
        it stays (hidden only by the person, until the design changes again) and carries the
        buttons that fix it."""
        plans = status.generation == "stale"
        files = status.has_harnesses and status.outputs in ("stale", "modified", "unreadable")
        key = (plans, files, status.model_hash)
        if self.ctl.read_only or not (plans or files) or self._dismissed_alert == key:
            self.alerts.clear("stale")
            return
        if plans and files:
            text = strings.BN_BOTH_STALE
        elif plans:
            text = strings.BN_PLANS_STALE
        else:
            text = strings.BN_OUTPUTS_STALE
        details = [
            strings.BN_DETAIL_GENERATED.format(status.generated_at)
            if status.generated_at
            else strings.BN_DETAIL_NOT_GENERATED
        ]
        actions: list[tuple[str, Callable[[], None]]] = []
        if plans:
            actions.append((strings.BN_GENERATE, self.act_generate.trigger))
        if files:
            actions.append((strings.BN_EXPORT, self.act_export.trigger))
            if plans:
                details.append(strings.BN_DETAIL_ORDER)
        self.alerts.show_banner("stale", "warning", text, details=details, actions=actions)

    def _alert_dismissed(self, key: str) -> None:
        if key == "stale":
            status = self.shell_status()
            self._dismissed_alert = (
                status.generation == "stale",
                status.has_harnesses and status.outputs in ("stale", "modified", "unreadable"),
                status.model_hash,
            )

    def _job_failed(self, message: str, *, retry: Callable[[], None] | None = None) -> None:
        """A generate or export that did not finish: a banner that stays until the next success
        (or until it is dismissed), not a message that fades. The words also go to the log of
        messages (`toasts.messages`) so nothing is told twice on screen."""
        self.toasts.record(message)
        self.alerts.show_banner(
            "job",
            "error",
            message,
            actions=[(strings.BN_RETRY, retry)] if retry is not None else [],
        )

    def _job_succeeded(self) -> None:
        self.alerts.clear("job")

    def _on_changed(self, delta: Delta) -> None:
        if self.filter_combo.currentData():  # connectors and harnesses come and go (generate, undo)
            before = self.filter_value.currentData()
            self._refresh_filter_values()
            if delta.full or self.filter_value.currentData() != before:
                self._filter_changed(0)
        if set(self.ctl.project.interface_types) != {
            a.objectName().removeprefix("menu-connect-") for a in self.menu_connect.actions()
        }:
            self._rebuild_connect_menu()
        self._update_tab_badges()
        self._update_selection_actions()
        p = self.ctl.project  # the counts follow every edit at once; only the hash waits
        self.status_counts.setText(
            strings.STATUS_COUNTS_NOHASH.format(
                strings.units_text(len(p.units)), strings.interfaces_text(len(p.interfaces))
            )
        )
        self.status_hash.setText("…")
        self.topbar.hash_label.setText("…")

    def _on_selection(self) -> None:
        c = self.ctl
        s = c.selection
        if len(c.selected) > 1:
            self.status_sel.setText(strings.SELECTED_MANY.format(len(c.selected)))
        else:
            self.status_sel.setText(strings.SELECTED.format(s.id) if s else strings.NOTHING_SEL)
        if s is not None and s.kind == "unit":
            self.view.reveal(s.id)
        if s is not None and not self.dock_right.isVisibleTo(self) and not self._told_properties:
            self._told_properties = True
            self.toasts.show_message(strings.PROPERTIES_HIDDEN, None)
        self._update_selection_actions()

    def _update_selection_actions(self) -> None:
        c = self.ctl
        s, chosen = c.selection, c.selected
        units = [u for u in c.selected_ids("unit") if u in c.project.units]
        ro = c.read_only
        can_red = bool(
            s
            and len(chosen) == 1
            and s.kind == "unit"
            and s.id in c.project.units
            and c.project.units[s.id].side != "redundant"
            and f"{s.id}-R" not in c.project.units
        )
        self.redundant_btn.setEnabled(can_red and not ro)
        self.act_redundant.setEnabled(can_red and not ro)
        self.delete_btn.setEnabled(bool(s) and not ro)
        self.act_delete.setEnabled(bool(s) and not ro)
        self.act_duplicate.setEnabled(bool(units) and not ro)
        self.act_select_all.setEnabled(bool(c.project.units))
        for act in self.align_actions.values():
            act.setEnabled(len(units) >= 2 and not ro)
        for act in self.distribute_actions.values():
            act.setEnabled(len(units) >= 3 and not ro)
        # a disabled control must say why
        if ro:
            why_red = why_del = why_dup = why_align = why_spread = strings.WHY_READ_ONLY
        else:
            why_del = "" if s else strings.WHY_NO_SELECTION
            why_dup = "" if units else strings.WHY_NEED_UNIT_SELECTED
            why_align = "" if len(units) >= 2 else strings.WHY_NEED_TWO_UNITS
            why_spread = "" if len(units) >= 3 else strings.WHY_NEED_THREE_UNITS
            if len(chosen) > 1 or not (s and s.kind == "unit" and s.id in c.project.units):
                why_red = strings.WHY_SELECT_UNIT
            elif c.project.units[s.id].side == "redundant":
                why_red = strings.WHY_IS_REDUNDANT
            elif f"{s.id}-R" in c.project.units:
                why_red = strings.WHY_HAS_REDUNDANT.format(f"{s.id}-R")
            else:
                why_red = ""
        self.redundant_btn.setToolTip(why_red or strings.REDUNDANT_TIP)
        self.act_redundant.setToolTip(why_red or strings.REDUNDANT_TIP)
        self.delete_btn.setToolTip(why_del or strings.DELETE_TIP)
        self.act_delete.setToolTip(why_del or strings.DELETE_TIP)
        self.act_duplicate.setToolTip(
            why_dup or tooltip_text(strings.DUPLICATE_TIP, self.act_duplicate.shortcut().toString())
        )
        for act in self.align_actions.values():
            act.setToolTip(why_align or act.text())
        for act in self.distribute_actions.values():
            act.setToolTip(why_spread or act.text())

    def _on_connect(self) -> None:
        c = self.ctl
        self.tool_select.setChecked(c.tool == "select")
        self.tool_connect.setChecked(c.tool == "connect")
        hint, warn = c.connect_hint_and_warning()
        self.hint.setText(hint)
        # reserve two lines so a long hint never makes the toolbar jump
        self.hint.setMinimumHeight(self.hint.fontMetrics().lineSpacing() * 2 + 4)
        self.hint.setProperty("error", warn)
        self.hint.style().unpolish(self.hint)
        self.hint.style().polish(self.hint)
        self.view.viewport().update()

    def _pick_mode(self, mode: str) -> None:
        self.ctl.set_mode(mode)
        self._on_mode()  # a click on the active button must not leave both unchecked

    def _on_mode(self) -> None:
        self.mode_guided.setChecked(self.ctl.mode == "guided")
        self.mode_expert.setChecked(self.ctl.mode == "expert")
        self.act_guided.setChecked(self.ctl.mode == "guided")
        self.act_expert.setChecked(self.ctl.mode == "expert")
        self.settings.setValue("ui/mode", self.ctl.mode)
        self._on_connect()

    # ---- editing flows -----------------------------------------------------------------------
    def _add_unit(self, template_id: str) -> None:
        uid = self.ctl.add_unit(template_id)
        if uid:
            self.view.focus_unit(uid)

    def _toggle_connect(self, type_id: str) -> None:
        if type_id not in self.ctl.project.interface_types:  # for example a stale palette entry
            self.toasts.show_message(strings.UNKNOWN_INTERFACE_TYPE.format(type_id), None)
            return
        if self.ctl.tool == "connect" and self.ctl.connect_type == type_id:
            self.ctl.end_connect()
        else:
            self.ctl.begin_connect(type_id)

    def _redundant_selected(self) -> None:
        s = self.ctl.selection
        if s and s.kind == "unit":
            self.ctl.redundant_copy(s.id)

    def delete_flow(self) -> None:
        """Delete what is selected, after saying what else goes with it."""
        c = self.ctl
        chosen = c.selected
        if not chosen:
            return
        if c.read_only:
            c.refuse_read_only()
            return
        project = c.project
        units = [u for u in c.selected_ids("unit") if u in project.units]
        links = [i for i in c.selected_ids("interface") if i in project.interfaces]
        # a unit that cannot be deleted, or a link that cannot: the edit itself says why
        if any(c.delete_impact(u).blocked_by_harnesses for u in units) or any(
            edit.interface_impact(project, i).blocked_by_harnesses for i in links
        ):
            c.delete_selected()
            return
        if len(chosen) == 1 and units:
            impact = c.delete_impact(units[0])
            ifs = ", ".join(f"<b>{i}</b>" for i in impact.interfaces)
            body = strings.DELETE_BODY.format(
                n=len(impact.interfaces),
                s="" if len(impact.interfaces) == 1 else "s",
                ifs=f": {ifs}" if ifs else "",
                c=len(impact.connectors),
            )
            title = strings.DELETE_TITLE.format(units[0])
        elif len(chosen) == 1:
            title, body = self._interface_delete_text(links[0])
        else:
            title, body = self._many_delete_text(units, links)
        dlg = ConfirmDialog(self, title, body, strings.DELETE)
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return
        c.delete_selected()

    def _plan_lines(self, interface_ids: list[str]) -> str:
        """For the delete question: the generated harnesses whose wires belong to these links."""
        wires: dict[str, int] = {}
        for iid in interface_ids:
            for hid, n in edit.interface_impact(self.ctl.project, iid).plan_wires.items():
                wires[hid] = wires.get(hid, 0) + n
        return "".join(strings.DELETE_IF_PLAN.format(h=h, n=n) for h, n in sorted(wires.items()))

    def _interface_delete_text(self, iid: str) -> tuple[str, str]:
        impact = edit.interface_impact(self.ctl.project, iid)
        a, b = (impact.ends + ("?", "?"))[:2]
        body = strings.DELETE_IF_BODY.format(
            iid=iid, type=impact.type_name, a=a, b=b, plans=self._plan_lines([iid])
        )
        return strings.DELETE_IF_TITLE.format(iid), body

    def _many_delete_text(self, units: list[str], links: list[str]) -> tuple[str, str]:
        project = self.ctl.project
        gone = {i for u in units for i in self.ctl.delete_impact(u).interfaces}
        every = sorted(gone | set(links))
        items = "".join(
            f"<li><b>{u}</b> (unit {project.units[u].name})</li>" for u in sorted(units)
        )
        for iid in sorted(set(links) - gone):
            impact = edit.interface_impact(project, iid)
            items += f"<li><b>{iid}</b> ({impact.type_name}, {' to '.join(impact.ends)})</li>"
        if gone:
            items += f"<li>{strings.interfaces_text(len(gone))} of the units: {', '.join(sorted(gone))}</li>"
        n = len(self.ctl.selected)
        return strings.DELETE_MANY_TITLE.format(n), strings.DELETE_MANY_BODY.format(
            items=items, plans=self._plan_lines(every)
        )

    # ---- opening the plans from the diagram ---------------------------------------------------------
    def _harness_for(self, kind: str, ident: str) -> tuple[str, str | None] | None:
        """(harness, wire) that show a unit or a link in the plans, or None if none does."""
        project = self.ctl.project
        if kind == "interface":
            for hid in sorted(project.harnesses):
                h = project.harnesses[hid]
                wires = sorted(w.id for w in h.wires if w.interface_id == ident)
                if wires or ident in h.interfaces:
                    return hid, (wires[0] if wires else None)
            return None
        mine = {c.id for c in edit.unit_connectors(project, ident)}
        links = {
            i.id
            for i in project.interfaces.values()
            if any(e.unit_id == ident for e in i.endpoints)
        }
        for hid in sorted(project.harnesses):
            h = project.harnesses[hid]
            box_of = {c.id: c.mates_with for c in h.connectors}
            for w in sorted(h.wires, key=lambda x: x.id):
                ends = (w.from_connector, w.to_connector)
                if w.interface_id in links or any(e in mine or box_of.get(e) in mine for e in ends):
                    return hid, w.id
        return None

    def _open_requested(self, kind: str, ident: str) -> None:
        """Double-click or Enter on a unit or link: show it in the harness plans."""
        found = self._harness_for(kind, ident)
        if found is None:
            self.toasts.show_message(
                strings.NOT_GENERATED.format(ident),
                None,
                8000,
                action=(strings.GENERATE, self.generate_flow),
            )
            return
        hid, wire = found
        self.show_harness_view()
        view = self.harness_target()
        select_harness = getattr(view, "select_harness", None)
        if select_harness is not None:
            select_harness(hid)
        select_wire = getattr(view, "select_wire", None)
        select_any = getattr(view, "select", None)
        if wire and select_wire is not None:
            select_wire(wire)
        elif wire and select_any is not None:
            select_any("wire", wire)

    def harness_target(self) -> QWidget:
        """The widget that shows harnesses now: the Harness view once installed, else the plans
        panel of the bottom dock."""
        return self.view_widget("harness") if self.view_installed("harness") else self.harness_panel

    def generate_flow(self) -> None:
        if self.ctl.read_only:
            return
        self.job_error = None
        token = self.ctl.state_token
        plan = self.compute_plan()
        if plan is None:
            if self.job_error:
                self._job_failed(
                    strings.GEN_FAILED.format(self.job_error), retry=self.generate_flow
                )
            else:
                self.toasts.show_message(strings.GEN_CANCELLED, None)
            return
        if plan.empty and not self.ctl.plan_problems(plan):
            if self._apply_record_only(plan, token):
                self._job_succeeded()
            return
        accepted = self.run_dialog(GeneratePreviewDialog(self, plan)) == QDialog.DialogCode.Accepted
        if accepted and self.ctl.apply_generation(plan, token):
            self._job_succeeded()
            self.show_harness_view()

    def _apply_record_only(self, plan: GenerationPlan, token: tuple[int, int]) -> bool:
        """A plan that changes no harness. When the design did change since the last generation
        (a unit was renamed) only the record of what the plans were made from is out of date; it
        is brought up to date so the status says "up to date" and the notice goes away (the
        command line writes the record the same way)."""
        if plan.ops and plan.record != self.ctl.project.generation:
            if token != self.ctl.state_token:
                self.ctl.message.emit(strings.GEN_STALE, False)
                return False
            return self.ctl.run(
                strings.STEP_GENERATE, plan.ops, message=strings.GEN_UP_TO_DATE, undo=False
            )
        return self.ctl.apply_generation(plan, token)

    def show_harness_view(self) -> None:
        """Show the harnesses: the Harness tab once it exists, else the plans in the bottom panel."""
        if self.main_tabs.show_slot("harness"):
            return
        self.dock_bottom.show()
        self.tabs.setCurrentWidget(self.harness_panel)
        self._give_room_to(self.dock_bottom, 420)

    def _give_room_to(self, dock: QDockWidget, height: int) -> None:
        """Make a bottom dock at least `height` tall (the plans tab is unusable as a sliver)."""
        if dock.height() < height:
            self.resizeDocks([dock], [height], Qt.Orientation.Vertical)

    def _compute_plan(self) -> GenerationPlan | None:
        """Plan in a worker thread behind a cancellable progress dialog; None if cancelled."""
        worker = PlanWorker(edit.clone_with(self.ctl.project, []))
        self._run_worker(worker, strings.GEN_RUNNING, "generate-progress")
        self.job_error = worker.error
        return worker.plan

    def _run_worker(
        self, worker: "PlanWorker | OutputsWorker | ArrangeWorker", label: str, name: str
    ) -> None:
        self._set_busy(
            "generate" if isinstance(worker, PlanWorker)
            else "export" if isinstance(worker, OutputsWorker) else "arrange"
        )  # fmt: skip
        try:
            self._run_worker_loop(worker, label, name)
        finally:
            self._set_busy(None)

    def _set_busy(self, kind: str | None) -> None:
        """A job runs (or has just ended): the chip says so and the buttons wait."""
        self.busy = kind
        self.topbar.update_status(running=kind)

    def _run_worker_loop(
        self, worker: "PlanWorker | OutputsWorker | ArrangeWorker", label: str, name: str
    ) -> None:
        progress = QProgressDialog(label, strings.CANCEL, 0, 100, self)
        progress.setObjectName(name)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(400)  # quick runs never flash a dialog
        loop = QEventLoop(self)

        def on_progress(fraction: float, text: str) -> None:
            try:
                progress.setValue(int(fraction * 100))
                progress.setLabelText(text)
            except RuntimeError:  # a late progress message after the dialog is gone
                return

        worker.progressed.connect(on_progress)
        progress.canceled.connect(worker.cancel)
        worker.finished.connect(loop.quit)
        worker.start()
        loop.exec()
        worker.wait()
        with contextlib.suppress(RuntimeError, TypeError):
            worker.progressed.disconnect(on_progress)  # no late messages into a closed dialog
        progress.reset()
        progress.deleteLater()

    def _user_name(self) -> str:
        saved = str(self.settings.value("ui/user", "") or "")
        if saved:
            return saved
        try:
            import getpass

            return getpass.getuser()
        except (OSError, KeyError, ImportError):
            return ""

    def change_flow(self, action: str, hid: str) -> None:
        """Review, release, new revision, changes and change log for one harness."""
        project, today = self.ctl.project, self.ctl.today()
        folder = self.ctl.outputs_folder()
        if action == "history":
            rows = changelog_rows(project, hid)
            self.run_dialog(HistoryDialog(self, strings.HISTORY_TITLE.format(hid), rows))
            return
        if action == "changes":
            self._changes_flow(hid)
            return
        if action == "delete":
            self._delete_harness_flow(hid)
            return
        if hid not in project.harnesses:
            self.toasts.show_message(strings.NO_HARNESSES_FOR_ACTION, None)
            return
        if action == "review":
            dlg = ChangeDialog(
                self,
                strings.REVIEW_TITLE.format(hid),
                by=self._user_name(),
                blockers=[],
                ask_comment=False,
                ok_text=strings.REVIEW_CONFIRM,
            )
        elif action == "release":
            # the dialog asks for the reason itself, so a stand-in keeps that blocker out of the list
            blockers = release_blockers(
                project, hid, by="x", comment="x" * 10, when=today, outputs_folder=folder,
                accept_placeholders="x" * 10, accept_unapproved_parts="x" * 10,
            )  # fmt: skip
            dlg = ChangeDialog.for_release(
                self,
                project,
                hid,
                strings.RELEASE_TITLE.format(hid),
                by=self._user_name(),
                blockers=[b.message for b in blockers],
                placeholders=project.placeholder_configs(),
                unapproved_parts=unapproved_parts(project, project.harnesses[hid]),
            )
        else:
            dlg = ChangeDialog.for_revise(
                self, project, hid, strings.NEW_REV_TITLE.format(hid), by=self._user_name()
            )
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return
        by, checker, comment = dlg.values()
        self.settings.setValue("ui/user", by)
        if action == "review":
            plan = plan_submit_review(project, hid, by=by, when=today)
            msg = strings.REVIEW_SUBMITTED.format(hid)
        elif action == "release":
            plan = plan_release(
                project,
                hid,
                by=by,
                checker=checker or None,
                comment=comment,
                when=today,
                outputs_folder=folder,
                accept_placeholders=dlg.accepted_placeholders(),
                accept_unapproved_parts=dlg.accepted_unapproved_parts(),
            )
            msg = strings.RELEASE_DONE.format(hid)
        else:
            plan = plan_new_revision(project, hid, by=by, comment=comment, when=today)
            msg = strings.NEW_REV_STARTED.format(hid)
        if self.ctl.apply_change(plan, msg):
            self.harness_panel.refresh()

    # ---- change control on "the" harness (menu, shortcut, Ctrl+K) ----------------------------------
    def current_harness(self) -> str | None:
        """The harness the person is looking at: the Harness view's, the Releases tab's, or the
        plans table's selection; None when none is chosen."""
        project = self.ctl.project
        candidates: list[object] = []
        if self.view_installed("harness"):
            view = self.view_widget("harness")
            candidates.append(
                getattr(view, "harness_id", getattr(view, "current_harness", lambda: None))()
            )
        if self.main_tabs.currentWidget() is self.releases_panel:
            candidates.append(self.releases_panel.current_harness())
        candidates.append(self.harness_panel.selected_harness())
        candidates.append(self.releases_panel.current_harness())
        for c in candidates:
            if isinstance(c, str) and c in project.harnesses:
                return c
        return None

    def change_target(self, action: str) -> None:
        """Review, release or revise "the" harness: the one in view, else the only one that the
        step applies to; with several, the Releases tab opens so one can be chosen."""
        project = self.ctl.project
        if not project.harnesses:
            self.toasts.show_message(strings.NO_HARNESSES_FOR_ACTION, None)
            return
        allowed = {
            "review": ("draft",),
            "release": ("draft", "in_review"),
            "revise": ("released",),
        }[action]
        fit = sorted(h for h, x in project.harnesses.items() if x.status in allowed)
        chosen = self.current_harness()
        if chosen is None or chosen not in fit:
            chosen = fit[0] if len(fit) == 1 else None
        if chosen is None:
            self.go_to("releases")
            self.toasts.show_message(strings.NO_HARNESS_FOR_ACTION, None)
            return
        self.change_flow(action, chosen)

    def values_flow(self) -> None:
        """Open the engineering values (the window of the Checks tab)."""
        self.checks_panel.open_config()

    def check_flow(self) -> None:
        """Run the design rule check now; a toast says how it went when it has finished."""
        self._check_asked = True
        self.ctl.check_now()

    def _on_check_state(self) -> None:
        busy = self.ctl.drc_busy()
        self.topbar.update_status(checking=busy)
        self.act_cancel_check.setEnabled(busy)
        if self._check_asked and not busy and self.ctl.drc_current:
            self._check_asked = False
            results = self.ctl.drc_rule_results()
            summary = by_rule.summary(results)
            text = (
                strings.CHECK_FINISHED if summary.failed else strings.CHECK_FINISHED_CLEAN
            ).format(  # fmt: skip
                failed=summary.failed, unchecked=summary.not_checked + summary.pending
            )
            self.toasts.show_message(
                text, None, 8000, action=(strings.CHECK_SHOW, partial(self._go_tab, "checks"))
            )

    def show_unchecked(self, key: str = "unchecked") -> None:
        """The status-bar link: the Checks tab, filtered to the rules that could not be checked."""
        self.go_to("checks")
        self.checks_panel.set_result_filter(key)

    # ---- the main tabs ---------------------------------------------------------------------------
    def go_to(self, name: str) -> bool:
        """Show a main view: diagram, harness, lists, checks or releases. The Harness tab falls
        back to the plans panel of the bottom dock until the new view exists; Lists has no
        fallback (False and a note)."""
        if name == "harness" and not self.main_tabs.is_installed("harness"):
            self.show_harness_view()
            return True
        if self.main_tabs.show_slot(name):
            return True
        title = {"lists": strings.TAB_LISTS}.get(name, name)
        self.toasts.show_message(strings.VIEW_NOT_INSTALLED.format(title), None)
        return False

    def _go_tab(self, name: str) -> None:
        self.go_to(name)

    def _cycle(self, step: int) -> None:
        self.cycle_panes(step)

    def _update_view_actions(self) -> None:
        self.go_actions["lists"].setEnabled(self.main_tabs.is_installed("lists"))
        has = bool(self.ctl.project.harnesses)
        self.act_release.setEnabled(has and not self.ctl.read_only)
        self.act_revise.setEnabled(has and not self.ctl.read_only)
        self.act_review.setEnabled(has and not self.ctl.read_only)

    # ---- export, import, new project ----------------------------------------------------------------
    def export_dialog_flow(self) -> None:
        """Export: one dialog to choose, run and read the result (the old `export_flow` stays for
        callers that bring their own worker)."""
        dlg = ExportDialog(
            self.ctl,
            self.theme,
            self,
            settings=self.settings,
            worker_factory=self.export_worker_factory,
            ask_folder=self.ask_folder,
            opener=self.open_url,
        )
        dlg.exported.connect(self._after_export)
        dlg.failed.connect(self._export_failed)
        self.run_dialog(dlg)
        dlg.deleteLater()

    def _after_export(self, result: object) -> None:
        self._outputs_epoch += 1  # files were written: read the outputs state again
        self._job_succeeded()
        if isinstance(result, ExportResult):
            self.toasts.show_message(strings.EXPORT_DONE.format(result.count, result.stamp), None)
        self.harness_panel.refresh()
        self._update_hash()

    def _export_failed(self, reason: str) -> None:
        self._job_failed(strings.EXPORT_ERROR.format(reason), retry=self.export_dialog_flow)

    def import_wizard_flow(self, kind: str) -> None:
        """Import approved parts, segment lengths, ampacity values or a KiCad netlist."""
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        pick = self.ask_import_file
        wizard = ImportWizard(self.ctl, self.theme, self, pick_file=pick, kind=kind)
        self.run_dialog(wizard)
        wizard.deleteLater()

    def _delete_harness_flow(self, hid: str) -> None:
        h = self.ctl.project.harnesses.get(hid)
        if h is None:
            return
        body = strings.DELETE_HARNESS_BODY.format(hid, len(h.wires))
        dlg = ConfirmDialog(self, strings.DELETE_HARNESS_TITLE.format(hid), body, strings.DELETE)
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return
        try:
            ops = edit.ops_delete_harness(self.ctl.project, hid)
        except edit.EditError as exc:
            self._error(str(exc))
            return
        if self.ctl.run(
            strings.STEP_DELETE.format(hid), ops, message=strings.HARNESS_DELETED.format(hid)
        ):
            self.harness_panel.refresh()

    def _changes_flow(self, hid: str) -> None:
        project = self.ctl.project
        h = project.harnesses.get(hid)
        bases = baselines_of(project, hid)
        if h is None or not bases:
            self.toasts.show_message(strings.NO_BASELINE.format(hid), None)
            return
        revs = [b.revision for b in bases]
        dlg = DiffDialog(
            self,
            strings.CHANGES_TITLE.format(hid),
            working_diff(project, h, bases[-1]),
            revs,
            revs[-1],
        )

        def recompute() -> None:
            base = next(b for b in bases if b.revision == dlg.baseline.currentText())
            dlg.set_diff(working_diff(project, h, base))

        dlg.baseline.currentTextChanged.connect(lambda _t: recompute())
        dlg.markRequested.connect(self.ctl.set_marks)
        self.run_dialog(dlg)

    def export_flow(self) -> None:
        if self.ctl.read_only:  # the command line refuses the same two cases
            self.toasts.show_message(strings.EXPORT_READ_ONLY, None)
            return
        if self.ctl.project.recovered:
            self.toasts.show_message(strings.EXPORT_DAMAGED, None)
            return
        folder = self.ctl.outputs_folder()
        if folder is None:
            self.toasts.show_message(strings.EXPORT_SAVE_FIRST, None)
            return
        if not self.ctl.project.harnesses:
            self.toasts.show_message(strings.EXPORT_NO_HARNESSES, None)
            return
        self.job_error = None
        token = self.ctl.state_token
        result = self.compute_outputs()
        if result is None:
            if self.job_error:
                self._job_failed(
                    strings.EXPORT_ERROR.format(self.job_error), retry=self.export_flow
                )
            else:
                self.toasts.show_message(strings.EXPORT_CANCELLED, None)
            return
        if token != self.ctl.state_token:  # edited while it was being built: it describes old data
            self.toasts.show_message(strings.CHANGES_DURING_JOB, None)
            return
        built, report = result
        if not report.ok:
            body = "<br>".join(i.message for i in report.errors[:6])
            self.run_dialog(ConfirmDialog(self, strings.EXPORT, body, strings.OK, danger=False))
            self._job_failed(
                strings.EXPORT_FAILED.format(len(report.errors)), retry=self.export_flow
            )
            return
        try:
            write_outputs(self.ctl.project, folder, built)
        except (HarnessError, OSError) as exc:
            self._error(self._explain(exc, folder))
            return
        self._outputs_epoch += 1
        self._job_succeeded()
        self.harness_panel.refresh()
        self.toasts.show_message(
            strings.EXPORT_DONE.format(len(built.files), built.stamp.short), None
        )

    def _compute_outputs(self) -> "tuple[OutputSet, VerifyReport] | None":
        worker = OutputsWorker(edit.clone_with(self.ctl.project, []))
        self._run_worker(worker, strings.EXPORT_RUNNING, "export-progress")
        self.job_error = worker.error
        return (
            None
            if worker.result is None or worker.report is None
            else (worker.result, worker.report)
        )

    def waive_flow(self, finding: object) -> None:
        dlg = WaiverDialog(self, finding)  # type: ignore[arg-type]
        if self.run_dialog(dlg) == QDialog.DialogCode.Accepted:
            self.ctl.waive(finding, dlg.justification())  # type: ignore[arg-type]

    def new_interface_flow(self) -> None:
        dlg = NewInterfaceDialog(self, self.ctl.project)
        if self.run_dialog(dlg) == QDialog.DialogCode.Accepted:
            t, a, b = dlg.choice()
            self.ctl.add_interface_between(t, a, b)

    def wire_colours_flow(self) -> None:
        if self.ctl.read_only:
            return
        dlg = WireColoursDialog(self, self.ctl.project)
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return
        ops = edit.ops_set_wire_colours(self.ctl.project, dlg.colours())
        if ops and self.ctl.run(strings.WIRE_COLOURS_LABEL, ops):
            self.toasts.show_message(strings.WIRE_COLOURS_SET, None)

    def add_zone_flow(self) -> None:
        name = self.ask_text(strings.A_ADD_ZONE, strings.ZONE_NAME, "")
        if name:
            self.ctl.add_zone(name)

    def import_flow(self) -> None:
        if self.ctl.read_only:
            return
        dlg = ImportDialog(self, self.ctl.project, self.theme, self.ask_file)
        if self.run_dialog(dlg) == QDialog.DialogCode.Accepted and dlg.plan.ok_count:
            self.ctl.apply_import(dlg.plan)

    def show_object(self, object_id: str) -> None:
        place = drc.locate(self.ctl.project, object_id)
        if place is None:
            self.toasts.show_message(strings.NOTHING_TO_SHOW, None)
            return
        kind, target = place
        if kind == "harness":
            self.show_harness_view()
            select_harness = getattr(self.harness_target(), "select_harness", None)
            if select_harness is not None:
                select_harness(target)
            return
        self.main_tabs.show_slot(
            "diagram"
        )  # (from the Checks tab the object is shown on the diagram)
        self.ctl.select(kind, target)
        if kind == "unit":
            self.view.focus_unit(target)
        else:
            self.view.focus_link(target)

    def _todo_activated(self, kind: str, target: str) -> None:
        if kind == "tab":
            self.tabs.setCurrentIndex(0)
        else:
            self.show_object(target)

    def open_commands(self) -> None:
        self.run_dialog(CommandPalette(self, self.palette_entries()))

    def palette_entries(self) -> list[PaletteEntry]:
        """Everything Ctrl+K can do: every enabled action of the window with its shortcut
        (Generate, Check, Export, Release, Revise, imports, tabs, Reset layout ...), adding
        units and connecting with a type, and going to any harness, unit or interface."""
        e: list[PaletteEntry] = []
        for act in self.actions():
            if act.text() and act.isEnabled() and act.objectName().startswith(("act-", "menu-")):
                hint = act.shortcut().toString()
                e.append(PaletteEntry(act.text().replace("&", ""), act.trigger, hint))
        for tid, tpl in edit.TEMPLATES.items():
            e.append(
                PaletteEntry(f"{strings.ADD_UNIT_PREFIX} {tpl.label}", partial(self._add_unit, tid))
            )
        for tid, t in sorted(self.ctl.project.interface_types.items()):
            e.append(
                PaletteEntry(
                    f"{strings.CONNECT_PREFIX} {t.name}", partial(self._toggle_connect, tid)
                )
            )
        for hid, h in sorted(self.ctl.project.harnesses.items()):
            e.append(
                PaletteEntry(
                    f"{strings.A_GO_HARNESS_ID} {hid} ({h.name})", partial(self._go_to_harness, hid)
                )
            )
        for uid, u in sorted(self.ctl.project.units.items()):
            e.append(
                PaletteEntry(
                    f"{strings.GO_TO_UNIT} {uid} ({u.name})", partial(self.show_object, uid)
                )
            )
        for iid, i in sorted(self.ctl.project.interfaces.items()):
            e.append(
                PaletteEntry(
                    f"{strings.GO_TO_INTERFACE} {iid} ({i.name})", partial(self.show_object, iid)
                )
            )
        return e + self.palette_entries_extra

    def _go_to_harness(self, hid: str) -> None:
        self.show_harness_view()
        select_harness = getattr(self.harness_target(), "select_harness", None)
        if select_harness is not None:
            select_harness(hid)

    def glossary_flow(self) -> None:
        self.run_dialog(GlossaryDialog(self))

    def about_flow(self) -> None:
        QMessageBox.about(self, strings.A_ABOUT, strings.ABOUT_TEXT.format(__version__))

    def issues_flow(self) -> None:
        r = self._last_issues
        dlg = IssuesDialog(self, r, self.ctl.project.recovered)
        dlg.saveCopyRequested.connect(self.save_as_flow)
        self.run_dialog(dlg)

    _last_issues: list = []  # type: ignore[type-arg]

    def sample_flow(self) -> None:
        if not self._confirm_discard():
            return
        self.ctl.open_sample()

    # ---- files ------------------------------------------------------------------------------
    def _ask_folder(self, title: str) -> str | None:
        path = QFileDialog.getExistingDirectory(self, title)
        return path or None

    def _ask_text(self, title: str, label: str, default: str) -> str | None:
        text, ok = QInputDialog.getText(self, title, label, text=default)
        return text if ok and text.strip() else None

    def _ask_choice(self, title: str, text: str, buttons: list[str]) -> int:
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        created = [box.addButton(b, QMessageBox.ButtonRole.ActionRole) for b in buttons]
        box.exec()
        clicked = box.clickedButton()
        return created.index(clicked) if clicked in created else len(buttons) - 1

    def _confirm_discard(self) -> bool:
        if not self.ctl.dirty:
            return True
        choice = self.ask_choice(
            strings.UNSAVED_TITLE,
            strings.UNSAVED_BODY,
            [strings.SAVE, strings.DISCARD, strings.CANCEL],
        )
        if choice == 0:
            return self.save_flow()
        if choice == 1:  # an explicit "discard": the recovery journal must not offer it again
            self.ctl.discard_journal()
            return True
        return False

    def new_project_flow(self) -> None:
        if not self._confirm_discard():
            return
        self._new_project_dialog(None)

    def new_from_example_flow(self) -> None:
        """Start from a bundled example (the same ones as `harness new --template`): the same
        dialog, with the first example ticked."""
        from harness_design_studio.core import templates

        if not self._confirm_discard():
            return
        self._new_project_dialog(
            next((t.name for t in templates.TEMPLATES if t.name != BLANK), None)
        )

    def _new_project_dialog(self, template: str | None) -> None:
        """One dialog for folder, name and starting point (SH-18), then create and open it."""
        dlg = NewProjectDialog(
            self.theme,
            self,
            ask_folder=self.ask_folder,
            template=template or "blank",
        )
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return
        request = dlg.request()
        if request is None:
            return
        self._create_project(request)

    def _create_project(self, request: NewProjectRequest) -> None:
        from harness_design_studio.core import templates

        folder = request.folder
        try:
            if request.is_blank:
                self.ctl.new_project(folder, request.name)
            else:
                templates.create_project(folder, request.template, request.name)
        except (HarnessError, OSError, ValidationError) as exc:
            self._error(self._explain(exc, folder))
            return
        if not request.is_blank and not self.open_project(folder):
            return
        self._last_issues = []
        self.settings.setValue("project/last", str(folder))

    def open_flow(self) -> None:
        folder = self.ask_folder(strings.OPEN_FOLDER)
        if not folder:
            return
        if self._is_open_here(Path(folder)):  # nothing to replace, so nothing to discard
            self.toasts.show_message(strings.ALREADY_OPEN, None)
            return
        if self._confirm_discard():
            self.open_project(Path(folder))

    def _is_open_here(self, folder: Path) -> bool:
        root = self.ctl.root
        try:
            return root is not None and folder.exists() and root.samefile(folder)
        except OSError:
            return False

    def open_project(self, folder: Path) -> bool:
        if self._is_open_here(folder):
            self.toasts.show_message(strings.ALREADY_OPEN, None)
            return True
        try:
            result = self.ctl.open_path(folder)
        except OSError as exc:
            self._error(self._explain(exc, folder))
            return False
        except ProjectLockedError:
            choice = self.ask_choice(
                strings.LOCKED_TITLE, strings.LOCKED_BODY, [strings.OPEN_READ_ONLY, strings.CANCEL]
            )
            if choice != 0:
                return False
            try:
                result = self.ctl.open_path(folder, read_only=True)
            except HarnessError as exc:
                self._error(str(exc))
                return False
        except HarnessError as exc:
            self._error(str(exc))
            return False
        self._last_issues = result.issues
        self.settings.setValue("project/last", str(folder))
        if self.ctl.open_note:
            self.toasts.show_message(self.ctl.open_note, None, 10000)
        if self.ctl.journal_available():
            choice = self.ask_choice(
                strings.RESTORE_TITLE,
                strings.RESTORE_BODY_CHANGED
                if self.ctl.journal_base_changed()
                else strings.RESTORE_BODY,
                [strings.RESTORE, strings.DISCARD_CHANGES],
            )
            if choice == 0:
                if not self.ctl.restore_journal():
                    self.toasts.show_message(strings.RESTORE_FAILED, None, 8000)
            else:
                self.ctl.discard_journal()
        if result.has_errors and not self.ctl.project.recovered:
            self.toasts.show_message(strings.PROJECT_HAS_ERRORS, None, 8000)
        return True

    def save_flow(self) -> bool:
        try:
            self.ctl.save()
        except NeedSaveAs:
            return self.save_as_flow()
        except (HarnessError, OSError, ValueError) as exc:
            self._on_save_error(exc)
            return False
        self.toasts.show_message(strings.SAVED, None, 2500)
        return True

    def save_as_flow(self) -> bool:
        folder = self.ask_folder(strings.SAVE_AS_FOLDER)
        if not folder:
            return False
        try:
            self.ctl.save_as(Path(folder))
        except (HarnessError, OSError, ValueError) as exc:
            self._error(self._explain(exc, folder))
            return False
        self.settings.setValue("project/last", folder)
        self.toasts.show_message(strings.SAVED, None, 2500)
        return True

    def _on_save_error(self, exc: Exception) -> None:
        self._error(self._explain(exc, None))

    @staticmethod
    def _explain(exc: Exception, folder: str | Path | None) -> str:
        """An error as a sentence a person can act on (never a Python message)."""
        if isinstance(exc, HarnessError):
            return str(exc)
        if isinstance(exc, ValidationError):  # for example a project name that is too long
            return _plain(exc)
        if isinstance(exc, ValueError):  # for example a lone surrogate that cannot be encoded
            return strings.SAVE_BAD_TEXT
        where = f" in {folder}" if folder else ""
        reason = getattr(exc, "strerror", None) or strings.FOLDER_UNUSABLE
        return strings.FILE_ERROR.format(where=where, reason=reason)

    def _error(self, text: str) -> None:
        self.toasts.show_message(text, None, 10000)

    def check_disk(self) -> None:
        """Offer a safe reload when the project files changed outside the tool (e.g. a Git pull)."""
        if not self.ctl.disk_changed():
            return
        choice = self.ask_choice(
            strings.CHANGED_TITLE, strings.CHANGED_BODY, [strings.RELOAD, strings.KEEP_MINE]
        )
        if choice == 0:
            try:
                result = self.ctl.reload()
            except (HarnessError, OSError) as exc:  # for example the folder was deleted
                self.ctl.keep_mine()  # do not ask again about these files
                self._error(strings.RELOAD_FAILED.format(self._explain(exc, self.ctl.root)))
                return
            if result is not None:
                self._last_issues = result.issues
        else:
            self.ctl.keep_mine()  # the box closing re-activates the window: do not ask again
            self.toasts.show_message(strings.KEEP_MINE_NOTE, None, 8000)

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.WindowActivate:
            QTimer.singleShot(0, self.check_disk)
        return super().event(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_discard():
            event.ignore()
            return
        self.ctl.release()
        self._save_settings()
        event.accept()

    # ---- settings, theme, scale -----------------------------------------------------------------
    def _restore_settings(self) -> None:
        saved_theme = str(self.settings.value("ui/theme", "system"))
        mode_name = saved_theme if saved_theme in MODES else "system"  # default: the OS scheme
        saved_scale = self.settings.value("ui/scale")
        if saved_scale is None:  # never chosen: follow the screen (a 4K screen gets 200 %)
            scale = self._screen_scale()
        else:
            try:  # a hand-edited settings file must not stop the editor from starting
                scale = int(str(saved_scale))
            except ValueError:
                scale = 100
        if scale not in self.scale_actions:
            scale = 100
        mode = str(self.settings.value("ui/mode", "guided"))
        wanted = bool(self.settings.value("ui/minimap", True, bool))
        self.act_minimap.setChecked(wanted)
        self.view.set_minimap_wanted(wanted)
        legend = bool(self.settings.value("ui/legend", True, bool))
        self.act_legend.setChecked(legend)
        self.view.set_legend_wanted(legend)
        snap = bool(self.settings.value("ui/snap", True, bool))
        self.act_snap.setChecked(snap)
        self.view.set_snap(snap)
        self.scale_actions[scale].setChecked(True)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            self.theme.apply(app, mode_name, scale / 100)
        else:
            self.theme.mode = mode_name
        self._sync_theme_actions()
        self.theme.changed.connect(self._sync_theme_actions)
        self.ctl.set_mode(mode if mode in ("guided", "expert") else "guided")
        geo = self.settings.value("ui/geometry")
        try:
            restored = isinstance(geo, QByteArray) and self.restoreGeometry(geo)
        except TypeError:
            restored = False
        if not restored:
            self.resize(self._first_size())
        state = self.settings.value("ui/state")
        try:  # a saved dock layout from a version with other docks is ignored
            self._have_saved_state = isinstance(state, QByteArray) and self.restoreState(
                state, STATE_VERSION
            )
        except TypeError:
            self._have_saved_state = False

    def _screen_scale(self) -> int:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return 100
        return auto_scale(screen.size().height(), screen.devicePixelRatio())

    def _first_size(self) -> QSize:
        """The window size when none was saved: 1360 x 860 at 100 %, scaled, and never more than
        the screen has room for."""
        want = QSize(self.theme.px(1360), self.theme.px(860))
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            room = screen.availableGeometry().size()
            if room.width() >= 1000 and room.height() >= 600:
                want = want.boundedTo(room)
        return want

    def _save_settings(self) -> None:
        self.settings.setValue("ui/geometry", self.saveGeometry())
        self.settings.setValue("ui/state", self.saveState(STATE_VERSION))

    def reset_layout(self) -> None:
        """View > Reset layout: the panels back where they start, the saved layout forgotten."""
        self.settings.remove("ui/state")
        self._have_saved_state = False
        self.restoreState(self._default_state, STATE_VERSION)
        for dock in (self.dock_left, self.dock_right, self.dock_bottom):
            dock.setFloating(False)
        self.main_tabs.show_slot("diagram")
        self._bottom_auto_hidden = False
        self._layout_class = None
        self.auto_layout()

    # ---- panels: F6 cycles through the diagram, the project panel, the inspector and the bottom ------
    def _panes(self) -> list[tuple[str, QWidget, QWidget]]:
        """(name, the area, what to show or focus) of every panel that is on screen now."""
        panes: list[tuple[str, QWidget, QWidget]] = [
            (strings.PANE_CANVAS, self.main_tabs, self.main_tabs.currentWidget())
        ]
        for name, dock, tabs in (
            (strings.PANE_TREE, self.dock_left, self.left_tabs),
            (strings.PANE_INSPECTOR, self.dock_right, self.side_tabs),
            (strings.PANE_BOTTOM, self.dock_bottom, self.tabs),
        ):
            if dock.isVisibleTo(self):
                panes.append((name, dock, tabs.currentWidget()))
        return panes

    @staticmethod
    def _first_focusable(root: QWidget) -> QWidget | None:
        """The first widget inside `root` that the Tab key reaches (root itself if it takes focus)."""
        tab = Qt.FocusPolicy.TabFocus
        if root.focusPolicy() & tab and root.isEnabled():
            return root
        w = root.nextInFocusChain()
        for _ in range(2000):
            if w is None or w is root:
                break
            if (
                root.isAncestorOf(w)
                and w.isVisibleTo(root)
                and w.isEnabled()
                and w.focusPolicy() & tab
            ):
                return w
            w = w.nextInFocusChain()
        return None

    def pane_of_focus(self) -> int:
        """Index in `_panes()` of the panel that holds the keyboard focus (the last one used when
        the focus is on something else, e.g. a menu)."""
        fw = QApplication.focusWidget()
        panes = self._panes()
        if fw is not None:
            for i, (_n, area, _w) in enumerate(panes):
                if area is fw or area.isAncestorOf(fw):
                    return i
        return min(self._pane, len(panes) - 1)

    def cycle_panes(self, step: int = 1) -> str:
        """F6 / Shift+F6: move the keyboard focus to the next / previous panel. Returns its name."""
        panes = self._panes()
        for k in range(1, len(panes) + 1):
            i = (self.pane_of_focus() + step * k) % len(panes)
            name, _area, content = panes[i]
            target = self.view if content is self.diagram_page else self._first_focusable(content)
            if target is None:
                continue
            target.setFocus(Qt.FocusReason.TabFocusReason)
            self._pane = i
            self.statusBar().showMessage(strings.PANE_FOCUSED.format(name), 2000)
            return name
        return ""

    def _focus_changed(self, _old: object, new: object) -> None:
        if isinstance(new, QWidget) and self.isAncestorOf(new):
            for i, (_n, area, _w) in enumerate(self._panes()):
                if area is new or area.isAncestorOf(new):
                    self._pane = i
                    return

    def _toggle_minimap(self) -> None:
        self.view.set_minimap_wanted(self.act_minimap.isChecked())
        self.settings.setValue("ui/minimap", self.act_minimap.isChecked())

    def _toggle_legend(self) -> None:
        self.view.set_legend_wanted(self.act_legend.isChecked())
        self.settings.setValue("ui/legend", self.act_legend.isChecked())

    def _toggle_snap(self) -> None:
        self.view.set_snap(self.act_snap.isChecked())
        self.settings.setValue("ui/snap", self.act_snap.isChecked())

    def _toggle_labels(self) -> None:
        self.view.dscene.show_all_labels = self.act_labels.isChecked()
        self.view.viewport().update()

    def _sync_theme_actions(self) -> None:
        """Keep the Theme menu and the dark-theme toggle in step with the theme (also when the
        operating system changes its scheme while the mode is "system")."""
        self.theme_actions[self.theme.mode].setChecked(True)
        self.act_dark.setChecked(self.theme.name == "dark")

    def set_theme_mode(self, mode: str) -> None:
        """Choose "system" (follow the OS), "light" or "dark"; stored as `ui/theme`."""
        if mode not in MODES:
            return
        app = QApplication.instance()
        if isinstance(app, QApplication):
            self.theme.apply(app, mode)
        else:
            self.theme.mode = mode
        self._sync_theme_actions()
        self.settings.setValue("ui/theme", mode)
        self.view.viewport().update()

    def _toggle_dark(self) -> None:
        self.set_theme_mode("dark" if self.act_dark.isChecked() else "light")

    def set_scale(self, pct: int) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            self.theme.apply(app, None, pct / 100)
        self.settings.setValue("ui/scale", pct)
        self.auto_layout()

    def _layout_class_now(self) -> tuple[bool, bool, bool]:
        scale = self.theme.scale
        eff_w, eff_h = self.width() / scale, self.height() / scale
        return (eff_w >= WIDE_PX, eff_w >= MEDIUM_PX, eff_h >= TALL_PX)

    def auto_layout(self) -> None:
        """At high UI scale or small windows, hide secondary panels so the diagram keeps room:
        narrow windows lose the side panels, short windows the bottom panel (the diagram keeps at
        least 55 % of the height at 1280 x 720). Called on first show, when the window crosses one
        of those sizes, and when the scale changes."""
        scale = self.theme.scale
        wide, medium, tall = self._layout_class = self._layout_class_now()
        was = (self.dock_left.isVisibleTo(self), self.dock_right.isVisibleTo(self))
        self.dock_right.setVisible(wide)
        self.dock_left.setVisible(medium)
        now = (self.dock_left.isVisibleTo(self), self.dock_right.isVisibleTo(self))
        if was != now and (was[0] and not now[0] or was[1] and not now[1]):
            self.toasts.show_message(strings.PANELS_HIDDEN, None)  # never hide panels silently
        if not tall and self.dock_bottom.isVisibleTo(self):
            self.dock_bottom.hide()
            self._bottom_auto_hidden = True
            self.toasts.show_message(strings.PANELS_HIDDEN_SHORT, None)
        elif tall and self._bottom_auto_hidden:
            self.dock_bottom.show()  # it was only hidden for lack of height
            self._bottom_auto_hidden = False
        self.table.scale_factor = scale
        self.dock_left.setMinimumWidth(self.theme.px(240))
        self.dock_right.setMinimumWidth(self.theme.px(260))
        self.resizeDocks([self.dock_left], [self.theme.px(250)], Qt.Orientation.Horizontal)
        # the bottom panel never takes more than 40% of the window, so the diagram keeps room
        # at large UI scales (its content scrolls; the View menu can still hide it)
        self.dock_bottom.setMaximumHeight(max(self.theme.px(160), int(self.height() * 0.40)))
        self.resizeDocks(
            [self.dock_bottom],
            [max(self.theme.px(110), int(self.height() * 0.20))],
            Qt.Orientation.Vertical,
        )

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._shown:
            self._shown = True
            if self._have_saved_state:  # the person's own layout stands
                self._layout_class = self._layout_class_now()
            else:
                self.auto_layout()

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        self.toasts.reposition()
        if self._shown and self._layout_class_now() != self._layout_class:
            if self._have_saved_state:  # (a saved layout is kept; only a crossing is acted on)
                self._have_saved_state = False
            self.auto_layout()
        if self.tour.active:
            self.tour.show_step(self.tour.index)

    def finish_tour(self) -> None:
        self.settings.setValue("tour/done", True)
        self.tour.stop()
