# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""A JSON reader that remembers on which line each key and each list item is.

The standard library's reader tells where a file is broken but not where a value is, and a
message about an extension file has to say "line 14, `rules[0].condition`". This reader accepts
exactly standard JSON (no comments, no trailing commas, no `NaN`), refuses a key that appears twice
in one object, and gives for every path of the document the line of its key (or of the list item).
"""

from dataclasses import dataclass, field

MAX_DEPTH = 40

type Path = tuple[str | int, ...]


class JsonSyntaxError(ValueError):
    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


@dataclass
class Located:
    value: object
    lines: dict[Path, int] = field(default_factory=dict)

    def line_of(self, path: Path) -> int | None:
        """The line of the key or item at `path`, else of the nearest parent that has one."""
        probe = path
        while True:
            if probe in self.lines:
                return self.lines[probe]
            if not probe:
                return 1
            probe = probe[:-1]


_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
_NUMBER_CHARS = frozenset("+-0123456789.eE")


class _Reader:
    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.lines: dict[Path, int] = {}

    # -- positions
    def line(self, pos: int | None = None) -> int:
        return self.text.count("\n", 0, self.pos if pos is None else pos) + 1

    def fail(self, message: str, pos: int | None = None) -> JsonSyntaxError:
        at = self.pos if pos is None else pos
        column = at - (self.text.rfind("\n", 0, at) + 1) + 1
        return JsonSyntaxError(message, self.line(at), column)

    # -- grammar
    def skip(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t\r\n":
            self.pos += 1

    def value(self, path: Path, depth: int) -> object:
        if depth > MAX_DEPTH:
            raise self.fail("the file is nested too deeply")
        self.skip()
        if self.pos >= len(self.text):
            raise self.fail("the file ends before a value")
        ch = self.text[self.pos]
        if ch == "{":
            return self.obj(path, depth)
        if ch == "[":
            return self.array(path, depth)
        if ch == '"':
            return self.string()
        for word, val in (("true", True), ("false", False), ("null", None)):
            if self.text.startswith(word, self.pos):
                self.pos += len(word)
                return val
        if ch in "-0123456789":
            return self.number()
        raise self.fail(f"unexpected character {ch!r}")

    def number(self) -> int | float:
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] in _NUMBER_CHARS:
            self.pos += 1
        raw = self.text[start : self.pos]
        try:
            if any(c in raw for c in ".eE"):
                number: int | float = float(raw)
            else:
                if raw.startswith("0") and len(raw) > 1 or raw.startswith("-0") and len(raw) > 2:
                    raise ValueError(raw)
                number = int(raw)
        except ValueError:
            raise self.fail(f"{raw!r} is not a number", start) from None
        if (
            isinstance(number, float)
            and number != number
            or number in (float("inf"), float("-inf"))
        ):
            raise self.fail(f"{raw!r} is not a finite number", start)
        return number

    def string(self) -> str:
        start = self.pos
        self.pos += 1
        out: list[str] = []
        while True:
            if self.pos >= len(self.text):
                raise self.fail("a text is not closed", start)
            ch = self.text[self.pos]
            if ch == '"':
                self.pos += 1
                return "".join(out)
            if ch == "\n":
                raise self.fail("a text runs over the end of the line", start)
            if ch == "\\":
                self.pos += 1
                esc = self.text[self.pos : self.pos + 1]
                if esc in _ESCAPES:
                    out.append(_ESCAPES[esc])
                    self.pos += 1
                elif esc == "u":
                    hexa = self.text[self.pos + 1 : self.pos + 5]
                    try:
                        code = int(hexa, 16) if len(hexa) == 4 else -1
                    except ValueError:
                        code = -1
                    if code < 0 or 0xD800 <= code <= 0xDFFF:
                        raise self.fail("a text escape \\u is not valid")
                    out.append(chr(code))
                    self.pos += 5
                else:
                    raise self.fail("a text escape is not valid")
            else:
                out.append(ch)
                self.pos += 1

    def obj(self, path: Path, depth: int) -> dict[str, object]:
        self.pos += 1
        result: dict[str, object] = {}
        self.skip()
        if self.text[self.pos : self.pos + 1] == "}":
            self.pos += 1
            return result
        while True:
            self.skip()
            if self.text[self.pos : self.pos + 1] != '"':
                raise self.fail("a key (a text in double quotes) was expected")
            key_at = self.pos
            key = self.string()
            if key in result:
                raise self.fail(f"the key {key!r} is there twice in one object", key_at)
            self.lines[(*path, key)] = self.line(key_at)
            self.skip()
            if self.text[self.pos : self.pos + 1] != ":":
                raise self.fail("a colon was expected after the key")
            self.pos += 1
            result[key] = self.value((*path, key), depth + 1)
            self.skip()
            nxt = self.text[self.pos : self.pos + 1]
            self.pos += 1
            if nxt == "}":
                return result
            if nxt != ",":
                self.pos -= 1
                raise self.fail("a comma or a closing brace was expected")

    def array(self, path: Path, depth: int) -> list[object]:
        self.pos += 1
        items: list[object] = []
        self.skip()
        if self.text[self.pos : self.pos + 1] == "]":
            self.pos += 1
            return items
        while True:
            self.skip()
            self.lines[(*path, len(items))] = self.line()
            items.append(self.value((*path, len(items)), depth + 1))
            self.skip()
            nxt = self.text[self.pos : self.pos + 1]
            self.pos += 1
            if nxt == "]":
                return items
            if nxt != ",":
                self.pos -= 1
                raise self.fail("a comma or a closing bracket was expected")


def loads(text: str) -> Located:
    """The document and the line of every key and item; `JsonSyntaxError` when it is not JSON."""
    reader = _Reader(text.removeprefix("﻿"))
    value = reader.value((), 0)
    reader.skip()
    if reader.pos < len(reader.text):
        raise reader.fail("there is more after the end of the document")
    return Located(value, reader.lines)
