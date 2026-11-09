# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Recompute the numbers of an `export-data` folder from its files alone.

    python reproduce.py FOLDER

This script does not import Harness Design Studio. It reads the CSV files and `configuration.json`
that `harness-design-studio export-data DIR --out FOLDER` wrote, works the wire sizing out again
with the equations of `docs/models/wire-sizing.md`, and compares what it gets with what the files
say, to 9 decimals:

* the cross-section of each gauge (the AWG definition),
* the derated current limit of each wire: base ampacity x bundle factor x temperature factor,
  with the bundle factor looked up for the bundle size, and the verdict against the current,
* whether the gauge is the smallest conductor that carries the current (or a larger one),
* the voltage drop of each wire: current x resistivity x length / cross-section x conductors, and
  its verdict against the largest drop allowed,
* the metres of every wire and accessory line of the bill of materials, from its contributions.

It prints one line of counts and a list of anything that differs, and ends with exit code 1 when
something does. A value the files leave empty (a gauge or a length not decided yet) is skipped, and
counted as such. The folder is only read.
"""

import csv
import json
import math
import sys
from pathlib import Path

TOL = 1e-9  # the agreement asked for: 9 decimals


def read_csv(folder: Path, name: str) -> list[dict[str, str]]:
    with (folder / f"{name}.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(text: str) -> float | None:
    return float(text) if text.strip() else None


def area_mm2(awg: int) -> float:
    """The AWG definition: d = 0.127 mm x 92^((36 - n) / 39), a solid round conductor."""
    return math.pi / 4 * (0.127 * 92 ** ((36 - awg) / 39)) ** 2


def exceeds(value: float, limit: float) -> bool:
    """Above the limit by more than rounding: the comparison the tool's rules use."""
    return value > limit and value - limit > 1e-9 * max(abs(value), abs(limit))


def bundle_factor(derating: dict, size: int) -> float | None:
    table = derating.get("bundle_factor_by_count")
    if isinstance(table, dict) and table:
        for count, factor in sorted((int(k), float(v)) for k, v in table.items()):
            if size <= count:
                return factor
        return None
    single = derating.get("bundle_derating")
    return float(single) if isinstance(single, int | float) else None


def reproduce(folder: Path) -> dict:
    """The counts of what was recomputed and the list of differences."""
    config = json.loads((folder / "configuration.json").read_text(encoding="utf-8"))
    values = {f["name"]: f["values"] for f in config["files"]}
    derating = values.get("derating", {})
    ampacity = {int(k): float(v) for k, v in (derating.get("ampacity_a_by_awg") or {}).items()}
    temperature = derating.get("temperature_derating")
    wires = read_csv(folder, "wire_sizing")
    seen = {"wires": len(wires), "areas": 0, "limits": 0, "gauges": 0, "drops": 0, "skipped": 0}
    differences: list[str] = []

    def same(what: str, wire: str, got: float, expected: float | None) -> None:
        if expected is None or abs(got - expected) > TOL:
            differences.append(f"{wire}: {what} is {expected} in the file, {got} recomputed")

    length_of: dict[str, float] = {}
    for row in wires:
        wire = row["Wire"]
        awg = number(row["Gauge (AWG)"])
        current = number(row["Current (A)"])
        length = number(row["Length (m)"])
        if length is not None:
            length_of[wire] = length
        if awg is None:
            seen["skipped"] += 1
            continue
        gauge = int(awg)
        area = area_mm2(gauge)
        same("cross-section (mm2)", wire, area, number(row["Cross-section (mm²)"]))
        seen["areas"] += 1
        # the derated current limit and its verdict
        k = bundle_factor(derating, int(row["Wires in the bundle"]))
        base = ampacity.get(gauge)
        if k is not None and base is not None and isinstance(temperature, int | float):
            limit = base * (k * temperature)
            same("derated current limit (A)", wire, limit, number(row["Derated current limit (A)"]))
            same("bundle factor K", wire, k, number(row["Bundle factor K"]))
            seen["limits"] += 1
            if current is not None:
                verdict = "fail" if exceeds(current, limit) else "pass"
                if verdict != row["Current verdict"]:
                    differences.append(
                        f"{wire}: current verdict {row['Current verdict']}, not {verdict}"
                    )
                same("current margin (A)", wire, limit - current, number(row["Current margin (A)"]))
                # the gauge: the smallest conductor (highest number) that carries the current
                ok = [g for g, a in ampacity.items() if not exceeds(current, a * (k * temperature))]
                if ok and not row["Locked"] and gauge > max(ok):
                    differences.append(
                        f"{wire}: AWG {gauge} is smaller than AWG {max(ok)}, which is needed"
                    )
                seen["gauges"] += 1
        # the voltage drop and its verdict
        rho, conductors = number(row["Resistivity (Ω·m)"]), number(row["Conductors counted"])
        if None in (current, rho, length, conductors) or not length:
            continue
        drop = current * rho * length / (area * 1e-6) * conductors
        same("voltage drop (V)", wire, drop, number(row["Voltage drop (V)"]))
        largest = number(row["Largest drop allowed (V)"])
        if largest is not None:
            verdict = "fail" if exceeds(drop, largest) else "pass"
            if verdict != row["Drop verdict"]:
                differences.append(f"{wire}: drop verdict {row['Drop verdict']}, not {verdict}")
            same("drop margin (V)", wire, largest - drop, number(row["Drop margin (V)"]))
        seen["drops"] += 1
    # the metres of the bill of materials
    conductors_of = {
        r["Wire"]: number(r["Conductors of the part"]) for r in read_csv(folder, "mass_wires")
    }
    metres: dict[str, float] = {}
    counts: dict[str, int] = {}
    for line in read_csv(folder, "bom_contributions"):
        part, amount = line["Part"], float(line["Amount"])
        if line["Unit"] == "ea":
            counts[part] = counts.get(part, 0) + int(amount)
            continue
        if line["Kind"] == "wire" and line["Length known"] == "yes":
            share = length_of[line["Source"]] / (conductors_of.get(line["Source"]) or 1)
            same("metres of the wire in the bill of materials", line["Source"], share, amount)
        metres[part] = metres.get(part, 0.0) + amount
    seen["bom_lines"] = 0
    for line in read_csv(folder, "bom"):
        part, quantity = line["Part"], float(line["Quantity"])
        expected = metres.get(part, 0.0) if line["Unit"] == "m" else float(counts.get(part, 0))
        same(f"quantity of {part} ({line['Unit']})", "BOM", expected, quantity)
        seen["bom_lines"] += 1
    return {"recomputed": seen, "differences": differences}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python reproduce.py FOLDER", file=sys.stderr)
        return 2
    result = reproduce(Path(argv[1]))
    print(", ".join(f"{k} {v}" for k, v in result["recomputed"].items()))
    for line in result["differences"]:
        print("DIFFERENT:", line)
    if not result["differences"]:
        print("Every recomputed number agrees with the files to 9 decimals.")
    return 1 if result["differences"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
