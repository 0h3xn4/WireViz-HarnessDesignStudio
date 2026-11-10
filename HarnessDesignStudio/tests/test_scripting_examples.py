# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""R11: the scripting examples run, and they use only the interface they teach.

`docs/examples/scripting/` holds three scripts. Each is run here (in this process, and one as a
program), so a change to the tool that breaks the interface breaks the test before it breaks a
reader's script. A second test reads the imports of every script and fails if one of them reaches
past `harness_design_studio.api.__all__`."""

import ast
import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from harness_design_studio import api

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "docs" / "examples" / "scripting"
SCRIPTS = sorted(FOLDER.glob("*.py"))


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"scripting_example_{name}", FOLDER / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# ---- they import only the interface ------------------------------------------------------------------


def test_there_are_three_scripts_and_a_readme() -> None:
    assert [p.name for p in SCRIPTS] == [
        "batch_projects.py", "explain_everything.py", "trade_study.py",
    ]  # fmt: skip
    readme = (FOLDER / "README.md").read_text(encoding="utf-8")
    for script in SCRIPTS:
        assert f"[`{script.name}`]({script.name})" in readme, script.name


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_a_script_uses_only_names_listed_in_the_interface(script: Path) -> None:
    tree = ast.parse(script.read_text(encoding="utf-8"))
    names: set[str] = set()
    module_aliases: set[str] = set()  # `from harness_design_studio import api` -> "api"
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                pytest.fail(f"{script.name}: a relative import")
            if module == "harness_design_studio":
                for alias in node.names:
                    assert alias.name == "api", f"{script.name}: {alias.name} is not the interface"
                    module_aliases.add(alias.asname or alias.name)
            elif module == "harness_design_studio.api":
                names.update(a.name for a in node.names)
            elif module.split(".")[0] == "harness_design_studio":
                pytest.fail(f"{script.name}: imports {module}, which is not the interface")
            else:
                assert module.split(".")[0] in sys.stdlib_module_names, f"{script.name}: {module}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top != "harness_design_studio", f"{script.name}: import {alias.name}"
                assert top in sys.stdlib_module_names, f"{script.name}: {alias.name}"
    for node in ast.walk(tree):  # api.something, when the module itself was imported
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in module_aliases
        ):
            names.add(node.attr)
    assert names, f"{script.name} uses nothing of the interface"
    unlisted = sorted(names - set(api.__all__))
    assert not unlisted, f"{script.name} uses {unlisted}, which api.__all__ does not list"


def test_the_check_would_catch_a_script_that_reaches_past_the_interface(tmp_path: Path) -> None:
    """The scan above is the guard; make sure it sees what it should."""
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from harness_design_studio.api import generate, not_a_name\n"
        "from harness_design_studio.core import edit\n"
    )
    tree = ast.parse(bad.read_text())
    froms = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert {a.name for a in froms[0].names} - set(api.__all__) == {"not_a_name"}
    assert froms[1].module == "harness_design_studio.core"


# ---- they run ------------------------------------------------------------------------------------------


def test_batch_projects(tmp_path: Path) -> None:
    module = load("batch_projects")
    target = tmp_path / "summary.csv"
    assert module.main([str(target)]) == 0
    table = rows(target)
    assert [r["project"] for r in table] == [
        "First steps: reaction wheel link", "Minimal satellite",
    ]  # fmt: skip
    assert tuple(table[0]) == module.COLUMNS
    assert all(r["generate_ok"] == "True" and r["open_errors"] == "0" for r in table)
    assert int(table[1]["wires"]) > int(table[0]["wires"]) > 0
    assert all(int(r["output_files"]) > 20 and len(r["model_hash"]) == 12 for r in table)
    text = target.read_text(encoding="utf-8")
    assert str(tmp_path) not in text
    again = tmp_path / "again.csv"
    module.main([str(again)])
    assert again.read_bytes() == target.read_bytes()  # the same design, the same bytes


def test_batch_projects_on_named_folders(tmp_path: Path) -> None:
    module = load("batch_projects")
    api.create_project(tmp_path / "mine", "first-steps")
    target = tmp_path / "mine.csv"
    assert module.main([str(target), str(tmp_path / "mine")]) == 0
    assert len(rows(target)) == 1
    assert (tmp_path / "mine" / "outputs" / "manifest.json").is_file()  # it changed the folder


def test_trade_study(tmp_path: Path) -> None:
    module = load("trade_study")
    target = tmp_path / "study.csv"
    assert module.main([str(target)]) == 0
    table = rows(target)
    assert [r["value"] for r in table] == ["0.5", "0.6", "0.8", "1.0"]
    refused, tight, mid, open_ = table
    assert refused["generate_ok"] == "False" and refused["gauges"] == ""
    assert int(refused["open_errors"]) > 0  # nothing fits: generate reports why
    assert all(r["generate_ok"] == "True" and r["open_errors"] == "0" for r in (tight, mid, open_))
    assert (
        len({tight["gauges"], mid["gauges"], open_["gauges"]}) == 3
    )  # the gauges follow the value
    assert float(open_["worst_voltage_drop_v"]) >= float(tight["worst_voltage_drop_v"]) > 0
    assert [p.name for p in tmp_path.iterdir()] == ["study.csv"]  # the copy was removed again


def _fresh(folder: Path) -> Path:
    api.create_project(folder, "flatsat")
    return folder


def test_trade_study_rejects_a_value_the_editor_rejects(tmp_path: Path) -> None:
    module = load("trade_study")
    folder = _fresh(tmp_path / "p")
    with pytest.raises(api.ConfigValueError):
        module.study(folder, (1.5,))


def test_explain_everything(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = load("explain_everything")
    out = tmp_path / "derivations"
    assert module.main([str(out)]) == 0
    printed = capsys.readouterr().out
    assert "derivations written to" in printed and "not set:" in printed
    document = json.loads((out / "derivations.json").read_text(encoding="utf-8"))
    assert document["derivations"] and document["project"]
    lines = (out / "derivations.csv").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(document["derivations"]) + 1
    folder = _fresh(tmp_path / "same")
    api.write_derivations(folder, tmp_path / "api")
    for name in ("derivations.json", "derivations.csv"):
        assert (out / name).read_bytes() == (tmp_path / "api" / name).read_bytes()


def test_a_script_runs_as_a_program(tmp_path: Path) -> None:
    target = tmp_path / "summary.csv"
    done = subprocess.run(  # noqa: S603 (tests only: our own interpreter and a fixed script)
        [sys.executable, str(FOLDER / "batch_projects.py"), str(target)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        check=False,
    )
    assert done.returncode == 0, done.stderr[-1500:]
    assert len(rows(target)) == 2
