"""REQ-GUI-08. Workshop feedback M1: the helpers behind the new-device dialog, the meaning of RTN, the list of
damaged files. No Qt."""

from harness_design_studio.core import describe, devices, recovery
from harness_design_studio.core.commands import History
from harness_design_studio.core.model import Project, QuarantinedItem
from harness_design_studio.core.samples import new_project


def add(p: Project, uid: str, name: str = "x") -> None:
    ops, _ = devices.ops_add_device(p, unit_id=uid, name=name)
    History(p).execute("add", ops)


# ---- suggest_device_id ------------------------------------------------------------------------


def test_the_id_comes_from_the_first_word_of_the_name() -> None:
    p = new_project()
    assert devices.suggest_device_id(p, "Star tracker") == "STAR1"
    assert devices.suggest_device_id(p, "  reaction wheel 2") == "REACTION1"
    assert devices.suggest_device_id(p, "OBC") == "OBC1"


def test_the_id_is_made_of_letters_and_digits_and_starts_with_a_letter() -> None:
    p = new_project()
    assert devices.suggest_device_id(p, "Gyro-3 (spare)") == "GYRO3"
    add(p, "GYRO3")
    assert devices.suggest_device_id(p, "Gyro-3 (spare)") == "GYRO31"
    assert devices.suggest_device_id(p, "Étoile") == "ETOILE1"
    assert devices.suggest_device_id(p, "3D camera") == "D1"
    assert devices.suggest_device_id(p, "42 Sun sensor") == "SUN1"  # (a leading number is skipped)
    assert devices.suggest_device_id(p, "") == ""
    assert devices.suggest_device_id(p, "  ---  ") == ""
    assert len(devices.suggest_device_id(p, "A" * 100)) <= 9


def test_the_id_is_unique_in_the_project() -> None:
    p = new_project()
    add(p, "STAR1")
    add(p, "STAR2")
    assert devices.suggest_device_id(p, "Star tracker") == "STAR3"
    assert devices.suggest_device_id(p, "star") == "STAR3"  # (case does not matter)
    assert devices.check_new_device(p, devices.suggest_device_id(p, "Star tracker"), "S") == ""


# ---- check_new_device -------------------------------------------------------------------------


def test_a_good_name_and_id_give_no_reason() -> None:
    assert devices.check_new_device(new_project(), "STAR1", "Star tracker") == ""


def test_each_reason_is_a_plain_sentence() -> None:
    p = new_project()
    add(p, "OBC1")
    assert devices.check_new_device(p, "X1", "") == "A device needs a name."
    assert devices.check_new_device(p, "X1", "   ") == "A device needs a name."
    assert devices.check_new_device(p, "", "Camera") == "A device needs an ID."
    assert "cannot be used as an ID" in devices.check_new_device(p, "1abc", "Camera")
    assert "cannot be used as an ID" in devices.check_new_device(p, "A B", "Camera")
    assert "reserved" in devices.check_new_device(p, "CON", "Camera")
    assert (
        devices.check_new_device(p, "OBC1", "Camera")
        == "ID OBC1 is already used by another device."
    )
    assert devices.check_new_device(p, "obc1", "Camera").endswith("already used by another device.")
    assert "1 to 200 characters" in devices.check_new_device(p, "X1", "n" * 201)


def test_the_checked_values_are_the_values_that_are_added() -> None:
    p = new_project()
    name, uid = "Star tracker", devices.suggest_device_id(p, "Star tracker")
    assert devices.check_new_device(p, uid, name) == ""
    ops, got = devices.ops_add_device(p, unit_id=uid, name=name, subsystem="aocs")
    History(p).execute("add", ops)
    assert got == "STAR1" and p.units["STAR1"].name == "Star tracker"
    assert p.units["STAR1"].subsystem == "aocs"


# ---- the meaning of a signal name -------------------------------------------------------------


def test_rtn_and_gnd_are_explained_and_other_names_are_not() -> None:
    assert (
        describe.signal_meaning("RTN") == "Return line: where the current of the signal comes back"
    )
    assert describe.signal_meaning("rtn ") == describe.signal_meaning("RTN")
    assert describe.signal_meaning("GND") == "Ground"
    for other in ("", "PWR", "SIG", "CANH", "HEAT_RTN"):
        assert describe.signal_meaning(other) == ""


# ---- the files that could not be loaded -------------------------------------------------------


def test_damaged_files_lists_each_file_once_sorted() -> None:
    p = new_project()
    assert recovery.damaged_files(p) == []
    p.quarantine_files = {"logical/units/b.json": b"{", "a.json": b"["}
    p.quarantine.append(QuarantinedItem("logical/units/c.json", "unit", "bad", {}))
    p.quarantine.append(QuarantinedItem("logical/units/c.json", "unit", "bad", {}))
    assert recovery.damaged_files(p) == ["a.json", "logical/units/b.json", "logical/units/c.json"]
