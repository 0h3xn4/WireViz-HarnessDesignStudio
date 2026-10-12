"""EditorController: the only object that changes the project. The GUI asks, it executes.

Every edit goes through `History.execute`, so it is a transaction (rolled back if it would leave the
project inconsistent), undoable, autosaved to the recovery journal, and reported to the views as a
small `Delta` so they redraw only what changed.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from pydantic import ValidationError
from PySide6.QtCore import QObject, QThread, QTimer, Signal

from harness_design_studio.core import checks, drc, edit
from harness_design_studio.core.commands import Delete, History, Op, Put, SetZones, apply_ops
from harness_design_studio.core.errors import HarnessError, TransactionError
from harness_design_studio.core.generate.engine import GenerationPlan, generation_status
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
    read_journal,
    write_journal,
)
from harness_design_studio.core.samples import mini3, new_project
from harness_design_studio.core.vcs.release import ReleasePlan

from . import strings
from .drc_process import run_check

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

    def run(self) -> None:
        self.found = run_check(self.snapshot)


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
        self.journal_error_shown = False
        self._findings_cache: tuple[object, list[checks.Finding]] | None = None
        self._open_cache: list[checks.Finding] | None = None
        self._counts_cache: tuple[object, tuple[int, int]] | None = None
        self._owners: dict[str, str] = {}
        self._installs = 0
        self.diff_marks: dict[str, str] = {}  # object ID -> added | changed | removed
        self.user_name = ""
        self.today: Callable[[], str] = lambda: date.today().isoformat()
        self._drc_raw: list[checks.Finding] = []
        self._drc_token: tuple[int, int] | None = None  # (installs, revision) the result is for
        self._drc_worker: DrcWorker | None = None
        self._drc_version = 0
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
            order = {"error": 0, "warning": 1, "info": 2}
            merged.sort(key=lambda f: (order[f.severity], f.id))
            self._findings_cache = (key, merged)
            self._open_cache = None
        return self._findings_cache[1]

    # ---- design rule check (background) --------------------------------------------------------

    @property
    def drc_current(self) -> bool:
        return self._drc_token == (self._installs, self.history.revision)

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
        worker, self._drc_worker = self._drc_worker, None
        if worker is None:
            return
        worker.wait()
        if worker.token[0] == self._installs:
            self._drc_raw, self._drc_token = worker.found, worker.token
            self._drc_version += 1
        if not self.drc_current:
            self._schedule_drc()
        self.drcChanged.emit()
        self.drcStateChanged.emit()

    def run_drc_now(self) -> None:
        """Synchronous check (tests, scripts); the editor itself uses the background worker."""
        self._drc_timer.stop()
        self.wait_drc()
        self._drc_raw = drc.run(self.project)
        self._drc_token = (self._installs, self.history.revision)
        self._drc_version += 1
        self.drcChanged.emit()
        self.drcStateChanged.emit()

    def wait_drc(self) -> None:
        if self._drc_worker is not None:
            self._drc_worker.wait()
            self._drc_worker = None

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
        owners = self._connector_owners()
        try:
            self.history.execute(label, ops)
        except TransactionError as exc:
            self.message.emit(f"{exc} {' '.join(exc.problems[:2])}".strip(), False)
            return False
        except HarnessError as exc:
            self.message.emit(str(exc), False)
            return False
        self._after_change(self.history.last_ops, owners)
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
            owners = self._connector_owners()
            label = self.history.undo()
            self._after_change(self.history.last_ops, owners)
            self.message.emit(f"Undone: {label}", False)

    def redo(self) -> None:
        if self.history.can_redo and not self.read_only:
            owners = self._connector_owners()
            label = self.history.redo()
            self._after_change(self.history.last_ops, owners)
            self.message.emit(f"Redone: {label}", False)

    def _connector_owners(self) -> dict[str, str]:
        """Unit of every box connector, captured before a change so deletions can be attributed."""
        return {c.id: c.unit_id for c in self.project.connectors.values() if c.unit_id}

    def _after_change(self, ops: list[Op], owners: dict[str, str] | None = None) -> None:
        self._owners = owners or {}
        delta = self._delta_of(ops)
        if self.selection and not self._selection_exists():
            self.selection = None
            self.selectionChanged.emit()
        self.changed.emit(delta)
        self.stateChanged.emit()
        self._schedule_journal()
        self._schedule_drc()

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
            return edit.Compat(False, "Pick a type", "Pick an interface type first.")
        return edit.unit_compat(self.project, self.connect_type, unit_id, src)

    def connector_compat(self, connector_id: str) -> edit.Compat:
        src = self.connect_from.unit_id if self.connect_from else None
        if self.connect_type is None:
            return edit.Compat(False, "Pick a type", "Pick an interface type first.")
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
        if self.tool != "connect":
            return ""
        if self.connect_type is None:
            return "Pick an interface type on the left."
        name = self.project.interface_types[self.connect_type].name
        thing = "connector" if self.mode == "expert" else "unit"
        if self.connect_from is None:
            return f"Click the first {thing} for {name}."
        others = [u for u in self.project.units if u != self.connect_from.unit_id]
        if not any(self.unit_has_valid_connector(u) for u in others):
            return f"No other unit has a free {name} connector. Pick another type, or add a unit that supports it."
        return f"Now click the second {thing}. Valid ones are highlighted."

    def pick(self, unit_id: str, connector_id: str | None = None) -> None:
        """Connect tool: first pick sets the source, second pick creates the interface."""
        if self.read_only or self.connect_type is None:
            return
        compat = (
            self.connector_compat(connector_id)
            if self.mode == "expert" and connector_id
            else self.unit_compat(unit_id)
        )
        if self.mode == "expert" and connector_id is None:
            self.message.emit("Click a connector (the small square) on the unit.", False)
            return
        if not compat.ok:
            self.message.emit(compat.why, False)
            return
        if self.connect_from is None:
            self.connect_from = ConnectFrom(unit_id, connector_id)
            self.connectChanged.emit()
            return
        src, type_id = self.connect_from, self.connect_type
        ops, iid = edit.ops_add_interface(
            self.project, type_id, src.unit_id, unit_id, src.connector_id, connector_id
        )
        auto = (
            " Connectors were chosen for you and are marked Auto until you confirm them."
            if self.mode == "guided"
            else ""
        )
        if self.run("Add interface", ops, message=f"Interface {iid} added.{auto}"):
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
        if self.run(f"Add {label}", ops):
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
                f"Delete {s.id}",
                lambda: edit.ops_delete_unit(self.project, s.id),
                message=f"Deleted {s.id}.",
            )
        return self.attempt(
            f"Delete {s.id}",
            lambda: edit.ops_delete_interface(self.project, s.id),
            message=f"Deleted {s.id}.",
        )

    def move_unit(self, unit_id: str, x: float, y: float) -> None:
        zone_before = self.project.units[unit_id].zone
        if self.attempt(f"Move {unit_id}", lambda: edit.ops_move_unit(self.project, unit_id, x, y)):
            zone = self.project.units[unit_id].zone
            if zone != zone_before:
                self.message.emit(f"{unit_id} is now in {zone}.", True)

    def redundant_copy(self, unit_id: str) -> None:
        try:
            result = edit.ops_redundant_copy(self.project, unit_id)
        except HarnessError as exc:
            self.message.emit(str(exc), False)
            return
        extra = (
            f" {len(result.skipped)} interface(s) could not be mirrored (no free connector): {', '.join(result.skipped)}."
            if result.skipped
            else ""
        )
        if self.run(
            f"Create redundant copy of {unit_id}",
            result.ops,
            message=f"Created {result.twin_id} and mirrored its interfaces (names end in -R).{extra}",
        ):
            self.select("unit", result.twin_id)

    def apply_fix(self, finding: checks.Finding) -> None:
        try:
            ops, msg = checks.fix_ops(self.project, finding)
        except HarnessError as exc:
            self.message.emit(str(exc), False)
            return
        self.run(f"Fix: {finding.title}", ops, message=msg)

    def waive(self, finding: checks.Finding, justification: str) -> bool:
        try:
            op = checks.waive_op(finding, justification)
        except Exception as exc:  # pydantic ValidationError for short text, EditError otherwise
            self.message.emit(_plain(exc), False)
            return False
        return self.run(
            f"Waive {finding.id}",
            [op],
            message="Waived. The justification will appear in the DRC report.",
        )

    def confirm_interface(self, interface_id: str) -> None:
        self.attempt(
            "Confirm connectors", lambda: edit.ops_confirm_interface(self.project, interface_id)
        )

    def rename_unit(self, old: str, new: str) -> bool:
        try:
            ops = edit.ops_rename_unit(self.project, old, new)
        except Exception as exc:
            self.message.emit(_plain(exc), False)
            return False
        was_selected = self.selection is not None and self.selection.id == old
        ok = self.run(f"Rename {old}", ops)
        if ok and was_selected:
            self.select("unit", new)
        return ok

    def update_unit(self, unit_id: str, **changes: object) -> bool:
        return self.attempt(
            f"Edit {unit_id}", lambda: edit.ops_update_unit(self.project, unit_id, **changes)
        )

    def update_interface(self, interface_id: str, **changes: object) -> bool:
        return self.attempt(
            f"Edit {interface_id}",
            lambda: edit.ops_update_interface(self.project, interface_id, **changes),
        )

    def set_endpoint_connector(self, interface_id: str, index: int, connector_id: str) -> bool:
        return self.attempt(
            "Choose connector",
            lambda: edit.ops_set_endpoint_connector(
                self.project, interface_id, index, connector_id
            ),
        )

    def set_connector_part(self, connector_id: str, part_id: str) -> bool:
        return self.attempt(
            "Change connector part",
            lambda: edit.ops_set_connector_part(self.project, connector_id, part_id),
        )

    def add_zone(self, name: str) -> bool:
        return self.attempt(
            "Add zone",
            lambda: edit.ops_add_zone(self.project, name),
            message=f"Zone {name.strip()} added.",
        )

    def add_interface_between(self, type_id: str, from_unit: str, to_unit: str) -> bool:
        try:
            ops, iid = edit.ops_add_interface(self.project, type_id, from_unit, to_unit)
        except HarnessError as exc:
            self.message.emit(str(exc), False)
            return False
        if self.run("Add interface", ops, message=f"Interface {iid} added."):
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

    def apply_generation(self, plan: GenerationPlan) -> bool:
        if plan.empty:
            if not self.project.interfaces:
                self.message.emit(strings.GEN_NO_INTERFACES, False)
                return True
            self.message.emit(strings.GEN_UP_TO_DATE, False)
            return True
        return self.run("Generate harnesses", plan.ops, message=plan.report.plain_summary())

    def apply_import(self, plan: ImportPlan) -> bool:
        n = plan.ok_count
        return self.run(
            f"Import {n} interfaces",
            plan.ops,
            message=f"Imported {n} interface{'s' if n != 1 else ''} in one step.",
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
        self.selection = None
        self.end_connect()
        self.journal_error_shown = False
        self.diff_marks = {}
        self.wait_drc()
        self._drc_raw, self._drc_token = [], None
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
            raise HarnessError("Choose an empty folder for the new project.")
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
        if not read_only:
            lock = ProjectLock(folder)
            lock.acquire()  # raises ProjectLockedError if open elsewhere
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

    def restore_journal(self) -> bool:
        if self.root is None:
            return False
        res = read_journal(self.root)
        if res is None or res.has_errors:
            return False
        keep_root, keep_lock = self.root, self._lock
        self._install(res.project, keep_root, keep_lock)
        self._saved_revision = -1  # restored state differs from disk: stays dirty
        self.stateChanged.emit()
        return True

    def discard_journal(self) -> None:
        if self.root is not None:
            clear_journal(self.root)

    def save(self) -> None:
        if self.root is None:
            raise NeedSaveAs("This project has no folder yet. Use Save As to choose one.")
        save_project(self.project, self.root, expected_fingerprint=self._fingerprint)
        self._after_save()

    def save_as(self, folder: Path) -> None:
        folder = Path(folder)
        if (folder / "project.json").exists():
            raise HarnessError("That folder already contains a project. Choose an empty folder.")
        if folder.exists() and any(folder.iterdir()):
            raise HarnessError("Choose an empty folder.")
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
        if self._lock:
            self._lock.release()
        if self.root is not None:
            clear_journal(self.root)
        self._lock, self.root, self.sample = lock, folder, False
        self._after_save()

    def _after_save(self) -> None:
        self._fingerprint = disk_fingerprint(self.root) if self.root else None
        self._saved_revision = self.history.revision
        if self.root is not None:
            clear_journal(self.root)
        self.stateChanged.emit()

    def disk_changed(self) -> bool:
        return (
            self.root is not None
            and self._fingerprint is not None
            and disk_fingerprint(self.root) != self._fingerprint
        )

    def reload(self) -> LoadResult | None:
        if self.root is None:
            return None
        folder, lock = self.root, self._lock
        result = load_project(folder)
        self._install(result.project, folder, lock)
        return result

    def release(self) -> None:
        self._timer.stop()
        self._drc_timer.stop()
        self.wait_drc()
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
            write_journal(self.project, self.root)
        except HarnessError as exc:
            if not self.journal_error_shown:
                self.journal_error_shown = True
                self.message.emit(f"Autosave is not working: {exc}", False)


def _plain(exc: Exception) -> str:
    """One readable line from an exception (pydantic errors list field problems, no values)."""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        parts = [str(e.get("msg", "")).removeprefix("Value error, ") for e in errors()]
        return "; ".join(p for p in parts if p) or "The value is not valid."
    return str(exc)
