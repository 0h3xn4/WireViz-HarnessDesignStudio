"""Identifier rules. IDs become file names and appear on drawings, so they are conservative."""

import re
from typing import Annotated

from pydantic import AfterValidator, Field

ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.\-]{0,63}$")
PIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,15}$")
# Device names Windows refuses as file names (with any extension).
RESERVED = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)


def check_id(value: str) -> str:
    if not ID_RE.fullmatch(value):
        raise ValueError(
            "must start with a letter and contain only letters, digits, '_', '-' or '.' "
            "(max 64 characters)"
        )
    if value.endswith("."):
        raise ValueError("must not end with a dot")
    if value.split(".")[0].casefold() in RESERVED:
        raise ValueError("is a reserved name on Windows and cannot be used")
    return value


def check_pin_id(value: str) -> str:
    if not PIN_RE.fullmatch(value) or value.endswith("."):
        raise ValueError("pin names use letters, digits, '_', '-' or '.' (max 16 characters)")
    return value


# The pattern is only for the JSON Schemas (editors); the validators above do the checking and
# give the plain-language messages.
Id = Annotated[str, AfterValidator(check_id), Field(json_schema_extra={"pattern": ID_RE.pattern})]
PinId = Annotated[
    str, AfterValidator(check_pin_id), Field(json_schema_extra={"pattern": PIN_RE.pattern})
]


def _maybe_id(value: str) -> str:
    return check_id(value) if value else value


# An ID that may be empty (an optional reference that is left out of the files while empty).
MaybeId = Annotated[str, AfterValidator(_maybe_id)]
