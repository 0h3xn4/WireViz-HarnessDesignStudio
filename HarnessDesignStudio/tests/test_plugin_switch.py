# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,union-attr"
"""REQ-OFFLINE-05: Python plug-ins can be switched off on a computer, by an environment variable or
by a machine-wide policy file that an IT department controls (D-203).

What is checked: while the switch is on, a plug-in that the project enables and the user trusted is
never imported (a module with a side effect at import time does not run), in this process and in a
fresh interpreter, whatever the project or the trust list says; a plug-in loaded earlier in the
process is not handed out again; the data-only extensions still apply; the `extensions`, `trust`
and `import-plugin` commands and the Help > Extensions page say so plainly; a policy file that
cannot be read or is not understood also switches them off (it fails closed); nothing can switch
them back on that the switch turned off; and the default (no variable, no file) is as before."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness_design_studio.core import drc, templates
from harness_design_studio.core.extensions import manager, plugins, policy, trust
from harness_design_studio.core.io.loader import load_project
from tests.ext_helpers import ext_file, gauge_rule, write_extensions

ROOT = Path(__file__).resolve().parents[1]
REAL_POLICY_PATH = policy.policy_path  # taken before conftest replaces it for each test

SOURCE = """\
with open({marker!r}, "a") as _f:
    _f.write("imported\\n")

PLUGIN = {{"name": "demo", "version": "1.0.0", "api": 1, "kinds": ["rule"], "description": "t"}}


def register(api):
    def check(project):
        for u in sorted(project.units):
            yield api.Hit(u, "device " + u)

    api.rule("x-demo", title="Demo", severity="info", why="w", how="h",
             compares="each device with nothing", check=check)
"""


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    """A project that enables a plug-in with a side effect at import and a data-only rule file."""
    target = tmp_path / "p"
    templates.create_project(target, "first-steps")
    (target / "extensions" / "plugins").mkdir(parents=True)
    marker = tmp_path / "marker.txt"
    (target / "extensions" / "plugins" / "demo.py").write_text(
        SOURCE.format(marker=str(marker)), encoding="utf-8"
    )
    write_extensions(
        target,
        {"gauge.json": ext_file("gauge", rules=[gauge_rule()])},
        plugins=["demo"],
    )
    plugins.forget_loaded()
    manager._RUNTIMES.clear()
    return target


def marker(folder: Path) -> Path:
    return folder.parent / "marker.txt"


def trust_demo(folder: Path) -> None:
    ext = load_project(folder).project.extensions
    info = next(p for p in ext.plugins if p.name == "demo")
    trust.trust(info.name, info.sha256, info.version, info.where)
    plugins.forget_loaded()
    manager._RUNTIMES.clear()


def demo_state(folder: Path) -> plugins.PluginInfo:
    ext = load_project(folder).project.extensions
    info: plugins.PluginInfo = next(p for p in ext.plugins if p.name == "demo")
    return info


def use_policy(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setattr(policy, "policy_path", lambda: path)


# ---- the default is as before ---------------------------------------------------------------------


def test_without_the_switch_an_enabled_and_trusted_plugin_loads_as_before(folder: Path) -> None:
    assert policy.plugins_blocked() == ""
    trust_demo(folder)
    assert demo_state(folder).state == plugins.LOADED
    assert marker(folder).read_text() == "imported\n"


@pytest.mark.parametrize("value", ["", "0", "  "])
def test_an_empty_or_zero_variable_does_not_switch_them_off(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(policy.ENV_NO_PLUGINS, value)
    assert policy.plugins_blocked() == ""


# ---- the environment variable ---------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "yes", "true", "off"])
def test_the_variable_switches_them_off_and_nothing_is_imported(
    folder: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    trust_demo(folder)
    monkeypatch.setenv(policy.ENV_NO_PLUGINS, value)
    info = demo_state(folder)
    assert info.state == plugins.BLOCKED and info.enabled and info.trusted
    assert policy.ENV_NO_PLUGINS in info.message and "switched off" in info.message
    project = load_project(folder).project
    found = drc.run(project)
    assert not marker(folder).exists()
    rules = {f.rule for f in found}
    assert "x-demo" not in rules
    problem = next(f for f in found if f.rule == "x-extension-problem")
    assert "demo" in problem.title and "switched off" in problem.title
    # the data-only rule file still applies
    assert manager.listing(project)["files"][0]["status"] == "applied"
    assert "x-gauge" in {r.id for r in manager.rules_for(project)}


def test_a_plugin_loaded_before_the_switch_is_not_handed_out_after_it(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trust_demo(folder)
    project = load_project(folder).project
    assert "x-demo" in {f.rule for f in drc.run(project)}
    monkeypatch.setenv(policy.ENV_NO_PLUGINS, "1")
    manager._RUNTIMES.clear()
    assert "x-demo" not in {f.rule for f in drc.run(project)}  # the project read before the switch
    ext = project.extensions
    info = next(p for p in ext.plugins if p.name == "demo")
    done = plugins.load(manager._plugin_candidate(info), folder)
    assert done.problem.startswith("Python plug-ins are switched off") and not done.items


# ---- the machine-wide policy file -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "blocked"),
    [
        (json.dumps({"python_plugins": "off"}), True),
        (json.dumps({"python_plugins": "allowed"}), False),
        (json.dumps({}), True),  # a file that does not allow them switches them off
        (json.dumps({"python_plugins": "on"}), True),  # only the one word allows them
        ("{", True),  # damaged: fails closed
        ("", True),
        ("[1, 2]", True),
        ("\xff\xfe", True),
    ],
)
def test_the_policy_file_switches_them_off_and_fails_closed(
    folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str, blocked: bool
) -> None:
    trust_demo(folder)
    path = tmp_path / "etc" / "policy.json"
    path.parent.mkdir()
    path.write_text(text, encoding="latin-1")
    use_policy(monkeypatch, path)
    reason = policy.plugins_blocked()
    assert bool(reason) is blocked
    if blocked:
        assert str(path) in reason
    state = demo_state(folder).state
    assert state == (plugins.BLOCKED if blocked else plugins.LOADED)
    assert marker(folder).exists() is not blocked


def test_a_policy_file_that_cannot_be_read_switches_them_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "policy.json"
    folder.mkdir()  # a folder where the file should be: it exists and cannot be read as a file
    use_policy(monkeypatch, folder)
    assert "could not be read" in policy.plugins_blocked()


def test_nothing_turns_them_back_on(
    folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The policy file allowing them does not undo the variable, and neither undoes the other."""
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"python_plugins": "allowed"}), encoding="utf-8")
    use_policy(monkeypatch, path)
    monkeypatch.setenv(policy.ENV_NO_PLUGINS, "1")
    assert policy.plugins_blocked()
    monkeypatch.delenv(policy.ENV_NO_PLUGINS)
    path.write_text(json.dumps({"python_plugins": "off"}), encoding="utf-8")
    assert policy.plugins_blocked()


def test_the_path_of_the_policy_file_cannot_be_moved_by_the_user(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No variable or setting of the user moves the file (that would let a user point the program at
    a file of their own). On Windows it is in ProgramData, which only the machine sets."""
    for name in (trust.ENV_DIR, "XDG_CONFIG_HOME", "HOME", "APPDATA", "LOCALAPPDATA"):
        monkeypatch.setenv(name, str(tmp_path / "mine"))
    path = REAL_POLICY_PATH()
    assert str(tmp_path) not in str(path)
    if sys.platform == "win32":
        assert path.parts[-2:] == ("HarnessDesignStudio", "policy.json")
    else:
        assert path == Path("/etc/harness-design-studio/policy.json")


# ---- what a person sees ---------------------------------------------------------------------------


def _cli(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "harness_design_studio.cli.main", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, check=False,
    )  # fmt: skip


def test_in_a_fresh_interpreter_the_commands_say_so_and_import_nothing(
    folder: Path, tmp_path: Path
) -> None:
    """The guarantee as an IT department meets it: with the variable set, `drc`, `check`,
    `extensions`, `export` and `import-plugin` import no plug-in although the user trusted it, and
    `trust` refuses to trust one."""
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
        trust.ENV_DIR: str(tmp_path / "me"),
        "QT_QPA_PLATFORM": "offscreen",
    }
    done = _cli(["trust", str(folder), "demo", "--yes"], env)
    assert done.returncode == 0, done.stderr
    off = {**env, policy.ENV_NO_PLUGINS: "1"}
    for args in (["drc", str(folder)], ["check", str(folder)], ["extensions", str(folder)],
                 ["export", str(folder), "--out", str(tmp_path / "out")]):  # fmt: skip
        run = _cli(args, off)
        assert run.returncode in (0, 1), (args, run.stderr)
        assert not marker(folder).exists(), args
    listing = _cli(["extensions", str(folder)], off)
    assert "Python plug-ins are switched off on this computer" in listing.stdout
    assert "blocked" in listing.stdout and "demo" in listing.stdout
    as_json = json.loads(_cli(["extensions", str(folder), "--json"], off).stdout)
    assert policy.ENV_NO_PLUGINS in as_json["python_plugins_blocked"]
    assert [p["state"] for p in as_json["plugins"]] == ["blocked"]
    refused = _cli(["trust", str(folder), "demo", "--yes"], off)
    assert refused.returncode == 2 and "switched off" in refused.stderr
    revoke = _cli(["trust", str(folder), "demo", "--revoke"], off)
    assert revoke.returncode == 0
    importer = _cli(["import-plugin", str(folder), "x", str(folder / "project.json")], off)
    assert importer.returncode == 2 and "switched off" in importer.stderr
    assert not marker(folder).exists()
    # and without the variable the same user's trusted plug-in is imported (the revoke above took
    # the trust back, so trust it again first)
    assert _cli(["trust", str(folder), "demo", "--yes"], env).returncode == 0
    assert _cli(["drc", str(folder)], env).returncode in (0, 1)
    assert marker(folder).exists()


@pytest.mark.gui
def test_the_extensions_page_says_so_and_offers_no_trust(
    qtbot, folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("PySide6")
    from harness_design_studio.gui.controller import EditorController
    from harness_design_studio.gui.extensions_dialog import ExtensionsDialog
    from harness_design_studio.gui.theme import ThemeManager

    monkeypatch.setenv(policy.ENV_NO_PLUGINS, "1")
    c = EditorController(drc_delay_ms=30)
    c.open_path(folder)
    try:
        dlg = ExtensionsDialog(None, ThemeManager(), c)
        qtbot.addWidget(dlg)
        dlg.show()
        assert dlg.plugins_off.isVisibleTo(dlg)
        assert dlg.plugins_off.text().startswith("Python plug-ins are switched off")
        dlg.plugins.selectRow(0)
        assert dlg.selected_plugin().state == plugins.BLOCKED
        assert not dlg.trust_btn.isEnabled()
        assert not marker(folder).exists()
    finally:
        c.release()
    monkeypatch.delenv(policy.ENV_NO_PLUGINS)
    c2 = EditorController(drc_delay_ms=30)
    c2.open_path(folder)
    try:
        dlg2 = ExtensionsDialog(None, ThemeManager(), c2)
        qtbot.addWidget(dlg2)
        dlg2.show()
        assert not dlg2.plugins_off.isVisibleTo(dlg2)
    finally:
        c2.release()
    shutil.rmtree(folder / "extensions")
