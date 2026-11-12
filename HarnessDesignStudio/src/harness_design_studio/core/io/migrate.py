# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
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


def _v2_number(files: RawFiles) -> RawFiles:
    """The number: a tool that writes format 2 says so, so that a version 1.x tool opens the project
    read-only instead of setting a harness aside piece by piece."""
    meta = files.get("project.json")
    if isinstance(meta, dict):
        meta["schema_version"] = 2
    return files


def _v2_journal_lines(files: RawFiles) -> RawFiles:
    """The journal (M7a, D-228): `journal.json`, one JSON list, becomes `journal.jsonl`, one entry
    per line, so that Git can keep both sides' entries of a merge. The entries are carried over as
    they are, each with its number and its chain value, so they still verify; an entry added later
    names its parent instead (`core.model.journal`). The part goes by the files, not by the number:
    it does nothing for a project without `journal.json`, and the loader reads a `journal.json`
    in a format 2 project the same way (a build before M7a wrote that). With both files, the
    entries of both, in the order of the files (the reader keeps one copy of an entry)."""
    old = files.pop("journal.json", None)
    if old is None:
        return files
    new = files.get("journal.jsonl")
    if (
        isinstance(new, dict)
        and isinstance(new.get("journal"), list)
        and isinstance(old, dict)
        and isinstance(old.get("journal"), list)
    ):
        files["journal.jsonl"] = {"journal": [*new["journal"], *old["journal"]]}
    elif new is None:
        files["journal.jsonl"] = old
    else:
        files["journal.json"] = old  # a damaged file: left as it is, for the loader to report
    return files


# The parts of the step from format 1 to 2, run in this order on a copy of the files. Format 2 is
# not frozen until 2.0.0 is tagged (D-226): the journal layout of M7a is one more part here, not a
# format 3 (D-228). After the tag, only sparse fields.
V1_TO_V2_PARTS: tuple[Callable[[RawFiles], RawFiles], ...] = (_v2_number, _v2_journal_lines)


def _v1_to_v2(files: RawFiles) -> RawFiles:
    """v1 to v2 (M4, D-201, D-226). Format 2 is the format that may hold a loose cable end (a
    connector with the role `loose` and the part `TBD-CONNECTOR`; its place on the diagram is the
    mark `pos:<connector id>` in `diagram/marks.json`, outside the model hash). Nothing in a
    format 1 project has to change for that: a loose end is new content, and the origin of a
    harness (`interfaces`, `link` or `drawn`) is worked out from `generated` and the connection that
    names it, never stored (`core.origin`), so no harness file, no hash and no output moves; the
    step writes the number and moves the journal to its file of one entry per line (M7a, D-228),
    which is outside every hash and output (`V1_TO_V2_PARTS`). The migration safety net
    (`core.io.upgrade`) proves it changes no hash, finding or output."""
    out = copy.deepcopy(files)
    for part in V1_TO_V2_PARTS:
        out = part(out)
    return out


# `MIGRATIONS[n]` takes a project from format n to n + 1; there is one for every format before the
# one this tool writes (`SCHEMA_VERSION`).
MIGRATIONS: dict[int, Callable[[RawFiles], RawFiles]] = {0: _v0_to_v1, 1: _v1_to_v2}


def current_version() -> int:
    """The format this tool writes."""
    return SCHEMA_VERSION


def schema_version_of(files: RawFiles) -> int:
    meta = files.get("project.json")
    if isinstance(meta, dict):
        value = meta.get("schema_version", 0)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return SCHEMA_VERSION  # unreadable project.json: assume current and report the real problem


def migrate_raw(files: RawFiles, from_version: int) -> RawFiles:
    version = from_version
    while version < current_version():
        files = MIGRATIONS[version](files)
        version += 1
    return files
