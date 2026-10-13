"""Shared test helpers."""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"
MINI3 = FIXTURES / "projects" / "mini3"


PROGRAMS = ("harness-design-studio", "harness")  # the command line tool and its short alias


def program_path(folder: Path) -> str:
    """A PATH in which the command line tool (and its alias) is the program of this source tree.

    One small script per name is written into `folder`. Without it the commands would run whatever
    copy is installed in the environment: an older one, one from another checkout, or none."""
    folder.mkdir(parents=True, exist_ok=True)
    for program in PROGRAMS:
        script = folder / program
        script.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" -m harness_design_studio.cli.main "$@"\n'
        )
        script.chmod(0o755)
    return os.pathsep.join([str(folder), str(Path(sys.executable).parent), os.environ["PATH"]])


def copy_project(src: Path, dest: Path) -> Path:
    shutil.copytree(src, dest)
    return dest


def edit_json(path: Path, fn: Any) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    result = fn(data)
    path.write_text(json.dumps(data if result is None else result, indent=2), encoding="utf-8")


def output_digests(files: dict[str, bytes]) -> dict[str, str]:
    """Stable digest per output file. XLSX is hashed by its cell contents because compressed
    bytes can differ between zlib versions; everything else is hashed as bytes."""
    import hashlib
    import json

    from harness_design_studio.core.outputs.verify import _xlsx_sheets

    out = {}
    for rel, data in sorted(files.items()):
        if rel.endswith(".xlsx"):
            data = json.dumps(_xlsx_sheets(data), sort_keys=True).encode()
        out[rel] = hashlib.sha256(data).hexdigest()
    return out


def time_limit(seconds: float) -> float:
    """Performance limit; shared CI runners are slower, so HARNESS_TIME_FACTOR (CI sets 3) scales it."""
    return seconds * float(os.environ.get("HARNESS_TIME_FACTOR", "1"))
