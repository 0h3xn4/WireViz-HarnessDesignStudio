"""EditorController: the only object that changes the project. The GUI asks, it executes.

Every edit goes through `History.execute`, so it is a transaction (rolled back if it would leave the
project inconsistent), undoable, autosaved to the recovery journal, and reported to the views as a
small `Delta` so they redraw only what changed.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from pydantic import ValidationError
from PySide6.QtCore import QObject, QThread, QTimer, Signal

from harness_design_studio.core import checks, drc, edit
from harness_design_studio.core.commands import Delete, History, Op, Put, SetZones, apply_ops
from harness_design_studio.core.errors import HarnessError, SaveError, TransactionError
from harness_design_studio.core.generate.engine import GenerationPlan, generation_status, input_hash
from harness_design_studio.core.imports import ImportPlan
from harness_design_studio.core.io.fs import ProjectLock
from harness_design_studio.core.io.loader import LoadResult, disk_fingerprint, load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Project
from harness_design_studio.core.outputs.build import DEFAULT_FOLDER, outputs_status
from harness_design_studio.core.recovery import (
    clear_journal,
    has_journal,
    journal_differs_from_disk,
    journal_path,
    read_journal,
    write_journal,
)
from harness_design_studio.core.samples import mini3, new_project
from harness_design_studio.core.vcs.release import ReleasePlan

from . import strings
from .drc_process import abort_check, run_check

JOURNAL_DELAY_MS = 1500
DRC_DELAY_MS = 1200  # run only after the user pauses (the check itself runs in another process)


class DrcWorker(QThread):
    """Runs the design rule check on a private copy of the project, in a helper process (this thread
    only waits for it, so it does not hold up the editor)."""

    def __init__(self, snapshot: Project, token: tuple[int, int]) -> None:
        super().__init__()
        self.snapshot = snapshot
        self.token = token
        self.found: list[checks.Finding] = []
        self.error: str | None = None  # why the check could not be completed
        self.completed = False  # set by run(), before the thread's `finished` signal
        self._cancelled = False

    def cancel(self) -> None:
        """Stop waiting for the helper (the result would be thrown away): kill it, and do not
        repeat the check in this thread."""
        self._cancelled = True
        abort_check()

    def run(self) -> None:
        try:
            self.found = run_check(self.snapshot, lambda: self._cancelled)
        except Exception as exc:  # never let it escape the thread: that would read as "no problems"
            self.error = reason_of(exc)
        finally:
            self.completed = True


@dataclass
class Delta:
    """What a change touched. `full` means redraw everything."""

    units: set[str] = field(default_factory=set)
    interfaces: set[str] = field(default_factory=set)
    followers: set[str] = field(default_factory=set)  # in `interfaces` only because a unit moved
    full: bool = False
    tables: bool = True


@dataclass(frozen=True)
class Selection:
    kind: str  # "unit" | "interface"
    id: str


@dataclass(frozen=True)
class ConnectFrom:
    unit_id: str
    connector_id: str | None


class NeedSaveAs(HarnessError):
    """The project has no folder yet (sample or unsaved)."""


RELEASE_WAIT_MS = 5000  # how long closing the window waits for a check that cannot be stopped
_ABANDONED: list[QThread] = []  # checks still running at exit: kept alive so Qt does not abort

MANY_FINDINGS = 1000  # above this, panels listing findings refresh on a short timer
LIST_DELAY_MS = 60


class EditorController(QObject):
    changed = Signal(object)  # Delta
    selectionChanged = Signal()
    connectChanged = Signal()
    modeChanged = Signal()
    message = Signal(str, bool)  # text, offer an Undo button
    stateChanged = Signal()  # title, dirty, read-only, banners
    drcChanged = Signal()  # new design rule results arrived
    drcStateChanged = Signal()  # checking started or finished
    marksChanged = Signal()  # diff marks on the diagram changed

    def __init__(
        self, journal_delay_ms: int = JOURNAL_DELAY_MS, drc_delay_ms: int = DRC_DELAY_MS
    ) -> None:
        super().__init__()
        self.project: Project = new_project()
        self.history = History(self.project)
        self.root: Path | None = None
        self.sample = False
        self.mode = "guided"
        self.selection: Selection | None = None
        self.tool = "select"
        self.connect_type: str | None = None
        self.connect_from: ConnectFrom | None = None
        self._lock: ProjectLock | None = None
        self._fingerprint: str | None = None
        self._saved_revision = 0
        self._kept_fingerprint: str | None = None  # "Keep my version": the disk state we ignore
        self.open_note: str | None = None  # why the last open_path was not a normal open
        self.journal_error_shown = False
        self._findings_cache: tuple[object, list[checks.Finding]] | None = None
        self._open_cache: list[checks.Finding] | None = None
        self._counts_cache: tuple[object, tuple[int, int]] | None = None
        self._owners: dict[str, str] = {}
        self._ends: dict[str, tuple[str, ...]] = {}
        self._installs = 0
        self.diff_marks: dict[str, str] = {}  # object ID -> added | changed | removed
        self.user_name = ""
        self.today: Callable[[], str] = lambda: date.today().isoformat()
        self._drc_raw: list[checks.Finding] = []
        self._drc_token: tuple[int, int] | None = None  # (installs, revision) the result is for
        self._drc_worker: DrcWorker | None = None
        self._retired: list[DrcWorker] = []  # cancelled checks that have not ended yet
        self._drc_version = 0
        self.drc_error: str | None = None  # the last check failed (shown instead of "all checked")
        self._drc_failed_token: tuple[int, int] | None = None
        self._drc_timer = QTimer(self)
        self._drc_timer.setSingleShot(True)
        self._drc_timer.setInterval(drc_delay_ms)
        self._drc_timer.timeout.connect(self._start_drc)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(journal_delay_ms)
        self._timer.timeout.connect(self.write_journal_now)

    # ---- state ------------------------------------------------------------------------------

    def findings_key(self) -> tuple[int, int, int, int]:
        """Changes whenever the findings may have changed (an edit, an install, a rule result)."""
        return (self._installs, self.history.revision, id(self.project), self._drc_version)

    def findings_are_many(self) -> bool:
        """True when the last result was large; lists that depend on it then update after the
        canvas has been redrawn instead of inside the edit (cheap: nothing is recomputed)."""
        return self._findings_cache is not None and len(self._findings_cache[1]) > MANY_FINDINGS

    def findings(self) -> list[checks.Finding]:
        """Logical findings plus the latest design rule findings, computed once per change."""
        key = self.findings_key()
        if self._findings_cache is None or self._findings_cache[0] != key:
            merged = [*checks.find(self.project), *drc.apply_waivers(self.project, self._drc_raw)]
            if self.drc_error is not None:
                merged.append(self._drc_failure_finding(self.drc_error))
            order = {"error": 0, "warning": 1, "info": 2}
            merged.sort(key=lambda f: (order[f.severity], f.id))
            self._findings_cache = (key, merged)
            self._open_cache = None
        return self._findings_cache[1]

    # ---- design rule check (background) --------------------------------------------------------

    @property
    def drc_current(self) -> bool:
        return self._drc_token == (self._installs, self.history.revision)

    @staticmethod
    def _drc_failure_finding(message: str) -> checks.Finding:
        return checks.Finding(
            id="drc-failed",
            rule="drc-failed",
            severity="error",
            object_id="",
            title=message,
            why=strings.DRC_FAILED_WHY,
        )

    def _schedule_drc(self) -> None:
        self._drc_timer.start()
        self.drcStateChanged.emit()

    def _start_drc(self) -> None:
        if self._drc_worker is not None:  # one at a time; the finished handler reschedules
            return
        token = (self._installs, self.history.revision)
        worker = DrcWorker(edit.clone_with(self.project, []), token)
        worker.finished.connect(self._drc_done)
        self._drc_worker = worker
        worker.start()

    def _drc_done(self) -> None:
        self._retired = [w for w in self._retired if not w.wait(0)]
        worker = self._drc_worker
        if worker is None or not worker.completed:  # the signal was a retired check's
            return
        self._drc_worker = None
        worker.wait()
        if worker.token[0] == self._installs:
            if worker.error is None:
                self._drc_raw, self._drc_token = worker.found, worker.token
                self.drc_error = self._drc_failed_token = None
            else:  # not a result: stays "not current" and is not retried until something changes
                self._drc_raw, self._drc_token = [], None
                self.drc_error = strings.DRC_FAILED.format(worker.error)
                self._drc_failed_token = worker.token
            self._drc_version += 1
        if not self.drc_current and self._drc_failed_token != (
            self._installs,
            self.history.revision,
        ):
            self._schedule_drc()
        self.drcChanged.emit()
        self.drcStateChanged.emit()

    def run_drc_now(self) -> None:
        """Synchronous check (tests, scripts); the editor itself uses the background worker."""
        self._drc_timer.stop()
        self.wait_drc()
        self._drc_raw = drc.run(self.project)
        self._drc_token = (self._installs, self.history.revision)
        self.drc_error = self._drc_failed_token = None
        self._drc_version += 1
        self.drcChanged.emit()
        self.drcStateChanged.emit()

    def wait_drc(self) -> None:
        """Forget the running check without waiting for a long or stuck one: its helper is killed
        and its result, if it still arrives, is not used."""
        worker, self._drc_worker = self._drc_worker, None
        if worker is None:
            return
        worker.cancel()
        self._retired = [w for w in self._retired if not w.wait(0)]
        if not worker.wait(0):
            self._retired.append(worker)

    def open_findings(self) -> list[checks.Finding]:
        """Findings without a waiver, built once per change (a project can have tens of
        thousands, and several panels ask on every edit)."""
        found = self.findings()
        if self._open_cache is None:
            self._open_cache = [f for f in found if f.waiver is None]
        return self._open_cache

    def severity_counts(self) -> tuple[int, int]:
        """(errors, warnings) among the open findings."""
        key = self.findings_key()
        if self._counts_cache is None or self._counts_cache[0] != key:
            open_ = self.open_findings()
            errors = sum(f.severity == "error" for f in open_)
            warnings = sum(f.severity == "warning" for f in open_)
            self._counts_cache = (key, (errors, warnings))
        return self._counts_cache[1]

    def todos(self) -> list[checks.Todo]:
        return checks.todos_from(self.findings())

    @property
    def autosaves(self) -> bool:
        """Whether unsaved changes are being kept in the recovery journal (needs a project folder)."""
        return self.root is not None and not self.read_only and not self.journal_error_shown

    @property
    def dirty(self) -> bool:
        return self.history.revision != self._saved_revision

    @property
    def read_only(self) -> bool:
        return self.project.read_only

    @property
    def title(self) -> str:
        name = self.project.meta.name
        return f"{name}{' *' if self.dirty else ''}{' (read-only)' if self.read_only else ''}"

    def set_mode(self, mode: str) -> None:
        if mode in ("guided", "expert") and mode != self.mode:
            self.mode = mode
            self.connect_from = None
            self.modeChanged.emit()
            self.connectChanged.emit()

    # ---- running edits -----------------------------------------------------------------------

    def run(
        self, label: str, ops: list[Op], *, message: str | None = None, undo: bool = True
    ) -> bool:
        """Execute ops as one transaction. Returns False (and tells the user why) if rejected."""
        if not ops:
            return True
        before = self._before_change()
        try:
            self.history.execute(label, ops)
        except TransactionError as exc:
            self._say_why_not(exc)
            return False
        except HarnessError as exc:
            self.message.emit(str(exc), False)
            return False
        self._after_change(self.history.last_ops, before)
        if message:
            self.message.emit(message, undo)
        return True

    def attempt(self, label: str, build: "object", *, message: str | None = None) -> bool:
        """Build ops with a function that may raise EditError, then run them."""
        try:
            ops = build()  # type: ignore[operator]
        except (HarnessError, ValidationError) as exc:
            self.message.emit(_plain(exc), False)
            return False
        return self.run(label, ops, message=message)

    def undo(self) -> None:
        if self.history.can_undo and not self.read_only:
            before = self._before_change()
            try:
                label = self.history.undo()
            except HarnessError as exc:  # for example a step that removes a saved release record
                self._say_why_not(exc)
                return
            self._after_change(self.history.last_ops, before)
            self.message.emit(strings.UNDONE.format(label), False)

    def redo(self) -> None:
        if self.history.can_redo and not self.read_only:
            before = self._before_change()
            try:
                label = self.history.redo()
            except HarnessError as exc:  # for example a harness that was released in the meantime
                self._say_why_not(exc)
                return
            self._after_change(self.history.last_ops, before)
            self.message.emit(strings.REDONE.format(label), False)

    def _say_why_not(self, exc: HarnessError) -> None:
        problems = exc.problems[:2] if isinstance(exc, TransactionError) else []
        self.message.emit(f"{exc} {' '.join(problems)}".strip(), False)

    def _before_change(self) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
        """Unit of every box connector and units at the ends of every interface, captured before a
        change so that deletions (and the undo of an addition) can be attributed."""
        owners = {c.id: c.unit_id for c in self.project.connectors.values() if c.unit_id}
        ends = {
            i.id: tuple(e.unit_id for e in i.endpoints) for i in self.project.interfaces.values()
        }
        return owners, ends

    def _after_change(
        self,
        ops: list[Op],
        before: tuple[dict[str, str], dict[str, tuple[str, ...]]] | None = None,
    ) -> None:
        self._owners, self._ends = before or ({}, {})
        self._clear_stale_connect()
        delta = self._delta_of(ops)
        if self.selection and not self._selection_exists():
            self.selection = None
            self.selectionChanged.emit()
        self.changed.emit(delta)
        self.stateChanged.emit()
        self._schedule_journal()
        self._schedule_drc()

    def _clear_stale_connect(self) -> None:
        """The connect tool forgets a first pick whose unit is gone (deleted, or its add undone)."""
        src = self.connect_from
        if src is not None and src.unit_id not in self.project.units:
            self.connect_from = None
            self.connectChanged.emit()

    def _selection_exists(self) -> bool:
        s = self.selection
        if s is None:
            return False
        return s.id in (self.project.units if s.kind == "unit" else self.project.interfaces)

    def _delta_of(self, ops: list[Op]) -> Delta:
        d = Delta()
        for op in ops:
            if isinstance(op, SetZones):
                d.full = True
            elif isinstance(op, (Put, Delete)):
                self._note(d, op)
        # links follow their units
        for i in self.project.interfaces.values():
            if i.id not in d.interfaces and any(e.unit_id in d.units for e in i.endpoints):
                d.interfaces.add(i.id)
                d.followers.add(i.id)
        return d

    def _note(self, d: Delta, op: Put | Delete) -> None:
        key = op.obj.id if isinstance(op, Put) else op.key  # type: ignore[attr-defined]
        if op.collection in ("units", "placements"):
            d.units.add(key)
        elif op.collection == "interfaces":
            d.interfaces.add(key)
            d.units.update(self._ends.get(key, ()))  # as it was before (it may be gone now)
            for e in (
                self.project.interfaces[key].endpoints if key in self.project.interfaces else ()
            ):
                d.units.add(e.unit_id)
            if isinstance(op, Put):
                d.units.update(e.unit_id for e in op.obj.endpoints)  # type: ignore[attr-defined]
        elif op.collection == "connectors":
            unit = op.obj.unit_id if isinstance(op, Put) else self._owners.get(key)  # type: ignore[attr-defined]
            if unit:
                d.units.add(unit)
            else:
                d.full = True

    # ---- selection and connect tool ---------------------------------------------------------

    def select(self, kind: str | None, id_: str | None = None) -> None:
        new = Selection(kind, id_) if kind and id_ else None
        if new != self.selection:
            self.selection = new
            self.selectionChanged.emit()

    def begin_connect(self, type_id: str | None) -> None:
        if type_id is not None and type_id not in self.project.interface_types:
            type_id = None  # a type that is not in this project (stale menu entry)
        self.tool = "connect"
        self.connect_type = type_id
        self.connect_from = None
        self.connectChanged.emit()

    def end_connect(self) -> None:
        self.tool = "select"
        self.connect_type = None
        self.connect_from = None
        self.connectChanged.emit()

    def unit_compat(self, unit_id: str) -> edit.Compat:
        src = self.connect_from.unit_id if self.connect_from else None
        if self.connect_type is None:
            return edit.Compat(False, strings.PICK_TYPE_SHORT, strings.PICK_TYPE_FIRST)
        return edit.unit_compat(self.project, self.connect_type, unit_id, src)

    def connector_compat(self, connector_id: str) -> edit.Compat:
        src = self.connect_from.unit_id if self.connect_from else None
        if self.connect_type is None:
            return edit.Compat(False, strings.PICK_TYPE_SHORT, strings.PICK_TYPE_FIRST)
        return edit.connector_compat(self.project, self.connect_type, connector_id, src)

    def unit_has_valid_connector(self, unit_id: str) -> bool:
        if self.connect_type is None:
            return False
        if self.mode == "guided":
            return self.unit_compat(unit_id).ok
        return any(
            self.connector_compat(c.id).ok for c in edit.unit_connectors(self.project, unit_id)
        )

    def connect_hint(self) -> str:
        return self.connect_hint_and_warning()[0]

    def connect_hint_and_warning(self) -> tuple[str, bool]:
        """The line under the toolbar while connecting, and whether it is a warning (no unit can
        take the chosen type)."""
        if self.tool != "connect":
            return "", False
        if self.connect_type is None:
            return strings.CONNECT_PICK_TYPE, False
        itype = self.project.interface_types.get(self.connect_type)
        if itype is None:  # a type that is not in this project (cannot normally happen)
            return strings.CONNECT_PICK_TYPE, False
        name = itype.name
        thing = strings.CONNECTOR_WORD if self.mode == "expert" else strings.UNIT_WORD
        if self.connect_from is None:
            return strings.CONNECT_FIRST.format(thing, name), False
        others = [u for u in self.project.units if u != self.connect_from.unit_id]
        if not any(self.unit_has_valid_connector(u) for u in others):
            return strings.CONNECT_NONE_FREE.format(name), True
        return strings.CONNECT_SECOND.format(thing), False

    def pick(self, unit_id: str, connector_id: str | None = None) -> None:
        """Connect tool: first pick sets the source, second pick creates the interface."""
        if self.read_only or self.connect_type is None:
            return
        self._clear_stale_connect()
        compat = (
            self.connector_compat(connector_id)
            if self.mode == "expert" and connector_id
            else self.unit_compat(unit_id)
        )
        if self.mode == "expert" and connector_id is None:
            self.message.emit(strings.CLICK_CONNECTOR, False)
            return
        if not compat.ok:
            self.message.emit(compat.why, False)
            return
        if self.connect_from is None:
            self.connect_from = ConnectFrom(unit_id, connector_id)
            self.connectChanged.emit()
            return
        src, type_id = self.connect_from, self.connect_type
        try:
            ops, iid = edit.ops_add_interface(
                self.project, type_id, src.unit_id, unit_id, src.connector_id, connector_id
            )
        except HarnessError as exc:
            self.message.emit(str(exc), False)
            self.connect_from = None
            self.connectChanged.emit()
            return
        auto = strings.IF_ADDED_AUTO if self.mode == "guided" else ""
        if self.run(strings.STEP_ADD_INTERFACE, ops, message=strings.IF_ADDED.format(iid) + auto):
            self.connect_from = None
            self.select("interface", iid)
            self.connectChanged.emit()

    # ---- high-level edits --------------------------------------------------------------------

    def add_unit(
        self, template_id: str, x: float | None = None, y: float | None = None
    ) -> str | None:
        try:
            ops, uid = edit.ops_add_unit(self.project, template_id, x, y)
        except HarnessError as exc:
            self.message.emit(str(exc), False)
            return None
        label = edit.TEMPLATES[template_id].label
        if self.run(strings.STEP_ADD.format(label), ops):
            self.select("unit", uid)
            return uid
        return None

    def delete_impact(self, unit_id: str) -> edit.DeleteImpact:
        return edit.delete_impact(self.project, unit_id)

    def delete_selected(self) -> bool:
        s = self.selection
        if s is None:
            return False
        if s.kind == "unit":
            return self.attempt(
                strings.STEP_DELETE.format(s.id),
                lambda: edit.ops_delete_unit(self.project, s.id),
                message=strings.DELETED.format(s.id),
            )
        return self.attempt(
            strings.STEP_DELETE.format(s.id),
            lambda: edit.ops_delete_interface(self.project, s.id),
            message=strings.DELETED.format(s.id),
        )

    def move_unit(self, unit_id: str, x: float, y: float) -> None:
        zone_before = self.project.units[unit_id].zone
        if self.attempt(
            strings.STEP_MOVE.format(unit_id),
            lambda: edit.ops_move_unit(self.project, unit_id, x, y),
        ):
            zone = self.project.units[unit_id].zone
            if zone != zone_before:
                self.message.emit(strings.NOW_IN_ZONE.format(unit_id, zone), True)

    def redundant_copy(self, unit_id: str) -> None:
        try:
            result = edit.ops_redundant_copy(self.project, unit_id)
        except HarnessError as exc:
            self.message.emit(str(exc), False)
            return
        extra = (
            strings.REDUNDANT_SKIPPED.format(len(result.skipped), ", ".join(result.skipped))
            if result.skipped
            else ""
        )
        if self.run(
            strings.STEP_REDUNDANT_COPY.format(unit_id),
            result.ops,
            message=strings.REDUNDANT_DONE.format(result.twin_id, extra),
        ):
            self.select("unit", result.twin_id)

    def apply_fix(self, finding: checks.Finding) -> None:
        try:
            ops, msg = checks.fix_ops(self.project, finding)
        except HarnessError as exc:
            self.message.emit(str(exc), False)
            return
        self.run(strings.STEP_FIX.format(finding.title), ops, message=msg)

    def waive(self, finding: checks.Finding, justification: str) -> bool:
        try:
            op = checks.waive_op(finding, justification)
        except Exception as exc:  # pydantic ValidationError for short text, EditError otherwise
            self.message.emit(_plain(exc), False)
            return False
        return self.run(
            strings.STEP_WAIVE.format(finding.id),
            [op],
            message=strings.WAIVED,
        )

    def confirm_interface(self, interface_id: str) -> None:
        self.attempt(
            strings.STEP_CONFIRM, lambda: edit.ops_confirm_interface(self.project, interface_id)
        )

    def rename_unit(self, old: str, new: str) -> bool:
        try:
            ops = edit.ops_rename_unit(self.project, old, new)
        except Exception as exc:
            self.message.emit(_plain(exc), False)
            return False
        was_selected = self.selection is not None and self.selection.id == old
        ok = self.run(strings.STEP_RENAME.format(old), ops)
        if ok and was_selected:
            self.select("unit", new)
        return ok

    def update_unit(self, unit_id: str, **changes: object) -> bool:
        return self.attempt(
            strings.STEP_EDIT.format(unit_id),
            lambda: edit.ops_update_unit(self.project, unit_id, **changes),
        )

    def update_interface(self, interface_id: str, **changes: object) -> bool:
        return self.attempt(
            strings.STEP_EDIT.format(interface_id),
            lambda: edit.ops_update_interface(self.project, interface_id, **changes),
        )

    def set_endpoint_connector(self, interface_id: str, index: int, connector_id: str) -> bool:
        return self.attempt(
            strings.STEP_CHOOSE_CONNECTOR,
            lambda: edit.ops_set_endpoint_connector(
                self.project, interface_id, index, connector_id
            ),
        )

    def set_connector_part(self, connector_id: str, part_id: str) -> bool:
        return self.attempt(
            strings.STEP_CHANGE_PART,
            lambda: edit.ops_set_connector_part(self.project, connector_id, part_id),
        )

    def add_zone(self, name: str) -> bool:
        return self.attempt(
            strings.STEP_ADD_ZONE,
            lambda: edit.ops_add_zone(self.project, name),
            message=strings.ZONE_ADDED.format(name.strip()),
        )

    def add_interface_between(self, type_id: str, from_unit: str, to_unit: str) -> bool:
        try:
            ops, iid = edit.ops_add_interface(self.project, type_id, from_unit, to_unit)
        except HarnessError as exc:
            self.message.emit(str(exc), False)
            return False
        if self.run(strings.STEP_ADD_INTERFACE, ops, message=strings.IF_ADDED.format(iid)):
            self.select("interface", iid)
            return True
        return False

    # ---- generation --------------------------------------------------------------------------

    def generation_status(self) -> str:
        return generation_status(self.project)

    def outputs_folder(self) -> Path | None:
        return None if self.root is None else self.root / DEFAULT_FOLDER

    def outputs_state(self) -> str:
        """Quick stale check (model hashes only); the CLI and verifier check file contents."""
        folder = self.outputs_folder()
        if folder is None:
            return "unsaved"
        return outputs_status(self.project, folder).state

    # ---- change control ----------------------------------------------------------------------

    def set_marks(self, marks: dict[str, str]) -> None:
        self.diff_marks = dict(marks)
        self.marksChanged.emit()

    def apply_change(self, plan: ReleasePlan, message: str) -> bool:
        """Run a review, release or new-revision plan as one undoable step."""
        if not plan.ok:
            self.message.emit(plan.blockers[0].message, False)
            return False
        return self.run(plan.label, plan.ops, message=message)

    @staticmethod
    def plan_problems(plan: GenerationPlan) -> int:
        """Errors and warnings the plan carries; a plan with any is never "up to date"."""
        return sum(f.severity in ("error", "warning") for f in plan.report.findings)

    @property
    def state_token(self) -> tuple[int, int]:
        """Changes with every edit and every opened project (to tell if a slow job went stale)."""
        return (self._installs, self.history.revision)

    def apply_generation(
        self, plan: GenerationPlan, planned_at: tuple[int, int] | None = None
    ) -> bool:
        """Apply a plan. A plan made for an earlier state of the project (`planned_at` is the
        `state_token` it was made at) is refused: it could undo or overwrite later edits."""
        stale = planned_at is not None and planned_at != self.state_token
        if not stale:  # the inputs the plan saw must be the ones it would be applied to
            stale = input_hash(edit.clone_with(self.project, plan.ops)) != plan.record.input_hash
        if stale:
            self.message.emit(strings.GEN_STALE, False)
            return False
        errors = len(plan.report.errors)
        if plan.empty and not self.plan_problems(plan):
            if not self.project.interfaces:
                self.message.emit(strings.GEN_NO_INTERFACES, False)
                return True
            self.message.emit(strings.GEN_UP_TO_DATE, False)
            return True
        message = strings.GEN_WITH_ERRORS.format(errors) if errors else plan.report.plain_summary()
        return self.run(strings.STEP_GENERATE, plan.ops, message=message)

    def apply_import(self, plan: ImportPlan) -> bool:
        n = plan.ok_count
        return self.run(
            strings.STEP_IMPORT.format(n),
            plan.ops,
            message=strings.IMPORTED.format(n, "s" if n != 1 else ""),
        )

    # ---- project files -----------------------------------------------------------------------

    def _install(
        self, project: Project, root: Path | None, lock: ProjectLock | None, sample: bool = False
    ) -> None:
        if self._lock is not None and self._lock is not lock:
            self._lock.release()
        self._installs += 1
        self.project = project
        apply_ops(project, edit.ops_autoplace(project))  # positions for units saved without any
        self.history = History(project)
        self._saved_revision = 0
        self.root = root
        self.sample = sample
        self._lock = lock
        self._fingerprint = disk_fingerprint(root) if root is not None else None
        self._kept_fingerprint = None
        self.selection = None
        self.end_connect()
        self.journal_error_shown = False
        self.diff_marks = {}
        self.wait_drc()
        self._drc_raw, self._drc_token = [], None
        self.drc_error = self._drc_failed_token = None
        self._drc_version += 1
        self.changed.emit(Delta(full=True))
        self.selectionChanged.emit()
        self.stateChanged.emit()
        self._schedule_drc()

    def open_sample(self) -> None:
        self._install(mini3(), None, None, sample=True)

    def new_project(self, folder: Path, name: str) -> None:
        folder = Path(folder)
        if folder.exists() and any(folder.iterdir()):
            raise HarnessError(strings.CHOOSE_EMPTY_NEW)
        project = new_project(name)
        folder.mkdir(parents=True, exist_ok=True)
        lock = ProjectLock(folder)
        lock.acquire()
        try:
            save_project(project, folder)
        except Exception:
            lock.release()
            raise
        self._install(project, folder, lock)

    def open_path(self, folder: Path, *, read_only: bool = False) -> LoadResult:
        folder = Path(folder)
        lock: ProjectLock | None = None
        self.open_note = None
        if not (folder / "project.json").is_file():
            load_project(folder)  # says in plain words why this is not a project; nothing is left
        if not read_only:  # behind: a lock file would be written into a folder that is no project
            lock = ProjectLock(folder)
            try:
                lock.acquire()  # raises ProjectLockedError if open elsewhere
            except SaveError as exc:  # read-only media or no permission: reading is still possible
                lock, read_only = None, True
                self.open_note = strings.OPEN_NO_LOCK.format(exc)
        try:
            result = load_project(folder)
        except Exception:
            if lock:
                lock.release()
            raise
        if read_only:
            result.project.read_only = True
        self._install(result.project, folder, lock)
        return result

    def journal_available(self) -> bool:
        return (
            self.root is not None
            and has_journal(self.root)
            and journal_differs_from_disk(self.root)
        )

    def journal_base_changed(self) -> bool:
        """True if the project files changed (for example by a Git pull) after the journal was
        started: restoring it would carry the old state over the newer files."""
        if self.root is None or self._fingerprint is None:
            return False
        try:
            payload = json.loads(journal_path(self.root).read_text(encoding="utf-8"))
            base = payload.get("base_fingerprint")
        except (OSError, ValueError, AttributeError):
            return False
        return isinstance(base, str) and base != self._fingerprint

    def restore_journal(self) -> bool:
        if self.root is None:
            return False
        res = read_journal(self.root)
        if res is None:
            return False
        res.project.read_only = res.project.read_only or self.read_only  # never opens up a session
        keep_root, keep_lock = self.root, self._lock
        self._install(res.project, keep_root, keep_lock)
        self._saved_revision = -1  # restored state differs from disk: stays dirty
        self.stateChanged.emit()
        return True

    def discard_journal(self) -> None:
        if self.root is not None and self._lock is not None:  # only our own; not another window's
            self._timer.stop()  # a pending autosave would write the discarded changes again
            clear_journal(self.root)

    def save(self) -> None:
        if self.root is None:
            raise NeedSaveAs(strings.NO_FOLDER_YET)
        save_project(self.project, self.root, expected_fingerprint=self._fingerprint)
        self._after_save()

    def save_as(self, folder: Path) -> None:
        folder = Path(folder)
        if (folder / "project.json").exists():
            raise HarnessError(strings.FOLDER_HAS_PROJECT)
        if folder.exists() and any(folder.iterdir()):
            raise HarnessError(strings.CHOOSE_EMPTY)
        folder.mkdir(parents=True, exist_ok=True)
        lock = ProjectLock(folder)
        lock.acquire()
        was_read_only = self.project.read_only
        self.project.read_only = False
        try:
            save_project(self.project, folder, allow_inconsistent=self.project.recovered)
        except Exception:
            self.project.read_only = was_read_only
            lock.release()
            raise
        owned = self._lock is not None
        if self._lock:
            self._lock.release()
        if self.root is not None and owned:  # a read-only copy must not delete the other's journal
            clear_journal(self.root)
        self._lock, self.root, self.sample = lock, folder, False
        self._after_save()

    def _after_save(self) -> None:
        self._fingerprint = disk_fingerprint(self.root) if self.root else None
        self._kept_fingerprint = None
        self._saved_revision = self.history.revision
        if self.root is not None:
            clear_journal(self.root)
        self.stateChanged.emit()

    def disk_changed(self) -> bool:
        """The files differ from what was loaded or saved, and the user has not already said
        "keep my version" for exactly this state of the files."""
        if self.root is None or self._fingerprint is None:
            return False
        now = disk_fingerprint(self.root)
        return now != self._fingerprint and now != self._kept_fingerprint

    def keep_mine(self) -> None:
        """Remember the current state of the files as seen and refused, so it is not asked again."""
        self._kept_fingerprint = disk_fingerprint(self.root) if self.root is not None else None

    def reload(self) -> LoadResult | None:
        if self.root is None:
            return None
        folder, lock = self.root, self._lock
        result = load_project(folder)
        result.project.read_only = result.project.read_only or self.read_only
        self._install(result.project, folder, lock)
        return result

    def release(self) -> None:
        self._timer.stop()
        self._drc_timer.stop()
        self.wait_drc()
        for w in self._retired:  # the helper is dead; this ends at once unless the check runs here
            w.wait(RELEASE_WAIT_MS)
        _ABANDONED.extend(w for w in self._retired if w.isRunning())  # never destroy a live thread
        self._retired = []
        if self._lock:
            self._lock.release()
            self._lock = None

    # ---- autosave journal --------------------------------------------------------------------

    def _schedule_journal(self) -> None:
        if self.root is not None and not self.read_only:
            self._timer.start()

    def write_journal_now(self) -> None:
        if self.root is None or self.read_only or not self.dirty:
            return
        try:
            write_journal(self.project, self.root, base_fingerprint=self._fingerprint)
        except (HarnessError, ValueError) as exc:  # ValueError: text that cannot be encoded
            if not self.journal_error_shown:
                self.journal_error_shown = True
                why = str(exc) if isinstance(exc, HarnessError) else strings.SAVE_BAD_TEXT
                self.message.emit(strings.AUTOSAVE_FAILED.format(why), False)
                self.stateChanged.emit()  # the status line stops promising an autosave


def reason_of(exc: BaseException) -> str:
    """The first line of an error as a reason a person can read (never a traceback)."""
    lines = (_plain(exc) or type(exc).__name__).strip().splitlines()
    return lines[0] if lines else type(exc).__name__


def _plain(exc: BaseException) -> str:
    """One readable line from an exception (pydantic errors list field problems, no values)."""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        parts = [str(e.get("msg", "")).removeprefix("Value error, ") for e in errors()]
        return "; ".join(p for p in parts if p) or strings.INVALID_VALUE
    return str(exc)
