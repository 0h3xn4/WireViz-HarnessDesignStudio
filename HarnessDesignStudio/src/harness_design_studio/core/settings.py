"""The settings of the tool: every value a result depends on that an engineer can choose (D-191, S2).

A **setting** is a key of a file `config/<file>.json` with a name, a unit, a description, a range and
a **default that is the behaviour of the tool before the setting existed**, so that a project that
sets nothing gets the same numbers as ever. A **definition** is something the tool fixes because it
is a definition or a numerical device, not an engineering choice (the AWG formula, the tolerance of
a float comparison). Nothing else is a model constant: `tests/test_settings.py` walks the calculation
modules and fails on a number that is neither a setting, a definition nor a listed exception, so a
new constant cannot slip into the code unseen.

This module is the one place that says what each value is. The Assumptions page (`harness-design-studio
settings`, the Assumptions window of the editor) is built from it, and so are the explanations
(`core.derive`): a value says where it came from (the project, the default of this table, or nothing).

    effective(project, "model", "service_loops_per_wire")  ->  Effective(2, "default", <Setting>)
"""

from dataclasses import dataclass
from typing import Any

from harness_design_studio.core.model import Project
from harness_design_studio.core.units import format_awg


@dataclass(frozen=True)
class Setting:
    file: str  # "derating" for config/derating.json
    key: str
    label: str
    unit: str  # "" when the value has none (a factor, a count, a name)
    kind: str  # "number" | "whole" | "choice" | "flag" | "table" | "pairs" | "names" | "text"
    default: object  # what the tool does when the key is unset; None: nothing to default to
    what: str  # one plain sentence
    used_by: str  # what depends on it
    source: str  # where the number comes from when the tool supplies it, else who decides
    range: str  # what is accepted
    assumption: str = ""  # the ID of the assumption (core.assumptions) this setting parameterises
    choices: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        return f"{self.file}.{self.key}"


@dataclass(frozen=True)
class Definition:
    """A fixed part of a calculation that is not an engineering choice."""

    id: str
    title: str
    text: str
    where: str


@dataclass(frozen=True)
class Effective:
    value: object
    origin: str  # "project" (set in the file), "default" (the tool's own), "unset" (nothing)
    setting: Setting


_PROJECT = "set by the project"
_PLACEHOLDER_SOURCE = "the engineer, from the program's standard (placeholder until reviewed)"
_ECSS = "ECSS-Q-ST-30-11C (profile ecss-q-st-30-11c)"

SETTINGS: tuple[Setting, ...] = (
    # ---- segmentation, segregation
    Setting("segmentation", "mode", "How interfaces are grouped into harnesses", "", "choice", "per_connector_pair", "Interfaces between the same two connectors, units or zones share a harness.", "segmentation of the harnesses", _PROJECT, "per_connector_pair, per_unit_pair or per_zone_pair", choices=("per_connector_pair", "per_unit_pair", "per_zone_pair"), assumption="A-SEGMENT-MODE"),
    Setting("segregation", "forbid_nominal_with_redundant", "Keep nominal and redundant chains apart", "", "flag", True, "Nominal and redundant chains never share a harness or connector.", "rule chains-mixed", _PROJECT, "true or false", assumption="A-SEGMENT-MODE"),
    Setting("segregation", "forbid_pyro_with_other", "Keep pyro lines apart", "", "flag", True, "Pyro lines never share a harness or connector.", "rule pyro-mixed", _PROJECT, "true or false", assumption="A-SEGMENT-MODE"),
    Setting("segregation", "category_pairs_to_separate", "Interface categories kept apart", "", "pairs", None, "Pairs of interface categories that must not share a harness.", "rule category-mixed", _PROJECT, "pairs of two different names", assumption="A-SEGMENT-MODE"),
    # ---- derating
    Setting("derating", "ampacity_a_by_awg", "Ampacity by wire gauge", "A", "table", None, "The current each gauge may carry before derating.", "wire sizing, wire current check", _PLACEHOLDER_SOURCE, "gauge 0 to 40, amperes above 0, not rising with the gauge number", "A-AMPACITY-AWG"),
    Setting("derating", "bundle_derating", "Bundle derating factor", "", "number", None, "One factor K for the wires of a bundle.", "wire sizing, wire current check", _PLACEHOLDER_SOURCE, "above 0 and at most 1", "A-BUNDLE-ALL"),
    Setting("derating", "bundle_factor_by_count", "Bundle factor by wire count", "", "table", None, "Factor K by the number of wires in a bundle; replaces the single factor.", "wire sizing, wire current check, bundle current", f"{_ECSS}, Table 6-41", "wire count 1 or more, K above 0 and at most 1, not rising with the count", "A-BUNDLE-ALL"),
    Setting("derating", "temperature_derating", "Temperature derating factor", "", "number", None, "One factor for the maximum ambient temperature.", "wire sizing, wire current check", _PLACEHOLDER_SOURCE, "above 0 and at most 1", "A-TEMP-FACTOR"),
    Setting("derating", "contact_current_factor", "Contact current factor", "", "number", None, "The fraction of a contact's rating that may be used.", "contact current check", _PLACEHOLDER_SOURCE, "above 0 and at most 1", "A-CONTACT-SHARED"),
    Setting("derating", "contact_rating_key", "Rating that holds the contact current", "", "text", "contact_current_a", "Which entry of a connector part's ratings is the contact current.", "contact current check", _PROJECT, "a name of a rating of the library"),
    Setting("derating", "max_voltage_drop_v", "Largest voltage drop", "V", "number", None, "The most a wire path may drop.", "wire sizing, voltage drop check", _PLACEHOLDER_SOURCE, "above 0"),
    Setting("derating", "spare_pin_fraction", "Spare pin fraction", "", "number", None, "The share of pins that must stay spare.", "spare pin check", _PLACEHOLDER_SOURCE, "0 or more, below 1", assumption="A-SPARE-PINS"),
    Setting("derating", "max_ambient_temperature_c", "Hottest ambient temperature", "degC", "number", None, "Compared with the ratings of connectors and wires.", "temperature margin check", _PROJECT, "a temperature", assumption="A-AMBIENT-ONLY"),
    Setting("derating", "connector_temperature_margin_c", "Connector temperature margin", "degC", "number", None, "How far below its maximum rating a connector must stay.", "temperature margin check", f"{_ECSS}, requirement 0140051 (30)", "0 or more", assumption="A-AMBIENT-ONLY"),
    Setting("derating", "wire_temperature_margin_c", "Wire temperature margin", "degC", "number", None, "How far below its maximum rating a wire must stay.", "temperature margin check", f"{_ECSS}, requirement 0140213 (50)", "0 or more", assumption="A-AMBIENT-ONLY"),
    Setting("derating", "connector_voltage_factor_withstand", "Connector voltage share of the withstanding voltage", "", "number", None, "Working voltage as a fraction of the dielectric withstanding voltage.", "connector voltage check", f"{_ECSS}, requirement 0140051 (0.25)", "above 0 and at most 1", assumption="A-CONNECTOR-VOLTAGE"),
    Setting("derating", "connector_voltage_factor_rated", "Connector voltage share of the rated voltage", "", "number", None, "Working voltage as a fraction of the rated voltage; the lower limit applies.", "connector voltage check", f"{_ECSS}, requirement 0140051 (0.75)", "above 0 and at most 1", assumption="A-CONNECTOR-VOLTAGE"),
    Setting("derating", "wire_voltage_factor", "Wire voltage share of the rated voltage", "", "number", None, "Working voltage as a fraction of the wire's rated voltage.", "wire voltage check", f"{_ECSS}, requirement 0140213 (0.5)", "above 0 and at most 1"),
    Setting("derating", "rf_power_factor", "RF power share of the rating", "", "number", None, "Recorded; no rule uses it yet.", "nothing yet", f"{_ECSS}, requirement 0140058 (0.75)", "above 0 and at most 1"),
    Setting("derating", "partial_load_factor", "Factors for partly loaded bundles", "", "table", None, "Table L; recorded, not applied (the report says so).", "nothing yet", f"{_ECSS}, requirement 0140220", "below_25_percent, 25_to_50_percent and above_50_percent, each above 0 and at most 2"),
    Setting("derating", "max_mating_cycles", "Most mating cycles", "cycles", "whole", None, "How many times a connector may be mated.", "mating cycles check", f"{_ECSS}, requirement 0140056 (50)", "a whole number above 0", assumption="A-MATING-REQUIRED"),
    # ---- generation
    Setting("generation", "wire_part_by_construction", "Wire part for each construction", "", "table", None, "The library wire part used for each construction (example parts by default).", "generated wires, mass, bill of materials", _PROJECT, "a wire part of the library for each construction"),
    Setting("generation", "default_gauge_awg", "Default gauge", "AWG", "whole", None, "The gauge when none is decided.", "generated wires", _PROJECT, "a whole number 0 to 40"),
    Setting("generation", "service_loop_m", "Service loop at each end", "m", "number", None, "Extra length added at each end of a generated wire.", "wire lengths (excluded while unset)", _PROJECT, "0 or more", "A-SERVICE-LOOP"),
    Setting("generation", "conductor_resistivity_ohm_m", "Conductor resistivity", "ohm m", "number", None, "For the voltage drop.", "wire sizing, voltage drop check", _PLACEHOLDER_SOURCE, "above 0", "A-DC-SOLID"),
    Setting("generation", "power_signal_gap_pins", "Pins between power and signal", "pins", "whole", None, "Empty pins between power and signal pins (0 used while unset).", "pin allocation", _PROJECT, "a whole number, 0 or more", assumption="A-PIN-ORDER"),
    Setting("generation", "power_return_gap_pins", "Pins between power and return", "pins", "whole", None, "Unassigned contacts between the supply and the return pin of a power interface.", "pin allocation", f"{_ECSS}, requirement 0140052 (1)", "a whole number 1 to 1000", assumption="A-RETURN-GAP"),
    Setting("generation", "mass_margin_fraction", "Mass margin", "", "number", None, "The margin added to the mass, as a fraction.", "mass with margin", _PROJECT, "0 or more", "A-MASS-SCOPE"),
    Setting("generation", "shield_end_a", "Shield grounding, end A", "", "choice", None, "Backshell, pigtail or floating.", "shield grounding check, generated shields", _PROJECT, "backshell_360, pigtail or floating", choices=("backshell_360", "pigtail", "floating"), assumption="A-SHIELD-ENDS"),
    Setting("generation", "shield_end_b", "Shield grounding, end B", "", "choice", None, "Backshell, pigtail or floating.", "shield grounding check, generated shields", _PROJECT, "backshell_360, pigtail or floating", choices=("backshell_360", "pigtail", "floating"), assumption="A-SHIELD-ENDS"),
    Setting("generation", "wire_colour_by_signal", "Wire colour for each signal", "", "table", None, "Used when a wire has no colour of its own.", "build workbook, drawings", _PROJECT, "a signal name and a colour name", assumption="A-COLOUR-TABLE"),
    Setting("generation", "test_continuity_max_ohm", "Largest continuity resistance", "ohm", "number", None, "Accepted as continuous.", "continuity test limits", _PLACEHOLDER_SOURCE, "above 0", assumption="A-TEST-LIMITS"),
    Setting("generation", "test_isolation_min_mohm", "Smallest insulation resistance", "Mohm", "number", None, "Accepted.", "isolation test limits", _PLACEHOLDER_SOURCE, "above 0", assumption="A-TEST-LIMITS"),
    Setting("generation", "test_isolation_voltage_v", "Isolation test voltage", "V", "number", None, "The voltage of the isolation test.", "isolation test limits", _PLACEHOLDER_SOURCE, "above 0", assumption="A-TEST-LIMITS"),
    # ---- emc
    Setting("emc", "classes", "EMC classes in use", "", "names", None, "Kept for reference; no rule reads it.", "nothing", _PROJECT, "a list of names"),
    Setting("emc", "conflicting_class_pairs", "EMC classes kept apart", "", "pairs", None, "Pairs of EMC classes that must not share a harness.", "rule emc-mixed", _PROJECT, "pairs of two different names"),
    Setting("emc", "shield_bonding", "Shield bonding", "", "choice", None, "Every shield bonded at both ends through a 360 degree backshell.", "rule shield-bonding", "ECSS-E-ST-20-07C, requirements 0080041 and 0080042", "both_ends_backshell", choices=("both_ends_backshell",), assumption="A-SHIELD-ENDS"),
    Setting("emc", "same_class_one_bundle", "One bundle per EMC class", "", "flag", None, "Interfaces of one EMC class between two devices run in one harness.", "rule emc-bundle", "ECSS-E-ST-20-07C, requirement 0080035", "true or false"),
    # ---- naming, change control, title block
    Setting("naming", "harness", "Name of a harness", "", "text", "W{n:03d}", "The pattern of the harness IDs.", "generated IDs", _PROJECT, "a pattern that gives a different valid ID for every number"),
    Setting("naming", "box_connector", "Name of a device connector", "", "text", "{unit}-J{n:02d}", "In the shipped file, but the generator does not read it.", "nothing", _PROJECT, "a pattern"),
    Setting("naming", "cable_connector", "Name of a cable connector", "", "text", "{harness}-P{n}", "The pattern of the cable connector IDs.", "generated IDs", _PROJECT, "a pattern"),
    Setting("naming", "wire", "Name of a wire", "", "text", "{harness}-{n:03d}", "The pattern of the wire IDs.", "generated IDs", _PROJECT, "a pattern"),
    Setting("naming", "shield", "Name of a shield", "", "text", "{harness}-S{n}", "The pattern of the shield IDs.", "generated IDs", _PROJECT, "a pattern"),
    Setting("naming", "branch", "Name of a branch point", "", "text", "{harness}-B{n}", "The pattern of the branch point IDs.", "generated IDs", _PROJECT, "a pattern"),
    Setting("naming", "segment", "Name of a routing segment", "", "text", "{harness}-L{n}", "The pattern of the segment IDs.", "generated IDs", _PROJECT, "a pattern"),
    Setting("naming", "signal_counterparts", "Words for the two ends of a line", "", "pairs", None, "A transmit word and its receive word, for the review of connections and the pairing.", "link review, pairing", _PROJECT, "pairs of two different words made of letters"),
    Setting("naming", "release_distinct_roles", "Different people in a release", "", "flag", False, "The author, the checker and the person who releases are three different people.", "release", _PROJECT, "true or false"),
    Setting("titleblock", "fields", "Title block fields", "", "names", None, "Which fields appear, in order.", "title blocks", _PROJECT, "known field names, each at most once"),
    # ---- model: what was built into the program before (D-191, S2); the defaults are those numbers
    Setting("model", "bundle_basis", "How the bundle of a wire is counted", "", "choice", "all_wires", "The number of wires the bundle factor K is looked up for: every wire of the harness, only the wires that carry a current, or the busiest routing segment of the wire's path.", "wire sizing, wire current check, bundle current", "the tool's own choice before D-191 (all_wires, the conservative reading of ECSS-Q-ST-30-11C 6.32.5.1)", "all_wires, loaded_wires or busiest_segment", "A-BUNDLE-ALL", ("all_wires", "loaded_wires", "busiest_segment")),
    Setting("model", "length_model", "How the length of a generated wire is made", "", "choice", "path_plus_loops", "The path through the routing segments plus the service loops, or that with a cut allowance and a take-up for twisting.", "wire lengths, voltage drop, mass, bill of materials, cut list", "the tool's own choice before D-191 (path_plus_loops)", "path_plus_loops or path_loops_allowance_twist", "A-SERVICE-LOOP", ("path_plus_loops", "path_loops_allowance_twist")),
    Setting("model", "cut_allowance_m", "Cut allowance per wire", "m", "number", 0.0, "Added to the length of every generated wire when the length model includes it.", "wire lengths", "the engineer (0 by default: no allowance)", "0 to 10", "A-SERVICE-LOOP"),
    Setting("model", "twist_takeup_fraction", "Take-up of twisting", "", "number", 0.0, "The extra length of a wire of a twisted construction, as a fraction of its length, when the length model includes it.", "wire lengths", "the engineer (0 by default: no take-up)", "0 to 0.5", "A-SERVICE-LOOP"),
    Setting("model", "drop_model", "Voltage drop model", "", "choice", "dc_solid", "DC drop of a solid round conductor at the resistivity given, or the same with the resistivity corrected to the hottest ambient temperature.", "wire sizing, voltage drop check", "the tool's own choice before D-191 (dc_solid)", "dc_solid or dc_at_ambient", "A-DC-SOLID", ("dc_solid", "dc_at_ambient")),
    Setting("model", "resistivity_temperature_coefficient", "Temperature coefficient of the resistivity", "1/K", "number", 0.00393, "For the model dc_at_ambient: the resistivity grows by this fraction per kelvin above the reference temperature (0.00393 is the usual value for annealed copper).", "voltage drop with the model dc_at_ambient", "the usual value for annealed copper (a property of the material, set it for another conductor)", "0 to 0.01", "A-DC-SOLID"),
    Setting("model", "resistivity_reference_temperature_c", "Temperature the resistivity is given for", "degC", "number", 20.0, "For the model dc_at_ambient: the temperature conductor_resistivity_ohm_m is valid at.", "voltage drop with the model dc_at_ambient", "the usual reference for tabulated resistivities (20 degC)", "-100 to 200", "A-DC-SOLID"),
    Setting("model", "mass_model", "Mass model", "", "choice", "connectors_and_wires", "The connectors and the wires of a harness, or every part of its bill of materials (contacts and accessories as well).", "mass, mass with margin", "the tool's own choice before D-191 (connectors_and_wires)", "connectors_and_wires or full_bom", "A-MASS-SCOPE", ("connectors_and_wires", "full_bom")),
    Setting("model", "pin_allocation_categories", "Interface categories allocated first", "", "names", ("power", "ground"), "In this order, before every other category; they count as the power group for the gap to the signal pins.", "pin allocation", "the tool's own choice before D-191 (power, then ground)", "a list of interface category names", assumption="A-PIN-ORDER"),
    Setting("model", "pin_fit_strategy", "How a run of pins is picked", "", "choice", "first_fit", "Which free run of pins a group of signals takes on a device connector: the first (from pin 1 up), the last (from the last pin down), or the first with a free pin between one interface and the next.", "pin allocation", "the tool's own choice before D-191 (first_fit)", "first_fit, last_fit or spread", "A-PIN-FIRST-FIT", ("first_fit", "last_fit", "spread")),
    Setting("model", "connector_choice", "Which connector carries an interface the tool places", "", "choice", "first_free", "When the tool chooses the connector of an interface at a device: the first free connector that carries the type, the one with the fewest pins left over (best fit), or the one with the most pins left over.", "choice of a connector, the connector of an interface that has none", "the tool's own choice before D-191 (first_free)", "first_free, fewest_spare_pins or most_spare_pins", "A-CONNECTOR-CHOICE", ("first_free", "fewest_spare_pins", "most_spare_pins")),
    Setting("model", "label_format", "Format of the labels of wires and cable connectors", "", "choice", "standard", "The text printed on a label: the standard text, a compact text (ID and far end only), a descriptive text (with the interface and the device) or the templates label_wire_template and label_connector_template.", "the Labels table and sheet", "the tool's own choice before D-191 (standard)", "standard, compact, descriptive or custom", "A-LABEL-FORMAT", ("standard", "compact", "descriptive", "custom")),
    Setting("model", "label_wire_template", "Template of a wire label (format custom)", "", "text", None, "For the format custom: text with the places {harness}, {wire}, {signal}, {name}, {interface}, {emc}, {end}, {from} and {to}, filled in for each end of each wire. Not set: the standard text.", "the Labels table and sheet with the format custom", "the engineer", "text of at most 200 characters, with the places above and nothing else in braces", "A-LABEL-FORMAT"),
    Setting("model", "label_connector_template", "Template of a cable connector label (format custom)", "", "text", None, "For the format custom: text with the places {harness}, {connector}, {name}, {mates} and {device}. Not set: the standard text.", "the Labels table and sheet with the format custom", "the engineer", "text of at most 200 characters, with the places above and nothing else in braces", "A-LABEL-FORMAT"),
    Setting("model", "readiness_blocking", "Checks that make a harness not ready to build", "", "names", ("Wires without a length", "Wires without a gauge", "Wires without a colour", "Wires without a part"), "The checks of the build workbook whose open items mean the answer to Ready to build is no; the others are notes.", "the answer Ready to build", "the tool's own choice before D-191 (the first four checks)", "names of the checks of the build workbook", assumption="A-READY-CHECKS"),
    Setting("model", "return_path_categories", "Interface categories counted with their return", "", "names", ("power", "ground"), "The voltage drop of a wire of these categories counts the current going out and coming back.", "wire sizing, voltage drop check", "the tool's own choice before D-191 (power and ground)", "a list of interface category names", "A-ROUND-TRIP"),
    Setting("model", "return_path_conductors", "Conductors counted for a category with a return", "", "whole", 2, "How many conductors the drop of such a wire counts: the way out and the way back.", "wire sizing, voltage drop check", "the tool's own choice before D-191 (2)", "a whole number 1 to 4", "A-ROUND-TRIP"),
    Setting("model", "single_path_conductors", "Conductors counted for every other category", "", "whole", 1, "How many conductors the drop of any other wire counts.", "wire sizing, voltage drop check", "the tool's own choice before D-191 (1)", "a whole number 1 to 4", "A-ROUND-TRIP"),
    Setting("model", "service_loops_per_wire", "Service loops added to a generated wire", "", "whole", 2, "How many service loops are added to the length of a generated wire (one at each end).", "wire lengths", "the tool's own choice before D-191 (2)", "a whole number 0 to 4", "A-SERVICE-LOOP"),
)  # fmt: skip

DEFINITIONS: tuple[Definition, ...] = (
    Definition("D-AWG", "The cross-section of a gauge", "The AWG diameter is 0.127 mm × 92^((36 − n)/39) and the cross-section is that of a solid round conductor (π/4 × d²). Gauges 0 to 40.", "core/units.py"),
    Definition("D-LIMIT-TOLERANCE", "A value at its limit is not over it", "A value within one billionth (relative) of its limit is at the limit: the one comparison that sizing and the design rules share, so both agree at the exact limit.", "core/generate/sizing.py (exceeds)"),
    Definition("D-DATA-ROUNDING", "Numbers in the data files", "A number written to a data file or table is rounded to 9 decimals and written without an exponent, so that sums carry no floating-point noise.", "core/outputs/tables.py (data_num)"),
    Definition("D-IMPORT-LENGTH-BOUND", "Largest length that is accepted", "A length above 10,000 m is refused, from an import and from a hand edit: a unit mistake, not a harness.", "core/generate/lengths.py (MAX_LENGTH_M), core/model"),
    Definition("D-TWISTED", "Which constructions are twisted", "The constructions twisted_pair, twisted_shielded_pair, quad and twinax are twisted: the take-up of twisting (model.twist_takeup_fraction) is applied to their wires.", "core/settings.py (TWISTED_CONSTRUCTIONS)"),
    Definition("D-MM-TO-M", "Millimetres to metres", "An accessory length in millimetres is divided by 1000 to give metres.", "core/outputs/tables.py (bom_contributions)"),
)  # fmt: skip

TWISTED_CONSTRUCTIONS = ("twisted_pair", "twisted_shielded_pair", "quad", "twinax")

_BY_ID = {s.id: s for s in SETTINGS}


def setting(file: str, key: str) -> Setting | None:
    return _BY_ID.get(f"{file}.{key}")


# ---- the comments in the files: `_about` (D-191 (2), R3) ----------------------------------------


def _plain_default(value: object) -> object:
    if isinstance(value, tuple | list):
        return [_plain_default(v) for v in value]
    return value


def about_entry(s: Setting) -> dict[str, object]:
    """What `_about` says about one setting: the text of the registry, field by field. A unit or an
    assumption the setting has not is left out; `default` is null when the tool has no default
    (the value then stays undecided and what depends on it is excluded)."""
    entry: dict[str, object] = {"label": s.label}
    if s.unit:
        entry["unit"] = s.unit
    entry["range"] = s.range
    entry["source"] = s.source
    entry["what"] = s.what
    entry["used_by"] = s.used_by
    entry["default"] = _plain_default(s.default)
    if s.assumption:
        entry["assumption"] = s.assumption
    return entry


def about_for(file: str) -> dict[str, dict[str, Any]]:
    """The `_about` of `config/<file>.json` as the registry says it now: an entry for every setting
    of the file, set in it or not, so that a person who wants to add a key sees its range."""
    return {s.key: about_entry(s) for s in SETTINGS if s.file == file}


def about_problems(file: str, about: dict[str, Any]) -> list[tuple[str, str]]:
    """How the `_about` of a file differs from `about_for(file)`, as (key, what) pairs in a fixed
    order; empty when it is current. A file without annotation (empty `about`) is not stale."""
    if not about:
        return []
    now = about_for(file)
    out: list[tuple[str, str]] = []
    for key in sorted(about):
        have = about[key]
        if key not in now:
            out.append((key, "is for a key the tool does not know (removed or misspelt)"))
        elif have != now[key]:
            fields = sorted(f for f in set(have) | set(now[key]) if have.get(f) != now[key].get(f))
            out.append((key, f"differs from what the tool says now ({', '.join(fields)})"))
    out.extend((key, "has no entry") for key in sorted(set(now) - set(about)))
    return out


def effective(project: Project, file: str, key: str) -> Effective:
    """The value the tool uses for a setting, and where it comes from."""
    s = _BY_ID[f"{file}.{key}"]
    cfg = project.config.get(file)
    value = cfg.values.get(key) if cfg is not None else None
    if value is not None:
        return Effective(value, "project", s)
    if s.default is not None:
        return Effective(s.default, "default", s)
    return Effective(None, "unset", s)


def whole(project: Project, file: str, key: str) -> int:
    """A whole-number setting that has a default (the model settings): never None."""
    value = effective(project, file, key).value
    if isinstance(value, bool) or not isinstance(value, int | float) or value != int(value):
        raise ValueError(f"{file}.{key} is not a whole number")
    return int(value)


def names(project: Project, file: str, key: str) -> tuple[str, ...]:
    value = effective(project, file, key).value
    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(v) for v in value)


def drop_conductors(project: Project, category: str) -> int:
    """How many conductors the voltage drop of a wire of this interface category counts (the way
    out and the way back for the categories with a return path, else one): A-ROUND-TRIP."""
    if category in names(project, "model", "return_path_categories"):
        return whole(project, "model", "return_path_conductors")
    return whole(project, "model", "single_path_conductors")


def number(project: Project, file: str, key: str) -> float:
    """A number setting that has a default (the model settings): never None."""
    value = effective(project, file, key).value
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{file}.{key} is not a number")
    return float(value)


def choice(project: Project, file: str, key: str) -> str:
    """A choice setting that has a default: the choice made, or the default when the value is not
    one of the choices (a damaged file is reported by `validate`, never silently used)."""
    e = effective(project, file, key)
    return str(e.value) if e.value in e.setting.choices else str(e.setting.default)


def resistivity(project: Project) -> tuple[float | None, str | None]:
    """The resistivity the voltage drop uses, in ohm metres, and what is missing for it (None when
    nothing is): the value of generation.conductor_resistivity_ohm_m for the model dc_solid, and
    that value corrected to the hottest ambient temperature for dc_at_ambient: rho x (1 + alpha x
    (T - T_ref)). A-DC-SOLID."""
    gen = project.config.get("generation")
    raw = gen.values.get("conductor_resistivity_ohm_m") if gen is not None else None
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return None, "generation.conductor_resistivity_ohm_m"
    rho = float(raw)
    if choice(project, "model", "drop_model") != "dc_at_ambient":
        return rho, None
    der = project.config.get("derating")
    t = der.values.get("max_ambient_temperature_c") if der is not None else None
    if isinstance(t, bool) or not isinstance(t, int | float):
        return None, "derating.max_ambient_temperature_c (the model dc_at_ambient needs it)"
    alpha = number(project, "model", "resistivity_temperature_coefficient")
    t_ref = number(project, "model", "resistivity_reference_temperature_c")
    return rho * (1 + alpha * (float(t) - t_ref)), None


def service_loops(project: Project) -> int:
    """How many service loops a generated wire gets: A-SERVICE-LOOP."""
    return whole(project, "model", "service_loops_per_wire")


# ---- the Assumptions page: what is in force for this project --------------------------------


@dataclass(frozen=True)
class Row:
    """One setting as the project has it."""

    setting: Setting
    value: object
    origin: str  # "project", "default" or "unset"
    placeholder: bool  # the file that holds it is still marked as not reviewed
    display: str  # the value as text; "not set" when nothing is in force


def display(value: object) -> str:
    if value is None:
        return "not set"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    if isinstance(value, list | tuple):
        return ", ".join(
            "+".join(map(str, v)) if isinstance(v, list | tuple) else str(v) for v in value
        )
    return str(value)


def display_of(s: Setting, value: object) -> str:
    """The value of a setting as text for a person. The table by wire gauge names each gauge with
    its cross-section (`AWG 24 (0.205 mm²): 2`, D2); every other value is shown as `display`
    shows it. The value itself, as `to_dict` and the files carry it, is not changed."""
    if s.id == "derating.ampacity_a_by_awg" and isinstance(value, dict):
        parts: list[str] = []
        for k, v in value.items():
            try:
                parts.append(f"{format_awg(int(k))}: {v}")
            except TypeError, ValueError:
                parts.append(f"{k}: {v}")
        return ", ".join(parts)
    return display(value)


def rows(project: Project) -> list[Row]:
    """Every setting with the value in force and where it comes from, in the order of the table."""
    out: list[Row] = []
    for s in SETTINGS:
        e = effective(project, s.file, s.key)
        cfg = project.config.get(s.file)
        placeholder = bool(cfg.placeholder) if cfg is not None and e.origin == "project" else False
        out.append(Row(s, e.value, e.origin, placeholder, display_of(s, e.value)))
    return out


def assumptions_in_force(project: Project) -> list[tuple[str, str, str, list[Row]]]:
    """Every assumption of `core.assumptions` as (ID, title, kind, the settings that parameterise
    it with their values in force): the page that says what the tool assumes for this project."""
    from harness_design_studio.core.assumptions import ASSUMPTIONS

    by_assumption: dict[str, list[Row]] = {}
    for r in rows(project):
        if r.setting.assumption:
            by_assumption.setdefault(r.setting.assumption, []).append(r)
    return [(a.id, a.title, a.kind, by_assumption.get(a.id, [])) for a in ASSUMPTIONS.values()]


def to_dict(project: Project) -> dict[str, object]:
    """Settings, definitions and assumptions as plain data (for `--json` and for scripts)."""
    return {
        "settings": [
            {
                "id": r.setting.id,
                "label": r.setting.label,
                "unit": r.setting.unit,
                "value": r.value,
                "origin": r.origin,
                "placeholder": r.placeholder,
                "default": r.setting.default,
                "what": r.setting.what,
                "used_by": r.setting.used_by,
                "source": r.setting.source,
                "range": r.setting.range,
                "assumption": r.setting.assumption,
            }
            for r in rows(project)
        ],
        "definitions": [
            {"id": d.id, "title": d.title, "text": d.text, "where": d.where} for d in DEFINITIONS
        ],
        "assumptions": [
            {"id": a, "title": t, "kind": k, "settings": [r.setting.id for r in rs]}
            for a, t, k, rs in assumptions_in_force(project)
        ],
    }


def render(project: Project) -> str:
    """The Assumptions page as text: what `harness-design-studio settings` prints and the window of
    the editor shows. Every setting with the value in force and where it comes from, the assumptions
    built into the tool with the settings that parameterise them, and the fixed definitions."""
    lines: list[str] = []
    current = ""
    for r in rows(project):
        s = r.setting
        if s.file != current:
            current = s.file
            lines.append(f"\nconfig/{current}.json")
        unit = f" {s.unit}" if s.unit and r.value is not None else ""
        origin = {
            "project": "set by the project"
            + (" (placeholder: not reviewed)" if r.placeholder else ""),
            "default": "the tool's own default",
            "unset": "not set: " + s.used_by + " stay undecided or excluded",
        }[r.origin]
        lines.append(f"  {s.key} = {r.display}{unit}   [{origin}]")
        lines.append(f"      {s.label}. {s.what} Used by: {s.used_by}. Source: {s.source}.")
    lines.append("\nAssumptions built into the tool")
    for a, title, kind, rs in assumptions_in_force(project):
        mine = "; ".join(f"{r.setting.id} = {r.display}" for r in rs)
        lines.append(f"  {a} ({kind}) {title}" + (f"  [{mine}]" if mine else ""))
    lines.append("\nFixed definitions (not engineering choices)")
    for d in DEFINITIONS:
        lines.append(f"  {d.id}: {d.title}. {d.text} [{d.where}]")
    return "\n".join(lines).lstrip("\n")
