"""CLAUDE.md is loaded into every session, so it stays short; the area notes live in
docs/developer/agent/ and CLAUDE.md links each of them (decision D-182)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / "CLAUDE.md"
AGENT = ROOT / "docs" / "developer" / "agent"

MAX_BYTES = 20_000


def test_claude_md_stays_short() -> None:
    size = len(CLAUDE.read_bytes())
    assert size <= MAX_BYTES, (
        f"CLAUDE.md is {size} bytes (limit {MAX_BYTES}): move the area notes to "
        "docs/developer/agent/ and link them from the section 'Where the rest is'"
    )


def test_every_area_note_is_linked_from_claude_md() -> None:
    text = CLAUDE.read_text(encoding="utf-8")
    notes = sorted(AGENT.glob("*.md"))
    assert notes, "docs/developer/agent/ holds no area note"
    for note in notes:
        assert f"docs/developer/agent/{note.name}" in text, f"CLAUDE.md does not link {note.name}"


def test_every_area_note_points_back_and_says_when_to_read_it() -> None:
    for note in sorted(AGENT.glob("*.md")):
        head = note.read_text(encoding="utf-8").split("\n## ", 1)[0]
        assert "(../../../CLAUDE.md)" in head, f"{note.name} does not link back to CLAUDE.md"
        assert "Read them when" in head, f"{note.name} does not say when to read it"
