"""Schema migrations on the raw JSON tree, one step per version. Lossless: nothing is dropped."""

import copy
from collections.abc import Callable
from typing import Any

from harness_design_studio.core.model import SCHEMA_VERSION

RawFiles = dict[str, Any]


def _v0_to_v1(files: RawFiles) -> RawFiles:
    """v0: no schema_version, project.json used `tool`, units had `redundant: bool`."""
    out = copy.deepcopy(files)
    meta = out.get("project.json")
    if isinstance(meta, dict):
        if "tool" in meta:
            meta["tool_version"] = meta.pop("tool")
        meta["schema_version"] = 1
    for rel, data in out.items():
        if rel.startswith("logical/units/") and isinstance(data, dict):
            for unit in data.get("units", []):
                if isinstance(unit, dict) and "redundant" in unit and "side" not in unit:
                    flag = unit.pop("redundant")
                    unit["side"] = "redundant" if flag is True else "nominal"
    return out


MIGRATIONS: dict[int, Callable[[RawFiles], RawFiles]] = {0: _v0_to_v1}


def schema_version_of(files: RawFiles) -> int:
    meta = files.get("project.json")
    if isinstance(meta, dict):
        value = meta.get("schema_version", 0)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return SCHEMA_VERSION  # unreadable project.json: assume current and report the real problem


def migrate_raw(files: RawFiles, from_version: int) -> RawFiles:
    version = from_version
    while version < SCHEMA_VERSION:
        files = MIGRATIONS[version](files)
        version += 1
    return files
