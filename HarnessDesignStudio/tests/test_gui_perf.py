"""REQ-PERF-01: the editor stays responsive at stress size (200 units, 2,000 interfaces, 20,000 wires).

Bounds are generous (about 3x the targets) so loaded CI machines do not flake; the real numbers
come from `python -m tools.bench_gui` and are recorded in docs/demos/M2.md.
"""

import time
from collections.abc import Callable
from typing import Any

import pytest

from tests.helpers import time_limit

pytest.importorskip("PySide6")
pytestmark = [pytest.mark.gui, pytest.mark.perf]

from PySide6.QtWidgets import QApplication  # noqa: E402

from tests.gui_helpers import make_window, show_problems  # noqa: E402
from tools.bench_stress import build  # noqa: E402


def elapsed_ms(fn) -> float:  # type: ignore[no-untyped-def]
    t = time.perf_counter()
    fn()
    QApplication.processEvents()
    return (time.perf_counter() - t) * 1000


@pytest.fixture
def stress(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(build(), None, None)
    win.view.fit()
    QApplication.processEvents()
    return win


def test_scene_has_all_items(stress) -> None:  # type: ignore[no-untyped-def]
    assert len(stress.view.dscene.unit_items) == 200 and len(stress.view.dscene.link_items) == 2000


def test_selection_is_fast(stress) -> None:  # type: ignore[no-untyped-def]
    elapsed_ms(lambda: stress.ctl.select("unit", "U005"))  # warm-up
    t = min(elapsed_ms(lambda k=k: stress.ctl.select("unit", f"U0{k:02d}")) for k in range(10, 14))
    assert t < time_limit(150), t


def test_edit_is_responsive(stress) -> None:  # type: ignore[no-untyped-def]
    elapsed_ms(lambda: stress.ctl.update_unit("U001", name="warm"))
    t = min(elapsed_ms(lambda k=k: stress.ctl.update_unit("U001", name=f"n{k}")) for k in range(3))
    assert t < time_limit(100), t  # the editor target at stress size


def test_loading_a_stress_project_is_reasonable(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    t = elapsed_ms(lambda: win.ctl._install(build(), None, None))
    # 2.5 s on a workstation; the slower hosted runners take 15 s (two runs: 15.35 s and 15.46 s)
    assert t < time_limit(10000), t


def test_problems_panel_is_capped(stress) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtWidgets import QFrame

    show_problems(stress)
    QApplication.processEvents()
    cards = [f for f in stress.problems.findChildren(QFrame) if f.property("card")]
    assert 0 < len(cards) <= 25


def test_the_problems_panel_builds_only_the_cards_it_shows(stress, qtbot) -> None:  # type: ignore[no-untyped-def]
    """Regression: the panel built a card for every finding (2000 here) on each change although it
    shows 25, making add, undo and redo 3 to 6 times slower. Counted, so slow machines do not matter."""
    from harness_design_studio.gui import panels

    show_problems(stress)
    QApplication.processEvents()
    built: list[int] = []
    original = stress.problems._card

    def counting(f):  # type: ignore[no-untyped-def]
        built.append(1)
        return original(f)

    stress.problems._card = counting
    stress.ctl.add_unit("computer")
    qtbot.waitUntil(lambda: not stress.problems._dirty, timeout=5000)
    assert 0 < len(built) <= panels.MAX_CARDS + 1, len(built)


def _dirty_regions(win: Any, edit: Callable[[], object]) -> list[Any]:
    """Scene regions reported as changed by one edit (the view repaints exactly these)."""
    seen: list[Any] = []
    win.view.scene().changed.connect(seen.extend)
    edit()
    QApplication.processEvents()
    win.view.scene().changed.disconnect()
    return seen


def test_a_rename_dirties_only_the_unit(stress) -> None:  # type: ignore[no-untyped-def]
    """Regression: every edit invalidated the lane backgrounds, which are as tall as the whole
    diagram, so one rename repainted all 2200 items in the main view and in the overview map."""
    stress.ctl.update_unit("U001", name="warm")
    QApplication.processEvents()
    regions = _dirty_regions(stress, lambda: stress.ctl.update_unit("U001", name="other"))
    assert regions
    assert max(r.height() for r in regions) < 1000, [r.getRect() for r in regions]


def test_editing_notes_does_not_dirty_the_lanes_or_resize_the_scene(stress) -> None:  # type: ignore[no-untyped-def]
    stress.ctl.update_unit("U001", name="warm")
    QApplication.processEvents()
    before = stress.view.scene().sceneRect()
    regions = _dirty_regions(stress, lambda: stress.ctl.update_unit("U002", notes="x"))
    assert stress.view.scene().sceneRect() == before
    assert max(r.height() for r in regions) < 1000


def test_the_interface_table_keeps_its_rows_on_a_rename(stress) -> None:  # type: ignore[no-untyped-def]
    stress.show_interfaces()
    QApplication.processEvents()
    resets: list[int] = []
    stress.interface_table.model.modelReset.connect(lambda: resets.append(1))
    stress.ctl.update_unit("U001", name="other")
    QApplication.processEvents()
    assert not resets


def test_links_follow_a_moved_unit_exactly_as_a_full_rebuild_draws_them(stress) -> None:  # type: ignore[no-untyped-def]
    """The skip in LinkItem.update_path (unchanged curve: no repaint) must never leave a stale link."""
    scene = stress.view.dscene
    stress.ctl.move_unit("U003", 520, 640)
    stress.ctl.move_unit("U010", 30, 90)
    QApplication.processEvents()
    incremental = {iid: link.path() for iid, link in scene.link_items.items()}
    scene.rebuild()
    rebuilt = {iid: link.path() for iid, link in scene.link_items.items()}
    assert incremental == rebuilt


def test_lists_of_many_findings_refresh_after_the_edit_not_inside_it(stress, qtbot) -> None:  # type: ignore[no-untyped-def]
    """With thousands of findings the problems list and tab counts follow on a short timer, so the
    canvas is redrawn first."""
    show_problems(stress)
    QApplication.processEvents()
    assert stress.ctl.findings_are_many()
    stress.ctl.update_unit("U001", name="x")
    assert stress.problems._dirty  # not rebuilt inside the edit
    qtbot.waitUntil(lambda: not stress.problems._dirty, timeout=5000)
