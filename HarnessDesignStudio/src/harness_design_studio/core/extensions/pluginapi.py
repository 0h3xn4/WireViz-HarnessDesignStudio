# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The registration API a Python plug-in is given (`docs/developer/extensions.md`).

A plug-in is a module (a single file in `<project>/extensions/plugins/`, or an installed package
that names its module in the entry-point group `harness_design_studio.plugins`) with two things at
the top level::

    PLUGIN = {"name": "my-rules", "version": "1.0.0", "api": 1, "kinds": ["rule"]}

    def register(api):
        api.rule("x-my-check", title=..., severity="warning", why=..., how=..., compares=...,
                 check=my_check)

`PLUGIN` is read *without running the module* (to show what the code is before anyone trusts it),
so it must be a literal. `register` is called once, after the project enabled the plug-in and the
exact code was trusted on this computer; everything it registers goes into the registry beside the
built-in items and is tagged with the plug-in's name, version and hash.

What a plug-in can add is limited to these kinds: `rule`, `field`, `table`, `importer`. The API
version (`PLUGIN_API_VERSION` in `registry.py`) is checked: a plug-in written for another version
is not loaded. The names here are stable across minor versions of the tool.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from harness_design_studio.core.commands import Op
from harness_design_studio.core.drc.base import Hit, Rule
from harness_design_studio.core.issues import Severity
from harness_design_studio.core.model import Project

from . import fields as fields_mod
from .expr import Value
from .registry import (
    FIELD,
    IMPORTER,
    PLUGIN,
    PLUGIN_API_VERSION,
    RULE,
    TABLE,
    Item,
    Registry,
    RegistryError,
)

type Table = list[list[str]]
_HitType = Hit  # (the class attribute below has the same name, so annotations use this one)

__all__ = ["Hit", "PluginApi", "PluginImport", "PluginRule", "PluginTable"]


@dataclass(frozen=True)
class PluginImport:
    """What an importer of a plug-in reads: the edits it proposes (applied as one change), one line
    for each thing it read, and notes (what it skipped or converted)."""

    ops: list[Op] = field(default_factory=list)
    rows: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PluginRule:
    rule: Rule
    compares: str  # what the rule compares: the sentence of its explanation
    plugin: str
    explain: Callable[[Project, str], str] | None = (
        None  # the statement for one object, if more than `compares`
    )


@dataclass(frozen=True)
class PluginTable:
    name: str
    title: str
    build: Callable[[Project], Table]


@dataclass(frozen=True)
class PluginImporter:
    name: str
    read: Callable[[Project, Path], PluginImport]
    suffixes: tuple[str, ...]


class PluginApi:
    """The object `register(api)` receives. Everything is registered under the plug-in's own name
    and version; a name that is already taken is an error that stops the plug-in loading."""

    Hit = Hit  # the result of a rule's check: Hit(object_id, title, key=None)
    api_version = PLUGIN_API_VERSION

    def __init__(self, name: str, version: str, sha256: str, staging: Registry) -> None:
        self._name, self._version, self._sha = name, version, sha256
        self._staging = staging

    def _add(self, kind: str, name: str, obj: object, doc: str) -> None:
        self._staging.register(
            Item(kind, name, self._version, PLUGIN, self._name, self._sha, doc, obj)
        )

    def rule(
        self,
        id: str,  # noqa: A002
        *,
        title: str,
        severity: Severity,
        why: str,
        how: str,
        check: Callable[[Project], Iterator[_HitType]],
        compares: str,
        sources: tuple[str, ...] = (),
        waivable: bool | None = None,
        explain: Callable[[Project, str], str] | None = None,
    ) -> None:
        """Add a design rule. `id` must start with `x-`. `check(project)` yields a `Hit` for each
        problem. `why` and `how` are the explanation and the fix, as for a built-in rule; `compares`
        is one sentence that says what the rule compares ("each wire's gauge with the smallest one
        allowed for power"): it is the explanation of the rule (`explain`), shown beside the
        statement of a finding, and a rule without it is refused. `explain(project, object_id)` may
        return a longer statement for one object."""
        if not id.startswith("x-"):
            raise RegistryError(f"the id of a plug-in rule must start with 'x-' (found '{id}')")
        if severity not in ("error", "warning", "info"):
            raise RegistryError(f"the severity of {id} must be error, warning or info")
        if not (title.strip() and why.strip() and how.strip() and compares.strip()):
            raise RegistryError(f"{id} needs a title, why, how and compares (its explanation)")
        if not callable(check):
            raise RegistryError(f"{id}: check must be a function of the project")
        rule = Rule(id, severity, title, why, how, check, waivable, tuple(sources))
        self._add(RULE, id, PluginRule(rule, compares, self._name, explain), why)

    def field(
        self,
        scope: str,
        name: str,
        fn: Callable[[fields_mod.Context], Value],
        *,
        unit: str = "",
        doc: str,
        kind: str = "number",
    ) -> None:
        """Add a derived value that expressions of declarative files can read as `scope.name`.
        `fn(context)` gets a `Context` (`project`, `harness`, `wire`, `connector`, `interface`)
        and returns a number, a text, true or false, or None for "not known"."""
        if scope not in fields_mod.SCOPES:
            raise RegistryError(
                f"field scope '{scope}' is not one of {', '.join(fields_mod.SCOPES)}"
            )
        if not name.isidentifier() or name.startswith("_") or not name.islower():
            raise RegistryError(f"field name '{name}' must be lower case letters, digits and '_'")
        if kind not in ("number", "text", "flag"):
            raise RegistryError("field kind must be number, text or flag")
        if not doc.strip():
            raise RegistryError(f"field {scope}.{name} needs a doc sentence")
        self._add(
            FIELD, f"{scope}.{name}", fields_mod.FieldDef(scope, name, unit, kind, doc, fn), doc
        )

    def table(self, name: str, build: Callable[[Project], Table], *, title: str) -> None:
        """Add an output table: `build(project)` returns the rows (the header row first, every cell
        a text). `export` writes it as system/extensions/<name>.csv."""
        if not name or not all(c.islower() or c.isdigit() or c in "-_" for c in name):
            raise RegistryError(
                f"table name '{name}' must be lower case letters, digits, '-' and '_'"
            )
        self._add(TABLE, name, PluginTable(name, title, build), title)

    def importer(
        self,
        name: str,
        read: Callable[[Project, Path], PluginImport],
        *,
        suffixes: tuple[str, ...] = (".csv",),
        doc: str,
    ) -> None:
        """Add a reader of an outside file: `read(project, path)` returns a `PluginImport`. Run it
        with `harness-design-studio import-plugin DIR NAME FILE`; `--dry-run` shows the result
        without changing the project."""
        if not name or not all(c.islower() or c.isdigit() or c in "-_" for c in name):
            raise RegistryError(
                f"importer name '{name}' must be lower case letters, digits, '-' and '_'"
            )
        self._add(IMPORTER, name, PluginImporter(name, read, tuple(suffixes)), doc)
