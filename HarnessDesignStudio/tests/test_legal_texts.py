# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""D-208: every legal text is written once (compliance/legal/texts.md) and copied word for word.

The tests fail when the generated module is stale, when a place that must carry a text does not,
and when a copy that was edited by hand no longer matches the source (a drift guard that looks for
the first words of each text anywhere in the documents and sources).
"""

import re
from pathlib import Path

import pytest

from harness_design_studio.core import legal_texts
from tools import gen_legal_texts

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SOURCE = ROOT / "compliance" / "legal" / "texts.md"

# Where each text must appear, word for word (the app is checked in tests/test_legal_app.py, the
# written files in tests/test_output_notices.py and the release notes in tests/test_release_notes.py).
EVERYWHERE = (
    "DISCLAIMER",
    "INTENDED_USE",
    "PROJECT_STATUS",
    "NOT_REVIEWED",
    "AI_AUTHORSHIP",
    "COPYRIGHT_SCOPE",
    "LICENCE",
    "WIREVIZ_RELATION",
    "NON_AFFILIATION",
    "TRADEMARKS",
    "PRIVACY_APP",
)
PLACES: dict[Path, tuple[str, ...]] = {
    REPO / "README.md": EVERYWHERE,
    ROOT / "README.md": EVERYWHERE,
    ROOT / "NOTICE": tuple(n for n in EVERYWHERE if n != "PRIVACY_APP"),
    REPO / "CONTRIBUTING.md": ("PROJECT_STATUS",),
    REPO / ".github" / "SUPPORT.md": ("PROJECT_STATUS", "DISCLAIMER"),
    REPO / ".github" / "SECURITY.md": ("PROJECT_STATUS", "DISCLAIMER"),
    REPO / ".github" / "pull_request_template.md": ("PROJECT_STATUS",),
    REPO / ".github" / "ISSUE_TEMPLATE" / "problem_report.md": ("PROJECT_STATUS",),
    ROOT / "packaging" / "windows" / "README-windows.txt": (
        "LICENCE",
        "DISCLAIMER",
        "PROJECT_STATUS",
    ),
    ROOT / "packaging" / "ubuntu" / "README.txt": (
        "PRIVACY_APP",
        "LICENCE",
        "DISCLAIMER",
        "PROJECT_STATUS",
    ),
}
# Folders left out of the drift guard: the audit quotes texts on purpose, the rest is not ours.
SKIP_PARTS = {".venv", "__pycache__", "dist", "build", "src/harness_design_studio.egg-info"}


def _flat(text: str) -> str:
    """The text with block-quote marks and line breaks folded into single spaces."""
    text = re.sub(r"^\s*>\s?", "", text, flags=re.M)
    return re.sub(r"\s+", " ", text).strip()


def _texts() -> dict[str, str]:
    return {k: v for k, v in vars(legal_texts).items() if k.isupper() and isinstance(v, str)}


def test_the_generated_module_matches_the_source() -> None:
    assert gen_legal_texts.render() == gen_legal_texts.TARGET.read_text(encoding="utf-8"), (
        "run: python -m tools.gen_legal_texts"
    )


def test_every_text_of_the_source_is_in_the_module() -> None:
    parsed = gen_legal_texts.parse(SOURCE.read_text(encoding="utf-8"))
    assert parsed == _texts()
    assert set(EVERYWHERE) | {"OUTPUT_NOTICE"} == set(parsed)


def test_the_texts_have_no_line_breaks_and_no_empty_text() -> None:
    for name, text in _texts().items():
        assert text.strip() and "\n" not in text, name


@pytest.mark.parametrize("place", sorted(PLACES), ids=lambda p: p.relative_to(REPO).as_posix())
def test_a_place_carries_its_texts_word_for_word(place: Path) -> None:
    body = _flat(place.read_text(encoding="utf-8"))
    for name in PLACES[place]:
        assert _flat(getattr(legal_texts, name)) in body, (
            f"{place.name}: {name} is missing or changed"
        )


def _documents() -> list[Path]:
    found: list[Path] = [REPO / "README.md"]
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT).as_posix()
        if not path.is_file() or path.suffix not in {".md", ".py", ".txt"}:
            continue
        if any(part in rel for part in SKIP_PARTS) or rel.startswith("compliance/legal/"):
            continue
        if rel.startswith(("tests/", ".venv")):
            continue
        found.append(path)
    return found


def test_no_copy_of_a_text_was_edited_by_hand() -> None:
    """A copy that starts like a text but does not hold all of it has drifted from the source."""
    problems: list[str] = []
    starts = {
        name: " ".join(_flat(text).split(" ")[:8])
        for name, text in _texts().items()
        if name != "OUTPUT_NOTICE"
    }
    for path in _documents():
        body = _flat(path.read_text(encoding="utf-8", errors="replace"))
        for name, start in starts.items():
            if start in body and _flat(getattr(legal_texts, name)) not in body:
                problems.append(f"{path.relative_to(REPO).as_posix()}: {name}")
    assert not problems, problems
