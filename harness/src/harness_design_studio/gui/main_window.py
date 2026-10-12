"""Main window: palette (left), diagram (centre), properties (right), problems and tables (bottom)."""

import contextlib
from collections.abc import Callable
from functools import partial
from pathlib import Path

from PySide6.QtCore import QEvent, QEventLoop, QSettings, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QDesktopServices, QKeySequence
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
from harness_design_studio.gui.canvas import DiagramView
from harness_design_studio.gui.controller import LIST_DELAY_MS, Delta, EditorController, NeedSaveAs
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
from harness_design_studio.gui.legend import LegendBar
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
from harness_design_studio.gui.theme import ThemeManager
from harness_design_studio.gui.tokens import CATEGORIES
from harness_design_studio.gui.tour import Tour
from harness_design_studio.resources import guide_path

SCALES = (100, 125, 150, 200)


def _exec(dialog: QDialog) -> int:
    return int(dialog.exec())


def _no_file() -> str | None:
    return None


class PlanWorker(QThread):
    """Computes a generation plan off the UI thread. It only reads the project; the UI is blocked
    by a modal progress dialog meanwhile, so nothing can change under it."""

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


class OutputsWorker(QThread):
    """Builds and independently verifies the output set off the UI thread (read-only)."""

    progressed = Signal(float, str)

    def __init__(self, project: Project) -> None:
        super().__init__()
        self._project = project
        self._cancelled = False
        self.result: OutputSet | None = None
        self.report: VerifyReport | None = None

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            self.result = build_outputs(
                self._project,
                cancel=lambda: self._cancelled,
                progress=lambda f, t: self.progressed.emit(f, t),
            )
            self.progressed.emit(0.95, "Independent check")
            self.report = verify_outputs(self._project, self.result.files)
        except OutputsCancelled:
            self.result = None


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
        self.hide()

    def show_message(
        self, text: str, undo: Callable[[], None] | None = None, ms: int = 5000
    ) -> None:
        self.messages.append(text)
        self._frames = [f for f in self._frames if self._alive(f[0])]
        if any(t == text and u == (undo is not None) for _f, t, u in self._frames):
            return  # the same message is already showing
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
        QTimer.singleShot(ms, lambda: self._expire(frame))
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

        self._build_center()
        self._build_docks()
        self._build_actions()
        self._build_menus_and_toolbar()
        self._build_status()
        self.toasts = ToastHost(self.view)
        self.tour = Tour(self, theme, self._tour_targets())
        self.tour.on_stop = lambda: self.settings.setValue("tour/done", True)

        self.ctl.message.connect(self._on_message)
        self.ctl.drcChanged.connect(self._update_tab_badges)
        self.ctl.stateChanged.connect(self._on_state)
        self.ctl.changed.connect(self._on_changed)
        self.ctl.selectionChanged.connect(self._on_selection)
        self.ctl.connectChanged.connect(self._on_connect)
        self.ctl.modeChanged.connect(self._on_mode)
        self.palette_panel.addUnit.connect(self._add_unit)
        self.palette_panel.connectType.connect(self._toggle_connect)
        self.palette_panel.importRequested.connect(self.import_flow)
        self.problems.showRequested.connect(self.show_object)
        self.problems.waiveRequested.connect(self.waive_flow)
        self.todo.activated.connect(self._todo_activated)
        self.table.newInterfaceRequested.connect(self.new_interface_flow)

        self._hash_timer = QTimer(self)
        self._hash_timer.setSingleShot(True)
        self._hash_timer.setInterval(250)
        self._hash_timer.timeout.connect(self._update_hash)
        self._badge_timer = QTimer(self)
        self._badge_timer.setSingleShot(True)
        self._badge_timer.setInterval(LIST_DELAY_MS)
        self._badge_timer.timeout.connect(self._apply_tab_badges)

        self._restore_settings()
        self._on_state()
        self._on_connect()
        self._on_selection()
        if first_run is None:
            first_run = not self.settings.value("tour/done", False, bool)
        self.ctl.open_sample()
        if first_run:
            QTimer.singleShot(200, self.tour.start)

    # ---- construction ------------------------------------------------------------------------
    def _build_center(self) -> None:
        centre = QWidget()
        lay = QVBoxLayout(centre)
        lay.setContentsMargins(0, 0, 0, 0)
        self.banner = Banner()
        lay.addWidget(self.banner)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 4, 8, 4)
        self.tool_select = QToolButton()
        self.tool_select.setText(strings.TOOL_SELECT)
        self.tool_select.setObjectName("tool-select")
        self.tool_select.setCheckable(True)
        self.tool_select.setChecked(True)
        self.tool_select.setToolTip(strings.TOOL_SELECT_TIP)
        self.tool_connect = QToolButton()
        self.tool_connect.setText(strings.TOOL_CONNECT)
        self.tool_connect.setObjectName("tool-connect")
        self.tool_connect.setCheckable(True)
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
        self.zoom_in_btn.setText("+")
        self.zoom_in_btn.setAccessibleName(strings.ZOOM_IN)
        self.zoom_out_btn = QToolButton()
        self.zoom_out_btn.setText("−")
        self.zoom_out_btn.setAccessibleName(strings.ZOOM_OUT)
        self.fit_btn = QToolButton()
        self.fit_btn.setText(strings.FIT)
        bar.addWidget(self.tool_select)
        bar.addWidget(self.tool_connect)
        bar.addWidget(self.hint, 1)
        for w in (
            self.redundant_btn,
            self.delete_btn,
            self.zoom_out_btn,
            self.zoom_in_btn,
            self.fit_btn,
        ):
            bar.addWidget(w)
        lay.addLayout(bar)
        self.view = DiagramView(self.ctl, self.theme)
        self.view.setObjectName("diagram")
        self.zoom_in_btn.clicked.connect(lambda: self.view.zoom_by(1.2))
        self.zoom_out_btn.clicked.connect(lambda: self.view.zoom_by(1 / 1.2))
        self.fit_btn.clicked.connect(self.view.fit)
        lay.addWidget(self.view, 1)
        self.legend = LegendBar(self.theme)
        lay.addWidget(self.legend)
        self.setCentralWidget(centre)
        self.ctl.changed.connect(lambda _d=None: self.legend.set_project(self.ctl.project))
        self.legend.set_project(self.ctl.project)

    def _build_docks(self) -> None:
        self.palette_panel = PalettePanel(self.ctl, self.theme)
        self.dock_left = self._dock(
            strings.PALETTE,
            self.palette_panel,
            Qt.DockWidgetArea.LeftDockWidgetArea,
            "dock-palette",
        )
        self.props = PropertiesPanel(self.ctl, self.theme)
        self.dock_right = self._dock(
            strings.PROPERTIES, self.props, Qt.DockWidgetArea.RightDockWidgetArea, "dock-properties"
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
        self.tabs.addTab(self.problems, strings.PROBLEMS)
        self.tabs.addTab(self.todo, strings.TODO)
        self.tabs.addTab(self.table, strings.INTERFACE_TABLE)
        self.tabs.addTab(self.harness_panel, strings.HARNESS_PLANS)
        self.tabs.addTab(self.outline, strings.OUTLINE)
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
        return dock

    def _build_status(self) -> None:
        sb = self.statusBar()
        self.status_saved = QLabel(strings.ALL_SAVED)
        self.status_sel = QLabel("")
        self.status_counts = QLabel("")
        for w in (self.status_saved, self.status_sel, self.status_counts):
            sb.addWidget(w)
            w.setContentsMargins(8, 0, 8, 0)

    # ---- actions -------------------------------------------------------------------------------
    def _act(
        self,
        text: str,
        slot: Callable[[], None],
        shortcut: str | QKeySequence.StandardKey | None = None,
        *,
        checkable: bool = False,
        name: str = "",
    ) -> QAction:
        a = QAction(text, self)
        if name:
            a.setObjectName(name)
        if shortcut is not None:
            a.setShortcut(QKeySequence(shortcut))
            a.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        a.setCheckable(checkable)
        a.triggered.connect(lambda _c=False: slot())
        self.addAction(a)
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
        self.act_redo2 = a(strings.REDO, self.ctl.redo, "Ctrl+Shift+Z", name="act-redo2")
        self.act_delete = a(strings.DELETE, self.delete_flow, "Delete", name="act-delete")
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
        self.act_fit = a(strings.FIT, self.view.fit, "Ctrl+0", name="act-fit")
        self.act_arrange = a(strings.A_ARRANGE, self.arrange_flow, name="act-arrange")
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

    def arrange_flow(self) -> None:
        ops = edit.ops_arrange(self.ctl.project)
        if not ops:
            self.toasts.show_message(strings.ARRANGE_NOTHING, None)
            return
        self.ctl.run("Arrange diagram", ops, message=strings.ARRANGE_DONE)

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
        for act in (self.act_save, self.act_save_as, self.act_import):
            f.addAction(act)
        f.addSeparator()
        f.addAction(self.act_quit)
        e = mb.addMenu(strings.M_EDIT)
        for act in (
            self.act_undo,
            self.act_redo,
            self.act_delete,
            self.act_redundant,
            self.act_add_zone,
            self.act_wire_colours,
        ):
            e.addAction(act)
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
        v.addAction(self.act_dark)
        v.addAction(self.act_minimap)
        v.addAction(self.act_labels)
        scale_menu = v.addMenu(strings.A_SCALE)
        for act in self.scale_actions.values():
            scale_menu.addAction(act)
        v.addSeparator()
        for act in (self.act_zoom_in, self.act_zoom_out, self.act_fit, self.act_arrange):
            v.addAction(act)
        v.addSeparator()
        for dock in (self.dock_left, self.dock_right, self.dock_bottom):
            v.addAction(dock.toggleViewAction())
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
        self.mode_guided.setChecked(True)
        self.mode_guided.setToolTip(strings.GUIDED_TIP)
        self.mode_expert = QToolButton()
        self.mode_expert.setObjectName("mode-expert")
        self.mode_expert.setText(strings.EXPERT)
        self.mode_expert.setCheckable(True)
        self.mode_expert.setToolTip(strings.EXPERT_TIP)
        self.mode_guided.clicked.connect(lambda: self._pick_mode("guided"))
        self.mode_expert.clicked.connect(lambda: self._pick_mode("expert"))
        tb.addWidget(self.mode_guided)
        tb.addWidget(self.mode_expert)
        tb.addSeparator()
        self.search_btn = QPushButton(strings.SEARCH_BUTTON)
        self.search_btn.setObjectName("search-button")
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
        spacer = QWidget()
        spacer.setSizePolicy(
            spacer.sizePolicy().horizontalPolicy().Expanding,
            spacer.sizePolicy().verticalPolicy().Preferred,
        )
        tb.addWidget(spacer)
        self.generate_btn = QPushButton(strings.GENERATE)
        self.generate_btn.setObjectName("generate")
        self.generate_btn.setToolTip(strings.GENERATE_TIP)
        self.generate_btn.clicked.connect(self.generate_flow)
        tb.addWidget(self.generate_btn)

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
        self.menu_connect.clear()
        for tid, t in sorted(self.ctl.project.interface_types.items()):
            act = self._act(t.name, partial(self._toggle_connect, tid), name=f"menu-connect-{tid}")
            act.setIcon(category_icon(t.category, self.theme))
            self.menu_connect.addAction(act)

    def _tour_targets(self) -> dict[str, QWidget]:
        return {
            "palette": self.palette_panel,
            "canvas": self.view,
            "types": self.palette_panel,
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

        self.toasts.show_message(text, undo_that_change if undoable else None)

    def _on_state(self) -> None:
        c = self.ctl
        ro = c.read_only
        self.setWindowTitle(f"{c.title} — {strings.APP_TITLE}")
        self.act_undo.setEnabled(c.history.can_undo and not ro)
        self.act_redo.setEnabled(c.history.can_redo and not ro)
        self.act_redo2.setEnabled(c.history.can_redo and not ro)
        self.act_save.setEnabled(not ro)
        self.act_import.setEnabled(not ro)
        self.act_wire_colours.setEnabled(not ro)
        self.status_saved.setText(strings.UNSAVED if c.dirty else strings.ALL_SAVED)
        self._update_banner()
        self._update_selection_actions()
        self._hash_timer.start()
        self._update_tab_badges()

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
        p = self.ctl.project
        self.status_counts.setText(
            strings.STATUS_COUNTS.format(
                strings.units_text(len(p.units)),
                strings.interfaces_text(len(p.interfaces)),
                model_hash(p)[:8],
            )
        )

    def _on_changed(self, delta: Delta) -> None:
        if delta.full and self.filter_combo.currentData():
            self._refresh_filter_values()  # a new project: its connectors and harnesses
            self._filter_changed(0)
        self._rebuild_connect_menu() if set(self.ctl.project.interface_types) != {
            a.objectName().removeprefix("menu-connect-") for a in self.menu_connect.actions()
        } else None
        self._update_tab_badges()
        self._update_selection_actions()
        p = self.ctl.project  # the counts follow every edit at once; only the hash waits
        self.status_counts.setText(
            strings.STATUS_COUNTS.format(
                strings.units_text(len(p.units)), strings.interfaces_text(len(p.interfaces)), "…"
            )
        )

    def _on_selection(self) -> None:
        s = self.ctl.selection
        self.status_sel.setText(strings.SELECTED.format(s.id) if s else strings.NOTHING_SEL)
        if s is not None and s.kind == "unit":
            self.view.reveal(s.id)
        if s is not None and not self.dock_right.isVisibleTo(self) and not self._told_properties:
            self._told_properties = True
            self.toasts.show_message(strings.PROPERTIES_HIDDEN, None)
        self._update_selection_actions()

    def _update_selection_actions(self) -> None:
        s, c = self.ctl.selection, self.ctl
        ro = c.read_only
        can_red = bool(
            s
            and s.kind == "unit"
            and s.id in c.project.units
            and c.project.units[s.id].side != "redundant"
            and f"{s.id}-R" not in c.project.units
        )
        self.redundant_btn.setEnabled(can_red and not ro)
        self.act_redundant.setEnabled(can_red and not ro)
        self.delete_btn.setEnabled(bool(s) and not ro)
        self.act_delete.setEnabled(bool(s) and not ro)
        # a disabled control must say why
        if ro:
            why_red = why_del = strings.WHY_READ_ONLY
        else:
            why_del = "" if s else strings.WHY_NO_SELECTION
            if not (s and s.kind == "unit" and s.id in c.project.units):
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

    def _on_connect(self) -> None:
        c = self.ctl
        self.tool_select.setChecked(c.tool == "select")
        self.tool_connect.setChecked(c.tool == "connect")
        hint = c.connect_hint()
        warn = hint.startswith("No other unit")
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
        if self.ctl.tool == "connect" and self.ctl.connect_type == type_id:
            self.ctl.end_connect()
        else:
            self.ctl.begin_connect(type_id)

    def _redundant_selected(self) -> None:
        s = self.ctl.selection
        if s and s.kind == "unit":
            self.ctl.redundant_copy(s.id)

    def delete_flow(self) -> None:
        s = self.ctl.selection
        if s is None or self.ctl.read_only:
            return
        if s.kind == "unit":
            impact = self.ctl.delete_impact(s.id)
            if impact.blocked_by_harnesses:
                self.ctl.delete_selected()  # explains why it cannot be done
                return
            ifs = ", ".join(f"<b>{i}</b>" for i in impact.interfaces)
            body = strings.DELETE_BODY.format(
                n=len(impact.interfaces),
                s="" if len(impact.interfaces) == 1 else "s",
                ifs=f": {ifs}" if ifs else "",
                c=len(impact.connectors),
            )
            dlg = ConfirmDialog(self, strings.DELETE_TITLE.format(s.id), body, strings.DELETE)
            if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
                return
        self.ctl.delete_selected()

    def generate_flow(self) -> None:
        if self.ctl.read_only:
            return
        plan = self.compute_plan()
        if plan is None:
            self.toasts.show_message(strings.GEN_CANCELLED, None)
            return
        if plan.empty:
            self.ctl.apply_generation(plan)
            return
        accepted = self.run_dialog(GeneratePreviewDialog(self, plan)) == QDialog.DialogCode.Accepted
        if accepted and self.ctl.apply_generation(plan):
            self.tabs.setCurrentWidget(self.harness_panel)
            self._give_room_to(self.dock_bottom, 420)

    def _give_room_to(self, dock: QDockWidget, height: int) -> None:
        """Make a bottom dock at least `height` tall (the plans tab is unusable as a sliver)."""
        if dock.height() < height:
            self.resizeDocks([dock], [height], Qt.Orientation.Vertical)

    def _compute_plan(self) -> GenerationPlan | None:
        """Plan in a worker thread behind a cancellable progress dialog; None if cancelled."""
        worker = PlanWorker(self.ctl.project)
        self._run_worker(worker, strings.GEN_RUNNING, "generate-progress")
        return worker.plan

    def _run_worker(self, worker: "PlanWorker | OutputsWorker", label: str, name: str) -> None:
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
            dlg = ChangeDialog(
                self,
                strings.RELEASE_TITLE.format(hid),
                by=self._user_name(),
                blockers=[b.message for b in blockers],
                ask_checker=True,
                ok_text=strings.RELEASE_CONFIRM,
                placeholders=project.placeholder_configs(),
                unapproved_parts=unapproved_parts(project, project.harnesses[hid]),
            )
        else:
            dlg = ChangeDialog(
                self,
                strings.NEW_REV_TITLE.format(hid),
                by=self._user_name(),
                blockers=[],
                ok_text=strings.NEW_REV_CONFIRM,
            )
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return
        by, checker, comment = dlg.values()
        self.settings.setValue("ui/user", by)
        if action == "review":
            plan = plan_submit_review(project, hid, by=by, when=today)
            msg = f"{hid} submitted for review."
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
            msg = f"New revision of {hid} started; it can be edited again."
        if self.ctl.apply_change(plan, msg):
            self.harness_panel.refresh()

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
        if self.ctl.run(f"Delete {hid}", ops, message=strings.HARNESS_DELETED.format(hid)):
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
        folder = self.ctl.outputs_folder()
        if folder is None:
            self.toasts.show_message(strings.EXPORT_SAVE_FIRST, None)
            return
        if not self.ctl.project.harnesses:
            self.toasts.show_message(strings.EXPORT_NO_HARNESSES, None)
            return
        result = self.compute_outputs()
        if result is None:
            self.toasts.show_message(strings.EXPORT_CANCELLED, None)
            return
        built, report = result
        if not report.ok:
            body = "<br>".join(i.message for i in report.errors[:6])
            self.run_dialog(ConfirmDialog(self, strings.EXPORT, body, strings.OK, danger=False))
            self.toasts.show_message(strings.EXPORT_FAILED.format(len(report.errors)), None)
            return
        try:
            write_outputs(self.ctl.project, folder, built)
        except (HarnessError, OSError) as exc:
            self._error(self._explain(exc, folder))
            return
        self.harness_panel.refresh()
        self.toasts.show_message(
            strings.EXPORT_DONE.format(len(built.files), built.stamp.short), None
        )

    def _compute_outputs(self) -> "tuple[OutputSet, VerifyReport] | None":
        worker = OutputsWorker(self.ctl.project)
        self._run_worker(worker, strings.EXPORT_RUNNING, "export-progress")
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
        if ops and self.ctl.run("wire colours", ops):
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
            self.tabs.setCurrentWidget(self.harness_panel)
            self.harness_panel.select_harness(target)
            return
        self.ctl.select(kind, target)
        if kind == "unit":
            self.view.focus_unit(target)

    def _todo_activated(self, kind: str, target: str) -> None:
        if kind == "tab":
            self.tabs.setCurrentIndex(0)
        else:
            self.show_object(target)

    def open_commands(self) -> None:
        self.run_dialog(CommandPalette(self, self.palette_entries()))

    def palette_entries(self) -> list[PaletteEntry]:
        e: list[PaletteEntry] = []
        for act in self.actions():
            if act.text() and act.isEnabled() and act.objectName().startswith(("act-", "menu-")):
                hint = act.shortcut().toString()
                e.append(PaletteEntry(act.text(), act.trigger, hint))
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
        return choice == 1

    def new_project_flow(self) -> None:
        if not self._confirm_discard():
            return
        folder = self.ask_folder(strings.NEW_FOLDER)
        if not folder:
            return
        name = self.ask_text(strings.NEW_NAME_TITLE, strings.NEW_NAME, Path(folder).name)
        if not name:
            return
        try:
            self.ctl.new_project(Path(folder), name)
        except (HarnessError, OSError) as exc:
            self._error(self._explain(exc, folder))
            return
        self._last_issues = []
        self.settings.setValue("project/last", folder)

    def new_from_example_flow(self) -> None:
        """Start from a bundled example (the same ones as `harness new --template`)."""
        from harness_design_studio.core import templates

        if not self._confirm_discard():
            return
        examples = templates.TEMPLATES
        text = strings.EXAMPLE_TEXT + "\n\n" + "\n".join(f"{t.name}: {t.summary}" for t in examples)
        choice = self.ask_choice(
            strings.EXAMPLE_TITLE, text, [*(t.name for t in examples), strings.CANCEL]
        )
        if choice >= len(examples):
            return
        folder = self.ask_folder(strings.NEW_FOLDER)
        if not folder:
            return
        name = self.ask_text(strings.NEW_NAME_TITLE, strings.NEW_NAME, Path(folder).name)
        if not name:
            return
        try:
            templates.create_project(Path(folder), examples[choice].name, name)
        except (HarnessError, OSError) as exc:
            self._error(self._explain(exc, folder))
            return
        if self.open_project(Path(folder)):
            self._last_issues = []
            self.settings.setValue("project/last", folder)

    def open_flow(self) -> None:
        if not self._confirm_discard():
            return
        folder = self.ask_folder(strings.OPEN_FOLDER)
        if folder:
            self.open_project(Path(folder))

    def open_project(self, folder: Path) -> bool:
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
        if self.ctl.journal_available():
            choice = self.ask_choice(
                strings.RESTORE_TITLE,
                strings.RESTORE_BODY,
                [strings.RESTORE, strings.DISCARD_CHANGES],
            )
            if choice == 0:
                self.ctl.restore_journal()
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
        except (HarnessError, OSError) as exc:
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
        except (HarnessError, OSError) as exc:
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
        where = f" in {folder}" if folder else ""
        reason = getattr(exc, "strerror", None) or "the folder cannot be used"
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
            result = self.ctl.reload()
            if result is not None:
                self._last_issues = result.issues
        else:
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
        dark = self.settings.value("ui/theme", "light") == "dark"
        scale = int(str(self.settings.value("ui/scale", 100)))
        mode = str(self.settings.value("ui/mode", "guided"))
        self.act_dark.setChecked(dark)
        wanted = bool(self.settings.value("ui/minimap", True, bool))
        self.act_minimap.setChecked(wanted)
        self.view.set_minimap_wanted(wanted)
        if scale in self.scale_actions:
            self.scale_actions[scale].setChecked(True)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            self.theme.apply(app, "dark" if dark else "light", scale / 100)
        self.ctl.set_mode(mode if mode in ("guided", "expert") else "guided")
        geo = self.settings.value("ui/geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1360, 860)

    def _save_settings(self) -> None:
        self.settings.setValue("ui/geometry", self.saveGeometry())

    def _toggle_minimap(self) -> None:
        self.view.set_minimap_wanted(self.act_minimap.isChecked())
        self.settings.setValue("ui/minimap", self.act_minimap.isChecked())

    def _toggle_labels(self) -> None:
        self.view.dscene.show_all_labels = self.act_labels.isChecked()
        self.view.viewport().update()

    def _toggle_dark(self) -> None:
        app = QApplication.instance()
        name = "dark" if self.act_dark.isChecked() else "light"
        if isinstance(app, QApplication):
            self.theme.apply(app, name)
        self.settings.setValue("ui/theme", name)
        self.view.viewport().update()

    def set_scale(self, pct: int) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            self.theme.apply(app, None, pct / 100)
        self.settings.setValue("ui/scale", pct)
        self.auto_layout()

    def auto_layout(self) -> None:
        """At high UI scale or small windows, hide secondary panels so the diagram keeps room."""
        scale = self.theme.scale
        eff_w = self.width() / scale
        was = (self.dock_left.isVisibleTo(self), self.dock_right.isVisibleTo(self))
        self.dock_right.setVisible(eff_w >= 1150)
        self.dock_left.setVisible(eff_w >= 800)
        now = (self.dock_left.isVisibleTo(self), self.dock_right.isVisibleTo(self))
        if was != now and (was[0] and not now[0] or was[1] and not now[1]):
            self.toasts.show_message(strings.PANELS_HIDDEN, None)  # never hide panels silently
        self.table.scale_factor = scale
        self.dock_left.setMinimumWidth(self.theme.px(240))
        self.dock_right.setMinimumWidth(self.theme.px(260))
        self.resizeDocks([self.dock_left], [self.theme.px(250)], Qt.Orientation.Horizontal)
        # the bottom panel never takes more than 45% of the window, so the diagram keeps room
        # at large UI scales (its content scrolls; the View menu can still hide it)
        self.dock_bottom.setMaximumHeight(max(self.theme.px(160), int(self.height() * 0.40)))
        self.resizeDocks(
            [self.dock_bottom],
            [max(self.theme.px(110), int(self.height() * 0.22))],
            Qt.Orientation.Vertical,
        )

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        self.toasts.reposition()
        if self.tour.active:
            self.tour.show_step(self.tour.index)

    def finish_tour(self) -> None:
        self.settings.setValue("tour/done", True)
        self.tour.stop()
