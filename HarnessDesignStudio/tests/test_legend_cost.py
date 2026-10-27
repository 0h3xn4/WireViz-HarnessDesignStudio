# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type,no-any-return"
"""D9 of the 1.8.0 audit: an edit took 250 ms at 150 devices because the legend asked
`describe.connector_family` for every harness connector, and each ask built the dictionary of every
connector again (`Project.all_connectors`), so the cost grew with the square of the project.
The legend now builds that map once per `set_project`; `_entries` (called on every paint and
layout) builds none."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core import describe  # noqa: E402
from harness_design_studio.core.commands import apply_ops  # noqa: E402
from harness_design_studio.core.links import plan_add_link, plan_create_harness  # noqa: E402
from harness_design_studio.core.model.project import Project  # noqa: E402
from harness_design_studio.gui.legend import LegendBar  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.helpers import pinout_project  # noqa: E402

PAIRS = (("OBC-J01", "RW1-J02"), ("PCDU-J02", "OBC-J02"), ("PCDU-J01", "RW1-J01"))


def with_harnesses(count: int = 2) -> Project:
    """The pinout project with `count` connections, each with a harness of its own."""
    p = pinout_project()
    p.harnesses, p.interfaces, p.baselines = {}, {}, {}  # a connector takes one plug (1.8.1)
    for cid, c in list(p.connectors.items()):  # and a pin an interface uses is not offered
        pins = [pin.model_copy(update={"interface_id": None}) for pin in c.pins]
        p.connectors[cid] = c.model_copy(update={"pins": pins})
    for a, b in PAIRS[:count]:
        ops, lid = plan_add_link(p, a, b)
        apply_ops(p, ops)
        ops, _hid = plan_create_harness(p, lid)
        apply_ops(p, ops)
    return p


@pytest.fixture
def counted(monkeypatch):
    calls: list[int] = []
    real = Project.all_connectors

    def counting(self):
        calls.append(1)
        return real(self)

    monkeypatch.setattr(Project, "all_connectors", counting)
    return calls


def test_the_family_of_a_harness_connector_can_come_from_a_map_built_once(counted) -> None:
    p = with_harnesses()
    owned = [c.id for h in p.harnesses.values() for c in h.connectors]
    assert owned and not set(owned) & set(p.connectors)
    connectors = p.all_connectors()
    counted.clear()
    with_map = [describe.connector_family(p, cid, connectors) for cid in owned]
    assert counted == []  # not one more map
    assert with_map == [describe.connector_family(p, cid) for cid in owned]
    assert len(counted) == len(owned)  # (without a map each ask still builds its own)
    assert describe.connector_family(p, "NO-SUCH", connectors) == ("generic", 0, "")


def test_the_legend_builds_the_connector_map_once_however_many_harnesses(counted) -> None:
    _ = QApplication.instance() or QApplication([])
    bar = LegendBar(ThemeManager())
    small = with_harnesses(1)
    counted.clear()
    bar.set_project(small)
    first = [label for _k, _p, label in bar._entries()]
    assert len(counted) == 1
    # more harnesses and connectors: still one map, and `_entries` and the layout build none
    big = with_harnesses(3)
    assert len(big.all_connectors()) > len(small.all_connectors())
    counted.clear()
    bar.set_project(big)
    bar._layout(400)
    bar._positions(400)
    for _ in range(5):
        bar._entries()
    assert len(counted) == 1
    assert [label for _k, _p, label in bar._entries()] == first
