# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg,attr-defined"
"""A release gate on the as-built records (owner decision 11), opt-in. The setting
`release_requires_asbuilt` of `config/naming.json` is off by default and then a release is what it
was. On, a harness is released only when its as-built records are complete (the 'needed values' of
docs/models/asbuilt.md) and no recorded length is out of tolerance, or the person releasing gives a
written reason with `--accept-asbuilt`, which is kept in the change log. The records are not frozen
by the release."""

import copy
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import asbuilt, configcheck, settings, templates
from harness_design_studio.core.generation_status import input_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import ConfigFile, Project
from harness_design_studio.core.outputs.build import write_outputs
from harness_design_studio.core.vcs.release import plan_release, release_blockers
from tests.test_s9_asbuilt import record

WHEN = "2026-03-01"
REASON = "Practice project: placeholders and example parts"
KEY = "release_requires_asbuilt"
GATE_CODES = {"asbuilt_incomplete", "asbuilt_length_out", "asbuilt_reason_short"}


def with_values(project: Project, file: str, **values: object) -> Project:
    p = copy.deepcopy(project)
    c = p.config[file]
    p.config[file] = ConfigFile(name=file, placeholder=c.placeholder, values={**c.values, **values})
    return p


def codes(p: Project, hid: str = "W001", folder: Path | None = None, **kw) -> set[str]:
    args = dict(
        by="Ada", comment="a long enough comment", when=WHEN, accept_placeholders=REASON,
        accept_unapproved_parts=REASON,
    )  # fmt: skip
    args.update(kw)
    return {b.code for b in release_blockers(p, hid, outputs_folder=folder, **args)}


def fill_everything(project: Project, hid: str = "W001", **changes: dict[str, str]) -> None:
    """Record every value the sheet asks of the harness, each as designed and each test within its
    limit; `changes` maps a wire ID to {heading: value} to record something else for it."""
    rows = asbuilt.template_rows(project, hid)
    head = rows[0]
    fill: dict[tuple[str, str], dict[str, str]] = {}
    for r in rows[1:]:
        kind, item = r[0], r[2]
        cell = dict(zip(head, r, strict=True)).__getitem__
        if kind == "harness":
            fill[(kind, item)] = {"Serial number": "SN-1", "Built by": "A", "Inspected by": "B"}
        elif kind == "part":
            fill[(kind, item)] = {"Lot": "LOT-1"}
        elif kind == "wire":
            fill[(kind, item)] = {"Cut length (m)": cell("Designed length (m)")}
            for a in ("A", "B"):
                if cell(f"Designed strip {a} (mm)"):
                    fill[(kind, item)][f"Strip {a} (mm)"] = cell(f"Designed strip {a} (mm)")
        elif kind == "pin":
            fill[(kind, item)] = {"Crimp tool": "T-1", "Crimp tool calibration ID": "CAL-1"}
        elif kind == "test":
            fill[(kind, item)] = {"Result": "pass"}
            if cell("Test type") == "continuity":
                fill[(kind, item)]["Continuity (ohm)"] = "0.1"
            else:
                fill[(kind, item)]["Isolation (Mohm)"] = "100000"
                fill[(kind, item)]["Test voltage (V)"] = "500"
    for wire, cells in changes.items():
        fill[("wire", wire)] = {**fill[("wire", wire)], **cells}
    record(project, fill, harness=hid)


@pytest.fixture(scope="module")
def flat(tmp_path_factory) -> Project:
    return templates.create_project(tmp_path_factory.mktemp("gate") / "flat", "flatsat")


@pytest.fixture(scope="module")
def complete(flat: Project) -> Project:
    p = copy.deepcopy(flat)
    fill_everything(p)
    status = next(s for s in asbuilt.asbuilt_report(p).harnesses if s.harness_id == "W001")
    assert status.complete and status.out_of_limit == 0, status
    return p


# ---- the setting ---------------------------------------------------------------------------------


def test_the_setting_is_registered_off_by_default_and_not_in_a_new_project(flat) -> None:
    s = settings.setting("naming", KEY)
    assert s is not None and s.default is False and s.kind == "flag" and s.file == "naming"
    assert settings.effective(flat, "naming", KEY).value is False
    assert KEY not in flat.config["naming"].values


@pytest.mark.parametrize("bad", ["yes", 1, [True]])
def test_a_value_that_is_not_true_or_false_is_an_error_and_the_gate_stays_off(flat, bad) -> None:
    p = with_values(flat, "naming", **{KEY: bad})
    assert [i.message for i in configcheck.validate(p)] == [f"config/naming.json: {KEY} must be true or false."]  # fmt: skip
    assert not GATE_CODES & codes(p)
    assert not configcheck.validate(with_values(flat, "naming", **{KEY: None}))
    assert not configcheck.validate(with_values(flat, "naming", **{KEY: False}))


def test_the_key_is_not_read_by_generation_so_switching_it_leaves_the_plans_current(flat) -> None:
    assert input_hash(with_values(flat, "naming", **{KEY: True})) == input_hash(flat)


# ---- off: a release is what it was ----------------------------------------------------------------


def test_off_a_release_ignores_the_records_whatever_they_say(flat, complete) -> None:
    assert not GATE_CODES & codes(flat)  # no records at all
    partly = copy.deepcopy(flat)
    record(partly, {("wire", "W001-001"): {"Cut length (m)": "3.50"}})
    assert not GATE_CODES & codes(partly)
    off = with_values(partly, "naming", **{KEY: False})
    assert not GATE_CODES & codes(off)
    assert not GATE_CODES & codes(with_values(partly, "generation", asbuilt_cut_tolerance_mm=1))


# ---- on: blocked ------------------------------------------------------------------------------------


def test_on_a_harness_without_records_is_blocked_with_a_clear_message(flat) -> None:
    p = with_values(flat, "naming", **{KEY: True})
    blockers = [b for b in release_blockers(p, "W001", by="Ada", comment="a long enough comment", when=WHEN, outputs_folder=None, accept_placeholders=REASON, accept_unapproved_parts=REASON) if b.code in GATE_CODES]  # fmt: skip
    assert [b.code for b in blockers] == ["asbuilt_incomplete"]
    m = blockers[0].message
    assert "W001 has no as-built records" in m and KEY in m and "--accept-asbuilt REASON" in m
    assert blockers[0].object_id == "W001"


def test_on_incomplete_records_are_blocked_and_the_message_counts_what_is_missing(flat) -> None:
    p = with_values(flat, "naming", **{KEY: True})
    record(p, {("wire", "W001-001"): {"Cut length (m)": "3.45"}})
    status = next(s for s in asbuilt.asbuilt_report(p).harnesses if s.harness_id == "W001")
    assert status.started and not status.complete and status.missing > 100
    (b,) = [x for x in release_blockers(p, "W001", by="Ada", comment="a long enough comment", when=WHEN, outputs_folder=None, accept_placeholders=REASON, accept_unapproved_parts=REASON) if x.code in GATE_CODES]  # fmt: skip
    assert b.code == "asbuilt_incomplete"
    assert f"{status.missing} value(s) are missing" in b.message and "first:" in b.message


def test_other_harnesses_are_not_asked_for_records_they_do_not_have_to_be_complete(flat, complete) -> None:  # fmt: skip
    p = with_values(complete, "naming", **{KEY: True})
    assert "asbuilt_incomplete" in codes(p, "W002")  # W002 has none: its own release is blocked
    assert not GATE_CODES & codes(p, "W001")  # W001's records are complete


def test_on_a_length_out_of_tolerance_is_blocked_even_when_the_records_are_complete(complete) -> None:  # fmt: skip
    p = with_values(complete, "naming", **{KEY: True})
    p = with_values(p, "generation", asbuilt_cut_tolerance_mm=10)
    record(p, {("wire", "W001-002"): {"Cut length (m)": "3.50"}})  # +50 mm
    got = [x for x in release_blockers(p, "W001", by="Ada", comment="a long enough comment", when=WHEN, outputs_folder=None, accept_placeholders=REASON, accept_unapproved_parts=REASON) if x.code in GATE_CODES]  # fmt: skip
    assert [x.code for x in got] == ["asbuilt_length_out"]
    assert "1 as-built length(s) of W001 are out of tolerance (first: W001-002 cut length (m))" in got[0].message  # fmt: skip
    assert "--accept-asbuilt REASON" in got[0].message
    # within the tolerance: not blocked; and with no tolerance set a difference is not out
    fine = with_values(p, "generation", asbuilt_cut_tolerance_mm=60)
    assert not GATE_CODES & codes(fine)
    none = with_values(p, "generation", asbuilt_cut_tolerance_mm=None)
    assert not GATE_CODES & codes(none)


def test_a_test_value_out_of_its_limit_is_reported_but_is_not_this_gate(complete) -> None:
    p = with_values(complete, "naming", **{KEY: True})
    tests = [r for r in asbuilt.template_rows(p, "W001")[1:] if r[0] == "test" and r[17] == "continuity"]  # fmt: skip
    record(p, {("test", tests[0][2]): {"Continuity (ohm)": "99"}})
    assert asbuilt.asbuilt_report(p).out_of_limit == 1
    assert not GATE_CODES & codes(p)


# ---- on: accepted with a reason ------------------------------------------------------------------------


def test_a_reason_accepts_the_blockers_and_a_short_reason_does_not(flat) -> None:
    p = with_values(flat, "naming", **{KEY: True})
    assert codes(p) >= {"asbuilt_incomplete"}
    assert not GATE_CODES & codes(p, accept_asbuilt="Built before the sheets were in use")
    assert "asbuilt_reason_short" in codes(p, accept_asbuilt="too short")
    assert "asbuilt_incomplete" not in codes(p, accept_asbuilt="too short")
    assert codes(with_values(flat, "naming", **{KEY: False}), accept_asbuilt="too short") & GATE_CODES == set()  # fmt: skip


def test_a_reason_that_is_not_needed_is_not_recorded(complete) -> None:
    p = with_values(complete, "naming", **{KEY: True})
    assert not GATE_CODES & codes(p, accept_asbuilt="Built before the sheets were in use")
    plan = plan_release(p, "W001", by="Ada", checker=None, comment="First release", when=WHEN, outputs_folder=Path("/nonexistent"), accept_placeholders=REASON, accept_unapproved_parts=REASON, accept_asbuilt="Not needed here")  # fmt: skip
    assert all(b.code.startswith("outputs") for b in plan.blockers)


def test_passes_when_the_records_are_complete(complete) -> None:
    p = with_values(complete, "naming", **{KEY: True})
    assert not GATE_CODES & codes(p)
    assert not {b.code for b in release_blockers(p, "W001", by="Ada", comment="a long enough comment", when=WHEN, outputs_folder=None, accept_placeholders=REASON, accept_unapproved_parts=REASON)} & GATE_CODES  # fmt: skip


# ---- the command: the reason goes to the change log -------------------------------------------------------


def _release_args(folder: Path, *more: str) -> list[str]:
    return ["release", str(folder), "W001", "--by", "Ada", "--comment", "Release for the bench test",
            "--accept-placeholders", REASON, "--accept-unapproved-parts", REASON, *more]  # fmt: skip


@pytest.fixture
def folder(flat: Project, tmp_path: Path) -> Path:
    p = with_values(flat, "naming", **{KEY: True})
    save_project(p, tmp_path / "p")
    write_outputs(load_project(tmp_path / "p").project, tmp_path / "p" / "outputs")
    return tmp_path / "p"


def test_the_command_is_blocked_then_released_with_a_reason_kept_in_the_change_log(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_release_args(folder)) == 1
    err = capsys.readouterr().err
    assert "blocked: [asbuilt_incomplete]" in err and "--accept-asbuilt REASON" in err
    assert main(_release_args(folder, "--accept-asbuilt", "short")) == 1
    err = capsys.readouterr().err
    assert "[asbuilt_reason_short]" in err and "--accept-asbuilt: " in err
    reason = "Built before the sheets existed; the paper records are in the binder"
    assert main(_release_args(folder, "--accept-asbuilt", reason)) == 0
    project = load_project(folder).project
    assert project.harnesses["W001"].status == "released"
    entry = next(e for e in project.changelog.values() if e.kind == "release")
    assert "[Released although the as-built records of W001 are incomplete (no records);" in entry.comment  # fmt: skip
    assert f"accepted by Ada: {reason}]" in entry.comment
    assert project.baselines["W001.A"].comment == entry.comment


def test_the_command_releases_without_the_option_when_the_gate_is_off(
    flat: Project, tmp_path: Path
) -> None:
    save_project(flat, tmp_path / "p")
    write_outputs(load_project(tmp_path / "p").project, tmp_path / "p" / "outputs")
    assert main(_release_args(tmp_path / "p")) == 0
    entry = next(e for e in load_project(tmp_path / "p").project.changelog.values() if e.kind == "release")  # fmt: skip
    assert "as-built" not in entry.comment


# ---- the records are not frozen ------------------------------------------------------------------------------


def test_a_release_does_not_freeze_the_records(folder: Path) -> None:
    assert main(_release_args(folder, "--accept-asbuilt", "Built before the sheets existed")) == 0
    project = load_project(folder).project
    assert project.harnesses["W001"].status == "released"
    record(project, {("wire", "W001-001"): {"Cut length (m)": "3.46"}})  # still allowed
    save_project(project, folder)
    again = load_project(folder).project
    assert again.harnesses["W001"].status == "released"
    assert again.asbuilt["wire:W001:W001-001"].cut_length_m == 3.46


def test_complete_records_release_without_the_option_and_without_a_note(
    complete: Project, tmp_path: Path
) -> None:
    save_project(with_values(complete, "naming", **{KEY: True}), tmp_path / "p")
    write_outputs(load_project(tmp_path / "p").project, tmp_path / "p" / "outputs")
    assert main(_release_args(tmp_path / "p")) == 0
    entry = next(e for e in load_project(tmp_path / "p").project.changelog.values() if e.kind == "release")  # fmt: skip
    assert "as-built" not in entry.comment
