# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg,attr-defined"
"""S9 (R6): the workflow page matches the code. One source, `core/workflow.py`: the page's tables are
made from it and a test fails when they differ; every step names only files, configuration files,
outputs, data tables and commands that the tool has; the states are worked out from the project."""

import json
import re
from pathlib import Path

import pytest

from harness_design_studio import api
from harness_design_studio.cli.main import build_parser, main
from harness_design_studio.core import asbuilt, open_data, templates, workflow
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.io.layout import is_managed
from harness_design_studio.core.model import CONFIG_NAMES
from harness_design_studio.core.outputs.build import build_outputs, write_outputs
from tools import gen_workflow_doc

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "user-manual" / "follow-the-workflow.md"


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")  # (Windows writes CRLF)


@pytest.fixture(scope="module")
def flat(tmp_path_factory):
    project = templates.create_project(tmp_path_factory.mktemp("wf") / "flat", "flatsat")
    table = asbuilt.template_rows(project, "W001")
    head = table[0]
    for row in table[1:]:
        if row[0] == "test" and row[2] == "T001":
            row[head.index("Continuity (ohm)")] = "0.4"
    apply_ops(project, asbuilt.plan_asbuilt_import(project, table).ops)
    return project


# ---- the page and the code agree ---------------------------------------------------------------


def test_the_tables_of_the_page_are_the_tables_of_the_code() -> None:
    text = _read(PAGE)
    assert gen_workflow_doc.render(text) == text, "run: python -m tools.gen_workflow_doc"
    for name, make in gen_workflow_doc.BLOCKS.items():
        block = text.split(gen_workflow_doc.marker(name) + "\n", 1)[1].split("\n" + gen_workflow_doc.marker(name, True), 1)[0]  # fmt: skip
        assert block == make()
    for step in workflow.STEPS:  # every step of the code is on the page, with its title and command
        assert f"**{step.title}**" in text
        assert not step.command or f"`harness-design-studio {step.command}`" in text


def test_the_page_says_the_nine_steps_and_the_states_the_code_has() -> None:
    text = _read(PAGE)
    assert len(workflow.STEPS) == 9 and workflow.KEYS[0] == "devices" and workflow.KEYS[-1] == "as-built"  # fmt: skip
    states = text.split("## What the states mean", 1)[1].split("##", 1)[0]
    for word in ("done", "to do", "pending", "out of date", "needs attention", "blocked"):
        assert f"| {word} |" in states
    assert set(workflow.STATES) == {"done", "todo", "pending", "stale", "attention", "blocked"}


def _as_regex(name: str) -> re.Pattern[str]:
    return re.compile("^" + re.sub(r"<[a-z]+>", "[^/]+", re.escape(name).replace("\\<", "<").replace("\\>", ">")) + "$")  # fmt: skip


def _problems(steps, made: set[str], tables: set[str], commands: set[str]) -> list[str]:
    """What the steps name that the tool does not have."""
    found: list[str] = []
    for step in steps:
        for item in (*step.consumes, *step.produces):
            if item.kind not in workflow.KINDS:
                found.append(f"{step.key}: kind {item.kind}")
            elif item.kind == workflow.PROJECT and not is_managed(re.sub(r"<[a-z]+>", "x", item.name)):  # fmt: skip
                found.append(f"{step.key}: {item.name} is not a file of a project")
            elif item.kind == workflow.CONFIG and item.name.removeprefix("config/").removesuffix(".json") not in CONFIG_NAMES:  # fmt: skip
                found.append(f"{step.key}: {item.name} is not a configuration file")
            elif item.kind == workflow.OUTPUT and not any(_as_regex(item.name).match(f) for f in made):  # fmt: skip
                found.append(f"{step.key}: no output file {item.name}")
            elif item.kind == workflow.DATA and item.name not in tables:
                found.append(f"{step.key}: no data table {item.name}")
        if step.command and step.command not in commands:
            found.append(f"{step.key}: no command {step.command}")
        for look in step.inspect:  # the commands and the tables a person is sent to exist
            for part in look.how.split(";"):
                words = part.split()
                if words and words[0] in ("explain", "export-data", "settings", "config", "diff", "log", "asbuilt") and words[0] not in commands:  # fmt: skip
                    found.append(f"{step.key}: no command {words[0]}")
                if words and words[0] == "export-data" and ("table" in words or "tables" in words):
                    at = words.index("table" if "table" in words else "tables")
                    found += [f"{step.key}: no data table {n.strip()}" for n in " ".join(words[at + 1 :]).split(",") if n.strip() not in tables]  # fmt: skip
    return found


def _world(flat):
    made = set(build_outputs(flat, drawings=False).files) | {"manifest.json"}
    tables = {t.name for t in open_data.all_tables(flat)}
    commands = set(
        next(a for a in build_parser()._actions if hasattr(a, "choices") and a.choices).choices
    )  # noqa: SLF001
    return made, tables, commands


def test_every_step_names_only_what_the_tool_has(flat) -> None:
    assert _problems(workflow.STEPS, *_world(flat)) == []


def test_a_step_that_names_a_file_an_output_a_table_or_a_command_the_tool_does_not_have_is_caught(flat) -> None:  # fmt: skip
    ok = workflow.STEPS[0]
    bad = [
        workflow.StepDef(
            ok.key,
            ok.title,
            ok.does,
            (workflow.Item(workflow.PROJECT, "logical/not-a-file.json"),),
            (),
            "",
            "",
        ),  # fmt: skip
        workflow.StepDef(
            ok.key,
            ok.title,
            ok.does,
            (),
            (workflow.Item(workflow.OUTPUT, "system/not-an-output.csv"),),
            "",
            "",
        ),  # fmt: skip
        workflow.StepDef(
            ok.key,
            ok.title,
            ok.does,
            (workflow.Item(workflow.CONFIG, "config/nothing.json"),),
            (),
            "",
            "",
        ),  # fmt: skip
        workflow.StepDef(
            ok.key, ok.title, ok.does, (workflow.Item(workflow.DATA, "no_such_table"),), (), "", ""
        ),  # fmt: skip
        workflow.StepDef(ok.key, ok.title, ok.does, (), (), "no-such-command", ""),
        workflow.StepDef(
            ok.key,
            ok.title,
            ok.does,
            (),
            (),
            "",
            "",
            (workflow.Inspect("x", "export-data table wire_sizing, nothing"),),
        ),  # fmt: skip
    ]
    world = _world(flat)
    for step in bad:
        assert len(_problems([step], *world)) == 1, step
    assert _problems([workflow.STEPS[3]], *world) == []


def test_the_manifest_item_is_what_write_outputs_makes(flat, tmp_path: Path) -> None:
    write_outputs(flat, tmp_path / "o", build_outputs(flat, drawings=False))
    assert (tmp_path / "o" / "manifest.json").is_file()
    assert (tmp_path / "o" / "system" / "asbuilt_report.md").is_file()  # the as-built step's output


def test_the_screens_take_their_step_words_from_the_same_table() -> None:
    from harness_design_studio.gui import next_step, strings
    from harness_design_studio.gui import workflow as bar

    assert set(workflow.PAGE_LABELS) <= set(workflow.KEYS) and set(workflow.BAR_LABELS) <= set(workflow.KEYS)  # fmt: skip
    assert tuple(workflow.PAGE_LABELS[k] for k in ("devices", "connect", "generate", "check", "outputs", "release")) == next_step.STEP_LABELS  # fmt: skip
    assert tuple(workflow.BAR_LABELS[k] for k in ("generate", "check", "release")) == (strings.STEP_GENERATE, strings.STEP_REVIEW, strings.STEP_RELEASE)  # fmt: skip
    assert bar.KEYS == ("generate", "review", "release")
    assert set(workflow.NEXT_KEY_STEP) == set(next_step.KEYS) - {"busy", "read_only"}
    assert set(workflow.NEXT_KEY_STEP.values()) <= set(workflow.KEYS)


# ---- the states, worked out from the project ---------------------------------------------------


def states(status) -> dict[str, str]:
    return {s.key: s.state for s in status}


def test_an_empty_project_is_blocked_by_the_steps_before(tmp_path: Path) -> None:
    project = templates.create_project(tmp_path / "b", "blank")
    status = workflow.workflow_status(project, tmp_path / "none")
    got = states(status)
    assert got["devices"] == "todo" and got["connect"] == "blocked"
    assert next(s for s in status if s.key == "connect").blocked_by == ("devices",)
    assert got["generate"] == "blocked" and got["check"] == "blocked" and got["as-built"] == "blocked"  # fmt: skip
    assert got["configure"] == "pending"  # the engineering values are not set


def test_a_generated_project_with_no_outputs_and_pending_values(tmp_path: Path) -> None:
    project = templates.create_project(tmp_path / "f", "flatsat")
    status = workflow.workflow_status(project, tmp_path / "none")
    got = states(status)
    assert (got["devices"], got["connect"], got["generate"]) == ("done", "done", "done")
    assert got["configure"] == "pending" and "4 engineering values" in next(s for s in status if s.key == "configure").detail  # fmt: skip
    assert got["build-data"] == "pending" and got["outputs"] == "todo"
    assert got["release"] == "blocked" and next(s for s in status if s.key == "release").blocked_by == ("outputs",)  # fmt: skip


def test_the_outputs_are_current_then_out_of_date_when_the_design_changes(tmp_path: Path) -> None:
    from harness_design_studio.core import edit
    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import evolve

    project = templates.create_project(tmp_path / "f", "flatsat")
    write_outputs(project, tmp_path / "f" / "outputs", build_outputs(project, drawings=False))
    check = workflow.Check(True, 0, 3)
    got = workflow.workflow_status(project, tmp_path / "f" / "outputs", check=check)
    assert states(got)["outputs"] == "done" and states(got)["check"] == "done"
    assert "3 warnings open" in next(s for s in got if s.key == "check").detail
    unit = next(iter(project.units.values()))
    edit.clone_with(project, [])  # (the copy is not used: the change is made on the project)
    apply_ops(project, [Put("units", evolve(unit, name=unit.name + " II"))])
    got = workflow.workflow_status(project, tmp_path / "f" / "outputs", check=check)
    assert states(got)["outputs"] == "stale" and states(got)["generate"] == "stale"
    assert states(workflow.workflow_status(project, tmp_path / "f" / "outputs", check=workflow.Check(True, 2)))["check"] == "attention"  # fmt: skip


def test_the_asbuilt_step_follows_the_records(flat, tmp_path: Path) -> None:
    got = states(workflow.workflow_status(flat, None, check=workflow.Check(True, 0)))
    assert got["as-built"] == "pending"  # one value recorded, many missing
    assert got["outputs"] == "todo"  # (the folder was not given)
    table = asbuilt.template_rows(flat, "W001")
    head = table[0]
    for row in table[1:]:
        if row[0] == "test" and row[2] == "T002":
            row[head.index("Continuity (ohm)")] = "1.4"
    from harness_design_studio.core import edit

    work = edit.clone_with(flat, [])
    apply_ops(work, asbuilt.plan_asbuilt_import(work, table).ops)
    status = workflow.workflow_status(work, None, check=workflow.Check(True, 0))
    step = next(s for s in status if s.key == "as-built")
    assert step.state == "attention" and "1 value out of the limit" in step.detail


# ---- the command and the interface ------------------------------------------------------------


def test_the_command_prints_the_steps_and_the_json_is_the_interface(tmp_path: Path, capsys) -> None:
    templates.create_project(tmp_path / "p", "flatsat")
    assert main(["workflow", str(tmp_path / "p")]) == 0
    out = capsys.readouterr().out
    assert out.startswith("1. Define the devices: done.") and "9. Record what was built: " in out
    assert "Uses: library/<category>.json" in out and "Look at: The candidates and the limits that sized each wire" in out  # fmt: skip
    assert "Blocked by: Write the outputs, Check the design." not in out  # (release waits for the outputs only)  # fmt: skip
    assert main(["workflow", str(tmp_path / "p"), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc == {"ok": True, **api.get_workflow(tmp_path / "p").to_dict()}
    assert [s["key"] for s in doc["steps"]] == list(workflow.KEYS)
    first = doc["steps"][0]
    assert first["consumes"][0] == {"kind": "project", "name": "library/<category>.json"}
    assert str(tmp_path) not in json.dumps(doc)
    assert main(["workflow", str(tmp_path / "p"), "--outputs", str(tmp_path / "elsewhere")]) == 0
