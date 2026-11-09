# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Comments in the config files: the reserved key `_about` (D-191 (2), R3, open decision 13).

A person who opens `config/derating.json` in an editor sees, next to each value, its unit, range,
source and use. It is opt-in and it is not part of the design: it is never a setting, it is out of
the model hash, the generation inputs, the numbers and every written output, and a project that has
none is written byte for byte as before."""

import json
import shutil
from pathlib import Path

import pytest

from harness_design_studio import api
from harness_design_studio.cli.jsonout import SHAPES
from harness_design_studio.cli.main import main
from harness_design_studio.core import configcheck, settings
from harness_design_studio.core.generation_status import generation_status
from harness_design_studio.core.io import layout
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.journal import files_hash
from harness_design_studio.core.model import CONFIG_NAMES


def read_all(folder: Path) -> dict[str, bytes]:
    """Every file under `folder` by POSIX path, bytes as they are on disk (Windows writes CRLF)."""
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*"))
        if p.is_file() and p.suffix != ".bak" and not p.name.startswith(".")
    }


def config_files(folder: Path) -> list[Path]:
    return sorted((folder / "config").glob("*.json"))


@pytest.fixture
def plain(tmp_path: Path) -> Path:
    folder = tmp_path / "plain"
    api.create_project(folder, "first-steps")
    assert api.generate(folder).ok
    return folder


@pytest.fixture
def annotated(tmp_path: Path, plain: Path) -> Path:
    folder = tmp_path / "annotated"
    shutil.copytree(plain, folder)
    assert main(["settings", str(folder), "--annotate"]) == 0
    return folder


# ---- what the file carries -------------------------------------------------------------------


def test_the_annotation_is_made_from_the_registry_for_every_key_of_the_file(
    annotated: Path,
) -> None:
    for path in config_files(annotated):
        doc = json.loads(path.read_text(encoding="utf-8"))
        name = path.stem
        assert doc["_about"] == json.loads(json.dumps(settings.about_for(name))), name
        assert set(doc["_about"]) == {s.key for s in settings.SETTINGS if s.file == name}
    entry = json.loads((annotated / "config" / "derating.json").read_text("utf-8"))["_about"][
        "max_voltage_drop_v"
    ]
    assert entry["unit"] == "V" and entry["default"] is None
    assert set(entry) == {
        "label", "unit", "range", "source", "what", "used_by", "default"
    }  # fmt: skip
    assert (
        "assumption"
        in json.loads((annotated / "config" / "derating.json").read_text("utf-8"))["_about"][
            "bundle_derating"
        ]
    )


def test_every_config_name_with_settings_can_be_annotated() -> None:
    files = {s.file for s in settings.SETTINGS}
    assert files <= set(CONFIG_NAMES)
    for name in files:
        assert (
            settings.about_for(name)
            and settings.about_problems(name, settings.about_for(name)) == []
        )


# ---- nothing else changes: hashes, numbers, outputs ------------------------------------------


def test_the_model_hash_the_files_hash_and_generation_ignore_the_annotation(
    plain: Path, annotated: Path
) -> None:
    a, b = load_project(plain).project, load_project(annotated).project
    assert b.config["derating"].about and not a.config["derating"].about
    assert layout.model_hash(a) == layout.model_hash(b)
    assert files_hash(layout.serialize(a, tool_version="")) == layout.model_hash(a)
    assert files_hash(layout.serialize(b, tool_version="")) == layout.model_hash(a)
    assert generation_status(b) == "current"  # annotating does not make the harnesses stale


def test_the_written_outputs_are_identical_with_and_without_the_annotation(
    tmp_path: Path, plain: Path, annotated: Path
) -> None:
    for folder in (plain, annotated):
        assert api.export(folder, out=tmp_path / f"out-{folder.name}").ok
    then, now = read_all(tmp_path / "out-plain"), read_all(tmp_path / "out-annotated")
    assert then and now == then
    data = tmp_path / "data"
    api.export_data(plain, data / "plain")
    api.export_data(annotated, data / "annotated")
    assert read_all(data / "annotated") == read_all(data / "plain")


def test_the_numbers_are_the_same_with_and_without_the_annotation(
    plain: Path, annotated: Path
) -> None:
    def numbers(folder: Path) -> list[object]:
        project = load_project(folder).project
        return [
            (h.id, w.id, w.gauge_awg, w.length_m, w.part_id)
            for h in project.harnesses.values()
            for w in h.wires
        ]

    assert numbers(plain) == numbers(annotated) != []
    a, b = api.run_checks(plain), api.run_checks(annotated)
    assert [f.to_dict() for f in a.findings] == [f.to_dict() for f in b.findings]


def test_the_journal_records_no_row_for_a_comment(tmp_path: Path) -> None:
    folder = tmp_path / "j"
    api.create_project(folder, "first-steps")
    before = len(api.get_journal(folder).entries)
    assert main(["settings", str(folder), "--annotate"]) == 0
    assert len(api.get_journal(folder).entries) == before


# ---- a project without comments is written as before; with them it round-trips ----------------


def test_a_project_without_comments_is_opened_and_saved_unchanged(plain: Path) -> None:
    then = read_all(plain)
    project = load_project(plain).project
    assert all(not c.about for c in project.config.values())
    from harness_design_studio.core.io.saver import save_project

    save_project(project, plain)
    assert read_all(plain) == then
    assert all(b'"_about"' not in data for rel, data in then.items() if rel.startswith("config/"))


def test_a_project_with_comments_round_trips_and_a_value_edit_keeps_them(annotated: Path) -> None:
    from harness_design_studio.core.io.saver import save_project

    then = read_all(annotated)
    save_project(load_project(annotated).project, annotated)
    assert read_all(annotated) == then
    assert main(["settings", str(annotated), "--set", "derating.bundle_derating=0.8"]) == 0
    assert api.set_config(annotated, "derating", "temperature_derating", 0.9).value == 0.9
    after = load_project(annotated).project
    assert after.config["derating"].values["bundle_derating"] == 0.8
    assert after.config["derating"].about == settings.about_for("derating")
    assert after.config["naming"].about == settings.about_for("naming")
    assert configcheck.annotation_issues(after) == []


def test_annotating_and_removing_gives_the_original_bytes_back(tmp_path: Path, plain: Path) -> None:
    folder = tmp_path / "x"
    shutil.copytree(plain, folder)
    then = read_all(folder)
    assert main(["settings", str(folder), "--annotate"]) == 0
    assert read_all(folder) != then
    assert set(read_all(folder)) == set(then)  # no file is created
    assert {rel for rel, data in read_all(folder).items() if data != then[rel]} <= {
        f"config/{p.stem}.json" for p in config_files(folder)
    }
    assert main(["settings", str(folder), "--no-annotate"]) == 0
    assert read_all(folder) == then


# ---- the command ------------------------------------------------------------------------------


def test_annotate_is_idempotent_and_json_names_the_files(
    tmp_path: Path, plain: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "y"
    shutil.copytree(plain, folder)
    capsys.readouterr()
    assert main(["settings", str(folder), "--annotate", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert list(doc) == list(SHAPES["settings --annotate"])
    assert doc["action"] == "annotate" and doc["changed"] is True
    assert doc["files"] == [f"config/{p.stem}.json" for p in config_files(folder)]
    assert folder.as_posix() not in json.dumps(doc)
    again = read_all(folder)
    assert main(["settings", str(folder), "--annotate", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["changed"] is False and doc["files"] == [] and doc["unchanged"]
    assert read_all(folder) == again
    assert main(["settings", str(folder), "--no-annotate", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["action"] == "remove" and doc["changed"] is True


def test_the_options_exclude_each_other(tmp_path: Path, plain: Path) -> None:
    assert main(["settings", str(plain), "--annotate", "--no-annotate"]) == 2
    assert (
        main(["settings", str(plain), "--annotate", "--set", "derating.bundle_derating=0.8"]) == 2
    )


def test_the_scripting_interface_annotates_and_removes(tmp_path: Path, plain: Path) -> None:
    folder = tmp_path / "z"
    shutil.copytree(plain, folder)
    result = api.annotate_config(folder)
    assert result.changed and result.action == "annotate" and "derating" in result.files
    assert result.to_dict()["files"][0].startswith("config/")
    assert not api.annotate_config(folder).changed
    assert api.get_config(folder).comment_warnings == ()
    assert api.annotate_config(folder, remove=True).action == "remove"
    assert all(not c.about for c in load_project(folder).project.config.values())


def test_new_can_start_annotated_and_does_not_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    off, on = tmp_path / "off", tmp_path / "on"
    assert main(["new", str(off), "--template", "first-steps"]) == 0
    assert main(["new", str(on), "--template", "first-steps", "--annotate-config"]) == 0
    capsys.readouterr()
    assert all(b"_about" not in p.read_bytes() for p in config_files(off))
    assert all(b"_about" in p.read_bytes() for p in config_files(on))
    assert layout.model_hash(load_project(on).project) == layout.model_hash(
        load_project(off).project
    )
    assert main(["validate", str(on)]) == 0
    assert "config_about_stale" not in capsys.readouterr().out
    api.create_project(tmp_path / "a", "blank", annotate_config=True)
    assert all(b"_about" in p.read_bytes() for p in config_files(tmp_path / "a"))


# ---- loading ignores it for values; a stale entry is a warning ---------------------------------


def edit_about(folder: Path, name: str, change) -> None:  # type: ignore[no-untyped-def]
    path = folder / "config" / f"{name}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    change(doc["_about"])
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_a_stale_entry_is_a_warning_that_names_the_file_and_the_key_and_annotate_fixes_it(
    annotated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit_about(annotated, "derating", lambda a: a["bundle_derating"].update(range="0 to 2"))
    edit_about(annotated, "derating", lambda a: a.update(removed_key={"unit": "V"}))
    edit_about(annotated, "derating", lambda a: a.pop("spare_pin_fraction"))
    capsys.readouterr()
    assert main(["validate", str(annotated)]) == 0  # a warning, never an error
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if "config_about_stale" in ln]
    assert len(lines) == 3
    assert any("config/derating.json: _about for 'bundle_derating' differs" in ln and "range" in ln for ln in lines)  # fmt: skip
    assert any("'removed_key'" in ln and "does not know" in ln for ln in lines)
    assert any("'spare_pin_fraction' has no entry" in ln for ln in lines)
    assert "3 warning(s)" in out
    assert main(["config", str(annotated)]) in (0, 1)
    assert "STALE COMMENT config/derating.json: _about for 'bundle_derating'" in capsys.readouterr().out  # fmt: skip
    assert len(api.get_config(annotated).comment_warnings) == 3
    assert main(["settings", str(annotated), "--annotate"]) == 0
    capsys.readouterr()
    assert main(["validate", str(annotated)]) == 0
    assert "config_about_stale" not in capsys.readouterr().out


def test_a_stale_entry_never_reaches_generation_or_the_numbers(
    annotated: Path, plain: Path
) -> None:
    edit_about(annotated, "derating", lambda a: a["bundle_derating"].update(range="0 to 2"))
    project = load_project(annotated).project
    assert configcheck.validate(project) == configcheck.validate(load_project(plain).project)
    assert configcheck.annotation_issues(project)
    assert api.generate(annotated).ok
    assert layout.model_hash(project) == layout.model_hash(load_project(plain).project)


def test_a_damaged_about_is_ignored_with_a_warning_and_the_values_are_kept(
    annotated: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = annotated / "config" / "derating.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["_about"] = ["not", "an", "object"]
    doc["values"]["bundle_derating"] = 0.7
    path.write_text(json.dumps(doc), encoding="utf-8")
    loaded = load_project(annotated)
    assert loaded.project.config["derating"].values["bundle_derating"] == 0.7
    assert not loaded.project.config["derating"].about and not loaded.project.quarantine
    assert [i.code for i in loaded.issues if i.severity == "warning"] == ["config_about_ignored"]
    capsys.readouterr()
    assert main(["validate", str(annotated)]) == 0
    assert "config/derating.json: '_about' must be an object" in capsys.readouterr().out


def test_about_is_never_a_setting(annotated: Path) -> None:
    project = load_project(annotated).project
    assert "_about" not in project.config["derating"].values
    assert settings.setting("derating", "_about") is None
    assert not any(i.object_id and "_about" in i.object_id for i in configcheck.validate(project))
    assert main(["settings", str(annotated), "--set", "derating._about=1"]) == 2


# ---- the schema and the editor ----------------------------------------------------------------


def test_the_json_schema_allows_the_comments() -> None:
    from harness_design_studio.core import schemas

    config = schemas.schemas()["config"]
    assert "_about" in config["properties"] and config["additionalProperties"] is False
    assert "_about" not in config["required"]
    assert config["properties"]["_about"]["description"]


@pytest.mark.gui
def test_the_engineering_values_page_shows_range_and_source_as_the_tooltip(  # type: ignore[no-untyped-def]
    qtbot, annotated: Path
) -> None:
    pytest.importorskip("PySide6")
    from harness_design_studio.gui.config_dialog import FieldRow
    from harness_design_studio.gui.theme import ThemeManager

    project = load_project(annotated).project
    values = configcheck.engineering_values(project)
    ev = next(v for v in values if (v.file, v.key) == ("derating", "bundle_derating"))
    row = FieldRow(ev, ThemeManager(), False)
    qtbot.addWidget(row)
    s = settings.setting("derating", "bundle_derating")
    assert s is not None
    assert s.range in row.editor.toolTip() and s.source in row.editor.toolTip()
    assert ev.what in row.editor.toolTip() and ev.used_by in row.editor.toolTip()
