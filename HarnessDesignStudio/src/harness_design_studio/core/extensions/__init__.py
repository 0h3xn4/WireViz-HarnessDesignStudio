# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Extensibility (D-191 (5), S8): a registry of rules, derived fields, models, output tables and
importers, with declarative extensions (rules, tables and lookup tables written as data files) first
and Python plug-ins second. Both are opt-in per project, and Python code runs only after the person
using the computer trusted that exact code.

The parts, from the outside in:

    registry      the list of everything the tool can run, built-in and extension items together
    expr          the small safe expression language of the declarative files (no `eval`)
    schema        the format of an extension file; also its JSON Schema
    declarative   reading a file, running a rule, making a table, explaining a rule
    plugins       finding Python plug-ins and the gate that decides whether one is imported
    trust         the user's list of trusted code (not in the project)
    manager       a project's extensions folder: discovery, the objects that run, provenance

`docs/developer/extensions.md` is the reference; `docs/user-manual/extend-the-tool.md` the task page.
This package must not be imported by the design rule modules at the top of a module (they call it
inside functions), so a project without an `extensions/` folder never reaches any of it.
"""

from .manager import (
    ProjectExtensions,
    attach,
    discover,
    is_extension_rule,
    loaded,
    provenance,
    refresh,
    rules_for,
    runtime,
)
from .registry import REGISTRY, Item, Registry

__all__ = [
    "REGISTRY", "Item", "ProjectExtensions", "Registry", "attach", "discover", "is_extension_rule",
    "loaded", "provenance", "refresh", "rules_for", "runtime",
]  # fmt: skip
