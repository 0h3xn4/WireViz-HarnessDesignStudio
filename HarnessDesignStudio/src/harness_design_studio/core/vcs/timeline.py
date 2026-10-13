"""The change log and differences as rows a view can show: the timeline of reviews, releases and
new revisions, a comparison of two revisions (or a revision and the working design), and its
changes grouped by kind of object, with values written so that a person can read them. It only
reads; the wording of events and the diff itself are those of `report` and `diff`."""

from dataclasses import dataclass, field
from typing import Any

from harness_design_studio.core.model import Project

from .diff import KIND_NAMES, Diff, ObjectChange, _show, diff_snapshots
from .release import ReleaseError
from .report import EVENTS, baselines_of, one_line, working_diff

__all__ = [
    "DiffGroup",
    "DiffRow",
    "ReleaseError",
    "TimelineRow",
    "compare_revisions",
    "diff_groups",
    "diff_rows",
    "field_label",
    "format_value",
    "timeline",
]


@dataclass(frozen=True)
class TimelineRow:
    id: str  # the change log entry, "C0001"
    harness_id: str
    revision: str
    kind: str  # "review" | "release" | "new_revision"
    event: str  # the same words as the change log table
    by: str
    when: str
    comment: str  # on one line
    has_baseline: bool  # a frozen revision exists to compare with


def timeline(project: Project, harness_id: str | None = None) -> list[TimelineRow]:
    """The change log in the order of its entries, for all harnesses or one."""
    have = {(b.harness_id, b.revision) for b in project.baselines.values()}
    return [
        TimelineRow(
            e.id,
            e.harness_id,
            e.revision,
            e.kind,
            EVENTS[e.kind],
            one_line(e.by),
            e.when,
            one_line(e.comment),
            (e.harness_id, e.revision) in have,
        )  # fmt: skip
        for e in sorted(project.changelog.values(), key=lambda x: x.id)
        if harness_id is None or e.harness_id == harness_id
    ]


def compare_revisions(
    project: Project, harness_id: str, before: str, after: str | None = None
) -> Diff:
    """What changed in `harness_id` from revision `before` to revision `after`, or to the working
    design when `after` is None."""
    bases = {b.revision: b for b in baselines_of(project, harness_id)}
    for rev in (before, after):
        if rev is not None and rev not in bases:
            raise ReleaseError(f"There is no revision {rev} of {harness_id} to compare with.")
    if after is not None:
        return diff_snapshots(bases[before].snapshot, bases[after].snapshot)
    h = project.harnesses.get(harness_id)
    if h is None:
        raise ReleaseError(f"{harness_id} is no longer in the design, so it has no working design.")
    return working_diff(project, h, bases[before])


# ---- readable diffs --------------------------------------------------------------------------------


def format_value(v: Any) -> str:
    """A value as the diff reports show it ("(none)", "(empty)", IDs of objects, at most 80
    characters), also inside tables and lists, so that no `None` or Python representation reaches
    a person."""
    if isinstance(v, dict):
        text = ", ".join(f"{k}: {format_value(x)}" for k, x in v.items()) or "(empty)"
        return text if len(text) <= 80 else text[:77] + "..."
    if isinstance(v, list) and any(x is None or isinstance(x, dict | list) and x for x in v):
        text = ", ".join(
            str(x.get("id", format_value(x)))
            if isinstance(x, dict) and "id" in x
            else format_value(x)
            for x in v
        )
        return text if len(text) <= 80 else text[:77] + "..."
    return _show(v)


_WORDS = {"awg": "AWG", "id": "ID", "emc": "EMC", "rf": "RF", "ids": "IDs"}
_UNITS = {"m": "(m)", "v": "(V)", "a": "(A)", "g": "(g)", "c": "(degC)", "mm2": "(mm2)"}


def field_label(name: str) -> str:
    """A field name as words: "length_m" -> "Length (m)", "gauge_awg" -> "Gauge AWG"."""
    parts = name.split("_")
    if len(parts) > 1 and parts[-1] in _UNITS:
        parts[-1] = _UNITS[parts[-1]]
    words = [_WORDS.get(p, p) for p in parts]
    text = " ".join(words)
    return text[:1].upper() + text[1:]


@dataclass(frozen=True)
class DiffRow:
    change: str  # "added" | "removed" | "changed"
    kind: str
    kind_name: str  # "Wire", "Box pin" ... (`diff.KIND_NAMES`)
    id: str
    field: str  # "" for an added or removed object
    label: str  # the field as words
    before: str
    after: str


def _rows(c: ObjectChange) -> list[DiffRow]:
    name = KIND_NAMES.get(c.kind, c.kind)
    if not c.fields:
        return [DiffRow(c.change, c.kind, name, c.id, "", "", "", "")]
    return [
        DiffRow(c.change, c.kind, name, c.id, f.name, field_label(f.name), format_value(f.before), format_value(f.after))
        for f in c.fields
    ]  # fmt: skip


def diff_rows(diff: Diff) -> list[DiffRow]:
    """One row per field change (one per object when it was added or removed), in the order of
    `diff.to_table`."""
    return [row for c in diff.changes for row in _rows(c)]


@dataclass(frozen=True)
class DiffGroup:
    kind: str
    name: str
    rows: tuple[DiffRow, ...] = field(default_factory=tuple)

    @property
    def counts(self) -> dict[str, int]:
        """Objects added, removed and changed in this group (not rows)."""
        objects: dict[str, set[str]] = {"added": set(), "removed": set(), "changed": set()}
        for r in self.rows:
            objects[r.change].add(r.id)
        return {k: len(v) for k, v in objects.items()}


def diff_groups(diff: Diff) -> list[DiffGroup]:
    """The rows grouped by kind of object, in the order of `KIND_NAMES`; kinds it does not know
    follow, sorted."""
    rows = diff_rows(diff)
    kinds = [k for k in KIND_NAMES if any(r.kind == k for r in rows)]
    kinds += sorted({r.kind for r in rows} - set(KIND_NAMES))
    return [
        DiffGroup(k, KIND_NAMES.get(k, k), tuple(r for r in rows if r.kind == k)) for k in kinds
    ]
