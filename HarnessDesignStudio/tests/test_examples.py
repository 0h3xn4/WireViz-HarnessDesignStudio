"""The bundled examples and templates are valid, current and really work with the tool."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import templates
from harness_design_studio.core.generate.engine import plan_generation
from harness_design_studio.core.imports import guess_mapping, plan_interface_import, read_table
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.resources import examples_path
from tools import build_examples

EXAMPLES = examples_path()
assert EXAMPLES is not None
PROJECTS = EXAMPLES / "projects"
TEMPLATES = EXAMPLES / "templates"


def _files(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_example_projects_are_what_the_build_script_writes(tmp_path: Path) -> None:
    """Run `python -m tools.build_examples` after changing a sample or the file format."""
    build_examples.build(tmp_path)
    assert _files(tmp_path) == _files(PROJECTS)


def test_every_listed_template_exists_and_has_no_errors() -> None:
    assert {t.name for t in templates.TEMPLATES} == {p.name for p in PROJECTS.iterdir()}
    for t in templates.TEMPLATES:
        loaded = load_project(PROJECTS / t.name)
        assert not loaded.has_errors, t.name
        assert loaded.project.meta.name == t.title, t.name


def test_first_steps_goes_through_the_whole_flow(tmp_path: Path) -> None:
    folder = tmp_path / "p"
    assert main(["new", str(folder), "--template", "first-steps"]) == 0
    assert main(["validate", str(folder)]) == 0
    assert main(["generate", str(folder)]) == 0
    assert main(["verify", str(folder)]) == 0
    assert main(["drc", str(folder)]) == 0
    assert main(["export", str(folder)]) == 0
    assert main(["verify", str(folder), "--outputs"]) == 0
    project = load_project(folder).project
    assert sorted(project.harnesses) == ["W001", "W002"]  # the templates below refer to these


def test_minimal_satellite_goes_through_the_whole_flow(tmp_path: Path) -> None:
    folder = tmp_path / "p"
    assert main(["new", str(folder), "--template", "minimal-satellite"]) == 0
    project = load_project(folder).project
    assert len(project.units) == 7 and len(project.interfaces) == 11
    assert all(i.redundancy == "nominal" for i in project.interfaces.values())
    for command in (["validate"], ["generate"], ["verify"], ["drc"], ["export"]):
        assert main([command[0], str(folder)]) == 0, command
    assert main(["verify", str(folder), "--outputs"]) == 0


def test_the_design_worksheet_names_only_real_unit_kinds_and_interface_types() -> None:
    from harness_design_studio.core import edit
    from harness_design_studio.core.samples import new_project

    text = (TEMPLATES / "design-worksheet.md").read_text(encoding="utf-8")
    for kind in ("computer", "computer_xl", "pdu", "battery", "solar_array", "actuator", "sensor",
                 "sun_sensor", "magnetorquer", "transceiver", "payload", "heater_panel", "pyro"):  # fmt: skip
        assert kind in edit.TEMPLATES and f"`{kind}`" in text, kind
    for interface_type in new_project("x").interface_types.values():
        assert interface_type.name in text, interface_type.name


def test_the_flatsat_example_opens_clean_and_stays_put_when_generated_again(tmp_path: Path) -> None:
    """The flatsat is shipped generated. A harness with ten or more segments or shields used to be
    reported as changed on every generation after a reload, because a saved project sorts them as
    text (S10 before S2) and the generator numbered them."""
    folder = tmp_path / "p"
    assert main(["new", str(folder), "--template", "flatsat"]) == 0
    loaded = load_project(folder)
    assert not loaded.has_errors
    project = loaded.project
    assert len(project.units) == 23 and len(project.interfaces) == 44
    assert (
        len(project.harnesses) == 8 and sum(len(h.wires) for h in project.harnesses.values()) == 103
    )
    assert max(len(h.shields) for h in project.harnesses.values()) >= 10
    plan = plan_generation(project)
    assert plan.ops == [] and not plan.report.changed and not plan.report.added
    assert main(["generate", str(folder)]) == 0
    assert main(["export", str(folder)]) == 0
    assert main(["verify", str(folder), "--outputs"]) == 0


def test_the_flatsat_has_no_rule_errors_and_says_its_numbers_are_examples() -> None:
    from harness_design_studio.core import drc

    project = load_project(PROJECTS / "flatsat").project
    assert [f.title for f in drc.run(project) if f.severity == "error"] == []
    assert "EXAMPLE" in project.meta.name
    assert project.config["derating"].placeholder  # example numbers never turn into reviewed values
    ground = {u.id for u in project.units.values() if u.subsystem == "egse"}
    assert ground == {"SCOE1", "GPSU1", "RFSU1"}


def test_the_flatsat_walkthrough_matches_the_example() -> None:
    import re

    project = load_project(PROJECTS / "flatsat").project
    text = (Path(__file__).resolve().parents[1] / "docs" / "FLATSAT_EXAMPLE.md").read_text(
        encoding="utf-8"
    )
    wires = sum(len(h.wires) for h in project.harnesses.values())
    assert f"{len(project.units)} units, {len(project.interfaces)} interfaces, " in text
    assert f"{len(project.harnesses)} harnesses, {wires} wires" in text
    for h in project.harnesses.values():
        row = re.search(rf"\| `{h.id}` \| [^|]+ \| (\d+) \|", text)
        assert row and int(row.group(1)) == len(h.wires), h.id
    named = set(re.findall(r"`([A-Z]+\d+)`", text))
    for prefix, first, last in re.findall(r"`([A-Z]+)(\d+)` to `\1(\d+)`", text):
        named |= {f"{prefix}{n}" for n in range(int(first), int(last) + 1)}
    assert set(project.units) <= named, sorted(set(project.units) - named)


def test_new_names_the_project_and_refuses_a_used_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "p"
    assert main(["new", str(folder), "--name", "Wheel study"]) == 0
    assert load_project(folder).project.meta.name == "Wheel study"
    assert main(["new", str(folder)]) == 2
    assert "not an empty folder" in capsys.readouterr().err
    assert main(["new", str(tmp_path / "q"), "--template", "nope"]) == 2
    assert main(["new"]) == 2
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["new", str(empty)]) == 0  # an empty folder is fine


def test_new_list_names_every_example(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["new", "--list"]) == 0
    out = capsys.readouterr().out
    assert all(t.name in out and t.summary in out for t in templates.TEMPLATES)


def test_templates_command_copies_everything_and_refuses_a_used_folder(tmp_path: Path) -> None:
    dest = tmp_path / "t"
    assert main(["templates", str(dest)]) == 0
    assert _files(dest) == _files(TEMPLATES)
    assert main(["templates", str(dest)]) == 2


@pytest.fixture
def generated(tmp_path: Path) -> Path:
    folder = tmp_path / "p"
    assert main(["new", str(folder), "--template", "first-steps"]) == 0
    assert main(["generate", str(folder)]) == 0
    return folder


def test_interface_template_imports(generated: Path) -> None:
    project = load_project(generated).project
    table = read_table(TEMPLATES / "interfaces.csv")
    plan = plan_interface_import(project, table, guess_mapping(table[0]))
    assert plan.rows and all(r.ok for r in plan.rows), [r.message for r in plan.rows]


def test_parts_lengths_and_netlist_templates_import(generated: Path) -> None:
    base = ["--dry-run"]
    assert main(["import-parts", str(generated), str(TEMPLATES / "approved-parts.csv"),
                 "--approved", "Approved", "--pending", "Review", "--rejected", "Rejected", *base]) == 0  # fmt: skip
    assert main(["import-lengths", str(generated), str(TEMPLATES / "segment-lengths.csv"),
                 "--unit", "mm", *base]) == 0  # fmt: skip
    assert main(["import-netlist", str(generated), str(TEMPLATES / "wheel-connectors.net"),
                 "--unit", "RW1", "--prefix", "J", "--connector", "J1=RW1-J01",
                 "--connector", "J2=RW1-J02", "--signal-map", str(TEMPLATES / "signal-map.csv"),
                 *base]) == 0  # fmt: skip


def test_imports_really_apply(generated: Path) -> None:
    assert main(["import-lengths", str(generated), str(TEMPLATES / "segment-lengths.csv"), "--unit", "mm"]) == 0  # fmt: skip
    assert main(["generate", str(generated)]) == 0
    harness = load_project(generated).project.harnesses["W001"]
    assert [s.length_m for s in harness.segments] == [0.85]


def test_demo_values_fill_in_the_checklist_and_stay_marked_as_placeholders(
    generated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for f in (TEMPLATES / "config-demo-values").glob("*.json"):
        shutil.copy(f, generated / "config" / f.name)
    capsys.readouterr()
    main(["config", str(generated)])
    out = capsys.readouterr().out
    assert "17 of 17 set" in out
    assert "still marked as placeholder" in out  # the demo values never look like reviewed data
    assert main(["generate", str(generated)]) == 0


def test_ampacity_demo_table_loads(generated: Path, capsys: pytest.CaptureFixture[str]) -> None:
    capsys.readouterr()
    # exit 1 because other values are still missing (that is what the command reports)
    assert main(["config", str(generated), "--ampacity-csv", str(TEMPLATES / "ampacity-DEMO-ONLY.csv")]) == 1  # fmt: skip
    assert "Loaded 6 gauges" in capsys.readouterr().out


def test_the_ci_script_runs_on_an_example(generated: Path) -> None:
    script = TEMPLATES / "ci" / "build.sh"
    assert subprocess.run(["sh", "-n", str(script)], check=False).returncode == 0
    env = {**os.environ, "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}"}
    done = subprocess.run(["sh", str(script), str(generated)], env=env, capture_output=True, text=True, check=False)  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr
    assert "build ok" in done.stdout


def test_the_github_workflow_template_uses_real_commands() -> None:
    text = (TEMPLATES / "ci" / "github-actions.yml").read_text(encoding="utf-8")
    for command in ("check", "generate", "verify", "export"):
        assert f"harness {command} design" in text

    # the same commands in the same order as build.sh (it once left out `drc`, the only one that
    # fails on design rule errors)
    def commands(source: str, folder: str) -> list[str]:
        return re.findall(rf"^\s*harness (\w+) {folder}(?=\s|$)", source, re.M)

    script = (TEMPLATES / "ci" / "build.sh").read_text()
    assert commands(text, "design") == commands(script, r'"\$DIR"')
    assert "drc" in commands(text, "design")


def test_the_template_readme_lists_every_file() -> None:
    text = (TEMPLATES / "README.md").read_text(encoding="utf-8")
    for path in TEMPLATES.rglob("*"):
        if path.is_file() and path.name != "README.md" and path.parent.name != "config-demo-values":
            assert path.name in text, path.name
    assert "config-demo-values/" in text


def test_a_failing_example_builder_keeps_the_old_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "blank").mkdir()
    (tmp_path / "blank" / "marker.txt").write_text("old")

    def boom() -> object:
        raise SystemExit("the builder failed")

    monkeypatch.setattr(build_examples, "BUILDERS", {"blank": boom})
    with pytest.raises(SystemExit):
        build_examples.build(tmp_path)
    assert (tmp_path / "blank" / "marker.txt").read_text() == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["blank"]  # no half-built folder left
