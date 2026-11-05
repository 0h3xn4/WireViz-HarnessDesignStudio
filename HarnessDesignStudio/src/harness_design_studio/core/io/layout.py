"""Mapping between the in-memory project and its folder of small JSON files.

One file per subsystem keeps Git merges clean; one file per harness likewise. File names only
*group* data: loading never depends on them, so renaming a subsystem never loses anything.
"""

import hashlib
import json
import re
from collections.abc import Callable, Hashable, Sequence
from typing import Any

from harness_design_studio.core.model import (
    CONFIG_NAMES,
    PART_CATEGORIES,
    Harness,
    Project,
    ProjectMeta,
)
from harness_design_studio.core.model.base import Entity
from harness_design_studio.core.model.config import ABOUT_KEY
from harness_design_studio.core.model.journal import Journal

from . import canonical
from .fs import slug

MANAGED_RE = re.compile(
    r"^(project\.json|waivers\.json|journal\.json|logical/layout\.json|generated/generation\.json|config/[^/]+\.json|library/[^/]+\.json|logical/interface_types\.json"
    r"|logical/links\.json|logical/(units|interfaces)/[^/]+\.json|physical/(connectors|harnesses)/[^/]+\.json|changelog\.json|baselines/[^/]+/[^/]+\.json"
    r"|imports/records\.json|asbuilt/records\.json|diagram/marks\.json)$"
)
JOURNAL_FILE = "journal.json"
MANAGED_DIRS = (
    "config", "library", "logical", "physical", "generated", "baselines", "imports", "asbuilt",
    "diagram",
)  # fmt: skip
IMPORT_RECORDS_FILE = "imports/records.json"  # optional; not part of the model hash
ASBUILT_FILE = "asbuilt/records.json"  # optional (S9); not part of the model hash
# optional; what was moved in the diagram; not in the hash. The file keeps schema version 1 and has
# no version of its own: a label on a line (`interface:`, `link:`, `end:`) is `{"id", "t"}`, its
# place along the line (`core.linepos`); a bend or a route (`bend:`, `route:`) is `{"id", "dx",
# "dy"}`, an offset; a label of release 1.14 and 1.15 with `dx` and `dy` is still read, and the
# diagram writes it as `t` once it has worked out the nearest point of the line (`DiagramMark`).
DIAGRAM_MARKS_FILE = "diagram/marks.json"

# What lives in the project folder but is not the design, so that it is never in the model hash:
# the journal and the import record (files the tool writes with the project), and the folders of the
# extensions (S8) and the as-built records (a later step), which are not serialised at all. The one
# list: `outside_the_hash(rel)` is what `model_hash` and `journal.files_hash` ask.
OUTSIDE_THE_HASH_FILES = frozenset({JOURNAL_FILE, IMPORT_RECORDS_FILE})
OUTSIDE_THE_HASH_FOLDERS = ("extensions/", "asbuilt/", "diagram/")


def mark_is_orphan(project: Project, mark_id: str) -> bool:
    """Whether a diagram mark is of a thing that no longer exists: "link:L1", "end:L1:0" and
    "bend:L1" belong to a connection, "interface:IF-1" and "route:IF-1" to an interface, whatever
    form the mark has (a place along the line, `t`, or an offset). A mark of a kind this tool does
    not know is never called an orphan (it is not ours to drop)."""
    kind, _, rest = mark_id.partition(":")
    ident = rest.partition(":")[0]
    if kind in ("link", "end", "bend"):
        return ident not in project.links
    if kind in ("interface", "route"):
        return ident not in project.interfaces
    return False


def prune_orphan_marks(project: Project) -> list[str]:
    """Drop the diagram marks of things that are gone (a deleted connection or interface), without
    a word; returns the IDs dropped. The marks stay in memory while the project is open, so that
    an undo of the delete finds them again: they are left out when the file is written
    (`serialize`) and dropped when a project is loaded."""
    gone = [m for m in project.diagram_marks if mark_is_orphan(project, m)]
    for m in gone:
        del project.diagram_marks[m]
    return gone


def outside_the_hash(rel: str) -> bool:
    """Whether the project file `rel` (a POSIX path inside the project folder) is left out of the
    model hash."""
    return rel in OUTSIDE_THE_HASH_FILES or rel.startswith(OUTSIDE_THE_HASH_FOLDERS)


def bytes_for_hash(rel: str, data: bytes) -> bytes:
    """The bytes of project file `rel` as the model hash sees them: a file of `config/` without its
    comments (`_about`, the opt-in annotation), so that annotating a project, or refreshing the
    annotation, changes no hash, no number and no written output. Any other file, and a config file
    without comments, as it is."""
    if not rel.startswith("config/") or b'"_about"' not in data:
        return data
    try:
        doc = json.loads(data)
    except ValueError:
        return data
    if not isinstance(doc, dict) or ABOUT_KEY not in doc:
        return data
    del doc[ABOUT_KEY]
    return canonical.dumps(doc)


def journal_payload(journal: Journal | None) -> dict[str, Any]:
    return {"journal": [e.model_dump(mode="json") for e in journal or ()]}


def is_managed(rel: str) -> bool:
    return bool(MANAGED_RE.match(rel))


def _dump(items: list[Entity]) -> list[dict[str, Any]]:
    return [i.model_dump(mode="json") for i in sorted(items, key=lambda x: getattr(x, "id"))]  # noqa: B009


type _Made = tuple[tuple[frozenset[int], Hashable], tuple[object, ...], bytes]
# The bytes of each file by name, with what they were made from. Entities are immutable, so a file
# whose objects (by identity) and extra parts are the same ones has the same bytes: serialising
# again after one edit rebuilds the one or two files that hold the edited object, not the project
# (audit A-9; the autosave journal, the model hash and every save serialise the whole project).
# The tuple of objects keeps them alive, so an identity cannot be taken over by another object.
_FILES: dict[str, _Made] = {}


class _Files:
    """One pass of `serialize`: files reused from the last pass when nothing they are made from has
    changed, and the set of files for the next pass."""

    def __init__(self) -> None:
        self._old = _FILES  # a dict is only ever replaced, never changed: safe across threads
        self.made: dict[str, _Made] = {}

    def get(
        self, rel: str, objs: Sequence[object], build: Callable[[], bytes], extra: Hashable = ()
    ) -> bytes:
        ident = (frozenset(map(id, objs)), extra)
        hit = self._old.get(rel)
        if hit is None or hit[0] != ident:
            hit = (ident, tuple(objs), build())
        self.made[rel] = hit
        return hit[2]

    def done(self) -> None:
        global _FILES
        _FILES = self.made


def forget_serialized_files() -> None:
    """Drop the remembered bytes (tests use it to compare with a pass that remembers nothing)."""
    global _FILES
    _FILES = {}


def _grouped[T: Entity](
    memo: _Files, items: dict[str, T], folder: str, key: str, group_of: Callable[[T], str]
) -> dict[str, bytes]:
    groups: dict[str, list[T]] = {}
    for item in items.values():
        groups.setdefault(slug(group_of(item)), []).append(item)
    return {
        f"{folder}/{g}.json": memo.get(
            f"{folder}/{g}.json",
            v,
            lambda v=v: canonical.dumps({key: _dump(list(v))}),  # type: ignore[misc]
        )
        for g, v in groups.items()
    }


def serialize(project: Project, *, tool_version: str | None = None) -> dict[str, bytes]:
    """Return every project file as canonical bytes, keyed by project-relative POSIX path."""
    memo = _Files()
    meta = project.meta
    if tool_version is not None:
        meta = ProjectMeta.model_validate({**meta.model_dump(), "tool_version": tool_version})
    files: dict[str, bytes] = {"project.json": canonical.dumps(meta.model_dump(mode="json"))}
    for name in CONFIG_NAMES:
        if name in project.config:
            files[f"config/{name}.json"] = canonical.dumps(project.config[name].model_dump())
    files["library/manifest.json"] = canonical.dumps(project.library_info.model_dump(mode="json"))
    for category in PART_CATEGORIES:
        parts = [p for p in project.parts.values() if p.category == category]
        files[f"library/{category}.json"] = memo.get(
            f"library/{category}.json",
            parts,
            lambda parts=parts: canonical.dumps({"parts": _dump(list(parts))}),  # type: ignore[misc]
        )
    types = list(project.interface_types.values())
    files["logical/interface_types.json"] = memo.get(
        "logical/interface_types.json",
        types,
        lambda: canonical.dumps({"interface_types": _dump(list(types))}),
    )
    placements = list(project.placements.values())
    zones = tuple(project.zones)
    files["logical/layout.json"] = memo.get(
        "logical/layout.json",
        placements,
        lambda: canonical.dumps({"zones": list(zones), "placements": _dump(list(placements))}),
        zones,
    )
    if project.generation is not None:
        files["generated/generation.json"] = canonical.dumps(
            project.generation.model_dump(mode="json")
        )
    if project.changelog:
        entries = list(project.changelog.values())
        files["changelog.json"] = memo.get(
            "changelog.json", entries, lambda: canonical.dumps({"changelog": _dump(list(entries))})
        )
    for b in project.baselines.values():
        # named by the baseline ID (unique, ASCII): revision names can differ only in characters
        # that a file name cannot hold, and two baselines must never share a file
        rel = f"baselines/{b.harness_id}/{b.id}.json"
        files[rel] = memo.get(rel, [b], lambda b=b: canonical.dumps(b.model_dump(mode="json")))  # type: ignore[misc]
    if project.links:  # left out while the project has no link (M2)
        links = list(project.links.values())
        files["logical/links.json"] = memo.get(
            "logical/links.json", links, lambda: canonical.dumps({"links": _dump(list(links))})
        )
    if project.journal is not None:  # a project has a journal if and only if the file exists
        kept: list[Any] = list(project.journal)
        files[JOURNAL_FILE] = memo.get(
            JOURNAL_FILE, kept, lambda: canonical.dumps(journal_payload(project.journal))
        )
    if project.import_records:  # optional: a project that never imported has no such file
        records = list(project.import_records.values())
        files[IMPORT_RECORDS_FILE] = memo.get(
            IMPORT_RECORDS_FILE,
            records,
            lambda: canonical.dumps({"imports": _dump(list(records))}),
        )
    if project.asbuilt:  # optional: a project that never recorded what was built has no such file
        built = list(project.asbuilt.values())
        files[ASBUILT_FILE] = memo.get(
            ASBUILT_FILE, built, lambda: canonical.dumps({"asbuilt": _dump(list(built))})
        )
    # optional: nothing moved by hand, no file, the files as they were; the marks of a thing that is
    # gone are left out (they stay in memory, so that an undo of the delete gets them back)
    marks = [m for m in project.diagram_marks.values() if not mark_is_orphan(project, m.id)]
    if marks:
        files[DIAGRAM_MARKS_FILE] = memo.get(
            DIAGRAM_MARKS_FILE, marks, lambda: canonical.dumps({"marks": _dump(list(marks))})
        )
    if project.waivers:
        waivers = list(project.waivers.values())
        files["waivers.json"] = memo.get(
            "waivers.json", waivers, lambda: canonical.dumps({"waivers": _dump(list(waivers))})
        )
    files.update(_grouped(memo, project.units, "logical/units", "units", lambda u: u.subsystem))

    def interface_group(i: Any) -> str:
        first = i.endpoints[0].unit_id if i.endpoints else ""
        unit = project.units.get(first)
        return unit.subsystem if unit else "unassigned"

    files.update(
        _grouped(memo, project.interfaces, "logical/interfaces", "interfaces", interface_group)
    )

    def connector_group(c: Any) -> str:
        unit = project.units.get(c.unit_id) if c.unit_id else None
        return unit.subsystem if unit else "unassigned"

    files.update(
        _grouped(memo, project.connectors, "physical/connectors", "connectors", connector_group)
    )
    for h in project.harnesses.values():
        files[f"physical/harnesses/{h.id}.json"] = memo.get(
            f"physical/harnesses/{h.id}.json",
            [h],
            lambda h=h: _harness_bytes(h),  # type: ignore[misc]
        )
    memo.done()
    return files


def _harness_bytes(h: Harness) -> bytes:
    data = h.model_dump(mode="json")
    for key in (
        "connectors",
        "wires",
        "splices",
        "shields",
        "branch_points",
        "segments",
        "accessories",
    ):
        if key in data:  # a sparse list (accessories) is left out while it is empty
            data[key] = sorted(data[key], key=lambda x: x["id"])
    return canonical.dumps(data)


def model_hash(project: Project) -> str:
    """Hash of the model state, independent of which tool version last saved it. The journal (who
    changed what and when), the import record (`imports/records.json`, where data came from), the
    extensions and the as-built records are not the design, so they are left out
    (`outside_the_hash`), and so are the comments of the config files (`_about`,
    `bytes_for_hash`): the same design gives the same hash with or without them."""
    digest = hashlib.sha256()
    for rel, data in sorted(serialize(project, tool_version="").items()):
        if outside_the_hash(rel):
            continue
        digest.update(rel.encode("utf-8") + b"\0" + bytes_for_hash(rel, data) + b"\0")
    return digest.hexdigest()
