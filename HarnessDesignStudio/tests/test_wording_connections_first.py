# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""D6 and D17 of the 1.8.0 audit: words that still told a person who works from connections to
"Press Generate" (the interface-first way), a "Not generated" chip for harnesses that are made
from a connection and never generated, and the word "unit" on the Inspector. The words follow
what the project has."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from dataclasses import replace  # noqa: E402

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from harness_design_studio.core.model.base import evolve  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.project_tree import empty_text  # noqa: E402
from harness_design_studio.gui.topbar import ShellStatus, chip_for  # noqa: E402
from tests.test_ui_links import link_up, window  # noqa: E402

# ---- the tour -------------------------------------------------------------------------------------


def test_tour_step_three_describes_the_link_window_not_the_interface_type_menu_first() -> None:
    key, text = strings.TOUR_STEPS[2]
    assert key == "types"
    assert "Link connectors" in text and "press Connect" in text
    assert "Edit > Connect with an interface type" in text  # the older way is named, second
    assert text.index("Link connectors") < text.index("interface type")


# ---- the three empty states ---------------------------------------------------------------------


def test_the_empty_harness_view_follows_the_project(tmp_path) -> None:
    win = window(tmp_path)
    view = win.harness_view
    view.refresh()
    assert strings.HV_EMPTY_NO_INTERFACES in view.empty_body.text()  # nothing yet
    assert "Connect" in view.empty_body.text() and "Create harness" in view.empty_body.text()
    assert link_up(win) == "L1"
    view.refresh()
    text = view.empty_body.text()
    assert strings.HV_EMPTY_HAS_LINKS in text and "Create harness" in text
    assert "Generate" not in text  # a person with a connection is not sent to Generate


def test_the_empty_lists_follow_the_project(tmp_path) -> None:
    win = window(tmp_path)
    panel = win.lists_panel
    panel.refresh()
    assert strings.LP_EMPTY_NO_INTERFACES in panel.empty_body.text()
    assert "Connect" in panel.empty_body.text()
    assert link_up(win) == "L1"
    panel.refresh()
    text = panel.empty_body.text()
    assert strings.LP_EMPTY_HAS_LINKS in text and "Generate" not in text


def test_the_tree_lines_for_empty_groups_follow_the_project(tmp_path) -> None:
    win = window(tmp_path)
    tree = win.project_tree
    model = tree.model
    assert model.roots["harnesses"].placeholder.name == strings.TREE_EMPTY["harnesses"]
    assert "Generate" in strings.TREE_EMPTY["harnesses"]  # interfaces: still the way to go
    assert link_up(win) == "L1"
    QApplication.processEvents()
    harnesses = model.roots["harnesses"].placeholder
    interfaces = model.roots["interfaces"].placeholder
    assert harnesses.name == strings.TREE_EMPTY_HAS_LINKS["harnesses"]
    assert "Generate" not in harnesses.name and "Create harness" in harnesses.name
    assert interfaces.name == strings.TREE_EMPTY_HAS_LINKS["interfaces"]
    win.ctl.undo()  # the connection goes: the first words come back
    QApplication.processEvents()
    assert model.roots["harnesses"].placeholder.name == strings.TREE_EMPTY["harnesses"]
    assert empty_text("units", win.ctl.project) == strings.TREE_EMPTY["units"]


# ---- "Not generated" is not said about harnesses nobody generates -------------------------------


def test_the_chip_does_not_say_not_generated_for_hand_made_harnesses() -> None:
    plain = ShellStatus(generation="none")
    assert chip_for(plain)[:2] == ("draft", strings.CHIP_NOT_GENERATED)  # nothing yet: as before
    by_hand = ShellStatus(generation="none", has_harnesses=True, harnesses=2, hand_made=2)
    assert chip_for(by_hand)[:2] == ("pass", strings.CHIP_BY_HAND)
    mixed = ShellStatus(generation="none", has_harnesses=True, harnesses=2, hand_made=1)
    assert chip_for(mixed)[0] == "draft"  # one of them should have been generated
    stale_files = ShellStatus(
        generation="none", has_harnesses=True, harnesses=1, hand_made=1, outputs="stale"
    )
    assert chip_for(stale_files)[:2] == ("stale", strings.CHIP_OUTPUTS_STALE)  # still reported
    assert chip_for(
        ShellStatus(
            generation="none", has_harnesses=True, harnesses=1, hand_made=1, outputs="current"
        )
    )[:2] == ("pass", strings.CHIP_UP_TO_DATE)


def hand_made_window(tmp_path):
    win = window(tmp_path)
    assert link_up(win) == "L1"
    harness_id = win.ctl.create_harness_from_link("L1")
    assert harness_id and not win.ctl.project.harnesses[harness_id].generated
    assert win.ctl.project.generation is None
    return win


def test_a_project_with_a_hand_made_harness_shows_no_not_generated_words(tmp_path) -> None:
    win = hand_made_window(tmp_path)
    win.go_to("harness")
    QApplication.processEvents()
    status = win.shell_status()
    assert status.hand_made == status.harnesses == 1
    assert chip_for(status)[1] != strings.CHIP_NOT_GENERATED
    win.harness_view.refresh()
    assert win.harness_view.hash_label.full() == strings.HV_MADE_BY_HAND
    # a harness that the program is meant to generate keeps the old words
    h = next(iter(win.ctl.project.harnesses.values()))
    win.ctl.project.harnesses[h.id] = evolve(h, generated=True)
    win.harness_view.refresh()
    assert win.harness_view.hash_label.full() == strings.HV_NOT_GENERATED


def test_the_old_files_banner_does_not_say_nothing_was_generated_for_hand_made_harnesses(
    tmp_path,
) -> None:
    win = hand_made_window(tmp_path)
    shown: list[list[str]] = []
    win.alerts.show_banner = lambda key, severity, text, details=(), **kw: shown.append(
        list(details)
    )
    win.problem_notices_on = lambda: True
    status = replace(win.shell_status(), outputs="stale")
    win._update_alerts(status)
    assert shown and strings.BN_DETAIL_NOT_GENERATED not in shown[-1]
    # a project that has harnesses to generate, and has not, keeps the line
    shown.clear()
    win._update_alerts(replace(status, hand_made=0))
    assert shown and strings.BN_DETAIL_NOT_GENERATED in shown[-1]


# ---- D17: the screen says device -------------------------------------------------------------------


def test_the_inspector_heading_and_the_connect_hint_say_device(tmp_path) -> None:
    assert strings.UNIT == "Device" and strings.UNIT_WORD == "device"
    win = window(tmp_path)
    win.ctl.select("unit", "OBC")
    QApplication.processEvents()
    headings = [w.text() for w in win.inspector.findChildren(QLabel) if w.property("heading")]
    assert "DEVICE" in headings and "UNIT" not in headings
    win.ctl.begin_connect(sorted(win.ctl.project.interface_types)[0])
    hint = win.ctl.connect_hint()
    assert hint.startswith("Click the first device") and "unit" not in hint.lower()
