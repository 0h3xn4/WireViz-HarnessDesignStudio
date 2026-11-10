# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""SI helpers. Wire sizes are AWG with mm² alongside (SPEC hard constraint 7)."""

import math
import re

AWG_MIN, AWG_MAX = 0, 40


def awg_to_diameter_mm(awg: int) -> float:
    """Conductor diameter from the AWG definition: d = 0.127 mm * 92^((36 - n) / 39)."""
    if not AWG_MIN <= awg <= AWG_MAX:
        raise ValueError(f"AWG size {awg} is outside the supported range {AWG_MIN}..{AWG_MAX}")
    return float(0.127 * 92 ** ((36 - awg) / 39))


def awg_to_area_mm2(awg: int) -> float:
    """Conductor cross-section in mm² (circular conductor of the AWG diameter)."""
    return math.pi / 4 * awg_to_diameter_mm(awg) ** 2


def area_text(awg: int) -> str:
    """The cross-section for a person: 3 significant digits (0.00501 for AWG 40, 0.205, 1.31, 21.2),
    so the finest gauges do not read as 0.005. The data files hold the number in full."""
    return f"{awg_to_area_mm2(awg):.3g}"


def format_awg(awg: int) -> str:
    return f"AWG {awg} ({area_text(awg)} mm²)"


def format_gauge(awg: int) -> str:
    """A gauge as a person reads it with its cross-section: `24 AWG (0.205 mm²)` (D2, D-193).

    This is for the screen and for explanations. The files the tool writes for the project (the
    drawings, the lists, the workbook, the design rule report) keep the plain gauge, so that
    their bytes do not change; the open-data files carry the cross-section as a number."""
    return f"{awg} AWG ({area_text(awg)} mm²)" if AWG_MIN <= awg <= AWG_MAX else f"{awg} AWG"


def gauge_short(awg: int) -> str:
    """The gauge with its cross-section in the short form of a table cell: `24 (0.205 mm²)`."""
    return f"{awg} ({area_text(awg)} mm²)" if AWG_MIN <= awg <= AWG_MAX else str(awg)


_AWG_IN_TEXT = re.compile(r"\bAWG (\d{1,2})\b(?! \()")
# `2 AWG to spare` and `over the limit by 2 AWG` are a difference of two gauge numbers, not a
# gauge: no cross-section follows them
_AWG_AFTER = re.compile(r"(?<!\bby )\b(\d{1,2}) AWG\b(?! \()(?! to spare)")


def with_area(text: str) -> str:
    """A sentence for the screen with the cross-section added after every gauge it names, in
    either of the two ways the tool writes one (`AWG 24` or `24 AWG`). A gauge that already has its
    cross-section, or is outside 0 to 40, is left as it is. Never used for a file."""

    def put(m: re.Match[str]) -> str:
        n = int(m.group(1))
        if not AWG_MIN <= n <= AWG_MAX:
            return m.group(0)
        return f"{m.group(0)} ({area_text(n)} mm²)"

    return _AWG_AFTER.sub(put, _AWG_IN_TEXT.sub(put, text))
