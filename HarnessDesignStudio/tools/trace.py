"""Traceability: tool requirement -> source -> verifying files -> tests that name the requirement.

Reads docs/REQUIREMENTS.md, scans tests/ for the requirement IDs, writes
compliance/traceability.csv. Exit code 1 if a requirement names a file that does not exist or is
named by no test and no tool (ECSS-E-ST-40C 5.8.3, ECSS-Q-ST-80C 6.2.6.12; gap G-02).
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = ["req_id", "requirement", "source", "verified_by", "tests_naming_it", "status"]
ROW = re.compile(r"^\|\s*(REQ-[A-Z0-9]+-\d+)\s*\|(.*)\|(.*)\|(.*)\|\s*$")
FILE = re.compile(r"`((?:tests|tools|src)/[\w./-]+)`")
ID = re.compile(r"REQ-[A-Z0-9]+-\d+")


def requirements() -> list[tuple[str, str, str, str]]:
    rows = []
    for line in (ROOT / "docs" / "REQUIREMENTS.md").read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if m:
            rows.append((m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()))
    return rows


def tests_naming() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for p in sorted((ROOT / "tests").glob("*.py")):
        for rid in ID.findall(p.read_text(encoding="utf-8")):
            found.setdefault(rid, set()).add(p.name)
    return found


def build() -> list[list[str]]:
    named = tests_naming()
    rows = []
    for rid, text, source, verified in requirements():
        files = FILE.findall(verified)
        missing = [f for f in files if not (ROOT / f).exists()]
        tests = sorted(named.get(rid, set()))
        has_tool = any(f.startswith(("tools/", "src/")) and f not in missing for f in files)
        if missing:
            status = "missing-file: " + " ".join(missing)
        elif tests:
            status = "traced"
        elif has_tool or any(f.startswith("tests/") for f in files):
            status = "verified-by-file-only"
        elif "(review)" in verified:
            status = "review-only"  # no automatic check; a person confirms it at each review
        else:
            status = "untraced"
        rows.append([rid, text, source, verified, " ".join(tests), status])
    return rows


def main() -> int:
    rows = build()
    out = ROOT / "compliance" / "traceability.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    bad = [r for r in rows if r[5] not in ("traced", "verified-by-file-only", "review-only")]
    for r in bad:
        print(f"{r[0]}: {r[5]}")
    print(f"{len(rows)} requirements, {sum(r[5] == 'traced' for r in rows)} named by a test")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
