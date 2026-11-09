# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Trade study: change one engineering value over a range and see what it does to the design.

The script copies the flatsat example to a temporary folder, sets the bundle derating factor of
`config/derating.json` to each value in turn, generates the harnesses again and writes one row for
each value: the wire gauges that result, the number of open findings, and the worst voltage drop.
Your own project is never touched. The numbers are the ones `generate` and `drc` give, and the
example's values are example values, not engineering data.

    python trade_study.py study.csv

To vary another value, change FILE and KEY (see `get_config` for the list), for example
`("generation", "service_loop_m")`. A value the tool refuses (a factor above 1) raises
`ConfigValueError`; a value for which no wire gauge fits makes `generate` report `ok` false and
save nothing, and the row then holds only the number of errors `generate` reported.
"""

import csv
import sys
import tempfile
from collections import Counter
from pathlib import Path

from harness_design_studio.api import (
    create_project,
    explain_all,
    generate,
    load_project,
    run_checks,
    set_config,
)

FILE, KEY = "derating", "bundle_derating"
VALUES = (0.5, 0.6, 0.8, 1.0)
COLUMNS = (
    "value",
    "generate_ok",
    "gauges",
    "open_errors",
    "open_warnings",
    "worst_voltage_drop_v",
)


def study(folder: Path, values: tuple[float, ...] = VALUES) -> list[dict[str, object]]:
    """Set the value, generate, and measure, for each value; the project in `folder` is changed."""
    rows: list[dict[str, object]] = []
    for value in values:
        set_config(folder, FILE, KEY, value)
        made = generate(folder)
        if (
            not made.ok
        ):  # nothing fits: generate saved nothing, so there is no new design to measure
            errors = sum(f.severity == "error" for f in made.findings)
            rows.append({"value": value, "generate_ok": False, "open_errors": errors})
            continue
        project = load_project(folder)
        gauges = Counter(
            w.gauge_awg for h in project.harnesses.values() for w in h.wires if w.gauge_awg
        )
        drops = [d.value for d in explain_all(project) if d.id == "wire-voltage-drop" and d.value]
        checks = run_checks(project)
        rows.append(
            {
                "value": value,
                "generate_ok": made.ok,
                "gauges": " ".join(f"AWG{g}x{n}" for g, n in sorted(gauges.items())),
                "open_errors": checks.open_errors,
                "open_warnings": checks.open_warnings,
                "worst_voltage_drop_v": f"{max(drops):.4f}" if drops else "",
            }
        )
    return rows


def main(argv: list[str]) -> int:
    target = Path(argv[0]) if argv else Path("trade-study.csv")
    with tempfile.TemporaryDirectory() as work:
        folder = Path(work) / "flatsat"
        create_project(folder, "flatsat")
        rows = study(folder)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n", restval="")
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
