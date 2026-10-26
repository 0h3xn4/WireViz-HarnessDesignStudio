"""A number of the same device (workshop feedback M4, point 20, D-175).

Redundancy is said by a NUMBER: "2 of these devices", not by choosing a nominal chain and a
redundant chain. The number is not stored; it is read from the devices the project has:

    device_count(project, "PCDU1")        # 1 + the copies PCDU1-R, PCDU1-3, ... that exist
    plan = plan_copies(project, "PCDU1", 3)    # makes PCDU1-R and PCDU1-3 (one undo step)

The second device of a pair is `ID-R`, exactly what *Create redundant copy* has always made (its
name ends in "(redundant)", it is on the redundant chain, and the links of the device are mirrored
onto it), so a project and its outputs are the same whichever way the copy was made. The third and
further devices are `ID-3`, `ID-4` ...: a copy of the same kind (redundant chain, same connectors,
links mirrored where the other end has a free connector of the right type; the others are named in
`skipped`). The tool only adds devices: a smaller number is reached by deleting a copy. Nothing is
stored in the project files that a device made by hand would not have.
"""

from dataclasses import dataclass

from .commands import Op
from .edit import EditError, clone_with, ops_redundant_copy, twin_id
from .model import Project

__all__ = [
    "MAX_DEVICES",
    "CopiesPlan",
    "copy_ids",
    "device_count",
    "is_copy",
    "plan_copies",
]

MAX_DEVICES = 10  # of one kind, the original included


def _suffix(position: int) -> str:
    """The ending of the copy that is device number `position` (2, 3, 4 ...): R, 3, 4 ..."""
    return "R" if position == 2 else str(position)


def copy_ids(unit_id: str, count: int) -> list[str]:
    """The IDs of the copies of a device made in `count` devices: none for 1, [`ID-R`] for 2,
    [`ID-R`, `ID-3`] for 3 ..."""
    return [twin_id(unit_id, _suffix(k)) for k in range(2, count + 1)]


def is_copy(project: Project, unit_id: str) -> bool:
    """True for a device on the redundant chain: it is a copy (or a backup chosen by hand) and is
    not itself made in a number."""
    unit = project.units.get(unit_id)
    return unit is not None and unit.side == "redundant"


def device_count(project: Project, unit_id: str) -> int:
    """How many of this device the project has: the device and its copies (`ID-R`, `ID-3` ...)."""
    if unit_id not in project.units:
        return 0
    have = {u.casefold() for u in project.units}
    return 1 + sum(1 for c in copy_ids(unit_id, MAX_DEVICES) if c.casefold() in have)


@dataclass(frozen=True)
class CopiesPlan:
    ops: list[Op]
    new_ids: tuple[str, ...]  # the devices that are added, in order
    skipped: tuple[
        str, ...
    ]  # links that could not be mirrored (no free connector at the other end)
    count: int  # the number of devices after the plan


def plan_copies(project: Project, unit_id: str, count: int) -> CopiesPlan:
    """The ops that bring the number of these devices up to `count` (one undo step). Raises
    `EditError` with a plain sentence when that cannot be done."""
    if unit_id not in project.units:
        raise EditError(f"Device '{unit_id}' does not exist.")
    if not isinstance(count, int) or isinstance(count, bool):
        raise EditError("The number of devices must be a whole number.")
    if count < 1 or count > MAX_DEVICES:
        raise EditError(f"The number of these devices is between 1 and {MAX_DEVICES}.")
    if is_copy(project, unit_id):
        raise EditError(
            f"{unit_id} is a copy; set the number on the device it was copied from "
            "(the one without -R or a number at the end)."
        )
    have = device_count(project, unit_id)
    if count <= have:
        raise EditError(
            f"There {'is' if have == 1 else 'are'} already {have} of these devices. "
            "To have fewer, delete a copy."
        )
    existing = {u.casefold() for u in project.units}
    todo = [
        k
        for k in range(2, MAX_DEVICES + 1)
        if twin_id(unit_id, _suffix(k)).casefold() not in existing
    ][: count - have]
    ops: list[Op] = []
    new_ids: list[str] = []
    skipped: list[str] = []
    scratch = project
    for k in todo:
        result = ops_redundant_copy(scratch, unit_id, _suffix(k))
        ops += result.ops
        new_ids.append(result.twin_id)
        skipped += [s for s in result.skipped if s not in skipped]
        scratch = clone_with(scratch, result.ops)
    return CopiesPlan(ops, tuple(new_ids), tuple(skipped), count)
