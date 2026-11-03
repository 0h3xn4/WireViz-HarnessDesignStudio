"""Write the two tables of docs/user-manual/follow-the-workflow.md from core/workflow.py, so the page
cannot disagree with the code. A test fails when the page holds other text between the markers.
Usage: python -m tools.gen_workflow_doc"""

import re
from pathlib import Path

from harness_design_studio.core import workflow

TARGET = Path(__file__).resolve().parents[1] / "docs" / "user-manual" / "follow-the-workflow.md"
BLOCKS = {
    "workflow-table": workflow.table_markdown,
    "workflow-inspect": workflow.inspect_markdown,
}


def marker(name: str, end: bool = False) -> str:
    return f"<!-- {name}:{'end' if end else 'start'} -->"


def render(text: str) -> str:
    """`text` with the text between each pair of markers replaced by the table of the code."""
    for name, make in BLOCKS.items():
        pattern = re.compile(
            re.escape(marker(name)) + r"\n(?:.*?\n)?" + re.escape(marker(name, True)), re.DOTALL
        )
        if not pattern.search(text):
            raise SystemExit(f"{TARGET.name} has no {marker(name)} ... {marker(name, True)}")
        block = f"{marker(name)}\n{make()}\n{marker(name, True)}"
        text = pattern.sub(lambda _m: block, text)  # noqa: B023
    return text


def main() -> None:
    before = TARGET.read_text(encoding="utf-8")
    after = render(before)
    if after != before:
        TARGET.write_text(after, encoding="utf-8", newline="\n")
    print(f"{TARGET.name}: {'written' if after != before else 'already current'}")


if __name__ == "__main__":
    main()
