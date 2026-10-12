"""Check and fill in the engineering configuration (D-11).

The real derating, ampacity and EMC values will come from the program's standard later. This
module makes that handover safe: it lists exactly which values are still missing and what depends
on each, validates values when they arrive (a factor above 1 or an ampacity that falls as the
wire gets bigger is rejected with a reason), and reads an ampacity table from a CSV so nobody has
to type JSON by hand. It never supplies a number itself.
"""

import math
from dataclasses import dataclass

from harness_design_studio.core import standard_profiles
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
    return isinstance(v, list) and all(
        isinstance(p, list) and len(p) == 2 and all(isinstance(x, str) and x for x in p) for p in v
    )


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
                bad(n, 'must be a list of pairs of names, for example [["A", "B"]]')
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
    decisions = {"segmentation": "D-10 (harness boundary rule)", "titleblock": "D-15 (title block)"}
    waiting = sorted(
        name
        for name, c in project.config.items()
        if c.placeholder and name in decisions and name not in {n.file for n in NEEDS}
    )
    for name in waiting:  # not values to type in, but owner decisions that are still open
        lines.append(
            f"Waiting for an owner decision: config/{name}.json is a placeholder until {decisions[name]} is made."
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
