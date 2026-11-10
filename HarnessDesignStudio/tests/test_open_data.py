# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""S5: open data. Every result as JSON and CSV, reproducible from the files alone, byte for byte.

What is checked: a small script that reads only the exported files (`docs/examples/open-data/
reproduce.py`: no Harness Design Studio code) recomputes the current limit, the voltage drop, the
gauge adequacy and the bill of materials of every packaged example and agrees with the files to 9
decimals; the same design written twice gives the same bytes; no data file holds a time, a user
name or a path; the run record exists only when asked, holds what it should, and is in no hash; the
tables equal the derivations and the output tables they are made from; the JSON and CSV files hold
the same rows; and the files that the importers know are read back by them."""

import ast
import csv
import importlib.util
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from harness_design_studio import api
from harness_design_studio.cli.main import main
from harness_design_studio.core import run_record, templates
from harness_design_studio.core.derive import explain_wire
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Project, evolve
from harness_design_studio.core.open_data import all_tables, data_files, num
from harness_design_studio.core.outputs import tables as out_tables
from harness_design_studio.core.outputs.build import build_outputs

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "examples" / "open-data" / "reproduce.py"
EXAMPLES = ("first-steps", "minimal-satellite", "small-satellite", "flatsat")


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("open_data_reproduce", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def engineer(project: Project, flatsat: Project) -> None:
    """Give an example that ships without engineering values the example values of the flatsat
    (derating, generation), a current on every interface and a length on every
    routing segment, then generate: so that every example has numbers to reproduce."""
    project.config = {
        **project.config,
        **{k: flatsat.config[k] for k in ("derating", "generation")},
    }
    for iid, i in list(project.interfaces.items()):
        if i.max_current_a is None:
            power = project.interface_types[i.type_id].category == "power"
            project.interfaces[iid] = evolve(i, max_current_a=0.8 if power else 0.1)
    generate_project(project)  # makes the harnesses and their routing segments
    for hid, h in list(project.harnesses.items()):
        segments = [evolve(s, length_m=0.5 + 0.25 * n) for n, s in enumerate(h.segments)]
        project.harnesses[hid] = evolve(h, segments=segments)
    generate_project(project)  # again, now that the lengths are known: the gauges are decided


@pytest.fixture(scope="module")
def folders(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Name -> a project folder, saved: each example as it ships, and each with example values."""
    base = tmp_path_factory.mktemp("open-data")
    made: dict[str, Path] = {}
    flat = templates.create_project(base / "flatsat", "flatsat")
    made["flatsat"] = base / "flatsat"
    for name in EXAMPLES[:-1]:
        project = templates.create_project(base / name, name)
        if not project.harnesses:
            generate_project(project)
            save_project(project, base / name)
        made[name] = base / name
        engineered = templates.create_project(base / f"{name}-numbers", name)
        engineer(engineered, flat)
        save_project(engineered, base / f"{name}-numbers")
        made[f"{name}-numbers"] = base / f"{name}-numbers"
    return made


@pytest.fixture(scope="module")
def exported(folders: dict[str, Path], tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for name, folder in folders.items():
        target = tmp_path_factory.mktemp(f"data-{name}")
        api.export_data(folder, target)
        out[name] = target
    return out


def rows_of(folder: Path, name: str) -> list[dict[str, Any]]:
    doc = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
    assert doc["format"] == 1 and doc["table"] == name
    return list(doc["rows"])


# ---- reproduction from the exported files alone ----------------------------------------------------


@pytest.mark.parametrize("name", [*EXAMPLES[:-1], "flatsat"])
def test_a_colleague_can_reproduce_the_numbers_of_each_example(
    name: str, exported: dict[str, Path]
) -> None:
    script = load_script()
    for variant in [name] if name == "flatsat" else [name, f"{name}-numbers"]:
        result = script.reproduce(exported[variant])
        assert result["differences"] == [], (variant, result["differences"][:3])
    # the examples with example values have numbers for every kind of recomputation
    seen = script.reproduce(exported["flatsat" if name == "flatsat" else f"{name}-numbers"])[
        "recomputed"
    ]
    assert seen["limits"] > 0 and seen["drops"] > 0 and seen["gauges"] > 0, name
    assert seen["areas"] > 0 and seen["bom_lines"] > 0, name


def test_the_script_is_independent_of_the_tool(exported: dict[str, Path]) -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            modules.add((node.module or "").split(".")[0])
    assert modules <= {"csv", "json", "math", "sys", "pathlib"}, modules
    # and it runs as a program in an isolated interpreter, on the files only
    done = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(exported["flatsat"])],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr
    assert "agrees with the files to 9 decimals" in done.stdout


def test_the_script_notices_a_changed_number(exported: dict[str, Path], tmp_path: Path) -> None:
    copy = tmp_path / "copy"
    copy.mkdir()
    for f in exported["flatsat"].iterdir():
        (copy / f.name).write_bytes(f.read_bytes())
    path = copy / "wire_sizing.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    header = next(csv.reader([lines[0]]))
    cells = next(csv.reader([lines[1]]))
    cells[header.index("Voltage drop (V)")] = "9.5"
    lines[1] = ",".join(f'"{c}"' if "," in c else c for c in cells)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = load_script().reproduce(copy)
    assert any("voltage drop" in d for d in result["differences"]), result["differences"]
    assert subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(copy)], capture_output=True, check=False
    ).returncode == 1  # fmt: skip


def test_the_numbers_are_the_numbers_of_the_derivations(folders: dict[str, Path]) -> None:
    project = load_project(folders["flatsat"]).project
    by_wire = {r["wire"]: r for r in all_rows(project, "wire_sizing")}
    checked = 0
    for h in project.harnesses.values():
        for w in h.wires:
            row = by_wire[w.id]
            ds = {d.id: d for d in explain_wire(project, w.id)}
            for key, kind in (("limit_a", "wire-current-limit"), ("voltage_drop_v", "wire-voltage-drop"), ("length_m", "wire-length")):  # fmt: skip
                expected = ds[kind].value
                got = row[key]
                assert (got is None) == (expected is None), (w.id, key)
                if expected is not None:
                    assert got == num(expected) and abs(got - expected) < 1e-9, (w.id, key)
                    checked += 1
            check = ds["wire-voltage-drop"].check
            if check is not None:
                assert row["max_voltage_drop_v"] == num(check.limit)
                assert row["drop_margin_v"] == num(check.margin)
                assert row["drop_verdict"] == ("pass" if check.passes else "fail")
    assert checked > 100


def all_rows(project: Project, name: str) -> list[dict[str, Any]]:
    (table,) = [t for t in all_tables(project) if t.name == name]
    return table.rows


def test_rule_results_carry_actual_limit_margin_and_verdict(folders: dict[str, Path]) -> None:
    project = load_project(folders["flatsat"]).project
    rows = all_rows(project, "rule_results")
    rules = {r["rule"] for r in rows}
    assert {"current-over-wire", "voltage-drop", "current-over-contact"} <= rules
    done = [r for r in rows if r["verdict"] != "not checked"]
    assert done
    for r in done:
        assert r["actual"] is not None and r["limit"] is not None and r["unit"]
        assert abs((r["limit"] - r["actual"]) - r["margin"]) < 1e-9, r
        assert r["verdict"] == ("pass" if r["margin"] >= -1e-9 else "fail"), r
    findings = all_rows(project, "findings")
    assert all(set(f) >= {"actual", "limit", "margin", "unit"} for f in findings)


def test_the_bill_of_materials_is_the_sum_of_its_contributions(folders: dict[str, Path]) -> None:
    project = load_project(folders["flatsat"]).project
    bom = all_rows(project, "bom")
    contributions = all_rows(project, "bom_contributions")
    text = out_tables.bom(project, [project.harnesses[i] for i in sorted(project.harnesses)])
    assert [(r["part"], r["unit"]) for r in bom] == [(r[0], r[7]) for r in text[1:]]
    for row, line in zip(bom, text[1:], strict=True):
        assert float(line[6]) == pytest.approx(row["quantity"], abs=1e-9)
        total = sum(
            c["amount"]
            for c in contributions
            if (c["part"], c["unit"]) == (row["part"], row["unit"])
        )
        assert total == pytest.approx(row["quantity"], abs=1e-9), row["part"]


def test_every_table_is_there_with_units_in_the_headers(
    exported: dict[str, Path], folders: dict[str, Path]
) -> None:
    names = {t.name for t in all_tables(load_project(folders["flatsat"]).project)}
    assert names == {
        "wire_sizing", "segmentation_groups", "segmentation_interfaces", "pin_allocation",
        "rule_results", "readiness", "lengths", "segment_lengths", "parts", "mass", "mass_wires",
        "bom", "bom_contributions", "findings", "test_limits", "settings",
    }  # fmt: skip
    folder = exported["flatsat"]
    assert {p.name for p in folder.iterdir()} == {
        *(f"{n}.json" for n in names), *(f"{n}.csv" for n in names),
        "configuration.json", "provenance.json", "README.txt",  # the notice (D-210)
    }  # fmt: skip
    head = (folder / "wire_sizing.csv").read_text(encoding="utf-8").splitlines()[0]
    for expected in ("Current (A)", "Gauge (AWG)", "Cross-section (mm²)", "Length (m)", "Voltage drop (V)", "Resistivity (Ω·m)"):  # fmt: skip
        assert expected in head
    doc = json.loads((folder / "wire_sizing.json").read_text(encoding="utf-8"))
    units = {c["key"]: c["unit"] for c in doc["columns"]}
    assert units["area_mm2"] == "mm²" and units["current_a"] == "A" and doc["format"] == 1
    assert doc["tool_version"] and len(doc["model_hash"]) == 64


def test_the_json_and_the_csv_hold_the_same_rows(exported: dict[str, Path]) -> None:
    folder = exported["flatsat"]
    for path in sorted(folder.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if "rows" not in doc:
            continue
        with (folder / f"{path.stem}.csv").open(newline="", encoding="utf-8") as handle:
            lines = list(csv.reader(handle))
        assert lines[0] == [c["header"] for c in doc["columns"]], path.name
        assert len(lines) - 1 == len(doc["rows"]), path.name
        for cells, row in zip(lines[1:], doc["rows"], strict=True):
            for cell, col in zip(cells, doc["columns"], strict=True):
                value = row[col["key"]]
                if value is None:
                    assert cell == "", (path.name, col["key"])
                elif isinstance(value, bool):
                    assert cell == ("yes" if value else "no")
                elif isinstance(value, int | float):
                    assert float(cell) == value, (path.name, col["key"])
                elif isinstance(value, str):
                    assert cell.lstrip("'") == value.lstrip("'"), (path.name, col["key"])
                else:
                    assert json.loads(cell) == value, (path.name, col["key"])


def test_settings_and_configuration_are_what_the_tool_used(folders: dict[str, Path]) -> None:
    project = load_project(folders["flatsat"]).project
    from harness_design_studio.core import settings

    out = {r["id"]: r for r in all_rows(project, "settings")}
    assert set(out) == {r.setting.id for r in settings.rows(project)}
    assert out["model.service_loops_per_wire"]["origin"] == "default"
    assert out["derating.ampacity_a_by_awg"]["origin"] == "project"
    assert out["derating.ampacity_a_by_awg"]["placeholder"] == "yes"
    config = json.loads(data_files(project)["configuration.json"])
    names = [f["name"] for f in config["files"]]
    assert names == sorted(project.config)
    derating = next(f for f in config["files"] if f["name"] == "derating")
    assert derating["placeholder"] is True
    assert derating["values"] == project.config["derating"].values


def test_provenance_names_the_tool_the_design_and_every_other_file(
    folders: dict[str, Path],
) -> None:
    project = load_project(folders["flatsat"]).project
    files = data_files(project)
    doc = json.loads(files["provenance.json"])
    assert doc["model_hash"] == model_hash(project) and doc["tool_version"]
    assert doc["imports"] == []  # kept in the project from stage S6 on
    listed = {f["path"]: f for f in doc["files"]}
    assert set(listed) == set(files) - {"provenance.json"}
    import hashlib

    for name, f in listed.items():
        assert f["sha256"] == hashlib.sha256(files[name]).hexdigest() and f["bytes"] == len(files[name])  # fmt: skip
    assert doc["placeholder_config"] == project.placeholder_configs()


# ---- the same bytes, and nothing that varies ----------------------------------------------------


def test_the_same_design_written_twice_gives_the_same_bytes(
    folders: dict[str, Path], tmp_path: Path
) -> None:
    for name in ("flatsat", "first-steps"):
        a, b = tmp_path / f"{name}-a", tmp_path / f"{name}-b"
        api.export_data(folders[name], a)
        api.export_data(load_project(folders[name]).project, b)  # a loaded project: the same
        assert main(["export-data", str(folders[name]), "--out", str(tmp_path / f"{name}-c")]) == 0
        c = tmp_path / f"{name}-c"
        names = sorted(p.name for p in a.iterdir())
        assert names == sorted(p.name for p in b.iterdir()) == sorted(p.name for p in c.iterdir())
        for n in names:
            assert (a / n).read_bytes() == (b / n).read_bytes() == (c / n).read_bytes(), n


def test_no_data_file_holds_a_time_a_user_or_a_path(
    folders: dict[str, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import getpass

    monkeypatch.setenv("HARNESS_AUTHOR", "Ada Operator-Name")
    out = tmp_path / "data"
    api.export_data(folders["flatsat"], out)
    user = getpass.getuser()
    stamp = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
    for path in sorted(out.iterdir()):
        text = path.read_text(encoding="utf-8")
        assert str(tmp_path) not in text and str(folders["flatsat"]) not in text, path.name
        assert "Ada Operator-Name" not in text, path.name
        assert not stamp.search(text), path.name
        assert "time_utc" not in text and "operator" not in text, path.name
        assert not re.search(r"(?<![\w.-])[A-Za-z]:\\|/home/|/Users/", text), path.name
        if len(user) > 3:
            assert f"/{user}/" not in text, path.name


def test_a_symlinked_data_folder_is_refused(folders: dict[str, Path], tmp_path: Path) -> None:
    real, link = tmp_path / "real", tmp_path / "link"
    real.mkdir()
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("this system does not make links")
    with pytest.raises(api.SaveError):
        api.export_data(folders["first-steps"], link)
    assert list(real.iterdir()) == []


# ---- the run record ----------------------------------------------------------------------------


def test_the_run_record_has_what_it_should_and_no_path(
    folders: dict[str, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-git-config"))
    project = load_project(folders["first-steps"]).project
    clock = datetime(2026, 11, 3, 9, 15, 42, 987654, tzinfo=UTC)
    record = run_record.make(project, operator="A. Engineer", now=lambda: clock, environ={})
    assert record == {
        "format": 1,
        "time_utc": "2026-11-03T09:15:42Z",
        "operator": "A. Engineer",
        "tool": "harness-design-studio",
        "tool_version": record["tool_version"],
        "platform": record["platform"],
        "python": record["python"],
        "model_hash": model_hash(project),
        "extensions": [],
    }
    assert record["tool_version"] and record["platform"] and record["python"].count(".") == 2
    # another zone is written as UTC
    other = datetime(2026, 11, 3, 10, 15, 42, tzinfo=timezone(timedelta(hours=1)))
    assert run_record.make(project, now=lambda: other, environ={})["time_utc"] == "2026-11-03T09:15:42Z"  # fmt: skip
    path = run_record.write(tmp_path / "x" / "y", record)
    assert path.name == "run_record.json" and json.loads(path.read_text(encoding="utf-8")) == record
    assert str(tmp_path) not in path.read_text(encoding="utf-8")
    assert path.read_bytes() == run_record.to_bytes(record)


def test_the_operator_is_the_given_name_or_the_environment_never_git_or_the_system(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "gitconfig"
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    env = {"HARNESS_AUTHOR": "From Env", "USER": "sysuser"}
    assert run_record.resolve_operator("  Given  ", environ=env) == "Given"
    assert run_record.resolve_operator(None, environ=env) == "From Env"
    config.write_text('[user]\n\tname = "Git Name"\n', encoding="utf-8")
    assert run_record.resolve_operator(None, environ={"USER": "sysuser"}) == "unknown"  # no Git
    assert run_record.resolve_operator("", environ=env) == "From Env"
    config.write_text("", encoding="utf-8")
    assert run_record.resolve_operator(None, environ={"USER": "sysuser"}) == "unknown"  # D-220
    assert run_record.resolve_operator(None, environ={"USERNAME": "winuser"}) == "unknown"
    assert run_record.resolve_operator(None, environ={"LOGNAME": "lname"}) == "unknown"
    assert run_record.resolve_operator(None, environ={}) == "unknown"
    assert run_record.resolve_operator("   ", environ={}) == "unknown"


def files_under(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}  # fmt: skip


def test_a_run_record_is_written_only_when_asked(tmp_path: Path) -> None:
    folder = tmp_path / "p"
    api.create_project(folder, "first-steps")
    assert main(["generate", str(folder)]) == 0
    assert main(["export", str(folder)]) == 0
    assert main(["export-data", str(folder), "--out", str(tmp_path / "d")]) == 0
    assert not list(tmp_path.rglob("run_record.json"))
    assert api.generate(folder).ok and api.export(folder).ok
    api.export_data(folder, tmp_path / "e")
    assert not list(tmp_path.rglob("run_record.json"))


def test_the_run_record_is_next_to_the_outputs_and_in_no_hash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plain, asked = tmp_path / "plain", tmp_path / "asked"
    api.create_project(plain, "first-steps")
    api.create_project(asked, "first-steps")
    assert main(["generate", str(plain)]) == 0
    assert main(["generate", str(asked), "--run-record", "--author", "Ada"]) == 0
    assert "run_record.json" in capsys.readouterr().out
    record = json.loads((asked / "outputs" / "run_record.json").read_text(encoding="utf-8"))
    assert record["operator"] == "Ada" and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", record["time_utc"])  # fmt: skip
    # the project itself is the same bytes either way, and the record is not part of the model
    assert model_hash(load_project(plain).project) == model_hash(load_project(asked).project)
    assert model_hash(load_project(asked).project) == record["model_hash"]
    # the exported files are the same bytes with and without the record; the manifest does not list it
    assert (
        main(["export", str(plain)]) == 0
        and main(["export", str(asked), "--run-record", "--json"]) == 0
    )
    out = capsys.readouterr().out
    assert json.loads(out[out.index("{") :])["run_record"] == "run_record.json"
    a, b = files_under(plain / "outputs"), files_under(asked / "outputs")
    assert "run_record.json" in b and "run_record.json" not in a
    assert {k: v for k, v in b.items() if k != "run_record.json"} == a
    manifest = json.loads(b["manifest.json"])
    assert "run_record.json" not in {f["path"] for f in manifest["files"]}
    assert b"run_record" not in b["manifest.json"]
    # and the self-check of the outputs does not call it an unlisted file
    assert api.verify(asked, outputs=True).issues == api.verify(plain, outputs=True).issues
    assert str(tmp_path) not in (asked / "outputs" / "run_record.json").read_text(encoding="utf-8")


def test_export_data_with_a_run_record(
    folders: dict[str, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "d"
    assert main(["export-data", str(folders["first-steps"]), "--out", str(out), "--run-record", "--author", "Ada", "--json"]) == 0  # fmt: skip
    doc = json.loads(capsys.readouterr().out)
    assert list(doc) == ["ok", "count", "model_hash", "files", "run_record"]
    assert doc["run_record"] == "run_record.json" and doc["count"] == len(doc["files"]) == 35
    assert (out / "run_record.json").is_file() and "run_record.json" not in doc["files"]
    assert json.loads((out / "run_record.json").read_text(encoding="utf-8"))["operator"] == "Ada"
    # the data files do not change with it
    other = tmp_path / "e"
    api.export_data(folders["first-steps"], other)
    assert {n: (out / n).read_bytes() for n in doc["files"]} == {n: (other / n).read_bytes() for n in doc["files"]}  # fmt: skip
    # --author alone is a mistake
    assert main(["export-data", str(folders["first-steps"]), "--out", str(tmp_path / "x"), "--author", "Ada"]) == 2  # fmt: skip
    assert not (tmp_path / "x").exists()
    assert main(["export", str(folders["first-steps"]), "--out", str(tmp_path / "y"), "--author", "Ada"]) == 2  # fmt: skip


def test_the_written_outputs_keep_the_plain_gauge(folders: dict[str, Path]) -> None:
    """D2: the cross-section is for the screen; no file of the outputs holds it."""
    project = load_project(folders["flatsat"]).project
    built = build_outputs(project, drawings=True)
    for name, data in built.files.items():
        if name.endswith((".csv", ".yaml", ".md", ".svg", ".json")):
            assert "mm²".encode() not in data or name.endswith("provenance.json"), name
            assert not re.search(rb"AWG \d+ \(", data), name


# ---- exports the tool can read back ----------------------------------------------------------------


def test_the_segment_lengths_file_is_read_back_by_import_lengths(
    folders: dict[str, Path],
    exported: dict[str, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    name = "small-satellite-numbers"
    copy = tmp_path / "copy"
    api.create_project(copy, "small-satellite")
    api.generate(copy)
    source = exported[name] / "segment_lengths.csv"
    rows = rows_of(exported[name], "segment_lengths")
    assert rows and all(r["length_m"] is not None for r in rows)
    assert (
        main(["import-lengths", str(copy), str(source), "--unit", "m", "--dry-run", "--json"]) == 0
    )
    doc = json.loads(capsys.readouterr().out)
    assert doc["ready"] == len(rows) and doc["problems"] == 0
    assert main(["import-lengths", str(copy), str(source), "--unit", "m"]) == 0
    capsys.readouterr()
    imported = load_project(copy).project
    original = load_project(folders[name]).project
    for hid, h in original.harnesses.items():
        for s in h.segments:
            got = {x.id: x.length_m for x in imported.harnesses[hid].segments}
            assert got[s.id] == s.length_m, (hid, s.id)


def test_the_parts_file_is_read_back_by_import_parts(
    folders: dict[str, Path],
    exported: dict[str, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    copy = tmp_path / "copy"
    api.create_project(copy, "flatsat")
    source = exported["flatsat"] / "parts.csv"
    original = load_project(folders["flatsat"]).project
    # a part of the copy is changed first, so the import has something to put back
    changed = load_project(copy).project
    pid = next(p for p, part in sorted(changed.parts.items()) if part.mass_g is not None)
    changed.parts[pid] = evolve(changed.parts[pid], mass_g=999.0)
    save_project(changed, copy)
    args = ["import-parts", str(copy), str(source), "--approved", "approved", "--pending", "pending", "--rejected", "not_approved"]  # fmt: skip
    assert main([*args, "--dry-run"]) == 0
    capsys.readouterr()
    assert main(args) == 0
    capsys.readouterr()
    got = load_project(copy).project.parts
    for part_id, part in original.parts.items():
        assert got[part_id].mass_g == part.mass_g, part_id
        assert got[part_id].mass_per_m_g == part.mass_per_m_g
        assert got[part_id].conductors == part.conductors
        assert got[part_id].approval == part.approval


def test_the_stamp_free_files_have_no_comment_line_for_a_reader_to_skip(
    exported: dict[str, Path],
) -> None:
    for path in exported["flatsat"].glob("*.csv"):
        assert not path.read_text(encoding="utf-8").startswith("#"), path.name


# ---- the interface -----------------------------------------------------------------------------------


def test_the_api_result_and_the_command_agree(
    folders: dict[str, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = api.export_data(folders["flatsat"], tmp_path / "a")
    assert result.count == len(result.files) == 35 and result.run_record == ""
    assert list(result.files) == sorted(result.files)
    assert (
        main(["export-data", str(folders["flatsat"]), "--out", str(tmp_path / "b"), "--json"]) == 0
    )
    assert json.loads(capsys.readouterr().out) == {"ok": True, **result.to_dict()}
    text = main(["export-data", str(folders["flatsat"]), "--out", str(tmp_path / "c")])
    assert text == 0 and f"{result.count} data files written to" in capsys.readouterr().out
    # a project that cannot be read is refused as the other commands refuse it
    assert main(["export-data", str(tmp_path / "missing"), "--out", str(tmp_path / "d")]) == 2
    assert not (tmp_path / "d").exists()


# ---- imports in the provenance, and the stamp line --------------------------------------------------


def test_provenance_lists_the_files_the_project_imported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "p"
    api.create_project(folder, "first-steps")
    assert api.generate(folder).ok
    lengths = tmp_path / "segment-lengths.csv"
    segs = [
        (h.id, s.id) for h in load_project(folder).project.harnesses.values() for s in h.segments
    ]
    lengths.write_text("Harness,Segment,Length\n" + "".join(f"{h},{s},850\n" for h, s in segs), encoding="utf-8")  # fmt: skip
    assert main(["import-lengths", str(folder), str(lengths), "--unit", "mm"]) == 0
    capsys.readouterr()
    project = load_project(folder).project
    (record,) = project.import_records.values()
    doc = json.loads(data_files(project)["provenance.json"])
    (entry,) = doc["imports"]
    assert entry["source_name"] == "segment-lengths.csv" and entry["kind"] == "lengths"
    assert entry["sha256"] == record.sha256 and entry["rows_read"] == len(segs)
    assert str(tmp_path) not in json.dumps(doc)


def test_a_stamped_output_is_read_back_by_the_importers(
    folders: dict[str, Path],
    exported: dict[str, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The first line of an output CSV is `# harness-design-studio VERSION model HASH`; the
    importers skip it, so the tool's own files can be read back."""
    work = tmp_path / "flat"
    api.create_project(work, "flatsat")
    api.export(work)
    bom = work / "outputs" / "system" / "bom.csv"
    assert bom.read_text(encoding="utf-8").startswith("# harness-design-studio ")
    args = [
        "import-parts",
        str(work),
        str(bom),
        "--approved",
        "approved",
        "--pending",
        "pending (example data)",
    ]
    assert main([*args, "--rejected", "not_approved", "--dry-run"]) == 0
    assert "Dry run" in capsys.readouterr().out
    # a stamped file of segment lengths (the first line is the stamp, as in the outputs)
    stamped = tmp_path / "lengths.csv"
    plain = (exported["small-satellite-numbers"] / "segment_lengths.csv").read_text(
        encoding="utf-8"
    )
    stamped.write_text(
        "# harness-design-studio 1.0.0 model abcdef012345\n" + plain, encoding="utf-8"
    )
    copy = tmp_path / "copy"
    api.create_project(copy, "small-satellite")
    api.generate(copy)
    assert (
        main(["import-lengths", str(copy), str(stamped), "--unit", "m", "--dry-run", "--json"]) == 0
    )
    doc = json.loads(capsys.readouterr().out)
    assert doc["problems"] == 0 and doc["ready"] > 0
