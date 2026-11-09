"""Build a self-contained, offline package with PyInstaller (one-folder) and archive it.

Build on Ubuntu 24.04 (the Linux platform, D-127). Output: dist/harness-design-studio-<version>-linux-<arch>.tar.gz
The Windows package (D-149) is built by tools/build_windows.py;
it uses the pieces of this module (the program builds, the exclude list and the allow-list check).

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
            "rich", "pygments", "markdown_it", "mdurl", "chardet", "toml",
            # pydantic.v1.mypy (and PySide6's project tools) import tomli, which pip-audit pulls into
            # the build environment; the program reads no TOML
            "tomli",
            # Python's TLS module: nothing imports it (REQ-OFFLINE-04); with it goes OpenSSL's libssl
            "ssl", "_ssl",
            # nothing imports multiprocessing, but in the package PyInstaller's start-up hook for it
            # imported it at every start, and with it Python's socket module (REQ-OFFLINE-04)
            "multiprocessing"]  # fmt: skip
# Network-capable native files that the build tools collect but the program never loads (REQ-OFFLINE-04,
# D-203): they are deleted from the package after PyInstaller, and `check_package` refuses a package
# that still has one. Name -> why it can use the network.
NETWORK_STRIP: dict[str, str] = {
    r"^(lib)?qvnc\.(so|dll)$": "Qt platform plug-in that serves the window as a VNC server (TCP)",
    r"^(lib)?qtuiotouchplugin\.(so|dll)$": "Qt input plug-in that listens for TUIO touch events (UDP)",
    r"^(lib)?Qt6Network(\.so(\.\d+)*|\.dll)$": "Qt's network library (needed only by the two plug-ins above)",
    r"^lib(gssapi_krb5|krb5|k5crypto|krb5support)\.so(\.\d+)*$": "Kerberos network login (needed only by Qt's network library)",
    r"^libssl(-3(-x64)?\.dll|\.so(\.\d+)*)$": "OpenSSL's TLS library (needed only by Python's TLS module)",
    r"^_ssl(\.[\w-]+)?\.(so|pyd)$": "Python's TLS module",
}
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
            or entry.name.lower().endswith(".dll")  # Windows shared libraries
        ):
            continue  # shared libraries and the frozen standard library
        top = entry.name.split("-")[0] if entry.name.endswith(".dist-info") else entry.name
        top = top.split(".")[0]
        if _is_python_library(top):
            continue
        if not _is_known(top):
            found.add(top)
    return sorted(found)


def _is_python_library(top: str) -> bool:
    """The interpreter itself: python3.14 on Linux."""
    return top == "python3"


def undeclared_in_build(app: Path, bases: Iterable[Path] | None = None) -> list[str]:
    """Everything in the built package, the PYZ archives included, that the allow-list does not cover.

    `bases` are the folders next to the archives (default: the two `_internal` folders of the Linux
    and Windows layout)."""
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


def network_strip_reason(name: str) -> str:
    """Why a file of this name must not be in the package ("" when it may)."""
    return next((why for pattern, why in NETWORK_STRIP.items() if re.match(pattern, name)), "")


def network_capable_files(folders: Iterable[Path]) -> list[Path]:
    """The files and links below `folders` that NETWORK_STRIP names."""
    return sorted(
        p
        for folder in folders
        if folder.is_dir()
        for p in folder.rglob("*")
        if (p.is_file() or p.is_symlink()) and network_strip_reason(p.name)
    )


def elf_needed(path: Path) -> list[str]:
    """The DT_NEEDED names of a 64-bit little-endian ELF file ([] for anything else)."""
    import struct

    try:
        data = path.read_bytes()
    except OSError:
        return []
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return []
    shoff, = struct.unpack_from("<Q", data, 0x28)
    shentsize, shnum = struct.unpack_from("<HH", data, 0x3A)
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * shentsize) for i in range(shnum)]
    out: list[str] = []
    for sec in sections:
        if sec[1] != 6:  # SHT_DYNAMIC
            continue
        strtab = sections[sec[6]]  # sh_link: the string table of the dynamic section
        for off in range(sec[4], sec[4] + sec[5], 16):
            tag, val = struct.unpack_from("<qQ", data, off)
            if tag == 0:
                break
            if tag == 1:  # DT_NEEDED
                start = strtab[4] + val
                out.append(data[start : data.index(b"\0", start)].decode())
    return out


def strip_network_capable(folders: Iterable[Path]) -> list[tuple[str, int]]:
    """Delete what NETWORK_STRIP names from the package folders; (path, bytes) of each one deleted.
    Fails when a file that stays needs a deleted library (Linux: its DT_NEEDED list)."""
    folders = [f for f in folders if f.is_dir()]
    removed: list[tuple[str, int]] = []
    names: set[str] = set()
    for path in network_capable_files(folders):
        size = 0 if path.is_symlink() else path.stat().st_size
        names.add(path.name)
        path.unlink()
        removed.append((path.as_posix(), size))
    needs = sorted(
        f"{p.name} needs {n}"
        for folder in folders
        for p in folder.rglob("*.so*")
        if p.is_file() and not p.is_symlink()
        for n in elf_needed(p)
        if n in names
    )
    if needs:
        raise SystemExit("error: a file of the package needs a library that was removed: " + "; ".join(needs))
    return removed


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
    `extra_args` are more PyInstaller options (an icon)."""
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
    sep = os.pathsep  # the separator of --add-data is ":" on Linux and ";" on Windows
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
    network = network_capable_files(bases)
    if network:
        print(
            "error: network-capable files the program does not use are in the package (REQ-OFFLINE-04): "
            + ", ".join(f"{p.name} ({network_strip_reason(p.name)})" for p in network),
            file=sys.stderr,
        )
        return 1
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


def report_stripped(removed: list[tuple[str, int]]) -> None:
    for path, size in removed:
        print(f"removed (network-capable, not used): {path} ({size} bytes)")
    print(f"removed {len(removed)} network-capable files, {sum(s for _p, s in removed)} bytes")


def main() -> int:
    if build_programs():
        return 1
    app = ROOT / "dist" / PACKAGE_NAME
    shutil.rmtree(app, ignore_errors=True)
    shutil.copytree(ROOT / "build" / f"dist-{GUI_NAME}" / GUI_NAME, app, symlinks=True)
    shutil.copytree(ROOT / "build" / f"dist-{CLI_NAME}" / CLI_NAME, app / "cli")
    report_stripped(strip_network_capable((app / "_internal", app / "cli" / "_internal")))
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
