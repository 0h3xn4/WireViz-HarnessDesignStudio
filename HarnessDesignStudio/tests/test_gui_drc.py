"""M4 (GUI): design rule findings appear in the Problems panel in the background, can be waived,
fixed in one click and shown on the diagram; edits never wait for the check."""

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QPushButton  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core import drc  # noqa: E402
from harness_design_studio.core.commands import Put  # noqa: E402
from harness_design_studio.core.generate.engine import generate_project  # noqa: E402
from harness_design_studio.core.model import evolve  # noqa: E402
from harness_design_studio.core.samples import sat15  # noqa: E402
from tests.gui_helpers import DialogScript, make_window, show_problems  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    p = sat15()
    generate_project(p)
    w.ctl._drc_timer.setInterval(30)  # the editor waits 1.2 s after the last edit
    w.ctl._install(p, None, None)
    return w


def wait_for_drc(qtbot, win) -> None:  # type: ignore[no-untyped-def]
    qtbot.waitUntil(lambda: win.ctl.drc_current, timeout=10000)


def test_results_arrive_in_the_background(win, qtbot) -> None:  # type: ignore[no-untyped-def]
    assert not win.ctl.drc_current  # nothing computed yet: the editor did not wait
    wait_for_drc(qtbot, win)
    rules = {f.rule for f in win.ctl.findings()}
    assert "part-unapproved" in rules and "unchecked-config" in rules
    show_problems(win)
    header = win.problems.findChild(type(win.problems.lay.itemAt(0).widget()), "drc-state").text()
    assert "35 rules" in header and "not checked" in header and "all" not in header.lower()


def test_editing_marks_the_check_as_running_again(win, qtbot) -> None:  # type: ignore[no-untyped-def]
    wait_for_drc(qtbot, win)
    unit = next(iter(win.ctl.project.units.values()))
    win.ctl.run("rename", [Put("units", evolve(unit, name="Renamed"))])
    assert not win.ctl.drc_current
    wait_for_drc(qtbot, win)


def test_waiving_a_design_rule_warning_applies_immediately(win, qtbot) -> None:  # type: ignore[no-untyped-def]
    wait_for_drc(qtbot, win)
    f = next(x for x in win.ctl.open_findings() if x.rule == "connector-lookalike")
    assert win.ctl.waive(f, "Keyed by cable clamps, see ICD 4.2")
    assert all(x.id != f.id for x in win.ctl.open_findings())
    assert any(x.id == f.id and x.waiver for x in win.ctl.findings())


def test_one_click_fix_regenerates(win, qtbot) -> None:  # type: ignore[no-untyped-def]
    wait_for_drc(qtbot, win)
    p = win.ctl.project
    h = next(x for x in p.harnesses.values() if x.generated and len(x.wires) > 1)
    w = h.wires[0]
    cable = next(c for c in h.connectors if c.id == w.to_connector)
    other = next(x.id for x in cable.pins if x.id not in (w.to_pin, w.from_pin))
    broken = [evolve(x, to_pin=other) if x.id == w.id else x for x in h.wires]
    assert win.ctl.run("break", [Put("harnesses", evolve(h, wires=broken))])
    wait_for_drc(qtbot, win)
    f = next(x for x in win.ctl.open_findings() if x.rule == "verify-mismatch")
    assert f.fix_label == "Regenerate harnesses"
    win.ctl.apply_fix(f)
    wait_for_drc(qtbot, win)
    assert not [x for x in win.ctl.open_findings() if x.rule == "verify-mismatch"]


def test_show_selects_units_and_switches_to_the_harness_tab(win, qtbot) -> None:  # type: ignore[no-untyped-def]
    p = win.ctl.project
    unit = next(iter(p.units))
    win.show_object(unit)
    assert win.ctl.selection and win.ctl.selection.id == unit
    h = next(iter(p.harnesses))
    win.show_object(h)
    assert win.main_tabs.currentWidget() is win.harness_view  # the Harness tab of the shell
    assert win.harness_view.harness_id() == h
    win.show_object(
        "no-such-object"
    )  # (a value file such as "derating" now opens its window, D-154)
    assert "no place" in win.toasts.messages[-1]


def test_locate_resolves_wires_connectors_and_composites() -> None:
    p = sat15()
    generate_project(p)
    h = next(iter(p.harnesses.values()))
    assert drc.locate(p, h.wires[0].id) == ("harness", h.id)
    assert drc.locate(p, f"{h.id}.S1") == ("harness", h.id)
    box = next(c for c in p.connectors.values() if c.unit_id)
    assert drc.locate(p, box.id) == ("unit", box.unit_id)
    assert drc.locate(p, "nothing-here") is None


def test_buttons_still_enabled_and_dialogs_unchanged(win) -> None:  # type: ignore[no-untyped-def]
    DialogScript(win, accept=False)
    assert win.findChild(QPushButton, "generate").isEnabled()


def test_editor_waits_for_a_pause_before_checking(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Edits must never wait for the check: it starts only after the user pauses."""
    from harness_design_studio.gui.controller import DRC_DELAY_MS

    assert DRC_DELAY_MS >= 1000
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(sat15(), None, None)
    assert w.ctl._drc_worker is None and not w.ctl.drc_current


def test_a_finding_card_shows_the_requirement_it_serves(win, qtbot) -> None:  # type: ignore[no-untyped-def]
    """REQ-STD-01: the card names the requirement ID as text, apart from the explanation."""
    from PySide6.QtWidgets import QLabel

    wait_for_drc(qtbot, win)
    show_problems(win)
    cited = [f for f in win.ctl.findings() if f.sources and f.waiver is None]
    assert cited, "sat15 has a connector look-alike warning"
    labels = [
        lab.text()
        for lab in win.problems.findChildren(QLabel)
        if lab.objectName() == "finding-requirement"
    ]
    assert any(cited[0].sources[0] in text for text in labels)
    assert "Requirement:" not in cited[0].why  # the explanation itself stays clean
