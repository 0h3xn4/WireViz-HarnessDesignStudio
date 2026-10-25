"""CD-X1, CD-X2, CD-X3, CD-X6: the headless plans of the device editor (core/devices.py): connectors,
pins, pasted rows, interface types on pins, the inline checks, the state of a device and the lock
that closes the hole of the audit (CD-G15) in the planners. No Qt."""

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_design_studio.core import devices, edit
from harness_design_studio.core.commands import Delete, History, Op, Put
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.issues import errors
from harness_design_studio.core.model import (
    Connector,
    Harness,
    Part,
    Pin,
    Placement,
    Project,
    Unit,
    Wire,
    evolve,
)
from harness_design_studio.core.samples import new_project
from harness_design_studio.core.vcs.locks import check_locks
from tests.test_change_control import do_release, exported, full, releasable


def run(p: Project, label: str, ops: list[Op]) -> None:
    History(p).execute(label, ops)
    assert errors(check_integrity(p)) == []


def device() -> Project:
    """A project with one empty custom unit GYRO1 and a custom 6-pin connector pair."""
    p = new_project()
    for part in (
        Part(id="MY-HD-6-F", category="connector", pin_count=6, mates_with="MY-HD-6-M",
             description="Custom 6-pin, female"),
        Part(id="MY-HD-6-M", category="connector", pin_count=6, mates_with="MY-HD-6-F",
             description="Custom 6-pin, male"),
        Part(id="MY-PLAIN-4", category="connector", pin_count=4),
        Part(id="MY-BIG-8-M", category="connector", pin_count=8, description="Custom 8-pin, male"),
    ):  # fmt: skip
        p.parts[part.id] = part
    p.units["GYRO1"] = Unit(id="GYRO1", name="Gyro unit", subsystem="aocs", side="nominal")
    p.placements["GYRO1"] = Placement(id="GYRO1", x=edit.lane_x(0), y=40)
    return p


def with_connector(part: str = "MY-HD-6-F") -> tuple[Project, str]:
    p = device()
    ops, cid = devices.ops_add_connector(p, "GYRO1", part_id=part)
    run(p, "add connector", ops)
    return p, cid


def pin(p: Project, cid: str, pid: str) -> Pin:
    return next(x for x in p.connectors[cid].pins if x.id == pid)


def refused(fn, *args, **kw) -> str:  # type: ignore[no-untyped-def]
    with pytest.raises(EditError) as exc:
        fn(*args, **kw)
    return str(exc.value)


# ---- add, update and delete a connector (CD-C2, CD-C3) -----------------------------------------


def test_add_connector_makes_pins_one_to_n_and_takes_the_gender_from_the_part() -> None:
    p, cid = with_connector()
    c = p.connectors[cid]
    assert cid == "GYRO1-J01" and c.name == "J01" and c.role == "box" and c.unit_id == "GYRO1"
    assert [x.id for x in c.pins] == ["1", "2", "3", "4", "5", "6"]
    assert c.gender == "female" and c.carries == [] and c.keying is None
    ops, cid2 = devices.ops_add_connector(p, "GYRO1", part_id="MY-PLAIN-4", gender="male")
    run(p, "add", ops)
    assert cid2 == "GYRO1-J02" and p.connectors[cid2].gender == "male"
    assert len(p.connectors[cid2].pins) == 4


def test_add_connector_with_given_pin_ids_keying_and_carries() -> None:
    p = device()
    ops, cid = devices.ops_add_connector(
        p, "GYRO1", part_id="MY-HD-6-F", name="Power", keying="B", carries=["can", "can"],
        pin_ids=["A1", "A2", "3"],
    )  # fmt: skip
    run(p, "add", ops)
    c = p.connectors[cid]
    assert (c.name, c.keying, c.carries) == ("Power", "B", ["can"])
    assert [x.id for x in c.pins] == ["A1", "A2", "3"]


def test_add_connector_errors() -> None:
    p = device()
    assert "does not exist" in refused(devices.ops_add_connector, p, "NOPE", part_id="MY-HD-6-F")
    assert "not a connector part" in refused(
        devices.ops_add_connector, p, "GYRO1", part_id="EX-WIRE-SINGLE"
    )
    assert "not a connector part" in refused(devices.ops_add_connector, p, "GYRO1", part_id="X")
    assert "pin name" in refused(
        devices.ops_add_connector, p, "GYRO1", part_id="MY-HD-6-F", pin_ids=["5V+"]
    )
    assert "listed twice" in refused(
        devices.ops_add_connector, p, "GYRO1", part_id="MY-HD-6-F", pin_ids=["A1", "a1"]
    )
    assert "has 4 pins" in refused(
        devices.ops_add_connector, p, "GYRO1", part_id="MY-PLAIN-4", pin_ids=list("12345")
    )
    assert "gender" in refused(
        devices.ops_add_connector, p, "GYRO1", part_id="MY-HD-6-F", gender="x"
    )
    assert "does not exist" in refused(
        devices.ops_add_connector, p, "GYRO1", part_id="MY-HD-6-F", carries=["nope"]
    )
    run(p, "add", devices.ops_add_connector(p, "GYRO1", part_id="MY-HD-6-F", name="Main")[0])
    assert "already has a connector called 'main'" in refused(
        devices.ops_add_connector, p, "GYRO1", part_id="MY-HD-6-F", name="main"
    )
    p.read_only = True
    assert "read-only" in refused(devices.ops_add_connector, p, "GYRO1", part_id="MY-HD-6-F")


def test_next_connector_name_skips_ids_in_use_even_in_harnesses() -> None:
    p, _ = with_connector()
    p.harnesses["H1"] = Harness(
        id="H1", name="h", connectors=[Connector(id="GYRO1-J02", name="J02", role="cable", part_id="MY-HD-6-M")]
    )  # fmt: skip
    assert devices.next_connector_name(p, "GYRO1") == ("GYRO1-J03", "J03")


def test_update_connector() -> None:
    p, cid = with_connector()
    run(
        p,
        "u",
        devices.ops_update_connector(
            p, cid, name="Main", gender="male", keying="A", carries=["can"], notes="n"
        ),
    )
    c = p.connectors[cid]
    assert (c.name, c.gender, c.keying, c.carries, c.notes) == ("Main", "male", "A", ["can"], "n")
    assert devices.ops_update_connector(p, cid, name="Main") == []
    run(p, "u", devices.ops_update_connector(p, cid, keying=""))
    assert p.connectors[cid].keying is None
    assert "cannot be changed here" in refused(devices.ops_update_connector, p, cid, part_id="X")
    assert "does not exist" in refused(devices.ops_update_connector, p, cid, carries=["zz"])
    assert "is not a connector of a device" in refused(devices.ops_update_connector, p, "NOPE")


def test_changing_the_part_resizes_the_pins_and_sets_the_gender() -> None:
    """CD-G5: the audit's run 5 left 9 pins and `female` after a change to a 31-pin male part."""
    p, cid = with_connector()
    (old,) = edit.ops_set_connector_part(p, cid, "MY-BIG-8-M")  # the old planner is unchanged
    assert isinstance(old, Put) and isinstance(old.obj, Connector)
    assert len(old.obj.pins) == 6 and old.obj.gender == "female"
    plan = devices.plan_change_part(p, cid, "MY-BIG-8-M")
    assert plan.add == ("7", "8") and plan.remove == () and plan.gender == "male"
    run(p, "part", devices.ops_change_part(p, cid, "MY-BIG-8-M"))
    c = p.connectors[cid]
    assert c.part_id == "MY-BIG-8-M" and c.gender == "male"
    assert [x.id for x in c.pins] == ["1", "2", "3", "4", "5", "6", "7", "8"]


def test_change_part_options_and_shrinking() -> None:
    p, cid = with_connector()
    run(p, "part", devices.ops_change_part(p, cid, "MY-BIG-8-M", resize=False, regender=False))
    c = p.connectors[cid]
    assert len(c.pins) == 6 and c.gender == "female"
    run(p, "set", devices.ops_set_pin(p, cid, "6", signal="X"))
    # back to 6 pins: nothing to remove, then to 4: pin 5 and 6 go but 6 carries a signal
    assert "pin 6 would have to go but is in use" in refused(
        devices.ops_change_part, p, cid, "MY-PLAIN-4"
    )
    run(p, "clear", devices.ops_set_pin(p, cid, "6", signal=""))
    run(p, "part", devices.ops_change_part(p, cid, "MY-PLAIN-4"))
    assert [x.id for x in p.connectors[cid].pins] == ["1", "2", "3", "4"]
    assert p.connectors[cid].gender == "female"  # the part says nothing: nothing is guessed
    assert devices.ops_change_part(p, cid, "MY-PLAIN-4") == []
    assert "not a connector part" in refused(devices.ops_change_part, p, cid, "EX-LABEL")


def test_resize_to_the_same_part_adds_the_missing_pins() -> None:
    p, cid = with_connector()
    run(p, "del", devices.ops_delete_pins(p, cid, ["5", "6"]))
    assert devices.pinout_problems(p, cid)[0].code == "pins_missing"
    run(p, "resize", devices.ops_change_part(p, cid, "MY-HD-6-F"))
    assert [x.id for x in p.connectors[cid].pins][-2:] == ["5", "6"]


def test_delete_connector_detaches_its_interfaces_and_refuses_hand_made_wires() -> None:
    p = new_project()
    ops, uid = edit.ops_add_unit(p, "computer")
    run(p, "u", ops)
    ops, uid2 = edit.ops_add_unit(p, "pdu")
    run(p, "u", ops)
    ops, iid = edit.ops_add_interface(p, "can", uid, uid2)
    run(p, "i", ops)
    cid = next(e.connector_id for e in p.interfaces[iid].endpoints if e.unit_id == uid)
    assert cid is not None
    impact = devices.connector_delete_impact(p, cid)
    assert impact.interfaces == (iid,) and impact.frozen is None
    run(p, "del", devices.ops_delete_connector(p, cid))
    assert cid not in p.connectors
    ends = {e.unit_id: e.connector_id for e in p.interfaces[iid].endpoints}
    assert ends[uid] is None and ends[uid2] is not None
    # a harness made by hand with a wire on the connector blocks the delete
    other = next(e.connector_id for e in p.interfaces[iid].endpoints if e.unit_id == uid2)
    assert other is not None
    p.harnesses["HX"] = Harness(
        id="HX", name="by hand", generated=False,
        connectors=[Connector(id="HX-P1", name="P1", role="cable", part_id="EX-MICROD-9-M", mates_with=other)],
        wires=[Wire(id="HX-W1", from_connector="HX-P1", from_pin="1", to_connector="HX-P1", to_pin="2")],
    )  # fmt: skip
    assert "made by hand" in refused(devices.ops_delete_connector, p, other)
    assert "is not a connector of a device" in refused(devices.ops_delete_connector, p, "NOPE")


# ---- pins (CD-C4, CD-C5) -----------------------------------------------------------------------


def test_set_pin_fields_and_mode() -> None:
    p, cid = with_connector()
    run(
        p,
        "s",
        devices.ops_set_pin(p, cid, "1", signal=" PWR ", contact_size="20", termination="crimp"),
    )
    x = pin(p, cid, "1")
    assert (x.signal, x.contact_size, x.termination) == ("PWR", "20", "crimp")
    run(p, "m", devices.ops_set_pin(p, cid, "1", mode="fixed"))
    assert (pin(p, cid, "1").fixed, pin(p, cid, "1").locked) == (True, False)
    assert devices.pin_mode(pin(p, cid, "1")) == "fixed"
    run(p, "m", devices.ops_set_pin(p, cid, "1", mode="locked"))
    assert (pin(p, cid, "1").fixed, pin(p, cid, "1").locked) == (False, True)
    run(p, "m", devices.ops_set_pin(p, cid, "1", fixed=True))
    assert devices.pin_mode(pin(p, cid, "1")) == "locked"  # locked wins
    run(p, "m", devices.ops_set_pin(p, cid, "1", mode="free", signal="", contact_size=None))
    assert pin(p, cid, "1") == Pin(id="1", termination="crimp")
    assert devices.ops_set_pin(p, cid, "1", termination="crimp") == []


def test_set_pin_errors() -> None:
    p, cid = with_connector()
    assert "no pin '9'" in refused(devices.ops_set_pin, p, cid, "9", signal="X")
    assert "cannot be changed here" in refused(devices.ops_set_pin, p, cid, "1", id="Z")
    assert "cannot be changed here" in refused(
        devices.ops_set_pin, p, cid, "1", interface_id="IF-001"
    )
    assert "1 to 200 characters" in refused(devices.ops_set_pin, p, cid, "1", signal="x" * 201)
    assert "1 to 200 characters" in refused(devices.ops_set_pin, p, cid, "1", signal="a\x00b")
    assert "termination" in refused(devices.ops_set_pin, p, cid, "1", termination="weld")
    assert "free, fixed, locked" in refused(devices.ops_set_pin, p, cid, "1", mode="auto")
    assert "yes or no" in refused(devices.ops_set_pin, p, cid, "1", fixed="yes")
    assert "must be text" in refused(devices.ops_set_pin, p, cid, "1", signal=5)


def test_retyping_the_signal_of_an_allocated_pin_takes_the_pin_over() -> None:
    p, cid = with_connector()
    c = p.connectors[cid]
    pins = [evolve(x, signal="CANH", interface_id="IF-001") if x.id == "1" else x for x in c.pins]
    p.connectors[cid] = evolve(c, pins=pins)
    run(p, "same", devices.ops_set_pin(p, cid, "1", contact_size="22"))
    assert pin(p, cid, "1").interface_id == "IF-001"
    run(p, "edit", devices.ops_set_pin(p, cid, "1", signal="PWR"))
    assert pin(p, cid, "1").interface_id is None and pin(p, cid, "1").signal == "PWR"


def test_add_pins_numbers_positions_and_limits() -> None:
    p, cid = with_connector("MY-PLAIN-4")
    run(p, "d", devices.ops_delete_pins(p, cid, ["2", "3"]))
    run(p, "a", devices.ops_add_pins(p, cid, after="1"))
    assert [x.id for x in p.connectors[cid].pins] == ["1", "2", "4"]  # counted on from pin 1
    run(p, "a", devices.ops_add_pins(p, cid, ["A1"], after="4"))
    assert [x.id for x in p.connectors[cid].pins] == ["1", "2", "4", "A1"]
    assert "more than 4 pins" in refused(devices.ops_add_pins, p, cid)
    assert "listed twice" in refused(devices.ops_add_pins, p, cid, ["a1"])
    assert "pin name" in refused(devices.ops_add_pins, p, cid, ["a b"])
    assert devices.ops_add_pins(p, cid, count=0) == []
    p2, c2 = with_connector()
    run(p2, "d", devices.ops_delete_pins(p2, c2, ["1", "2", "3", "4", "5", "6"]))
    run(p2, "a", devices.ops_add_pins(p2, c2, count=3))
    assert [x.id for x in p2.connectors[c2].pins] == ["1", "2", "3"]
    assert "no pin 'Z'" in refused(devices.ops_add_pins, p2, c2, after="Z")


def test_delete_pins_and_the_impact_line() -> None:
    p, cid = with_connector()
    c = p.connectors[cid]
    pins = [
        evolve(x, signal="CANH", interface_id="IF-011") if x.id in ("3", "4") else x for x in c.pins
    ]
    p.connectors[cid] = evolve(c, pins=pins)
    p.harnesses["W003"] = Harness(
        id="W003", name="gen", generated=True,
        connectors=[Connector(id="W003-P1", name="P1", role="cable", part_id="MY-HD-6-M", mates_with=cid)],
    )  # fmt: skip
    impact = devices.pin_impact(p, cid, ["3", "4", "6"])
    assert impact.interfaces == (("IF-011", ("3", "4")),) and impact.outdated_harnesses == ("W003",)
    assert impact.sentence() == "used by IF-011 on pins 3 and 4; W003 will be out of date"
    assert devices.pin_impact(p, cid, ["6"]).sentence() == "W003 will be out of date"
    run(p, "del", devices.ops_delete_pins(p, cid, ["3", "4"]))
    assert [x.id for x in p.connectors[cid].pins] == ["1", "2", "5", "6"]
    assert devices.ops_delete_pins(p, cid, []) == []
    assert "no pin 'Q'" in refused(devices.ops_delete_pins, p, cid, ["Q"])


def test_hand_made_harness_blocks_delete_and_rename_of_a_pin() -> None:
    p, cid = with_connector()
    p.harnesses["HX"] = Harness(
        id="HX", name="by hand", generated=False,
        connectors=[Connector(id="HX-P1", name="P1", role="cable", part_id="MY-HD-6-M", mates_with=cid,
                              pins=[Pin(id=str(i)) for i in range(1, 7)])],
        wires=[Wire(id="HX-W1", from_connector="HX-P1", from_pin="2", to_connector="HX-P1", to_pin="3")],
    )  # fmt: skip
    assert "HX (made by hand or released)" in refused(devices.ops_delete_pins, p, cid, ["2"])
    assert "HX" in refused(devices.ops_rename_pin, p, cid, "3", "C3")
    run(p, "ok", devices.ops_delete_pins(p, cid, ["1"]))  # an unused pin goes
    run(p, "ok", devices.ops_rename_pin(p, cid, "4", "D4"))
    assert "HX" in refused(
        devices.ops_set_pinout, p, cid, [x for x in p.connectors[cid].pins if x.id != "2"]
    )


def test_rename_pin() -> None:
    p, cid = with_connector()
    run(p, "s", devices.ops_set_pin(p, cid, "1", signal="PWR", mode="fixed"))
    run(p, "r", devices.ops_rename_pin(p, cid, "1", "A1"))
    ids = [x.id for x in p.connectors[cid].pins]
    assert ids[0] == "A1" and pin(p, cid, "A1").signal == "PWR" and pin(p, cid, "A1").fixed
    run(p, "r", devices.ops_rename_pin(p, cid, "A1", "a1"))  # only the case: fine
    assert p.connectors[cid].pins[0].id == "a1"
    assert devices.ops_rename_pin(p, cid, "a1", "a1") == []
    assert "already has a pin" in refused(devices.ops_rename_pin, p, cid, "2", "3")
    assert "pin name" in refused(devices.ops_rename_pin, p, cid, "2", "5V+")
    assert "no pin 'ZZ'" in refused(devices.ops_rename_pin, p, cid, "ZZ", "Y")


def test_set_pinout_is_one_put_and_one_undo_step() -> None:
    p, cid = with_connector()
    before = model_hash(p)
    new = [evolve(x, signal=f"S{x.id}") for x in p.connectors[cid].pins]
    ops = devices.ops_set_pinout(p, cid, new)
    assert len(ops) == 1 and isinstance(ops[0], Put)
    h = History(p)
    h.execute("Paste 6 pins", ops)
    assert [x.signal for x in p.connectors[cid].pins] == [f"S{i}" for i in range(1, 7)]
    h.undo()
    assert model_hash(p) == before
    h.redo()
    assert pin(p, cid, "3").signal == "S3"
    assert devices.ops_set_pinout(p, cid, list(p.connectors[cid].pins)) == []
    assert "listed twice" in refused(devices.ops_set_pinout, p, cid, [Pin(id="A"), Pin(id="a")])
    assert "more than 6 pins" in refused(
        devices.ops_set_pinout, p, cid, [Pin(id=str(i)) for i in range(7)]
    )


# ---- rows from a spreadsheet -------------------------------------------------------------------


def test_pasted_rows_update_add_and_report_each_bad_row() -> None:
    p, cid = with_connector()
    rows = [
        {"pin": "1", "signal": "PWR", "mode": "Fixed"},
        {"pin": "A9", "signal": "X", "contact_size": "22", "termination": "Solder"},
        {"pin": "5V+", "signal": "bad"},
        {"pin": "2", "mode": "maybe"},
        {"pin": "3", "termination": "weld"},
        {"pin": "1", "signal": "again"},
        {"pin": "a9"},
        {"pin": ""},
    ]
    plan = devices.plan_pin_rows(p, cid, rows)
    assert not plan.ok
    assert [i.row for i in plan.issues] == [3, 4, 5, 6, 7, 8]
    assert "pin name" in plan.issues[0].reason and "mode 'maybe'" in plan.issues[1].reason
    assert "weld" in plan.issues[2].reason and "listed again (row 1)" in plan.issues[3].reason
    assert "pin name is empty" in plan.issues[5].reason
    assert plan.added == ("A9",) and plan.changed == ("1",)
    assert "row 3" in refused(devices.ops_paste_rows, p, cid, rows) and "and 5 more" in refused(
        devices.ops_paste_rows, p, cid, rows
    )
    good = [rows[0], rows[1]]
    # 7 pins on a 6 pin part is refused by the plan
    assert "more than 6 pins" in refused(devices.ops_paste_rows, p, cid, good)
    run(
        p,
        "paste",
        devices.ops_paste_rows(
            p,
            cid,
            [rows[0], {"pin": "2", "signal": "RTN", "mode": "fixed", "termination": "crimp"}],
        ),
    )
    assert (pin(p, cid, "1").signal, pin(p, cid, "1").fixed) == ("PWR", True)
    assert pin(p, cid, "2").termination == "crimp"


def test_rows_with_replace_drop_the_pins_they_do_not_name() -> None:
    p, cid = with_connector()
    plan = devices.plan_pin_rows(
        p, cid, [{"pin": "A1", "signal": "PWR"}, {"pin": "2", "signal": ""}], replace=True
    )
    assert plan.ok and [x.id for x in plan.pins] == ["A1", "2"]
    assert set(plan.removed) == {"1", "3", "4", "5", "6"} and plan.added == ("A1",)
    run(
        p,
        "import",
        devices.ops_paste_rows(
            p, cid, [{"pin": "A1", "signal": "PWR"}, {"pin": "2"}], replace=True
        ),
    )
    assert {x.id for x in p.connectors[cid].pins} == {"A1", "2"}
    # an empty cell of a column that is present clears it; an absent column leaves it alone
    run(p, "s", devices.ops_set_pin(p, cid, "2", signal="KEEP", contact_size="20"))
    run(p, "p", devices.ops_paste_rows(p, cid, [{"pin": "2", "contact_size": ""}]))
    assert (pin(p, cid, "2").signal, pin(p, cid, "2").contact_size) == ("KEEP", None)
    # a pin whose name differs only in case from an existing one is a clash, not a new pin
    assert not devices.plan_pin_rows(p, cid, [{"pin": "a1"}]).ok


# ---- interface types on pins (CD-C8) -----------------------------------------------------------


def test_fill_from_type_writes_signals_in_order_and_fixes_the_pins() -> None:
    p, cid = with_connector()
    run(p, "fill", devices.fill_from_type(p, cid, ["3", "4"], "can"))
    assert [(x.id, x.signal, x.fixed) for x in p.connectors[cid].pins[2:4]] == [
        ("3", "CANH", True),
        ("4", "CANL", True),
    ]
    run(p, "fill", devices.fill_from_type(p, cid, ["1", "2"], "power_primary", fixed=False))
    assert (pin(p, cid, "1").signal, pin(p, cid, "1").fixed) == ("PWR", False)
    assert "2 signals (CANH, CANL); 3 pins are selected" in refused(
        devices.fill_from_type, p, cid, ["1", "2", "3"], "can"
    )
    assert "1 pin is selected" in refused(devices.fill_from_type, p, cid, ["1"], "can")
    assert "does not exist" in refused(devices.fill_from_type, p, cid, ["1"], "nope")
    assert "no pin 'Z'" in refused(devices.fill_from_type, p, cid, ["1", "Z"], "can")
    assert "listed twice" in refused(devices.fill_from_type, p, cid, ["1", "1"], "can")


def test_suggest_carries_lists_complete_types_only() -> None:
    p, cid = with_connector()
    assert devices.suggest_carries(p, cid) == []
    run(p, "f", devices.fill_from_type(p, cid, ["3", "4"], "can"))
    run(p, "f", devices.fill_from_type(p, cid, ["1", "2"], "power_primary"))
    assert devices.suggest_carries(p, cid) == ["can", "power_primary", "power_secondary"]
    run(p, "c", devices.ops_set_pin(p, cid, "4", signal=""))
    assert devices.suggest_carries(p, cid) == ["power_primary", "power_secondary"]


# ---- the pinout as exported, the table the view reads (CD-C11) ---------------------------------


def test_pinout_table_is_the_rows_of_box_pinouts_for_this_device_only() -> None:
    from harness_design_studio.core.outputs.tables import box_pinouts

    p, cid = with_connector()
    ops, cid2 = devices.ops_add_connector(p, "GYRO1", part_id="MY-PLAIN-4")
    run(p, "a", ops)
    run(p, "f", devices.fill_from_type(p, cid, ["3", "4"], "can"))
    table = devices.pinout_table(p, "GYRO1")
    everything = box_pinouts(p)
    assert table[0] == everything[0]
    assert table[1:] == [r for r in everything[1:] if r[0] in (cid, cid2)]
    assert len(table) == 1 + 6 + 4
    assert ["GYRO1-J01", "box", "", "MY-HD-6-F", "3", "CANH", "", "", "no"] in table
    assert ["GYRO1-J01", "box", "", "MY-HD-6-F", "1", "", "", "", "yes"] in table
    assert box_pinouts(p) == everything  # the full table is unchanged by the filter argument
    assert "does not exist" in refused(devices.pinout_table, p, "NOPE")


def test_pin_rows_derive_direction_and_class_and_never_guess() -> None:
    p, cid = with_connector()
    run(p, "f", devices.fill_from_type(p, cid, ["3", "4"], "can"))
    run(p, "f", devices.ops_set_pin(p, cid, "1", signal="PWR"))
    run(p, "f", devices.ops_set_pin(p, cid, "2", signal="HEATER_ENABLE"))
    rows = {r.pin: r for r in devices.pin_rows(p, cid)}
    assert (rows["3"].direction, rows["3"].category, rows["3"].mode) == ("bidir", "data", "fixed")
    assert "CAN" in rows["3"].note or "can" in rows["3"].note.lower()
    assert (rows["1"].direction, rows["1"].category) == (
        "passive",
        "power",
    )  # both power types agree
    assert (rows["2"].direction, rows["2"].category) == ("", "")
    assert "No interface type has a signal called 'HEATER_ENABLE'" in rows["2"].note
    assert rows["5"].spare and not rows["3"].spare and rows["5"].note == "No signal on this pin."
    assert rows["2"].severity == "info"  # CD-K4
    # RTN is a signal of power and discrete types: the meaning is the same (passive), but the class
    # differs, so nothing is claimed
    run(p, "f", devices.ops_set_pin(p, cid, "5", signal="RTN"))
    five = next(r for r in devices.pin_rows(p, cid) if r.pin == "5")
    assert (five.direction, five.category) == ("", "") and "different meanings" in five.note


def test_pin_rows_with_an_interface_use_its_type() -> None:
    p = new_project()
    ops, a = edit.ops_add_unit(p, "computer")
    run(p, "u", ops)
    ops, b = edit.ops_add_unit(p, "power")
    run(p, "u", ops)
    ops, iid = edit.ops_add_interface(p, "discrete", a, b)
    run(p, "i", ops)
    cid = next(e.connector_id for e in p.interfaces[iid].endpoints if e.unit_id == a)
    assert cid
    c = p.connectors[cid]
    p.connectors[cid] = evolve(
        c, pins=[evolve(c.pins[0], signal="RTN", interface_id=iid, locked=True), *c.pins[1:]]
    )
    row = devices.pin_rows(p, cid)[0]
    assert (row.direction, row.category, row.interface_id) == ("passive", "discrete", iid)
    assert not row.auto and row.mode == "locked"
    p.connectors[cid] = evolve(
        p.connectors[cid], pins=[evolve(c.pins[0], signal="RTN", interface_id=iid), *c.pins[1:]]
    )
    assert devices.pin_rows(p, cid)[0].auto


# ---- inline checks, CD-X6: each with a positive and a quiet case -------------------------------


def codes(p: Project, cid: str) -> set[str]:
    return {x.code for x in devices.pinout_problems(p, cid)}


def test_k1_pin_names_that_clash_ignoring_case() -> None:
    p, cid = with_connector()
    assert not {"pin_same_ignoring_case", "pin_listed_twice"} & codes(p, cid)
    c = p.connectors[cid]
    p.connectors[cid] = evolve(c, pins=[Pin(id="A1"), Pin(id="a1"), Pin(id="A1"), *c.pins[3:]])
    found = {x.code: x for x in devices.pinout_problems(p, cid)}
    assert (
        found["pin_same_ignoring_case"].severity == "error"
        and found["pin_same_ignoring_case"].check == "CD-K1"
    )
    assert found["pin_listed_twice"].pin_id == "A1"


def test_k2_pin_count_against_the_part() -> None:
    p, cid = with_connector()
    assert not {"too_many_pins", "pins_missing"} & codes(p, cid)
    run(p, "d", devices.ops_delete_pins(p, cid, ["6"]))
    found = [x for x in devices.pinout_problems(p, cid) if x.check == "CD-K2"]
    assert [(x.severity, x.message) for x in found] == [("info", "5 of 6 pins defined.")]
    c = p.connectors[cid]
    p.connectors[cid] = evolve(
        c, pins=[*c.pins, Pin(id="7"), Pin(id="8")]
    )  # (integrity would refuse)
    assert (
        next(x for x in devices.pinout_problems(p, cid) if x.code == "too_many_pins").severity
        == "error"
    )


def test_k3_same_signal_on_two_pins() -> None:
    p, cid = with_connector()
    run(p, "s", devices.ops_set_pin(p, cid, "1", signal="PWR"))
    assert "signal_on_two_pins" not in codes(p, cid)
    run(p, "s", devices.ops_set_pin(p, cid, "2", signal="PWR"))
    found = next(x for x in devices.pinout_problems(p, cid) if x.code == "signal_on_two_pins")
    assert found.severity == "warning" and "pins 1, 2" in found.message and found.pin_id == "2"


def test_k4_signal_no_interface_type_has() -> None:
    p, cid = with_connector()
    run(p, "s", devices.ops_set_pin(p, cid, "1", signal="CANH"))
    assert "signal_unknown" not in codes(p, cid)
    run(p, "s", devices.ops_set_pin(p, cid, "2", signal="canl"))
    found = next(x for x in devices.pinout_problems(p, cid) if x.code == "signal_unknown")
    assert (
        found.severity == "info" and "Did you mean CANL?" in found.message and found.pin_id == "2"
    )


def test_k5_incomplete_interface_type_on_a_fixed_pinout_only() -> None:
    p, cid = with_connector()
    run(
        p, "s", devices.ops_set_pin(p, cid, "3", signal="CANH")
    )  # free: the allocator is not involved
    assert "interface_incomplete" not in codes(p, cid)
    run(p, "s", devices.ops_set_pin(p, cid, "3", mode="fixed"))
    found = next(x for x in devices.pinout_problems(p, cid) if x.code == "interface_incomplete")
    assert (
        found.severity == "warning" and "CANH of CAN is here but CANL has no pin" in found.message
    )
    run(p, "s", devices.ops_set_pin(p, cid, "4", signal="CANL", mode="fixed"))
    assert "interface_incomplete" not in codes(p, cid)
    # PWR and RTN complete both power types: the lone RTN of the discrete type is explained by them
    run(p, "s", devices.fill_from_type(p, cid, ["1", "2"], "power_primary"))
    assert "interface_incomplete" not in codes(p, cid)


def test_k6_locked_pin_and_its_interface() -> None:
    p = new_project()
    ops, a = edit.ops_add_unit(p, "computer")
    run(p, "u", ops)
    ops, b = edit.ops_add_unit(p, "pdu")
    run(p, "u", ops)
    ops, iid = edit.ops_add_interface(p, "can", a, b)
    run(p, "i", ops)
    cid = next(e.connector_id for e in p.interfaces[iid].endpoints if e.unit_id == a)
    other = next(c.id for c in edit.unit_connectors(p, a) if c.id != cid)
    assert cid and other

    def lock(conn: str, sig: str | None, interface: str) -> None:
        c = p.connectors[conn]
        p.connectors[conn] = evolve(
            c,
            pins=[evolve(c.pins[0], locked=True, signal=sig, interface_id=interface), *c.pins[1:]],
        )

    lock(cid, "CANH", iid)
    assert not {
        "locked_pin_wrong_connector",
        "locked_pin_wrong_signal",
        "locked_pin_interface_missing",
    } & codes(p, cid)
    lock(other, "CANH", iid)
    assert "locked_pin_wrong_connector" in codes(p, other)
    lock(cid, "TX+", iid)
    found = next(x for x in devices.pinout_problems(p, cid) if x.code == "locked_pin_wrong_signal")
    assert found.severity == "error" and "not a signal of CAN" in found.message
    lock(cid, "CANH", "IF-999")
    assert "locked_pin_interface_missing" in codes(p, cid)


def test_k7_gender_nobody_states() -> None:
    p, cid = with_connector()
    assert "gender_unspecified" not in codes(p, cid)  # the part says female
    ops, c2 = devices.ops_add_connector(p, "GYRO1", part_id="MY-PLAIN-4")
    run(p, "a", ops)
    found = next(x for x in devices.pinout_problems(p, c2) if x.code == "gender_unspecified")
    assert found.severity == "warning"
    run(p, "g", devices.ops_update_connector(p, c2, gender="male"))
    assert "gender_unspecified" not in codes(p, c2)


def test_k8_carries_a_type_the_pins_cannot_complete() -> None:
    p, cid = with_connector()
    run(p, "c", devices.ops_update_connector(p, cid, carries=["can"]))
    assert "carries_incomplete" not in codes(
        p, cid
    )  # not a fixed pinout: the allocator places them
    run(p, "s", devices.fill_from_type(p, cid, ["1", "2"], "power_primary"))
    found = next(x for x in devices.pinout_problems(p, cid) if x.code == "carries_incomplete")
    assert (
        found.severity == "warning" and "no CANH, CANL" in found.message and "CAN" in found.message
    )
    run(p, "s", devices.fill_from_type(p, cid, ["3", "4"], "can"))
    assert "carries_incomplete" not in codes(p, cid)


def test_problems_are_sorted_worst_first() -> None:
    p, cid = with_connector()
    c = p.connectors[cid]
    p.connectors[cid] = evolve(c, pins=[Pin(id="A1", signal="zz"), Pin(id="a1"), *c.pins[2:5]])
    severities = [x.severity for x in devices.pinout_problems(p, cid)]
    rank = {"error": 0, "warning": 1, "info": 2}
    assert [rank[x] for x in severities] == sorted(rank[x] for x in severities)


# ---- locks: closing the hole in the planners (CD-C13, CD-X3) -----------------------------------


def released(tmp_path: Path) -> tuple[Project, str, str]:
    """A project with a released harness; the box connector it mates with and one of its spare pins."""
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    h = p.harnesses[hid]
    cid = next(c.mates_with for c in h.connectors if c.mates_with)
    assert cid is not None
    return p, hid, cid


def test_the_hole_exists_in_check_locks_and_is_closed_in_the_planner(tmp_path: Path) -> None:
    p, hid, cid = released(tmp_path)
    spare = next(x for x in p.connectors[cid].pins if not x.signal and not x.interface_id)
    raw: Op = Put(
        "connectors",
        evolve(p.connectors[cid], pins=[x for x in p.connectors[cid].pins if x.id != spare.id]),
    )
    check_locks(p, [raw])  # CD-G15: the old rule lets this through (and is not changed)
    why = devices.pin_set_frozen(p, cid)
    assert why and hid in why and "start a new revision" in why
    assert why.startswith(f"Connector {cid} is used by {hid}, which is released.")
    msg = refused(devices.ops_delete_pins, p, cid, [spare.id])
    assert why in msg
    assert why in refused(devices.ops_add_pins, p, cid)
    assert why in refused(devices.ops_rename_pin, p, cid, spare.id, "ZZ9")
    assert why in refused(
        devices.ops_set_pinout, p, cid, [x for x in p.connectors[cid].pins if x.id != spare.id]
    )
    assert why in refused(devices.ops_delete_connector, p, cid)
    assert why in refused(devices.ops_change_part, p, cid, "EX-MICROD-31-M")
    assert why in refused(
        devices.ops_update_connector,
        p,
        cid,
        gender="unspecified" if p.connectors[cid].gender != "unspecified" else "male",
    )
    assert why in refused(devices.ops_update_connector, p, cid, keying="Z")
    assert devices.ops_update_connector(p, cid, notes="a note")  # cosmetic fields stay editable
    assert devices.ops_update_connector(p, cid, name="Renamed")


def test_a_spare_pin_of_a_frozen_connector_stays_editable_and_a_released_pin_does_not(
    tmp_path: Path,
) -> None:
    p, hid, cid = released(tmp_path)
    spare = next(x for x in p.connectors[cid].pins if not x.signal and not x.interface_id)
    ops = devices.ops_set_pin(p, cid, spare.id, signal="SPARE_TEST", contact_size="22")
    History(p).execute("edit spare", ops)  # accepted by the real lock check as well
    assert pin(p, cid, spare.id).signal == "SPARE_TEST"
    used = next(x for x in p.connectors[cid].pins if x.interface_id)
    why = devices.pin_lock_reason(p, cid, used.id)
    assert why and f"{cid}" in why and hid in why
    assert why in refused(devices.ops_set_pin, p, cid, used.id, signal="X")
    assert why in refused(devices.fill_from_type, p, cid, [used.id], "ground")
    # the sentence is the one the real check gives for the same edit
    with pytest.raises(TransactionError) as exc:
        check_locks(
            p,
            [
                Put(
                    "connectors",
                    evolve(
                        p.connectors[cid],
                        pins=[
                            evolve(used, signal="X") if x.id == used.id else x
                            for x in p.connectors[cid].pins
                        ],
                    ),
                )
            ],
        )
    assert any(why == line for line in exc.value.problems)
    assert devices.pin_lock_reason(p, cid, spare.id) is None
    rows = {r.pin: r for r in devices.pin_rows(p, cid)}
    assert rows[used.id].lock == why and rows[spare.id].lock is None


def test_a_connector_a_release_does_not_use_is_free(tmp_path: Path) -> None:
    p, hid, cid = released(tmp_path)
    free = next(c.id for c in p.connectors.values() if devices.pin_set_frozen(p, c.id) is None)
    spare = p.connectors[free].pins[-1].id
    History(p).execute("del", devices.ops_delete_pins(p, free, [spare]))
    assert spare not in {x.id for x in p.connectors[free].pins}
    assert devices.pin_set_frozen(p, "NOPE") is None


def test_device_state_draft_in_use_locked_and_read_only(tmp_path: Path) -> None:
    p = new_project()
    ops, a = edit.ops_add_unit(p, "computer")
    run(p, "u", ops)
    ops, b = edit.ops_add_unit(p, "pdu")
    run(p, "u", ops)
    s = devices.device_state(p, a)
    assert s.state == "draft" and s.interfaces == () and "No interface ends on" in s.sentence
    ops, iid = edit.ops_add_interface(p, "can", a, b)
    run(p, "i", ops)
    s = devices.device_state(p, a)
    assert s.state == "in_use" and s.interfaces == (iid,) and iid in s.sentence
    p.read_only = True
    s = devices.device_state(p, a)
    assert s.state == "read_only" and "read-only" in s.sentence
    assert "does not exist" in refused(devices.device_state, p, "NOPE")
    q, hid, cid = released(tmp_path)
    unit = q.connectors[cid].unit_id
    assert unit
    s = devices.device_state(q, unit)
    assert s.state == "locked" and s.released_by[0].harness_id == hid
    assert hid in s.sentence and "released" in s.sentence
    unlocked = next(u for u in q.units if devices.device_state(q, u).state != "locked")
    assert devices.device_state(q, unlocked).released_by == ()


# ---- everything goes through History: undo and redo restore the project (CD-X1) ----------------


def test_every_planner_is_one_undoable_step() -> None:
    p, cid = with_connector()
    h = History(p)
    start = model_hash(p)
    steps: list[tuple[str, list[Op]]] = [
        ("set", devices.ops_set_pin(p, cid, "1", signal="PWR", mode="fixed")),
        ("fill", devices.fill_from_type(p, cid, ["3", "4"], "can")),
    ]
    for label, ops in steps:
        h.execute(label, ops)
    h.execute("part", devices.ops_change_part(p, cid, "MY-BIG-8-M"))
    h.execute("rename", devices.ops_rename_pin(p, cid, "1", "A1"))
    h.execute("del", devices.ops_delete_pins(p, cid, ["2"]))
    h.execute("conn", devices.ops_update_connector(p, cid, name="Main"))
    after = model_hash(p)
    assert h.next_undo_label == "conn"
    for _ in range(6):
        h.undo()
    assert model_hash(p) == start
    for _ in range(6):
        h.redo()
    assert model_hash(p) == after
    assert errors(check_integrity(p)) == []


_ACTIONS = st.lists(
    st.tuples(
        st.integers(0, 7),
        st.integers(0, 9),
        st.sampled_from(["A1", "a1", "7", "X", "CANH", "CANL", "PWR", ""]),
    ),
    max_size=14,
)


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_ACTIONS)
def test_random_device_edits_with_undo_and_redo_keep_the_project_clean(
    actions: list[tuple[int, int, str]],
) -> None:
    """CD-X2: any mix of planners (refused ones are skipped) leaves integrity clean after each
    step, and undoing every step gives back the first state, redoing every step the last."""
    p, cid = with_connector()
    h = History(p)
    first = model_hash(p)
    done = 0
    for kind, k, word in actions:
        c = p.connectors.get(cid)
        if c is None:
            break
        pins = [x.id for x in c.pins]
        some = pins[k % len(pins)] if pins else "1"
        try:
            if kind == 0:
                ops = devices.ops_set_pin(p, cid, some, signal=word)
            elif kind == 1:
                ops = devices.ops_rename_pin(p, cid, some, word or "Q")
            elif kind == 2:
                ops = devices.ops_add_pins(p, cid, [word] if word else None)
            elif kind == 3:
                ops = devices.ops_delete_pins(p, cid, [some])
            elif kind == 4:
                ops = devices.ops_change_part(
                    p, cid, ["MY-HD-6-F", "MY-BIG-8-M", "MY-PLAIN-4"][k % 3]
                )
            elif kind == 5:
                ops = devices.ops_paste_rows(p, cid, [{"pin": word or "9", "signal": word}])
            elif kind == 6:
                ops = devices.fill_from_type(p, cid, pins[:2], ["can", "power_primary"][k % 2])
            else:
                ops = devices.ops_update_connector(p, cid, carries=[["can"], ["rs485"], []][k % 3])
        except EditError:
            continue
        before = model_hash(p)
        try:
            h.execute("step", ops)
        except TransactionError:
            assert model_hash(p) == before  # rolled back
            continue
        if ops:
            done += 1
        assert errors(check_integrity(p)) == []
    last = model_hash(p)
    for _ in range(done):
        h.undo()
    assert model_hash(p) == first
    for _ in range(done):
        h.redo()
    assert model_hash(p) == last


def test_connector_removed_by_undo_of_add() -> None:
    p = device()
    h = History(p)
    ops, cid = devices.ops_add_connector(p, "GYRO1", part_id="MY-HD-6-F")
    h.execute("add", ops)
    assert cid in p.connectors
    h.undo()
    assert cid not in p.connectors
    h.redo()
    assert cid in p.connectors
    assert isinstance(ops[0], Put) and not any(isinstance(o, Delete) for o in ops)


@pytest.mark.perf
def test_a_cell_edit_takes_under_100_ms_at_1000_pins_and_100_units() -> None:
    """CD-X8, the headless part: plan + History.execute of one pin edit."""
    import time

    from harness_design_studio.core.samples import stress_project
    from tests.helpers import time_limit

    p = stress_project(units=100, interfaces=600)
    p.parts["BIG-1000"] = Part(id="BIG-1000", category="connector", pin_count=1000)
    ops, cid = devices.ops_add_connector(p, next(iter(p.units)), part_id="BIG-1000")
    h = History(p)
    h.execute("add", ops)
    assert len(p.connectors[cid].pins) == 1000
    worst = 0.0
    for k in range(5):
        start = time.perf_counter()
        h.execute("edit", devices.ops_set_pin(p, cid, "500", signal=f"S{k}"))
        worst = max(worst, time.perf_counter() - start)
    assert worst < time_limit(0.1), worst
    start = time.perf_counter()
    devices.pin_rows(p, cid)
    assert time.perf_counter() - start < time_limit(0.1)


# ---- a new device, interface on pins, pasted cells, parts and interface types ---------------------


def test_add_device_makes_an_empty_unit_in_a_free_slot() -> None:
    p = new_project()
    ops, uid = devices.ops_add_device(p)
    run(p, "add", ops)
    assert uid == "DEV1" and p.units[uid].name == "Device 1" and p.units[uid].side == "nominal"
    assert p.units[uid].subsystem == "general" and edit.unit_connectors(p, uid) == []
    assert uid in p.placements
    ops, uid2 = devices.ops_add_device(
        p, name="Gyro", subsystem="aocs", side="redundant", zone="panel-B"
    )
    run(p, "add", ops)
    assert uid2 == "DEV2" and p.units[uid2].zone == "panel-B" and p.units[uid2].subsystem == "aocs"
    assert devices.default_subsystem(p) == "aocs"  # one each: the first by name
    assert len({(v.x, v.y) for v in p.placements.values()}) == 2
    ops, uid3 = devices.ops_add_device(p, unit_id="GYRO1")
    assert uid3 == "GYRO1" and len(ops) == 2


def test_add_device_errors() -> None:
    p = new_project()
    run(p, "a", devices.ops_add_device(p, unit_id="G1")[0])
    assert "already used" in refused(devices.ops_add_device, p, unit_id="g1")
    assert "cannot be used as an ID" in refused(devices.ops_add_device, p, unit_id="1G")
    assert "chain" in refused(devices.ops_add_device, p, side="left")
    assert "does not exist" in refused(devices.ops_add_device, p, zone="nowhere")
    assert "1 to 200" in refused(devices.ops_add_device, p, name="x" * 201)
    p.read_only = True
    assert "read-only" in refused(devices.ops_add_device, p)


def test_the_id_of_a_renamed_unit_is_not_free_for_a_new_device() -> None:
    """A renamed unit keeps its connector ids, so its old id would overwrite them."""
    p, cid = with_connector()
    run(p, "rename", edit.ops_rename_unit(p, "GYRO1", "GYRO2"))
    assert "GYRO1" in cid and "already used" in refused(devices.ops_add_device, p, unit_id="GYRO1")


def test_update_device() -> None:
    p = device()
    run(
        p,
        "u",
        devices.ops_update_device(
            p, "GYRO1", name="Gyro 2", subsystem="adcs", side="redundant", notes="n"
        ),
    )
    u = p.units["GYRO1"]
    assert (u.name, u.subsystem, u.side, u.notes) == ("Gyro 2", "adcs", "redundant", "n")
    assert devices.ops_update_device(p, "GYRO1", name="Gyro 2") == []
    assert "needs a name" in refused(devices.ops_update_device, p, "GYRO1", name=" ")
    assert "needs a subsystem" in refused(devices.ops_update_device, p, "GYRO1", subsystem="")
    assert "chain" in refused(devices.ops_update_device, p, "GYRO1", side="x")
    assert "cannot be changed here" in refused(devices.ops_update_device, p, "GYRO1", zone="z")
    assert "does not exist" in refused(devices.ops_update_device, p, "NOPE", name="x")


def test_a_released_device_keeps_its_design_fields_but_not_its_labels(tmp_path: Path) -> None:
    p, hid, cid = released(tmp_path)
    unit = p.connectors[cid].unit_id
    assert unit
    run(p, "labels", devices.ops_update_device(p, unit, name="Renamed", notes="x"))
    why = refused(devices.ops_update_device, p, unit, subsystem="other")
    assert hid in why and "released" in why


def can_link(p: Project, cid: str) -> tuple[str, str]:
    """A CAN link between an OBC and GYRO1 whose GYRO1 end has no connector yet."""
    ops, obc = edit.ops_add_unit(p, "computer")
    run(p, "u", ops)
    ops, iid = edit.ops_add_interface(p, "can", obc, "GYRO1", to_connector=cid)
    run(p, "i", ops)
    i = p.interfaces[iid]
    eps = [
        e.model_copy(update={"connector_id": None, "auto": False}) if e.unit_id == "GYRO1" else e
        for e in i.endpoints
    ]
    p.interfaces[iid] = evolve(i, endpoints=eps)
    return obc, iid


def test_assign_pins_writes_locked_interface_and_signals_and_the_end_gets_the_connector() -> None:
    p, cid = with_connector()
    _obc, iid = can_link(p, cid)
    ops = devices.ops_assign_pins(p, cid, ["3", "4"], iid)
    assert len(ops) == 2  # the connector and the interface's end, one step
    run(p, "assign", ops)
    assert [
        (x.id, x.signal, x.interface_id, x.locked, x.fixed) for x in p.connectors[cid].pins[2:4]
    ] == [("3", "CANH", iid, True, False), ("4", "CANL", iid, True, False)]
    end = next(e for e in p.interfaces[iid].endpoints if e.unit_id == "GYRO1")
    assert end.connector_id == cid and not end.auto
    assert not [x for x in devices.pinout_problems(p, cid) if x.severity == "error"]
    # a second time the end is already on this connector: only the pins change
    assert len(devices.ops_assign_pins(p, cid, ["5", "6"], iid)) == 1
    row = next(r for r in devices.pin_rows(p, cid) if r.pin == "3")
    assert (row.interface_id, row.mode, row.direction, row.auto) == (iid, "locked", "bidir", False)


def test_assign_pins_with_chosen_signals_and_errors() -> None:
    p, cid = with_connector()
    _obc, iid = can_link(p, cid)
    run(p, "a", devices.ops_assign_pins(p, cid, ["5", "2"], iid, ["CANL", "CANH"]))
    assert (pin(p, cid, "5").signal, pin(p, cid, "2").signal) == ("CANL", "CANH")
    assert "needs 2 pins (CANH, CANL); 1 is selected" in refused(
        devices.ops_assign_pins, p, cid, ["1"], iid
    )
    assert "TX+ is not a signal of CAN" in refused(
        devices.ops_assign_pins, p, cid, ["1", "3"], iid, ["TX+", "CANL"]
    )
    assert "one pin only" in refused(
        devices.ops_assign_pins, p, cid, ["1", "3"], iid, ["CANL", "CANL"]
    )
    assert "listed twice" in refused(devices.ops_assign_pins, p, cid, ["1", "1"], iid)
    assert "no pin 'Z'" in refused(devices.ops_assign_pins, p, cid, ["1", "Z"], iid)
    assert "does not exist" in refused(devices.ops_assign_pins, p, cid, ["1", "2"], "IF-999")


def test_assign_pins_refuses_an_interface_that_does_not_end_here_or_another_connector() -> None:
    p, cid = with_connector()
    obc, iid = can_link(p, cid)
    ops, c2 = devices.ops_add_connector(p, "GYRO1", part_id="MY-HD-6-F")
    run(p, "c", ops)
    ops, other = edit.ops_add_unit(p, "computer")
    run(p, "u", ops)
    assert "does not end on" in refused(
        devices.ops_assign_pins,
        p,
        p.connectors[edit.unit_connectors(p, other)[0].id].id,
        ["1", "2"],
        iid,
    )
    # the connector of the interface's end is the first one; the second is refused
    run(p, "assign", devices.ops_assign_pins(p, cid, ["1", "2"], iid))
    assert f"ends on {cid}, not on {c2}" in refused(devices.ops_assign_pins, p, c2, ["1", "2"], iid)
    # a connector that carries another interface is refused with the editor's rule
    ops, iid2 = edit.ops_add_interface(p, "can", other, "GYRO1", to_connector=c2)
    run(p, "i2", ops)
    i2 = p.interfaces[iid2]
    p.interfaces[iid2] = evolve(
        i2,
        endpoints=[
            e.model_copy(update={"connector_id": None}) if e.unit_id == "GYRO1" else e
            for e in i2.endpoints
        ],
    )
    run(p, "c", devices.ops_update_connector(p, cid, carries=["can"]))
    assert "already carries" in refused(
        devices.ops_assign_pins, p, cid, ["3", "4"], iid2
    ) or "not meant" in refused(devices.ops_assign_pins, p, cid, ["3", "4"], iid2)
    run(p, "c", devices.ops_update_connector(p, c2, carries=["rs422"]))
    assert "is not meant for CAN" in refused(devices.ops_assign_pins, p, c2, ["3", "4"], iid2)


def test_unassign_pins_frees_them() -> None:
    p, cid = with_connector()
    _obc, iid = can_link(p, cid)
    run(p, "assign", devices.ops_assign_pins(p, cid, ["3", "4"], iid))
    run(p, "unassign", devices.ops_unassign_pins(p, cid, ["3", "5"]))
    assert pin(p, cid, "3") == Pin(id="3") and pin(p, cid, "4").interface_id == iid
    assert devices.ops_unassign_pins(p, cid, ["1"]) == []
    assert "no pin 'Z'" in refused(devices.ops_unassign_pins, p, cid, ["Z"])


def test_assigned_pins_of_a_released_interface_cannot_be_reassigned(tmp_path: Path) -> None:
    p, hid, cid = released(tmp_path)
    used = next(x for x in p.connectors[cid].pins if x.interface_id)
    why = refused(devices.ops_unassign_pins, p, cid, [used.id])
    assert hid in why and "released" in why


def test_rows_from_a_pasted_block() -> None:
    p, cid = with_connector()
    rows = devices.rows_from_grid(p, cid, "3", ["signal"], [["CANH"], ["CANL"]])
    assert rows == [{"signal": "CANH", "pin": "3"}, {"signal": "CANL", "pin": "4"}]
    run(p, "paste", devices.ops_paste_rows(p, cid, rows))
    assert (pin(p, cid, "3").signal, pin(p, cid, "4").signal) == ("CANH", "CANL")
    named = devices.rows_from_grid(
        p, cid, None, ["pin", "signal", "mode"], [["1", "PWR", "fixed"], ["2"]]
    )
    assert named == [
        {"pin": "1", "signal": "PWR", "mode": "fixed"},
        {"pin": "2", "signal": "", "mode": ""},
    ]
    assert "only 2 pins from 5 down" in refused(
        devices.rows_from_grid, p, cid, "5", ["signal"], [["a"], ["b"], ["c"]]
    )
    assert "starts at" in refused(devices.rows_from_grid, p, cid, None, ["signal"], [["a"]])
    assert "starts at" in refused(devices.rows_from_grid, p, cid, "Z", ["signal"], [["a"]])
    assert "not a column" in refused(devices.rows_from_grid, p, cid, "1", ["wire"], [["a"]])


def test_add_part_is_pending_and_unverified_and_never_approved() -> None:
    p = device()
    ops = devices.ops_add_part(
        p,
        part_id="MY-NEW-12-F",
        pin_count=12,
        gender="female",
        manufacturer="Acme",
        part_number="A-12",
    )
    run(p, "part", ops)
    part = p.parts["MY-NEW-12-F"]
    assert (part.category, part.approval, part.unverified, part.pin_count) == (
        "connector",
        "pending",
        True,
        12,
    )
    assert part.description == "12-pin connector, female" and part.manufacturer == "Acme"
    ops, cid = devices.ops_add_connector(p, "GYRO1", part_id="MY-NEW-12-F")
    run(p, "c", ops)
    assert p.connectors[cid].gender == "female" and len(p.connectors[cid].pins) == 12
    # mating half named: both name each other
    run(
        p,
        "mate",
        devices.ops_add_part(
            p, part_id="MY-NEW-12-M", pin_count=12, gender="male", mates_with="MY-NEW-12-F"
        ),
    )
    assert (
        p.parts["MY-NEW-12-F"].mates_with == "MY-NEW-12-M"
        and p.parts["MY-NEW-12-M"].mates_with == "MY-NEW-12-F"
    )
    # the approval cannot be passed in
    assert "cannot be changed here" in refused(
        devices.ops_update_part, p, "MY-NEW-12-F", approval="approved"
    )


def test_add_part_pair_makes_both_halves() -> None:
    p = device()
    run(
        p,
        "pair",
        devices.ops_add_part_pair(
            p,
            part_id="MY-NEW-9-F",
            pin_count=9,
            gender="female",
            description="Mini D 9-pin, female",
        ),
    )
    a, b = p.parts["MY-NEW-9-F"], p.parts["MY-NEW-9-M"]
    assert (a.mates_with, b.mates_with) == ("MY-NEW-9-M", "MY-NEW-9-F")
    assert a.approval == b.approval == "pending" and a.unverified and b.unverified
    from harness_design_studio.core.describe import part_gender

    assert (part_gender(a), part_gender(b)) == ("female", "male")
    run(
        p,
        "pair",
        devices.ops_add_part_pair(
            p, part_id="OTHER-M", pin_count=3, gender="male", mate_id="OTHER-F"
        ),
    )
    assert (
        p.parts["OTHER-F"].mates_with == "OTHER-M" and part_gender(p.parts["OTHER-F"]) == "female"
    )


def test_part_errors_and_update() -> None:
    p = device()
    assert "already exists" in refused(devices.ops_add_part, p, part_id="my-hd-6-f", pin_count=3)
    assert "pin count" in refused(devices.ops_add_part, p, part_id="X1", pin_count=0)
    assert "pin count" in refused(devices.ops_add_part, p, part_id="X1", pin_count=1001)
    assert "pin count" in refused(devices.ops_add_part, p, part_id="X1", pin_count=True)
    assert "male or female" in refused(
        devices.ops_add_part, p, part_id="X1", pin_count=3, gender="x"
    )
    assert "not a connector part" in refused(
        devices.ops_add_part, p, part_id="X1", pin_count=3, mates_with="EX-LABEL"
    )
    assert "own ID" in refused(
        devices.ops_add_part_pair, p, part_id="Z-F", pin_count=3, mate_id="z-f"
    )
    assert "cannot be used as an ID" in refused(
        devices.ops_add_part_pair, p, part_id="1", pin_count=3
    )
    run(
        p,
        "u",
        devices.ops_update_part(
            p, "MY-PLAIN-4", manufacturer="Acme", description="4 pin, male", pin_count=5
        ),
    )
    assert p.parts["MY-PLAIN-4"].pin_count == 5 and p.parts["MY-PLAIN-4"].manufacturer == "Acme"
    assert devices.ops_update_part(p, "MY-PLAIN-4", manufacturer="Acme") == []
    ops, cid = devices.ops_add_connector(p, "GYRO1", part_id="MY-PLAIN-4")
    run(p, "c", ops)
    assert "has 5 pins; MY-PLAIN-4 cannot have fewer" in refused(
        devices.ops_update_part, p, "MY-PLAIN-4", pin_count=3
    )
    assert "does not exist" in refused(devices.ops_update_part, p, "NOPE", notes="x")
    assert "must be text" in refused(devices.ops_update_part, p, "MY-PLAIN-4", notes=3)


def test_a_part_a_release_uses_cannot_be_edited(tmp_path: Path) -> None:
    p, hid, cid = released(tmp_path)
    part = p.connectors[cid].part_id
    why = refused(devices.ops_update_part, p, part, manufacturer="Acme")
    assert hid in why and "released" in why
    assert devices.ops_update_part(p, part, notes="a note")  # cosmetic


def test_signal_lines() -> None:
    assert devices.parse_signal_lines("CANH bidir BUS\n\nCANL bidir BUS\nGND\n") == [
        ("CANH", "bidir", "BUS"), ("CANL", "bidir", "BUS"), ("GND", "passive", None),
    ]  # fmt: skip
    assert "Line 2: a direction is one of" in refused(devices.parse_signal_lines, "A\nB sideways")
    assert "Line 1: write a name" in refused(devices.parse_signal_lines, "A out P extra")


def test_add_interface_type_is_unverified_and_usable() -> None:
    p, cid = with_connector()
    specs = devices.parse_signal_lines("HEAT_ON out\nHEAT_RTN passive")
    run(
        p,
        "t",
        devices.ops_add_interface_type(
            p, type_id="heater_ctl", name="Heater control", category="discrete", signals=specs
        ),
    )
    t = p.interface_types["heater_ctl"]
    assert t.unverified and [(s.name, s.direction) for s in t.signals] == [
        ("HEAT_ON", "out"),
        ("HEAT_RTN", "passive"),
    ]
    run(p, "fill", devices.fill_from_type(p, cid, ["1", "2"], "heater_ctl"))
    assert pin(p, cid, "1").signal == "HEAT_ON"
    assert devices.suggest_carries(p, cid) == ["heater_ctl"]
    row = next(r for r in devices.pin_rows(p, cid) if r.pin == "1")
    assert (row.direction, row.category) == ("out", "discrete")
    assert "already exists" in refused(
        devices.ops_add_interface_type,
        p,
        type_id="HEATER_CTL",
        name="x",
        category="data",
        signals=specs,
    )
    assert "needs at least one signal" in refused(
        devices.ops_add_interface_type, p, type_id="n1", name="x", category="data", signals=[]
    )
    assert "listed twice" in refused(
        devices.ops_add_interface_type,
        p,
        type_id="n1",
        name="x",
        category="data",
        signals=[("A", "in", None), ("A", "in", None)],
    )
    assert "category is one of" in refused(
        devices.ops_add_interface_type, p, type_id="n1", name="x", category="loud", signals=specs
    )
    assert "construction is one of" in refused(
        devices.ops_add_interface_type,
        p,
        type_id="n1",
        name="x",
        category="data",
        signals=specs,
        construction="rope",
    )
    assert "needs a name" in refused(
        devices.ops_add_interface_type, p, type_id="n1", name=" ", category="data", signals=specs
    )
    assert "direction is one of" in refused(
        devices.ops_add_interface_type,
        p,
        type_id="n1",
        name="n",
        category="data",
        signals=[("A", "up", None)],
    )


def test_update_interface_type() -> None:
    p = device()
    run(
        p,
        "u",
        devices.ops_update_interface_type(
            p,
            "can",
            name="CAN 2.0",
            shielding="overall",
            signals=[
                ("CANH", "bidir", "BUS"),
                ("CANL", "bidir", "BUS"),
                ("CANGND", "passive", None),
            ],
        ),
    )
    t = p.interface_types["can"]
    assert t.name == "CAN 2.0" and t.shielding == "overall" and len(t.signals) == 3
    assert devices.ops_update_interface_type(p, "can", name="CAN 2.0") == []
    assert "cannot be changed here" in refused(
        devices.ops_update_interface_type, p, "can", unverified=False
    )
    assert "shielding is one of" in refused(
        devices.ops_update_interface_type, p, "can", shielding="x"
    )
    assert "needs a name" in refused(devices.ops_update_interface_type, p, "can", name="")
    assert "Signals are a list" in refused(
        devices.ops_update_interface_type, p, "can", signals="CANH"
    )
    assert "does not exist" in refused(devices.ops_update_interface_type, p, "nope", name="x")


def test_an_interface_type_a_release_uses_cannot_be_edited(tmp_path: Path) -> None:
    p, hid, cid = released(tmp_path)
    tid = p.interfaces[
        next(
            iter(
                p.harnesses[hid].interfaces
                or {w.interface_id for w in p.harnesses[hid].wires if w.interface_id}
            )
        )
    ].type_id
    why = refused(
        devices.ops_update_interface_type,
        p,
        tid,
        shielding="none" if p.interface_types[tid].shielding != "none" else "overall",
    )
    assert hid in why
