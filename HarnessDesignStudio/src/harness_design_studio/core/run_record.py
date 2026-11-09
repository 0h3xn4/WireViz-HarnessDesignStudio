# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The run record: who ran the tool, when, with what, kept outside the hashes (D-191 (1), S5).

The files the tool writes carry no time and no user name, so that the same design gives the same
bytes (the output hashes, the numbers snapshot, a Git diff of the outputs). A reviewer still wants
to know when a set of files was made and by whom. That goes in a file of its own, `run_record.json`,
which is written **only when asked** (`export --run-record`, `generate --run-record`, `export-data
--run-record`), next to the files and never inside one, and which is not part of any hash:

    {"format": 1, "time_utc": "2026-11-03T09:15:42Z", "operator": "A. Engineer",
     "tool": "harness-design-studio", "tool_version": "1.11.1", "platform": "Linux-6.8-x86_64",
     "python": "3.14.0", "model_hash": "9f3c...", "extensions": []}

The record holds no path. `extensions` is the list of the plug-ins in force (name and version);
it is empty until the extension registry (S8) fills it. The clock and the operator are parameters,
so a test makes the record it wants; `model_hash` is the one `export` and `provenance.json` show,
so the record ties a time and a person to exactly those files.
"""

import json
import platform
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness_design_studio import __version__
from harness_design_studio.core import journal
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.model import Project

FORMAT = 1
FILE_NAME = "run_record.json"
OPERATOR_ENV = "HARNESS_AUTHOR"
UNKNOWN = "unknown"

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """The time of the run, in UTC and to the second (the only clock the tool reads)."""
    return datetime.now(UTC).replace(microsecond=0)


def resolve_operator(
    explicit: str | None = None,
    *,
    environ: dict[str, str] | None = None,
    folder: Path | None = None,
) -> str:
    """Who is running the tool: the name given (`--author`), else the environment variable
    `HARNESS_AUTHOR`, else the `user.name` Git has for the project folder, else the user of the
    operating system (`USER`, `USERNAME` or `LOGNAME`), else "unknown". Never an empty text. The
    journal of the project resolves its author the same way: this calls `journal.resolve_author`."""
    return journal.resolve_author(explicit, environ=environ, folder=folder)


def make(
    project: Project,
    *,
    operator: str | None = None,
    now: Clock | None = None,
    folder: Path | None = None,
    extensions: Sequence[dict[str, str]] = (),
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """The run record of this run as data. `now` and `operator` are given by a test; `folder` is
    the project folder (to find the Git name; it is not recorded); `extensions` is what the
    extension registry reports (name and version of each plug-in in force)."""
    when = (now or utc_now)().astimezone(UTC).replace(microsecond=0)
    if not extensions and project.extensions is not None:
        # S8: every enabled declarative file and loaded plug-in (name, version, kind, file, hash)
        from harness_design_studio.core.extensions.manager import provenance

        extensions = [{k: str(v) for k, v in row.items()} for row in provenance(project)]
    return {
        "format": FORMAT,
        "time_utc": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "operator": resolve_operator(operator, environ=environ, folder=folder),
        "tool": "harness-design-studio",
        "tool_version": __version__,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "model_hash": model_hash(project),
        "extensions": [dict(e) for e in extensions],
    }


def to_bytes(record: dict[str, Any]) -> bytes:
    return (json.dumps(record, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def write(folder: Path, record: dict[str, Any]) -> Path:
    """Write `run_record.json` into `folder` (made when missing) and return its path."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / FILE_NAME
    path.write_bytes(to_bytes(record))
    return path


def write_for(
    project: Project,
    folder: Path,
    *,
    operator: str | None = None,
    now: Clock | None = None,
    project_folder: Path | None = None,
    extensions: Sequence[dict[str, str]] = (),
    environ: dict[str, str] | None = None,
) -> Path:
    """Make the record of this run and write it into `folder`."""
    return write(
        folder,
        make(
            project,
            operator=operator,
            now=now,
            folder=project_folder,
            extensions=extensions,
            environ=environ,
        ),
    )
