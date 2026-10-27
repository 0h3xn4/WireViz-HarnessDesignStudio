# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""1.8.1 (audit C-15): names in rich-text labels are escaped, so a device called `A<B and C>D`
is shown as typed in the delete question and the connector rows."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from harness_design_studio.core.model import evolve  # noqa: E402
from harness_design_studio.core.samples import mini3  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402

NAME = "A<B and C>D"


@pytest.fixture
def win(qtbot, tmp_path):
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    p = mini3()
    for uid in list(p.units)[:2]:
        p.units[uid] = evolve(p.units[uid], name=NAME)
    w.ctl._install(p, None, None)
    QApplication.processEvents()
    return w


def test_the_delete_question_shows_a_name_with_angle_brackets_as_typed(win) -> None:
    units = sorted(win.ctl.project.units)[:2]
    _title, body = win._many_delete_text(units, [])
    assert "A&lt;B and C&gt;D" in body and NAME not in body


def test_the_connector_rows_show_a_name_with_angle_brackets_as_typed(win) -> None:
    p = win.ctl.project
    box = next(c for c in sorted(p.connectors.values(), key=lambda c: c.id) if c.role == "box")
    uid, cid = box.unit_id, box.id
    p.connectors[cid] = evolve(p.connectors[cid], name=NAME)
    win.ctl.set_mode("expert")  # the physical connectors show in the full workspace
    win.ctl.select("unit", uid)
    QApplication.processEvents()
    texts = [lb.text() for lb in win.props.findChildren(QLabel)]
    assert "<b>A&lt;B and C&gt;D</b>" in texts
