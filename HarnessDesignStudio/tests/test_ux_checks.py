# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SC-1, SC-2, SC-3, SH-3, SH-17 (part), SH-28: the Checks tab (a result per design rule), the
engineering value dialog, the pending-values link and the honest Problems header. Offscreen."""

import time
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QModelIndex, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
)

from harness_design_studio.core import configcheck, drc, templates  # noqa: E402
from harness_design_studio.core.checks import Finding  # noqa: E402
from harness_design_studio.core.drc import by_rule  # noqa: E402
from harness_design_studio.gui import drc_process, panels, strings  # noqa: E402
from harness_design_studio.gui.checks_panel import (  # noqa: E402
    FILTERS,
    ChecksPanel,
    PendingValuesLink,
    RulesModel,
    pending_summary,
    rule_row,
    rule_state,
)
from harness_design_studio.gui.config_dialog import ConfigValueDialog  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.states import STATE_ROLE  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.gui_helpers import make_window, show_problems  # noqa: E402
from tests.helpers import time_limit  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402


def _flatsat(tmp_path: Path) -> Path:
    folder = tmp_path / "flatsat"
    templates.create_project(folder, "flatsat")
    return folder


@pytest.fixture
def host(qtbot, tmp_path):
    """The Checks tab on its own, on the flatsat example, its first check finished."""
    theme = ThemeManager()
    ctl = EditorController(drc_delay_ms=30)
    ctl.open_path(_flatsat(tmp_path))
    ctl.run_drc_now()
    panel = ChecksPanel(ctl, theme)
    qtbot.addWidget(panel)
    panel.resize(1100, 760)
    panel.show()
    QApplication.processEvents()
    yield ctl, theme, panel
    ctl.wait_drc()


@pytest.fixture
def flat(qtbot, tmp_path):
    """The shipped flatsat example in a real window, its first check finished."""
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._drc_timer.setInterval(30)  # the editor waits 1.2 s after the last edit
    win.ctl.open_path(_flatsat(tmp_path))
    qtbot.waitUntil(lambda: win.ctl.drc_current, timeout=20000)
    return win


def wait_current(qtbot, ctl) -> None:
    qtbot.waitUntil(lambda: ctl.drc_current, timeout=20000)


def result_of(panel: ChecksPanel, rule_id: str) -> by_rule.RuleResult:
    return next(r for r in panel.results() if r.rule_id == rule_id)


# ---- Problems header (SC-1, SH-3) --------------------------------------------------------------


def test_the_problems_header_never_says_all_rules_were_checked_while_some_were_not(flat) -> None:
    show_problems(flat)
    state = flat.problems.findChild(QLabel, "drc-state")
    assert state is not None
    s = by_rule.summary(flat.ctl.drc_rule_results())
    assert s.not_checked + s.pending > 0  # the flatsat leaves engineering values open
    assert "all" not in state.text().lower()
    assert state.text() == strings.DRC_DONE.format(
        total=s.total, passed=s.passed, failed=s.failed, unchecked=s.not_checked + s.pending
    )


def test_the_problems_header_says_all_passed_only_when_nothing_failed_or_is_open(flat) -> None:
    ctl = flat.ctl
    results = [
        replace(r, status="pass", count=0, missing=(), notes=()) for r in ctl.drc_rule_results()
    ]
    ctl._rule_cache = (ctl.findings_key(), results)
    show_problems(flat)
    flat.problems._signature = None
    flat.problems.refresh()
    state = flat.problems.findChild(QLabel, "drc-state")
    assert state is not None
    assert state.text() == strings.DRC_ALL_PASSED.format(total=len(results))


def test_not_checked_notes_are_never_cut_off_by_the_card_limit(flat) -> None:
    ctl = flat.ctl
    many = [
        Finding(f"part-unapproved.X{i:03d}", "part-unapproved", "warning", f"X{i:03d}",
                f"Part X{i:03d} is not approved", "why", can_waive=True)
        for i in range(60)
    ] + [
        Finding(f"unchecked-config.N{i:02d}", "unchecked-config", "info", f"N{i:02d}",
                f"Note {i} was not checked", "why")
        for i in range(30)
    ]  # fmt: skip
    ctl._drc_raw = [*drc.run(ctl.project), *many]
    ctl._drc_version += 1
    show_problems(flat)
    flat.problems._signature = None
    flat.problems.refresh()
    cards = [f for f in flat.problems.findChildren(QFrame) if f.property("card")]
    notes = [c for c in cards if c.objectName().startswith("finding-unchecked-config.")]
    assert len(notes) >= 30 + 3  # every note, the three of the example included
    assert len(cards) - len(notes) <= panels.MAX_CARDS
    texts = " ".join(x.text() for x in flat.problems.findChildren(QLabel))
    assert "more" in texts  # the other problems are still capped, and say so


def test_a_cancelled_check_is_called_out_of_date_in_problems(flat) -> None:
    ctl = flat.ctl
    ctl._drc_timer.setInterval(60000)
    unit = next(iter(ctl.project.units.values()))
    ctl.update_unit(unit.id, name="Renamed")
    ctl.cancel_check()
    show_problems(flat)
    flat.problems.refresh()
    state = flat.problems.findChild(QLabel, "drc-state")
    assert state is not None and state.text() == strings.DRC_STALE


# ---- the rules table (SC-2) ---------------------------------------------------------------------


def test_one_row_per_rule_with_a_state_chip_for_each_result(host) -> None:
    ctl, _theme, panel = host
    s = by_rule.summary(ctl.drc_rule_results())
    assert panel.model.rowCount() == s.total == 35
    states = [panel.model.data(panel.model.index(r, 3), STATE_ROLE) for r in range(35)]
    assert states.count("pass") == s.passed and states.count("fail") == s.failed
    assert states.count("pending") == s.pending and states.count("not-checked") == s.not_checked
    assert {"pass", "fail", "pending"} <= set(states)
    ids = [panel.model.index(r, 0).data() for r in range(35)]
    assert ids[:2] == ["duplicate-id", "wire-dangling"]


def test_the_summary_strip_counts_every_result_in_words_and_icons(host) -> None:
    ctl, _theme, panel = host
    s = by_rule.summary(ctl.drc_rule_results())
    values = len(configcheck.missing(ctl.project))
    assert panel.summary_text() == (
        f"35 rules: {s.passed} passed · {s.failed} failed · {s.not_checked + s.pending} not checked"
        f" · {values} pending values"
    )
    for key, word in (
        ("pass", "passed"),
        ("fail", "failed"),
        ("unchecked", "not checked"),
        ("values", "pending values"),
    ):
        b = panel.segments[key]
        assert word in b.text() and not b.icon().isNull()
    assert panel.strip.accessibleName() == panel.summary_text()


def test_a_pass_that_read_placeholder_values_says_so(host) -> None:
    ctl, _theme, panel = host
    r = result_of(panel, "current-over-contact")
    assert r.status == "pass" and r.placeholder_files
    assert rule_state(r) == ("pass", "Pass (placeholder values)")
    row = panel.model.row_of("current-over-contact")
    assert row is not None
    assert panel.model.index(row, 3).data() == "Pass (placeholder values)"
    assert "placeholder" in panel.model.index(row, 3).data(Qt.ItemDataRole.ToolTipRole)
    assert "placeholder" in panel.strip.toolTip()
    panel.select_rule("current-over-contact")
    assert (
        "placeholder" in panel.details.note.text()
        and "Nobody has reviewed" in panel.details.note.text()
    )


def test_the_tooltip_of_a_rule_names_its_standard_requirements(host) -> None:
    _ctl, _theme, panel = host
    r = result_of(panel, "connector-voltage")
    row = panel.model.row_of("connector-voltage")
    assert row is not None and r.sources
    tip = panel.model.index(row, 0).data(Qt.ItemDataRole.ToolTipRole)
    assert all(src in tip for src in r.sources)
    assert panel.model.index(row, 1).data(Qt.ItemDataRole.ToolTipRole) == tip
    plain = panel.model.row_of("duplicate-id")
    assert plain is not None
    assert (
        panel.model.index(plain, 0).data(Qt.ItemDataRole.ToolTipRole)
        == strings.CHECKS_TIP_NO_REQUIREMENTS
    )


def test_the_rule_that_lists_other_notes_explains_itself(host) -> None:
    _ctl, _theme, panel = host
    r = result_of(panel, "unchecked-config")
    assert r.count > 0 and rule_state(r)[0] == "pass"  # it ran; its notes are what it reports
    row = panel.model.row_of("unchecked-config")
    assert row is not None
    assert panel.model.index(row, 3).data(Qt.ItemDataRole.ToolTipRole) == strings.CHECKS_TIP_NOTES
    panel.select_rule("unchecked-config")
    assert panel.details.note.text() == strings.CHECKS_TIP_NOTES
    assert panel.details.objects.source.rowCount() == r.count


def test_filter_by_result_text_and_both_together(host) -> None:
    ctl, _theme, panel = host
    s = by_rule.summary(ctl.drc_rule_results())
    panel.set_result_filter("fail")
    assert len(panel.visible_rule_ids()) == s.failed
    panel.set_result_filter("pending")
    assert len(panel.visible_rule_ids()) == s.pending
    panel.set_result_filter("unchecked")
    assert len(panel.visible_rule_ids()) == s.pending + s.not_checked
    panel.set_result_filter("pass")
    assert len(panel.visible_rule_ids()) == s.passed
    panel.set_result_filter("all")
    assert len(panel.visible_rule_ids()) == 35
    panel.set_text_filter("ECSS-Q-ST-30-11_0140217")  # a requirement ID, not part of any cell
    assert set(panel.visible_rule_ids()) == {"current-over-wire", "bundle-current"}
    panel.set_result_filter("pending")
    assert panel.visible_rule_ids() == ["bundle-current"]
    assert panel.count_label.text() == strings.CHECKS_SHOWING.format(1, 35)
    panel.set_text_filter("")
    panel.set_result_filter("all")
    assert [k for k, _t, _s in FILTERS][0] == "all"


def test_sorting_by_result_puts_failures_first_then_pending_then_passes(host) -> None:
    _ctl, _theme, panel = host
    panel.table.sortByColumn(3, Qt.SortOrder.AscendingOrder)
    states = [
        panel.table.proxy.index(r, 3).data(STATE_ROLE) for r in range(panel.table.proxy.rowCount())
    ]
    first_pass = states.index("pass")
    assert set(states[:first_pass]) <= {"fail", "pending", "not-checked", "info"}
    assert states[0] == "fail" and states.index("pending") < first_pass
    panel.table.sortByColumn(4, Qt.SortOrder.DescendingOrder)  # open problems, most first
    counts = [int(panel.table.proxy.index(r, 4).data()) for r in range(3)]
    assert counts == sorted(counts, reverse=True) and counts[0] == 14


def test_numbers_are_right_aligned_and_ids_are_monospace(host) -> None:
    _ctl, _theme, panel = host
    align = panel.model.index(0, 4).data(Qt.ItemDataRole.TextAlignmentRole)
    assert align & int(Qt.AlignmentFlag.AlignRight)
    assert panel.model.index(0, 0).data(Qt.ItemDataRole.FontRole) is not None


def test_the_table_is_a_view_over_a_model_not_a_table_widget(host) -> None:
    from PySide6.QtCore import QAbstractTableModel
    from PySide6.QtWidgets import QTableView, QTableWidget

    _ctl, _theme, panel = host
    assert isinstance(panel.table, QTableView) and not isinstance(panel.table, QTableWidget)
    assert isinstance(panel.model, QAbstractTableModel) and isinstance(panel.model, RulesModel)
    assert not panel.findChildren(QTableWidget)


# ---- the details of a rule -------------------------------------------------------------------------


def test_selecting_a_rule_lists_its_offending_objects(host) -> None:
    _ctl, _theme, panel = host
    r = result_of(panel, "part-unapproved")
    assert panel.select_rule("part-unapproved")
    objects = panel.details.objects
    assert panel.details.result is not None and panel.details.result.rule_id == "part-unapproved"
    assert objects.source.rowCount() == r.count == 14
    assert objects.isVisibleTo(panel) and panel.details.show_btn.isEnabled()
    first = objects.proxy.index(0, 0).data()
    assert first == r.findings[0].object_id
    assert objects.proxy.index(0, 1).data() == r.findings[0].title
    assert objects.proxy.index(0, 2).data() in ("Warning", "Error", "Info")
    assert "part-unapproved" in objects.accessibleName() or r.topic in objects.accessibleName()


def test_a_rule_that_could_not_run_shows_the_exact_missing_value_and_a_supply_button(host) -> None:
    _ctl, _theme, panel = host
    assert panel.select_rule("spare-pins-low")
    d = panel.details
    assert d.chip.state() == "pending"
    where = d.findChild(QLabel, "checks-missing-where")
    assert where is not None and where.text() == "config/derating.json: spare_pin_fraction"
    label = d.findChild(QLabel, "checks-missing-label")
    assert label is not None and "Spare pin fraction" in label.text()
    button = d.findChild(QPushButton, "supply-derating-spare_pin_fraction")
    assert button is not None and button.text() == strings.CHECKS_SUPPLY
    assert button.accessibleName() == strings.CHECKS_SUPPLY_NAME.format("Spare pin fraction")
    assert not d.objects.isVisibleTo(panel)  # nothing to list: the rule did not run
    # a value with a unit says the unit
    panel.select_rule("voltage-drop") or None
    panel.select_rule("temperature-margin")
    units = [w.text() for w in panel.details.findChildren(QLabel, "checks-missing-what")]
    assert any("degrees Celsius" in u and "Unit: degC" in u for u in units)
    assert len(panel.details.supply_buttons) == 3


def test_a_missing_part_rating_is_a_data_gap_without_a_supply_button(host) -> None:
    _ctl, _theme, panel = host
    gap = by_rule.RuleResult(
        "current-over-contact", "Contact current", "error", "not_checked", 0, 0, (), (), (),
        (by_rule.MissingValue("data", "5 contacts have no rating"),),
        ("5 contacts have no rating",), (), (),
    )  # fmt: skip
    panel.details.set_result(gap)
    assert panel.details.chip.state() == "not-checked"
    assert panel.details.supply_buttons == []
    texts = " ".join(w.text() for w in panel.details.findChildren(QLabel, "checks-missing-what"))
    assert "5 contacts have no rating" in texts
    assert panel.details.none_label.text() == strings.CHECKS_OBJECTS_NONE_PARTLY


def test_enter_on_an_object_asks_to_show_it_and_so_does_a_double_click(host, qtbot) -> None:
    _ctl, _theme, panel = host
    panel.select_rule("part-unapproved")
    objects = panel.details.objects
    wanted = objects.proxy.index(0, 0).data()
    pos = objects.visualRect(objects.proxy.index(0, 1)).center()
    QTest.mouseClick(objects.viewport(), Qt.MouseButton.LeftButton, pos=pos)  # selects the row
    with qtbot.waitSignal(panel.showRequested, timeout=1000) as got:
        QTest.mouseDClick(objects.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    assert got.args == [wanted]
    objects.setFocus()
    objects.setCurrentIndex(objects.proxy.index(1, 0))
    with qtbot.waitSignal(panel.showRequested, timeout=1000) as got:
        QTest.keyClick(objects, Qt.Key.Key_Return)
    assert got.args == [objects.proxy.index(1, 0).data()]
    with qtbot.waitSignal(panel.showRequested, timeout=1000) as got:
        panel.details.show_btn.click()
    assert got.args == [objects.proxy.index(1, 0).data()]


def test_new_results_for_the_same_rules_refresh_the_open_details_in_place(host) -> None:
    ctl, _theme, panel = host
    panel.select_rule("spare-pins-low")
    old = result_of(panel, "spare-pins-low")
    assert panel.details.chip.state() == "pending"
    newer = [
        replace(r, status="fail", count=2, missing=(), notes=()) if r.rule_id == old.rule_id else r
        for r in ctl.drc_rule_results()
    ]
    ctl._rule_cache = (ctl.findings_key(), newer)  # same number of rules: rows update in place
    panel.refresh()
    assert panel.current_rule_id() == "spare-pins-low"
    assert panel.details.chip.state() == "fail"
    assert panel.details.supply_buttons == []
    row = panel.model.row_of("spare-pins-low")
    assert row is not None and panel.model.index(row, 4).data() == "2"


# ---- checking, cancelling and failing (SH-17) -------------------------------------------------------


def test_while_the_helper_runs_the_strip_says_checking_and_offers_cancel(host) -> None:
    ctl, _theme, panel = host
    ctl._drc_timer.setInterval(60000)  # an edit schedules a check; it has not started yet
    unit = next(iter(ctl.project.units.values()))
    ctl.update_unit(unit.id, name="Renamed")
    assert ctl.drc_busy() and not ctl.drc_current
    assert panel.status.text() == strings.CHECKS_CHECKING
    assert panel.cancel_btn.isVisibleTo(panel) and not panel.again_btn.isVisibleTo(panel)
    assert panel.table.isVisibleTo(panel) and panel.model.rowCount() == 35  # last results stay
    panel.cancel_btn.click()
    assert not ctl.drc_busy() and not ctl._drc_timer.isActive()
    assert panel.status.text() == strings.CHECKS_CANCELLED
    assert not panel.cancel_btn.isVisibleTo(panel) and panel.again_btn.isVisibleTo(panel)


def test_check_again_runs_the_check_and_clears_the_notice(host, qtbot) -> None:
    ctl, _theme, panel = host
    ctl._drc_timer.setInterval(60000)
    ctl.update_unit(next(iter(ctl.project.units.values())).id, name="Renamed")
    panel.cancel_btn.click()
    panel.again_btn.click()
    assert panel.cancel_btn.isVisibleTo(panel)  # running again
    wait_current(qtbot, ctl)
    assert panel.status.text() == "" and not panel.again_btn.isVisibleTo(panel)
    ctl.wait_drc()


def test_a_failed_check_leaves_a_banner_until_the_next_success(
    qtbot, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv(drc_process.DISABLE_ENV, "1")
    real = drc.run

    def boom(project):
        raise ValueError("rule exploded")

    monkeypatch.setattr(drc, "run", boom)
    ctl = EditorController(drc_delay_ms=30)
    panel = ChecksPanel(ctl, ThemeManager())
    qtbot.addWidget(panel)
    panel.show()
    ctl.open_path(_flatsat(tmp_path))
    qtbot.waitUntil(lambda: ctl.drc_error is not None, timeout=20000)
    qtbot.waitUntil(lambda: ctl._drc_worker is None, timeout=20000)
    assert panel.banner.isVisibleTo(panel)
    assert "rule exploded" in panel.banner_text.text()
    assert panel.model.rowCount() == 0 and panel.empty.isVisibleTo(panel)  # never a list of passes
    assert panel.summary_text() == ""
    QApplication.processEvents()
    assert panel.banner.isVisibleTo(panel)  # nothing hides it but a success
    monkeypatch.setattr(drc, "run", real)
    retry = panel.banner.findChild(QPushButton, "checks-failure-retry")
    assert retry is not None
    retry.click()
    qtbot.waitUntil(lambda: ctl.drc_current, timeout=20000)
    assert not panel.banner.isVisibleTo(panel) and panel.model.rowCount() == 35
    ctl.wait_drc()


def test_nothing_is_shown_as_passed_before_the_first_check_has_finished(qtbot, tmp_path) -> None:
    ctl = EditorController(drc_delay_ms=60000)
    panel = ChecksPanel(ctl, ThemeManager())
    qtbot.addWidget(panel)
    panel.show()
    ctl.open_path(_flatsat(tmp_path))
    assert not ctl.drc_has_result() and ctl.drc_rule_results() == []
    assert panel.model.rowCount() == 0 and panel.empty.isVisibleTo(panel)
    assert panel.empty.text() == strings.CHECKS_CHECKING
    ctl.cancel_check()
    assert panel.empty.text() == strings.CHECKS_NO_RESULT


def test_results_are_grouped_once_per_check_and_never_recomputed(host, monkeypatch) -> None:
    ctl, _theme, panel = host
    calls: list[int] = []
    real = by_rule.run_by_rule

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(by_rule, "run_by_rule", counting)
    first = ctl.drc_rule_results()
    for _ in range(5):
        panel.refresh()
        assert ctl.drc_rule_results() is first
    assert calls == []


# ---- the engineering value dialog (SC-3) --------------------------------------------------------------


def field(dlg: ConfigValueDialog, file: str, key: str):
    return dlg.fields[(file, key)]


def test_the_dialog_lists_every_value_grouped_by_file_with_the_right_editor(host) -> None:
    ctl, theme, _panel = host
    dlg = ConfigValueDialog(ctl, theme)
    values = configcheck.engineering_values(ctl.project, include_optional=True)
    assert set(dlg.fields) == {(v.file, v.key) for v in values}
    assert list(dlg.groups) == list(dict.fromkeys(v.file for v in values))
    kinds = {(v.file, v.key): v.kind for v in values}
    for key, kind in kinds.items():
        editor = dlg.fields[key].editor
        assert isinstance(editor, QComboBox) == (kind in ("choice", "flag")), key
    unit = dlg.findChild(QLabel, "unit-derating-max_voltage_drop_v")
    assert unit is not None and unit.text() == "V"
    assert (
        dlg.fields[("derating", "max_voltage_drop_v")].editor.accessibleName()
        == "Maximum voltage drop (V)"
    )
    assert dlg.fields[("emc", "same_class_one_bundle")].editor.accessibleName()
    dlg.close()


def test_missing_values_carry_the_pending_chip_and_set_ones_do_not(host) -> None:
    ctl, theme, _panel = host
    dlg = ConfigValueDialog(ctl, theme)
    missing = {(n.file, n.key) for n in configcheck.missing(ctl.project)}
    for key, row in dlg.fields.items():
        if row.ev.optional:
            continue
        assert row.chip.isVisibleTo(dlg) == (key in missing)
        if key in missing:
            assert row.chip.state() == "pending"
    assert dlg.only_missing.isChecked()  # opened from the link: only what is missing
    assert (
        not dlg.groups["derating"].rows[0].isVisibleTo(dlg)
        or dlg.groups["derating"].rows[0].ev.missing
    )
    dlg.close()


def test_opened_for_one_key_it_shows_everything_and_focuses_that_value(host) -> None:
    ctl, theme, _panel = host
    dlg = ConfigValueDialog(ctl, theme, "derating", "spare_pin_fraction")
    dlg.show()
    QApplication.processEvents()
    editor = field(dlg, "derating", "spare_pin_fraction").editor
    assert not dlg.only_missing.isChecked()
    assert editor.hasFocus() or dlg.focusWidget() is editor
    dlg.close()


def test_typing_a_bad_value_shows_the_reason_inline_and_never_a_message_box(
    host, monkeypatch
) -> None:
    ctl, theme, _panel = host

    def no_box(*a, **k):
        raise AssertionError("a message box was used")

    for name in ("warning", "critical", "information", "question", "exec"):
        monkeypatch.setattr(QMessageBox, name, no_box)
    dlg = ConfigValueDialog(ctl, theme, "derating", "spare_pin_fraction")
    dlg.show()
    row = field(dlg, "derating", "spare_pin_fraction")
    assert isinstance(row.editor, QLineEdit)
    row.editor.setText("abc")
    err = configcheck.plan_set_value(ctl.project, "derating", "spare_pin_fraction", "abc").error
    assert row.error.text() == err and row.error.isVisibleTo(dlg)
    assert row.editor.property("invalid") is True
    assert not dlg.apply_btn.isEnabled() and dlg.message.text() == strings.CONFIG_FIX_FIRST
    row.editor.setText("1.5")  # a number, but not a share
    assert "must be" in row.error.text() and not dlg.apply_btn.isEnabled()
    before = len(ctl.history._undo)
    assert dlg.apply() is False and len(ctl.history._undo) == before
    row.editor.setText("0.2")
    assert not row.error.isVisibleTo(dlg) and dlg.apply_btn.isEnabled()
    dlg.close()


def test_apply_sets_all_changes_as_one_labelled_undo_step(host) -> None:
    ctl, theme, _panel = host
    dlg = ConfigValueDialog(ctl, theme)
    field(dlg, "derating", "spare_pin_fraction").editor.setText("0.2")
    field(dlg, "derating", "max_ambient_temperature_c").editor.setText("85 degC")
    field(dlg, "emc", "conflicting_class_pairs").editor.setText("A + B, C + D")
    shield = field(dlg, "generation", "shield_end_a").editor
    assert isinstance(shield, QComboBox)
    shield.setCurrentIndex(shield.findData("pigtail"))
    assert len(dlg.changes()) == 4
    assert "4 changes" in dlg.message.text()
    before = len(ctl.history._undo)
    applied: list[int] = []
    dlg.applied.connect(applied.append)
    assert dlg.apply() is True and applied == [4]
    assert len(ctl.history._undo) == before + 1  # one step
    assert ctl.history.next_undo_label == strings.CONFIG_LABEL_MANY.format(4)
    values = ctl.project.config
    assert values["derating"].values["spare_pin_fraction"] == 0.2
    assert values["derating"].values["max_ambient_temperature_c"] == 85
    assert values["emc"].values["conflicting_class_pairs"] == [["A", "B"], ["C", "D"]]
    assert values["generation"].values["shield_end_a"] == "pigtail"
    ctl.undo()
    assert ctl.project.config["derating"].values["spare_pin_fraction"] is None
    assert ctl.project.config["emc"].values["conflicting_class_pairs"] is None
    assert len(ctl.history._undo) == before


def test_a_single_change_names_the_value_in_the_undo_label(host) -> None:
    ctl, theme, _panel = host
    dlg = ConfigValueDialog(ctl, theme, "derating", "spare_pin_fraction")
    field(dlg, "derating", "spare_pin_fraction").editor.setText("0.2")
    assert dlg.apply()
    assert ctl.history.next_undo_label == "Set Spare pin fraction"


def test_the_placeholder_toggle_marks_a_file_reviewed_in_the_same_step(host) -> None:
    ctl, theme, _panel = host
    assert ctl.project.config["derating"].placeholder
    dlg = ConfigValueDialog(ctl, theme, "derating", "spare_pin_fraction")
    toggle = dlg.groups["derating"].toggle
    assert toggle.isChecked() and toggle.isEnabled()
    field(dlg, "derating", "spare_pin_fraction").editor.setText("0.2")
    toggle.setChecked(False)
    before = len(ctl.history._undo)
    assert dlg.apply()
    assert len(ctl.history._undo) == before + 1
    cfg = ctl.project.config["derating"]
    assert cfg.placeholder is False and cfg.values["spare_pin_fraction"] == 0.2
    ctl.undo()
    assert ctl.project.config["derating"].placeholder is True


def test_a_value_frozen_by_a_release_is_disabled_and_says_why(qtbot, tmp_path) -> None:
    from tests.test_change_control import do_release, exported, full, releasable

    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    ctl = EditorController()
    ctl._install(p, None, None)
    dlg = ConfigValueDialog(ctl, ThemeManager(), "derating", "spare_pin_fraction")
    locked = field(dlg, "derating", "spare_pin_fraction")
    assert not locked.editor.isEnabled()
    assert locked.chip.state() == "locked"
    reason = configcheck.plan_set_value(p, "derating", "spare_pin_fraction", 0.31).error
    assert reason and strings.CONFIG_LOCKED.format(reason) == locked.caption.text()
    assert field(dlg, "generation", "service_loop_m").editor.isEnabled()
    dlg.close()


def test_a_read_only_project_cannot_be_changed(host) -> None:
    ctl, theme, _panel = host
    ctl.project.read_only = True
    dlg = ConfigValueDialog(ctl, theme, "derating", "spare_pin_fraction")
    row = field(dlg, "derating", "spare_pin_fraction")
    assert not row.editor.isEnabled() and not dlg.apply_btn.isEnabled()
    assert dlg.message.text() == strings.CONFIG_READ_ONLY
    assert dlg.apply() is False
    ctl.project.read_only = False


# ---- the journey: supply a value, the rule moves (SC-2 + SC-3) ----------------------------------------------


def _open_supply(panel: ChecksPanel, rule: str, file: str, key: str) -> ConfigValueDialog:
    assert panel.select_rule(rule)
    button = panel.details.findChild(QPushButton, f"supply-{file}-{key}")
    assert button is not None
    button.click()
    dlg = panel.config_dialog()
    assert dlg is not None
    return dlg


def test_journey_supplying_a_pending_value_moves_the_rule_to_pass_in_one_undo_step(
    host, qtbot
) -> None:
    ctl, _theme, panel = host
    ctl._drc_timer.setInterval(30)
    assert result_of(panel, "spare-pins-low").status == "pending"
    steps = len(ctl.history._undo)
    dlg = _open_supply(panel, "spare-pins-low", "derating", "spare_pin_fraction")
    row = field(dlg, "derating", "spare_pin_fraction")
    assert row.editor.hasFocus() or dlg.focusWidget() is row.editor
    row.editor.setText("0.2")
    assert dlg.apply_btn.isEnabled()
    dlg.apply_btn.click()
    assert dlg.result() == 1 or not dlg.isVisible()
    assert len(ctl.history._undo) == steps + 1  # exactly one step
    assert not ctl.drc_current  # the check runs again by itself
    assert panel.status.text() == strings.CHECKS_CHECKING
    wait_current(qtbot, ctl)
    after = result_of(panel, "spare-pins-low")
    assert after.status in ("pass", "fail") and after.missing == ()
    assert panel.current_rule_id() == "spare-pins-low"  # the selection stays on the rule
    assert panel.details.chip.state() == after_state(after)
    s = by_rule.summary(ctl.drc_rule_results())
    assert panel.summary_text() == (
        f"{s.total} rules: {s.passed} passed · {s.failed} failed · {s.not_checked + s.pending}"
        f" not checked · {len(configcheck.missing(ctl.project))} pending values"
    )
    # undo puts the value back and the rule becomes pending again
    ctl.undo()
    assert len(ctl.history._undo) == steps
    assert ctl.project.config["derating"].values["spare_pin_fraction"] is None
    wait_current(qtbot, ctl)
    assert result_of(panel, "spare-pins-low").status == "pending"
    assert panel.details.chip.state() == "pending"
    ctl.wait_drc()


def after_state(r: by_rule.RuleResult) -> str:
    return rule_state(r)[0]


def test_journey_a_value_that_trips_the_rule_moves_it_to_fail(host, qtbot) -> None:
    ctl, _theme, panel = host
    ctl._drc_timer.setInterval(30)
    dlg = _open_supply(panel, "spare-pins-low", "derating", "spare_pin_fraction")
    field(dlg, "derating", "spare_pin_fraction").editor.setText("0.99")
    assert dlg.apply()
    wait_current(qtbot, ctl)
    r = result_of(panel, "spare-pins-low")
    assert r.status == "fail" and r.count > 0
    panel.select_rule("spare-pins-low")
    assert panel.details.objects.source.rowCount() == r.count
    ctl.undo()
    wait_current(qtbot, ctl)
    assert result_of(panel, "spare-pins-low").status == "pending"
    ctl.wait_drc()


def test_a_second_click_on_supply_value_reuses_the_open_dialog(host) -> None:
    _ctl, _theme, panel = host
    first = _open_supply(panel, "spare-pins-low", "derating", "spare_pin_fraction")
    panel.select_rule("mating-cycles")
    again = panel.details.findChild(QPushButton, "supply-derating-max_mating_cycles")
    assert again is not None
    again.click()
    assert panel.config_dialog() is first
    focus = first.focusWidget()
    assert focus is field(first, "derating", "max_mating_cycles").editor
    first.close()


# ---- the pending values link (SH-3) -----------------------------------------------------------------------


def test_the_link_counts_rules_not_checked_and_values_missing(host) -> None:
    ctl, theme, panel = host
    unchecked, values = pending_summary(ctl)
    s = by_rule.summary(ctl.drc_rule_results())
    assert unchecked == s.not_checked + s.pending == 12
    assert values == len(configcheck.missing(ctl.project)) == 4
    link = PendingValuesLink(ctl, theme)
    assert link.text() == strings.PENDING_LINK.format(values=4, rules=12)
    assert link.accessibleName().startswith(strings.PENDING_LINK_NAME)
    got: list[str] = []
    link.filterRequested.connect(got.append)
    link.filterRequested.connect(panel.set_result_filter)
    link.click()
    assert got == ["unchecked"]
    assert panel.result_filter() == "unchecked"
    assert set(panel.visible_rule_ids()) == {
        r.rule_id for r in panel.results() if r.status in ("pending", "not_checked")
    }


def test_the_link_follows_the_values_and_hides_when_nothing_is_pending(qtbot) -> None:
    from tests.test_change_control import full

    ctl = EditorController()
    ctl._install(full(), None, None)
    link = PendingValuesLink(ctl, ThemeManager())
    qtbot.addWidget(link)
    link.show()
    missing = [(n.file, n.key) for n in configcheck.missing(ctl.project)]
    assert pending_summary(ctl) == (0, len(missing))  # no check has finished: no rule count yet
    assert link.text() == strings.PENDING_LINK_VALUES.format(len(missing)) and link.isVisible()
    examples = {"spare_pin_fraction": "0.2", "power_signal_gap_pins": "1",
                "category_pairs_to_separate": "power + analog", "conflicting_class_pairs": "A + B"}  # fmt: skip
    for file, key in missing:
        plan = configcheck.plan_set_value(ctl.project, file, key, examples[key])
        assert plan.ok and ctl.run(f"set {key}", plan.ops)
    assert pending_summary(ctl) == (0, 0)
    assert not link.isVisible() and link.text() == ""
    ctl.undo()
    assert link.isVisible() and link.text() == strings.PENDING_LINK_VALUES.format(1)


# ---- keyboard only ------------------------------------------------------------------------------------------


def test_everything_can_be_done_from_the_keyboard(host, qtbot) -> None:
    ctl, _theme, panel = host
    ctl._drc_timer.setInterval(30)
    table = panel.table
    table.setFocus()
    table.setCurrentIndex(table.proxy.index(0, 0))
    QApplication.processEvents()
    assert panel.current_rule_id() == "duplicate-id"
    QTest.keyClick(table, Qt.Key.Key_Down)
    assert panel.current_rule_id() == "wire-dangling"
    for _ in range(11):  # one more than before 1.4.0: pin-shared sits before it
        QTest.keyClick(table, Qt.Key.Key_Down)
    assert panel.current_rule_id() == "spare-pins-low"
    # Enter in the table moves into the details: the Supply value button of the missing value
    QTest.keyClick(table, Qt.Key.Key_Return)
    supply = panel.details.supply_buttons[0]
    assert supply.hasFocus()
    # Space presses it (a button), and the dialog opens with the cursor in the value
    QTest.keyClick(supply, Qt.Key.Key_Space)
    dlg = panel.config_dialog()
    assert dlg is not None
    editor = field(dlg, "derating", "spare_pin_fraction").editor
    assert dlg.focusWidget() is editor or editor.hasFocus()
    QTest.keyClicks(editor, "0.25")
    assert editor.text() == "0.25" and dlg.apply_btn.isEnabled()
    steps = len(ctl.history._undo)
    dlg.activateWindow()
    # Ctrl+Return is a window shortcut: it only fires once the dialog is the active window, which
    # takes a moment on a loaded machine
    qtbot.waitUntil(dlg.isActiveWindow, timeout=5000)
    QTest.keyClick(editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert len(ctl.history._undo) == steps + 1 and not dlg.isVisible()
    wait_current(qtbot, ctl)
    assert result_of(panel, "spare-pins-low").status != "pending"
    # on a rule with objects: Tab reaches the objects table and Enter shows the object
    assert panel.select_rule("part-unapproved")
    panel.activateWindow()
    table.setFocus()
    QApplication.processEvents()
    QTest.keyClick(table, Qt.Key.Key_Return)
    assert panel.details.objects.hasFocus()
    with qtbot.waitSignal(panel.showRequested, timeout=1000) as got:
        QTest.keyClick(panel.details.objects, Qt.Key.Key_Return)
    assert got.args == [panel.details.objects.proxy.index(0, 0).data()]
    QTest.keyClick(panel.details.objects, Qt.Key.Key_Tab)
    assert panel.details.show_btn.hasFocus()
    ctl.wait_drc()


def test_ctrl_f_goes_to_the_filter_and_the_summary_counts_are_buttons(host) -> None:
    _ctl, _theme, panel = host
    panel.activateWindow()
    panel.table.setFocus()
    QApplication.processEvents()
    QTest.keyClick(panel.table, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    assert panel.filter_text.hasFocus()
    segment = panel.segments["fail"]
    segment.setFocus()
    QTest.keyClick(segment, Qt.Key.Key_Space)
    assert panel.result_filter() == "fail"


# ---- performance and accessibility ----------------------------------------------------------------------------


def _hundred(results: list[by_rule.RuleResult]) -> list[by_rule.RuleResult]:
    return [replace(results[i % len(results)], rule_id=f"rule-{i:03d}") for i in range(100)]


@pytest.mark.perf
def test_a_hundred_rules_build_filter_and_sort_quickly(host) -> None:
    ctl, theme, panel = host
    results = _hundred(ctl.drc_rule_results())
    model = RulesModel(theme)
    t = time.perf_counter()
    model.set_results(results)
    build = (time.perf_counter() - t) * 1000
    assert model.rowCount() == 100 and build < time_limit(200), build
    t = time.perf_counter()
    panel.model.set_results(results)
    panel.set_result_filter("pending")
    panel.set_text_filter("rule-0")
    panel.set_text_filter("")
    panel.table.sortByColumn(3, Qt.SortOrder.AscendingOrder)
    panel.set_result_filter("all")
    QApplication.processEvents()
    total = (time.perf_counter() - t) * 1000
    assert total < time_limit(500), total
    # a refresh with unchanged results does not rebuild rows
    seen: list[int] = []
    panel.model.modelReset.connect(lambda: seen.append(1))
    panel.refresh()
    panel.refresh()
    assert seen == []


def test_the_panel_the_details_and_the_dialog_have_accessible_names(host) -> None:
    ctl, theme, panel = host
    panel.select_rule("spare-pins-low")
    assert unnamed(panel) == []
    panel.select_rule("part-unapproved")
    assert unnamed(panel) == []
    assert panel.table.accessibleName() == strings.CHECKS_TABLE
    assert (
        panel.model.index(0, 3).data(Qt.ItemDataRole.AccessibleTextRole).startswith("Result: Pass")
    )
    for button in (panel.cancel_btn, panel.again_btn, panel.details.show_btn):
        assert button.accessibleName() and button.toolTip()
    dlg = ConfigValueDialog(ctl, theme)
    dlg.only_missing.setChecked(False)
    dlg.show()
    assert unnamed(dlg) == []
    for g in dlg.groups.values():
        assert g.toggle.accessibleName() and g.box.accessibleName()
    dlg.close()
    link = PendingValuesLink(ctl, theme)
    link.show()
    assert link.accessibleName() and link.toolTip()
    link.close()


def test_the_panel_renders_in_light_and_dark_with_distinct_pending_and_not_checked(host) -> None:
    from PySide6.QtWidgets import QApplication as App

    _ctl, theme, panel = host
    app = App.instance()
    for mode in ("light", "dark"):
        theme.apply(app, mode)  # type: ignore[arg-type]
        panel.select_rule("spare-pins-low")
        image = panel.grab().toImage()
        assert not image.isNull() and image.width() > 500
    pend = rule_row(result_of(panel, "spare-pins-low"))
    ok = rule_row(result_of(panel, "duplicate-id"))
    assert pend["state"] == "pending" and ok["state"] == "pass"
    assert pend["result"][1] != ok["result"][1]


def test_looking_up_a_rule_that_does_not_exist_is_harmless(host) -> None:
    _ctl, _theme, panel = host
    assert panel.model.row_of("no-such-rule") is None
    assert panel.select_rule("no-such-rule") is False
    assert panel.table.proxy.mapFromSource(QModelIndex()).isValid() is False
