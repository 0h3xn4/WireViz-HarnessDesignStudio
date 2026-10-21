"""PyInstaller entry point. `--selftest` exercises the real editor offscreen and exits (used by CI).

The self-test opens the sample, adds a unit, connects two units, saves to a temp folder, reloads it
and checks the result, so a broken package fails loudly instead of showing an empty window.

The Windows editor has no console, so it prints nothing: the exit code (0 = ok) is the result, and
`--selftest --selftest-out FILE` also writes the message ("selftest ok" or what failed) to FILE.
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
            except (OSError, subprocess.SubprocessError):
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


if __name__ == "__main__":
    if _asked("--selftest", sys.argv):
        raise SystemExit(selftest(_selftest_out(sys.argv)))
    raise SystemExit(main())
