"""REQ-GUI-13. Release 1.9 W1: the first connector of a device, pairing by pin number and a pasted
pairing. The planners propose; they change nothing."""

import pytest

from harness_design_studio.core import devices, links
from harness_design_studio.core import first_connector as fc
from harness_design_studio.core.commands import History
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.model import Pin, Project
from harness_design_studio.core.pairing import pair_by_number, parse_pairing
from harness_design_studio.core.samples import new_project


def two_devices(a_part: str = "EX-MICROD-9-F", b_part: str = "EX-MICROD-9-M") -> Project:
    p = new_project()
    for uid, part in (("OBC", a_part), ("RW1", b_part)):
        ops, _u, _c = fc.plan_device_with_connector(p, part, unit_id=uid, name=uid)
        History(p).execute("add", ops)
    return p


# ---- the choices ------------------------------------------------------------------------------


def test_the_family_is_the_part_id_without_pins_and_gender() -> None:
    assert fc.part_family("EX-MICROD-15-F") == "EX-MICROD"
    assert fc.part_family("EX-RJ45-M") == "EX-RJ45"
    assert fc.part_family("EX-SMA-F") == "EX-SMA"
    assert fc.part_family("MYPART") == "MYPART"


def test_the_choices_list_family_pins_and_gender_of_the_library() -> None:
    choices = fc.connector_choices(new_project())
    micro = [c for c in choices if c.family == "EX-MICROD"]
    assert {c.pin_count for c in micro} == {9, 15, 21, 25, 31}
    assert {c.gender for c in micro} == {"male", "female"}
    assert {c.label for c in micro} == {"Micro-D"}
    assert [c.part_id for c in micro if c.pin_count == 9] == ["EX-MICROD-9-M", "EX-MICROD-9-F"]


def test_a_device_gets_its_first_connector_in_one_plan() -> None:
    p = new_project()
    ops, uid, cid = fc.plan_device_with_connector(p, "EX-DSUB-15-F", unit_id="OBC", name="Computer")
    History(p).execute("add", ops)
    assert cid is not None
    c = p.connectors[cid]
    assert (uid, cid, c.unit_id, c.name, c.gender) == ("OBC", "OBC-J01", "OBC", "J01", "female")
    assert [x.id for x in c.pins] == [str(k) for k in range(1, 16)]
    assert all(x.signal is None for x in c.pins)
    assert c.part_id == "EX-DSUB-15-F"


def test_no_part_means_a_device_with_no_connector() -> None:
    p = new_project()
    ops, uid, cid = fc.plan_device_with_connector(p, None, unit_id="OBC", name="Computer")
    assert cid is None and [type(o).__name__ for o in ops] == ["Put", "Put"]


def test_a_part_that_does_not_exist_is_refused_with_a_sentence() -> None:
    with pytest.raises(EditError):
        fc.plan_device_with_connector(new_project(), "NOPE", unit_id="OBC", name="Computer")


# ---- pair by pin number -----------------------------------------------------------------------


def test_pin_numbers_pair_pin_for_pin_and_change_nothing() -> None:
    p = two_devices()
    before = model_hash(p)
    found = pair_by_number(p, "OBC-J01", "RW1-J01")
    assert [(x.a_pin, x.b_pin) for x in found.pairs] == [(str(k), str(k)) for k in range(1, 10)]
    assert found.unpaired_a == found.unpaired_b == ()
    assert model_hash(p) == before


def test_a_connector_with_more_pins_leaves_the_rest_unpaired_and_says_so() -> None:
    p = two_devices("EX-MICROD-15-F", "EX-MICROD-9-M")
    found = pair_by_number(p, "OBC-J01", "RW1-J01")
    assert len(found.pairs) == 9
    assert found.unpaired_a == tuple(str(k) for k in range(10, 16)) and found.unpaired_b == ()
    assert any("OBC-J01" in n and "no pin with the same number" in n for n in found.notes)


def test_pins_in_the_table_or_in_another_link_are_not_offered() -> None:
    p = two_devices()
    ops, _lid = links.plan_add_link(p, "OBC-J01", "RW1-J01", [("1", "1")])
    History(p).execute("link", ops)
    again = pair_by_number(p, "OBC-J01", "RW1-J01", skip_a={"2"}, skip_b={"2"})
    assert "1" not in [x.a_pin for x in again.pairs] and "2" not in [x.a_pin for x in again.pairs]
    assert any("already paired in link" in n for n in again.notes)


def test_the_same_device_twice_is_refused() -> None:
    p = two_devices()
    ops, _ = devices.ops_add_connector(p, "OBC", part_id="EX-DSUB-9-M")
    History(p).execute("more", ops)
    with pytest.raises(EditError):
        pair_by_number(p, "OBC-J01", "OBC-J02")


def test_pin_names_that_are_not_numbers_pair_when_equal_ignoring_case() -> None:
    p = two_devices()
    for cid, ids in (("OBC-J01", ["A1", "b2", "C3"]), ("RW1-J01", ["a1", "B2", "D4"])):
        p.connectors[cid] = p.connectors[cid].model_copy(update={"pins": [Pin(id=i) for i in ids]})
    found = pair_by_number(p, "OBC-J01", "RW1-J01")
    assert [(x.a_pin, x.b_pin) for x in found.pairs] == [("A1", "a1"), ("b2", "B2")]
    assert found.unpaired_a == ("C3",) and found.unpaired_b == ("D4",)


# ---- paste a pairing --------------------------------------------------------------------------


def test_two_columns_with_tabs_are_proposed_and_a_heading_is_skipped() -> None:
    p = two_devices()
    found = parse_pairing(p, "OBC-J01", "RW1-J01", "Pin A\tPin B\n1\t4\n2\t3\r\n\n5\t9\n")
    assert [(x.a_pin, x.b_pin) for x in found.pairs] == [("1", "4"), ("2", "3"), ("5", "9")]
    assert not found.notes


def test_commas_semicolons_and_spaces_work_and_more_columns_are_ignored() -> None:
    p = two_devices()
    for text in ("1,2\n3,4", "1;2\n3;4", "1 2\n3 4", "1\t2\tTX\n3\t4\tRX"):
        found = parse_pairing(p, "OBC-J01", "RW1-J01", text)
        assert [(x.a_pin, x.b_pin) for x in found.pairs] == [("1", "2"), ("3", "4")], text


def test_bad_lines_are_named_and_the_good_ones_are_kept() -> None:
    p = two_devices()
    text = "1\t1\n99\t2\n3\t77\n4\n1\t5\n6\t6\n"
    found = parse_pairing(p, "OBC-J01", "RW1-J01", text)
    assert [(x.a_pin, x.b_pin) for x in found.pairs] == [("1", "1"), ("6", "6")]
    joined = " | ".join(found.notes)
    assert "Line 2" in joined and "no pin '99'" in joined
    assert "Line 3" in joined and "no pin '77'" in joined
    assert "Line 4" in joined and "needs a pin" in joined
    assert "Line 5" in joined and "earlier line" in joined


def test_a_pin_already_in_the_table_is_not_taken_again() -> None:
    p = two_devices()
    found = parse_pairing(p, "OBC-J01", "RW1-J01", "1\t1\n2\t2", skip_a={"1"})
    assert [(x.a_pin, x.b_pin) for x in found.pairs] == [("2", "2")]
    assert any("Line 1" in n and "already paired" in n for n in found.notes)


def test_empty_text_says_what_to_paste() -> None:
    found = parse_pairing(two_devices(), "OBC-J01", "RW1-J01", "  \n")
    assert not found.pairs and any("Paste two columns" in n for n in found.notes)


def test_the_proposal_is_not_saved_by_the_planner() -> None:
    p = two_devices()
    before = model_hash(p)
    parse_pairing(p, "OBC-J01", "RW1-J01", "1\t1")
    assert model_hash(p) == before and not p.links
