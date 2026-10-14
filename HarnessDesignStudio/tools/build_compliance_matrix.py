"""Build compliance/compliance_matrix.csv from the requirement lists and the assessments.

Inputs (all under compliance/): requirements/*.csv, assessment/process_rules.csv (clause-level
rules for ECSS-E-ST-40C and ECSS-Q-ST-80C), assessment/process_overrides.csv (single requirements),
assessment/design_assessment.csv (one row per harness-relevant design requirement).

Statuses never say "compliant". Process rows: evidence-candidate, partial, gap, human, na.
The matrix only records the assessment; Phase 3 evidence decides.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "compliance"
PROCESS = ("ECSS-E-ST-40C", "ECSS-Q-ST-80C")
DESIGN = ("ECSS-Q-ST-30-11C", "ECSS-E-ST-20-07C", "ESCC-3901")
HEADER = [
    "standard", "kind", "id", "clause", "requirement", "applicable", "status", "basis",
    "evidence", "gap", "rationale", "status_after_phase2", "evidence_after_phase2",
]  # fmt: skip


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def matches(clause: str, prefix: str) -> bool:
    return clause == prefix or clause.startswith(prefix + ".")


def clause_key(r: dict[str, str]) -> str:
    c = r["clause"]
    return c if c[:1].isdigit() else c.split(".")[0]  # annex rows: the annex letter


def process_rows(std: str) -> list[list[str]]:
    rules = [x for x in read(ROOT / "assessment" / "process_rules.csv") if x["standard"] == std]
    rules.sort(key=lambda x: -len(x["prefix"]))
    over = {x["ID"]: x for x in read(ROOT / "assessment" / "process_overrides.csv")}
    rows: list[list[str]] = []
    for r in read(ROOT / "requirements" / f"{std}.csv"):
        if r["deleted"] == "Y":
            continue
        cat = r["cat_C"]
        base = [std, "A", r["ID"], r["clause"], r["text"][:160], cat]
        if cat == "N":
            rows.append(
                [
                    *base,
                    "na",
                    "tailoring table",
                    "",
                    "",
                    "Not applicable at criticality C",
                    "na",
                    "",
                ]
            )
            continue
        if r["ID"] in over:
            o = over[r["ID"]]
            rows.append(
                [*base, o["status"], "requirement", o["evidence"], o["gap"], o["rationale"],
                 o["status"], o["evidence"]]
            )  # fmt: skip
            continue
        key = clause_key(r)
        rule = next((x for x in rules if matches(key, x["prefix"])), None)
        if rule is None:
            raise SystemExit(f"no assessment rule for {std} {r['ID']} clause {r['clause']}")
        rows.append(
            [*base, rule["status"], "clause", rule["evidence"], rule["gap"], rule["rationale"],
             rule["after_status"], rule["after_evidence"]]
        )  # fmt: skip
    return rows


def design_rows(std: str) -> list[list[str]]:
    assess = {x["ID"]: x for x in read(ROOT / "assessment" / "design_assessment.csv")}
    rows: list[list[str]] = []
    for r in read(ROOT / "requirements" / f"{std}.csv"):
        if r["deleted"] == "Y" or r["harness_relevant"] != "Y":
            continue
        a = assess.get(r["ID"])
        if a is None:
            raise SystemExit(f"no design assessment for {r['ID']}")
        status = f"today:{a['today']} target:{a['target']}"
        rows.append(
            [std, "B", r["ID"], r["clause"], r["text"][:160], "Y", status, "requirement",
             a["evidence"], a["gap"], a["remediation"], f"after:{a['after']}", a["tests"]]
        )  # fmt: skip
    return rows


def build() -> list[list[str]]:
    rows: list[list[str]] = []
    for s in PROCESS:
        rows += process_rows(s)
    for s in DESIGN:
        rows += design_rows(s)
    return rows


def main() -> int:
    rows = build()
    with (ROOT / "compliance_matrix.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    for std in (*PROCESS, *DESIGN):
        c = Counter(r[6] for r in rows if r[0] == std)
        print(std, sum(c.values()), dict(sorted(c.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
