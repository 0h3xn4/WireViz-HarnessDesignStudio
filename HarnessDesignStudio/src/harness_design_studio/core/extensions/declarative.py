# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Declarative extensions: rules, tables and lookup tables written as data (D-191 (5), S8).

`read_file` turns the bytes of one `extensions/*.json` file into an `ExtFile`: it checks the shape
(`schema.py`), reads every expression with the hand-written parser (`expr.py`) against the fields
that exist, and reports every problem with the file, the line, the path and the key. A file with a
problem is not applied at all (half a rule is worse than none) and the problem is listed by
`validate`, `extensions` and the Help page; it never stops generation or the other files.

`DeclRule` runs a rule over the objects of a project and explains it, `build_table` makes a table,
and `lookup_value` reads a lookup table. None of this runs anything but the tool's own code: the
file is data.
"""

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from harness_design_studio.core import settings as settings_mod
from harness_design_studio.core.derive import Check, Derivation, Input, Step, _g
from harness_design_studio.core.drc.base import Hit, Rule
from harness_design_studio.core.generate.sizing import exceeds
from harness_design_studio.core.issues import Severity
from harness_design_studio.core.model import Project
from harness_design_studio.core.outputs.tables import data_num

from . import expr
from . import fields as fields_mod
from .fields import Context, FieldDef
from .jsonpos import JsonSyntaxError, Located
from .jsonpos import loads as load_located
from .schema import FILE, FORMAT, Problem, check, show_path

PREFIX = "x-"
PLACEHOLDERS = ("object", "actual", "limit", "margin", "over", "unit", "rule", "title")
_BRACES = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.]*)\}")


@dataclass(frozen=True)
class ExtIssue:
    """One problem in an extension, worded so that it can be found: the file, the line, the path
    inside the file and the key."""

    severity: str  # "error" | "warning"
    file: str
    line: int
    path: str
    message: str

    def render(self) -> str:
        where = f"{self.file}:{self.line}" if self.line else self.file
        return f"{where}: {self.path}: {self.message}" if self.path else f"{where}: {self.message}"

    def to_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class Param:
    name: str
    value: object
    unit: str = ""
    source: str = ""
    description: str = ""


@dataclass(frozen=True)
class Lookup:
    name: str
    mode: str
    points: tuple[tuple[str, float], ...]  # (key as written, value)
    key: str = ""
    unit: str = ""
    source: str = ""
    description: str = ""


@dataclass(frozen=True)
class RuleSpec:
    id: str  # with the prefix x-
    title: str
    severity: Severity
    applies_to: str
    condition: expr.Node
    when: expr.Node | None
    message: str
    why: str
    how: str
    unit: str
    requirements: tuple[str, ...]
    waivable: bool | None
    file: str  # "extensions/min-gauge.json"
    version: str
    sha256: str
    line: int


@dataclass(frozen=True)
class ColumnSpec:
    header: str
    value: expr.Node
    unit: str = ""


@dataclass(frozen=True)
class TableSpec:
    name: str
    title: str
    applies_to: str
    columns: tuple[ColumnSpec, ...]
    where: expr.Node | None
    sort: expr.Node | None
    file: str
    version: str
    sha256: str


@dataclass(frozen=True)
class ExtFile:
    rel: str
    name: str
    version: str
    description: str
    sha256: str
    params: tuple[Param, ...] = ()
    lookups: tuple[Lookup, ...] = ()
    rules: tuple[RuleSpec, ...] = ()
    tables: tuple[TableSpec, ...] = ()

    def param(self, name: str) -> Param | None:
        return next((p for p in self.params if p.name == name), None)

    def lookup(self, name: str) -> Lookup | None:
        return next((p for p in self.lookups if p.name == name), None)


# ---- reading a file --------------------------------------------------------------------------------


def _at(
    rel: str, doc: Located, path: tuple[str | int, ...], message: str, severity: str = "error"
) -> ExtIssue:
    return ExtIssue(severity, rel, doc.line_of(path) or 1, show_path(path), message)


def _field_vocabulary(applies_to: str, defs: Sequence[FieldDef]) -> frozenset[str]:
    return fields_mod.vocabulary_fields(applies_to, defs)


def read_file(
    rel: str, data: bytes, sha256: str, defs: Sequence[FieldDef]
) -> tuple[ExtFile | None, list[ExtIssue]]:
    """The file, or None when it has a problem; every problem found, in file order."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, [
            ExtIssue("error", rel, 1, "", f"the file is not UTF-8 text (byte {exc.start})")
        ]
    try:
        doc = load_located(text)
    except JsonSyntaxError as exc:
        return None, [
            ExtIssue(
                "error", rel, exc.line, "", f"not valid JSON at column {exc.column}: {exc.message}"
            )
        ]
    except RecursionError:
        return None, [ExtIssue("error", rel, 1, "", "the file is nested too deeply")]
    issues = [
        ExtIssue("error", rel, doc.line_of(p.path) or 1, show_path(p.path), p.message)
        for p in check(FILE, doc.value)
    ]
    if issues:
        return None, sorted(issues, key=lambda i: (i.line, i.path))
    root = doc.value
    if not isinstance(root, dict):  # (the shape check has refused anything else)
        return None, issues
    root = cast(dict[str, Any], root)
    issues = _semantics(rel, doc, root, sha256, defs)
    if any(i.severity == "error" for i in issues):
        return None, sorted(issues, key=lambda i: (i.line, i.path))
    return _build(rel, root, sha256, defs), []


def _semantics(
    rel: str, doc: Located, root: dict[str, Any], sha: str, defs: Sequence[FieldDef]
) -> list[ExtIssue]:
    out: list[ExtIssue] = []

    def add(path: tuple[str | int, ...], message: str) -> None:
        out.append(_at(rel, doc, path, message))

    params = set(root.get("parameters", {}))
    lookups: set[str] = set()
    for n, lk in enumerate(root.get("lookups", [])):
        if lk["name"] in lookups:
            add(
                ("lookups", n, "name"),
                f"the lookup table '{lk['name']}' is defined twice in this file",
            )
        lookups.add(lk["name"])
        out += _lookup_problems(rel, doc, n, lk)
    seen: set[str] = set()
    for n, rule in enumerate(root.get("rules", [])):
        rid = _rule_id(rule["id"])
        if rid in seen:
            add(("rules", n, "id"), f"the rule '{rule['id']}' is defined twice in this file")
        seen.add(rid)
        out += _rule_problems(rel, doc, n, rule, params, lookups, defs)
    names: set[str] = set()
    for n, table in enumerate(root.get("tables", [])):
        if table["name"] in names:
            add(("tables", n, "name"), f"the table '{table['name']}' is defined twice in this file")
        names.add(table["name"])
        out += _table_problems(rel, doc, n, table, params, lookups, defs)
    return out


def _rule_id(local: str) -> str:
    return local if local.startswith(PREFIX) else PREFIX + local


def _vocab(
    applies_to: str, params: set[str], lookups: set[str], defs: Sequence[FieldDef]
) -> expr.Vocabulary:
    from .fields import known_settings

    return expr.Vocabulary(
        _field_vocabulary(applies_to, defs), known_settings(), frozenset(params), frozenset(lookups)
    )


def _parse(
    rel: str, doc: Located, path: tuple[str | int, ...], text: str, vocab: expr.Vocabulary
) -> tuple[expr.Node | None, list[ExtIssue]]:
    try:
        return expr.parse(text, vocab), []
    except expr.ExprError as exc:
        return None, [_at(rel, doc, path, f"column {exc.column}: {exc.message}")]


def _rule_problems(
    rel: str,
    doc: Located,
    n: int,
    rule: dict[str, Any],
    params: set[str],
    lookups: set[str],
    defs: Sequence[FieldDef],
) -> list[ExtIssue]:
    base: tuple[str | int, ...] = ("rules", n)
    applies = str(rule["applies_to"])
    vocab = _vocab(applies, params, lookups, defs)
    out: list[ExtIssue] = []
    for key in ("when", "condition"):
        if key in rule:
            _node, issues = _parse(rel, doc, (*base, key), str(rule[key]), vocab)
            out += issues
    allowed = set(PLACEHOLDERS) | set(vocab.fields)
    for key in ("message",):
        for name in _BRACES.findall(str(rule[key])):
            if name not in allowed:
                out.append(
                    _at(
                        rel,
                        doc,
                        (*base, key),
                        f"the placeholder {{{name}}} is not known (use {{object}}, {{actual}}, {{limit}}, {{margin}}, {{over}}, {{unit}}, {{rule}}, {{title}} or a field such as {{{next(iter(sorted(vocab.fields)), 'wire.id')}}})",
                    )
                )
    return out


def _table_problems(
    rel: str,
    doc: Located,
    n: int,
    table: dict[str, Any],
    params: set[str],
    lookups: set[str],
    defs: Sequence[FieldDef],
) -> list[ExtIssue]:
    base: tuple[str | int, ...] = ("tables", n)
    vocab = _vocab(str(table["applies_to"]), params, lookups, defs)
    out: list[ExtIssue] = []
    for key in ("where", "sort"):
        if key in table:
            out += _parse(rel, doc, (*base, key), str(table[key]), vocab)[1]
    for c, col in enumerate(table["columns"]):
        out += _parse(rel, doc, (*base, "columns", c, "value"), str(col["value"]), vocab)[1]
    return out


def _lookup_problems(rel: str, doc: Located, n: int, lk: dict[str, Any]) -> list[ExtIssue]:
    base: tuple[str | int, ...] = ("lookups", n)
    out: list[ExtIssue] = []
    values: dict[str, Any] = lk["values"]
    if not values:
        out.append(_at(rel, doc, (*base, "values"), "a lookup table needs at least one value"))
    mode = str(lk.get("mode", "exact"))
    if mode != "exact":
        for k in values:
            try:
                float(k)
            except ValueError:
                out.append(
                    _at(
                        rel,
                        doc,
                        (*base, "values", k),
                        f"the mode {mode} needs numbers as keys; '{k}' is not one",
                    )
                )
    return out


def _build(rel: str, root: dict[str, Any], sha: str, defs: Sequence[FieldDef]) -> ExtFile:
    version = str(root["version"])
    params = tuple(
        Param(name, p["value"], p.get("unit", ""), p.get("source", ""), p.get("description", ""))
        for name, p in sorted(root.get("parameters", {}).items())
    )
    lookups = tuple(
        Lookup(
            lk["name"],
            lk.get("mode", "exact"),
            tuple(
                sorted(
                    ((k, float(v)) for k, v in lk["values"].items()),
                    key=lambda kv: _sort_key(kv[0]),
                )
            ),
            lk.get("key", ""),
            lk.get("unit", ""),
            lk.get("source", ""),
            lk.get("description", ""),
        )  # fmt: skip
        for lk in root.get("lookups", [])
    )
    names_p = {p.name for p in params}
    names_l = {lk.name for lk in lookups}
    rules: list[RuleSpec] = []
    for n, r in enumerate(root.get("rules", [])):
        vocab = _vocab(r["applies_to"], names_p, names_l, defs)
        rules.append(
            RuleSpec(
                _rule_id(r["id"]),
                r["title"],
                r["severity"],
                r["applies_to"],
                expr.parse(r["condition"], vocab),
                expr.parse(r["when"], vocab) if "when" in r else None,
                r["message"],
                r["why"],
                r["how"],
                r.get("unit", ""),
                tuple(r.get("requirements", [])),
                r.get("waivable"),
                rel,
                version,
                sha,
                n,
            )  # fmt: skip
        )
    tables: list[TableSpec] = []
    for t in root.get("tables", []):
        vocab = _vocab(t["applies_to"], names_p, names_l, defs)
        tables.append(
            TableSpec(
                t["name"],
                t["title"],
                t["applies_to"],
                tuple(
                    ColumnSpec(c["header"], expr.parse(c["value"], vocab), c.get("unit", ""))
                    for c in t["columns"]
                ),
                expr.parse(t["where"], vocab) if "where" in t else None,
                expr.parse(t["sort"], vocab) if "sort" in t else None,
                rel,
                version,
                sha,
            )  # fmt: skip
        )
    return ExtFile(
        rel,
        str(root["name"]),
        version,
        str(root.get("description", "")),
        sha,
        params,
        lookups,
        tuple(rules),
        tuple(tables),
    )


def _sort_key(key: str) -> tuple[int, float, str]:
    try:
        return (0, float(key), key)
    except ValueError:
        return (1, 0.0, key)


# ---- the objects a rule or a table runs over ----------------------------------------------------------


def contexts(project: Project, applies_to: str) -> Iterator[tuple[str, Context]]:
    """(object id, context) for every object of the kind, in the order of the built-in rules: by ID."""
    if applies_to == "wire":
        for h in sorted(project.harnesses.values(), key=lambda x: x.id):
            for w in h.wires:
                yield w.id, Context(project, harness=h, wire=w)
    elif applies_to == "connector":
        for c in sorted(project.connectors.values(), key=lambda x: x.id):
            yield c.id, Context(project, connector=c)
        for h in sorted(project.harnesses.values(), key=lambda x: x.id):
            for c in h.connectors:
                yield c.id, Context(project, harness=h, connector=c)
    elif applies_to == "interface":
        for i in sorted(project.interfaces.values(), key=lambda x: x.id):
            yield i.id, Context(project, interface=i)
    else:
        for h in sorted(project.harnesses.values(), key=lambda x: x.id):
            yield h.id, Context(project, harness=h)


def context_of(project: Project, applies_to: str, object_id: str) -> Context | None:
    return next((c for oid, c in contexts(project, applies_to) if oid == object_id), None)


class ObjectEnv(expr.Env):
    """What an expression reads for one object: the fields of the object, the parameters and lookup
    tables of its file, the settings of the project."""

    def __init__(
        self, project: Project, ctx: Context, file: ExtFile, defs: dict[str, FieldDef]
    ) -> None:
        self.project, self.ctx, self.file, self.defs = project, ctx, file, defs
        self._memo: dict[str, expr.Value] = {}

    def field(self, scope: str, name: str) -> expr.Value:
        fid = f"{scope}.{name}"
        if fid not in self._memo:
            d = self.defs.get(fid)
            self._memo[fid] = None if d is None else _clean(d.fn(self.ctx))
        return self._memo[fid]

    def setting(self, name: str) -> expr.Value:
        return fields_mod.setting_value(self.project, name)

    def param(self, name: str) -> expr.Value:
        p = self.file.param(name)
        v = p.value if p is not None else None
        return v if v is None or isinstance(v, bool | int | float | str) else None

    def lookup(self, table: str, key: expr.Value) -> expr.Value:
        lk = self.file.lookup(table)
        return None if lk is None else lookup_value(lk, key)


def _clean(v: object) -> expr.Value:
    """A value a plug-in field returned, as a value of the language (anything else is not known)."""
    if v is None or isinstance(v, bool | int | float | str):
        return v
    return None


def lookup_value(lk: Lookup, key: expr.Value) -> expr.Value:
    """The value of a lookup table for a key, by its mode; None when the key is not covered."""
    if key is None or isinstance(key, bool):
        return None
    if isinstance(key, str):
        return next((v for k, v in lk.points if k == key), None)
    if not isinstance(key, int | float):
        return None
    numeric = [(float(k), v) for k, v in lk.points if _is_number(k)]
    x = float(key)
    exact = next((v for k, v in numeric if not exceeds(x, k) and not exceeds(k, x)), None)
    if exact is not None or lk.mode == "exact":
        return exact
    if lk.mode == "next_up":  # the first listed key at or above
        return next((v for k, v in numeric if not exceeds(x, k)), None)
    if lk.mode == "next_down":  # the last listed key at or below
        below = [v for k, v in numeric if not exceeds(k, x)]
        return below[-1] if below else None
    below_pts = [(k, v) for k, v in numeric if k < x]
    above_pts = [(k, v) for k, v in numeric if k > x]
    if not below_pts or not above_pts:
        return None  # interpolate: never beyond the table
    (k0, v0), (k1, v1) = below_pts[-1], above_pts[0]
    return v0 + (v1 - v0) * (x - k0) / (k1 - k0)


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


# ---- a rule -------------------------------------------------------------------------------------------


@dataclass
class Outcome:
    applies: bool  # false: the object is not one the rule is about (`when` is false)
    ok: bool | None  # None: not known
    actual: expr.Value = None
    limit: expr.Value = None
    margin: float | None = None
    op: str = ""
    trace: expr.Trace = field(default_factory=expr.Trace)
    problem: str = ""  # why it could not be worked out (not the same as "not known")
    unknown: tuple[str, ...] = ()  # the fields that were not known


def _fmt(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _margin(op: str, actual: expr.Value, limit: expr.Value) -> float | None:
    if not (expr._num(actual) and expr._num(limit)):
        return None
    a, b = float(actual), float(limit)
    if op in ("<", "<="):
        return b - a
    if op in (">", ">="):
        return a - b
    return None


class DeclRule:
    """A declarative rule, ready to run: its specification and the file it comes from."""

    def __init__(self, spec: RuleSpec, file: ExtFile, defs: dict[str, FieldDef]) -> None:
        self.spec, self.file, self.defs = spec, file, defs

    def evaluate(self, project: Project, ctx: Context) -> Outcome:
        env = ObjectEnv(project, ctx, self.file, self.defs)
        out = Outcome(True, None)
        s = self.spec
        try:
            if s.when is not None:
                guard = expr.evaluate(s.when, env, out.trace)
                if guard is False:
                    out.applies = False
                    return out
                if guard is None:
                    out.ok = None
                    out.unknown = self._unknown(out)
                    return out
                if guard is not True:
                    raise expr.ExprRuntimeError("'when' did not give true or false")
            verdict = expr.evaluate(s.condition, env, out.trace)
            if verdict is not None and not isinstance(verdict, bool):
                raise expr.ExprRuntimeError("'condition' did not give true or false")
            out.ok = verdict
            leaf = expr.deciding_compare(s.condition, env)
            if leaf is not None:
                out.op = leaf.op
                out.actual = expr.evaluate(leaf.left, env, out.trace)
                out.limit = expr.evaluate(leaf.right, env, out.trace)
                out.margin = _margin(leaf.op, out.actual, out.limit)
        except expr.ExprRuntimeError as exc:
            out.ok = None
            out.problem = str(exc)
        out.unknown = self._unknown(out)
        return out

    @staticmethod
    def _unknown(out: Outcome) -> tuple[str, ...]:
        return tuple(k for k, v in out.trace.fields.items() if v is None)

    def message(self, object_id: str, out: Outcome, env: ObjectEnv) -> str:
        s = self.spec

        def fill(m: re.Match[str]) -> str:
            name = m.group(1)
            if name == "object":
                return object_id
            if name == "actual":
                return _fmt(out.actual)
            if name == "limit":
                return _fmt(out.limit)
            if name == "margin":
                return _fmt(out.margin)
            if name == "over":
                return (
                    _fmt(abs(out.margin))
                    if out.margin is not None and out.margin < 0
                    else _fmt(None)
                )
            if name == "unit":
                return s.unit
            if name == "rule":
                return s.id
            if name == "title":
                return s.title
            scope, _, fname = name.partition(".")
            return _fmt(env.field(scope, fname))

        return _BRACES.sub(fill, s.message)

    def results(self, project: Project) -> Iterator[tuple[str, Outcome]]:
        for oid, ctx in contexts(project, self.spec.applies_to):
            yield oid, self.evaluate(project, ctx)

    def check(self, project: Project) -> Iterator[Hit]:
        for oid, ctx in contexts(project, self.spec.applies_to):
            out = self.evaluate(project, ctx)
            if out.applies and out.ok is False:
                yield Hit(
                    oid, self.message(oid, out, ObjectEnv(project, ctx, self.file, self.defs))
                )

    def notes(self, project: Project) -> list[str]:
        """What the rule could not look at: objects whose value is not known, or that it could not
        work out. Empty when it saw everything it was about."""
        unknown: list[str] = []
        problems: list[str] = []
        for oid, out in self.results(project):
            if not out.applies:
                continue
            if out.problem:
                problems.append(f"{oid}: {out.problem}")
            elif out.ok is None:
                unknown.append(oid)
        notes = []
        if unknown:
            shown = ", ".join(unknown[:6]) + (
                f" and {len(unknown) - 6} more" if len(unknown) > 6 else ""
            )
            notes.append(
                f"{self.spec.id} was not checked for {shown}: a value it reads is not known"
            )
        if problems:
            notes.append(
                f"{self.spec.id} could not be worked out for {problems[0]}"
                + (f" (and {len(problems) - 1} more)" if len(problems) > 1 else "")
            )
        return notes

    def rule(self) -> Rule:
        s = self.spec
        return Rule(s.id, s.severity, s.title, s.why, s.how, self.check, s.waivable, s.requirements)

    # -- the explanation (S1 form: equation, inputs, actual, limit, margin)

    def derivation(self, project: Project, object_id: str) -> Derivation | None:
        s = self.spec
        ctx = context_of(project, s.applies_to, object_id)
        if ctx is None:
            return None
        out = self.evaluate(project, ctx)
        env = ObjectEnv(project, ctx, self.file, self.defs)
        equation = "this rule holds when " + expr.render(s.condition)
        if s.when is not None:
            equation += ", for objects where " + expr.render(s.when)
        inputs: list[Input] = []
        for fid, value in out.trace.fields.items():
            d = self.defs.get(fid)
            inputs.append(
                Input(
                    fid,
                    _shown(value),
                    d.unit if d else "",
                    f"field {fid}: {d.doc}" if d else f"field {fid}",
                )
            )
        for name, value in out.trace.params.items():
            p = self.file.param(name)
            note = f", {p.source}" if p and p.source else ""
            inputs.append(
                Input(
                    f"parameter {name}",
                    _shown(value),
                    p.unit if p else "",
                    f"{self.file.rel}: parameters.{name}{note}",
                )
            )
        for name, value in out.trace.settings.items():
            file_, _, key = name.partition(".")
            st = settings_mod.setting(file_, key)
            e = settings_mod.effective(project, file_, key)
            inputs.append(
                Input(
                    st.label if st else name,
                    _shown(value),
                    st.unit if st else "",
                    f"config/{file_}.json: {key} ({e.origin})",
                )
            )
        for table, lookup_key, found in out.trace.lookups:
            lk = self.file.lookup(table)
            note = f", {lk.source}" if lk and lk.source else ""
            inputs.append(
                Input(
                    f"lookup {table}[{_fmt(lookup_key)}]",
                    _shown(found),
                    lk.unit if lk else "",
                    f"{self.file.rel}: lookups.{table} ({lk.mode if lk else ''}){note}",
                )
            )
        steps: list[Step] = []
        if s.when is not None:
            steps.append(
                Step(
                    "applies where",
                    expr.render(s.when),
                    0.0,
                    "",
                    "yes"
                    if out.applies
                    else "no, so the rule has nothing to say about this object",
                )
            )
        verdict = {True: "holds", False: "does not hold", None: "not known"}[out.ok]
        steps.append(Step("condition", expr.render(s.condition), 0.0, "", verdict))
        leaf = expr.deciding_compare(s.condition, env)
        check: Check | None = None
        if leaf is not None and expr._num(out.actual) and expr._num(out.limit):
            steps.append(Step("actual", expr.render(leaf.left), float(out.actual), s.unit))
            steps.append(Step("limit", expr.render(leaf.right), float(out.limit), s.unit))
            a, b = float(out.actual), float(out.limit)
            ok = bool(out.ok)
            margin = out.margin if out.margin is not None else 0.0
            u = f" {s.unit}" if s.unit else ""
            if out.margin is not None:
                phrase = (
                    f"within the limit, {_g(margin)}{u} to spare"
                    if ok
                    else f"over the limit by {_g(-margin)}{u}"
                )
            else:
                phrase = "as required" if ok else "not as required"
            check = Check(
                a,
                b,
                s.unit,
                ok,
                margin,
                f"the actual value is {_g(a)}{u} and the limit is {_g(b)}{u}: {phrase}",
            )
        missing = [f"{f} is not known" for f in out.unknown]
        reference = " ".join(
            t
            for t in (
                f"Extension rule {s.id} from {s.file} (version {s.version}, sha256 {s.sha256[:12]}); it is not part of the tool.",
                f"Why it matters: {s.why}",
                f"To fix it: {s.how}",
                f"Requirement IDs: {', '.join(s.requirements)}." if s.requirements else "",
            )
            if t
        )
        text = (
            out.problem
            or ("this object is not one the rule is about" if not out.applies else "")
            or {
                True: "the rule holds for this object",
                False: self.message(object_id, out, env),
                None: "not known: " + (", ".join(missing) or "a value is missing"),
            }[out.ok]
        )
        return Derivation(
            "rule-limit", f"Rule {s.id} for {object_id}", s.title,
            float(out.actual) if expr._num(out.actual) else None, s.unit, equation,
            tuple(inputs), tuple(steps), check, (), reference, tuple(missing), text=text,
        )  # fmt: skip


def _shown(value: object) -> float | int | str | None:
    if value is None or isinstance(value, float | int | str) and not isinstance(value, bool):
        return value
    return str(value).lower() if isinstance(value, bool) else str(value)


# ---- a table ------------------------------------------------------------------------------------------


type Table = list[list[str]]


def _cell(value: expr.Value) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return data_num(value)
    if isinstance(value, list):
        return ", ".join(_cell(v) for v in value)
    return str(value)


def _order(value: expr.Value) -> tuple[int, float, str]:
    if value is None:
        return (2, 0.0, "")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return (0, float(value), "")
    return (1, 0.0, str(value))


def build_table(
    project: Project, spec: TableSpec, file: ExtFile, defs: dict[str, FieldDef]
) -> tuple[Table, list[str]]:
    """The rows of a table (header first) and the problems met (a cell that could not be worked out)."""
    header = [c.header + (f" ({c.unit})" if c.unit else "") for c in spec.columns]
    rows: list[tuple[tuple[int, float, str], list[str]]] = []
    problems: list[str] = []
    for oid, ctx in contexts(project, spec.applies_to):
        env = ObjectEnv(project, ctx, file, defs)
        try:
            if spec.where is not None and expr.evaluate(spec.where, env) is not True:
                continue
            key = expr.evaluate(spec.sort, env) if spec.sort is not None else None
        except expr.ExprRuntimeError as exc:
            problems.append(f"{oid}: {exc}")
            continue
        cells: list[str] = []
        for col in spec.columns:
            try:
                cells.append(_cell(expr.evaluate(col.value, env)))
            except expr.ExprRuntimeError as exc:
                problems.append(f"{oid}, {col.header}: {exc}")
                cells.append("error")
        rows.append((_order(key), cells))
    if spec.sort is not None:
        rows.sort(key=lambda r: r[0])  # stable: the order of the design breaks ties
    return [header, *(cells for _k, cells in rows)], problems


__all__ = [
    "DeclRule",
    "ExtFile",
    "ExtIssue",
    "FORMAT",
    "Lookup",
    "Param",
    "Problem",
    "RuleSpec",
    "TableSpec",
    "build_table",
    "context_of",
    "contexts",
    "lookup_value",
    "read_file",
]
