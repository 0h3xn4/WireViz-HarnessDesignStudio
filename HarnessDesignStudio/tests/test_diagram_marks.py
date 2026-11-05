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
from harness_design_studio.core.model import DiagramMark, Link
from harness_design_studio.core.samples import mini3
from harness_design_studio.core.schemas import schemas


def marked():
    p = mini3()
    p.links["L1"] = Link(id="L1", a_connector="OBC-J01", b_connector="RW1-J02")
    p.diagram_marks["link:L1"] = DiagramMark(id="link:L1", dx=12.5, dy=-30.0)
    return p


def test_a_project_without_marks_has_no_marks_file() -> None:
    assert not [rel for rel in layout.serialize(mini3()) if rel.startswith("diagram/")]


def test_marks_are_in_a_file_of_their_own_and_change_no_other_file_and_no_hash() -> None:
    plain, with_marks = marked(), marked()
    del plain.diagram_marks["link:L1"]
    a, b = layout.serialize(plain), layout.serialize(with_marks)
    assert set(b) - set(a) == {"diagram/marks.json"}
    assert {
        rel for rel in a if a[rel] != b[rel] and rel != "logical/links.json"
    } == set()  # (the other files are as they were)
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


# ---- the marks of a thing that is gone ----------------------------------------------------------
def with_all_marks():
    p = marked()
    for key in ("end:L1:0", "end:L1:1", "bend:L1", "interface:IF-TM-RW1", "route:IF-TM-RW1"):
        p.diagram_marks[key] = DiagramMark(id=key, dx=5.0, dy=0.0)
    return p


def test_a_mark_is_an_orphan_when_its_connection_or_interface_is_gone() -> None:
    p = with_all_marks()
    assert not [m for m in p.diagram_marks if layout.mark_is_orphan(p, m)]
    del p.links["L1"]
    gone = sorted(m for m in p.diagram_marks if layout.mark_is_orphan(p, m))
    assert gone == ["bend:L1", "end:L1:0", "end:L1:1", "link:L1"]
    del p.interfaces["IF-TM-RW1"]
    assert layout.mark_is_orphan(p, "route:IF-TM-RW1") and layout.mark_is_orphan(
        p, "interface:IF-TM-RW1"
    )
    assert not layout.mark_is_orphan(p, "later:kind:of-mark")  # (not ours to drop)


def test_the_file_is_written_without_the_marks_of_a_deleted_thing_and_not_at_all_when_none_is_left(
    tmp_path,
) -> None:
    p = with_all_marks()
    save_project(p, tmp_path / "p")

    def ids() -> list[str]:
        doc = json.loads((tmp_path / "p" / "diagram" / "marks.json").read_text())
        return [m["id"] for m in doc["marks"]]

    assert len(ids()) == 6
    del p.links["L1"]
    save_project(p, tmp_path / "p")
    assert sorted(ids()) == ["interface:IF-TM-RW1", "route:IF-TM-RW1"]
    assert len(p.diagram_marks) == 6  # (in memory they wait: an undo of the delete needs them)
    del p.interfaces["IF-TM-RW1"]
    save_project(p, tmp_path / "p")
    assert not (tmp_path / "p" / "diagram" / "marks.json").exists()


def test_loading_drops_the_marks_of_a_thing_that_is_gone_without_a_word(tmp_path) -> None:
    save_project(with_all_marks(), tmp_path / "p")
    f = tmp_path / "p" / "diagram" / "marks.json"
    doc = json.loads(f.read_text())
    doc["marks"] += [
        {"id": "link:L9", "dx": 1.0, "dy": 2.0},
        {"id": "route:IF-OLD", "dx": 1.0, "dy": 0.0},
    ]
    f.write_text(json.dumps(doc))
    loaded = load_project(tmp_path / "p")
    assert "link:L9" not in loaded.project.diagram_marks
    assert "route:IF-OLD" not in loaded.project.diagram_marks
    assert len(loaded.project.diagram_marks) == 6
    assert not loaded.project.quarantine
    assert not [i for i in loaded.issues if "mark" in i.message.lower()]  # (silently)
    save_project(loaded.project, tmp_path / "p")
    assert len(json.loads(f.read_text())["marks"]) == 6  # (and the next save writes the clean file)


def test_a_project_whose_marks_all_vanish_loses_its_file_on_the_next_save(tmp_path) -> None:
    save_project(marked(), tmp_path / "p")
    f = tmp_path / "p" / "diagram" / "marks.json"
    links = tmp_path / "p" / "logical" / "links.json"
    links.unlink()  # (the connection was removed by hand)
    loaded = load_project(tmp_path / "p")
    assert loaded.project.diagram_marks == {}
    save_project(loaded.project, tmp_path / "p")
    assert not f.exists()


def test_the_marks_of_a_deleted_connection_come_back_with_an_undo_and_never_touch_the_hash() -> (
    None
):
    p = marked()
    h0 = layout.model_hash(p)
    history = History(p)
    link = p.links["L1"]
    history.execute("delete", [Delete("links", "L1")])
    assert "diagram/marks.json" not in layout.serialize(p)  # (not written while it is gone)
    history.undo()
    assert p.links["L1"] == link and "diagram/marks.json" in layout.serialize(p)
    assert layout.model_hash(p) == h0
    history.redo()
    assert "diagram/marks.json" not in layout.serialize(p)
    history.undo()
    assert [m.id for m in p.diagram_marks.values()] == ["link:L1"]  # (moved where it was)
    assert p.diagram_marks["link:L1"].dx == 12.5
