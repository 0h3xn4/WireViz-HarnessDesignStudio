"""Command-line interface to the core."""


def blocked_text(exc: Exception) -> str:
    """A refused change as the message and, one per line, the reasons the model gave."""
    problems = getattr(exc, "problems", [])
    return "\n".join([f"error: {exc}", *(f"  - {p}" for p in problems)])
