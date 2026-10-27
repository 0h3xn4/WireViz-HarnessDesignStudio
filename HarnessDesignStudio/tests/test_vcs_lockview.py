"""SH-4 / SC-6 / SC-14: which objects a release locks, why, and which fields stay editable.
The sentences are the ones `check_locks` refuses with, so the inspector and the toast agree."""

from pathlib import Path

import pytest

from harness_design_studio.core import edit
from harness_design_studio.core.commands import Delete, Op, Put, SetConfig
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.model import Project, evolve
from harness_design_studio.core.model.config import ConfigFile
from harness_design_studio.core.vcs import lockview
from harness_design_studio.core.vcs.hashing import content_hash
from harness_design_studio.core.vcs.locks import check_locks
from harness_design_studio.core.vcs.release import ReleaseError
from harness_design_studio.core.vcs.snapshot import (
    FROZEN_GENERATION_KEYS,
    carried_interfaces,
    used_part_ids,
)
from tests.test_change_control import (  # noqa: F401  (the fixture is used by every test)
    _export_template,
    do_release,
    exported,
    full,
    releasable,
)


def released(tmp_path: Path) -> tuple[Project, str]:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    return p, hid


def refusal(p: Project, op: Op) -> list[str]:
    with pytest.raises(TransactionError) as exc:
        check_locks(p, [op])
    return list(exc.value.problems)


def test_a_draft_project_locks_nothing() -> None:
    p = full()
    assert lockview.locked_objects(p) == {}
    assert lockview.lock_reason(p, "interface", next(iter(p.interfaces))) is None


def test_released_harness_locks_its_wires_interfaces_pins_parts_types_and_config(
    tmp_path: Path,
) -> None:
    p, hid = released(tmp_path)
    h = p.harnesses[hid]
    locked = lockview.locked_objects(p)
    owner = [lockview.LockRef(hid, h.revision)]
    assert locked[("harness", hid)] == owner
    for w in h.wires:
        assert locked[("wire", w.id)] == owner
    for c in h.connectors:
        assert locked[("cable_connector", c.id)] == owner
        assert c.mates_with is None or locked[("box_connector", c.mates_with)] == owner
        for pin in c.pins:
            assert locked[("cable_pin", f"{c.id}.{pin.id}")] == owner
    for iid in carried_interfaces(h):
        assert locked[("interface", iid)] == owner
    for pid in used_part_ids(p, h):
        assert locked[("part", pid)] == owner
    assert ("interface_type", p.interfaces[next(iter(carried_interfaces(h)))].type_id) in locked
    assert ("config", "derating") in locked and ("config", "naming") not in locked
    box_pins = [k for k in locked if k[0] == "box_pin"]
    assert box_pins and all("." in k[1] for k in box_pins)
    for kind, _id in locked:
        assert kind in lockview.KINDS


def test_units_of_locked_interfaces_are_locked(tmp_path: Path) -> None:
    p, hid = released(tmp_path)
    h = p.harnesses[hid]
    units = {e.unit_id for i in carried_interfaces(h) for e in p.interfaces[i].endpoints}
    locked = lockview.locked_objects(p)
    assert units and all(("unit", u) in locked for u in units)
    others = set(p.units) - units
    assert all(("unit", u) not in locked for u in others)


def test_two_released_harnesses_are_both_listed_sorted_by_id(tmp_path: Path) -> None:
    p, hid = released(tmp_path)
    other = next(h for h in sorted(p.harnesses) if h != hid)
    p2 = edit.clone_with(p, [])
    p2.harnesses[other] = evolve(p2.harnesses[other], status="released")
    locked = lockview.locked_objects(p2)
    assert locked[("harness", other)] == [lockview.LockRef(other, p2.harnesses[other].revision)]
    owners = [r.harness_id for r in locked[("config", "derating")]]
    assert owners == sorted({hid, other})
    for iid in carried_interfaces(p2.harnesses[other]):
        assert other in [r.harness_id for r in locked[("interface", iid)]]


def test_reason_for_an_interface_is_the_sentence_the_refusal_uses(tmp_path: Path) -> None:
    p, hid = released(tmp_path)
    iid = sorted(carried_interfaces(p.harnesses[hid]))[0]
    changed = evolve(p.interfaces[iid], max_current_a=(p.interfaces[iid].max_current_a or 0) + 1)
    [msg] = refusal(p, Put("interfaces", changed))
    assert lockview.lock_reason(p, "interface", iid) == msg
    assert "is carried by" in msg and "released" in msg and "start a new revision" in msg


@pytest.mark.parametrize("kind", ["part", "interface_type", "unit", "harness"])
def test_reason_matches_the_refusal_for_other_kinds(kind: str, tmp_path: Path) -> None:
    p, hid = released(tmp_path)
    h = p.harnesses[hid]
    if kind == "part":
        oid = sorted(used_part_ids(p, h))[0]
        new: object = evolve(p.parts[oid], mass_g=123.0)
        op: Op = Put("parts", new)  # type: ignore[arg-type]
    elif kind == "interface_type":
        oid = p.interfaces[sorted(carried_interfaces(h))[0]].type_id
        op = Put("interface_types", evolve(p.interface_types[oid], category="rf"))
    elif kind == "unit":
        oid = next(u for k, u in lockview.locked_objects(p) if k == "unit")
        op = Put(
            "units",
            evolve(
                p.units[oid], side="redundant" if p.units[oid].side != "redundant" else "nominal"
            ),
        )
    else:
        oid = hid
        op = Delete("harnesses", hid)
    [msg] = refusal(p, op)
    assert lockview.lock_reason(p, kind, oid) == msg


def test_reason_for_a_box_connector_and_its_pins(tmp_path: Path) -> None:
    p, hid = released(tmp_path)
    box = next(c for k, c in lockview.locked_objects(p) if k == "box_connector")
    conn = p.connectors[box]
    changed = evolve(
        conn, part_id=conn.part_id, gender="male" if conn.gender != "male" else "female"
    )
    [msg] = refusal(p, Put("connectors", changed))
    assert lockview.lock_reason(p, "box_connector", box) == msg
    pin = next(
        i for k, i in lockview.locked_objects(p) if k == "box_pin" and i.startswith(box + ".")
    )
    assert lockview.lock_reason(p, "box_pin", pin) == msg


def test_reason_for_wires_is_the_harness_sentence(tmp_path: Path) -> None:
    p, hid = released(tmp_path)
    w = p.harnesses[hid].wires[0]
    [msg] = refusal(p, Delete("harnesses", hid))
    assert lockview.lock_reason(p, "wire", w.id) == msg
    assert msg.startswith(f"{hid} is released (revision {p.harnesses[hid].revision});")


def test_reason_for_a_config_file_names_the_harnesses(tmp_path: Path) -> None:
    p, hid = released(tmp_path)
    old = p.config["derating"]
    new = ConfigFile(
        name="derating",
        placeholder=old.placeholder,
        values={**old.values, "spare_pin_fraction": 0.31},
    )
    [msg] = refusal(p, SetConfig(new))
    assert lockview.lock_reason(p, "config", "derating") == msg
    assert hid in msg


def test_an_unlocked_object_has_no_reason(tmp_path: Path) -> None:
    p, hid = released(tmp_path)
    assert lockview.lock_reason(p, "config", "naming") is None
    assert lockview.lock_reason(p, "unit", "does-not-exist") is None
    assert lockview.lock_reason(p, "no-such-kind", "x") is None


def test_cosmetic_fields_are_the_ones_check_locks_lets_through(tmp_path: Path) -> None:
    p, hid = released(tmp_path)
    iid = sorted(carried_interfaces(p.harnesses[hid]))[0]
    for field in lockview.cosmetic_fields("interface"):
        if field == "requirement_id":
            value: object = "REQ-9"
        else:
            value = "renamed"
        check_locks(p, [Put("interfaces", evolve(p.interfaces[iid], **{field: value}))])
    assert lockview.cosmetic_fields("interface") == {"name", "notes", "requirement_id"}
    assert lockview.cosmetic_fields("unit") == {"name", "notes", "zone"}
    assert lockview.cosmetic_fields("part") == {"notes"}
    assert lockview.cosmetic_fields("interface_type") == {"name", "notes"}
    box = next(c for k, c in lockview.locked_objects(p) if k == "box_connector")
    free = lockview.cosmetic_fields("box_connector")
    assert {"name", "notes"} <= free and not free & {"part_id", "gender", "keying", "pins", "id"}
    for field in ("name", "notes"):
        check_locks(p, [Put("connectors", evolve(p.connectors[box], **{field: "renamed"}))])
    for kind in ("wire", "harness", "config", "box_pin"):
        assert lockview.cosmetic_fields(kind) == frozenset()


def test_field_lock_disables_only_non_cosmetic_fields(tmp_path: Path) -> None:
    p, hid = released(tmp_path)
    iid = sorted(carried_interfaces(p.harnesses[hid]))[0]
    assert lockview.field_lock_reason(p, "interface", iid, "name") is None
    assert lockview.field_lock_reason(p, "interface", iid, "notes") is None
    reason = lockview.field_lock_reason(p, "interface", iid, "max_current_a")
    assert reason == lockview.lock_reason(p, "interface", iid)
    free = next(i for i in p.interfaces if i not in carried_interfaces(p.harnesses[hid]))
    assert lockview.field_lock_reason(p, "interface", free, "max_current_a") is None


def test_config_keys_outside_the_frozen_set_stay_editable(tmp_path: Path) -> None:
    p, hid = released(tmp_path)
    assert lockview.config_key_locked(p, "derating", "spare_pin_fraction")
    assert lockview.config_key_locked(p, "generation", "shield_end_a")
    assert not lockview.config_key_locked(p, "generation", "service_loop_m")
    assert not lockview.config_key_locked(p, "naming", "harness")
    assert lockview.field_lock_reason(p, "config", "generation", "service_loop_m") is None
    assert lockview.field_lock_reason(p, "config", "generation", "shield_end_a") is not None


def test_what_a_release_will_lock_lists_every_group(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    h = p.harnesses[hid]
    plan = lockview.release_locks(p, hid)
    assert plan.harness_id == hid
    assert list(plan.wires) == sorted(w.id for w in h.wires)
    assert set(plan.interfaces) == carried_interfaces(h)
    assert set(plan.parts) == used_part_ids(p, h)
    assert set(plan.interface_types) == {p.interfaces[i].type_id for i in carried_interfaces(h)}
    assert set(plan.cable_connectors) == {c.id for c in h.connectors}
    assert plan.box_pins and all(pin.split(".")[0] in p.connectors for pin in plan.box_pins)
    counts = plan.counts()
    assert counts["wires"] == len(h.wires)
    assert counts["pins"] == len(plan.cable_pins) + len(plan.box_pins)
    assert counts["interfaces"] == len(plan.interfaces) and counts["parts"] == len(plan.parts)
    assert counts["config_files"] == len(plan.config_files)


def test_release_locks_shows_placeholder_files_and_unset_values() -> None:
    p = full()
    hid = releasable(p)
    plan = lockview.release_locks(p, hid)
    files = {c.name: c for c in plan.config_files}
    assert set(files) == {"derating", "emc", "segregation", "titleblock", "generation"}
    gen = files["generation"]
    assert set(gen.values) <= set(FROZEN_GENERATION_KEYS)
    assert gen.placeholder == p.config["generation"].placeholder
    assert gen.unset == tuple(sorted(k for k, v in gen.values.items() if v is None))
    assert plan.placeholder_files == tuple(sorted(n for n, c in files.items() if c.placeholder))


def test_release_locks_of_an_unknown_harness_is_a_plain_error() -> None:
    with pytest.raises(ReleaseError, match="no harness"):
        lockview.release_locks(full(), "W999")


def test_what_a_release_will_lock_is_what_it_then_locks(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    plan = lockview.release_locks(p, hid)
    do_release(p, hid, exported(p, tmp_path))
    locked = lockview.locked_objects(p)
    for kind, ids in (
        ("wire", plan.wires), ("interface", plan.interfaces), ("part", plan.parts),
        ("interface_type", plan.interface_types), ("cable_connector", plan.cable_connectors),
        ("box_connector", plan.box_connectors), ("unit", plan.units),
        ("box_pin", plan.box_pins), ("cable_pin", plan.cable_pins),
        ("config", tuple(c.name for c in plan.config_files)),
    ):  # fmt: skip
        assert set(ids) == {i for k, i in locked if k == kind}, kind


def test_nothing_in_it_changes_the_project(tmp_path: Path) -> None:
    p, hid = released(tmp_path)
    h0 = content_hash(p)
    lockview.locked_objects(p)
    lockview.release_locks(p, hid)
    assert content_hash(p) == h0
