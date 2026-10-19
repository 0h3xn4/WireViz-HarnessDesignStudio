# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""Check boxes, radio buttons and the tick boxes of trees are visible on both themes: an unticked box has
a border that stands out from the background (3:1), a ticked one is not only a colour (it holds a
tick, a dash or a dot). They are painted by `ThemeStyle` from the palette (D-150)."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QCheckBox, QRadioButton, QTreeWidget, QTreeWidgetItem  # noqa: E402

from harness_design_studio.gui.theme.style import INDICATOR_PX  # noqa: E402
from harness_design_studio.gui.theme.tokens import DARK, LIGHT  # noqa: E402
from tests.ux_rel import themed  # noqa: E402


def luminance(c: QColor) -> float:
    def f(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(c.redF()) + 0.7152 * f(c.greenF()) + 0.0722 * f(c.blueF())


def contrast(a: QColor, b: QColor) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def picture(widget, qtbot) -> QImage:
    qtbot.addWidget(widget)
    widget.show()
    widget.resize(40, 30)
    image: QImage = widget.grab().toImage()
    return image


@pytest.mark.parametrize(("name", "tokens"), [("light", LIGHT), ("dark", DARK)])
def test_every_state_has_a_border_that_shows_and_a_mark_that_is_not_only_colour(
    qtbot, name, tokens
) -> None:
    themed(name)
    page = QColor(tokens["bg.canvas"])
    for kind in (QCheckBox, QRadioButton):
        off = kind()  # no text: only the indicator is drawn
        image = picture(off, qtbot)
        seen = [QColor(image.pixel(x, y)) for x in range(40) for y in range(30)]
        assert any(contrast(c, page) >= 3.0 for c in seen), (name, kind.__name__, "outline")
    on, off, part = QCheckBox(), QCheckBox(), QCheckBox()
    on.setChecked(True)
    part.setTristate(True)
    part.setCheckState(Qt.CheckState.PartiallyChecked)
    images = [picture(w, qtbot) for w in (off, on, part)]
    assert len({bytes(i.constBits()) for i in images}) == 3, "off, ticked and dash all differ"
    ticked = images[1]
    inner = {ticked.pixel(x, y) for x in range(2, 2 + INDICATOR_PX) for y in range(8, 22)}
    assert len(inner) > 1  # a tick is drawn on the fill, not only a fill
    dot = QRadioButton()
    dot.setChecked(True)
    assert picture(dot, qtbot) != picture(QRadioButton(), qtbot)
    themed("light")


def test_the_tick_boxes_of_a_tree_use_the_same_painting(qtbot) -> None:
    themed("dark")
    tree = QTreeWidget()
    item = QTreeWidgetItem(["unit"])
    item.setCheckState(0, Qt.CheckState.Unchecked)
    tree.addTopLevelItem(item)
    qtbot.addWidget(tree)
    tree.show()
    tree.resize(200, 80)
    image = tree.grab().toImage()
    page = QColor(DARK["bg.surface"])
    seen = [QColor(image.pixel(x, y)) for x in range(0, 40) for y in range(0, 30)]
    assert any(contrast(c, page) >= 3.0 for c in seen)
    themed("light")
