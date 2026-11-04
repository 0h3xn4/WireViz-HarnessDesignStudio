"""Comments in the config files: `settings --annotate` and `--no-annotate` (D-191 (2), R3).

A person who opens `config/derating.json` in an editor can see, next to each value, its unit, its
valid range, where the number comes from and what uses it: the reserved top-level key `_about` of
the file holds one entry for each setting of the file, made from the registry (`core.settings`).
It is opt-in. A project that has none is written byte for byte as before. When it is there, it is
never a setting, it is left out of the model hash and of every number and written output
(`core.io.layout.bytes_for_hash`), and a stale entry (the registry says something else now) is a
warning of `validate` and `config` that names the file and the key
(`configcheck.annotation_issues`).
Annotating changes no value: only files that exist are written, and no file is created.
"""

from dataclasses import dataclass
from typing import Any

from . import settings
from .commands import History, Op, SetConfig
from .model import Project
from .model.base import evolve


@dataclass(frozen=True)
class AnnotationResult:
    """What `annotate` did: `action` is "annotate" or "remove"; `files` are the config files that
    were rewritten and `unchanged` those that already were as wanted, both by file name (for
    example "derating"), sorted."""

    action: str
    files: tuple[str, ...]
    unchanged: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return bool(self.files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "files": [f"config/{n}.json" for n in self.files],
            "unchanged": [f"config/{n}.json" for n in self.unchanged],
            "changed": self.changed,
        }


def annotate(project: Project, *, remove: bool = False) -> AnnotationResult:
    """Write (or refresh) `_about` in every existing config file of `project`, or with `remove`
    take it out. Changes the project in memory (one undo step); the caller saves it."""
    ops: list[Op] = []
    files: list[str] = []
    unchanged: list[str] = []
    for name in sorted(project.config):
        cfg = project.config[name]
        wanted = {} if remove else settings.about_for(name)
        if cfg.about == wanted:
            unchanged.append(name)
            continue
        ops.append(SetConfig(evolve(cfg, about=wanted)))
        files.append(name)
    if ops:
        label = "Remove" if remove else "Write"
        History(project).execute(f"{label} the comments in the config files", ops)
    return AnnotationResult("remove" if remove else "annotate", tuple(files), tuple(unchanged))
