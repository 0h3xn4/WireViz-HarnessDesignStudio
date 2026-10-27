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

    from harness_design_studio.core.outputs.verify import _xlsx_sheets, _xlsx_values

    out = {}
    for rel, data in sorted(files.items()):
        if rel.endswith("_build.xlsx"):  # numbers and all sheets, read with the spreadsheet library
            data = json.dumps(_xlsx_values(data), sort_keys=True).encode()
        elif rel.endswith(".xlsx"):
            data = json.dumps(_xlsx_sheets(data), sort_keys=True).encode()
        out[rel] = hashlib.sha256(data).hexdigest()
    return out


DEFAULT_TIME_FACTOR = 2.0  # a limit is met on an idle workstation with room to spare (E-F1)


def time_factor() -> float:
    """The factor that scales every wall-clock limit: HARNESS_TIME_FACTOR (CI sets 3, the Windows
    job 8), or 2 when it is not set, so `pytest -m perf` alone is green on an idle machine."""
    return float(os.environ.get("HARNESS_TIME_FACTOR", str(DEFAULT_TIME_FACTOR)))


def time_limit(seconds: float) -> float:
    """Performance limit; shared CI runners are slower, so HARNESS_TIME_FACTOR scales it."""
    return seconds * time_factor()


def within(measured: float, limit: float, what: str = "") -> None:
    """Assert that `measured` is under `limit` (both in the unit the test works in), and say both
    numbers and the factor when it is not, so a slow machine can be told from a slowdown."""
    allowed = time_limit(limit)
    assert measured < allowed, (
        f"{what + ': ' if what else ''}measured {measured:.4g}, limit {allowed:.4g} "
        f"({limit:g} x HARNESS_TIME_FACTOR {time_factor():g})"
    )


def pinout_project() -> Any:  # a Project
    """mini3 with labelled pins on four device connectors (example data, no engineering values):
    RS-422 on OBC-J01 and RW1-J02 (pins 1 to 4: TX+, TX-, RX+, RX-; pin 5 has no signal) and power
    on PCDU-J02 and OBC-J02 (pins 1 and 2: PWR, RTN; pin 3 has no signal). No link yet."""
    from harness_design_studio.core.model import Pin
    from harness_design_studio.core.samples import mini3

    p = mini3()
    data = ("TX+", "TX-", "RX+", "RX-")
    for cid in ("OBC-J01", "RW1-J02"):
        c = p.connectors[cid]
        pins = [Pin(id=str(k + 1), signal=s) for k, s in enumerate(data)] + [Pin(id="5")]
        p.connectors[cid] = c.model_copy(update={"pins": pins})
    for cid in ("PCDU-J02", "OBC-J02"):
        c = p.connectors[cid]
        pins = [Pin(id="1", signal="PWR"), Pin(id="2", signal="RTN"), Pin(id="3")]
        p.connectors[cid] = c.model_copy(update={"pins": pins})
    return p
