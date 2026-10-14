"""Project tree (SH-6, SC-20): the left panel that lists everything in the project.

Roots: Units, Interfaces, Harnesses (with a release-state badge), Parts, Interface types,
Configuration (with the placeholder flag and the number of values still pending) and Imports (the
entry points for interface tables, parts, lengths, engineering values and KiCad netlists). Every
object shows how many errors, warnings and "not checked" notes belong to it, and a lock when a
released harness holds it (the tooltip says why).

    tree = ProjectTree(ctl, theme)
    tree.selectionRequested.connect(...)   # (kind, id): a row was clicked or Enter was pressed
    tree.openRequested.connect(...)        # (kind, id): double-click or Ctrl+Enter
    tree.importRequested.connect(...)      # kind: "interfaces" | "parts" | "lengths" |
                                           #       "engineering" | "netlist"
    tree.addRequested.connect(...)         # kind: "unit" | "interface" (the "Add" menu)
    tree.set_context_actions(lambda kind, id: [QAction(...)])

It is a `QTreeView` over `ProjectTreeModel` (a `QAbstractItemModel`), never a `QTreeWidget`. The
model follows the controller's `Delta`: a change touches only the rows of the objects it names (a
rename updates one row, an added unit inserts one), and the counts and locks are recomputed from
the controller's findings and `core.vcs.lockview` without running any rule. Enter on a unit or an
interface selects it on the canvas through `ctl.select`; the other kinds only emit the signals.
"""

import bisect
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, Final

from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QRectF,
    QSettings,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QContextMenuEvent, QFont, QFontMetrics, QKeyEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import configcheck, describe, drc
from harness_design_studio.core.drc.by_rule import UNCHECKED
from harness_design_studio.core.vcs.lockview import lock_reason, locked_objects
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import LIST_DELAY_MS, Delta, EditorController
from harness_design_studio.gui.icons import draw_icon, icon_button
from harness_design_studio.gui.states import STATE_ROLE, STATES, chip_size, paint_chip
from harness_design_studio.gui.tables import natural_key
from harness_design_studio.gui.theme import ThemeManager
from harness_design_studio.gui.tokens import CATEGORIES, style_category

ROOT_ORDER: Final = (
    "units",
    "interfaces",
    "harnesses",
    "parts",
    "interface_types",
    "config",
    "imports",
)
OBJECT_KINDS: Final = ("unit", "interface", "harness", "part", "interface_type", "config")
IMPORT_KINDS: Final = tuple(
    strings.TREE_IMPORTS
)  # interfaces, parts, lengths, engineering, netlist
CANVAS_KINDS: Final = ("unit", "interface")  # the kinds `ctl.select` knows
_CHILD_KIND: Final = {
    "units": "unit",
    "interfaces": "interface",
    "harnesses": "harness",
    "parts": "part",
    "interface_types": "interface_type",
    "config": "config",
    "imports": "import",
}
_ROOT_ICON: Final = {
    "units": "unit",
    "interfaces": "interface",
    "harnesses": "harness",
    "parts": "part",
    "interface_types": "interface-type",
    "config": "config",
    "imports": "import",
}
_KIND_ICON: Final = {
    "unit": "unit",
    "interface": "interface",
    "harness": "harness",
    "part": "part",
    "interface_type": "interface-type",
    "config": "config",
    "import": "import",
}
_EXPANDED_BY_DEFAULT: Final = ("units", "interfaces", "harnesses", "config")
BULK = 40  # more changes than this (and most of a root) are applied as one block

_UR = int(Qt.ItemDataRole.UserRole)
KIND_ROLE: Final = _UR + 20  # "root" | one of OBJECT_KINDS | "import" | "empty"
ID_ROLE: Final = _UR + 21  # the object ID (the root key for a root, the import kind for an import)
IDENT_ROLE: Final = _UR + 22  # the ID text painted in monospace
NAME_ROLE: Final = _UR + 23  # the rest of the label
COUNTS_ROLE: Final = _UR + 24  # (errors, warnings, not checked)
LOCK_ROLE: Final = _UR + 25  # the sentence that says why the object is locked, or None
CHILDREN_ROLE: Final = _UR + 26  # number of objects under a root
STATE_TEXT_ROLE: Final = _UR + 27  # the text on the state chip
ICON_ROLE: Final = _UR + 28  # name of the icon in gui/icons.py
NODE_ROLE: Final = _UR + 29  # the row itself (for the delegate: one lookup instead of many)
_FLAGS_ROW: Final = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
_FLAGS_HINT: Final = Qt.ItemFlag.ItemIsEnabled
_FLAGS_OFF: Final = Qt.ItemFlag.NoItemFlags

Counts = tuple[int, int, int]
ContextProvider = Callable[[str, str], Sequence[QAction]]


def _plural(forms: tuple[str, str], n: int) -> str:
    return forms[0 if n == 1 else 1].format(n)


def counts_text(errors: int, warnings: int, unchecked: int) -> str:
    """ "2 errors, 1 warning, 3 not checked" (only the parts that are not zero)."""
    parts = []
    if errors:
        parts.append(_plural(strings.TREE_N_ERRORS, errors))
    if warnings:
        parts.append(_plural(strings.TREE_N_WARNINGS, warnings))
    if unchecked:
        parts.append(_plural(strings.TREE_N_NOT_CHECKED, unchecked))
    return ", ".join(parts)


class _Node:
    """A row of the tree. The model owns them; `obj` is the project object the row shows, so a
    change is found by identity (the project's objects are immutable)."""

    __slots__ = (
        "children",
        "counts",
        "id",
        "ident",
        "kind",
        "lock",
        "name",
        "obj",
        "parent",
        "placeholder",
        "row",
        "search",
        "sort",
        "sorts",
        "state",
        "state_text",
    )

    def __init__(self, kind: str, id_: str, parent: "_Node | None") -> None:
        self.kind, self.id, self.parent = kind, id_, parent
        self.row = 0
        self.children: list[_Node] = []
        self.sorts: list[tuple[Any, ...]] = []  # sort keys of the real children, same order
        self.placeholder: _Node | None = None  # the "nothing here yet" row of an empty root
        self.ident = ""
        self.name = ""
        self.search = ""
        self.sort: tuple[Any, ...] = ()
        self.obj: object = None
        self.counts: Counts = (0, 0, 0)
        self.lock: str | None = None
        self.state: str | None = None
        self.state_text: str | None = None

    @property
    def real_children(self) -> int:
        return len(self.sorts)


class ProjectTreeModel(QAbstractItemModel):
    """The tree's data: one root node per group, the objects below them in natural ID order."""

    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl, self.theme = ctl, theme
        self._top = _Node("top", "", None)
        self._by_key: dict[tuple[str, str], _Node] = {}
        self.roots: dict[str, _Node] = {}
        self._read_only = ctl.read_only
        self._locked: dict[tuple[str, str], Any] = {}
        self._lock_sig: object = None
        self._badged: set[_Node] = set()
        self._counts_key: object = None
        self._wire_owner: dict[str, str] = {}
        self._wire_sig: tuple[int, ...] = ()
        for key in ROOT_ORDER:
            node = _Node("root", key, self._top)
            node.row = len(self._top.children)
            node.ident = ""
            node.name = strings.TREE_ROOTS[key]
            node.search = node.name.lower()
            node.sort = (node.row,)
            self._top.children.append(node)
            self.roots[key] = node
            self._by_key[("root", key)] = node
        for kind, label in strings.TREE_IMPORTS.items():
            leaf = _Node("import", kind, self.roots["imports"])
            leaf.name = label
            leaf.search = label.lower()
            leaf.row = len(self.roots["imports"].children)
            self.roots["imports"].children.append(leaf)
            self.roots["imports"].sorts.append((leaf.row,))
            self._by_key[("import", kind)] = leaf
        for key in _CHILD_KIND:
            if key != "imports":
                self._ensure_placeholder(self.roots[key], notify=False)
        self.sync_all()
        self.refresh_locks()
        self.refresh_counts()

    # ---- QAbstractItemModel ------------------------------------------------------------------

    # The view asks these a few thousand times per layout, so they stay lean.
    def node(self, index: QModelIndex | QPersistentModelIndex) -> _Node:
        if index.isValid():
            node = index.internalPointer()
            if node is not None:
                return node  # type: ignore[no-any-return]
        return self._top

    def index_of(self, node: _Node) -> QModelIndex:
        if node is self._top or node.parent is None:
            return QModelIndex()
        return self.createIndex(node.row, 0, node)

    def index(  # noqa: N802
        self,
        row: int,
        column: int,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),  # noqa: B008
    ) -> QModelIndex:
        children = (parent.internalPointer() if parent.isValid() else self._top).children
        if column or not 0 <= row < len(children):
            return QModelIndex()
        return self.createIndex(row, 0, children[row])

    def parent(self, child: QModelIndex | QPersistentModelIndex = QModelIndex()) -> QModelIndex:  # type: ignore[override]  # noqa: B008
        if not child.isValid():
            return QModelIndex()
        up = child.internalPointer().parent
        if up is None or up is self._top:
            return QModelIndex()
        return self.createIndex(up.row, 0, up)

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return len((parent.internalPointer() if parent.isValid() else self._top).children)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 1

    def hasChildren(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> bool:  # noqa: B008, N802
        return bool((parent.internalPointer() if parent.isValid() else self._top).children)

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        node = self.node(index)
        if node.kind == "empty":
            return _FLAGS_HINT
        if node.kind == "import" and self.ctl.read_only:
            return _FLAGS_OFF
        return _FLAGS_ROW

    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = 0) -> Any:
        if not index.isValid():
            return None
        node = index.internalPointer()
        if role == NODE_ROLE:
            return node
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{node.ident}  {node.name}".strip()
        if role == KIND_ROLE:
            return node.kind
        if role == ID_ROLE:
            return node.id
        if role == IDENT_ROLE:
            return node.ident
        if role == NAME_ROLE:
            return node.name
        if role == COUNTS_ROLE:
            return node.counts
        if role == LOCK_ROLE:
            return node.lock
        if role == CHILDREN_ROLE:
            return node.real_children
        if role == STATE_ROLE:
            return node.state
        if role == STATE_TEXT_ROLE:
            return node.state_text
        if role == ICON_ROLE:
            return _ROOT_ICON[node.id] if node.kind == "root" else _KIND_ICON.get(node.kind)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self.tooltip(node)
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return self.accessible_text(node)
        return None

    # ---- text built on demand ----------------------------------------------------------------

    def tooltip(self, node: _Node) -> str:
        p = self.ctl.project
        lines: list[str] = []
        if node.kind == "unit" and node.id in p.units:
            u = p.units[node.id]
            lines.append(
                strings.TREE_TIP_UNIT.format(
                    u.id, u.name, u.subsystem, u.zone or strings.TREE_NO_ZONE, u.side
                )
            )
        elif node.kind == "interface" and node.id in p.interfaces:
            i = p.interfaces[node.id]
            ends = " - ".join(e.unit_id for e in i.endpoints)
            lines.append(
                strings.TREE_TIP_INTERFACE.format(i.id, describe.link_caption(p, i.id), ends)
            )
        elif node.kind == "harness" and node.id in p.harnesses:
            h = p.harnesses[node.id]
            lines.append(
                strings.TREE_TIP_HARNESS.format(
                    h.id,
                    h.name,
                    h.revision,
                    strings.STATE_LABELS[describe.harness_state(h)].lower(),
                )
            )
        elif node.kind == "part" and node.id in p.parts:
            part = p.parts[node.id]
            lines.append(
                strings.TREE_TIP_PART.format(
                    part.id,
                    part.description or part.part_number or part.id,
                    strings.APPROVAL.get(part.approval, part.approval),
                )
            )
        elif node.kind == "interface_type" and node.id in p.interface_types:
            t = p.interface_types[node.id]
            lines.append(
                strings.TREE_TIP_TYPE.format(
                    t.id, t.name, CATEGORIES[style_category(t.category)]["label"]
                )
            )
        elif node.kind == "config":
            lines.append(self._config_tip(node.id))
        elif node.kind == "import":
            lines.append(
                strings.TREE_IMPORT_READ_ONLY
                if self.ctl.read_only
                else strings.TREE_IMPORT_TIP.format(strings.TREE_IMPORTS[node.id].rstrip("…"))
            )
        elif node.kind == "root" or node.kind == "empty":
            lines.append(node.name)
        if node.kind != "root" and any(node.counts):
            lines.append(counts_text(*node.counts) + ".")
        if node.kind == "root" and any(node.counts):
            lines.append(counts_text(*node.counts) + ".")
        if node.lock:
            lines.append(node.lock)
        return "\n".join(lines)

    def _config_tip(self, name: str) -> str:
        p = self.ctl.project
        cfg = p.config.get(name)
        lines = []
        if cfg is not None and cfg.placeholder:
            lines.append(strings.TREE_TIP_CONFIG_PLACEHOLDER.format(name))
        missing = [n for n in configcheck.missing(p) if n.file == name]
        if missing:
            lines.append(
                strings.TREE_TIP_CONFIG_MISSING.format(
                    f"{len(missing)} {strings.TREE_VALUE_WORD[0 if len(missing) == 1 else 1]}",
                    ", ".join(n.key for n in missing),
                )
            )
        return " ".join(lines) or strings.TREE_TIP_CONFIG_OK.format(name)

    def accessible_text(self, node: _Node) -> str:
        if node.kind == "root":
            return f"{node.name}, {node.real_children}" if node.id != "imports" else node.name
        if node.kind == "empty":
            return node.name
        parts = [
            strings.TREE_ROOTS[_root_of(node.kind)].rstrip("s")
            if node.kind not in ("import",)
            else "",
            f"{node.ident} {node.name}".strip(),
        ]
        if node.state is not None:
            parts.append(node.state_text or STATES[node.state].label)
        if any(node.counts):
            parts.append(counts_text(*node.counts))
        if node.lock:
            parts.append(STATES["locked"].label)
        return ". ".join(p for p in parts if p)

    # ---- finding rows ------------------------------------------------------------------------

    def find(self, kind: str, id_: str) -> _Node | None:
        return self._by_key.get((kind, id_))

    def index_for(self, kind: str, id_: str) -> QModelIndex:
        node = self.find(kind, id_)
        return self.index_of(node) if node is not None else QModelIndex()

    def child_ids(self, root: str) -> list[str]:
        return [c.id for c in self.roots[root].children if c.kind != "empty"]

    # ---- building and updating rows ----------------------------------------------------------

    def _source(self, root: str) -> Mapping[str, Any]:
        p = self.ctl.project
        found: dict[str, Mapping[str, Any]] = {
            "units": p.units,
            "interfaces": p.interfaces,
            "harnesses": p.harnesses,
            "parts": p.parts,
            "interface_types": p.interface_types,
            "config": p.config,
        }
        return found[root]

    def _fill(self, node: _Node, obj: Any) -> None:
        """Set the text and state of a row from its project object."""
        node.obj = obj
        node.sort = natural_key(node.id)
        node.state = node.state_text = None
        node.ident = node.id
        kind = node.kind
        if kind == "unit":
            side = f" ({obj.side})" if obj.side != "none" and obj.side not in obj.name else ""
            node.name = f"{obj.name}{side}"
        elif kind in ("interface", "interface_type"):
            node.name = obj.name
        elif kind == "harness":
            node.name = obj.name
            node.state = describe.harness_state(obj)
            word = strings.STATE_LABELS[node.state]
            node.state_text = (
                f"{word} {obj.revision}" if node.state in ("released", "revised") else word
            )
        elif kind == "part":
            node.name = obj.description or obj.part_number or ""
        elif kind == "config":
            node.name = ""
            missing = sum(n.file == node.id for n in configcheck.missing(self.ctl.project))
            if missing:
                node.state, node.state_text = "pending", strings.TREE_CONFIG_PENDING.format(missing)
            elif obj.placeholder:
                node.state, node.state_text = "pending", strings.TREE_CONFIG_PLACEHOLDER
        node.search = f"{node.ident} {node.name}".lower()

    def _renumber(self, owner: _Node, start: int = 0) -> None:
        for k in range(start, len(owner.children)):
            owner.children[k].row = k

    def _ensure_placeholder(self, root: _Node, *, notify: bool = True) -> None:
        """An empty root shows one row that says what to do; a root with objects shows none."""
        if root.real_children == 0 and root.placeholder is None and root.id in strings.TREE_EMPTY:
            node = _Node("empty", root.id, root)
            node.name = strings.TREE_EMPTY[root.id]
            node.search = node.name.lower()
            if notify:
                self.beginInsertRows(self.index_of(root), 0, 0)
            node.row = 0
            root.children.insert(0, node)
            root.placeholder = node
            if notify:
                self.endInsertRows()
        elif root.real_children and root.placeholder is not None:
            node = root.placeholder
            if notify:
                self.beginRemoveRows(self.index_of(root), node.row, node.row)
            root.children.remove(node)
            root.placeholder = None
            self._renumber(root)
            if notify:
                self.endRemoveRows()

    def _insert(self, root: _Node, key: str, obj: Any) -> None:
        if root.placeholder is not None:
            self._drop_placeholder(root)
        node = _Node(_CHILD_KIND[root.id], key, root)
        self._fill(node, obj)
        node.lock = self._lock_of(node)
        pos = bisect.bisect_left(root.sorts, node.sort)
        self.beginInsertRows(self.index_of(root), pos, pos)
        root.children.insert(pos, node)
        root.sorts.insert(pos, node.sort)
        self._renumber(root, pos)
        self._by_key[(node.kind, key)] = node
        self.endInsertRows()

    def _drop_placeholder(self, root: _Node) -> None:
        node = root.placeholder
        if node is None:
            return
        self.beginRemoveRows(self.index_of(root), node.row, node.row)
        root.children.remove(node)
        root.placeholder = None
        self._renumber(root)
        self.endRemoveRows()

    def _remove(self, node: _Node) -> None:
        root = node.parent
        if root is None:
            return
        self.beginRemoveRows(self.index_of(root), node.row, node.row)
        del root.children[node.row]
        del root.sorts[node.row]
        self._renumber(root, node.row)
        self._by_key.pop((node.kind, node.id), None)
        self._badged.discard(node)
        self.endRemoveRows()

    def _update(self, node: _Node, obj: Any) -> None:
        before = (node.ident, node.name, node.state, node.state_text)
        self._fill(node, obj)
        idx = self.index_of(node)
        if before != (node.ident, node.name, node.state, node.state_text):
            self.dataChanged.emit(idx, idx)

    def _replace_all(self, root: _Node, source: Mapping[str, Any]) -> None:
        """Swap every row of a root for the objects of `source` in one block."""
        old = root.children
        if old:
            self.beginRemoveRows(self.index_of(root), 0, len(old) - 1)
            for n in old:
                self._by_key.pop((n.kind, n.id), None)
                self._badged.discard(n)
            root.children, root.sorts, root.placeholder = [], [], None
            self.endRemoveRows()
        nodes = []
        for key, obj in source.items():
            node = _Node(_CHILD_KIND[root.id], key, root)
            self._fill(node, obj)
            node.lock = self._lock_of(node)
            nodes.append(node)
        nodes.sort(key=lambda n: n.sort)
        if nodes:
            self.beginInsertRows(self.index_of(root), 0, len(nodes) - 1)
            root.children = nodes
            root.sorts = [n.sort for n in nodes]
            self._renumber(root)
            for n in nodes:
                self._by_key[(n.kind, n.id)] = n
            self.endInsertRows()
        self._ensure_placeholder(root)

    def sync_keys(self, root_key: str, keys: Iterable[str]) -> None:
        """Bring the rows of the given IDs in line with the project (add, remove, update)."""
        root = self.roots[root_key]
        source = self._source(root_key)
        kind = _CHILD_KIND[root_key]
        adds, removes, updates = [], [], []
        for key in keys:
            node = self._by_key.get((kind, key))
            obj = source.get(key)
            if obj is None:
                if node is not None:
                    removes.append(node)
            elif node is None:
                adds.append((key, obj))
            elif node.obj is not obj:
                updates.append((node, obj))
        if len(adds) + len(removes) > BULK and len(adds) + len(removes) >= root.real_children / 2:
            self._replace_all(root, source)
        else:
            for node in removes:
                self._remove(node)
            for key, obj in adds:
                self._insert(root, key, obj)
            for node, obj in updates:
                self._update(node, obj)
            self._ensure_placeholder(root)
        if adds or removes:
            idx = self.index_of(root)
            self.dataChanged.emit(idx, idx)
        if root_key == "config":
            self._refresh_config_root()

    def sync_root(self, root_key: str) -> None:
        """Compare a whole root with the project (cheap: identity of each object)."""
        root = self.roots[root_key]
        source = self._source(root_key)
        kind = _CHILD_KIND[root_key]
        keys = set(source)
        keys.update(n.id for n in root.children if n.kind == kind)
        self.sync_keys(root_key, keys)

    def sync_all(self) -> None:
        for key in _CHILD_KIND:
            if key != "imports":
                self.sync_root(key)

    def _refresh_config_root(self) -> None:
        root = self.roots["config"]
        n = len(configcheck.missing(self.ctl.project))
        state, text = ("pending", strings.TREE_CONFIG_PENDING.format(n)) if n else (None, None)
        if (root.state, root.state_text) != (state, text):
            root.state, root.state_text = state, text
            idx = self.index_of(root)
            self.dataChanged.emit(idx, idx)

    # ---- read-only imports -------------------------------------------------------------------

    def refresh_read_only(self) -> None:
        ro = self.ctl.read_only
        if ro != self._read_only:
            self._read_only = ro
            top, bottom = (
                self.index_of(self.roots["imports"].children[0]),
                self.index_of(self.roots["imports"].children[-1]),
            )
            self.dataChanged.emit(top, bottom)

    # ---- locks -------------------------------------------------------------------------------

    def _lock_of(self, node: _Node) -> str | None:
        if node.kind not in OBJECT_KINDS or (node.kind, node.id) not in self._locked:
            return None
        return lock_reason(self.ctl.project, node.kind, node.id, self._locked)

    def refresh_locks(self) -> None:
        """Show the lock on the objects a released harness holds. Recomputed only when the set of
        released harnesses (or the project) is different from last time."""
        p = self.ctl.project
        sig = (
            id(p),
            tuple((h.id, h.revision) for h in p.harnesses.values() if h.status == "released"),
        )
        if sig == self._lock_sig:
            return
        self._lock_sig = sig
        self._locked = dict(locked_objects(p))
        for node in self._by_key.values():
            if node.kind in OBJECT_KINDS:
                reason = self._lock_of(node)
                if reason != node.lock:
                    node.lock = reason
                    idx = self.index_of(node)
                    self.dataChanged.emit(idx, idx)

    # ---- problem counts ----------------------------------------------------------------------

    def _wire_index(self) -> dict[str, str]:
        """Wire and cable-connector IDs -> harness, rebuilt only when a harness changed."""
        harnesses = self.ctl.project.harnesses
        sig = tuple(id(h) for h in harnesses.values())
        if sig != self._wire_sig:
            self._wire_sig = sig
            owner: dict[str, str] = {}
            for h in harnesses.values():
                for w in h.wires:
                    owner[w.id] = h.id
                for c in h.connectors:
                    owner[c.id] = h.id
            self._wire_owner = owner
        return self._wire_owner

    def place(
        self, object_id: str, memo: dict[str, tuple[str, str] | None]
    ) -> tuple[str, str] | None:
        """The row a finding about `object_id` belongs to, or None when it belongs to no row."""
        p = self.ctl.project
        if object_id in p.units:
            return "unit", object_id
        if object_id in p.interfaces:
            return "interface", object_id
        if object_id in p.harnesses:
            return "harness", object_id
        box = p.connectors.get(object_id)
        if box is not None and box.unit_id in p.units:
            return "unit", box.unit_id
        owner = self._wire_index().get(object_id)
        if owner is not None:
            return "harness", owner
        if object_id in p.parts:
            return "part", object_id
        if object_id in p.interface_types:
            return "interface_type", object_id
        if object_id in p.config:
            return "config", object_id
        if object_id not in memo:
            memo[object_id] = drc.locate(p, object_id)
        return memo[object_id]

    def count_problems(self) -> dict[tuple[str, str], list[int]]:
        """Open findings grouped by the row they belong to: [errors, warnings, not checked]."""
        p = self.ctl.project
        memo: dict[str, tuple[str, str] | None] = {}
        out: dict[tuple[str, str], list[int]] = {}
        for f in self.ctl.open_findings():
            if f.rule == UNCHECKED:
                slot = 2
                key = ("config", f.object_id) if f.object_id in p.config else ("root", "config")
            elif f.severity == "error":
                slot, key = 0, self.place(f.object_id, memo)  # type: ignore[assignment]
            elif f.severity == "warning":
                slot, key = 1, self.place(f.object_id, memo)  # type: ignore[assignment]
            else:
                continue
            if key is None:
                continue
            out.setdefault(key, [0, 0, 0])[slot] += 1
        return out

    def refresh_counts(self) -> None:
        """Recompute the counts from the controller's findings (no rule runs here)."""
        self._counts_key = self.ctl.findings_key()
        grouped = self.count_problems()
        touched: set[_Node] = set()
        for (kind, id_), c in grouped.items():
            node = self._by_key.get(("root", id_) if kind == "root" else (kind, id_))
            if node is None:
                continue
            counts: Counts = (c[0], c[1], c[2])
            touched.add(node)
            if node.counts != counts:
                node.counts = counts
                idx = self.index_of(node)
                self.dataChanged.emit(idx, idx)
        for node in self._badged - touched:
            if node.counts != (0, 0, 0):
                node.counts = (0, 0, 0)
                idx = self.index_of(node)
                self.dataChanged.emit(idx, idx)
        self._badged = touched
        for key, root in self.roots.items():
            if key == "imports":
                continue
            sums = [0, 0, 0]
            for child in root.children:
                for k in range(3):
                    sums[k] += child.counts[k]
            own = grouped.get(("root", key), [0, 0, 0])  # notes that belong to no single row
            total: Counts = (sums[0] + own[0], sums[1] + own[1], sums[2] + own[2])
            if root.counts != total:
                root.counts = total
                idx = self.index_of(root)
                self.dataChanged.emit(idx, idx)

    def counts_current(self) -> bool:
        return self._counts_key == self.ctl.findings_key()


def _root_of(kind: str) -> str:
    for root, child in _CHILD_KIND.items():
        if child == kind:
            return root
    return "units"


class _Kit:
    """Fonts and sizes a row is painted with; made once per font and scale, not per row."""

    def __init__(self, theme: ThemeManager, base: QFont) -> None:
        self.base = QFont(base)
        self.small = theme.font("sm")
        self.mono = theme.mono_font("base")
        self.bold = QFont(base)
        self.bold.setBold(True)
        self.italic = QFont(base)
        self.italic.setItalic(True)
        self.fm_base = QFontMetrics(self.base)
        self.fm_small = QFontMetrics(self.small)
        self.fm_mono = QFontMetrics(self.mono)
        self.fm_bold = QFontMetrics(self.bold)
        self.fm_italic = QFontMetrics(self.italic)
        self.icon = theme.icon_size(16)
        self.badge = theme.px(14)
        self.height = max(theme.px(28), self.fm_base.height() + theme.space(8))
        self.min_label = theme.px(48)  # room the label keeps before badges are left out


_LEFT_MIDDLE: Final = int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
_COUNT_ICONS: Final = (("error", "error"), ("warning", "warning"), ("not-checked", "not-checked"))


class _TreeDelegate(QStyledItemDelegate):
    """Paints a row: kind icon, the ID in monospace, the name, and on the right the problem
    counts (icon and number), the lock and the state chip. It draws the selection, hover and
    focus from the theme tokens itself, so a row costs a handful of calls."""

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme
        self._kit: _Kit | None = None
        self._kit_key: tuple[str, int, float] | None = None
        theme.changed.connect(self._forget)

    def _forget(self) -> None:
        self._kit = self._kit_key = None

    def kit(self, font: QFont) -> _Kit:
        key = (font.family(), font.pixelSize(), self.theme.scale)
        if self._kit is None or key != self._kit_key:
            self._kit, self._kit_key = _Kit(self.theme, font), key
        return self._kit

    def sizeHint(  # noqa: N802
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        return QSize(self.theme.px(120), self.kit(option.font).height)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        node = index.data(NODE_ROLE)
        if node is None:
            return
        theme, kit = self.theme, self.kit(option.font)
        state = option.state
        selected = bool(state & QStyle.StateFlag.State_Selected)
        enabled = bool(state & QStyle.StateFlag.State_Enabled)
        rect = QRectF(option.rect)
        painter.save()
        painter.setClipRect(rect)
        if selected:
            painter.fillRect(rect, theme.color("primary"))
        elif state & QStyle.StateFlag.State_MouseOver and enabled:
            painter.fillRect(rect, theme.color("surface-2"))
        if state & QStyle.StateFlag.State_HasFocus:
            painter.setPen(QPen(theme.color("focus"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
        text_c = theme.color("on-primary" if selected else "text" if enabled else "text-muted")
        muted_c = theme.color("on-primary" if selected else "text-muted")
        gap = theme.space(4)
        left, right = rect.left() + gap, rect.right() - gap
        mid = rect.center().y()
        if node.kind == "empty":
            painter.setFont(kit.italic)
            painter.setPen(muted_c)
            width = int(right - left)
            painter.drawText(
                QRectF(left, rect.top(), width, rect.height()),
                _LEFT_MIDDLE,
                kit.fm_italic.elidedText(node.name, Qt.TextElideMode.ElideRight, width),
            )
            painter.restore()
            return
        floor = left + kit.icon + kit.min_label
        # ---- right side, drawn right to left: state chip, lock, counts (errors end up leftmost)
        if node.state is not None:
            size = chip_size(node.state, theme, node.state_text, kit.small)
            chip = QRectF(
                right - size.width(), mid - size.height() / 2, size.width(), size.height()
            )
            if chip.left() > floor:
                paint_chip(
                    painter, chip, node.state, theme,
                    text=node.state_text, selected=selected, font=kit.small,
                )  # fmt: skip
                right = chip.left() - gap
        if node.lock:
            box = QRectF(right - kit.badge, mid - kit.badge / 2, kit.badge, kit.badge)
            if box.left() > floor:
                draw_icon(painter, "lock", box, muted_c, stroke=1.5)
                right = box.left() - gap
        painter.setFont(kit.small)
        for slot in (2, 1, 0):
            n = node.counts[slot]
            if not n:
                continue
            label = str(n)
            width = kit.badge + 2 + kit.fm_small.horizontalAdvance(label)
            x = right - width
            if x <= floor:
                break
            name, token = _COUNT_ICONS[slot]
            colour = theme.color("on-primary" if selected else token)
            draw_icon(
                painter,
                name,
                QRectF(x, mid - kit.badge / 2, kit.badge, kit.badge),
                colour,
                stroke=1.5,
            )
            painter.setPen(colour)
            painter.drawText(
                QRectF(x + kit.badge + 2, rect.top(), width - kit.badge - 2, rect.height()),
                _LEFT_MIDDLE,
                label,
            )
            right = x - gap
        # ---- left side: icon, ID, name
        icon_name = _ROOT_ICON[node.id] if node.kind == "root" else _KIND_ICON.get(node.kind)
        if icon_name:
            draw_icon(
                painter, icon_name, QRectF(left, mid - kit.icon / 2, kit.icon, kit.icon), muted_c, stroke=1.5
            )  # fmt: skip
            left += kit.icon + gap
        avail = max(0, int(right - left))
        if node.kind == "root":
            painter.setFont(kit.bold)
            painter.setPen(text_c)
            label = kit.fm_bold.elidedText(node.name, Qt.TextElideMode.ElideRight, avail)
            painter.drawText(QRectF(left, rect.top(), avail, rect.height()), _LEFT_MIDDLE, label)
            if node.id != "imports":
                shown = kit.fm_bold.horizontalAdvance(label) + gap * 2
                painter.setFont(kit.small)
                painter.setPen(muted_c)
                painter.drawText(
                    QRectF(left + shown, rect.top(), max(0, avail - shown), rect.height()),
                    _LEFT_MIDDLE,
                    str(node.real_children),
                )
            painter.restore()
            return
        if node.ident:
            painter.setFont(kit.mono)
            painter.setPen(text_c)
            shown_id = kit.fm_mono.elidedText(node.ident, Qt.TextElideMode.ElideRight, avail)
            painter.drawText(QRectF(left, rect.top(), avail, rect.height()), _LEFT_MIDDLE, shown_id)
            used = kit.fm_mono.horizontalAdvance(shown_id) + gap * 2
            left += used
            avail = max(0, avail - used)
        if node.name and avail > 0:
            painter.setFont(kit.base)
            painter.setPen(muted_c if node.ident else text_c)
            painter.drawText(
                QRectF(left, rect.top(), avail, rect.height()),
                _LEFT_MIDDLE,
                kit.fm_base.elidedText(node.name, Qt.TextElideMode.ElideRight, avail),
            )
        painter.restore()


class _Proxy(QSortFilterProxyModel):
    """Keeps the order of the model; shows rows whose ID or name contains every word typed (and
    the groups above them)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._words: list[str] = []
        self.setRecursiveFilteringEnabled(True)
        self.setDynamicSortFilter(False)

    def set_text(self, text: str) -> None:
        self.beginFilterChange()
        self._words = text.lower().split()
        self.endFilterChange()

    @property
    def active(self) -> bool:
        return bool(self._words)

    def filterAcceptsRow(  # noqa: N802
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        if not self._words:
            return True
        model = self.sourceModel()
        if not isinstance(model, ProjectTreeModel):
            return True
        node = model.node(model.index(source_row, 0, source_parent))
        if node.kind in ("empty", "root"):
            return False if node.kind == "empty" else any(w in node.search for w in self._words)
        return all(w in node.search for w in self._words)


class _FilterEdit(QLineEdit):
    """The filter box: Escape clears it (and then leaves the box), Down goes to the tree."""

    leave = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("tree-filter")
        self.setPlaceholderText(strings.TREE_FILTER_PLACEHOLDER)
        self.setAccessibleName(strings.TREE_FILTER_NAME)
        self.setToolTip(strings.TREE_FILTER_TIP)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            if self.text():
                self.clear()
            else:
                self.leave.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Down:
            self.leave.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _TreeView(QTreeView):
    """The tree: Enter and Ctrl+Enter are reported instead of the default `activated`, and "/"
    asks for the filter box."""

    enterPressed = Signal(QModelIndex)
    openPressed = Signal(QModelIndex)
    filterRequested = Signal()
    menuRequested = Signal(QPoint)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            index = self.currentIndex()
            if index.isValid():
                ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                (self.openPressed if ctrl else self.enterPressed).emit(index)
            event.accept()
            return
        if event.text() == "/" and not event.modifiers() & ~Qt.KeyboardModifier.ShiftModifier:
            self.filterRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        self.menuRequested.emit(event.globalPos())
        event.accept()


class ProjectTree(QWidget):
    """The project tree with its filter box and "Add" menu.

    Signals: `selectionRequested(kind, id)` (click or Enter on an object), `openRequested(kind,
    id)` (double-click or Ctrl+Enter), `importRequested(kind)` (Enter or double-click on an import
    entry), `addRequested(kind)` ("unit" or "interface", from the "Add" menu or a group's
    context menu). A click or Enter on a unit or an interface also selects it on the canvas
    (`ctl.select`).
    """

    selectionRequested = Signal(str, str)
    openRequested = Signal(str, str)
    importRequested = Signal(str)
    addRequested = Signal(str)

    def __init__(
        self, ctl: EditorController, theme: ThemeManager, settings: QSettings | None = None
    ) -> None:
        super().__init__()
        self.ctl, self.theme, self.settings = ctl, theme, settings
        self.setObjectName("project-tree")
        self.contextActions: ContextProvider | None = None
        self._syncing = False
        self._expanded_before: set[str] | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.space(4))
        # ---- filter and "Add"
        top = QWidget()
        top_lay = QVBoxLayout(top)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(theme.space(4))
        self.filter_edit = _FilterEdit()
        filter_row = QHBoxLayout()
        filter_row.setSpacing(theme.space(4))
        filter_row.addWidget(self.filter_edit, 1)
        self.clear_button = QToolButton()
        self.clear_button.setObjectName("tree-filter-clear")
        icon_button(self.clear_button, "close", theme, strings.TREE_FILTER_CLEAR, "Esc")
        self.clear_button.clicked.connect(self.filter_edit.clear)
        self.clear_button.setVisible(False)
        filter_row.addWidget(self.clear_button)
        top_lay.addLayout(filter_row)
        self.add_button = QToolButton()
        self.add_button.setObjectName("tree-add")
        icon_button(self.add_button, "plus", theme, strings.TREE_ADD_TIP, text=strings.TREE_ADD)
        self.add_button.setAccessibleName(strings.TREE_ADD)
        self.add_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.add_menu = QMenu(self.add_button)
        self.add_actions: dict[str, QAction] = {}
        for kind, label in strings.TREE_ADD_ENTRIES.items():
            act = self.add_menu.addAction(label)
            act.setObjectName(f"tree-add-{kind}")
            act.triggered.connect(lambda _=False, k=kind: self.addRequested.emit(k))
            self.add_actions[kind] = act
        self.add_button.setMenu(self.add_menu)
        top_lay.addWidget(self.add_button)
        lay.addWidget(top)
        # ---- the tree
        self.model = ProjectTreeModel(ctl, theme)
        self.proxy = _Proxy(self)  # in use only while a filter is typed (it costs on every change)
        self.view = _TreeView()
        self.view.setObjectName("project-tree-view")
        self.view.setModel(self.model)
        self.view.setItemDelegate(_TreeDelegate(theme, self.view))
        self.view.setHeaderHidden(True)
        self.view.setUniformRowHeights(True)
        self.view.setAnimated(False)
        self.view.setIndentation(theme.space(16))
        self.view.setFrameShape(QTreeView.Shape.NoFrame)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setExpandsOnDoubleClick(True)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.view.setAccessibleName(strings.TREE_NAME)
        self.view.setAccessibleDescription(strings.TREE_HELP)
        self.view.setToolTip("")
        lay.addWidget(self.view, 1)
        self.setTabOrder(self.filter_edit, self.add_button)
        self.setTabOrder(self.add_button, self.view)
        self._restore_expansion()
        # ---- wiring
        self._counts_timer = QTimer(self)
        self._counts_timer.setSingleShot(True)
        self._counts_timer.setInterval(LIST_DELAY_MS)
        self._counts_timer.timeout.connect(self.flush)
        self._project = ctl.project
        ctl.changed.connect(self._on_changed)
        ctl.selectionChanged.connect(self._sync_selection)
        ctl.stateChanged.connect(self.model.refresh_read_only)
        ctl.drcChanged.connect(self._schedule_counts)
        theme.changed.connect(self._restyle)
        self.filter_edit.textChanged.connect(self._filter_changed)
        self.filter_edit.textChanged.connect(lambda t: self.clear_button.setVisible(bool(t)))
        self.filter_edit.leave.connect(self.view.setFocus)
        self.view.clicked.connect(self._clicked)
        self.view.doubleClicked.connect(self._double_clicked)
        self.view.enterPressed.connect(self._enter)
        self.view.openPressed.connect(self._open)
        self.view.filterRequested.connect(self.focus_filter)
        self.view.menuRequested.connect(self._show_menu)
        self.view.expanded.connect(self._remember_expansion)
        self.view.collapsed.connect(self._remember_expansion)
        self._sync_selection()

    # ---- public helpers ----------------------------------------------------------------------

    def set_context_actions(self, provider: ContextProvider | None) -> None:
        """Set the function that gives the context-menu actions of an object: `provider(kind, id)`
        returns a list of `QAction`; they follow the tree's own entries."""
        self.contextActions = provider

    def focus_filter(self) -> None:
        self.filter_edit.setFocus()
        self.filter_edit.selectAll()

    def set_filter(self, text: str) -> None:
        self.filter_edit.setText(text)

    def has(self, kind: str, id_: str) -> bool:
        return self.model.find(kind, id_) is not None

    def child_ids(self, root: str) -> list[str]:
        """IDs of the objects under a group ("units", "interfaces", "harnesses", "parts",
        "interface_types" or "config"), in the order shown."""
        return self.model.child_ids(root)

    def counts(self, kind: str, id_: str) -> Counts:
        """(errors, warnings, not checked) of a row; `kind` "root" and a group key for a group."""
        node = self.model.find(kind, id_)
        return node.counts if node is not None else (0, 0, 0)

    def lock_of(self, kind: str, id_: str) -> str | None:
        node = self.model.find(kind, id_)
        return node.lock if node is not None else None

    def state_of(self, kind: str, id_: str) -> tuple[str, str] | None:
        """(state key, chip text) of a row, or None when it has no chip."""
        node = self.model.find(kind, id_)
        if node is None or node.state is None:
            return None
        return node.state, node.state_text or STATES[node.state].label

    def current(self) -> tuple[str, str] | None:
        """(kind, id) of the row with the cursor, or None."""
        node = self.model.node(self._source_index(self.view.currentIndex()))
        return None if node.kind in ("top", "empty") else (node.kind, node.id)

    def select(self, kind: str, id_: str) -> bool:
        """Put the cursor on a row without telling anybody (False if there is no such row, or the
        filter hides it)."""
        if self.current() == (kind, id_):
            return True  # already there: an unrelated edit must not scroll the tree back
        index = self.index_for(kind, id_)
        if not index.isValid():
            return False
        self._syncing = True
        try:
            self.view.setCurrentIndex(index)
            self.view.scrollTo(index)
        finally:
            self._syncing = False
        return True

    def flush(self) -> None:
        """Bring the problem counts up to date now (they are otherwise refreshed a moment after
        a change when the project has very many findings)."""
        self._counts_timer.stop()
        self.model.refresh_counts()

    def expand_all(self) -> None:
        self.view.expandAll()

    def collapse_all(self) -> None:
        self.view.collapseAll()

    def is_expanded(self, root: str) -> bool:
        return self.view.isExpanded(self._view_index(self.model.index_of(self.model.roots[root])))

    # ---- following the controller ------------------------------------------------------------

    def _on_changed(self, delta: Delta) -> None:
        project = self.ctl.project
        if delta.full or project is not self._project:
            self._project = project
            self.model.sync_all()
        else:
            self.model.sync_keys("units", delta.units)
            self.model.sync_keys("interfaces", delta.interfaces)
            for root in ("harnesses", "parts", "interface_types", "config"):
                self.model.sync_root(root)
        self.model.refresh_locks()
        if self.ctl.findings_are_many():
            self._schedule_counts()
        else:
            self.flush()
        self._sync_selection()

    def _schedule_counts(self) -> None:
        if self.ctl.findings_are_many():
            self._counts_timer.start()
        else:
            self.flush()

    def _sync_selection(self) -> None:
        s = self.ctl.selection
        if s is None:
            self._syncing = True
            self.view.setCurrentIndex(QModelIndex())
            self.view.clearSelection()
            self._syncing = False
        else:
            self.select(s.kind, s.id)

    def _restyle(self) -> None:
        self.view.setIndentation(self.theme.space(16))
        self.view.scheduleDelayedItemsLayout()
        self.view.viewport().update()

    # ---- user actions ------------------------------------------------------------------------

    def _node_at(self, index: QModelIndex) -> Any:
        return self.model.node(self._source_index(index))

    def _select_node(self, node: Any) -> None:
        if node.kind not in OBJECT_KINDS:
            return
        if node.kind in CANVAS_KINDS:
            self.ctl.select(node.kind, node.id)
        self.selectionRequested.emit(node.kind, node.id)

    def _select_kind(self, kind: str, id_: str) -> None:
        node = self.model.find(kind, id_)
        if node is not None:
            self._select_node(node)

    def _clicked(self, index: QModelIndex) -> None:
        self._select_node(self._node_at(index))

    def _enter(self, index: QModelIndex) -> None:
        node = self._node_at(index)
        if node.kind == "root":
            self.view.setExpanded(index, not self.view.isExpanded(index))
        elif node.kind == "import":
            if not self.ctl.read_only:
                self.importRequested.emit(node.id)
        else:
            self._select_node(node)

    def _double_clicked(self, index: QModelIndex) -> None:
        node = self._node_at(index)
        if node.kind == "import":
            if not self.ctl.read_only:
                self.importRequested.emit(node.id)
        elif node.kind in OBJECT_KINDS:
            self._select_node(node)
            self.openRequested.emit(node.kind, node.id)

    def _open(self, index: QModelIndex) -> None:
        node = self._node_at(index)
        if node.kind in OBJECT_KINDS:
            self._select_node(node)
            self.openRequested.emit(node.kind, node.id)
        elif node.kind == "import" and not self.ctl.read_only:
            self.importRequested.emit(node.id)

    # ---- context menu ------------------------------------------------------------------------

    def build_menu(self, kind: str, id_: str) -> QMenu:
        """The context menu of a row (also used by the tests; `contextActions` adds to it)."""
        menu = QMenu(self)
        if kind in OBJECT_KINDS:
            if kind in CANVAS_KINDS:
                act = menu.addAction(strings.TREE_MENU_SELECT)
                act.triggered.connect(lambda _=False: self._select_kind(kind, id_))
            opener = menu.addAction(strings.TREE_MENU_OPEN)
            opener.triggered.connect(lambda _=False: self.openRequested.emit(kind, id_))
            copy = menu.addAction(strings.TREE_MENU_COPY_ID)
            copy.triggered.connect(lambda _=False: QApplication.clipboard().setText(id_))
            if self.contextActions is not None:
                extra = list(self.contextActions(kind, id_))
                if extra:
                    menu.addSeparator()
                    for a in extra:
                        menu.addAction(a)
        elif kind == "root":
            add_kind = _CHILD_KIND.get(id_)
            if add_kind in strings.TREE_ADD_ENTRIES:
                label = strings.TREE_ADD_IN.format(strings.TREE_ROOTS[id_].lower().rstrip("s"))
                menu.addAction(label).triggered.connect(
                    lambda _=False: self.addRequested.emit(str(add_kind))
                )
            menu.addAction(strings.TREE_MENU_EXPAND).triggered.connect(self.expand_all)
            menu.addAction(strings.TREE_MENU_COLLAPSE).triggered.connect(self.collapse_all)
        for act in menu.actions():
            if not act.isSeparator():
                act.setObjectName(
                    act.objectName() or "tree-menu-" + act.text().lower().replace(" ", "-")
                )
        return menu

    def _show_menu(self, global_pos: QPoint) -> None:
        index = self.view.indexAt(self.view.viewport().mapFromGlobal(global_pos))
        if not index.isValid():
            return
        node = self._node_at(index)
        if node.kind in ("empty", "import"):
            return
        self.build_menu(node.kind, node.id).exec(global_pos)

    # ---- filter and expansion ----------------------------------------------------------------

    def _filtering(self) -> bool:
        return self.view.model() is self.proxy

    def _view_index(self, src: QModelIndex) -> QModelIndex:
        """The view's index for a model index (they differ only while a filter is typed)."""
        return self.proxy.mapFromSource(src) if self._filtering() else src

    def _source_index(self, index: QModelIndex) -> QModelIndex:
        return self.proxy.mapToSource(index) if self._filtering() else index

    def index_for(self, kind: str, id_: str) -> QModelIndex:
        """The view's index of a row (invalid if there is none, or the filter hides it)."""
        return self._view_index(self.model.index_for(kind, id_))

    def _filter_changed(self, text: str) -> None:
        if text.strip():
            if not self._filtering():
                self._expanded_before = {r for r in ROOT_ORDER if self.is_expanded(r)}
                self.proxy.setSourceModel(self.model)
                self.view.setModel(self.proxy)
            self.proxy.set_text(text)
            self.view.expandAll()
            return
        if self._filtering():
            self.proxy.set_text("")
            self.view.setModel(self.model)
            self.proxy.setSourceModel(None)  # type: ignore[arg-type]
            before = self._expanded_before or set(_EXPANDED_BY_DEFAULT)
            self._expanded_before = None
            for r in ROOT_ORDER:
                self.view.setExpanded(self.model.index_of(self.model.roots[r]), r in before)
            self._sync_selection()

    def _saved_roots(self) -> set[str]:
        if self.settings is not None:
            raw = self.settings.value("tree/expanded")
            if isinstance(raw, str):
                return {raw}
            if isinstance(raw, list):
                return {str(x) for x in raw}
        return set(_EXPANDED_BY_DEFAULT)

    def _restore_expansion(self) -> None:
        keep = self._saved_roots()
        for r in ROOT_ORDER:
            self.view.setExpanded(
                self._view_index(self.model.index_of(self.model.roots[r])), r in keep
            )

    def _remember_expansion(self) -> None:
        if self.settings is None or self._filtering():
            return
        open_roots = [r for r in ROOT_ORDER if self.is_expanded(r)]
        self.settings.setValue("tree/expanded", open_roots or "")
