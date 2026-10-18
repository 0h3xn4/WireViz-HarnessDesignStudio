"""Regression tests for the editor findings of the October audit (offscreen Qt)."""

import contextlib

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QLabel, QPushButton  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core import edit  # noqa: E402
from harness_design_studio.core.generate.engine import generate_project  # noqa: E402
from harness_design_studio.core.model import evolve  # noqa: E402
from harness_design_studio.core.samples import mini3, sat15, stress_project  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.main_window import ToastHost  # noqa: E402
from tests.gui_helpers import DialogScript, click_unit, make_window, show_problems  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(sat15(), None, None)
    return w


def _toast_buttons(win, name: str) -> list[QPushButton]:  # type: ignore[no-untyped-def]
    found: list[QPushButton] = win.toasts.findChildren(QPushButton, name)
    return found


def test_a_toast_undo_never_undoes_a_newer_change(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl.redundant_copy("RW1")
    win.ctl.redundant_copy("RW2")
    undo = [b for b in _toast_buttons(win, "toast-undo") if b.isVisibleTo(win.toasts)]
    assert len(undo) == 1  # a newer Undo replaces the older one
    undo[0].click()
    assert "RW2-R" not in win.ctl.project.units and "RW1-R" in win.ctl.project.units


def test_an_old_toast_undo_says_it_is_stale_instead_of_undoing(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl.redundant_copy("RW1")
    button = _toast_buttons(win, "toast-undo")[0]
    win.ctl.history  # noqa: B018
    ops = edit.ops_move_unit(win.ctl.project, "OBC1", 10.0, 10.0)
    win.ctl.history.execute("move", ops)  # something else happens, without a toast
    button.click()
    assert "RW1-R" in win.ctl.project.units  # not undone
    assert strings.UNDO_STALE in win.toasts.messages


def test_toasts_are_limited_deduplicated_and_closable(win) -> None:  # type: ignore[no-untyped-def]
    host: ToastHost = win.toasts
    for n in range(6):
        host.show_message(f"message {n}", None, 60000)
    shown = [b for b in host.findChildren(QPushButton, "toast-close") if b.isVisibleTo(host)]
    assert len(shown) <= ToastHost.MAX_VISIBLE
    host.show_message("same", None, 60000)
    host.show_message("same", None, 60000)
    labels = [x for x in host.findChildren(QLabel) if x.text() == "same" and x.isVisibleTo(host)]
    assert len(labels) == 1
    for b in [b for b in host.findChildren(QPushButton, "toast-close") if b.isVisibleTo(host)]:
        b.click()
    win.toasts._shrink()


def test_a_long_toast_is_not_cut_off(win) -> None:  # type: ignore[no-untyped-def]
    text = "A long message " * 40
    win.toasts.show_message(text, None, 60000)
    label = next(x for x in win.toasts.findChildren(QLabel) if x.text() == text)
    assert label.minimumHeight() >= label.fontMetrics().height() * 3


def test_saving_to_an_unusable_folder_is_a_message_not_an_exception(win) -> None:  # type: ignore[no-untyped-def]
    win.ask_folder = lambda _title: "/proc/does-not-exist"  # type: ignore[assignment]
    assert win.save_as_flow() is False
    assert "Could not save" in win.toasts.messages[-1]


def test_zooming_out_never_zooms_in(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl._install(stress_project(), None, None)
    win.view.fit()
    before = win.view.transform().m11()
    win.view.zoom_by(1 / 1.1)
    assert win.view.transform().m11() <= before + 1e-9


def test_the_overview_map_can_be_switched_off_and_hides_in_small_views(win) -> None:  # type: ignore[no-untyped-def]
    win.view.set_minimap_wanted(False)
    assert not win.view.minimap.isVisibleTo(win.view)
    win.view.set_minimap_wanted(True)
    win.resize(1440, 900)
    assert win.view.minimap.isVisibleTo(win.view)
    win.act_minimap.setChecked(False)
    win._toggle_minimap()
    assert not win.view.minimap.isVisibleTo(win.view)


def test_counts_use_proper_singular_and_follow_edits_at_once(win) -> None:  # type: ignore[no-untyped-def]
    assert strings.units_text(1) == "1 unit" and strings.units_text(3) == "3 units"
    assert strings.interfaces_text(1) == "1 interface"
    win.ctl.new_project  # noqa: B018
    ops, _uid = edit.ops_add_unit(win.ctl.project, "computer")
    win.ctl.run("add", ops)
    assert strings.units_text(len(win.ctl.project.units)) in win.status_counts.text()


def test_disabled_buttons_say_why(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl.select(None)
    win._update_selection_actions()
    assert (
        not win.redundant_btn.isEnabled() and win.redundant_btn.toolTip() == strings.WHY_SELECT_UNIT
    )
    assert win.delete_btn.toolTip() == strings.WHY_NO_SELECTION
    click_unit(win, "OBC1")
    win.ctl.redundant_copy("OBC1")
    click_unit(win, "OBC1")
    assert "OBC1-R" in win.redundant_btn.toolTip()


def test_generate_on_a_project_without_interfaces_says_what_to_do(win) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.core.generate.engine import plan_generation
    from harness_design_studio.core.model import Project

    win.ctl._install(Project(), None, None)
    win.ctl.apply_generation(plan_generation(win.ctl.project))
    assert strings.GEN_NO_INTERFACES in win.toasts.messages


def test_the_preview_and_summary_are_plain_words() -> None:
    p = sat15()
    from harness_design_studio.core.generate.engine import plan_generation

    text = plan_generation(p).report.plain_summary()
    assert text.startswith("This will create") and "harness plans" in text
    assert "frozen" not in text and "unchanged" not in text


def test_a_hand_made_harness_can_be_deleted_from_the_harness_tab(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl._install(mini3(), None, None)
    win.go_to("harness")
    win.harness_view.select_harness("W001")
    delete = win.harness_view.more_actions["delete"]  # "More" menu of the Harness tab
    assert delete.isEnabled()
    script = DialogScript(win, accept=True)
    delete.trigger()
    assert script.seen and "W001" not in win.ctl.project.harnesses
    win.ctl.undo()
    assert "W001" in win.ctl.project.harnesses


def test_deleting_a_unit_blocked_by_a_hand_made_harness_names_the_next_step(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl._install(mini3(), None, None)
    click_unit(win, "RW1")
    DialogScript(win, accept=True)
    win.delete_btn.click()
    assert "Delete that harness first" in win.toasts.messages[-1]


def test_findings_of_one_kind_about_one_interface_share_a_card(win) -> None:  # type: ignore[no-untyped-def]
    p = sat15()
    generate_project(p)
    hid = next(h.id for h in p.harnesses.values() if len(h.wires) >= 4)
    h = p.harnesses[hid]
    win.ctl._install(p, None, None)
    p.harnesses[hid] = evolve(h, wires=[])  # every signal of its interfaces loses its wire
    win.ctl.run_drc_now()
    show_problems(win).refresh()
    from PySide6.QtWidgets import QFrame

    names = [f.objectName() for f in win.problems.findChildren(QFrame)]
    assert any(n.startswith("finding-group-") for n in names), names


# ---- audit fixes: canvas heights, stale forms, table filter, number fields ------------------------


def test_every_unit_item_follows_its_height_after_a_link_is_deleted(win) -> None:  # type: ignore[no-untyped-def]
    scene = win.view.dscene
    project = win.ctl.project
    iid = max(project.interfaces)
    win.ctl.select("interface", iid)
    assert win.ctl.delete_selected()
    for uid, item in scene.unit_items.items():
        links = sum(
            1 for i in project.interfaces.values() if uid in {e.unit_id for e in i.endpoints}
        )
        assert item.height() == edit.guided_height(links), uid


def _confirm_buttons(win) -> list[QPushButton]:  # type: ignore[no-untyped-def]
    return [b for b in win.props.findChildren(QPushButton) if b.objectName().startswith("confirm-")]


def test_the_form_of_a_unit_drops_the_confirm_button_when_its_link_is_undone(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl._install(mini3(), None, None)
    win.act_expert.trigger()
    assert win.ctl.add_interface_between("rs422", "OBC", "PCDU")
    win.ctl.select("unit", "OBC")
    stale = _confirm_buttons(win)
    assert stale
    new_id = next(i for i in win.ctl.project.interfaces if i not in {"IF-PWR-RW1", "IF-TM-RW1"})
    win.ctl.undo()
    assert new_id not in win.ctl.project.interfaces
    assert _confirm_buttons(win) == []
    for b in stale:  # a click that still reaches an old button is answered, not raised
        with contextlib.suppress(RuntimeError):  # (the old button may already be gone)
            b.click()
    assert not win.ctl.project.interfaces.get(new_id)


def test_confirming_a_missing_interface_is_a_plain_edit_error(win) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(edit.EditError):
        edit.ops_confirm_interface(win.ctl.project, "IF-NOPE")
    messages: list[tuple[str, bool]] = []
    win.ctl.message.connect(lambda text, ok: messages.append((text, ok)))
    win.ctl.confirm_interface("IF-NOPE")
    assert messages and not messages[-1][1]


def test_the_interface_filter_finds_ids_and_two_words(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl._install(mini3(), None, None)
    t = win.interface_table
    t.refresh()
    ids = sorted(win.ctl.project.interfaces)
    assert len(ids) == 2
    for text, want in (
        ("rs422", 1),
        ("IF-PWR", 1),
        ("if-pwr-rw1", 1),
        ("power rw1", 1),
        ("RW1 OBC", 1),
        ("rw1", 2),
        ("no such thing", 0),
        ("", 2),
    ):
        t.filter.setText(text)
        assert t.proxy.rowCount() == want, text


def test_leaving_a_number_field_unchanged_changes_nothing(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl._install(mini3(), None, None)
    win.ctl.update_interface("IF-PWR-RW1", max_current_a=12.3456789, voltage_v=28.123456789)
    win.ctl.select("interface", "IF-PWR-RW1")
    amps, volts = win.props.fields["max_current_a"], win.props.fields["voltage_v"]
    assert (amps.text(), volts.text()) == ("12.3456789", "28.123456789")
    revision = win.ctl.history.revision
    amps.editingFinished.emit()
    volts.editingFinished.emit()
    i = win.ctl.project.interfaces["IF-PWR-RW1"]
    assert (i.max_current_a, i.voltage_v) == (12.3456789, 28.123456789)
    assert win.ctl.history.revision == revision
    win.interface_table.refresh()
    model = win.interface_table.model
    assert model.data(model.index(0, 6)) == "12.3456789"
    assert model.setData(model.index(0, 6), "12.3456789")  # an unchanged cell is not an edit
    assert win.ctl.history.revision == revision


def test_numbers_are_shown_so_they_read_back_exactly() -> None:
    from harness_design_studio.gui.panels import format_number

    for value, text in (
        (None, ""),
        (3.0, "3"),
        (0.5, "0.5"),
        (1234567.0, "1234567"),
        (1e-05, "0.00001"),
        (1e22, "10000000000000000000000"),
        (0.1 + 0.2, "0.30000000000000004"),
    ):
        assert format_number(value) == text
        if value is not None:
            assert float(text) == value
