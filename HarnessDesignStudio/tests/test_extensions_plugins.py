"""S8: Python plug-ins are opt-in per project and trusted per exact code.

What is checked: a plug-in whose module has a side effect at import time is not executed unless the
project enables it AND the user trusted that exact code; trust is kept in the user's settings folder,
not in the project, and is tied to the hash, so a change of one byte takes it away; a plug-in that
cannot be loaded (syntax error, an exception, a wrong declaration, a name that is taken) is reported
and stops nothing; an installed package is found by its entry point and gated the same way."""

import copy
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from harness_design_studio.core import derive, drc
from harness_design_studio.core.extensions import manager, plugins, trust
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.outputs.build import build_outputs
from tests.ext_helpers import ext_file, gauge_rule, generated, write_extensions

ROOT = Path(__file__).resolve().parents[1]


def plugin_source(
    name: str = "demo",
    marker: Path | None = None,
    *,
    kinds: str = '["rule"]',
    body: str = "",
    api: int = 1,
) -> str:
    """A plug-in with a rule that finds every harness; if `marker` is given the module writes it at
    import time (a side effect that must not happen before trust). `body` is more lines of
    `register`."""
    lines = []
    if marker:
        lines += [f"with open({str(marker)!r}, 'a') as _f:", "    _f.write('imported\\n')"]
    lines += [
        f'PLUGIN = {{"name": "{name}", "version": "1.2.3", "api": {api}, "kinds": {kinds}, "description": "a test"}}',
        "",
        "",
        "def register(api):",
        "    def check(project):",
        "        for h in sorted(project.harnesses):",
        '            yield api.Hit(h, "harness " + h + " found")',
        "",
        f'    api.rule("x-{name}", title="Demo", severity="info", why="because", how="by hand",',
        '             compares="each harness with nothing", check=check)',
    ]
    lines += ["    " + line for line in textwrap.dedent(body).strip("\n").splitlines()]
    return "\n".join(lines) + "\n"


@pytest.fixture(scope="module")
def saved(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("plug") / "p"
    save_project(generated(folder.parent / "g"), folder)
    return folder


@pytest.fixture
def folder(saved: Path, tmp_path: Path) -> Path:
    import shutil

    target = tmp_path / "p"
    shutil.copytree(saved, target)
    plugins.forget_loaded()
    manager._RUNTIMES.clear()
    return target


def add_plugin(
    folder: Path, source: str, file: str = "demo.py", enable: str | None = "demo"
) -> Path:
    (folder / "extensions" / "plugins").mkdir(parents=True, exist_ok=True)
    path = folder / "extensions" / "plugins" / file
    path.write_text(source, encoding="utf-8")
    write_extensions(folder, {}, plugins=[enable] if enable else [])
    return path


def state(folder: Path, name: str = "demo") -> str:
    ext = load_project(folder).project.extensions
    assert ext is not None
    return str(next(p.state for p in ext.plugins if p.name == name))


def trust_it(folder: Path, name: str = "demo") -> plugins.PluginInfo:
    ext = load_project(folder).project.extensions
    assert ext is not None
    info: plugins.PluginInfo = next(p for p in ext.plugins if p.name == name)
    trust.trust(info.name, info.sha256, info.version, info.where)
    return info


# ---- the gate: enabled and trusted ------------------------------------------------------------------------


def test_a_plugin_with_a_side_effect_is_not_executed_until_enabled_and_trusted(
    folder: Path, tmp_path: Path
) -> None:
    marker = tmp_path / "marker.txt"
    add_plugin(folder, plugin_source(marker=marker), enable=None)
    # not enabled: listed, not imported
    project = load_project(folder).project
    drc.run(project)
    assert state(folder) == "disabled" and not marker.exists()
    # enabled, not trusted: listed, not imported, and the check says so
    write_extensions(folder, {}, plugins=["demo"])
    project = load_project(folder).project
    found = drc.run(project)
    assert state(folder) == "untrusted" and not marker.exists()
    assert not [f for f in found if f.rule == "x-demo"]
    problem = next(f for f in found if f.rule == "x-extension-problem")
    assert "demo" in problem.title and "not trusted" in problem.title
    # trusted but not enabled: still not imported
    write_extensions(folder, {}, plugins=[])
    trust_it(folder)
    load_project(folder)
    assert not marker.exists()
    # enabled and trusted: imported, once
    write_extensions(folder, {}, plugins=["demo"])
    project = load_project(folder).project
    assert state(folder) == "loaded" and marker.read_text() == "imported\n"
    rules = {f.rule for f in drc.run(project)}
    assert "x-demo" in rules and "x-extension-problem" not in rules
    load_project(folder)
    assert marker.read_text() == "imported\n"  # not run again for the same code in this process


def test_an_untrusted_plugin_is_not_imported_in_a_fresh_interpreter(
    folder: Path, tmp_path: Path
) -> None:
    """The guarantee as a user meets it: `drc` on a cloned project runs none of its Python."""
    marker = tmp_path / "marker.txt"
    add_plugin(folder, plugin_source(marker=marker))
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
        "HARNESS_DESIGN_STUDIO_CONFIG_DIR": str(tmp_path / "nobody-trusted-anything"),
        "QT_QPA_PLATFORM": "offscreen",
    }
    run = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "harness_design_studio.cli.main", "drc", str(folder)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, check=False,
    )  # fmt: skip
    assert run.returncode in (0, 1), run.stderr
    assert not marker.exists()
    assert "x-extension-problem" in run.stdout and "not trusted" in run.stdout
    trust_env = {**env, "HARNESS_DESIGN_STUDIO_CONFIG_DIR": str(tmp_path / "me")}
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "harness_design_studio.cli.main", "trust", str(folder), "demo", "--yes"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=trust_env, check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    assert not marker.exists()  # trusting reads the code and never runs it
    again = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "harness_design_studio.cli.main", "drc", str(folder)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=trust_env, check=False,
    )  # fmt: skip
    assert again.returncode in (0, 1) and marker.exists() and "x-demo" in again.stdout


def test_changing_the_code_takes_the_trust_away(folder: Path, tmp_path: Path) -> None:
    marker = tmp_path / "marker.txt"
    path = add_plugin(folder, plugin_source(marker=marker))
    info = trust_it(folder)
    assert state(folder) == "loaded"
    marker.unlink()
    plugins.forget_loaded()
    manager._RUNTIMES.clear()
    path.write_text(path.read_text() + "# one more line\n", encoding="utf-8")
    assert state(folder) == "untrusted" and not marker.exists()
    ext = load_project(folder).project.extensions
    assert ext is not None
    new = next(p for p in ext.plugins if p.name == "demo")
    assert new.sha256 != info.sha256 and new.lines == info.lines + 1
    assert trust.trusted_hashes("demo") == [info.sha256]  # the old entry is only the old code
    trust.trust(
        "demo", new.sha256, new.version, new.where
    )  # trusting new code replaces the old trust
    assert trust.trusted_hashes("demo") == [new.sha256]
    path.write_text(path.read_text().replace("one more", "another"), encoding="utf-8")
    assert state(folder) == "untrusted"


def test_revoking_trust_unloads_it_for_the_next_project_open(folder: Path) -> None:
    add_plugin(folder, plugin_source())
    trust_it(folder)
    assert state(folder) == "loaded"
    assert trust.revoke("demo") == 1 and trust.revoke("demo") == 0
    project = load_project(folder).project
    assert state(folder) == "untrusted"
    assert "x-demo" not in {f.rule for f in drc.run(project)}


def test_the_trust_is_not_in_the_project(
    folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cloned repository cannot trust itself: the store is in the user's settings folder, and a
    file that claims to be a store inside the project is never read."""
    add_plugin(folder, plugin_source())
    info = trust_it(folder)
    store = trust.store_path()
    assert (
        store.is_file()
        and folder not in store.parents
        and trust.FILE_NAME not in {p.name for p in folder.rglob("*")}
    )
    doc = json.loads(store.read_text())
    assert doc["trusted"] == [
        {
            "name": "demo",
            "sha256": info.sha256,
            "version": "1.2.3",
            "where": "extensions/plugins/demo.py",
        }
    ]
    assert (
        "path" not in store.read_text() and str(tmp_path) not in store.read_text()
    )  # no project path in it
    # the clone brings its own "trusted" file: it counts for nothing
    (folder / "extensions" / trust.FILE_NAME).write_text(store.read_text())
    (folder / trust.FILE_NAME).write_text(store.read_text())
    # another person's computer: their store is empty
    monkeypatch.setenv(trust.ENV_DIR, str(tmp_path / "another-computer"))
    assert state(folder) == "untrusted"
    assert not trust.is_trusted("demo", info.sha256)


def test_a_damaged_or_foreign_store_trusts_nothing(folder: Path) -> None:
    add_plugin(folder, plugin_source())
    info = trust_it(folder)
    path = trust.store_path()
    for text in (
        "{",
        "[]",
        json.dumps({"format": "other", "trusted": [{"name": "demo", "sha256": info.sha256}]}),
        json.dumps({"format": trust.FORMAT, "trusted": [{"name": "demo", "sha256": "abc"}]}),
        "",
    ):
        path.write_text(text)
        assert trust.read() == [] and not trust.is_trusted("demo", info.sha256), text


# ---- a plug-in that cannot be loaded ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "fragment"),
    [
        ("this is not python(", "cannot be read as Python"),
        ("x = 1\n", "no PLUGIN declaration"),
        ("PLUGIN = dict(name='demo')\n", "must be a literal"),
        ("import os\nPLUGIN = {'name': os.name}\n", "must be a literal"),
        (
            'PLUGIN = {"name": "Demo!", "version": "1", "api": 1, "kinds": ["rule"]}\n',
            "lower-case letters",
        ),
        ('PLUGIN = {"name": "demo", "version": "", "api": 1, "kinds": ["rule"]}\n', "version"),
        (
            'PLUGIN = {"name": "demo", "version": "1", "api": 1, "kinds": ["rule", "magic"]}\n',
            "kinds",
        ),
        ('PLUGIN = {"name": "demo", "version": "1", "api": 1, "kinds": []}\n', "kinds"),
        (
            'PLUGIN = {"name": "demo", "version": "1", "kinds": ["rule"]}\n',
            "API version) is missing",
        ),
        (
            'PLUGIN = {"name": "demo", "version": "1", "api": 2, "kinds": ["rule"]}\n',
            "written for API version 2",
        ),
    ],
)
def test_a_plugin_without_a_usable_declaration_is_listed_and_cannot_be_trusted(
    folder: Path, source: str, fragment: str, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_design_studio.cli.main import main

    add_plugin(folder, source, enable="demo")
    ext = load_project(folder).project.extensions
    assert ext is not None
    (info,) = ext.plugins
    assert info.state == "invalid" and fragment in info.message, info.message
    assert main(["trust", str(folder), info.name, "--yes"]) == 2  # nothing to trust
    assert "cannot be trusted" in capsys.readouterr().err
    assert trust.read() == []


def test_a_failing_plugin_is_reported_and_the_others_still_load(
    folder: Path, tmp_path: Path
) -> None:
    marker = tmp_path / "m.txt"
    add_plugin(folder, plugin_source("good", marker), file="good.py", enable="good")
    bad = folder / "extensions" / "plugins" / "bad.py"
    bad.write_text(
        'PLUGIN = {"name": "bad", "version": "1", "api": 1, "kinds": ["rule"]}\nraise RuntimeError("boom at import")\n'
    )
    write_extensions(folder, {}, plugins=["good", "bad"])
    for n in ("good", "bad"):
        trust_it(folder, n)
    project = load_project(folder).project
    ext = project.extensions
    assert ext is not None
    by = {p.name: p for p in ext.plugins}
    assert by["good"].state == "loaded"
    assert by["bad"].state == "failed" and "RuntimeError: boom at import" in by["bad"].message
    found = drc.run(project)
    assert "x-good" in {f.rule for f in found}
    problem = next(f for f in found if f.rule == "x-extension-problem")
    assert "bad" in problem.title and "boom at import" in problem.title


@pytest.mark.parametrize(
    ("source", "fragment"),
    [
        (plugin_source(kinds='["field"]'), "registered a rule ('x-demo') but declares only field"),
        (
            plugin_source(
                body='api.rule("not-prefixed", title="t", severity="info", why="w", how="h", compares="c", check=lambda p: iter(()))'
            ),
            "must start with 'x-'",
        ),
        (
            plugin_source(
                body='api.rule("x-other", title="t", severity="info", why="w", how="h", compares="", check=lambda p: iter(()))'
            ),
            "needs a title, why, how and compares",
        ),
        (
            plugin_source(
                body='api.rule("x-demo", title="t", severity="info", why="w", how="h", compares="c", check=lambda p: iter(()))'
            ),
            "already registered",
        ),
        (
            plugin_source(
                kinds='["rule", "table"]',
                body='api.table("bom", lambda p: [["a"]], title="clash with a built-in table")',
            ),
            "already provided by the tool",
        ),
        (plugin_source(body="raise ValueError('register failed')"), "ValueError: register failed"),
        (
            'PLUGIN = {"name": "demo", "version": "1.2.3", "api": 1, "kinds": ["rule"]}\n',
            "no register(api)",
        ),
        (
            'PLUGIN = {"name": "demo", "version": "1.2.3", "api": 1, "kinds": ["rule"]}\ndef register(api):\n    pass\n',
            "registered nothing",
        ),
    ],
)
def test_a_plugin_that_registers_wrongly_does_not_load(
    folder: Path, source: str, fragment: str
) -> None:
    add_plugin(folder, source)
    trust_it(folder)
    project = load_project(folder).project
    ext = project.extensions
    assert ext is not None
    (info,) = ext.plugins
    assert info.state == "failed" and fragment in info.message, info.message
    assert "x-demo" not in {f.rule for f in drc.run(project)}  # nothing it registered is in force


def test_a_link_is_not_followed_and_no_bytecode_is_written(folder: Path, tmp_path: Path) -> None:
    real = tmp_path / "elsewhere.py"
    real.write_text(plugin_source())
    folder_plugins = folder / "extensions" / "plugins"
    folder_plugins.mkdir(parents=True)
    try:
        (folder_plugins / "linked.py").symlink_to(real)
    except OSError:
        pytest.skip("no symbolic links here")
    write_extensions(folder, {}, plugins=["demo"])
    ext = load_project(folder).project.extensions
    assert (
        ext is not None and ext.plugins[0].state == "invalid" and "link" in ext.plugins[0].message
    )
    (folder_plugins / "linked.py").unlink()
    add_plugin(folder, plugin_source())
    trust_it(folder)
    assert state(folder) == "loaded"
    assert not (
        folder_plugins / "__pycache__"
    ).exists()  # a plug-in is never compiled to a cached file


def test_the_code_that_runs_is_the_code_that_was_hashed(folder: Path) -> None:
    path = add_plugin(folder, plugin_source())
    (c,) = plugins.project_candidates(folder)
    path.write_text(path.read_text() + "# changed after the check\n")
    done = plugins.load(c, folder)
    assert "changed after it was checked" in done.problem and not done.items


def test_a_plugin_rule_that_raises_is_reported_not_fatal(folder: Path) -> None:
    src = plugin_source(body="").replace(
        "yield api.Hit(h", "raise RuntimeError('rule broke')\n            yield api.Hit(h"
    )
    add_plugin(folder, src)
    trust_it(folder)
    project = load_project(folder).project
    found = drc.run(project)
    assert any(
        f.rule == "x-extension-problem" and "RuntimeError" in f.title and "x-demo" in f.title
        for f in found
    )
    assert len(found) > 10  # the rest of the check ran


# ---- what a plug-in can add --------------------------------------------------------------------------------------


def test_a_plugin_field_table_and_importer_are_registered_and_used(
    folder: Path, tmp_path: Path
) -> None:
    body = """
api.field("wire", "double_length", lambda c: (c.wire.length_m or 0) * 2 if c.wire and c.wire.length_m else None, unit="m", doc="Twice the length.")
api.table("wire-count", lambda p: [["Harness", "Wires"], *[[h.id, str(len(h.wires))] for h in sorted(p.harnesses.values(), key=lambda x: x.id)]], title="Wires per harness")
def read(project, path):
    return api.PluginImport(rows=["read " + path.name], notes=["note"])
api.importer("lines", read, doc="Reads a file.")
"""
    src = plugin_source(kinds='["rule", "field", "table", "importer"]', body=body)
    src = src.replace(
        "def register(api):",
        "def register(api):\n    from harness_design_studio.core.extensions.pluginapi import PluginImport\n    api.PluginImport = PluginImport",
        1,
    )
    add_plugin(folder, src)
    write_extensions(
        folder,
        {
            "use.json": ext_file(
                rules=[
                    gauge_rule(
                        id="long",
                        condition="wire.double_length <= 6",
                        unit="m",
                        message="{object} {actual}",
                    )
                ]
            )
        },
        plugins=["demo"],
    )
    ext = load_project(folder).project.extensions
    assert ext is not None
    # before trust the field does not exist, so the file that reads it is not applied (and says why)
    assert [f.status for f in ext.files] == ["broken"]
    assert any("unknown field 'wire.double_length'" in i.render() for i in ext.issues)
    trust_it(folder)
    project = load_project(folder).project
    ext = project.extensions
    assert (
        ext is not None
        and not [i for i in ext.issues]
        and [f.status for f in ext.files] == ["applied"]
    )
    hit = {f.object_id: f.title for f in drc.run(project) if f.rule == "x-long"}
    assert hit["W001-001"] == "W001-001 6.9"  # 2 x 3.45 m
    ((name, rows),), _ = manager.tables_for(project)
    assert name == "wire-count" and rows[0] == ["Harness", "Wires"] and rows[1][0] == "W001"
    assert "system/extensions/wire-count.csv" in build_outputs(project, drawings=False).files
    rt = manager.runtime(project)
    assert rt is not None and set(rt.importers) == {"lines"}
    kinds = {
        (i["kind"], i["name"]): i
        for i in manager.listing(project)["items"]
        if i["source"] == "plugin"
    }
    assert set(kinds) == {
        ("rule", "x-demo"),
        ("field", "wire.double_length"),
        ("table", "wire-count"),
        ("importer", "lines"),
    }
    assert all(
        i["origin"] == "demo" and i["trusted"] is True and len(i["sha256"]) == 64
        for i in kinds.values()
    )


def test_a_plugin_rule_has_an_explanation(folder: Path) -> None:
    add_plugin(folder, plugin_source())
    trust_it(folder)
    project = load_project(folder).project
    f = next(x for x in drc.run(project) if x.rule == "x-demo")
    (d,) = derive.explain_finding(project, "x-demo", f.object_id)
    assert d.id == "rule-check" and d.equation.startswith(
        "this rule is a yes/no check: it compares each harness"
    )
    assert d.text == "harness W001 found" or d.text.startswith("harness ")
    assert (
        "Plug-in rule x-demo from plug-in demo (version 1.2.3, sha256" in d.reference
        and "not part of the tool" in d.reference
    )
    assert derive.is_explainable(project, "x-demo")
    assert not derive.is_explainable(project, "x-nothing")
    assert derive.explain_finding(project, "x-nothing", "W001") == []


def test_a_plugin_travels_to_the_rule_check_process(folder: Path) -> None:
    import pickle

    add_plugin(folder, plugin_source())
    trust_it(folder)
    project = load_project(folder).project
    here = [(f.id, f.title) for f in drc.run(project)]
    assert any(i.startswith("x-demo.") for i, _ in here)
    plugins.forget_loaded()  # the other process has loaded nothing yet
    manager._RUNTIMES.clear()
    there = pickle.loads(pickle.dumps(copy.copy(project)))  # noqa: S301
    assert [(f.id, f.title) for f in drc.run(there)] == here
    # and when trust is gone in that process the plug-in is not used
    trust.revoke("demo")
    plugins.forget_loaded()
    manager._RUNTIMES.clear()
    after = pickle.loads(pickle.dumps(copy.copy(project)))  # noqa: S301
    assert not any(f.rule == "x-demo" for f in drc.run(after))


# ---- installed packages (entry points) ------------------------------------------------------------------------------


def make_dist(
    site: Path,
    module: str,
    name: str,
    version: str = "2.0",
    source: str | None = None,
    extra_files: dict[str, str] | None = None,
) -> Path:
    """An installed package in `site`: a module, a .dist-info with an entry point and a RECORD."""
    site.mkdir(parents=True, exist_ok=True)
    src = (
        source
        if source is not None
        else plugin_source(name).replace('"version": "1.2.3"', f'"version": "{version}"')
    )
    (site / f"{module}.py").write_text(src, encoding="utf-8")
    info = site / f"{module}-{version}.dist-info"
    info.mkdir(exist_ok=True)
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {module}\nVersion: {version}\n")
    (info / "entry_points.txt").write_text(f"[harness_design_studio.plugins]\n{name} = {module}\n")
    files = [
        f"{module}.py",
        f"{module}-{version}.dist-info/METADATA",
        f"{module}-{version}.dist-info/entry_points.txt",
    ]
    for rel, text in (extra_files or {}).items():
        (site / rel).write_text(text)
        files.append(rel)
    (info / "RECORD").write_text("".join(f"{f},,\n" for f in files))
    return site


def test_an_installed_plugin_is_found_hashed_and_gated_like_a_project_one(
    folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = make_dist(tmp_path / "site", "hds_entry_one", "entryone")
    monkeypatch.syspath_prepend(str(site))
    for m in [m for m in sys.modules if m.startswith("hds_entry_one")]:
        del sys.modules[m]
    write_extensions(folder, {}, plugins=["entryone"])
    search = [str(site)]
    ext = manager.discover(folder, search)
    assert ext is not None
    (info,) = ext.plugins
    assert (info.name, info.version, info.kinds, info.source) == (
        "entryone",
        "2.0",
        ("rule",),
        "entry-point",
    )
    assert (
        info.state == "untrusted" and info.where == "hds_entry_one 2.0" and len(info.sha256) == 64
    )
    assert "hds_entry_one" not in sys.modules  # listed, not imported
    trust.trust(info.name, info.sha256, info.version, info.where)
    ext = manager.discover(folder, search)
    assert ext is not None and ext.plugins[0].state == "loaded" and "hds_entry_one" in sys.modules
    # the package changes on disk: new hash, no trust
    (site / "hds_entry_one.py").write_text((site / "hds_entry_one.py").read_text() + "# upgrade\n")
    plugins.forget_loaded()
    again = manager.discover(folder, search)
    assert (
        again is not None
        and again.plugins[0].sha256 != info.sha256
        and again.plugins[0].state == "untrusted"
    )
    # a name the project did not enable stays disabled even when trusted
    write_extensions(folder, {}, plugins=[])
    other = manager.discover(folder, search)
    assert other is not None and other.plugins[0].state == "disabled"
    for m in [m for m in sys.modules if m.startswith("hds_entry_one")]:
        del sys.modules[m]


def test_an_installed_plugin_whose_name_does_not_match_its_entry_point_is_invalid(
    folder: Path, tmp_path: Path
) -> None:
    site = make_dist(
        tmp_path / "site", "hds_entry_two", "entrytwo", source=plugin_source("other-name")
    )
    write_extensions(folder, {}, plugins=["entrytwo"])
    ext = manager.discover(folder, [str(site)])
    assert (
        ext is not None
        and ext.plugins[0].state == "invalid"
        and "not the name of the entry point" in ext.plugins[0].message
    )


def test_a_package_without_readable_python_files_cannot_be_hashed(
    folder: Path, tmp_path: Path
) -> None:
    site = tmp_path / "site"
    site.mkdir()
    info = site / "nopy-1.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: nopy\nVersion: 1.0\n")
    (info / "entry_points.txt").write_text("[harness_design_studio.plugins]\nnopy = nopy\n")
    (info / "RECORD").write_text("nopy-1.0.dist-info/METADATA,,\n")
    write_extensions(folder, {}, plugins=["nopy"])
    ext = manager.discover(folder, [str(site)])
    assert (
        ext is not None
        and ext.plugins[0].state == "invalid"
        and "no hash of its code can be made" in ext.plugins[0].message
    )


# ---- the registry --------------------------------------------------------------------------------------------------


def test_the_registry_lists_built_in_and_extension_items_together(folder: Path) -> None:
    from harness_design_studio.core.extensions.registry import REGISTRY

    add_plugin(folder, plugin_source())
    write_extensions(folder, {"t.json": ext_file(rules=[gauge_rule()])}, plugins=["demo"])
    trust_it(folder)
    project = load_project(folder).project
    items = manager.listing(project)["items"]
    rules = [i for i in items if i["kind"] == "rule"]
    assert [i["name"] for i in rules][:3] == ["duplicate-id", "wire-dangling", "model-inconsistent"]
    assert [i["source"] for i in rules].count("built-in") == 39
    assert {i["name"]: i["source"] for i in rules if i["source"] != "built-in"} == {
        "x-demo": "plugin",
        "x-gauge": "declarative",
    }
    kinds = {i["kind"] for i in items}
    assert kinds == {"rule", "field", "model", "table", "importer", "lookup"} - {"lookup"}
    assert len(REGISTRY.items("rule")) == 39  # the tool's registry is not changed by a project
    assert REGISTRY.get("rule", "x-demo") is None
    with pytest.raises(Exception, match="already registered"):
        REGISTRY.register(REGISTRY.get("rule", "duplicate-id"))  # type: ignore[arg-type]
    modules = [i["name"] for i in items if i["kind"] == "model"]
    assert "model.bundle_basis" in modules and "model.drop_model" in modules


def test_every_registered_rule_is_explained(folder: Path) -> None:
    """The check of the built-in rules (tests/test_s1_rules.py) extended to the registry: a rule of an
    extension, declarative or Python, answers `explain` as well."""
    from harness_design_studio.core.derive_rules import INFO

    add_plugin(folder, plugin_source())
    write_extensions(
        folder,
        {
            "t.json": ext_file(
                rules=[
                    gauge_rule(),
                    gauge_rule(id="other", applies_to="harness", condition="harness.wires <= 1"),
                ]
            )
        },
        plugins=["demo"],
    )
    trust_it(folder)
    project = load_project(folder).project
    rule_items = [i for i in manager.listing(project)["items"] if i["kind"] == "rule"]
    assert len(rule_items) == 39 + 3
    for item in rule_items:
        name = item["name"]
        if item["source"] == "built-in":
            assert name in INFO, name
            continue
        assert derive.is_explainable(project, name), name
        found = [f for f in drc.run(project) if f.rule == name]
        objects = [found[0].object_id] if found else [next(iter(project.harnesses))]
        got = derive.explain_finding(project, name, objects[0])
        assert got and got[0].equation, name


def test_trust_taken_back_elsewhere_stops_a_plugin_that_is_already_in_memory(folder: Path) -> None:
    """The editor holds the project; the person revokes trust in a terminal. The next check, even in
    a process that cached what it built, does not run the plug-in."""
    add_plugin(folder, plugin_source())
    trust_it(folder)
    project = load_project(folder).project
    assert any(f.rule == "x-demo" for f in drc.run(project))
    assert trust.revoke("demo") == 1
    found = drc.run(project)  # the same project object, the same cached runtime
    assert not any(f.rule == "x-demo" for f in found)
