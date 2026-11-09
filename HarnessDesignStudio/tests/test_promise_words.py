# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""D-208 (rule 7 of the legal brief): no promise wording about the tool or its results.

The words "guarantee", "ensure", "certified", "compliant", "validated", "qualified", "safe",
"error-free", "accurate", "flight-proven" and "approved" must not be used to say something about
the tool or what it makes. The check reads the text a person sees: the READMEs and user documents,
the strings of the app, the help of the command line, the text of the written files and of the
release notes, and the package descriptions.

What is allowed, and only this:
- a sentence that says the opposite ("does not say that a harness is compliant", "not validated");
- the legal texts themselves (the intended use names "qualified engineers", which is who must check);
- "approved" as a state of a part or a row of data (the approved-parts list), as long as it is not
  said of the design, the tool, the results or an output.
"""

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_design_studio.core import legal_texts

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SRC = ROOT / "src" / "harness_design_studio"

PROMISE = re.compile(
    r"\b(guarantee[sd]?|guaranteeing|ensur(?:e|es|ed|ing)|certified|compliant|validated|qualified|"
    r"safe|error-free|accurate|flight-proven)\b",
    re.IGNORECASE,
)
# "approved" said of the design, the tool, results or an output (not of a part or a row of data)
APPROVAL_CLAIM = re.compile(
    r"\b(?:design|harness(?:es)?|tool|program|results?|outputs?|drawings?)\s+"
    r"(?:is|are|was|were|has been|have been|gets|got)\s+(?:\w+\s+)?approved\b"
    r"|\bapproved by (?:the )?(?:tool|program|software)\b",
    re.IGNORECASE,
)
NEGATION = re.compile(
    r"\b(?:not|never|no|nobody|without|cannot|does not|do not)\b|n't", re.IGNORECASE
)
ROOT_README_UPSTREAM_MARKER = "Original WireViz README"

DOCS = (
    "INSTALL",
    "FAQ",
    "GETTING_STARTED",
    "README",
    "OUTPUTS",
    "CLI",
    "TROUBLESHOOTING",
    "CONCEPTS",
    "CHEATSHEET",
    "TIPS",
    "SECURITY",
)
MARKDOWN = [REPO / "README.md", ROOT / "README.md", ROOT / "CHANGELOG.md", REPO / "CONTRIBUTING.md"]
MARKDOWN += [ROOT / "NOTICE", REPO / ".github" / "SUPPORT.md", REPO / ".github" / "SECURITY.md"]
MARKDOWN += [REPO / ".github" / "pull_request_template.md"]
MARKDOWN += sorted((REPO / ".github" / "ISSUE_TEMPLATE").glob("*.md"))
MARKDOWN += [ROOT / "docs" / f"{n}.md" for n in DOCS]
MARKDOWN += sorted((ROOT / "docs" / "user-manual").glob("*.md"))
MARKDOWN += sorted((ROOT / "docs" / "releases").glob("*.md"))
TEXT = [
    ROOT / "packaging" / "windows" / "README-windows.txt",
    ROOT / "packaging" / "ubuntu" / "README.txt",
]
PYTHON = [
    SRC / "gui" / "strings.py",
    ROOT / "tools" / "release_notes.py",
    ROOT / "tools" / "build_deb.py",
]
PYTHON += sorted((SRC / "cli").glob("*.py"))
PYTHON += sorted((SRC / "core" / "outputs").glob("*.py"))
PYTHON += [SRC / "core" / "legal_texts.py"]


def _without_legal_texts(text: str) -> str:
    for value in vars(legal_texts).values():
        if isinstance(value, str) and len(value) > 20:
            text = text.replace(value, "")
    return text


def problems_in(text: str) -> list[str]:
    """The promise words in `text` that are not allowed (see the module text), with a snippet."""
    found: list[str] = []
    for line in _without_legal_texts(text).splitlines():
        for match in list(PROMISE.finditer(line)) + list(APPROVAL_CLAIM.finditer(line)):
            before = line[max(0, match.start() - 120) : match.start() + len(match.group(0))]
            before = re.split(r"(?<=[.!?;:|])\s", before)[-1]  # the sentence so far
            if not NEGATION.search(before):
                found.append(line[max(0, match.start() - 40) : match.end() + 40].strip())
    return found


def _strings(path: Path) -> Iterator[str]:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def _id(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


@pytest.mark.parametrize("path", [p for p in MARKDOWN if p.exists()], ids=_id)
def test_no_promise_words_in_the_documents(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if path == REPO / "README.md":
        text = text.split(ROOT_README_UPSTREAM_MARKER)[0]  # the rest is WireViz's own README
    assert not problems_in(text), problems_in(text)


@pytest.mark.parametrize("path", [p for p in TEXT if p.exists()], ids=_id)
def test_no_promise_words_in_the_package_texts(path: Path) -> None:
    assert not problems_in(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", PYTHON, ids=_id)
def test_no_promise_words_in_the_text_a_person_sees(path: Path) -> None:
    found = [p for s in _strings(path) for p in problems_in(s)]
    assert not found, found


def test_the_check_itself_finds_what_it_should() -> None:
    assert problems_in("The tool guarantees a safe harness.")
    assert problems_in("Results are accurate and approved by the tool.")
    assert problems_in("The design is approved.")
    assert problems_in("A certified, error-free, flight-proven result.")
    assert not problems_in("The tool does not say that a harness is compliant.")
    assert not problems_in("Not validated against the WireViz program.")
    assert not problems_in("No parts are approved yet; import the approved parts list.")
    assert not problems_in(legal_texts.INTENDED_USE)  # "qualified engineers", from the source
