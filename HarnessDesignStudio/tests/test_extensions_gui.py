# mypy: disable-error-code="no-untyped-def,no-untyped-call,union-attr,attr-defined"
"""S8: Help > Extensions, the question that names the code before it is loaded, and what the Checks
panel says about a rule that comes from an extension. Offscreen."""

import shutil
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QPlainTextEdit  # noqa: E402

from harness_design_studio.core import drc, templates  # noqa: E402
from harness_design_studio.core.extensions import manager, plugins, trust  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.checks_panel import ChecksPanel  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.extensions_dialog import (  # noqa: E402
    ExtensionsDialog,
    TrustDialog,
    ask_to_trust_enabled,
    source_text,
)
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.ext_helpers import ext_file, gauge_rule, write_extensions  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "examples" / "extensions"


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    """The flatsat example with the example extensions copied in (the plug-in is not trusted)."""
    target = tmp_path / "flatsat"
    templates.create_project(target, "flatsat")
    shutil.copytree(EXAMPLES, target / "extensions", ignore=shutil.ignore_patterns("README.md"))
    plugins.forget_loaded()
    manager._RUNTIMES.clear()
    return target


@pytest.fixture
def ctl(qtbot, folder):
    c = EditorController(drc_delay_ms=30)
    c.open_path(folder)
    c.run_drc_now()
    yield c
    c.wait_drc()
    c.release()


def plugin_row(dlg: ExtensionsDialog, name: str) -> int:
    for r in range(dlg.plugins.rowCount()):
        if dlg.plugins.item(r, 0).text() == name:
            return r
    raise AssertionError(name)


# ---- Help > Extensions ----------------------------------------------------------------------------------------


def test_help_extensions_is_in_the_help_menu_and_opens_the_page(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    opened: list[object] = []
    win.run_dialog = lambda d: opened.append(d)  # type: ignore[method-assign,assignment,return-value]
    win.act_extensions.trigger()
    assert len(opened) == 1 and type(opened[0]).__name__ == "ExtensionsDialog"
    help_menu = win.menuBar().actions()[-1].menu()
    assert help_menu is not None and win.act_extensions in help_menu.actions()
    assert win.act_extensions.text() == strings.A_EXTENSIONS


def test_the_page_of_a_project_without_extensions_says_so_and_stays_small(qtbot, tmp_path) -> None:
    c = EditorController(drc_delay_ms=30)
    c.open_path(_plain(tmp_path))
    dlg = ExtensionsDialog(None, ThemeManager(), c)
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.empty.isVisibleTo(dlg) and dlg.empty.text() == strings.EXT_NO_FOLDER
    assert (
        not dlg.files.isVisibleTo(dlg)
        and not dlg.plugins.isVisibleTo(dlg)
        and not dlg.builtin.isVisibleTo(dlg)
    )
    assert dlg.items.rowCount() > 100  # with no folder the only thing to list is what the tool has
    assert dlg.windowTitle() == strings.EXT_TITLE
    c.release()


def _plain(tmp_path: Path) -> Path:
    folder = tmp_path / "plain"
    templates.create_project(folder, "flatsat")
    return folder


def test_the_page_lists_files_plugins_items_and_problems(qtbot, ctl) -> None:
    dlg = ExtensionsDialog(None, ThemeManager(), ctl)
    qtbot.addWidget(dlg)
    dlg.show()
    QApplication.processEvents()
    files = {
        dlg.files.item(r, 0).text(): [dlg.files.item(r, c).text() for c in range(6)]
        for r in range(dlg.files.rowCount())
    }
    assert set(files) == {
        "extensions/minimum-wire-gauge-power.json",
        "extensions/power-wire-table.json",
    }
    row = files["extensions/minimum-wire-gauge-power.json"]
    assert (
        row[1:3] == ["minimum-wire-gauge-power", "1.0.0"]
        and len(row[3]) == 12
        and row[4:] == [strings.EXT_YES, "applied"]
    )
    r = plugin_row(dlg, "duplicate-signal-wires")
    cells = [dlg.plugins.item(r, c).text() for c in range(9)]
    assert (
        cells[1:3] == ["1.0.0", "rule"]
        and cells[3] == "extensions/plugins/duplicate-signal-wires.py"
    )
    assert cells[6:8] == [strings.EXT_YES, strings.EXT_NO] and cells[8].startswith("untrusted")
    kinds = {dlg.items.item(r, 0).text() for r in range(dlg.items.rowCount())}
    names = {dlg.items.item(r, 1).text() for r in range(dlg.items.rowCount())}
    assert (
        "x-min-gauge-power" in names and "duplicate-id" not in names
    )  # built-in items are behind a box
    assert kinds >= {"rule", "table", "lookup"}
    dlg.builtin.setChecked(True)
    names = {dlg.items.item(r, 1).text() for r in range(dlg.items.rowCount())}
    assert "duplicate-id" in names and "x-min-gauge-power" in names


def test_the_page_trusts_a_plugin_after_naming_the_code_and_takes_trust_back(
    qtbot, ctl, folder
) -> None:
    dlg = ExtensionsDialog(None, ThemeManager(), ctl)
    qtbot.addWidget(dlg)
    dlg.show()
    assert not dlg.trust_btn.isEnabled() and not dlg.revoke_btn.isEnabled()  # nothing selected
    dlg.plugins.selectRow(plugin_row(dlg, "duplicate-signal-wires"))
    assert dlg.trust_btn.isEnabled() and not dlg.revoke_btn.isEnabled()
    asked: list[TrustDialog] = []

    def decline(d: QDialog) -> int:
        assert isinstance(d, TrustDialog)
        asked.append(d)
        return QDialog.DialogCode.Rejected

    dlg.run_dialog = decline
    assert dlg.ask_trust() is False and trust.read() == []
    # the question names the code
    q = asked[0]
    texts = {k: v.text() for k, v in q.fields.items()}
    assert texts["Name"] == "duplicate-signal-wires" and texts["Version"] == "1.0.0"
    assert (
        texts["File"] == "extensions/plugins/duplicate-signal-wires.py"
        and len(texts["SHA-256"]) == 64
    )
    assert int(texts["Lines"]) == len(
        (folder / "extensions/plugins/duplicate-signal-wires.py").read_text().splitlines()
    )

    def accept(d: QDialog) -> int:
        d.typed.setText("duplicate-signal-wires")  # type: ignore[attr-defined]
        d.ok.click()  # type: ignore[attr-defined]
        return d.result()

    dlg.run_dialog = accept
    assert dlg.ask_trust() is True
    assert trust.is_trusted("duplicate-signal-wires", texts["SHA-256"])
    ext = ctl.project.extensions
    assert (
        ext is not None
        and next(p for p in ext.plugins if p.name == "duplicate-signal-wires").state == "loaded"
    )
    dlg.plugins.selectRow(plugin_row(dlg, "duplicate-signal-wires"))
    assert dlg.revoke_btn.isEnabled() and not dlg.trust_btn.isEnabled()
    dlg.revoke()
    assert trust.read() == []
    ext = ctl.project.extensions
    assert (
        ext is not None
        and next(p for p in ext.plugins if p.name == "duplicate-signal-wires").state == "untrusted"
    )


def test_the_trust_question_needs_the_name_typed_and_can_show_the_code(qtbot, ctl, folder) -> None:
    ext = ctl.project.extensions
    assert ext is not None
    info = next(p for p in ext.plugins if p.name == "duplicate-signal-wires")
    dlg = TrustDialog(None, ThemeManager(), info, source_text(ext.root, info))
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.windowTitle() == strings.EXT_TRUST_TITLE
    assert "duplicate-signal-wires" in dlg.findChild(QLabel, "trust-body").text()
    risk = dlg.findChild(QLabel, "trust-risk").text()
    assert "runs with your rights" in risk and "no sandbox" in risk
    assert not dlg.ok.isEnabled() and dlg.later.isDefault()  # the safe answer is the default
    dlg.typed.setText("duplicate")
    assert not dlg.ok.isEnabled()
    dlg.typed.setText("duplicate-signal-wires")
    assert dlg.ok.isEnabled()
    assert not dlg.source.isVisibleTo(dlg)
    dlg.source_btn.click()
    assert (
        dlg.source.isVisibleTo(dlg)
        and "def register(api):" in dlg.source.toPlainText()
        and dlg.source_btn.text() == strings.EXT_HIDE_SOURCE
    )
    assert (
        dlg.findChild(QPlainTextEdit, "trust-source") is dlg.source
        and dlg.findChild(QLineEdit, "trust-typed") is dlg.typed
    )


def test_opening_a_project_names_the_code_it_enables_and_declining_loads_nothing(
    qtbot, ctl
) -> None:
    asked: list[str] = []

    def no(d: QDialog) -> int:
        asked.append(d.info.name)  # type: ignore[attr-defined]
        return QDialog.DialogCode.Rejected

    assert ask_to_trust_enabled(None, ThemeManager(), ctl, no) == 0
    assert asked == ["duplicate-signal-wires"] and trust.read() == []

    def yes(d: QDialog) -> int:
        d.typed.setText("duplicate-signal-wires")  # type: ignore[attr-defined]
        d.ok.click()  # type: ignore[attr-defined]
        return d.result()

    assert ask_to_trust_enabled(None, ThemeManager(), ctl, yes) == 1
    assert ask_to_trust_enabled(None, ThemeManager(), ctl, no) == 0 and asked == [
        "duplicate-signal-wires"
    ]  # not asked again
    ext = ctl.project.extensions
    assert ext is not None and ext.plugins[0].state == "loaded"


def test_a_read_only_session_never_asks(qtbot, ctl) -> None:
    ctl.project.read_only = True
    assert ask_to_trust_enabled(None, ThemeManager(), ctl, lambda d: pytest.fail("asked")) == 0


# ---- the Checks panel -------------------------------------------------------------------------------------------


def test_the_checks_panel_shows_an_extension_rule_says_where_it_comes_from_and_explains_it(
    qtbot, ctl
) -> None:
    panel = ChecksPanel(ctl, ThemeManager())
    qtbot.addWidget(panel)
    panel.resize(1100, 760)
    panel.show()
    qtbot.waitUntil(lambda: ctl.drc_current, timeout=20000)
    ids = [r.rule_id for r in panel.results()]
    assert ids[:39] == [r.id for r in drc.RULES]
    assert "x-min-gauge-power" in ids and "x-own-ampacity" in ids
    # the plug-in is not trusted: its rule is not in force, and a notice says so
    assert "x-duplicate-signal-wires" not in ids and "x-extension-problem" in ids
    assert panel.select_rule("x-min-gauge-power")
    details = panel.details
    assert details.id_label.text() == "x-min-gauge-power"
    assert (
        "not part of the tool" in details.note.text()
        and "minimum-wire-gauge-power.json" in details.note.text()
    )
    assert details.explain_btn.isVisibleTo(details)
    assert panel.select_rule("duplicate-id")
    assert "not part of the tool" not in details.note.text() and details.explainable("duplicate-id")
    assert panel.select_rule("x-extension-problem")
    assert "Help > Extensions" in details.note.text()


def test_the_checks_of_a_project_without_extensions_are_the_39_rules_and_nothing_else(
    qtbot, tmp_path
) -> None:
    c = EditorController(drc_delay_ms=30)
    c.open_path(_plain(tmp_path))
    c.run_drc_now()
    panel = ChecksPanel(c, ThemeManager())
    qtbot.addWidget(panel)
    qtbot.waitUntil(lambda: c.drc_current, timeout=20000)
    assert [r.rule_id for r in panel.results()] == [r.id for r in drc.RULES]
    c.wait_drc()
    c.release()


def test_reloading_the_extensions_runs_the_check_again(qtbot, ctl, folder) -> None:
    write_extensions(
        folder, {"extra.json": ext_file("extra", rules=[gauge_rule(id="extra")])}, plugins=[]
    )
    ctl.reload_extensions()
    qtbot.waitUntil(lambda: ctl.drc_current, timeout=20000)
    assert any(r.rule_id == "x-extra" for r in ctl.drc_rule_results())
    assert not any(
        r.rule_id == "x-min-gauge-power" for r in ctl.drc_rule_results()
    )  # enabled.json changed
    assert load_project(folder).project.extensions is not None


def test_a_project_built_from_files_gets_its_extensions_when_installed(qtbot, ctl, folder) -> None:
    """A project restored from the autosave journal is built from files, not from the folder: the
    controller attaches the extensions again."""
    from harness_design_studio.core.io.loader import load_from_files, read_tree

    files, broken, issues = read_tree(folder)
    restored = load_from_files(files, broken, issues).project
    assert restored.extensions is None
    ctl._install(restored, folder, ctl._lock)
    assert ctl.project is restored and restored.extensions is not None
    assert [f.status for f in restored.extensions.files] == ["applied", "applied"]
