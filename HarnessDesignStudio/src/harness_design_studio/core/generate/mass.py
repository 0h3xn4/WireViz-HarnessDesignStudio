"""Mass of a harness from library data. Missing data is reported, never replaced by a guess."""

from dataclasses import dataclass, field

from harness_design_studio.core import settings
from harness_design_studio.core.model import Harness, Project

from .lengths import wire_length


@dataclass
class MassReport:
    total_g: float = 0.0
    margin_g: float | None = None  # None while the margin fraction is a placeholder
    complete: bool = True
    missing: list[str] = field(default_factory=list)

    @property
    def with_margin_g(self) -> float | None:
        return None if self.margin_g is None else self.total_g + self.margin_g


def wire_mass_g(mass_per_m_g: float, length_m: float, conductors: int) -> float:
    """The mass of one wire: the mass per metre of its part times its length, divided by the
    conductors of the part (a twisted pair part carries 2 wires: each is one conductor of it).
    The one place that does this sum (the harness mass and the derivation of the mass call it)."""
    return mass_per_m_g * length_m / conductors


def pins_in_use(h: Harness) -> set[tuple[str, str]]:
    """The (connector, pin) pairs of the harness that have a wire attached."""
    used: set[tuple[str, str]] = set()
    for w in h.wires:
        used.add((w.from_connector, w.from_pin))
        used.add((w.to_connector, w.to_pin))
    return used


def _add_bom_parts(project: Project, h: Harness, r: MassReport) -> None:
    """The model full_bom counts what the connectors and the wires leave out: the contact parts (one
    for each pin that has a wire) and the accessories (by quantity, or by length for a part with a
    mass per metre), each by the mass of its part; a part without that mass is reported as missing."""
    used = pins_in_use(h)
    for c in h.connectors:
        for pin in c.pins:
            if not pin.contact_part or (c.id, pin.id) not in used:
                continue
            part = project.parts.get(pin.contact_part)
            if part is None or part.mass_g is None:
                r.missing.append(f"mass of contact part {pin.contact_part}")
            else:
                r.total_g += part.mass_g
    for a in h.accessories:
        if not a.part_id:
            continue
        part = project.parts.get(a.part_id)
        if a.length_mm is None:
            if part is None or part.mass_g is None:
                r.missing.append(f"mass of accessory part {a.part_id}")
            else:
                r.total_g += part.mass_g * a.quantity
        elif part is None or part.mass_per_m_g is None:
            r.missing.append(f"mass per metre of accessory part {a.part_id}")
        else:
            r.total_g += part.mass_per_m_g * (a.length_mm * a.quantity / 1000)


def harness_mass(project: Project, h: Harness) -> MassReport:
    r = MassReport()
    for c in h.connectors:
        part = project.parts.get(c.part_id)
        if part is None or part.mass_g is None:
            r.missing.append(f"mass of connector part {c.part_id}")
        else:
            r.total_g += part.mass_g
    for w in h.wires:
        part = project.parts.get(w.part_id) if w.part_id else None
        if part is None or part.mass_per_m_g is None:
            r.missing.append(f"mass per metre of wire part {w.part_id or '(none)'}")
        elif (length := wire_length(h, w)) is None:
            r.missing.append(f"length of wire {w.id}")
        else:
            r.total_g += wire_mass_g(part.mass_per_m_g, length, part.conductors)
    if settings.choice(project, "model", "mass_model") == "full_bom":
        _add_bom_parts(project, h, r)
    r.missing = sorted(set(r.missing))
    r.complete = not r.missing
    margin = (
        project.config["generation"].values.get("mass_margin_fraction")
        if "generation" in project.config
        else None
    )
    if isinstance(margin, int | float) and not isinstance(margin, bool):
        r.margin_g = r.total_g * float(margin)
    return r
