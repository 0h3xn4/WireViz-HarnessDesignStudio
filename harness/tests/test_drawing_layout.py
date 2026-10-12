# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""The harness drawing keeps to its sheet: nothing runs into the title block, every wire is drawn
once, the routing sketch does not crowd the wires out, nested shields keep their sleeves, and a
wire with both ends on one side does not run backwards across its cable block."""

import pytest

from harness_design_studio.core import describe
from harness_design_studio.core.model import (
    BranchPoint,
    Connector,
    Harness,
    Part,
    Pin,
    Project,
    Segment,
    ShieldGroup,
    Wire,
)
from harness_design_studio.core.outputs import drawing
from harness_design_studio.core.outputs.canvas import SHEETS, Curve, Line, Rect, Text, text_width
from harness_design_studio.core.outputs.stamp import Stamp


def conn(cid: str, n: int, pin_ids: list[str] | None = None) -> Connector:
    ids = pin_ids or [str(k) for k in range(1, n + 1)]
    return Connector(
        id=cid, name=cid, role="cable", part_id="EX-DSUB-15-F", pins=[Pin(id=i) for i in ids]
    )


def wire(wid: str, a: str, pa: str, b: str, pb: str) -> Wire:
    return Wire(id=wid, from_connector=a, from_pin=pa, to_connector=b, to_pin=pb)


def sheets(h: Harness, size: str = "A4"):
    return drawing.harness_sheets(Project(), h, Stamp("0", "x" * 64), size)


def below_the_title_block(sheet, size: str) -> list[object]:
    """Items of the diagram that reach into the title block or off the sheet."""
    w_mm, h_mm = SHEETS[size]
    tx, ty = w_mm - drawing.MARGIN - drawing.TB_W, h_mm - drawing.MARGIN - drawing.TB_H
    stop = next(
        k
        for k, it in enumerate(sheet.items)
        if isinstance(it, Rect) and (it.x, it.y, it.w, it.h) == (tx, ty, drawing.TB_W, drawing.TB_H)
    )  # the title block's own items follow its frame
    bad = []
    for it in sheet.items[1:stop]:
        if isinstance(it, Rect):
            box = (it.x, it.y, it.x + it.w, it.y + it.h)
        elif isinstance(it, Text):
            box = (it.left, it.y - it.size, it.left + text_width(it.s, it.size), it.y)
        elif isinstance(it, (Line, Curve)):
            box = (min(it.x1, it.x2), min(it.y1, it.y2), max(it.x1, it.x2), max(it.y1, it.y2))
        else:
            continue
        into_title = box[2] > tx and box[3] > ty
        if box[3] > h_mm or box[2] > w_mm or into_title:
            bad.append(it)
    return bad


def wire_ids_drawn(all_sheets) -> list[str]:
    return [
        it.s.split()[0]
        for sh in all_sheets
        for it in sh.items
        if isinstance(it, Text) and it.bold and it.size == drawing.PIN_SIZE and it.s.startswith("W")
    ]


@pytest.mark.parametrize("size", ["A4", "A3"])
def test_cable_blocks_never_reach_the_title_block(size) -> None:
    n = 80
    h = Harness(
        id="H1",
        name="h",
        connectors=[conn("A", n), conn("B", n)],
        wires=[wire(f"W{k:03d}", "A", str(k), "B", str(k)) for k in range(1, n + 1)],
    )
    out = sheets(h, size)
    assert len(out) >= 2
    assert not [b for sh in out for b in below_the_title_block(sh, size)]
    assert sorted(wire_ids_drawn(out)) == sorted(w.id for w in h.wires)  # each wire drawn once


def test_the_routing_sketch_does_not_crowd_the_wires_out() -> None:
    k = 8
    cs = [conn("A", 20), *[conn(f"B{i:02d}", 2) for i in range(k)]]
    ws = [wire(f"W{i:02d}", "A", str(i + 1), f"B{i:02d}", "1") for i in range(k)]
    segs = [Segment(id="S0", from_node="A", to_node="BP1", length_m=1.0)] + [
        Segment(id=f"S{i + 1}", from_node="BP1", to_node=f"B{i:02d}", length_m=1.0)
        for i in range(k)
    ]
    h = Harness(
        id="H1",
        name="h",
        wires=ws,
        connectors=cs,
        branch_points=[BranchPoint(id="BP1", name="bp")],
        segments=segs,
    )
    out = sheets(h)
    assert len(out) <= 2, len(out)  # it was one wire per sheet
    assert not [b for sh in out for b in below_the_title_block(sh, "A4")]
    assert sorted(wire_ids_drawn(out)) == sorted(w.id for w in ws)


def test_nested_shields_all_keep_their_sleeves() -> None:
    cs = [conn("A", 8), conn("B", 8)]
    ws = [wire(f"W{k}", "A", str(k), "B", str(k)) for k in range(1, 5)]
    shields = [
        ShieldGroup(id="S1", kind="overall_shield", wire_ids=["W1", "W2", "W3", "W4"]),
        ShieldGroup(id="S2", kind="twisted_pair", wire_ids=["W1", "W2"]),
        ShieldGroup(id="S3", kind="twisted_pair", wire_ids=["W3", "W4"]),
    ]
    h = Harness(id="H1", name="h", wires=ws, connectors=cs, shields=shields)
    out = sheets(h)
    text = [it.s for sh in out for it in sh.items if isinstance(it, Text)]
    for s in shields:
        assert any(t.startswith(f"{s.id}  ") for t in text), s.id
    assert sorted(wire_ids_drawn(out)) == ["W1", "W2", "W3", "W4"]
    fills = {
        it.fill
        for sh in out
        for it in sh.items
        if isinstance(it, Rect) and it.fill in drawing._LEVELS
    }
    assert len(fills) == 2  # an outer jacket and a darker one for the shields inside it


def test_a_wire_with_both_ends_on_one_side_does_not_run_backwards_through_the_block() -> None:
    cs = [conn("A", 4), conn("B", 4), conn("C", 4)]
    ws = [
        wire("W1", "A", "1", "B", "1"),
        wire("W2", "B", "2", "C", "1"),
        wire("W3", "A", "2", "C", "2"),
    ]
    out = sheets(Harness(id="H1", name="h", wires=ws, connectors=cs))
    curves = [it for sh in out for it in sh.items if isinstance(it, Curve)]
    assert curves and all(abs(c.x2 - c.x1) <= drawing.MAX_WIRE_RUN + 1.0 for c in curves)
    assert sorted(wire_ids_drawn(out)) == ["W1", "W2", "W3"]
    # a wire from a connector to itself is drawn too
    own = Harness(
        id="H2", name="h", wires=[wire("W1", "A", "1", "A", "2")], connectors=[conn("A", 4)]
    )
    assert wire_ids_drawn(sheets(own)) == ["W1"]


def test_a_long_pin_id_stays_inside_its_column() -> None:
    long_id = "LONGPINNAME_B12"
    h = Harness(
        id="H1",
        name="h",
        connectors=[conn("A", 1, ["SHIELD_GND_1"]), conn("B", 1, [long_id])],
        wires=[wire("W1", "A", "SHIELD_GND_1", "B", long_id)],
    )
    for it in (i for sh in sheets(h) for i in sh.items if isinstance(i, Text)):
        if (
            it.bold
            and it.size == drawing.PIN_SIZE
            and it.s != "W1"
            and "~" in it.s
            or it.s in ("SHIELD_GND_1", long_id)
        ):
            assert text_width(it.s, it.size) <= 10.5 + 0.01, it.s


def test_long_shield_and_spare_pin_lines_are_wrapped_not_cut() -> None:
    ids = [f"W{k:03d}" for k in range(1, 61)]
    h = Harness(
        id="H1",
        name="h",
        connectors=[conn("A", 70), conn("B", 70)],
        wires=[wire(i, "A", str(k), "B", str(k)) for k, i in enumerate(ids, start=1)],
        shields=[
            ShieldGroup(
                id="S1", kind="overall_shield", wire_ids=ids, end_a="backshell_360", end_b="pigtail"
            )
        ],
    )
    lines = drawing._extras(h)
    assert all(len(line) <= 150 for line in lines)
    joined = " ".join(lines)
    assert "ends backshell_360 / pigtail" in joined and ids[-1] in joined
    assert not any(
        "~" in t.s
        for sh in sheets(h)
        for t in sh.items
        if isinstance(t, Text) and t.s.startswith(" ")
    )


def test_connector_family_is_matched_by_word_not_by_substring() -> None:
    def family(description: str) -> tuple[str, int, str]:
        p = Project()
        p.parts["P1"] = Part(id="P1", category="connector", description=description, pin_count=2)
        c = Connector(id="C1", name="C1", role="box", part_id="P1", pins=[], unit_id=None)
        p.connectors["C1"] = c
        return describe.connector_family(p, "C1")

    assert family("Small 2-pin power plug, female")[0] == "generic"  # "sma" inside "small"
    assert family("SMA coax, female")[0] == "coax"
    assert family("D-sub 9-pin, male")[0] == "dsub"
    assert family("Micro-D 9-pin, female")[0] == "microd"
    assert family("Mini-TNC jack")[0] == "coax"  # a hyphen ends a word


def test_part_gender_takes_the_first_word_it_finds() -> None:
    def gender(text: str):
        return describe.part_gender(Part(id="P", category="connector", description=text))

    assert gender("male plug, mates with female socket") == "male"
    assert gender("female socket, mates with male plug") == "female"
    assert gender("D-sub 9-pin") == "unspecified"
