"""The tour shows each step with the panel it points at in front."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.inspector import TABS  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402


def _step(w, key: str) -> None:  # type: ignore[no-untyped-def]
    keys = [k for k, _text in strings.TOUR_STEPS]
    w.tour.show_step(keys.index(key))
    assert strings.TOUR_STEPS[w.tour.index][0] == key


def test_the_tour_brings_the_project_tree_to_the_front_for_the_add_step(  # type: ignore[no-untyped-def]
    qtbot, tmp_path: Path
) -> None:
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.left_tabs.setCurrentIndex(w.left_tabs.index_of("interfaces"))
    w.tour.start()
    assert strings.TOUR_STEPS[w.tour.index][0] == "add"
    assert w.left_tabs.currentIndex() == w.left_tabs.index_of("tree")
    assert w.project_tree.add_button.isVisibleTo(w)  # the Add button the step names
    w.tour.skip.click()


def test_the_tour_points_at_the_connect_tool_and_its_type_arrow(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.tour.start()
    _step(w, "types")
    assert w.tour.targets["types"] is w.tool_connect
    assert w.tool_connect.menu() is w.menu_connect  # the arrow lists the interface types
    assert "Link connectors" in w.tour.text.text()  # Connect opens that window now
    assert "arrow next to Connect" in w.tour.text.text()  # the older way, by type
    w.tour.skip.click()


def test_the_tour_brings_the_problems_tab_to_the_front(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.inspector.show_tab("inspector")
    w.tour.start()
    _step(w, "problems")
    assert w.inspector.tabs.currentIndex() == TABS.index("problems")
    assert w.tour.targets["problems"] is w.side_tabs
    w.tour.skip.click()
