"""The Releases tab: the timeline of reviews, releases and new revisions of every harness, the
differences between two revisions (or a revision and the working design), and the per-harness
change-control actions.

    panel = ReleasesPanel(ctl, theme, settings=settings)
    panel.changeRequested.connect(window.change_flow)       # ("review" | "release" | "revise", id)

The panel only reads the project (`core.vcs.timeline`: `timeline`, `compare_revisions`,
`diff_groups`) and never edits it: the buttons emit signals and the window runs the dialogs, so the
steps stay undoable `History` transactions. "Mark on diagram" goes through `ctl.set_marks`, as in
the existing change dialog. Which state a harness is in is always a state chip (draft, in review,
released, revised), never colour alone.
"""

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListView,
    QPushButton,
    QSplitter,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.model import Project
from harness_design_studio.core.vcs.diff import Diff
from harness_design_studio.core.vcs.report import baselines_of
from harness_design_studio.core.vcs.timeline import (
    DiffGroup,
    TimelineRow,
    compare_revisions,
    diff_groups,
    timeline,
)
from harness_design_studio.gui import icons, strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.states import STATES, StateChip
from harness_design_studio.gui.tables import Column, DictTableModel, Row, TableView
from harness_design_studio.gui.theme import ThemeManager


def _m(row: Row) -> Mapping[Any, Any]:
    return row if isinstance(row, Mapping) else {}


REFRESH_MS = 150  # a visible panel reads the project this long after the last change
ALL = ""  # the combo box entry "All harnesses"
WORKING = ""  # the "with" entry "Working design"
_EVENT_STATE = {"review": "in-review", "release": "released", "new_revision": "revised"}


def harness_state(project: Project, harness_id: str) -> str:
    """The key of `gui.states.STATES` for a harness: draft, in-review, released, or revised (a
    draft that follows a released revision)."""
    h = project.harnesses.get(harness_id)
    if h is None:
        return "draft"
    if h.status == "released":
        return "released"
    if h.status == "in_review":
        return "in-review"
    if any(b.harness_id == harness_id for b in project.baselines.values()):
        return "revised"
    return "draft"


def timeline_rows(project: Project, harness_id: str | None = None) -> list[dict[str, Any]]:
    """The timeline as table rows (dicts): the log's words, a state for the event and for the
    baseline, and the whole comment for the tooltip."""
    rows: list[dict[str, Any]] = []
    for r in timeline(project, harness_id):
        rows.append(_timeline_dict(r))
    return rows


def _timeline_dict(r: TimelineRow) -> dict[str, Any]:
    return {
        "id": r.id,
        "harness": r.harness_id,
        "revision": r.revision,
        "kind": r.kind,
        "event": r.event,
        "by": r.by,
        "when": r.when,
        "comment": r.comment,
        "has_baseline": r.has_baseline,
        "baseline": strings.REL_BASELINE_CHIP.format(r.revision) if r.has_baseline else "",
    }


def diff_table_rows(groups: list[DiffGroup], kind: str | None = None) -> list[dict[str, Any]]:
    """The changes of the groups (all, or the one of `kind`) as table rows. A whole object that
    was added or removed has no field, and the empty side says so in words instead of showing
    nothing or `None`."""
    changes = {
        "added": strings.REL_ADDED,
        "removed": strings.REL_REMOVED,
        "changed": strings.REL_CHANGED,
    }
    rows: list[dict[str, Any]] = []
    for g in groups:
        if kind is not None and g.kind != kind:
            continue
        for r in g.rows:
            whole = r.field == ""
            rows.append(
                {
                    "change": changes[r.change],
                    "change_key": r.change,
                    "kind": r.kind_name,
                    "id": r.id,
                    "field": strings.REL_WHOLE_OBJECT if whole else r.label,
                    "before": strings.REL_DID_NOT_EXIST
                    if whole and r.change == "added"
                    else r.before,  # fmt: skip
                    "after": strings.REL_NO_LONGER
                    if whole and r.change == "removed"
                    else r.after,  # fmt: skip
                }
            )
    return rows


def group_text(g: DiffGroup) -> str:
    """ "Wire: 2 added, 1 changed" (kinds with no change of a sort leave that sort out)."""
    counts = g.counts
    parts = [f"{counts[k]} {k}" for k in ("added", "removed", "changed") if counts[k]]
    return strings.REL_GROUP_ITEM.format(g.name, ", ".join(parts) or strings.REL_COUNTS_ZERO)


class ReleasesPanel(QWidget):
    """Timeline, differences and change-control actions for the harnesses of the open project."""

    changeRequested = Signal(str, str)  # action ("review" | "release" | "revise"), harness ID
    submitReviewRequested = Signal(str)
    releaseRequested = Signal(str)
    reviseRequested = Signal(str)
    harnessChanged = Signal(str)  # the harness the actions and the comparison are about ("" none)
    diffChanged = Signal(int)  # number of changed objects now shown

    def __init__(
        self,
        ctl: EditorController,
        theme: ThemeManager,
        *,
        settings: QSettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.ctl, self.theme = ctl, theme
        self.setObjectName("releases-panel")
        self.setAccessibleName(strings.REL_ACCESSIBLE)
        self._dirty = True
        self._diff: Diff | None = None
        self._groups: list[DiffGroup] = []
        self._cache: dict[tuple[Any, ...], Diff] = {}
        self._building = False
        lay = QVBoxLayout(self)

        # ---- header: harness, its state, the three actions -------------------------------
        head = QHBoxLayout()
        label = QLabel(strings.REL_HARNESS)
        self.harness = QComboBox()
        self.harness.setObjectName("releases-harness")
        self.harness.setAccessibleName(strings.REL_HARNESS)
        self.harness.setToolTip(strings.REL_HARNESS)
        label.setBuddy(self.harness)
        self.state = StateChip(theme, "draft")
        self.state.setObjectName("releases-state")
        head.addWidget(label)
        head.addWidget(self.harness)
        head.addWidget(self.state)
        head.addStretch(1)
        self.action_buttons: dict[str, QPushButton] = {}
        for action, icon, text, tip in (
            ("review", "review", strings.REL_SUBMIT, strings.REL_SUBMIT_TIP),
            ("release", "release", strings.REL_RELEASE, strings.REL_RELEASE_TIP),
            ("revise", "revise", strings.REL_REVISE, strings.REL_REVISE_TIP),
        ):
            b = QPushButton()
            b.setObjectName(f"releases-{action}")
            icons.icon_button(b, icon, theme, tip, text=text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, a=action: self._request(a))
            head.addWidget(b)
            self.action_buttons[action] = b
        lay.addLayout(head)
        self.action_note = QLabel()
        self.action_note.setObjectName("releases-note")
        self.action_note.setProperty("muted", True)
        self.action_note.setWordWrap(True)
        lay.addWidget(self.action_note)

        split = QSplitter(Qt.Orientation.Vertical)
        split.setObjectName("releases-split")
        split.setChildrenCollapsible(False)
        lay.addWidget(split, 1)

        # ---- the timeline ---------------------------------------------------------------------
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        title = QLabel(strings.REL_TIMELINE)
        title.setProperty("heading", True)
        tl.addWidget(title)
        cols = [
            Column("id", strings.REL_COLUMNS["id"], mono=True),
            Column("harness", strings.REL_COLUMNS["harness"], mono=True),
            Column("revision", strings.REL_COLUMNS["revision"], mono=True),
            Column(
                "event",
                strings.REL_COLUMNS["event"],
                state=lambda r: _EVENT_STATE.get(str(_m(r)["kind"])),
            ),  # fmt: skip
            Column("by", strings.REL_COLUMNS["by"]),
            Column("when", strings.REL_COLUMNS["when"], mono=True),
            Column("comment", strings.REL_COLUMNS["comment"], tooltip="comment", width=360),
            Column(
                "baseline",
                strings.REL_COLUMNS["baseline"],
                state=lambda r: "released" if _m(r)["has_baseline"] else None,
                tooltip=lambda r: (
                    strings.REL_BASELINE_TIP.format(_m(r)["revision"])
                    if _m(r)["has_baseline"]
                    else strings.REL_NO_BASELINE_TIP
                ),
            ),  # fmt: skip
        ]
        self.timeline_model = DictTableModel(cols, [], theme)
        self.timeline = TableView(
            self.timeline_model,
            theme,
            name=strings.REL_TIMELINE_NAME,
            settings=settings,
            key="releases-timeline",
        )
        self.timeline.setObjectName("releases-timeline")
        self.timeline_empty = QLabel()
        self.timeline_empty.setObjectName("releases-empty")
        self.timeline_empty.setProperty("muted", True)
        self.timeline_empty.setWordWrap(True)
        self.timeline_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        host = QWidget()
        stack = QStackedLayout(host)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.addWidget(self.timeline)
        stack.addWidget(self.timeline_empty)
        self._timeline_stack = stack
        tl.addWidget(host, 1)
        split.addWidget(top)

        # ---- the differences --------------------------------------------------------------------
        bottom = QWidget()
        dl = QVBoxLayout(bottom)
        dl.setContentsMargins(0, 0, 0, 0)
        dtitle = QLabel(strings.REL_DIFF_TITLE)
        dtitle.setProperty("heading", True)
        dl.addWidget(dtitle)
        pick = QHBoxLayout()
        self.before = QComboBox()
        self.before.setObjectName("releases-before")
        self.before.setAccessibleName(strings.REL_BEFORE)
        self.after = QComboBox()
        self.after.setObjectName("releases-after")
        self.after.setAccessibleName(strings.REL_AFTER)
        for text, box in ((strings.REL_BEFORE, self.before), (strings.REL_AFTER, self.after)):
            lab = QLabel(text)
            lab.setBuddy(box)
            pick.addWidget(lab)
            pick.addWidget(box)
        pick.addStretch(1)
        self.mark = QPushButton()
        self.mark.setObjectName("releases-mark")
        icons.icon_button(self.mark, "diagram", theme, strings.REL_MARK_TIP, text=strings.MARK_DIAGRAM)  # fmt: skip
        self.mark.setToolTip(strings.REL_MARK_TIP)
        self.clear = QPushButton()
        self.clear.setObjectName("releases-clear")
        icons.icon_button(self.clear, "close", theme, strings.REL_CLEAR_TIP, text=strings.CLEAR_MARKS)  # fmt: skip
        self.clear.setToolTip(strings.REL_CLEAR_TIP)
        pick.addWidget(self.mark)
        pick.addWidget(self.clear)
        dl.addLayout(pick)
        self.summary = QLabel()
        self.summary.setObjectName("releases-summary")
        self.summary.setWordWrap(True)
        dl.addWidget(self.summary)
        body = QSplitter(Qt.Orientation.Horizontal)
        body.setObjectName("releases-diff-split")
        body.setChildrenCollapsible(False)
        self.groups = QListView()
        self.groups.setObjectName("releases-groups")
        self.groups.setAccessibleName(strings.REL_DIFF_NAME)
        self.groups.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.group_model = QStandardItemModel(self.groups)
        self.groups.setModel(self.group_model)
        dcols = [
            Column("change", strings.REL_DIFF_COLUMNS["change"], width=90),
            Column("kind", strings.REL_DIFF_COLUMNS["kind"], width=120),
            Column("id", strings.REL_DIFF_COLUMNS["id"], mono=True, width=110),
            Column("field", strings.REL_DIFF_COLUMNS["field"], width=150),
            Column(
                "before", strings.REL_DIFF_COLUMNS["before"], mono=True, tooltip="before", width=200
            ),  # fmt: skip
            Column(
                "after", strings.REL_DIFF_COLUMNS["after"], mono=True, tooltip="after", width=200
            ),  # fmt: skip
        ]
        self.diff_model = DictTableModel(dcols, [], theme)
        self.diff = TableView(
            self.diff_model,
            theme,
            name=strings.REL_DIFF_TABLE,
            settings=settings,
            key="releases-diff",
        )
        self.diff.setObjectName("releases-diff")
        body.addWidget(self.groups)
        body.addWidget(self.diff)
        body.setStretchFactor(0, 1)
        body.setStretchFactor(1, 4)
        dl.addWidget(body, 1)
        split.addWidget(bottom)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)

        # ---- wiring -----------------------------------------------------------------------------
        self.harness.currentIndexChanged.connect(self._harness_picked)
        self.before.currentIndexChanged.connect(self._compare)
        self.after.currentIndexChanged.connect(self._compare)
        sel = self.timeline.selectionModel()
        if sel is not None:
            sel.selectionChanged.connect(lambda *_: self._row_picked())
        groups_sel = self.groups.selectionModel()
        if groups_sel is not None:
            groups_sel.currentChanged.connect(lambda *_: self._show_group())
        self.mark.clicked.connect(self.mark_on_diagram)
        self.clear.clicked.connect(lambda: self.ctl.set_marks({}))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.refresh)
        ctl.changed.connect(lambda _d: self._invalidate())
        self.refresh()

    # ---- keeping up with the project ------------------------------------------------------

    def _invalidate(self) -> None:
        """The project changed: a visible panel reads it again a moment later (many edits in a row
        cost one read, and an edit stays under its time budget); a hidden one when it is shown."""
        self._dirty = True
        if self.isVisible():
            self._timer.start()

    def showEvent(self, event: object) -> None:
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    def refresh(self) -> None:
        """Read the project again (the window refreshes a hidden tab when it is shown)."""
        self._dirty = False
        self._cache.clear()
        project = self.ctl.project
        keep = self.current_harness()
        keep_entry = self.selected_entry()
        self._building = True
        try:
            self.harness.clear()
            self.harness.addItem(strings.REL_ALL, ALL)
            for hid in sorted(project.harnesses):
                h = project.harnesses[hid]
                state = STATES[harness_state(project, hid)].label
                self.harness.addItem(strings.REL_HARNESS_ITEM.format(hid, state, h.revision), hid)
            index = self.harness.findData(keep or ALL)
            self.harness.setCurrentIndex(max(0, index))
        finally:
            self._building = False
        self._load_timeline()
        self._select_entry(keep_entry)
        self._fill_pickers()
        self._update_actions()
        self._compare()

    def _select_entry(self, entry: str | None) -> None:
        """Select the timeline line with this entry ID again (after the rows were read anew)."""
        sel = self.timeline.selectionModel()
        if not entry or sel is None:
            return
        self._building = True
        try:
            for i in range(self.timeline.proxy.rowCount()):
                row = self.timeline.row_at(self.timeline.proxy.index(i, 0))
                if isinstance(row, Mapping) and row.get("id") == entry:
                    index = self.timeline.proxy.index(i, 0)
                    sel.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
                    sel.select(
                        index,
                        QItemSelectionModel.SelectionFlag.ClearAndSelect
                        | QItemSelectionModel.SelectionFlag.Rows,
                    )
                    return
        finally:
            self._building = False

    def selected_entry(self) -> str | None:
        """The change-log entry ("C0001") of the selected timeline line, if one is selected."""
        rows = self.timeline.selected_rows()
        return str(rows[0]["id"]) if rows and isinstance(rows[0], Mapping) else None

    # ---- the harness the panel is about -------------------------------------------------------

    def current_harness(self) -> str | None:
        """The harness chosen in the box, or else the one of the selected timeline line."""
        chosen = self.harness.currentData()
        if chosen:
            return str(chosen)
        rows = self.timeline.selected_rows()
        if rows and isinstance(rows[0], Mapping):
            return str(rows[0]["harness"])
        return None

    def select_harness(self, harness_id: str) -> bool:
        """Choose a harness in the box; False if the project has no such harness."""
        if self._dirty:
            self.refresh()
        index = self.harness.findData(harness_id)
        if index < 0:
            return False
        self.harness.setCurrentIndex(index)
        return True

    def _harness_picked(self) -> None:
        if self._building:
            return
        self._load_timeline()
        self._fill_pickers()
        self._update_actions()
        self._compare()
        self.harnessChanged.emit(self.current_harness() or "")

    def _row_picked(self) -> None:
        if self._building:
            return
        self._fill_pickers(prefer=self._selected_revision())
        self._update_actions()
        self._compare()
        self.harnessChanged.emit(self.current_harness() or "")

    def _selected_revision(self) -> str | None:
        rows = self.timeline.selected_rows()
        if rows and isinstance(rows[0], Mapping) and rows[0].get("has_baseline"):
            return str(rows[0]["revision"])
        return None

    # ---- the timeline -------------------------------------------------------------------------

    def _load_timeline(self) -> None:
        chosen = str(self.harness.currentData() or "") or None
        rows = timeline_rows(self.ctl.project, chosen)
        self.timeline_model.set_rows(rows)
        self.timeline_empty.setText(
            strings.REL_EMPTY_ONE.format(chosen) if chosen else strings.REL_EMPTY_ALL
        )
        self._timeline_stack.setCurrentWidget(self.timeline if rows else self.timeline_empty)

    # ---- the actions --------------------------------------------------------------------------

    def _request(self, action: str) -> None:
        hid = self.current_harness()
        if not hid or not self.action_buttons[action].isEnabled():
            return
        self.changeRequested.emit(action, hid)
        {
            "review": self.submitReviewRequested,
            "release": self.releaseRequested,
            "revise": self.reviseRequested,
        }[action].emit(hid)

    def action_enabled(self, action: str) -> bool:
        return self.action_buttons[action].isEnabled()

    def _update_actions(self) -> None:
        project = self.ctl.project
        hid = self.current_harness()
        h = project.harnesses.get(hid or "")
        if h is None:
            self.state.hide()
        else:
            self.state.set_state(harness_state(project, h.id), strings.REL_REVISION.format(h.revision))  # fmt: skip
            self.state.show()
        status = h.status if h is not None else ""
        wanted = {"review": ("draft",), "release": ("draft", "in_review"), "revise": ("released",)}
        tips = {
            "review": strings.REL_SUBMIT_TIP,
            "release": strings.REL_RELEASE_TIP,
            "revise": strings.REL_REVISE_TIP,
        }
        for action, button in self.action_buttons.items():
            ok = h is not None and status in wanted[action] and not self.ctl.read_only
            button.setEnabled(ok)
            tip = tips[action]
            if not ok:  # a disabled button says why
                if self.ctl.read_only:
                    tip = f"{tip}. {strings.REL_READ_ONLY}"
                elif h is None:
                    tip = f"{tip}. {strings.REL_CHOOSE_HARNESS}"
                else:
                    tip = f"{tip}. {strings.REL_WRONG_STATE.format(h.id, h.status.replace('_', ' '), ' or '.join(w.replace('_', ' ') for w in wanted[action]))}"  # fmt: skip
            button.setToolTip(tip)
        note = (
            strings.REL_READ_ONLY
            if self.ctl.read_only
            else strings.REL_CHOOSE_HARNESS
            if h is None
            else ""
        )
        self.action_note.setText(note)
        self.action_note.setVisible(bool(note))

    # ---- the differences ----------------------------------------------------------------------

    def _fill_pickers(self, prefer: str | None = None) -> None:
        hid = self.current_harness()
        revs = [b.revision for b in baselines_of(self.ctl.project, hid)] if hid else []
        before_now = prefer or self.before.currentData()
        after_now = self.after.currentData()
        self._building = True
        try:
            self.before.clear()
            self.after.clear()
            for rev in revs:
                self.before.addItem(strings.REL_REVISION.format(rev), rev)
            self.after.addItem(strings.REL_WORKING, WORKING)
            for rev in revs:
                self.after.addItem(strings.REL_REVISION.format(rev), rev)
            if revs:
                i = self.before.findData(before_now)
                self.before.setCurrentIndex(i if i >= 0 else len(revs) - 1)
                j = self.after.findData(after_now)
                self.after.setCurrentIndex(j if j >= 0 else 0)
        finally:
            self._building = False
        self.before.setEnabled(bool(revs))
        self.after.setEnabled(bool(revs))

    def compare(self, harness_id: str, before: str, after: str | None = None) -> bool:
        """Show the changes of `harness_id` from revision `before` to revision `after` (None: the
        working design). False if the harness or a revision does not exist."""
        if not self.select_harness(harness_id):
            return False
        i = self.before.findData(before)
        j = self.after.findData(after if after else WORKING)
        if i < 0 or j < 0:
            return False
        self.before.setCurrentIndex(i)
        self.after.setCurrentIndex(j)
        return True

    def _compare(self) -> None:
        if self._building:
            return
        hid = self.current_harness()
        self._diff, self._groups = None, []
        self.mark.setEnabled(False)
        if not hid:
            self._no_diff(strings.REL_DIFF_NEED_HARNESS)
            return
        revs = [b.revision for b in baselines_of(self.ctl.project, hid)]
        if not revs:
            self._no_diff(strings.REL_DIFF_NO_BASE.format(hid))
            return
        before = str(self.before.currentData() or "")
        after = str(self.after.currentData() or "") or None
        if not before or before == after:
            self._no_diff(strings.REL_DIFF_SAME)
            return
        key = (hid, before, after, self.ctl.history.revision)
        diff = self._cache.get(key)
        if diff is None:
            try:
                diff = compare_revisions(self.ctl.project, hid, before, after)
            except HarnessError as exc:
                self._no_diff(str(exc))
                return
            self._cache[key] = diff
        self._diff = diff
        self._groups = diff_groups(diff)
        a = strings.REL_REVISION.format(after) if after else strings.REL_WORKING
        b = strings.REL_REVISION.format(before)
        self.summary.setText(
            strings.REL_DIFF_SUMMARY.format(b, a, diff.summary())
            if not diff.empty
            else strings.REL_DIFF_NONE.format(b, a)
        )
        self._fill_groups()
        self.mark.setEnabled(not diff.empty)
        self.diffChanged.emit(len(diff.changes))

    def _no_diff(self, message: str) -> None:
        self.summary.setText(message)
        self.group_model.clear()
        self.diff_model.set_rows([])
        self.diffChanged.emit(0)

    def _fill_groups(self) -> None:
        self.group_model.clear()
        total = sum(len(g.rows) for g in self._groups)
        first = QStandardItem(f"{strings.REL_ALL_KINDS} ({total})")
        first.setData("", Qt.ItemDataRole.UserRole)
        self.group_model.appendRow(first)
        for g in self._groups:
            item = QStandardItem(group_text(g))
            item.setData(g.kind, Qt.ItemDataRole.UserRole)
            item.setToolTip(group_text(g))
            self.group_model.appendRow(item)
        for r in range(self.group_model.rowCount()):
            self.group_model.item(r).setEditable(False)
        self.groups.setCurrentIndex(self.group_model.index(0, 0))
        self._show_group()

    def _show_group(self) -> None:
        index = self.groups.currentIndex()
        kind = str(index.data(Qt.ItemDataRole.UserRole) or "") if index.isValid() else ""
        self.diff_model.set_rows(diff_table_rows(self._groups, kind or None))

    def select_group(self, kind: str | None) -> None:
        """Show the changes of one kind of object (`"wire"`, `"box_pin"` ...), or all of them."""
        for r in range(self.group_model.rowCount()):
            item = self.group_model.item(r)
            if str(item.data(Qt.ItemDataRole.UserRole) or "") == (kind or ""):
                self.groups.setCurrentIndex(self.group_model.index(r, 0))
                return

    def mark_on_diagram(self) -> int:
        """Mark the changed units, interfaces and harnesses on the diagram; returns how many."""
        if self._diff is None:
            return 0
        marks = self._diff.affected()
        self.ctl.set_marks(marks)
        return len(marks)

    def group_index(self, kind: str) -> QModelIndex:
        for r in range(self.group_model.rowCount()):
            if str(self.group_model.item(r).data(Qt.ItemDataRole.UserRole) or "") == kind:
                return self.group_model.index(r, 0)
        return QModelIndex()
