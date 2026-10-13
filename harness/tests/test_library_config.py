"""REQ-LIB-01 / REQ-CFG-01: starter library and configuration never invent engineering numbers."""

from harness_design_studio.core.model import PART_CATEGORIES
from harness_design_studio.core.model.config import CONFIG_NAMES, default_configs
from harness_design_studio.core.starter import starter_interface_types, starter_parts


def test_starter_parts_are_unverified_examples_without_numbers() -> None:
    parts = starter_parts()
    assert len({p.id for p in parts}) == len(parts)
    assert all(p.unverified and p.approval == "pending" for p in parts)
    assert all(p.mass_g is None and p.mass_per_m_g is None and not p.ratings for p in parts)
    assert all("example" in (p.description or "").lower() for p in parts)
    assert {p.category for p in parts} <= set(PART_CATEGORIES)
    assert {"connector", "wire", "sleeving", "label"} <= {p.category for p in parts}


def test_starter_covers_connector_families_from_spec() -> None:
    ids = " ".join(p.id for p in starter_parts())
    for family in ("DSUB", "MICROD", "MDM", "CIRC", "SMA", "TNC"):
        assert family in ids


def test_starter_interface_types_cover_spec_list() -> None:
    types = {t.id: t for t in starter_interface_types()}
    for tid in ("power_primary", "power_secondary", "rs422", "rs485", "spacewire", "can", "mil1553b",
                "lvds", "i2c", "analog", "thermistor", "heater", "discrete", "pyro", "rf_coax", "ground"):  # fmt: skip
        assert tid in types
    assert all(
        t.unverified and t.impedance_ohm is None and t.default_gauge_awg is None
        for t in types.values()
    )
    assert len(types["spacewire"].signals) == 8  # 4 differential pairs
    assert {s.pair for s in types["rs422"].signals} == {"TX", "RX"}


def test_config_set_complete_and_placeholders_flagged() -> None:
    cfg = default_configs()
    assert set(cfg) == set(CONFIG_NAMES)
    assert {n for n, c in cfg.items() if c.placeholder} == {
        "segmentation", "segregation", "derating", "emc", "titleblock", "generation"
    }  # fmt: skip


def test_the_config_checklist_does_not_use_decision_log_numbers() -> None:
    """`harness config` is read by people who have no access to the repository's decision log."""
    import re

    from harness_design_studio.core import configcheck
    from harness_design_studio.core.samples import new_project

    text, _ok = configcheck.report(new_project())
    assert "Waiting for an owner decision" in text
    assert not re.search(r"\bD-\d+\b", text), text
