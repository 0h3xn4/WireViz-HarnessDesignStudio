# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""R11: the scripting interface does what the commands do, and says so in plain data.

Each function is compared with the command it stands for: the same files on disk, the same
numbers, the same findings. The tests for `--json` (tests/test_cli_json.py) compare the documents."""

import dataclasses
import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from harness_design_studio import api
from harness_design_studio.cli.main import main
from harness_design_studio.core import derive_export, edit, templates
from harness_design_studio.core.checks import find, waive_op
from harness_design_studio.core.commands import History
from harness_design_studio.core.drc import run as run_rules
from harness_design_studio.core.drc.rules import RULES
from harness_design_studio.core.io.fs import ProjectLock
from harness_design_studio.core.io.loader import load_project as core_load
from harness_design_studio.core.io.saver import save_project as core_save


@pytest.fixture(autouse=True)
def fixed_clock_and_author(monkeypatch: pytest.MonkeyPatch) -> None:
    """The journal of a new project holds a time and a name: fix both, so that the command and the
    interface can be compared byte for byte."""
    from harness_design_studio.core import journal

    monkeypatch.setattr(journal, "now", lambda: "2026-11-03T11:30:00Z")
    monkeypatch.setenv("HARNESS_AUTHOR", "Ann Engineer")


def tree(folder: Path) -> dict[str, str]:
    """Every file of a folder (not the lock and the `.bak` copies) with a digest of its bytes."""
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file() and not p.name.startswith(".harness.lock") and p.suffix != ".bak"
    }


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """first-steps, generated and exported once; tests that change a project copy it."""
    folder = tmp_path_factory.mktemp("api") / "base"
    api.create_project(folder, "first-steps")
    assert api.generate(folder).ok and api.export(folder).ok
    return folder


@pytest.fixture
def work(base: Path, tmp_path: Path) -> Path:
    shutil.copytree(base, tmp_path / "work")
    return tmp_path / "work"


# ---- projects ------------------------------------------------------------------------------------


def test_templates_and_create_project(tmp_path: Path) -> None:
    listed = api.list_templates()
    assert [t.name for t in listed] == [t.name for t in templates.TEMPLATES]
    project = api.create_project(tmp_path / "p", "first-steps", name="My name")
    assert project.meta.name == "My name" and len(project.units) == 3
    assert api.load_project(tmp_path / "p").meta.name == "My name"
    assert (tmp_path / "p" / ".gitattributes").is_file()  # as `new` makes it
    with pytest.raises(api.TemplateError, match="Unknown template"):
        api.create_project(tmp_path / "q", "nope")
    with pytest.raises(api.TemplateError, match="not an empty folder"):
        api.create_project(tmp_path / "p", "blank")
    assert issubclass(api.TemplateError, api.HarnessError)


def test_new_by_the_command_and_by_the_interface_write_the_same_files(tmp_path: Path) -> None:
    assert main(["new", str(tmp_path / "cli"), "--template", "small-satellite"]) == 0
    api.create_project(tmp_path / "api", "small-satellite")
    assert tree(tmp_path / "cli") == tree(tmp_path / "api")


def test_load_errors_form_one_tree(tmp_path: Path, base: Path) -> None:
    with pytest.raises(api.LoadError, match="not a folder"):
        api.load_project(tmp_path / "nowhere")
    (tmp_path / "plain").mkdir()
    with pytest.raises(api.LoadError, match="no project.json"):
        api.load_project(tmp_path / "plain")
    damaged = tmp_path / "damaged"
    shutil.copytree(base, damaged)
    (damaged / "logical" / "interfaces" / "power.json").write_text("{not json")
    with pytest.raises(api.ProjectDamagedError) as raised:
        api.load_project(damaged)
    assert isinstance(raised.value, api.LoadError) and isinstance(raised.value, api.HarnessError)
    assert raised.value.issues and all(isinstance(i, api.IssueRecord) for i in raised.value.issues)
    # the check reports the damage instead of refusing it, as `validate` does
    result = api.validate(damaged)
    assert not result.ok and result.errors >= 1
    reading: list[Callable[[Path], object]] = [api.run_checks, api.get_config, api.explain_all]
    changing: list[Callable[[Path], object]] = [api.generate, api.export, api.verify]
    for call in (*reading, *changing):
        with pytest.raises(api.ProjectDamagedError):
            call(damaged)


def test_a_read_only_project_is_not_changed(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from harness_design_studio.core.io import loader

    real = loader.load_project

    def read_only(path: Path):  # type: ignore[no-untyped-def]
        result = real(path)
        result.project.read_only = True
        return result

    monkeypatch.setattr("harness_design_studio.api._load_project", read_only)
    before = tree(work)
    for call in (
        lambda: api.generate(work),
        lambda: api.export(work),
        lambda: api.set_config(work, "derating", "bundle_derating", 0.7),
    ):
        with pytest.raises(api.ReadOnlyProjectError, match="read-only"):
            call()
    assert tree(work) == before
    assert api.run_checks(work).rules_run == 39  # reading still works


def test_the_interface_takes_the_lock_of_the_editor(work: Path) -> None:
    lock = ProjectLock(work)
    lock.acquire()
    try:
        with pytest.raises(api.ProjectLockedError):
            api.generate(work)
        with pytest.raises(api.ProjectLockedError):
            api.set_config(work, "derating", "bundle_derating", 0.7)
        assert api.run_checks(work).ok  # reading does not need it
    finally:
        lock.release()
    assert api.generate(work).ok


# ---- checking, generating, exporting -------------------------------------------------------------


def test_validate_matches_the_command(work: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(work)]) == 0
    text = capsys.readouterr().out
    result = api.validate(work)
    assert result.ok and f"{result.errors} error(s), {result.warnings} warning(s)." in text
    assert all(f"{i.severity.upper():7} {i.code}: {i.message}" in text for i in result.issues)
    assert api.validate(work, merge_check=True).ok


def test_generate_by_the_command_and_by_the_interface_write_the_same_files(tmp_path: Path) -> None:
    for name in ("cli", "api"):
        api.create_project(tmp_path / name, "minimal-satellite")
    assert main(["generate", str(tmp_path / "cli")]) == 0
    result = api.generate(tmp_path / "api")
    assert result.ok and result.saved and result.added
    assert tree(tmp_path / "cli") == tree(tmp_path / "api")
    again = api.generate(tmp_path / "api")  # a second run changes nothing
    assert again.ok and not again.added and not again.changed and again.unchanged
    assert tree(tmp_path / "cli") == tree(tmp_path / "api")


def test_a_generation_with_errors_saves_nothing(tmp_path: Path) -> None:
    folder = tmp_path / "p"
    api.create_project(folder, "flatsat")
    api.set_config(folder, "derating", "bundle_derating", 0.5)  # no gauge fits
    before = tree(folder)
    result = api.generate(folder)
    assert not result.ok and not result.saved and result.findings
    assert tree(folder) == before


def test_run_checks_is_what_the_rules_and_the_editor_give(work: Path) -> None:
    project = api.load_project(work)
    result = api.run_checks(project)  # a loaded project and a folder give the same answer
    assert result == api.run_checks(work)
    expected = {f.id for f in [*find(project), *run_rules(project)]}
    assert {f.id for f in result.findings} == expected
    assert result.rules_run == len(RULES) and result.ok == (result.open_errors == 0)
    assert result.open_warnings + result.open_notes + result.open_errors + result.waived == len(
        result.findings
    )


def test_a_waived_finding_is_marked_with_its_reason(work: Path) -> None:
    project = api.load_project(work)
    warning = (
        next(f for f in find(project) if f.can_waive and f.severity != "error")
        if any(f.can_waive for f in find(project))
        else next(f for f in run_rules(project) if f.can_waive and f.waiver is None)
    )
    History(project).execute("waive", [waive_op(warning, "Accepted for the example")])
    core_save(project, work)
    result = api.run_checks(work)
    waived = [f for f in result.findings if f.waived]
    assert [f.id for f in waived] == [warning.id]
    assert waived[0].waiver_justification == "Accepted for the example" and result.waived == 1


def test_verify_and_export_match_the_commands(base: Path, tmp_path: Path) -> None:
    assert api.verify(base).ok and api.verify(base, outputs=True).ok
    with pytest.raises(api.NoOutputsError):
        folder = tmp_path / "fresh"
        api.create_project(folder, "first-steps")
        api.verify(folder, outputs=True)
    cli_folder, api_folder = tmp_path / "cli", tmp_path / "api"
    for f in (cli_folder, api_folder):
        shutil.copytree(base, f)
        shutil.rmtree(f / "outputs")
    assert main(["export", str(cli_folder)]) == 0
    result = api.export(api_folder)
    assert result.written and result.ok and not result.blocked
    assert tree(cli_folder / "outputs") == tree(api_folder / "outputs")
    assert {f.path for f in result.files} == {
        p.relative_to(api_folder / "outputs").as_posix()
        for p in (api_folder / "outputs").rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }


def test_export_to_another_folder_and_with_drawings(work: Path, tmp_path: Path) -> None:
    plain = api.export(work, tmp_path / "plain")
    drawn = api.export(work, tmp_path / "drawn", drawings=True)
    assert len(drawn.files) > len(plain.files)
    drawings = [
        f.path for f in drawn.files if f.path.startswith("harnesses/") and f.path.endswith(".pdf")
    ]
    assert drawings
    assert not any(f.path.startswith("harnesses/") and f.path.endswith(".pdf") for f in plain.files)
    assert plain.model_hash == drawn.model_hash and len(plain.model_hash) == 12
    # drawings written earlier and left out now are reported, as the command says it
    shutil.copytree(tmp_path / "drawn", tmp_path / "drawn2")
    again = api.export(work, tmp_path / "drawn2")
    assert again.drawings_removed


def test_nothing_to_export_is_a_result_not_an_error(tmp_path: Path) -> None:
    folder = tmp_path / "p"
    api.create_project(folder, "first-steps")
    result = api.export(folder)
    assert (result.ok, result.written, result.blocked) == (False, False, "nothing_to_export")
    assert not (folder / "outputs").exists()


# ---- explaining -----------------------------------------------------------------------------------


def test_explain_matches_the_derivations_and_the_files(work: Path, tmp_path: Path) -> None:
    project = api.load_project(work)
    every = api.explain_all(project)
    assert every == derive_export.explain_all(project) == api.explain_all(work)
    wire = next(iter(project.harnesses.values())).wires[0].id
    mine = api.explain(project, wire)
    # the four numbers of the wire come first, in this order, with the choice of its gauge after
    # the length; the explanations of its label, colour and pins (transparency step S1) follow
    assert [d.id for d in mine][:5] == [
        "wire-length", "gauge", "wire-current-limit", "wire-voltage-drop", "wire-mass",
    ]  # fmt: skip
    # the choice of the gauge is computed on demand: it is not in `explain_all` or its files
    assert all(d in every for d in mine if d.id != "gauge")
    assert not [d for d in every if d.id == "gauge"]
    assert json.dumps([d.to_dict() for d in mine])  # the plain form
    with pytest.raises(api.EditError):
        api.explain(project, "NOT-AN-OBJECT")
    written = api.write_derivations(project, tmp_path / "d")
    assert written.count == len(every) and tuple(p.name for p in written.files) == (
        "derivations.json", "derivations.csv",
    )  # fmt: skip
    assert (tmp_path / "d" / "derivations.json").read_bytes() == derive_export.to_json_bytes(
        project, every
    )
    assert main(["explain", str(work), "--all", "--out", str(tmp_path / "c")]) == 0
    assert (tmp_path / "c" / "derivations.csv").read_bytes() == (
        tmp_path / "d" / "derivations.csv"
    ).read_bytes()


def test_explain_finding_is_the_derivation_the_editor_shows(tmp_path: Path) -> None:
    from harness_design_studio.core.derive import EXPLAINABLE_RULES
    from harness_design_studio.core.derive import explain_finding as core_explain_finding

    folder = tmp_path / "p"
    api.create_project(folder, "flatsat")
    api.set_config(folder, "derating", "max_voltage_drop_v", 0.1)  # a limit the wires break
    api.generate(folder)
    project = api.load_project(folder)
    result = api.run_checks(project)
    explained = {f.id: api.explain_finding(project, f.id) for f in result.findings}
    for finding in result.findings:
        assert explained[finding.id] == core_explain_finding(
            project, finding.rule, finding.object_id
        )
        if finding.rule not in EXPLAINABLE_RULES:
            assert explained[finding.id] == []  # no calculation behind this rule
    shown = [f for f in result.findings if f.rule in EXPLAINABLE_RULES]
    assert shown and all(explained[f.id] for f in shown), "a finding with a calculation has one"
    assert all(isinstance(d, api.Derivation) for f in shown for d in explained[f.id])
    with pytest.raises(api.EditError, match="There is no finding"):
        api.explain_finding(folder, "no-such.finding")


# ---- configuration --------------------------------------------------------------------------------


def test_get_config_lists_every_value_with_its_use(work: Path) -> None:
    report = api.get_config(work)
    assert report.total == 17 and len(report.values) > report.total
    bundle = report.value("derating", "bundle_derating")
    assert (bundle.unit, bundle.kind, bundle.missing, bundle.value) == ("", "number", True, None)
    assert bundle.used_by and bundle.what and bundle.placeholder and bundle.source == ""
    assert report.set_count < report.total and not report.ok
    assert report.value("derating", "ampacity_a_by_awg").unit == "A"
    with pytest.raises(KeyError):
        report.value("derating", "nope")
    assert report == api.get_config(api.load_project(work))
    assert json.dumps(report.to_dict())


def test_set_config_checks_the_value_as_the_editor_does(work: Path) -> None:
    value = api.set_config(work, "derating", "bundle_derating", 0.7)
    assert value.value == 0.7 and value.source == "set in the project"
    assert api.get_config(work).value("derating", "bundle_derating").value == 0.7
    assert api.set_config(work, "derating", "bundle_derating", "0,8").value == 0.8  # as typed
    assert api.set_config(work, "derating", "max_voltage_drop_v", "0.5 V").value == 0.5
    before = tree(work)
    for key, bad in (
        ("bundle_derating", 1.5),  # a factor above 1
        ("bundle_derating", 0),
        ("bundle_derating", "much"),
        ("no_such_key", 1),
    ):
        with pytest.raises(api.ConfigValueError) as raised:
            api.set_config(work, "derating", key, bad)
        assert isinstance(raised.value, api.EditError) and str(raised.value)
    with pytest.raises(api.ConfigValueError, match="gauge 20"):
        api.set_config(work, "derating", "ampacity_a_by_awg", {"20": 5, "22": 9})  # rises
    assert tree(work) == before  # a refused value changes no file
    cleared = api.set_config(work, "derating", "bundle_derating", None)
    assert cleared.value is None and cleared.missing
    reviewed = api.set_config(work, "derating", "bundle_derating", 0.9, placeholder=False)
    assert reviewed.placeholder is False


def test_a_value_set_through_the_interface_is_the_value_the_command_reports(
    work: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api.set_config(work, "generation", "service_loop_m", 0.25)
    assert main(["config", str(work), "--json"]) in (0, 1)
    doc = json.loads(capsys.readouterr().out)
    loop = next(v for v in doc["values"] if v["key"] == "service_loop_m")
    assert loop["value"] == 0.25 and loop["display"] == "0.25"
    # and regenerating uses it: the design hash changes with the value
    before = api.run_checks(work).model_hash
    api.set_config(work, "generation", "service_loop_m", 0.5)
    api.generate(work)
    assert api.run_checks(work).model_hash != before


# ---- rules and plain data -------------------------------------------------------------------------


def test_list_rules_is_the_registry() -> None:
    rules = api.list_rules()
    assert [r.id for r in rules] == [r.id for r in RULES] and len(rules) == 39
    assert len({r.id for r in rules}) == 39
    sample = rules[0]
    assert sample.why and sample.how and sample.severity in ("error", "warning", "info")
    text = (Path(__file__).resolve().parents[1] / "docs" / "RULES.md").read_text(encoding="utf-8")
    assert all(f"`{r.id}`" in text for r in rules)


def test_every_result_is_plain_data(work: Path) -> None:
    results: list[Any] = [
        api.validate(work), api.run_checks(work), api.verify(work), api.generate(work),
        api.export(work), api.get_config(work), api.list_rules()[0], api.list_templates()[0],
    ]  # fmt: skip
    for result in results:
        params = getattr(type(result), "__dataclass_params__", None)
        assert params is not None and params.frozen
        assert dataclasses.fields(result)
        again = json.loads(json.dumps(result.to_dict()))
        assert again == result.to_dict()
    text = json.dumps([r.to_dict() for r in results])
    assert str(work) not in text


def test_the_interface_prints_nothing_and_never_exits(
    work: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api.validate(work)
    api.run_checks(work)
    api.generate(work)
    api.export(work)
    api.explain_all(work)
    api.get_config(work)
    api.set_config(work, "derating", "bundle_derating", 0.7)
    with pytest.raises(api.HarnessError):
        api.load_project(work / "missing")
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


def test_the_core_functions_are_the_ones_called(work: Path) -> None:
    """Nothing is computed twice: the project that `load_project` returns is the loader's."""
    assert api.load_project(work) == core_load(work).project
    assert edit.clone_with(api.load_project(work), []) == api.load_project(work)


def test_get_settings_is_the_settings_command(
    work: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_design_studio.core import settings

    records = api.get_settings(work)
    assert [r.id for r in records] == [s.id for s in settings.SETTINGS]
    assert api.get_settings(api.load_project(work)) == records
    assert main(["settings", str(work), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert [r.to_dict() for r in records] == doc["settings"]
    assert {r.origin for r in records} <= {"project", "default", "unset"}
    api.set_config(work, "generation", "service_loop_m", 0.3)
    changed = {r.id: r for r in api.get_settings(work)}["generation.service_loop_m"]
    assert (changed.value, changed.origin) == (0.3, "project")
