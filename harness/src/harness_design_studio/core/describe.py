"""Plain-language captions for the diagram: what a link carries and what a connector is.

Pure functions of the project (no Qt). They only repeat what the project data says: a voltage or
a current shows when somebody entered it, and nothing is filled in from a standard.
"""

import re

from harness_design_studio.core.model import Part
from harness_design_studio.core.model.physical import Gender
from harness_design_studio.core.model.project import Project

_GENDER = {"male": "M", "female": "F"}


def _num(value: float) -> str:
    return f"{value:g}"


def link_caption(project: Project, interface_id: str) -> str:
    """ "CAN", or "Primary power · 28 V · 5 A" when the voltage and the current are set."""
    i = project.interfaces.get(interface_id)
    if i is None:
        return interface_id
    t = project.interface_types.get(i.type_id)
    parts = [t.name if t is not None else i.type_id]
    if i.voltage_v is not None:
        parts.append(f"{_num(i.voltage_v)} V")
    if i.max_current_a is not None:
        parts.append(f"{_num(i.max_current_a)} A")
    return " · ".join(parts)


def part_gender(part: Part | None) -> Gender:
    """ "male", "female" or "unspecified", as the library part says it in its description (e.g.
    "D-sub 9-pin, female"); where it says both ("male plug, mates with female socket") the first
    word counts. A part that does not say gives "unspecified"; nothing is guessed."""
    text = (part.description or "").lower() if part is not None else ""
    found = re.search(r"\b(female|male)\b", text)
    if found is None:
        return "unspecified"
    return "female" if found.group(1) == "female" else "male"


def link_values(project: Project, interface_id: str) -> str:
    """ "28 V · 5 A": only what somebody entered, nothing when neither is set."""
    i = project.interfaces.get(interface_id)
    if i is None:
        return ""
    parts = []
    if i.voltage_v is not None:
        parts.append(f"{_num(i.voltage_v)} V")
    if i.max_current_a is not None:
        parts.append(f"{_num(i.max_current_a)} A")
    return " · ".join(parts)


def connector_kind(project: Project, connector_id: str) -> str:
    """Short connector type: "D-sub 15-pin F" (from the part description and the gender)."""
    c = project.connectors.get(connector_id)
    if c is None:
        return ""
    part = project.parts.get(c.part_id)
    text = (part.description or part.part_number or part.id) if part is not None else c.part_id
    text = re.sub(r"\s*\([^)]*\)", "", text)  # "(example)" and the like
    text = re.sub(r",?\s*\b(fe)?male\b", "", text, flags=re.IGNORECASE).strip(" ,")
    gender = _GENDER.get(c.gender, "")
    return f"{text} {gender}".strip()


def connector_family(project: Project, connector_id: str) -> tuple[str, int, str]:
    """(family, pin count, gender) for drawing a connector: family is one of "dsub", "microd",
    "circular", "rj45", "coax" or "generic". It is read from the part's description."""
    c = project.connectors.get(connector_id) or project.all_connectors().get(connector_id)
    if c is None:
        return "generic", 0, ""
    part = project.parts.get(c.part_id)
    described = f"{part.description or ''} {part.part_number or ''}" if part is not None else ""
    text = f"{described} {c.part_id}".lower()
    pins = part.pin_count if part is not None and part.pin_count else 0
    family = "generic"
    for key, name in (
        ("micro-d", "microd"),
        ("microd", "microd"),
        ("mdm", "microd"),
        ("d-sub", "dsub"),
        ("dsub", "dsub"),
        ("circular", "circular"),
        ("38999", "circular"),
        ("rj45", "rj45"),
        ("coax", "coax"),
        ("sma", "coax"),
        ("tnc", "coax"),
    ):
        if re.search(
            rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", text
        ):  # a word, not part of one
            family = name
            break
    gender = c.gender if c.gender != "unspecified" else part_gender(part)
    return family, pins, gender


FAMILY_LABEL = {
    "dsub": "D-sub",
    "microd": "Micro-D / MDM",
    "circular": "Circular",
    "rj45": "RJ45",
    "coax": "Coax",
    "generic": "Other",
}
