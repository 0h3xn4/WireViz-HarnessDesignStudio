"""D-149: the Windows and macOS packages. The scripts run on those systems (the workflow
`harness-packages.yml` builds and tests the real files); here the parts that do not need them."""

import os
import plistlib
import re
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ISS = ROOT / "packaging" / "windows" / "harness-design-studio.iss"


def test_the_file_names_are_the_ones_the_release_notes_expect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import build_macos, build_windows
    from tools import release_notes as rn

    v = "9.9.9"
    monkeypatch.setattr("platform.machine", lambda: "arm64")
    names = [build_windows.setup_name(v), build_windows.zip_name(v), build_macos.dmg_name(v)]
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    names.append(build_macos.dmg_name(v))
    assert names == [
        "harness-design-studio-9.9.9-windows-x86_64-setup.exe",
        "harness-design-studio-9.9.9-windows-x86_64.zip",
        "harness-design-studio-9.9.9-macos-arm64.dmg",
        "harness-design-studio-9.9.9-macos-x86_64.dmg",
    ]
    assert {package.key for package, _ in rn._found(v, names)} == {
        "win-setup",
        "win-zip",
        "mac-arm",
        "mac-intel",
    }
    # the setup program's name in the Inno Setup script is the same pattern
    iss = ISS.read_text(encoding="utf-8")
    assert "OutputBaseFilename=harness-design-studio-{#AppVersion}-windows-x86_64-setup" in iss


def test_a_release_needs_a_file_of_every_kind() -> None:
    from tools import release_notes as rn

    v = "9.9.9"
    names = [
        f"harness-design-studio_{v}_amd64.deb",
        f"harness-design-studio-{v}-linux-x86_64.tar.gz",
        f"harness-design-studio-{v}-windows-x86_64-setup.exe",
        f"harness-design-studio-{v}-windows-x86_64.zip",
        f"harness-design-studio-{v}-macos-arm64.dmg",
        f"harness-design-studio-{v}-macos-x86_64.dmg",
    ]
    assert rn.missing_packages(v, names) == []
    gone = rn.missing_packages(v, names[:4] + names[5:])
    assert gone == [f"harness-design-studio-{v}-macos-arm64.dmg"]
    assert len(rn.missing_packages(v, [])) == 6


def test_the_checksum_file_covers_every_kind_of_package(tmp_path: Path) -> None:
    from harness_design_studio import __version__
    from tools import gen_scf

    for suffix in (".exe", ".zip", ".dmg", ".deb", ".tar.gz", ".txt"):
        (tmp_path / f"harness-design-studio-{__version__}{suffix}").write_text("x")
    found = gen_scf.build_scf(dist=tmp_path)["deliverables"]
    assert isinstance(found, dict) and sorted(Path(n).suffix for n in found) == sorted(
        [".exe", ".zip", ".dmg", ".deb", ".gz"]
    )


def test_the_numeric_version_of_the_setup_program() -> None:
    from tools.build_windows import numeric_version

    assert numeric_version("1.2.0") == "1.2.0.0"
    assert numeric_version("1.2.0rc1") == "1.2.0.0"
    with pytest.raises(ValueError, match="three numbers"):
        numeric_version("dev")


def test_the_portable_zip_is_the_same_whenever_it_is_built(tmp_path: Path) -> None:
    from tools.build_windows import make_zip

    folder = tmp_path / "app"
    (folder / "cli").mkdir(parents=True)
    (folder / "harness-design-studio-gui.exe").write_bytes(b"gui")
    (folder / "cli" / "harness-design-studio.exe").write_bytes(b"cli")
    (folder / "README-windows.txt").write_text("read me")
    first = make_zip(folder, tmp_path / "a.zip", 1_700_000_000).read_bytes()
    os.utime(folder / "README-windows.txt", (1, 1))  # file times do not matter
    second = make_zip(folder, tmp_path / "b.zip", 1_700_000_000).read_bytes()
    assert first == second
    with zipfile.ZipFile(tmp_path / "a.zip") as zf:
        # no top folder: Explorer's "Extract All" makes a folder named like the file
        assert zf.namelist() == [
            "README-windows.txt",
            "cli/harness-design-studio.exe",
            "harness-design-studio-gui.exe",
        ]
        assert zf.read("cli/harness-design-studio.exe") == b"cli"


def test_the_setup_script_installs_per_user_and_reaches_no_network() -> None:
    iss = ISS.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss and "DefaultDirName={autopf}\\" in iss
    assert "ChangesEnvironment=yes" in iss and "InfoBeforeFile=" in iss
    assert "{autoprograms}" in iss and "UninstallDisplayIcon" in iss
    # the two folders on the user's PATH: the command line tool and the editor
    assert iss.count("AddToUserPath(") == 3 and iss.count("RemoveFromUserPath(") == 3
    assert "HKCU" in iss and "HKLM" not in iss and "HKEY_LOCAL_MACHINE" not in iss
    for network in (
        "http://",
        "https://",
        "DownloadTemporaryFile",
        "InitializeWizard",
        "InstallDLL",
    ):
        assert network not in iss, network
    # the application id is a GUID, the same one the smoke test looks for in the registry
    from tools.smoke_package import app_id

    assert re.fullmatch(r"\{[0-9A-F-]{36}\}", app_id())


def test_the_windows_readme_names_the_programs_and_the_smartscreen_steps() -> None:
    text = (ROOT / "packaging" / "windows" / "README-windows.txt").read_text(encoding="utf-8")
    for needed in (
        "harness-design-studio-gui.exe",
        "cli\\harness-design-studio.exe",
        "More info",
        "Run anyway",
        "--selftest-out",
    ):
        assert needed in text, needed


def test_the_app_bundle_describes_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import build_macos

    monkeypatch.setattr("platform.machine", lambda: "arm64")
    plist = build_macos.info_plist({"CFBundleIconFile": "x.icns", "CFBundleVersion": "0.0.0"})
    assert plist["CFBundleIdentifier"] == "org.harnessdesignstudio.app"
    assert plist["CFBundleName"] == plist["CFBundleDisplayName"] == "Harness Design Studio"
    assert plist["CFBundleExecutable"] == "harness-design-studio-gui"
    assert plist["LSMinimumSystemVersion"] == "13.0" and plist["NSHighResolutionCapable"] is True
    assert plist["LSApplicationCategoryType"] == "public.app-category.developer-tools"
    from harness_design_studio import __version__

    assert plist["CFBundleShortVersionString"] == plist["CFBundleVersion"] == __version__
    assert plist["CFBundleIconFile"] == "x.icns"  # PyInstaller's own keys stay
    plistlib.dumps(plist)  # it can be written


def test_the_macos_command_launcher_is_valid_shell_and_follows_links(tmp_path: Path) -> None:
    from tools import build_macos

    app = tmp_path / "App.app" / "Contents"
    (app / "MacOS").mkdir(parents=True)
    cli = app / "Resources" / "cli"
    cli.mkdir(parents=True)
    (cli / "harness-design-studio").write_text('#!/bin/sh\necho "cli $*"\n')
    (cli / "harness-design-studio").chmod(0o755)
    launcher = app / "MacOS" / "harness-design-studio"
    launcher.write_text(build_macos.LAUNCHER, encoding="utf-8")
    launcher.chmod(0o755)
    assert subprocess.run(["sh", "-n", str(launcher)], check=False).returncode == 0
    link = tmp_path / "bin" / "harness"  # a link from a folder on the PATH
    link.parent.mkdir()
    link.symlink_to(launcher)
    for command in (launcher, link):
        done = subprocess.run(
            [str(command), "--version"], capture_output=True, text=True, check=False
        )
        assert done.stdout.strip() == "cli --version", (command, done.stderr)


def test_the_dmg_command_and_signing_files_are_shipped() -> None:
    pk = ROOT / "packaging" / "macos"
    entitlements = plistlib.loads((pk / "entitlements.plist").read_bytes())
    # only what a frozen Python program needs; no network, camera, microphone or file access rights
    assert set(entitlements) == {
        "com.apple.security.cs.allow-unsigned-executable-memory",
        "com.apple.security.cs.disable-library-validation",
    }
    text = (pk / "README-macos.txt").read_text(encoding="utf-8")
    assert "xattr -dr com.apple.quarantine" in text and "Open" in text


def test_the_ico_holds_png_images_of_the_logo(tmp_path: Path) -> None:
    from tools import make_icons

    ico = make_icons.write_ico(tmp_path / "logo.ico").read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", ico)
    assert (reserved, kind, count) == (0, 1, len(make_icons.ICO_SIZES))
    sizes = []
    for i in range(count):
        width, _, _, _, _, bits, length, offset = struct.unpack_from("<BBBBHHII", ico, 6 + 16 * i)
        assert bits == 32 and ico[offset : offset + 8] == b"\x89PNG\r\n\x1a\n"
        assert len(ico[offset : offset + length]) == length
        sizes.append(width or 256)
    assert sizes == list(make_icons.ICO_SIZES)


def test_the_iconset_covers_the_sizes_of_apple() -> None:
    from tools import make_icons

    names = {name for name, _ in make_icons.ICONSET}
    assert {"icon_16x16.png", "icon_512x512@2x.png"} <= names
    assert {size for _, size in make_icons.ICONSET} == {16, 32, 64, 128, 256, 512, 1024}


def test_the_package_check_ignores_shared_libraries_of_windows_and_macos(tmp_path: Path) -> None:
    from tools.build_installer import undeclared_files

    internal = tmp_path / "_internal"
    internal.mkdir()
    for name in (
        "python312.dll",
        "VCRUNTIME140.dll",
        "api-ms-win-core-file-l1-1-0.dll",
        "Python.dylib",
    ):
        (internal / name).write_text("x")
    for name in ("pydantic_core", "PySide6", "harness_design_studio", "_ctypes.pyd"):
        (internal / name).mkdir()
    assert undeclared_files(internal) == []
    (internal / "chardet").mkdir()
    (internal / "stray.cp312-win_amd64.pyd").write_text("x")  # an extension module is code
    assert undeclared_files(internal) == ["chardet", "stray"]


def test_the_package_check_follows_the_qt_links_and_names_of_the_macos_bundle(
    tmp_path: Path,
) -> None:
    from tools.build_installer import undeclared_files

    frameworks = tmp_path / "Frameworks"
    (frameworks / "PySide6" / "Qt" / "lib" / "QtCore.framework" / "Versions" / "A").mkdir(
        parents=True
    )
    qt = frameworks / "PySide6" / "Qt" / "lib" / "QtCore.framework" / "Versions" / "A" / "QtCore"
    qt.write_text("x")
    (frameworks / "QtCore").symlink_to(qt.relative_to(frameworks))
    (frameworks / "Python").write_text("x")
    (frameworks / "python3__dot__12").write_text("x")
    assert undeclared_files(frameworks) == []
    other = tmp_path / "elsewhere"
    other.write_text("x")
    (frameworks / "QtStray").symlink_to(other)  # a link to something that is not a known package
    (frameworks / "pythonista").write_text("x")
    assert undeclared_files(frameworks) == ["QtStray", "pythonista"]


def test_the_licence_texts_are_in_the_repository_for_systems_without_debian(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tools import collect_licences

    for name in ("LGPL-3", "GPL-3"):
        text = (collect_licences.BUNDLED / name).read_text(encoding="utf-8")
        assert "GNU" in text and "Version 3, 29 June 2007" in text
    monkeypatch.setattr(collect_licences, "COMMON", tmp_path / "no-such-folder")
    collect_licences.collect(tmp_path / "LICENSES")
    assert (tmp_path / "LICENSES" / "LGPL-3.txt").is_file()
    assert (tmp_path / "LICENSES" / "GPL-3.txt").is_file()


def _load_gui_entry() -> object:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gui_entry_for_windows", ROOT / "packaging/gui_entry.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_editor_reports_the_selftest_in_a_file_for_the_windows_editor_without_console(
    tmp_path: Path,
) -> None:
    entry = _load_gui_entry()
    out = entry._selftest_out  # type: ignore[attr-defined]
    assert out(["prog", "--selftest", "--selftest-out", "r.txt"]) == Path("r.txt")
    assert out(["prog", "--selftest"]) is None
    assert out(["prog", "--selftest", "--selftest-out"]) is None
    assert out(["prog", "--selftest", "other", "r.txt"]) is None


def test_a_failing_selftest_writes_what_failed_and_an_error_writes_its_traceback(
    tmp_path: Path,
) -> None:
    code = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('entry', {str(ROOT / 'packaging/gui_entry.py')!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "from pathlib import Path\n"
        f"out = Path({str(tmp_path / 'result.txt')!r})\n"
        "m._fonts_are_bundled = lambda: False\n"
        "assert m.selftest(out) == 1\n"
        "assert out.read_text() == 'selftest FAILED at: bundled fonts\\n', out.read_text()\n"
        "def boom(tmp): raise RuntimeError('boom')\n"
        "m._run_steps = boom\n"
        "assert m.selftest(out) == 1\n"
        "assert 'selftest FAILED with an error' in out.read_text() and 'boom' in out.read_text()\n"
    )
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": os.pathsep.join(sys.path)}
    r = subprocess.run(
        [sys.executable, "-P", "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=300,
    )
    assert r.returncode == 0, (r.stdout, r.stderr[-800:])


def test_the_smoke_test_compares_with_the_source_install_and_finds_its_files(
    tmp_path: Path,
) -> None:
    """The walk-through the workflows run on the finished packages, here against the source."""
    from tools import smoke_package

    problems, files = smoke_package.walkthrough(
        [sys.executable, "-m", "harness_design_studio.cli.main"], tmp_path / "one"
    )
    assert problems == [] and files
    again = smoke_package.source_reference(tmp_path / "two")
    assert files == again  # the same commands give the same bytes
    broken, _ = smoke_package.walkthrough(
        [sys.executable, "-c", "raise SystemExit(3)"], tmp_path / "x"
    )
    assert broken and "ended with 3" in broken[0]


def test_the_smoke_test_checks_the_app_bundle_plist(tmp_path: Path) -> None:
    from harness_design_studio import __version__
    from tools import smoke_package

    app = tmp_path / "Harness Design Studio.app"
    (app / "Contents" / "Resources").mkdir(parents=True)
    plist = {
        "CFBundleIdentifier": "org.harnessdesignstudio.app",
        "CFBundleShortVersionString": __version__,
        "CFBundleExecutable": "harness-design-studio-gui",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "CFBundleIconFile": "icon.icns",
    }
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(plist))
    (app / "Contents" / "Resources" / "icon.icns").write_bytes(b"icns")
    assert smoke_package.plist_problems(app) == []
    plist["LSMinimumSystemVersion"] = "10.0"
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(plist))
    assert "LSMinimumSystemVersion" in smoke_package.plist_problems(app)[0]


def test_the_build_scripts_refuse_the_wrong_system() -> None:
    if sys.platform == "win32":
        pytest.skip("this is the system the Windows script builds on")
    from tools import build_macos, build_windows

    assert build_windows.main([]) == 1
    if sys.platform != "darwin":
        assert build_macos.main() == 1
