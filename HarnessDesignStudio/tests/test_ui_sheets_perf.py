# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""UI overhaul M4 acceptance at stress size (200 units, 2,000 interfaces): the tables open fast and a
paste of 500 rows is applied as one undo step."""

import time

import pytest

from tests.helpers import time_limit, within

pytest.importorskip("PySide6")
pytestmark = [pytest.mark.gui, pytest.mark.perf]

from PySide6.QtCore import QItemSelection, QItemSelectionModel  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.gui.sheet import paste_text  # noqa: E402
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


def test_the_interface_table_opens_within_200_ms(stress) -> None:
    elapsed_ms(stress.show_units)  # warm up the widgets
    t = elapsed_ms(stress.show_interfaces)
    assert stress.interface_table.proxy.rowCount() == 2000
    within(t, 200, "opening a table, ms")


def test_the_unit_table_opens_within_200_ms(stress) -> None:
    elapsed_ms(stress.show_interfaces)
    t = elapsed_ms(stress.show_units)
    assert stress.unit_table.proxy.rowCount() == 200
    within(t, 200, "opening a table, ms")


def test_pasting_500_rows_is_one_undo_step_and_fast(stress) -> None:
    stress.show_interfaces()
    QApplication.processEvents()
    view = stress.interface_table.view
    model = view.model()
    sel = view.selectionModel()
    sel.select(
        QItemSelection(model.index(0, 1), model.index(0, 1)),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )
    sel.setCurrentIndex(model.index(0, 1), QItemSelectionModel.SelectionFlag.NoUpdate)
    before = {i.id: i.name for i in stress.ctl.project.interfaces.values()}
    text = "\n".join(f"pasted {n}" for n in range(500))
    t = elapsed_ms(lambda: paste_text(view, text))
    after = {i.id: i.name for i in stress.ctl.project.interfaces.values()}
    assert sum(1 for k in before if before[k] != after[k]) == 500
    assert t < time_limit(1500), t
    stress.ctl.undo()
    assert {i.id: i.name for i in stress.ctl.project.interfaces.values()} == before
