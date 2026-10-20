# mypy: allow-untyped-calls, no-warn-unused-ignores, disable-error-code=misc
"""Screenshot harness of the whole editor for the UI overhaul (docs/ui/UI_OVERHAUL.md).

Opens every window, tab, dock tab, menu and dialog of the real Qt editor (offscreen) on the flatsat
example, in the light and the dark theme, and saves PNGs. One shot that fails is reported at the end
and does not stop the others. Usage:

    python -m tools.ui_screenshots [OUTPUT_FOLDER]      (default: docs/ui/screenshots/before)
    python -m tools.ui_screenshots OUT --theme dark     (one theme only)
    python -m tools.ui_screenshots OUT --part extra     (only the empty and stress pictures)
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QSettings
from PySide6.QtWidgets import QApplication, QDialog, QMenu

from harness_design_studio.gui.main_window import MainWindow
from harness_design_studio.gui.theme import ThemeManager
from harness_design_studio.resources import examples_path

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "docs" / "ui" / "screenshots" / "before"
WORK = Path(tempfile.gettempdir()) / "harness-ui-shots"
FAILED: list[str] = []


def _wait(ms: int) -> None:
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.02)


def _settle(win: MainWindow, ms: int = 400) -> None:
    """Let timers and background jobs finish (the rule check, the status hash, the toasts)."""
    _wait(ms)
    waited = 0
    while (win.ctl.drc_busy() or not win.ctl.drc_current) and waited < 30000:
        _wait(200)
        waited += 200
    waited = 0
    while win.toasts.isVisible() and waited < 8000:
        _wait(200)
        waited += 200
    _wait(ms)


class Shots:
    def __init__(self, out: Path, theme: str) -> None:
        self.out = out
        self.theme = theme
        self.count = 0
        out.mkdir(parents=True, exist_ok=True)

    def grab(self, name: str, widget: Any) -> None:
        QApplication.processEvents()
        self.count += 1
        path = self.out / f"{name}_{self.theme}.png"
        widget.grab().save(str(path))
        print(path.name)

    def attempt(self, name: str, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception:  # one broken shot must not stop the rest
            FAILED.append(f"{name}_{self.theme}: {traceback.format_exc(limit=3).strip()}")
            print("FAILED", name)


def _fresh(tmp: Path, theme: str, example: str = "flatsat") -> MainWindow:
    folder = tmp / theme
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    root = examples_path()
    assert root is not None
    shutil.copytree(root / "projects" / example, folder / example)
    settings = QSettings(str(folder / "ui.ini"), QSettings.Format.IniFormat)
    win = MainWindow(settings, ThemeManager(), first_run=False)
    win.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
    win.resize(1440, 900)
    win.show()
    if theme == "dark":
        win.set_theme_mode("dark")
    else:
        win.set_theme_mode("light")
    assert win.open_project(folder / example)
    win.view.fit()
    _settle(win)
    return win


def _dialog(win: MainWindow, shots: Shots, name: str, open_it: Callable[[], None]) -> None:
    """Run a flow whose dialog goes through run_dialog: grab it, then close it."""

    def grab_it(d: QDialog) -> int:
        d.show()
        d.adjustSize()
        _wait(300)
        shots.grab(name, d)
        return 0

    old = win.run_dialog
    win.run_dialog = grab_it  # type: ignore[assignment]
    try:
        open_it()
    finally:
        win.run_dialog = old  # type: ignore[assignment]


def _menus(win: MainWindow, shots: Shots) -> None:
    for action in win.menuBar().actions():
        menu = action.menu()
        if not isinstance(menu, QMenu):
            continue
        title = action.text().replace("&", "").lower().replace(" ", "-")
        menu.popup(win.mapToGlobal(QPoint(40, 30)))
        _wait(200)
        shots.grab(f"menu-{title}", menu)
        menu.close()


def run_theme(theme: str, out: Path, parts: set[str]) -> int:
    shots = Shots(out, theme)
    tmp = WORK / theme
    if "main" in parts:
        _main_part(theme, shots, tmp)
    if "extra" in parts:
        _extra_part(theme, shots, tmp)
    print(f"{theme}: {shots.count} pictures")
    return shots.count


def _main_part(theme: str, shots: Shots, tmp: Path) -> None:
    win = _fresh(WORK, theme)
    a = shots.attempt

    # --- the shell -------------------------------------------------------------------------
    win.go_to("diagram")
    win.ctl.select("unit", "PDU2")
    _settle(win)
    a("shell-diagram-selected-1440x900", lambda: shots.grab("01-diagram-selected-1440x900", win))
    win.ctl.set_mode("expert")
    _settle(win)
    a("diagram-expert", lambda: shots.grab("02-diagram-expert", win))
    win.ctl.set_mode("guided")
    win.view.fit()

    # --- main tabs -------------------------------------------------------------------------
    for number, name in (
        (3, "harness"),
        (4, "lists"),
        (5, "checks"),
        (6, "releases"),
        (7, "devices"),
    ):
        if name == "harness":
            win.go_to("harness")
            win.harness_view.select_harness("W001")
        else:
            win.go_to(name)
        _settle(win)
        a(f"tab-{name}", lambda n=number, nm=name: shots.grab(f"{n:02d}-tab-{nm}", win))
    win.go_to("diagram")

    # --- left and right docks -------------------------------------------------------------
    win.show_interfaces()
    _settle(win)
    a("left-interfaces", lambda: shots.grab("08-left-interfaces-tab", win))
    win.show_units()
    _settle(win)
    a("left-units", lambda: shots.grab("08b-left-units-tab", win))
    win.left_tabs.setCurrentIndex(win.left_tabs.index_of("tree"))
    for number, tab in ((9, "inspector"), (10, "why"), (11, "problems")):
        win.dock_right.show()
        win.inspector.show_tab(tab)
        _settle(win, 200)
        a(f"right-{tab}", lambda n=number, t=tab: shots.grab(f"{n:02d}-right-{t}-tab", win))
    win.inspector.show_tab("inspector")

    # --- the areas of the shell (UI overhaul M2) ------------------------------------------------
    for number, key in ((14, "home"), (15, "settings")):
        win.set_area(key)
        _settle(win, 200)
        a(f"area-{key}", lambda n=number, k=key: shots.grab(f"{n}-area-{k}", win))
    for label, section in (("15b", "shortcuts"), ("15c", "about"), ("15d", "licences")):
        win.settings_page.show_section(section)
        _settle(win, 200)
        a(f"settings-{section}", lambda n=label, s=section: shots.grab(f"{n}-settings-{s}", win))
    win.settings_page.show_section("appearance")
    win.set_area("model")
    win.toggle_problems()
    _settle(win, 600)
    a("problems-panel", lambda: shots.grab("16-problems-panel", win))
    win.toggle_problems()
    win.rail.toggle.click()
    _settle(win, 200)
    a("rail-collapsed", lambda: shots.grab("17-rail-collapsed", win))
    win.rail.toggle.click()

    # --- menus, command palette, tour ------------------------------------------------------
    a("menus", lambda: _menus(win, shots))

    def palette() -> None:
        win.open_commands()
        assert win.command_palette is not None
        win.command_palette.input.setText("gen")
        shots.grab("12-command-palette", win)
        win.command_palette.dismiss()

    a("palette", palette)

    def tour() -> None:
        win.tour.start()
        shots.grab("13-first-run-tour", win)
        win.tour.stop()

    a("tour", tour)

    # --- dialogs ---------------------------------------------------------------------------
    a(
        "dlg-new-interface",
        lambda: _dialog(win, shots, "22-dlg-new-interface", win.new_interface_flow),
    )
    a("dlg-wire-colours", lambda: _dialog(win, shots, "23-dlg-wire-colours", win.wire_colours_flow))
    a("dlg-glossary", lambda: _dialog(win, shots, "24-dlg-glossary", win.glossary_flow))
    a("dlg-issues", lambda: _dialog(win, shots, "25-dlg-known-issues", win.issues_flow))
    a(
        "dlg-new-project",
        lambda: _dialog(win, shots, "26-dlg-new-project", win.new_from_example_flow),
    )
    a(
        "dlg-import-interfaces",
        lambda: _dialog(win, shots, "27-dlg-import-interfaces", win.import_flow),
    )

    def values() -> None:
        win.go_to("checks")
        dialog = win.checks_panel.open_config()
        _wait(300)
        shots.grab("28-dlg-engineering-values", dialog)
        dialog.close()
        win.go_to("diagram")

    a("dlg-values", values)

    def export() -> None:
        def show(d: QDialog) -> int:
            d.show()
            _wait(300)
            shots.grab("29-dlg-export-before", d)
            d.export_btn.click()  # type: ignore[attr-defined]
            waited = 0
            while d.export_result is None and waited < 30000:  # type: ignore[attr-defined]
                _wait(200)
                waited += 200
            _wait(500)
            shots.grab("30-dlg-export-after", d)
            return 0

        old = win.run_dialog
        win.run_dialog = show  # type: ignore[assignment]
        try:
            win.export_dialog_flow()
        finally:
            win.run_dialog = old  # type: ignore[assignment]

    a("dlg-export", export)

    def import_wizard() -> None:
        from harness_design_studio.core import templates

        templates.copy_import_templates(tmp / "my-templates")
        parts = tmp / "my-templates" / "approved-parts.csv"
        win.ask_import_file = lambda kind, filters: str(parts)

        def wizard(d: QDialog) -> int:
            d.show()
            d.resize(900, 640)
            d.load_file(str(parts))  # type: ignore[attr-defined]
            shots.grab("31-dlg-import-wizard-file", d)
            d.next()  # type: ignore[attr-defined]
            _wait(200)
            shots.grab("32-dlg-import-wizard-columns", d)
            return 0

        old = win.run_dialog
        win.run_dialog = wizard  # type: ignore[assignment]
        try:
            win.import_wizard_flow("parts")
        finally:
            win.run_dialog = old  # type: ignore[assignment]

    a("dlg-import-wizard", import_wizard)

    a(
        "dlg-release",
        lambda: _dialog(win, shots, "33-dlg-release", lambda: win.change_flow("release", "W001")),
    )

    def after_release() -> None:
        from harness_design_studio.core.outputs.build import write_outputs
        from harness_design_studio.core.vcs.release import plan_release

        folder = win.ctl.outputs_folder()
        assert folder is not None
        write_outputs(win.ctl.project, folder)
        plan = plan_release(
            win.ctl.project,
            "W001",
            by="A. Engineer",
            checker="B. Reviewer",
            comment="First release for the review",
            when="2026-03-01",
            outputs_folder=folder,
            accept_placeholders="Example values for the documentation",
            accept_unapproved_parts="Example parts for the documentation",
        )
        assert plan.ok and win.ctl.apply_change(plan, "W001 released")
        write_outputs(win.ctl.project, folder)
        win._outputs_epoch += 1
        _settle(win)
        win.ctl.select("unit", "PDU2")
        win.view.fit()
        shots.grab("34-released-diagram", win)
        win.go_to("harness")
        win.harness_view.select_harness("W001")
        _settle(win)
        shots.grab("35-released-harness", win)
        win.go_to("releases")
        win.releases_panel.select_harness("W001")
        win.releases_panel.compare("W001", "A")
        _settle(win)
        shots.grab("36-releases-compare", win)
        win.go_to("diagram")
        _dialog(win, shots, "37-dlg-new-revision", lambda: win.change_flow("revise", "W001"))
        _dialog(win, shots, "38-dlg-changes", lambda: win._changes_flow("W001"))

    a("released", after_release)

    # --- sizes and scale ------------------------------------------------------------------
    for width, height in ((1280, 720), (1920, 1080)):
        win.resize(width, height)
        win.go_to("diagram")
        win.view.fit()
        _settle(win, 300)
        a(f"size-{width}", lambda w=width, h=height: shots.grab(f"40-diagram-{w}x{h}", win))
    win.resize(1150, 400)
    _settle(win, 300)
    a("size-small", lambda: shots.grab("41-diagram-1150x400", win))
    win.resize(1440, 900)
    win.scale_actions[150].trigger()
    _settle(win, 300)
    a("scale-150", lambda: shots.grab("42-scale-150", win))
    win.scale_actions[100].trigger()
    win.hide()  # (close() here crashed the offscreen platform once the layout had been squeezed)


def _extra_part(theme: str, shots: Shots, tmp: Path) -> None:
    """An empty project (the first start) and a stress project (100 units, 800 links)."""
    a = shots.attempt

    def empty() -> None:
        folder = tmp / "empty"
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        settings = QSettings(str(folder / "ui.ini"), QSettings.Format.IniFormat)
        w = MainWindow(settings, ThemeManager(), first_run=False)
        w.resize(1440, 900)
        w.show()
        w.set_theme_mode(theme)
        w.ctl._install(w.ctl.project, None, None)
        _settle(w, 300)
        shots.grab("50-first-start", w)
        w.close()

    a("empty", empty)

    def stress() -> None:
        from tools.bench_stress import build

        settings = QSettings(str(tmp / "stress.ini"), QSettings.Format.IniFormat)
        w = MainWindow(settings, ThemeManager(), first_run=False)
        w.resize(1440, 900)
        w.show()
        w.set_theme_mode(theme)
        w.ctl._install(build(), None, None)
        w.view.fit()
        _settle(w, 600)
        shots.grab("51-stress-100-units", w)
        w.close()

    if theme == "light":
        a("stress", stress)

    def fresh_design() -> None:
        """A design that was never generated: the generate preview and the delete impact (a unit
        of the flatsat is in a harness, so its delete is refused instead of explained)."""
        folder = tmp / "first-steps"
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        root = examples_path()
        assert root is not None
        shutil.copytree(root / "projects" / "first-steps", folder / "first-steps")
        settings = QSettings(str(folder / "ui.ini"), QSettings.Format.IniFormat)
        w = MainWindow(settings, ThemeManager(), first_run=False)
        w.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
        w.resize(1440, 900)
        w.show()
        w.set_theme_mode(theme)
        assert w.open_project(folder / "first-steps")
        w.view.fit()
        _settle(w)
        _dialog(w, shots, "20-dlg-generate-preview", w.generate_flow)
        w.ctl.select("unit", next(iter(w.ctl.project.units)))
        _dialog(w, shots, "21-dlg-delete-impact", w.delete_flow)
        w.hide()

    a("fresh-design", fresh_design)


def _one_process_each(out: Path, themes: list[str], parts: set[str]) -> int:
    """Every theme and part in a process of its own: a second window with its own theme manager in a
    process that has already shown the first one crashes the offscreen platform (a fault inside
    Qt's `setStyleSheet`, found in the final milestone), so the pictures are never made together."""
    import subprocess

    worst = 0
    for theme in themes:
        for part in sorted(parts):
            cmd = [
                sys.executable,
                "-m",
                "tools.ui_screenshots",
                str(out),
                "--theme",
                theme,
                "--part",
                part,
            ]
            worst = max(worst, subprocess.run(cmd, check=False).returncode)
    return worst


def main(argv: list[str]) -> int:
    out = DEFAULT_OUT
    themes = ["light", "dark"]
    parts = {"main", "extra"}
    args = list(argv)
    if "--part" in args:
        i = args.index("--part")
        parts = {args[i + 1]}
        del args[i : i + 2]
    if "--theme" in args:
        i = args.index("--theme")
        themes = [args[i + 1]]
        del args[i : i + 2]
    if args:
        out = Path(args[0])
    if len(themes) > 1 or len(parts) > 1:
        return _one_process_each(out, themes, parts)
    app = QApplication.instance() or QApplication(sys.argv)
    assert app is not None
    total = 0
    for theme in themes:
        total += run_theme(theme, out, parts)
    for line in FAILED:
        print("FAILED:", line)
    print(f"{total} pictures in {out}, {len(FAILED)} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
