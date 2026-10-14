"""Consistency of released harnesses with their baselines (used by the rules and `harness-design-studio check`)."""

from harness_design_studio.core.issues import Issue
from harness_design_studio.core.model import Harness, Project, Snapshot

from .locks import _pins_equal, interface_design, part_design, type_design, unit_design
from .snapshot import frozen_config, normalize


def release_integrity(project: Project) -> list[Issue]:
    """Errors for released harnesses that no longer match their baseline (edited after release,
    or damaged by a merge) or have none."""
    out: list[Issue] = []
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        if h.status != "released":
            stale = project.baselines.get(f"{h.id}.{h.revision}")
            if stale is not None:
                out.append(
                    Issue(
                        "error",
                        "released_modified",
                        f"{h.id} has a baseline for revision {h.revision} but is no longer released; it was set back to {h.status} by hand. Start a new revision instead.",
                        None,
                        h.id,
                    )
                )
            continue
        b = project.baselines.get(f"{h.id}.{h.revision}")
        if b is None:
            out.append(
                Issue(
                    "error",
                    "released_without_baseline",
                    f"{h.id} is released (revision {h.revision}) but has no baseline.",
                    None,
                    h.id,
                )
            )
        elif not b.snapshot.harnesses or normalize(b.snapshot.harnesses[0]) != normalize(h):
            out.append(_modified(h))
        elif any(
            (now := project.interfaces.get(i.id)) is None
            or interface_design(now) != interface_design(i)
            for i in b.snapshot.interfaces
        ):
            out.append(_modified(h, "an interface it carries was changed"))
        elif any(
            (unit_now := project.units.get(u.id)) is None or unit_design(unit_now) != unit_design(u)
            for u in b.snapshot.units
        ):
            out.append(_modified(h, "a unit it connects to was changed"))
        elif _box_connector_changed(project, b.snapshot):
            out.append(_modified(h, "a box connector it plugs into was changed"))
        elif changed := _used_data_changed(project, b.snapshot):
            out.append(_modified(h, changed, REVISE))
    return out


def _used_data_changed(project: Project, snapshot: Snapshot) -> str:
    """Says which parts, interface types or configuration the release recorded have changed
    since. A baseline made before these were recorded (the field is None) is not compared."""
    parts = [
        p.id
        for p in snapshot.parts or []
        if (now := project.parts.get(p.id)) is None or part_design(now) != part_design(p)
    ]
    if parts:
        return f"part {_list(parts)} it uses was changed"
    types = [
        t.id
        for t in snapshot.interface_types or []
        if (now_t := project.interface_types.get(t.id)) is None
        or type_design(now_t) != type_design(t)
    ]
    if types:
        return f"interface type {_list(types)} it uses was changed"
    if snapshot.config is not None:
        now_c = frozen_config(project)
        files = sorted(
            n for n in set(snapshot.config) | set(now_c) if snapshot.config.get(n) != now_c.get(n)
        )
        if files:
            return f"configuration {_list(files)} it depends on was changed"
    return ""


def _list(ids: list[str]) -> str:
    return ", ".join(ids[:3]) + (f" and {len(ids) - 3} more" if len(ids) > 3 else "")


def _box_connector_changed(project: Project, snapshot: Snapshot) -> bool:
    """A stored box connector is gone, or its part, gender, keying or the pins that carry the
    harness's interfaces differ (other pins and labels may change)."""
    carried = {i.id for i in snapshot.interfaces}
    return any(
        (now := project.connectors.get(c.id)) is None or not _pins_equal(c, now, carried)
        for c in snapshot.connectors
    )


REVISE = "Undo the change, or start a new revision of the harness and make it there."


def _modified(h: Harness, what: str = "", how: str = "") -> Issue:
    detail = f" ({what})" if what else ""
    tail = f" {how}" if how else ""
    return Issue(
        "error",
        "released_modified",
        f"{h.id} was changed after its release (revision {h.revision}){detail}; it no longer matches its baseline.{tail}",
        None,
        h.id,
    )
