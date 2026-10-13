# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SH-6 / SC-20: the project tree (`gui/project_tree.py`). Offscreen, on a bare controller."""

import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtGui import QAction, QColor  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core import configcheck, describe, drc, templates  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.model import Project  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.core.vcs.lockview import locked_objects  # noqa: E402
from harness_design_studio.gui import project_tree, strings  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.project_tree import (  # noqa: E402
    COUNTS_ROLE,
    ProjectTree,
)
from harness_design_studio.gui.tables import natural_key  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.helpers import time_limit  # noqa: E402
from tests.test_change_control import do_release, exported, full, releasable  # noqa: E402


@pytest.fixture
def theme(qapp):
    th = ThemeManager()
    th.apply(qapp, "light", 1.0)
    yield th
    ThemeManager().apply(qapp, "light", 1.0)


@pytest.fixture
def ctl(qapp) -> Iterator[EditorController]:
    c = EditorController(journal_delay_ms=10_000, drc_delay_ms=600_000)
    yield c
    c.release()


@pytest.fixture
def flat(ctl, tmp_path: Path) -> EditorController:
    templates.create_project(tmp_path / "flat", "flatsat")
    ctl._install(load_project(tmp_path / "flat").project, None, None)
    return cast(EditorController, ctl)


def make(ctl, theme, qtbot, **kw) -> ProjectTree:
    tree = ProjectTree(ctl, theme, **kw)
    qtbot.addWidget(tree)
    tree.resize(320, 700)
    tree.show()
    QApplication.processEvents()
    return tree


def root_labels(tree: ProjectTree) -> list[str]:
    m = tree.view.model()
    return [m.index(r, 0).data() for r in range(m.rowCount())]


def addable(ctl: EditorController) -> tuple[str, str, str]:
    """A type and two units the tool accepts as a new link."""
    from harness_design_studio.core import edit
    from harness_design_studio.core.errors import HarnessError

    units = sorted(ctl.project.units)
    for t in sorted(ctl.project.interface_types):
        for a in units:
            for b in units:
                if a < b:
                    try:
                        edit.ops_add_interface(ctl.project, t, a, b)
                    except HarnessError:
                        continue
                    return t, a, b
    raise AssertionError("no link can be added")


class Spy:
    """Counts the structural signals of the tree's model."""

    def __init__(self, tree: ProjectTree) -> None:
        self.inserted: list[int] = []
        self.removed: list[int] = []
        self.resets = 0
        self.changed = 0
        m = tree.model
        m.rowsInserted.connect(lambda _p, a, b: self.inserted.append(b - a + 1))
        m.rowsRemoved.connect(lambda _p, a, b: self.removed.append(b - a + 1))
        m.modelReset.connect(lambda: setattr(self, "resets", self.resets + 1))
        m.dataChanged.connect(lambda *_: setattr(self, "changed", self.changed + 1))


# ---- the roots -----------------------------------------------------------------------------------


def test_the_roots_are_the_seven_groups_in_order(ctl, theme, qtbot) -> None:
    tree = make(ctl, theme, qtbot)
    assert root_labels(tree) == [
        "Units",
        "Interfaces",
        "Harnesses",
        "Parts",
        "Interface types",
        "Configuration",
        "Imports",
    ]


def test_it_is_a_tree_view_over_a_model_not_a_tree_widget(ctl, theme, qtbot) -> None:
    from PySide6.QtWidgets import QTreeView, QTreeWidget

    tree = make(ctl, theme, qtbot)
    assert isinstance(tree.view, QTreeView) and not isinstance(tree.view, QTreeWidget)
    assert tree.view.model() is tree.model


def test_imports_are_leaves_for_every_kind_of_import(ctl, theme, qtbot) -> None:
    tree = make(ctl, theme, qtbot)
    assert tree.child_ids("imports") == ["interfaces", "parts", "lengths", "engineering", "netlist"]
    assert tuple(project_tree.IMPORT_KINDS) == tuple(tree.child_ids("imports"))


def test_an_empty_project_says_what_to_do_in_each_empty_group(ctl, theme, qtbot) -> None:
    ctl._install(new_project("Empty"), None, None)
    tree = make(ctl, theme, qtbot)
    interfaces = tree.model.roots["interfaces"]
    assert [c.name for c in interfaces.children] == [
        "No interfaces yet. Add one with Ctrl+I or import a table."
    ]
    assert tree.child_ids("interfaces") == []  # the hint is not an object
    assert tree.counts("root", "interfaces") == (0, 0, 0)
    for root in ("units", "harnesses"):
        assert tree.model.roots[root].placeholder is not None


def test_the_hint_goes_away_when_the_first_object_arrives_and_comes_back_when_it_leaves(
    ctl, theme, qtbot
) -> None:
    ctl._install(new_project("Empty"), None, None)
    tree = make(ctl, theme, qtbot)
    units = tree.model.roots["units"]
    uid = ctl.add_unit("computer")
    assert uid is not None and units.placeholder is None
    assert tree.child_ids("units") == [uid]
    ctl.undo()
    assert tree.child_ids("units") == [] and units.placeholder is not None


# ---- what the rows show --------------------------------------------------------------------------


def test_objects_are_listed_in_natural_order_of_their_ids(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    p = flat.project
    assert tree.child_ids("units") == sorted(p.units, key=natural_key)
    assert tree.child_ids("interfaces") == sorted(p.interfaces, key=natural_key)
    assert tree.child_ids("harnesses") == sorted(p.harnesses, key=natural_key)
    assert tree.child_ids("parts") == sorted(p.parts, key=natural_key)
    assert tree.child_ids("interface_types") == sorted(p.interface_types, key=natural_key)
    assert tree.child_ids("config") == sorted(p.config, key=natural_key)


def test_a_harness_shows_its_release_state_as_a_chip(flat, theme, qtbot) -> None:
    from dataclasses import replace  # noqa: F401

    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import evolve

    tree = make(flat, theme, qtbot)
    p = flat.project
    hid = sorted(p.harnesses)[0]
    h = p.harnesses[hid]
    assert tree.state_of("harness", hid) == (describe.harness_state(h), "Draft")
    for status, rev, expect in (
        ("in_review", "A", ("in-review", "In review")),
        ("released", "A", ("released", "Released A")),
        ("draft", "B", ("revised", "Revised B")),
    ):
        flat.run("state", [Put("harnesses", evolve(h, status=status, revision=rev))])
        assert tree.state_of("harness", hid) == expect


def test_configuration_shows_placeholder_and_the_values_still_pending(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    p = flat.project
    missing = configcheck.missing(p)
    assert missing and p.placeholder_configs()
    for name in p.config:
        n = sum(m.file == name for m in missing)
        state = tree.state_of("config", name)
        if n:
            assert state == ("pending", f"{n} pending"), name
        elif p.config[name].placeholder:
            assert state == ("pending", "Placeholder"), name
        else:
            assert state is None, name
    assert tree.state_of("root", "config") == ("pending", f"{len(missing)} pending")


def test_a_reviewed_configuration_without_gaps_shows_no_chip(ctl, theme, qtbot) -> None:
    from harness_design_studio.core.commands import SetConfig
    from harness_design_studio.core.model import ConfigFile

    tree = make(ctl, theme, qtbot)
    assert tree.state_of("config", "naming") is None  # reviewed and nothing missing
    ctl.run("flag", [SetConfig(ConfigFile(name="naming", placeholder=True, values={}))])
    assert tree.state_of("config", "naming") == ("pending", "Placeholder")


def test_ids_are_painted_in_the_monospace_font(flat, theme, qtbot) -> None:
    """The delegate's IDs use the theme's mono font (IBM Plex Mono or the system fixed font); the
    names use the interface font."""
    from harness_design_studio.gui.theme import mono_family

    tree = make(flat, theme, qtbot)
    kit = tree.view.itemDelegate().kit(tree.view.font())  # type: ignore[attr-defined]
    assert kit.mono.family() == mono_family() == theme.mono_font().family()
    assert kit.mono.styleHint() == kit.mono.StyleHint.Monospace
    assert kit.base.family() != kit.mono.family() or kit.base.styleHint() == kit.mono.styleHint()
    assert kit.mono.pixelSize() == theme.type("base")


# ---- incremental updates -------------------------------------------------------------------------


def test_adding_a_unit_inserts_one_row_and_selects_it(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    spy = Spy(tree)
    uid = flat.add_unit("computer")
    assert uid is not None
    assert spy.inserted == [1] and spy.removed == [] and spy.resets == 0
    assert tree.has("unit", uid) and tree.current() == ("unit", uid)
    assert tree.child_ids("units") == sorted(flat.project.units, key=natural_key)


def test_a_rename_changes_one_row_without_inserting_or_removing(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    uid = tree.child_ids("units")[0]
    spy = Spy(tree)
    flat.update_unit(uid, name="Brand new name")
    assert spy.inserted == [] and spy.removed == [] and spy.resets == 0
    assert tree.model.find("unit", uid).name.startswith("Brand new name")  # type: ignore[union-attr]


def test_deleting_and_undoing_updates_the_rows(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    uid = tree.child_ids("units")[0]
    flat.select("unit", uid)
    flat.delete_selected()
    assert not tree.has("unit", uid)
    assert tree.child_ids("interfaces") == sorted(flat.project.interfaces, key=natural_key)
    flat.undo()
    assert tree.has("unit", uid)
    assert tree.child_ids("interfaces") == sorted(flat.project.interfaces, key=natural_key)


def test_a_new_interface_appears_in_the_interfaces_group(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    tid, a, b = addable(flat)
    spy = Spy(tree)
    assert flat.add_interface_between(tid, a, b)
    assert spy.inserted == [1]
    assert tree.child_ids("interfaces") == sorted(flat.project.interfaces, key=natural_key)


def test_opening_another_project_replaces_the_rows_and_keeps_the_groups_open(
    flat, theme, qtbot, tmp_path: Path
) -> None:
    tree = make(flat, theme, qtbot)
    assert tree.is_expanded("units")
    flat._install(full(), None, None)
    assert tree.child_ids("units") == sorted(flat.project.units, key=natural_key)
    assert tree.child_ids("harnesses") == sorted(flat.project.harnesses, key=natural_key)
    assert tree.is_expanded("units")
    flat._install(new_project("Empty"), None, None)
    assert tree.child_ids("units") == [] and tree.child_ids("harnesses") == []


def test_the_tree_never_rebuilds_the_model_on_an_edit(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    spy = Spy(tree)
    uid = tree.child_ids("units")[0]
    flat.update_unit(uid, name="x")
    flat.update_unit(uid, notes="y")
    flat.move_unit(uid, 10, 10)
    assert spy.resets == 0 and spy.inserted == [] and spy.removed == []


# ---- problem counts ------------------------------------------------------------------------------


def expected_counts(ctl: EditorController) -> dict[tuple[str, str], list[int]]:
    """Counts worked out the plain way: `drc.locate` per finding."""
    p = ctl.project
    out: dict[tuple[str, str], list[int]] = {}
    for f in ctl.open_findings():
        if f.rule == "unchecked-config" or f.severity == "info":
            continue
        place = drc.locate(p, f.object_id)
        if place is None:
            continue
        out.setdefault(place, [0, 0, 0])[0 if f.severity == "error" else 1] += 1
    return out


def test_every_node_carries_the_errors_and_warnings_of_its_object(flat, theme, qtbot) -> None:
    flat.run_drc_now()
    tree = make(flat, theme, qtbot)
    tree.flush()
    want = expected_counts(flat)
    assert want, "the example should have problems for this test to mean something"
    for (kind, oid), (e, w, _n) in want.items():
        assert tree.counts(kind, oid)[:2] == (e, w), (kind, oid)
    for kind, ids in (
        ("unit", tree.child_ids("units")),
        ("interface", tree.child_ids("interfaces")),
        ("harness", tree.child_ids("harnesses")),
    ):
        for oid in ids:
            if (kind, oid) not in want:
                assert tree.counts(kind, oid)[:2] == (0, 0), (kind, oid)


def test_a_group_adds_up_the_counts_of_its_objects(flat, theme, qtbot) -> None:
    flat.run_drc_now()
    tree = make(flat, theme, qtbot)
    tree.flush()
    for root, kind in (("units", "unit"), ("harnesses", "harness"), ("interfaces", "interface")):
        ids = tree.child_ids(root)
        total = tuple(sum(tree.counts(kind, i)[k] for i in ids) for k in range(3))
        assert tree.counts("root", root) == total, root
    assert sum(tree.counts("root", r)[1] for r in ("units", "harnesses", "interfaces")) > 0


def test_counts_follow_an_edit(flat, theme, qtbot) -> None:
    flat.run_drc_now()
    tree = make(flat, theme, qtbot)
    tree.flush()
    hit = next(u for u in tree.child_ids("units") if tree.counts("unit", u)[1])
    flat.select("unit", hit)
    flat.delete_selected()  # its results are stale now; nothing is attributed to a gone object
    tree.flush()
    assert not tree.has("unit", hit)
    for (kind, oid), (e, w, _n) in expected_counts(flat).items():
        assert tree.counts(kind, oid)[:2] == (e, w), (kind, oid)
    flat.undo()
    tree.flush()
    assert tree.counts("unit", hit)[1] > 0  # back with its undone edit


def test_not_checked_notes_are_counted_on_the_configuration(flat, theme, qtbot) -> None:
    flat.run_drc_now()
    tree = make(flat, theme, qtbot)
    tree.flush()
    notes = [f for f in flat.open_findings() if f.rule == "unchecked-config"]
    assert notes, "the example has checks that could not run"
    assert tree.counts("root", "config")[2] == len(notes)


def test_counts_are_in_words_for_a_screen_reader_and_a_tooltip(flat, theme, qtbot) -> None:
    flat.run_drc_now()
    tree = make(flat, theme, qtbot)
    tree.flush()
    uid = next(u for u in tree.child_ids("units") if tree.counts("unit", u)[1])
    idx = tree.index_for("unit", uid)
    assert idx.data(COUNTS_ROLE) != (0, 0, 0)
    text = idx.data(Qt.ItemDataRole.AccessibleTextRole)
    assert re.search(r"\d+ warning", text), text
    assert re.search(r"\d+ warning", idx.data(Qt.ItemDataRole.ToolTipRole))


def test_counts_are_painted_with_an_icon_and_a_number(flat, theme, qtbot) -> None:
    """The row paints the count with its icon; the same row with the count removed differs."""
    flat.run_drc_now()
    tree = make(flat, theme, qtbot)
    tree.flush()
    uid = next(u for u in tree.child_ids("units") if tree.counts("unit", u)[1])
    tree.select("unit", uid)
    idx = tree.index_for("unit", uid)
    rect = tree.view.visualRect(idx)
    with_counts = tree.view.viewport().grab(rect).toImage()
    node = tree.model.find("unit", uid)
    node.counts = (0, 0, 0)  # type: ignore[union-attr]
    tree.view.viewport().update()
    QApplication.processEvents()
    without = tree.view.viewport().grab(rect).toImage()
    assert with_counts != without


# ---- locks ---------------------------------------------------------------------------------------


@pytest.fixture
def released(ctl, tmp_path: Path):
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    ctl._install(p, None, None)
    return ctl, hid


def test_objects_held_by_a_released_harness_carry_a_lock_with_the_reason(
    released, theme, qtbot
) -> None:
    ctl, hid = released
    tree = make(ctl, theme, qtbot)
    p = ctl.project
    locked = locked_objects(p)
    assert ("harness", hid) in locked
    for kind in ("harness", "interface", "unit", "part", "interface_type", "config"):
        keys = [k for k in locked if k[0] == kind]
        assert keys, kind
        for _, oid in keys:
            reason = tree.lock_of(kind, oid)
            assert reason and hid in reason, (kind, oid)
            idx = tree.index_for(kind, oid)
            assert reason in idx.data(Qt.ItemDataRole.ToolTipRole)
    free = next(i for i in p.interfaces if ("interface", i) not in locked)
    assert tree.lock_of("interface", free) is None


def test_the_released_harness_shows_released_and_locked_together(released, theme, qtbot) -> None:
    ctl, hid = released
    tree = make(ctl, theme, qtbot)
    state = tree.state_of("harness", hid)
    assert state is not None and state[0] == "released" and tree.lock_of("harness", hid)


def test_the_lock_goes_when_the_release_is_undone(released, theme, qtbot) -> None:
    ctl, hid = released
    tree = make(ctl, theme, qtbot)
    assert tree.lock_of("harness", hid)
    # a new revision unlocks (the harness is a draft again)
    from harness_design_studio.core.vcs.release import plan_new_revision

    plan = plan_new_revision(
        ctl.project, hid, by="Ada", comment="Change a connector", when="2026-04-01"
    )
    assert plan.ok
    assert ctl.apply_change(plan, "revised")
    assert tree.lock_of("harness", hid) is None
    assert tree.state_of("harness", hid) == ("revised", "Revised B")


# ---- selection, keyboard, signals ----------------------------------------------------------------


def test_the_tree_follows_the_selection_on_the_canvas(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    uid = tree.child_ids("units")[3]
    flat.select("unit", uid)
    assert tree.current() == ("unit", uid)
    iid = tree.child_ids("interfaces")[2]
    flat.select("interface", iid)
    assert tree.current() == ("interface", iid)
    flat.select(None)
    assert tree.current() is None


def test_following_the_selection_does_not_send_it_back(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    got: list[tuple[str, str]] = []
    tree.selectionRequested.connect(lambda k, i: got.append((k, i)))
    flat.select("unit", tree.child_ids("units")[1])
    assert got == []


def row_rect(tree: ProjectTree, kind: str, oid: str):
    idx = tree.index_for(kind, oid)
    tree.view.scrollTo(idx)
    return tree.view.visualRect(idx).center()


def test_a_click_selects_on_the_canvas_and_says_so(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    got: list[tuple[str, str]] = []
    tree.selectionRequested.connect(lambda k, i: got.append((k, i)))
    uid = tree.child_ids("units")[2]
    QTest.mouseClick(
        tree.view.viewport(), Qt.MouseButton.LeftButton, pos=row_rect(tree, "unit", uid)
    )
    assert got == [("unit", uid)]
    assert flat.selection is not None and flat.selection.id == uid


def test_arrow_keys_move_the_cursor_and_enter_selects(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    got: list[tuple[str, str]] = []
    tree.selectionRequested.connect(lambda k, i: got.append((k, i)))
    first = tree.child_ids("units")[0]
    assert tree.select("unit", first)
    tree.view.setFocus()
    QTest.keyClick(tree.view, Qt.Key.Key_Down)
    second = tree.child_ids("units")[1]
    assert tree.current() == ("unit", second)
    assert got == [] and flat.selection is None  # moving is not selecting
    QTest.keyClick(tree.view, Qt.Key.Key_Return)
    assert got == [("unit", second)]
    assert flat.selection is not None and flat.selection.id == second


def test_enter_on_a_harness_part_or_type_only_reports_it(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    got: list[tuple[str, str]] = []
    tree.selectionRequested.connect(lambda k, i: got.append((k, i)))
    for kind, root in (
        ("harness", "harnesses"),
        ("part", "parts"),
        ("interface_type", "interface_types"),
    ):
        oid = tree.child_ids(root)[0]
        tree.select(kind, oid)
        QTest.keyClick(tree.view, Qt.Key.Key_Return)
        assert got[-1] == (kind, oid)
    assert flat.selection is None


def test_ctrl_enter_and_double_click_open(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    opened: list[tuple[str, str]] = []
    tree.openRequested.connect(lambda k, i: opened.append((k, i)))
    hid = tree.child_ids("harnesses")[0]
    tree.select("harness", hid)
    tree.view.setFocus()
    QTest.keyClick(tree.view, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert opened == [("harness", hid)]
    uid = tree.child_ids("units")[0]
    pos = row_rect(tree, "unit", uid)
    QTest.mouseClick(tree.view.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    QTest.mouseDClick(tree.view.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    assert opened[-1] == ("unit", uid)


def test_right_opens_and_left_closes_a_group(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    tree.view.setFocus()
    idx = tree.index_for("root", "parts")
    tree.view.setCurrentIndex(idx)
    assert not tree.is_expanded("parts")
    QTest.keyClick(tree.view, Qt.Key.Key_Right)
    assert tree.is_expanded("parts")
    QTest.keyClick(tree.view, Qt.Key.Key_Left)
    assert not tree.is_expanded("parts")


def test_enter_on_a_group_opens_and_closes_it(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    idx = tree.index_for("root", "parts")
    tree.view.setCurrentIndex(idx)
    tree.view.setFocus()
    QTest.keyClick(tree.view, Qt.Key.Key_Return)
    assert tree.is_expanded("parts")
    QTest.keyClick(tree.view, Qt.Key.Key_Return)
    assert not tree.is_expanded("parts")


def test_typing_jumps_to_a_name(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    target = tree.child_ids("units")[-1]
    tree.select("unit", tree.child_ids("units")[0])
    tree.view.setFocus()
    QTest.keyClicks(tree.view, target[:3])
    cur = tree.current()
    assert cur is not None and cur[1].startswith(target[:3])


def test_slash_moves_to_the_filter_box(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    tree.view.setFocus()
    QTest.keyClick(tree.view, Qt.Key.Key_Slash)
    assert tree.filter_edit.hasFocus()


def test_import_entries_are_started_with_enter_or_double_click(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    got: list[str] = []
    tree.importRequested.connect(got.append)
    tree.view.setFocus()
    for kind in project_tree.IMPORT_KINDS:
        idx = tree.index_for("import", kind)
        tree.view.setCurrentIndex(idx)
        QTest.keyClick(tree.view, Qt.Key.Key_Return)
    assert got == list(project_tree.IMPORT_KINDS)
    got.clear()
    tree.view.expand(tree.index_for("root", "imports"))
    pos = row_rect(tree, "import", "parts")
    QTest.mouseClick(tree.view.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    assert got == []  # a single click only marks the entry
    QTest.mouseDClick(tree.view.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    assert got == ["parts"]


def test_a_read_only_project_cannot_start_an_import(flat, theme, qtbot) -> None:
    flat.project.read_only = True
    tree = make(flat, theme, qtbot)
    flat.stateChanged.emit()
    got: list[str] = []
    tree.importRequested.connect(got.append)
    idx = tree.index_for("import", "parts")
    tree.view.setCurrentIndex(idx)
    tree.view.setFocus()
    QTest.keyClick(tree.view, Qt.Key.Key_Return)
    assert got == []
    assert not tree.view.model().flags(idx) & Qt.ItemFlag.ItemIsEnabled
    assert "read-only" in idx.data(Qt.ItemDataRole.ToolTipRole)


# ---- filter, add menu, context menu --------------------------------------------------------------


def test_the_filter_shows_only_matching_rows_and_restores_the_groups(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    all_units = tree.child_ids("units")
    opened = {r for r in project_tree.ROOT_ORDER if tree.is_expanded(r)}
    target = all_units[-1]
    tree.set_filter(target)
    shown = [
        tree.proxy.index(r, 0, tree.proxy.index(0, 0)).data(project_tree.ID_ROLE)
        for r in range(tree.proxy.rowCount(tree.proxy.index(0, 0)))
    ]
    assert target in shown and len(shown) < len(all_units)
    tree.set_filter("")
    assert {r for r in project_tree.ROOT_ORDER if tree.is_expanded(r)} == opened
    assert tree.view.model().rowCount() == 7 and tree.view.model() is tree.model


def test_the_filter_matches_names_and_ids_case_insensitively(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    uid = tree.child_ids("units")[0]
    name = flat.project.units[uid].name
    tree.set_filter(name.upper())
    unit_root = tree.proxy.index(0, 0)
    ids = [
        tree.proxy.index(r, 0, unit_root).data(project_tree.ID_ROLE)
        for r in range(tree.proxy.rowCount(unit_root))
    ]
    assert uid in ids


def test_the_add_menu_asks_for_a_unit_or_an_interface(ctl, theme, qtbot) -> None:
    tree = make(ctl, theme, qtbot)
    got: list[str] = []
    tree.addRequested.connect(got.append)
    tree.add_actions["unit"].trigger()
    tree.add_actions["interface"].trigger()
    assert got == ["unit", "interface"]
    assert tree.add_button.text() == "Add" and not tree.add_button.icon().isNull()


def test_the_context_menu_has_the_provider_actions_after_its_own(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    asked: list[tuple[str, str]] = []
    mine = QAction("Do my thing")

    def provider(kind: str, oid: str):
        asked.append((kind, oid))
        return [mine]

    tree.set_context_actions(provider)
    uid = tree.child_ids("units")[0]
    menu = tree.build_menu("unit", uid)
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert asked == [("unit", uid)]
    assert texts[-1] == "Do my thing" and "Copy ID" in texts and "Select on the diagram" in texts
    root_menu = tree.build_menu("root", "units")
    assert "Add unit…" in [a.text() for a in root_menu.actions()]
    next(a for a in menu.actions() if a.text() == "Copy ID").trigger()
    assert QApplication.clipboard().text() == uid


def test_the_context_menu_of_a_group_can_add(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    got: list[str] = []
    tree.addRequested.connect(got.append)
    menu = tree.build_menu("root", "interfaces")
    next(a for a in menu.actions() if a.text().startswith("Add ")).trigger()
    assert got == ["interface"]


# ---- accessibility, themes, settings -------------------------------------------------------------


def test_the_controls_have_names_and_the_rows_read_out_what_they_are(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    assert tree.view.accessibleName() == "Project tree" and tree.view.accessibleDescription()
    assert tree.filter_edit.accessibleName() and tree.add_button.accessibleName()
    assert "/" in tree.filter_edit.toolTip()
    uid = tree.child_ids("units")[0]
    idx = tree.index_for("unit", uid)
    text = idx.data(Qt.ItemDataRole.AccessibleTextRole)
    assert uid in text and "Unit" in text
    hid = tree.child_ids("harnesses")[0]
    htext = tree.index_for("harness", hid).data(Qt.ItemDataRole.AccessibleTextRole)
    assert "Draft" in htext  # the state is in words for a screen reader


def test_it_paints_in_light_and_dark_and_at_other_scales(flat, qapp, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    a, b = tree.child_ids("units")[:2]
    flat.add_interface_between(sorted(flat.project.interface_types)[0], a, b)
    tree.flush()
    images = []
    for mode, scale in (("light", 1.0), ("dark", 1.0), ("light", 1.5)):
        theme.apply(qapp, mode, scale)
        QApplication.processEvents()
        img = tree.grab().toImage()
        assert not img.isNull()
        images.append(img)
        bg = QColor(theme.tokens["bg"])
        inked = sum(
            1
            for x in range(0, img.width(), 3)
            for y in range(0, img.height(), 3)
            if QColor(img.pixel(x, y)) != bg
        )
        assert inked > 50, (mode, scale)
    assert images[0] != images[1]


def test_no_colour_literal_and_no_style_sheet_in_the_tree_module() -> None:
    src = Path(project_tree.__file__).read_text(encoding="utf-8")
    assert not re.search(r"#[0-9A-Fa-f]{6}\b", src) and "setStyleSheet" not in src


def test_open_groups_are_remembered(ctl, theme, qtbot, tmp_path: Path) -> None:
    settings = QSettings(str(tmp_path / "tree.ini"), QSettings.Format.IniFormat)
    tree = make(ctl, theme, qtbot, settings=settings)
    tree.view.setExpanded(tree.index_for("root", "parts"), True)
    tree.view.setExpanded(tree.index_for("root", "units"), False)
    settings.sync()
    again = make(
        ctl,
        theme,
        qtbot,
        settings=QSettings(str(tmp_path / "tree.ini"), QSettings.Format.IniFormat),
    )
    assert again.is_expanded("parts") and not again.is_expanded("units")


def test_every_string_comes_from_the_strings_module() -> None:
    assert strings.TREE_ROOTS["config"] == "Configuration"
    assert set(strings.TREE_IMPORTS) == set(project_tree.IMPORT_KINDS)


# ---- speed (100 units, 800 links) ----------------------------------------------------------------


@pytest.fixture
def big(ctl, theme, qtbot):
    from tools.bench_stress import build

    p: Project = build(units=100, interfaces=800, harnesses=30, wires=3000)
    ctl._install(p, None, None)
    tree = make(ctl, theme, qtbot)
    return ctl, tree


def elapsed_ms(fn) -> float:
    t = time.perf_counter()
    fn()
    QApplication.processEvents()
    return (time.perf_counter() - t) * 1000


def test_the_tree_lists_100_units_and_800_links(big) -> None:
    ctl, tree = big
    assert len(tree.child_ids("units")) == 100 and len(tree.child_ids("interfaces")) == 800


def test_an_edit_stays_under_the_budget_with_the_tree_open(big) -> None:
    ctl, tree = big
    elapsed_ms(lambda: ctl.update_unit("U001", name="warm"))
    t = min(elapsed_ms(lambda k=k: ctl.update_unit("U001", name=f"n{k}")) for k in range(3))
    assert t < time_limit(100), t


def test_the_tree_itself_takes_a_small_part_of_the_edit_budget(big) -> None:
    from harness_design_studio.gui.controller import Delta

    ctl, tree = big
    ctl.update_unit("U001", name="warm")
    tree.flush()
    t0 = time.perf_counter()
    tree._on_changed(Delta(units={"U001"}))
    took = (time.perf_counter() - t0) * 1000
    assert took < time_limit(30), took


def test_adding_a_unit_stays_under_the_budget_and_inserts_one_row(big) -> None:
    ctl, tree = big
    spy = Spy(tree)
    t = elapsed_ms(lambda: ctl.add_unit("computer"))
    assert spy.inserted == [1] and spy.resets == 0
    assert t < time_limit(150), t


def test_a_move_does_not_rebuild_any_row(big) -> None:
    ctl, tree = big
    spy = Spy(tree)
    ctl.move_unit("U002", 400, 400)
    assert spy.inserted == [] and spy.removed == [] and spy.resets == 0


def test_selecting_a_row_far_down_the_list_is_fast(big) -> None:
    ctl, tree = big
    iid = tree.child_ids("interfaces")[700]
    t = min(
        elapsed_ms(lambda k=k: ctl.select("interface", tree.child_ids("interfaces")[700 - k]))
        for k in range(3)
    )
    assert tree.current() is not None
    assert t < time_limit(60), t
    assert iid


def test_counts_of_a_big_project_match_the_findings(big) -> None:
    """About 12,000 findings (wire and verifier errors, a part warning) sorted onto their rows."""
    ctl, tree = big
    ctl.run_drc_now()
    assert ctl.findings_are_many() or len(ctl.findings()) > 1000
    t0 = time.perf_counter()
    tree.flush()
    took = (time.perf_counter() - t0) * 1000
    want = expected_counts(ctl)
    assert sum(v[0] for v in want.values()) > 1000
    for (kind, oid), (e, w, _n) in want.items():
        assert tree.counts(kind, oid)[:2] == (e, w), (kind, oid)
    assert took < time_limit(150), took  # sorting thousands of findings onto 100 + 800 + 30 rows


def test_with_many_findings_the_counts_follow_the_edit_on_a_short_timer(big, qtbot) -> None:
    ctl, tree = big
    ctl.run_drc_now()
    tree.flush()
    t0 = time.perf_counter()
    ctl.update_unit("U001", name="n1")  # no event loop: the short timer cannot fire inside it
    t = (time.perf_counter() - t0) * 1000
    assert t < time_limit(100), t
    assert not tree.model.counts_current()  # not counted inside the edit
    qtbot.waitUntil(tree.model.counts_current, timeout=5000)


def test_a_settings_free_tree_leaves_no_files(ctl, theme, qtbot, tmp_path: Path) -> None:
    make(ctl, theme, qtbot)
    assert not list(tmp_path.iterdir())


def test_every_interactive_widget_of_the_tree_has_a_name(flat, theme, qtbot) -> None:
    """The same rule tests/test_accessibility.py applies to the whole window."""
    from PySide6.QtWidgets import (
        QAbstractButton,
        QAbstractItemView,
        QComboBox,
        QHeaderView,
        QLineEdit,
        QWidget,
    )

    tree = make(flat, theme, qtbot)
    bad = []
    for w in tree.findChildren(QWidget):
        if (
            isinstance(w, QAbstractButton | QLineEdit | QComboBox | QAbstractItemView)
            and not isinstance(w, QHeaderView)
            and w.isVisibleTo(tree)
        ):
            name = w.accessibleName() or str(getattr(w, "text", lambda: "")())
            if not name.strip():
                bad.append(f"{type(w).__name__} {w.objectName()}")
    assert not bad, bad


def test_escape_clears_the_filter_and_then_goes_back_to_the_tree(flat, theme, qtbot) -> None:
    tree = make(flat, theme, qtbot)
    tree.filter_edit.setFocus()
    QTest.keyClicks(tree.filter_edit, "OBC")
    assert tree.filter_edit.text() == "OBC"
    QTest.keyClick(tree.filter_edit, Qt.Key.Key_Escape)
    assert tree.filter_edit.text() == "" and tree.view.model() is tree.model
    QTest.keyClick(tree.filter_edit, Qt.Key.Key_Escape)
    assert tree.view.hasFocus()
    tree.filter_edit.setFocus()
    QTest.keyClick(tree.filter_edit, Qt.Key.Key_Down)
    assert tree.view.hasFocus()


def test_an_edit_elsewhere_does_not_scroll_the_tree_back_to_the_selection(big) -> None:
    ctl, tree = big
    tree.view.resize(300, 300)
    ctl.select("unit", "U001")
    bar = tree.view.verticalScrollBar()
    bar.setValue(bar.maximum())
    away = bar.value()
    assert away > 0
    ctl.update_unit("U050", name="Elsewhere")
    QApplication.processEvents()
    assert bar.value() == away
    ctl.select("unit", "U099")
    QApplication.processEvents()
    assert tree.current() == ("unit", "U099")
