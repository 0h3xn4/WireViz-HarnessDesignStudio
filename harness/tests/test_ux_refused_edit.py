# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""CV-9: when the controller refuses an edit (a released harness holds the object), the form must
not keep showing the rejected value."""

from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit  # noqa: E402

from harness_design_studio.core.vcs.lockview import locked_objects  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.panels import PropertiesPanel  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.test_change_control import do_release, exported, full, releasable  # noqa: E402


@pytest.fixture
def theme(qapp):
    th = ThemeManager()
    th.apply(qapp, "light", 1.0)
    yield th
    ThemeManager().apply(qapp, "light", 1.0)


@pytest.fixture
def released(qapp, tmp_path: Path) -> Iterator[tuple[EditorController, str]]:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    ctl = EditorController(journal_delay_ms=10_000, drc_delay_ms=600_000)
    ctl._install(p, None, None)
    yield ctl, hid
    ctl.release()


def panel(ctl, theme, qtbot) -> PropertiesPanel:
    pp = PropertiesPanel(ctl, theme)
    qtbot.addWidget(pp)
    pp.resize(320, 700)
    pp.show()
    QApplication.processEvents()
    return pp


def locked_interface(ctl) -> str:
    return next(i for (k, i) in sorted(locked_objects(ctl.project)) if k == "interface")


def locked_unit(ctl) -> str:
    return next(i for (k, i) in sorted(locked_objects(ctl.project)) if k == "unit")


def combo(pp: PropertiesPanel, name: str) -> QComboBox:
    found = pp.findChild(QComboBox, name)
    assert found is not None, name
    return found


def test_a_refused_chain_change_goes_back_to_the_stored_value(released, theme, qtbot) -> None:
    ctl, _ = released
    pp = panel(ctl, theme, qtbot)
    iid = locked_interface(ctl)
    ctl.select("interface", iid)
    old = ctl.project.interfaces[iid].redundancy
    refused: list[str] = []
    ctl.message.connect(lambda text, _undo: refused.append(text))
    box = combo(pp, "if-chain")
    new = next(v for v in ("nominal", "redundant", "none") if v != old)
    box.setCurrentText(new)
    box.activated.emit(box.currentIndex())
    assert refused and "released" in refused[-1]
    assert ctl.project.interfaces[iid].redundancy == old
    assert combo(pp, "if-chain").currentText() == old  # not the rejected value


def test_a_refused_number_goes_back_to_the_stored_value(released, theme, qtbot) -> None:
    ctl, _ = released
    pp = panel(ctl, theme, qtbot)
    iid = locked_interface(ctl)
    ctl.select("interface", iid)
    field = pp.fields["voltage_v"]
    assert isinstance(field, QLineEdit)
    shown = field.text()
    field.setText("77.5" if shown != "77.5" else "66.5")
    field.editingFinished.emit()
    assert ctl.project.interfaces[iid].voltage_v != 77.5
    assert pp.fields["voltage_v"].text() == shown  # type: ignore[attr-defined]


def test_a_refused_unit_side_and_rename_go_back(released, theme, qtbot) -> None:
    ctl, _ = released
    pp = panel(ctl, theme, qtbot)
    uid = locked_unit(ctl)
    ctl.select("unit", uid)
    old_side = ctl.project.units[uid].side
    box = combo(pp, "unit-side")
    new = next(v for v in ("nominal", "redundant", "none") if v != old_side)
    box.setCurrentText(new)
    box.activated.emit(box.currentIndex())
    assert combo(pp, "unit-side").currentText() == old_side
    ident = pp.fields["id"]
    assert isinstance(ident, QLineEdit)
    ident.setText(uid + "X")
    ident.editingFinished.emit()
    assert ctl.project.units.get(uid) is not None
    assert pp.fields["id"].text() == uid  # type: ignore[attr-defined]


def test_an_accepted_cosmetic_edit_keeps_what_was_typed(released, theme, qtbot) -> None:
    ctl, _ = released
    pp = panel(ctl, theme, qtbot)
    iid = locked_interface(ctl)
    ctl.select("interface", iid)
    name = pp.fields["name"]
    assert isinstance(name, QLineEdit)
    name.setText("A better name")
    name.editingFinished.emit()
    assert ctl.project.interfaces[iid].name == "A better name"
    assert pp.fields["name"].text() == "A better name"  # type: ignore[attr-defined]


def test_a_refused_connector_part_goes_back(released, theme, qtbot) -> None:
    ctl, _ = released
    ctl.set_mode("expert")
    pp = panel(ctl, theme, qtbot)
    uid = locked_unit(ctl)
    ctl.select("unit", uid)
    boxes = [b for b in pp.findChildren(QComboBox) if b.objectName().startswith("part-")]
    assert boxes
    first = boxes[0]
    cid = first.objectName().removeprefix("part-")
    old = ctl.project.connectors[cid].part_id
    other = next(t for t in (first.itemText(k) for k in range(first.count())) if t != old)
    first.setCurrentText(other)
    first.activated.emit(first.currentIndex())
    assert ctl.project.connectors[cid].part_id in (old, other)
    now = combo(pp, f"part-{cid}")
    assert now.currentText() == ctl.project.connectors[cid].part_id


def test_the_auto_badge_says_why_the_connector_was_chosen(
    qapp, theme, qtbot, tmp_path: Path
) -> None:
    """CV-23: the tooltip of the "Auto" badge carries the reasons and what is not confirmed."""
    from PySide6.QtWidgets import QLabel

    from harness_design_studio.core import edit, templates
    from harness_design_studio.core.io.loader import load_project
    from harness_design_studio.core.model import evolve

    templates.create_project(tmp_path / "flat", "flatsat")
    p = load_project(tmp_path / "flat").project
    q = edit.clone_with(p, [])
    iid = next(i for i, x in q.interfaces.items() if all(e.connector_id for e in x.endpoints))
    i = q.interfaces[iid]
    q.interfaces[iid] = evolve(i, endpoints=[evolve(i.endpoints[0], auto=True), *i.endpoints[1:]])
    ctl = EditorController(journal_delay_ms=10_000, drc_delay_ms=600_000)
    ctl._install(q, None, None)
    try:
        ctl.set_mode("expert")
        pp = panel(ctl, theme, qtbot)
        unit = q.interfaces[iid].endpoints[0].unit_id
        ctl.select("unit", unit)
        badges = [b for b in pp.findChildren(QLabel) if b.text() == "Auto"]
        assert badges
        tip = badges[0].toolTip()
        assert tip.startswith("Chosen for you; confirm to accept")
        assert "not confirmed yet" in tip
        ctl.select("interface", iid)
        badges = [b for b in pp.findChildren(QLabel) if b.text() == "Auto"]
        assert badges and "not confirmed yet" in badges[0].toolTip()
    finally:
        ctl.release()
