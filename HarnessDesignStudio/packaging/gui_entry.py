"""PyInstaller entry point. `--selftest` exercises the real editor offscreen and exits (used by CI).

The self-test opens the sample, adds a unit, connects two units, saves to a temp folder, reloads it
and checks the result, so a broken package fails loudly instead of showing an empty window.

The Windows editor has no console, so it prints nothing: the exit code (0 = ok) is the result, and
`--selftest --selftest-out FILE` also writes the message ("selftest ok" or what failed) to FILE.

`--audit-run PROJECT REPORT [SECONDS]` is the editor's part of the offline audit
(`tools/offline_audit.py`, REQ-OFFLINE-02): it starts the editor as a person would (the real
settings file, a first start when there is none), opens PROJECT, presses F1 for the guide with the
system's URL opener replaced by a recorder (no browser is started), runs the design rule check in
its helper process, opens a folder that does not exist (a deliberate error), stays idle for SECONDS
(default 20) and quits; REPORT gets what it saw as JSON (the URLs the editor asked to open, the
shared libraries mapped into this process, the network modules of Python that were imported).
It changes nothing that the editor does: it only drives it.
"""

import os
import sys
import tempfile
from pathlib import Path


def _asked(flag: str, argv: list[str]) -> bool:
    """True when `flag` is the first argument (a project path or other argument never counts)."""
    return argv[1:2] == [flag]


if __name__ == "__main__" and _asked("--drc-worker", sys.argv):
    # The editor starts this same program as its helper process for the design rule check.
    from harness_design_studio.core.drc.worker import main as _drc_worker

    raise SystemExit(_drc_worker())


def _tell(message: str) -> None:
    """Say why the editor cannot start, where the person will see it: on the terminal, and in a
    small window when it was started from the menu (a program started that way has no terminal).
    The window comes from zenity, kdialog or xmessage when the machine has one."""
    import shutil
    import subprocess

    print(message, file=sys.stderr)
    if sys.stderr is not None and sys.stderr.isatty():
        return
    env = {k: v for k, v in os.environ.items() if k != "LD_LIBRARY_PATH"}
    if "LD_LIBRARY_PATH_ORIG" in os.environ:  # the bootloader's own value: the system tools need it
        env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH_ORIG"]
    title = "Harness Design Studio"
    for tool, args in (
        ("zenity", ["--error", "--no-markup", "--title", title, "--text", message]),
        ("kdialog", ["--title", title, "--error", message]),
        ("xmessage", ["-center", message]),
    ):
        found = shutil.which(tool, path=env.get("PATH"))
        if found:
            try:
                subprocess.run([found, *args], env=env, timeout=600, check=False)  # noqa: S603
            except OSError, subprocess.SubprocessError:
                continue
            return


def _check_system(argv: list[str]) -> int | None:
    """The first-start check of the machine's own libraries (Linux). Returns an exit code when
    the editor must not go on, else None. `--check-system` runs only this and says "ok"."""
    import ctypes

    from harness_design_studio.gui import startup_help

    only_check = _asked("--check-system", argv)
    if not only_check and (_asked("--selftest", argv) or os.environ.get("QT_QPA_PLATFORM")):
        return None  # the self-test and an explicit platform (offscreen) need no window system
    missing = startup_help.missing_libraries(ctypes.CDLL)
    if missing:
        _tell(startup_help.message(missing))
        return startup_help.EXIT_CODE
    if startup_help.no_display(os.environ) and not only_check:
        _tell(startup_help.NO_DISPLAY_MESSAGE)
        return startup_help.EXIT_CODE
    if only_check:
        print("system libraries ok")
        return 0
    return None


if __name__ == "__main__":
    _code = _check_system(sys.argv)
    if _code is not None:
        raise SystemExit(_code)

try:
    from harness_design_studio.gui.app import create_window, main  # noqa: E402
except ImportError as _error:  # a library the check did not name: say which, not a traceback
    from harness_design_studio.gui import startup_help as _help

    _named = _help.from_error(str(_error))
    if _named:
        _tell(_help.message(_named))
        raise SystemExit(_help.EXIT_CODE) from None
    raise


def _report(message: str, out: Path | None) -> None:
    """Print the result and, when asked, write it to a file (a windowed program has no stdout)."""
    print(message)
    if out is not None:
        out.write_text(message + "\n", encoding="utf-8")


def selftest(out: Path | None = None) -> int:
    if not os.environ.get("QT_QPA_PLATFORM"):  # an empty value is as good as none and aborts Qt
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    try:
        with tempfile.TemporaryDirectory(prefix="harness-selftest-") as folder:
            failed = _run_steps(Path(folder))
    except Exception:
        if out is None:
            raise
        import traceback

        _report("selftest FAILED with an error:\n" + traceback.format_exc(), out)
        return 1
    if failed:
        _report("selftest FAILED at: " + ", ".join(failed), out)
        return 1
    _report("selftest ok", out)
    return 0


def _selftest_out(argv: list[str]) -> Path | None:
    """The FILE of `--selftest --selftest-out FILE` (None without it)."""
    return Path(argv[3]) if len(argv) == 4 and argv[2] == "--selftest-out" else None


def _run_steps(tmp: Path) -> list[str]:
    """Run every step; return the names of the ones that failed."""
    from PySide6.QtCore import QSettings

    from harness_design_studio.core.io.loader import load_project

    win = create_window(QSettings(str(tmp / "ui.ini"), QSettings.Format.IniFormat), first_run=False)
    win.show()
    ctl = win.ctl
    try:
        uid = ctl.add_unit("sensor")
        ctl.begin_connect("rs422")
        ctl.pick("OBC")
        ctl.pick(uid or "ST1")
        ctl.save_as(tmp / "project")
        loaded = load_project(tmp / "project")
        results = {
            "edit, save and reload": uid in loaded.project.units
            and len(loaded.project.interfaces) == 3
            and not loaded.has_errors,
            "generate and export": _generate_and_export(ctl, tmp),
            "rule check process": _rule_check_process_works(ctl),
            "bundled examples": _examples_are_bundled(tmp),
            "bundled fonts": _fonts_are_bundled(),
            "runs on its own Python": _runs_from_its_own_python(),
        }
    finally:
        ctl.release()
        win.settings.sync()  # the window keeps Home's recent list in them; write now, not at exit
    return [name for name, ok in results.items() if not ok]


def _own_roots() -> list[Path]:
    """The folders that belong to the package: the one the program starts from, the one PyInstaller
    unpacks to."""
    exe = Path(sys.executable).resolve()
    roots = [exe.parent]
    if getattr(sys, "_MEIPASS", None):
        roots.append(Path(sys._MEIPASS).resolve())  # type: ignore[attr-defined]
    return roots


def _runs_from_its_own_python() -> bool:
    """A package runs on the Python and Qt inside it: nothing it imports comes from outside its own
    folder. (From the source install the question does not arise.)"""
    if not getattr(sys, "frozen", False):
        return True
    roots = _own_roots()
    inside = [p for p in sys.path if p and any(Path(p).resolve().is_relative_to(r) for r in roots)]
    return bool(inside) and len(inside) == len([p for p in sys.path if p])


def _examples_are_bundled(tmp: Path) -> bool:
    """`harness-design-studio new` works from the packaged program: the examples are inside it."""
    from harness_design_studio.core import templates

    made = templates.create_project(tmp / "from-example", "first-steps")
    files = templates.copy_import_templates(tmp / "templates")
    return len(made.units) == 3 and any(f.name == "interfaces.csv" for f in files)


def _fonts_are_bundled() -> bool:
    """The Inter and JetBrains Mono fonts are inside the package and Qt can load them."""
    from harness_design_studio.gui.theme import fonts

    return {fonts.UI_FAMILY, fonts.MONO_FAMILY} <= set(fonts.load_fonts())


def _rule_check_process_works(ctl: object) -> bool:
    """The helper process starts from the packaged program and agrees with a check done here."""
    from harness_design_studio.core import drc
    from harness_design_studio.gui.drc_process import _shared, run_check

    project = ctl.project  # type: ignore[attr-defined]
    found = run_check(project)
    alive = _shared.alive  # False would mean it silently fell back to running in this process
    _shared.close()
    return alive and found == drc.run(project)


def _generate_and_export(ctl: object, tmp: Path) -> bool:
    """Generate harnesses, build every output type, verify them independently and write them."""
    from harness_design_studio.core.commands import apply_ops
    from harness_design_studio.core.generate.engine import plan_generation
    from harness_design_studio.core.outputs.build import build_outputs, write_outputs
    from harness_design_studio.core.outputs.verify import read_folder, verify_outputs

    project = ctl.project  # type: ignore[attr-defined]
    apply_ops(project, plan_generation(project).ops)
    built = build_outputs(project)
    if not verify_outputs(project, built.files).ok:
        return False
    write_outputs(project, tmp / "outputs", built)
    return verify_outputs(project, read_folder(tmp / "outputs")).ok


def audit_run(argv: list[str]) -> int:
    """The editor's part of the offline audit (see the module text). Exit 0 when every step ran."""
    import json

    from PySide6.QtCore import QObject, QTimer, QUrl, Slot
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QApplication

    from harness_design_studio.gui.app import make_settings
    from harness_design_studio.gui.drc_process import _shared, run_check

    project, report = Path(argv[2]), Path(argv[3])
    idle_s = float(argv[4]) if len(argv) > 4 else 20.0
    opened: list[str] = []
    dismissed: list[str] = []
    steps: dict[str, bool] = {}

    class Recorder(QObject):
        """Stands in for the system's URL opener: records, starts nothing."""

        @Slot(QUrl)
        def record(self, url: QUrl) -> None:
            opened.append(url.toString())

    recorder = Recorder()
    for scheme in ("file", "http", "https", "ftp", "mailto"):
        QDesktopServices.setUrlHandler(scheme, recorder, "record")
    settings = make_settings()
    win = create_window(settings)  # first start when the settings file is new, as for a person
    win.open_url = lambda url: bool(opened.append(url.toString())) or True  # type: ignore[method-assign]
    app = QApplication.instance()

    def dismiss() -> None:
        """A question (the role at first start, a message) is answered with its default: no one
        is there to click."""
        modal = QApplication.activeModalWidget()
        if modal is not None:
            dismissed.append(modal.windowTitle() or type(modal).__name__)
            modal.close()

    closer = QTimer()
    closer.timeout.connect(dismiss)
    closer.start(200)
    win.show()
    QApplication.processEvents()
    steps["open the project"] = bool(win.open_project(project))
    QApplication.processEvents()
    win.act_guide.trigger()  # F1: the guide, handed to the system's opener (here the recorder)
    guide = [u for u in opened if u.endswith("index.html")]
    steps["F1 asks to open the local guide only"] = bool(guide) and all(
        u.startswith("file://") for u in opened
    )
    found = run_check(win.ctl.project)
    steps["rule check in the helper process"] = _shared.alive and isinstance(found, list)
    steps["a folder that does not exist is refused"] = not win.open_project(
        project.parent / "no-such-project-folder"
    )
    QTimer.singleShot(int(idle_s * 1000), app.quit)  # type: ignore[union-attr]
    app.exec()  # type: ignore[union-attr]
    maps = Path("/proc/self/maps")
    libraries = (
        sorted({line.split()[-1] for line in maps.read_text().splitlines() if ".so" in line})
        if maps.is_file()
        else []
    )
    if sys.platform == "win32":
        libraries = _windows_modules()
    network_modules = sorted(
        m
        for m in sys.modules
        if m.split(".")[0] in ("socket", "_socket", "ssl", "_ssl", "http", "urllib", "asyncio")
        or m.endswith(("QtNetwork", "QtWebEngineCore"))
    )
    win.ctl.release()
    win.close()
    _shared.close()
    settings.sync()
    doc = {
        "steps": steps,
        "urls_opened": opened,
        "dialogs_dismissed": dismissed,
        "settings_file": settings.fileName(),
        "libraries_mapped": libraries,
        "python_network_modules": network_modules,
        "idle_seconds": idle_s,
    }
    report.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if all(steps.values()) else 1


def _windows_modules() -> list[str]:
    """The DLLs loaded into this process (Windows), by the system's own list."""
    import ctypes
    from ctypes import wintypes

    psapi = ctypes.WinDLL("psapi")  # type: ignore[attr-defined]
    kernel = ctypes.WinDLL("kernel32")  # type: ignore[attr-defined]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.EnumProcessModules.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]  # fmt: skip
    psapi.GetModuleFileNameExW.argtypes = [
        wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD,
    ]  # fmt: skip
    handle = kernel.GetCurrentProcess()
    modules = (wintypes.HMODULE * 4096)()
    needed = wintypes.DWORD()
    if not psapi.EnumProcessModules(handle, modules, ctypes.sizeof(modules), ctypes.byref(needed)):
        return []
    names = []
    buf = ctypes.create_unicode_buffer(1024)
    for i in range(needed.value // ctypes.sizeof(wintypes.HMODULE)):
        if psapi.GetModuleFileNameExW(handle, modules[i], buf, 1024):
            names.append(buf.value)
    return sorted(names)


if __name__ == "__main__":
    if _asked("--audit-run", sys.argv) and len(sys.argv) in (4, 5):
        raise SystemExit(audit_run(sys.argv))
    if _asked("--selftest", sys.argv):
        raise SystemExit(selftest(_selftest_out(sys.argv)))
    raise SystemExit(main())
