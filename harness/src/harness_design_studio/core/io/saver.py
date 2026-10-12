"""Save a project folder. Writes only changed files, atomically, keeping a `.bak` of each."""

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from harness_design_studio import __version__
from harness_design_studio.core.errors import LoadError, SaveError
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.issues import errors
from harness_design_studio.core.model import SCHEMA_VERSION, Project, evolve

from . import canonical
from .fs import atomic_write_bytes, escapes_root, long_path
from .layout import MANAGED_DIRS, is_managed, serialize
from .loader import LoadResult, disk_fingerprint, load_project

GITIGNORE = (
    b"*.bak\n.harness.lock\n.harness.lock.takeover\n.*.tmp\n"
    b".harness-recovery/\n.migration-backup-v*/\n"
)


@dataclass
class SaveResult:
    written: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    backup_dir: str | None = None


def _quarantine_payload(project: Project) -> dict[str, object]:
    return {
        "items": [
            {"file": q.file, "kind": q.kind, "reason": q.reason, "raw": q.raw}
            for q in project.quarantine
        ]
    }


def save_project(
    project: Project,
    root: Path | str,
    *,
    expected_fingerprint: str | None = None,
    allow_inconsistent: bool = False,
) -> SaveResult:
    """Write the project. Raises `SaveError` on any problem; written files are always whole."""
    root = Path(root)
    base = long_path(root)
    exists = (base / "project.json").is_file()
    if project.read_only:
        raise SaveError("This project was saved by a newer version of the tool and is read-only.")
    if project.recovered and exists:
        raise SaveError(
            "Parts of this project could not be loaded, so saving over the original folder is "
            "blocked to protect the original files. Save it to a new folder instead."
        )
    for top in MANAGED_DIRS:
        folder = base / top
        if folder.exists() and (folder.is_symlink() or escapes_root(base, folder)):
            raise SaveError(
                f"The folder '{top}' is a link that leads outside the project, "
                "so nothing was saved. Replace it with a real folder."
            )
    problems = errors(check_integrity(project))
    if problems and not allow_inconsistent:
        raise SaveError(
            f"The project has {len(problems)} consistency error(s) (first: {problems[0].message}) "
            "and was not saved. Fix them, or save a recovery copy."
        )
    if (
        expected_fingerprint is not None
        and exists
        and disk_fingerprint(root) != expected_fingerprint
    ):
        raise SaveError(
            "The project files changed on disk since you opened them (for example after a Git "
            "pull). Reload the project, or save to a different folder."
        )

    result = SaveResult()
    files = serialize(project, tool_version=__version__)
    if exists and project.migrated_from is not None:
        backup = base / f".migration-backup-v{project.migrated_from}"
        if not backup.exists():
            for rel in sorted(r for r in _managed_on_disk(base)):
                dest = backup / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(base / rel, dest)
        result.backup_dir = backup.name

    # The record of what was generated and the project file go last: if a write fails half-way,
    # the record still describes the older harnesses instead of claiming newer ones.
    last = ("generated/generation.json", "project.json")
    for rel, data in sorted(
        files.items(), key=lambda kv: (kv[0] in last, kv[0] == "project.json", kv[0])
    ):
        path = base / rel
        if path.is_file() and path.read_bytes() == data:
            continue
        atomic_write_bytes(path, data, root=base)
        result.written.append(rel)
    if project.recovered:
        atomic_write_bytes(
            base / "quarantine.json", canonical.dumps(_quarantine_payload(project)), root=base
        )
        for rel, raw in project.quarantine_files.items():
            atomic_write_bytes(base / "quarantine" / "files" / rel, raw, backup=False, root=base)
    for rel in sorted(set(_managed_on_disk(base)) - set(files)):
        if project.quarantine_files and rel in project.quarantine_files:
            continue
        stale = base / rel
        if escapes_root(base, stale.parent):
            raise SaveError(f"'{rel}' lies behind a link that leads outside the project.")
        stale.replace(stale.with_name(stale.name + ".bak"))  # removed objects stay recoverable
        result.removed.append(rel)
    gitignore = base / ".gitignore"
    if not gitignore.exists():
        atomic_write_bytes(gitignore, GITIGNORE, backup=False, root=base)
    project.meta = evolve(project.meta, tool_version=__version__, schema_version=SCHEMA_VERSION)
    project.migrated_from = None
    return result


def _managed_on_disk(base: Path) -> list[str]:
    found = []
    for top_file in ("project.json", "waivers.json", "changelog.json"):
        if (base / top_file).is_file():
            found.append(top_file)
    for top in MANAGED_DIRS:
        folder = base / top
        if folder.is_dir():
            found += [
                rel
                for p in folder.rglob("*.json")
                if is_managed(rel := p.relative_to(base).as_posix())
            ]
    return found


def migrate_project(root: Path | str) -> LoadResult | None:
    """Upgrade an old-format project in place, keeping the original files in a backup folder.

    Returns None if the project is already current.
    """
    result = load_project(root)
    if result.project.migrated_from is None:
        return None
    if result.has_errors:
        raise LoadError(
            "The project has errors and was not migrated. Run `harness validate` first."
        )
    save_project(result.project, root)
    return result
