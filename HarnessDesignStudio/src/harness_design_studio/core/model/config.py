"""Rule configuration. Standards numbers are never hard-coded; defaults are placeholders."""

from typing import Any

from .base import Entity, Name

CONFIG_NAMES: tuple[str, ...] = (
    "segmentation", "segregation", "derating", "naming", "emc", "titleblock", "generation",
)  # fmt: skip


class ConfigFile(Entity):
    name: Name
    placeholder: bool  # True until an engineer has reviewed and filled in the values
    values: dict[str, Any]


def default_configs() -> dict[str, ConfigFile]:
    """Starter configuration. Every `placeholder: True` file needs an engineer's review."""
    return {
        "segmentation": ConfigFile(
            name="segmentation",
            placeholder=True,  # DECISIONS D-10: defaulted, owner must confirm
            values={
                "mode": "per_connector_pair"
            },  # per_connector_pair | per_unit_pair | per_zone_pair
        ),
        "segregation": ConfigFile(
            name="segregation",
            placeholder=True,
            values={
                "forbid_nominal_with_redundant": True,
                "forbid_pyro_with_other": True,
                "category_pairs_to_separate": None,
            },
        ),
        "derating": ConfigFile(
            name="derating",
            placeholder=True,  # DECISIONS D-11: real values must come from the program's standard
            values={
                "contact_current_factor": None,
                "bundle_derating": None,
                "temperature_derating": None,
                "max_ambient_temperature_c": None,
                "max_voltage_drop_v": None,
                "spare_pin_fraction": None,
                "ampacity_a_by_awg": None,  # {"20": amps, ...} from the program's standard
                "contact_rating_key": "contact_current_a",
            },
        ),
        "generation": ConfigFile(
            name="generation",
            placeholder=True,  # electrical values below must come from an engineer
            values={
                "wire_part_by_construction": {
                    "single": "EX-WIRE-SINGLE",
                    "twisted_pair": "EX-WIRE-SINGLE",
                    "twisted_shielded_pair": "EX-WIRE-TWISTED-SHIELDED",
                    "quad": "EX-WIRE-TWISTED-SHIELDED",
                    "coax": "EX-WIRE-SINGLE",
                    "twinax": "EX-WIRE-TWISTED-SHIELDED",
                },  # example library parts, not qualified
                "default_gauge_awg": None,
                "service_loop_m": None,
                "conductor_resistivity_ohm_m": None,
                "power_signal_gap_pins": None,
                "mass_margin_fraction": None,
                "test_continuity_max_ohm": None,
                "test_isolation_min_mohm": None,
                "test_isolation_voltage_v": None,
                "shield_end_a": None,  # grounding concept: backshell_360 | pigtail | floating
                "shield_end_b": None,
            },
        ),
        "naming": ConfigFile(
            name="naming",
            placeholder=False,
            values={
                "harness": "W{n:03d}",
                "box_connector": "{unit}-J{n:02d}",
                "cable_connector": "{harness}-P{n}",
                "wire": "{harness}-{n:03d}",
            },
        ),
        "emc": ConfigFile(
            name="emc", placeholder=True, values={"classes": None, "conflicting_class_pairs": None}
        ),
        "titleblock": ConfigFile(
            name="titleblock",
            placeholder=True,  # DECISIONS D-15
            values={
                "fields": [
                    "project",
                    "harness_id",
                    "title",
                    "revision",
                    "date",
                    "author",
                    "checker",
                    "approver",
                    "sheet",
                    "status",
                ]
            },
        ),
    }
