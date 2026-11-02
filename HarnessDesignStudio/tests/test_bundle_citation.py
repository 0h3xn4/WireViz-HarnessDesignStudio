"""The note on a wire sizing names "Table 6-41" only when the table of bundle factors is the one of the
ECSS profile; a table of one's own is named as what it is (D-191; before, the standard was cited for
any table). The factor and the gauge do not change."""

from harness_design_studio.core.generate.sizing import Sizing, size_wire
from harness_design_studio.core.standard_profiles import BUNDLE_K

AMPACITY = {"20": 3.0, "22": 2.2, "24": 1.6, "26": 1.1}


def sized(by_count: dict[str, float]) -> Sizing:
    derating: dict[str, object] = {
        "ampacity_a_by_awg": AMPACITY,
        "bundle_derating": None,
        "temperature_derating": 0.9,
        "max_voltage_drop_v": 1.0,
        "bundle_factor_by_count": by_count,
    }
    generation: dict[str, object] = {"conductor_resistivity_ohm_m": 1.7e-8}
    return size_wire(
        derating, generation, current_a=0.5, length_m=2.0, path_conductors=2, bundle_wires=10
    )


def test_the_standard_table_is_cited_as_the_standard() -> None:
    s = sized(dict(BUNDLE_K))
    assert any("(Table 6-41)" in n for n in s.notes)


def test_a_table_of_ones_own_is_not_cited_as_the_standard() -> None:
    s = sized({"1": 1, "10": 0.7, "50": 0.5})
    assert not any("Table 6-41" in n for n in s.notes)
    assert any("bundle_factor_by_count" in n and "0.7" in n for n in s.notes)


def test_the_source_named_does_not_change_the_number() -> None:
    a, b = sized(dict(BUNDLE_K)), sized({"1": 1, "10": BUNDLE_K["10"], "50": 0.5})
    assert a.awg is not None and a.awg == b.awg  # K for 10 wires is the same in both tables
    assert not a.pending and not b.pending and a.error is None and b.error is None
