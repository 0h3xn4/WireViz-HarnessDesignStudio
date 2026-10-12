"""Build a self-contained, offline package with PyInstaller (one-folder) and archive it.

Ubuntu only (D-110). Build on Ubuntu 24.04 (the supported platform).
Output: dist/harness-design-studio-<version>-linux-<arch>.tar.gz
"""

import platform
import shutil
import subprocess
import sys
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
        if entry.name.startswith("lib") or entry.name == "base_library.zip":
            continue  # shared libraries and the frozen standard library
        top = entry.name.split("-")[0] if entry.name.endswith(".dist-info") else entry.name
        top = top.split(".")[0]
        if top != "python3" and not _is_known(top):
            found.add(top)
    return sorted(found)


def undeclared_in_build(app: Path) -> list[str]:
    """Everything in the built package, the PYZ archives included, that the allow-list does not cover."""
    from PyInstaller.archive.readers import ZlibArchiveReader  # type: ignore[import-untyped]

    found: set[str] = set()
    for name in ("harness-design-studio", "harness"):
        pyz = ROOT / "build" / name / name / "PYZ-00.pyz"
        found.update(undeclared_modules(ZlibArchiveReader(str(pyz)).toc))
    for base in (app / "_internal", app / "cli" / "_internal"):
        if base.is_dir():
            found.update(undeclared_files(base))
    return sorted(found)


def _pyinstaller(
    name: str, entry: Path, *, windowed: bool, extra_excludes: tuple[str, ...] = ()
) -> int:
    work = ROOT / "build"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--windowed" if windowed else "--console",
           "--name", name, "--distpath", str(ROOT / "dist"), "--workpath", str(work / name),
           "--specpath", str(work), "--paths", str(ROOT / "src")]  # fmt: skip
    for mod in (*EXCLUDES, *extra_excludes):
        cmd += ["--exclude-module", mod]
    cmd += [
        "--hidden-import",
        "defusedxml",
    ]  # openpyxl imports it only if present: XML bomb protection
    guide = ROOT / "src" / "harness_design_studio" / "resources" / "guide"
    cmd += ["--add-data", f"{guide}:harness_design_studio/resources/guide"]
    examples = (
        ROOT / "src" / "harness_design_studio" / "resources" / "examples"
    )  # `harness new`, templates
    cmd += ["--add-data", f"{examples}:harness_design_studio/resources/examples"]
    fonts = ROOT / "src" / "harness_design_studio" / "resources" / "fonts"  # IBM Plex, SIL OFL 1.1
    cmd += ["--add-data", f"{fonts}:harness_design_studio/resources/fonts"]
    cmd.append(str(entry))
    return subprocess.run(cmd, check=False).returncode


def main() -> int:
    packaging = ROOT / "packaging"
    if _pyinstaller("harness-design-studio", packaging / "gui_entry.py", windowed=True):
        return 1
    # Console command (validate/check/migrate); no Qt, so it stays small. Shipped inside the folder.
    if _pyinstaller(
        "harness",
        packaging / "cli_entry.py",
        windowed=False,
        extra_excludes=("PySide6", "shiboken6"),
    ):
        return 1
    shutil.copytree(
        ROOT / "dist" / "harness",
        ROOT / "dist" / "harness-design-studio" / "cli",
        dirs_exist_ok=True,
    )
    shutil.rmtree(ROOT / "dist" / "harness", ignore_errors=True)
    app = ROOT / "dist" / "harness-design-studio"
    leaked = sorted(
        p.name for base in (app / "_internal", app / "cli" / "_internal") if base.is_dir()
        for p in base.iterdir() if p.name.split(".")[0] in FORBIDDEN
    )  # fmt: skip
    if leaked:
        print(
            f"error: development tools ended up in the package: {', '.join(leaked)}",
            file=sys.stderr,
        )
        return 1
    extra = undeclared_in_build(app)
    if extra:
        print(
            "error: code that is not a declared dependency ended up in the package (its licence "
            f"is not shipped): {', '.join(extra)}. Add it to EXCLUDES, or to ALLOWED_PACKAGES with "
            "its licence and SBOM entry.",
            file=sys.stderr,
        )
        return 1
    from tools.collect_licences import collect

    collect(app / "LICENSES")
    for item in (
        ROOT / "packaging" / "ubuntu"
    ).iterdir():  # install scripts, desktop file, icon, readme
        if item.is_file():
            shutil.copy2(item, ROOT / "dist" / "harness-design-studio" / item.name)
    system = platform.system().lower()
    base = (
        ROOT / "dist" / f"harness-design-studio-{__version__}-{system}-{platform.machine().lower()}"
    )
    fmt = "gztar"
    archive = shutil.make_archive(
        str(base), fmt, root_dir=ROOT / "dist", base_dir="harness-design-studio"
    )
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
