"""SC-5, SC-9, SC-10: what the harness view needs from the core, without Qt. The drawing sheets
say which items draw which wire, pin and connector (in memory only, so no output byte changes), and
`explain` can answer for a connector and a pin as well as for a wire."""

from copy import copy
from functools import cache

from harness_design_studio.core.generate.explain import (
    explain_connector,
    explain_harness,
    explain_pin,
    explain_wire,
)
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.model import Project
from harness_design_studio.core.outputs.canvas import Curve, Line, Rect, Sheet, Text, to_pdf, to_svg
from harness_design_studio.core.outputs.drawing import harness_sheets
from harness_design_studio.core.outputs.stamp import Stamp
from harness_design_studio.resources import examples_path

STAMP = Stamp("test", "0" * 8)


@cache
def flatsat() -> Project:
    return load_project(examples_path() / "projects" / "flatsat").project


def test_every_wire_pin_and_connector_of_a_harness_is_marked_on_some_sheet() -> None:
    p = flatsat()
    h = p.harnesses["W002"]
    sheets = harness_sheets(p, h, STAMP, "A3")
    marks: set[tuple[str, str]] = set().union(*(s.marks for s in sheets))
    for w in h.wires:
        assert ("wire", w.id) in marks
        assert ("pin", f"{w.from_connector}/{w.from_pin}") in marks
        assert ("pin", f"{w.to_connector}/{w.to_pin}") in marks
    for c in h.connectors:
        if any(c.id in (w.from_connector, w.to_connector) for w in h.wires):
            assert ("connector", c.id) in marks
    for s in h.shields:
        assert ("shield", s.id) in marks


def test_a_wire_mark_points_at_the_curves_and_lines_that_draw_it() -> None:
    p = flatsat()
    h = p.harnesses["W003"]
    (sheet,) = harness_sheets(p, h, STAMP, "A3")
    for w in h.wires:
        idx = sheet.marks[("wire", w.id)]
        kinds = {type(sheet.items[i]) for i in idx}
        assert Curve in kinds and Line in kinds and Text in kinds  # leads, the run, its label
        label = [sheet.items[i] for i in idx if isinstance(sheet.items[i], Text)]
        assert any(t.s.startswith(w.id) for t in label)
    for key, idx in sheet.marks.items():
        assert idx == sorted(set(idx)) and all(0 <= i < len(sheet.items) for i in idx), key


def test_marks_never_reach_the_written_files() -> None:
    p = flatsat()
    h = p.harnesses["W002"]
    sheets = harness_sheets(p, h, STAMP, "A3")
    assert sum(1 for s in sheets if s.marks) >= 2  # the sheets with the lines under the diagram have none
    for sheet in sheets:
        svg, pdf = to_svg(sheet, STAMP.line), to_pdf([sheet], "t", STAMP.line)
        bare = Sheet(sheet.width, sheet.height, list(sheet.items), sheet.title)
        assert svg == to_svg(bare, STAMP.line) and pdf == to_pdf([bare], "t", STAMP.line)
        assert b"marks" not in svg and b"marks" not in pdf
        assert sheet == bare  # equal as drawings: the marks do not count


def test_two_builds_give_the_same_marks() -> None:
    p = flatsat()
    h = p.harnesses["W004"]
    a, b = harness_sheets(p, h, STAMP, "A3"), harness_sheets(p, h, STAMP, "A3")
    assert [s.marks for s in a] == [s.marks for s in b]


def test_mark_adds_the_items_since_start() -> None:
    sh = Sheet(10, 10)
    sh.add(Rect(0, 0, 1, 1))
    start = len(sh.items)
    sh.add(Line(0, 0, 1, 1), Text(1, 1, "x"))
    sh.mark("wire", "W1", start)
    sh.mark("wire", "W2", len(sh.items))  # nothing added: no mark
    assert sh.marks == {("wire", "W1"): [1, 2]}


def test_explain_connector_and_pin_use_the_recorded_reasons() -> None:
    p = flatsat()
    prov = p.generation.provenance if p.generation else {}
    h = p.harnesses["W001"]
    c = h.connectors[0]
    assert explain_connector(p, h, c.id) == prov[f"connector:{c.id}"] != []
    assert c.mates_with
    pin = next(x for x in c.pins if f"pin:{c.mates_with}.{x.id}" in prov)
    assert explain_pin(p, h, c.id, pin.id) == prov[f"pin:{c.mates_with}.{pin.id}"]
    assert explain_pin(p, h, c.id, "no-such-pin") == []
    assert explain_pin(p, h, "no-such-connector", "1") == []
    assert explain_connector(p, h, "no-such-connector") == []


def test_explain_is_empty_for_a_project_that_was_never_generated() -> None:
    p = flatsat()
    h = p.harnesses["W001"]
    bare = copy(p)
    bare.generation = None
    assert explain_connector(bare, h, h.connectors[0].id) == []
    assert explain_pin(bare, h, h.connectors[0].id, "1") == []
    assert explain_wire(bare, h, h.wires[0]) == [] and explain_harness(bare, h) == []
