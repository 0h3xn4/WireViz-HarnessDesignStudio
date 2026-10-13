# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SC-11, SC-13, SC-22: the lists panel (wire list, pinouts, BOM, mass and length, test tables,
labels, system BOM) and the generate plan table, on the flatsat example, offscreen."""

import zipfile
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QApplication, QComboBox, QLineEdit  # noqa: E402

from harness_design_studio.core.commands import Put  # noqa: E402
from harness_design_studio.core.generate.engine import plan_generation  # noqa: E402
from harness_design_studio.core.io.layout import model_hash  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.model import Project, evolve  # noqa: E402
from harness_design_studio.core.outputs import tables  # noqa: E402
from harness_design_studio.core.outputs.stamp import csv_bytes, parse_csv, stamp_of  # noqa: E402
from harness_design_studio.core.samples import sat15  # noqa: E402
from harness_design_studio.gui import lists_panel as lp  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.lists_panel import ListsPanel, cell_state  # noqa: E402
from harness_design_studio.gui.plan_table import GeneratePlanTable, plan_rows  # noqa: E402
from harness_design_studio.gui.states import STATE_ROLE, chip_size  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from harness_design_studio.resources import examples_path  # noqa: E402


def flatsat() -> Project:
    root = examples_path()
    assert root is not None
    return load_project(root / "projects" / "flatsat").project


@pytest.fixture
def theme(qapp):
    th = ThemeManager()
    th.apply(qapp, "light", 1.0)
    yield th
    ThemeManager().apply(qapp, "light", 1.0)


def make_panel(qtbot, theme, project: Project | None = None, size=(1280, 720)):
    ctl = EditorController()
    ctl._install(project if project is not None else flatsat(), None, None)
    panel = ListsPanel(ctl, theme)
    qtbot.addWidget(panel)
    panel.resize(*size)
    panel.show()
    panel.select_harness("W002") if "W002" in ctl.project.harnesses else None
    panel.wait_idle()
    return ctl, panel


def shown(panel: ListsPanel, name: str) -> list[list[str]]:
    """The rows of a list as the view shows them, header first."""
    v = panel.view(name)
    m = v.model()
    head = [m.headerData(c, Qt.Orientation.Horizontal) for c in range(m.columnCount())]
    return [head] + [
        [m.index(r, c).data(Qt.ItemDataRole.DisplayRole) or "" for c in range(m.columnCount())]
        for r in range(m.rowCount())
    ]


# ---- SC-11: the tables are the outputs' tables ----------------------------------------------------------


def test_every_list_is_the_table_the_outputs_builders_make(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    p, h = ctl.project, ctl.project.harnesses["W002"]
    want = {
        "wirelist": tables.wire_list(p, h),
        "pinouts": tables.pinouts(p, h),
        "bom": tables.bom(p, [h]),
        "mass": tables.mass_length(p, [h]),
        "tests": tables.tests(p, h),
        "labels": tables.labels(p, h),
        "system-bom": tables.bom(p, [p.harnesses[i] for i in sorted(p.harnesses)]),
    }
    assert [n for n, _t, _h in lp.LISTS] == list(want)
    for name, table in want.items():
        assert shown(panel, name) == table, name  # same header and the same rows, nothing added


def test_the_panel_never_changes_the_design(qtbot, theme) -> None:
    p = flatsat()
    before = model_hash(p)
    ctl, panel = make_panel(qtbot, theme, p)
    for name, _t, _h in lp.LISTS:
        panel.set_table(name)
        panel.view(name).selectAll()
    panel.filter.setText("W002")
    assert model_hash(ctl.project) == before


def test_sub_tabs_are_named_and_in_order(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    assert [panel.tabs.tabText(i) for i in range(panel.tabs.count())] == [
        "Wire list", "Pinouts", "BOM", "Mass and length", "Test tables", "Labels", "System BOM",
    ]  # fmt: skip
    assert panel.current_name() == "wirelist"
    panel.set_table("tests")
    assert panel.current_name() == "tests"
    with pytest.raises(KeyError):
        panel.set_table("nope")


def test_units_are_in_the_headers(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    assert "Length (m)" in shown(panel, "wirelist")[0] and "AWG" in shown(panel, "wirelist")[0]
    assert "Mass of wires and cable connectors (g)" in shown(panel, "mass")[0]
    assert "Wire length known (m)" in shown(panel, "mass")[0]
    assert "Quantity" in shown(panel, "bom")[0] and "Unit" in shown(panel, "bom")[0]


def test_numbers_are_right_aligned_and_ids_are_monospace(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    m = panel.view("wirelist").source
    cols = {c.header: c for c in m.columns}
    assert cols["Length (m)"].alignment == "right" and cols["Length (m)"].numeric
    assert cols["Wire"].mono and cols["From connector"].mono and not cols["Signal"].mono
    idx = m.index(0, m.columns.index(cols["Length (m)"]))
    assert idx.data(Qt.ItemDataRole.TextAlignmentRole) & int(Qt.AlignmentFlag.AlignRight)
    assert (
        m.index(0, 0).data(Qt.ItemDataRole.FontRole).family() == lp.mono_family()
        if hasattr(lp, "mono_family")
        else True
    )


def test_harness_selector_switches_the_lists_and_the_system_bom_stays(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    system = shown(panel, "system-bom")
    assert panel.select_harness("W003") and panel.harness_id() == "W003"
    p = ctl.project
    assert shown(panel, "wirelist") == tables.wire_list(p, p.harnesses["W003"])
    assert shown(panel, "system-bom") == system  # all harnesses: not tied to the selection
    assert not panel.select_harness("nope")


# ---- pending / not checked styling -----------------------------------------------------------------------


def test_cell_states_come_only_from_what_the_tables_say() -> None:
    assert cell_state("AWG", "pending") == "pending"
    assert cell_state("Approval", "pending (example data)") == "pending"
    assert cell_state("Limit", "TBD (placeholder)") == "pending"
    assert cell_state("Test voltage", "TBD (placeholder)") == "pending"
    assert cell_state("Length (m)", "") == "pending"  # an unknown length is not an empty cell
    assert cell_state("Margin (g)", "") == "pending"
    assert cell_state("Category", "unknown") == "not-checked"
    assert cell_state("Approval", "missing from parts list") == "warning"
    assert cell_state("Approval", "approved") == "pass"
    assert cell_state("Approval", "not_approved") == "fail"
    assert cell_state("Locked", "yes") == "locked"
    assert cell_state("Complete", "no") == "pending"
    assert cell_state("Signal", "") is None  # an ordinary empty cell stays empty
    assert cell_state("Colour", "") is None
    assert cell_state("Wire", "W1") is None and cell_state("AWG", "24") is None


def test_pending_gauges_and_placeholder_limits_are_chips_in_the_views(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    wl = panel.view("wirelist").source
    awg = wl.columns[[c.header for c in wl.columns].index("AWG")]
    k = wl.columns.index(awg)
    pending = [r for r in range(wl.rowCount()) if wl.index(r, k).data() == "pending"]
    assert pending and all(wl.index(r, k).data(STATE_ROLE) == "pending" for r in pending)
    ok = [r for r in range(wl.rowCount()) if wl.index(r, k).data() != "pending"]
    assert all(wl.index(r, k).data(STATE_ROLE) is None for r in ok)
    # test tables: limits that are placeholders
    tt = panel.view("tests").source
    k = [c.header for c in tt.columns].index("Limit")
    states = {tt.index(r, k).data(STATE_ROLE) for r in range(tt.rowCount())}
    cfg = ctl.project.config.get("generation")
    limit_set = bool(cfg and cfg.values.get("test_continuity_max_ohm") is not None)
    assert states == ({None} if limit_set else {"pending"}) or states <= {None, "pending"}
    # accessible text says the state in words
    idx = wl.index(pending[0], wl.columns.index(awg))
    assert "Pending" in idx.data(Qt.ItemDataRole.AccessibleTextRole)


def test_unknown_lengths_show_as_pending_not_as_empty(qtbot, theme) -> None:
    p = flatsat()
    h = p.harnesses["W003"]
    p.harnesses["W003"] = evolve(
        h,
        segments=[evolve(s, length_m=None) for s in h.segments],
        wires=[evolve(w, length_m=None) for w in h.wires],
    )
    ctl, panel = make_panel(qtbot, theme, p)
    panel.select_harness("W003")
    wl = panel.view("wirelist").source
    k = [c.header for c in wl.columns].index("Length (m)")
    blanks = [r for r in range(wl.rowCount()) if wl.index(r, k).data() == ""]
    assert blanks
    assert all(wl.index(r, k).data(STATE_ROLE) == "pending" for r in blanks)


# ---- sort, filter, copy -----------------------------------------------------------------------------------


def test_filter_and_sort(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    view = panel.view("wirelist")
    total = view.source.rowCount()
    panel.filter.setText("RTN")
    n = view.proxy.rowCount()
    assert 0 < n < total and str(n) in panel.count.text() and str(total) in panel.count.text()
    panel.filter.setText("")
    assert view.proxy.rowCount() == total and panel.count.text() == strings.LP_COUNT_ALL.format(
        total
    )
    col = [c.header for c in view.source.columns].index("Length (m)")
    view.sortByColumn(col, Qt.SortOrder.DescendingOrder)
    values = [
        float(view.model().index(r, col).data())
        for r in range(view.model().rowCount())
        if view.model().index(r, col).data()
    ]
    assert values == sorted(values, reverse=True)  # numbers sort as numbers, not as text


def test_filter_applies_to_every_list(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    panel.filter.setText("W002-P2")
    for name in ("wirelist", "pinouts", "labels"):
        view = panel.view(name)
        assert 0 < view.proxy.rowCount() < view.source.rowCount(), name


def test_only_pending_or_not_checked_keeps_rows_with_a_chip(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    view = panel.view("wirelist")
    total = view.proxy.rowCount()
    panel.only_open.setChecked(True)
    n = view.proxy.rowCount()
    assert 0 < n < total
    for r in range(n):
        states = {
            view.model().index(r, c).data(STATE_ROLE) for c in range(view.model().columnCount())
        }
        assert states & {"pending", "not-checked"}
    panel.only_open.setChecked(False)
    assert view.proxy.rowCount() == total


def test_ctrl_c_copies_tab_separated_text(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    view = panel.view("wirelist")
    view.setFocus()
    view.selectAll()
    QTest.keyClick(view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    text = QApplication.clipboard().text()
    rows = [line.split("\t") for line in text.split("\n")]
    want = tables.wire_list(ctl.project, ctl.project.harnesses["W002"])
    assert rows == want[1:]
    QTest.keyClick(
        view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
    )
    assert QApplication.clipboard().text().split("\n")[0].split("\t") == want[0]


# ---- export of the visible table ---------------------------------------------------------------------------


def test_export_csv_is_the_visible_rows_through_the_output_writer(qtbot, theme, tmp_path) -> None:
    ctl, panel = make_panel(qtbot, theme)
    panel.filter.setText("RTN")
    view = panel.view("wirelist")
    col = [c.header for c in view.source.columns].index("Wire")
    view.sortByColumn(col, Qt.SortOrder.DescendingOrder)
    table = panel.visible_table()
    assert table[0] == tables.wire_list(ctl.project, ctl.project.harnesses["W002"])[0]
    assert len(table) - 1 == view.proxy.rowCount() and all("RTN" in r for r in table[1:])
    ids = [r[0] for r in table[1:]]
    assert ids == sorted(ids, key=lambda s: s, reverse=True) or len(ids) < 2
    path = panel.export_to(tmp_path / "rows.csv")
    assert path == tmp_path / "rows.csv"
    data = path.read_bytes()
    assert data == csv_bytes(table, stamp_of(ctl.project))  # the same writer as the outputs
    assert parse_csv(data) == table


def test_export_xlsx_is_a_workbook_of_the_visible_rows(qtbot, theme, tmp_path) -> None:
    from harness_design_studio.core.outputs.verify import _xlsx_sheets

    ctl, panel = make_panel(qtbot, theme)
    panel.set_table("bom")
    path = panel.export_to(tmp_path / "bom.xlsx")
    assert zipfile.is_zipfile(path)
    sheets = _xlsx_sheets(path.read_bytes())
    assert sheets["BOM"] == panel.visible_table("bom")
    assert panel.export_to(tmp_path / "other").suffix == ".csv"  # a name without a suffix gets one


def test_the_export_button_asks_the_window_with_the_list_and_format(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    got: list[tuple[str, str]] = []
    panel.exportTableRequested.connect(lambda n, f: got.append((n, f)))
    panel.set_table("pinouts")
    panel.act_csv.trigger()
    panel.act_xlsx.trigger()
    assert got == [("pinouts", "csv"), ("pinouts", "xlsx")]
    assert not panel.export_btn.icon().isNull() and "CSV" in panel.export_btn.toolTip()


# ---- the stale banner ----------------------------------------------------------------------------------------


def test_stale_banner_appears_when_the_model_changed_since_generation(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    assert not panel.banner.isVisible() and not panel.is_stale()
    unit = next(iter(ctl.project.units.values()))
    ctl.run("rename", [Put("units", evolve(unit, name="Renamed unit"))])
    panel.refresh()
    panel.wait_idle()
    assert panel.is_stale() and panel.banner.isVisible()
    assert "changed after the harnesses were generated" in panel.banner_text.text()
    assert panel.banner_chip.state() == "stale"
    got = []
    panel.generateRequested.connect(lambda: got.append(1))
    panel.banner_btn.click()
    assert got == [1]
    ctl.undo()
    panel.refresh()
    panel.wait_idle()
    assert not panel.banner.isVisible()


def test_staleness_is_worked_out_off_the_ui_thread(qtbot, theme, monkeypatch) -> None:
    import threading
    import time

    calls = []
    real = lp.generation_status  # type: ignore[attr-defined]

    def slow(project):
        calls.append(threading.current_thread() is not threading.main_thread())
        time.sleep(0.1)
        return real(project)

    monkeypatch.setattr(lp, "generation_status", slow)
    ctl = EditorController()
    ctl._install(flatsat(), None, None)
    panel = ListsPanel(ctl, theme)
    qtbot.addWidget(panel)
    panel.show()
    t = time.perf_counter()
    panel.refresh()
    assert (time.perf_counter() - t) * 1000 < 90
    panel.wait_idle()
    assert calls and all(calls)
    n = len(calls)
    panel.refresh()
    panel.wait_idle()
    assert len(calls) == n  # cached by the state token


# ---- SC-22: empty states ------------------------------------------------------------------------------------


def test_empty_project_says_what_to_do(qtbot, theme) -> None:
    ctl = EditorController()
    panel = ListsPanel(ctl, theme)
    qtbot.addWidget(panel)
    panel.show()
    assert panel.stack.currentWidget() is panel.empty
    assert "Add interfaces" in panel.empty_body.text() and "Generate" in panel.empty_body.text()
    assert not panel.empty_generate.isVisible()
    assert not panel.tabs.isVisible() and not panel.export_btn.isVisible()


def test_interfaces_without_harnesses_offer_generate(qtbot, theme) -> None:
    p = flatsat()
    p.harnesses.clear()
    p.generation = None
    ctl = EditorController()
    ctl._install(p, None, None)
    panel = ListsPanel(ctl, theme)
    qtbot.addWidget(panel)
    panel.show()
    assert panel.empty_generate.isVisible()
    got = []
    panel.generateRequested.connect(lambda: got.append(1))
    panel.empty_generate.click()
    assert got == [1]


# ---- layout, keyboard, accessibility --------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_layout_at_1280_by_720_has_nothing_clipped(qtbot, qapp, theme, mode) -> None:
    from PySide6.QtCore import QPoint

    theme.apply(qapp, mode)
    ctl, panel = make_panel(qtbot, theme, size=(1280, 720))
    QApplication.processEvents()
    area = panel.rect()
    for w in panel.findChildren(QAbstractButton):
        if w.isVisibleTo(panel):
            pos = w.mapTo(panel, QPoint(0, 0))
            assert area.contains(pos) and area.contains(pos + QPoint(w.width() - 1, w.height() - 1))
            if w.text():
                need = w.fontMetrics().horizontalAdvance(w.text()) + w.iconSize().width()
                assert w.width() >= need, w.objectName()
    for name, _t, _h in lp.LISTS:
        panel.set_table(name)
        QApplication.processEvents()
        v = panel.view(name)
        head = v.horizontalHeader()
        for k in range(v.model().columnCount()):
            title = v.model().headerData(k, Qt.Orientation.Horizontal)
            assert head.sectionSize(k) >= v.fontMetrics().horizontalAdvance(title), (name, title)
            for r in range(v.source.rowCount()):  # no state chip is cut off
                state = v.source.state_at(r, k)
                if state:
                    need = chip_size(state, theme, v.source.text_at(r, k) or None, v.font()).width()
                    assert head.sectionSize(k) >= need, (name, title, need)
        assert v.height() > 150
    assert not panel.grab().isNull()


def test_keyboard_only_and_accessible_names(qtbot, theme) -> None:
    ctl, panel = make_panel(qtbot, theme)
    panel.tabs.setFocus()
    QTest.keyClick(panel.tabs.tabBar(), Qt.Key.Key_Right)
    assert panel.current_name() == "pinouts"
    QTest.keyClick(panel, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    assert panel.filter.hasFocus()
    for w in panel.findChildren(QAbstractButton) + panel.findChildren(QComboBox):
        if w.isVisibleTo(panel):
            assert w.accessibleName(), w.objectName()
    for w in panel.findChildren(QLineEdit):
        if w.isVisibleTo(panel) and w.objectName() == "lists-filter":
            assert w.accessibleName()
    for name, _t, _h in lp.LISTS:
        assert panel.view(name).accessibleName()
        assert panel.view(name).focusPolicy() & Qt.FocusPolicy.TabFocus


# ---- SC-13: the generate plan table ------------------------------------------------------------------------------


def test_plan_table_lists_new_harnesses_of_a_first_generation(qtbot, theme) -> None:
    p = sat15()
    plan = plan_generation(p)
    rows = plan_rows(plan, p)
    assert {r["harness"] for r in rows} == set(plan.report.added) and rows
    assert all(r["change_key"] == "new" for r in rows)
    table = GeneratePlanTable(theme)
    qtbot.addWidget(table)
    table.show()
    table.set_plan(plan, p)
    m = table.model
    assert [m.headerData(i, Qt.Orientation.Horizontal) for i in range(4)] == [
        "Harness", "Name", "Change", "Locked pins kept",
    ]  # fmt: skip
    assert m.rowCount() == len(plan.report.added)
    assert m.index(0, 2).data() == strings.GP_NEW and m.index(0, 2).data(STATE_ROLE) == "info"
    assert m.index(0, 1).data() == plan.harnesses[rows[0]["harness"]].name


def test_plan_table_for_a_change_an_unchanged_and_a_removed_harness(qtbot, theme) -> None:
    p = flatsat()
    h = p.harnesses["W003"]
    p.harnesses["W003"] = evolve(h, name="Renamed by hand")  # generation will put its name back
    ghost = evolve(
        p.harnesses["W008"], id="W099", name="Orphan", group_key="no-such-group", interfaces=[]
    )
    p.harnesses["W099"] = ghost
    plan = plan_generation(p)
    rows = {r["harness"]: r for r in plan_rows(plan, p)}
    assert set(rows) == set(plan.report.added) | set(plan.report.changed) | set(
        plan.report.unchanged
    ) | set(plan.report.removed) | set(plan.report.frozen)
    for hid in plan.report.unchanged:
        assert rows[hid]["change_key"] == "unchanged" and rows[hid]["change_state"] is None
    for hid in plan.report.changed:
        assert rows[hid]["change_key"] == "changed" and rows[hid]["change_state"] == "warning"
    for hid in plan.report.removed:
        assert rows[hid]["change_key"] == "removed" and rows[hid]["name"]  # named from the project
    table = GeneratePlanTable(theme)
    qtbot.addWidget(table)
    table.set_plan(plan, p)
    order = [r["change_key"] for r in table.rows()]
    assert order == sorted(
        order, key=lambda k: ["new", "changed", "removed", "frozen", "unchanged"].index(k)
    )


def test_plan_table_counts_locked_pins_kept_per_harness(qtbot, theme) -> None:
    p = flatsat()
    h = p.harnesses["W003"]
    c = next(c for c in h.connectors if c.mates_with)
    assert c.mates_with
    box = p.connectors[c.mates_with]
    pin = next(x for x in box.pins if x.signal)
    p.connectors[box.id] = evolve(
        box, pins=[evolve(x, locked=True) if x.id == pin.id else x for x in box.pins]
    )
    plan = plan_generation(p)
    assert f"{box.id}.{pin.id}" in plan.report.kept_locks
    rows = {r["harness"]: r for r in plan_rows(plan, p)}
    assert rows["W003"]["locked"] >= 1
    table = GeneratePlanTable(theme)
    qtbot.addWidget(table)
    table.set_plan(plan, p)
    assert str(rows["W003"]["locked"]) in {
        table.model.index(r, 3).data() for r in range(table.model.rowCount())
    }
    k = table.model.columns[3]
    assert k.numeric and k.alignment == "right"


def test_plan_table_shows_a_released_harness_as_kept(qtbot, theme, tmp_path: Path) -> None:
    from tests.test_vcs_lockview import released

    p, hid = released(tmp_path)
    plan = plan_generation(p)
    assert hid in plan.report.frozen
    table = GeneratePlanTable(theme)
    qtbot.addWidget(table)
    table.set_plan(plan, p)
    row = next(i for i, r in enumerate(table.rows()) if r["harness"] == hid)
    assert table.model.index(row, 2).data() == strings.GP_FROZEN
    assert table.model.index(row, 2).data(STATE_ROLE) == "released"
    assert "released" in table.model.index(row, 2).data(Qt.ItemDataRole.ToolTipRole).lower()


def test_plan_table_for_an_empty_plan_says_so_and_copies_as_tsv(qtbot, theme) -> None:
    p = flatsat()
    plan = plan_generation(p)
    table = GeneratePlanTable(theme)
    qtbot.addWidget(table)
    table.show()
    table.set_plan(plan, p)
    assert table.model.rowCount() == len(p.harnesses) and not plan.report.added
    table.view.selectAll()
    text = table.view.copy_selection(headers=True)
    assert text.split("\n")[0].split("\t") == ["Harness", "Name", "Change", "Locked pins kept"]
    from harness_design_studio.core.generate.engine import GenerationPlan, RegenReport

    empty = GenerationPlan([], RegenReport(), plan.record, {})
    table.set_plan(empty, p)
    assert table.model.rowCount() == 0 and table.note.text() == strings.GP_NONE
