"""Canonical JSON: the same data always yields the same bytes (sorted keys, fixed layout)."""

import json
import re
from typing import Any

from harness_design_studio.core.errors import SaveError


def dumps(data: Any) -> bytes:
    text = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
    try:
        return (text + "\n").encode("utf-8")
    except UnicodeEncodeError:  # a lone surrogate: not text, cannot be stored
        raise SaveError(
            "The project contains a character that is not valid text (a lone surrogate), "
            "so it cannot be written. Remove or replace that text."
        ) from None


class DuplicateKeyError(ValueError):
    pass


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"key '{key}' appears twice in the same object")
        result[key] = value
    return result


class LoneSurrogateError(ValueError):
    pass


_SURROGATE = re.compile("[\ud800-\udfff]")


def _reject_lone_surrogates(data: Any) -> None:
    """A "\\ud800" escape without its partner is not text: it cannot be written back as UTF-8."""
    todo = [data]
    while todo:
        item = todo.pop()
        if isinstance(item, str):
            if _SURROGATE.search(item):
                raise LoneSurrogateError("the file contains a lone surrogate escape")
        elif isinstance(item, dict):
            todo.extend(item.keys())
            todo.extend(item.values())
        elif isinstance(item, list):
            todo.extend(item)


def _no_constants(name: str) -> Any:
    raise ValueError(f"'{name}' is not valid JSON")


def _finite_float(text: str) -> float:
    value = float(text)
    if value in (float("inf"), float("-inf")) or value != value:
        raise ValueError("a number is too large to store")  # e.g. 1e999 would read back as infinity
    return value


def loads_strict(data: bytes) -> Any:
    """Parse UTF-8 JSON, rejecting duplicate keys (silent data loss) and NaN/Infinity."""
    text = data.decode("utf-8")  # UnicodeDecodeError is a ValueError
    if text.startswith("﻿"):
        text = text[1:]
    parsed = json.loads(
        text,
        object_pairs_hook=_no_duplicates,
        parse_constant=_no_constants,
        parse_float=_finite_float,
    )
    _reject_lone_surrogates(parsed)
    return parsed
