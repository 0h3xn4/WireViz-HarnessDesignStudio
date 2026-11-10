# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Explain everything: how every number of a project was made, as files.

    python explain_everything.py OUT_FOLDER [PROJECT_FOLDER]

Writes `derivations.json` and `derivations.csv` to OUT_FOLDER: for every wire its length, the
current its gauge may carry after derating, the voltage drop and the mass; for every harness its
mass; for every part why the bill of materials has its quantity; for every interface the current
limit of its contacts. Each entry has the equation, the inputs with their units and where each comes
from, the steps, the check against its limit and the assumptions it rests on. Without PROJECT_FOLDER
it explains the flatsat example. The files are the ones `harness-design-studio explain --all --out`
writes, and the same design gives the same bytes.

It then lists what stops a number from being checked: the derivations that have no value yet.
"""

import sys
import tempfile
from pathlib import Path

from harness_design_studio.api import create_project, explain_all, write_derivations


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("derivations")
    if len(argv) > 1:
        return report(Path(argv[1]), out)
    with tempfile.TemporaryDirectory() as work:
        folder = Path(work) / "flatsat"
        create_project(folder, "flatsat")
        return report(folder, out)


def report(project: Path, out: Path) -> int:
    written = write_derivations(project, out)
    print(f"{written.count} derivations written to {out} ({written.without_value} without a value)")
    missing = sorted({m for d in explain_all(project) for m in d.missing})
    for what in missing[:5]:
        print(f"not set: {what}")
    if len(missing) > 5:
        print(f"... and {len(missing) - 5} more (see the column Missing of derivations.csv)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
