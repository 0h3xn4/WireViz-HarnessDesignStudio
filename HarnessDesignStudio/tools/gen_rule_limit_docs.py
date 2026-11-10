# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Write the table of docs/models/rule-limits.md (every design rule: whether it compares a number with
a limit or is a yes/no check, and what it compares) from `core.derive_rules.INFO`, so the page cannot
leave a rule out or drift from the code. A test fails if the committed table is stale.
Usage: python -m tools.gen_rule_limit_docs"""

from pathlib import Path

from harness_design_studio.core.derive_rules import ALL_RULE_IDS, INFO, LIMIT
from harness_design_studio.core.drc import RULES

TARGET = Path(__file__).resolve().parents[1] / "docs" / "models" / "rule-limits.md"
START = "<!-- rule-table:start (python -m tools.gen_rule_limit_docs) -->"
END = "<!-- rule-table:end -->"

# the three rules that had a derivation of their own before step S1 of the transparency work
OWN_KIND = {
    "current-over-wire": "wire-current-limit",
    "voltage-drop": "wire-voltage-drop",
    "current-over-contact": "contact-current",
}


def severity_of(rule_id: str) -> str:
    for r in RULES:
        if r.id == rule_id:
            return r.severity
    return {"verify-mismatch": "error"}.get(rule_id, "info or warning (the Problems panel)")


def render_table() -> str:
    lines = [
        START,
        "",
        "| Rule | Form | What it compares | Derivation |",
        "| --- | --- | --- | --- |",
    ]
    for rule_id in ALL_RULE_IDS:
        info = INFO[rule_id]
        if info.form == LIMIT:
            form, kind = "number against a limit", OWN_KIND.get(rule_id, "rule-limit")
        else:
            form, kind = "yes/no check", "rule-check"
        lines.append(f"| `{rule_id}` | {form} | {info.compares} | `{kind}` |")
    lines += ["", END]
    return "\n".join(lines)


def render_page(current: str) -> str:
    head, _, rest = current.partition(START)
    _, _, tail = rest.partition(END)
    return head + render_table() + tail


def main() -> None:
    TARGET.write_text(render_page(TARGET.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
