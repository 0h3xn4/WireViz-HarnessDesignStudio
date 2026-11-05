# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""REQ-GUI-13. `diagram/marks.json`: where the person moved labels in the diagram. Optional, like
the import record: a project without marks has no such file, its files and model hash are as they
were, and a project with marks has the same model hash as without them. A label that sits on a line
is a position along it (`t`, a fraction of the length of the line); a bend or a route is an offset;
a mark of release 1.14 and 1.15 (a free offset of a label) is still read."""

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
    p.diagram_marks["link:L1"] = DiagramMark(id="link:L1", t=0.25)
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
    assert doc == {"marks": [{"id": "link:L1", "t": 0.25}]}
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
    h.execute("move", [Put("diagram_marks", DiagramMark(id="interface:IF-TM-RW1", t=0.75))])
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
    for t in (-0.1, 1.5, float("nan")):
        with pytest.raises(ValueError):
            DiagramMark(id="link:L1", t=t)


# ---- the marks of a thing that is gone ----------------------------------------------------------
def with_all_marks():
    p = marked()
    for key in ("end:L1:0", "end:L1:1", "interface:IF-TM-RW1"):
        p.diagram_marks[key] = DiagramMark(id=key, t=0.4)
    for key in ("bend:L1", "route:IF-TM-RW1"):
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
        {"id": "link:L9", "dx": 1.0, "dy": 2.0},  # (a mark of an earlier version)
        {"id": "link:L8", "t": 0.5},
        {"id": "end:L8:1", "t": 0.9},
        {"id": "interface:IF-OLD", "t": 0.1},
        {"id": "route:IF-OLD", "dx": 1.0, "dy": 0.0},
    ]
    f.write_text(json.dumps(doc))
    loaded = load_project(tmp_path / "p")
    for gone in ("link:L9", "link:L8", "end:L8:1", "interface:IF-OLD", "route:IF-OLD"):
        assert gone not in loaded.project.diagram_marks
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
    assert p.diagram_marks["link:L1"].t == 0.25


# ---- the two forms of a mark: a place along the line, and the offset of 1.14 and 1.15 -----------
def write_marks(folder, marks):
    f = folder / "diagram" / "marks.json"
    f.parent.mkdir(exist_ok=True)
    f.write_text(json.dumps({"marks": marks}))
    return f


def test_a_mark_of_an_earlier_version_is_read_and_kept_as_it_is_until_the_diagram_turns_it() -> (
    None
):
    old = DiagramMark.model_validate({"id": "interface:IF-TM-RW1", "dx": 12.5, "dy": -30.0})
    assert (old.dx, old.dy, old.t) == (12.5, -30.0, None)
    new = DiagramMark.model_validate({"id": "interface:IF-TM-RW1", "t": 0.5})
    assert (new.dx, new.dy, new.t) == (None, None, 0.5)
    assert old.model_dump(mode="json") == {"id": "interface:IF-TM-RW1", "dx": 12.5, "dy": -30.0}
    assert new.model_dump(mode="json") == {"id": "interface:IF-TM-RW1", "t": 0.5}
    # a bend and a route stay as they were written by 1.15.0, byte for byte, a zero included
    route = DiagramMark(id="route:IF-TM-RW1", dx=-14.0, dy=0.0)
    assert route.model_dump(mode="json") == {"id": "route:IF-TM-RW1", "dx": -14.0, "dy": 0.0}


def test_an_old_file_loads_and_is_written_back_as_it_was(tmp_path) -> None:
    p = marked()
    del p.diagram_marks["link:L1"]
    save_project(p, tmp_path / "p")
    marks = [  # (sorted by ID, as the tool writes them)
        {"dx": 5.0, "dy": 0.0, "id": "bend:L1"},
        {"dx": 12.5, "dy": -30.0, "id": "link:L1"},
    ]
    f = write_marks(tmp_path / "p", marks)
    loaded = load_project(tmp_path / "p")
    assert not loaded.project.quarantine
    assert loaded.project.diagram_marks["link:L1"].dx == 12.5
    save_project(loaded.project, tmp_path / "p")  # (the diagram has not looked at it: as it was)
    assert json.loads(f.read_text()) == {"marks": marks}


def test_marks_of_both_forms_live_in_one_file_and_neither_changes_the_hash(tmp_path) -> None:
    p = marked()
    p.diagram_marks["end:L1:1"] = DiagramMark(id="end:L1:1", t=1.0)
    p.diagram_marks["bend:L1"] = DiagramMark(id="bend:L1", dx=-8.0, dy=0.0)
    p.diagram_marks["interface:IF-TM-RW1"] = DiagramMark(id="interface:IF-TM-RW1", dx=3.0, dy=4.0)
    plain = marked()
    plain.diagram_marks.clear()
    assert layout.model_hash(p) == layout.model_hash(plain)
    save_project(p, tmp_path / "p")
    doc = json.loads((tmp_path / "p" / "diagram" / "marks.json").read_text())
    assert [m["id"] for m in doc["marks"]] == sorted(m["id"] for m in doc["marks"])
    assert {m["id"]: sorted(m) for m in doc["marks"]} == {
        "bend:L1": ["dx", "dy", "id"],
        "end:L1:1": ["id", "t"],
        "interface:IF-TM-RW1": ["dx", "dy", "id"],
        "link:L1": ["id", "t"],
    }
    assert load_project(tmp_path / "p").project.diagram_marks == p.diagram_marks


BAD_MARKS = [
    {"id": "link:L1", "t": 1.5},  # outside the line
    {"id": "link:L1", "t": -0.2},
    {"id": "link:L1", "t": "half"},
    {"id": "link:L1", "t": None},  # no place at all
    {"id": "link:L1"},
    {"id": "link:L1", "dx": 3.0},  # an offset needs both
    {"id": "link:L1", "t": 0.5, "dx": 1.0, "dy": 1.0},  # two places
    {"id": "bend:L1", "t": 0.5},  # a bend is an offset
    {"id": "route:IF-TM-RW1", "t": 0.5},
    {"id": "link:L1", "t": 0.5, "colour": "red"},  # a field nobody knows
]


@pytest.mark.parametrize("bad", BAD_MARKS, ids=lambda m: json.dumps(m))
def test_a_damaged_mark_of_any_kind_is_set_aside_as_today_and_the_rest_is_kept(
    tmp_path, bad
) -> None:
    save_project(marked(), tmp_path / "p")
    write_marks(tmp_path / "p", [bad, {"id": "interface:IF-TM-RW1", "t": 0.3}])
    loaded = load_project(tmp_path / "p")
    assert set(loaded.project.diagram_marks) == {"interface:IF-TM-RW1"}
    assert [q.file for q in loaded.project.quarantine] == ["diagram/marks.json"]
    assert layout.model_hash(loaded.project) == layout.model_hash(marked())  # (no design harmed)


def test_a_mark_of_a_kind_this_tool_does_not_know_is_kept_and_never_an_orphan(tmp_path) -> None:
    save_project(marked(), tmp_path / "p")
    write_marks(
        tmp_path / "p", [{"id": "later:thing", "t": 0.5}, {"id": "later:old", "dx": 1.0, "dy": 2.0}]
    )
    loaded = load_project(tmp_path / "p")
    assert set(loaded.project.diagram_marks) == {"later:thing", "later:old"}
    assert not loaded.project.quarantine
    assert not layout.mark_is_orphan(loaded.project, "later:thing")


def test_the_places_of_a_deleted_thing_are_not_written_and_come_back_with_the_undo(
    tmp_path,
) -> None:
    p = with_all_marks()
    history = History(p)
    history.execute("delete", [Delete("links", "L1")])
    save_project(p, tmp_path / "p")
    doc = json.loads((tmp_path / "p" / "diagram" / "marks.json").read_text())
    assert {m["id"]: m.get("t") for m in doc["marks"]} == {
        "interface:IF-TM-RW1": 0.4,
        "route:IF-TM-RW1": None,
    }
    history.undo()
    save_project(p, tmp_path / "p")
    doc = json.loads((tmp_path / "p" / "diagram" / "marks.json").read_text())
    assert {m["id"]: m.get("t") for m in doc["marks"]} == {
        "bend:L1": None,
        "end:L1:0": 0.4,
        "end:L1:1": 0.4,
        "interface:IF-TM-RW1": 0.4,
        "link:L1": 0.25,
        "route:IF-TM-RW1": None,
    }


def test_the_schema_of_the_file_names_the_place_and_the_offset() -> None:
    schema = json.dumps(schemas()["diagram-marks"])
    assert '"t"' in schema and '"dx"' in schema and '"dy"' in schema


def test_no_written_output_changes_with_marks_of_either_form_not_even_the_block_diagram() -> None:
    """The block diagram that is written has the router's own places for its labels: where the
    person put a label in the editor is not in any output."""
    from harness_design_studio.core.outputs.build import build_outputs

    plain, with_marks = marked(), marked()
    del plain.diagram_marks["link:L1"]
    for key, mark in {
        "interface:IF-TM-RW1": DiagramMark(id="interface:IF-TM-RW1", t=0.9),
        "route:IF-TM-RW1": DiagramMark(id="route:IF-TM-RW1", dx=30.0, dy=0.0),
        "end:L1:0": DiagramMark(id="end:L1:0", dx=3.0, dy=4.0),  # (an old one)
    }.items():
        with_marks.diagram_marks[key] = mark
    a = build_outputs(plain, drawings=False)
    b = build_outputs(with_marks, drawings=False)
    assert a.files.keys() == b.files.keys()
    assert {name for name in a.files if a.files[name] != b.files[name]} == set()
    assert any(name.startswith("system/block_diagram") for name in a.files)
