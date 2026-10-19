"""Build the macOS package (D-149): "Harness Design Studio.app" in a .dmg. Run on macOS.

Output: dist/harness-design-studio-<version>-macos-<arch>.dmg with arch = platform.machine()
(arm64 on Apple Silicon, x86_64 on Intel): the program is built for the machine it is built on.

The app (dist/Harness Design Studio.app):
  Contents/MacOS/harness-design-studio-gui    the editor (answers --selftest and --drc-worker)
  Contents/MacOS/harness-design-studio        the command line tool (a launcher for the program
  Contents/MacOS/harness                      in Contents/Resources/cli; `harness` is the short name)
  Contents/Resources/cli/                     the command line tool built with PyInstaller (no Qt)
  Contents/Resources/LICENSES/                the licences of the shipped components
The .dmg holds the app and a link to /Applications.

Without a certificate the app is signed ad hoc (Apple Silicon refuses unsigned code) and is neither
signed with a Developer ID nor notarized: the first start needs *Open* from the context menu. The
environment can switch signing on (all optional; the release workflow sets them when the repository has a certificate):
  HARNESS_MACOS_IDENTITY       name of the Developer ID Application certificate in the keychain
  HARNESS_NOTARY_APPLE_ID, HARNESS_NOTARY_TEAM_ID, HARNESS_NOTARY_PASSWORD
                               (app-specific password) to notarize and staple the .dmg
Signing and notarization use Apple's servers; the finished program never uses the network.
Usage: python -m tools.build_macos
"""

import os
import platform
import plistlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

from harness_design_studio import __version__
from tools.build_installer import (
    CLI_NAME,
    GUI_NAME,
    PACKAGE_NAME,
    ROOT,
    build_programs,
    check_package,
)

PK = ROOT / "packaging" / "macos"
APP_NAME = "Harness Design Studio"
BUNDLE_ID = "org.harnessdesignstudio.app"
MIN_SYSTEM = "13.0"
ALIAS = "harness"
LAUNCHER = """#!/bin/sh
# Starts the command line tool that is inside this app (Contents/Resources/cli).
self="$0"
while [ -h "$self" ]; do
  dir=$(cd "$(dirname "$self")" && pwd)
  link=$(readlink "$self")
  case "$link" in /*) self="$link" ;; *) self="$dir/$link" ;; esac
done
here=$(cd "$(dirname "$self")" && pwd)
exec "$here/../Resources/cli/@CLI@" "$@"
""".replace("@CLI@", CLI_NAME)
MACHO_MAGIC = {
    b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
}  # fmt: skip


def arch() -> str:
    return platform.machine().lower()  # arm64 or x86_64


def dmg_name(version: str = __version__) -> str:
    return f"{PACKAGE_NAME}-{version}-macos-{arch()}.dmg"


def run(cmd: list[str], **kw: object) -> None:
    subprocess.run(cmd, check=True, **kw)  # type: ignore[call-overload]


def ditto(src: Path, dst: Path) -> None:
    """Copy a folder the way Finder does (links, modes and resource forks kept)."""
    run(["ditto", str(src), str(dst)])


def info_plist(existing: dict[str, object]) -> dict[str, object]:
    """The Info.plist of the app: PyInstaller's keys with the ones of this program set."""
    plist = dict(existing)
    plist.update(
        {
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleExecutable": GUI_NAME,
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "LSMinimumSystemVersion": MIN_SYSTEM,
            "LSApplicationCategoryType": "public.app-category.developer-tools",
            "NSHighResolutionCapable": True,
            "NSSupportsAutomaticGraphicsSwitching": True,
            "NSHumanReadableCopyright": "Harness Design Studio",
        }
    )
    return plist


def edit_plist(app: Path) -> None:
    path = app / "Contents" / "Info.plist"
    with path.open("rb") as f:
        existing = plistlib.load(f)
    with path.open("wb") as f:
        plistlib.dump(info_plist(existing), f)


def add_command_line_tool(app: Path) -> None:
    """The command line tool inside the app, next to the editor, with the `harness` short name."""
    ditto(ROOT / "build" / f"dist-{CLI_NAME}" / CLI_NAME, app / "Contents" / "Resources" / "cli")
    for name in (CLI_NAME, ALIAS):
        launcher = app / "Contents" / "MacOS" / name
        launcher.write_text(LAUNCHER, encoding="utf-8")
        launcher.chmod(0o755)


def is_macho(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(4) in MACHO_MAGIC
    except OSError:
        return False


def sign_tree(folder: Path, identity: str, entitlements: Path) -> None:
    """Sign every Mach-O file of a plain folder (the command line tool), deepest first, and then
    the framework bundles in it (Python.framework), so that each bundle is sealed after its files."""
    files = [p for p in folder.rglob("*") if p.is_file() and not p.is_symlink() and is_macho(p)]
    for path in sorted(files, key=lambda p: len(p.parts), reverse=True):
        run(["codesign", "--force", "--options", "runtime", "--timestamp",
             "--entitlements", str(entitlements), "--sign", identity, str(path)])  # fmt: skip
    frameworks = [p for p in folder.rglob("*.framework") if p.is_dir() and not p.is_symlink()]
    for path in sorted(frameworks, key=lambda p: len(p.parts), reverse=True):
        run(["codesign", "--force", "--options", "runtime", "--timestamp",
             "--sign", identity, str(path)])  # fmt: skip


def sign_app(app: Path, identity: str | None) -> None:
    """Seal the finished app. Ad hoc without an identity (Apple Silicon needs some signature)."""
    if identity is None:
        run(["codesign", "--force", "--deep", "--sign", "-", str(app)])
        return
    entitlements = PK / "entitlements.plist"
    sign_tree(app / "Contents" / "Resources" / "cli", identity, entitlements)
    run(["codesign", "--force", "--options", "runtime", "--timestamp",
         "--entitlements", str(entitlements), "--sign", identity, str(app)])  # fmt: skip
    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)])


def make_dmg(app: Path, target: Path, identity: str | None) -> Path:
    stage = ROOT / "build" / "dmg"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    ditto(app, stage / app.name)
    (stage / "Applications").symlink_to("/Applications")
    shutil.copy2(PK / "README-macos.txt", stage / "README.txt")
    target.unlink(missing_ok=True)
    cmd = ["hdiutil", "create", "-volname", APP_NAME, "-srcfolder", str(stage), "-fs", "HFS+",
           "-format", "UDZO", "-imagekey", "zlib-level=9", "-ov", str(target)]  # fmt: skip
    for attempt in range(3):  # hdiutil sometimes fails with "Resource busy" on a shared runner
        try:
            run(cmd)
            break
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(5)
    if identity is not None:
        run(["codesign", "--force", "--timestamp", "--sign", identity, str(target)])
    return target


def notarize(dmg: Path) -> None:
    """Send the .dmg to Apple's notary service, wait for the verdict and staple the ticket."""
    run(["xcrun", "notarytool", "submit", str(dmg), "--wait",
         "--apple-id", os.environ["HARNESS_NOTARY_APPLE_ID"],
         "--team-id", os.environ["HARNESS_NOTARY_TEAM_ID"],
         "--password", os.environ["HARNESS_NOTARY_PASSWORD"]])  # fmt: skip
    run(["xcrun", "stapler", "staple", str(dmg)])


def main() -> int:
    if sys.platform != "darwin":
        print("error: the macOS package is built on macOS", file=sys.stderr)
        return 1
    if arch() not in ("arm64", "x86_64"):
        print(f"error: unknown processor {platform.machine()}", file=sys.stderr)
        return 1
    from tools.make_icons import write_icns

    identity = os.environ.get("HARNESS_MACOS_IDENTITY") or None
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    (ROOT / "build").mkdir(exist_ok=True)
    icon = write_icns(ROOT / "build" / "harness-design-studio.icns")
    gui_args = ["--icon", str(icon), "--osx-bundle-identifier", BUNDLE_ID]
    if identity is not None:  # PyInstaller signs the editor's libraries and frameworks itself
        gui_args += ["--codesign-identity", identity,
                     "--osx-entitlements-file", str(PK / "entitlements.plist")]  # fmt: skip
    if build_programs(gui_args=tuple(gui_args)):
        return 1
    built = ROOT / "build" / f"dist-{GUI_NAME}" / f"{GUI_NAME}.app"
    if not built.is_dir():
        print(f"error: PyInstaller made no {built.name}", file=sys.stderr)
        return 1
    app = dist / f"{APP_NAME}.app"
    shutil.rmtree(app, ignore_errors=True)
    ditto(built, app)
    edit_plist(app)
    add_command_line_tool(app)
    if check_package(
        (app / "Contents" / "Frameworks", app / "Contents" / "Resources" / "cli" / "_internal"), app
    ):
        return 1
    from tools.collect_licences import collect

    collect(app / "Contents" / "Resources" / "LICENSES")
    sign_app(app, identity)
    dmg = make_dmg(app, dist / dmg_name(), identity)
    if all(os.environ.get(k) for k in ("HARNESS_NOTARY_APPLE_ID", "HARNESS_NOTARY_TEAM_ID",
                                       "HARNESS_NOTARY_PASSWORD")) and identity is not None:  # fmt: skip
        notarize(dmg)
    print(dmg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
