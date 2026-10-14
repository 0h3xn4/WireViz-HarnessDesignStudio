"""Mass of a harness from library data. Missing data is reported, never replaced by a guess."""

from dataclasses import dataclass, field

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
            r.total_g += part.mass_per_m_g * length
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
