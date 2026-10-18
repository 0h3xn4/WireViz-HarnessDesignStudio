# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""Wire colours are the owner's data: set per signal (generation.wire_colour_by_signal), by hand
in a dialog, undone like any edit, and applied to the wires when they are generated."""

from pathlib import Path

import pytest

from harness_design_studio.core import edit, templates
from harness_design_studio.core.commands import History
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.wirecolours import COLOURS, name_of, resolve


@pytest.fixture
def project(tmp_path: Path):
    templates.create_project(tmp_path / "f", "first-steps")
    return load_project(tmp_path / "f").project


def test_codes_and_names_resolve_to_the_same_colour() -> None:
    assert resolve("red") == resolve("RD") == ("RD", "#e02020")
    assert resolve("Gray") == resolve("GY")
    assert resolve(None) == ("", "#808080") and resolve("") == ("", "#808080")
    assert resolve("striped")[1] == "#808080"  # unknown: kept as text, drawn grey
    assert name_of("BU") == "blue" and name_of("striped") == ""
    assert len({code for _n, code, _h in COLOURS}) == len(COLOURS)


def test_two_colour_wires_keep_both_codes() -> None:
    # B-19: "yellow/green" was cut to "yellow" -> ("yellow", grey); "white/blue" printed "white/"
    for typed in ("yellow/green", "green-yellow", "YE/GN", "Yellow / Green"):
        code, hexcolour = resolve(typed)
        assert "/" in code and len(code.split("/")) == 2 and hexcolour == "#808080"
    assert resolve("yellow/green")[0] == "YE/GN" and resolve("green-yellow")[0] == "GN/YE"
    assert resolve("white/blue")[0] == "WH/BU"
    assert name_of("yellow/green") == ""  # not one colour of the table
    assert resolve("red/striped")[0] == "red/st"  # one part unknown: kept as typed (shortened)


def test_signal_names_and_the_colour_ops(project) -> None:
    signals = edit.signal_names(project)
    assert signals and signals == sorted(signals)
    assert edit.wire_colour_map(project) == {}
    ops = edit.ops_set_wire_colours(project, {signals[0]: "red", signals[-1]: ""})
    history = History(project)
    history.execute("wire colours", ops)
    assert edit.wire_colour_map(project) == {signals[0]: "red"}
    assert edit.ops_set_wire_colours(project, {signals[0]: "red"}) == []  # nothing changes
    history.undo()
    assert edit.wire_colour_map(project) == {}
    # clearing every colour removes the key again
    history.execute("wire colours", edit.ops_set_wire_colours(project, {signals[0]: "blue"}))
    history.execute("wire colours", edit.ops_set_wire_colours(project, {signals[0]: ""}))
    assert "wire_colour_by_signal" not in project.config["generation"].values


def test_generated_wires_take_the_chosen_colours(project) -> None:
    sig = edit.signal_names(project)[0]
    History(project).execute("wire colours", edit.ops_set_wire_colours(project, {sig: "green"}))
    generate_project(project)
    every = [w for h in project.harnesses.values() for w in h.wires]
    hit = [w for w in every if w.signal and sig in w.signal.split("/")[:1] + [w.signal]]
    assert hit and all(w.colour == "green" for w in hit)  # "TX+/RX+" takes the colour of TX+
    assert all(w.colour is None for w in every if w not in hit)


@pytest.mark.gui
def test_the_dialog_sets_the_colours_and_the_wire_list_shows_them(qtbot, tmp_path) -> None:
    from PySide6.QtWidgets import QDialog

    from harness_design_studio.gui.dialogs import WireColoursDialog
    from tests.gui_helpers import make_window

    templates.create_project(tmp_path / "g", "first-steps")
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(load_project(tmp_path / "g").project, None, None)
    sig = "TX+"  # the signal of the first harness of the example
    assert sig in edit.signal_names(win.ctl.project)

    def pick(dlg: QDialog) -> int:
        assert isinstance(dlg, WireColoursDialog)
        box = dlg.boxes[sig]
        box.setCurrentIndex(box.findData("yellow"))
        return int(QDialog.DialogCode.Accepted)

    win.run_dialog = pick  # type: ignore[assignment]
    win.act_wire_colours.trigger()
    assert edit.wire_colour_map(win.ctl.project) == {sig: "yellow"}
    win.act_undo.trigger()
    assert edit.wire_colour_map(win.ctl.project) == {}
    win.act_wire_colours.trigger()
    generate_project(win.ctl.project)
    view = win.harness_view  # the wire table of the Harness tab has the Colour column
    win.go_to("harness")
    view.refresh()
    assert view.select_harness(sorted(win.ctl.project.harnesses)[0])
    assert win.ctl.project.harnesses, "generation made no harness"
    col = view.wire_model.column_index("colour")
    texts = [view.wire_model.text_at(r, col) for r in range(view.wire_model.rowCount())]
    assert texts
    assert "yellow (YE)" in texts
