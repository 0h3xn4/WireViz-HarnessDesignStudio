"""Smoke tests of a finished Windows or macOS package (D-149), used by the workflows.

They look at the file that would be given to a user, not at the build folder:
  windows-setup FILE   install the setup program silently for the current user, run the checks,
                       uninstall it silently and check that nothing is left
  windows-zip FILE     extract the portable .zip and run the checks
  macos-dmg FILE       mount the .dmg, copy the app out, check it and run the checks
  folder DIR           the checks only, for a program folder in the layout of the Linux and Windows
                       packages (harness-design-studio-gui[.exe] and cli/harness-design-studio[.exe])
The checks of a program: `--version`, the first-steps walk-through through the command line tool
(new, validate, generate, drc, export, verify --outputs) whose files must be byte-identical to
those of the same commands run from the source install, and the editor's `--selftest`
(offscreen; the Windows editor has no console, so the result is the exit code and the file of
`--selftest-out`). On Windows the programs are blocked from the network by firewall rules while
they run (best effort: needs administrator rights, which the CI runner has).
Usage: python -m tools.smoke_package windows-setup|windows-zip|macos-dmg|folder PATH
"""

import hashlib
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from collections.abc import Callable
from pathlib import Path

from harness_design_studio import __version__

ROOT = Path(__file__).resolve().parents[1]
ISS = ROOT / "packaging" / "windows" / "harness-design-studio.iss"
APP_NAME = "Harness Design Studio"
PROJECT = "wheel-link"
WALKTHROUGH = (
    ["new", PROJECT, "--template", "first-steps"],
    ["validate", PROJECT],
    ["generate", PROJECT],
    ["drc", PROJECT],
    ["export", PROJECT],
    ["verify", PROJECT, "--outputs"],
)
TIMEOUT = 300


def say(message: str) -> None:
    print(message, flush=True)


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=False,
    )  # fmt: skip


def tail(text: str, lines: int = 12) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def tree_hashes(folder: Path) -> dict[str, str]:
    """relative path -> SHA-256 of every file below `folder`."""
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def walkthrough(cli: list[str], where: Path) -> tuple[list[str], dict[str, str]]:
    """Run the first-steps commands with `cli` in `where`; (problems, hashes of the project)."""
    where.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    env = {**os.environ, "PYTHONUTF8": "1"}
    for args in WALKTHROUGH:
        done = run([*cli, *args], cwd=where, env=env)
        if done.returncode != 0:
            problems.append(
                f"`{' '.join(args)}` ended with {done.returncode}: {tail(done.stdout + done.stderr)}"
            )
            break
    return problems, tree_hashes(where / PROJECT) if (where / PROJECT).is_dir() else {}


def source_reference(where: Path) -> dict[str, str]:
    """The same commands run from the source install (this Python), the reference for the bytes."""
    problems, hashes = walkthrough([sys.executable, "-m", "harness_design_studio.cli.main"], where)
    if problems:
        raise SystemExit(
            "error: the source install fails its own walk-through: " + "; ".join(problems)
        )
    return hashes


def check_program(cli: Path, gui: Path, work: Path, aliases: tuple[Path, ...] = ()) -> list[str]:
    """The checks of one program folder; the problems found (empty = fine)."""
    problems: list[str] = []
    for exe in (cli, gui, *aliases):
        if not exe.is_file():
            problems.append(f"missing: {exe}")
    if problems:
        return problems
    want = f"harness {__version__}"
    for exe in (cli, *aliases):
        done = run([str(exe), "--version"])
        if done.returncode != 0 or done.stdout.strip() != want:
            problems.append(
                f"{exe.name} --version printed {done.stdout.strip()!r} (exit {done.returncode}), want {want!r}"
            )
        else:
            say(f"ok: {exe.name} --version -> {want}")
    steps, got = walkthrough([str(cli)], work / "frozen")
    problems += steps
    if not steps:
        say(f"ok: first-steps walk-through through {cli.name} ({len(got)} project files)")
        want_files = source_reference(work / "source")
        if got != want_files:
            differ = sorted(
                k for k in got.keys() | want_files.keys() if got.get(k) != want_files.get(k)
            )
            problems.append(
                f"the files differ from the source install in {len(differ)} places: {differ[:8]}"
            )
        else:
            say("ok: every project file is byte-identical to the source install's")
    result = work / "selftest.txt"
    result.unlink(missing_ok=True)
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    done = run([str(gui), "--selftest", "--selftest-out", str(result)], env=env)
    text = result.read_text(encoding="utf-8").strip() if result.is_file() else "(no result file)"
    if done.returncode != 0 or text != "selftest ok":
        problems.append(
            f"{gui.name} --selftest: exit {done.returncode}, result {text!r}, {tail(done.stdout + done.stderr)}"
        )
    else:
        say(f"ok: {gui.name} --selftest -> selftest ok")
    return problems


# --- Windows ---------------------------------------------------------------------------------


def exe_names(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*.exe"))


def block_network(folder: Path) -> Callable[[], None]:
    """Firewall rules that stop every program of `folder` from making outgoing connections; the
    returned function removes them. Best effort (administrator rights are needed)."""
    names: list[str] = []
    failures: list[str] = []
    for i, exe in enumerate(exe_names(folder)):
        if exe.name.startswith("unins"):
            continue
        name = f"harness-smoke-block-{os.getpid()}-{i}"
        # one string, so that the quotes around the program are the ones netsh wants
        rule = f'netsh advfirewall firewall add rule name="{name}" dir=out action=block program="{exe}" enable=yes'
        done = subprocess.run(rule, capture_output=True, text=True, check=False)  # noqa: S603
        if done.returncode == 0:
            names.append(name)
        elif not failures:
            failures.append(f"{rule} -> {(done.stdout + done.stderr).strip()[:300]}")
    say(f"network: {len(names)} programs are blocked from outgoing connections by firewall rules")
    if failures:
        say("network: the first rule that failed said: " + failures[0])

    def undo() -> None:
        for name in names:
            run(
                ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"]
            )  # no spaces in name

    return undo


def windows_program(folder: Path, work: Path) -> list[str]:
    undo = block_network(folder)
    try:
        cli = folder / "cli" / "harness-design-studio.exe"
        return check_program(cli, folder / "harness-design-studio-gui.exe", work,
                             (folder / "cli" / "harness.exe",))  # fmt: skip
    finally:
        undo()


def app_id() -> str:
    match = re.search(r"^AppId=\{\{([0-9A-Fa-f-]+)\}", ISS.read_text(encoding="utf-8"), re.M)
    if match is None:
        raise SystemExit(f"error: no AppId in {ISS}")
    return "{" + match.group(1) + "}"


def user_path() -> list[str]:
    if sys.platform != "win32":
        raise OSError("the registry is Windows only")
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        try:
            value, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            return []
    return [p.rstrip("\\").lower() for p in str(value).split(";") if p]


def uninstall_key_exists() -> bool:
    if sys.platform != "win32":
        raise OSError("the registry is Windows only")
    import winreg

    path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_id()}_is1"
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, path))
    except FileNotFoundError:
        return False
    return True


def start_menu_folder() -> Path:
    return (
        Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME
    )


def windows_setup(setup: Path, work: Path) -> list[str]:
    target = work / "install folder" / APP_NAME  # with spaces, like most real paths
    log = work / "setup.log"
    before = user_path()
    say(f"installing {setup.name} into {target}")
    done = run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER",
                f"/DIR={target}", f"/LOG={log}"], timeout=600)  # fmt: skip
    problems: list[str] = []
    if done.returncode != 0:
        problems.append(f"the setup program ended with {done.returncode}")
    if not (target / "harness-design-studio-gui.exe").is_file():
        text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else "(no log)"
        say("---- setup log (end) ----\n" + tail(text, 40))
        return [*problems, "the setup program installed nothing"]
    say("ok: installed without administrator rights")
    for rel in ("cli/harness-design-studio.exe", "cli/harness.exe", "unins000.exe", "LICENSES/LGPL-3.txt",
                "README-windows.txt"):  # fmt: skip
        if not (target / rel).is_file():
            problems.append(f"the install lacks {rel}")
    shortcut = start_menu_folder() / f"{APP_NAME}.lnk"
    if not shortcut.is_file():
        problems.append(f"no Start menu entry at {shortcut}")
    else:
        say("ok: Start menu entry")
    entries = user_path()
    for entry in (target / "cli", target):
        if str(entry).lower() not in entries:
            problems.append(f"{entry} is not on the user PATH")
    if uninstall_key_exists():
        say("ok: registered with Apps & features (uninstall key)")
    else:
        problems.append("no uninstall registration under HKCU")
    problems += windows_program(target, work)
    say("uninstalling")
    run(
        [str(target / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        timeout=600,
    )
    deadline = time.monotonic() + 120  # the uninstaller hands over to a copy of itself
    while target.exists() and time.monotonic() < deadline:
        time.sleep(2)
    if target.exists():
        problems.append(
            f"the uninstaller left {target}: {sorted(p.name for p in target.iterdir())[:10]}"
        )
    else:
        say("ok: the install folder is gone")
    if any(str(e).lower() in user_path() for e in (target / "cli", target)):
        problems.append("the user PATH still lists the install folder")
    if user_path() != before:
        problems.append("the user PATH differs from before the install")
    else:
        say("ok: the user PATH is as before")
    if uninstall_key_exists():
        problems.append("the uninstall registration is still there")
    if start_menu_folder().exists():
        problems.append("the Start menu folder is still there")
    return problems


def windows_zip(archive: Path, work: Path) -> list[str]:
    target = work / "portable folder"
    with zipfile.ZipFile(archive) as zf:
        bad = zf.testzip()
        if bad:
            return [f"damaged member {bad}"]
        names = zf.namelist()
        zf.extractall(target)
    say(f"extracted {len(names)} files")
    problems = [f"missing {n} at the top of the .zip" for n in ("harness-design-studio-gui.exe",
                "cli/harness-design-studio.exe", "cli/harness.exe", "LICENSES/LGPL-3.txt") if n not in names]  # fmt: skip
    return problems or windows_program(target, work)


# --- macOS -----------------------------------------------------------------------------------


def plist_problems(app: Path) -> list[str]:
    with (app / "Contents" / "Info.plist").open("rb") as f:
        info = plistlib.load(f)
    want = {
        "CFBundleIdentifier": "org.harnessdesignstudio.app",
        "CFBundleShortVersionString": __version__,
        "CFBundleExecutable": "harness-design-studio-gui",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
    }
    problems = [
        f"Info.plist {k} is {info.get(k)!r}, want {v!r}"
        for k, v in want.items()
        if info.get(k) != v
    ]
    icon = str(info.get("CFBundleIconFile", ""))
    if (
        not icon
        or not (
            app / "Contents" / "Resources" / (icon if icon.endswith(".icns") else icon + ".icns")
        ).is_file()
    ):
        problems.append(f"the icon {icon!r} of Info.plist is not in Contents/Resources")
    return problems


def macos_app(app: Path, work: Path) -> list[str]:
    problems = plist_problems(app)
    macos = app / "Contents" / "MacOS"
    gui = macos / "harness-design-studio-gui"
    if gui.is_file():
        archs = run(["lipo", "-archs", str(gui)]).stdout.split()
        if platform.machine() not in archs:
            problems.append(
                f"the editor is built for {archs}, this machine is {platform.machine()}"
            )
        else:
            say(f"ok: built for {platform.machine()}")
    verify = run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)])
    if verify.returncode != 0:
        problems.append("codesign --verify: " + tail(verify.stdout + verify.stderr))
    else:
        say("ok: the signature is valid")
    return problems + check_program(
        macos / "harness-design-studio", gui, work, (macos / "harness",)
    )


def macos_dmg(dmg: Path, work: Path) -> list[str]:
    mount = work / "mount"
    mount.mkdir()
    attach = run(
        ["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(mount), str(dmg)]
    )
    if attach.returncode != 0:
        return ["hdiutil attach: " + tail(attach.stdout + attach.stderr)]
    problems: list[str] = []
    copied = work / f"{APP_NAME}.app"
    try:
        shown = sorted(p.name for p in mount.iterdir())
        say(f"the image holds: {shown}")
        if not (mount / "Applications").is_symlink():
            problems.append("the image has no Applications link")
        if not (mount / f"{APP_NAME}.app").is_dir():
            return [*problems, f"the image has no {APP_NAME}.app"]
        subprocess.run(["ditto", str(mount / f"{APP_NAME}.app"), str(copied)], check=True)
    finally:
        for attempt in range(3):
            if (
                run(["hdiutil", "detach", str(mount), *(["-force"] if attempt else [])]).returncode
                == 0
            ):
                break
            time.sleep(3)
    return problems + macos_app(copied, work)


def main(argv: list[str]) -> int:
    modes: dict[str, Callable[[Path, Path], list[str]]] = {
        "windows-setup": windows_setup,
        "windows-zip": windows_zip,
        "macos-dmg": macos_dmg,
        "folder": lambda folder, work: check_program(
            *(
                (
                    folder / "cli" / "harness-design-studio.exe",
                    folder / "harness-design-studio-gui.exe",
                )
                if sys.platform == "win32"
                else (
                    folder / "cli" / "harness-design-studio",
                    folder / "harness-design-studio-gui",
                )
            ),
            work,
        ),
    }
    if len(argv) != 2 or argv[0] not in modes or not Path(argv[1]).exists():
        print(__doc__, file=sys.stderr)
        return 2
    tmp = tempfile.mkdtemp(prefix="harness-smoke-")
    try:
        problems = modes[argv[0]](Path(argv[1]).resolve(), Path(tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # a program that is still closing may hold a file
    for problem in problems:
        print(f"FAILED: {problem}", file=sys.stderr)
    say("smoke test passed" if not problems else f"smoke test FAILED ({len(problems)} problems)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
