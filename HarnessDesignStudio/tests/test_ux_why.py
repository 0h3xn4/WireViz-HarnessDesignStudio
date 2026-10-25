# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SC-8 / CV-23: the Why panel (`gui/why_panel.py`). Offscreen, on a bare controller."""

from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from harness_design_studio.core import templates, why  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.model import evolve  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.states import StateChip  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from harness_design_studio.gui.why_panel import FIRST_LINES, WhyPanel  # noqa: E402


@pytest.fixture
def theme(qapp):
    th = ThemeManager()
    th.apply(qapp, "light", 1.0)
    yield th
    ThemeManager().apply(qapp, "light", 1.0)


@pytest.fixture
def ctl(qapp, tmp_path: Path) -> Iterator[EditorController]:
    c = EditorController(journal_delay_ms=10_000, drc_delay_ms=600_000)
    templates.create_project(tmp_path / "flat", "flatsat")
    c._install(load_project(tmp_path / "flat").project, None, None)
    yield c
    c.release()


def make(ctl, theme, qtbot) -> WhyPanel:
    panel = WhyPanel(ctl, theme)
    qtbot.addWidget(panel)
    panel.resize(320, 600)
    panel.show()
    QApplication.processEvents()
    return panel


def texts(panel: WhyPanel) -> list[str]:
    return [lab.text() for lab in panel.findChildren(QLabel)]


def a_wire(ctl) -> str:
    return str(ctl.project.harnesses["W001"].wires[0].id)


def test_with_nothing_selected_it_says_what_to_select(ctl, theme, qtbot) -> None:
    panel = make(ctl, theme, qtbot)
    assert panel.shown() is None and panel.rows == []
    assert any("Select a device" in t for t in texts(panel))


def test_it_follows_the_selection_of_a_unit_and_of_a_link(ctl, theme, qtbot) -> None:
    panel = make(ctl, theme, qtbot)
    iid = "IF-010"
    ctl.select("interface", iid)
    assert panel.shown() == ("interface", iid)
    assert any(t == "WHY: LINK IF-010" or "IF-010" in t for t in texts(panel))
    expect = [r.line for r in why.reasons(ctl.project, "interface", iid)][:FIRST_LINES]
    assert panel.reason_lines() == expect and expect
    uid = next(iter(ctl.project.units))
    ctl.select("unit", uid)
    assert panel.shown() == ("unit", uid)
    ctl.select(None)
    assert panel.shown() is None


def test_a_wire_shows_its_reasons_as_rule_and_sentence(ctl, theme, qtbot) -> None:
    panel = make(ctl, theme, qtbot)
    wid = a_wire(ctl)
    panel.show_object("wire", wid)
    lines = panel.reason_lines()
    assert lines and lines[0].startswith("wiring: ")
    assert any(line.startswith("wire-sizing: ") for line in lines)
    rules = [lab.text() for lab in panel.findChildren(QLabel) if lab.objectName() == "why-rule"]
    assert "wiring" in rules  # the rule is its own (monospace) label


def test_only_the_first_lines_show_until_show_all(ctl, theme, qtbot) -> None:
    panel = make(ctl, theme, qtbot)
    panel.show_object("interface", "IF-010")
    total = len(why.reasons(ctl.project, "interface", "IF-010"))
    assert total > FIRST_LINES
    assert len(panel.rows) == FIRST_LINES
    button = panel.show_all_button
    assert button is not None and button.text() == f"Show all {total}"
    assert button.accessibleName() and button.toolTip()
    button.click()
    assert len(panel.rows) == total
    assert panel.show_all_button is not None and panel.show_all_button.text() == "Show fewer"
    panel.show_all_button.click()
    assert len(panel.rows) == FIRST_LINES


def test_few_reasons_need_no_button(ctl, theme, qtbot) -> None:
    panel = make(ctl, theme, qtbot)
    panel.show_object("harness", "W001")
    assert panel.show_all_button is None and len(panel.rows) == 1


def test_another_object_starts_collapsed_again(ctl, theme, qtbot) -> None:
    panel = make(ctl, theme, qtbot)
    panel.show_object("interface", "IF-010")
    assert panel.show_all_button is not None
    panel.show_all_button.click()
    panel.show_object("interface", "IF-011")
    assert len(panel.rows) <= FIRST_LINES


def test_connectors_and_pins_have_reasons_too(ctl, theme, qtbot) -> None:
    panel = make(ctl, theme, qtbot)
    cable = ctl.project.harnesses["W001"].connectors[0]
    panel.show_object("connector", cable.id)
    assert panel.reason_lines()[0].startswith("mating: ")
    panel.show_object("pin", f"{cable.mates_with}.{cable.pins[0].id}")
    assert panel.reason_lines()[0].startswith("pin-allocation: ")


def test_an_object_without_a_record_says_so(ctl, theme, qtbot) -> None:
    panel = make(ctl, theme, qtbot)
    panel.show_object("wire", "no-such-wire")
    assert panel.rows == [] and any("Nothing was recorded" in t for t in texts(panel))


def test_pending_reasons_come_with_a_pending_chip(ctl, theme, qtbot) -> None:
    from harness_design_studio.core.commands import Put

    h = ctl.project.harnesses["W001"]
    w = h.wires[0]
    ctl.run("bare", [Put("harnesses", evolve(h, wires=[evolve(w, gauge_awg=None), *h.wires[1:]]))])
    panel = make(ctl, theme, qtbot)
    panel.show_object("wire", w.id)
    chips = panel.findChildren(StateChip)
    assert any(c.state() == "pending" and c.text() is None for c in chips)
    assert any("gauge is pending" in t for t in texts(panel))


def test_the_placeholder_note_names_the_files(ctl, theme, qtbot) -> None:
    panel = make(ctl, theme, qtbot)
    panel.show_object("wire", a_wire(ctl))
    used = sorted(ctl.project.generation.placeholders_used)  # type: ignore[union-attr]
    assert used
    chips = [c for c in panel.findChildren(StateChip) if c.text() == "Placeholder"]
    assert chips and chips[0].state() == "pending"
    assert any(", ".join(used) in t for t in texts(panel))


def test_why_text_is_for_tooltips_anywhere(ctl, theme, qtbot) -> None:
    panel = make(ctl, theme, qtbot)
    wid = a_wire(ctl)
    text = panel.why_text("wire", wid, 2)
    assert text == why.why_text(ctl.project, "wire", wid, 2)
    assert text.splitlines()[0].startswith("wiring: ")
    assert panel.why_text("wire", "nope") == ""


def test_it_follows_a_regeneration_without_being_asked(ctl, theme, qtbot) -> None:
    from harness_design_studio.core.commands import SetGeneration

    panel = make(ctl, theme, qtbot)
    panel.show_object("harness", "W001")
    before = panel.reason_lines()
    gen = ctl.project.generation
    assert gen is not None
    prov = {**gen.provenance, "harness:W001": ["segmentation: a new reason"]}
    ctl.run("regen", [SetGeneration(evolve(gen, provenance=prov))])
    assert panel.reason_lines() == ["segmentation: a new reason"] != before


def test_nothing_is_rebuilt_when_the_reasons_are_unchanged(ctl, theme, qtbot) -> None:
    panel = make(ctl, theme, qtbot)
    panel.show_object("interface", "IF-010")
    first = panel.rows[0]
    ctl.update_unit(next(iter(ctl.project.units)), name="Renamed")
    assert panel.rows and panel.rows[0] is first


def test_the_panel_has_a_name_and_rows_have_accessible_text(ctl, theme, qtbot) -> None:
    panel = make(ctl, theme, qtbot)
    panel.show_object("wire", a_wire(ctl))
    assert panel.accessibleName() == "Why"
    assert all(r.accessibleName() for r in panel.rows)
