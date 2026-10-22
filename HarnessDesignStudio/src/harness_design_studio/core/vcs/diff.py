"""Diff engine: compares two snapshots (a baseline, the working design for one harness, or a
whole project) and lists added, removed and changed objects exactly, with field-level changes.

Objects are flattened to (kind, id) -> fields. Nested collections become objects of their own
(a harness's wires, cable connectors and their pins, shields, segments ...), so a single changed
pin shows up as that pin, not as "the connector changed".
"""

from dataclasses import dataclass, field
from typing import Any

from harness_design_studio.core.model import Project, Snapshot
from harness_design_studio.core.model.base import Entity

Flat = dict[tuple[str, str], dict[str, Any]]

_HARNESS_PARTS = {
    "connectors": "cable_connector", "wires": "wire", "splices": "splice", "shields": "shield",
    "branch_points": "branch_point", "segments": "segment", "accessories": "accessory",
}  # fmt: skip


@dataclass(frozen=True)
class FieldChange:
    name: str
    before: Any
    after: Any


@dataclass(frozen=True)
class ObjectChange:
    kind: str
    id: str
    change: str  # "added" | "removed" | "changed"
    fields: tuple[FieldChange, ...] = ()


@dataclass
class Diff:
    changes: list[ObjectChange] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.changes

    def of(self, change: str) -> list[ObjectChange]:
        return [c for c in self.changes if c.change == change]

    def counts(self) -> dict[str, int]:
        return {k: len(self.of(k)) for k in ("added", "removed", "changed")}

    def summary(self) -> str:
        n = self.counts()
        return f"{n['added']} added, {n['removed']} removed, {n['changed']} changed"

    def affected(self) -> dict[str, str]:
        """Object ID -> "added" | "removed" | "changed" for units, interfaces and harnesses, so
        the editor can highlight them (a changed pin or wire marks its harness as changed)."""
        out: dict[str, str] = {}
        for c in self.changes:
            if c.kind in ("unit", "interface", "harness"):
                out[c.id] = c.change
        return out


def _dump(obj: Entity) -> dict[str, Any]:
    return obj.model_dump(mode="json")


def _flatten_harness(flat: Flat, h: Entity) -> None:
    data = _dump(h)
    hid = str(data["id"])
    flat[("harness", hid)] = {k: v for k, v in data.items() if k not in _HARNESS_PARTS}
    for key, kind in _HARNESS_PARTS.items():
        for child in data.get(key, []):  # a sparse list is left out while empty
            child = dict(child)
            if kind == "cable_connector":
                for pin in child.pop("pins"):
                    flat[("cable_pin", f"{child['id']}.{pin['id']}")] = pin
            flat[(kind, str(child["id"]))] = child


def _flatten_box(flat: Flat, c: Entity) -> None:
    data = _dump(c)
    pins = data.pop("pins", [])
    flat[("box_connector", data["id"])] = data
    for pin in pins:
        flat[("box_pin", f"{data['id']}.{pin['id']}")] = pin


def flatten_snapshot(s: Snapshot) -> Flat:
    flat: Flat = {}
    for u in s.units:
        flat[("unit", u.id)] = _dump(u)
    for i in s.interfaces:
        flat[("interface", i.id)] = _dump(i)
    for c in s.connectors:
        _flatten_box(flat, c)
    for h in s.harnesses:
        _flatten_harness(flat, h)
    return flat


def flatten_project(p: Project) -> Flat:
    flat: Flat = {}
    for u in p.units.values():
        flat[("unit", u.id)] = _dump(u)
    for t in p.interface_types.values():
        flat[("interface_type", t.id)] = _dump(t)
    for i in p.interfaces.values():
        flat[("interface", i.id)] = _dump(i)
    for part in p.parts.values():
        flat[("part", part.id)] = _dump(part)
    for c in p.connectors.values():
        _flatten_box(flat, c)
    for h in p.harnesses.values():
        _flatten_harness(flat, h)
    for name, cfg in p.config.items():
        flat[("config", name)] = {"values": cfg.values, "placeholder": cfg.placeholder}
    for w in p.waivers.values():
        flat[("waiver", w.id)] = _dump(w)
    for pl in p.placements.values():
        flat[("placement", pl.id)] = _dump(pl)
    flat[("project", "name")] = {"name": p.meta.name, "description": p.meta.description}
    flat[("zones", "list")] = {"zones": list(p.zones)}
    flat[("library", "info")] = _dump(p.library_info)
    for b in p.baselines.values():
        flat[("baseline", b.id)] = {
            "revision": b.revision, "released_on": b.released_on, "by": b.by,
            "comment": b.comment, "content_hash": b.content_hash,
        }  # fmt: skip
    for e in p.changelog.values():
        flat[("change_entry", e.id)] = _dump(e)
    return flat


def diff_flat(before: Flat, after: Flat) -> Diff:
    out = Diff()
    for key in sorted(set(before) | set(after)):
        kind, id_ = key
        if key not in before:
            out.changes.append(ObjectChange(kind, id_, "added"))
        elif key not in after:
            out.changes.append(ObjectChange(kind, id_, "removed"))
        else:
            a, b = before[key], after[key]
            names = sorted(set(a) | set(b))
            changed = tuple(
                FieldChange(n, a.get(n), b.get(n))
                for n in names
                if _norm(a.get(n)) != _norm(b.get(n))
            )
            if changed:
                out.changes.append(ObjectChange(kind, id_, "changed", changed))
    return out


def _norm(v: Any) -> Any:
    """Lists of objects compare in a stable order; everything else as is."""
    if isinstance(v, list) and v and all(isinstance(x, dict) and "id" in x for x in v):
        return sorted(v, key=lambda x: str(x["id"]))
    return v


def diff_snapshots(before: Snapshot, after: Snapshot) -> Diff:
    return diff_flat(flatten_snapshot(before), flatten_snapshot(after))


def diff_projects(before: Project, after: Project) -> Diff:
    return diff_flat(flatten_project(before), flatten_project(after))


# ---- readable reports ------------------------------------------------------------------------------

KIND_NAMES = {
    "unit": "Unit", "interface": "Interface", "interface_type": "Interface type", "part": "Part",
    "box_connector": "Box connector", "box_pin": "Box pin", "harness": "Harness",
    "cable_connector": "Cable connector", "cable_pin": "Cable pin", "wire": "Wire", "splice": "Splice",
    "shield": "Shield", "branch_point": "Branch point", "segment": "Segment", "accessory": "Accessory",
    "config": "Configuration",
    "waiver": "Waiver", "placement": "Diagram position", "project": "Project", "zones": "Zones",
    "library": "Parts library information", "baseline": "Baseline", "change_entry": "Change log entry",
}  # fmt: skip


def _show(v: Any) -> str:
    if v is None:
        return "(none)"
    if isinstance(v, list):
        return (
            ", ".join(_show(x) if not isinstance(x, dict) else str(x.get("id", x)) for x in v)
            or "(empty)"
        )
    text = str(v)
    return text if len(text) <= 80 else text[:77] + "..."


def render_markdown(title: str, diff: Diff, *, before: str = "before", after: str = "after") -> str:
    lines = [f"# {title}", "", f"Comparing {before} with {after}: {diff.summary()}."]
    if diff.empty:
        return "\n".join([*lines, "", "No differences.", ""])
    for change, heading in (("added", "Added"), ("removed", "Removed"), ("changed", "Changed")):
        group = diff.of(change)
        if not group:
            continue
        lines += ["", f"## {heading} ({len(group)})", ""]
        for c in group:
            lines.append(f"- {KIND_NAMES.get(c.kind, c.kind)} `{c.id}`")
            for f in c.fields:
                lines.append(f"  - {f.name}: {_show(f.before)} -> {_show(f.after)}")
    return "\n".join([*lines, ""])


def to_table(diff: Diff) -> list[list[str]]:
    rows = [["Change", "Kind", "ID", "Field", "Before", "After"]]
    for c in diff.changes:
        if c.fields:
            rows += [
                [c.change, c.kind, c.id, f.name, _show(f.before), _show(f.after)] for f in c.fields
            ]
        else:
            rows.append([c.change, c.kind, c.id, "", "", ""])
    return rows
