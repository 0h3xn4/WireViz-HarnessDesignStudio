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
            "going out and coming back: the conductors counted are 2 (1 for every other category; "
            "the categories and both counts are settings of config/model.json, with these as "
            "defaults). The return is taken to have the same gauge and length as the wire itself.",
            "setting",
            "config/model.json: return_path_categories, return_path_conductors, single_path_conductors",
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
            "A bundle is every wire of the harness, fully loaded (by default)",
            "By default the bundle factor K is taken for the number of all wires of the harness, "
            "signal wires and unloaded wires included, each taken as fully loaded. There is no "
            "division of a harness into bundles, and the length term of the standard's table is not "
            "used (it is taken as 1, the conservative case). The setting model.bundle_basis selects "
            "another count: only the wires that carry a current, or the busiest routing segment of "
            "the wire's path (see core/generate/bundle.py).",
            "setting",
            "config/model.json: bundle_basis (default all_wires)",
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
            "path plus 2 × the service loop of the configuration: one loop at each end (the number "
            "of loops is the setting service_loops_per_wire of config/model.json, 2 by default). When the "
            "service loop is not set, nothing is added and generation says so. The same extra "
            "length is added to every wire whatever its gauge, part or end.",
            "setting",
            "config/generation.json: service_loop_m; config/model.json: service_loops_per_wire",
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
            "By default the mass counts the mass of each connector part of the harness and the mass "
            "of each wire. It does not count contacts, backshells, accessories (sleeving, heat "
            "shrink, labels), splices, solder or shield terminations; the setting model.mass_model "
            "full_bom adds the contact parts (one for each pin with a wire) and the accessory parts. "
            "A part without a mass is named as missing, never replaced by a guess. The margin is "
            "added to the total only.",
            "setting",
            "config/model.json: mass_model (default connectors_and_wires)",
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
        Assumption(
            "A-BOM-CONTACTS",
            "A contact part is counted once for each pin that has a wire",
            "A pin that names a contact part adds one of that part to the bill of materials when a "
            "wire of the harness is attached to it, and nothing otherwise: no spare contacts, no "
            "contacts for the pins of a connector that nobody uses.",
            "built in",
            "core/outputs/tables.py (bom_contributions), core/generate/mass.py (pins_in_use)",
        ),
        Assumption(
            "A-BOM-NO-ALLOWANCE",
            "The bill of materials counts what is drawn, with no spares or waste",
            "A connector part is counted once per connector, a wire part in metres as the sum of the "
            "lengths of its wires (each length already includes the service loops) divided by the "
            "conductors of the part, and an accessory part by its quantity or its length. No spare, "
            "overage, cut allowance or waste is added. A wire with no length adds nothing and is "
            "counted in the column Wires without length.",
            "built in",
            "core/outputs/tables.py (bom_contributions)",
        ),
        Assumption(
            "A-CONTACT-SHARED",
            "The current of an interface is checked against every contact at its ends",
            "The whole current of an interface is compared with the derated rating of the contacts "
            "of the connector at each of its endpoints: it is not split over the pins the interface "
            "uses, and the rating is that of the connector part, not of the contact or the wire "
            "crimped into it. The derating factor is one number for every connector.",
            "built in",
            "core/drc/rules.py (_current_over_contact)",
        ),
        Assumption(
            "A-READY-CHECKS",
            "Which checks decide Ready to build is a setting",
            "The answer to Ready to build on the first sheet of the build workbook is no when any check "
            "named in model.readiness_blocking has an open item, and yes otherwise. The other checks of "
            "the sheet are notes: they show their open items and do not change the answer. By default the "
            "first four checks block (wires without a length, a gauge, a colour or a part).",
            "setting",
            "config/model.json: readiness_blocking (default the first four checks)",
        ),
        Assumption(
            "A-READY-SCOPE",
            "Ready to build looks at the eight checks of the sheet and at nothing else",
            "The answer is worked out from the model alone, by the eight checks of the Start here sheet. "
            "It does not look at design rule errors, at the release state or the sign-off of the harness, "
            "at the test limits or at the values of the configuration. A yes does not mean the harness "
            "passes its checks or may be built: the sheet says if the values rest on placeholder files.",
            "built in",
            "core/outputs/buildsheet.py (readiness, open_items)",
        ),
        Assumption(
            "A-TEST-LIMITS",
            "The three test limits are global numbers",
            "The continuity limit (largest resistance), the insulation limit (smallest resistance) and "
            "the insulation test voltage are one number each for every test of that type in every "
            "harness: they do not follow the length, the gauge, the part or any standard. While a key is "
            "not set the test sheet says TBD (placeholder); the tool puts no number in its place.",
            "setting",
            "config/generation.json: test_continuity_max_ohm, test_isolation_min_mohm, test_isolation_voltage_v",
        ),
        Assumption(
            "A-TEST-LIST",
            "The test sheet tests every wire and every shield the same way",
            "A harness gets one continuity test for each wire (end to end), one insulation test for each "
            "wire against every other wire and shield, and one insulation test for each shield group "
            "against every wire. The tests are numbered in that order. There is no sampling and no test "
            "of a single pair of conductors against each other.",
            "built in",
            "core/outputs/tables.py (tests)",
        ),
        Assumption(
            "A-PIN-ORDER",
            "Signals get pins in the order of their category, power first",
            "On one device connector the interfaces are placed in this order: first the categories listed "
            "in model.pin_allocation_categories (power, then ground, by default), in that order, then "
            "every other category, and by interface ID inside a category. Those first categories count as "
            "the power group: kept together as one block, with power_return_gap_pins unassigned contacts "
            "between the signals, and followed by power_signal_gap_pins free pins before the first signal "
            "pin (0 while unset).",
            "setting",
            "config/model.json: pin_allocation_categories; config/generation.json: power_signal_gap_pins, power_return_gap_pins",
        ),
        Assumption(
            "A-PIN-FIRST-FIT",
            "A signal takes the first free pins that fit, and an earlier choice is kept",
            "Inside that order each group of signals (a pair, a power block, a single signal) takes the "
            "first free run of pins of the connector in the order of the pin list, at the start after the "
            "gap. A pair sits on neighbouring pins. A pin that is locked, or is held by a released "
            "harness, is never moved. A pin a person typed in without a lock stays. A connector with a "
            "fixed pinout gives each signal the free pin of that name. A previous allocation is kept "
            "while it is still valid, so a small change makes a small difference. Pin neighbours are the "
            "neighbours in the list of pins, not a measured position.",
            "built in",
            "core/generate/pins.py (allocate)",
        ),
        Assumption(
            "A-SEGMENT-MODE",
            "The mode decides which interfaces share a harness",
            "Interfaces between the same pair of device connectors (per_connector_pair, the default), "
            "of devices (per_unit_pair) or of zones (per_zone_pair) share a harness. Nominal and "
            "redundant chains never share one while segregation.forbid_nominal_with_redundant is on. "
            "Per device pair and per zone pair, a pyro line (while forbid_pyro_with_other is on) and "
            "the categories listed in category_pairs_to_separate get a harness of their own; per "
            "connector pair the connector decides and the tool only notes it when one harness mixes them.",
            "setting",
            "config/segmentation.json: mode; config/segregation.json: forbid_nominal_with_redundant, forbid_pyro_with_other, category_pairs_to_separate",
        ),
        Assumption(
            "A-ZONE",
            "The zone of a device is a field of the device, and a drag can change it",
            "Per zone pair, a device belongs to the zone typed in its Zone field. The block diagram "
            "rewrites that field when a device box is dropped into another zone (the tool says so in a "
            "message), and the harness grouping then changes with it. A device with no zone is in the "
            "zone named no zone.",
            "built in",
            "core/generate/segmentation.py (segment), gui: the block diagram",
        ),
        Assumption(
            "A-LABEL-FORMAT",
            "A label has a fixed form",
            "A wire has two labels, A and B. Each reads: the wire ID, then the name (the label a person "
            "gave the wire, else its signal), then 'to' and the far end (connector and pin), then the EMC "
            "class in brackets when the interface type has one. A cable connector label reads its own "
            "label, else the label of the device connector it plugs into, then 'ID mates DEVICE-CONNECTOR'. "
            "The form is built into the tool; only the words come from the design.",
            "built in",
            "core/outputs/tables.py (wire_label_texts, connector_label_text)",
        ),
        Assumption(
            "A-COLOUR-TABLE",
            "A wire takes the colour its signal has in the table, and no other",
            "Generation gives a wire the colour that config/generation.json wire_colour_by_signal lists "
            "for its signal (for a wire labelled TX+/RX+ the whole label counts first, then each name). "
            "A signal that is not in the table gets no colour, and the build workbook shows it as a check "
            "that blocks. A colour a person gave a wire is kept. The colour names and their IEC 60757 "
            "codes are a table of the tool that decides nothing: a name it does not know is kept as typed.",
            "setting",
            "config/generation.json: wire_colour_by_signal; core/wirecolours.py",
        ),
        Assumption(
            "A-SHIELD-GROUPS",
            "A shield group follows the construction and the shielding of the interface type",
            "A coax wire is a shield of its own, a quad is one group, the wires of a pair of a signal "
            "type are a twisted pair (a shielded pair when the type shields per pair), and an interface "
            "whose type shields overall gets one overall shield over its wires. A power or ground type "
            "twists the way out and the way back together. A group a person made is kept.",
            "built in",
            "core/generate/shields.py (plan)",
        ),
        Assumption(
            "A-SHIELD-ENDS",
            "The ends of a shield are the grounding concept of the project",
            "Every generated shield group, except a coax, gets the ends shield_end_a and shield_end_b "
            "of config/generation.json (backshell 360 degrees, pigtail or floating); while a value is "
            "not set floating is used and generation says so. A coax shield is bonded at both ends, "
            "fixed by the file format. The rules shield-wrong-end and shield-bonding compare the ends "
            "with the concept and with emc.json shield_bonding.",
            "setting",
            "config/generation.json: shield_end_a, shield_end_b; config/emc.json: shield_bonding",
        ),
        Assumption(
            "A-CONNECTOR-CHOICE",
            "A connector is the first free one that carries the type; the cable end is the mating part",
            "When the tool chooses the connector of an interface at a device, it takes the first free "
            "connector of that device (in ID order) that carries the interface type, and marks it as "
            "chosen for you until a person confirms it. The cable end of a device connector is the part "
            "the library names as its mating part; a part with none is mated with itself, and "
            "generation says so. Gender is the opposite of the device connector's, and keying is copied.",
            "built in",
            "core/checks.py (_assign_connectors), core/edit.py (free_connectors), core/generate/engine.py (_build_harness)",
        ),
        Assumption(
            "A-SPARE-PINS",
            "A pin is spare when it has no interface and no signal",
            "The spare-pin check counts, for each device connector that carries at least one interface, "
            "the pins with neither an interface nor a signal, and compares them with the required "
            "fraction of all pins of the connector. The fraction is not rounded: the number of spare "
            "pins must be at least fraction × pins. A connector that carries nothing is not checked.",
            "setting",
            "config/derating.json: spare_pin_fraction",
        ),
        Assumption(
            "A-CONNECTOR-VOLTAGE",
            "The connector voltage limit is the lower of the limits that can be worked out",
            "The working voltage of an interface is compared with the lower of: the share of the "
            "dielectric withstanding voltage of the connector part, and the share of its rated voltage. "
            "A limit that needs a value the part does not have is left out; with neither the connector "
            "is not checked. The voltage is the interface's one number, not a waveform.",
            "setting",
            "config/derating.json: connector_voltage_factor_withstand, connector_voltage_factor_rated",
        ),
        Assumption(
            "A-AMBIENT-ONLY",
            "The temperature check uses one ambient temperature and no self-heating",
            "The hottest ambient temperature of the project is compared with the maximum temperature of "
            "the part less the margin. The self-heating of the conductor by its current is not added "
            "(it needs a thermal analysis outside the tool, and the check list says so).",
            "setting",
            "config/derating.json: max_ambient_temperature_c, connector_temperature_margin_c, wire_temperature_margin_c",
        ),
        Assumption(
            "A-MATING-REQUIRED",
            "The mating cycles are a number the programme may use, not a count of matings",
            "The rated mating cycles of a connector part are compared with the number of cycles the "
            "programme may use (max_mating_cycles). The tool does not know how often a connector is "
            "really mated: that is a record kept by people.",
            "setting",
            "config/derating.json: max_mating_cycles",
        ),
        Assumption(
            "A-RETURN-GAP",
            "Power and return pins are far enough apart when enough contacts between them are free",
            "For any two power or ground pins of different signals on one connector, the contacts "
            "between them in the list of pins that carry no interface and no signal are counted, and "
            "must be at least power_return_gap_pins. Neighbours are neighbours in the list of pins.",
            "setting",
            "config/generation.json: power_return_gap_pins",
        ),
        Assumption(
            "A-BUNDLE-CURRENT",
            "The bundle check uses the wire limit, and does not need the temperature factor",
            "bundle-current compares the current of the interface with the same limit as the wire "
            "current check (ampacity × bundle factor from the table × temperature factor) but only when a "
            "table of bundle factors is set, and counts an unset temperature factor as 1.",
            "built in",
            "core/drc/standard_rules.py (_bundle_current)",
        ),
    )
}


def describe(ids: tuple[str, ...]) -> list[Assumption]:
    """The assumptions named, in the order given; an unknown ID is a mistake in the program."""
    return [ASSUMPTIONS[i] for i in ids]
