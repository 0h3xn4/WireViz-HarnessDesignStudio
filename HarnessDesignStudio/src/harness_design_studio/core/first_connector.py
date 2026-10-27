"""The first connector of a new device (Release 1.9, W1): which connector parts the library offers
as a family, a pin count and a gender, and one plan that adds a device with that connector.

A person who thinks in devices and connections picks "Micro-D, 15 pins, female", not a part ID. The
parts keep their IDs; the family is the ID without its pin count and gender (`EX-MICROD-15-F` is in
the family `EX-MICROD`). Nothing here adds a model field: the connector is an ordinary box
connector (`devices.ops_add_connector`) and the pins are `1` to `N` with no signals, to be named in
the Devices tab or paired by number in the connection window.

    choices = connector_choices(project)         # sorted: family, pin count, gender
    ops, unit_id, connector_id = plan_device_with_connector(project, part_id, name="OBC", ...)
"""

import re
from dataclasses import dataclass

from . import devices, edit
from .commands import Op
from .describe import part_gender
from .model import Project

_TAIL = re.compile(r"(-\d+)?(-[MF])?$")
_LEAD = re.compile(r"^(.*?)\s+\d+-pin\b", re.IGNORECASE)


@dataclass(frozen=True)
class ConnectorChoice:
    part_id: str
    family: str  # the key: the part ID without pin count and gender
    label: str  # the family as a person reads it ("Micro-D", "D-sub")
    pin_count: int
    gender: str  # "male", "female" or "unspecified"


def part_family(part_id: str) -> str:
    """`EX-MICROD-15-F` -> `EX-MICROD`; an ID that does not end that way is its own family."""
    return _TAIL.sub("", part_id) or part_id


def connector_choices(project: Project) -> list[ConnectorChoice]:
    """The connector parts that have a pin count, ready to be picked as family, pins and gender."""
    out: list[ConnectorChoice] = []
    for p in project.parts.values():
        if p.category != "connector" or not p.pin_count:
            continue
        family = part_family(p.id)
        found = _LEAD.match(p.description or "")
        label = found.group(1).strip() if found else family
        out.append(ConnectorChoice(p.id, family, label, p.pin_count, part_gender(p)))
    order = {"male": 0, "female": 1, "unspecified": 2}
    out.sort(key=lambda c: (c.label.casefold(), c.family, c.pin_count, order[c.gender], c.part_id))
    return out


def plan_device_with_connector(
    project: Project, part_id: str | None, **device: object
) -> tuple[list[Op], str, str | None]:
    """The operations for a new device (`devices.ops_add_device` with these fields) and, when
    `part_id` is given, its first connector of that part. Returns (ops, unit ID, connector ID or
    None). Raises `EditError` with the reason when either cannot be made."""
    ops, uid = devices.ops_add_device(project, **device)  # type: ignore[arg-type]
    if not part_id:
        return ops, uid, None
    more, cid = devices.ops_add_connector(edit.clone_with(project, ops), uid, part_id=part_id)
    return [*ops, *more], uid, cid
