"""Regression tests for the core findings of the October audit: release record and undo (A-2),
damaged files (A-1), lone surrogates (A-3), stored units and box connectors of a baseline (E-4)
and the lock rules (I-2)."""

import json
from pathlib import Path

import pytest

from harness_design_studio.core import edit
from harness_design_studio.core.commands import Delete, History, Put, apply_ops
from harness_design_studio.core.errors import HarnessError, SaveError, TransactionError
from harness_design_studio.core.io import canonical
from harness_design_studio.core.io import loader as loader_mod
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Project, evolve
from harness_design_studio.core.recovery import write_journal
from harness_design_studio.core.samples import mini3
from harness_design_studio.core.vcs.consistency import release_integrity
from harness_design_studio.core.vcs.release import plan_new_revision
from tests.test_change_control import WHEN, do_release, exported, full, releasable

# ---- A-2: undo must not erase a saved release ---------------------------------------------------


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_a_saved_release_cannot_be_undone_and_saved_away(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    hist = do_release(p, hid, exported(p, tmp_path))
    root = tmp_path / "proj"
    save_project(p, root)
    baseline = root / "baselines" / hid / f"{hid}.A.json"
    assert baseline.is_file() and not hist.can_undo
    with pytest.raises(TransactionError, match="it cannot be undone"):
        hist.undo()
    assert p.harnesses[hid].status == "released" and p.baselines and p.changelog
    before = _tree(root)
    save_project(p, root)
    assert baseline.is_file() and _tree(root) == before


def test_an_unsaved_release_can_still_be_undone_even_after_other_saves(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    root = tmp_path / "proj"
    save_project(p, root)  # saved before the release
    hist = do_release(p, hid, exported(p, tmp_path))
    assert hist.can_undo
    hist.undo()
    assert p.harnesses[hid].status != "released" and not p.baselines and not p.changelog
    hist.redo()
    assert p.baselines


def test_a_saved_new_revision_cannot_be_undone(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    hist = do_release(p, hid, exported(p, tmp_path))
    plan = plan_new_revision(p, hid, by="Ada", comment="A change is needed", when=WHEN)
    hist.execute(plan.label, plan.ops)
    save_project(p, tmp_path / "proj")
    assert not hist.can_undo and hist.undo_blocked
    with pytest.raises(HarnessError):
        hist.undo()
    assert len(p.changelog) == 2


def test_steps_made_after_the_save_can_be_undone_but_not_the_saved_release(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    hist = do_release(p, hid, exported(p, tmp_path))
    save_project(p, tmp_path / "proj")
    uid = next(iter(p.units))
    hist.execute("rename", edit.ops_rename_unit(p, uid, "RENAMED"))
    assert hist.can_undo
    hist.undo()
    assert not hist.can_undo and p.baselines  # only the saved release is left
    hist.redo()
    assert hist.can_undo


# ---- A-1: files that cannot be read count as damaged --------------------------------------------


def _saved(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    save_project(mini3(), root)
    return root


def _assert_save_refused_and_untouched(project: Project, root: Path) -> None:
    before = _tree(root)
    with pytest.raises(SaveError):
        save_project(project, root)
    after = _tree(root)
    assert after == before  # nothing moved to .bak, nothing regenerated


def test_a_symlinked_project_file_is_damaged_and_never_saved_over(tmp_path: Path) -> None:
    root = _saved(tmp_path)
    victim = root / "physical" / "harnesses" / "W001.json"
    elsewhere = tmp_path / "copy.json"
    elsewhere.write_bytes(victim.read_bytes())
    victim.unlink()
    victim.symlink_to(elsewhere)
    loaded = load_project(root)
    assert loaded.project.recovered
    assert "physical/harnesses/W001.json" in {q.file for q in loaded.project.quarantine}
    _assert_save_refused_and_untouched(loaded.project, root)


def test_an_oversized_project_file_is_damaged_and_never_saved_over(tmp_path: Path) -> None:
    root = _saved(tmp_path)
    victim = root / "physical" / "harnesses" / "W001.json"
    with victim.open("r+b") as f:
        f.truncate(loader_mod.MAX_FILE_BYTES + 1)  # sparse: nothing is really written
    loaded = load_project(root)
    assert loaded.has_errors and loaded.project.recovered
    _assert_save_refused_and_untouched(loaded.project, root)


def test_an_unreadable_project_file_is_damaged_and_never_saved_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _saved(tmp_path)
    real = Path.read_bytes

    def read_bytes(self: Path) -> bytes:
        if self.name == "W001.json":
            raise PermissionError(13, "Permission denied")
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    loaded = load_project(root)
    monkeypatch.undo()
    assert any(i.code == "file_unreadable" for i in loaded.issues)
    assert loaded.project.recovered
    _assert_save_refused_and_untouched(loaded.project, root)


def test_a_damaged_project_can_still_be_saved_as_a_new_folder_and_lists_the_file(
    tmp_path: Path,
) -> None:
    root = _saved(tmp_path)
    victim = root / "physical" / "harnesses" / "W001.json"
    with victim.open("r+b") as f:
        f.truncate(loader_mod.MAX_FILE_BYTES + 1)
    loaded = load_project(root)
    save_project(loaded.project, tmp_path / "copy", allow_inconsistent=True)
    listed = json.loads((tmp_path / "copy" / "quarantine.json").read_text(encoding="utf-8"))
    assert [i["file"] for i in listed["items"]] == ["physical/harnesses/W001.json"]


# ---- A-3: a lone surrogate is invalid JSON; the writer never raises UnicodeEncodeError ----------


def test_a_lone_surrogate_in_a_config_value_makes_the_file_damaged_not_clean(
    tmp_path: Path,
) -> None:
    root = _saved(tmp_path)
    path = root / "config" / "naming.json"
    text = path.read_text(encoding="utf-8").replace(
        '"harness":', '"extra": "x\\ud800y", "harness":'
    )
    path.write_text(text, encoding="utf-8")
    loaded = load_project(root)
    assert any(i.code == "invalid_json" for i in loaded.issues) and loaded.has_errors
    assert loaded.project.quarantine_files["config/naming.json"] == path.read_bytes()
    _assert_save_refused_and_untouched(loaded.project, root)
    save_project(loaded.project, tmp_path / "copy", allow_inconsistent=True)  # no crash
    write_journal(loaded.project, tmp_path / "copy")


def test_a_lone_surrogate_in_unit_notes_and_in_a_key_is_caught(tmp_path: Path) -> None:
    root = _saved(tmp_path)
    path = root / "logical" / "units" / "power.json"
    path.write_text(
        path.read_text(encoding="utf-8").replace('"notes": ""', '"notes": "a\\udc00b"'),
        encoding="utf-8",
    )
    loaded = load_project(root)
    assert loaded.has_errors and loaded.project.recovered
    save_project(loaded.project, tmp_path / "copy", allow_inconsistent=True)
    write_journal(loaded.project, tmp_path / "copy")
    with pytest.raises(ValueError, match="surrogate|valid"):
        canonical.loads_strict(b'{"a\\ud800": 1}')


def test_a_paired_surrogate_escape_is_ordinary_text() -> None:
    assert canonical.loads_strict(b'{"a": "\\ud83d\\ude00"}') == {"a": "\U0001f600"}


def test_the_writer_raises_a_harness_error_for_a_surrogate_that_still_gets_there() -> None:
    with pytest.raises(HarnessError):
        canonical.dumps({"x": "a\ud800b"})


# ---- E-4: stored units and box connectors are compared ------------------------------------------


def _released(tmp_path: Path) -> tuple[Project, str]:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    assert release_integrity(p) == []
    return p, hid


def _box(p: Project, hid: str) -> str:
    return next(c.mates_with for c in p.harnesses[hid].connectors if c.mates_with)


def test_a_changed_part_of_a_released_box_connector_is_reported(tmp_path: Path) -> None:
    p, hid = _released(tmp_path)
    box = p.connectors[_box(p, hid)]
    other = next(k for k, v in p.parts.items() if v.category == "connector" and k != box.part_id)
    apply_ops(p, [Put("connectors", evolve(box, part_id=other))])
    assert [i.code for i in release_integrity(p)] == ["released_modified"]


def test_a_changed_gender_of_a_released_box_connector_is_reported(tmp_path: Path) -> None:
    p, hid = _released(tmp_path)
    box = p.connectors[_box(p, hid)]
    gender = "male" if box.gender != "male" else "female"
    apply_ops(p, [Put("connectors", evolve(box, gender=gender))])
    assert [i.code for i in release_integrity(p)] == ["released_modified"]


def test_a_changed_pin_of_a_released_box_connector_is_reported(tmp_path: Path) -> None:
    p, hid = _released(tmp_path)
    box = p.connectors[_box(p, hid)]
    carried = {w.interface_id for w in p.harnesses[hid].wires if w.interface_id}
    first = next(i for i, pin in enumerate(box.pins) if pin.interface_id in carried)
    pins = list(box.pins)
    pins[first] = evolve(pins[first], signal="HACKED")
    apply_ops(p, [Put("connectors", evolve(box, pins=pins))])
    assert [i.code for i in release_integrity(p)] == ["released_modified"]


def test_a_deleted_box_connector_pin_is_reported(tmp_path: Path) -> None:
    p, hid = _released(tmp_path)
    box = p.connectors[_box(p, hid)]
    carried = {w.interface_id for w in p.harnesses[hid].wires if w.interface_id}
    pins = [x for x in box.pins if x.interface_id not in carried]
    apply_ops(p, [Put("connectors", evolve(box, pins=pins))])
    assert [i.code for i in release_integrity(p)] == ["released_modified"]


def test_pins_of_other_harnesses_and_labels_may_change_after_a_release(tmp_path: Path) -> None:
    p, hid = _released(tmp_path)
    box = p.connectors[_box(p, hid)]
    carried = {w.interface_id for w in p.harnesses[hid].wires if w.interface_id}
    pins = [evolve(x, signal="OTHER") if x.interface_id not in carried else x for x in box.pins]
    apply_ops(p, [Put("connectors", evolve(box, pins=pins, name="Renamed", notes="n"))])
    assert release_integrity(p) == []


def test_a_changed_unit_design_field_of_a_released_harness_is_reported(tmp_path: Path) -> None:
    p, hid = _released(tmp_path)
    uid = p.connectors[_box(p, hid)].unit_id
    assert uid
    unit = p.units[uid]
    apply_ops(
        p, [Put("units", evolve(unit, side="redundant" if unit.side != "redundant" else "nominal"))]
    )
    assert [i.code for i in release_integrity(p)] == ["released_modified"]
    apply_ops(p, [Put("units", unit)])
    apply_ops(p, [Put("units", evolve(unit, name="Renamed", notes="x", zone="elsewhere"))])
    assert release_integrity(p) == []


def test_a_missing_unit_of_a_released_harness_is_reported(tmp_path: Path) -> None:
    p, hid = _released(tmp_path)
    uid = p.connectors[_box(p, hid)].unit_id
    assert uid
    del p.units[uid]
    assert "released_modified" in {i.code for i in release_integrity(p)}


# ---- I-2: lock rule survivors M31-M35 -----------------------------------------------------------


def test_a_released_harness_cannot_be_replaced_by_a_non_draft_copy(tmp_path: Path) -> None:  # M31
    p, hid = _released(tmp_path)
    h = p.harnesses[hid]
    for status in ("in_review", "released"):
        new = evolve(h, revision="B", status=status)
        with pytest.raises(TransactionError):
            History(p).execute("x", [Put("harnesses", new)])


def test_a_released_harness_cannot_be_edited_under_the_same_revision(tmp_path: Path) -> None:  # M32
    p, hid = _released(tmp_path)
    h = p.harnesses[hid]
    new = evolve(h, status="draft", revision=h.revision)
    with pytest.raises(TransactionError):
        History(p).execute("x", [Put("harnesses", new)])
    new = evolve(h, status="draft", revision=h.revision, wires=h.wires[1:])
    with pytest.raises(TransactionError):
        History(p).execute("x", [Put("harnesses", new)])


def test_part_gender_keying_of_a_used_box_connector_are_locked(tmp_path: Path) -> None:  # M33
    p, hid = _released(tmp_path)
    box = p.connectors[_box(p, hid)]
    other = next(k for k, v in p.parts.items() if v.category == "connector" and k != box.part_id)
    for change in (
        {"part_id": other},
        {"gender": "male" if box.gender != "male" else "female"},
        {"keying": "K-other"},
    ):
        with pytest.raises(TransactionError):
            History(p).execute("x", [Put("connectors", evolve(box, **change))])


def test_redundancy_and_voltage_of_a_carried_interface_are_locked(tmp_path: Path) -> None:  # M34
    p, hid = _released(tmp_path)
    iid = next(w.interface_id for w in p.harnesses[hid].wires if w.interface_id)
    i = p.interfaces[iid]
    other_side = "redundant" if i.redundancy != "redundant" else "nominal"
    for change in ({"redundancy": other_side}, {"voltage_v": (i.voltage_v or 0) + 1.0}):
        with pytest.raises(TransactionError):
            History(p).execute("x", [Put("interfaces", evolve(i, **change))])
    History(p).execute("cosmetic", [Put("interfaces", evolve(i, notes="just a note"))])


def test_the_release_record_cannot_be_overwritten(tmp_path: Path) -> None:  # M35
    p, hid = _released(tmp_path)
    b = next(iter(p.baselines.values()))
    e = next(iter(p.changelog.values()))
    with pytest.raises(TransactionError):
        History(p).execute("x", [Put("baselines", evolve(b, comment="rewritten history"))])
    with pytest.raises(TransactionError):
        History(p).execute("x", [Put("changelog", evolve(e, comment="rewritten history"))])
    with pytest.raises(TransactionError):
        History(p).execute("x", [Delete("changelog", e.id)])


def test_design_fields_of_a_unit_of_a_released_harness_are_locked(tmp_path: Path) -> None:
    p, hid = _released(tmp_path)
    uid = p.connectors[_box(p, hid)].unit_id
    assert uid
    unit = p.units[uid]
    other_side = "redundant" if unit.side != "redundant" else "nominal"
    with pytest.raises(TransactionError):
        History(p).execute("x", [Put("units", evolve(unit, side=other_side))])
    History(p).execute("label", [Put("units", evolve(unit, name="Renamed", zone="elsewhere"))])
