"""Consistency of released harnesses with their baselines (used by the rules and `harness check`)."""

from harness_design_studio.core.issues import Issue
from harness_design_studio.core.model import Harness, Project, Snapshot

from .locks import _pins_equal, interface_design, unit_design
from .snapshot import normalize


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
    return out


def _box_connector_changed(project: Project, snapshot: Snapshot) -> bool:
    """A stored box connector is gone, or its part, gender, keying or the pins that carry the
    harness's interfaces differ (other pins and labels may change)."""
    carried = {i.id for i in snapshot.interfaces}
    return any(
        (now := project.connectors.get(c.id)) is None or not _pins_equal(c, now, carried)
        for c in snapshot.connectors
    )


def _modified(h: Harness, what: str = "") -> Issue:
    detail = f" ({what})" if what else ""
    return Issue(
        "error",
        "released_modified",
        f"{h.id} was changed after its release (revision {h.revision}){detail}; it no longer matches its baseline.",
        None,
        h.id,
    )
