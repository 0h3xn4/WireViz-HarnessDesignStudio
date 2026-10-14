# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""Check boxes, radio buttons and the tick boxes of trees are visible on both themes: an unticked box has
a border that stands out from the background (3:1), a ticked one is not only a colour (it holds a
tick, a dash or a dot)."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QCheckBox, QRadioButton  # noqa: E402

from harness_design_studio.gui import indicators  # noqa: E402
from harness_design_studio.gui.tokens import DARK, LIGHT  # noqa: E402
from tests.ux_rel import themed  # noqa: E402


def luminance(c: QColor) -> float:
    def f(v: float) -> float:
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(c.redF()) + 0.7152 * f(c.greenF()) + 0.0722 * f(c.blueF())


def contrast(a: QColor, b: QColor) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def pictures(css: str) -> dict[str, Path]:
    import re

    return {Path(m).stem: Path(m) for m in re.findall(r"url\(([^)]+\.png)\)", css)}


@pytest.mark.parametrize(("name", "tokens"), [("light", LIGHT), ("dark", DARK)])
def test_every_state_is_a_picture_with_a_border_that_shows(name, tokens) -> None:
    css = indicators.indicator_css(tokens, name, 1.0)
    pics = pictures(css)
    assert set(pics) >= {"box-off", "box-on", "box-part", "radio-off", "radio-on"}
    bg = QColor(tokens["bg"])
    for state in ("box-off", "radio-off"):
        image = QImage(str(pics[state]))
        assert image.width() == image.height() == indicators.SIZE
        # the outline is the border token and stands out from the page by 3:1
        edge = QColor(image.pixel(indicators.SIZE // 2, 1))
        assert edge.alpha() > 0 and contrast(edge, bg) >= 3.0, state
    on = QImage(str(pics["box-on"]))
    off = QImage(str(pics["box-off"]))
    inner = {on.pixel(x, y) for x in range(3, 13) for y in range(3, 13)}
    assert len(inner) > 1  # a tick is drawn on the fill, not only a fill
    assert on != off and QImage(str(pics["box-part"])) != on  # ticked, dash and empty all differ


def test_a_real_check_box_on_the_dark_theme_draws_its_border(qtbot) -> None:
    themed("dark")
    box = QCheckBox()  # no text: only the indicator is drawn
    radio = QRadioButton()
    for w in (box, radio):
        qtbot.addWidget(w)
        w.show()
        w.resize(40, 30)
        image = w.grab().toImage()
        bg = QColor(DARK["bg"])
        seen = [QColor(image.pixel(x, y)) for x in range(0, 40) for y in range(0, 30)]
        assert any(contrast(c, bg) >= 3.0 for c in seen), type(w).__name__
    themed("light")
