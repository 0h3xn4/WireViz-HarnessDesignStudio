"""The migration safety net (plan 2.3, D-200): an upgrade of a project to a newer file format that
can be looked at first, is recorded, checks itself and undoes itself.

`migrate.py` holds the steps that change the raw files from one format to the next. This module is
what makes running them safe, and it knows nothing about any one step:

* `plan_upgrade` is the **dry run**: it loads the project, upgrades it in memory, writes nothing,
  and says which files would change, how many objects of each kind there are before and after, the
  model hash before and after, and anything it could not carry over.
* `upgrade_project` is the **upgrade**: it refuses when the plan says something would be lost,
  copies every original file to `.migration-backup-v<N>/`, writes the migration record
  (`MIGRATION.json` in that folder), writes the project, reloads it and **checks itself**: the same
  model hash, the same findings of `validate` and `check`, the baselines of released harnesses
  untouched, and a full in-memory export of the project as it was and as it is now, byte for byte.
  Any difference, and any error while writing: every file is put back from the backup and
  `UpgradeFailed` says so.

A migration generates nothing and invents no ID. It adds one entry to the change journal, "migrated
from format N", and only to a project that has a journal. The model hash does not depend on the
format number (`layout.schema_one`), so a faithful upgrade changes no hash, no stamp and no
baseline.

The record is outside the project hash and every written output: it lives in the backup folder,
which no loader, hash or output reads.
"""

import hashlib
import json
import os
import shutil
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness_design_studio import __version__
from harness_design_studio.core.errors import HarnessError, SaveError
from harness_design_studio.core.issues import Issue, errors
from harness_design_studio.core.model import Project

from . import canonical, migrate
from .fs import atomic_write_bytes, escapes_root, long_path
from .layout import model_hash, serialize
from .loader import (
    UNREAD_CODES,
    LoadResult,
    disk_fingerprint,
    load_project,
    read_tree,
)
from .saver import _managed_on_disk, _migration_backup, save_project

RECORD_NAME = "MIGRATION.json"
RECORD_VERSION = 1
BACKUP_PREFIX = ".migration-backup-v"
ROLLED_BACK_SUFFIX = ".rolled-back"
INTERRUPTED_SUFFIX = ".interrupted"

# What the counts say, in the words of the screen (the files say `units`).
KIND_NAMES = {
    "units": "devices",
    "interfaces": "interfaces",
    "connectors": "box connectors",
    "interface_types": "interface types",
    "parts": "library parts",
    "placements": "placements",
    "zones": "zones",
    "links": "connections",
    "changelog": "change log entries",
    "waivers": "waivers",
    "journal": "journal entries",
    "imports": "import records",
    "asbuilt": "as-built records",
    "marks": "diagram marks",
}
HARNESS_LISTS = (
    "connectors", "wires", "splices", "shields", "branch_points", "segments", "accessories",
)  # fmt: skip
# Kinds whose count may differ without anything being lost, and why.
DIAGRAM_MARKS = "diagram marks"  # the marks of a thing that is gone are left out when loading
CONFIG_FILES = "configuration files"  # one that is missing is written with the placeholder values
JOURNAL_ENTRIES = "journal entries"  # the migration adds one
# a file that is missing is written with the built-in values the project already uses
DEFAULTED = frozenset({CONFIG_FILES, "library manifest", "zones"})
# Findings that describe the files on disk and not the design: they are gone once the files have
# been written again by the tool (a file that was missing is written with the values in use), which
# is the point of the upgrade.
FORM_CODES = frozenset({"migrated", "not_canonical", "file_name_mismatch", "config_defaulted"})
EXPORT_LIMIT = 5  # how many differing files an explanation names


class UpgradeError(HarnessError):
    """The project was not upgraded and nothing was written (it is damaged, would lose something,
    is read-only, or an earlier upgrade left its backup in the way)."""

    def __init__(self, message: str, reasons: list[str] | None = None) -> None:
        super().__init__(message)
        self.reasons = reasons or []


class UpgradeFailed(UpgradeError):
    """Something went wrong while the project was being written or when it was checked afterwards.
    `rolled_back` says whether every file was put back from the backup."""

    def __init__(
        self, message: str, reasons: list[str], *, rolled_back: bool, backup: str | None = None
    ) -> None:
        super().__init__(message, reasons)
        self.rolled_back = rolled_back
        self.backup = backup


# ---- counting ------------------------------------------------------------------------------------


def count_raw(files: Mapping[str, Any]) -> dict[str, int]:
    """How many objects of each kind a tree of parsed project files holds. It reads the files and
    not the model, so the same function counts the project as it was saved and the project as the
    tool would write it, whatever format either is in. Kinds with no object are left out."""
    counts: Counter[str] = Counter()
    for rel, data in files.items():
        if rel == "project.json" or not isinstance(data, dict):
            continue
        if rel.startswith("physical/harnesses/"):
            counts["harnesses"] += 1
            for key in HARNESS_LISTS:
                if isinstance(data.get(key), list):
                    counts[f"harness {key.replace('_', ' ')}"] += len(data[key])
        elif rel.startswith("baselines/"):
            counts["baselines"] += 1
        elif rel.startswith("config/"):
            counts[CONFIG_FILES] += 1
        elif rel == "generated/generation.json":
            counts["generation record"] += 1
        elif rel == "library/manifest.json":
            counts["library manifest"] += 1
        else:
            for key, value in data.items():
                if isinstance(value, list):
                    counts[KIND_NAMES.get(str(key), str(key))] += len(value)
    return {k: v for k, v in sorted(counts.items()) if v}


def parsed_files(files: Mapping[str, bytes]) -> dict[str, Any]:
    """The bytes of a serialised project parsed again (what `read_tree` makes of a folder)."""
    return {rel: json.loads(data) for rel, data in files.items()}


def format_of(folder: Path | str) -> int | None:
    """The format number a project folder says it is in, read from `project.json` alone and without
    loading anything; None when that file is missing or cannot be read."""
    path = long_path(Path(folder)) / "project.json"
    try:
        if path.is_symlink() or not path.is_file():
            return None
        doc = canonical.loads_strict(path.read_bytes())
    except OSError, ValueError, RecursionError:
        return None
    return migrate.schema_version_of({"project.json": doc})


# ---- reading the disk ----------------------------------------------------------------------------


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _managed_files(base: Path) -> list[str]:
    return sorted(set(_managed_on_disk(base)))


def disk_hashes(base: Path) -> dict[str, str]:
    """SHA-256 of every project file the tool manages that is a real file (a link is not read:
    the loader does not read it either)."""
    found = {}
    for rel in _managed_files(base):
        path = base / rel
        if path.is_symlink() or escapes_root(base, path):
            continue
        found[rel] = _sha(path.read_bytes())
    return found


def _linked_files(base: Path) -> list[str]:
    return [
        rel
        for rel in _managed_files(base)
        if (base / rel).is_symlink() or escapes_root(base, base / rel)
    ]


def _backup_dir(base: Path, version: int) -> Path:
    return base / f"{BACKUP_PREFIX}{version}"


def read_record(backup: Path) -> dict[str, Any] | None:
    """The migration record of a backup folder; None when there is none or it cannot be read."""
    try:
        doc = json.loads((backup / RECORD_NAME).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def _write_record(backup: Path, record: dict[str, Any]) -> None:
    atomic_write_bytes(backup / RECORD_NAME, canonical.dumps(record), backup=False)


# ---- what the checks compare ---------------------------------------------------------------------


def export_digests(project: Project) -> dict[str, str]:
    """SHA-256 of every file a full export of the project writes (all drawings included), made in
    memory; the bytes themselves are not kept. An export that cannot be made is a result too: it is
    the same for two projects only if it fails the same way."""
    from harness_design_studio.core.outputs.build import build_outputs

    try:
        files = build_outputs(project).files
    except Exception as exc:  # noqa: BLE001 - the kind of failure is the result
        return {"": f"export failed: {type(exc).__name__}"}
    return {rel: _sha(data) for rel, data in sorted(files.items())}


def _digest_differences(old: Mapping[str, str], new: Mapping[str, str]) -> list[str]:
    names = sorted(r for r in set(old) | set(new) if old.get(r) != new.get(r))
    return [
        f"{r or 'export'}: " + ("missing" if r not in new else "new" if r not in old else "differs")
        for r in names
    ]


def project_findings(
    result: LoadResult, extra: list[Issue]
) -> list[tuple[str, str, str, str, str]]:
    """What `validate` and `check` report for a loaded project, as sortable tuples, without the
    findings that describe the form of the files on disk (`FORM_CODES`)."""
    return sorted(
        (i.severity, i.code, i.message, i.location or "", i.object_id or "")
        for i in [*result.issues, *extra]
        if i.code not in FORM_CODES
    )


def _folder_findings(root: Path) -> list[tuple[str, str, str, str, str]]:
    from harness_design_studio.core.validation import validate_folder

    result, extra = validate_folder(root, merge_check=True)
    return project_findings(result, extra)


def compare_projects(old: Project, new: Project) -> dict[str, str]:
    """What differs between a project and the same project after an upgrade, on the points that
    must not differ, each as a short key and a sentence: the model hash (`hash`), the content hash
    that the baselines of released harnesses use (`content`), the baselines themselves
    (`baselines`) and the consistency of the released harnesses with them (`released`). Empty when
    nothing differs."""
    from harness_design_studio.core.vcs.consistency import release_integrity
    from harness_design_studio.core.vcs.hashing import content_hash

    found = {}
    if model_hash(old) != model_hash(new):
        found["hash"] = "The model hash differs."
    if content_hash(old) != content_hash(new):
        found["content"] = "The content hash of the released harnesses differs."
    if old.baselines != new.baselines:
        found["baselines"] = "A baseline of a released harness differs."
    if release_integrity(old) != release_integrity(new):
        found["released"] = "A released harness no longer matches its baseline as it did."
    return found


def _baseline_files(files: Mapping[str, Any]) -> dict[str, Any]:
    return {rel: data for rel, data in files.items() if rel.startswith("baselines/")}


# ---- the dry run ---------------------------------------------------------------------------------


@dataclass
class UpgradePlan:
    """What an upgrade would do, found out without writing anything (`plan_upgrade`)."""

    from_version: int
    to_version: int
    files: dict[str, str] = field(default_factory=dict)  # file -> "changed", "new" or "removed"
    counts_before: dict[str, int] = field(default_factory=dict)
    counts_after: dict[str, int] = field(default_factory=dict)
    hash_before: str | None = None  # None: the old format cannot be read as it is
    hash_after: str = ""
    hash_equal: bool | None = None
    exports_equal: bool | None = None  # None: not compared (the old format cannot be read as it is)
    baselines_intact: bool | None = None
    journal_entry: bool = False  # the project keeps a journal, so the upgrade adds an entry
    lost: list[str] = field(default_factory=list)  # anything the upgrade could not carry over
    notes: list[str] = field(default_factory=list)
    # kept for `upgrade_project`; not part of what is reported
    project: Project | None = field(default=None, repr=False)
    reference: Project | None = field(default=None, repr=False)
    reference_exports: dict[str, str] = field(default_factory=dict, repr=False)
    raw_baselines: dict[str, Any] = field(default_factory=dict, repr=False)
    fingerprint: str = field(default="", repr=False)

    @property
    def ok(self) -> bool:
        """Nothing is lost, nothing was made up, and everything that is compared is equal."""
        return not self.lost

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "files": [{"file": f, "change": c} for f, c in sorted(self.files.items())],
            "counts_before": self.counts_before,
            "counts_after": self.counts_after,
            "model_hash_before": self.hash_before,
            "model_hash_after": self.hash_after or None,
            "hash_equal": self.hash_equal,
            "exports_equal": self.exports_equal,
            "baselines_intact": self.baselines_intact,
            "journal_entry": self.journal_entry,
            "lost": self.lost,
            "notes": self.notes,
        }


def _count_differences(
    before: dict[str, int], after: dict[str, int], journal: bool
) -> tuple[list[str], list[str]]:
    """(lost or made up, notes) between the counts of the files as they were and will be."""
    lost: list[str] = []
    notes: list[str] = []
    for kind in sorted(set(before) | set(after)):
        a, b = before.get(kind, 0), after.get(kind, 0)
        if kind == JOURNAL_ENTRIES and journal:
            a += 1  # the entry the upgrade adds
        if a == b:
            continue
        if kind == DIAGRAM_MARKS and b < a:
            notes.append(f"{a - b} diagram mark(s) of things that no longer exist are left out.")
        elif kind in DEFAULTED and b > a and (kind == CONFIG_FILES or a == 0):
            notes.append(
                f"{kind}: {b - a} missing, written with the built-in values "
                "(the project was already using them)."
            )
        elif b < a:
            lost.append(f"{a - b} of {a} {kind} would not be carried over.")
        else:
            lost.append(f"{b - a} {kind} would be made up (an upgrade generates nothing).")
    return lost, notes


def _journal_ahead(project: Project, from_version: int, to_version: int) -> bool:
    """Add the entry "migrated from format N" to the journal of the project in memory; False when
    the project has no journal (it is not given one)."""
    if project.journal is None:
        return False
    from harness_design_studio.core import journal as journal_module

    project.journal = journal_module.extended(
        project.journal, journal_module.migration_rows(from_version, to_version)
    )
    return True


def _usable(result: LoadResult) -> bool:
    return not result.has_errors and not result.project.recovered and not result.project.read_only


def plan_upgrade(root: Path | str, *, exports: bool = True) -> UpgradePlan | None:
    """The dry run: what upgrading the project in `root` to the format of this tool would do,
    found out without writing a byte. None when the project is in the current format. Raises
    `UpgradeError` when it cannot be upgraded at all (saved by a newer tool). A project that would
    lose something is returned with `lost` filled in; `exports=False` skips the in-memory export of
    the old and the upgraded project (the slowest step)."""
    root = Path(root)
    base = long_path(root)
    fingerprint = disk_fingerprint(root)
    files, broken, tree_issues = read_tree(root)
    from_version = migrate.schema_version_of(files)
    to_version = migrate.current_version()
    if from_version > to_version:
        raise UpgradeError(
            f"This project is in format {from_version}, newer than this tool understands "
            f"(format {to_version}); it can only be opened read-only."
        )
    if from_version == to_version:
        return None
    plan = UpgradePlan(from_version, to_version, fingerprint=fingerprint)
    plan.counts_before = count_raw(files)
    plan.raw_baselines = _baseline_files(files)
    loaded = load_project(root)
    problems = [i.render() for i in errors(loaded.issues)]
    if loaded.project.recovered and not problems:
        problems = ["parts of the project could not be loaded"]
    if problems:
        plan.lost = [
            f"The project has damaged files, so nothing can be carried over safely: {p}"
            for p in problems[:EXPORT_LIMIT]
        ]
        return plan
    unread = [i for i in loaded.issues if i.code in UNREAD_CODES]
    plan.lost += [f"{i.location}: {i.message}" for i in unread]
    plan.lost += [
        f"{rel}: a link to another file; it is not read, so it cannot be carried over."
        for rel in _linked_files(base)
        if not any(i.location == rel for i in unread)
    ]
    project = loaded.project
    plan.project = project
    plan.journal_entry = _journal_ahead(project, from_version, to_version)
    would_write = serialize(project, tool_version=__version__)
    plan.counts_after = count_raw(parsed_files(would_write))
    lost, plan.notes = _count_differences(plan.counts_before, plan.counts_after, plan.journal_entry)
    plan.lost += lost
    plan.files = _files_that_change(base, project, would_write)
    # the project as it was saved, read without the steps; only a reading that is clean counts
    as_saved = load_project(root, migrate=False)
    plan.reference = as_saved.project if _usable(as_saved) else project
    if plan.reference is project:
        plan.notes.append(
            f"Format {from_version} cannot be read as it is by this version, so the project is "
            "compared with its own upgrade after the write, not with the old reading."
        )
    else:
        plan.hash_before = model_hash(plan.reference)
    plan.hash_after = model_hash(project)
    plan.hash_equal = None if plan.hash_before is None else plan.hash_before == plan.hash_after
    if plan.hash_equal is False:
        plan.lost.append("The model hash would change: the upgrade changes the design.")
    differences = compare_projects(plan.reference, project)
    differences.pop("hash", None)  # said above
    plan.baselines_intact = None if plan.hash_before is None else not differences
    plan.lost += list(differences.values()) if plan.hash_before is not None else []
    plan.reference_exports = export_digests(plan.reference) if exports else {}
    if exports and plan.hash_before is not None:
        wrong = _digest_differences(plan.reference_exports, export_digests(project))
        plan.exports_equal = not wrong
        if wrong:
            plan.lost.append(f"A full export would differ ({'; '.join(wrong[:EXPORT_LIMIT])}).")
    return plan


def _files_that_change(base: Path, project: Project, files: Mapping[str, bytes]) -> dict[str, str]:
    """The files a save of `project` writes or removes, worked out as `save_project` does."""
    found: dict[str, str] = {}
    for rel, data in files.items():
        path = base / rel
        if path.is_file() and not path.is_symlink():
            if path.read_bytes() != data:
                found[rel] = "changed"
        else:
            found[rel] = "new"
    for rel in set(_managed_on_disk(base)) - set(files):
        if not (project.quarantine_files and rel in project.quarantine_files):
            found[rel] = "removed"
    if not (base / ".gitignore").exists():
        found[".gitignore"] = "new"
    return found


def render_plan(plan: UpgradePlan) -> list[str]:
    """The dry run as text lines (the command line prints them)."""
    lines = [f"Project format {plan.from_version}; this tool writes format {plan.to_version}."]
    lines.append(f"Files that would change ({len(plan.files)}):")
    lines += [f"  {change:8} {rel}" for rel, change in sorted(plan.files.items())]
    lines.append("Objects by kind, before and after:")
    for kind in sorted(set(plan.counts_before) | set(plan.counts_after)):
        a, b = plan.counts_before.get(kind, 0), plan.counts_after.get(kind, 0)
        lines.append(f"  {kind}: {a} -> {b}")
    if plan.hash_before is None:
        lines.append(f"Model hash: not comparable before; after {plan.hash_after[:12]}.")
    else:
        verdict = "equal" if plan.hash_equal else "NOT EQUAL"
        lines.append(f"Model hash: {plan.hash_before[:12]} -> {plan.hash_after[:12]} ({verdict}).")
    if plan.exports_equal is not None:
        same = "identical" if plan.exports_equal else "DIFFERENT"
        lines.append(f"A full export before and after: {same}.")
    if plan.journal_entry:
        lines.append(f'The journal gets one entry: "migrated from format {plan.from_version}".')
    lines += [f"Note: {n}" for n in plan.notes]
    if plan.lost:
        lines.append("Could not be carried over:")
        lines += [f"  {x}" for x in plan.lost]
        lines.append("Nothing was written, and the upgrade is refused while this stands.")
    else:
        lines.append("Nothing is lost. Nothing was written.")
    return lines


# ---- the upgrade ---------------------------------------------------------------------------------


@dataclass
class UpgradeResult:
    from_version: int
    to_version: int
    backup: str  # the folder name, inside the project
    record: str  # the record, relative to the project
    written: list[str]
    plan: UpgradePlan
    self_check: dict[str, bool | None]


def _record(
    plan: UpgradePlan,
    status: str,
    before: Mapping[str, str],
    after: Mapping[str, str] | None,
    gitignore_existed: bool,
    check: Mapping[str, bool | None] | None,
) -> dict[str, Any]:
    return {
        "record_version": RECORD_VERSION,
        "status": status,
        "from_version": plan.from_version,
        "to_version": plan.to_version,
        "tool_version": __version__,
        "model_hash": {"before": plan.hash_before, "after": plan.hash_after},
        "counts": {"before": plan.counts_before, "after": plan.counts_after},
        "files": {"before": dict(before), "after": dict(after) if after is not None else None},
        "journal_entry": plan.journal_entry,
        "gitignore_existed": gitignore_existed,
        "self_check": dict(check) if check is not None else None,
    }


def _make_backup(base: Path, plan: UpgradePlan) -> tuple[Path, dict[str, str]]:
    """The backup of the original files, checked file by file against the project; the SHA-256 of
    every file in it. Nothing of the project has been changed when this raises."""
    folder = _backup_dir(base, plan.from_version)
    if os.path.lexists(folder) and (read_record(folder) or {}).get("status") == "complete":
        raise UpgradeError(
            f"'{folder.name}' holds the record of an earlier upgrade. Rename or remove that "
            "folder and try again; nothing was changed."
        )
    try:
        backup = _migration_backup(base, plan.from_version)
    except SaveError as exc:
        raise UpgradeError(str(exc)) from exc
    held = {}
    for rel in _managed_files(base):
        path = base / rel
        if path.is_symlink() or escapes_root(base, path):
            continue
        try:
            held[rel] = _sha((backup / rel).read_bytes())
        except OSError as exc:
            raise UpgradeError(
                f"The backup is missing '{rel}' ({exc.strerror}); nothing was changed."
            ) from exc
        if held[rel] != _sha(path.read_bytes()):
            raise UpgradeError(
                f"The backup of '{rel}' is not the file now on disk. Rename or remove the folder "
                f"'{backup.name}' and try again; nothing was changed."
            )
    return backup, held


def _restore(
    base: Path, backup: Path, before: Mapping[str, str], gitignore_existed: bool
) -> list[str]:
    """Put every original file back from the backup, take away what the upgrade made, and check by
    hash that the project is as it was. The problems that remain, if any."""
    problems: list[str] = []
    for rel in sorted(before):
        try:
            data = (backup / rel).read_bytes()
            path = base / rel
            if not (path.is_file() and not path.is_symlink() and path.read_bytes() == data):
                atomic_write_bytes(path, data, backup=False, root=base)
        except (OSError, SaveError) as exc:
            problems.append(f"'{rel}' could not be put back ({exc}).")
    for rel in sorted(set(_managed_files(base)) - set(before)):
        if (base / rel).is_symlink():
            continue  # not ours
        try:
            (base / rel).unlink()  # made by the upgrade
        except OSError as exc:
            problems.append(f"'{rel}' could not be removed ({exc.strerror}).")
    if not gitignore_existed:
        (base / ".gitignore").unlink(missing_ok=True)
    now = disk_hashes(base)
    problems += [
        f"'{rel}' is not as it was."
        for rel in sorted(set(before) | set(now))
        if before.get(rel) != now.get(rel)
    ]
    return problems


def recover_interrupted(root: Path | str) -> str | None:
    """An upgrade that was killed while it wrote leaves its backup with the record `started`, and
    a project of mixed files. Put the originals back; returns the name of the backup folder used,
    or None when there is nothing to recover. Called by `upgrade_project` before anything else."""
    base = long_path(Path(root))
    for backup in sorted(base.glob(f"{BACKUP_PREFIX}*")):
        record = read_record(backup) if backup.is_dir() and not backup.is_symlink() else None
        if record is None or record.get("status") != "started":
            continue
        before = record.get("files", {}).get("before", {})
        problems = _restore(base, backup, before, bool(record.get("gitignore_existed", True)))
        if problems:
            raise UpgradeError(
                f"An earlier upgrade was interrupted and its backup '{backup.name}' could not be "
                "put back completely.",
                problems,
            )
        _park(backup, record, "interrupted", INTERRUPTED_SUFFIX)
        return backup.name
    return None


def _park(backup: Path, record: dict[str, Any], status: str, suffix: str) -> None:
    """Mark the backup of an upgrade that did not finish and has been put back, and rename it so
    that a new upgrade starts clean while the record of what happened stays."""
    parked = backup.with_name(backup.name + suffix)
    try:
        _write_record(backup, {**record, "status": status})
        if parked.exists():
            shutil.rmtree(parked, ignore_errors=True)
        os.replace(backup, parked)
    except OSError, SaveError:
        pass  # the project is already as it was; the backup keeps its name and is reused


def self_check(
    root: Path,
    plan: UpgradePlan,
    findings_before: list[tuple[str, str, str, str, str]],
) -> tuple[dict[str, bool | None], list[str]]:
    """The check after the write: reload the folder and compare it with the project as it was.
    Returns the result of each check and the problems found."""
    base = long_path(root)
    check: dict[str, bool | None] = {}
    problems: list[str] = []
    reloaded = load_project(root)
    clean = _usable(reloaded) and reloaded.project.migrated_from is None
    check["reload"] = clean
    if not clean:
        first = "; ".join(i.render() for i in errors(reloaded.issues)[:3])
        problems.append(f"The upgraded folder does not load cleanly: {first}")
        return check, problems
    new, old = reloaded.project, plan.reference
    if old is None:
        raise UpgradeError("There is no project to compare with.")
    new_hash = model_hash(new)
    check["model_hash"] = new_hash == plan.hash_after and (plan.hash_before in (None, new_hash))
    if not check["model_hash"]:
        problems.append("The model hash of the upgraded project is not the one it had before.")
    check["findings"] = _folder_findings(root) == findings_before
    if not check["findings"]:
        problems.append("`validate` and `check` do not give the same findings as before.")
    differences = compare_projects(old, new)
    differences.pop("hash", None)  # said above
    check["baselines"] = not differences
    problems += list(differences.values())
    on_disk = {rel: canonical.loads_strict(data) for rel, data in _read_baselines(base).items()}
    if on_disk != plan.raw_baselines:
        check["baselines"] = False
        problems.append("A baseline file is not the same as before the upgrade.")
    wrong = _digest_differences(plan.reference_exports, export_digests(new))
    check["exports"] = not wrong
    if wrong:
        first = "; ".join(wrong[:EXPORT_LIMIT])
        problems.append(f"A full export of the project differs from the one before ({first}).")
    return check, problems


def _read_baselines(base: Path) -> dict[str, bytes]:
    return {
        rel: (base / rel).read_bytes()
        for rel in _managed_files(base)
        if rel.startswith("baselines/") and not (base / rel).is_symlink()
    }


def upgrade_project(
    root: Path | str, *, on_written: Callable[[], None] | None = None
) -> UpgradeResult | None:
    """Upgrade the project in `root` to the format of this tool, safely (see the module text).
    None when it is in the current format. Raises `UpgradeError` when it was refused and nothing
    was written, `UpgradeFailed` when it was written, found wrong and put back. The caller holds
    the project lock. `on_written` is called once the files are written, before the check (a test
    uses it to simulate a failure there)."""
    root = Path(root)
    base = long_path(root)
    recover_interrupted(root)
    plan = plan_upgrade(root)
    if plan is None:
        return None
    if plan.lost or plan.project is None or plan.reference is None:
        why = plan.lost[0] if plan.lost else "it cannot be read."
        raise UpgradeError(
            f"The project was not upgraded and nothing was changed: {why}", plan.lost
        )
    findings_before = _folder_findings(root)
    gitignore_existed = (base / ".gitignore").exists()
    backup, before = _make_backup(base, plan)
    record = f"{backup.name}/{RECORD_NAME}"
    _write_record(backup, _record(plan, "started", before, None, gitignore_existed, None))
    written: list[str] = []
    try:
        saved = save_project(plan.project, root, expected_fingerprint=plan.fingerprint)
        written = saved.written
        if on_written is not None:
            on_written()
        check, problems = self_check(root, plan, findings_before)
    except BaseException as exc:
        left = _restore(base, backup, before, gitignore_existed)
        _put_back(backup, plan, before, gitignore_existed, [str(exc), *left], bool(left))
        if not isinstance(exc, Exception):
            raise  # an interrupt: the project is put back, then the interrupt goes on
        raise UpgradeFailed(
            _failed_text(left, f"it could not be written: {exc}"),
            [str(exc), *left],
            rolled_back=not left,
            backup=backup.name + ROLLED_BACK_SUFFIX,
        ) from exc
    if problems:
        left = _restore(base, backup, before, gitignore_existed)
        _put_back(backup, plan, before, gitignore_existed, [*problems, *left], bool(left))
        raise UpgradeFailed(
            _failed_text(left, "the check after the write found a difference"),
            [*problems, *left],
            rolled_back=not left,
            backup=backup.name + ROLLED_BACK_SUFFIX,
        )
    after = disk_hashes(base)
    _write_record(backup, _record(plan, "complete", before, after, gitignore_existed, check))
    return UpgradeResult(
        plan.from_version, plan.to_version, backup.name, record, written, plan, check
    )


def _failed_text(left: list[str], what: str) -> str:
    if left:
        return (
            f"The upgrade failed ({what}) and the original files could NOT all be put back. "
            "They are in the .migration-backup-v* folder of the project: copy them over the "
            "project files by hand."
        )
    return (
        f"The upgrade failed ({what}). Every file was put back from the backup; the project is "
        "as it was."
    )


def _put_back(
    backup: Path,
    plan: UpgradePlan,
    before: Mapping[str, str],
    gitignore_existed: bool,
    problems: list[str],
    incomplete: bool,
) -> None:
    """Record why an upgrade was undone and, when every file is back, park its backup under a name
    of its own. When some file could not be put back the backup stays as it is, with the record
    `started`, so that the next run tries again."""
    if incomplete:
        return
    record = _record(plan, "rolled_back", before, None, gitignore_existed, None)
    record["problems"] = problems
    _park(backup, record, "rolled_back", ROLLED_BACK_SUFFIX)
