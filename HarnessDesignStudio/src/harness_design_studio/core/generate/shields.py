# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Which wires of a harness form a shield group, and with what ends (decision of D-191, S1).

The generator and the explanation (`core.derive_build`) call the same two functions, so the group
an explanation names is the group generation made. A group follows the construction and the
shielding of the interface type: a coax wire has its own group, a quad is one group, a pair of a
type is a twisted pair, or a shielded pair when the type shields per pair, and the whole interface
is one more group when the type shields overall. The ends of a group are the grounding concept of
`config/generation.json` (`shield_end_a`, `shield_end_b`); a coax shield has the fixed end of the
format (bonded at both ends).
"""

from dataclasses import dataclass
from typing import Any, cast

from harness_design_studio.core.model import InterfaceInstance, Project, Wire
from harness_design_studio.core.model.physical import COAX_SHIELD_END

END_CHOICES = ("backshell_360", "pigtail", "floating")
FLOATING = "floating"


@dataclass(frozen=True)
class Planned:
    """A group generation makes: its kind, its wires, the interface it is made for, and why."""

    kind: str
    wires: list[Wire]
    interface_id: str
    why: str


def concept_ends(gen: dict[str, object]) -> tuple[Any, Any, bool]:
    """(end A, end B, placeholder) of the grounding concept: a value that is not set or not one of
    the choices is `floating`, and `placeholder` says that one of the two was not set."""
    ends = [gen.get("shield_end_a"), gen.get("shield_end_b")]
    a, b = (cast(Any, e if isinstance(e, str) and e in END_CHOICES else FLOATING) for e in ends)
    return a, b, ends[0] is None or ends[1] is None


def pair_names(project: Project, i: InterfaceInstance) -> dict[str, str | None]:
    """The pair of each signal of the interface's type: its `pair`, or `power` for a power or
    ground type (the way out and the way back are twisted together), else none."""
    t = project.interface_types[i.type_id]
    return {
        s.name: (s.pair or ("power" if t.category in ("power", "ground") else None))
        for s in t.signals
    }


def plan(project: Project, ifaces: list[InterfaceInstance], wires: list[Wire]) -> list[Planned]:
    """The shield groups of the wires of the interfaces, in the order generation makes them."""
    out: list[Planned] = []
    for i in ifaces:
        t = project.interface_types[i.type_id]
        mine = [w for w in wires if w.interface_id == i.id]
        if t.construction in ("single",):
            continue
        if t.construction == "coax":
            out += [
                Planned("coax", [w], i.id, f"the type {t.id} is a coax: each wire is one shield")
                for w in mine
            ]
            continue
        if t.construction == "quad":
            out.append(Planned("quad", mine, i.id, f"the type {t.id} is a quad: one group"))
            continue
        pair_of = pair_names(project, i)
        groups: dict[str, list[Wire]] = {}
        for w in mine:
            src = w.signal.split("/")[0] if w.signal else ""
            name = pair_of.get(src)
            if name is not None:
                groups.setdefault(f"{name}|{w.from_connector}", []).append(w)
        kind = "shielded_pair" if t.shielding == "per_pair" else "twisted_pair"
        for key in sorted(groups):
            out.append(
                Planned(
                    kind,
                    groups[key],
                    i.id,
                    f"the wires of pair {key.split('|')[0]} of {i.id} are twisted together"
                    + (" and shielded per pair" if kind == "shielded_pair" else "")
                    + f" (type {t.id}, shielding {t.shielding or 'none'})",
                )
            )
        if t.shielding == "overall":
            out.append(
                Planned(
                    "overall_shield",
                    mine,
                    i.id,
                    f"the type {t.id} shields overall: one shield over all the wires of {i.id}",
                )
            )
    return out


def ends_of(kind: str, a: Any, b: Any) -> tuple[Any, Any]:
    """The ends a group of this kind gets: the concept's, or the fixed ones of a coax."""
    return (COAX_SHIELD_END, COAX_SHIELD_END) if kind == "coax" else (a, b)
