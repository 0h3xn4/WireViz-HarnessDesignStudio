"""Regression tests for the data-layer findings of the October audit (one test per defect)."""

from pathlib import Path

import pytest

from harness_design_studio.core import edit
from harness_design_studio.core.commands import Delete, History, Put
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.model import Project, evolve
from harness_design_studio.core.samples import mini3, sat15
from harness_design_studio.core.vcs.consistency import release_integrity
from tests.test_change_control import do_release, exported, full, releasable


def test_a_new_unit_never_reuses_the_id_of_a_renamed_units_connectors() -> None:
    p = sat15()
    ops, uid = edit.ops_add_unit(p, "sensor")
    History(p).execute("add", ops)
    History(p).execute("rename", edit.ops_rename_unit(p, uid, "STAR"))
    old_connectors = sorted(c.id for c in p.connectors.values() if c.unit_id == "STAR")
    assert old_connectors and old_connectors[0].startswith(uid + "-")
    ops2, uid2 = edit.ops_add_unit(p, "sensor")
    assert uid2 != uid
    History(p).execute("add", ops2)
    assert sorted(c.id for c in p.connectors.values() if c.unit_id == "STAR") == old_connectors


def test_renaming_a_unit_onto_foreign_connector_ids_is_refused() -> None:
    p = sat15()
    ops, uid = edit.ops_add_unit(p, "sensor")
    History(p).execute("add", ops)
    History(p).execute("rename", edit.ops_rename_unit(p, uid, "STAR"))
    ops2, uid2 = edit.ops_add_unit(p, "sensor")
    History(p).execute("add", ops2)
    with pytest.raises(EditError):
        edit.ops_rename_unit(p, uid2, uid)


def test_baselines_and_change_log_cannot_be_deleted_or_replaced(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    hist = do_release(p, hid, exported(p, tmp_path))
    bid = next(iter(p.baselines))
    with pytest.raises(TransactionError):
        hist.execute("del", [Delete("baselines", bid)])
    with pytest.raises(TransactionError):
        hist.execute("del", [Delete("changelog", next(iter(p.changelog)))])
    assert bid in p.baselines


def test_design_fields_of_a_carried_interface_are_locked_after_release(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    hist = do_release(p, hid, exported(p, tmp_path))
    iid = sorted({w.interface_id for w in p.harnesses[hid].wires if w.interface_id})[0]
    with pytest.raises(TransactionError):
        hist.execute("edit", [edit.ops_update_interface(p, iid, max_current_a=99.0)[0]])
    # labels stay editable
    hist.execute("note", [evolve_put(p, iid)])


def evolve_put(p: Project, iid: str) -> Put:
    return Put("interfaces", evolve(p.interfaces[iid], notes="reviewed"))


def test_a_released_harness_set_back_to_draft_by_hand_is_reported(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    assert not release_integrity(p)
    p.harnesses[hid] = evolve(p.harnesses[hid], status="draft")  # what a hand edit does
    assert [i.code for i in release_integrity(p)] == ["released_modified"]


def test_interface_changed_by_hand_after_release_is_reported(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    iid = sorted({w.interface_id for w in p.harnesses[hid].wires if w.interface_id})[0]
    p.interfaces[iid] = evolve(p.interfaces[iid], max_current_a=99.0)
    issues = release_integrity(p)
    assert issues and "interface" in issues[0].message


# ---- io, recovery and locks ---------------------------------------------------------------------


def _corrupt_one_placement(folder: Path) -> None:
    import json

    f = folder / "logical" / "layout.json"
    data = json.loads(f.read_text())
    data["placements"].append({"id": "BAD ID!", "x": "not a number", "y": 1})
    f.write_text(json.dumps(data))


def test_journal_keeps_what_could_not_be_loaded(tmp_path: Path) -> None:
    from harness_design_studio.core.io.loader import load_project
    from harness_design_studio.core.io.saver import save_project
    from harness_design_studio.core.recovery import read_journal, write_journal

    save_project(mini3(), tmp_path / "p")
    _corrupt_one_placement(tmp_path / "p")
    loaded = load_project(tmp_path / "p")
    assert loaded.project.recovered
    write_journal(loaded.project, tmp_path / "p")
    restored = read_journal(tmp_path / "p")
    assert restored is not None and restored.project.recovered
    from harness_design_studio.core.errors import SaveError

    with pytest.raises(SaveError):
        save_project(restored.project, tmp_path / "p")  # still protected


def test_two_baselines_never_share_a_file(tmp_path: Path) -> None:
    from harness_design_studio.core.io.layout import serialize

    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    b = next(iter(p.baselines.values()))
    other = evolve(b, id=f"{hid}.zz", revision="é")
    third = evolve(b, id=f"{hid}.yy", revision="ü")
    p.baselines[other.id] = other
    p.baselines[third.id] = third
    names = [n for n in serialize(p) if n.startswith("baselines/")]
    assert len(names) == len(set(names)) == len(p.baselines)


def test_infinite_numbers_are_a_load_problem_not_a_crash_on_save(tmp_path: Path) -> None:
    import json

    from harness_design_studio.core.io.loader import load_project
    from harness_design_studio.core.io.saver import save_project

    save_project(mini3(), tmp_path / "p")
    cfg = next((tmp_path / "p" / "config").glob("*.json"))
    data = json.loads(cfg.read_text())
    data["values"] = {"x": 0}
    cfg.write_text(json.dumps(data).replace('"x": 0', '"x": 1e999'))
    loaded = load_project(tmp_path / "p")
    assert loaded.has_errors
    assert "invalid_json" in {i.code for i in loaded.issues}  # named, not silently defaulted


def _lock_worker(root: str, barrier: object, out: object) -> None:
    import time

    from harness_design_studio.core.errors import ProjectLockedError
    from harness_design_studio.core.io.fs import ProjectLock

    lock = ProjectLock(Path(root))
    barrier.wait()  # type: ignore[attr-defined]
    try:
        lock.acquire()
        out.put(1)  # type: ignore[attr-defined]
        time.sleep(0.3)  # keep holding while the others finish
    except ProjectLockedError:
        out.put(0)  # type: ignore[attr-defined]


def test_stale_lock_takeover_gives_the_lock_to_exactly_one_process(tmp_path: Path) -> None:
    import json
    import multiprocessing as mp

    from harness_design_studio.core.io.fs import LOCK_NAME

    # fork where there is one; Windows has only spawn (slower, so fewer rounds)
    forking = "fork" in mp.get_all_start_methods()
    ctx = mp.get_context("fork" if forking else "spawn")
    for _ in range(8 if forking else 2):
        (tmp_path / LOCK_NAME).write_text(
            json.dumps({"pid": 2**22 + 12345, "host": __import__("platform").node(), "since": 1})
        )
        barrier = ctx.Barrier(5)
        out = ctx.Queue()
        procs = [
            ctx.Process(target=_lock_worker, args=(str(tmp_path), barrier, out)) for _ in range(5)
        ]
        for pr in procs:
            pr.start()
        results = [out.get(timeout=60) for _ in procs]
        for pr in procs:
            pr.join(timeout=60)
        (tmp_path / LOCK_NAME).unlink(missing_ok=True)
        assert sum(results) == 1, results


def test_a_project_folder_that_is_a_link_to_elsewhere_is_not_read_or_written(
    tmp_path: Path,
) -> None:
    import shutil

    from harness_design_studio.core.errors import SaveError
    from harness_design_studio.core.io.loader import disk_fingerprint, load_project
    from harness_design_studio.core.io.saver import save_project

    save_project(mini3(), tmp_path / "p")
    outside = tmp_path / "outside"
    shutil.move(str(tmp_path / "p" / "config"), outside)
    (tmp_path / "p" / "config").symlink_to(outside, target_is_directory=True)
    before = sorted(x.read_bytes() for x in outside.glob("*.json"))
    loaded = load_project(tmp_path / "p")
    assert any(i.code == "symlink_ignored" for i in loaded.issues)
    with pytest.raises(SaveError):
        save_project(loaded.project, tmp_path / "p")
    assert sorted(x.read_bytes() for x in outside.glob("*.json")) == before
    assert disk_fingerprint(tmp_path / "p")


def test_dangling_link_does_not_break_the_fingerprint(tmp_path: Path) -> None:
    from harness_design_studio.core.io.loader import disk_fingerprint
    from harness_design_studio.core.io.saver import save_project

    save_project(mini3(), tmp_path / "p")
    (tmp_path / "p" / "logical" / "units" / "zzz.json").symlink_to(tmp_path / "missing.json")
    assert disk_fingerprint(tmp_path / "p")


def test_new_project_folders_ignore_the_autosave_journal() -> None:
    from harness_design_studio.core.io.saver import GITIGNORE

    assert b".harness-recovery/" in GITIGNORE and b".harness.lock" in GITIGNORE


# ---- commands, integrity, edit ------------------------------------------------------------------


def test_undoing_the_first_config_removes_it() -> None:
    from harness_design_studio.core.commands import SetConfig
    from harness_design_studio.core.io.layout import model_hash

    p = mini3()
    cfg = next(iter(p.config.values()))
    del p.config[cfg.name]
    h0 = model_hash(p)
    hist = History(p)
    hist.execute("set", [SetConfig(cfg)])
    hist.undo()
    assert cfg.name not in p.config and model_hash(p) == h0


def test_a_second_error_on_the_same_object_is_not_waved_through() -> None:
    p = mini3()
    iid = next(iter(p.interfaces))
    i = p.interfaces[iid]
    ghost = evolve(i.endpoints[0], unit_id="GHOST1")
    p.interfaces[iid] = evolve(i, endpoints=[*i.endpoints, ghost])  # loaded with an error already
    ghost2 = evolve(i.endpoints[0], unit_id="GHOST2")
    from harness_design_studio.core.commands import Put

    with pytest.raises(TransactionError):
        History(p).execute(
            "more",
            [
                Put(
                    "interfaces",
                    evolve(p.interfaces[iid], endpoints=[*p.interfaces[iid].endpoints, ghost2]),
                )
            ],
        )


def test_deleting_an_interface_removes_its_waivers_and_unknown_carried_ids_are_found() -> None:
    from harness_design_studio.core import integrity
    from harness_design_studio.core.model import Waiver

    p = sat15()
    iid = sorted(p.interfaces)[0]
    w = Waiver(id=f"x.{iid}", rule="x", object_id=iid, justification="long enough reason")
    p.waivers[w.id] = w
    History(p).execute("del", edit.ops_delete_interface(p, iid))
    assert w.id not in p.waivers
    # a harness that lists an interface which does not exist is reported
    from harness_design_studio.core.generate.engine import generate_project

    p2 = sat15()
    generate_project(p2)
    hid = sorted(p2.harnesses)[0]
    p2.harnesses[hid] = evolve(p2.harnesses[hid], interfaces=["IF-NOPE"])
    assert any(
        i.code == "unknown_interface" and "IF-NOPE" in i.message
        for i in integrity.check_integrity(p2)
    )


def test_delete_blocked_by_a_released_harness_says_what_to_do(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    iid = sorted({w.interface_id for w in p.harnesses[hid].wires if w.interface_id})[0]
    with pytest.raises(EditError, match="new revision"):
        edit.ops_delete_interface(p, iid)


def test_ops_delete_harness_refuses_released(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    with pytest.raises(EditError):
        edit.ops_delete_harness(p, hid)
    other = next(h for h in p.harnesses if h != hid)
    History(p).execute("del", edit.ops_delete_harness(p, other))
    assert other not in p.harnesses


def test_checks_survive_an_interface_that_names_a_missing_unit() -> None:
    from harness_design_studio.core import checks

    p = sat15()
    iid = sorted(p.interfaces)[0]
    i = p.interfaces[iid]
    p.interfaces[iid] = evolve(
        i, endpoints=[*i.endpoints, evolve(i.endpoints[0], unit_id="GHOST")], redundancy="nominal"
    )
    assert checks.find(p) is not None
