"""REQ-JOURNAL-01: autosave journal inside the project folder; layout/waiver persistence."""

import json
from pathlib import Path

from harness_design_studio.core import edit
from harness_design_studio.core.commands import History
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.recovery import (
    clear_journal,
    has_journal,
    journal_differs_from_disk,
    journal_path,
    read_journal,
    write_journal,
)
from harness_design_studio.core.samples import mini3
from tests.helpers import FIXTURES, copy_project, edit_json


def test_journal_round_trip_and_clear(tmp_path: Path) -> None:
    root = tmp_path / "p"
    p = mini3()
    save_project(p, root)
    assert not has_journal(root)
    History(p).execute("add", edit.ops_add_unit(p, "sensor")[0])  # unsaved change
    write_journal(p, root)
    assert has_journal(root) and journal_differs_from_disk(root)
    restored = read_journal(root)
    assert restored is not None and not restored.has_errors
    assert model_hash(restored.project) == model_hash(p)
    clear_journal(root)
    assert not has_journal(root) and not (root / ".harness-recovery").exists()
    assert read_journal(root) is None


def test_journal_equal_to_disk_is_not_a_difference(tmp_path: Path) -> None:
    root = tmp_path / "p"
    p = mini3()
    save_project(p, root)
    write_journal(p, root)
    assert not journal_differs_from_disk(root)


def test_corrupt_journal_is_ignored(tmp_path: Path) -> None:
    root = tmp_path / "p"
    save_project(mini3(), root)
    for garbage in ("not json", "[]", '{"files": 3}', '{"files": {"project.json": "{"}}'):
        journal_path(root).parent.mkdir(exist_ok=True)
        journal_path(root).write_text(garbage)
        assert read_journal(root) is None, garbage  # unusable: ignored, never raises
        if "project.json" not in garbage:
            # (a journal whose files parse as text but not as JSON still counts as "differs"; that
            # is reported in the audit notes, so it is not pinned here)
            assert journal_differs_from_disk(root) is False, garbage


def test_journal_never_leaves_the_project_folder(tmp_path: Path) -> None:
    root = tmp_path / "p"
    save_project(mini3(), root)
    write_journal(mini3(), root)
    assert journal_path(root).resolve().is_relative_to(root.resolve())


def test_layout_zones_and_waivers_persist(tmp_path: Path) -> None:
    from harness_design_studio.core import checks

    root = tmp_path / "p"
    p = mini3()
    h = History(p)
    h.execute("zone", edit.ops_add_zone(p, "deck"))
    h.execute("redundant", edit.ops_redundant_copy(p, "RW1").ops)
    finding = next(f for f in checks.open_findings(p) if f.rule == "cross-strap")
    h.execute("waive", [checks.waive_op(finding, "Cross-strap is intentional, see ICD 4.2")])
    save_project(p, root)
    again = load_project(root)
    assert not again.has_errors and not again.project.recovered
    assert again.project.zones == ["panel-A", "panel-B", "deck"]
    assert again.project.placements["RW1-R"] == p.placements["RW1-R"]
    assert finding.id in again.project.waivers
    assert model_hash(again.project) == model_hash(p)
    assert (root / "waivers.json").exists()
    h.undo()
    h.undo()  # waiver removed again
    save_project(p, root)
    assert (root / "waivers.json.bak").exists() and not (root / "waivers.json").exists()


def test_m1_format_project_still_loads_cleanly() -> None:
    result = load_project(FIXTURES / "m1_project")
    assert not result.has_errors and not result.project.recovered
    assert result.project.zones == ["panel-A", "panel-B"] and result.project.placements == {}
    assert all(not e.auto for i in result.project.interfaces.values() for e in i.endpoints)
    assert edit.position_of(result.project, "OBC")  # unplaced units get a slot


def test_bad_layout_and_waiver_files_are_quarantined(tmp_path: Path) -> None:
    root = copy_project(FIXTURES / "projects" / "mini3", tmp_path / "p")
    (root / "logical/layout.json").write_text('{"zones": "x", "placements": []}')
    r = load_project(root)
    assert r.project.recovered and r.project.zones == ["panel-A", "panel-B"]
    root2 = copy_project(FIXTURES / "projects" / "mini3", tmp_path / "q")
    edit_json(root2 / "logical/layout.json", lambda d: d.update(zones=["a", "a"]))
    assert load_project(root2).project.recovered
    edit_json(root2 / "logical/layout.json", lambda d: d.update(zones=["a", " "]))
    assert load_project(root2).project.recovered
    root3 = copy_project(FIXTURES / "projects" / "mini3", tmp_path / "r")
    (root3 / "waivers.json").write_text(
        json.dumps(
            {"waivers": [{"id": "x.y", "rule": "x", "object_id": "y", "justification": "short"}]}
        )
    )
    r3 = load_project(root3)
    assert r3.project.recovered and not r3.project.waivers


def test_orphan_placement_is_a_warning_not_an_error() -> None:
    from harness_design_studio.core.integrity import check_integrity
    from harness_design_studio.core.model import Placement

    p = mini3()
    p.placements["GHOST"] = Placement(id="GHOST", x=1, y=2)
    issues = check_integrity(p)
    assert [i.severity for i in issues] == ["warning"] and issues[0].code == "orphan_placement"
