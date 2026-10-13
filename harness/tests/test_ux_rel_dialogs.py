# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SC-14 / SC-15: the release dialog lists what it will lock, the revise dialog explains what becomes
editable, and OK says in words what it still needs. Driven offscreen on the flatsat example."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QModelIndex, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QTreeView  # noqa: E402

from harness_design_studio.core.vcs.lockview import release_locks  # noqa: E402
from harness_design_studio.gui import lock_tree, strings  # noqa: E402
from harness_design_studio.gui.dialogs import ChangeDialog  # noqa: E402
from tests.ux_rel import flatsat_controller, release_all, themed  # noqa: E402


@pytest.fixture
def ctl(qtbot, tmp_path: Path):
    themed()
    return flatsat_controller(tmp_path)


def top_rows(tree: QTreeView) -> dict[str, QModelIndex]:
    model = tree.model()
    return {str(model.index(r, 0).data()): model.index(r, 0) for r in range(model.rowCount())}


def release_dialog(ctl, hid="W001", **kw) -> ChangeDialog:
    p = ctl.project
    dlg = ChangeDialog.for_release(
        None,
        p,
        hid,
        strings.RELEASE_TITLE.format(hid),
        by="Ada",
        blockers=[],
        placeholders=p.placeholder_configs(),
        unapproved_parts=["EX-WIRE-SINGLE"],
        **kw,
    )
    return dlg


def test_the_release_dialog_lists_what_it_will_lock(qtbot, ctl) -> None:
    dlg = release_dialog(ctl)
    qtbot.addWidget(dlg)
    dlg.show()
    counts = release_locks(ctl.project, "W001").counts()
    text = dlg.locks_summary.text()
    assert text.startswith("This release locks: ")
    for key in ("wires", "pins", "interfaces", "parts", "interface_types", "config_files"):
        assert lock_tree.plural(counts[key], key) in text
    assert "18 wires" in text and "1 interface type," in text  # W001 on flatsat
    assert dlg.locks_tree.isVisible()
    rows = top_rows(dlg.locks_tree)
    assert f"Wires ({counts['wires']})" in rows
    assert f"Config files ({counts['config_files']})" in rows
    # every wire of the harness is in the tree, below its group
    model = dlg.locks_tree.model()
    wires = rows[f"Wires ({counts['wires']})"]
    assert model.rowCount(wires) == counts["wires"]


def test_placeholder_config_values_are_shown_as_pending_not_as_data(qtbot, ctl) -> None:
    dlg = release_dialog(ctl)
    qtbot.addWidget(dlg)
    assert "Still placeholders when released" in dlg.locks_summary.text()
    model = dlg.locks_tree.model()
    group = next(i for t, i in top_rows(dlg.locks_tree).items() if t.startswith("Config files"))
    files = [model.index(r, 0, group) for r in range(model.rowCount(group))]
    shown = [str(f.data()) for f in files]
    assert any("placeholder values" in s for s in shown)
    # a frozen key that has no value is listed as pending (own icon, italic), never as "None"
    pending = [
        model.index(r, 0, f)
        for f in files
        for r in range(model.rowCount(f))
        if "not set" in str(model.index(r, 0, f).data())
    ]
    assert pending
    for idx in pending:
        assert not idx.data(Qt.ItemDataRole.DecorationRole).isNull()
        assert idx.data(Qt.ItemDataRole.FontRole).italic()
        assert "None" not in str(idx.data())


def test_the_lock_tree_opens_with_the_keyboard(qtbot, ctl) -> None:
    dlg = release_dialog(ctl)
    qtbot.addWidget(dlg)
    dlg.show()
    tree = dlg.locks_tree
    tree.setFocus()
    tree.setCurrentIndex(tree.model().index(0, 0))
    assert not tree.isExpanded(tree.model().index(0, 0))
    QTest.keyClick(tree, Qt.Key.Key_Right)
    assert tree.isExpanded(tree.model().index(0, 0))
    assert tree.accessibleName() == strings.RELEASE_LOCKS_TREE


def test_the_revise_dialog_explains_what_becomes_editable(qtbot, ctl) -> None:
    assert release_all(ctl) == ["W001", "W003"]
    dlg = ChangeDialog.for_revise(None, ctl.project, "W001", strings.NEW_REV_TITLE.format("W001"), by="Ada")  # fmt: skip
    qtbot.addWidget(dlg)
    dlg.show()
    assert strings.READY_TO_RELEASE not in dlg.status.text()
    assert "revision B" in dlg.status.text() and "revision A" in dlg.status.text()
    assert "What becomes editable:" in dlg.locks_summary.text()
    # W003 is released too and shares parts and config with W001: those stay locked, and the
    # dialog says so instead of promising they become editable
    unlocks = lock_tree.revision_unlocks(ctl.project, "W001")
    assert unlocks.still_locked
    assert "Still locked because another released harness uses it" in dlg.locks_summary.text()
    names = list(top_rows(dlg.locks_tree))
    assert any(n.startswith("Wires") for n in names)


def test_what_becomes_editable_matches_the_locks_after_the_revision(qtbot, ctl) -> None:
    from harness_design_studio.core.vcs.lockview import locked_objects
    from harness_design_studio.core.vcs.release import plan_new_revision

    release_all(ctl)
    before = locked_objects(ctl.project)
    only_w001 = {k for k, refs in before.items() if {r.harness_id for r in refs} == {"W001"}}
    unlocks = lock_tree.revision_unlocks(ctl.project, "W001")
    assert unlocks.editable_count == len(only_w001) > 0
    plan = plan_new_revision(ctl.project, "W001", by="Ada", comment="Second look", when="2026-03-02")  # fmt: skip
    assert ctl.apply_change(plan, "revised")
    after = locked_objects(ctl.project)
    assert not (only_w001 & set(after))  # everything it called editable is editable now
    kept = {k for k, refs in before.items() if "W001" in {r.harness_id for r in refs}} - only_w001
    assert kept <= set(after)  # and what it called still locked is still locked


def test_ok_says_what_is_missing_instead_of_staying_silently_disabled(qtbot, ctl) -> None:
    dlg = release_dialog(ctl)
    qtbot.addWidget(dlg)
    dlg.show()
    assert not dlg.ok.isEnabled()
    assert dlg.hint.isVisible()
    assert "at least 10 characters in the comment (10 more to go)" in dlg.hint.text()
    assert strings.RELEASE_CONFIRM in dlg.hint.text()
    dlg.comment.setPlainText("Release")
    assert "(3 more to go)" in dlg.hint.text()
    assert dlg.ok.toolTip() == dlg.hint.text()  # a disabled button explains itself on hover too
    dlg.comment.setPlainText("Release for the CDR")
    dlg.placeholder_reason.setText("Example values for a test")
    assert "unapproved parts" in dlg.hint.text()  # the placeholder reason is in, this one is not
    dlg.parts_reason.setText("Example parts for a test")
    assert dlg.ok.isEnabled()
    assert dlg.hint.text() == strings.HINT_OK
    dlg.by.setText("")
    assert not dlg.ok.isEnabled() and strings.HINT_NAME in dlg.hint.text()


def test_blockers_are_named_in_the_hint(qtbot, ctl) -> None:
    dlg = ChangeDialog(None, "Release W001", by="Ada", blockers=["Export first."])
    qtbot.addWidget(dlg)
    assert not dlg.ok.isEnabled()
    assert strings.HINT_BLOCKERS in dlg.hint.text()


def test_the_old_calls_still_work(qtbot) -> None:
    """The main window builds the dialog without the new arguments; nothing changes for it."""
    dlg = ChangeDialog(None, "Submit W001 for review", by="Ada", blockers=[], ask_comment=False)
    qtbot.addWidget(dlg)
    assert dlg.ok.isEnabled() and not dlg.locks_tree.isVisibleTo(dlg)
    assert dlg.status.text() == ""
