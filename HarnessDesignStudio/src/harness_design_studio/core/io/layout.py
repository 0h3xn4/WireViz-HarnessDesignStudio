"""Mapping between the in-memory project and its folder of small JSON files.

One file per subsystem keeps Git merges clean; one file per harness likewise. File names only
*group* data: loading never depends on them, so renaming a subsystem never loses anything.
"""

import hashlib
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

from . import canonical
from .fs import slug

MANAGED_RE = re.compile(
    r"^(project\.json|waivers\.json|logical/layout\.json|generated/generation\.json|config/[^/]+\.json|library/[^/]+\.json|logical/interface_types\.json"
    r"|logical/links\.json|logical/(units|interfaces)/[^/]+\.json|physical/(connectors|harnesses)/[^/]+\.json|changelog\.json|baselines/[^/]+/[^/]+\.json)$"
)
MANAGED_DIRS = ("config", "library", "logical", "physical", "generated", "baselines")


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
    """Hash of the model state, independent of which tool version last saved it."""
    digest = hashlib.sha256()
    for rel, data in sorted(serialize(project, tool_version="").items()):
        digest.update(rel.encode("utf-8") + b"\0" + data + b"\0")
    return digest.hexdigest()
