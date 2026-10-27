"""Command-line interface to the core."""


def blocked_text(exc: Exception) -> str:
    """A refused change as the message and, one per line, the reasons the model gave."""
    problems = getattr(exc, "problems", [])
    return "\n".join([f"error: {exc}", *(f"  - {p}" for p in problems)])


_NEEDS_QUOTES = frozenset("\"'`$&|;<>()*?[]{}!")


def quoted(path: object) -> str:
    """A path as it is typed in a command: in double quotes when it holds a space or a character a
    shell would split or expand, so that a hint can be pasted as it is."""
    text = str(path)
    if text and not any(c.isspace() or c in _NEEDS_QUOTES for c in text):
        return text
    return '"' + text.replace('"', '\\"') + '"'
