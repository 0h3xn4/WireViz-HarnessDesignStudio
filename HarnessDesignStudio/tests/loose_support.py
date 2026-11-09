# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type,attr-defined,index"
"""A project that holds loose ends, to run the whole tool over (M4a of the 2.0 programme, D-201).

`build_loose(dest)` copies the packaged `flatsat` example (23 devices, 8 generated harnesses) and adds
five harnesses a person drew, none of them made by Generate (no golden holds it: it is built here,
never committed):

* `A` a cable from a free port, the other end loose (four wires with signal names);
* `B` a cable from a free port, plugged into another free port (nothing loose: the control);
* `C` a hand-made harness with two loose ends, a twisted pair, a sleeve on a loose end, a segment with
  a length, one wire with gauge, colour and length, and a note;
* `D` a cable from a port that Generate uses, plugged into another port and unplugged again (a loose
  end whose pins are the pins of a port);
* `E` a cable with every wire complete and one end still loose (the one the release gate judges).

Nothing here is shipped; `python -m tests.loose_support DIR` writes the project to look at it."""

import sys
from pathlib import Path

from harness_design_studio.core.commands import Put, apply_ops
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.manual_harness import (
    plan_add_loose_end,
    plan_cable_from_port,
    plan_new_harness,
    plan_plug_loose_end,
    plan_unplug,
)
from harness_design_studio.core.model import Accessory, evolve
from harness_design_studio.core.model.physical import Segment
from harness_design_studio.core.wires import plan_add_wire, plan_group_wires, plan_wire_edit
from harness_design_studio.resources import examples_path
from tests.helpers import copy_project


def build_loose(dest: Path, *, plug_b: bool = True) -> Path:
    root = examples_path()
    assert root is not None
    copy_project(root / "projects" / "flatsat", dest)
    p = load_project(dest).project
    for cid, signals in (
        ("PCDU1-J10", ("PWR", "RTN", "TX+", "TX-")),
        ("OBC1-J12", ("PWR", "RTN", "RX+", "RX-")),
        ("GPSU1-J02", ("1PPS+", "1PPS-")),
        ("RIU1-J11", ("1PPS+", "1PPS-")),
    ):
        c = p.connectors[cid]
        pins = [
            evolve(x, signal=signals[i]) if i < len(signals) else x for i, x in enumerate(c.pins)
        ]
        p.connectors[cid] = evolve(c, pins=pins)

    a = plan_cable_from_port(p, "PCDU1-J10", name="Loose cable A")
    apply_ops(p, a.ops)

    b = plan_cable_from_port(p, "GPSU1-J02", name="Plugged cable B")
    apply_ops(p, b.ops)
    if plug_b:
        apply_ops(p, plan_plug_loose_end(p, b.harness_id, b.loose_id, "RIU1-J11"))

    ops, hid = plan_new_harness(p, "Hand made C")
    apply_ops(p, ops)
    h = p.harnesses[hid]
    apply_ops(
        p,
        [Put("harnesses", evolve(h, notes="Two loose ends, nothing decided yet."))],
    )
    ids = []
    for _ in range(2):
        ops, cid = plan_add_loose_end(
            p, hid, pin_ids=["1", "2", "3"], signals={"1": "SIG+", "2": "SIG-"}
        )
        apply_ops(p, ops)
        ids.append(cid)
    for pin, sig, extra in (
        ("1", "SIG+", {"gauge_awg": 24, "colour": "white", "length_m": 0.6}),
        ("2", "SIG-", {}),
        ("3", None, {}),
    ):
        apply_ops(p, plan_add_wire(p, hid, ids[0], pin, ids[1], pin, signal=sig, **extra))
    wires = [w.id for w in p.harnesses[hid].wires][:2]
    apply_ops(p, plan_group_wires(p, wires, "twisted_pair"))
    h = p.harnesses[hid]
    apply_ops(
        p,
        [
            Put(
                "harnesses",
                evolve(
                    h,
                    accessories=[
                        Accessory(
                            id="ACC-001",
                            kind="sleeving",
                            part_id="EX-SLEEVE",
                            target=ids[1],
                            length_mm=80.0,
                            position="over the loose end",
                        )
                    ],
                    segments=[Segment(id="SEG-1", from_node=ids[0], to_node=ids[1], length_m=0.4)],
                ),
            )
        ],
    )

    d = plan_cable_from_port(p, "PCDU1-J09", name="Unplugged cable D")
    apply_ops(p, d.ops)
    apply_ops(p, plan_plug_loose_end(p, d.harness_id, d.loose_id, "OBC1-J12"))
    apply_ops(p, plan_unplug(p, d.harness_id, d.loose_id))
    # E: a cable with every wire complete (gauge, wire type, colour, length) and one end still loose:
    # nothing but the end is missing, so this is the harness the release gate has to judge.
    e = plan_cable_from_port(p, "GPSU1-J02", name="Complete cable E", pin_ids=["1", "2"])
    apply_ops(p, e.ops)
    wire_ids = [w.id for w in p.harnesses[e.harness_id].wires]
    apply_ops(
        p,
        plan_wire_edit(
            p,
            wire_ids,
            {"gauge_awg": 24, "part_id": "EX-WIRE-SINGLE", "colour": "red", "length_m": 0.5},
        ),
    )
    save_project(p, dest)
    return dest


if __name__ == "__main__":  # pragma: no cover
    build_loose(Path(sys.argv[1]))
