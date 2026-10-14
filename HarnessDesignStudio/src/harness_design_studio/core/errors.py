"""Explicit error types. Messages are plain language and never contain design data values."""


class HarnessError(Exception):
    """Base class for all expected errors raised by the core."""


class LoadError(HarnessError):
    """The project folder cannot be opened at all (not a project, not a folder, unreadable)."""


class SaveError(HarnessError):
    """The project could not be written; the previous files are left intact."""


class ProjectLockedError(HarnessError):
    """The project is already open in another running instance."""


class TransactionError(HarnessError):
    """A change was rejected and rolled back because it would leave the model inconsistent."""

    def __init__(self, message: str, problems: list[str] | None = None) -> None:
        super().__init__(message)
        self.problems = problems or []
