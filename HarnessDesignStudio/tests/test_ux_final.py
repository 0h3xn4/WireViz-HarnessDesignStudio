"""The diagram's badge click and "Why?" reach the right dock."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from harness_design_studio.gui.inspector import TABS  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402


def test_badge_click_and_why_reach_the_right_dock(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.core.samples import sat15

    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(sat15(), None, None)
    w.dock_right.hide()
    w.ctl.request_problems("OBC")
    assert w.dock_right.isVisible()
    assert w.inspector.tabs.currentIndex() == TABS.index("problems")
    w.dock_right.hide()
    w.ctl.request_why("unit", "OBC")
    assert w.dock_right.isVisible()
    assert w.inspector.tabs.currentIndex() == TABS.index("why")
