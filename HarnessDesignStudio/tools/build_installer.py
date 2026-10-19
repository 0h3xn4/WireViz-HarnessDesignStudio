"""Build a self-contained, offline package with PyInstaller (one-folder) and archive it.

Build on Ubuntu 24.04 (the Linux platform, D-127). Output: dist/harness-design-studio-<version>-linux-<arch>.tar.gz
The Windows and macOS packages (D-149) are built by tools/build_windows.py and tools/build_macos.py;
they use the pieces of this module (the program builds, the exclude list and the allow-list check).

Layout of the package folder dist/harness-design-studio/ (the name of the folder, the .deb and the
install folder stays; the programs inside it are named like the commands of a pip install):
  harness-design-studio-gui   the editor (also answers --selftest and --drc-worker)
  cli/harness-design-studio   the command line tool (`harness` is a link to it, made by the installers)
"""

import gzip
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
from collections.abc import Iterable
from pathlib import Path

from harness_design_studio import __version__

ROOT = Path(__file__).resolve().parents[1]
EXCLUDES = ["PySide6.QtNetwork", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
            "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtQml", "PySide6.QtQuick",
            "PySide6.QtPdf", "PySide6.QtSvg", "tkinter",
            # development tools that PyInstaller would otherwise pull in from the build environment
            "mypy", "pydantic.mypy", "hypothesis", "pytest", "_pytest", "lxml", "setuptools",
            "pkg_resources", "attr", "attrs", "pip",
            # pydantic imports rich (and through it pygments, markdown_it, mdurl, chardet, toml)
            # only to pretty-print its own debug output; their licences are not shipped
            "rich", "pygments", "markdown_it", "mdurl", "chardet", "toml"]  # fmt: skip
FORBIDDEN = {"mypy", "hypothesis", "pytest", "_pytest", "lxml", "setuptools", "pip", "ruff"}
# The only third-party code that may be in the package: the declared runtime dependencies (and what
# they need), PySide6 with shiboken6, and the app. Everything else must be the standard library.
ALLOWED_PACKAGES = frozenset({
    "harness_design_studio", "pydantic", "pydantic_core", "annotated_types", "typing_extensions",
    "typing_inspection", "openpyxl", "et_xmlfile", "defusedxml", "PySide6", "shiboken6",
})  # fmt: skip
GUI_NAME = "harness-design-studio-gui"
CLI_NAME = "harness-design-studio"
PACKAGE_NAME = "harness-design-studio"  # the folder, the archive, the .deb and the install folder
PYINSTALLER_PREFIXES = ("_pyi", "pyi_", "PyInstaller", "_sysconfigdata")  # runtime hooks and tables


def _is_known(top: str) -> bool:
    return (
        top in ALLOWED_PACKAGES
        or top in sys.stdlib_module_names
        or top.startswith(PYINSTALLER_PREFIXES)
    )


def undeclared_modules(names: Iterable[str]) -> list[str]:
    """Top-level modules in a module list (the PYZ table of contents) that are neither the standard
    library nor an allowed package."""
    return sorted({n.split(".")[0] for n in names if not _is_known(n.split(".")[0])})


def undeclared_files(internal: Path) -> list[str]:
    """The same for the files next to the archive (extension modules, package folders, metadata)."""
    found = set()
    for entry in internal.iterdir():
        if (
            entry.name.startswith("lib")
            or entry.name == "base_library.zip"
            or entry.name.lower().endswith((".dll", ".dylib"))  # Windows and macOS shared libraries
        ):
            continue  # shared libraries and the frozen standard library
        top = entry.name.split("-")[0] if entry.name.endswith(".dist-info") else entry.name
        top = top.split(".")[0]
        if _is_python_library(entry.name, top) or _links_into_known(entry, internal):
            continue
        if not _is_known(top):
            found.add(top)
    return sorted(found)


def _is_python_library(name: str, top: str) -> bool:
    """The interpreter itself: python3.13 (Linux), Python (macOS), python3__dot__12 (macOS, the
    name PyInstaller gives a file whose name has a dot)."""
    return (
        top == "python3"
        or name in ("Python", "Python.framework")
        or re.fullmatch(r"python3__dot__\d+", name) is not None
    )


def _links_into_known(entry: Path, base: Path) -> bool:
    """macOS: Qt's frameworks are linked from the top folder (QtCore -> PySide6/Qt/lib/...)."""
    if not entry.is_symlink():
        return False
    try:
        inside = entry.resolve().relative_to(base.resolve())
    except ValueError:
        return False
    return len(inside.parts) > 1 and _is_known(inside.parts[0])


def undeclared_in_build(app: Path, bases: Iterable[Path] | None = None) -> list[str]:
    """Everything in the built package, the PYZ archives included, that the allow-list does not cover.

    `bases` are the folders next to the archives (default: the two `_internal` folders of the Linux
    and Windows layout; the macOS app bundle names its own)."""
    from PyInstaller.archive.readers import ZlibArchiveReader  # type: ignore[import-untyped]

    found: set[str] = set()
    for name in (GUI_NAME, CLI_NAME):
        pyz = ROOT / "build" / name / name / "PYZ-00.pyz"
        found.update(undeclared_modules(ZlibArchiveReader(str(pyz)).toc))
    if bases is None:
        bases = (app / "_internal", app / "cli" / "_internal")
    for base in bases:
        if base.is_dir():
            found.update(undeclared_files(base))
    return sorted(found)


def make_tarball(root_dir: Path, base_dir: str, target: Path, stamp: int) -> Path:
    """A .tar.gz of root_dir/base_dir that does not depend on who builds it or when: owner root,
    sorted entries, fixed times, normalised modes and no time in the gzip header."""

    def clean(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = info.gid = 0
        info.uname = info.gname = "root"
        info.mtime = stamp
        if not info.issym():
            info.mode = 0o755 if info.isdir() or info.mode & 0o111 else 0o644
        return info

    paths = [root_dir / base_dir, *sorted((root_dir / base_dir).rglob("*"))]
    with (
        target.open("wb") as raw,
        gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w") as tar,
    ):
        for path in paths:
            tar.add(path, arcname=path.relative_to(root_dir).as_posix(), recursive=False,
                    filter=clean)  # fmt: skip
    return target


def pyinstaller_build(
    name: str,
    entry: Path,
    *,
    windowed: bool,
    extra_excludes: tuple[str, ...] = (),
    extra_args: tuple[str, ...] = (),
) -> int:
    """Build one program; its folder (named like the program) is made in build/dist-<name>.
    `extra_args` are more PyInstaller options (an icon, the bundle identifier of the macOS app)."""
    work = ROOT / "build"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--windowed" if windowed else "--console",
           "--name", name, "--distpath", str(work / f"dist-{name}"), "--workpath", str(work / name),
           "--specpath", str(work), "--paths", str(ROOT / "src")]  # fmt: skip
    for mod in (*EXCLUDES, *extra_excludes):
        cmd += ["--exclude-module", mod]
    cmd += [
        "--hidden-import",
        "defusedxml",
    ]  # openpyxl imports it only if present: XML bomb protection
    sep = os.pathsep  # the separator of --add-data is ":" on Linux and macOS and ";" on Windows
    guide = ROOT / "src" / "harness_design_studio" / "resources" / "guide"
    cmd += ["--add-data", f"{guide}{sep}harness_design_studio/resources/guide"]
    examples = (
        ROOT / "src" / "harness_design_studio" / "resources" / "examples"
    )  # `harness-design-studio new`, templates
    cmd += ["--add-data", f"{examples}{sep}harness_design_studio/resources/examples"]
    fonts = (
        ROOT / "src" / "harness_design_studio" / "resources" / "fonts"
    )  # Inter and JetBrains Mono, SIL OFL 1.1
    cmd += ["--add-data", f"{fonts}{sep}harness_design_studio/resources/fonts"]
    cmd += extra_args
    cmd.append(str(entry))
    return subprocess.run(cmd, check=False).returncode


def build_programs(
    gui_args: tuple[str, ...] = (),
    cli_args: tuple[str, ...] = (),
    extra_excludes: tuple[str, ...] = (),
) -> int:
    """Build the editor (windowed) and the command line tool (console, no Qt) with PyInstaller."""
    packaging = ROOT / "packaging"
    if pyinstaller_build(
        GUI_NAME,
        packaging / "gui_entry.py",
        windowed=True,
        extra_excludes=extra_excludes,
        extra_args=gui_args,
    ):
        return 1
    # Console command (validate/check/migrate); no Qt, so it stays small. Shipped inside the folder.
    return pyinstaller_build(
        CLI_NAME,
        packaging / "cli_entry.py",
        windowed=False,
        extra_excludes=("PySide6", "shiboken6", *extra_excludes),
        extra_args=cli_args,
    )


def check_package(bases: Iterable[Path], app: Path | None = None) -> int:
    """Refuse a package that holds development tools or code that is not a declared dependency
    (its licence would not be shipped). `bases` are the folders that hold the libraries."""
    bases = list(bases)
    leaked = sorted(
        p.name for base in bases if base.is_dir()
        for p in base.iterdir() if p.name.split(".")[0] in FORBIDDEN
    )  # fmt: skip
    if leaked:
        print(
            f"error: development tools ended up in the package: {', '.join(leaked)}",
            file=sys.stderr,
        )
        return 1
    extra = undeclared_in_build(app or ROOT, bases)
    if extra:
        for base in bases:  # where they are, to find out what they are
            if base.is_dir():
                for p in sorted(base.iterdir()):
                    if p.name.split(".")[0] in extra or p.name in extra:
                        target = p.resolve() if p.is_symlink() else "(not a link)"
                        print(f"  {p} -> {target}", file=sys.stderr)
        print(
            "error: code that is not a declared dependency ended up in the package (its licence "
            f"is not shipped): {', '.join(extra)}. Add it to EXCLUDES, or to ALLOWED_PACKAGES with "
            "its licence and SBOM entry.",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    if build_programs():
        return 1
    app = ROOT / "dist" / PACKAGE_NAME
    shutil.rmtree(app, ignore_errors=True)
    shutil.copytree(ROOT / "build" / f"dist-{GUI_NAME}" / GUI_NAME, app, symlinks=True)
    shutil.copytree(ROOT / "build" / f"dist-{CLI_NAME}" / CLI_NAME, app / "cli")
    if check_package((app / "_internal", app / "cli" / "_internal"), app):
        return 1
    from tools.collect_licences import collect

    collect(app / "LICENSES")
    for item in (
        ROOT / "packaging" / "ubuntu"
    ).iterdir():  # install scripts, desktop file, icon, readme
        if item.is_file():
            shutil.copy2(item, app / item.name)
    system = platform.system().lower()
    base = ROOT / "dist" / f"{PACKAGE_NAME}-{__version__}-{system}-{platform.machine().lower()}"
    from tools.build_deb import epoch

    archive = make_tarball(
        ROOT / "dist", PACKAGE_NAME, base.with_name(base.name + ".tar.gz"), epoch()
    )
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
