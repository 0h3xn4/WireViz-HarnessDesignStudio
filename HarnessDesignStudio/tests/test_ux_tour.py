"""The tour shows the palette steps with the Palette tab in front."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from tests.gui_helpers import make_window  # noqa: E402


def test_the_tour_brings_the_palette_tab_to_the_front(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.left_tabs.setCurrentIndex(w.left_tabs.index_of("tree"))
    w.tour.start()
    assert w.left_tabs.currentIndex() == w.left_tabs.index_of("palette")
    w.tour.skip.click()
