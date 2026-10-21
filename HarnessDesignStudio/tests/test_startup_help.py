# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""The Linux package must start without hassle: what the editor does when the machine lacks a
graphics or window-system library, or has no desktop session, and the proof that a package does
not lean on the Python of the machine (the CI smoke test runs it without one). REQ-START-01."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from harness_design_studio.gui import startup_help
from tests.test_installers import (
    ROOT,
    _load_gui_entry,  # noqa: PLC2701
    fake_package,
    run_script,
)


def missing_loader(*gone: str):
    def load(name: str) -> object:
        if name in gone:
            raise OSError(f"{name}: cannot open shared object file: No such file or directory")
        return object()

    return load


def test_nothing_is_reported_when_every_library_loads() -> None:
    assert startup_help.missing_libraries(missing_loader(), "linux") == []


def test_a_missing_library_is_named_with_its_ubuntu_package() -> None:
    got = startup_help.missing_libraries(missing_loader("libEGL.so.1", "libxcb.so.1"), "linux")
    assert got == [("libEGL.so.1", "libegl1"), ("libxcb.so.1", "libxcb1")]


def test_only_linux_is_checked() -> None:
    gone = missing_loader(*(f for f, _p in startup_help.REQUIRED))
    assert startup_help.missing_libraries(gone, "win32") == []
    assert len(startup_help.missing_libraries(gone, "linux")) == len(startup_help.REQUIRED)


def test_the_message_says_what_is_missing_and_the_command_that_fixes_it() -> None:
    text = startup_help.message([("libGL.so.1", "libgl1"), ("libEGL.so.1", "libegl1")])
    assert "libGL.so.1, libEGL.so.1" in text
    assert "sudo apt install libegl1 libgl1" in text  # sorted, once each
    assert "Python and Qt are inside it" in text


def test_a_library_that_is_not_known_is_named_without_a_package() -> None:
    text = startup_help.message([("libweird.so.9", "")])
    assert "libweird.so.9" in text and "sudo apt" not in text


def test_the_text_of_an_import_error_names_the_library() -> None:
    err = "libEGL.so.1: cannot open shared object file: No such file or directory"
    assert startup_help.from_error(err) == [("libEGL.so.1", "libegl1")]
    two = f"{err}\nlibweird.so.9: cannot open shared object file\n{err}"
    assert startup_help.from_error(two) == [("libEGL.so.1", "libegl1"), ("libweird.so.9", "")]
    assert startup_help.from_error("ModuleNotFoundError: No module named 'x'") == []


def test_every_required_library_is_one_the_message_knows_and_the_deb_depends_on() -> None:
    deb = (ROOT / "tools" / "build_deb.py").read_text(encoding="utf-8")
    for soname, package in startup_help.REQUIRED:
        assert startup_help.KNOWN[soname] == package
        assert package in deb or package == "libxcb1", package  # libxcb1 comes with libxcb-*


@pytest.mark.parametrize(
    ("env", "want"),
    [
        ({}, True),
        ({"DISPLAY": ":0"}, False),
        ({"WAYLAND_DISPLAY": "wayland-0"}, False),
        ({"QT_QPA_PLATFORM": "offscreen"}, False),  # tests, CI and the self-test
        ({"DISPLAY": ""}, True),
    ],
)
def test_no_graphical_session_is_noticed_on_linux_only(env, want) -> None:
    assert startup_help.no_display(env, "linux") is want
    assert startup_help.no_display(env, "win32") is False


def test_the_entry_runs_only_the_check_for_check_system(monkeypatch, capsys) -> None:
    entry = _load_gui_entry()
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.setattr(startup_help, "missing_libraries", lambda *a, **k: [])
    assert entry._check_system(["prog", "--check-system"]) == 0
    assert "system libraries ok" in capsys.readouterr().out
    gone = [("libEGL.so.1", "libegl1")]
    told: list[str] = []
    monkeypatch.setattr(startup_help, "missing_libraries", lambda *a, **k: gone)
    monkeypatch.setattr(entry, "_tell", told.append)
    assert entry._check_system(["prog", "--check-system"]) == startup_help.EXIT_CODE
    assert "sudo apt install libegl1" in told[0]


def test_the_selftest_and_an_explicit_platform_skip_the_check(monkeypatch) -> None:
    entry = _load_gui_entry()
    boom = pytest.fail
    monkeypatch.setattr(startup_help, "missing_libraries", lambda *a, **k: boom("checked"))
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    assert entry._check_system(["prog", "--selftest"]) is None
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert entry._check_system(["prog"]) is None


def test_a_start_without_a_desktop_says_so(monkeypatch) -> None:
    entry = _load_gui_entry()
    told: list[str] = []
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(startup_help, "missing_libraries", lambda *a, **k: [])
    monkeypatch.setattr(startup_help, "no_display", lambda *a, **k: True)
    monkeypatch.setattr(entry, "_tell", told.append)
    assert entry._check_system(["prog"]) == startup_help.EXIT_CODE
    assert told == [startup_help.NO_DISPLAY_MESSAGE]


def test_the_package_runs_on_its_own_python_check_passes_from_source() -> None:
    entry = _load_gui_entry()
    assert entry._runs_from_its_own_python() is True  # not frozen: the question does not arise


def test_install_warns_when_the_system_check_fails_but_still_installs(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    gui = pkg / "harness-design-studio-gui"
    gui.write_text(
        '#!/bin/sh\nif [ "$1" = --check-system ]; then echo "needs libEGL.so.1"; exit 3; fi\n'
    )
    gui.chmod(0o755)
    r = run_script(pkg / "install.sh", tmp_path, "--prefix", str(tmp_path / "opt"))
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "opt" / "harness-design-studio-gui").is_file()
    assert "WARNING: the editor will not start yet." in r.stderr
    assert "needs libEGL.so.1" in r.stderr


def test_install_is_quiet_when_the_system_check_passes(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    r = run_script(pkg / "install.sh", tmp_path, "--prefix", str(tmp_path / "opt"))
    assert r.returncode == 0 and "WARNING" not in r.stderr


def test_the_smoke_test_environment_has_no_python(tmp_path: Path, monkeypatch) -> None:
    from tools import smoke_package

    with_python = tmp_path / "py"
    with_python.mkdir()
    (with_python / "python3").write_text("")
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("PATH", os.pathsep.join([str(with_python), str(plain)]))
    monkeypatch.setenv("PYTHONPATH", "/x")
    monkeypatch.setenv("PYTHONHOME", "/y")
    monkeypatch.setenv("VIRTUAL_ENV", "/z")
    env = smoke_package.clean_env({"QT_QPA_PLATFORM": "offscreen"})
    assert env["PATH"] == str(plain)
    assert not any(k.upper().startswith("PYTHON") for k in env)
    assert "VIRTUAL_ENV" not in env and env["QT_QPA_PLATFORM"] == "offscreen"


def test_the_smoke_test_runs_the_packages_in_that_environment() -> None:
    text = (ROOT / "tools" / "smoke_package.py").read_text(encoding="utf-8")
    assert "clean_env()" in text and 'walkthrough([str(cli)], work / "frozen", bare)' in text


@pytest.mark.skipif(sys.platform != "linux", reason="needs the Linux loader")
def test_check_system_from_the_real_entry_reports_ok_or_names_what_is_missing(tmp_path) -> None:
    """On the machine that runs the tests: either everything is there, or the message says what."""
    r = subprocess.run(
        [sys.executable, "-P", str(ROOT / "packaging/gui_entry.py"), "--check-system"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path), "QT_QPA_PLATFORM": ""},
        check=False,
        timeout=120,
    )
    if r.returncode == 0:
        assert "system libraries ok" in r.stdout
    else:
        assert r.returncode == startup_help.EXIT_CODE and "sudo apt install" in r.stderr


def test_ci_runs_the_tarball_on_the_smallest_machine_it_supports() -> None:
    """A package that works only next to a full set of libraries is not "just run it": CI starts the
    tarball in a bare Ubuntu with no Python and only the three libraries it cannot carry."""
    script = (ROOT / "packaging/ubuntu/container/minimal-machine-test.sh").read_text()
    needed = " ".join(p for _f, p in startup_help.REQUIRED)
    assert "libgl1 libegl1 libxcb1" in script and needed.split()[0] in script
    assert "--network none" in script and "must have no Python" in script
    assert "--check-system" in script and "--selftest" in script and "xvfb-run" in script
    workflow = (ROOT.parent / ".github/workflows/harness-ci.yml").read_text()
    assert "minimal-machine-test.sh" in workflow
    # checkout cleans the workspace: it must come before the artifact is downloaded
    job = workflow[workflow.index("package-on-24-04:") :]
    assert job.index("actions/checkout") < job.index("actions/download-artifact")


def test_the_smoke_environment_keeps_the_system_folders_even_with_a_stub_python(
    tmp_path: Path, monkeypatch
) -> None:
    """A system keeps its own `python3` in /usr/bin; removing that folder takes `dirname` and the
    like away from the launcher scripts of a package."""
    from tools import smoke_package

    system = tmp_path / "usr-bin"
    system.mkdir()
    (system / "python3").write_text("")
    runner = tmp_path / "runner"
    runner.mkdir()
    (runner / "python3").write_text("")
    monkeypatch.setattr(smoke_package, "SYSTEM_FOLDERS", (str(system),))
    monkeypatch.setenv("PATH", os.pathsep.join([str(system), str(runner)]))
    env = smoke_package.clean_env()
    assert env["PATH"] == str(system)


def _frozen(monkeypatch, exe: Path, meipass: Path, path: list[Path]) -> Any:
    entry = _load_gui_entry()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "path", [str(p) for p in path])
    return entry


def test_a_package_that_imports_from_outside_itself_fails_the_check(tmp_path, monkeypatch) -> None:
    pkg = tmp_path / "pkg"
    (pkg / "_internal").mkdir(parents=True)
    outside = tmp_path / "site-packages"
    outside.mkdir()
    entry = _frozen(
        monkeypatch,
        pkg / "harness-design-studio-gui",
        pkg / "_internal",
        [pkg / "_internal" / "base_library.zip", outside],
    )
    assert entry._runs_from_its_own_python() is False
    assert _frozen(
        monkeypatch, pkg / "x", pkg / "_internal", [pkg / "_internal" / "base_library.zip"]
    )._runs_from_its_own_python()
    assert not _frozen(monkeypatch, pkg / "x", pkg / "_internal", [])._runs_from_its_own_python()
