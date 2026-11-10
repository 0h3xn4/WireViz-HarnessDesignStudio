# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Where a harness came from: `interfaces`, `link` or `drawn` (M4, D-200 (3), D-201).

    harness_origin(project, "W001")      # "interfaces": Generate made it from the interfaces
    harness_origin(project, "W007")      # "link": made from a connection (`Link.harness_id`)
    harness_origin(project, "W009")      # "drawn": a person drew it

The origin is worked out from what the files already say, never stored: a harness is `interfaces`
when `Harness.generated` is true, else `link` when a connection names it, else `drawn`. Storing it
would change the model hash, the content hash and `system/export.json` of every project that has a
hand-made harness (the migration safety net refuses that), and a stored value could disagree with
the two facts it comes from. Generate never touches a harness whose origin is not `interfaces`;
that is what `generated` already means. Pure functions of the project; they change nothing.
"""

from .model import Project
from .model.physical import Origin


def harness_link(project: Project, harness_id: str) -> str | None:
    """The ID of the connection that made the harness (the first by ID when two say so), or None."""
    ids = sorted(x.id for x in project.links.values() if x.harness_id == harness_id)
    return ids[0] if ids else None


def harness_origin(project: Project, harness_id: str) -> Origin:
    """`interfaces` (made by Generate), `link` (made from a connection) or `drawn` (a person's)."""
    h = project.harnesses.get(harness_id)
    if h is not None and h.generated:
        return "interfaces"
    return "link" if harness_link(project, harness_id) is not None else "drawn"


def harness_origins(project: Project) -> dict[str, Origin]:
    """The origin of every harness, by ID (one pass, for a list of harnesses)."""
    linked = {x.harness_id for x in project.links.values() if x.harness_id}
    return {
        h.id: "interfaces" if h.generated else "link" if h.id in linked else "drawn"
        for h in project.harnesses.values()
    }


__all__ = ["harness_link", "harness_origin", "harness_origins"]
