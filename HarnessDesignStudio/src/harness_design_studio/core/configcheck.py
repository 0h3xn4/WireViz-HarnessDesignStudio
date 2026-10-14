"""Check and fill in the engineering configuration (D-11).

The real derating, ampacity and EMC values will come from the program's standard later. This
module makes that handover safe: it lists exactly which values are still missing and what depends
on each, validates values when they arrive (a factor above 1 or an ampacity that falls as the
wire gets bigger is rejected with a reason), and reads an ampacity table from a CSV so nobody has
to type JSON by hand. It never supplies a number itself.
"""

import math
import re
from dataclasses import dataclass

from harness_design_studio.core import standard_profiles
from harness_design_studio.core.commands import Op, SetConfig
from harness_design_studio.core.issues import Issue
from harness_design_studio.core.model import Project
from harness_design_studio.core.model.config import ConfigFile

Table = list[list[str]]
SHIELD_ENDS = ("backshell_360", "pigtail", "floating")


@dataclass(frozen=True)
class Need:
    file: str
    key: str
    what: str  # plain language
    used_by: str  # what stays "not checked" or "pending" until it is set


NEEDS: tuple[Need, ...] = (
    Need("derating", "ampacity_a_by_awg", "current each wire gauge may carry, in amperes, as {\"20\": 5.0, ...}", "wire sizing, wire current check"),
    Need("derating", "bundle_derating", "factor (above 0, at most 1) for wires in a bundle", "wire sizing, wire current check"),
    Need("derating", "temperature_derating", "factor (above 0, at most 1) for the maximum ambient temperature", "wire sizing, wire current check"),
    Need("derating", "contact_current_factor", "fraction (above 0, at most 1) of a contact's rating that may be used", "contact current check"),
    Need("derating", "max_voltage_drop_v", "largest allowed voltage drop, in volts", "wire sizing, voltage drop check"),
    Need("derating", "spare_pin_fraction", "share of pins (0 to 1) that must stay spare", "spare pin check"),
    Need("generation", "conductor_resistivity_ohm_m", "conductor resistivity in ohm metres", "wire sizing, voltage drop check"),
    Need("generation", "shield_end_a", "grounding of shield end A: backshell_360, pigtail or floating", "shield grounding check, shield ends in generated harnesses"),
    Need("generation", "shield_end_b", "grounding of shield end B: backshell_360, pigtail or floating", "shield grounding check, shield ends in generated harnesses"),
    Need("generation", "service_loop_m", "extra length added at each end, in metres", "wire lengths (excluded while unset)"),
    Need("generation", "power_signal_gap_pins", "empty pins between power and signal pins", "pin allocation (0 used while unset)"),
    Need("generation", "mass_margin_fraction", "margin added to masses (0 or more)", "mass with margin"),
    Need("generation", "test_continuity_max_ohm", "largest resistance accepted as continuous, in ohms", "continuity test limits"),
    Need("generation", "test_isolation_min_mohm", "smallest insulation resistance accepted, in megohms", "isolation test limits"),
    Need("generation", "test_isolation_voltage_v", "test voltage for the isolation test, in volts", "isolation test limits"),
    Need("segregation", "category_pairs_to_separate", "pairs of interface categories that must not share a harness, for example [[\"power\", \"analog\"]]", "category separation check"),
    Need("emc", "conflicting_class_pairs", "pairs of EMC classes that must not share a harness, for example [[\"A\", \"B\"]]", "EMC separation check"),
)  # fmt: skip


# Values that are not part of the hand-over list above: the rules of the supplied standards
# (D-131) stay silent until a profile or an engineer sets them. They are listed apart so that
# `missing`, `report` and `harness-design-studio config` keep saying exactly what they said before.
OPTIONAL_NEEDS: tuple[Need, ...] = (
    Need("derating", "max_ambient_temperature_c", "hottest ambient temperature, in degrees Celsius", "temperature margin check"),
    Need("derating", "connector_temperature_margin_c", "how far below its maximum rating a connector must stay, in degrees Celsius", "temperature margin check"),
    Need("derating", "wire_temperature_margin_c", "how far below its maximum rating a wire must stay, in degrees Celsius", "temperature margin check"),
    Need("derating", "connector_voltage_factor_withstand", "share (above 0, at most 1) of the dielectric withstanding voltage a connector may work at", "connector working voltage check"),
    Need("derating", "connector_voltage_factor_rated", "share (above 0, at most 1) of the rated voltage a connector may work at", "connector working voltage check"),
    Need("derating", "wire_voltage_factor", "share (above 0, at most 1) of the rated voltage a wire may work at", "wire working voltage check"),
    Need("derating", "max_mating_cycles", "most mating and de-mating cycles the programme may use", "mating cycles check"),
    Need("derating", "bundle_factor_by_count", "derating factor K by number of wires in a bundle, as {\"1\": 1, \"2\": 0.9, ...}", "bundle current check, wire sizing"),
    Need("generation", "power_return_gap_pins", "unassigned contacts between power and return pins", "power and return pin check"),
    Need("emc", "shield_bonding", "how shields are bonded: both_ends_backshell", "shield bonding check, shield parts check"),
    Need("emc", "same_class_one_bundle", "true if wires of one EMC class must share one bundle", "EMC class split check"),
)  # fmt: skip


def need_for(file: str, key: str) -> Need | None:
    """The description of a value, whether it is a required one or an optional one."""
    return next((n for n in (*NEEDS, *OPTIONAL_NEEDS) if (n.file, n.key) == (file, key)), None)


def _cfg(project: Project, name: str) -> dict[str, object]:
    c = project.config.get(name)
    return dict(c.values) if c is not None else {}


def missing(project: Project) -> list[Need]:
    return [n for n in NEEDS if _cfg(project, n.file).get(n.key) is None]


def _num(v: object) -> float | None:
    """A finite number (not a bool, not inf or nan); anything else is not a number here."""
    if isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v):
        return float(v)
    return None


def _pairs_ok(v: object) -> bool:
    """Pairs of two different names, each pair once (["A","B"] and ["B","A"] are the same pair)."""
    if not isinstance(v, list) or not all(
        isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) and x for x in p) for p in v
    ):
        return False
    pairs = [frozenset(p) for p in v]
    return all(len(p) == 2 for p in pairs) and len(set(pairs)) == len(pairs)


def validate(project: Project) -> list[Issue]:
    """Problems with values that ARE set (unset values are not problems, only 'missing')."""
    out: list[Issue] = []

    def bad(n: Need, why: str) -> None:
        out.append(
            Issue(
                "error",
                "config_invalid",
                f"config/{n.file}.json: {n.key} {why}.",
                f"config/{n.file}.json",
                f"{n.file}.{n.key}",
            )
        )

    for n in NEEDS:
        v = _cfg(project, n.file).get(n.key)
        if v is None:
            continue
        if n.key in ("bundle_derating", "temperature_derating", "contact_current_factor"):
            x = _num(v)
            if x is None or not 0 < x <= 1:
                bad(n, "must be a number above 0 and at most 1")
        elif n.key == "spare_pin_fraction":
            x = _num(v)
            if x is None or not 0 <= x < 1:
                bad(n, "must be a number from 0 up to (not including) 1")
        elif n.key in (
            "max_voltage_drop_v",
            "conductor_resistivity_ohm_m",
            "test_continuity_max_ohm",
            "test_isolation_min_mohm",
            "test_isolation_voltage_v",
        ):
            x = _num(v)
            if x is None or x <= 0:
                bad(n, "must be a number above 0")
        elif n.key in ("service_loop_m", "mass_margin_fraction", "power_signal_gap_pins"):
            x = _num(v)
            if x is None or x < 0 or (n.key == "power_signal_gap_pins" and x != int(x)):
                bad(
                    n,
                    "must be a number of 0 or more"
                    + (" (a whole number)" if n.key == "power_signal_gap_pins" else ""),
                )
        elif n.key in ("shield_end_a", "shield_end_b"):
            if v not in SHIELD_ENDS:
                bad(n, f"must be one of {', '.join(SHIELD_ENDS)}")
        elif n.key in ("category_pairs_to_separate", "conflicting_class_pairs"):
            if not _pairs_ok(v):
                bad(
                    n,
                    'must be a list of pairs of two different names, each pair once, for example [["A", "B"]]',
                )
        elif n.key == "ampacity_a_by_awg":
            out.extend(_validate_ampacity(n, v))
    out.extend(validate_titleblock(project))
    out.extend(standard_profiles.validate(project))
    return out


def _validate_ampacity(n: Need, v: object) -> list[Issue]:
    where = f"config/{n.file}.json"

    def err(msg: str) -> list[Issue]:
        return [
            Issue("error", "config_invalid", f"{where}: {n.key} {msg}.", where, f"{n.file}.{n.key}")
        ]

    if not isinstance(v, dict) or not v:
        return err('must be a table of gauge and amperes, for example {"20": 5.0}')
    table: dict[int, float] = {}
    for k, a in v.items():
        try:
            gauge = int(k)
        except (TypeError, ValueError):
            return err(f"has '{k}' as a gauge; gauges are whole numbers such as 20")
        amps = _num(a)
        if not 0 <= gauge <= 40 or amps is None or amps <= 0:
            return err(
                f"has an impossible entry for gauge {k}: gauge 0 to 40 and amperes above 0 are needed"
            )
        table[gauge] = amps
    ordered = sorted(table)  # a smaller AWG number is a bigger wire and must carry at least as much
    for small, big in zip(ordered, ordered[1:], strict=False):
        if table[small] < table[big]:
            return err(
                f"says gauge {small} (the bigger wire) carries less than gauge {big}; check the table"
            )
    return []


def plan_ampacity_import(table: Table) -> tuple[dict[str, float], list[str]]:
    """Read a two-column table (gauge, amperes) with or without a header row. Returns the table
    for `ampacity_a_by_awg` and a list of row problems; nothing is applied if there are any."""
    problems: list[str] = []
    out: dict[str, float] = {}
    for n, row in enumerate(table, start=1):
        if len(row) < 2:
            problems.append(f"Row {n}: needs a gauge and an ampere value")
            continue
        g, a = row[0].strip(), row[1].strip().replace(",", ".")
        if n == 1 and not g.lstrip("-").isdigit():
            continue  # header row
        try:
            gauge, amps = int(g), float(a)
        except ValueError:
            problems.append(
                f"Row {n}: '{row[0]}' and '{row[1]}' are not a gauge and an ampere value"
            )
            continue
        if not 0 <= gauge <= 40 or not amps > 0 or amps == float("inf"):
            problems.append(f"Row {n}: gauge {gauge} with {row[1]} A is not possible")
        elif str(gauge) in out:
            problems.append(f"Row {n}: gauge {gauge} appears twice")
        else:
            out[str(gauge)] = amps
    if not out and not problems:
        problems.append("The table has no data rows")
    return out, problems


def with_value(cfg: ConfigFile, key: str, value: object) -> ConfigFile:
    return ConfigFile(name=cfg.name, placeholder=cfg.placeholder, values={**cfg.values, key: value})


def report(project: Project) -> tuple[str, bool]:
    """The hand-over checklist as text, and whether every value is set and valid."""
    todo, problems = missing(project), validate(project)
    lines = [f"Engineering values: {len(NEEDS) - len(todo)} of {len(NEEDS)} set."]
    for n in todo:
        lines.append(f"- MISSING config/{n.file}.json {n.key}: {n.what}. Needed for: {n.used_by}.")
    lines += [f"- INVALID {i.message}" for i in problems]
    still = sorted(
        name
        for name, c in project.config.items()
        if c.placeholder and name in {n.file for n in NEEDS}
    )
    if still:
        lines.append(
            f'Files still marked as placeholder (set "placeholder": false after review): {", ".join(still)}.'
        )
    decisions = {
        "segmentation": "the rule for how interfaces are grouped into harnesses is confirmed",
        "titleblock": "the title block fields are confirmed",
    }
    waiting = sorted(
        name
        for name, c in project.config.items()
        if c.placeholder and name in decisions and name not in {n.file for n in NEEDS}
    )
    for name in waiting:  # not values to type in, but owner decisions that are still open
        lines.append(
            f"Waiting for an owner decision: config/{name}.json is a placeholder until {decisions[name]}."
        )
    return "\n".join(lines), not todo and not problems


TITLEBLOCK_FIELDS = (
    "project", "harness_id", "title", "revision", "date", "author", "checker", "approver",
    "sheet", "status",
)  # fmt: skip
TITLEBLOCK_DEFAULT = ("project", "harness_id", "title", "revision", "status", "sheet")


def validate_titleblock(project: Project) -> list[Issue]:
    """`titleblock.json` `fields` must be a list of known field names, each at most once. Any
    of them may be left out (the sheet number too); a missing or empty list means the default."""
    raw = _cfg(project, "titleblock").get("fields")
    if raw is None:
        return []
    where = "config/titleblock.json"

    def err(why: str) -> list[Issue]:
        return [
            Issue(
                "error",
                "config_invalid",
                f"{where}: fields {why}. The fields are: {', '.join(TITLEBLOCK_FIELDS)}.",
                where,
                "titleblock.fields",
            )
        ]

    if not isinstance(raw, list):
        return err("must be a list of field names")
    for f in raw:
        if not isinstance(f, str):
            return err("must contain only field names written as text")
    unknown = [f for f in raw if f not in TITLEBLOCK_FIELDS]
    if unknown:
        shown = ", ".join(f"'{f[:30]}'" for f in unknown[:3])
        return err(f"names a field that does not exist ({shown})")
    twice = sorted({f for f in raw if raw.count(f) > 1})
    if twice:
        return err(f"lists '{twice[0]}' more than once")
    return []


def titleblock_fields(project: Project) -> list[str]:
    """The fields the title block shows, in order: the configured list when it is valid and not
    empty, else the default. (An invalid list is reported by `validate_titleblock`.)"""
    raw = _cfg(project, "titleblock").get("fields")
    if validate_titleblock(project) or not isinstance(raw, list) or not raw:
        return list(TITLEBLOCK_DEFAULT)
    return [str(f) for f in raw]


# ---- the engineering values as a form -----------------------------------------------------------------
#
# Everything below is headless support for a form that lists the values and sets them. It reads and
# writes nothing by itself: `plan_set_value` returns the ops, which the caller runs through the
# history like any other change, and the values are checked by `validate`.


@dataclass(frozen=True)
class FieldInfo:
    label: str
    unit: str = ""
    kind: str = "number"  # "number" | "choice" | "pairs" | "table" | "flag"
    choices: tuple[str, ...] = ()
    whole: bool = False  # a whole number
    hint: str = ""  # how to type a list or a table


_TABLE_HINT = "Write one entry per line or separated by commas, like 20: 5.0"
FIELD_INFO: dict[tuple[str, str], FieldInfo] = {
    ("derating", "ampacity_a_by_awg"): FieldInfo("Ampacity by wire gauge", "A", "table", hint="Write one gauge and its amperes per entry, like 20: 5.0, 22: 3.5"),
    ("derating", "bundle_derating"): FieldInfo("Bundle derating factor"),
    ("derating", "temperature_derating"): FieldInfo("Temperature derating factor"),
    ("derating", "contact_current_factor"): FieldInfo("Contact current factor"),
    ("derating", "max_voltage_drop_v"): FieldInfo("Maximum voltage drop", "V"),
    ("derating", "spare_pin_fraction"): FieldInfo("Spare pin fraction"),
    ("generation", "conductor_resistivity_ohm_m"): FieldInfo("Conductor resistivity", "ohm m"),
    ("generation", "shield_end_a"): FieldInfo("Shield grounding, end A", kind="choice", choices=SHIELD_ENDS),
    ("generation", "shield_end_b"): FieldInfo("Shield grounding, end B", kind="choice", choices=SHIELD_ENDS),
    ("generation", "service_loop_m"): FieldInfo("Service loop at each end", "m"),
    ("generation", "power_signal_gap_pins"): FieldInfo("Pins between power and signal", "pins", whole=True),
    ("generation", "mass_margin_fraction"): FieldInfo("Mass margin"),
    ("generation", "test_continuity_max_ohm"): FieldInfo("Largest continuity resistance", "ohm"),
    ("generation", "test_isolation_min_mohm"): FieldInfo("Smallest insulation resistance", "Mohm"),
    ("generation", "test_isolation_voltage_v"): FieldInfo("Isolation test voltage", "V"),
    ("segregation", "category_pairs_to_separate"): FieldInfo("Categories kept apart", kind="pairs", hint="Write pairs joined by +, separated by commas, like power + analog, data + rf"),
    ("emc", "conflicting_class_pairs"): FieldInfo("EMC classes kept apart", kind="pairs", hint="Write pairs joined by +, separated by commas, like A + B, C + D"),
    ("derating", "max_ambient_temperature_c"): FieldInfo("Hottest ambient temperature", "degC"),
    ("derating", "connector_temperature_margin_c"): FieldInfo("Connector temperature margin", "degC"),
    ("derating", "wire_temperature_margin_c"): FieldInfo("Wire temperature margin", "degC"),
    ("derating", "connector_voltage_factor_withstand"): FieldInfo("Connector voltage share of withstand voltage"),
    ("derating", "connector_voltage_factor_rated"): FieldInfo("Connector voltage share of rated voltage"),
    ("derating", "wire_voltage_factor"): FieldInfo("Wire voltage share of rated voltage"),
    ("derating", "max_mating_cycles"): FieldInfo("Most mating cycles", "cycles", whole=True),
    ("derating", "bundle_factor_by_count"): FieldInfo("Bundle factor by wire count", kind="table", hint="Write one wire count and its factor per entry, like 1: 1.0, 10: 0.57"),
    ("generation", "power_return_gap_pins"): FieldInfo("Pins between power and return", "pins", whole=True),
    ("emc", "shield_bonding"): FieldInfo("Shield bonding", kind="choice", choices=("both_ends_backshell",)),
    ("emc", "same_class_one_bundle"): FieldInfo("One bundle per EMC class", kind="flag"),
}  # fmt: skip


@dataclass(frozen=True)
class EngineeringValue:
    """One value of the hand-over list, ready to show in a form."""

    file: str
    key: str
    label: str
    unit: str
    kind: str  # "number" | "choice" | "pairs" | "table" | "flag"
    choices: tuple[str, ...]
    hint: str
    what: str  # plain-language description (the hand-over list's own words)
    used_by: str  # what stays unchecked or pending until it is set
    value: object  # as stored (None: not set)
    display: str  # the value as text for the form ("" when not set)
    placeholder: bool  # the file is still marked as a placeholder: nobody has reviewed it
    source: str  # "" (not set), a requirement ID with its profile, or "set in the project"
    missing: bool
    optional: bool  # a value of a standard profile, not on the hand-over list
    locked: str | None  # why a release forbids changing it (None: it can be changed)


def display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, dict):
        return ", ".join(f"{k}: {display_value(v)}" for k, v in value.items())
    if isinstance(value, list):
        return "; ".join(
            " + ".join(map(str, x)) if isinstance(x, list) else display_value(x) for x in value
        )
    return str(value)


def _source(file: str, key: str, value: object) -> str:
    if value is None:
        return ""
    for name, settings in standard_profiles.PROFILES.items():
        for s in settings:
            if (s.file, s.key) == (file, key) and s.value == value:
                return f"{s.source} (profile {name})"
    return "set in the project"


def engineering_values(
    project: Project, *, include_optional: bool = False
) -> list[EngineeringValue]:
    """The hand-over list (`NEEDS`, in that order) as form fields; with `include_optional` the
    values of the standard profiles follow."""
    from harness_design_studio.core.vcs.lockview import field_lock_reason, locked_objects

    locked = locked_objects(project)
    out: list[EngineeringValue] = []
    for optional, needs in ((False, NEEDS), (True, OPTIONAL_NEEDS)):
        if optional and not include_optional:
            continue
        for n in needs:
            info = FIELD_INFO[(n.file, n.key)]
            value = _cfg(project, n.file).get(n.key)
            cfg = project.config.get(n.file)
            out.append(
                EngineeringValue(
                    n.file, n.key, info.label, info.unit, info.kind, info.choices, info.hint,
                    n.what, n.used_by, value, display_value(value),
                    cfg.placeholder if cfg is not None else True,
                    _source(n.file, n.key, value), value is None, optional,
                    field_lock_reason(project, "config", n.file, n.key, locked),
                )
            )  # fmt: skip
    return out


@dataclass(frozen=True)
class ValuePlan:
    """The result of asking to set a value: the ops that do it, or the reason it cannot be done."""

    ops: list[Op]
    error: str | None = None
    value: object = None  # the value as it will be stored

    @property
    def ok(self) -> bool:
        return self.error is None


def _fail(message: str) -> ValuePlan:
    return ValuePlan([], message)


def _read_number(info: FieldInfo, raw: object) -> tuple[object, str | None]:
    if isinstance(raw, bool):
        return None, f"{info.label}: {raw} is not a number."
    if isinstance(raw, int | float):
        x = float(raw)
        shown = str(raw)
    else:
        shown = str(raw).strip()
        text = shown.replace(",", ".")
        if info.unit and text.lower().endswith(info.unit.lower()):
            text = text[: -len(info.unit)].strip()
        try:
            x = float(text)
        except ValueError:
            return None, f"{info.label}: '{shown[:30]}' is not a number."
    if not math.isfinite(x):
        return None, f"{info.label}: {shown[:30]} is not a number."
    if info.whole and x.is_integer():
        return int(x), None
    return (raw if isinstance(raw, int) else x), None


def _read_table(info: FieldInfo, raw: object) -> tuple[object, str | None]:
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items()}, None
    out: dict[str, float] = {}
    for item in re.split(r"[,;\n]", str(raw)):
        item = item.strip()
        if not item:
            continue
        parts = re.split(r"\s*[:=]\s*", item)
        try:
            if len(parts) != 2:
                raise ValueError(item)
            out[str(int(parts[0]))] = float(parts[1])
        except ValueError:
            return None, f"{info.label}: '{item[:30]}' is not an entry. {info.hint}."
    if not out:
        return None, f"{info.label}: no entries found. {info.hint}."
    return out, None


def _read_pairs(info: FieldInfo, raw: object) -> tuple[object, str | None]:
    if isinstance(raw, list):
        return raw, None
    out: list[list[str]] = []
    for item in re.split(r"[,;\n]", str(raw)):
        if not item.strip():
            continue
        parts = [x.strip() for x in re.split(r"[+/]", item)]
        if len(parts) != 2 or not all(parts):
            return None, f"{info.label}: '{item.strip()[:30]}' is not a pair. {info.hint}."
        out.append(parts)
    return out, None


def _read_value(info: FieldInfo, raw: object) -> tuple[object, str | None]:
    """The stored form of what was typed or chosen; (None, None) clears the value."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, None
    if info.kind == "number":
        return _read_number(info, raw)
    if info.kind == "choice":
        text = str(raw).strip()
        if text not in info.choices:
            return None, f"{info.label} must be one of {', '.join(info.choices)}."
        return text, None
    if info.kind == "flag":
        text = str(raw).strip().lower()
        if isinstance(raw, bool):
            return raw, None
        if text in ("true", "yes", "on", "1"):
            return True, None
        if text in ("false", "no", "off", "0"):
            return False, None
        return None, f"{info.label} must be yes or no."
    if info.kind == "table":
        return _read_table(info, raw)
    return _read_pairs(info, raw)


def plan_set_value(
    project: Project, file: str, key: str, value: object, *, placeholder: bool | None = None
) -> ValuePlan:
    """The ops that set `key` of config file `file` (nothing else changes), or why not. `value`
    may be what a form gives (text such as "0,5 V", "power + analog, data + rf", "20: 5, 22: 3.5")
    or a ready value; empty text or None clears it. `placeholder` also sets the file's review
    flag. The value is checked by `validate`, and the result is refused if a release froze it."""
    from harness_design_studio.core.edit import clone_with
    from harness_design_studio.core.errors import TransactionError
    from harness_design_studio.core.vcs.locks import check_locks

    if need_for(file, key) is None or (file, key) not in FIELD_INFO:
        return _fail(f"config/{file}.json has no engineering value called {key}.")
    info = FIELD_INFO[(file, key)]
    parsed, error = _read_value(info, value)
    if error is not None:
        return _fail(error)
    old = project.config.get(file)
    base = old if old is not None else ConfigFile(name=file, placeholder=True, values={})
    new = ConfigFile(
        name=file,
        placeholder=base.placeholder if placeholder is None else placeholder,
        values={**base.values, key: parsed},
    )
    ops: list[Op] = [SetConfig(new)]
    if parsed is not None:
        trial = clone_with(project, ops)
        for issue in validate(trial):
            if issue.object_id == f"{file}.{key}":
                why = issue.message.removeprefix(f"config/{file}.json: ").removeprefix(f"{key} ")
                return _fail(f"{info.label} {why}")
    try:
        check_locks(project, ops)
    except TransactionError as exc:
        return _fail(exc.problems[0] if exc.problems else str(exc))
    return ValuePlan(ops, None, parsed)


def plan_placeholder(project: Project, file: str, placeholder: bool) -> ValuePlan:
    """The ops that mark a config file as reviewed (False) or as a placeholder (True)."""

    old = project.config.get(file)
    if old is None:
        return _fail(f"config/{file}.json does not exist in this project.")
    return ValuePlan(
        [SetConfig(ConfigFile(name=file, placeholder=placeholder, values=dict(old.values)))]
    )
