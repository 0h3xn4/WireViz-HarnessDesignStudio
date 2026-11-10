# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Write `src/harness_design_studio/core/legal_texts.py` from `compliance/legal/texts.md`, the one
place where every legal text is written (decision D-210). A test fails if the committed module is
stale. Usage: python -m tools.gen_legal_texts [--check]"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "compliance" / "legal" / "texts.md"
TARGET = ROOT / "src" / "harness_design_studio" / "core" / "legal_texts.py"

HEADING = re.compile(r"^## ([A-Z][A-Z_]+)\s*$")


def parse(text: str) -> dict[str, str]:
    """The text of every `## NAME` section: its first block quote line, without the `> `."""
    found: dict[str, str] = {}
    name: str | None = None
    for line in text.splitlines():
        if m := HEADING.match(line):
            name = m.group(1)
        elif name and line.startswith("> ") and name not in found:
            found[name] = line[2:].strip()
    return found


def render() -> str:
    texts = parse(SOURCE.read_text(encoding="utf-8"))
    out = [
        # REUSE-IgnoreStart (the header of the file this writes, not of this file)
        "# SPDX-FileCopyrightText: 2026 0h3xn4",
        "# SPDX-License-Identifier: GPL-3.0-only",
        # REUSE-IgnoreEnd
        '"""The legal texts, word for word (decision D-210).',
        "",
        "GENERATED from compliance/legal/texts.md by `python -m tools.gen_legal_texts`; do not edit.",
        'A test fails if this file is stale or if a place that must carry a text does not."""',
        "",
    ]
    for name, value in texts.items():
        out.append(f"{name} = {json.dumps(value, ensure_ascii=False)}")
    out += [
        "",
        "",
        "def output_notice(tool: str, version: str) -> str:",
        '    """The short notice every generated document carries."""',
        "    return OUTPUT_NOTICE.format(tool=tool, version=version)",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if the committed file is stale")
    args = ap.parse_args(argv)
    text = render()
    if args.check:
        if TARGET.read_text(encoding="utf-8") != text:
            print("stale: run python -m tools.gen_legal_texts", file=sys.stderr)
            return 1
        return 0
    TARGET.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
