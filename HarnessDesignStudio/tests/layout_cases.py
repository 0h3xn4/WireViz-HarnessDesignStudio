"""Every dialog and window of the program, built the way the program builds it, for the layout
sweep (`tests/test_ui_layout_sweep.py`).

A `Case` has a name (the file of the class is in the comment), a `make(ctx)` that returns the
widget, and the states it is looked at in. `CASES` is the list; a dialog that is added to the
program is added here, and a test of the sweep fails when one is missing (it compares with the
classes the GUI package defines).
"""

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QWidget

from harness_design_studio.core import checks, edit
from harness_design_studio.core.issues import Issue
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.theme import ThemeManager
from harness_design_studio.resources import examples_path

LONG = "Star tracker electronics unit, redundant"  # 40 characters
VERY_LONG_ID = "STARTRACKER-ELECTRONICS-UNIT-A-REDUNDANT"


@dataclass
class Ctx:
    """What a case can use: the theme, a flatsat project (with 40-character names) behind a
    controller, and a folder to write into."""

    theme: ThemeManager
    tmp: Path
    ctl: EditorController
    settings: QSettings
    keep: list[Any] = field(default_factory=list)  # things that must outlive the widget

    @property
    def project(self):  # type: ignore[no-untyped-def]
        return self.ctl.project


def make_ctx(theme: ThemeManager, tmp: Path) -> Ctx:
    root = examples_path()
    assert root is not None
    folder = tmp / "flatsat"
    shutil.copytree(root / "projects" / "flatsat", folder)
    shutil.copytree(
        Path(__file__).resolve().parents[1] / "docs" / "examples" / "extensions",
        folder / "extensions",
        ignore=shutil.ignore_patterns("README.md"),
    )
    ctl = EditorController(drc_delay_ms=600_000)
    ctl.open_path(folder)
    ctl.today = lambda: "2026-03-01"  # type: ignore[method-assign]
    p = ctl.project
    for i, (uid, u) in enumerate(list(p.units.items())):
        if i % 3 == 0:
            p.units[uid] = u.model_copy(update={"name": f"{LONG} {uid}"[:60]})
    settings = QSettings(str(tmp / "ui.ini"), QSettings.Format.IniFormat)
    return Ctx(theme, tmp, ctl, settings)


@dataclass(frozen=True)
class Case:
    name: str
    make: Callable[[Ctx], QWidget]
    classes: tuple[str, ...] = ()  # the GUI classes this case covers (the completeness test)


def _first_wire_ids(ctx: Ctx, n: int = 3) -> tuple[str, list[str]]:
    hid = "W001"
    return hid, [w.id for w in ctx.project.harnesses[hid].wires][:n]


def _connector_with_pins(ctx: Ctx) -> tuple[str, list[str]]:
    c = next(c for c in ctx.project.connectors.values() if c.role == "box" and len(c.pins) >= 4)
    return c.id, [p.id for p in c.pins][:3]


def _finding(severity: str = "warning") -> checks.Finding:
    return checks.Finding(
        id="x.1",
        rule="wire-current",
        severity=severity,  # type: ignore[arg-type]
        object_id="W001-0001",
        title=LONG,
        why="The current is more than the wire can carry. " * 3,
        can_waive=True,
        can_deviate=severity == "error",
    )


def _cases() -> list[Case]:
    from harness_design_studio.core.vcs import release as _release  # noqa: F401
    from harness_design_studio.gui import (
        assumptions_dialog,
        config_dialog,
        devices_dialogs,
        dialogs,
        export_dialog,
        extensions_dialog,
        harness_edit_dialogs,
        journal_dialog,
        library_window,
        link_dialog,
        new_project_dialog,
        role_dialog,
    )
    from harness_design_studio.gui.main_window import MainWindow  # noqa: F401

    def devs(ctx: Ctx):  # type: ignore[no-untyped-def]
        return ctx.project

    out: list[Case] = []

    def add(name: str, make: Callable[[Ctx], QWidget], *classes: str) -> None:
        out.append(Case(name, make, classes))

    # ---- the Devices tab dialogs (gui/devices_dialogs.py)
    add(
        "Add device",
        lambda c: devices_dialogs.NewDeviceDialog(None, c.theme, c.project),
        "NewDeviceDialog",
    )
    add(
        "Add device (Quick mode)",
        lambda c: devices_dialogs.QuickDeviceDialog(None, c.theme, c.project),
        "QuickDeviceDialog",
    )
    add(
        "New connector part",
        lambda c: devices_dialogs.NewPartDialog(None, c.theme, c.project),
        "NewPartDialog",
    )
    add(
        "New interface type",
        lambda c: devices_dialogs.NewTypeDialog(None, c.theme, c.project),
        "NewTypeDialog",
    )

    def fill(c: Ctx) -> QWidget:
        cid, pins = _connector_with_pins(c)
        return devices_dialogs.FillDialog(None, c.theme, c.project, cid, pins)

    def contact(c: Ctx) -> QWidget:
        cid, pins = _connector_with_pins(c)
        return devices_dialogs.ContactDialog(None, c.theme, c.project, cid, pins)

    def assign(c: Ctx) -> QWidget:
        cid, pins = _connector_with_pins(c)
        return devices_dialogs.AssignDialog(None, c.theme, c.project, cid, pins)

    add("Signals on pins", fill, "FillDialog")
    add("Contact of pins", contact, "ContactDialog")
    add("Interface on pins", assign, "AssignDialog")

    def lib_dialog(c: Ctx) -> QWidget:
        return devices_dialogs.LibraryDialog(None, c.theme, c.project, _library_data(c))

    add("Add from library file", lib_dialog, "LibraryDialog")

    # ---- the connection windows (gui/link_dialog.py)
    add(
        "Link connectors",
        lambda c: link_dialog.LinkDialog(None, c.theme, c.project, a_unit="RW1", b_unit="OBC"),
        "LinkDialog",
    )
    add(
        "Create harness",
        lambda c: link_dialog.CreateHarnessDialog(None, c.theme, LONG + ". " + LONG + ". " + LONG),
        "CreateHarnessDialog",
    )
    add(
        "Add a connector",
        lambda c: link_dialog.AddConnectorDialog(None, c.theme, c.project, "OBC"),
        "AddConnectorDialog",
    )
    add(
        "Paste a pairing",
        lambda c: link_dialog.PastePairingDialog(None, c.theme, "OBC-J01", "RW1-J02"),
        "PastePairingDialog",
    )

    # ---- gui/cable_end_dialog.py (M4c: the keyboard way to a loose cable end)
    add("Plug a loose end in", _cable_end_dialog, "CableEndDialog")
    add("Plug a loose end in (nothing to choose)", partial(_cable_end_dialog, empty=True))

    # ---- gui/dialogs.py
    add(
        "Confirm (delete)",
        lambda c: dialogs.ConfirmDialog(
            None,
            "Delete harness W001?",
            f"<p>{LONG}</p><p>It has 12 wires and 3 connectors. " * 2
            + "</p><ul><li>one</li><li>two</li></ul>",
            "Delete",
        ),
        "ConfirmDialog",
    )
    add(
        "Upgrade an older project format",
        lambda c: dialogs.UpgradeDialog(None, 1, 2),
        "UpgradeDialog",
    )
    add(
        "Waive a warning", lambda c: dialogs.WaiverDialog(None, _finding("warning")), "WaiverDialog"
    )
    add(
        "Accept a deviation",
        lambda c: dialogs.WaiverDialog(None, _finding("error")),
        "WaiverDialog",
    )
    add(
        "New interface", lambda c: dialogs.NewInterfaceDialog(None, c.project), "NewInterfaceDialog"
    )
    add("Wire colours", lambda c: dialogs.WireColoursDialog(None, c.project), "WireColoursDialog")
    add(
        "Import interfaces (table)",
        lambda c: dialogs.ImportDialog(None, c.project, c.theme, lambda: None),
        "ImportDialog",
    )
    add("Glossary", lambda c: dialogs.GlossaryDialog(None), "GlossaryDialog")
    add(
        "Recovery issues",
        lambda c: dialogs.IssuesDialog(
            None,
            [
                Issue("error", "bad-file", LONG * 3, "logical/units/a.json"),
                Issue("warning", "x", "Something is odd"),
            ],
            True,
        ),
        "IssuesDialog",
    )
    add(
        "History log",
        lambda c: dialogs.HistoryDialog(
            None,
            "Log of W001",
            [
                ["id", "h", "rev", "action", "by", "when", "comment"],
                ["1", "W001", "1", "released", "Ada", "2026-03-01", LONG],
            ],
        ),
        "HistoryDialog",
    )
    add("Generate preview", _generate_preview, "GeneratePreviewDialog")
    add("Release (change dialog)", _release_dialog, "ChangeDialog")
    add("Revise (change dialog)", _revise_dialog, "ChangeDialog")
    add(
        "Review (no comment)",
        lambda c: dialogs.ChangeDialog(
            None, "Submit W001 for review", by="Ada", blockers=[], ask_comment=False
        ),
        "ChangeDialog",
    )
    add("Changes (diff)", _diff_dialog, "DiffDialog")
    add("Revisions (history)", _revisions_dialog, "HistoryDialog")

    # ---- other dialogs
    add(
        "Assumptions",
        lambda c: assumptions_dialog.AssumptionsDialog(None, c.theme, c.project),
        "AssumptionsDialog",
    )
    add("Explain (how it was calculated)", _explain, "ExplainDialog")
    add(
        "Engineering values",
        lambda c: config_dialog.ConfigValueDialog(c.ctl, c.theme),
        "ConfigValueDialog",
        "FieldRow",
    )
    add(
        "Export",
        lambda c: export_dialog.ExportDialog(
            c.ctl, c.theme, settings=c.settings, ask_folder=lambda t: str(c.tmp / "out")
        ),
        "ExportDialog",
        "ExportResultPanel",
    )
    add(
        "Extensions",
        lambda c: extensions_dialog.ExtensionsDialog(None, c.theme, c.ctl),
        "ExtensionsDialog",
    )
    add("Trust a plug-in", _trust, "TrustDialog")
    add(
        "Edit all wires",
        lambda c: harness_edit_dialogs.BulkWireDialog(
            None, c.theme, c.project, *_first_wire_ids(c)
        ),
        "BulkWireDialog",
    )
    add("Change group", _group, "ChangeGroupDialog")
    add(
        "History window (journal)",
        lambda c: journal_dialog.JournalDialog(
            None, c.theme, c.project, start_journal=lambda: True
        ),
        "JournalDialog",
    )
    add("Library conflict", _conflict, "LibraryConflictDialog")
    add(
        "Save to library",
        lambda c: library_window.SaveToLibraryDialog(None, c.theme, c.project, ["OBC"], str(c.tmp)),
        "SaveToLibraryDialog",
    )
    add(
        "New project",
        lambda c: new_project_dialog.NewProjectDialog(c.theme, None, start_folder=c.tmp),
        "NewProjectDialog",
    )
    add("Who are you working as", lambda c: role_dialog.RoleDialog(None, c.theme), "RoleDialog")
    add("Import wizard: file", lambda c: _wizard(c, "interfaces"), "ImportWizard", "FilePage")
    add("Import wizard: pinout", lambda c: _wizard(c, "pinout"), "ImportWizard", "FilePage")
    add("Import wizard: parts", lambda c: _wizard(c, "parts"), "ImportWizard", "FilePage")
    add(
        "Library window",
        lambda c: library_window.LibraryWindow(c.ctl, c.theme, c.settings),
        "LibraryWindow",
    )
    add("Command palette", _palette, "CommandPalette")
    add("Ask for a name (input dialog)", _input_dialog)
    add("Ask a question (message box)", _message_box)
    return out


def _library_data(c: Ctx) -> dict[str, Any]:
    """A device library file of four devices with long names (the format `read_library` takes)."""
    from harness_design_studio.core import device_library

    unit_ids = list(c.project.units)[:4]
    data = device_library.export_devices(c.project, unit_ids)
    return data  # type: ignore[no-any-return]


def _generate_preview(c: Ctx) -> QWidget:
    from harness_design_studio.core.generate.engine import plan_generation
    from harness_design_studio.gui import dialogs

    plan = plan_generation(c.project)
    return dialogs.GeneratePreviewDialog(None, plan)


def _cable_end_dialog(c: Ctx, empty: bool = False) -> QWidget:
    from harness_design_studio.gui import strings
    from harness_design_studio.gui.cable_end_dialog import CableEndDialog

    ends = [(f"{VERY_LONG_ID}-P{k} ({LONG}) of W00{k}", f"W00{k}-P2") for k in range(1, 4)]
    ports = [
        (f"{uid} {LONG} ({VERY_LONG_ID}-J01)", f"{uid}-J01") for uid in list(c.project.units)[:6]
    ]
    return CableEndDialog(
        None,
        c.theme,
        strings.LE_PLUG_TITLE,
        strings.LE_PLUG_INTRO,
        strings.LE_PLUG_OK,
        ends=[] if empty else ends,
        ports=ports,
    )


def _release_dialog(c: Ctx) -> QWidget:
    from harness_design_studio.gui import dialogs

    return dialogs.ChangeDialog(
        None,
        "Release W001",
        by="Ada",
        blockers=["Export the outputs first.", LONG * 2],
        ask_checker=True,
        placeholders=["gauge of W001-0001", "length of W001-0002"],
        unapproved_parts=["EX-MICROD-9-F", "EX-RJ45-F"],
        loose_ends=[f"{VERY_LONG_ID}-P{k}" for k in range(1, 8)],
        rule_note="Rule: " + LONG * 2,
    )


def _revise_dialog(c: Ctx) -> QWidget:
    from harness_design_studio.gui import dialogs

    return dialogs.ChangeDialog(
        None,
        "New revision of W001",
        by="Ada",
        blockers=[],
        explain="A new revision unlocks the harness for editing. " * 3,
    )


def _diff_dialog(c: Ctx) -> QWidget:
    from harness_design_studio.core.vcs.diff import Diff
    from harness_design_studio.gui import dialogs

    return dialogs.DiffDialog(None, "Changes since release", Diff(), ["A", "B"], "A")


def _revisions_dialog(c: Ctx) -> QWidget:
    from harness_design_studio.gui import dialogs

    header = ["id", "harness", "rev", "action", "by", "when", "comment"]
    rows = [header] + [
        [f"{i}", "W001", f"{i}", "released", "Ada", "2026-03-01", LONG] for i in range(5)
    ]
    return dialogs.HistoryDialog(None, "Revisions of W001", rows)


def _explain(c: Ctx) -> QWidget:
    from harness_design_studio.core.derive import explain_finding
    from harness_design_studio.gui import explain_dialog

    wire = c.project.harnesses["W001"].wires[0].id
    found = explain_finding(c.project, "current-over-wire", str(wire))
    return explain_dialog.ExplainDialog(None, c.theme, found)


def _trust(c: Ctx) -> QWidget:
    from harness_design_studio.gui import extensions_dialog
    from harness_design_studio.gui.extensions_dialog import source_text

    ext = c.project.extensions
    assert ext is not None and ext.plugins
    info = ext.plugins[0]
    return extensions_dialog.TrustDialog(None, c.theme, info, source_text(ext.root, info))


def _group(c: Ctx) -> QWidget:
    from harness_design_studio.gui import harness_edit_dialogs

    gid = next(s.id for h in c.project.harnesses.values() for s in h.shields)
    return harness_edit_dialogs.ChangeGroupDialog(None, c.theme, c.project, gid)


def _conflict(c: Ctx) -> QWidget:
    from harness_design_studio.core.device_library import DeviceConflict, LibraryConflict
    from harness_design_studio.gui import library_window

    found = [DeviceConflict("RW1", 2, 1, "RW1-2"), DeviceConflict(VERY_LONG_ID, 0, 3, "X-2")]
    return library_window.LibraryConflictDialog(None, LibraryConflict("RW1.json", found))


def _wizard(c: Ctx, kind: str) -> QWidget:
    from harness_design_studio.gui import import_wizard

    return import_wizard.ImportWizard(c.ctl, c.theme, pick_file=lambda k, f: None, kind=kind)


def _input_dialog(c: Ctx) -> QWidget:
    """What `MainWindow._ask_text` shows (Qt's own input dialog, in the program's style)."""
    from PySide6.QtWidgets import QInputDialog

    box = QInputDialog(None)
    box.setWindowTitle("New harness")
    box.setLabelText("Name of the new harness (" + LONG + "):")
    box.setTextValue("")
    return box


def _message_box(c: Ctx) -> QWidget:
    """What `MainWindow._ask_choice` shows: a question and three buttons."""
    from PySide6.QtWidgets import QMessageBox

    from harness_design_studio.gui import strings

    box = QMessageBox(None)
    box.setWindowTitle(strings.UNSAVED_TITLE)
    box.setText(strings.UNSAVED_BODY + " " + LONG)
    for text in (strings.SAVE, strings.DISCARD, strings.CANCEL):
        box.addButton(text, QMessageBox.ButtonRole.ActionRole)
    return box


def _palette(c: Ctx) -> QWidget:
    from PySide6.QtWidgets import QMainWindow

    from harness_design_studio.gui.command_palette import CommandPalette, PaletteEntry

    host = QMainWindow()
    host.resize(900, 600)
    c.keep.append(host)
    host.show()
    entries = [PaletteEntry(f"{LONG} {i}", lambda: None, "Ctrl+K") for i in range(30)]
    pal = CommandPalette(host, entries)
    pal.open()
    return pal


# ---- the main window: every area, tab and panel, in each role and in Quick mode ----------------------


def make_window(ctx: Ctx, role: str = "electrical", quick: bool = False):  # type: ignore[no-untyped-def]
    """The main window with the flatsat project open (a second copy of the folder: the first is
    open in `ctx.ctl`)."""
    from harness_design_studio.gui.main_window import MainWindow

    folder = ctx.tmp / f"flatsat-window-{role}-{quick}"
    shutil.copytree(ctx.tmp / "flatsat", folder, ignore=shutil.ignore_patterns(".lock*", "*.lock"))
    settings = QSettings(str(ctx.tmp / f"window-{role}-{quick}.ini"), QSettings.Format.IniFormat)
    settings.setValue("ui/role", role)
    settings.setValue("ui/quick", quick)
    settings.setValue("ui/scale", round(ctx.theme.scale * 100))  # (the window applies its own)
    settings.setValue("ui/theme", ctx.theme.name)
    settings.setValue("tour/done", True)
    settings.sync()
    win = MainWindow(settings, ctx.theme, first_run=False)
    win.ask_choice = lambda title, text, buttons: 1  # type: ignore[method-assign]
    win.run_dialog = lambda dlg: 0  # type: ignore[method-assign]  # (a question would wait for a click)
    win.open_project(folder)
    return win


def window_views(win) -> list[tuple[str, Callable[[], None]]]:  # type: ignore[no-untyped-def]
    """The places of the window the person can look at: each is a name and what brings it up."""
    from harness_design_studio.gui import areas
    from harness_design_studio.gui.inspector import TABS

    views: list[tuple[str, Callable[[], None]]] = []

    def view(label: str, action: Callable[[], object]) -> None:
        def bring_up() -> None:
            action()

        views.append((label, bring_up))

    for a in areas.AREAS:
        if a.tabs:
            for tab in a.tabs:
                view(f"{a.key}/{tab}", partial(win._show_area, a.key, tab=tab))
        else:
            view(a.key, partial(win._show_area, a.key))
    for inspector_tab in TABS:
        view(f"inspector/{inspector_tab}", partial(win.inspector.show_tab, inspector_tab))
    from harness_design_studio.gui.settings_page import SECTIONS

    def settings_section(key: str) -> None:
        win._show_area("settings")
        win.settings_page.show_section(key)

    for key, _title in SECTIONS:
        view(f"settings/{key}", partial(settings_section, key))
    return views


CASES: list[Case] = []


def cases() -> list[Case]:
    if not CASES:
        CASES.extend(_cases())
    return CASES


__all__ = ["Case", "Ctx", "cases", "edit", "make_ctx"]
