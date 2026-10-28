"""REQ-CC-04, A-2 (audit 1.8.0, 1.9.0): the box pins that the wires of a released harness reach are
frozen with the release, also for a harness made from a link or by hand (it has no interface to
say which pins it uses). The edit that would change one is refused with the harness named; the
other pins of the same connector stay editable."""

import json
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import links
from harness_design_studio.core.commands import Delete, History, Put, apply_ops
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Pin, Project, evolve
from harness_design_studio.core.outputs.build import write_outputs
from harness_design_studio.core.vcs import lockview
from harness_design_studio.core.vcs.consistency import release_integrity
from harness_design_studio.core.vcs.locks import check_locks
from harness_design_studio.core.vcs.release import plan_release
from tests.helpers import pinout_project

A, B = "OBC-J01", "RW1-J02"
REASON = "Test project: values are placeholders"


def link_harness() -> tuple[Project, str]:
    """pinout_project with a harness made from a link of pins 1 and 2 (not 3, 4 or 5)."""
    p = pinout_project()
    ops, lid = links.plan_add_link(p, A, B, [("1", "1"), ("2", "2")])
    apply_ops(p, ops)
    ops, hid = links.plan_create_harness(p, lid)
    apply_ops(p, ops)
    h = p.harnesses[hid]
    wires = [evolve(w, gauge_awg=22, length_m=1.0) for w in h.wires]
    apply_ops(p, [Put("harnesses", evolve(h, wires=wires))])
    return p, hid


def released(tmp_path: Path) -> tuple[Project, str, History]:
    p, hid = link_harness()
    folder = tmp_path / "outputs"
    write_outputs(p, folder)
    plan = plan_release(
        p, hid, by="Ada", checker="Bob", comment="First release for the CDR", when="2026-03-01",
        outputs_folder=folder, accept_placeholders=REASON, accept_unapproved_parts=REASON,
    )  # fmt: skip
    assert plan.ok, [b.message for b in plan.blockers]
    hist = History(p)
    hist.execute(plan.label, plan.ops)
    assert p.harnesses[hid].status == "released"
    return p, hid, hist


def with_pin(c: object, pin_id: str, **changes: object) -> object:
    assert hasattr(c, "pins")
    pins = [evolve(x, **changes) if x.id == pin_id else x for x in c.pins]
    return evolve(c, pins=pins)


def test_the_signal_of_a_pin_a_released_wire_uses_cannot_change(tmp_path: Path) -> None:
    p, hid, hist = released(tmp_path)
    c = p.connectors[A]
    before = c.model_copy(deep=True)
    op = Put("connectors", with_pin(c, "1", signal="OTHER"))
    with pytest.raises(TransactionError) as exc:
        check_locks(p, [op])
    assert any(
        f"Connector {A} is used by {hid}, which is released" in x for x in exc.value.problems
    )
    with pytest.raises(TransactionError):
        hist.execute("edit", [op])
    assert p.connectors[A] == before


@pytest.mark.parametrize("field", ["signal", "function", "role", "direction", "contact_size"])
def test_every_field_of_a_used_pin_is_frozen(tmp_path: Path, field: str) -> None:
    p, _hid, _hist = released(tmp_path)
    value = {"signal": "X", "function": "f", "role": "power", "direction": "in", "contact_size": "20"}
    with pytest.raises(TransactionError):
        check_locks(p, [Put("connectors", with_pin(p.connectors[A], "2", **{field: value[field]}))])


def test_removing_a_used_pin_or_the_connector_is_refused(tmp_path: Path) -> None:
    p, _hid, _hist = released(tmp_path)
    c = p.connectors[A]
    gone = evolve(c, pins=[x for x in c.pins if x.id != "1"])
    with pytest.raises(TransactionError):
        check_locks(p, [Put("connectors", gone)])
    with pytest.raises(TransactionError):
        check_locks(p, [Delete("connectors", A)])


def test_the_other_pins_of_the_same_connector_stay_editable(tmp_path: Path) -> None:
    p, _hid, hist = released(tmp_path)
    c = p.connectors[A]
    for pin_id in ("3", "5"):  # pin 3 has a signal, pin 5 none; neither is reached by a wire
        c = with_pin(c, pin_id, signal="FREE", function="free text")  # type: ignore[assignment]
    c = evolve(c, pins=[*c.pins, Pin(id="6", signal="NEW")])
    hist.execute("edit other pins", [Put("connectors", c)])
    assert p.connectors[A].pins[-1].id == "6"
    removed = evolve(c, pins=[x for x in c.pins if x.id != "6"])
    hist.execute("remove a spare pin", [Put("connectors", removed)])


def test_the_lock_view_lists_the_pins_the_wires_reach(tmp_path: Path) -> None:
    p, hid, _hist = released(tmp_path)
    locked = lockview.locked_objects(p)
    ref = lockview.LockRef(hid, "A")
    for box in (A, B):
        assert locked[("box_pin", f"{box}.1")] == [ref]
        assert locked[("box_pin", f"{box}.2")] == [ref]
        assert ("box_pin", f"{box}.3") not in locked
    why = lockview.lock_reason(p, "box_pin", f"{A}.1")
    assert why == f"Connector {A} is used by {hid}, which is released. " + (
        f"{hid} is released (revision A); start a new revision to change it."
    )
    assert lockview.field_lock_reason(p, "box_pin", f"{A}.1", "signal") == why
    rl = lockview.release_locks(p, hid)
    assert rl.box_pins == (f"{A}.1", f"{A}.2", f"{B}.1", f"{B}.2")


def test_a_hand_edit_of_a_used_pin_is_found_by_the_check(tmp_path: Path) -> None:
    p, hid, _hist = released(tmp_path)
    assert not [i for i in release_integrity(p) if i.object_id == hid]
    apply_ops(p, [Put("connectors", with_pin(p.connectors[A], "3", signal="FREE"))])
    assert not [i for i in release_integrity(p) if i.object_id == hid]  # an unused pin
    apply_ops(p, [Put("connectors", with_pin(p.connectors[A], "1", signal="OTHER"))])
    (issue,) = [i for i in release_integrity(p) if i.object_id == hid]
    assert issue.code == "released_modified" and "box connector" in issue.message


def test_a_new_revision_unfreezes_the_pins(tmp_path: Path) -> None:
    from harness_design_studio.core.vcs.release import plan_new_revision

    p, hid, hist = released(tmp_path)
    plan = plan_new_revision(p, hid, by="Ada", comment="Change a signal", when="2026-03-02")
    assert plan.ok
    hist.execute(plan.label, plan.ops)
    hist.execute("edit", [Put("connectors", with_pin(p.connectors[A], "1", signal="OTHER"))])


def test_a_draft_harness_freezes_nothing() -> None:
    p, _hid = link_harness()
    check_locks(p, [Put("connectors", with_pin(p.connectors[A], "1", signal="OTHER"))])
    assert not any(k[0] == "box_pin" for k in lockview.locked_objects(p))


def test_the_planners_refuse_a_used_pin_with_the_harness_named(tmp_path: Path) -> None:
    from harness_design_studio.core import devices
    from harness_design_studio.core.edit import EditError

    p, hid, _hist = released(tmp_path)
    with pytest.raises(EditError, match=f"Pin 1 of {A} cannot change.*{hid}.*released"):
        devices.ops_set_pin(p, A, "1", signal="OTHER")
    with pytest.raises(EditError, match=f"Pin 2 of {A} cannot change.*{hid}"):
        devices.ops_set_pinout(
            p, A, [evolve(x, signal="X") if x.id == "2" else x for x in p.connectors[A].pins]
        )
    assert devices.ops_set_pin(p, A, "3", signal="FREE")  # an unused pin: allowed
    assert devices.pin_lock_reason(p, A, "4") is None


def files_of(folder: Path) -> dict[Path, bytes]:
    return {
        f: f.read_bytes()
        for f in sorted(folder.rglob("*"))
        if f.is_file() and not f.name.startswith(".harness.lock")
    }


def _cli(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = cli_main(args)
    out = capsys.readouterr()
    return code, out.out + out.err


def test_import_pinout_replace_is_refused_for_a_used_pin_and_the_files_are_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p, hid, _hist = released(tmp_path)
    folder = tmp_path / "proj"
    save_project(p, folder)
    before = files_of(folder)
    sheet = tmp_path / "pins.csv"
    unit = str(p.connectors[A].unit_id)
    rows = "Connector,Pin,Signal\nJ01,1,{one}\nJ01,2,TX-\nJ01,3,{three}\nJ01,4,RX-\nJ01,5,\n"
    args = ["import-pinout", str(folder), str(sheet), "--device", unit, "--replace"]
    sheet.write_text(rows.format(one="CHANGED", three="RX+"), encoding="utf-8")
    code, text = _cli(args, capsys)
    assert code != 0 and hid in text and "released" in text, text
    assert files_of(folder) == before
    sheet.write_text(rows.format(one="TX+", three="CHANGED"), encoding="utf-8")  # pin 3: no wire
    code, text = _cli(args, capsys)
    assert code == 0, text
