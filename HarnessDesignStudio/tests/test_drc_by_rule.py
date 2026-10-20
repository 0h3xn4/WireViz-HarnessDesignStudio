"""SC-1: a result for every design rule (pass / fail / not checked / pending), built from the same
findings the check already produces. No rule logic is involved."""

import pytest

from harness_design_studio.core import configcheck, drc, edit
from harness_design_studio.core.drc import by_rule
from harness_design_studio.core.drc.rules import RULES
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import Project
from harness_design_studio.core.model.config import ConfigFile
from harness_design_studio.core.samples import sat15

_BASE: Project | None = None


def base() -> Project:
    global _BASE
    if _BASE is None:
        _BASE = sat15()
        generate_project(_BASE)
    return edit.clone_with(_BASE, [])


def set_cfg(p: Project, name: str, **values: object) -> None:
    old = p.config[name]
    p.config[name] = ConfigFile(
        name=name, placeholder=old.placeholder, values={**old.values, **values}
    )


def by_id(results: list[by_rule.RuleResult]) -> dict[str, by_rule.RuleResult]:
    return {r.rule_id: r for r in results}


def test_every_rule_has_exactly_one_result_in_report_order() -> None:
    p = base()
    results = by_rule.run_by_rule(p)
    assert len(RULES) == 35
    assert [r.rule_id for r in results][:35] == [r.id for r in RULES]
    assert all(r.status in ("pass", "fail", "not_checked", "pending") for r in results)


def test_results_group_the_findings_the_run_already_made() -> None:
    p = base()
    findings = drc.run(p)
    results = by_id(by_rule.run_by_rule(p, findings))
    for rule in RULES:
        mine = [f for f in findings if f.rule == rule.id and f.waiver is None]
        assert results[rule.id].count == len(mine)
        assert list(results[rule.id].finding_ids) == [f.id for f in mine]
        assert results[rule.id].severity == rule.severity
        assert results[rule.id].topic == rule.topic


def test_it_does_not_run_the_rules_again_when_given_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = base()
    findings = drc.run(p)

    def boom(_p: Project) -> list[object]:
        raise AssertionError("the rules ran twice")

    monkeypatch.setattr(by_rule, "_run", boom)
    assert by_rule.run_by_rule(p, findings)


def test_a_rule_with_open_findings_fails_and_names_the_objects() -> None:
    p = base()
    set_cfg(p, "derating", spare_pin_fraction=0.99)
    r = by_id(by_rule.run_by_rule(p))["spare-pins-low"]
    assert r.status == "fail"
    assert r.count >= 1 and len(r.object_ids) == r.count
    assert set(r.object_ids) <= set(p.connectors)


def test_a_rule_whose_value_is_missing_is_pending_with_the_exact_value() -> None:
    p = base()
    set_cfg(p, "derating", spare_pin_fraction=None)
    r = by_id(by_rule.run_by_rule(p))["spare-pins-low"]
    assert r.status == "pending"
    assert [(m.file, m.key) for m in r.missing] == [("derating", "spare_pin_fraction")]
    assert r.missing[0].kind == "config" and not r.missing[0].optional
    assert "spare" in r.missing[0].what
    assert r.missing[0].where == "config/derating.json: spare_pin_fraction"


def test_pending_names_every_missing_key_the_rule_needs() -> None:
    p = base()
    set_cfg(p, "derating", max_voltage_drop_v=None)
    set_cfg(p, "generation", conductor_resistivity_ohm_m=None)
    r = by_id(by_rule.run_by_rule(p))["voltage-drop"]
    assert r.status == "pending"
    assert {(m.file, m.key) for m in r.missing} == {
        ("derating", "max_voltage_drop_v"),
        ("generation", "conductor_resistivity_ohm_m"),
    }


def test_a_rule_with_everything_set_and_no_findings_passes() -> None:
    p = base()
    set_cfg(p, "derating", spare_pin_fraction=0.0)
    r = by_id(by_rule.run_by_rule(p))["spare-pins-low"]
    assert r.status == "pass" and r.count == 0 and not r.missing


def test_a_rule_that_skipped_things_is_not_checked_and_says_what_is_missing() -> None:
    p = base()
    set_cfg(p, "derating", connector_voltage_factor_rated=0.75)  # parts carry no rated voltage
    p.interfaces[next(iter(p.interfaces))] = p.interfaces[next(iter(p.interfaces))].model_copy(
        update={"voltage_v": 28.0}
    )
    results = by_id(by_rule.run_by_rule(p))
    r = results["connector-voltage"]
    assert r.status == "not_checked"
    assert r.notes and "rated or withstand voltage" in r.notes[0]
    assert r.missing[0].kind == "data"
    assert r.missing[0].what == r.notes[0]


def test_a_check_that_needs_an_outside_analysis_is_not_checked() -> None:
    p = base()
    set_cfg(p, "derating", max_ambient_temperature_c=60, wire_temperature_margin_c=50,
            connector_temperature_margin_c=30)  # fmt: skip
    r = by_id(by_rule.run_by_rule(p))["temperature-margin"]
    assert r.status == "not_checked"
    assert any(m.kind == "analysis" for m in r.missing)


def test_optional_standard_rules_off_by_default_are_pending_and_marked_optional() -> None:
    p = base()
    r = by_id(by_rule.run_by_rule(p))["mating-cycles"]
    assert r.status == "pending"
    assert [(m.file, m.key, m.optional) for m in r.missing] == [
        ("derating", "max_mating_cycles", True)
    ]


def test_required_missing_values_are_not_marked_optional() -> None:
    p = base()
    needs = {(n.file, n.key) for n in configcheck.NEEDS}
    for res in by_rule.run_by_rule(p):
        for m in res.missing:
            if m.kind == "config":
                assert ((m.file, m.key) in needs) != m.optional


def test_unchecked_config_row_lists_notes_no_rule_owns() -> None:
    p = base()
    set_cfg(p, "derating", rf_power_factor=0.75)
    types = p.interface_types
    rf = next(iter(types.values())).model_copy(update={"category": "rf"})
    p.interface_types[rf.id] = rf
    r = by_id(by_rule.run_by_rule(p))["unchecked-config"]
    assert r.status == "not_checked"
    assert any("multipactor" in n for n in r.notes)


def test_unchecked_config_row_passes_when_every_note_belongs_to_a_rule() -> None:
    p = base()
    r = by_id(by_rule.run_by_rule(p))["unchecked-config"]
    assert r.status == "pass"
    assert r.count == len([f for f in drc.run(p) if f.rule == "unchecked-config"])


def test_waived_findings_do_not_fail_a_rule_but_are_counted() -> None:
    p = base()
    set_cfg(p, "derating", spare_pin_fraction=0.99)
    first = by_id(by_rule.run_by_rule(p))["spare-pins-low"]
    from harness_design_studio.core.model import Waiver

    for f in first.findings:
        p.waivers[f.id] = Waiver(id=f.id, rule=f.rule, object_id=f.object_id,
                                 justification="Accepted for the demo build.")  # fmt: skip
    again = by_id(by_rule.run_by_rule(p))["spare-pins-low"]
    assert again.status == "pass" and again.count == 0 and again.waived == first.count


def test_verifier_mismatches_get_a_row_only_when_there_are_some() -> None:
    p = base()
    assert "verify-mismatch" not in by_id(by_rule.run_by_rule(p))
    findings = drc.run(p)
    fake = findings[0].__class__("verify-mismatch.x", "verify-mismatch", "error", "W001", "t", "w")
    rows = by_id(by_rule.run_by_rule(p, [*findings, fake]))
    assert rows["verify-mismatch"].status == "fail" and rows["verify-mismatch"].count == 1


def test_placeholder_files_are_named_on_rules_that_use_them() -> None:
    p = base()
    set_cfg(p, "derating", spare_pin_fraction=0.0)
    p.config["derating"] = ConfigFile(
        name="derating", placeholder=True, values=p.config["derating"].values
    )
    r = by_id(by_rule.run_by_rule(p))["spare-pins-low"]
    assert r.status == "pass" and r.placeholder_files == ("derating",)


def test_summary_counts_each_state_and_the_values_still_pending() -> None:
    p = base()
    results = by_rule.run_by_rule(p)
    s = by_rule.summary(results)
    assert s.total == len(results)
    assert s.passed + s.failed + s.not_checked + s.pending == s.total
    assert s.pending == sum(r.status == "pending" for r in results)
    missing_required = {
        (m.file, m.key) for r in results for m in r.missing if m.kind == "config" and not m.optional
    }
    assert s.pending_values == len(missing_required)
    assert s.pending_values > 0
    set_cfg(p, "derating", spare_pin_fraction=0.0)
    after = by_rule.summary(by_rule.run_by_rule(p))
    assert after.pending_values == s.pending_values - 1
    assert after.pending == s.pending - 1


def test_summary_of_nothing_is_zero() -> None:
    assert by_rule.summary([]) == by_rule.Summary(0, 0, 0, 0, 0, 0, 0)


def test_the_worker_result_can_be_used_as_it_is() -> None:
    """The worker sends `drc.run`'s findings through a pipe as a pickle; they group the same way."""
    import io

    from harness_design_studio.core.drc import worker

    p = base()
    pipe = io.BytesIO()
    worker.send(pipe, ("findings", drc.run(p)))
    pipe.seek(0)
    message = worker.receive(pipe)
    assert isinstance(message, tuple) and message[0] == "findings"
    assert by_rule.run_by_rule(p, message[1]) == by_rule.run_by_rule(p)


def test_a_project_without_harnesses_still_gets_every_row() -> None:
    p = Project()
    results = by_rule.run_by_rule(p)
    assert [r.rule_id for r in results] == [r.id for r in RULES]
    assert by_rule.summary(results).total == 35


def test_it_is_reachable_from_the_drc_package() -> None:
    p = base()
    assert drc.run_by_rule(p) == by_rule.run_by_rule(p)
    assert drc.run_by_rule(p, drc.run(p)) == by_rule.run_by_rule(p)
