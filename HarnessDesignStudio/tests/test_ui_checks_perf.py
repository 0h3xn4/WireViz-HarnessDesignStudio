# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""UI overhaul M5 at stress size (200 units, 2,000 interfaces, about 82,000 findings): an edit that
follows a rule check stays quick, and taking in a check result is a short step on the GUI thread
(it was 11 s: the diagram's state index and the project tree looked up every finding in a scan of
every wire, D-154)."""

import time

import pytest

from tests.helpers import time_limit

pytest.importorskip("PySide6")
pytestmark = [pytest.mark.gui, pytest.mark.perf]

from PySide6.QtWidgets import QApplication  # noqa: E402

from tests.gui_helpers import make_window  # noqa: E402
from tools.bench_stress import build  # noqa: E402


def elapsed_ms(fn) -> float:
    t = time.perf_counter()
    fn()
    QApplication.processEvents()
    return (time.perf_counter() - t) * 1000


@pytest.fixture
def stress(qtbot, tmp_path):
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.show()
    win.ctl._install(build(), None, None)
    QApplication.processEvents()
    return win


def test_an_edit_after_a_check_with_many_findings_is_quick(stress) -> None:
    c = stress.ctl
    c.run_drc_now()
    assert len(c.open_findings()) > 50_000
    elapsed_ms(lambda: c.update_unit("U001", name="warm"))
    t = min(elapsed_ms(lambda k=k: c.update_unit("U001", name=f"n{k}")) for k in range(3))
    assert t < time_limit(250), (
        t
    )  # (was 11,000 ms; a CI runner needs 400 ms where a laptop needs 90)


def test_taking_in_a_check_result_is_a_short_step_on_the_gui_thread(stress, qtbot) -> None:
    c = stress.ctl
    spent: list[float] = []
    original = c._drc_done

    def timed() -> None:
        start = time.perf_counter()
        original()
        spent.append((time.perf_counter() - start) * 1000)

    c._drc_done = timed  # type: ignore[method-assign]
    c._start_drc()
    qtbot.waitUntil(lambda: c.drc_current, timeout=180_000)
    assert len(c.open_findings()) > 50_000
    assert spent and max(spent) < time_limit(600), spent  # (130 ms here, 900 ms on a CI runner)
