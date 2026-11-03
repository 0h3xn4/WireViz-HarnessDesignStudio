"""The format of a declarative extension file: one description that both checks a file and writes
its JSON Schema (`harness-design-studio schema DIR` exports it as `extension.schema.json`), so the
schema an editor shows and the check the tool makes cannot disagree.

This module checks the *shape* of a file (keys, types, ranges, names). What an expression means
(a field that exists, a lookup table that is defined) is checked by `declarative.py`.
"""

import re
from dataclasses import dataclass, field

from .jsonpos import Located, Path

FORMAT = "harness-design-studio-extension"
FORMAT_VERSION = 1
NAME_PATTERN = r"^[a-z][a-z0-9_-]{0,47}$"
SEVERITIES = ("error", "warning", "info")
APPLIES_TO = ("wire", "connector", "interface", "harness")
LOOKUP_MODES = ("exact", "next_up", "next_down", "interpolate")


@dataclass(frozen=True)
class S:
    """The description of one value."""

    type: str  # object list map text number whole bool enum scalar expr
    doc: str = ""
    required: bool = False
    props: tuple[tuple[str, S], ...] = ()  # for an object
    item: S | None = None  # for a list, and for the values of a map
    choices: tuple[str, ...] = ()
    pattern: str = ""
    max_len: int = 400
    min_items: int = 0
    max_items: int = 200
    const: object = None
    key_pattern: str = ""  # for a map: what its keys look like
    empty_ok: bool = False  # a text that may be left empty (a unit that has none)

    def prop(self, name: str) -> S | None:
        return dict(self.props).get(name)


def _req(s: S) -> S:
    return S(**{**s.__dict__, "required": True})


NAME = S("text", "A name: lower-case letters, digits, '-' and '_'.", pattern=NAME_PATTERN)
SENTENCE = S("text", max_len=600, empty_ok=True)

PARAMETER = S(
    "object",
    "A named value of the extension, used in expressions as param('name'). Give its unit and where the number comes from.",
    props=(
        ("value", _req(S("scalar", "A number, a text or true or false."))),
        ("unit", S("text", "The unit, for the explanation.", max_len=40, empty_ok=True)),
        (
            "source",
            S(
                "text",
                "Where the number comes from (a standard, a requirement, a decision).",
                max_len=300,
                empty_ok=True,
            ),
        ),
        ("description", SENTENCE),
    ),
)

LOOKUP = S(
    "object",
    "A table of values an expression can look up with lookup('name', key).",
    props=(
        ("name", _req(NAME)),
        ("description", SENTENCE),
        (
            "key",
            S(
                "text",
                "What the key is (for the explanation), for example 'AWG gauge'.",
                max_len=80,
                empty_ok=True,
            ),
        ),
        ("unit", S("text", "The unit of the values.", max_len=40, empty_ok=True)),
        ("source", S("text", "Where the values come from.", max_len=300, empty_ok=True)),
        (
            "mode",
            S(
                "enum",
                "exact: the key must be in the table; next_up: the first listed key at or above it; next_down: the last listed key at or below it; interpolate: a straight line between the two neighbours (numbers only).",
                choices=LOOKUP_MODES,
            ),
        ),
        (
            "values",
            _req(
                S(
                    "map",
                    "Key to value. Keys are written as text; numbers are read as numbers.",
                    item=S("number"),
                    max_items=500,
                    key_pattern=r"^[A-Za-z0-9_.+-]{1,40}$",
                )
            ),
        ),
    ),
)

RULE = S(
    "object",
    "A design rule. It applies to every object of `applies_to` where `when` is true (or to every object when there is no `when`) and finds a problem where `condition` is false.",
    props=(
        ("id", _req(NAME)),
        ("title", _req(S("text", "The short name shown in the report.", max_len=80))),
        (
            "severity",
            _req(
                S(
                    "enum",
                    "error: the design is wrong; warning: it should be looked at (can be waived); info: a note.",
                    choices=SEVERITIES,
                )
            ),
        ),
        (
            "applies_to",
            _req(S("enum", "The kind of object the rule runs over.", choices=APPLIES_TO)),
        ),
        ("when", S("expr", "Only objects for which this is true are checked.")),
        (
            "condition",
            _req(
                S(
                    "expr",
                    "What must be true. A comparison such as wire.gauge_awg <= param('max_awg') gives the actual value, the limit and the margin of the finding.",
                )
            ),
        ),
        (
            "message",
            _req(
                S(
                    "text",
                    "The statement of one problem. May use {object} {actual} {limit} {margin} {over} {unit} and {scope.field}.",
                    max_len=300,
                )
            ),
        ),
        ("why", _req(S("text", "Why it matters.", max_len=600))),
        ("how", _req(S("text", "How to fix it by hand.", max_len=600))),
        (
            "unit",
            S(
                "text",
                "The unit of actual and limit, for the message and the explanation.",
                max_len=40,
                empty_ok=True,
            ),
        ),
        (
            "requirements",
            S(
                "list",
                "IDs of the requirements the rule serves.",
                item=S("text", max_len=80),
                max_items=20,
            ),
        ),
        ("waivable", S("bool", "Whether a finding can be waived (by default only a warning can).")),
    ),
)

COLUMN = S(
    "object",
    "A column of a table.",
    props=(
        ("header", _req(S("text", "The heading.", max_len=60))),
        ("value", _req(S("expr", "What the cell shows."))),
        ("unit", S("text", "The unit, written after the heading.", max_len=40, empty_ok=True)),
    ),
)

TABLE = S(
    "object",
    "An output table. `export` writes it as system/extensions/<name>.csv with one row for every object of `applies_to` for which `where` is true.",
    props=(
        ("name", _req(NAME)),
        ("title", _req(S("text", "What the table is for.", max_len=120))),
        ("applies_to", _req(S("enum", "The kind of object a row is for.", choices=APPLIES_TO))),
        ("where", S("expr", "Only objects for which this is true get a row.")),
        ("sort", S("expr", "Rows are sorted by this value, then by the order of the design.")),
        (
            "columns",
            _req(S("list", "The columns, left to right.", item=COLUMN, min_items=1, max_items=40)),
        ),
    ),
)

FILE = S(
    "object",
    "An extension file of a project: rules, tables and lookup tables written as data. Nothing in it is a program.",
    props=(
        ("format", _req(S("text", "Always " + FORMAT + ".", const=FORMAT))),
        ("format_version", _req(S("whole", "Always 1.", const=FORMAT_VERSION))),
        ("name", _req(NAME)),
        (
            "version",
            _req(S("text", "The version of this extension file, as you number it.", max_len=40)),
        ),
        ("description", SENTENCE),
        (
            "parameters",
            S(
                "map",
                "Named values the expressions use.",
                item=PARAMETER,
                max_items=100,
                key_pattern=NAME_PATTERN,
            ),
        ),
        ("lookups", S("list", "Lookup tables.", item=LOOKUP, max_items=50)),
        ("rules", S("list", "Design rules.", item=RULE, max_items=100)),
        ("tables", S("list", "Output tables.", item=TABLE, max_items=50)),
    ),
)

ENABLED = S(
    "object",
    "Which extensions this project uses. Nothing in the extensions folder runs unless it is listed here.",
    props=(
        (
            "format",
            _req(
                S(
                    "text",
                    "Always harness-design-studio-extensions-enabled.",
                    const="harness-design-studio-extensions-enabled",
                )
            ),
        ),
        ("format_version", _req(S("whole", "Always 1.", const=1))),
        (
            "declarative",
            S(
                "list",
                "File names in the extensions folder (for example min-gauge.json).",
                item=S("text", max_len=120),
                max_items=200,
            ),
        ),
        (
            "plugins",
            S(
                "list",
                "Names of Python plug-ins. A plug-in also needs to be trusted on this computer before it is loaded.",
                item=S("text", max_len=80),
                max_items=100,
            ),
        ),
    ),
)
ENABLED_FORMAT = "harness-design-studio-extensions-enabled"


# ---- the check ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Problem:
    path: Path
    key: str
    message: str


@dataclass
class Checked:
    problems: list[Problem] = field(default_factory=list)

    def add(self, path: Path, key: str, message: str) -> None:
        self.problems.append(Problem(path, key, message))


def show_path(path: Path) -> str:
    out = ""
    for p in path:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else str(p))
    return out or "(the file)"


def _kind(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true or false"
    if isinstance(value, int | float):
        return "a number"
    if isinstance(value, str):
        return "a text"
    if isinstance(value, list):
        return "a list"
    return "an object"


def check(spec: S, value: object, path: Path = ()) -> list[Problem]:
    """Every way `value` departs from `spec`, each with the path and the key."""
    out = Checked()
    _check(spec, value, path, out)
    return out.problems


def _check(spec: S, value: object, path: Path, out: Checked) -> None:
    key = str(path[-1]) if path else ""
    t = spec.type
    if t == "object":
        if not isinstance(value, dict):
            out.add(path, key, f"expected an object, found {_kind(value)}")
            return
        known = dict(spec.props)
        for name in value:
            if name not in known:
                hint = _closest(name, list(known))
                out.add((*path, name), name, f"unknown key '{name}'" + hint)
        for name, sub in spec.props:
            if name in value:
                _check(sub, value[name], (*path, name), out)
            elif sub.required:
                out.add((*path, name), name, f"the key '{name}' is required")
    elif t == "list":
        if not isinstance(value, list):
            out.add(path, key, f"expected a list, found {_kind(value)}")
            return
        if len(value) < spec.min_items:
            out.add(path, key, f"needs at least {spec.min_items} item(s)")
        if len(value) > spec.max_items:
            out.add(path, key, f"has more than {spec.max_items} items")
        for n, item in enumerate(value[: spec.max_items]):
            if spec.item is not None:
                _check(spec.item, item, (*path, n), out)
    elif t == "map":
        if not isinstance(value, dict):
            out.add(path, key, f"expected an object, found {_kind(value)}")
            return
        if len(value) > spec.max_items:
            out.add(path, key, f"has more than {spec.max_items} entries")
        for k, item in list(value.items())[: spec.max_items]:
            if spec.key_pattern and not re.match(spec.key_pattern, k):
                out.add(
                    (*path, k),
                    k,
                    f"'{k}' is not an acceptable name here (pattern {spec.key_pattern})",
                )
            if spec.item is not None:
                _check(spec.item, item, (*path, k), out)
    elif t in ("text", "expr", "enum"):
        if not isinstance(value, str):
            out.add(path, key, f"expected a text, found {_kind(value)}")
        elif not value.strip() and not spec.empty_ok:
            out.add(path, key, "must not be empty")
        elif len(value) > spec.max_len and t != "expr":
            out.add(path, key, f"is longer than {spec.max_len} characters")
        elif any(ord(c) < 32 for c in value):
            out.add(path, key, "must not contain control characters")
        elif t == "enum" and value not in spec.choices:
            out.add(
                path,
                key,
                f"'{value}' is not one of {', '.join(spec.choices)}"
                + _closest(value, list(spec.choices)),
            )
        elif spec.pattern and not re.match(spec.pattern, value):
            out.add(
                path,
                key,
                f"'{value}' is not an acceptable name: lower-case letters, digits, '-' and '_', starting with a letter, at most 48 characters",
            )
        elif spec.const is not None and value != spec.const:
            out.add(path, key, f"must be '{spec.const}'")
    elif t in ("number", "whole"):
        ok = isinstance(value, int | float) and not isinstance(value, bool)
        if not ok:
            out.add(path, key, f"expected a number, found {_kind(value)}")
        elif t == "whole" and value != int(value):  # type: ignore[call-overload]
            out.add(path, key, "expected a whole number")
        elif spec.const is not None and value != spec.const:
            out.add(path, key, f"must be {spec.const}")
    elif t == "bool":
        if not isinstance(value, bool):
            out.add(path, key, f"expected true or false, found {_kind(value)}")
    elif t == "scalar":
        if value is None or isinstance(value, list | dict):
            out.add(path, key, f"expected a number, a text or true or false, found {_kind(value)}")
        elif isinstance(value, str) and len(value) > 200:
            out.add(path, key, "is longer than 200 characters")


def _closest(word: str, choices: list[str]) -> str:
    import difflib

    hit = difflib.get_close_matches(word, choices, n=1, cutoff=0.6)
    return f" (did you mean '{hit[0]}'?)" if hit else ""


def check_located(spec: S, doc: Located) -> list[tuple[int, Problem]]:
    """The problems with the line of each."""
    return [(doc.line_of(p.path) or 1, p) for p in check(spec, doc.value)]


# ---- the JSON Schema ------------------------------------------------------------------------------


def json_schema(spec: S, *, title: str = "", top: bool = True) -> dict[str, object]:
    out: dict[str, object] = {}
    if top:
        out["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        out["title"] = title
    if spec.doc:
        out["description"] = spec.doc
    t = spec.type
    if t == "object":
        out["type"] = "object"
        out["additionalProperties"] = False
        out["properties"] = {n: json_schema(s, top=False) for n, s in spec.props}
        required = [n for n, s in spec.props if s.required]
        if required:
            out["required"] = required
    elif t == "list":
        out["type"] = "array"
        out["items"] = json_schema(spec.item, top=False) if spec.item is not None else {}
        if spec.min_items:
            out["minItems"] = spec.min_items
        out["maxItems"] = spec.max_items
    elif t == "map":
        out["type"] = "object"
        out["additionalProperties"] = (
            json_schema(spec.item, top=False) if spec.item is not None else True
        )
        if spec.key_pattern:
            out["propertyNames"] = {"pattern": spec.key_pattern}
    elif t == "enum":
        out["type"] = "string"
        out["enum"] = list(spec.choices)
    elif t in ("text", "expr"):
        out["type"] = "string"
        out["minLength"] = 0 if spec.empty_ok else 1
        if t == "text":
            out["maxLength"] = spec.max_len
        if spec.pattern:
            out["pattern"] = spec.pattern
        if spec.const is not None:
            out["const"] = spec.const
        if t == "expr":
            out["description"] = (
                spec.doc + " " if spec.doc else ""
            ) + "An expression of the extension language (see docs/developer/extensions.md)."
    elif t == "number":
        out["type"] = "number"
    elif t == "whole":
        out["type"] = "integer"
        if spec.const is not None:
            out["const"] = spec.const
    elif t == "bool":
        out["type"] = "boolean"
    elif t == "scalar":
        out["type"] = ["number", "string", "boolean"]
    return out


def schemas() -> dict[str, dict[str, object]]:
    """The JSON Schemas of the two files of an extensions folder, by name."""
    return {
        "extension": json_schema(FILE, title="extension"),
        "extensions-enabled": json_schema(ENABLED, title="extensions-enabled"),
    }
