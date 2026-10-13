"""SC-3: the engineering values as a list of fields, and a way to set one through the existing
config ops, validated by the same validators. No new file format."""

from pathlib import Path

import pytest

from harness_design_studio.core import configcheck, edit
from harness_design_studio.core.commands import History, SetConfig
from harness_design_studio.core.model import Project
from harness_design_studio.core.model.config import ConfigFile
from harness_design_studio.core.samples import sat15
from tests.test_change_control import do_release, exported, full, releasable


def fresh() -> Project:
    return edit.clone_with(sat15(), [])


def by_key(
    values: list[configcheck.EngineeringValue],
) -> dict[tuple[str, str], configcheck.EngineeringValue]:
    return {(v.file, v.key): v for v in values}


def test_one_field_for_each_required_value_in_the_same_order() -> None:
    p = fresh()
    fields = configcheck.engineering_values(p)
    assert [(f.file, f.key) for f in fields] == [(n.file, n.key) for n in configcheck.NEEDS]
    assert all(f.label and f.kind in ("number", "choice", "pairs", "table") for f in fields)
    assert {f.key for f in fields if f.kind == "choice"} == {"shield_end_a", "shield_end_b"}
    shield = by_key(fields)[("generation", "shield_end_a")]
    assert shield.choices == configcheck.SHIELD_ENDS


def test_missing_fields_agree_with_configcheck_missing() -> None:
    p = fresh()
    fields = configcheck.engineering_values(p)
    assert {(f.file, f.key) for f in fields if f.missing} == {
        (n.file, n.key) for n in configcheck.missing(p)
    }


def test_units_and_labels_are_plain() -> None:
    f = by_key(configcheck.engineering_values(fresh()))
    assert f[("derating", "max_voltage_drop_v")].unit == "V"
    assert f[("generation", "service_loop_m")].unit == "m"
    assert f[("generation", "conductor_resistivity_ohm_m")].unit == "ohm m"
    assert f[("derating", "ampacity_a_by_awg")].unit == "A"
    assert f[("derating", "spare_pin_fraction")].label == "Spare pin fraction"
    assert f[("derating", "max_voltage_drop_v")].what == next(
        n.what for n in configcheck.NEEDS if n.key == "max_voltage_drop_v"
    )


def test_current_value_placeholder_flag_and_source_are_reported() -> None:
    p = fresh()
    p.config["derating"] = ConfigFile(
        name="derating",
        placeholder=True,
        values={**p.config["derating"].values, "spare_pin_fraction": 0.2},
    )
    f = by_key(configcheck.engineering_values(p))
    spare = f[("derating", "spare_pin_fraction")]
    assert spare.value == 0.2 and not spare.missing and spare.placeholder
    assert spare.display == "0.2" and spare.source == "set in the project"
    empty = f[("derating", "max_voltage_drop_v")]
    assert empty.value is None and empty.missing and empty.display == "" and empty.source == ""


def test_a_value_from_a_standard_profile_names_its_requirement() -> None:
    from harness_design_studio.core import standard_profiles

    p = fresh()
    plan = standard_profiles.plan_profile(p, "ecss-q-st-30-11c")
    History(p).execute("profile", [SetConfig(c) for c in plan.configs])
    f = by_key(configcheck.engineering_values(p, include_optional=True))
    factor = f[("derating", "contact_current_factor")]
    assert factor.source.startswith("ECSS-Q-ST-30-11_0140051")
    assert "ecss-q-st-30-11c" in factor.source


def test_optional_values_are_listed_only_on_request_and_marked() -> None:
    p = fresh()
    assert not any(f.optional for f in configcheck.engineering_values(p))
    more = configcheck.engineering_values(p, include_optional=True)
    assert [f.optional for f in more].count(False) == len(configcheck.NEEDS)
    assert ("derating", "max_mating_cycles") in by_key(more)
    assert by_key(more)[("emc", "same_class_one_bundle")].kind == "flag"


def test_required_lists_stay_exactly_as_they_were() -> None:
    assert len(configcheck.NEEDS) == 17
    text, ok = configcheck.report(fresh())
    assert not ok and "MISSING config/derating.json spare_pin_fraction" in text
    assert "max_mating_cycles" not in text


def apply(p: Project, plan: configcheck.ValuePlan) -> None:
    assert plan.error is None, plan.error
    History(p).execute("Set value", plan.ops)


def test_plan_sets_a_number_through_the_config_ops_and_keeps_the_review_flag() -> None:
    p = fresh()
    plan = configcheck.plan_set_value(p, "derating", "spare_pin_fraction", 0.2)
    assert plan.ok and len(plan.ops) == 1 and isinstance(plan.ops[0], SetConfig)
    before = p.config["derating"]
    apply(p, plan)
    assert p.config["derating"].values["spare_pin_fraction"] == 0.2
    assert p.config["derating"].placeholder == before.placeholder
    assert {k: v for k, v in p.config["derating"].values.items() if k != "spare_pin_fraction"} == {
        k: v for k, v in before.values.items() if k != "spare_pin_fraction"
    }
    assert ("derating", "spare_pin_fraction") not in {
        (n.file, n.key) for n in configcheck.missing(p)
    }


def test_text_from_a_form_is_read_like_a_number() -> None:
    p = fresh()
    assert configcheck.plan_set_value(p, "derating", "max_voltage_drop_v", "0,5 V").value == 0.5
    assert configcheck.plan_set_value(p, "generation", "power_signal_gap_pins", "2").value == 2
    assert isinstance(
        configcheck.plan_set_value(p, "generation", "power_signal_gap_pins", "2").value, int
    )
    assert configcheck.plan_set_value(p, "derating", "spare_pin_fraction", " 0.25 ").value == 0.25


@pytest.mark.parametrize(
    ("file", "key", "value", "words"),
    [
        ("derating", "bundle_derating", 1.5, "above 0 and at most 1"),
        ("derating", "bundle_derating", 0, "above 0 and at most 1"),
        ("derating", "spare_pin_fraction", 1, "up to (not including) 1"),
        ("derating", "max_voltage_drop_v", -1, "above 0"),
        ("generation", "power_signal_gap_pins", 1.5, "whole number"),
        ("generation", "shield_end_a", "rubber", "backshell_360"),
        ("derating", "max_voltage_drop_v", "abc", "not a number"),
        ("derating", "max_voltage_drop_v", float("nan"), "not a number"),
        ("derating", "max_voltage_drop_v", True, "not a number"),
        ("derating", "ampacity_a_by_awg", "20: 5, 22: 7", "carries less"),
        ("derating", "ampacity_a_by_awg", "twenty", "gauge"),
        ("segregation", "category_pairs_to_separate", "power", "pair"),
        ("emc", "conflicting_class_pairs", "A+A", "two different"),
    ],
)
def test_wrong_values_come_back_as_plain_sentences_and_change_nothing(
    file: str, key: str, value: object, words: str
) -> None:
    p = fresh()
    plan = configcheck.plan_set_value(p, file, key, value)
    assert not plan.ok and plan.ops == []
    assert plan.error and words in plan.error
    assert "Traceback" not in plan.error and "config/" not in plan.error.split(" ")[0]


def test_the_same_validators_decide() -> None:
    """Whatever `validate` finds in the value is what the plan refuses, and nothing more."""
    p = fresh()
    for key, value in (("bundle_derating", 2.0), ("temperature_derating", 0.9)):
        plan = configcheck.plan_set_value(p, "derating", key, value)
        raw = ConfigFile(
            name="derating", placeholder=True, values={**p.config["derating"].values, key: value}
        )
        trial = edit.clone_with(p, [SetConfig(raw)])
        bad = [i for i in configcheck.validate(trial) if i.object_id == f"derating.{key}"]
        assert bool(bad) == (not plan.ok)


def test_lists_and_tables_can_be_typed_without_json() -> None:
    p = fresh()
    pairs = configcheck.plan_set_value(
        p, "segregation", "category_pairs_to_separate", "power + analog; data/rf"
    )
    assert pairs.value == [["power", "analog"], ["data", "rf"]]
    apply(p, pairs)
    assert p.config["segregation"].values["category_pairs_to_separate"] == [
        ["power", "analog"],
        ["data", "rf"],
    ]
    table = configcheck.plan_set_value(p, "derating", "ampacity_a_by_awg", "20: 5, 22: 3.5\n24=2")
    assert table.value == {"20": 5.0, "22": 3.5, "24": 2.0}
    apply(p, table)
    assert configcheck.plan_set_value(p, "derating", "ampacity_a_by_awg", {"20": 5.0}).ok


def test_choice_and_flag_values() -> None:
    p = fresh()
    assert configcheck.plan_set_value(p, "generation", "shield_end_b", "pigtail").value == "pigtail"
    assert configcheck.plan_set_value(p, "emc", "same_class_one_bundle", "yes").value is True
    assert configcheck.plan_set_value(p, "emc", "same_class_one_bundle", False).value is False
    assert not configcheck.plan_set_value(p, "emc", "same_class_one_bundle", "maybe").ok


def test_empty_input_clears_a_value() -> None:
    p = fresh()
    apply(p, configcheck.plan_set_value(p, "derating", "spare_pin_fraction", 0.2))
    plan = configcheck.plan_set_value(p, "derating", "spare_pin_fraction", "")
    assert plan.ok and plan.value is None
    apply(p, plan)
    assert p.config["derating"].values["spare_pin_fraction"] is None


def test_the_review_flag_can_be_set_with_the_value() -> None:
    p = fresh()
    plan = configcheck.plan_set_value(p, "derating", "spare_pin_fraction", 0.2, placeholder=False)
    apply(p, plan)
    assert p.config["derating"].placeholder is False
    flag = configcheck.plan_placeholder(p, "derating", True)
    apply(p, flag)
    assert p.config["derating"].placeholder is True
    assert configcheck.plan_placeholder(p, "nonexistent", True).error


def test_unknown_names_are_a_plain_error() -> None:
    p = fresh()
    plan = configcheck.plan_set_value(p, "derating", "no_such_key", 1)
    assert not plan.ok and "no_such_key" in (plan.error or "")
    assert not configcheck.plan_set_value(p, "nofile", "x", 1).ok


def test_a_missing_config_file_is_created_not_a_crash() -> None:
    p = fresh()
    del p.config["emc"]
    plan = configcheck.plan_set_value(p, "emc", "conflicting_class_pairs", "A+B")
    assert plan.ok
    apply(p, plan)
    assert p.config["emc"].values["conflicting_class_pairs"] == [["A", "B"]]


def test_a_value_frozen_by_a_release_is_refused_with_the_lock_sentence(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    plan = configcheck.plan_set_value(p, "derating", "spare_pin_fraction", 0.31)
    assert not plan.ok and plan.ops == []
    assert hid in (plan.error or "") and "new revision" in (plan.error or "")
    fields = by_key(configcheck.engineering_values(p))
    assert fields[("derating", "spare_pin_fraction")].locked == plan.error
    assert fields[("generation", "service_loop_m")].locked is None
    assert configcheck.plan_set_value(p, "generation", "service_loop_m", 0.1).ok
