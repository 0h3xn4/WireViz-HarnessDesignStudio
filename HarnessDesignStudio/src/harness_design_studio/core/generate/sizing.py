"""Wire sizing from current, length and derating. Every number comes from configuration.

If a needed value is a placeholder (null), the gauge stays undecided and the result lists exactly
which values are missing. The tool never guesses an engineering value.
"""

import math
from dataclasses import dataclass, field

from harness_design_studio.core.units import awg_to_area_mm2


@dataclass
class Sizing:
    awg: int | None = None
    notes: list[str] = field(default_factory=list)  # how the decision was made
    pending: list[str] = field(default_factory=list)  # configuration values still missing
    error: str | None = None


REL_TOL = 1e-9  # a value within a billionth of its limit is at the limit, not over it


def exceeds(value: float, limit: float) -> bool:
    """True if `value` is above `limit` by more than float rounding. The one comparison that
    sizing and the design rules share, so both agree at the exact limit."""
    if value <= limit or math.isnan(value):
        return False
    return math.isinf(value) or value - limit > REL_TOL * max(abs(value), abs(limit))


def derated_limit(base: float, bundle: float, temperature: float) -> float:
    """`base` after the bundle and temperature factors; one order of operations for everybody."""
    return base * (bundle * temperature)


def voltage_drop_v(
    current_a: float, resistivity_ohm_m: float, length_m: float, awg: int, conductors: int
) -> float:
    return current_a * resistivity_ohm_m * length_m / (awg_to_area_mm2(awg) * 1e-6) * conductors


def _num(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def ampacity_table(raw: object) -> dict[int, float] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    out: dict[int, float] = {}
    for k, v in raw.items():
        try:
            gauge = int(k)
            out[gauge] = float(v)
        except TypeError, ValueError:
            return None
        if not 0 <= gauge <= 40:  # outside the supported gauges: no table rather than a crash
            return None
    return out


def bundle_k(raw: object, count: int) -> float | None:
    """K of ECSS-Q-ST-30-11C Table 6-41 for `count` wires: the next listed count, never a better
    factor than the table gives; None if there is no table or the bundle is larger than it lists."""
    if not isinstance(raw, dict) or not raw:
        return None
    try:
        points = sorted((int(k), float(v)) for k, v in raw.items())
    except TypeError, ValueError:
        return None
    for n, k in points:
        if count <= n:
            return k
    return None


def wire_current_limit(
    derating: dict[str, object],
    awg: int | None,
    bundle_wires: int | None,
    *,
    temperature_optional: bool = False,
) -> float | None:
    """The current a wire of this gauge may carry after derating: the ampacity table times the
    bundle factor times the temperature factor. When the table of bundle factors is set it
    replaces the single factor (as in `size_wire`). None while a value is missing, or the bundle is
    larger than the table lists. `temperature_optional` takes an unset temperature factor as 1.

    The one limit of the rules `current-over-wire` and `bundle-current`, so they cannot disagree."""
    table = ampacity_table(derating.get("ampacity_a_by_awg"))
    bundle = _num(derating.get("bundle_derating"))
    temp = _num(derating.get("temperature_derating"))
    by_count = derating.get("bundle_factor_by_count")
    if isinstance(by_count, dict) and by_count and bundle_wires is not None:
        bundle = bundle_k(by_count, bundle_wires)
    if temp is None and temperature_optional:
        temp = 1.0
    if table is None or bundle is None or temp is None or awg is None or awg not in table:
        return None
    return derated_limit(table[awg], bundle, temp)


def size_wire(
    derating: dict[str, object],
    generation: dict[str, object],
    *,
    current_a: float | None,
    length_m: float | None,
    path_conductors: int,
    bundle_wires: int | None = None,
) -> Sizing:
    """Smallest conductor whose derated ampacity and voltage drop satisfy the project rules."""
    s = Sizing()
    if current_a is None:
        s.pending.append("interface current (set Max current on the interface)")
        return s
    table = ampacity_table(derating.get("ampacity_a_by_awg"))
    bundle = _num(derating.get("bundle_derating"))
    temp = _num(derating.get("temperature_derating"))
    by_count = derating.get("bundle_factor_by_count")
    if isinstance(by_count, dict) and by_count and bundle_wires is not None:
        bundle = bundle_k(by_count, bundle_wires)  # the table replaces the single factor
        if bundle is None:
            s.pending.append(f"derating.bundle_factor_by_count (no entry for {bundle_wires} wires)")
        else:
            s.notes.append(f"bundle factor K {bundle:g} for {bundle_wires} wires (Table 6-41)")
    if table is None:
        s.pending.append("derating.ampacity_a_by_awg")
    if bundle is None:
        s.pending.append("derating.bundle_derating")
    if temp is None:
        s.pending.append("derating.temperature_derating")
    if s.pending or table is None or bundle is None or temp is None:
        return s
    factor = bundle * temp
    candidates = sorted(table, reverse=True)  # smallest conductor first (highest AWG number)
    ok = [
        awg for awg in candidates if not exceeds(current_a, derated_limit(table[awg], bundle, temp))
    ]
    if not ok:
        s.error = f"no listed gauge carries {current_a:g} A after derating (factor {factor:g})"
        return s
    awg = ok[0]
    s.notes.append(
        f"ampacity: AWG {awg} carries {derated_limit(table[awg], bundle, temp):g} A derated (factor {factor:g}) for {current_a:g} A"
    )
    max_drop = _num(derating.get("max_voltage_drop_v"))
    rho = _num(generation.get("conductor_resistivity_ohm_m"))
    if max_drop is None:
        s.pending.append("derating.max_voltage_drop_v")
    if rho is None:
        s.pending.append("generation.conductor_resistivity_ohm_m")
    if length_m is None:
        s.pending.append("wire length (enter routing segment lengths)")
    if max_drop is not None and rho is not None and length_m is not None:
        for cand in sorted((a for a in table if a <= awg), reverse=True):
            drop = voltage_drop_v(current_a, rho, length_m, cand, path_conductors)
            if not exceeds(drop, max_drop) and math.isfinite(drop):
                awg = cand
                s.notes.append(
                    f"voltage drop: AWG {cand} gives {drop:g} V over {path_conductors} conductor(s), limit {max_drop:g} V"
                )
                break
        else:
            s.error = (
                f"no listed gauge keeps the voltage drop under {max_drop:g} V over {length_m:g} m"
            )
            return s
    s.awg = awg if not s.pending else None  # a decision with open inputs is not final
    if s.pending:
        s.notes.append(f"provisional AWG {awg} from ampacity only; pending: {', '.join(s.pending)}")
    return s
