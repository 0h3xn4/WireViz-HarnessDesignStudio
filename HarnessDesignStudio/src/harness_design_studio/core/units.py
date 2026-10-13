"""SI helpers. Wire sizes are AWG with mm² alongside (SPEC hard constraint 7)."""

import math

AWG_MIN, AWG_MAX = 0, 40


def awg_to_diameter_mm(awg: int) -> float:
    """Conductor diameter from the AWG definition: d = 0.127 mm * 92^((36 - n) / 39)."""
    if not AWG_MIN <= awg <= AWG_MAX:
        raise ValueError(f"AWG size {awg} is outside the supported range {AWG_MIN}..{AWG_MAX}")
    return float(0.127 * 92 ** ((36 - awg) / 39))


def awg_to_area_mm2(awg: int) -> float:
    """Conductor cross-section in mm² (circular conductor of the AWG diameter)."""
    return math.pi / 4 * awg_to_diameter_mm(awg) ** 2


def format_awg(awg: int) -> str:
    return f"AWG {awg} ({awg_to_area_mm2(awg):.3f} mm²)"
