"""Every relative link and anchor in the Markdown documentation resolves."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = [
    ROOT / "README.md",
    ROOT / "CLAUDE.md",
    ROOT / "CHANGELOG.md",
    *sorted((ROOT / "docs").rglob("*.md")),  # also developer/, user-manual/, guide/, examples/ ...
    ROOT / "src" / "harness_design_studio" / "resources" / "examples" / "templates" / "README.md",
]
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)|!\[[^\]]*\]\(([^)\s]+)\)")


def _anchors(markdown: Path) -> set[str]:
    out: set[str] = set()
    inside = False
    for line in markdown.read_text().splitlines():
        if line.startswith("```"):
            inside = not inside
        elif not inside and (m := re.match(r"#{1,6}\s+(.*)", line)):
            text = re.sub(r"[`*_]", "", m.group(1)).strip().lower()  # GitHub's rule
            out.add(re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", text)))
    return out


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_links_resolve(doc: Path) -> None:
    text = doc.read_text()
    inside = False
    problems: list[str] = []
    for line in text.splitlines():
        if line.startswith("```"):
            inside = not inside
            continue
        if inside:
            continue
        for match in LINK.finditer(line):
            target = match.group(1) or match.group(2)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path, _, anchor = target.partition("#")
            file = (doc.parent / path).resolve() if path else doc
            if not file.exists():
                problems.append(f"{target}: no such file")
            elif anchor and file.suffix == ".md" and anchor not in _anchors(file):
                problems.append(f"{target}: no such heading")
    assert not problems, f"{doc.name}: {problems}"
