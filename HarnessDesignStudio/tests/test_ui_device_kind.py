# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type,no-any-return"
"""REQ-GUI-24, the window side: the Kind of a device in the inspector (`Automatic: <what the name
says>` first, then the kinds), one undo step for each change, the card, the tooltip and the legend
following it, and the words *set by hand*."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QWidget  # noqa: E402

from harness_design_studio.core import templates  # noqa: E402
from harness_design_studio.core.io import layout  # noqa: E402
from harness_design_studio.gui import device_kinds as dk  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402
from tests.test_ui_device_looks import _Hover, render  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):
    templates.create_project(tmp_path / "flatsat", "flatsat")
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    assert w.open_project(tmp_path / "flatsat")
    w.view.fit()
    QApplication.processEvents()
    w.view.grab()
    return w


def combo(win, uid: str) -> QComboBox:
    win.ctl.select("unit", uid)
    QApplication.processEvents()
    box = win.props.findChild(QComboBox, "unit-kind")
    assert box is not None
    return box


def choose(box: QComboBox, data) -> None:
    box.setCurrentIndex(box.findData(data))
    box.activated.emit(box.currentIndex())
    QApplication.processEvents()


def test_the_first_entry_says_what_automatic_would_pick(win) -> None:
    box = combo(win, "BAT1")
    assert box.itemText(0) == "Automatic: Battery" and box.currentIndex() == 0
    assert box.itemData(0) is None
    assert combo(win, "RW1").itemText(0) == "Automatic: Reaction wheel"


def test_the_list_has_every_kind_by_name_and_the_plain_box_last(win) -> None:
    box = combo(win, "BAT1")
    ids = [box.itemData(i) for i in range(1, box.count())]
    assert sorted(ids) == sorted(dk.KIND_IDS) and ids[-1] == "device"
    names = [box.itemText(i) for i in range(1, box.count() - 1)]
    assert names == sorted(names)  # by name, so a kind is found without knowing the table
    assert box.itemText(box.count() - 1) == "Device (plain box)"
    assert box.toolTip() and box.accessibleName().startswith("Kind")


def test_a_choice_is_one_undo_step_and_the_card_the_tooltip_and_the_words_follow(win) -> None:
    start = layout.model_hash(win.ctl.project)
    box = combo(win, "BAT1")
    choose(box, "antenna")
    p = win.ctl.project
    assert p.units["BAT1"].kind == "antenna"
    item = win.view.dscene.unit_items["BAT1"]
    looks = item.facts().looks
    assert (looks.kind.key, looks.source) == ("antenna", "manual")
    item.hoverMoveEvent(_Hover())
    render(win, "BAT1")
    assert "Looks like: Antenna (set by hand)" in item.toolTip()
    text = win.props.findChild(QLabel, "unit-looks-text")
    assert text.text() == "Looks like: Antenna (set by hand)"
    box = win.props.findChild(QComboBox, "unit-kind")
    assert box.currentData() == "antenna" and box.itemText(0) == "Automatic: Battery"
    kinds = [pl for k, pl, _t in win.view.legend.bar._entries() if k == "device"]
    assert "antenna" in kinds and "battery" not in kinds  # BAT1 was the only battery
    win.ctl.undo()  # one step: back to reading it from the name
    QApplication.processEvents()
    assert p.units["BAT1"].kind is None and layout.model_hash(p) == start
    assert win.view.dscene.unit_items["BAT1"].facts().looks.source == "name"
    win.ctl.redo()
    assert p.units["BAT1"].kind == "antenna"


def test_automatic_clears_the_kind(win) -> None:
    choose(combo(win, "RW1"), "gyro")
    assert win.ctl.project.units["RW1"].kind == "gyro"
    box = win.props.findChild(QComboBox, "unit-kind")
    choose(box, None)
    assert win.ctl.project.units["RW1"].kind is None
    assert win.view.dscene.unit_items["RW1"].facts().looks.kind.key == "reaction_wheel"


def test_the_plain_box_can_be_chosen(win) -> None:
    choose(combo(win, "OBC1"), "device")
    looks = win.view.dscene.unit_items["OBC1"].facts().looks
    assert looks.generic and looks.source == "manual"
    text = win.props.findChild(QLabel, "unit-looks-text")
    assert text.text() == "Looks like: Device (set by hand)"


def test_the_inspector_text_names_the_way_to_change_it(win) -> None:
    combo(win, "BAT1")
    row = win.props.findChild(QWidget, "unit-looks")
    assert "Kind" in row.toolTip() and "Rename the device" in row.toolTip()
