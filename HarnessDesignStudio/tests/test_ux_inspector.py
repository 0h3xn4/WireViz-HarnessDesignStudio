# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SH-8 / CV-7 / SC-8: the inspector (`gui/inspector.py`): lock banner, locked fields, Used in,
properties of harnesses, parts, types and configuration, the Why and Problems tabs."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHeaderView,
    QLineEdit,
    QWidget,
)

from harness_design_studio.core import configcheck, describe, templates  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.usedby import used_by  # noqa: E402
from harness_design_studio.core.vcs.lockview import (  # noqa: E402
    field_lock_reason,
    lock_reason,
    locked_objects,
)
from harness_design_studio.core.vcs.release import plan_new_revision  # noqa: E402
from harness_design_studio.gui import inspector as ins  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.inspector import Inspector  # noqa: E402
from harness_design_studio.gui.panels import ProblemsPanel, PropertiesPanel  # noqa: E402
from harness_design_studio.gui.states import StateChip  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from harness_design_studio.gui.why_panel import WhyPanel  # noqa: E402
from tests.test_change_control import do_release, exported, full, releasable  # noqa: E402
from tests.test_ux_tree import addable  # noqa: E402


@pytest.fixture
def theme(qapp):
    th = ThemeManager()
    th.apply(qapp, "light", 1.0)
    yield th
    ThemeManager().apply(qapp, "light", 1.0)


@pytest.fixture
def ctl(qapp, tmp_path: Path) -> Iterator[EditorController]:
    c = EditorController(journal_delay_ms=10_000, drc_delay_ms=600_000)
    templates.create_project(tmp_path / "flat", "flatsat")
    c._install(load_project(tmp_path / "flat").project, None, None)
    yield c
    c.release()


@pytest.fixture
def released(qapp, tmp_path: Path) -> Iterator[tuple[EditorController, str]]:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    c = EditorController(journal_delay_ms=10_000, drc_delay_ms=600_000)
    c._install(p, None, None)
    yield c, hid
    c.release()


def make(ctl, theme, qtbot, **kw) -> Inspector:
    w = Inspector(ctl, theme, **kw)
    qtbot.addWidget(w)
    w.resize(340, 760)
    w.show()
    QApplication.processEvents()
    return w


def rows_of(table) -> list[dict[str, Any]]:
    """The rows (dicts) behind a TableView."""
    return cast(list[dict[str, Any]], table.source.rows())


def locked_of(ctl, kind: str) -> str:
    return next(i for (k, i) in sorted(locked_objects(ctl.project)) if k == kind)


def free_of(ctl, kind: str) -> str:
    locked = locked_objects(ctl.project)
    table = {"unit": ctl.project.units, "interface": ctl.project.interfaces}[kind]
    return str(next(i for i in sorted(table) if (kind, i) not in locked))


# ---- tabs ----------------------------------------------------------------------------------------


def test_three_tabs_in_the_order_inspector_why_problems(ctl, theme, qtbot) -> None:
    w = make(ctl, theme, qtbot)
    assert [w.tabs.tabText(i) for i in range(3)] == ["Inspector", "Why", "Problems"]
    assert isinstance(w.props, PropertiesPanel) and isinstance(w.why, WhyPanel)
    w.show_tab("why")
    assert w.tabs.currentIndex() == 1
    w.show_tab("inspector")
    assert w.tabs.currentIndex() == 0


def test_it_wraps_the_properties_panel_it_is_given(ctl, theme, qtbot) -> None:
    props = PropertiesPanel(ctl, theme)
    w = make(ctl, theme, qtbot, props=props)
    assert w.props is props and w.stack.indexOf(props) == 0
    uid = next(iter(ctl.project.units))
    ctl.select("unit", uid)
    assert "name" in props.fields  # the form is the existing one


def test_the_problems_tab_hosts_the_panel_that_was_handed_in(ctl, theme, qtbot) -> None:
    problems = ProblemsPanel(ctl)
    w = make(ctl, theme, qtbot, problems=problems)
    assert w.problems_panel() is problems
    assert problems.parent() is w._problems_host
    w.show_tab("problems")
    QApplication.processEvents()
    assert problems.isVisible()


def test_the_problems_can_be_attached_later_and_the_tab_shows_their_number(
    ctl, theme, qtbot
) -> None:
    w = make(ctl, theme, qtbot)
    assert w.problems_panel() is None and not w._problems_hint.isHidden()
    problems = ProblemsPanel(ctl)
    ctl.run_drc_now()
    w.set_problems(problems)
    errors, warnings = problems.counts()
    assert errors + warnings > 0
    assert w.tabs.tabText(2) == f"Problems ({errors + warnings})"
    assert w._problems_hint.isHidden()


# ---- the lock banner (CV-7) ----------------------------------------------------------------------


def test_a_free_object_has_no_banner(ctl, theme, qtbot) -> None:
    w = make(ctl, theme, qtbot)
    ctl.select("unit", next(iter(ctl.project.units)))
    assert not w.banner.isVisibleTo(w)


def test_a_locked_link_shows_who_holds_it_and_how_to_revise(released, theme, qtbot) -> None:
    ctl, hid = released
    w = make(ctl, theme, qtbot)
    iid = locked_of(ctl, "interface")
    ctl.select("interface", iid)
    assert w.banner.isVisibleTo(w)
    reason = lock_reason(ctl.project, "interface", iid)
    assert reason and reason in w.banner.sentence.text()
    assert w.banner.chip.state() == "released"
    assert hid in (w.banner.chip.text() or "") and ctl.project.harnesses[hid].revision in (
        w.banner.chip.text() or ""
    )
    assert "Names and notes can still be changed" in w.banner.sentence.text()
    assert w.banner.button.isVisibleTo(w) and w.banner.button.text() == "Start new revision"
    assert w.banner.button.accessibleName() and hid in w.banner.button.toolTip()


def test_the_revise_button_names_the_harness(released, theme, qtbot) -> None:
    ctl, hid = released
    w = make(ctl, theme, qtbot)
    got: list[str] = []
    w.reviseRequested.connect(got.append)
    ctl.select("interface", locked_of(ctl, "interface"))
    w.banner.button.click()
    assert got == [hid]


def test_a_released_harness_banner_and_the_other_states(released, theme, qtbot) -> None:
    ctl, hid = released
    w = make(ctl, theme, qtbot)
    w.show_object("harness", hid)
    assert w.banner.chip.state() == "released" and w.banner.button.isVisibleTo(w)
    other = next(h for h in ctl.project.harnesses if h != hid)
    w.show_object("harness", other)
    assert w.banner.chip.state() == "draft" and not w.banner.button.isVisibleTo(w)
    assert other in w.banner.sentence.text()


def test_banner_for_covers_every_state_without_qt() -> None:
    from harness_design_studio.core.model import evolve

    p = full()
    h = next(iter(p.harnesses.values()))
    for status, rev, state in (
        ("draft", "A", "draft"),
        ("in_review", "A", "in-review"),
        ("draft", "B", "revised"),
    ):
        p.harnesses[h.id] = evolve(h, status=status, revision=rev)
        info = ins.banner_for(p, "harness", h.id)
        assert info is not None and info.state == state and info.revise is None
    assert ins.banner_for(p, "unit", next(iter(p.units))) is None
    assert ins.banner_for(p, "harness", "nope") is None
    assert describe.harness_state(p.harnesses[h.id]) == "revised"


def test_the_read_only_project_cannot_start_a_revision(released, theme, qtbot) -> None:
    ctl, hid = released
    ctl.project.read_only = True
    w = make(ctl, theme, qtbot)
    ctl.select("interface", locked_of(ctl, "interface"))
    assert not w.banner.button.isEnabled()


# ---- locked fields -------------------------------------------------------------------------------


def test_forbidden_fields_are_disabled_with_the_reason_and_cosmetic_ones_stay(
    released, theme, qtbot
) -> None:
    ctl, _ = released
    w = make(ctl, theme, qtbot)
    iid = locked_of(ctl, "interface")
    ctl.select("interface", iid)
    project = ctl.project
    for key in ("max_current_a", "voltage_v"):
        field = w.props.fields[key]
        reason = field_lock_reason(project, "interface", iid, key)
        assert reason and not field.isEnabled() and field.toolTip() == reason, key
    chain = w.props.findChild(QComboBox, "if-chain")
    assert chain is not None and not chain.isEnabled()
    assert chain.toolTip() == field_lock_reason(project, "interface", iid, "redundancy")
    for key in ("name", "requirement_id"):  # cosmetic: still editable
        assert w.props.fields[key].isEnabled(), key
        assert field_lock_reason(project, "interface", iid, key) is None


def test_a_locked_unit_keeps_only_its_name_editable(released, theme, qtbot) -> None:
    ctl, _ = released
    w = make(ctl, theme, qtbot)
    uid = locked_of(ctl, "unit")
    ctl.select("unit", uid)
    assert w.props.fields["name"].isEnabled()
    assert not w.props.fields["id"].isEnabled()
    side = w.props.findChild(QComboBox, "unit-side")
    assert side is not None and not side.isEnabled() and side.toolTip()


def test_a_free_object_of_a_project_with_a_release_is_fully_editable(
    released, theme, qtbot
) -> None:
    ctl, _ = released
    w = make(ctl, theme, qtbot)
    iid = free_of(ctl, "interface")
    ctl.select("interface", iid)
    assert all(w.props.fields[k].isEnabled() for k in ("name", "max_current_a", "voltage_v"))
    chain = w.props.findChild(QComboBox, "if-chain")
    assert chain is not None and chain.isEnabled()


def test_expert_connector_parts_of_a_locked_unit_are_disabled(released, theme, qtbot) -> None:
    ctl, _ = released
    ctl.set_mode("expert")
    w = make(ctl, theme, qtbot)
    uid = locked_of(ctl, "unit")
    ctl.select("unit", uid)
    parts = [c for c in w.props.findChildren(QComboBox) if c.objectName().startswith("part-")]
    assert parts
    locked_boxes = {i for (k, i) in locked_objects(ctl.project) if k == "box_connector"}
    for combo in parts:
        cid = combo.objectName().removeprefix("part-")
        assert combo.isEnabled() == (cid not in locked_boxes), cid


def test_a_new_revision_frees_the_fields_again(released, theme, qtbot) -> None:
    ctl, hid = released
    w = make(ctl, theme, qtbot)
    iid = locked_of(ctl, "interface")
    ctl.select("interface", iid)
    assert not w.props.fields["voltage_v"].isEnabled()
    plan = plan_new_revision(ctl.project, hid, by="Ada", comment="Change a link", when="2026-04-01")
    assert plan.ok and ctl.apply_change(plan, "revised")
    QApplication.processEvents()
    assert w.props.fields["voltage_v"].isEnabled()
    assert not w.banner.isVisibleTo(w)


def test_the_form_can_still_be_used_after_the_lock_is_removed(released, theme, qtbot) -> None:
    ctl, hid = released
    w = make(ctl, theme, qtbot)
    iid = locked_of(ctl, "interface")
    ctl.select("interface", iid)
    plan = plan_new_revision(ctl.project, hid, by="Ada", comment="Change a link", when="2026-04-01")
    ctl.apply_change(plan, "revised")
    field = w.props.fields["voltage_v"]
    field.setText("12")  # type: ignore[attr-defined]
    field.editingFinished.emit()  # type: ignore[attr-defined]
    assert ctl.project.interfaces[iid].voltage_v == 12


# ---- Used in -------------------------------------------------------------------------------------


def test_used_in_lists_where_an_interface_is_used(ctl, theme, qtbot) -> None:
    w = make(ctl, theme, qtbot)
    ctl.select("interface", "IF-010")
    w.flush()
    uses = used_by(ctl.project, "interface", "IF-010")
    rows = rows_of(w.used_table)
    assert [r["id"] for r in rows] == [u.id for u in uses]
    assert {r["kind"] for r in rows} >= {"Device", "Harness", "Wire"}
    assert w.used_title.text() == f"USED IN ({len(uses)})"
    assert w.used_table.isVisibleTo(w) and not w.used_none.isVisibleTo(w)


def test_used_in_for_a_unit_part_and_type(ctl, theme, qtbot) -> None:
    w = make(ctl, theme, qtbot)
    uid = next(iter(ctl.project.units))
    ctl.select("unit", uid)
    w.flush()
    assert w.used_table.source.rowCount() == len(used_by(ctl.project, "unit", uid)) > 0
    part = ctl.project.harnesses["W001"].connectors[0].part_id
    w.show_object("part", part)
    w.flush()
    assert w.used_table.source.rowCount() == len(used_by(ctl.project, "part", part)) > 0
    tid = ctl.project.interfaces["IF-010"].type_id
    w.show_object("interface_type", tid)
    w.flush()
    assert w.used_table.source.rowCount() == len(used_by(ctl.project, "interface_type", tid)) > 0


def test_something_nobody_uses_says_so(ctl, theme, qtbot) -> None:
    from harness_design_studio.core.commands import Delete

    w = make(ctl, theme, qtbot)
    free = next(pid for pid in ctl.project.parts if not used_by(ctl.project, "part", pid))
    w.show_object("part", free)
    w.flush()
    assert w.used_none.isVisibleTo(w) and not w.used_table.isVisibleTo(w)
    assert Delete is not None


def test_used_in_is_hidden_when_nothing_is_selected_and_for_configuration(
    ctl, theme, qtbot
) -> None:
    w = make(ctl, theme, qtbot)
    assert not w.used_box.isVisibleTo(w)
    w.show_object("config", "derating")
    assert not w.used_box.isVisibleTo(w)


def test_opening_a_used_in_row_asks_to_show_it(ctl, theme, qtbot) -> None:
    w = make(ctl, theme, qtbot)
    got: list[tuple[str, str]] = []
    w.showRequested.connect(lambda k, i: got.append((k, i)))
    ctl.select("interface", "IF-010")
    w.flush()
    w.used_table.setFocus()
    w.used_table.selectRow(0)
    w.used_table.setCurrentIndex(w.used_table.proxy.index(0, 0))
    QTest.keyClick(w.used_table, Qt.Key.Key_Return)
    assert len(got) == 1 and got[0][1] == rows_of(w.used_table)[0]["id"]


def test_used_in_follows_an_edit(ctl, theme, qtbot) -> None:
    w = make(ctl, theme, qtbot)
    tid, a, b = addable(ctl)
    ctl.select("unit", a)
    w.flush()
    before = w.used_table.source.rowCount()
    assert ctl.add_interface_between(tid, a, b)
    ctl.select("unit", a)
    qtbot.waitUntil(lambda: w.used_table.source.rowCount() > before, timeout=3000)


# ---- properties of harnesses, parts, types and configuration -------------------------------------


def test_a_harness_shows_its_state_chip_in_a_table(ctl, theme, qtbot) -> None:
    w = make(ctl, theme, qtbot)
    w.show_object("harness", "W001")
    assert w.stack.currentIndex() == 1
    rows = {r["name"]: r for r in rows_of(w.facts_table)}
    assert rows["State"]["state"] == "draft" and rows["State"]["status"] == "Draft"
    assert rows["Wires"]["value"] == str(len(ctl.project.harnesses["W001"].wires))


def test_configuration_shows_each_engineering_value_with_its_status(released, theme, qtbot) -> None:
    ctl, _ = released
    w = make(ctl, theme, qtbot)
    p = ctl.project
    # make three kinds of value in the derating file: not set, set but unreviewed, locked
    values = [
        v for v in configcheck.engineering_values(p, include_optional=True) if v.file == "derating"
    ]
    w.show_object("config", "derating")
    rows = {r["name"]: r for r in rows_of(w.facts_table)}
    assert "Review" in rows and rows["Review"]["state"] == "pending"
    assert rows["Review"]["status"] == "Placeholder"
    assert len(rows) == len(values) + 1
    for v in values:
        row = rows[v.label]
        if v.locked:
            assert row["state"] == "locked" and row["tip"] == v.locked
        elif v.missing:
            assert (row["state"], row["status"]) == ("pending", "Not set")
        elif v.placeholder:
            assert (row["state"], row["status"]) == ("pending", "Unreviewed")
        else:
            assert row["state"] is None
    assert any(r["state"] == "locked" for r in rows.values()), "a release freezes derating values"


def test_configuration_without_engineering_values_still_shows_its_review_flag(
    ctl, theme, qtbot
) -> None:
    w = make(ctl, theme, qtbot)
    w.show_object("config", "naming")
    facts = rows_of(w.facts_table)
    assert len(facts) == 1 and facts[0]["name"] == "Review"
    assert facts[0]["state"] is None  # reviewed


def test_a_part_and_a_type_show_their_facts_and_example_data_is_marked(ctl, theme, qtbot) -> None:
    w = make(ctl, theme, qtbot)
    part = sorted(ctl.project.parts)[0]
    w.show_object("part", part)
    states = {r["state"] for r in rows_of(w.facts_table)}
    assert states & {"pass", "pending", "fail"}  # the approval
    if ctl.project.parts[part].unverified:
        assert "not-checked" in states
    tid = sorted(ctl.project.interface_types)[0]
    w.show_object("interface_type", tid)
    assert w.facts_table.source.rowCount() >= 4


def test_pointing_at_a_gone_object_goes_back_to_the_form(ctl, theme, qtbot) -> None:
    w = make(ctl, theme, qtbot)
    w.show_object("harness", "W001")
    from harness_design_studio.core.commands import Delete

    ctl.run("gone", [Delete("harnesses", "W001")])
    QApplication.processEvents()
    assert w.stack.currentWidget() is w.props


def test_a_selection_on_the_canvas_takes_over_again(ctl, theme, qtbot) -> None:
    w = make(ctl, theme, qtbot)
    w.show_object("harness", "W001")
    assert w.current() == ("harness", "W001")
    uid = next(iter(ctl.project.units))
    ctl.select("unit", uid)
    assert w.current() == ("unit", uid) and w.stack.currentWidget() is w.props


def test_show_object_of_a_unit_selects_it_and_of_a_wire_feeds_the_why_tab(
    ctl, theme, qtbot
) -> None:
    w = make(ctl, theme, qtbot)
    uid = sorted(ctl.project.units)[1]
    w.show_object("unit", uid, tab="inspector")
    assert ctl.selection is not None and ctl.selection.id == uid
    wid = ctl.project.harnesses["W001"].wires[0].id
    w.show_object("wire", wid, tab="why")
    assert w.why.shown() == ("wire", wid) and w.tabs.currentIndex() == 1


# ---- accessibility -------------------------------------------------------------------------------


def label_of(w: QWidget) -> str:
    name = w.accessibleName()
    if name:
        return name
    text = getattr(w, "text", None)
    return str(text()) if callable(text) else ""


def test_every_interactive_widget_has_an_accessible_name(released, theme, qtbot) -> None:
    ctl, hid = released
    problems = ProblemsPanel(ctl)
    w = make(ctl, theme, qtbot, problems=problems)
    ctl.set_mode("expert")
    interactive = (QAbstractButton, QLineEdit, QComboBox, QAbstractItemView)
    for kind, oid in (("interface", locked_of(ctl, "interface")), ("unit", locked_of(ctl, "unit"))):
        ctl.select(kind, oid)
        w.flush()
        for tab in ("inspector", "why", "problems"):
            w.show_tab(tab)
            QApplication.processEvents()
            bad = [
                f"{type(c).__name__} {c.objectName()}"
                for c in w.findChildren(QWidget)
                if isinstance(c, interactive)
                and not isinstance(c, QHeaderView)
                and c.isVisibleTo(w)
                and not label_of(c).strip()
            ]
            assert not bad, (kind, tab, bad)
    for kind in ("harness", "config", "part"):
        w.show_object(
            kind, {"harness": hid, "config": "derating", "part": sorted(ctl.project.parts)[0]}[kind]
        )
        w.show_tab("inspector")
        bad = [
            type(c).__name__
            for c in w.findChildren(QWidget)
            if isinstance(c, interactive)
            and not isinstance(c, QHeaderView)
            and c.isVisibleTo(w)
            and not label_of(c).strip()
        ]
        assert not bad, (kind, bad)


def test_the_banner_chip_reads_out_its_state(released, theme, qtbot) -> None:
    ctl, _ = released
    w = make(ctl, theme, qtbot)
    ctl.select("interface", locked_of(ctl, "interface"))
    chip = w.banner.findChild(StateChip)
    assert chip is not None and "Released" in chip.accessibleName()
    assert w.banner.accessibleName()


def test_no_colour_literal_and_no_style_sheet_in_the_new_modules() -> None:
    import re

    from harness_design_studio.gui import why_panel

    for module in (ins, why_panel):
        src = Path(str(module.__file__)).read_text(encoding="utf-8")
        assert not re.search(r"#[0-9A-Fa-f]{6}\b", src) and "setStyleSheet" not in src
