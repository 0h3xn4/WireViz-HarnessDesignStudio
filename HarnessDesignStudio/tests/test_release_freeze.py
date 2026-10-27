"""E-5 / I-2: a release freezes the parts, interface types and configuration that the released
harness uses (and records them in the baseline); old baselines without these records still load
and are not reported."""

import json
from pathlib import Path

import pytest

from harness_design_studio.core.commands import Delete, DeleteConfig, History, Put, SetConfig
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.io.layout import serialize
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import ConfigFile, Part, Project, evolve
from harness_design_studio.core.vcs.consistency import release_integrity
from harness_design_studio.core.vcs.snapshot import used_interface_type_ids, used_part_ids
from tests.test_change_control import (  # noqa: F401  (the fixture is used by every test)
    _export_template,
    do_release,
    exported,
    full,
    releasable,
)


def released(tmp: Path) -> tuple[Project, str, History]:
    p = full()
    hid = releasable(p)
    hist = do_release(p, hid, exported(p, tmp))
    return p, hid, hist


def used_part(p: Project, hid: str) -> str:
    return sorted(used_part_ids(p, p.harnesses[hid]))[0]


def test_the_baseline_records_used_parts_types_and_configuration(tmp_path: Path) -> None:
    p, hid, _ = released(tmp_path)
    snap = p.baselines[f"{hid}.A"].snapshot
    assert snap.parts is not None and snap.interface_types is not None and snap.config is not None
    assert {x.id for x in snap.parts} == used_part_ids(p, p.harnesses[hid])
    assert {t.id for t in snap.interface_types} == used_interface_type_ids(p, p.harnesses[hid])
    assert {"derating", "emc", "segregation", "titleblock", "generation"} <= set(snap.config)
    assert "naming" not in snap.config and "segmentation" not in snap.config
    assert "wire_part_by_construction" not in snap.config["generation"]
    assert not release_integrity(p)


def test_editing_a_used_part_is_refused_and_says_how_to_proceed(tmp_path: Path) -> None:
    p, hid, hist = released(tmp_path)
    pid = used_part(p, hid)
    part = p.parts[pid]
    with pytest.raises(TransactionError) as err:
        hist.execute("edit", [Put("parts", evolve(part, approval="not_approved"))])
    text = " ".join([str(err.value), *err.value.problems])
    assert pid in text and hid in text and "new revision" in text
    with pytest.raises(TransactionError):
        hist.execute("edit", [Put("parts", evolve(part, mass_g=123.0))])
    with pytest.raises(TransactionError):
        hist.execute("delete", [Delete("parts", pid)])
    assert p.parts[pid] == part


def test_what_is_not_used_stays_editable(tmp_path: Path) -> None:
    p, hid, hist = released(tmp_path)
    used = used_part_ids(p, p.harnesses[hid])
    pid = used_part(p, hid)
    hist.execute(
        "note", [Put("parts", evolve(p.parts[pid], notes="checked"))]
    )  # notes are cosmetic
    hist.execute("same", [Put("parts", p.parts[pid])])
    other = next(i for i in sorted(p.parts) if i not in used)
    hist.execute("edit", [Put("parts", evolve(p.parts[other], mass_g=7.0))])
    hist.execute("new", [Put("parts", Part(id="EX-NEW-PART", category="wire"))])
    unused_type = next(
        t
        for t in sorted(p.interface_types)
        if t not in used_interface_type_ids(p, p.harnesses[hid])
    )
    hist.execute(
        "type",
        [Put("interface_types", evolve(p.interface_types[unused_type], default_gauge_awg=22))],
    )
    assert not release_integrity(p)


def test_editing_a_used_interface_type_is_refused(tmp_path: Path) -> None:
    p, hid, hist = released(tmp_path)
    tid = sorted(used_interface_type_ids(p, p.harnesses[hid]))[0]
    t = p.interface_types[tid]
    with pytest.raises(TransactionError, match="blocked"):
        hist.execute("edit", [Put("interface_types", evolve(t, shielding="overall"))])
    with pytest.raises(TransactionError):
        hist.execute("delete", [Delete("interface_types", tid)])
    hist.execute("note", [Put("interface_types", evolve(t, notes="x", name="Renamed"))])


def test_editing_frozen_configuration_is_refused_but_other_files_are_free(tmp_path: Path) -> None:
    p, hid, hist = released(tmp_path)
    der = p.config["derating"]
    with pytest.raises(TransactionError) as err:
        hist.execute("cfg", [SetConfig(ConfigFile(name="derating", placeholder=False, values={}))])
    assert "derating" in " ".join(err.value.problems) and hid in " ".join(err.value.problems)
    with pytest.raises(TransactionError):
        hist.execute("cfg", [DeleteConfig("derating")])
    gen = p.config["generation"]
    with pytest.raises(TransactionError):
        hist.execute(
            "cfg",
            [
                SetConfig(
                    evolve(
                        gen, values={**gen.values, "service_loop_m": 1.0, "shield_end_a": "pigtail"}
                    )
                )
            ],
        )
    # generation values that only decide how new harnesses are made, and other files, stay free
    hist.execute("cfg", [SetConfig(evolve(gen, values={**gen.values, "service_loop_m": 0.25}))])
    seg = p.config["segmentation"]
    hist.execute("cfg", [SetConfig(evolve(seg, values={"mode": "per_unit_pair"}))])
    # the review flag is not a value
    hist.execute("cfg", [SetConfig(evolve(der, placeholder=not der.placeholder))])
    assert not release_integrity(p)


def test_hand_edits_after_release_are_reported(tmp_path: Path) -> None:
    p, hid, _ = released(tmp_path)
    pid = used_part(p, hid)
    p.parts[pid] = evolve(p.parts[pid], mass_g=999.0)
    issues = release_integrity(p)
    assert [i.code for i in issues] == ["released_modified"]
    assert pid in issues[0].message and "new revision" in issues[0].message
    p.parts[pid] = evolve(p.parts[pid], mass_g=p.baselines[f"{hid}.A"].snapshot.parts[0].mass_g)  # type: ignore[index]

    tid = sorted(used_interface_type_ids(p, p.harnesses[hid]))[0]
    saved_type = p.interface_types[tid]
    p.interface_types[tid] = evolve(saved_type, shielding="overall")
    assert "interface type" in release_integrity(p)[0].message
    p.interface_types[tid] = saved_type
    assert not release_integrity(p)

    old = p.config["derating"]
    p.config["derating"] = evolve(old, values={**old.values, "spare_pin_fraction": 0.5})
    assert "derating" in release_integrity(p)[0].message


def test_a_new_revision_unlocks_and_the_next_release_records_the_new_values(
    tmp_path: Path,
) -> None:
    from harness_design_studio.core.vcs.release import plan_new_revision

    p, hid, hist = released(tmp_path)
    pid = used_part(p, hid)
    plan = plan_new_revision(
        p, hid, by="Ada", comment="change the mass of a part", when="2026-04-01"
    )
    assert plan.ok
    hist.execute(plan.label, plan.ops)
    hist.execute("edit", [Put("parts", evolve(p.parts[pid], mass_g=42.0))])
    assert not release_integrity(p)  # revision B has no baseline yet; revision A's is history


def test_old_baselines_without_the_new_records_load_clean_and_are_written_back_unchanged(
    tmp_path: Path,
) -> None:
    p, hid, _ = released(tmp_path)
    files = serialize(p)
    name = f"baselines/{hid}/{hid}.A.json"
    data = json.loads(files[name])
    for key in ("parts", "interface_types", "config", "waivers"):
        del data["snapshot"][key]  # what a baseline made by an earlier version looks like
    old_bytes = (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()

    folder = tmp_path / "proj"
    save_project(p, folder)
    (folder / name).write_bytes(old_bytes)
    loaded = load_project(folder)
    assert not loaded.project.recovered
    snap = loaded.project.baselines[f"{hid}.A"].snapshot
    assert snap.parts is None and snap.interface_types is None and snap.config is None
    assert not release_integrity(loaded.project)  # nothing recorded: nothing compared
    assert serialize(loaded.project)[name] == old_bytes  # a save does not rewrite it

    # the lock still protects what the live harness uses
    hist = History(loaded.project)
    pid = used_part(loaded.project, hid)
    with pytest.raises(TransactionError):
        hist.execute("edit", [Put("parts", evolve(loaded.project.parts[pid], mass_g=1.5))])


def test_waivers_are_recorded_but_not_locked(tmp_path: Path) -> None:
    from harness_design_studio.core.model import Waiver

    p = full()
    hid = releasable(p)
    w = Waiver(id=f"r.{hid}", rule="r", object_id=hid, justification="accepted by the team")
    p.waivers[w.id] = w
    hist = do_release(p, hid, exported(p, tmp_path))
    assert [x.id for x in p.baselines[f"{hid}.A"].snapshot.waivers or []] == [w.id]
    hist.execute("waive", [Put("waivers", evolve(w, justification="accepted again, rev 2"))])
    assert not release_integrity(p)
