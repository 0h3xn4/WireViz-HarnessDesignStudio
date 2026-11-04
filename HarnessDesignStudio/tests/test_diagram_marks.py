# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""REQ-GUI-13. `diagram/marks.json`: where the person moved labels in the diagram. Optional, like
the import record: a project without marks has no such file, its files and model hash are as they
were, and a project with marks has the same model hash as without them."""

import json

import pytest

from harness_design_studio.core import journal
from harness_design_studio.core.commands import Delete, History, Put
from harness_design_studio.core.io import layout
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import DiagramMark
from harness_design_studio.core.samples import mini3
from harness_design_studio.core.schemas import schemas


def marked():
    p = mini3()
    p.diagram_marks["link:L1"] = DiagramMark(id="link:L1", dx=12.5, dy=-30.0)
    return p


def test_a_project_without_marks_has_no_marks_file() -> None:
    assert not [rel for rel in layout.serialize(mini3()) if rel.startswith("diagram/")]


def test_marks_are_in_a_file_of_their_own_and_change_no_other_file_and_no_hash() -> None:
    plain, with_marks = mini3(), marked()
    a, b = layout.serialize(plain), layout.serialize(with_marks)
    assert set(b) - set(a) == {"diagram/marks.json"}
    assert {rel for rel in a if a[rel] != b[rel]} == set()  # (the other files are as they were)
    assert layout.outside_the_hash("diagram/marks.json")
    assert layout.model_hash(with_marks) == layout.model_hash(plain)
    assert journal.files_hash(b) == journal.files_hash(a)


def test_marks_survive_save_and_load(tmp_path) -> None:
    p = marked()
    save_project(p, tmp_path / "p")
    doc = json.loads((tmp_path / "p" / "diagram" / "marks.json").read_text())
    assert doc == {"marks": [{"dx": 12.5, "dy": -30.0, "id": "link:L1"}]}
    loaded = load_project(tmp_path / "p")
    assert loaded.project.diagram_marks == p.diagram_marks
    assert not loaded.project.quarantine


def test_a_project_saved_without_marks_loads_and_saves_byte_for_byte(tmp_path) -> None:
    p = mini3()
    save_project(p, tmp_path / "p")
    before = {
        f.relative_to(tmp_path / "p"): f.read_bytes()
        for f in (tmp_path / "p").rglob("*")
        if f.is_file()
    }
    loaded = load_project(tmp_path / "p").project
    assert loaded.diagram_marks == {}
    save_project(loaded, tmp_path / "p")
    after = {
        f.relative_to(tmp_path / "p"): f.read_bytes()
        for f in (tmp_path / "p").rglob("*")
        if f.is_file()
    }
    assert after == before
    assert not (tmp_path / "p" / "diagram").exists()


def test_taking_the_last_mark_away_removes_the_file(tmp_path) -> None:
    p = marked()
    save_project(p, tmp_path / "p")
    del p.diagram_marks["link:L1"]
    save_project(p, tmp_path / "p")
    assert not (tmp_path / "p" / "diagram" / "marks.json").exists()


def test_a_damaged_mark_is_set_aside_and_the_project_still_opens(tmp_path) -> None:
    save_project(marked(), tmp_path / "p")
    f = tmp_path / "p" / "diagram" / "marks.json"
    f.write_text(json.dumps({"marks": [{"id": "link:L1", "dx": "far", "dy": 1.0}]}))
    loaded = load_project(tmp_path / "p")
    assert loaded.project.diagram_marks == {}
    assert loaded.project.quarantine


def test_a_mark_is_a_step_that_can_be_undone() -> None:
    p = mini3()
    h = History(p)
    h.execute("move", [Put("diagram_marks", DiagramMark(id="interface:IF-TM-RW1", dx=3.0, dy=4.0))])
    assert "interface:IF-TM-RW1" in p.diagram_marks
    h.undo()
    assert p.diagram_marks == {}
    h.redo()
    h.execute("reset", [Delete("diagram_marks", "interface:IF-TM-RW1")])
    assert p.diagram_marks == {}


def test_a_mark_has_a_schema_and_refuses_numbers_that_are_not_finite() -> None:
    assert "diagram-marks" in schemas()
    with pytest.raises(ValueError):
        DiagramMark(id="link:L1", dx=float("inf"), dy=0.0)
    with pytest.raises(ValueError):
        DiagramMark(id="link:L1", dx=0.0, dy=1e9)
