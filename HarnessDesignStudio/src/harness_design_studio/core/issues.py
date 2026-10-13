"""Findings reported by loading, integrity checking and `harness validate`/`check`."""

from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True, order=True)
class Issue:
    severity: Severity
    code: str
    message: str
    location: str | None = None  # project-relative file path, if the issue belongs to a file
    object_id: str | None = None

    def key(self) -> tuple[str, str, str | None, str | None]:
        """Identity used to compare issue sets before and after a change."""
        return (self.severity, self.code, self.location, self.object_id)

    def render(self) -> str:
        where = f" [{self.location}]" if self.location else ""
        return f"{self.severity.upper():7} {self.code}: {self.message}{where}"


def errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "error"]
