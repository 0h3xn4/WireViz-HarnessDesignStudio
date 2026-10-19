"""M7: Ubuntu packaging (D-110): install and uninstall scripts, desktop entry, icon and the .deb."""

import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET  # noqa: S405
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
PK = ROOT / "packaging" / "ubuntu"


def fake_package(tmp: Path) -> Path:
    """A package folder as build_installer makes it, with stub programs instead of PyInstaller output."""
    pkg = tmp / "harness-design-studio"
    (pkg / "cli").mkdir(parents=True)
    (pkg / "_internal").mkdir()
    (pkg / "_internal" / "lib.txt").write_text("x")
    for exe in (pkg / "harness-design-studio-gui", pkg / "cli" / "harness-design-studio"):
        exe.write_text('#!/bin/sh\necho stub "$@"\n')
        exe.chmod(0o755)
    for item in PK.iterdir():
        if item.is_file():
            shutil.copy2(item, pkg / item.name)
    return pkg


def run_script(script: Path, tmp: Path, *args: str) -> subprocess.CompletedProcess[str]:
    if sys.platform != "linux":
        pytest.skip("install.sh and uninstall.sh are the Linux tarball's scripts (GNU tools)")
    env = {**os.environ, "HARNESS_INSTALL_ROOT": str(tmp / "root"), "HOME": str(tmp / "home")}
    return subprocess.run(
        ["sh", str(script), *args], capture_output=True, text=True, env=env, check=False
    )


def test_install_then_uninstall_leaves_nothing_behind(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    prefix = tmp_path / "opt"
    r = run_script(pkg / "install.sh", tmp_path, "--prefix", str(prefix))
    assert r.returncode == 0, r.stderr
    root = tmp_path / "root"
    assert (
        (prefix / "harness-design-studio-gui").is_file()
        and (prefix / "cli" / "harness-design-studio").is_file()
        and (prefix / "_internal" / "lib.txt").is_file()
    )
    link = root / "bin" / "harness-design-studio"  # the command line tool, as with pip
    cli = prefix / "cli" / "harness-design-studio"
    assert link.is_symlink() and os.readlink(link) == str(cli)
    gui = root / "bin" / "harness-design-studio-gui"
    assert gui.is_symlink() and os.readlink(gui) == str(prefix / "harness-design-studio-gui")
    alias = root / "bin" / "harness"  # the short alias of the command line tool
    assert alias.is_symlink() and os.readlink(alias) == str(cli)
    desktop = (root / "share" / "applications" / "harness-design-studio.desktop").read_text()
    assert f'Exec="{prefix}/harness-design-studio-gui"' in desktop and "@" not in desktop
    assert (root / "share" / "icons" / "harness-design-studio.svg").is_file()
    out = subprocess.run(
        [str(link), "--version"], capture_output=True, text=True, check=True
    ).stdout
    assert "stub" in out
    r = run_script(pkg / "uninstall.sh", tmp_path, "--prefix", str(prefix))
    assert r.returncode == 0 and not prefix.exists()
    assert not list((root).rglob("harness*"))


def test_reinstall_replaces_the_old_version(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    prefix = tmp_path / "opt"
    run_script(pkg / "install.sh", tmp_path, "--prefix", str(prefix))
    (prefix / "_internal" / "stale.txt").write_text("old")
    assert run_script(pkg / "install.sh", tmp_path, "--prefix", str(prefix)).returncode == 0
    assert not (prefix / "_internal" / "stale.txt").exists()


def test_scripts_reject_unknown_options(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    assert run_script(pkg / "install.sh", tmp_path, "--bogus").returncode == 2
    assert run_script(pkg / "uninstall.sh", tmp_path, "--bogus").returncode == 2


def test_desktop_entry_and_icon_are_valid() -> None:
    text = (PK / "harness-design-studio.desktop.in").read_text()
    for key in (
        "Type=Application",
        "Name=Harness Design Studio",
        "Exec=@EXEC@",
        "Icon=@ICON@",
        "Terminal=false",
        "Categories=",
    ):
        assert key in text
    root = ET.fromstring((PK / "harness-design-studio.svg").read_text())  # noqa: S314
    assert root.tag.endswith("svg") and root.get("viewBox") == "0 0 64 64"


@pytest.mark.skipif(shutil.which("dpkg-deb") is None, reason="dpkg-deb not installed")
def test_deb_has_the_right_files_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)  # the release machine does not set it
    from harness_design_studio import __version__
    from tools.build_deb import build, epoch

    app = fake_package(tmp_path / "src")
    deb = build(app, tmp_path / "out")
    info = subprocess.run(
        ["dpkg-deb", "-I", str(deb)], capture_output=True, text=True, check=True
    ).stdout
    assert "Package: harness-design-studio" in info and "Architecture: amd64" in info
    assert f"Version: {__version__.replace('rc', '~rc')}" in info and "libxcb-cursor0" in info
    listing = subprocess.run(
        ["dpkg-deb", "-c", str(deb)], capture_output=True, text=True, check=True
    ).stdout
    for path in (
        "./opt/harness-design-studio/harness-design-studio-gui",
        "./opt/harness-design-studio/cli/harness-design-studio",
        "./usr/bin/harness-design-studio",
        "./usr/bin/harness-design-studio-gui",
        "./usr/bin/harness",
        "./usr/share/applications/harness-design-studio.desktop",
        "./usr/share/icons/hicolor/scalable/apps/harness-design-studio.svg",
    ):
        assert path in listing, path
    assert "root/root" in listing  # owned by root, not by the build user
    again = build(app, tmp_path / "out2")
    assert again.read_bytes() == deb.read_bytes()  # reproducible
    # every member of the ar archive carries the fixed time, not the time of the build
    data = deb.read_bytes()
    pos, times = 8, set()
    while pos < len(data):
        times.add(int(data[pos + 16 : pos + 28]))
        pos += 60 + int(data[pos + 48 : pos + 58])
        pos += pos % 2
    assert times == {epoch()}


def test_the_tarball_does_not_depend_on_who_builds_it(tmp_path: Path) -> None:
    import tarfile

    from tools.build_installer import make_tarball

    pkg = fake_package(tmp_path / "src")
    if os.getuid() == 0:
        for path in [pkg, *pkg.rglob("*")]:
            os.chown(path, 1001, 1001, follow_symlinks=False)
    first = make_tarball(pkg.parent, "harness-design-studio", tmp_path / "a.tar.gz", 1_700_000_000)
    for path in pkg.rglob("*"):  # a later build: other times and modes
        os.utime(path, (1_800_000_000, 1_800_000_000), follow_symlinks=False)
        if path.is_file() and not os.access(path, os.X_OK):
            path.chmod(0o664)
    second = make_tarball(pkg.parent, "harness-design-studio", tmp_path / "b.tar.gz", 1_700_000_000)
    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first) as tar:
        members = tar.getmembers()
    assert members[0].name == "harness-design-studio" and len(members) > 5
    for m in members:
        assert (m.uid, m.gid, m.uname, m.gname, m.mtime) == (0, 0, "root", "root", 1_700_000_000)
    modes = {m.name: m.mode for m in members}
    assert modes["harness-design-studio/install.sh"] in (0o644, 0o755)
    assert modes["harness-design-studio/cli/harness-design-studio"] == 0o755


def test_container_recipes_are_valid_shell_and_name_the_right_base() -> None:
    cont = PK / "container"
    for script in ("build-in-container.sh", "clean-machine-test.sh"):
        assert (
            subprocess.run(
                ["sh", "-n", str(cont / script)], capture_output=True, check=False
            ).returncode
            == 0
        ), script
    assert "FROM ubuntu:24.04" in (cont / "Dockerfile.build-24.04").read_text()
    assert "--network none" in (cont / "clean-machine-test.sh").read_text()
    for script in ("install.sh", "uninstall.sh"):
        assert (
            subprocess.run(
                ["sh", "-n", str(PK / script)], capture_output=True, check=False
            ).returncode
            == 0
        )


def test_the_release_image_has_what_the_tests_that_must_not_skip_need() -> None:
    import re

    cont = PK / "container"
    image = (cont / "Dockerfile.build-24.04").read_text()
    pin = re.search(r'"playwright==([\d.]+)"', (ROOT / "pyproject.toml").read_text())
    assert pin and f"playwright=={pin.group(1)}" in image  # the same version as the dev extra
    assert "poppler-utils" in image and "install --with-deps chromium" in image
    assert (
        "PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers" in image
    )  # where tests/test_prototype.py looks
    assert "HARNESS_REQUIRE_BROWSER=1" in (cont / "build-in-container.sh").read_text()


def test_every_library_list_in_the_docs_is_the_one_the_deb_depends_on() -> None:
    import re

    from tools.build_deb import DEPENDS

    libs = {d.split()[0] for d in DEPENDS.split(", ")} - {"libc6"}
    assert len(libs) == 14
    where = [ROOT / "packaging/ubuntu/README.txt", ROOT / "docs/INSTALL.md", ROOT / "docs/FAQ.md"]
    where += [ROOT / "docs/TROUBLESHOOTING.md", ROOT.parent / ".github/workflows/harness-ci.yml"]
    where += [PK / "container" / "Dockerfile.build-24.04"]
    for path in where:
        words = set(re.findall(r"[\w.+-]+", path.read_text()))
        assert libs <= words, (path.name, sorted(libs - words))


def test_install_refuses_a_folder_without_the_built_program(tmp_path: Path) -> None:
    """Running install.sh from the source folder once left dangling links and reported success."""
    src = tmp_path / "source"
    src.mkdir()
    for item in PK.iterdir():
        if item.is_file():
            shutil.copy2(item, src / item.name)
    r = run_script(src / "install.sh", tmp_path)
    assert r.returncode == 1 and "no built program" in r.stderr
    assert not (tmp_path / "root").exists() and not (tmp_path / "home").exists()


def test_uninstall_removes_only_what_was_installed(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    prefix = tmp_path / "shared folder"
    prefix.mkdir()
    (prefix / "mydata.txt").write_text("keep me")
    assert run_script(pkg / "install.sh", tmp_path, "--prefix", str(prefix)).returncode == 0
    assert (prefix / ".harness-design-studio-install").is_file()
    r = run_script(pkg / "uninstall.sh", tmp_path, "--prefix", str(prefix))
    assert r.returncode == 0
    assert (prefix / "mydata.txt").read_text() == "keep me"
    assert not (prefix / "harness-design-studio-gui").exists()
    assert not (prefix / "_internal").exists()
    assert not (prefix / ".harness-design-studio-install").exists()


def test_a_folder_the_installer_did_not_make_is_never_removed_or_replaced(tmp_path: Path) -> None:
    """The user's own cli/ and LICENSES/ were erased, with a message that said all was well."""
    pkg = fake_package(tmp_path)
    mine = tmp_path / "proj"
    for name in ("cli", "LICENSES", "_internal"):
        (mine / name).mkdir(parents=True)
        (mine / name / "mine.txt").write_text("mine")
    r = run_script(pkg / "uninstall.sh", tmp_path, "--prefix", str(mine))
    assert r.returncode == 1 and "not touching" in r.stderr and "Removed" not in r.stdout
    r = run_script(pkg / "install.sh", tmp_path, "--prefix", str(mine))
    assert r.returncode == 1 and "not touching" in r.stderr
    for name in ("cli", "LICENSES", "_internal"):
        assert (mine / name / "mine.txt").read_text() == "mine"
    assert not (mine / "harness-design-studio-gui").exists()  # nothing was half installed
    # a folder the installer made is removed, but only the items it listed
    ok = tmp_path / "ok"
    assert run_script(pkg / "install.sh", tmp_path, "--prefix", str(ok)).returncode == 0
    (ok / "notes").mkdir()
    assert run_script(pkg / "uninstall.sh", tmp_path, "--prefix", str(ok)).returncode == 0
    assert (ok / "notes").is_dir() and not (ok / "cli").exists()


def test_the_marker_cannot_make_uninstall_remove_other_folders(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    prefix = tmp_path / "opt"
    assert run_script(pkg / "install.sh", tmp_path, "--prefix", str(prefix)).returncode == 0
    (prefix / "precious").mkdir()
    with (prefix / ".harness-design-studio-install").open("a") as f:
        f.write("precious\n../opt\n")
    assert run_script(pkg / "uninstall.sh", tmp_path, "--prefix", str(prefix)).returncode == 0
    assert (prefix / "precious").is_dir()


def test_install_inside_the_unpack_folders_parent_keeps_the_package(tmp_path: Path) -> None:
    """--prefix = the folder that holds the unpacked package used to delete the package itself
    (the package folder and the program file had the same name). Nothing of the package is an
    install item now, so it is simply left where it is; an item folder that holds it is refused."""
    pkg = fake_package(tmp_path / "opt")
    r = run_script(pkg / "install.sh", tmp_path, "--prefix", str(tmp_path / "opt"))
    assert r.returncode == 0, r.stderr
    assert (pkg / "harness-design-studio-gui").is_file()
    assert (pkg / "_internal" / "lib.txt").is_file() and (pkg / "install.sh").is_file()
    inside = fake_package(tmp_path / "other" / "cli")  # unpacked inside the item folder cli/
    r = run_script(inside / "install.sh", tmp_path, "--prefix", str(tmp_path / "other"))
    assert r.returncode == 2 and "unpacked inside" in r.stderr
    assert (inside / "cli" / "harness-design-studio").is_file()
    link = tmp_path / "linked"
    link.symlink_to(pkg)
    r = run_script(pkg / "install.sh", tmp_path, "--prefix", str(link))
    assert r.returncode == 2 and (pkg / "cli" / "harness-design-studio").is_file()


def test_installed_files_belong_to_root_not_to_whoever_unpacked(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    if os.getuid() == 0:
        for path in [pkg, *pkg.rglob("*")]:
            os.chown(path, 1234, 1234, follow_symlinks=False)
    prefix = tmp_path / "opt"
    assert run_script(pkg / "install.sh", tmp_path, "--prefix", str(prefix)).returncode == 0
    owners = {(p.lstat().st_uid, p.lstat().st_gid) for p in prefix.rglob("*")}
    assert owners == {(os.getuid(), os.getgid())}
    assert not list(prefix.glob(".*.new"))  # no leftovers of the temporary copy


def test_help_and_empty_prefix(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    for script in ("install.sh", "uninstall.sh"):
        r = run_script(pkg / script, tmp_path, "--help")
        assert r.returncode == 0 and "Usage" in r.stdout
        r = run_script(pkg / script, tmp_path, "--prefix", "")
        assert r.returncode == 2 and "empty" in r.stderr
    r = run_script(pkg / "install.sh", tmp_path, "--prefix", "/")
    assert r.returncode == 2 and "root folder" in r.stderr
    assert not (tmp_path / "home").exists()


def test_a_link_to_another_program_is_not_replaced(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    bindir = tmp_path / "root" / "bin"
    bindir.mkdir(parents=True)
    other = tmp_path / "somewhere"
    other.mkdir()
    (bindir / "harness").symlink_to(other)  # a link to a folder: ln -sf would put a link inside it
    r = run_script(pkg / "install.sh", tmp_path, "--prefix", str(tmp_path / "opt"))
    assert r.returncode == 1 and "not touching" in r.stderr
    assert not list(other.iterdir()) and not (tmp_path / "opt").exists()


def test_uninstalling_one_install_keeps_the_launcher_of_another(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    assert run_script(pkg / "install.sh", tmp_path, "--prefix", str(a)).returncode == 0
    assert run_script(pkg / "install.sh", tmp_path, "--prefix", str(b)).returncode == 0
    assert run_script(pkg / "uninstall.sh", tmp_path, "--prefix", str(a)).returncode == 0
    root = tmp_path / "root"
    desktop = (root / "share" / "applications" / "harness-design-studio.desktop").read_text()
    assert f"{b}/harness-design-studio-gui" in desktop
    assert (root / "share" / "icons" / "harness-design-studio.svg").is_file()
    cli = (b / "cli" / "harness-design-studio").resolve()
    assert (root / "bin" / "harness").resolve() == cli
    assert (root / "bin" / "harness-design-studio").resolve() == cli
    assert (root / "bin" / "harness-design-studio-gui").resolve() == (
        b / "harness-design-studio-gui"
    ).resolve()


def test_a_backslash_in_the_prefix_is_escaped_for_the_desktop_entry(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    prefix = tmp_path / "back\\slash"
    assert run_script(pkg / "install.sh", tmp_path, "--prefix", str(prefix)).returncode == 0
    desktop = (
        tmp_path / "root" / "share" / "applications" / "harness-design-studio.desktop"
    ).read_text()
    exec_line = next(ln for ln in desktop.splitlines() if ln.startswith("Exec="))
    assert "back\\\\\\\\slash" in exec_line  # four backslashes stand for one


def test_uninstall_never_removes_a_program_that_is_not_ours(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    root = tmp_path / "root"
    (root / "bin").mkdir(parents=True)
    mine = root / "bin" / "harness"
    mine.write_text("#!/bin/sh\necho my own harness\n")
    r = run_script(pkg / "install.sh", tmp_path, "--prefix", str(tmp_path / "opt"))
    assert r.returncode == 1 and "not touching" in r.stderr
    assert mine.read_text().endswith("my own harness\n")
    r = run_script(pkg / "uninstall.sh", tmp_path, "--prefix", str(tmp_path / "opt"))
    assert mine.exists()


def test_a_prefix_with_spaces_and_symbols_gives_a_valid_launcher(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    prefix = tmp_path / "my apps & more" / "harness tool"
    assert run_script(pkg / "install.sh", tmp_path, "--prefix", str(prefix)).returncode == 0
    desktop = (
        tmp_path / "root" / "share" / "applications" / "harness-design-studio.desktop"
    ).read_text()
    exec_line = next(ln for ln in desktop.splitlines() if ln.startswith("Exec="))
    assert exec_line == f'Exec="{prefix}/harness-design-studio-gui"' and "@" not in desktop
    out = subprocess.run(
        [str(tmp_path / "root" / "bin" / "harness-design-studio"), "--version"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "stub" in out


def test_a_relative_prefix_and_the_unpack_folder_are_handled(tmp_path: Path) -> None:
    if sys.platform != "linux":
        pytest.skip("install.sh is the Linux tarball's script (GNU tools)")
    pkg = fake_package(tmp_path)
    env = {
        **os.environ,
        "HARNESS_INSTALL_ROOT": str(tmp_path / "root"),
        "HOME": str(tmp_path / "h"),
    }
    r = subprocess.run(
        ["sh", str(pkg / "install.sh"), "--prefix", "rel/opt"],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        check=False,
    )
    assert r.returncode == 0
    link = tmp_path / "root" / "bin" / "harness-design-studio"
    assert os.path.isabs(os.readlink(link)) and link.resolve().is_file()
    r = run_script(pkg / "install.sh", tmp_path, "--prefix", str(pkg))
    assert (
        r.returncode == 2 and (pkg / "harness-design-studio-gui").is_file()
    )  # its own source survives


def test_uninstall_when_nothing_is_installed_says_so(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    r = run_script(pkg / "uninstall.sh", tmp_path, "--prefix", str(tmp_path / "never"))
    assert r.returncode == 0 and "Nothing to remove" in r.stdout


def test_the_local_system_install_does_not_share_the_debs_folder() -> None:
    text = (PK / "install.sh").read_text()
    assert (
        "/usr/local/lib/harness-design-studio" in text
        and "prefix=/opt/harness-design-studio;" not in text
    )


@pytest.mark.skipif(shutil.which("dpkg-deb") is None, reason="dpkg-deb not installed")
def test_the_deb_ships_licences_and_not_the_tarball_scripts(tmp_path: Path) -> None:
    from tools.build_deb import DEPENDS, build

    app = fake_package(tmp_path / "src")
    (app / "LICENSES").mkdir()
    (app / "LICENSES" / "README.txt").write_text("licences")
    deb = build(app, tmp_path / "out")
    listing = subprocess.run(
        ["dpkg-deb", "-c", str(deb)], capture_output=True, text=True, check=True
    ).stdout
    assert "./usr/share/doc/harness-design-studio/copyright" in listing
    assert "./usr/share/doc/harness-design-studio/LICENSES/README.txt" in listing
    assert "opt/harness-design-studio/install.sh" not in listing
    for name in ("README.txt", "harness-design-studio.desktop.in", "harness-design-studio.svg"):
        assert f"opt/harness-design-studio/{name}" not in listing, name  # tarball-only files
    assert "libc6 (>= 2.39)" in DEPENDS and "libxcb-xinerama0" in DEPENDS


@pytest.mark.skipif(shutil.which("dpkg-deb") is None, reason="dpkg-deb not installed")
def test_the_deb_copyright_names_the_owner_and_grants_no_licence(tmp_path: Path) -> None:
    from tools.build_deb import build

    deb = build(fake_package(tmp_path / "src"), tmp_path / "out")
    subprocess.run(["dpkg-deb", "-x", str(deb), str(tmp_path / "x")], check=True)
    text = (
        tmp_path / "x" / "usr" / "share" / "doc" / "harness-design-studio" / "copyright"
    ).read_text()
    assert "Copyright: the repository owner (GitHub account 0h3xn4)" in text
    assert "Not chosen yet by the owner (decision D-02" in text
    assert "No licence is granted by this file." in text
    assert "to be filled in" not in text and "decided by the project owner" not in text
    # machine-readable format: a header paragraph, then paragraphs of Files / Copyright / License
    paragraphs = [p for p in text.strip().split("\n\n") if p.strip()]
    assert paragraphs[0].startswith("Format: https://www.debian.org/doc/packaging-manuals/")
    for para in paragraphs[1:]:
        fields = [ln.split(":", 1)[0] for ln in para.splitlines() if not ln.startswith(" ")]
        assert fields == ["Files", "Copyright", "License"], para
    assert "License: LicenseRef-Proprietary" in text


def test_the_licence_collector_finds_the_runtime_packages_and_the_lgpl_text(tmp_path: Path) -> None:
    from tools.collect_licences import collect, runtime_distributions

    names = set(runtime_distributions())
    assert {"pydantic", "openpyxl"} <= names and "pytest" not in names and "mypy" not in names
    if not Path("/usr/share/common-licenses/LGPL-3").is_file():
        pytest.skip("needs the Debian/Ubuntu common-licenses folder")
    rows = collect(tmp_path / "LICENSES")
    assert any("pydantic" in r for r in rows)
    assert (tmp_path / "LICENSES" / "LGPL-3.txt").is_file()


def test_the_package_check_names_modules_that_are_not_declared_dependencies() -> None:
    from tools.build_installer import undeclared_modules

    toc = [
        "harness_design_studio.core.model", "pydantic._internal._core_utils", "openpyxl.styles",
        "json.decoder", "xml.etree.ElementTree", "PySide6", "_pyi_rth_utils.qt", "typing_extensions",
        "_sysconfigdata__x86_64-linux-gnu",
        "rich.console", "pygments.lexers", "markdown_it.main", "chardet",
    ]  # fmt: skip
    assert undeclared_modules(toc) == ["chardet", "markdown_it", "pygments", "rich"]
    assert undeclared_modules(toc[:9]) == []


def test_the_package_check_covers_files_next_to_the_archive(tmp_path: Path) -> None:
    from tools.build_installer import undeclared_files

    internal = tmp_path / "_internal"
    for name in ("libQt6Core.so.6", "base_library.zip", "pydantic_core", "PySide6", "python3.13",
                 "pydantic-2.13.5.dist-info", "harness_design_studio"):  # fmt: skip
        (internal / name).mkdir(parents=True)
    assert undeclared_files(internal) == []
    for name in ("chardet", "7cf47097c39cf1afcee8__mypyc.cpython-313-x86_64-linux-gnu.so",
                 "rich-15.0.0.dist-info"):  # fmt: skip
        (internal / name).mkdir()
    assert undeclared_files(internal) == [
        "7cf47097c39cf1afcee8__mypyc", "chardet", "rich",
    ]  # fmt: skip


def test_the_known_runtime_packages_are_all_allowed_in_the_package() -> None:
    from importlib import metadata

    from tools.build_installer import ALLOWED_PACKAGES, EXCLUDES
    from tools.collect_licences import runtime_distributions

    owners = metadata.packages_distributions()
    runtime = {
        d.metadata["Name"].lower().replace("_", "-") for d in runtime_distributions().values()
    }
    top = {
        m for m, dists in owners.items() if runtime & {x.lower().replace("_", "-") for x in dists}
    }
    top -= {"__pycache__", "Shiboken"}  # not imported by the app (Shiboken is a build-time alias)
    assert top and top <= ALLOWED_PACKAGES, sorted(top - ALLOWED_PACKAGES)
    # rich and the like come in only through pydantic's optional pretty printing: keep them out
    assert {"rich", "pygments", "markdown_it", "mdurl", "chardet", "toml"} <= set(EXCLUDES)
    assert not {"rich", "pygments", "chardet"} & ALLOWED_PACKAGES


def test_the_root_setup_describes_the_package_with_the_upstream_readme() -> None:
    """The fork's root setup.py (the WireViz package) reads its description as UTF-8 whatever the locale."""
    import json
    import sys

    root = ROOT.parent
    if not (root / "setup.py").is_file():
        pytest.skip("the repository root is not here")
    driver = (
        "import json, runpy, setuptools\n"
        "seen = {}\n"
        "setuptools.setup = lambda **kw: seen.update(kw)\n"
        "runpy.run_path('setup.py')\n"
        "keys = ('long_description', 'long_description_content_type', 'python_requires', 'name')\n"
        "print(json.dumps({k: seen.get(k) for k in keys}))\n"
    )
    env = {**os.environ, "LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONIOENCODING": "utf-8"}
    env.pop("LANG", None)
    r = subprocess.run(
        [sys.executable, "-c", driver],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert r.returncode == 0, r.stderr[-600:]
    meta = json.loads(r.stdout)
    upstream = (root / "docs" / "upstream" / "README.upstream.md").read_text(encoding="utf-8")
    assert meta["long_description"] == upstream and upstream.startswith("# WireViz")
    assert meta["long_description_content_type"] == "text/markdown"
    assert meta["python_requires"] == ">=3.7"
    # a wheel built from the source distribution needs the file too
    assert "docs/upstream/README.upstream.md" in (root / "MANIFEST.in").read_text(encoding="utf-8")


RELEASE_WORKFLOW = ROOT.parent / ".github" / "workflows" / "release.yml"


def test_the_release_workflow_builds_and_publishes_on_a_tag() -> None:
    """Pushing a tag vX.Y.Z builds, verifies and publishes; only the release job may write."""
    if not RELEASE_WORKFLOW.is_file():
        pytest.skip("the repository root is not here")
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert 'tags: ["v*"]' in text and "workflow_dispatch:" in text and "tag:" in text
    assert text.index("push:") < text.index("tags:") < text.index("jobs:")
    # the token is read-only for the workflow and writable for the release job alone
    assert "permissions:\n  contents: read" in text
    # only the job that publishes and the job that rewrites the page text may write
    assert text.count("contents: write") == 2
    assert text.index("contents: write") > text.index("jobs:\n  release:")
    for command in (
        "python -m tools.release_notes check",
        "python -m tools.build_installer",
        "python -m tools.build_deb",
        "--selftest",
        "python -m tools.gen_scf dist",
        "sha256sum -c SHA256SUMS",
        "gh release create",
        "--verify-tag",
        "gh release upload",
        "--clobber",
        "dist/*.tar.gz",
        "dist/*.deb",
        "dist/SHA256SUMS",
    ):
        assert command in text, command
    # the order matters: build, then checksums, then the page
    for earlier, later in (
        ("tools.build_installer", "tools.build_deb"),
        ("tools.build_deb", "tools.gen_scf"),
        ("tools.gen_scf", "tools.release_notes notes"),
        ("tools.release_notes notes", "gh release create"),
    ):
        assert text.index(earlier) < text.index(later), (earlier, later)
    # only actions that the other workflows already use
    used = {ln.split("uses:")[1].strip() for ln in text.splitlines() if "uses:" in ln}
    assert used <= {"actions/checkout@v4", "actions/setup-python@v5", "actions/upload-artifact@v4"}
    # the system libraries are the ones the CI job that installs the packages uses
    ci = (RELEASE_WORKFLOW.parent / "harness-ci.yml").read_text(encoding="utf-8")
    libs = (
        "libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0"
    )
    line = next(ln for ln in text.splitlines() if libs in ln).split("install -y")[1].strip()
    assert line in ci


def test_the_release_check_refuses_a_tag_that_does_not_fit() -> None:
    from tools import release_notes as rn

    log = "# Changelog\n\n## Unreleased\n\n## 2.0.0 (date)\n\nintro\n\n- a\n\n## 1.0.0\n\n- b\n"
    assert rn.problems("v2.0.0", "2.0.0", log) == []
    assert "want v2.0.0" in rn.problems("v2.0.1", "2.0.0", log)[0]
    assert "no '## 3.0.0' heading" in rn.problems("v3.0.0", "3.0.0", log)[0]
    assert (
        "empty" in rn.problems("v2.0.0", "2.0.0", "## Unreleased\n\n## 2.0.0 (x)\n\n## 1.0.0\n")[0]
    )
    unreleased = log.replace("## Unreleased\n", "## Unreleased\n\n- not released\n")
    assert "Unreleased" in rn.problems("v2.0.0", "2.0.0", unreleased)[0]
    # 2.0.0 must not match the heading of 2.0.0rc1 or 12.0.0
    assert rn.section("## 2.0.0rc1\n\n- x\n", "2.0.0") is None
    assert rn.section("## 12.0.0\n\n- x\n", "2.0.0") is None


def test_the_release_notes_have_a_download_table_highlights_and_the_checksums(
    tmp_path: Path,
) -> None:
    from harness_design_studio import __version__
    from tools import release_notes as rn

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    # the real files agree; text under "## Unreleased" is allowed between releases (the release
    # gate in tools/release_check refuses it at release time)
    found = [
        p
        for p in rn.problems(f"v{__version__}", __version__, changelog, ROOT)
        if "Unreleased" not in p
    ]
    assert found == []
    body = rn.section(changelog, __version__)
    assert body and not any(ln.startswith("## ") for ln in body.splitlines())
    highlights = rn.highlights_file(__version__).read_text(encoding="utf-8")
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(
        f"{'a' * 64}  harness-design-studio_{__version__}_amd64.deb\n"
        f"{'b' * 64}  harness-design-studio-{__version__}-linux-x86_64.tar.gz\n"
        f"{'c' * 64}  something-else.txt\n",
        encoding="utf-8",
    )
    out = tmp_path / "notes.md"
    text = rn.notes(__version__, changelog, sums.read_text(encoding="utf-8"), highlights)
    assert text.startswith("**Harness Design Studio**")
    assert "not a statement of compliance with any standard" in text
    assert "## Download" in text and f"`harness-design-studio_{__version__}_amd64.deb`" in text
    assert f"## What is new in {__version__}\n\n{highlights.strip()}" in text
    # the whole changelog section is kept, folded away
    assert f"<details>\n<summary>The full list of changes</summary>\n\n{body}" in text
    assert f"| `harness-design-studio_{__version__}_amd64.deb` | `{'a' * 64}` |" in text
    assert "Other files: `something-else.txt`" in text
    # only the systems whose files are there get install steps and a checksum command
    assert "sha256sum -c SHA256SUMS" in text and "Get-FileHash" not in text
    assert "Windows" not in text.split("## Install")[1].split("## Check")[0]
    assert rn.main(["notes", "v0.0.1", str(sums), str(out)]) == 1  # the tag must fit the version


def test_the_release_notes_list_the_windows_and_macos_packages_when_they_exist() -> None:
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
    sums = "".join(f"{'d' * 64}  {name}\n" for name in names)
    text = rn.notes(v, f"## {v}\n\nFirst paragraph.\n\n- a\n", sums)
    for name in names:
        assert f"`{name}`" in text
    assert "Other files" not in text  # every file was recognised
    assert "First paragraph." in text  # without a highlights file the first paragraph is used
    for command in ("sha256sum -c", "shasum -a 256 -c", "Get-FileHash"):
        assert command in text
    assert "SmartScreen" in text and "right-click" in text


def test_every_release_has_a_highlights_file() -> None:
    from harness_design_studio import __version__
    from tools import release_notes as rn

    assert rn.highlights_file(__version__).is_file()
    assert rn.highlights_file(__version__).read_text(encoding="utf-8").strip()


def test_the_release_workflow_can_write_the_page_text_again_without_building() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "notes_only:" in text
    assert "if: ${{ !inputs.notes_only }}" in text and "if: ${{ inputs.notes_only }}" in text
    notes_job = text[text.index("\n  notes:") :]
    assert "gh release edit" in notes_job and "--root" in notes_job
    for forbidden in ("build_installer", "build_deb", "gh release upload", "gh release create"):
        assert forbidden not in notes_job, forbidden


def _load_gui_entry() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gui_entry_under_test", ROOT / "packaging/gui_entry.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_entry_flags_count_only_as_the_first_argument() -> None:
    entry = _load_gui_entry()
    assert entry._asked("--selftest", ["prog", "--selftest"])
    assert entry._asked("--drc-worker", ["prog", "--drc-worker"])
    assert not entry._asked("--selftest", ["prog", "my--selftest", "--selftest"])
    assert not entry._asked("--drc-worker", ["prog", "/path/to/project", "--drc-worker"])
    assert not entry._asked("--selftest", ["prog"])


def _selftest_env(tmp_path: Path, **extra: str) -> dict[str, str]:
    scratch = tmp_path / "scratch"
    scratch.mkdir(exist_ok=True)
    env = {**os.environ, "TMPDIR": str(scratch), "PYTHONPATH": os.pathsep.join(sys.path)}
    env.pop("QT_QPA_PLATFORM", None)
    return {**env, **extra}


def test_the_selftest_accepts_an_empty_platform_variable_and_cleans_up(tmp_path: Path) -> None:
    """QT_QPA_PLATFORM= (empty) aborted Qt, and every run left its temporary folder behind."""
    r = subprocess.run(
        [sys.executable, "-P", str(ROOT / "packaging/gui_entry.py"), "--selftest"],
        capture_output=True,
        text=True,
        env=_selftest_env(tmp_path, QT_QPA_PLATFORM=""),
        check=False,
        timeout=300,
    )
    assert r.returncode == 0 and "selftest ok" in r.stdout, (r.stdout, r.stderr[-500:])
    assert list((tmp_path / "scratch").iterdir()) == []


def test_a_failing_selftest_names_the_step(tmp_path: Path) -> None:
    code = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('entry', {str(ROOT / 'packaging/gui_entry.py')!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "m._fonts_are_bundled = lambda: False\n"
        "raise SystemExit(m.selftest())\n"
    )
    r = subprocess.run(
        [sys.executable, "-P", "-c", code],
        capture_output=True,
        text=True,
        env=_selftest_env(tmp_path, QT_QPA_PLATFORM="offscreen"),
        check=False,
        timeout=300,
    )
    assert r.returncode == 1, (r.stdout, r.stderr[-500:])
    assert "selftest FAILED at: bundled fonts" in r.stdout
    assert list((tmp_path / "scratch").iterdir()) == []


def test_the_ci_workflow_keeps_runs_on_master_and_checks_both_packages() -> None:
    ci_file = ROOT.parent / ".github" / "workflows" / "harness-ci.yml"
    if not ci_file.is_file():
        pytest.skip("the repository root is not here")
    ci = ci_file.read_text(encoding="utf-8")
    # a second merge must not cancel the run on the first merge commit
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in ci
    # upload-artifact only fails when none of its files exist
    assert "ls dist/*.deb dist/*.tar.gz" in ci
    # the documents-only job also runs the test that reads the flatsat walkthrough
    docs_job = ci[ci.index("  docs:") : ci.index("  test:")]
    assert "tests/test_examples.py::test_the_flatsat_walkthrough_matches_the_example" in docs_job


def test_the_wheel_carries_the_dotfiles_of_the_example_projects() -> None:
    """The `**` in package-data does not match names that start with a dot."""
    import glob
    import tomllib

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = pyproject["tool"]["setuptools"]["package-data"]["harness_design_studio.resources"]
    pkg = ROOT / "src" / "harness_design_studio" / "resources"
    shipped = {
        f
        for pat in patterns
        for f in glob.glob(pat, root_dir=pkg, recursive=True)  # noqa: PTH207
    }
    dotfiles = {
        p.relative_to(pkg).as_posix() for p in (pkg / "examples").rglob(".*") if p.is_file()
    }
    assert dotfiles and dotfiles <= shipped, sorted(dotfiles - shipped)


def test_the_offline_wheelhouse_downloads_only_pinned_packages(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tools import vendor

    commands: list[list[str]] = []

    def fake(cmd: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake)
    assert vendor.main(str(tmp_path / "wheelhouse")) == 0
    named = [a for c in commands[1:] for a in c[c.index("download") + 3 :]]
    assert named and all("==" in a for a in named), named


def test_the_pip_commands_and_their_short_aliases() -> None:
    """`harness-design-studio` (command line) and `harness-design-studio-gui` (editor) are the
    names; `harness` and `harness-gui` stay as aliases of the same functions."""
    import tomllib

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    cli, gui = "harness_design_studio.cli.main:main", "harness_design_studio.gui.app:main"
    assert pyproject["scripts"] == {"harness-design-studio": cli, "harness": cli}
    assert pyproject["gui-scripts"] == {"harness-design-studio-gui": gui, "harness-gui": gui}


def test_the_workflows_start_the_editor_by_its_gui_name() -> None:
    """--selftest belongs to the packaged editor; `harness-design-studio` is the command line."""
    if not RELEASE_WORKFLOW.is_file():
        pytest.skip("the repository root is not here")
    for name in ("release.yml", "harness-ci.yml"):
        text = (RELEASE_WORKFLOW.parent / name).read_text(encoding="utf-8")
        for line in text.splitlines():
            if "--selftest" in line:
                assert "harness-design-studio-gui --selftest" in line, (name, line)


def test_upgrading_from_1_0_0_replaces_its_program_file_and_links(tmp_path: Path) -> None:
    """1.0.0 installed the editor as `harness-design-studio` and linked `harness` to cli/harness.
    Installing the new package over it leaves nothing of the old names, and the new uninstall
    script also removes an install that was made by 1.0.0."""
    pkg = fake_package(tmp_path)
    prefix = tmp_path / "opt"
    root = tmp_path / "root"
    prefix.mkdir()
    (prefix / "_internal").mkdir()
    (prefix / "cli").mkdir()
    (prefix / "harness-design-studio").write_text("old editor")
    (prefix / "cli" / "harness").write_text("old cli")
    (prefix / ".harness-design-studio-install").write_text(
        "# made by 1.0.0\nharness-design-studio\n_internal\ncli\n"
    )
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "harness-design-studio").symlink_to(prefix / "harness-design-studio")
    (root / "bin" / "harness").symlink_to(prefix / "cli" / "harness")
    old = tmp_path / "old-copy"
    shutil.copytree(prefix, old, symlinks=True)
    assert run_script(pkg / "install.sh", tmp_path, "--prefix", str(prefix)).returncode == 0
    assert not (prefix / "harness-design-studio").exists()  # the old program file is gone
    assert (prefix / "harness-design-studio-gui").is_file()
    assert not (prefix / "cli" / "harness").exists()
    assert (root / "bin" / "harness-design-studio").resolve() == (
        prefix / "cli" / "harness-design-studio"
    ).resolve()
    assert (root / "bin" / "harness").resolve() == (
        prefix / "cli" / "harness-design-studio"
    ).resolve()
    assert run_script(pkg / "uninstall.sh", tmp_path, "--prefix", str(prefix)).returncode == 0
    assert not prefix.exists() and not list(root.rglob("harness*"))


def test_uninstall_of_a_1_0_0_install_removes_its_links_and_files(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    prefix = tmp_path / "opt"
    root = tmp_path / "root"
    (prefix / "cli").mkdir(parents=True)
    (prefix / "_internal").mkdir()
    (prefix / "harness-design-studio").write_text("old editor")
    (prefix / "cli" / "harness").write_text("old cli")
    (prefix / ".harness-design-studio-install").write_text(
        "# made by 1.0.0\nharness-design-studio\n_internal\ncli\n"
    )
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "harness-design-studio").symlink_to(prefix / "harness-design-studio")
    (root / "bin" / "harness").symlink_to(prefix / "cli" / "harness")
    mine = root / "bin" / "harness-design-studio-gui"
    mine.write_text("a program of the user")  # not ours: never removed
    assert run_script(pkg / "uninstall.sh", tmp_path, "--prefix", str(prefix)).returncode == 0
    assert not prefix.exists()
    assert not (root / "bin" / "harness").is_symlink()
    assert not (root / "bin" / "harness-design-studio").is_symlink()
    assert mine.read_text() == "a program of the user"


def test_install_does_not_replace_a_gui_link_that_is_not_ours(tmp_path: Path) -> None:
    pkg = fake_package(tmp_path)
    bindir = tmp_path / "root" / "bin"
    bindir.mkdir(parents=True)
    other = tmp_path / "somewhere"
    other.mkdir()
    (bindir / "harness-design-studio-gui").symlink_to(other)
    r = run_script(pkg / "install.sh", tmp_path, "--prefix", str(tmp_path / "opt"))
    assert r.returncode == 1 and "not touching" in r.stderr and not (tmp_path / "opt").exists()
