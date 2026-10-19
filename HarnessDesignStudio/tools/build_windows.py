"""Build the Windows packages (D-149): a portable .zip and the Inno Setup installer. Run on Windows.

Output in dist/:
  harness-design-studio-<version>-windows-x86_64.zip          the program folder, to extract anywhere
  harness-design-studio-<version>-windows-x86_64-setup.exe    per-user installer (no administrator)

The program folder dist/harness-design-studio/ has the same layout as the Linux one:
  harness-design-studio-gui.exe        the editor (windowed, no console; answers --selftest)
  cli/harness-design-studio.exe        the command line tool (console); cli/harness.exe is a copy
Needs Inno Setup 6 (ISCC.exe on the PATH or in its usual folder). Signing happens only when the
environment names a certificate: HARNESS_SIGN_PFX (path of the .pfx file) and HARNESS_SIGN_PASSWORD,
optionally HARNESS_SIGN_TIMESTAMP_URL; without them the files are unsigned. Signing is the only
step that uses the network (the timestamp); the finished program never does.
Usage: python -m tools.build_windows [--no-installer]
"""

import os
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from harness_design_studio import __version__
from tools.build_installer import (
    CLI_NAME,
    GUI_NAME,
    PACKAGE_NAME,
    ROOT,
    build_programs,
    check_package,
    ttf_fonts_args,
)

PK = ROOT / "packaging" / "windows"
ISS = PK / "harness-design-studio.iss"
# tzdata comes with the build environment on Windows (zoneinfo has no system database there) but the
# program uses no time zones, and it is not a declared dependency (its licence would not be shipped)
EXCLUDES = ("tzdata",)
ALIAS = "harness"  # the short name of the command line tool, as with pip
DEFAULT_TIMESTAMP_URL = "http://timestamp.digicert.com"


def zip_name(version: str = __version__) -> str:
    return f"{PACKAGE_NAME}-{version}-windows-x86_64.zip"


def setup_name(version: str = __version__) -> str:
    return f"{PACKAGE_NAME}-{version}-windows-x86_64-setup.exe"


def numeric_version(version: str) -> str:
    """1.2.0 or 1.2.0rc1 -> 1.2.0.0 (the version resource of the setup program takes numbers only)."""
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if match is None:
        raise ValueError(f"version {version!r} does not start with three numbers")
    return ".".join(match.groups()) + ".0"


def make_zip(folder: Path, target: Path, stamp: int) -> Path:
    """A .zip of the contents of `folder` (no top folder, so Explorer's *Extract All* makes one named
    like the file). Sorted entries, fixed times and modes: the same input gives the same bytes."""
    date = max(stamp, 315532800)  # the zip format starts in 1980
    when = time.gmtime(date)[:6]
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(folder).as_posix(), when)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (
                0o755 if path.suffix.lower() in (".exe", ".dll", ".pyd") else 0o644
            ) << 16
            zf.writestr(info, path.read_bytes(), zipfile.ZIP_DEFLATED, 9)
    return target


def find_iscc() -> Path | None:
    found = shutil.which("ISCC")
    if found:
        return Path(found)
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if not base:
            continue
        for sub in ("Inno Setup 6", "Programs/Inno Setup 6"):
            candidate = Path(base) / sub / "ISCC.exe"
            if candidate.is_file():
                return candidate
    return None


def find_signtool() -> Path | None:
    found = shutil.which("signtool")
    if found:
        return Path(found)
    kits = (
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
        / "Windows Kits"
        / "10"
        / "bin"
    )
    candidates = sorted(kits.glob("*/x64/signtool.exe"), reverse=True) if kits.is_dir() else []
    return candidates[0] if candidates else None


def signing_requested() -> bool:
    return bool(os.environ.get("HARNESS_SIGN_PFX"))


def sign(files: list[Path]) -> None:
    """Authenticode-sign the files with the certificate named in the environment."""
    pfx = os.environ.get("HARNESS_SIGN_PFX", "")
    tool = find_signtool()
    if not Path(pfx).is_file():
        raise SystemExit(f"error: HARNESS_SIGN_PFX names no file: {pfx}")
    if tool is None:
        raise SystemExit("error: signtool.exe not found (it comes with the Windows SDK)")
    cmd = [str(tool), "sign", "/fd", "SHA256", "/f", pfx]
    if os.environ.get("HARNESS_SIGN_PASSWORD"):
        cmd += ["/p", os.environ["HARNESS_SIGN_PASSWORD"]]
    cmd += [
        "/tr",
        os.environ.get("HARNESS_SIGN_TIMESTAMP_URL") or DEFAULT_TIMESTAMP_URL,
        "/td",
        "SHA256",
    ]
    for start in range(0, len(files), 20):  # keep the command line short
        subprocess.run([*cmd, *map(str, files[start : start + 20])], check=True)
    print(f"signed {len(files)} files")


def run_iscc(iscc: Path, app: Path, out_dir: Path, icon: Path) -> Path:
    cmd = [
        str(iscc), "/Q",
        f"/DAppVersion={__version__}",
        f"/DNumericVersion={numeric_version(__version__)}",
        f"/DSourceDir={app}",
        f"/DOutputDir={out_dir}",
        f"/DIconFile={icon}",
        str(ISS),
    ]  # fmt: skip
    subprocess.run(cmd, check=True)
    target = out_dir / setup_name()
    if not target.is_file():
        raise SystemExit(f"error: Inno Setup did not write {target}")
    return target


def assemble(app: Path) -> int:
    """Copy the two built programs into dist/harness-design-studio and add licences and the readme."""
    shutil.rmtree(app, ignore_errors=True)
    shutil.copytree(ROOT / "build" / f"dist-{GUI_NAME}" / GUI_NAME, app)
    shutil.copytree(ROOT / "build" / f"dist-{CLI_NAME}" / CLI_NAME, app / "cli")
    # The same program under its short name: a PyInstaller exe finds its libraries (_internal) next
    # to itself whatever it is called.
    shutil.copy2(app / "cli" / f"{CLI_NAME}.exe", app / "cli" / f"{ALIAS}.exe")
    if check_package((app / "_internal", app / "cli" / "_internal"), app):
        return 1
    from tools.collect_licences import collect

    collect(app / "LICENSES")
    shutil.copy2(PK / "README-windows.txt", app / "README-windows.txt")
    return 0


def main(argv: list[str]) -> int:
    if sys.platform != "win32":
        print("error: the Windows packages are built on Windows", file=sys.stderr)
        return 1
    if platform.machine().lower() not in ("amd64", "x86_64"):
        print(
            f"error: the package is for 64-bit x86, this machine is {platform.machine()}",
            file=sys.stderr,
        )
        return 1
    installer = "--no-installer" not in argv
    iscc = find_iscc() if installer else None
    if installer and iscc is None:
        print("error: Inno Setup 6 (ISCC.exe) not found: choco install innosetup", file=sys.stderr)
        return 1
    from tools.build_deb import epoch
    from tools.make_icons import write_ico

    dist = ROOT / "dist"
    (ROOT / "build").mkdir(exist_ok=True)
    icon = write_ico(ROOT / "build" / "harness-design-studio.ico")
    if build_programs(
        gui_args=("--icon", str(icon), *ttf_fonts_args()),
        cli_args=("--icon", str(icon)),
        extra_excludes=EXCLUDES,
    ):
        return 1
    app = dist / PACKAGE_NAME
    if assemble(app):
        return 1
    if signing_requested():
        sign(sorted(p for p in app.rglob("*.exe")))
    archive = make_zip(app, dist / zip_name(), epoch())
    print(archive)
    if iscc is not None:
        setup = run_iscc(iscc, app, dist, icon)
        if signing_requested():
            sign([setup])
        print(setup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
