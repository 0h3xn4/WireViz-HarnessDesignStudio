"""Mapping between the in-memory project and its folder of small JSON files.

One file per subsystem keeps Git merges clean; one file per harness likewise. File names only
*group* data: loading never depends on them, so renaming a subsystem never loses anything.
"""

import hashlib
import re
from collections.abc import Callable
from typing import Any

from harness_design_studio.core.model import CONFIG_NAMES, PART_CATEGORIES, Project, ProjectMeta
from harness_design_studio.core.model.base import Entity

from . import canonical
from .fs import slug

MANAGED_RE = re.compile(
    r"^(project\.json|waivers\.json|logical/layout\.json|generated/generation\.json|config/[^/]+\.json|library/[^/]+\.json|logical/interface_types\.json"
    r"|logical/(units|interfaces)/[^/]+\.json|physical/(connectors|harnesses)/[^/]+\.json|changelog\.json|baselines/[^/]+/[^/]+\.json)$"
)
# Serialized harness files by object identity (harnesses are immutable); keeps hashing cheap.
_HARNESS_CACHE: dict[int, tuple[Any, bytes]] = {}
MANAGED_DIRS = ("config", "library", "logical", "physical", "generated", "baselines")


def is_managed(rel: str) -> bool:
    return bool(MANAGED_RE.match(rel))


def _dump(items: list[Entity]) -> list[dict[str, Any]]:
    return [i.model_dump(mode="json") for i in sorted(items, key=lambda x: getattr(x, "id"))]  # noqa: B009


def _grouped[T: Entity](
    items: dict[str, T], folder: str, key: str, group_of: Callable[[T], str]
) -> dict[str, bytes]:
    groups: dict[str, list[T]] = {}
    for item in items.values():
        groups.setdefault(slug(group_of(item)), []).append(item)
    return {f"{folder}/{g}.json": canonical.dumps({key: _dump(list(v))}) for g, v in groups.items()}


def serialize(project: Project, *, tool_version: str | None = None) -> dict[str, bytes]:
    """Return every project file as canonical bytes, keyed by project-relative POSIX path."""
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
        files[f"library/{category}.json"] = canonical.dumps({"parts": _dump(list(parts))})
    files["logical/interface_types.json"] = canonical.dumps(
        {"interface_types": _dump(list(project.interface_types.values()))}
    )
    files["logical/layout.json"] = canonical.dumps(
        {"zones": list(project.zones), "placements": _dump(list(project.placements.values()))}
    )
    if project.generation is not None:
        files["generated/generation.json"] = canonical.dumps(
            project.generation.model_dump(mode="json")
        )
    if project.changelog:
        files["changelog.json"] = canonical.dumps(
            {"changelog": _dump(list(project.changelog.values()))}
        )
    for b in project.baselines.values():
        # named by the baseline ID (unique, ASCII): revision names can differ only in characters
        # that a file name cannot hold, and two baselines must never share a file
        files[f"baselines/{b.harness_id}/{b.id}.json"] = canonical.dumps(b.model_dump(mode="json"))
    if project.waivers:
        files["waivers.json"] = canonical.dumps({"waivers": _dump(list(project.waivers.values()))})
    files.update(_grouped(project.units, "logical/units", "units", lambda u: u.subsystem))

    def interface_group(i: Any) -> str:
        first = i.endpoints[0].unit_id if i.endpoints else ""
        unit = project.units.get(first)
        return unit.subsystem if unit else "unassigned"

    files.update(_grouped(project.interfaces, "logical/interfaces", "interfaces", interface_group))

    def connector_group(c: Any) -> str:
        unit = project.units.get(c.unit_id) if c.unit_id else None
        return unit.subsystem if unit else "unassigned"

    files.update(_grouped(project.connectors, "physical/connectors", "connectors", connector_group))
    keep: dict[int, tuple[Any, bytes]] = {}
    for h in project.harnesses.values():
        cached = _HARNESS_CACHE.get(id(h))
        if cached is None or cached[0] is not h:  # immutable objects: identity means same content
            data = h.model_dump(mode="json")
            for key in ("connectors", "wires", "splices", "shields", "branch_points", "segments"):
                data[key] = sorted(data[key], key=lambda x: x["id"])
            cached = (h, canonical.dumps(data))
        keep[id(h)] = cached
        files[f"physical/harnesses/{h.id}.json"] = cached[1]
    _HARNESS_CACHE.clear()
    _HARNESS_CACHE.update(keep)
    return files


def model_hash(project: Project) -> str:
    """Hash of the model state, independent of which tool version last saved it."""
    digest = hashlib.sha256()
    for rel, data in sorted(serialize(project, tool_version="").items()):
        digest.update(rel.encode("utf-8") + b"\0" + data + b"\0")
    return digest.hexdigest()
