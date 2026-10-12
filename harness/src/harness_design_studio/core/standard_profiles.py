"""Optional value profiles taken from the supplied standards (D-131).

The tool ships no standard values by default. A project may switch a profile on; the profile fills
only the values that are still unset (`null`), marks every file it changes as a placeholder (even
one an engineer had reviewed: the new values are not reviewed), and every value carries the ID of
the requirement it comes from (compliance/requirements). Nothing here is applied silently, and
the values still need an engineer's review.

Profiles:
  ecss-q-st-30-11c   derating of connectors, wires and bundles (ECSS-Q-ST-30-11C Rev.2)
  ecss-e-st-20-07c   wiring and shield rules (ECSS-E-ST-20-07C Rev.2)
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from harness_design_studio.core.issues import Issue
from harness_design_studio.core.model import ConfigFile, Project

Q = "ECSS-Q-ST-30-11_"
E = "ECSS-E-ST-20-07_"


@dataclass(frozen=True)
class Setting:
    file: str
    key: str
    value: object
    source: str  # requirement ID
    note: str


# Table 6-41: derating factor K for bundles (fully loaded), by count of wires.
BUNDLE_K = {"1": 1, "2": 0.9, "3": 0.81, "4": 0.76, "5": 0.71, "6": 0.66, "7": 0.62, "8": 0.6,
            "9": 0.59, "10": 0.57, "15": 0.49, "25": 0.4, "50": 0.29, "100": 0.21, "200": 0.15,
            "300": 0.12}  # fmt: skip
# Table 6-42: additional factor L for partially loaded bundles, by share of wires carrying current.
PARTIAL_L = {"below_25_percent": 1.2, "25_to_50_percent": 1.1, "above_50_percent": 1}

PROFILES: dict[str, tuple[Setting, ...]] = {
    "ecss-q-st-30-11c": (
        Setting("derating", "contact_current_factor", 0.5, Q + "0140051",
                "Table 6-10 current 50 %"),
        Setting("derating", "connector_voltage_factor_withstand", 0.25, Q + "0140051",
                "Table 6-10 working voltage: 25 % of the dielectric withstanding voltage"),
        Setting("derating", "connector_voltage_factor_rated", 0.75, Q + "0140051",
                "Table 6-10 working voltage: 75 % of the rated voltage, whichever is lower"),
        Setting("derating", "connector_temperature_margin_c", 30, Q + "0140051",
                "Table 6-10 maximum operating temperature 30 degC below the maximum rating"),
        Setting("derating", "rf_power_factor", 0.75, Q + "0140058", "Table 6-11 RF power 75 %"),
        Setting("derating", "wire_voltage_factor", 0.5, Q + "0140213", "6.32.4 a.1 voltage 50 %"),
        Setting("derating", "wire_temperature_margin_c", 50, Q + "0140213",
                "6.32.4 a.2 wire surface temperature 50 degC below the manufacturer maximum"),
        Setting("derating", "bundle_factor_by_count", BUNDLE_K, Q + "0140218",
                "Table 6-41, K for a full bundle; n wires use the next listed count"),
        Setting("derating", "partial_load_factor", PARTIAL_L, Q + "0140220",
                "Table 6-42, L for partially loaded bundles (not applied automatically)"),
        Setting("derating", "max_mating_cycles", 50, Q + "0140056",
                "6.11.3 e and 6.12.3 c: at most 50 mating and de-mating cycles"),
        Setting("generation", "power_return_gap_pins", 1, Q + "0140052",
                "6.11.3 a: power and return separated by at least one unassigned contact"),
    ),
    "ecss-e-st-20-07c": (
        Setting("emc", "shield_bonding", "both_ends_backshell", E + "0080041",
                "4.2.13.2 d: shields bonded at both ends through the connector body or backshell"),
        Setting("emc", "same_class_one_bundle", True, E + "0080035",
                "4.2.13.1 b: wires of one category in the same bundle"),
    ),
}  # fmt: skip

POSITIVE_FACTORS = (
    "contact_current_factor",
    "connector_voltage_factor_withstand",
    "connector_voltage_factor_rated",
    "rf_power_factor",
    "wire_voltage_factor",
)
NON_NEGATIVE = ("connector_temperature_margin_c", "wire_temperature_margin_c")


@dataclass(frozen=True)
class ProfilePlan:
    configs: list[ConfigFile]  # files to write
    applied: list[Setting]
    kept: list[tuple[Setting, object]]  # already set by a person: not overwritten
    marked: tuple[
        str, ...
    ] = ()  # reviewed files that are a placeholder again, as values were added


def plan_profile(project: Project, name: str) -> ProfilePlan:
    if name not in PROFILES:
        raise ValueError(f"unknown profile '{name}'; choose one of {', '.join(sorted(PROFILES))}")
    files = {n: c for n, c in project.config.items()}
    applied: list[Setting] = []
    kept: list[tuple[Setting, object]] = []
    changed: dict[str, dict[str, object]] = {}
    for s in PROFILES[name]:
        base = files.get(s.file)
        values = dict(base.values) if base is not None else {}
        values.update(changed.get(s.file, {}))
        current = values.get(s.key)
        if current is None:
            changed.setdefault(s.file, {})[s.key] = copy.deepcopy(
                s.value
            )  # not shared with the profile
            applied.append(s)
        elif current != s.value:
            kept.append((s, current))
    out = []
    marked: list[str] = []
    for fname, new in sorted(changed.items()):
        base = files.get(fname)
        if base is not None and not base.placeholder:
            marked.append(fname)
        out.append(
            ConfigFile(
                name=fname,
                placeholder=True,  # values the profile set are not reviewed (D-131)
                values={**(base.values if base else {}), **new},
            )
        )
    return ProfilePlan(out, applied, kept, tuple(marked))


def _table_ok(v: object, numeric_keys: bool, upper: float = 2) -> bool:
    """A non-empty table of numbers above 0 and up to `upper` (K is at most 1, L up to 2)."""
    if not isinstance(v, dict) or not v:
        return False
    for k, x in v.items():
        if numeric_keys:
            try:
                if int(k) < 1:
                    return False
            except (TypeError, ValueError):
                return False
        if not isinstance(x, int | float) or isinstance(x, bool) or not 0 < x <= upper:
            return False
    return True


def validate(project: Project) -> list[Issue]:
    """Problems with the optional standard values that ARE set."""
    out: list[Issue] = []

    def bad(file: str, key: str, why: str) -> None:
        out.append(Issue("error", "config_invalid", f"config/{file}.json: {key} {why}.",
                         f"config/{file}.json", f"{file}.{key}"))  # fmt: skip

    d = project.config.get("derating")
    dv = d.values if d is not None else {}
    for k in POSITIVE_FACTORS:
        v = dv.get(k)
        if v is not None and not (
            isinstance(v, int | float) and not isinstance(v, bool) and 0 < v <= 1
        ):
            bad("derating", k, "must be a number above 0 and at most 1")
    for k in NON_NEGATIVE:
        v = dv.get(k)
        if v is not None and not (
            isinstance(v, int | float) and not isinstance(v, bool) and v >= 0
        ):
            bad("derating", k, "must be a number of 0 or more")
    v = dv.get("max_mating_cycles")
    if v is not None and not (isinstance(v, int) and not isinstance(v, bool) and v >= 1):
        bad("derating", "max_mating_cycles", "must be a whole number of 1 or more")
    v = dv.get("bundle_factor_by_count")
    if v is not None:
        if not _table_ok(v, True, 1):
            bad(
                "derating",
                "bundle_factor_by_count",
                "must be a table of wire count and factor (K above 0, at most 1)",
            )
        else:
            counts = sorted(v, key=int)
            factors = [v[c] for c in counts]
            if any(b > a for a, b in zip(factors, factors[1:], strict=False)):
                bad("derating", "bundle_factor_by_count", "must not rise as the wire count grows")
    v = dv.get("partial_load_factor")
    if v is not None and not (
        _table_ok(v, False)
        and set(v) == {"below_25_percent", "25_to_50_percent", "above_50_percent"}
    ):
        bad("derating", "partial_load_factor",
            "must have below_25_percent, 25_to_50_percent and above_50_percent")  # fmt: skip
    g = project.config.get("generation")
    gv = g.values if g is not None else {}
    v = gv.get("power_return_gap_pins")
    if v is not None and not (isinstance(v, int) and not isinstance(v, bool) and v >= 0):
        bad("generation", "power_return_gap_pins", "must be a whole number of 0 or more")
    v = gv.get("default_gauge_awg")
    if v is not None and not (isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 40):
        bad("generation", "default_gauge_awg", "must be a whole number from 0 to 40")
    v = dv.get("max_ambient_temperature_c")
    if v is not None and not (
        isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v) and v > -273.15
    ):
        bad("derating", "max_ambient_temperature_c", "must be a temperature in degC above -273.15")
    v = dv.get("contact_rating_key")
    if v is not None and not (isinstance(v, str) and v.strip()):
        bad("derating", "contact_rating_key", "must be the name of a part rating")
    s = project.config.get("segregation")
    for k in ("forbid_nominal_with_redundant", "forbid_pyro_with_other"):
        v = (s.values if s is not None else {}).get(k)
        if v is not None and not isinstance(v, bool):
            bad("segregation", k, "must be true or false")
    e = project.config.get("emc")
    ev = e.values if e is not None else {}
    v = ev.get("classes")
    if v is not None and not (
        isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v)
    ):
        bad("emc", "classes", "must be a list of class names")
    v = ev.get("shield_bonding")
    if v is not None and v != "both_ends_backshell":
        bad("emc", "shield_bonding", "must be both_ends_backshell")
    return out
