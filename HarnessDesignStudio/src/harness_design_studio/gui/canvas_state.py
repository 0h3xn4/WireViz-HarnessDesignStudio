"""What the diagram says about each object: problems, values still to enter, not checked, auto-filled
connectors and release locks, as an index id -> `ObjectState`.

The index is built from what the controller already holds (the open findings and the release
locks), once per change and never while painting: the items read it with a dictionary lookup and
repaint only when their own entry changed (`StateIndex.changed_from`). Nothing here is Qt; it works
on plain data, so it is tested without a window.

What a count means for one object:
  errors, warnings   open findings (waived ones are left out) that point at the object: a unit
                     (also through its connectors or the parts it uses), a link (also through
                     its wires). Information-level findings are not counted.
  pending            values still to enter: on a link the voltage and current of a power link
                     (`describe.link_missing`); on a unit the sum of its links'.
  not_checked        1 while the design check has not produced a result for this project (it
                     never ran, or it failed), so an object without problems is not taken for a
                     passed one; a check that is merely out of date keeps showing its last result.
  auto               connectors the tool chose and nobody confirmed.
  locks              the released harnesses (ID, revision) that lock the object.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from harness_design_studio.core import describe, drc
from harness_design_studio.core.checks import Finding
from harness_design_studio.core.model import Project

# The states a badge can show, most serious first; the key is a `states.STATES` key.
BADGE_ORDER = ("fail", "warning", "pending", "not-checked")
MAX_COUNT = 99  # a badge never shows more than this ("99+")

Locked = Mapping[tuple[str, str], Sequence[tuple[str, str]]]


@dataclass(frozen=True)
class ObjectState:
    errors: int = 0
    warnings: int = 0
    pending: int = 0
    not_checked: int = 0
    auto: int = 0
    locks: tuple[tuple[str, str], ...] = ()  # (harness ID, revision)

    @property
    def problems(self) -> int:
        return self.errors + self.warnings

    @property
    def clear(self) -> bool:
        """Nothing to show: no problem, nothing pending or unchecked, no auto, no lock."""
        return self == EMPTY

    @property
    def lock_text(self) -> str:
        """ "W001 A" (the first harness that locks it, and its revision), "W001 A +1" for more."""
        if not self.locks:
            return ""
        first = " ".join(self.locks[0])
        return first + (f" +{len(self.locks) - 1}" if len(self.locks) > 1 else "")

    def count_of(self, state: str) -> int:
        return {
            "fail": self.errors,
            "warning": self.warnings,
            "pending": self.pending,
            "not-checked": self.not_checked,
        }[state]

    def badges(self) -> list[tuple[str, int]]:
        """(state key, count) for every state that applies, most serious first."""
        return [(k, n) for k in BADGE_ORDER if (n := self.count_of(k))]

    def sentence(self, kind: str = "unit") -> str:
        """Plain words for the tooltip of the badges ("2 problems, 1 warning, ..."); "" when
        there is nothing to say."""
        parts: list[str] = []
        if self.errors:
            parts.append(f"{self.errors} problem{'s' if self.errors != 1 else ''}")
        if self.warnings:
            parts.append(f"{self.warnings} warning{'s' if self.warnings != 1 else ''}")
        if self.pending:
            what = "value" if self.pending == 1 else "values"
            parts.append(f"{self.pending} {what} still to enter")
        if self.not_checked:
            parts.append("not checked yet (the design check has no result)")
        return ", ".join(parts)


EMPTY = ObjectState()


def badge_text(count: int, state: str) -> str:
    """What a badge writes next to its icon: the count (99+ at most); nothing for "not checked"
    with a count of one, where a number would say nothing."""
    if state == "not-checked" and count <= 1:
        return ""
    return f"{MAX_COUNT}+" if count > MAX_COUNT else str(count)


class StateIndex:
    """`of(kind, id)` for kind "unit", "interface", "link" (a connection of two connectors, which
    shows problems only) or "connector" (a unit's box connector, which carries a lock only)."""

    def __init__(
        self,
        states: dict[tuple[str, str], ObjectState],
        findings: dict[tuple[str, str], tuple[str, ...]],
        *,
        checked: bool,
    ) -> None:
        self._states = states
        self._findings = findings
        self.checked = checked

    def of(self, kind: str, ident: str) -> ObjectState:
        return self._states.get((kind, ident), EMPTY)

    def finding_ids(self, kind: str, ident: str) -> tuple[str, ...]:
        """The IDs of the findings counted for an object, for a Problems list filtered to it."""
        return self._findings.get((kind, ident), ())

    def keys(self) -> Iterable[tuple[str, str]]:
        return self._states.keys()

    def changed_from(self, old: StateIndex) -> set[tuple[str, str]]:
        """The objects whose entry differs from `old`'s: the only ones that need repainting."""
        out = {k for k, v in self._states.items() if old._states.get(k, EMPTY) != v}
        out |= {k for k in old._states if k not in self._states}
        return out

    def quiet(self) -> StateIndex:
        """The same index without the notices that nobody asked for: problems, warnings, values
        still to enter and "not checked" are zero; the locks and the auto marks stay."""
        quiet = {
            k: ObjectState(auto=v.auto, locks=v.locks)
            for k, v in self._states.items()
            if v.auto or v.locks
        }
        return StateIndex(quiet, self._findings, checked=self.checked)

    def present(self) -> tuple[bool, bool, bool, bool, bool]:
        """(a problem, a warning, a pending value, a lock, an unchecked object) somewhere: what the
        legend lists."""
        s = self._states.values()
        return (
            any(v.errors for v in s),
            any(v.warnings for v in s),
            any(v.pending for v in s),
            any(v.locks for v in s),
            any(v.not_checked for v in s),
        )


NO_INDEX = StateIndex({}, {}, checked=True)


def _resolver(project: Project) -> Any:
    """A function: finding object ID -> the canvas objects it belongs to, [(kind, id)]. Cheap
    dictionary lookups first (units, links, box connectors, wires, parts); `drc.locate` only for
    the odd composite ID, and cached, so thousands of findings stay fast."""
    wire_link: dict[str, str] | None = None
    part_units: dict[str, set[str]] | None = None
    harness_objects: set[str] | None = None
    cache: dict[str, list[tuple[str, str]]] = {}

    def lazy_wires() -> dict[str, str]:
        nonlocal wire_link
        if wire_link is None:
            wire_link = {
                w.id: w.interface_id
                for h in project.harnesses.values()
                for w in h.wires
                if w.interface_id
            }
        return wire_link

    def lazy_parts() -> dict[str, set[str]]:
        nonlocal part_units
        if part_units is None:
            part_units = defaultdict(set)
            for c in project.connectors.values():
                if c.role == "box" and c.unit_id:
                    part_units[c.part_id].add(c.unit_id)
        return part_units

    def lazy_harness_objects() -> set[str]:
        nonlocal harness_objects
        if harness_objects is None:
            harness_objects = {w.id for h in project.harnesses.values() for w in h.wires}
            harness_objects.update(c.id for h in project.harnesses.values() for c in h.connectors)
        return harness_objects

    def canvas_place(oid: str) -> tuple[str, str] | None:
        """What `drc.locate` answers, for the two kinds the diagram has (a unit or a link); an
        answer that names a harness is None here. `drc.locate` scans every wire of every harness
        for an ID that is not a unit or a link, which for 20,000 findings on 20,000 wires took
        11 seconds on the GUI thread; a set of the harness objects answers the same at once."""
        if oid in project.units:
            return ("unit", oid)
        if oid in project.interfaces:
            return ("interface", oid)
        if oid in project.harnesses:
            return None
        box = project.connectors.get(oid)
        if box is not None and box.unit_id:
            return ("unit", box.unit_id)
        if oid in lazy_harness_objects():
            return None
        parts = oid.split(".")
        if parts[0] in ("wire-spec", "mating-cycles") and len(parts) == 2:
            where = drc.locate(project, oid)  # one per part: the scan is paid a few times only
            return where if where is not None and where[0] in ("unit", "interface") else None
        if parts[0] == "emc-class" and len(parts) > 2 and parts[2] in project.units:
            return ("unit", parts[2])
        return canvas_place(parts[0]) if parts[0] != oid else None

    def resolve(oid: str) -> list[tuple[str, str]]:
        got = cache.get(oid)
        if got is not None:
            return got
        out: list[tuple[str, str]] = []
        if oid in project.units:
            out = [("unit", oid)]
        elif oid in project.interfaces:
            out = [("interface", oid)]
        elif oid in project.links:
            out = [("link", oid)]
        elif (c := project.connectors.get(oid)) is not None and c.unit_id:
            out = [("unit", c.unit_id)]
        elif oid in lazy_wires():
            out = [("interface", lazy_wires()[oid])]
        elif oid in project.parts:
            out = [("unit", u) for u in sorted(lazy_parts().get(oid, ()))]
        else:
            where = canvas_place(oid)
            if where is not None:
                out = [where]
            else:  # a wire spec or the like: the links that run on that wire
                head = oid.split(".")[-1]
                if head in lazy_wires():
                    out = [("interface", lazy_wires()[head])]
        cache[oid] = out
        return out

    return resolve


def build_index(
    project: Project,
    findings: Iterable[Finding],
    locked: Locked | None = None,
    *,
    checked: bool = True,
) -> StateIndex:
    """The index of a project: `findings` are the open ones (`ctl.open_findings()`), `locked` is
    `lockview.locked_objects(project)`, `checked` says a design check result exists."""
    resolve = _resolver(project)
    errors: dict[tuple[str, str], int] = defaultdict(int)
    warnings: dict[tuple[str, str], int] = defaultdict(int)
    ids: dict[tuple[str, str], list[str]] = defaultdict(list)
    for f in findings:
        if f.severity not in ("error", "warning") or f.waiver is not None:
            continue
        for key in resolve(f.object_id):
            (errors if f.severity == "error" else warnings)[key] += 1
            ids[key].append(f.id)
    pending_link = {i: len(describe.link_missing(project, i)) for i in project.interfaces}
    pending_unit: dict[str, int] = defaultdict(int)
    auto_unit: dict[str, int] = defaultdict(int)
    auto_link: dict[str, int] = {}
    for iid, i in project.interfaces.items():
        n_auto = 0
        for e in i.endpoints:
            if e.auto:
                n_auto += 1
                auto_unit[e.unit_id] += 1
        auto_link[iid] = n_auto
        for u in {e.unit_id for e in i.endpoints}:
            pending_unit[u] += pending_link[iid]
    lock_of: dict[tuple[str, str], tuple[tuple[str, str], ...]] = {}
    for (kind, ident), refs in (locked or {}).items():
        mapped = {"unit": "unit", "interface": "interface", "box_connector": "connector"}.get(kind)
        if mapped and refs:
            lock_of[(mapped, ident)] = tuple((r[0], r[1]) for r in refs)
    not_checked = 0 if checked else 1
    states: dict[tuple[str, str], ObjectState] = {}

    def put(key: tuple[str, str], **kw: Any) -> None:
        s = ObjectState(
            errors=errors.get(key, 0),
            warnings=warnings.get(key, 0),
            locks=lock_of.get(key, ()),
            not_checked=not_checked if key[0] not in ("connector", "link") else 0,
            **kw,
        )
        if not s.clear:
            states[key] = s

    for uid in project.units:
        put(("unit", uid), pending=pending_unit.get(uid, 0), auto=auto_unit.get(uid, 0))
    for iid in project.interfaces:
        put(("interface", iid), pending=pending_link[iid], auto=auto_link[iid])
    for lid in project.links:  # (a connection shows the problems of its review)
        put(("link", lid))
    for key in lock_of:
        if key[0] == "connector":
            put(key)
    return StateIndex(states, {k: tuple(v) for k, v in ids.items()}, checked=checked)
