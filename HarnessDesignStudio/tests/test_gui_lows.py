"""Regression tests for the low editor findings of the October audit that were still open after the
medium round (F2-10 numbers and chain text, F1-27 strings kept in one place)."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core.samples import mini3  # noqa: E402
from harness_design_studio.gui import panels, strings  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(mini3(), None, None)
    QApplication.processEvents()
    w.interface_table.refresh()
    return w


def _messages(win) -> list[str]:  # type: ignore[no-untyped-def]
    got: list[str] = []
    win.ctl.message.connect(lambda text, ok: got.append(text))
    return got


# ---- F2-10 ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["٣", "５", "²", "1٫5", "１２"])
def test_numbers_must_be_written_with_ascii_digits(text: str) -> None:
    value, error = panels.parse_optional_float(text)
    assert value is None and error == strings.NUMBER_HELP


def test_ascii_numbers_and_blank_still_parse() -> None:
    assert panels.parse_optional_float(" 2.5 ") == (2.5, "")
    assert panels.parse_optional_float("1e3") == (1000.0, "")
    assert panels.parse_optional_float("") == (None, "")


def test_a_non_ascii_digit_in_the_max_current_cell_is_refused(win) -> None:  # type: ignore[no-untyped-def]
    model = win.interface_table.model
    messages = _messages(win)
    iid = model.ids[0]
    before = win.ctl.project.interfaces[iid].max_current_a
    revision = win.ctl.history.revision
    assert model.setData(model.index(0, 6), "٣") is False
    assert win.ctl.project.interfaces[iid].max_current_a == before
    assert win.ctl.history.revision == revision
    assert strings.NUMBER_HELP in messages


@pytest.mark.parametrize("text", ["bogus", ""])
def test_an_unknown_chain_in_the_table_is_refused_in_plain_words(win, text: str) -> None:  # type: ignore[no-untyped-def]
    model = win.interface_table.model
    messages = _messages(win)
    iid = model.ids[0]
    before = win.ctl.project.interfaces[iid].redundancy
    revision = win.ctl.history.revision
    assert model.setData(model.index(0, 5), text) is False
    assert win.ctl.project.interfaces[iid].redundancy == before
    assert win.ctl.history.revision == revision
    assert messages == [strings.CHAIN_HELP]


def test_a_known_chain_in_the_table_is_accepted(win) -> None:  # type: ignore[no-untyped-def]
    model = win.interface_table.model
    iid = model.ids[0]
    new = "none" if win.ctl.project.interfaces[iid].redundancy != "none" else "nominal"
    assert model.setData(model.index(0, 5), new) is True
    assert win.ctl.project.interfaces[iid].redundancy == new


# ---- F1-27: the words on screen live in strings.py --------------------------------------------------


def test_table_headers_come_from_strings(win, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    headers = list(strings.INTERFACE_COLUMNS)
    assert headers[:3] == ["ID", "Name", "Type"]
    model = win.interface_table.model
    got = [model.headerData(c, Qt.Orientation.Horizontal) for c in range(model.columnCount())]
    assert got == headers


def test_undo_step_names_come_from_strings(win, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(strings, "STEP_ADD_ZONE", "Zone step")
    monkeypatch.setattr(strings, "STEP_EDIT", "Change {}")
    assert win.ctl.add_zone("Bay")
    assert win.ctl.history.next_undo_label == "Zone step"
    iid = sorted(win.ctl.project.interfaces)[0]
    assert win.ctl.update_interface(iid, notes="x")
    assert win.ctl.history.next_undo_label == f"Change {iid}"


def test_the_plain_fallback_for_a_bad_value_comes_from_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from harness_design_studio.gui import controller

    class Odd(Exception):
        def errors(self) -> list[dict[str, str]]:
            return []

    monkeypatch.setattr(strings, "INVALID_VALUE", "Odd value.")
    assert controller._plain(Odd()) == "Odd value."


def test_canvas_wording_comes_from_strings(win, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    for name in ("TAG_FROM", "TAG_NOMINAL", "TAG_REDUNDANT"):
        assert hasattr(strings, name), name
    ctl = win.ctl
    ctl.set_mode("expert")
    ctl.add_unit("sensor")  # carries power, spacewire and rs422, but not CAN
    ctl.begin_connect("can")
    uid = next(u for u in ctl.project.units if not ctl.unit_has_valid_connector(u))
    monkeypatch.setattr(strings, "NO_FREE_CONNECTOR", "Nothing free for {}")
    state, reason = win.view.dscene.unit_items[uid]._compat_reason()
    assert state == "no" and reason == "Nothing free for CAN"
