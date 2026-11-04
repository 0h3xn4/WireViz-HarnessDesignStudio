"""The units of the numeric fields of `system/export.json` (release 1.13, D-195, requirement R5).

`export.json` holds the model as saved, and a saved field states its unit in its name (`length_m`,
`max_current_a`) or has none because it is a count. A reader of the file alone should not have to
know that, so the file also holds an object `field_units`: the path of every numeric field to its
unit. This table is the one source of that object; `tests/test_export_units.py` checks it against
the fields of the model and against the numeric fields of real files, so a field added to the model
without an entry here fails a test.

A path is written the way `docs/OUTPUTS.md` writes it: a list is `[]`, an object key is `.key`
(`harnesses[].wires[].length_m`). The unit is an SI-style symbol (`m`, `mm`, `A`, `V`, `ohm`, `g`,
`g/m`, `degC`), `AWG` for the wire gauge (the plain AWG number stays in the file, D2), or
`none (what it is)` for a number that has no unit: a count, a flag, the version of the format.
"""

from collections.abc import Mapping
from typing import Any

from harness_design_studio.core.model import Project

# path of a numeric field -> unit. Bool fields (`locked`, `fixed`, ...) are not numbers and are not here.
FIELD_UNITS: dict[str, str] = {
    "format_version": "none (version number of this file format)",
    "interface_types[].impedance_ohm": "ohm",
    "interface_types[].default_gauge_awg": "AWG",
    "interfaces[].max_current_a": "A",
    "interfaces[].voltage_v": "V",
    "parts[].pin_count": "none (count of pins)",
    "parts[].mass_g": "g",
    "parts[].mass_per_m_g": "g/m",
    "parts[].conductors": "none (count of conductors in one metre of the part)",
    "harnesses[].wires[].gauge_awg": "AWG",
    "harnesses[].wires[].length_m": "m",
    "harnesses[].wires[].strip_a_mm": "mm",
    "harnesses[].wires[].strip_b_mm": "mm",
    "harnesses[].segments[].length_m": "m",
    "harnesses[].accessories[].length_mm": "mm",
    "harnesses[].accessories[].quantity": "none (count of pieces)",
}

RATINGS = "parts[].ratings."  # the keys of `Part.ratings` are names a project may choose
# the ratings the rules read (`library_import.RATING_KEYS`; a test keeps the two lists equal)
RATING_UNITS: dict[str, str] = {
    "contact_current_a": "A",
    "rated_voltage_v": "V",
    "dielectric_withstand_v": "V",
    "max_temp_c": "degC",
    "mating_cycles": "none (count of mating cycles)",
    "shield_insulated": "none (flag: 1 = yes, 0 = no)",
    "conductive_finish": "none (flag: 1 = yes, 0 = no)",
}
# a rating of a project's own is given the unit its name ends in; if the name says none, the file
# says so rather than guess
_SUFFIX_UNITS: tuple[tuple[str, str], ...] = (
    ("_ohm", "ohm"), ("_mm", "mm"), ("_a", "A"), ("_v", "V"), ("_c", "degC"), ("_g", "g"),
)  # fmt: skip
NOT_STATED = "not stated (the name of this rating does not end in a unit)"


def rating_unit(key: str) -> str:
    """The unit of one entry of `Part.ratings`."""
    if key in RATING_UNITS:
        return RATING_UNITS[key]
    for suffix, unit in _SUFFIX_UNITS:
        if key.endswith(suffix):
            return unit
    return NOT_STATED


def field_units(project: Project) -> dict[str, str]:
    """The object `field_units` of `export.json`: every numeric field of the model, plus the
    ratings of the parts of this project that are not among the ones the tool knows."""
    out = dict(FIELD_UNITS)
    for key, unit in RATING_UNITS.items():
        out[RATINGS + key] = unit
    for part in project.parts.values():
        for key in part.ratings:
            out.setdefault(RATINGS + key, rating_unit(key))
    return dict(sorted(out.items()))


def numeric_paths(doc: object, prefix: str = "") -> set[str]:
    """The paths of the numbers in a loaded `export.json` (a bool is not a number; `field_units`
    itself is skipped)."""
    found: set[str] = set()
    if isinstance(doc, bool):
        return found
    if isinstance(doc, int | float):
        return {prefix}
    if isinstance(doc, Mapping):
        for key, value in doc.items():
            if not prefix and key == "field_units":
                continue
            found |= numeric_paths(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(doc, list):
        for value in doc:
            found |= numeric_paths(value, prefix + "[]")
    return found


def missing_units(doc: Mapping[str, Any]) -> list[str]:
    """The numeric fields of a loaded `export.json` that `field_units` does not state a unit for.
    A file with no `field_units` (written before release 1.13) is not asked for one."""
    units = doc.get("field_units")
    if units is None:
        return []
    if not isinstance(units, Mapping):
        return ["field_units"]
    return sorted(
        p for p in numeric_paths(doc) if not isinstance(units.get(p), str) or not units[p].strip()
    )
