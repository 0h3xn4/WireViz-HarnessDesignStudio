"""The model assumptions the tool makes without being asked, each with an ID that a derivation can cite.

A derivation (`core/derive.py`) says how a number was made. Some of what it rests on is not a value
an engineer typed into `config/*.json` but a choice built into the program: the voltage drop counts
the current going out and coming back, a bundle is every wire of the harness, and so on. Those
choices are listed here, in plain words, so that nobody has to say "the tool computed it". This is
the seed of the registry of constants and assumptions of the transparency work (D-191): today every
entry has `kind == "built in"` and cannot be changed without editing the program; each one that
becomes a setting changes its kind and names its configuration key.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Assumption:
    id: str
    title: str
    text: str
    kind: str  # "built in" (in the program) or "setting" (a key of config/*.json)
    where: str  # the function that makes it, or the configuration key


ASSUMPTIONS: dict[str, Assumption] = {
    a.id: a
    for a in (
        Assumption(
            "A-ROUND-TRIP",
            "A power or ground wire is counted twice in the voltage drop",
            "The voltage drop of a wire of a power or ground interface is the drop of the current "
            "going out and coming back: the conductors counted are 2 (1 for every other category). "
            "The return is taken to have the same gauge and length as the wire itself.",
            "built in",
            "core/generate/engine.py (conductors), core/drc/rules.py (_voltage_drop)",
        ),
        Assumption(
            "A-DC-SOLID",
            "The voltage drop is a DC drop in a solid round conductor",
            "ΔV = I × ρ × L / A with the cross-section A of a solid circular conductor of the AWG "
            "diameter. No temperature rise of the conductor, no contact resistance, no stranding "
            "factor and no AC effects are included. ρ is the value of the configuration.",
            "built in",
            "core/generate/sizing.py (voltage_drop_v), core/units.py (awg_to_area_mm2)",
        ),
        Assumption(
            "A-BUNDLE-ALL",
            "A bundle is every wire of the harness, fully loaded",
            "The bundle factor K is taken for the number of all wires of the harness, signal wires "
            "and unloaded wires included, each taken as fully loaded. There is no division of a "
            "harness into bundles, and the length term of the standard's table is not used (it is "
            "taken as 1, the conservative case).",
            "built in",
            "core/drc/rules.py (_wire_current_limit), core/generate/engine.py (bundle_wires)",
        ),
        Assumption(
            "A-TEMP-FACTOR",
            "The temperature factor is one typed number",
            "The temperature derating is the single factor of the configuration. It is not "
            "computed from an ambient temperature, a wire's temperature rating or the insulation.",
            "setting",
            "config/derating.json: temperature_derating",
        ),
        Assumption(
            "A-AMPACITY-AWG",
            "The base ampacity depends on the AWG only",
            "The current a wire may carry before derating comes from one table by AWG. It does not "
            "depend on the wire part, the insulation, the stranding or the environment.",
            "setting",
            "config/derating.json: ampacity_a_by_awg",
        ),
        Assumption(
            "A-SERVICE-LOOP",
            "A generated wire is longer than its path by two service loops",
            "A wire that generation measures from the routing segments is given the length of its "
            "path plus 2 × the service loop of the configuration: one loop at each end. When the "
            "service loop is not set, nothing is added and generation says so. The same extra "
            "length is added to every wire whatever its gauge, part or end.",
            "setting",
            "config/generation.json: service_loop_m; core/generate/engine.py",
        ),
        Assumption(
            "A-PATH-UNIQUE",
            "The length of a wire is the one path through the segments",
            "A wire runs along the path of routing segments between its two connectors. The path "
            "must be unique: if the segments form a loop, there is no single length, the length "
            "stays undecided and the design rule segment-loop reports the loop. Bend radii, "
            "tolerances and the part of a connector inside its backshell are not added.",
            "built in",
            "core/generate/lengths.py (path_trail)",
        ),
        Assumption(
            "A-MASS-SCOPE",
            "The mass of a harness is its connectors and its wires",
            "The mass counts the mass of each connector part of the harness and the mass of each "
            "wire. It does not count contacts, backshells, accessories (sleeving, heat shrink, "
            "labels), splices, solder or shield terminations, and a part without a mass is named as "
            "missing, never replaced by a guess. The margin is added to the total only.",
            "built in",
            "core/generate/mass.py (harness_mass)",
        ),
        Assumption(
            "A-MASS-CONDUCTORS",
            "A wire carries its share of a multi-conductor part",
            "The mass of a wire is the mass per metre of its part times its length divided by the "
            "number of conductors of the part: a twisted pair part (2 conductors) counts half of "
            "its mass for each of its two wires, so that the cable is counted once.",
            "built in",
            "core/generate/mass.py (wire_mass_g)",
        ),
    )
}


def describe(ids: tuple[str, ...]) -> list[Assumption]:
    """The assumptions named, in the order given; an unknown ID is a mistake in the program."""
    return [ASSUMPTIONS[i] for i in ids]
