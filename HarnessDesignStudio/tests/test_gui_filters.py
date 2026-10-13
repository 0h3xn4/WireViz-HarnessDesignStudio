# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""REQ-GUI-04: the toolbar filter shows one signal class, connector or bundle and fades the rest,
without changing the project."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from harness_design_studio.core.generate.engine import generate_project  # noqa: E402
from harness_design_studio.core.samples import sat15  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    p = sat15()
    generate_project(p)
    w.ctl._install(p, None, None)
    return w


def choose(win, kind, value):  # type: ignore[no-untyped-def]
    win.filter_combo.setCurrentIndex(win.filter_combo.findData(kind))
    if value is not None:
        win.filter_value.setCurrentIndex(win.filter_value.findData(value))


def faded(win):  # type: ignore[no-untyped-def]
    scene = win.view.dscene
    return {iid for iid, link in scene.link_items.items() if link.opacity() < 1.0}


def test_by_signal_class(win) -> None:  # type: ignore[no-untyped-def]
    scene, before = win.view.dscene, win.ctl.project
    cats = {iid: scene._link_category(iid) for iid in scene.link_items}
    assert len(set(cats.values())) >= 2
    chosen = sorted(set(cats.values()))[0]
    choose(win, "class", chosen)
    assert faded(win) == {i for i, c in cats.items() if c != chosen}
    assert win.ctl.project is before and not win.ctl.dirty


def test_by_connector(win) -> None:  # type: ignore[no-untyped-def]
    p = win.ctl.project
    cid = next(e.connector_id for i in p.interfaces.values() for e in i.endpoints if e.connector_id)
    choose(win, "connector", cid)
    keep = {i.id for i in p.interfaces.values() if any(e.connector_id == cid for e in i.endpoints)}
    assert keep and faded(win) == set(p.interfaces) - keep
    units = {e.unit_id for i in p.interfaces.values() if i.id in keep for e in i.endpoints}
    for uid, item in win.view.dscene.unit_items.items():
        assert (item.opacity() == 1.0) == (uid in units)


def test_by_bundle(win) -> None:  # type: ignore[no-untyped-def]
    p = win.ctl.project
    h = next(h for h in sorted(p.harnesses.values(), key=lambda x: x.id) if h.interfaces)
    choose(win, "bundle", h.id)
    keep = set(h.interfaces) | {w.interface_id for w in h.wires if w.interface_id}
    assert faded(win) == set(p.interfaces) - keep


def test_all_interfaces_restores_everything_and_hides_the_value_picker(win) -> None:  # type: ignore[no-untyped-def]
    choose(win, "class", "power")
    assert win.filter_value_action.isVisible() and faded(win)
    choose(win, None, None)
    assert not faded(win) and not win.filter_value_action.isVisible()
    assert all(item.opacity() == 1.0 for item in win.view.dscene.unit_items.values())


def test_the_filter_follows_a_new_project_and_an_added_interface(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    choose(win, "bundle", sorted(win.ctl.project.harnesses)[0])
    scene = win.view.dscene
    scene.rebuild()
    assert scene.filter == ("bundle", sorted(win.ctl.project.harnesses)[0])
    assert faded(win)
    from harness_design_studio.core.samples import mini3

    win.ctl._install(mini3(), None, None)  # another project: its own bundles are offered
    assert win.filter_value.findData(sorted(win.ctl.project.harnesses)[0]) >= 0
    assert win.filter_value.count() == len(win.ctl.project.harnesses)
