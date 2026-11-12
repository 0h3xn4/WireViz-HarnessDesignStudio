# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Canonical JSON: the same data always yields the same bytes (sorted keys, fixed layout)."""

import json
import re
from array import array
from itertools import accumulate
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


MAX_NESTING = 1000
"""How deeply a file may nest lists and objects. Python up to 3.13 stopped the parser at about this
depth with a `RecursionError`; 3.14 reads far deeper, so the limit is checked here (a real project
file nests about ten levels)."""

_STRINGS = re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"')
_NOT_BRACKETS = re.compile(r"[^\[\]{}]+")
_BRACKET_STEPS = bytes.maketrans(
    b"[{]}", b"\x01\x01\xff\xff"
)  # +1 opens, -1 (as a signed byte) closes


def _deepest(brackets: str) -> int:
    steps = array("b", brackets.encode("ascii").translate(_BRACKET_STEPS))
    return max(accumulate(steps), default=0)


def _nested_too_deeply(text: str) -> bool:
    """True when `text` nests lists and objects deeper than `MAX_NESTING`. The cheap count of all
    brackets comes first; brackets inside strings are only taken out when the quick count says the
    file may be too deep."""
    if text.count("[") + text.count("{") <= MAX_NESTING:
        return False
    if _deepest(_NOT_BRACKETS.sub("", text)) <= MAX_NESTING:
        return False
    return _deepest(_NOT_BRACKETS.sub("", _STRINGS.sub("", text))) > MAX_NESTING


def loads_strict(data: bytes) -> Any:
    """Parse UTF-8 JSON, rejecting duplicate keys (silent data loss), NaN/Infinity and files that
    nest deeper than `MAX_NESTING` (`RecursionError`, as the parser raised before Python 3.14)."""
    text = data.decode("utf-8")  # UnicodeDecodeError is a ValueError
    if text.startswith("﻿"):
        text = text[1:]
    if _nested_too_deeply(text):
        raise RecursionError("the file nests lists and objects too deeply")
    parsed = json.loads(
        text,
        object_pairs_hook=_no_duplicates,
        parse_constant=_no_constants,
        parse_float=_finite_float,
    )
    _reject_lone_surrogates(parsed)
    return parsed


# ---- one object per line (`journal.jsonl`, M7a, D-228) ------------------------------------------


def dumps_line(data: Any) -> bytes:
    """One object as one line of canonical JSON: sorted keys, no spaces, no line break inside, the
    text as it is (not escaped to ASCII), ending in a line feed. The same object gives the same
    bytes, so a line written once is never written differently."""
    text = json.dumps(
        data, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )
    try:
        return (text + "\n").encode("utf-8")
    except UnicodeEncodeError:  # a lone surrogate: not text, cannot be stored
        raise SaveError(
            "The project contains a character that is not valid text (a lone surrogate), "
            "so it cannot be written. Remove or replace that text."
        ) from None


def loads_lines(data: bytes, key: str) -> dict[str, list[Any]]:
    """A file of one JSON value per line, read as `{key: [value, ...]}` in the order of the lines,
    with the rules of `loads_strict` for each line. Empty lines are skipped, and so is a carriage
    return at the end of a line (a Git checkout on Windows may add one). A line that is not valid
    JSON raises `json.JSONDecodeError` with the line and column in the whole file."""
    text = data.decode("utf-8")  # UnicodeDecodeError is a ValueError
    if text.startswith("﻿"):
        text = text[1:]
    values: list[Any] = []
    offset = 0
    for line in text.split("\n"):
        start, offset = offset, offset + len(line) + 1
        bare = line.removesuffix("\r")
        if not bare.strip():
            continue
        try:
            values.append(loads_strict(bare.encode("utf-8")))
        except json.JSONDecodeError as exc:
            raise json.JSONDecodeError(exc.msg, text, start + exc.pos) from None
    return {key: values}
