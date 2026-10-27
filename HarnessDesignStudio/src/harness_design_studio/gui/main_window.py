"""Main window: top bar, banners, main tabs, project panel with the interface table, inspector, status bar."""

import contextlib
import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any

import shiboken6
from pydantic import ValidationError
from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QEventLoop,
    QSettings,
    QSize,
    QStandardPaths,
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
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio import __version__
from harness_design_studio.core import device_library, drc, edit, manual_harness
from harness_design_studio.core import links as core_links
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
    drawings_exported,
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
from harness_design_studio.gui import areas, recent, strings
from harness_design_studio.gui.canvas import DiagramView, ZoomIndicator
from harness_design_studio.gui.checks_panel import ChecksPanel, PendingValuesLink
from harness_design_studio.gui.command_palette import CommandPalette, PaletteEntry
from harness_design_studio.gui.controller import (
    Delta,
    EditorController,
    NeedSaveAs,
    _plain,
    reason_of,
)
from harness_design_studio.gui.devices_dialogs import (
    AssignDialog,
    ContactDialog,
    FillDialog,
    LibraryDialog,
    NewDeviceDialog,
    NewPartDialog,
    NewTypeDialog,
)
from harness_design_studio.gui.devices_view import DevicesView
from harness_design_studio.gui.dialogs import (
    Banner,
    ChangeDialog,
    ConfirmDialog,
    DiffDialog,
    GeneratePreviewDialog,
    GlossaryDialog,
    HistoryDialog,
    ImportDialog,
    IssuesDialog,
    NewInterfaceDialog,
    WaiverDialog,
    WireColoursDialog,
)
from harness_design_studio.gui.export_dialog import ExportDialog, ExportResult
from harness_design_studio.gui.harness_view import HarnessView
from harness_design_studio.gui.icons import icon, icon_button, style_dock_buttons, tooltip_text
from harness_design_studio.gui.import_kinds import KINDS
from harness_design_studio.gui.import_wizard import ImportWizard
from harness_design_studio.gui.inspector import Inspector
from harness_design_studio.gui.interface_table import InterfaceTable
from harness_design_studio.gui.jobs import JobStatus
from harness_design_studio.gui.library_window import SETTINGS_FOLDER as LIBRARY_FOLDER_KEY
from harness_design_studio.gui.library_window import LibraryWindow
from harness_design_studio.gui.link_dialog import CreateHarnessDialog, LinkDialog, harness_preview
from harness_design_studio.gui.lists_panel import ListsPanel
from harness_design_studio.gui.new_project_dialog import (
    BLANK,
    NewProjectDialog,
    NewProjectRequest,
)
from harness_design_studio.gui.next_page import NextStepPage
from harness_design_studio.gui.next_step import NextInputs, next_step
from harness_design_studio.gui.pages import HomePage
from harness_design_studio.gui.panels import ProblemsPanel, PropertiesPanel, category_icon
from harness_design_studio.gui.problems_panel import ProblemsList
from harness_design_studio.gui.project_tree import ProjectTree
from harness_design_studio.gui.rail import NavRail
from harness_design_studio.gui.releases_panel import ReleasesPanel
from harness_design_studio.gui.role_dialog import RoleDialog
from harness_design_studio.gui.roles import (
    ELECTRICAL,
    SYSTEMS,
    clean_role,
    default_role,
    role_key,
)
from harness_design_studio.gui.settings_page import SCALES, SettingsPage
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
from harness_design_studio.gui.theme.tokens import CATEGORIES
from harness_design_studio.gui.topbar import ShellStatus, TopBar
from harness_design_studio.gui.tour import Tour
from harness_design_studio.gui.unit_table import UnitTable
from harness_design_studio.resources import guide_path

ARRANGE_IN_WORKER = 60  # a diagram with more units is arranged off the UI thread
STATE_VERSION = 3  # of the saved dock layout (`saveState`); change it when the docks change
WIDE_PX = 1222  # in UI-scale-free px: the right dock needs this much window width (the rail's 72 included)
MEDIUM_PX = 872  # ... and the left dock this much
# the left dock opens this wide on the Interfaces tab (if the window allows)
INTERFACE_DOCK_PX = 760
MAIN_TABS = ("diagram", "harness", "lists", "checks", "releases", "devices")  # Ctrl+1 ... Ctrl+6


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

    def __init__(self, project: Project, drawings: bool = True) -> None:
        super().__init__()
        self._project = project
        self.drawings = drawings  # the PDF and SVG drawings of the harnesses (D-169)
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
                drawings=self.drawings,
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
        self._settings_were_empty = not settings.allKeys()  # a first run (see `_restore_role`)
        # `first_run=False` says this is not a first start: no tour and no question about the role
        self._first_start = first_run is not False
        self._role_to_ask = False  # a first start with no role set by the hook: ask once
        # "systems" | "electrical", set from the settings in `_restore_settings`
        self.role = ELECTRICAL
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
        # file to read for "Add from library…" of the Devices tab: (title, filter) -> path
        self.ask_open_path: Callable[[str, str], str | None] = self._ask_open_path
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
        self._layout_class: tuple[bool, bool] | None = None
        self._left_width = 0  # the left panel's width before the Interfaces tab widened it
        self.command_palette: CommandPalette | None = None  # the Ctrl+K overlay, while it is open
        self._pane = 0
        self._area = areas.DEFAULT
        self._switching_area = False
        self.examples_folder: Callable[[], Path] = self._examples_folder  # (tests replace it)
        self.library_window: LibraryWindow | None = None  # made when first opened
        self._recent_shown: list[recent.RecentEntry] | None = None
        self._active_worker: PlanWorker | OutputsWorker | ArrangeWorker | None = None
        self._last_check = ""

        self._build_center()
        self._build_docks()
        self._build_actions()
        self._build_menus_and_toolbar()
        self._build_status()
        self.toasts = ToastHost(self.view)
        self._register_slots()
        self._install_default_views()
        self._show_area(areas.DEFAULT)
        self.tour = Tour(self, theme, self._tour_targets(), self._tour_reveals())
        self.tour.on_stop = lambda: self.settings.setValue("tour/done", True)

        self.ctl.message.connect(self._on_message)
        self.ctl.drcStateChanged.connect(self._on_check_state)
        self.ctl.stateChanged.connect(self._on_state)
        self.ctl.changed.connect(self._on_changed)
        self.ctl.selectionChanged.connect(self._on_selection)
        self.ctl.openRequested.connect(self._open_requested)
        self.ctl.problemsRequested.connect(self._show_problems)
        self.ctl.whyRequested.connect(self._show_why)
        self.props.deleteRequested.connect(self.delete_flow)
        self.ctl.connectChanged.connect(self._on_connect)
        self.ctl.linkRequested.connect(self.link_flow)
        self.ctl.linkSelectionChanged.connect(self._on_link_selection)
        self.ctl.modeChanged.connect(self._on_mode)
        self.interface_table.newInterfaceRequested.connect(self.new_interface_flow)
        self.unit_table.newUnitRequested.connect(lambda: self.menu_add.exec(QCursor.pos()))
        self.checks_panel.showRequested.connect(self.show_object)
        self.releases_panel.changeRequested.connect(self.change_flow)
        self.pending_link.filterRequested.connect(self.show_unchecked)
        self.topbar.generateClicked.connect(self.act_generate.trigger)
        self.topbar.checkClicked.connect(self.act_check.trigger)
        self.topbar.releaseClicked.connect(self.act_release.trigger)
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

        self._default_state = self.saveState(STATE_VERSION)  # View > Reset layout goes back to it
        self._restore_settings()
        self._on_state()
        self._on_connect()
        self._on_selection()
        if first_run is None:
            first_run = not self.settings.value("tour/done", False, bool)
        self.ctl.open_sample()
        self._open_for_role()
        self._update_hash()
        if self._role_to_ask:
            pass  # the question comes first, when the window shows (`showEvent`); the tour after it
        elif first_run:
            QTimer.singleShot(200, self.tour.start)
        self._tour_wanted = bool(first_run)

    # ---- construction ------------------------------------------------------------------------
    def _build_center(self) -> None:
        shell = QWidget()
        shell.setObjectName("shell")
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.topbar = TopBar(
            self.theme
        )  # placed in the top tool bar (see _build_menus_and_toolbar)
        self.generate_btn = self.topbar.generate_btn
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
        self.tool_connect.setAccessibleName(strings.TOOL_CONNECT)
        self.tool_connect.setAccessibleDescription(strings.TOOL_CONNECT_TIP)
        # the arrow next to it lists the interface types (it was the palette's job)
        self.tool_connect.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.tool_select.clicked.connect(lambda: self.ctl.end_connect())
        self.tool_connect.clicked.connect(lambda: self.ctl.begin_link())
        # the Systems engineer role shows Select, Connect and Add device, and one More menu for the
        # rest (stage S2); both are hidden for the Electrical / AIT engineer role
        self.tool_add_device = QToolButton()
        self.tool_add_device.setObjectName("tool-add-device")
        self.tool_add_device.setText(strings.TOOL_ADD_DEVICE)
        self.tool_add_device.setToolTip(strings.TOOL_ADD_DEVICE_TIP)
        self.tool_add_device.setAccessibleName(strings.TOOL_ADD_DEVICE)
        self.tool_add_device.setVisible(False)
        self.tool_more = QToolButton()
        self.tool_more.setObjectName("tool-more")
        self.tool_more.setText(strings.TOOL_MORE)
        self.tool_more.setToolTip(strings.TOOL_MORE_TIP)
        self.tool_more.setAccessibleName(strings.TOOL_MORE)
        self.tool_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.tool_more.setVisible(False)
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
        bar.addWidget(self.tool_add_device)
        self.tool_row = bar  # Arrange and the filters join it (they only act on the diagram)
        bar.addWidget(self.hint, 1)
        self.view = DiagramView(self.ctl, self.theme)
        self.view.setObjectName("diagram")
        self.view.addDeviceRequested.connect(self.add_device_flow)
        self.zoom_level = ZoomIndicator(self.view)  # "100 %"; View.zoomChanged(float) feeds it
        for w in (
            self.redundant_btn,
            self.delete_btn,
            self.zoom_out_btn,
            self.zoom_in_btn,
            self.fit_btn,
        ):
            bar.addWidget(w)
        bar.addWidget(self.tool_more)
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
        self.main_tabs.add_slot(
            "devices",
            strings.TAB_DEVICES,
            EmptyStateWidget(self.theme, strings.TAB_DEVICES, strings.EMPTY_VIEW_DEVICES, icon="unit"),
            installed=False,
            tip=strings.TAB_TIP.format(strings.TAB_DEVICES, 6),
        )  # fmt: skip
        self.main_tabs.tabBar().setAccessibleName(strings.SHELL_MAIN_TABS)
        # the area pages: Home and Settings are pages of their own, every other area is a set of
        # tabs of main_tabs (`set_area`)
        self.home_page = HomePage(
            self.theme,
            new=lambda: self.act_new.trigger(),
            open_=lambda: self.act_open.trigger(),
            example=lambda: self.act_new_example.trigger(),
            sample=lambda: self.act_sample.trigger(),
            library=lambda: self.open_library_flow(),
            open_recent=lambda path: self.open_recent_flow(path),
            forget_recent=lambda path: self.forget_recent(path),
            open_example=lambda name: self.open_example_flow(name),
        )
        self.next_page = NextStepPage(
            self.theme,
            actions={
                "add_device": lambda: self.add_device_flow(),
                "new_harness": lambda: self.new_harness_flow(),
                "connect": lambda: self._next_connect(),
                "make_harness": lambda: self._next_make_harness(),
                "generate": lambda: self.generate_flow(),
                "check": lambda: self.check_flow(),
                "fix": lambda: self._next_fix(),
                "build_sheets": lambda: self.export_dialog_flow(),
                "release": lambda: self._next_go("releases"),
                "done": lambda: self._next_go("lists"),
                "show_everything": lambda: self.show_everything(),
                "library": lambda: self.open_library_flow(),
            },
        )
        self.settings_page = SettingsPage(
            self.theme,
            set_role=lambda value: self.set_role(value),
            set_theme=lambda mode: self.set_theme_mode(mode),
            set_scale=lambda pct: self.scale_actions[pct].trigger(),
            set_reduce_motion=lambda on: self._set_checked(self.act_reduce_motion, on),
            set_mode=lambda mode: self._pick_mode(mode),
            set_snap=lambda on: self._set_checked(self.act_snap, on),
            set_labels=lambda on: self._set_checked(self.act_labels, on),
            set_connection_ends=lambda on: self._set_checked(self.act_connection_ends, on),
            set_problem_notices=lambda on: self._set_checked(self.act_problem_notices, on),
            open_values=lambda: self.values_flow(),
            choose_library_folder=lambda: self.choose_library_folder_flow(),
            clear_library_folder=lambda: self.set_library_folder(""),
            open_library=lambda: self.open_library_flow(),
            shortcut_rows=self.shortcut_rows,
            settings_file=self.settings.fileName(),
        )
        shrinkable(self.home_page)  # a page never sets the minimum size of the window
        shrinkable(self.next_page)
        shrinkable(self.settings_page)
        self.area_stack = QStackedWidget()
        self.area_stack.setObjectName("area-stack")
        self.area_stack.addWidget(self.main_tabs)
        self.area_stack.addWidget(self.home_page)
        self.area_stack.addWidget(self.next_page)
        self.area_stack.addWidget(self.settings_page)
        outer.addWidget(self.area_stack, 1)
        self.main_tabs.currentChanged.connect(lambda _i: self._tab_changed())
        self.setCentralWidget(shell)

    def _build_docks(self) -> None:
        # left: the project tree (a slot, filled when it exists) and the interface table
        self.unit_table = UnitTable(self.ctl, self.settings)
        self.interface_table = InterfaceTable(self.ctl, self.settings)
        self.left_tabs = SlotTabs()
        self.left_tabs.setObjectName("left-tabs")
        self.left_tabs.setAccessibleName(strings.SHELL_LEFT_TABS)
        self.left_tabs.add_slot(
            "tree",
            strings.TAB_PROJECT,
            EmptyStateWidget(self.theme, strings.TAB_PROJECT, strings.EMPTY_VIEW_TREE, icon="tree"),
            installed=False,
        )
        self.left_tabs.add_slot(
            "units", strings.TAB_UNITS, self.unit_table, tip=strings.TAB_UNITS_TIP
        )
        self.left_tabs.add_slot(
            "interfaces",
            strings.TAB_INTERFACES,
            self.interface_table,
            tip=strings.TAB_INTERFACES_TIP,
        )
        self.dock_left = self._dock(
            strings.TAB_PROJECT,
            self.left_tabs,
            Qt.DockWidgetArea.LeftDockWidgetArea,
            "dock-project",
        )
        self.left_tabs.currentChanged.connect(lambda _i: self._left_tab_changed())
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
        # (280 px: the three tabs Project, Device list and Interfaces fit in a row, without arrows)
        self.dock_left.setMinimumWidth(280)
        self.dock_right.setMinimumWidth(260)
        self.resizeDocks([self.dock_left, self.dock_right], [280, 310], Qt.Orientation.Horizontal)
        # bottom: the Problems panel, closed until it is asked for (status bar, View menu, Ctrl+Shift+M)
        self.problems_list = ProblemsList(self.ctl, self.theme)
        self.dock_problems = self._dock(
            strings.PROBLEMS_PANEL_TITLE,
            self.problems_list,
            Qt.DockWidgetArea.BottomDockWidgetArea,
            "dock-problems",
        )
        self.dock_problems.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.dock_problems.setMinimumHeight(120)
        self.dock_problems.hide()
        self.problems_list.showRequested.connect(self.show_object)
        self.problems_list.detailsRequested.connect(self._problem_details)

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
        self.jobs = JobStatus(self.theme)  # what runs in the background, with Cancel
        sb.addWidget(self.jobs)
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
        self.problems_btn = QPushButton(strings.PROBLEMS_BUTTON.format(0))
        self.problems_btn.setObjectName("problems-button")
        self.problems_btn.setProperty("ghost", True)
        self.problems_btn.setProperty("toggle", True)
        self.problems_btn.setCheckable(True)
        self.problems_btn.setToolTip(strings.A_PROBLEMS_TIP)
        self.problems_btn.setAccessibleName(strings.A_PROBLEMS)
        self.problems_btn.clicked.connect(lambda _c=False: self.toggle_problems())
        self.dock_problems.visibilityChanged.connect(self.problems_btn.setChecked)
        self.offline = QToolButton()  # the program works offline: say so, plainly
        self.offline.setObjectName("offline-indicator")
        self.offline.setProperty("ghost", True)
        self.offline.setText(strings.OFFLINE_TEXT)
        self.offline.setIcon(icon("lock", self.theme))
        self.offline.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.offline.setToolTip(strings.OFFLINE_TIP)
        self.offline.setAccessibleName(f"{strings.OFFLINE_TEXT}. {strings.OFFLINE_TIP}")
        self.offline.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        sb.addPermanentWidget(self.problems_btn)
        sb.addPermanentWidget(self.offline)
        # the model hash, the rule count and the generation record are details: they stay in the
        # widgets (and in the tooltip of the counts) but take no room in the bar
        for w in (self.status_hash, self.status_rules, self.status_generated):
            w.setVisible(False)
        sb.addPermanentWidget(self.pending_link)
        sb.addPermanentWidget(self.zoom_level)  # "100 %" (the view's zoomChanged feeds it)

    def _left_tab_changed(self) -> None:
        self._sync_dock_titles()
        if not self.dock_left.isVisible():
            return
        if self.left_tabs.currentWidget() in (self.interface_table, self.unit_table):
            # the table has eight columns: give the left panel room for them (at most 55 % of the window)
            want = min(self.theme.px(INTERFACE_DOCK_PX), self.width() * 11 // 20)
            if self.dock_left.width() < want:
                if (
                    not self._left_width
                ):  # (going from one table to the other keeps the first width)
                    self._left_width = self.dock_left.width()
                self.resizeDocks([self.dock_left], [want], Qt.Orientation.Horizontal)
        elif self._left_width:  # back to the tree: the panel narrows to what it was
            self.resizeDocks([self.dock_left], [self._left_width], Qt.Orientation.Horizontal)
            self._left_width = 0

    def _sync_dock_titles(self) -> None:
        current = self.left_tabs.currentWidget()
        self.dock_left.setWindowTitle(
            strings.TAB_INTERFACES
            if current is self.interface_table
            else strings.TAB_UNITS
            if current is self.unit_table
            else strings.TAB_PROJECT  # fmt: skip
        )

    # ---- the slot registry: views that are written elsewhere plug in here --------------------------
    def _register_slots(self) -> None:
        """Name every place a later view goes. `install_view(name, widget)` fills one."""
        for name, tabs, title in (
            ("harness", self.main_tabs, strings.TAB_HARNESS),
            ("lists", self.main_tabs, strings.TAB_LISTS),
            ("devices", self.main_tabs, strings.TAB_DEVICES),
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
            widget.changesRequested.connect(lambda hid: self.change_flow("changes", hid))
            widget.historyRequested.connect(lambda hid: self.change_flow("history", hid))
            widget.deleteRequested.connect(lambda hid: self.change_flow("delete", hid))
            widget.newHarnessRequested.connect(self.new_harness_flow)
            widget.whyRequested.connect(lambda kind, ident: self._show_why(kind, ident))
            return True
        if isinstance(widget, ListsPanel):
            widget.generateRequested.connect(self.act_generate.trigger)
            widget.exportTableRequested.connect(lambda name, fmt: self.export_table_flow(name, fmt))
            return True
        if isinstance(widget, DevicesView):
            widget.addRequested.connect(lambda: self.menu_add.exec(QCursor.pos()))
            widget.duplicateRequested.connect(self._duplicate_device)
            widget.exportPinoutRequested.connect(self.export_pinout_flow)
            widget.saveToLibraryRequested.connect(self.save_device_to_library_flow)
            widget.addFromLibraryRequested.connect(self.add_from_library_flow)
            widget.whyRequested.connect(lambda kind, ident: self._show_why(kind, ident))
            widget.reviseRequested.connect(lambda hid: self.change_flow("revise", hid))
            widget.fillRequested.connect(self.fill_pins_flow)
            widget.assignRequested.connect(self.assign_pins_flow)
            widget.contactRequested.connect(self.contact_pins_flow)
            widget.newPartRequested.connect(self.new_part_flow)
            widget.newTypeRequested.connect(self.new_type_flow)
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
        """Plug in the views: Harness, Lists, the project tree and the inspector (with its Why and
        Problems tabs; the Problems tab holds the problems list with the to-do items)."""
        self.harness_view = HarnessView(self.ctl, self.theme, self.settings)
        self.harness_view.wire_editor.run_dialog = lambda dlg: self.run_dialog(dlg)
        self.lists_panel = ListsPanel(self.ctl, self.theme, self.settings)
        self.lists_panel.files.ask_folder = lambda title: self.ask_folder(title)
        self.project_tree = ProjectTree(self.ctl, self.theme, self.settings)
        # the properties panel leaves its tab for the inspector that wraps it
        self.side_tabs.install("inspector", EmptyStateWidget(self.theme, strings.TAB_INSPECTOR, ""))
        self.problems = ProblemsPanel(self.ctl)
        self.problems.showRequested.connect(self.show_object)
        self.problems.waiveRequested.connect(self.waive_flow)
        self.inspector = Inspector(self.ctl, self.theme, props=self.props, problems=self.problems)
        self.install_view("harness", self.harness_view)
        self.install_view("lists", self.lists_panel)
        self.devices_view = DevicesView(self.ctl, self.theme, self.settings)
        self.install_view("devices", self.devices_view)
        self.install_view("tree", self.project_tree)
        self.install_view("inspector", self.inspector)
        self.project_tree.set_context_actions(self._tree_actions)
        self.project_tree.deleteRequested.connect(self._tree_delete)
        self.harness_view.selectionChanged.connect(self._drawing_selected)
        # the lock banner follows the harness chosen in Drawings and in Revisions
        self.harness_view.selector.currentIndexChanged.connect(
            lambda _i: self._update_lock_banner()
        )
        self.releases_panel.harness.currentIndexChanged.connect(
            lambda _i: self._update_lock_banner()
        )

    def _drawing_selected(self, kind: str, ident: str) -> None:
        """A wire, connector or pin picked in the drawing or its tables: the inspector shows the
        link a wire belongs to (the diagram selects it too) and the Why tab knows the object."""
        if kind == "wire":
            for h in self.ctl.project.harnesses.values():
                wire = next((w for w in h.wires if w.id == ident), None)
                if wire is not None and wire.interface_id in self.ctl.project.interfaces:
                    self.ctl.select("interface", wire.interface_id)
                    break
        if kind in ("wire", "connector", "pin"):
            self.inspector.show_object(kind, ident)

    # ---- what the new views ask for ----------------------------------------------------------------
    def _show_why(self, kind: str, ident: str) -> None:
        """The Why of a harness, wire, connector or pin: in the right dock's Why tab."""
        self.dock_right.show()
        self.inspector.show_object(kind, ident, tab="why")

    def _show_problems(self, object_id: str) -> None:
        """A badge on the diagram asked for the problems of an object: the right dock's Problems
        tab (the object is already selected, so the diagram keeps showing what they are about)."""
        self.dock_right.show()
        self.inspector.show_tab("problems")

    def _problem_details(self, object_id: str) -> None:
        """Shift+Enter or "Details and fixes" in the Problems panel: go to the object and open
        its problems as cards (fix, waive) in the inspector."""
        self.show_object(object_id)
        self._show_problems(object_id)

    def _tree_selected(self, kind: str, ident: str) -> None:
        if kind not in ("unit", "interface", "link"):  # (those the tree selects on the canvas)
            self.inspector.show_object(kind, ident)

    def _tree_opened(self, kind: str, ident: str) -> None:
        if kind in ("unit", "interface"):
            self.ctl.request_open(kind, ident)
        elif kind == "link":
            self.edit_link_flow(ident)
        elif kind == "harness":
            self._go_to_harness(ident)
        else:
            self.inspector.show_object(kind, ident)

    def _tree_actions(self, kind: str, ident: str) -> list[QAction]:
        """The change-control steps of a harness row in the tree's context menu."""
        if kind == "link":
            return self._link_actions(ident)
        h = self.ctl.project.harnesses.get(ident)
        if kind != "harness" or h is None:
            return []
        ro = self.ctl.read_only
        has_base = any(b.harness_id == ident for b in self.ctl.project.baselines.values())
        steps = (
            ("review", strings.A_REVIEW, h.status == "draft" and not ro),
            ("release", strings.A_RELEASE, h.status in ("draft", "in_review") and not ro),
            ("revise", strings.A_REVISE, h.status == "released" and not ro),
            ("changes", strings.A_CHANGES, has_base),
            ("history", strings.A_HISTORY, True),
            ("delete", strings.A_DELETE_HARNESS, h.status in ("draft", "in_review") and not ro),
        )
        out: list[QAction] = []
        for action, text, enabled in steps:
            act = QAction(text, self)
            act.setObjectName(f"tree-harness-{action}")
            act.setEnabled(enabled)
            act.triggered.connect(lambda _c=False, a=action: self.change_flow(a, ident))
            out.append(act)
        return out

    def _tree_delete(self, kind: str, ident: str) -> None:
        """Delete pressed in the project tree on a unit or an interface: what is deleted is the
        row with the cursor (and the rest of a multiple selection made in the tree)."""
        if kind == "link":
            self.delete_link_flow(ident)
            return
        chosen = {(s.kind, s.id) for s in self.ctl.selected}
        if (kind, ident) not in chosen:
            self.ctl.select(kind, ident)
        self.delete_flow()

    def _tree_import(self, kind: str) -> None:
        if kind == "interfaces":
            self.import_interfaces_flow()
        else:
            self.import_wizard_flow({"engineering": "values"}.get(kind, kind))

    def _tree_add(self, kind: str) -> None:
        if kind == "interface":
            self.new_interface_flow()
        elif kind == "link":
            self.link_flow()
        else:
            self.menu_add.exec(QCursor.pos())  # which kind of unit

    # ---- connections: two connectors joined pin to pin (M2 of the workshop feedback) ----------------
    def link_flow(
        self, a_unit: str = "", a_connector: str = "", b_unit: str = "", b_connector: str = ""
    ) -> None:
        """Edit > Link connectors… (Ctrl+Shift+K), or the Connect tool after two devices: the
        window proposes the pairs by signal name; OK joins the connectors as one undo step."""
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        if len(self.ctl.project.units) < 2:
            self.toasts.show_message(strings.LINK_NEED_TWO, None)
            return
        dlg = LinkDialog(
            self,
            self.theme,
            self.ctl.project,
            a_unit=a_unit,
            a_connector=a_connector,
            b_unit=b_unit,
            b_connector=b_connector,
        )
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return
        lid = self.ctl.add_link(
            dlg.a_connector_id(), dlg.b_connector_id(), dlg.pairs(), dlg.name(), dlg.roles()
        )
        if lid:
            self.view.focus_connection(lid)

    def _chosen_link(self, link_id: str | None) -> str | None:
        lid = link_id or self.ctl.selected_link
        if lid is None or lid not in self.ctl.project.links:
            self.toasts.show_message(strings.LINK_PICK_ONE, None)
            return None
        return lid

    def edit_link_flow(self, link_id: str | None = None) -> None:
        """Edit the pairs, the name and the pin roles of a connection."""
        lid = self._chosen_link(link_id)
        if lid is None:
            return
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        dlg = LinkDialog(self, self.theme, self.ctl.project, link_id=lid)
        if self.run_dialog(dlg) == QDialog.DialogCode.Accepted:
            self.ctl.edit_link(lid, dlg.pairs(), dlg.name(), dlg.roles())

    def rename_link_flow(self, link_id: str | None = None) -> None:
        lid = self._chosen_link(link_id)
        if lid is None:
            return
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        name = self.ask_text(
            strings.LINK_RENAME_TITLE, strings.LINK_NAME, self.ctl.project.links[lid].name
        )
        if name is not None:
            self.ctl.rename_link(lid, name)

    def delete_link_flow(self, link_id: str | None = None) -> None:
        lid = self._chosen_link(link_id)
        if lid is None:
            return
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        self.ctl.delete_link(lid)

    def create_harness_flow(self, link_id: str | None = None) -> None:
        """The one button that makes a harness from a connection: it says what will be added,
        asks once, and makes it as one undo step. Nothing makes a harness on its own."""
        lid = self._chosen_link(link_id)
        if lid is None:
            return
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        try:
            sentence = harness_preview(self.ctl.project, lid)
        except edit.EditError as exc:
            self._error(str(exc))
            return
        if (
            self.run_dialog(CreateHarnessDialog(self, self.theme, sentence))
            != QDialog.DialogCode.Accepted
        ):
            return
        hid = self.ctl.create_harness_from_link(lid)
        if hid is None:
            return
        self.go_to("harness")
        self.harness_view.refresh()
        self.harness_view.select_harness(hid)

    def check_connections_flow(self) -> None:
        """Check my connections: the review of every connection, without changing anything. The
        findings are the cards of the Problems panel (filtered to the connections), where each
        one shows the connection on the diagram."""
        if not self.ctl.project.links:
            self.toasts.show_message(strings.LINK_CHECK_NONE, None)
            return
        found = core_links.check_links(self.ctl.project)
        self.dock_problems.show()
        self.problems_list.show_filter("links")
        self.ctl.check_now()
        text = (
            strings.LINK_CHECK_FOUND[0 if len(found) == 1 else 1].format(len(found))
            if found
            else strings.LINK_CHECK_CLEAN
        )
        self.toasts.show_message(text, None, 8000)

    def show_link_harness_flow(self, link_id: str | None = None) -> None:
        """Show the harness that was made from a connection: the Harness tab opens on it."""
        lid = self._chosen_link(link_id)
        if lid is None:
            return
        hid = self.ctl.project.links[lid].harness_id
        if not hid or hid not in self.ctl.project.harnesses:
            self.toasts.show_message(strings.A_LINK_SHOW_HARNESS_NONE, None)
            return
        self._go_to_harness(hid)

    def bulk_wires_flow(self) -> None:
        """Edit > Edit all wires of the harness… (Ctrl+Shift+B): the Harness tab opens on the harness
        shown there and a window asks for the gauge, type, colour and length."""
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        if not self.ctl.project.harnesses:
            self.toasts.show_message(strings.BULK_NO_HARNESS, None)
            return
        self.go_to("harness")
        self.harness_view.refresh()
        self.harness_view.wire_editor.bulk_edit()

    def _link_actions(self, link_id: str) -> list[QAction]:
        """The entries of a connection's row in the project tree."""
        link = self.ctl.project.links.get(link_id)
        if link is None:
            return []
        ro = self.ctl.read_only
        out: list[QAction] = []
        for name, text, slot, enabled in (
            ("edit", strings.A_LINK_EDIT, self.edit_link_flow, not ro),
            ("rename", strings.A_LINK_RENAME, self.rename_link_flow, not ro),
            (
                "harness",
                strings.A_LINK_HARNESS,
                self.create_harness_flow,
                not ro and not link.harness_id and bool(link.pairs),
            ),
            (
                "show-harness",
                strings.A_LINK_SHOW_HARNESS,
                self.show_link_harness_flow,
                bool(link.harness_id) and link.harness_id in self.ctl.project.harnesses,
            ),
            ("delete", strings.A_LINK_DELETE, self.delete_link_flow, not ro),
        ):
            act = QAction(text, self)
            act.setObjectName(f"tree-link-{name}")
            act.setEnabled(enabled)
            act.triggered.connect(lambda _c=False, f=slot: f(link_id))
            out.append(act)
        return out

    def _on_link_selection(self) -> None:
        """The Edit > Selected connection actions follow the connection that is picked."""
        c = self.ctl
        link = c.project.links.get(c.selected_link or "")
        have = link is not None and not c.read_only
        for act in (self.act_link_edit, self.act_link_rename, self.act_link_delete):
            act.setEnabled(have)
        self.act_link_harness.setEnabled(
            have and link is not None and not link.harness_id and bool(link.pairs)
        )
        made = link is not None and bool(link.harness_id) and link.harness_id in c.project.harnesses
        self.act_link_show_harness.setEnabled(made)
        self.act_link_show_harness.setToolTip(
            strings.A_LINK_SHOW_HARNESS_TIP if made else strings.A_LINK_SHOW_HARNESS_NONE
        )
        self.menu_connection.setEnabled(link is not None)

    # ---- devices: a new device, parts, interface types, pins from a type or an interface -----------
    def add_device_flow(self) -> None:
        """Add > Device… (Ctrl+Shift+N): asks for the name (and the ID and subsystem), then adds
        an empty device in a free slot as one undo step and opens it in the Devices tab."""
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        dlg = NewDeviceDialog(self, self.theme, self.ctl.project)
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return
        uid = self.ctl.add_device(count=dlg.count(), **dlg.values())
        if uid is None:
            return
        self.go_to("devices")
        self.devices_view.show_unit(uid)
        self.devices_view.focus_name()

    def new_harness_flow(self) -> None:
        """Edit > New harness… (Ctrl+Shift+H): an empty harness made by hand, with no interface
        behind it; the Harness tab opens on its Connectors tab."""
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        name = self.ask_text(strings.NEW_HARNESS_TITLE, strings.NEW_HARNESS_NAME, "")
        if not name:
            return
        try:
            ops, hid = manual_harness.plan_new_harness(self.ctl.project, name)
        except edit.EditError as exc:
            self._error(str(exc))
            return
        if not self.ctl.run(
            strings.STEP_NEW_HARNESS.format(hid), ops, message=strings.HARNESS_CREATED.format(hid)
        ):
            return
        self.go_to("harness")
        self.harness_view.refresh()
        self.harness_view.select_harness(hid)
        self.harness_view.show_connectors()

    def new_part_flow(self) -> str | None:
        """New part… (a connector part, with its mating half if asked): always pending and
        unverified. The part is chosen in the picker of the Devices tab afterwards."""
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return None
        dlg = NewPartDialog(self, self.theme, self.ctl.project)
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return None
        pair, fields = dlg.values()
        pid = self.ctl.add_part(pair, **fields)
        if pid:
            self.devices_view.select_part(pid)
        return pid

    def new_type_flow(self) -> str | None:
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return None
        dlg = NewTypeDialog(self, self.theme, self.ctl.project)
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return None
        return self.ctl.add_interface_type(**dlg.values())

    def fill_pins_flow(self, connector_id: str, pins: list[str]) -> None:
        """Fill from interface type… (Ctrl+L in the pin table)."""
        dlg = FillDialog(self, self.theme, self.ctl.project, connector_id, pins)
        accepted = self.run_dialog(dlg) == QDialog.DialogCode.Accepted
        if dlg.wants_new_type:
            if self.new_type_flow():
                self.fill_pins_flow(connector_id, pins)
            return
        if accepted:
            self.ctl.fill_pins(connector_id, pins, dlg.type_id(), fixed=dlg.fixed.isChecked())

    def contact_pins_flow(self, connector_id: str, pins: list[str]) -> None:
        """Cable contact… of the selected pins (the pin table's menu and button)."""
        dlg = ContactDialog(self, self.theme, self.ctl.project, connector_id, pins)
        if self.run_dialog(dlg) == QDialog.DialogCode.Accepted:
            self.ctl.set_pin_contacts(connector_id, pins, dlg.part_id())

    def assign_pins_flow(self, connector_id: str, pins: list[str]) -> None:
        """Assign to interface… (Ctrl+Enter in the pin table)."""
        dlg = AssignDialog(self, self.theme, self.ctl.project, connector_id, pins)
        accepted = self.run_dialog(dlg) == QDialog.DialogCode.Accepted
        if dlg.wants_new_interface:
            before = set(self.ctl.project.interfaces)
            self.new_interface_flow()
            if set(self.ctl.project.interfaces) != before:
                self.assign_pins_flow(connector_id, pins)
            return
        if accepted:
            chosen, signals = dlg.assignment()
            self.ctl.assign_pins(connector_id, chosen, dlg.interface_id(), signals)

    def _duplicate_device(self, unit_id: str) -> None:
        """Duplicate in the Devices tab: the same step as Edit > Duplicate on that unit."""
        self.ctl.select("unit", unit_id)
        self.ctl.duplicate_selected()

    def export_pinout_flow(self, unit_id: str) -> None:
        """ "Export pinout" of the Devices tab: ask where, then write the rows as they are shown."""
        suggested = f"{unit_id}_pinout.csv"
        path = self.ask_save_path(strings.DV_EXPORT_TITLE, suggested, strings.DV_EXPORT_FILTER)
        if not path:
            return
        try:
            written = self.devices_view.export_to(Path(path))
        except (OSError, ValueError) as exc:
            self._error(self._explain(exc, Path(path).parent))
            return
        self.toasts.show_message(strings.DV_EXPORTED.format(written.name), None)

    def save_device_to_library_flow(self, unit_id: str) -> None:
        """ "Save to library…" of the Devices tab: ask where, then add the device to that file."""
        path = self.ask_save_path(
            strings.DV_LIB_SAVE_TITLE,
            device_library.default_file_name([unit_id]),
            strings.DV_LIB_FILTER,
        )
        if not path:
            return
        target = Path(path)
        try:
            data = device_library.export_devices(self.ctl.project, [unit_id])
            existing = device_library.read_library(target) if target.exists() else None
            device_library.write_library(target, device_library.merge_library(existing, data))
        except (HarnessError, OSError) as exc:
            self._error(self._explain(exc, target.parent))
            return
        self.toasts.show_message(strings.DV_LIB_SAVED.format(unit_id, target.name), None)

    # ---- the library window and its folder (workshop M4, D-175) -------------------------------------
    def library_folder(self) -> str:
        """The library folder of this person ('' while none is chosen); kept in the settings."""
        return str(self.settings.value(LIBRARY_FOLDER_KEY, "") or "")

    def set_library_folder(self, folder: str) -> None:
        """Use this folder as the library ('' for none): stored, shown on the Settings page and read
        by the library window if it is open. Nothing is written into the folder."""
        folder = folder.strip()
        if folder:
            self.settings.setValue(LIBRARY_FOLDER_KEY, folder)
        else:
            self.settings.remove(LIBRARY_FOLDER_KEY)
        self.settings_page.show_library_folder(folder)
        if self.library_window is not None:
            self.library_window.set_folder(folder)

    def choose_library_folder_flow(self) -> None:
        """File > Library folder…: ask for the folder and use it."""
        path = self.ask_folder(strings.LIB_FOLDER_TITLE)
        if path:
            self.set_library_folder(path)

    def open_library_flow(self) -> None:
        """File > Library… (Ctrl+Shift+O): the library window, beside the editor, not modal."""
        win = self.library_window
        if win is None:
            win = LibraryWindow(self.ctl, self.theme, self.settings, self)
            win.run_dialog = lambda dlg: self.run_dialog(dlg)
            win.folderChangeRequested.connect(self.choose_library_folder_flow)
            self.library_window = win
        win.show()
        win.raise_()
        win.activateWindow()

    def add_from_library_flow(self) -> None:
        """ "Add from library…" of the Devices tab: choose a file, tick the devices, add them as
        one undo step."""
        if self.ctl.read_only:
            self.ctl.refuse_read_only()
            return
        path = self.ask_open_path(strings.DV_LIB_OPEN_TITLE, strings.DV_LIB_FILTER)
        if not path:
            return
        try:
            data = device_library.read_library(Path(path))
        except (HarnessError, OSError) as exc:
            self._error(self._explain(exc, Path(path).parent))
            return
        dlg = LibraryDialog(self, self.theme, self.ctl.project, data)
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return
        plan = dlg.plan()
        if not plan.ops or not self.ctl.run(strings.STEP_ADD_DEVICES, plan.ops):
            return
        added = [r.new_id for r in plan.rows if r.ok]
        self.go_to("devices")
        self.devices_view.show_unit(added[0])
        self.toasts.show_message(strings.DV_LIB_ADDED.format(len(added), Path(path).name), None)

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
    def _ask_open_path(title: str, filters: str) -> str | None:
        path, _ = QFileDialog.getOpenFileName(None, title, "", filters)
        return path or None

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
        self.act_import = a(
            strings.A_IMPORT, self.import_interfaces_flow, "Ctrl+Shift+I", name="act-import"
        )
        self.act_library = a(
            strings.A_LIBRARY, self.open_library_flow, "Ctrl+Shift+O", name="act-library"
        )
        self.act_library.setToolTip(strings.A_LIBRARY_TIP)
        self.act_library_folder = a(
            strings.A_LIBRARY_FOLDER, self.choose_library_folder_flow, name="act-library-folder"
        )
        self.act_library_folder.setToolTip(strings.A_LIBRARY_FOLDER_TIP)
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
            # not from other panels (the project tree reports its own Delete)
            only_in=(self.view, self.interface_table.view, self.unit_table.view),
        )
        self.act_redundant = a(
            strings.REDUNDANT_COPY, self._redundant_selected, name="act-redundant"
        )
        self.act_connect_tool = a(
            strings.TOOL_CONNECT, self.ctl.begin_link, "C", name="act-connect"
        )  # the pinout way; the interface types are in Edit > Connect with an interface type
        self.act_link_connectors = a(
            strings.A_LINK, self.link_flow, "Ctrl+Shift+K", name="act-link-connectors"
        )
        self.act_link_edit = a(strings.A_LINK_EDIT, self.edit_link_flow, name="act-link-edit")
        self.act_link_rename = a(
            strings.A_LINK_RENAME, self.rename_link_flow, name="act-link-rename"
        )
        self.act_link_harness = a(
            strings.A_LINK_HARNESS, self.create_harness_flow, name="act-link-harness"
        )
        self.act_link_show_harness = a(
            strings.A_LINK_SHOW_HARNESS, self.show_link_harness_flow, name="act-link-show-harness"
        )
        self.act_link_show_harness.setToolTip(strings.A_LINK_SHOW_HARNESS_TIP)
        self.act_link_delete = a(
            strings.A_LINK_DELETE, self.delete_link_flow, name="act-link-delete"
        )
        self.act_check_connections = a(
            strings.A_CHECK_CONNECTIONS, self.check_connections_flow, name="act-check-connections"
        )
        self.act_select_tool = a(strings.TOOL_SELECT, self.ctl.end_connect, name="act-select")
        self.act_add_zone = a(strings.A_ADD_ZONE, self.add_zone_flow, name="act-add-zone")
        # the two roles (D-176): exclusive, checkable; View > Role and Settings are views of them
        self.act_role_systems = a(
            strings.ROLE_SYSTEMS,
            lambda: self.set_role(SYSTEMS),
            checkable=True,
            name="act-role-systems",
        )
        self.act_role_electrical = a(
            strings.ROLE_ELECTRICAL,
            lambda: self.set_role(ELECTRICAL),
            checkable=True,
            name="act-role-electrical",
        )
        self.act_role_systems.setToolTip(strings.ROLE_SYSTEMS_TIP)
        self.act_role_electrical.setToolTip(strings.ROLE_ELECTRICAL_TIP)
        rgroup = QActionGroup(self)
        rgroup.addAction(self.act_role_systems)
        rgroup.addAction(self.act_role_electrical)
        self.act_role_electrical.setChecked(True)
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
        self.act_connection_ends = a(
            strings.A_CONNECTION_ENDS,
            self._toggle_connection_ends,
            checkable=True,
            name="act-connection-ends",
        )
        self.act_connection_ends.setToolTip(strings.A_CONNECTION_ENDS_TIP)
        self.act_reduce_motion = a(
            strings.SETTINGS_REDUCE_MOTION,
            self._toggle_reduce_motion,
            checkable=True,
            name="act-reduce-motion",
        )
        self.act_minimap.setChecked(True)
        self.act_problem_notices = a(
            strings.A_PROBLEM_NOTICES,
            self._toggle_problem_notices,
            checkable=True,
            name="act-problem-notices",
        )
        self.act_problem_notices.setToolTip(strings.A_PROBLEM_NOTICES_TIP)
        self.act_problem_notices.setChecked(True)
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
        self.act_changes = a(strings.A_CHANGES, partial(self.harness_step, "changes"), name="act-changes")  # fmt: skip
        self.act_history = a(strings.A_HISTORY, partial(self.harness_step, "history"), name="act-history")  # fmt: skip
        self.act_delete_harness = a(strings.A_DELETE_HARNESS, partial(self.harness_step, "delete"), name="act-delete-harness")  # fmt: skip
        self.act_changes.setToolTip(strings.CHANGES_TIP)
        self.act_history.setToolTip(strings.HISTORY_TIP)
        self.act_delete_harness.setToolTip(strings.DELETE_HARNESS_TIP)
        self.act_values = a(strings.A_VALUES, self.values_flow, name="act-values")
        self.act_new_interface = a(
            strings.A_NEW_INTERFACE, self.new_interface_flow, "Ctrl+I", name="act-new-interface"
        )
        self.act_add_device = a(
            strings.A_ADD_DEVICE, self.add_device_flow, "Ctrl+Shift+N", name="act-add-device"
        )
        self.act_add_device.setToolTip(f"{strings.A_ADD_DEVICE_TIP} (Ctrl+Shift+N)")
        self.act_new_harness = a(
            strings.A_NEW_HARNESS, self.new_harness_flow, "Ctrl+Shift+H", name="act-new-harness"
        )
        self.act_new_harness.setToolTip(f"{strings.A_NEW_HARNESS_TIP} (Ctrl+Shift+H)")
        self.act_bulk_wires = a(
            strings.A_BULK_WIRES, self.bulk_wires_flow, "Ctrl+Shift+B", name="act-bulk-wires"
        )
        self.act_bulk_wires.setToolTip(f"{strings.A_BULK_WIRES_TIP} (Ctrl+Shift+B)")
        self.act_problems = a(
            strings.A_PROBLEMS, self.toggle_problems, "Ctrl+Shift+M", name="act-problems"
        )
        self.act_reset_layout = a(
            strings.A_RESET_LAYOUT, self.reset_layout, name="act-reset-layout"
        )
        # the way back to the side panels in the Systems engineer role (stage S2); it exists, hidden
        # and disabled (so the palette skips it), in the Electrical / AIT engineer role
        self.act_show_panels = a(
            strings.A_SHOW_PANELS,
            lambda: self.show_panels(self.act_show_panels.isChecked()),
            checkable=True,
            name="act-show-panels",
        )
        self.act_show_panels.setToolTip(strings.SHOW_PANELS_TIP)
        self.act_show_panels.setEnabled(False)
        self.act_show_panels.setVisible(False)
        self.act_next_pane = a(strings.A_NEXT_PANE, partial(self._cycle, 1), "F6", name="act-next-pane")  # fmt: skip
        self.act_prev_pane = a(strings.A_PREV_PANE, partial(self._cycle, -1), "Shift+F6", name="act-prev-pane")  # fmt: skip
        self.go_actions: dict[str, QAction] = {}
        self.act_go_home = a(
            strings.GO_HOME, lambda: self.set_area("home"), "Ctrl+7", name="act-go-home"
        )
        self.act_go_settings = a(strings.GO_SETTINGS, lambda: self.set_area("settings"), "Ctrl+,", name="act-go-settings")  # fmt: skip
        for k, (name, label) in enumerate(
            zip(
                MAIN_TABS,
                (
                    strings.A_GO_DIAGRAM,
                    strings.A_GO_HARNESS,
                    strings.A_GO_LISTS,
                    strings.A_GO_CHECKS,
                    strings.A_GO_RELEASES,
                    strings.A_GO_DEVICES,
                ),  # fmt: skip
                strict=True,
            ),
            start=1,
        ):
            self.go_actions[name] = a(label, partial(self._go_tab, name), f"Ctrl+{k}", name=f"act-go-{name}")  # fmt: skip
        self.act_go_interfaces = a(
            strings.A_GO_INTERFACES, self.show_interfaces, "Ctrl+Shift+T", name="act-go-interfaces"
        )
        self.act_go_units = a(
            strings.A_GO_UNITS, self.show_units, "Ctrl+Shift+J", name="act-go-units"
        )
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
            "link_edit": self.act_link_edit,
            "link_harness": self.act_link_harness,
            "link_show_harness": self.act_link_show_harness,
            "link_delete": self.act_link_delete,
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
        f.addAction(self.act_library)
        f.addAction(self.act_library_folder)
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
        e.addAction(self.act_link_connectors)
        e.addAction(self.act_connect_tool)
        align_menu = e.addMenu(strings.A_ALIGN)
        for act in self.align_actions.values():
            align_menu.addAction(act)
        spread_menu = e.addMenu(strings.A_DISTRIBUTE)
        for act in self.distribute_actions.values():
            spread_menu.addAction(act)
        e.addAction(self.act_add_zone)
        e.addAction(self.act_new_harness)
        e.addAction(self.act_bulk_wires)
        e.addAction(self.act_wire_colours)
        self.menu_add = e.addMenu(strings.M_ADD_UNIT)
        self.menu_add.addAction(self.act_add_device)
        self.menu_add.addSeparator()
        for tid, tpl in edit.TEMPLATES.items():
            act = self._act(tpl.label, partial(self._add_unit, tid), name=f"menu-add-{tid}")
            self.menu_add.addAction(act)
        self.menu_connect = e.addMenu(strings.M_CONNECT_WITH_TYPE)  # the older, interface-first way
        self.menu_connection = e.addMenu(strings.M_CONNECTION)
        for act in (
            self.act_link_edit,
            self.act_link_rename,
            self.act_link_harness,
            self.act_link_show_harness,
            self.act_link_delete,
        ):
            self.menu_connection.addAction(act)
        self._rebuild_connect_menu()
        self.tool_connect.setMenu(self.menu_connect)
        v = mb.addMenu(strings.M_VIEW)
        v.addAction(self.act_show_panels)  # (the Systems engineer role only)
        v.addSeparator()
        self.menu_role = v.addMenu(strings.M_ROLE)
        self.menu_role.setObjectName("menu-role")
        self.menu_role.addAction(self.act_role_systems)
        self.menu_role.addAction(self.act_role_electrical)
        v.addSeparator()
        v.addAction(self.act_problem_notices)
        v.addSeparator()
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
        v.addAction(self.act_connection_ends)
        v.addAction(self.act_reduce_motion)
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
        for dock in (self.dock_left, self.dock_right):
            v.addAction(dock.toggleViewAction())
        v.addAction(self.act_problems)
        v.addAction(self.act_reset_layout)
        d = mb.addMenu(strings.M_DESIGN)
        self.menu_design = d
        for act in (self.act_generate, self.act_check, self.act_cancel_check, self.act_export):
            d.addAction(act)
        d.addAction(self.act_check_connections)
        d.addSeparator()
        for act in (
            self.act_review,
            self.act_release,
            self.act_revise,
            self.act_changes,
            self.act_history,
            self.act_delete_harness,
        ):
            d.addAction(act)
        d.addSeparator()
        d.addAction(self.act_values)
        g = mb.addMenu(strings.M_GO)
        self.menu_go = g
        g.addAction(self.act_go_home)
        for act in self.go_actions.values():
            g.addAction(act)
        g.addAction(self.act_go_settings)
        g.addAction(self.act_go_interfaces)
        g.addAction(self.act_go_units)
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

        # the top bar: one full-width row above everything (project, state, where you are, edit,
        # mode, search, the three jobs)
        tb = QToolBar(strings.TOOLBAR)
        tb.setObjectName("main-toolbar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.addWidget(self.topbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        self.top_toolbar = tb
        self.rail = NavRail(self.theme)
        rail_bar = QToolBar(strings.RAIL_NAME)
        rail_bar.setObjectName("rail-toolbar")
        rail_bar.setMovable(False)
        rail_bar.setFloatable(False)
        rail_bar.addWidget(self.rail)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, rail_bar)
        self.rail_toolbar = rail_bar
        self.rail.select(self._area)
        self.rail.areaSelected.connect(self.set_area)
        self.act_undo.setIcon(icon("undo", self.theme))
        self.act_redo.setIcon(icon("redo", self.theme))
        self.act_redo.setToolTip(tooltip_text(strings.REDO, "Ctrl+Y"))
        for act, name in ((self.act_undo, "undo-button"), (self.act_redo, "redo-button")):
            button = QToolButton()
            button.setObjectName(name)
            button.setDefaultAction(act)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setProperty("iconOnly", True)
            button.setFocusPolicy(
                Qt.FocusPolicy.StrongFocus
            )  # reachable with Tab, not only by shortcut
            self.topbar.add_edit(button)
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
        self.topbar.add_mode(self.mode_guided)
        self.topbar.add_mode(self.mode_expert)
        # "Show panels": the way back to the project tree and the properties in the
        # Systems engineer role (stage S2); the button shows there only
        self.panels_btn = QToolButton()
        self.panels_btn.setObjectName("panels-button")
        self.panels_btn.setCheckable(True)
        self.panels_btn.clicked.connect(
            lambda _c=False: self.show_panels(self.panels_btn.isChecked())
        )
        icon_button(
            self.panels_btn,
            "panel-open",
            self.theme,
            strings.SHOW_PANELS_TIP,
            text=strings.SHOW_PANELS_BUTTON,
        )
        self.panels_btn.setAccessibleName(strings.SHOW_PANELS_BUTTON)
        self.panels_btn.setProperty("toggle", True)
        self.panels_btn.setVisible(False)
        self.topbar.add_mode(self.panels_btn)
        for dock in (self.dock_left, self.dock_right):
            dock.visibilityChanged.connect(lambda _v=False: self._sync_panels_action())
        # the More menu of the diagram tool row (Systems engineer role): every tool the row leaves out
        self.menu_more = QMenu(self.tool_more)
        self.menu_more.setObjectName("menu-more")
        self.menu_more.setToolTipsVisible(True)
        for act in (self.act_redundant, self.act_delete):
            self.menu_more.addAction(act)
        self.menu_more.addSeparator()
        for act in (self.act_zoom_out, self.act_zoom_in, self.act_fit, self.act_arrange):
            self.menu_more.addAction(act)
        self.menu_more.addSeparator()
        self.menu_more_filter = self.menu_more.addMenu(strings.TOOL_MORE_FILTER)
        self.menu_more_filter.setObjectName("menu-more-filter")
        self.menu_more_filter.aboutToShow.connect(self._rebuild_more_filter)
        self.tool_more.setMenu(self.menu_more)
        self.tool_add_device.clicked.connect(lambda _c=False: self.act_add_device.trigger())
        self.act_add_device.changed.connect(
            lambda: self.tool_add_device.setEnabled(self.act_add_device.isEnabled())
        )
        self.arrange_btn = QToolButton()
        self.arrange_btn.setObjectName("arrange-button")
        self.arrange_btn.setDefaultAction(self.act_arrange)
        self.arrange_btn.setText(strings.A_ARRANGE)
        self.arrange_btn.setToolTip(strings.ARRANGE_TIP)
        self.arrange_btn.setAccessibleName(strings.A_ARRANGE)
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
        self.topbar.add_search(self.search_btn)
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
        self.filter_value = QComboBox()
        self.filter_value.setObjectName("filter-value")
        self.filter_value.setAccessibleName(strings.FILTER_VALUE)
        self.filter_value.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.filter_value.currentIndexChanged.connect(self._filter_changed)
        self.filter_value.setVisible(False)
        self.filter_value_action = self.filter_value  # (the toolbar action it once had)
        # Arrange and the filters act on the diagram only: they sit at the right end of the Model
        # area's tab bar (a corner widget), which has the room the diagram's tool row has not
        self.filter_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.filter_combo.setMinimumContentsLength(10)
        self.diagram_tools = QWidget()
        self.diagram_tools.setObjectName("diagram-tools")
        row = QHBoxLayout(self.diagram_tools)
        row.setContentsMargins(self.theme.space(4), 0, self.theme.space(8), 0)
        row.setSpacing(self.theme.space(8))
        for w in (self.arrange_btn, self.filter_combo, self.filter_value):
            row.addWidget(w)
        self.main_tabs.setCornerWidget(self.diagram_tools, Qt.Corner.TopRightCorner)
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
        self.filter_value.setVisible(bool(kind) and self.filter_value.count() > 0)

    def _filter_kind_changed(self, _index: int) -> None:
        self._refresh_filter_values()
        self._filter_changed(0)

    def _set_filter(self, kind: str | None, value: str | None) -> None:
        """Show only one signal class, connector or bundle (or all): the same as the two pickers
        of the Model tab, which the Systems engineer role hides."""
        self.filter_combo.setCurrentIndex(max(self.filter_combo.findData(kind), 0))
        if kind and value is not None:
            at = self.filter_value.findData(value)
            if at >= 0:
                self.filter_value.setCurrentIndex(at)

    def _rebuild_more_filter(self) -> None:
        """The "Show only" entries of the More menu, ticked for the filter in force."""
        menu = self.menu_more_filter
        menu.clear()
        kind, value = self.filter_combo.currentData(), self.filter_value.currentData()
        everything = menu.addAction(strings.FILTER_ALL)
        everything.setCheckable(True)
        everything.setChecked(not kind)
        everything.triggered.connect(lambda _c=False: self._set_filter(None, None))
        for title, k in (
            (strings.FILTER_CLASS, "class"),
            (strings.FILTER_CONNECTOR, "connector"),
            (strings.FILTER_BUNDLE, "bundle"),
        ):
            sub = menu.addMenu(title)
            options = self._filter_options(k)
            sub.setEnabled(bool(options))
            for text, v in options:
                act = sub.addAction(text)
                act.setCheckable(True)
                act.setChecked(kind == k and value == v)
                act.triggered.connect(lambda _c=False, k=k, v=v: self._set_filter(k, v))

    def _filter_changed(self, _index: int) -> None:
        kind = self.filter_combo.currentData()
        self.view.dscene.set_filter(kind, self.filter_value.currentData() if kind else None)

    def _sync_connect_menu(self) -> None:
        """Tick the interface type the Connect tool is using (and none while it is off)."""
        c = self.ctl
        for act in self.menu_connect.actions():
            act.setChecked(
                c.tool == "connect"
                and act.objectName().removeprefix("menu-connect-") == c.connect_type
            )

    def _rebuild_connect_menu(self) -> None:
        for old in self.menu_connect.actions():  # `_act` also registered them on the window
            self.removeAction(old)
            old.deleteLater()
        self.menu_connect.clear()
        for tid, t in sorted(self.ctl.project.interface_types.items()):
            act = self._act(
                t.name,
                partial(self._toggle_connect, tid),
                checkable=True,
                name=f"menu-connect-{tid}",
            )
            act.setIcon(category_icon(t.category, self.theme))
            self.menu_connect.addAction(act)
        self._sync_connect_menu()

    def _tour_reveals(self) -> dict[str, Callable[[], None]]:
        """The step about adding units needs the project tree in front, the one about problems
        the Problems tab of the inspector."""

        def tree() -> None:
            self.left_tabs.setCurrentIndex(self.left_tabs.index_of("tree"))

        def problems() -> None:
            self.inspector.show_tab("problems")

        return {"add": tree, "problems": problems}

    def _tour_targets(self) -> dict[str, QWidget]:
        return {
            "add": self.left_tabs,
            "canvas": self.view,
            "types": self.tool_connect,
            "problems": self.side_tabs,
            "generate": self.generate_btn,
            "role": self.rail,
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
        self.act_add_device.setEnabled(not ro)
        self.act_new_harness.setEnabled(not ro)
        self.act_bulk_wires.setEnabled(not ro)
        self.menu_add.setEnabled(not ro)  # the ways to add a unit and to connect (the Palette's)
        self.menu_connect.setEnabled(not ro)
        self.act_link_connectors.setEnabled(not ro)
        self._on_link_selection()
        self.act_generate.setEnabled(not ro)
        self.act_wire_colours.setEnabled(not ro)
        unsaved = strings.UNSAVED if c.autosaves else strings.UNSAVED_NO_JOURNAL
        self.status_saved.setText(unsaved if c.dirty else strings.ALL_SAVED)
        self._refresh_undo_actions()
        self._update_banner()
        self._update_problems_button()
        self._update_selection_actions()
        self._update_view_actions()
        self._update_lock_banner()
        self.act_cancel_check.setEnabled(c.drc_busy())
        # a newly opened project is read at once; an edit waits for the pause (hashing takes time)
        opened = self._facts_token is None or self._facts_token[0] != c.state_token[0]
        self._show_status(path=True, compute=opened)
        self._hash_timer.start()

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
        status = ShellStatus(
            name=c.project.meta.name,
            model_hash=digest,
            dirty=c.dirty,
            read_only=c.read_only,
            generation=generation,
            outputs=outputs,
            running=self.busy,
            checking=c.drc_busy(),
            has_harnesses=bool(c.project.harnesses),
            units=len(c.project.units),
            interfaces=len(c.project.interfaces),
            links=len(c.project.links),
            generated_at=record.input_hash[:8] if record is not None else "",
            revision=self._revision_text(),
        )
        return replace(status, **self._workflow_facts())

    def _workflow_facts(self) -> dict[str, Any]:
        """What the Check and Release steps need: the rule results and the harness statuses."""
        c = self.ctl
        results = c.drc_rule_results() if c.drc_current else []
        summary = by_rule.summary(results) if results else None
        statuses = [h.status for h in c.project.harnesses.values()]
        return {
            "checked": bool(c.drc_current and results),
            "failed": summary.failed if summary else 0,
            "unchecked": (summary.not_checked + summary.pending) if summary else 0,
            "harnesses": len(statuses),
            "hand_made": sum(1 for h in c.project.harnesses.values() if not h.generated),
            "in_review": statuses.count("in_review"),
            "released": statuses.count("released"),
        }

    def _revision_text(self) -> str:
        revs = sorted({h.revision for h in self.ctl.project.harnesses.values()})
        if not revs:
            return ""
        return revs[0] if len(revs) == 1 else f"{revs[0]}-{revs[-1]}"

    def _show_status(self, *, path: bool, compute: bool = True) -> None:
        """Push the status into the top bar, the banner and the status bar."""
        status = self.shell_status(compute)
        self.topbar.apply(status)
        self._update_next(status)
        self._update_home()
        self.status_hash.setText(status.model_hash)
        self.status_counts.setToolTip(
            " · ".join(
                (
                    f"{strings.STATUS_HASH} {status.model_hash}",
                    self.status_rules.text(),
                    self.status_generated.text(),
                )
            )
        )
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

    def _fit_status(self) -> None:
        """The status bar gives up its least important parts when the window is narrow, so what is
        left is never cut: the selection first, then the counts and the folder, then the save text
        (the top bar says it too). The job indicator, Problems, Offline, the pending-values link
        and the zoom stay."""
        eff = self.width() / self.theme.scale
        counts = self.role != SYSTEMS  # (the Systems engineer role shows no counts)
        self.status_sel.setVisible(counts and eff >= 1400)
        self.status_counts.setVisible(counts and eff >= 1250)
        self.status_path.setVisible(eff >= 1250)
        self.status_saved.setVisible(eff >= 1100)

    def _update_problems_button(self) -> None:
        self.problems_btn.setText(strings.PROBLEMS_BUTTON.format(len(self.ctl.open_findings())))

    # ---- Home: recent projects and the examples -------------------------------------------------
    @staticmethod
    def _examples_folder() -> Path:
        """Where "Try the flatsat example" puts its copy: Documents/Harness Design Studio."""
        docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        return Path(docs or str(Path.home())) / "Harness Design Studio"

    def open_example_flow(self, name: str) -> None:
        """Open a packaged example as a copy of its own in the examples folder (made the first time,
        opened as it is afterwards, so the person's changes to it stay)."""
        from harness_design_studio.core import templates

        if not self._confirm_discard():
            return
        dest = self.examples_folder() / name
        try:
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                templates.create_project(dest, name)
        except (templates.TemplateError, OSError) as exc:
            self._error(str(exc))
            return
        self.open_project(dest)

    def open_recent_flow(self, path: str) -> None:
        if not Path(path).is_dir():
            self.toasts.show_message(strings.HOME_MISSING.format(path), None)
            return
        if self._confirm_discard():
            self.open_project(Path(path))

    def forget_recent(self, path: str) -> None:
        recent.forget(self.settings, path)
        self._update_home()

    def _remember_current(self) -> None:
        c = self.ctl
        root = c.root
        if root is None:
            return
        statuses = [h.status for h in c.project.harnesses.values()]
        recent.remember(
            self.settings,
            recent.RecentEntry(
                path=str(root),
                name=c.project.meta.name,
                units=len(c.project.units),
                interfaces=len(c.project.interfaces),
                harnesses=len(statuses),
                draft=statuses.count("draft"),
                in_review=statuses.count("in_review"),
                released=statuses.count("released"),
            ),
        )

    def _update_home(self) -> None:
        c = self.ctl
        p = c.project
        root = c.root
        self._remember_current()
        entries = recent.load(self.settings)
        if entries != self._recent_shown:
            self._recent_shown = entries
            self.home_page.set_recent(entries, exists=lambda path: Path(path).is_dir())
        self.home_page.show_project(
            p.meta.name or strings.TB_UNSAVED_PROJECT,
            str(root) if root is not None else "",
            strings.HOME_SUMMARY.format(len(p.units), len(p.interfaces), len(p.harnesses)),
        )
        self._sync_settings_page()

    def _update_alerts(self, status: ShellStatus) -> None:
        """The persistent notice when the plans or the exported files no longer match the design:
        it stays (hidden only by the person, until the design changes again) and carries the
        buttons that fix it."""
        self._update_lock_banner()
        plans = status.generation == "stale"
        files = status.has_harnesses and status.outputs in ("stale", "modified", "unreadable")
        key = (plans, files, status.model_hash)
        if (
            self.ctl.read_only
            or not (plans or files)
            or self._dismissed_alert == key
            or not self.problem_notices_on()
        ):
            self.alerts.clear("stale")
            return
        if plans and files:
            text = strings.BN_BOTH_STALE
        elif plans:
            text = strings.BN_PLANS_STALE
        else:
            text = strings.BN_OUTPUTS_STALE
        details = []
        if status.generated_at:
            details.append(strings.BN_DETAIL_GENERATED.format(status.generated_at))
        elif not (status.harnesses and status.hand_made == status.harnesses):
            # (harnesses made from connections or by hand are never generated: no such line)
            details.append(strings.BN_DETAIL_NOT_GENERATED)
        actions: list[tuple[str, Callable[[], None]]] = []
        if plans:
            actions.append((strings.BN_GENERATE, self.act_generate.trigger))
        if files:
            actions.append((strings.BN_EXPORT, self.act_export.trigger))
            if plans:
                details.append(strings.BN_DETAIL_ORDER)
        self.alerts.show_banner("stale", "warning", text, details=details, actions=actions)

    def _locked_refs(self) -> list[tuple[str, str]]:
        """(harness, revision) of the released harnesses that lock what is in front of you: the
        harness shown in Drawings, the one chosen in Revisions, or the selected unit or link."""
        c = self.ctl
        released = {
            h.id: h.revision for h in c.project.harnesses.values() if h.status == "released"
        }
        if not released:
            return []
        hid: str | None = None
        if self._area == "drawings" and self.view_installed("harness"):
            selector = getattr(self.harness_target(), "selector", None)
            hid = str(selector.currentData() or "") if selector is not None else None
        elif self._area == "revisions":
            hid = self.releases_panel.current_harness()
        elif self._area in ("model", "checks", "outputs"):
            s = c.selection
            if s is not None and s.kind in ("unit", "interface"):
                return [r for r in c.state_index().of(s.kind, s.id).locks]
            return []
        return [(hid, released[hid])] if hid in released else []

    def _update_lock_banner(self) -> None:
        """Released data is unmistakably locked: a banner over the work area says so and offers
        the way out, a new revision."""
        refs = self._locked_refs()
        if not refs:
            self.alerts.clear("locked")
            return
        text = (
            strings.LOCK_BANNER_ONE.format(*refs[0])
            if len(refs) == 1
            else strings.LOCK_BANNER_MANY.format(len(refs))
        )
        first = refs[0][0]
        actions: list[tuple[str, Callable[[], None]]] = []
        if not self.ctl.read_only:
            actions.append((strings.LOCK_BANNER_ACTION, lambda: self.change_flow("revise", first)))
        self.alerts.show_banner("locked", "info", text, actions=actions, dismissible=False)

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
        self._update_lock_banner()
        if len(c.selected) > 1:
            self.status_sel.setText(strings.SELECTED_MANY.format(len(c.selected)))
        else:
            self.status_sel.setText(strings.SELECTED.format(s.id) if s else strings.NOTHING_SEL)
        if s is not None and s.kind == "unit":
            self.view.reveal(s.id)
        if s is not None and not self.dock_right.isVisibleTo(self) and not self._told_properties:
            self._told_properties = True
            if self.role == SYSTEMS:
                self.toasts.show_message(
                    strings.PROPERTIES_CLOSED,
                    None,
                    8000,
                    action=(strings.SHOW_PANELS_BUTTON, lambda: self.show_panels(True)),
                )
            else:
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
        self._sync_connect_menu()
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
            f"<li><b>{u}</b> (device {project.units[u].name})</li>" for u in sorted(units)
        )
        for iid in sorted(set(links) - gone):
            impact = edit.interface_impact(project, iid)
            items += f"<li><b>{iid}</b> ({impact.type_name}, {' to '.join(impact.ends)})</li>"
        if gone:
            items += f"<li>{strings.interfaces_text(len(gone))} of the devices: {', '.join(sorted(gone))}</li>"
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
        if kind == "link":  # a connection of two connectors: its pairs
            self.edit_link_flow(ident)
            return
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
        """The widget that shows harnesses: the Harness view."""
        return self.view_widget("harness")

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
        """Show the harnesses: the Harness tab."""
        self.main_tabs.show_slot("harness")

    def _compute_plan(self) -> GenerationPlan | None:
        """Plan in a worker thread behind a cancellable progress dialog; None if cancelled."""
        worker = PlanWorker(edit.clone_with(self.ctl.project, []))
        self._run_worker(worker, strings.GEN_RUNNING, "generate-progress")
        self.job_error = worker.error
        return worker.plan

    def _run_worker(
        self, worker: "PlanWorker | OutputsWorker | ArrangeWorker", label: str, name: str
    ) -> None:
        self._active_worker = worker
        self._set_busy(
            "generate" if isinstance(worker, PlanWorker)
            else "export" if isinstance(worker, OutputsWorker) else "arrange"
        )  # fmt: skip
        try:
            self._run_worker_loop(worker, label, name)
        finally:
            self._active_worker = None
            self._set_busy(None)

    def _set_busy(self, kind: str | None) -> None:
        """A job runs (or has just ended): the chip says so and the buttons wait."""
        self.busy = kind
        self.topbar.update_status(running=kind)
        self._update_jobs()

    def _update_jobs(self) -> None:
        """The status bar's job indicator: the running job (generate, export, arrange or the rule
        check) with Cancel, or the last result."""
        if self.busy:
            text = {
                "generate": strings.JOB_GENERATING,
                "export": strings.JOB_EXPORTING,
                "arrange": strings.JOB_ARRANGING,
            }.get(self.busy, self.busy)
            worker = self._active_worker
            self.jobs.start(text, cancel=worker.cancel if worker is not None else None)
        elif self.ctl.drc_busy():
            self.jobs.start(strings.JOB_CHECKING, cancel=self.ctl.cancel_check)
        else:
            self.jobs.finish()

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
        self.ctl.apply_change(plan, msg)

    # ---- change control on "the" harness (menu, shortcut, Ctrl+K) ----------------------------------
    def current_harness(self) -> str | None:
        """The harness the person is looking at: the Harness view's, the Releases tab's, or the
        tree's; None when none is chosen."""
        project = self.ctl.project
        candidates: list[object] = []
        if self.view_installed("harness"):
            view = self.view_widget("harness")
            candidates.append(
                getattr(view, "harness_id", getattr(view, "current_harness", lambda: None))()
            )
        if self.main_tabs.currentWidget() is self.releases_panel:
            candidates.append(self.releases_panel.current_harness())
        tree_row = self.project_tree.current()
        if tree_row is not None and tree_row[0] == "harness":
            candidates.append(tree_row[1])
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

    def harness_step(self, action: str) -> None:
        """Changes, change log or delete for "the" harness (menu, tree, Ctrl+K): the one in view,
        else the only one there is; with several, the Releases tab opens so one can be chosen."""
        project = self.ctl.project
        if not project.harnesses:
            self.toasts.show_message(strings.NO_HARNESSES_FOR_ACTION, None)
            return
        chosen = self.current_harness()
        if chosen is None and len(project.harnesses) == 1:
            chosen = next(iter(project.harnesses))
        if chosen is None:
            self.go_to("releases")
            self.toasts.show_message(strings.NO_HARNESS_FOR_ACTION, None)
            return
        if action == "delete" and self.ctl.read_only:
            self.ctl.refuse_read_only()
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
        if not busy and self.ctl.drc_current:
            self._last_check = strings.JOB_LAST_CHECK.format(time.strftime("%H:%M"))
            self.jobs.finish(self._last_check)
        self._update_jobs()
        self._update_problems_button()
        self._update_next(self.shell_status(compute=False))  # the Check step may be done now
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
        """Show a main view: diagram, harness, lists, checks or releases (False and a note when
        the view is not installed)."""
        if self.main_tabs.is_installed(name):
            self._show_area(areas.area_of_tab(name), tab=name)
            return self.main_tabs.show_slot(name)
        title = {"lists": strings.TAB_LISTS}.get(name, name)
        self.toasts.show_message(strings.VIEW_NOT_INSTALLED.format(title), None)
        return False

    # ---- the role and the next step -------------------------------------------------------------------
    def _restore_role(self) -> None:
        """The role of this settings file. A stored role stands. Without one: a file that has values
        is an existing user (the choice of 1.7.0 carries over, anybody else is an Electrical / AIT
        engineer) and gets its role silently; a file with nothing stored gets the role the hook
        `roles.FIRST_RUN_ROLE` names, and with no hook the window asks once, when it shows
        (`ask_role_flow`) and starts as an Electrical / AIT engineer until the person answers."""
        stored = clean_role(self.settings.value("ui/role", ""), "")
        if stored:
            self._apply_role(stored)
            return
        value = default_role(not self._settings_were_empty, self.settings.value("ui/workspace"))
        if value is None:
            self._role_to_ask = self._first_start
            self._apply_role(ELECTRICAL)  # (not stored: the answer is)
            return
        self.settings.setValue("ui/role", value)
        self._apply_role(value)

    def _apply_role(self, value: str) -> None:
        """What the role decides at once: the checked actions, the rail, the tool row of the
        diagram, the status bar and the way back to the panels (the panels, minimap and legend
        come from the layout memory, `_load_role_layout`)."""
        self.role = value
        systems = value == SYSTEMS
        self.act_role_systems.setChecked(systems)
        self.act_role_electrical.setChecked(not systems)
        self.next_page.set_role(value)
        self.rail.set_hidden(areas.hidden_in(value))
        for w in (self.redundant_btn, self.delete_btn, self.zoom_out_btn, self.zoom_in_btn):
            w.setVisible(not systems)
        self.fit_btn.setVisible(not systems)
        self.tool_add_device.setVisible(systems)
        self.tool_more.setVisible(systems)
        self.zoom_level.setVisible(not systems)
        self.act_show_panels.setVisible(systems)
        self.act_show_panels.setEnabled(systems)
        self.panels_btn.setVisible(systems)
        self._sync_panels_action()
        self._update_crumbs()  # (Arrange and the filters of the Model tab)
        self._load_problem_notices()  # (each role has its own default and its own key)
        self._fit_status()

    def set_role(self, value: str, *, save_left: bool = True) -> None:
        """View > Role: store and apply the choice, and with it that role's own layout (panels,
        minimap, legend), at once. The layout of the role that is left is saved first, under its
        own keys (`save_left` False: nothing was set up yet, as at the first start). The open page
        stays; the next project that is opened shows the first page of the role."""
        value = clean_role(value, self.role)
        if value != self.role:
            if save_left:
                self._save_settings()  # the layout of the role being left
            self.settings.setValue("ui/role", value)
            self._apply_role(value)
            self._load_role_layout()
            self._restore_project_layout(with_area=False)
        else:
            self.settings.setValue("ui/role", value)
            self._apply_role(value)
        self._sync_settings_page()

    def ask_role_flow(self) -> str:
        """The question of the first start: *Who are you working as?* (a small modal window with
        two big buttons). The answer is stored and its layout applied at once; closing the window
        without choosing means Electrical / AIT engineer, which shows everything. A person who
        picks Systems engineer lands on the Next step page."""
        dlg = RoleDialog(self, self.theme)
        self.run_dialog(dlg)
        value = dlg.choice or ELECTRICAL
        self._role_to_ask = False
        self.set_role(value, save_left=False)
        if value == SYSTEMS:
            self._show_area("next")
        return value

    def _first_start_flow(self) -> None:
        """The first time the window shows: the question about the role, then the tour."""
        if not shiboken6.isValid(self):
            return
        if self._role_to_ask:
            self.ask_role_flow()
        if self._tour_wanted:
            QTimer.singleShot(200, self.tour.start)

    def _wkey(self, key: str) -> str:
        """A settings key of the layout, for the role that is open: the Electrical / AIT engineer
        keeps the keys the Full workspace had, the Systems engineer has keys of its own (the
        Simple workspace's; a layout saved in one never overwrites the other)."""
        return role_key(key, self.role)

    def _load_role_layout(self, *, initial: bool = False) -> None:
        """Minimap, legend and the panels of the role that is open: what was saved for it, or its
        start state (Electrical / AIT engineer: the usual panels for the window width; Systems
        engineer: every panel closed, minimap and legend off). `initial` is the call from the
        constructor."""
        simple = self.role == SYSTEMS
        for act, apply, key in (
            (self.act_minimap, self.view.set_minimap_wanted, "ui/minimap"),
            (self.act_legend, self.view.set_legend_wanted, "ui/legend"),
        ):
            wanted = bool(self.settings.value(self._wkey(key), not simple, bool))
            act.setChecked(wanted)
            apply(wanted)
        state = self.settings.value(self._wkey("ui/state"))
        try:  # a saved dock layout from a version with other docks is ignored
            restored = isinstance(state, QByteArray) and self.restoreState(state, STATE_VERSION)
        except TypeError:
            restored = False
        self._have_saved_state = restored
        if not restored:
            if not initial:
                self.restoreState(self._default_state, STATE_VERSION)
                for dock in (self.dock_left, self.dock_right):
                    dock.setFloating(False)
            if simple:
                self._close_panels()
        if self._shown:
            if simple or restored:
                self._layout_class = self._layout_class_now()
            else:
                self._layout_class = None
                self.auto_layout()
        self._sync_panels_action()

    def _close_panels(self) -> None:
        """Every dock closed: the start state of the Systems engineer role."""
        for dock in (self.dock_left, self.dock_right, self.dock_problems):
            dock.hide()

    def _panels_open(self) -> bool:
        return self.dock_left.isVisibleTo(self) or self.dock_right.isVisibleTo(self)

    def show_panels(self, on: bool) -> None:
        """Open or close the project tree and the inspector together (the Show panels toggle of
        the Systems engineer role; the Problems panel is its own toggle)."""
        self.dock_left.setVisible(on)
        self.dock_right.setVisible(on)
        self._sync_panels_action()

    def _sync_panels_action(self) -> None:
        """Show panels is ticked while the tree or the inspector is open (also when the person
        opened or closed one with its own control)."""
        on = self._panels_open()
        self.act_show_panels.setChecked(on)
        self.panels_btn.setChecked(on)

    def _need_inspector(self) -> None:
        """A person went to an object to look at it or change it. The Systems engineer role keeps
        the side panels closed until asked for, so this is the asking: the inspector opens. The
        Electrical / AIT engineer role is left alone."""
        if self.role == SYSTEMS and not self.dock_right.isVisibleTo(self):
            self.dock_right.show()

    def show_everything(self) -> None:
        """The link of the Next step page: the Electrical / AIT engineer role, on the diagram."""
        self.set_role(ELECTRICAL)
        self.set_area(areas.DEFAULT)

    def _open_for_role(self) -> None:
        """A project was opened: the Systems engineer role starts on the next step (the other one
        stays where it is)."""
        if self.role == SYSTEMS:
            self._show_area("next")

    def _next_inputs(self, s: ShellStatus) -> NextInputs:
        return NextInputs(
            units=s.units,
            interfaces=s.interfaces,
            links=s.links,
            harnesses=s.harnesses,
            hand_made_harnesses=s.hand_made,
            generation=s.generation,
            running=s.running,
            checked=s.checked,
            failed=s.failed,
            unchecked=s.unchecked,
            outputs=s.outputs,
            in_review=s.in_review,
            released=s.released,
            read_only=s.read_only,
            has_folder=self.ctl.root is not None,
        )

    def _update_next(self, status: ShellStatus) -> None:
        self.next_page.show_next(next_step(self._next_inputs(status)))

    def _next_go(self, view: str) -> None:
        self.go_to(view)

    def _next_connect(self) -> None:
        """The Next step button "Connect two devices": the diagram with the Connect tool."""
        self.go_to("diagram")
        self.act_connect_tool.trigger()

    def _next_make_harness(self) -> None:
        """The Next step button "Create harness": the first connection that has no harness."""
        p = self.ctl.project
        todo = [lid for lid in sorted(p.links) if not p.links[lid].harness_id]
        if todo:
            self.create_harness_flow(todo[0])

    def _next_fix(self) -> None:
        """The Next step button "Show the problems": the Checks, filtered to what failed."""
        self.go_to("checks")
        self.checks_panel.set_result_filter("fail")

    # ---- areas -----------------------------------------------------------------------------------
    def area(self) -> str:
        """The key of the area that is open: home, model, checks, drawings, outputs, revisions or
        settings."""
        return self._area

    def set_area(self, key: str) -> None:
        """Open an area (the rail's buttons call this): its first view, or the view that was open
        last when it is in the area."""
        if key not in areas.KEYS:
            return
        self._show_area(key)

    def _show_area(self, key: str, *, tab: str | None = None) -> None:
        a = areas.area(key)
        self._area = key
        self._switching_area = True
        self.rail.select(key)
        if not a.tabs:
            pages = {"home": self.home_page, "next": self.next_page}
            self.area_stack.setCurrentWidget(pages.get(key, self.settings_page))
        else:
            tabs = self.main_tabs
            tabs.set_filter(None)  # (every tab shows while one is chosen)
            names = tabs.names()
            want = tab
            if want is None:
                current = names[tabs.currentIndex()]
                want = current if current in a.tabs else next(
                    (n for n in a.tabs if tabs.is_installed(n)), None
                )  # fmt: skip
            if want is not None and tabs.is_installed(want):
                tabs.show_slot(want)
            tabs.set_filter(a.tabs)
            self.area_stack.setCurrentWidget(tabs)
        self._switching_area = False
        self._update_crumbs()
        self._update_lock_banner()

    def _tab_changed(self) -> None:
        """A tab was chosen (by a click, a shortcut or code): the rail follows it."""
        if self._switching_area:
            return
        names = self.main_tabs.names()
        i = self.main_tabs.currentIndex()
        if i < 0 or i >= len(names):
            return
        key = areas.area_of_tab(names[i])
        if key != self._area or self.area_stack.currentWidget() is not self.main_tabs:
            self._show_area(key, tab=names[i])
        else:
            self._update_crumbs()

    def _update_crumbs(self) -> None:
        a = areas.area(self._area)
        parts = [a.title]
        if a.tabs and len(a.tabs) > 1:
            names = self.main_tabs.names()
            i = self.main_tabs.currentIndex()
            if 0 <= i < len(names):
                parts.append(self.main_tabs.tabText(i))
        self.topbar.set_crumbs(strings.CRUMB_SEPARATOR.join(parts))
        names = self.main_tabs.names()
        i = self.main_tabs.currentIndex()
        on_diagram = 0 <= i < len(names) and names[i] == "diagram"
        self.diagram_tools.setVisible(on_diagram and self.role != SYSTEMS)

    def toggle_problems(self) -> None:
        """Show or hide the Problems panel at the bottom of the window."""
        show = not self.dock_problems.isVisible()
        self.dock_problems.setVisible(show)
        if show:
            self.resizeDocks([self.dock_problems], [self.theme.px(200)], Qt.Orientation.Vertical)

    def show_interfaces(self) -> None:
        """Go to the Interface table (the left panel's second tab) and put the keyboard in it."""
        self.dock_left.show()
        self.left_tabs.setCurrentWidget(self.interface_table)
        self.interface_table.view.setFocus()

    def show_units(self) -> None:
        """Go to the Unit table (the left panel's second tab) and put the keyboard in it."""
        self.dock_left.show()
        self.left_tabs.setCurrentWidget(self.unit_table)
        self.unit_table.view.setFocus()

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
        self.act_history.setEnabled(has)
        self.act_changes.setEnabled(bool(self.ctl.project.baselines))
        self.act_delete_harness.setEnabled(has and not self.ctl.read_only)

    # ---- export, import, new project ----------------------------------------------------------------
    def export_dialog_flow(self) -> None:
        """Export: one dialog to choose, run and read the result (the old `export_flow` stays for
        callers that bring their own worker). A project with no folder (the sample, a project that
        was never saved) first asks where to save it, and goes on to the dialog once it is saved;
        a cancelled chooser stops there."""
        p = self.ctl.project
        needs_folder = (
            self.ctl.outputs_folder() is None
            and bool(p.harnesses)
            and not self.ctl.read_only
            and not p.recovered
        )
        if needs_folder and not self.save_as_flow(strings.EXPORT_SAVE_AS_FOLDER):
            return
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
        self.harness_view.refresh_status()  # the files changed, the design did not
        self.lists_panel.files.invalidate()
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
        paste: list[bool] = []

        def ask_paste() -> None:
            paste.append(True)
            wizard.reject()

        wizard.pasteRequested.connect(ask_paste)
        self.run_dialog(wizard)
        wizard.deleteLater()
        if paste:  # "Paste table text instead": the older dialog, which also takes CSV text
            self.import_flow()

    def import_interfaces_flow(self) -> None:
        """File > Import > Interfaces and Ctrl+Shift+I: the same wizard as every other kind."""
        self.import_wizard_flow("interfaces")

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
        self.ctl.run(
            strings.STEP_DELETE.format(hid), ops, message=strings.HARNESS_DELETED.format(hid)
        )

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
        self.harness_view.refresh_status()
        self.lists_panel.files.invalidate()
        self.toasts.show_message(
            strings.EXPORT_DONE.format(len(built.files), built.stamp.short), None
        )

    def _compute_outputs(self) -> "tuple[OutputSet, VerifyReport] | None":
        folder = self.ctl.outputs_folder()  # the same set as the last export there (D-169)
        had = folder is not None and drawings_exported(folder)
        worker = OutputsWorker(edit.clone_with(self.ctl.project, []), drawings=had)
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
        if object_id in self.ctl.project.links:  # a connection: on the diagram, picked
            self.main_tabs.show_slot("diagram")
            self.ctl.select_link(object_id)
            self.view.focus_connection(object_id)
            return
        place = drc.locate(self.ctl.project, object_id)
        if place is None:
            if not self._show_other_object(object_id):
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
        self._need_inspector()
        if kind == "unit":
            self.view.focus_unit(target)
        else:
            self.view.focus_link(target)

    def _show_other_object(self, object_id: str) -> bool:
        """The things a finding can name that are not on the diagram or in a harness: a part (in
        Devices) and an engineering value file (its window). True when it went somewhere."""
        p = self.ctl.project
        if object_id in p.parts:
            self.go_to("devices")
            self.devices_view.select_part(object_id)
            return True
        if object_id in p.config:
            self.checks_panel.open_config(object_id)
            return True
        return False

    def open_commands(self) -> None:
        """Ctrl+K: the command palette, a non-modal overlay over the window (Ctrl+K again, Esc, a
        click elsewhere or any other move of the keyboard closes it)."""
        if self.command_palette is not None and self.command_palette.isVisible():
            self.command_palette.dismiss()
            return
        if self.command_palette is not None:
            self.command_palette.deleteLater()
        self.command_palette = CommandPalette(self, self.palette_entries())
        self.command_palette.open()

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
        """About is a section of Settings, not a message box."""
        self.set_area("settings")
        self.settings_page.show_section("about")

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
        self._open_for_role()

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
        """Start from a bundled example (the same ones as `harness-design-studio new --template`): the same
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
        self._open_for_role()
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
        self._save_project_layout()  # the project that is open now keeps its panels
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
        self._restore_project_layout()
        self._open_for_role()
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

    def save_as_flow(self, title: str | None = None) -> bool:
        folder = self.ask_folder(title or strings.SAVE_AS_FOLDER)
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
        if self.library_window is not None:
            self.library_window.close()  # keeps its own size and place, ends its helper thread
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
        self._restore_role()
        snap = bool(self.settings.value("ui/snap", True, bool))
        self.act_snap.setChecked(snap)
        self.view.set_snap(snap)
        labels = bool(self.settings.value("ui/labels", False, bool))
        self.act_labels.setChecked(labels)
        self.view.dscene.show_all_labels = labels
        ends = bool(self.settings.value("ui/connection_ends", False, bool))
        self.act_connection_ends.setChecked(ends)
        self.view.set_connection_ends(ends)
        reduce = bool(self.settings.value("ui/reduce_motion", False, bool))
        self.act_reduce_motion.setChecked(reduce)
        self.theme.set_reduce_motion(reduce)
        self.scale_actions[scale].setChecked(True)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            self.theme.apply(app, mode_name, scale / 100)
        else:
            self.theme.mode = mode_name
        self._sync_theme_actions()
        self.theme.changed.connect(self._sync_theme_actions)
        self.ctl.set_mode(mode if mode in ("guided", "expert") else "guided")
        for toggled in (
            self.act_snap,
            self.act_labels,
            self.act_connection_ends,
            self.act_reduce_motion,
            self.act_problem_notices,
        ):
            toggled.toggled.connect(lambda _on=False: self._sync_settings_page())
        self.act_role_systems.toggled.connect(lambda _on=False: self._sync_settings_page())
        self.theme.changed.connect(self._sync_settings_page)
        self._sync_settings_page()
        geo = self.settings.value("ui/geometry")
        try:
            restored = isinstance(geo, QByteArray) and self.restoreGeometry(geo)
        except TypeError:
            restored = False
        if not restored:
            self.resize(self._first_size())
        self._load_role_layout(initial=True)  # minimap, legend and docks of the role

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
        self.settings.setValue(self._wkey("ui/state"), self.saveState(STATE_VERSION))
        self._save_project_layout()

    def _layout_group(self) -> str | None:
        """The settings group of this project's layout: the project folder, hashed (a path is not
        a safe key). None for a project that has no folder yet."""
        root = self.ctl.root
        if root is None:
            return None
        return "layout/" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]

    def _save_project_layout(self) -> None:
        """The panels, the open area and the view, remembered per project (the window's own
        size is global). Nothing is written into the project."""
        group = self._layout_group()
        if group is None:
            return
        names = self.main_tabs.names()
        i = self.main_tabs.currentIndex()
        self.settings.setValue(self._wkey(f"{group}/state"), self.saveState(STATE_VERSION))
        self.settings.setValue(self._wkey(f"{group}/area"), self._area)
        self.settings.setValue(self._wkey(f"{group}/tab"), names[i] if 0 <= i < len(names) else "")
        self.settings.setValue(self._wkey(f"{group}/rail"), self.rail.collapsed)

    def _restore_project_layout(self, *, with_area: bool = True) -> None:
        """The panels, the open area and the rail of this project in the role that is open
        (`with_area` False: the panels only, for a switch of role, which leaves the page)."""
        group = self._layout_group()
        if group is None or not self.settings.contains(self._wkey(f"{group}/area")):
            return
        state = self.settings.value(self._wkey(f"{group}/state"))
        try:  # a layout from a version with other docks is ignored
            if isinstance(state, QByteArray):
                self.restoreState(state, STATE_VERSION)
        except TypeError:
            pass
        self._sync_panels_action()
        if not with_area:
            return
        self.rail.set_collapsed(bool(self.settings.value(self._wkey(f"{group}/rail"), False, bool)))
        area = str(self.settings.value(self._wkey(f"{group}/area"), areas.DEFAULT))
        tab = str(self.settings.value(self._wkey(f"{group}/tab"), "")) or None
        if area in areas.KEYS:
            self._show_area(area, tab=tab if tab in self.main_tabs.names() else None)

    def reset_layout(self) -> None:
        """View > Reset layout: the panels back where they start, the saved layout forgotten."""
        self.settings.remove(self._wkey("ui/state"))
        self._have_saved_state = False
        self.restoreState(self._default_state, STATE_VERSION)
        for dock in (self.dock_left, self.dock_right):
            dock.setFloating(False)
        if self.role == SYSTEMS:
            self._close_panels()
        self.main_tabs.show_slot("diagram")
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
        ):
            if dock.isVisibleTo(self):
                panes.append((name, dock, tabs.currentWidget()))
        if self.dock_problems.isVisibleTo(self):
            panes.append((strings.PANE_PROBLEMS, self.dock_problems, self.problems_list))
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
        self.settings.setValue(self._wkey("ui/minimap"), self.act_minimap.isChecked())

    def _toggle_legend(self) -> None:
        self.view.set_legend_wanted(self.act_legend.isChecked())
        self.settings.setValue(self._wkey("ui/legend"), self.act_legend.isChecked())

    def problem_notices_on(self) -> bool:
        """Whether the notices nobody asked for are shown (View > Show problem notices): the
        Problems button and its count, the count on the inspector tab, the status chip of the top
        bar, the chips and badges of the diagram, the pending-values link and the out-of-date
        banner. The Check button, the Checks area, the Problems panel and the banners that say why
        something cannot be done never look at it."""
        return self.act_problem_notices.isChecked()

    def _load_problem_notices(self) -> None:
        """The value of the open role: stored under its own key, on for the Electrical / AIT
        engineer and off for the Systems engineer until the person says otherwise."""
        wanted = bool(
            self.settings.value(self._wkey("ui/problem_notices"), self.role != SYSTEMS, bool)
        )
        self.act_problem_notices.setChecked(wanted)
        self._apply_problem_notices()

    def _toggle_problem_notices(self) -> None:
        self.settings.setValue(self._wkey("ui/problem_notices"), self.problem_notices_on())
        self._apply_problem_notices()

    def _apply_problem_notices(self) -> None:
        """Show or hide every unrequested notice at once: a visibility change on each, one repaint
        of the diagram's marks that changed (no rebuild of the scene)."""
        on = self.problem_notices_on()
        self.problems_btn.setVisible(on)
        self.pending_link.set_suppressed(not on)
        self.topbar.set_notices(on)
        self.inspector.set_problem_counts(on)
        self.view.set_problem_notices(on)
        self._update_alerts(self.shell_status(compute=False))
        self._sync_settings_page()

    def _toggle_snap(self) -> None:
        self.view.set_snap(self.act_snap.isChecked())
        self.settings.setValue("ui/snap", self.act_snap.isChecked())

    def _toggle_labels(self) -> None:
        self.view.dscene.show_all_labels = self.act_labels.isChecked()
        self.settings.setValue("ui/labels", self.act_labels.isChecked())
        self.view.viewport().update()

    def _toggle_connection_ends(self) -> None:
        self.view.set_connection_ends(self.act_connection_ends.isChecked())
        self.settings.setValue("ui/connection_ends", self.act_connection_ends.isChecked())

    def _toggle_reduce_motion(self) -> None:
        self.theme.set_reduce_motion(self.act_reduce_motion.isChecked())
        self.settings.setValue("ui/reduce_motion", self.act_reduce_motion.isChecked())

    @staticmethod
    def _set_checked(act: QAction, on: bool) -> None:
        """Make a checkable action `on` through its own handler (a menu click would do the same)."""
        if act.isChecked() != on:
            act.trigger()

    def _sync_settings_page(self) -> None:
        self.settings_page.sync(
            theme_mode=self.theme.mode,
            scale=round(self.theme.scale * 100),
            mode=self.ctl.mode,
            role=self.role,
            reduce_motion=self.act_reduce_motion.isChecked(),
            snap=self.act_snap.isChecked(),
            labels=self.act_labels.isChecked(),
            connection_ends=self.act_connection_ends.isChecked(),
            problem_notices=self.act_problem_notices.isChecked(),
        )
        self.settings_page.show_library_folder(self.library_folder())

    def shortcut_rows(self) -> list[tuple[str, str]]:
        """Every action of the window that has a key: (name, key), by name."""
        rows = {
            (
                act.text().replace("&", ""),
                act.shortcut().toString(QKeySequence.SequenceFormat.NativeText),
            )
            for act in self.actions()
            if act.text() and not act.shortcut().isEmpty()
        }
        return sorted(rows, key=lambda r: (r[0].lower(), r[1]))

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
        """Set the interface size. Qt makes every widget read the new style sheet (about a second
        with the window full of tables), so the pointer shows that the program is busy."""
        app = QApplication.instance()
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if isinstance(app, QApplication):
                self.theme.apply(app, None, pct / 100)
            self.settings.setValue("ui/scale", pct)
            self.auto_layout()
        finally:
            QGuiApplication.restoreOverrideCursor()

    def _layout_class_now(self) -> tuple[bool, bool]:
        eff_w = self.width() / self.theme.scale
        return (eff_w >= WIDE_PX, eff_w >= MEDIUM_PX)

    def auto_layout(self) -> None:
        """At high UI scale or small windows, hide secondary panels so the diagram keeps room:
        narrow windows lose the side panels (the diagram never shares its height with a bottom
        panel any more). Called on first show, when the window crosses one of those widths, and
        when the scale changes."""
        scale = self.theme.scale
        wide, medium = self._layout_class = self._layout_class_now()
        if self.role == SYSTEMS:  # (it closes what no longer fits, never opens a panel)
            wide = wide and self.dock_right.isVisibleTo(self)
            medium = medium and self.dock_left.isVisibleTo(self)
        was = (self.dock_left.isVisibleTo(self), self.dock_right.isVisibleTo(self))
        self.dock_right.setVisible(wide)
        self.dock_left.setVisible(medium)
        now = (self.dock_left.isVisibleTo(self), self.dock_right.isVisibleTo(self))
        if was != now and (was[0] and not now[0] or was[1] and not now[1]):
            self.toasts.show_message(strings.PANELS_HIDDEN, None)  # never hide panels silently
        self.interface_table.scale_factor = scale
        self.unit_table.scale_factor = scale
        self.dock_left.setMinimumWidth(self.theme.px(280))
        self.dock_right.setMinimumWidth(self.theme.px(260))
        self.resizeDocks([self.dock_left], [self.theme.px(280)], Qt.Orientation.Horizontal)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._shown:
            self._shown = True
            if self._role_to_ask:  # the first start: the question, then the tour
                QTimer.singleShot(0, self._first_start_flow)
            if self._have_saved_state:  # the person's own layout stands
                self._layout_class = self._layout_class_now()
            else:
                self.auto_layout()

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        self.toasts.reposition()
        self.rail.set_compact(self.height() < self.theme.px(640))
        self._fit_status()
        if self.command_palette is not None and self.command_palette.isVisible():
            self.command_palette.reposition()
        if self._shown and self._layout_class_now() != self._layout_class:
            if self._have_saved_state:  # (a saved layout is kept; only a crossing is acted on)
                self._have_saved_state = False
            self.auto_layout()
        if self.tour.active:
            self.tour.show_step(self.tour.index)

    def finish_tour(self) -> None:
        self.settings.setValue("tour/done", True)
        self.tour.stop()
