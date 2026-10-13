"""REQ-NUM-01: Numerical accuracy of the sizing arithmetic (ECSS-Q-ST-80C 7.1.7, gap G-13).

The AWG size is defined by two exact points, 36 AWG = 0.005 in and 4/0 = 0.46 in,
with 39 geometric steps between them. The tests check those points, the ratio, and compare the
float voltage-drop and ampacity arithmetic with exact rational arithmetic.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from harness_design_studio.core.generate.sizing import size_wire
from harness_design_studio.core.units import awg_to_area_mm2, awg_to_diameter_mm

INCH_MM = 25.4  # exact by definition


def test_the_two_defining_points_of_awg() -> None:
    assert awg_to_diameter_mm(36) == pytest.approx(0.005 * INCH_MM, rel=1e-12)
    # the supported range starts at AWG 0; three more sizes up (4/0) reach 0.46 in
    assert awg_to_diameter_mm(0) * 92 ** (3 / 39) == pytest.approx(0.46 * INCH_MM, rel=1e-12)


def test_every_six_sizes_halve_the_diameter_within_one_percent() -> None:
    # the rule of thumb: diameter ratio per 6 sizes is 92^(6/39) = 2.0050
    for n in range(0, 34):
        assert awg_to_diameter_mm(n) / awg_to_diameter_mm(n + 6) == pytest.approx(
            92 ** (6 / 39), rel=1e-12
        )


def test_area_matches_exact_circle_formula() -> None:
    for n in (0, 10, 20, 30, 40):
        d = awg_to_diameter_mm(n)
        assert awg_to_area_mm2(n) == pytest.approx(math.pi * d * d / 4, rel=1e-15)


def test_voltage_drop_matches_exact_arithmetic() -> None:
    rho, length, current = 1.7e-8, 12.5, 3.0  # test inputs, not engineering data
    table = {str(n): 100.0 for n in range(10, 31)}
    der = {
        "ampacity_a_by_awg": table,
        "bundle_derating": 1.0,
        "temperature_derating": 1.0,
        "max_voltage_drop_v": 0.25,
    }
    s = size_wire(
        der,
        {"conductor_resistivity_ohm_m": rho},
        current_a=current,
        length_m=length,
        path_conductors=2,
    )
    assert s.awg is not None
    area_m2 = Fraction(awg_to_area_mm2(s.awg)) / 10**6
    exact = Fraction(current) * Fraction(rho) * Fraction(length) / area_m2 * 2
    assert float(exact) <= 0.25
    smaller = Fraction(awg_to_area_mm2(s.awg + 1)) / 10**6
    assert float(Fraction(current) * Fraction(rho) * Fraction(length) / smaller * 2) > 0.25
    note = next(x for x in s.notes if x.startswith("voltage drop"))
    printed = float(note.split("gives ")[1].split(" V")[0])
    assert printed == pytest.approx(float(exact), rel=1e-5)  # note prints 6 significant digits


def test_derating_arithmetic_is_exact_to_float_precision() -> None:
    der = {
        "ampacity_a_by_awg": {"20": 5.0},
        "bundle_derating": 0.6,
        "temperature_derating": 0.9,
    }
    s = size_wire(der, {}, current_a=2.7, length_m=None, path_conductors=1)
    assert "ampacity: AWG 20 carries 2.7 A derated (factor 0.54) for 2.7 A" in s.notes
    # 5.0 * 0.6 * 0.9 = 2.7 within rounding: the limit case passes, the next current fails
    assert size_wire(der, {}, current_a=2.7000001, length_m=None, path_conductors=1).error
