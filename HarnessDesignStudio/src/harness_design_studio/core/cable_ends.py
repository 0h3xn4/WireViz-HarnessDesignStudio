"""The ends of the cables a person drew, as the diagram shows them (M4c of the programme, D-201).

    ends = drawn_ends(project)           # every end the block diagram draws, by harness and ID
    box = free_port(project, "OBC")      # the connector of a device a new cable goes into
    box = plug_port(project, "W009", "W009-P2", "RW1")   # the connector a loose end plugs into
    hid = harness_of(project, "W009-P2") # the harness a cable connector belongs to

A cable drawn by hand is a harness (`core/manual_harness.py`); it has no `Link`, so the lines of
connections do not show it. The diagram draws it from what this module says: each **loose end**
of a harness that is plugged in somewhere hangs on a dashed line out of the port the harness
plugs into (its *anchor*), and each further connector of a harness drawn by hand that is plugged
into another device is a line from that anchor to its port. A harness made from a connection is
drawn by the connection's own line, so only its loose ends are added here; a harness Generate made
has neither. A loose end of a harness that is plugged in nowhere has no place on the diagram: it is
listed in the project tree and reached from the menu.

Where an end hangs is the diagram mark `pos:<connector id>` (an offset from the place the diagram
gives it, outside the model hash; `core/io/layout.py` drops it when the connector goes). Pure
functions of the project; they change nothing and know nothing of a screen.
"""

from dataclasses import dataclass

from .edit import EditError, unit_connectors
from .integrity import mating_plugs
from .manual_harness import plan_plug_loose_end, propose_plug
from .model import Connector, Harness, Project
from .model.physical import LOOSE_ROLE

POS_KIND = "pos"


def pos_mark(connector_id: str) -> str:
    """The ID of the diagram mark that keeps where a loose end hangs."""
    return f"{POS_KIND}:{connector_id}"


@dataclass(frozen=True)
class CableEnd:
    """One end the diagram draws. `anchor` is the device connector the harness is plugged into
    (where the line starts) and `anchor_unit` its device; a loose end (`loose`) hangs in the air
    at its `index` among the loose ends of the same anchor, a plugged end sits on `target` (a
    device connector) of `target_unit`."""

    harness_id: str
    connector_id: str
    name: str
    loose: bool
    anchor: str
    anchor_unit: str
    target: str = ""
    target_unit: str = ""
    index: int = 0
    pins: int = 0


def harness_of(project: Project, connector_id: str) -> Harness | None:
    """The harness that holds the cable connector `connector_id`, or None."""
    for h in project.harnesses.values():
        if any(c.id == connector_id for c in h.connectors):
            return h
    return None


def connector_of(project: Project, connector_id: str) -> tuple[Harness, Connector] | None:
    """(harness, connector) of a cable connector, or None."""
    for h in project.harnesses.values():
        for c in h.connectors:
            if c.id == connector_id:
                return h, c
    return None


def all_loose_ends(project: Project) -> list[tuple[str, Connector]]:
    """Every loose end of the project as (harness ID, connector), by harness and connector ID."""
    out: list[tuple[str, Connector]] = []
    for hid in sorted(project.harnesses):
        for c in sorted(project.harnesses[hid].connectors, key=lambda x: x.id):
            if c.role == LOOSE_ROLE:
                out.append((hid, c))
    return out


def _plugged(project: Project, h: Harness) -> list[tuple[Connector, Connector]]:
    """The connectors of a harness that sit on a connector of a device, with that connector."""
    out = []
    for c in sorted(h.connectors, key=lambda x: x.id):
        box = project.connectors.get(c.mates_with or "")
        if box is not None and box.role == "box" and box.unit_id in project.units:
            out.append((c, box))
    return out


def drawn_ends(project: Project) -> list[CableEnd]:
    """The ends of cables drawn by hand that the diagram draws (see the module)."""
    linked = {x.harness_id for x in project.links.values() if x.harness_id}
    out: list[CableEnd] = []
    for hid in sorted(project.harnesses):
        h = project.harnesses[hid]
        if h.generated:
            continue
        plugged = _plugged(project, h)
        if not plugged:
            continue
        anchor = plugged[0][1]
        index = 0
        for c in sorted(h.connectors, key=lambda x: x.id):
            if c.role != LOOSE_ROLE:
                continue
            out.append(
                CableEnd(
                    hid, c.id, c.name, True, anchor.id, anchor.unit_id or "",
                    index=index, pins=len(c.pins),
                )
            )
            index += 1
        if hid in linked:  # the connection's own line shows the plugged ends
            continue
        for c, box in plugged[1:]:
            out.append(
                CableEnd(
                    hid, c.id, c.name, False, anchor.id, anchor.unit_id or "",
                    box.id, box.unit_id or "", pins=len(c.pins),
                )
            )
    return out


def free_port(project: Project, unit_id: str) -> str | None:
    """The connector of a device a new cable from the device as a whole goes into (Guided and
    Quick show one port per device): the first by ID that has pins and no cable plug on it yet;
    None when there is none."""
    plugs = mating_plugs(project.harnesses.values())
    for c in unit_connectors(project, unit_id):
        if c.pins and c.id not in plugs:
            return c.id
    return None


def plug_port(project: Project, harness_id: str, loose_id: str, unit_id: str) -> str:
    """The connector of the device `unit_id` that the loose end plugs into when it is dropped on
    the device as a whole: the first by ID with no cable plug on it whose pins pair with the end's
    (by name; else by number with no names that disagree). Raises `EditError` with the reason the
    first candidate gives when none does."""
    plugs = mating_plugs(project.harnesses.values())
    candidates = [c.id for c in unit_connectors(project, unit_id) if c.id not in plugs and c.pins]
    if not candidates:
        raise EditError(f"{unit_id} has no connector a cable end can plug into.")
    proposals = {}
    for cid in candidates:
        try:
            proposals[cid] = propose_plug(project, harness_id, loose_id, cid)
        except EditError:
            continue
    for wanted in ("signal", "number"):  # a connector whose pin names fit comes first
        for cid, prop in proposals.items():
            if prop.by == wanted and prop.pairs and not prop.disagreements:
                return cid
    plan_plug_loose_end(project, harness_id, loose_id, candidates[0])  # raises with the reason
    return candidates[0]  # pragma: no cover - the plan above refuses


__all__ = [
    "POS_KIND",
    "CableEnd",
    "all_loose_ends",
    "connector_of",
    "drawn_ends",
    "free_port",
    "harness_of",
    "plug_port",
    "pos_mark",
]
