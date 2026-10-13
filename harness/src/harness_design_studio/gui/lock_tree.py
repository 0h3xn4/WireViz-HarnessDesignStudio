"""What a release locks and what a new revision makes editable, as a tree a dialog or panel can show.

The facts come from `core.vcs.lockview` (`release_locks`, `locked_objects`, `cosmetic_fields`); this
module only groups and words them, so a view needs no logic of its own:

    locks = release_locks(project, "W001")
    groups = release_groups(locks)                # [LockGroup("wires", "Wires", ...), ...]
    summary_text(groups)                          # "12 wires, 40 pins, 3 interfaces, ..."
    model = tree_model(groups, theme)             # a QStandardItemModel for a QTreeView

Values that are not set yet are listed as *pending* (clock icon, italic), and a configuration file
that is still marked as a placeholder says so, so a release never hides that it freezes numbers
nobody has reviewed.
"""

from collections import defaultdict
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel

from harness_design_studio.core.model import Project
from harness_design_studio.core.vcs.lockview import (
    KIND_LABELS,
    ReleaseLocks,
    cosmetic_fields,
    locked_objects,
)
from harness_design_studio.core.vcs.timeline import format_value
from harness_design_studio.gui import icons, strings
from harness_design_studio.gui.theme import ThemeManager

# Display groups, in this order. A group collects one or more object kinds (`lockview.KINDS`).
GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("wires", ("wire",)),
    ("pins", ("cable_pin", "box_pin")),
    ("interfaces", ("interface",)),
    ("connectors", ("cable_connector", "box_connector")),
    ("units", ("unit",)),
    ("parts", ("part",)),
    ("interface_types", ("interface_type",)),
    ("config_files", ("config",)),
    ("other", ("harness", "splice", "shield", "branch_point", "segment")),
)
_GROUP_OF = {kind: key for key, kinds in GROUPS for kind in kinds}
# the words of the summary sentence: key -> (one, many)
NOUNS = {
    "wires": ("wire", "wires"),
    "pins": ("pin", "pins"),
    "interfaces": ("interface", "interfaces"),
    "connectors": ("connector", "connectors"),
    "units": ("unit", "units"),
    "parts": ("part", "parts"),
    "interface_types": ("interface type", "interface types"),
    "config_files": ("config file", "config files"),
    "other": ("other item", "other items"),
}
SUMMARY_KEYS = ("wires", "pins", "interfaces", "parts", "interface_types", "config_files")
LABELS = {
    "wires": strings.LOCK_GROUP_WIRES,
    "pins": strings.LOCK_GROUP_PINS,
    "interfaces": strings.LOCK_GROUP_INTERFACES,
    "connectors": strings.LOCK_GROUP_CONNECTORS,
    "units": strings.LOCK_GROUP_UNITS,
    "parts": strings.LOCK_GROUP_PARTS,
    "interface_types": strings.LOCK_GROUP_TYPES,
    "config_files": strings.LOCK_GROUP_CONFIG,
    "other": strings.LOCK_GROUP_OTHER,
}


@dataclass(frozen=True)
class LockItem:
    """One object (or one configuration value) in a group. `state` is a key of `gui.states.STATES`
    ("pending" for a value that is not set yet) or None."""

    text: str
    state: str | None = None
    note: str = ""  # the tooltip
    children: tuple["LockItem", ...] = ()


@dataclass(frozen=True)
class LockGroup:
    key: str  # "wires", "pins" ...
    label: str  # "Wires"
    items: tuple[LockItem, ...]
    note: str = ""  # what stays editable, for the group's tooltip and label

    @property
    def count(self) -> int:
        return len(self.items)


def plural(n: int, key: str) -> str:
    one, many = NOUNS[key]
    return f"{n} {one if n == 1 else many}"


def summary_text(groups: list[LockGroup], keys: tuple[str, ...] = SUMMARY_KEYS) -> str:
    """"12 wires, 40 pins, 3 interfaces, 5 parts, 2 interface types, 3 config files"; a group
    without objects is left out ("nothing" when none is left)."""
    by_key = {g.key: g.count for g in groups}
    parts = [plural(by_key[k], k) for k in keys if by_key.get(k)]
    return ", ".join(parts) if parts else strings.LOCK_NOTHING


def _group(key: str, items: list[LockItem], note: str = "") -> LockGroup:
    ordered = sorted(items, key=lambda i: i.text)
    return LockGroup(key, LABELS[key], tuple(ordered), note)


def _editable_note(kind: str) -> str:
    fields = sorted(cosmetic_fields(kind))
    return strings.LOCK_STAYS_EDITABLE.format(", ".join(f.replace("_", " ") for f in fields)) if fields else ""  # fmt: skip


def _config_item(name: str, placeholder: bool, values: dict[str, object], unset: set[str]) -> LockItem:
    children = tuple(
        LockItem(
            f"{key}: {strings.LOCK_NOT_SET}" if key in unset else f"{key}: {format_value(value)}",
            "pending" if key in unset else None,
            strings.LOCK_NOT_SET_NOTE if key in unset else "",
        )
        for key, value in sorted(values.items())
    )
    if placeholder:
        return LockItem(
            f"{name} ({strings.LOCK_PLACEHOLDER})", "pending", strings.LOCK_PLACEHOLDER_NOTE, children
        )
    return LockItem(name, None, "", children)


def release_groups(locks: ReleaseLocks) -> list[LockGroup]:
    """The objects releasing a harness freezes, in display groups (empty groups are left out)."""
    groups = {
        "wires": [LockItem(w) for w in locks.wires],
        "pins": [
            *(LockItem(f"{p} ({strings.LOCK_PIN_CABLE})") for p in locks.cable_pins),
            *(LockItem(f"{p} ({strings.LOCK_PIN_UNIT})") for p in locks.box_pins),
        ],
        "interfaces": [LockItem(i) for i in locks.interfaces],
        "connectors": [
            *(LockItem(f"{c} ({strings.LOCK_PIN_CABLE})") for c in locks.cable_connectors),
            *(LockItem(f"{c} ({strings.LOCK_PIN_UNIT})") for c in locks.box_connectors),
        ],
        "units": [LockItem(u) for u in locks.units],
        "parts": [LockItem(p) for p in locks.parts],
        "interface_types": [LockItem(t) for t in locks.interface_types],
        "config_files": [
            _config_item(c.name, c.placeholder, c.values, set(c.unset)) for c in locks.config_files
        ],
    }
    notes = {"interfaces": "interface", "units": "unit", "parts": "part", "interface_types": "interface_type"}  # fmt: skip
    return [
        _group(key, items, _editable_note(notes[key]) if key in notes else "")
        for key, items in groups.items()
        if items
    ]


@dataclass(frozen=True)
class RevisionUnlocks:
    """What starting a new revision of a harness changes in the locks."""

    harness_id: str
    revision: str  # the released revision
    editable: tuple[LockGroup, ...]  # locked by this harness only: editable after the revision
    still_locked: tuple[LockGroup, ...]  # also locked by another released harness: stays locked

    @property
    def editable_count(self) -> int:
        return sum(g.count for g in self.editable)


def revision_unlocks(project: Project, harness_id: str) -> RevisionUnlocks:
    """The objects that become editable when `harness_id` gets a new revision (those only it
    locks) and those that stay locked because another released harness also locks them."""
    h = project.harnesses.get(harness_id)
    revision = h.revision if h is not None else ""
    editable: dict[str, list[LockItem]] = defaultdict(list)
    kept: dict[str, list[LockItem]] = defaultdict(list)
    for (kind, oid), refs in sorted(locked_objects(project).items()):
        if not any(r.harness_id == harness_id for r in refs):
            continue
        others = sorted({r.harness_id for r in refs} - {harness_id})
        key = _GROUP_OF.get(kind, "other")
        label = f"{oid} ({KIND_LABELS.get(kind, kind)})" if key in ("other", "connectors", "pins") else oid  # fmt: skip
        if others:
            kept[key].append(
                LockItem(f"{label} ({strings.LOCK_ALSO.format(', '.join(others))})", "locked")
            )
        else:
            editable[key].append(LockItem(label))
    order = [k for k, _ in GROUPS]
    return RevisionUnlocks(
        harness_id,
        revision,
        tuple(_group(k, editable[k]) for k in order if editable.get(k)),
        tuple(_group(k, kept[k]) for k in order if kept.get(k)),
    )


# ---- the model -------------------------------------------------------------------------------


def _item(entry: LockItem, theme: ThemeManager) -> QStandardItem:
    row = QStandardItem(entry.text)
    row.setEditable(False)
    if entry.state:
        row.setIcon(icons.icon(entry.state if entry.state != "locked" else "lock", theme, "pending" if entry.state == "pending" else "locked"))  # fmt: skip
        if entry.state == "pending":
            font = QFont()
            font.setItalic(True)
            row.setFont(font)
    if entry.note:
        row.setToolTip(entry.note)
    row.setData(entry.text if not entry.state else f"{entry.state}: {entry.text}", Qt.ItemDataRole.AccessibleTextRole)  # fmt: skip
    for child in entry.children:
        row.appendRow(_item(child, theme))
    return row


def tree_model(groups: list[LockGroup] | tuple[LockGroup, ...], theme: ThemeManager) -> QStandardItemModel:
    """One top-level row per group ("Wires (12)"), the objects below it."""
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels([strings.LOCK_TREE_HEADER])
    for g in groups:
        top = QStandardItem(f"{g.label} ({g.count})")
        top.setEditable(False)
        if g.note:
            top.setToolTip(g.note)
            top.setText(f"{g.label} ({g.count}) — {g.note}")
        for entry in g.items:
            top.appendRow(_item(entry, theme))
        model.appendRow(top)
    return model
