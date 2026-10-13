"""Low findings of the audit in the data layer and the rules (A-13 to A-17, C-22, C-23)."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_design_studio.cli.main import main
from harness_design_studio.core import commands, drc
from harness_design_studio.core.commands import History, Put, apply_ops
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import (
    Baseline,
    ChangeEntry,
    LibraryInfo,
    Project,
    Unit,
    evolve,
)
from harness_design_studio.core.model.review import Snapshot
from harness_design_studio.core.samples import mini3
from tests import test_drc as t

SRC = Path(__file__).resolve().parents[1] / "src" / "harness_design_studio"


def codes(p: Project) -> set[str]:
    return {i.code for i in check_integrity(p)}


# ---- A-13: set-aside objects are located in one pass per file -------------------------------------------


def test_many_set_aside_units_read_their_file_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_project(mini3(), tmp_path / "p")
    f = next((tmp_path / "p" / "logical" / "units").glob("*.json"))
    data = json.loads(f.read_text(encoding="utf-8"))
    good = data["units"][0]
    bad = [{**good, "id": f"BAD{k:04d}", "zone": 5} for k in range(300)]
    f.write_text(json.dumps({"units": data["units"] + bad}, indent=2, sort_keys=True), "utf-8")
    reads: list[Path] = []
    real = Path.read_bytes

    def counting(self: Path) -> bytes:
        reads.append(self)
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    result = load_project(tmp_path / "p")
    assert sum(1 for i in result.issues if i.code == "quarantined") == 300
    assert sum(1 for r in reads if r == f) <= 2  # the loader reads it once, the line search once


def test_each_set_aside_object_still_gets_its_own_line(tmp_path: Path) -> None:
    save_project(mini3(), tmp_path / "p")
    f = next((tmp_path / "p" / "logical" / "units").glob("*.json"))
    data = json.loads(f.read_text(encoding="utf-8"))
    data["units"][0]["zone"] = 5
    f.write_text(json.dumps(data, indent=2, sort_keys=True), "utf-8")
    text = f.read_text(encoding="utf-8")
    line = text[: text.index(f'"id": "{data["units"][0]["id"]}"')].count("\n") + 1
    msgs = [i.message for i in load_project(tmp_path / "p").issues if i.code == "quarantined"]
    assert [m for m in msgs if m.endswith(f"(line {line})")], msgs


# ---- A-14: the undo history is capped; an empty change is not a step ------------------------------------


def test_the_undo_history_is_capped() -> None:
    p = mini3()
    hist = History(p)
    unit = next(iter(p.units.values()))
    for k in range(commands.MAX_UNDO_STEPS + 20):
        hist.execute(f"edit {k}", [Put("units", evolve(unit, notes=f"n{k}"))])
    undone = 0
    while hist.can_undo:
        hist.undo()
        undone += 1
    assert undone == commands.MAX_UNDO_STEPS


def test_an_empty_change_is_no_undo_step_and_keeps_redo() -> None:
    p = mini3()
    hist = History(p)
    unit = next(iter(p.units.values()))
    hist.execute("edit", [Put("units", evolve(unit, notes="x"))])
    hist.undo()
    revision = hist.revision
    hist.execute("nothing", [])
    assert hist.can_redo and hist.revision == revision and hist.next_undo_label is None


# ---- A-15: the integrity cache sees the owning harness's generated flag ---------------------------------


def test_a_changed_generated_flag_is_seen_by_the_integrity_cache() -> None:
    p = t.base()
    h = next(h for h in p.harnesses.values() if h.generated)
    c = h.connectors[0]
    new_c = c.model_copy(update={"mates_with": "NOWHERE-J99"})
    plan = h.model_copy(update={"connectors": [new_c, *h.connectors[1:]]})
    p.harnesses[h.id] = plan
    assert [i.severity for i in check_integrity(p) if i.code == "unknown_mate"] == ["warning"]
    p.harnesses[h.id] = plan.model_copy(update={"generated": False})  # same connector objects
    assert [i.severity for i in check_integrity(p) if i.code == "unknown_mate"] == ["error"]


# ---- A-16: text validation ------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["20240101", "2024-W01-1", "2024-1-1", "2024-02-30", "soon", ""])
def test_a_library_date_must_be_yyyy_mm_dd(bad: str) -> None:
    with pytest.raises(ValidationError):
        LibraryInfo(date=bad)
    assert LibraryInfo(date="2024-02-29").date == "2024-02-29"


_INVISIBLE = [chr(c) for c in (0x2028, 0x2029, 0xE000, 0xFEFF)]


@pytest.mark.parametrize("bad", [f"a{c}b" for c in _INVISIBLE])
def test_names_refuse_line_separators_and_private_use_text(bad: str) -> None:
    with pytest.raises(ValidationError):
        Unit(id="U1", name=bad, subsystem="s")


def test_a_name_may_keep_accents_and_joiners() -> None:
    nbsp, combining = chr(0x00A0), chr(0x0301)
    assert Unit(id="U1", name=f"Reg{combining}ulateur 5{nbsp}V", subsystem="s").subsystem == "s"
    assert Unit(id="U2", name="Régulateur", subsystem="s").name == "Régulateur"


def test_release_dates_must_be_dates() -> None:
    snap = Snapshot()
    kw = {"harness_id": "W001", "revision": "A", "by": "Ada", "comment": "a long enough text"}
    with pytest.raises(ValidationError):
        Baseline(id="W001.A", released_on="soon", content_hash="x", snapshot=snap, **kw)
    with pytest.raises(ValidationError):
        ChangeEntry(id="C0001", harness_id="W001", revision="A", kind="release", by="Ada", when="x")


def test_layout_zones_with_control_characters_are_set_aside(tmp_path: Path) -> None:
    save_project(mini3(), tmp_path / "p")
    f = tmp_path / "p" / "logical" / "layout.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    data["zones"] = ["panel-A", "bad" + chr(0xE000) + "zone"]
    f.write_text(json.dumps(data), "utf-8")
    result = load_project(tmp_path / "p")
    assert any(i.code == "quarantined" and "zone" in i.message for i in result.issues)
    assert "bad" + chr(0xE000) + "zone" not in result.project.zones


# ---- A-17: referential gaps -----------------------------------------------------------------------------


def test_a_part_that_mates_with_itself_or_a_missing_part_is_an_error() -> None:
    p = mini3()
    part = next(x for x in p.parts.values() if x.category == "connector")
    assert "unknown_mate_part" not in codes(p)
    for target in (part.id, "NO-SUCH-PART"):
        q = mini3()
        q.parts[part.id] = evolve(part, mates_with=target)
        assert "unknown_mate_part" in codes(q)


def test_a_connector_for_a_missing_interface_type_is_reported() -> None:
    p = mini3()
    box = next(iter(p.connectors.values()))
    p.connectors[box.id] = evolve(box, carries=["NO-SUCH-TYPE"])
    found = [i for i in check_integrity(p) if i.code == "unknown_carried_type"]
    assert found and found[0].severity == "warning"


def _baseline(p: Project, bid: str, hid: str, rev: str = "A") -> Baseline:
    return Baseline(
        id=bid, harness_id=hid, revision=rev, released_on="2026-01-02", by="Ada",
        comment="a long enough comment", content_hash="x", snapshot=Snapshot(),
    )  # fmt: skip


def test_release_records_must_belong_to_a_harness_and_match_their_id() -> None:
    p = t.base()
    hid = next(iter(p.harnesses))
    p.baselines[f"{hid}.A"] = _baseline(p, f"{hid}.A", hid)
    assert not codes(p) & {"unknown_harness", "baseline_id_mismatch"}
    p.baselines["GHOST.A"] = _baseline(p, "GHOST.A", "GHOST")
    assert "unknown_harness" in codes(p)
    p.baselines["GHOST.A"] = _baseline(p, "GHOST.A", hid)
    assert "baseline_id_mismatch" in codes(p)


def test_baselines_that_differ_only_by_case_are_reported() -> None:
    p = t.base()
    hid = next(iter(p.harnesses))
    p.baselines[f"{hid}.A"] = _baseline(p, f"{hid}.A", hid, "A")
    p.baselines[f"{hid}.a"] = _baseline(p, f"{hid}.a", hid, "a")
    assert any(i.code == "duplicate_id" and "baselines" in i.message for i in check_integrity(p))


def test_a_change_log_entry_of_a_deleted_harness_is_only_a_warning() -> None:
    p = t.base()
    p.changelog["C0001"] = ChangeEntry(
        id="C0001", harness_id="GONE", revision="A", kind="review", by="Ada", when="2026-01-02"
    )
    found = [i for i in check_integrity(p) if i.object_id == "C0001"]
    assert found and all(i.severity == "warning" for i in found)


# ---- C-22 -----------------------------------------------------------------------------------------------


def test_manufacturer_names_are_compared_without_case_and_spaces() -> None:
    p = t.base()
    box = next(c for c in p.connectors.values() if c.part_id in p.parts)
    cable = next(
        (c, h) for h in p.harnesses.values() for c in h.connectors if c.mates_with == box.id
    )[0]
    a, b = p.parts[cable.part_id], p.parts[box.part_id]
    apply_ops(p, [Put("parts", evolve(a, manufacturer="Acme Corp"))])
    if b.id != a.id:
        apply_ops(p, [Put("parts", evolve(b, manufacturer=" ACME corp "))])
    assert t.fire("connector-manufacturer", p) == []
    if b.id != a.id:
        apply_ops(p, [Put("parts", evolve(b, manufacturer="Other"))])
        assert t.fire("connector-manufacturer", p)


def test_emc_class_split_sees_interfaces_that_only_the_wires_name() -> None:
    p = t.pos_emc_class_split()
    assert t.fire("emc-class-split", p)
    for h in list(p.harnesses.values()):
        apply_ops(p, [Put("harnesses", evolve(h, interfaces=[]))])
    assert t.fire("emc-class-split", p)


def test_findings_about_parts_can_be_shown() -> None:
    p = t.base()
    wire_part = next(w.part_id for h in p.harnesses.values() for w in h.wires if w.part_id)
    h = next(h for h in sorted(p.harnesses.values(), key=lambda x: x.id) if any(
        w.part_id == wire_part for w in h.wires))  # fmt: skip
    assert drc.locate(p, f"wire-spec.{wire_part}") == ("harness", h.id)
    box = next(c for c in p.connectors.values())
    cable_uses = any(c.part_id == box.part_id for hh in p.harnesses.values() for c in hh.connectors)
    where = drc.locate(p, f"mating-cycles.{box.part_id}")
    assert where is not None and where[0] == ("harness" if cable_uses else "unit")
    assert drc.locate(p, "mating-cycles.NO-SUCH-PART") is None


def test_applying_a_profile_to_generated_plans_says_they_are_out_of_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    save_project(t.base(), tmp_path / "p")
    assert load_project(tmp_path / "p").project.generation is not None
    main(["config", str(tmp_path / "p"), "--apply-profile", "ecss-q-st-30-11c"])
    out = capsys.readouterr().out
    assert "out of date" in out and "harness generate" in out


# ---- C-23 -----------------------------------------------------------------------------------------------


def test_the_verifier_does_not_import_the_generator() -> None:
    tree = ast.parse((SRC / "core" / "verify.py").read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.append(("." * node.level) + (node.module or ""))
        elif isinstance(node, ast.Import):
            names += [a.name for a in node.names]
    assert not [n for n in names if "generate" in n], names


# ---- A-18: tests for changes that earlier mutation runs did not catch -----------------------------------


def test_canonical_json_keeps_text_and_refuses_nan() -> None:
    from harness_design_studio.core.io import canonical

    assert canonical.dumps({"b": 1, "a": "é"}) == '{\n  "a": "é",\n  "b": 1\n}\n'.encode()
    with pytest.raises(ValueError):
        canonical.dumps({"x": float("nan")})


def test_a_second_error_of_the_same_kind_on_the_same_object_cancels_the_edit() -> None:
    from harness_design_studio.core.errors import TransactionError
    from harness_design_studio.core.model import Pin

    p = t.base()
    box = next(c for c in p.connectors.values() if len(c.pins) >= 2)
    first, second = box.pins[0], box.pins[1]
    apply_ops(p, [Put("connectors", evolve(box, pins=[*box.pins, first]))])  # one duplicate_pin
    assert [i.code for i in check_integrity(p)].count("duplicate_pin") == 1
    worse = evolve(p.connectors[box.id], pins=[*p.connectors[box.id].pins, second])
    hist = History(p)
    with pytest.raises(TransactionError):
        hist.execute("worse", [Put("connectors", worse)])
    assert [i.code for i in check_integrity(p)].count("duplicate_pin") == 1
    assert hist.revision == 0 and isinstance(first, Pin)


def test_every_change_undo_and_redo_moves_the_revision() -> None:
    p = mini3()
    hist = History(p)
    unit = next(iter(p.units.values()))
    hist.execute("edit", [Put("units", evolve(unit, notes="x"))])
    assert hist.revision == 1
    hist.undo()
    assert hist.revision == 2
    hist.redo()
    assert hist.revision == 3
