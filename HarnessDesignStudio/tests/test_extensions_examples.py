"""S8: the examples in `docs/examples/extensions/` are the ones the manual explains, and they work:
a declarative rule and a Python rule are added to a project without editing the tool."""

import json
import shutil
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import derive, drc
from harness_design_studio.core.extensions import manager, plugins, trust
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import evolve
from harness_design_studio.core.outputs.build import build_outputs
from tests.ext_helpers import generated

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "examples" / "extensions"


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "p"
    save_project(generated(tmp_path / "g"), folder)
    shutil.copytree(EXAMPLES, folder / "extensions", ignore=shutil.ignore_patterns("README.md"))
    plugins.forget_loaded()
    manager._RUNTIMES.clear()
    return folder


def test_the_example_files_are_valid_and_listed_in_their_readme() -> None:
    readme = (EXAMPLES / "README.md").read_text(encoding="utf-8")
    shipped = sorted(
        p.relative_to(EXAMPLES).as_posix()
        for p in EXAMPLES.rglob("*")
        if p.is_file() and p.name != "README.md"
    )
    assert shipped == [
        "enabled.json",
        "minimum-wire-gauge-power.json",
        "plugins/duplicate-signal-wires.py",
        "power-wire-table.json",
    ]
    for rel in shipped:
        assert f"`{rel}`" in readme, rel
    enabled = json.loads((EXAMPLES / "enabled.json").read_text())
    assert enabled["declarative"] == [
        "minimum-wire-gauge-power.json",
        "power-wire-table.json",
    ] and enabled["plugins"] == ["duplicate-signal-wires"]


def test_the_declarative_rule_minimum_wire_gauge_for_power(project_dir: Path) -> None:
    project = load_project(project_dir).project
    ext = project.extensions
    assert ext is not None and not [
        i for i in ext.issues if "duplicate-signal-wires" not in i.message
    ]
    assert [(f.name, f.status) for f in ext.files] == [
        ("minimum-wire-gauge-power", "applied"),
        ("power-wire-table", "applied"),
    ]
    hit = {f.object_id: f for f in drc.run(project) if f.rule == "x-min-gauge-power"}
    # the flatsat has power wires of AWG 24 and 26 and none thicker than the example's AWG 22
    assert (
        hit["W001-001"].title
        == "Wire W001-001 (PWR) is AWG 24, thinner than the AWG 22 allowed for power"
    )
    assert (
        hit["W001-009"].title
        == "Wire W001-009 (PWR) is AWG 26, thinner than the AWG 22 allowed for power"
    )
    assert hit["W001-001"].severity == "warning"
    (d,) = derive.explain_finding(project, "x-min-gauge-power", "W001-001")
    assert d.check is not None and (d.check.actual, d.check.limit, d.check.margin) == (
        24.0,
        22.0,
        -2.0,
    )
    assert [i.name for i in d.inputs] == [
        "wire.category",
        "wire.gauge_awg",
        "parameter thinnest_awg",
    ]
    assert d.inputs[2].source.startswith(
        "extensions/minimum-wire-gauge-power.json: parameters.thinnest_awg"
    )
    # a thicker wire passes; a signal wire is not what the rule is about
    for h in project.harnesses.values():
        for n, w in enumerate(h.wires):
            if w.id == "W001-001":
                h.wires[n] = evolve(w, gauge_awg=20)
    assert "W001-001" not in {
        f.object_id for f in drc.run(project) if f.rule == "x-min-gauge-power"
    }
    power = {
        w.id
        for h in project.harnesses.values()
        for w in h.wires
        if (i := project.interfaces.get(w.interface_id or ""))
        and project.interface_types[i.type_id].category == "power"
    }
    assert {f.object_id for f in drc.run(project) if f.rule == "x-min-gauge-power"} <= power


def test_the_declarative_table_and_the_own_ampacity_rule(project_dir: Path) -> None:
    project = load_project(project_dir).project
    files = build_outputs(project, drawings=False).files
    text = files["system/extensions/power-wires.csv"].decode()
    lines = text.splitlines()
    assert (
        lines[1]
        == "Wire,Harness,Signal,Gauge (AWG),Cross-section (mm2),Current (A),Table ampacity (A)"
    )
    assert "W001-001,W001,PWR,24,0.205,0.8,5" in lines
    assert "W001-009,W001,PWR,26,0.129,0.3,3.5" in lines
    assert all(row.split(",")[0] for row in lines[2:])
    # the flatsat's currents stay within the example's table: the rule is silent, and not "not checked"
    assert not [f for f in drc.run(project) if f.rule == "x-own-ampacity"]
    from harness_design_studio.core.drc import by_rule

    assert next(
        r for r in by_rule.run_by_rule(project) if r.rule_id == "x-own-ampacity"
    ).status in ("pass", "not_checked")


def test_the_python_rule_is_added_without_editing_the_tool(
    project_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # two wires of the first harness carry the same signal between the same two connectors
    project = load_project(project_dir).project
    h = project.harnesses["W001"]
    w = h.wires[0]
    h.wires.append(evolve(w, id="W001-099"))
    save_project(project, project_dir)
    assert main(["drc", str(project_dir)]) in (0, 1)
    out = capsys.readouterr().out
    assert "x-duplicate-signal-wires" not in out  # enabled, not trusted: nothing of it runs
    assert "x-extension-problem" in out
    assert main(["trust", str(project_dir), "duplicate-signal-wires", "--yes"]) == 0
    capsys.readouterr()
    assert main(["drc", str(project_dir)]) in (0, 1)
    out = capsys.readouterr().out
    assert (
        "x-duplicate-signal-wires" in out
        and "W001 has 2 wires for PWR from W001-P2 to W001-P11 (W001-001, W001-099)" in out
    )
    assert "x-extension-problem" not in out
    src = (
        EXAMPLES / "plugins" / "duplicate-signal-wires.py"
    ).read_bytes()  # the bytes on disk, whatever the line ends
    assert trust.is_trusted("duplicate-signal-wires", plugins.sha256_bytes(src))


def test_the_examples_in_the_extensions_command(
    project_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["trust", str(project_dir), "duplicate-signal-wires", "--yes"]) == 0
    capsys.readouterr()
    assert main(["extensions", str(project_dir), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    ext_rules = {
        i["name"]: i for i in doc["items"] if i["kind"] == "rule" and i["source"] != "built-in"
    }
    assert set(ext_rules) == {"x-min-gauge-power", "x-own-ampacity", "x-duplicate-signal-wires"}
    assert {
        i["name"] for i in doc["items"] if i["kind"] == "table" and i["source"] != "built-in"
    } == {"power-wires"}
    prov = [(r[0], r[2]) for r in manager.loaded(load_project(project_dir).project)]
    assert prov == [
        ("minimum-wire-gauge-power", "declarative"),
        ("power-wire-table", "declarative"),
        ("duplicate-signal-wires", "plugin"),
    ]


def test_the_run_record_and_the_open_data_name_the_extensions_in_force(
    project_dir: Path, tmp_path: Path
) -> None:
    """S5 meets S8: run_record.json lists every enabled data file and loaded plug-in (name, version,
    kind, file, SHA-256); provenance.json of `export-data` does too; a project without extensions
    has an empty list and no key, and the model hash is the same either way."""
    from harness_design_studio.core import open_data, run_record
    from harness_design_studio.core.io.layout import model_hash

    assert main(["trust", str(project_dir), "duplicate-signal-wires", "--yes"]) == 0
    project = load_project(project_dir).project
    record = run_record.make(project, operator="tester")
    names = [(e["name"], e["kind"]) for e in record["extensions"]]
    assert names == [
        ("minimum-wire-gauge-power", "declarative"),
        ("power-wire-table", "declarative"),
        ("duplicate-signal-wires", "plugin"),
    ]
    assert all(len(e["sha256"]) == 64 and e["version"] == "1.0.0" for e in record["extensions"])
    assert str(project_dir) not in json.dumps(record)
    prov = json.loads(open_data.data_files(project)[open_data.PROVENANCE])
    assert [e["name"] for e in prov["extensions"]] == [n for n, _ in names]
    # not enabled: nothing is listed, in either place
    (project_dir / "extensions" / "enabled.json").write_text(
        json.dumps({"format": "harness-design-studio-extensions-enabled", "format_version": 1})
    )
    plain = load_project(project_dir).project
    assert run_record.make(plain, operator="tester")["extensions"] == []
    assert "extensions" not in json.loads(open_data.data_files(plain)[open_data.PROVENANCE])
    assert model_hash(plain) == model_hash(project)  # the extensions are not project data
    shutil.rmtree(project_dir / "extensions")
    assert model_hash(load_project(project_dir).project) == model_hash(project)
