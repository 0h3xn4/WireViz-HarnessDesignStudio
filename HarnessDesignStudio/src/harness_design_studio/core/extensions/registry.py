"""The registry: one list of everything the tool can run, built-in and extension together.

Rules, derived fields, models, output tables, lookup tables and importers are *items* of one kind
each. The built-in ones are registered at start through exactly the call an extension uses
(`Registry.register`, see `builtins.py`), so `harness-design-studio extensions DIR` lists a built-in
rule and a rule of a project's extension in one table, with where each comes from: its source
(`built-in`, `declarative` for a data file, `plugin` for Python code), its origin (the file or the
plug-in), its version and the SHA-256 of the file or the code.

The registry of the tool (`REGISTRY`) holds the built-in items only. What a project enables is added
in a copy of it made for that project (`Registry.layered`), so two projects open at once never see
each other's extensions and a project that enables none sees the built-ins and nothing else.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

# The kinds of item. A plug-in declares which of these it provides (`PLUGIN["kinds"]`).
RULE = "rule"  # a design rule: a check that yields findings
FIELD = "field"  # a derived value an expression can read (wire.mm2, wire.ampacity_limit_a)
MODEL = "model"  # a calculation model the tool offers as a setting (model.bundle_basis ...)
TABLE = "table"  # an output table written by `export`
LOOKUP = "lookup"  # a table of values an expression can look up
IMPORTER = "importer"  # a reader of an outside file
KINDS = (RULE, FIELD, MODEL, TABLE, LOOKUP, IMPORTER)
PLUGIN_KINDS = (RULE, FIELD, TABLE, IMPORTER)  # what Python code may add

BUILTIN = "built-in"
DECLARATIVE = "declarative"
PLUGIN = "plugin"
SOURCES = (BUILTIN, DECLARATIVE, PLUGIN)

PLUGIN_API_VERSION = 1
"""The version of the registration API for Python plug-ins (`pluginapi.PluginApi`). A plug-in names
the version it was written for (`PLUGIN["api"]`); a different one is not loaded."""


class RegistryError(ValueError):
    """An item cannot be registered: the kind is unknown or the name is taken."""


@dataclass(frozen=True)
class Item:
    kind: str
    name: str
    version: str  # the tool's version for a built-in, the extension's own for the others
    source: str  # BUILTIN, DECLARATIVE or PLUGIN
    origin: str = (
        ""  # "" for a built-in; the file ("extensions/min-gauge.json") or the plug-in name
    )
    sha256: str = ""  # of the file or the code the item comes from ("" for a built-in)
    doc: str = ""  # one plain sentence
    obj: object = field(default=None, compare=False, repr=False)  # the callable or the spec

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind, "name": self.name, "version": self.version, "source": self.source,
            "origin": self.origin, "sha256": self.sha256, "doc": self.doc,
        }  # fmt: skip


class Registry:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], Item] = {}

    def register(self, item: Item) -> Item:
        """Add an item. The name of a kind is unique: a second registration is refused, so an
        extension can never replace a built-in rule or another extension's item."""
        if item.kind not in KINDS:
            raise RegistryError(f"'{item.kind}' is not a kind of item (one of {', '.join(KINDS)})")
        if item.source not in SOURCES:
            raise RegistryError(f"'{item.source}' is not a source (one of {', '.join(SOURCES)})")
        if not item.name:
            raise RegistryError("an item needs a name")
        key = (item.kind, item.name)
        if key in self._items:
            first = self._items[key]
            where = "the tool" if first.source == BUILTIN else first.origin
            raise RegistryError(f"the {item.kind} '{item.name}' is already registered by {where}")
        self._items[key] = item
        return item

    def get(self, kind: str, name: str) -> Item | None:
        return self._items.get((kind, name))

    def items(self, kind: str | None = None) -> list[Item]:
        """The items in a fixed order: by kind (the order of `KINDS`); within a kind the built-ins
        in the order they were registered, then the others by name."""
        order = {k: n for n, k in enumerate(KINDS)}
        rows = [i for i in self._items.values() if kind is None or i.kind == kind]
        builtin = [i for i in rows if i.source == BUILTIN]
        others = sorted((i for i in rows if i.source != BUILTIN), key=lambda i: i.name)
        return sorted(builtin + others, key=lambda i: order[i.kind])  # stable: keeps the above

    def names(self, kind: str) -> list[str]:
        return [i.name for i in self.items(kind)]

    def layered(self, extra: Iterable[Item] = ()) -> Registry:
        """A copy with the items of `extra` added; this registry is not changed."""
        out = Registry()
        out._items = dict(self._items)
        for item in extra:
            out.register(item)
        return out

    def __len__(self) -> int:
        return len(self._items)


REGISTRY = Registry()
"""The built-in items (filled by `builtins.install`)."""
