"""The limit of every design rule, or, for a rule that has none, what it compares (D-191, S1).

`explain_finding(project, rule_id, object_id)` (in `core.derive`) answers for every rule of the
registry `drc.RULES`, for the independent verification and for the logical rules of the Problems
panel. A rule falls in one of two forms, which `INFO` records for each:

    limit      the rule compares a number with a limit. The derivation (kind `rule-limit`, or the kind
               of its own for the three rules explained since step 1: `wire-current-limit`,
               `wire-voltage-drop`, `contact-current`) carries the equation, the inputs with their
               units and sources, the steps and the check: actual, limit, margin and the verdict.
    yes-no     the rule has no numeric limit. The derivation (kind `rule-check`) says so in its
               equation, "this rule is a yes/no check: it compares X with Y", and shows the
               statement of the finding, the configuration the rule reads and what it saw.

The numbers come from the very functions the rules call (`standard_rules.connector_voltage_limit`,
`sizing.wire_current_limit`, `sizing.exceeds`, ...), so an explanation cannot disagree with a finding:
a test compares the verdict of every derivation with the finding of the rule. The findings
themselves are not changed (their texts feed the hashes of the written files).
"""

from collections.abc import Callable
from dataclasses import dataclass

from harness_design_studio.core import settings
from harness_design_studio.core.checks import Finding
from harness_design_studio.core.checks import find as logical_findings
from harness_design_studio.core.derive import (
    EXPLAINABLE_RULES,
    LOGICAL_RULES,
    Check,
    Derivation,
    Input,
    Step,
    _bundle,
    _g,
    text_step,
)
from harness_design_studio.core.drc import run as run_drc
from harness_design_studio.core.drc.base import cfg, number
from harness_design_studio.core.drc.by_rule import READS
from harness_design_studio.core.drc.rules import RULES, _carried, wires_on_pins
from harness_design_studio.core.drc.standard_rules import (
    _rating,
    _temperature_users,
    connector_voltage_limit,
    emc_class_bundles,
)
from harness_design_studio.core.generate.bundle import bundle_size
from harness_design_studio.core.generate.sizing import (
    ampacity_table,
    exceeds,
    wire_current_limit,
)
from harness_design_studio.core.model import Harness, Project, ShieldGroup
from harness_design_studio.core.units import AWG_MAX, AWG_MIN, format_awg

RULE_IDS = EXPLAINABLE_RULES
SHOWN = 8  # how many names a line gives before "and N more": no result depends on it

Builder = Callable[[Project, str], Derivation | None]
Observer = Callable[[Project, str], list[Input]]


@dataclass(frozen=True)
class RuleInfo:
    """What an explanation says about a rule, besides the object it is asked for."""

    form: str  # "limit" or "yes-no"
    compares: str  # "X with Y": the two things the rule compares
    assumptions: tuple[str, ...] = ()
    build: Builder | None = None  # the derivation of the limit, for a rule of the form "limit"
    observe: Observer | None = None  # what the rule saw at the object, for a yes/no rule


def _gauge_name(awg: int | None) -> str:
    """A gauge with its cross-section, for the name of an input (D2): `AWG 24 (0.205 mm²)`."""
    if awg is None or not AWG_MIN <= awg <= AWG_MAX:
        return f"AWG {awg}"
    return format_awg(awg)


def _names(items: list[str]) -> str:
    if not items:
        return "none"
    return ", ".join(items[:SHOWN]) + (
        f" and {len(items) - SHOWN} more" if len(items) > SHOWN else ""
    )


def _cfg_input(project: Project, label: str, file: str, key: str, unit: str = "") -> Input:
    c = project.config.get(file)
    value = c.values.get(key) if c is not None else None
    return Input(
        label,
        value,
        unit,
        f"config/{file}.json: {key}" + ("" if value is not None else " (not set)"),
    )


def _upper(actual: float, limit: float, unit: str, what: str, limit_what: str) -> Check:
    """A check against an upper limit: the value must not exceed it (margin: room left)."""
    ok = not exceeds(actual, limit)
    return Check(
        actual, limit, unit, ok, limit - actual,
        f"{what} is {_g(actual)} {unit} and {limit_what} is {_g(limit)} {unit}: "
        + (f"within the limit, {_g(limit - actual)} {unit} to spare" if ok else f"over the limit by {_g(actual - limit)} {unit}"),
    )  # fmt: skip


def _lower(actual: float, needed: float, unit: str, what: str, needed_what: str) -> Check:
    """A check against a lower limit: the value must be at least the needed one (margin: room)."""
    ok = not exceeds(needed, actual)
    return Check(
        actual, needed, unit, ok, actual - needed,
        f"{what} is {_g(actual)} {unit} and {needed_what} is {_g(needed)} {unit}: "
        + (f"enough, {_g(actual - needed)} {unit} to spare" if ok else f"short by {_g(needed - actual)} {unit}"),
    )  # fmt: skip


def _derivation(
    subject: str, quantity: str, value: float | None, unit: str, equation: str,
    inputs: list[Input], steps: list[Step], check: Check | None, assumptions: tuple[str, ...],
    reference: str, missing: list[str],
) -> Derivation:  # fmt: skip
    return Derivation(
        "rule-limit", subject, quantity, value, unit, equation, tuple(inputs), tuple(steps),
        check, assumptions, reference, tuple(missing),
    )  # fmt: skip


# ---- the rules that compare a number with a limit ------------------------------------------------


def _spare_pins(project: Project, oid: str) -> Derivation | None:
    c = project.connectors.get(oid)
    if c is None:
        return None
    fraction = number(cfg(project, "derating").get("spare_pin_fraction"))
    pins = len(c.pins)
    spare = sum(1 for p in c.pins if p.interface_id is None and not p.signal)
    used = sum(1 for p in c.pins if p.interface_id is not None)
    missing = [] if fraction is not None else ["derating.spare_pin_fraction"]
    inputs = [
        _cfg_input(project, "Required share of spare pins", "derating", "spare_pin_fraction"),
        Input("Pins of the connector", pins, "pins", f"connector {c.id}"),
        Input("Pins with an interface", used, "pins", f"connector {c.id}"),
        Input(
            "Spare pins (no interface, no signal)",
            spare,
            "pins",
            f"connector {c.id} (A-SPARE-PINS)",
        ),
    ]
    steps: list[Step] = []
    check = None
    limit = None
    if fraction is not None:
        limit = fraction * pins
        steps.append(Step("Spare pins required", f"{_g(fraction)} × {pins}", limit, "pins"))
        check = _lower(
            float(spare),
            limit,
            "pins",
            f"the number of spare pins of {c.id}",
            "the number required",
        )
    if not used:
        steps.append(
            text_step(
                "Connector checked",
                "no pin carries an interface, so the rule does not check it",
                "no",
                "",
            )
        )
    return _derivation(
        f"Connector {c.id}", "Spare pins required", limit, "pins",
        "spare pins required = required share × pins of the connector; the connector needs at least that many",
        inputs, steps, check, ("A-SPARE-PINS",),
        "The fraction is not rounded: 20 % of 9 pins is 1.8 pins, so 2 spare pins are needed.", missing,
    )  # fmt: skip


def _connector_voltage(project: Project, oid: str) -> Derivation | None:
    left, _, right = oid.partition(".")
    i, conn = project.interfaces.get(left), project.connectors.get(right)
    if i is None or conn is None:
        return None
    d = cfg(project, "derating")
    f1, f2 = (
        number(d.get("connector_voltage_factor_withstand")),
        number(d.get("connector_voltage_factor_rated")),
    )
    dwv, rated = (
        _rating(project, conn.part_id, "dielectric_withstand_v"),
        _rating(project, conn.part_id, "rated_voltage_v"),
    )
    inputs = [
        Input("Working voltage of the interface", i.voltage_v, "V", f"interface {i.id}: Voltage"),
        _cfg_input(project, "Share of the withstanding voltage", "derating", "connector_voltage_factor_withstand"),
        Input("Dielectric withstanding voltage", dwv, "V", f"connector part {conn.part_id}: ratings.dielectric_withstand_v"),
        _cfg_input(project, "Share of the rated voltage", "derating", "connector_voltage_factor_rated"),
        Input("Rated voltage", rated, "V", f"connector part {conn.part_id}: ratings.rated_voltage_v"),
    ]  # fmt: skip
    steps: list[Step] = []
    if f1 is not None and dwv is not None:
        steps.append(
            Step("Limit from the withstanding voltage", f"{_g(f1)} × {_g(dwv)}", f1 * dwv, "V")
        )
    if f2 is not None and rated is not None:
        steps.append(
            Step("Limit from the rated voltage", f"{_g(f2)} × {_g(rated)}", f2 * rated, "V")
        )
    limit = connector_voltage_limit(project, conn.part_id)
    missing = (
        []
        if limit is not None
        else [f"a rated or withstanding voltage of part {conn.part_id} and its share in derating"]
    )
    if i.voltage_v is None:
        missing.append(f"the voltage of interface {i.id}")
    check = None
    if limit is not None:
        steps.append(Step("Limit used", "the lower of the limits above", limit, "V"))
        if i.voltage_v is not None:
            check = _upper(
                i.voltage_v,
                limit,
                "V",
                f"the working voltage of {i.id}",
                "the limit of the connector",
            )
    return _derivation(
        f"Interface {i.id} at connector {conn.id}", "Connector working voltage limit", limit, "V",
        "limit = the lower of (share of the withstanding voltage × withstanding voltage) and (share of the rated voltage × rated voltage)",
        inputs, steps, check, ("A-CONNECTOR-VOLTAGE",),
        "The shares are the project's own values (a profile of the standard fills them in: see the "
        "setting); the ratings are those of the parts library.", missing,
    )  # fmt: skip


def _wire_voltage(project: Project, oid: str) -> Derivation | None:
    for h in project.harnesses.values():
        for w in h.wires:
            if w.id != oid:
                continue
            i = project.interfaces.get(w.interface_id or "")
            factor = number(cfg(project, "derating").get("wire_voltage_factor"))
            rated = _rating(project, w.part_id or "", "rated_voltage_v")
            inputs = [
                Input("Working voltage of the interface", i.voltage_v if i else None, "V", f"interface {w.interface_id or '(none)'}: Voltage"),
                _cfg_input(project, "Share of the rated voltage", "derating", "wire_voltage_factor"),
                Input("Rated voltage of the wire part", rated, "V", f"wire part {w.part_id or '(none)'}: ratings.rated_voltage_v"),
            ]  # fmt: skip
            missing = []
            if factor is None:
                missing.append("derating.wire_voltage_factor")
            if rated is None:
                missing.append(f"the rated voltage of the part of wire {w.id}")
            if i is None or i.voltage_v is None:
                missing.append(f"the voltage of the interface of wire {w.id}")
            limit = factor * rated if factor is not None and rated is not None else None
            steps: list[Step] = []
            if factor is not None and rated is not None and limit is not None:
                steps.append(Step("Limit", f"{_g(factor)} × {_g(rated)}", limit, "V"))
            check = (
                _upper(
                    i.voltage_v,
                    limit,
                    "V",
                    f"the working voltage of wire {w.id}",
                    "the limit of the wire part",
                )
                if limit is not None and i is not None and i.voltage_v is not None
                else None
            )
            return _derivation(
                f"Wire {w.id}", "Wire working voltage limit", limit, "V",
                "limit = share of the rated voltage × rated voltage of the wire part",
                inputs, steps, check, ("A-WIRE-VOLTAGE",),
                "The share is the project's own value; the rating is that of the parts library.", missing,
            )  # fmt: skip
    return None


def _temperature(project: Project, oid: str) -> Derivation | None:
    d = cfg(project, "derating")
    for what, key in (
        ("connector", "connector_temperature_margin_c"),
        ("wire", "wire_temperature_margin_c"),
    ):
        for obj, pid in _temperature_users(project, what):
            if obj != oid:
                continue
            ambient = number(d.get("max_ambient_temperature_c"))
            margin = number(d.get(key))
            top = _rating(project, pid, "max_temp_c")
            inputs = [
                _cfg_input(project, "Hottest ambient temperature", "derating", "max_ambient_temperature_c", "degC"),
                Input(f"Maximum temperature of the {what} part", top, "degC", f"{what} part {pid}: ratings.max_temp_c"),
                _cfg_input(project, f"Margin below the maximum ({what})", "derating", key, "degC"),
            ]  # fmt: skip
            missing = [
                m for m, v in (
                    ("derating.max_ambient_temperature_c", ambient), (f"derating.{key}", margin),
                    (f"max_temp_c of part {pid}", top),
                ) if v is None
            ]  # fmt: skip
            limit = top - margin if top is not None and margin is not None else None
            steps: list[Step] = []
            if top is not None and margin is not None and limit is not None:
                steps.append(
                    Step(
                        "Highest ambient the part may see",
                        f"{_g(top)} − {_g(margin)}",
                        limit,
                        "degC",
                    )
                )
            check = (
                _upper(
                    ambient,
                    limit,
                    "degC",
                    "the hottest ambient temperature",
                    "the highest the part may see",
                )
                if limit is not None and ambient is not None
                else None
            )
            return _derivation(
                f"{what.capitalize()} {oid} (part {pid})", "Temperature limit of the part", limit, "degC",
                "limit = maximum temperature of the part − margin; the hottest ambient temperature must not exceed it",
                inputs, steps, check, ("A-AMBIENT-ONLY",),
                "No self-heating of the conductor is added: the check list names the thermal analysis "
                "the tool does not do.", missing,
            )  # fmt: skip
    return None


def _mating_cycles(project: Project, oid: str) -> Derivation | None:
    pid = oid.removeprefix("mating-cycles.")
    if pid not in project.parts:
        return None
    limit = number(cfg(project, "derating").get("max_mating_cycles"))
    rated = _rating(project, pid, "mating_cycles")
    missing = [
        m
        for m, v in (("derating.max_mating_cycles", limit), (f"mating_cycles of part {pid}", rated))
        if v is None
    ]
    ok = not (rated is not None and limit is not None and rated < limit)
    check = (
        Check(
            rated, limit, "cycles", ok, rated - limit,
            f"the part is rated for {_g(rated)} cycles and the programme may use {_g(limit)}: "
            + (f"enough, {_g(rated - limit)} to spare" if ok else f"short by {_g(limit - rated)}"),
        )
        if rated is not None and limit is not None
        else None
    )  # fmt: skip
    return _derivation(
        f"Connector part {pid}", "Mating cycles required", limit, "cycles",
        "required cycles = the number the programme may use; the rated mating cycles of the part must be at least that",
        [
            _cfg_input(project, "Cycles the programme may use", "derating", "max_mating_cycles", "cycles"),
            Input("Rated mating cycles", rated, "cycles", f"connector part {pid}: ratings.mating_cycles"),
        ],
        [], check, ("A-MATING-REQUIRED",),
        "A rated number below the required one is a finding, with no tolerance.", missing,
    )  # fmt: skip


def _power_return(project: Project, oid: str) -> Derivation | None:
    head, _, q_id = oid.rpartition("+")
    conn, p_id, hits = None, "", []
    owners = [c for c in project.connectors.values()] + [
        c for h in project.harnesses.values() for c in h.connectors
    ]
    for c in owners:
        if head.startswith(c.id + "."):
            conn, p_id = c, head[len(c.id) + 1 :]
            hits.append(c)
            break
    if conn is None:
        return None
    gap_raw = number(cfg(project, "generation").get("power_return_gap_pins"))
    order = list(conn.pins)
    ids = [p.id for p in order]
    if p_id not in ids or q_id not in ids:
        return None
    k, m = ids.index(p_id), ids.index(q_id)
    if k > m:
        k, m = m, k
    free = sum(1 for x in order[k + 1 : m] if x.interface_id is None and not x.signal)
    missing = [] if gap_raw is not None else ["generation.power_return_gap_pins"]
    ok = gap_raw is None or not free < gap_raw
    check = (
        Check(
            float(free), gap_raw, "contacts", ok, free - gap_raw,
            f"{free} contact(s) between the pins and {_g(gap_raw)} required: "
            + ("enough" if ok else f"{_g(gap_raw - free)} short"),
        )
        if gap_raw is not None
        else None
    )  # fmt: skip
    return _derivation(
        f"Pins {order[k].id} and {order[m].id} of {conn.id}", "Contacts required between power and return",
        gap_raw, "contacts",
        "unassigned contacts between the two pins in the list of pins must be at least the gap required",
        [
            _cfg_input(project, "Contacts required between", "generation", "power_return_gap_pins", "contacts"),
            Input("Signals", f"{order[k].signal} (pin {order[k].id}) and {order[m].signal} (pin {order[m].id})", "", f"connector {conn.id}"),
        ],
        [Step("Unassigned contacts between them", f"pins {order[k].id} to {order[m].id} with no interface and no signal", free, "contacts")],
        check, ("A-RETURN-GAP",),
        "Neighbours are neighbours in the list of pins (ECSS-Q-ST-30-11C 6.11.3 a is cited by the rule).", missing,
    )  # fmt: skip


def _bundle_current(project: Project, oid: str) -> Derivation | None:
    for h in project.harnesses.values():
        for w in h.wires:
            if w.id != oid:
                continue
            d = cfg(project, "derating")
            table = ampacity_table(d.get("ampacity_a_by_awg"))
            n = bundle_size(project, h, w)
            k, k_input, k_ref, k_missing = _bundle(d, n, h.id)
            temp = number(d.get("temperature_derating"))
            i = project.interfaces.get(w.interface_id or "")
            missing = [m for m in (k_missing,) if m]
            if table is None:
                missing.append("derating.ampacity_a_by_awg")
            elif w.gauge_awg not in table:
                missing.append(
                    f"derating.ampacity_a_by_awg has no entry for the gauge of wire {w.id}"
                )
            limit = wire_current_limit(d, w.gauge_awg, n, temperature_optional=True)
            inputs = []
            if table is not None and w.gauge_awg in table:
                inputs.append(
                    Input(
                        f"Base ampacity of {_gauge_name(w.gauge_awg)}",
                        table[w.gauge_awg],
                        "A",
                        f'config/derating.json: ampacity_a_by_awg["{w.gauge_awg}"]',
                    )
                )
            if k_input is not None:
                inputs.append(k_input)
            inputs.append(
                Input(
                    "Temperature factor",
                    temp if temp is not None else 1,
                    "",
                    "config/derating.json: temperature_derating"
                    + ("" if temp is not None else " (not set: counted as 1 by this rule)"),
                )
            )
            inputs.append(
                Input(
                    "Current carried",
                    i.max_current_a if i else None,
                    "A",
                    f"interface {w.interface_id or '(none)'}: Max current",
                )
            )
            steps = []
            if limit is not None and k is not None and table is not None and w.gauge_awg in table:
                steps.append(
                    Step(
                        "Limit of the bundle",
                        f"{_g(table[w.gauge_awg])} × {_g(k)} × {_g(temp if temp is not None else 1)}",
                        limit,
                        "A",
                    )
                )
            check = (
                _upper(
                    i.max_current_a,
                    limit,
                    "A",
                    f"the current of wire {w.id}",
                    f"the limit of a bundle of {n} wires",
                )
                if limit is not None and i is not None and i.max_current_a is not None
                else None
            )
            return _derivation(
                f"Wire {w.id}", "Bundle current limit", limit, "A",
                "limit = base ampacity × bundle factor K of the table × temperature factor (1 when not set)",
                inputs, steps, check, ("A-BUNDLE-ALL", "A-BUNDLE-CURRENT"),
                k_ref + "The rule runs only when the table of bundle factors is set; the factor L of "
                "partly loaded bundles (Table 6-42) is not applied.", missing,
            )  # fmt: skip
    return None


def _pin_shared(project: Project, oid: str) -> Derivation | None:
    h = project.harnesses.get(oid)
    if h is None:
        return None
    shared = {k: v for k, v in wires_on_pins(h).items() if len(v) > 1}
    most = max((len(v) for v in shared.values()), default=1)
    steps = [
        Step(f"Pin {pid} of {cid}", ", ".join(sorted(ids)), len(ids), "wires")
        for (cid, pid), ids in sorted(shared.items())
    ]
    check = Check(
        float(most), 1.0, "wires", most <= 1, 1.0 - most,
        f"the most wires on one pin is {most}, and one is allowed: " + ("no pin is shared" if most <= 1 else f"{len(shared)} pin(s) carry more than one wire"),
    )  # fmt: skip
    return _derivation(
        f"Harness {h.id}", "Wires allowed on one pin", 1.0, "wires",
        "wires on a pin ≤ 1; every pin of the harness is counted with the wires of the harness that end on it",
        [Input("Pins with more than one wire", len(shared), "pins", f"harness {h.id}")],
        steps, check, ("A-PIN-ONE-WIRE",), "One wire to a pin is the limit of the rule; it is not a setting.", [],
    )  # fmt: skip


def _emc_class_split(project: Project, oid: str) -> Derivation | None:
    head, _, rest = oid.partition(".")
    cls, _, units = rest.partition(".")
    first, _, second = units.partition(".")
    if head != "emc-class" or not (cls and first and second):
        return None
    key = (cls, first, second)
    ids = sorted(emc_class_bundles(project).get(key, set()))
    flag = cfg(project, "emc").get("same_class_one_bundle")
    check = Check(
        float(len(ids)), 1.0, "bundles", len(ids) <= 1, 1.0 - len(ids),
        f"interfaces of class {key[0]} between {key[1]} and {key[2]} run in {len(ids)} bundle(s) and one is allowed: "
        + ("one bundle" if len(ids) <= 1 else ", ".join(ids)),
    )  # fmt: skip
    return _derivation(
        f"EMC class {key[0]} between {key[1]} and {key[2]}", "Bundles allowed for one class between two devices", 1.0, "bundles",
        "bundles that carry the class between the two devices ≤ 1",
        [
            Input("Rule is on", None if flag is None else str(flag), "", "config/emc.json: same_class_one_bundle" + ("" if flag is not None else " (not set)")),
            Input("Harnesses that carry it", _names(ids), "", "the design"),
        ],
        [Step("Bundles", ", ".join(ids), len(ids), "bundles")], check, ("A-EMC-ONE-BUNDLE",),
        "One bundle is the limit of the rule (ECSS-E-ST-20-07C 4.2.13.1 b); only switching the rule on is a setting.", [],
    )  # fmt: skip


# ---- what the rules that are yes/no checks saw ---------------------------------------------------


def _find_shield(project: Project, oid: str) -> tuple[Harness, ShieldGroup] | None:
    hid, _, sid = oid.partition(".")
    h = project.harnesses.get(hid)
    s = next((x for x in h.shields if x.id == sid), None) if h else None
    return (h, s) if h is not None and s is not None else None


def _see_shield(project: Project, oid: str) -> list[Input]:
    found = _find_shield(project, oid)
    if found is None:
        return []
    h, s = found
    g = cfg(project, "generation")
    bonding = cfg(project, "emc").get("shield_bonding")
    return [
        Input("Shield group", f"{s.kind} in {h.id}", "", f"harness {h.id}"),
        Input("Ends of the group", f"{s.end_a}/{s.end_b}", "", f"shield group {s.id}"),
        Input(
            "Grounding concept",
            f"{g.get('shield_end_a')}/{g.get('shield_end_b')}",
            "",
            "config/generation.json: shield_end_a, shield_end_b",
        ),
        Input(
            "Bonding required",
            None if bonding is None else str(bonding),
            "",
            "config/emc.json: shield_bonding",
        ),
    ]


def _harness_of(project: Project, oid: str) -> Harness | None:
    return project.harnesses.get(oid.split(".")[0])


def _see_interfaces(project: Project, oid: str) -> list[Input]:
    """The interfaces of a harness (or on a connector) with their chain, category and EMC class."""
    h = _harness_of(project, oid)
    rows: list[str] = []
    if h is not None:
        for i in _carried(project, h):
            t = project.interface_types.get(i.type_id)
            rows.append(
                f"{i.id} ({i.redundancy}, {t.category if t else '?'}, {(t.emc_class if t else None) or 'no EMC class'})"
            )
    else:
        conn = project.connectors.get(oid)
        if conn is not None:
            for iid in sorted({p.interface_id for p in conn.pins if p.interface_id}):
                found = project.interfaces.get(iid)
                ft = project.interface_types.get(found.type_id) if found else None
                if found is not None:
                    rows.append(f"{found.id} ({found.redundancy}, {ft.category if ft else '?'})")
    return [Input("Interfaces it carries", _names(rows), "", "the design")]


def _see_mate(project: Project, oid: str) -> list[Input]:
    for h in project.harnesses.values():
        for c in h.connectors:
            box = project.connectors.get(c.mates_with or "")
            if c.id == oid and box is not None:
                bp = project.parts.get(box.part_id)
                cp = project.parts.get(c.part_id)
                return [
                    Input("Gender (cable end, device)", f"{c.gender}, {box.gender}", "", f"connectors {c.id}, {box.id}"),
                    Input("Part (cable end, device)", f"{c.part_id}, {box.part_id}", "", f"connectors {c.id}, {box.id}"),
                    Input("Mating part named by the library", bp.mates_with if bp else None, "", f"parts library: {box.part_id}"),
                    Input("Pins (cable end, device)", f"{len(c.pins)}, {len(box.pins)}", "", f"connectors {c.id}, {box.id}"),
                    Input("Keying (cable end, device)", f"{c.keying}, {box.keying}", "", f"connectors {c.id}, {box.id}"),
                    Input("Manufacturer (cable end, device)", f"{cp.manufacturer if cp else None}, {bp.manufacturer if bp else None}", "", "parts library"),
                ]  # fmt: skip
    return []


def _see_part(project: Project, oid: str) -> list[Input]:
    pid = oid.removeprefix("wire-spec.")
    part = project.parts.get(pid)
    if part is None:
        return [Input("Part", pid, "", "used, but not in the parts list")]
    return [
        Input("Approval", part.approval, "", f"parts library: {pid}"),
        Input("Marked as unverified example data", "yes" if part.unverified else "no", "", f"parts library: {pid}"),
        Input("Specification", part.specification, "", f"parts library: {pid}"),
    ]  # fmt: skip


def _see_wire(project: Project, oid: str) -> list[Input]:
    for h in project.harnesses.values():
        for w in h.wires:
            if w.id == oid:
                return [
                    Input("Wire", f"{w.from_connector}.{w.from_pin} to {w.to_connector}.{w.to_pin}", "", f"harness {h.id}"),
                    Input("Signal", w.signal, "", f"wire {w.id}"),
                    Input("Interface", w.interface_id, "", f"wire {w.id}"),
                ]  # fmt: skip
    return []


def _see_pin(project: Project, oid: str) -> list[Input]:
    cid, _, pid = oid.rpartition(".")
    for h in project.harnesses.values():
        for c in h.connectors:
            if c.id == cid:
                pin = next((p for p in c.pins if p.id == pid), None)
                on = wires_on_pins(h).get((cid, pid), [])
                return [
                    Input("Signal on the pin", pin.signal if pin else None, "", f"pin {pid} of {cid}"),
                    Input("Wires attached", _names(sorted(on)), "", f"harness {h.id}"),
                ]  # fmt: skip
    return []


def _see_ends(project: Project, oid: str) -> list[Input]:
    """The two ends of an interface: the side of each device and the connector of each end."""
    i = project.interfaces.get(oid)
    if i is None:
        return []
    out: list[Input] = []
    for e in i.endpoints:
        u = project.units.get(e.unit_id)
        out.append(
            Input(
                f"End at {e.unit_id}",
                f"side {u.side if u else '?'}; connector "
                + (e.connector_id or "none")
                + ("; chosen by the tool, not confirmed" if e.auto else ""),
                "",
                f"interface {i.id}",
            )
        )
    return out


def _see_unit(project: Project, oid: str) -> list[Input]:
    ifaces = sorted(
        i.id for i in project.interfaces.values() if any(e.unit_id == oid for e in i.endpoints)
    )
    links = sorted(
        k
        for k, link in project.links.items()
        if any(
            (c := project.connectors.get(cid)) is not None and c.unit_id == oid
            for cid in (link.a_connector, link.b_connector)
        )
    )
    return [
        Input("Interfaces of the device", _names(ifaces), "", f"device {oid}"),
        Input("Connections of the device", _names(links), "", f"device {oid}"),
    ]


# ---- the table: every rule ---------------------------------------------------------------------

YES_NO = "yes-no"
LIMIT = "limit"

INFO: dict[str, RuleInfo] = {
    "duplicate-id": RuleInfo(YES_NO, "how many times each connector, wire and pin ID is used with once"),
    "wire-dangling": RuleInfo(YES_NO, "the connector and pin each wire end names with the connectors and pins the harness has"),
    "model-inconsistent": RuleInfo(YES_NO, "the logical model (devices, interfaces, connectors) with the physical one (harnesses, wires, pins) for the mismatches the integrity check lists"),
    "segment-loop": RuleInfo(YES_NO, "the routing segments of a harness with a tree: a loop gives a wire two possible routes", ("A-PATH-UNIQUE",)),
    "signal-unassigned": RuleInfo(YES_NO, "each signal of an interface type with the pins of the connector at each end that carry it", ("A-PIN-ORDER", "A-PIN-FIRST-FIT")),
    "pin-floating": RuleInfo(YES_NO, "each pin that is named with a signal with the wires attached to it", observe=_see_pin),
    "pin-shared": RuleInfo(LIMIT, "the number of wires on a pin with one", build=_pin_shared),
    "mate-mismatch": RuleInfo(YES_NO, "a cable connector with the device connector it plugs into: gender, mating part, number of pins and keying", observe=_see_mate),
    "direction-conflict": RuleInfo(YES_NO, "the directions of the two signals a wire joins: two outputs or two inputs conflict", observe=_see_wire),
    "current-over-contact": RuleInfo(LIMIT, "the current of an interface with the derated rating of the contacts of the connector at its end", ("A-CONTACT-SHARED",)),
    "current-over-wire": RuleInfo(LIMIT, "the current of an interface with the derated ampacity of the wire's gauge", ("A-AMPACITY-AWG", "A-BUNDLE-ALL", "A-TEMP-FACTOR")),
    "voltage-drop": RuleInfo(LIMIT, "the voltage drop over a wire at the current of its interface with the largest drop allowed", ("A-DC-SOLID", "A-ROUND-TRIP")),
    "spare-pins-low": RuleInfo(LIMIT, "the number of spare pins of a connector with the required share of its pins", ("A-SPARE-PINS",), build=_spare_pins),
    "shield-unterminated": RuleInfo(YES_NO, "the two ends of each shield group with 'floating': both floating is not terminated", ("A-SHIELD-ENDS",), observe=_see_shield),
    "shield-wrong-end": RuleInfo(YES_NO, "the ends of each shield group with the grounding concept of the project", ("A-SHIELD-ENDS",), observe=_see_shield),
    "chains-mixed": RuleInfo(YES_NO, "the redundancy (nominal or redundant) of the interfaces in each harness and on each connector", ("A-SEGMENT-MODE",), observe=_see_interfaces),
    "pyro-mixed": RuleInfo(YES_NO, "the categories of the interfaces in each harness and on each connector with 'pyro'", ("A-SEGMENT-MODE",), observe=_see_interfaces),
    "category-mixed": RuleInfo(YES_NO, "the interface categories in a harness with the pairs the project keeps apart", ("A-SEGMENT-MODE",), observe=_see_interfaces),
    "emc-mixed": RuleInfo(YES_NO, "the EMC classes in a harness with the pairs of classes that must stay apart", ("A-SEGMENT-MODE",), observe=_see_interfaces),
    "connector-lookalike": RuleInfo(YES_NO, "the connectors of one device that are in use, by part, keying, gender and number of pins: identical ones can be mixed up", ("A-CONNECTOR-CHOICE",)),
    "part-unapproved": RuleInfo(YES_NO, "the approval of each part in use with 'approved', and whether it is marked as unverified example data", observe=_see_part),
    "connector-voltage": RuleInfo(LIMIT, "the working voltage of an interface with the lower of the shares of the withstanding and the rated voltage of the connector part", ("A-CONNECTOR-VOLTAGE",), build=_connector_voltage),
    "wire-voltage": RuleInfo(LIMIT, "the working voltage of an interface with the share of the rated voltage of the wire part", build=_wire_voltage),
    "temperature-margin": RuleInfo(LIMIT, "the hottest ambient temperature with the maximum temperature of the part less the margin", ("A-AMBIENT-ONLY",), build=_temperature),
    "mating-cycles": RuleInfo(LIMIT, "the rated mating cycles of a connector part with the cycles the programme may use", ("A-MATING-REQUIRED",), build=_mating_cycles),
    "connector-manufacturer": RuleInfo(YES_NO, "the manufacturer of a cable connector's part with that of the device connector it mates with", observe=_see_mate),
    "wire-specification": RuleInfo(YES_NO, "each approved wire part with its specification field: an empty field is a finding", observe=_see_part),
    "shield-bonding": RuleInfo(YES_NO, "the ends of each shield group with 'backshell_360' at both ends, when the project requires bonding", ("A-SHIELD-ENDS",), observe=_see_shield),
    "shield-parts": RuleInfo(YES_NO, "the conductive finish of the connectors and the insulating sheath of the shielded wires with 'none' (rating 0)", ("A-SHIELD-GROUPS",)),
    "emc-class-split": RuleInfo(LIMIT, "the number of harnesses that carry one EMC class between two devices with one", build=_emc_class_split),
    "power-return-adjacent": RuleInfo(LIMIT, "the unassigned contacts between a power and a return pin with the contacts required", ("A-RETURN-GAP", "A-PIN-ORDER"), build=_power_return),
    "bundle-current": RuleInfo(LIMIT, "the current of an interface with the derated ampacity of the wire's gauge in a bundle of its size", ("A-BUNDLE-ALL", "A-BUNDLE-CURRENT"), build=_bundle_current),
    "link-unpaired": RuleInfo(YES_NO, "each pin of a connection that has a signal with the pairs of that connection"),
    "link-direction": RuleInfo(YES_NO, "the directions of the two pins of each pair of a connection"),
    "link-signal-mismatch": RuleInfo(YES_NO, "the two signal names of each pair of a connection"),
    "link-power-return": RuleInfo(YES_NO, "each power pair of a connection with a return pair on the same connection"),
    "config-invalid": RuleInfo(YES_NO, "each value in config/*.json with the range it must lie in (the checks of configcheck)"),
    "released-modified": RuleInfo(YES_NO, "each released harness with the baseline it was released as (its content hash)"),
    "unchecked-config": RuleInfo(YES_NO, "the values and ratings each rule needs with what the project has set; it lists what could not be checked"),
    "verify-mismatch": RuleInfo(YES_NO, "the wires and tables with what the interfaces require, worked out again by the independent check (core/verify)"),
    "cross-strap": RuleInfo(YES_NO, "the side (nominal or redundant) of the two devices of an interface", observe=_see_ends),
    "no-connector": RuleInfo(YES_NO, "each end of an interface with a chosen connector", ("A-CONNECTOR-CHOICE",), observe=_see_ends),
    "unconfirmed": RuleInfo(YES_NO, "the connector of each end of an interface with 'chosen by a person' (a tool choice is not confirmed)", ("A-CONNECTOR-CHOICE",), observe=_see_ends),
    "isolated": RuleInfo(YES_NO, "each device with the interfaces and connections that join it to another", observe=_see_unit),
}  # fmt: skip


# every rule in the order of the report: the registry, the independent verification, the logical rules
ALL_RULE_IDS: tuple[str, ...] = (*(r.id for r in RULES), "verify-mismatch", *LOGICAL_RULES)


def rule_info(rule_id: str) -> RuleInfo | None:
    return INFO.get(rule_id)


def compares(rule_id: str) -> str:
    """The sentence for a rule that is a yes/no check: what it compares."""
    info = INFO[rule_id]
    return f"this rule is a yes/no check: it compares {info.compares}"


def _rule_text(rule_id: str) -> tuple[str, str, tuple[str, ...], str]:
    """(why, how, requirement IDs, topic) of a rule of the registry, or of the other rules."""
    for r in RULES:
        if r.id == rule_id:
            return r.why, r.how, r.sources, r.topic
    return "", "", (), rule_id


def _statements(
    project: Project, rule_id: str, object_id: str, findings: list[Finding] | None
) -> list[str]:
    found = findings if findings is not None else [*logical_findings(project), *run_drc(project)]
    return [f.title for f in found if f.rule == rule_id and f.object_id == object_id]


def yes_no_derivation(
    project: Project, rule_id: str, object_id: str, findings: list[Finding] | None = None
) -> Derivation:
    info = INFO[rule_id]
    why, how, sources, topic = _rule_text(rule_id)
    statements = _statements(project, rule_id, object_id, findings)
    inputs: list[Input] = [
        Input(
            "Statement of the finding" if k == 0 else f"Statement of the finding ({k + 1})",
            text,
            "",
            f"rule {rule_id}, object {object_id}",
        )
        for k, text in enumerate(statements)
    ]
    for file, key in READS.get(rule_id, ()):
        s = settings.setting(file, key)
        e = settings.effective(project, file, key)
        inputs.append(
            Input(
                s.label if s else key,
                None if e.value is None else settings.display(e.value),
                s.unit if s else "",
                f"config/{file}.json: {key}"
                + ("" if e.value is not None else " (not set: the rule is silent until it is)"),
            )
        )
    if info.observe is not None:
        inputs += info.observe(project, object_id)
    reference = " ".join(
        t
        for t in (
            f"Why it matters: {why}" if why else "",
            f"To fix it: {how}" if how else "",
            f"Requirement IDs: {', '.join(sources)}." if sources else "",
        )
        if t
    )
    return Derivation(
        "rule-check",
        f"Rule {rule_id} for {object_id}",
        topic,
        None,
        "",
        compares(rule_id),
        tuple(inputs),
        (),
        None,
        info.assumptions,
        reference,
        text=statements[0] if statements else "no finding for this object today",
    )


def explain_rule(
    project: Project, rule_id: str, object_id: str, findings: list[Finding] | None = None
) -> list[Derivation]:
    """What `explain_finding` answers for a rule other than the three explained first: the limit
    of a rule of the form *limit*, or the statement of a *yes/no* rule. Empty for a rule that does
    not exist, or for a limit rule whose object is gone."""
    info = INFO.get(rule_id)
    if info is None:
        if project.extensions is not None:  # S8: a rule of an extension explains itself
            from harness_design_studio.core.extensions.manager import explain, is_extension_rule

            if is_extension_rule(project, rule_id):
                return explain(project, rule_id, object_id, findings)
        return []
    if info.form == LIMIT:
        if info.build is None:
            return []  # (the three first rules are answered by `explain_finding` itself)
        d = info.build(project, object_id)
        return [d] if d is not None else []
    return [yes_no_derivation(project, rule_id, object_id, findings)]
