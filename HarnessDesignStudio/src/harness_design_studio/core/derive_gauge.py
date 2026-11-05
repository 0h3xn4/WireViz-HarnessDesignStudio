"""How the gauge of a wire was chosen: the derivation kind `gauge` (audit R1, owner decision 14).

The other derivations of a wire explain a number the gauge leads to (the derated limit, the voltage
drop). This one explains the choice of the gauge itself: the gauges the search tried, the current
each may carry after derating, the voltage drop of each, which is the first that passes, and the
settings and assumptions it rests on.

It runs no search of its own. It calls `derive.replay_sizing`, which calls `sizing.size_wire` with
the arguments generation gives it, and prints the `SizingTrace` that function returns, so the
explanation cannot disagree with the gauge the generator chose (a test compares them on all the
packaged examples). A gauge that a person set (an override with its reason, a lock, a wire drawn by
hand) was not chosen by the search, and the derivation says so.

It is computed on demand: `explain OBJECT` and `explain --json` print it for a wire, and
`explain --all` (`derivations.json`) does not contain it, so that file is unchanged.
"""

from harness_design_studio.core.derive import (
    Check,
    Derivation,
    Input,
    Step,
    _bundle,
    _g,
    generated_alternative,
    replay_sizing,
    resistivity_source,
    text_step,
)
from harness_design_studio.core.drc.base import cfg
from harness_design_studio.core.generate import bundle
from harness_design_studio.core.generate.bundle import bundle_size
from harness_design_studio.core.generate.sizing import exceeds, wire_current_limit
from harness_design_studio.core.model import Harness, Project, Wire
from harness_design_studio.core.units import awg_to_area_mm2

KIND = "gauge"
EQUATION = (
    "gauge = the smallest conductor (the highest AWG number) whose derated limit is not below the "
    "current; then larger, one listed size at a time, until the voltage drop is within its limit"
)
ASSUMPTIONS = ("A-AMPACITY-AWG", "A-BUNDLE-ALL", "A-TEMP-FACTOR", "A-DC-SOLID", "A-ROUND-TRIP")


def _by_hand(project: Project, h: Harness, w: Wire) -> Derivation | None:
    """The derivation of a gauge that nobody searched for: set with a reason, locked, or drawn by
    hand. None for a wire whose gauge is the search's."""
    subject = f"Wire {w.id}"
    if "gauge_awg" in w.overrides:
        how = f"set by the engineer, reason: {w.overrides['gauge_awg']}"
        source = f"wire {w.id}: overridden by the engineer, reason: {w.overrides['gauge_awg']}"
        ref = (
            "Generation keeps this gauge and does not search; the rules `current-over-wire` and "
            "`voltage-drop` still check it. `explain` on the wire shows the override and what the "
            "set gauge does to the checks."
        )
    elif w.manual:
        how = "the wire was drawn by a person, so generation never sizes it"
        source = f"wire {w.id}: drawn by hand"
        ref = "Generation keeps a wire drawn by hand as it is; the design rules still check it."
    elif w.locked and not w.overrides:  # (with overrides of other values, generation sizes it)
        how = "the wire is locked (its gauge was entered by hand), so generation keeps it"
        source = f"wire {w.id}: locked, no reason recorded"
        ref = (
            "A locked wire with no override recorded has no reason with it; to record one, use "
            "`override`. The design rules still check the gauge."
        )
    else:
        return None
    alt, why = generated_alternative(project, h, w, "gauge_awg")
    inputs = [
        Input("Gauge on the wire", w.gauge_awg, "AWG", source),
        Input(
            "Gauge the search gives now",
            alt if alt is not None else "not decided",
            "AWG" if isinstance(alt, int) else "",
            why,
        ),
    ]
    return Derivation(
        KIND, subject, "Gauge", w.gauge_awg, "AWG",
        "the gauge is not chosen by the search: a person set it and generation keeps it",
        tuple(inputs), (text_step("How the gauge was decided", "", how),), None, (), ref,
    )  # fmt: skip


def gauge_derivation(project: Project, h: Harness, w: Wire) -> Derivation:
    """The choice of the gauge of the wire: every candidate the search tried and why the first that
    passed was taken; or, for a gauge a person set, that it was not chosen."""
    by_hand = _by_hand(project, h, w)
    if by_hand is not None:
        return by_hand
    subject = f"Wire {w.id}"
    interface = project.interfaces.get(w.interface_id or "")
    itype = project.interface_types.get(interface.type_id) if interface else None
    sizing = replay_sizing(project, h, w)
    trace = sizing.trace
    if trace is None:  # the search could not start: no current, or a value of the ampacity is open
        alt, why = generated_alternative(project, h, w, "gauge_awg")
        if isinstance(alt, int):  # no current to size for: the default gauge of the configuration
            return Derivation(
                KIND, subject, "Gauge", alt, "AWG",
                "no current to size for: the default gauge of the interface type or the "
                "configuration",
                (Input("Default gauge", alt, "AWG", why),),
                (text_step("How the gauge was decided", "", "by default, not by the search"),),
                None, (), "The interface has no Max current, so there is nothing to size the "
                "gauge for. Set the current to have the search choose it.",
            )  # fmt: skip
        return Derivation(
            KIND, subject, "Gauge", None, "AWG", EQUATION, assumptions=ASSUMPTIONS,
            missing=tuple(sizing.pending),
        )  # fmt: skip
    derating = cfg(project, "derating")
    temp = trace.temperature
    k = trace.bundle_k
    factor = k * temp
    wires = bundle_size(project, h, w)
    _k, k_input, k_ref, _missing = _bundle(derating, wires, h.id, bundle.basis(project))
    inputs = [
        Input(
            "Current carried", trace.current_a, "A",
            f"interface {interface.id}: Max current" if interface else "the interface",
        ),
        k_input or Input("Bundle factor K", k, "", "config/derating.json"),
        Input("Temperature factor", temp, "", "config/derating.json: temperature_derating"),
    ]  # fmt: skip
    steps = [Step("Combined factor", f"K × temperature = {_g(k)} × {_g(temp)}", factor, "")]
    for a in trace.ampacity:
        steps.append(
            Step(
                f"Try AWG {a.awg} for {_g(trace.current_a)} A: "
                + ("carries it" if a.carries else "too small"),
                f"limit = base ampacity × combined factor = {_g(a.base_a)} × {_g(factor)}",
                a.limit_a,
                "A",
            )  # fmt: skip
        )
    if sizing.error and not trace.ampacity[-1].carries:
        return Derivation(
            KIND, subject, "Gauge", None, "AWG", EQUATION, tuple(inputs), tuple(steps), None,
            ASSUMPTIONS, k_ref + "No listed gauge carries the current: " + sizing.error + ".",
            text="none: " + sizing.error,
        )  # fmt: skip
    chosen_amp = trace.ampacity[-1]
    steps.append(
        text_step(
            "Smallest gauge that carries the current",
            "the first one tried above that carries it",
            f"AWG {chosen_amp.awg}",
        )
    )
    awg = chosen_amp.awg
    pending = tuple(sizing.pending)
    max_drop, rho, length = trace.max_drop_v, trace.resistivity, trace.length_m
    if trace.drops and max_drop is not None and rho is not None and length is not None:
        n = trace.conductors
        inputs += [
            Input("Resistivity ρ", rho, "Ω·m", resistivity_source(project)),
            Input(
                "Length L", length, "m",
                f"the length of wire {w.id} itself" if w.length_m is not None
                else f"the routing segments of harness {h.id} between its connectors",
            ),
            Input(
                "Conductors counted n", n, "",
                f"category '{itype.category if itype else ''}' of its interface type: "
                "config/model.json: return_path_categories (A-ROUND-TRIP)",
            ),
            Input("Voltage drop limit", max_drop, "V", "config/derating.json: max_voltage_drop_v"),
        ]  # fmt: skip
        for dr in trace.drops:
            area = awg_to_area_mm2(dr.awg)
            steps.append(
                Step(
                    f"Try AWG {dr.awg} for the drop, limit {_g(max_drop)} V: "
                    + ("within the limit" if dr.within else "over the limit"),
                    f"I × ρ × L / A × n = {_g(trace.current_a)} × {_g(rho)} × {_g(length)} / "
                    f"{_g(area * 1e-6)} × {n}",
                    dr.drop_v,
                    "V",
                )  # fmt: skip
            )
        if trace.drops[-1].within:
            awg = trace.drops[-1].awg
    elif pending:
        steps.append(
            text_step(
                "Voltage drop not tried",
                "waiting for " + "; ".join(pending),
                f"provisional AWG {awg} from the ampacity alone",
            )
        )
    if sizing.error and trace.drops and not trace.drops[-1].within:
        return Derivation(
            KIND, subject, "Gauge", None, "AWG", EQUATION, tuple(inputs), tuple(steps), None,
            ASSUMPTIONS, k_ref + "No listed gauge keeps the voltage drop within its limit: "
            + sizing.error + ".",
            text="none: " + sizing.error,
        )  # fmt: skip
    value = sizing.awg
    limit = wire_current_limit(derating, awg, wires)  # the one limit the rules use
    check = None
    if limit is not None:
        ok = not exceeds(trace.current_a, limit)
        spare = limit - trace.current_a
        verdict = (
            f"within the limit, {_g(spare)} A to spare"
            if ok
            else f"over the limit by {_g(-spare)} A"
        )
        check = Check(
            trace.current_a, limit, "A", ok, limit - trace.current_a,
            f"AWG {awg} carries {_g(limit)} A after derating and the wire carries "
            f"{_g(trace.current_a)} A: "
            + verdict,
        )  # fmt: skip
    if value is not None:
        steps.append(
            text_step("Gauge chosen", "the first candidate that passes both tests", f"AWG {value}")
        )
    note = ""
    if value is not None and w.gauge_awg is not None:
        note = (
            f"The wire has AWG {w.gauge_awg}, the gauge of this search. "
            if w.gauge_awg == value
            else f"The wire has AWG {w.gauge_awg}, but the search on the design and settings as "
            f"they are now gives AWG {value}: generate again to follow the design. "
        )
    return Derivation(
        KIND, subject, "Gauge", value, "AWG", EQUATION, tuple(inputs), tuple(steps), check,
        ASSUMPTIONS,
        note + k_ref + "Base ampacity table, temperature factor, resistivity and drop limit: the "
        "project's own values (config/derating.json, config/generation.json); the project records "
        "no source for them. The search is the one generation runs "
        "(core/generate/sizing.py: size_wire).",
        pending,
    )  # fmt: skip


def wire_derivations(project: Project, h: Harness, w: Wire) -> list[Derivation]:
    """The choice of the gauge of a wire, for `explain` (not part of `explain --all`)."""
    return [gauge_derivation(project, h, w)]
