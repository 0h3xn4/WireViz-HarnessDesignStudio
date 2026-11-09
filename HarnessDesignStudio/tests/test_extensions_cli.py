# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""S8: the commands `extensions`, `trust` and `import-plugin`, the schema of the extension files,
and the scripting interface (`list_extensions`)."""

import io
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

from harness_design_studio import api
from harness_design_studio.cli.jsonout import SHAPES
from harness_design_studio.cli.main import main
from harness_design_studio.core.extensions import manager, plugins, schema, trust
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from tests.ext_helpers import ext_file, gauge_rule, generated, write_extensions
from tests.test_extensions_plugins import add_plugin, plugin_source


@pytest.fixture(scope="module")
def saved(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("cli") / "p"
    save_project(generated(folder.parent / "g"), folder)
    return folder


@pytest.fixture
def folder(saved: Path, tmp_path: Path) -> Path:
    target = tmp_path / "p"
    shutil.copytree(saved, target)
    plugins.forget_loaded()
    manager._RUNTIMES.clear()
    return target


def doc_of(capsys: pytest.CaptureFixture[str], *argv: str, rc: int = 0) -> dict[str, Any]:
    assert main([*argv, "--json"]) == rc, argv
    doc = json.loads(capsys.readouterr().out)
    assert list(doc)[0] == "ok" and doc["ok"] is (rc == 0)
    return doc  # type: ignore[no-any-return]


class FakeStdin(io.StringIO):
    def isatty(self) -> bool:
        return True


# ---- extensions ------------------------------------------------------------------------------------------


def test_extensions_json_lists_name_version_kind_source_and_hash(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    add_plugin(folder, plugin_source())
    write_extensions(
        folder,
        {
            "t.json": ext_file(
                rules=[gauge_rule()], lookups=[{"name": "amp", "values": {"24": 1.0}}]
            )
        },
        plugins=["demo"],
    )
    doc = doc_of(
        capsys, "extensions", str(folder), rc=1
    )  # the plug-in is enabled, not trusted: not applied
    assert list(doc) == list(SHAPES["extensions"])
    assert (
        doc["has_folder"] is True
        and doc["enabled_declarative"] == ["t.json"]
        and doc["enabled_plugins"] == ["demo"]
    )
    (f,) = doc["files"]
    assert (
        f["file"],
        f["name"],
        f["version"],
        f["enabled"],
        f["status"],
        f["rules"],
        f["lookups"],
    ) == ("extensions/t.json", "t", "1.0.0", True, "applied", 1, 1)
    assert len(f["sha256"]) == 64
    (p,) = doc["plugins"]
    assert (p["name"], p["version"], p["kinds"], p["enabled"], p["trusted"], p["state"]) == (
        "demo",
        "1.2.3",
        ["rule"],
        True,
        False,
        "untrusted",
    )
    items = {(i["kind"], i["name"]): i for i in doc["items"]}
    assert (
        items[("rule", "x-gauge")]["source"] == "declarative"
        and items[("rule", "x-gauge")]["origin"] == "extensions/t.json"
    )
    assert (
        items[("rule", "x-gauge")]["sha256"] == f["sha256"]
        and items[("rule", "x-gauge")]["version"] == "1.0.0"
    )
    assert ("rule", "x-demo") not in items  # untrusted code registers nothing
    assert (
        items[("rule", "duplicate-id")]["source"] == "built-in"
        and items[("rule", "duplicate-id")]["trusted"] is True
    )
    assert any(i["kind"] == "lookup" and i["name"] == "t/amp" for i in doc["items"])
    # after trust the plug-in is in the list, with its hash
    assert main(["trust", str(folder), "demo", "--yes"]) == 0
    capsys.readouterr()
    doc = doc_of(capsys, "extensions", str(folder))
    items = {(i["kind"], i["name"]): i for i in doc["items"]}
    rule = items[("rule", "x-demo")]
    assert (rule["source"], rule["origin"], rule["version"], rule["trusted"], rule["enabled"]) == (
        "plugin",
        "demo",
        "1.2.3",
        True,
        True,
    )
    assert rule["sha256"] == doc["plugins"][0]["sha256"]
    assert str(folder) not in json.dumps(doc)  # no absolute path
    assert doc == doc_of(capsys, "extensions", str(folder))  # the same twice


def test_extensions_text_and_a_project_without_the_folder(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["extensions", str(folder)]) == 0
    out = capsys.readouterr().out
    assert "no extensions folder" in out and "built-in items are registered" in out
    assert main(["extensions", str(folder), "--all"]) == 0
    assert "duplicate-id" in capsys.readouterr().out
    doc = doc_of(capsys, "extensions", str(folder))
    assert (
        doc["has_folder"] is False
        and doc["files"] == []
        and doc["plugins"] == []
        and doc["issues"] == []
    )
    assert all(i["source"] == "built-in" for i in doc["items"])
    assert sum(i["kind"] == "rule" for i in doc["items"]) == 39
    write_extensions(folder, {"t.json": ext_file(rules=[gauge_rule()])})
    assert main(["extensions", str(folder)]) == 0
    out = capsys.readouterr().out
    assert "Declarative files" in out and "x-gauge" in out and "built-in items not listed" in out


def test_enable_and_disable_write_enabled_json(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_extensions(
        folder,
        {
            "a.json": ext_file("a", rules=[gauge_rule()]),
            "b.json": ext_file("b", rules=[gauge_rule(id="b")]),
        },
        enabled=[],
    )
    add_plugin(folder, plugin_source(), enable=None)
    assert main(["extensions", str(folder), "--enable", "a.json", "--enable", "demo"]) in (0, 1)
    capsys.readouterr()
    enabled = json.loads((folder / "extensions" / "enabled.json").read_text())
    assert enabled["declarative"] == ["a.json"] and enabled["plugins"] == ["demo"]
    assert main(["extensions", str(folder), "--disable", "a.json"]) in (0, 1)
    assert json.loads((folder / "extensions" / "enabled.json").read_text())["declarative"] == []
    assert main(["extensions", str(folder), "--enable", "nothing.json"]) == 2
    assert "neither a file in extensions/ nor a plug-in" in capsys.readouterr().err
    (folder / "extensions" / "enabled.json").write_text("{")
    assert main(["extensions", str(folder), "--enable", "a.json"]) == 2
    assert "fix extensions/enabled.json first" in capsys.readouterr().err


def test_a_bad_enabled_json_is_reported_and_enables_nothing(folder: Path) -> None:
    write_extensions(folder, {"a.json": ext_file(rules=[gauge_rule()])})
    (folder / "extensions" / "enabled.json").write_text(
        json.dumps({"format": "x", "declarative": ["a.json"], "extra": 1})
    )
    ext = load_project(folder).project.extensions
    assert ext is not None and ext.enabled_files == ()
    text = [i.render() for i in ext.issues]
    assert any("extensions/enabled.json:" in t and "extra: unknown key" in t for t in text), text
    assert {f.status for f in ext.files} == {"disabled"}


def test_an_enabled_name_that_does_not_exist_is_reported(folder: Path) -> None:
    write_extensions(folder, {}, enabled=["missing.json"], plugins=["ghost"])
    ext = load_project(folder).project.extensions
    assert ext is not None
    text = " | ".join(i.render() for i in ext.issues)
    assert "'missing.json' is enabled but extensions/missing.json does not exist" in text
    assert "the plug-in 'ghost' is enabled but no such plug-in" in text


# ---- trust ---------------------------------------------------------------------------------------------------


def test_trust_shows_the_code_and_asks_for_the_name(
    folder: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    add_plugin(folder, plugin_source())
    (info_ext,) = [load_project(folder).project.extensions.plugins[0]]  # type: ignore[union-attr]
    monkeypatch.setattr(sys, "stdin", FakeStdin("wrong\n"))
    assert main(["trust", str(folder), "demo"]) == 1
    out = capsys.readouterr().out
    for line in (
        "name:      demo",
        "version:   1.2.3",
        "kinds:     rule",
        "where:     extensions/plugins/demo.py",
        f"sha256:    {info_ext.sha256}",
        f"lines:     {info_ext.lines}",
    ):
        assert line in out, line
    assert "runs with your rights" in out and "no sandbox" in out and "Not trusted" in out
    assert trust.read() == []
    monkeypatch.setattr(sys, "stdin", FakeStdin("demo\n"))
    assert main(["trust", str(folder), "demo"]) == 0
    assert "is trusted on this computer" in capsys.readouterr().out
    assert trust.is_trusted("demo", info_ext.sha256)
    assert main(["trust", str(folder), "demo", "--yes"]) == 0
    assert "already trusted" in capsys.readouterr().out


def test_trust_without_a_person_to_ask_does_not_trust(
    folder: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    add_plugin(folder, plugin_source())
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))  # not a terminal
    assert main(["trust", str(folder), "demo"]) == 1
    assert "nobody to ask" in capsys.readouterr().out and trust.read() == []
    doc = doc_of(capsys, "trust", str(folder), "demo", rc=1)  # --json never asks
    assert (
        list(doc) == list(SHAPES["trust"])
        and doc["trusted"] is False
        and doc["changed"] is False
        and doc["name"] == "demo"
    )
    doc = doc_of(capsys, "trust", str(folder), "demo", "--yes")
    assert (
        doc["trusted"] is True
        and doc["changed"] is True
        and doc["lines"] > 5
        and doc["where"] == "extensions/plugins/demo.py"
    )
    assert doc == {
        **doc_of(capsys, "trust", str(folder), "demo", "--yes"),
        "changed": True,
    }  # the second call changes nothing


def test_trust_revoke_list_and_unknown_names(
    folder: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["trust", str(folder)]) == 0
    assert "no Python plug-ins" in capsys.readouterr().out
    add_plugin(folder, plugin_source())
    assert main(["trust", str(folder), "demo", "--yes"]) == 0
    capsys.readouterr()
    assert main(["trust", str(folder)]) == 0
    assert "demo" in capsys.readouterr().out
    assert main(["trust", str(folder), "demo", "--revoke"]) == 0
    assert "taken back" in capsys.readouterr().out and trust.read() == []
    assert main(["trust", str(folder), "demo", "--revoke"]) == 0
    assert "was not trusted" in capsys.readouterr().out
    assert main(["trust", str(folder), "nothing", "--yes"]) == 2
    assert "no plug-in named 'nothing'" in capsys.readouterr().err
    doc = doc_of(capsys, "trust", str(folder))
    assert doc["action"] == "list"


def test_trusting_does_not_enable(folder: Path, capsys: pytest.CaptureFixture[str]) -> None:
    add_plugin(folder, plugin_source(), enable=None)
    assert main(["trust", str(folder), "demo", "--yes"]) == 0
    assert "does not enable demo" in capsys.readouterr().out
    ext = load_project(folder).project.extensions
    assert ext is not None and ext.plugins[0].state == "disabled" and ext.plugins[0].trusted


# ---- import-plugin ----------------------------------------------------------------------------------------------


IMPORTER = """
from harness_design_studio.core import configcheck
from harness_design_studio.core.commands import SetConfig
from harness_design_studio.core.extensions.pluginapi import PluginImport

def read(project, path):
    first = path.read_text(encoding="utf-8").splitlines()[0]
    cfg = project.config["generation"]
    value = float(first)
    if cfg.values.get("service_loop_m") == value:
        return PluginImport(rows=["service loop is already " + first])
    return PluginImport(ops=[SetConfig(configcheck.with_value(cfg, "service_loop_m", value))],
                        rows=["service loop " + first + " m"], notes=["from " + path.name])

api.importer("loop", read, doc="Reads the service loop from the first line of a file.")
"""


def test_import_plugin_runs_an_importer_of_a_trusted_plugin(
    folder: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    add_plugin(folder, plugin_source(kinds='["rule", "importer"]', body=IMPORTER))
    data = tmp_path / "loop.txt"
    data.write_text("0.25\n")
    assert (
        main(["import-plugin", str(folder), "loop", str(data)]) == 2
    )  # not trusted: no such importer
    assert "no importer named 'loop'" in capsys.readouterr().err
    assert main(["trust", str(folder), "demo", "--yes"]) == 0
    capsys.readouterr()
    assert main(["import-plugin", str(folder), "loop", str(data), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert (
        "service loop 0.25 m" in out
        and "would be made (dry run)" in out
        and "note: from loop.txt" in out
    )
    assert load_project(folder).project.config["generation"].values.get("service_loop_m") != 0.25
    doc = doc_of(capsys, "import-plugin", str(folder), "loop", str(data))
    assert (
        list(doc) == list(SHAPES["import-plugin"])
        and doc["changed"] is True
        and doc["dry_run"] is False
    )
    assert doc["rows"] == ["service loop 0.25 m"] and doc["notes"] == ["from loop.txt"]
    assert load_project(folder).project.config["generation"].values["service_loop_m"] == 0.25
    assert main(["import-plugin", str(folder), "loop", str(data)]) == 0
    assert "Already up to date." in capsys.readouterr().out
    data.write_text("not a number\n")
    assert main(["import-plugin", str(folder), "loop", str(data)]) == 1
    assert "stopped: ValueError" in capsys.readouterr().err


# ---- the schema, the interface ---------------------------------------------------------------------------------------


def test_the_schema_command_exports_the_extension_schemas(tmp_path: Path) -> None:
    target = tmp_path / "schemas"
    assert main(["schema", str(target)]) == 0
    ext = json.loads((target / "extension.schema.json").read_text())
    enabled = json.loads((target / "extensions-enabled.schema.json").read_text())
    assert ext["title"] == "extension" and ext["additionalProperties"] is False
    assert set(ext["required"]) == {"format", "format_version", "name", "version"}
    rule = ext["properties"]["rules"]["items"]
    assert rule["properties"]["severity"]["enum"] == ["error", "warning", "info"]
    assert rule["properties"]["applies_to"]["enum"] == ["wire", "connector", "interface", "harness"]
    assert set(rule["required"]) == {
        "id",
        "title",
        "severity",
        "applies_to",
        "condition",
        "message",
        "why",
        "how",
    }
    assert (
        "condition" in rule["properties"]
        and "expression" in rule["properties"]["condition"]["description"]
    )
    assert enabled["properties"]["plugins"]["type"] == "array"
    settings = json.loads((target / "editor-settings.json").read_text())
    matches = {tuple(e["fileMatch"]): e["url"] for e in settings["json.schemas"]}
    assert matches[("/extensions/enabled.json",)] == "./schemas/extensions-enabled.schema.json"
    assert (
        matches[("/extensions/*.json", "!/extensions/enabled.json")]
        == "./schemas/extension.schema.json"
    )


def test_the_schema_and_the_check_come_from_one_description() -> None:
    """Every key of the description is in the schema, and a file the schema accepts passes the check."""
    for name, spec in (("extension", schema.FILE), ("extensions-enabled", schema.ENABLED)):
        doc = schema.schemas()[name]
        assert set(dict(doc)["properties"]) == {n for n, _ in spec.props}  # type: ignore[call-overload]
    good = ext_file(
        rules=[gauge_rule()],
        lookups=[{"name": "t", "values": {"1": 2}}],
        tables=[
            {
                "name": "t",
                "title": "t",
                "applies_to": "wire",
                "columns": [{"header": "h", "value": "wire.id"}],
            }
        ],
        parameters={"p": {"value": 1}},
    )
    assert schema.check(schema.FILE, good) == []
    messages = [p.message for p in schema.check(schema.FILE, {**good, "tables": [{"name": "T"}]})]
    assert any("'T' is not an acceptable name" in m for m in messages) and any(
        "'title' is required" in m or "the key 'title' is required" in m for m in messages
    )


def test_list_extensions_in_the_scripting_interface(folder: Path) -> None:
    write_extensions(folder, {"t.json": ext_file(rules=[gauge_rule()])})
    got = api.list_extensions(folder)
    assert got["has_folder"] is True and [f["name"] for f in got["files"]] == ["t"]
    assert any(i["name"] == "x-gauge" for i in got["items"])
    assert api.list_extensions(load_project(folder).project) == got
    result = api.run_checks(folder)
    assert result.rules_run == 40 and any(f.rule == "x-gauge" for f in result.findings)
