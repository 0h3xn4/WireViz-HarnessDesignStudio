"""REQ-TX-01: transactions are all-or-nothing with consistent undo/redo."""

import pytest

from harness_design_studio.core import edit
from harness_design_studio.core.commands import Delete, History, Put, SetConfig, SetMeta, apply_ops
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.model import ProjectMeta, Unit, evolve
from harness_design_studio.core.samples import mini3


def test_execute_undo_redo_restores_exact_state() -> None:
    p = mini3()
    h = History(p)
    start = model_hash(p)
    h.execute("add unit", [Put("units", Unit(id="NEW", name="n", subsystem="s"))])
    after = model_hash(p)
    assert after != start and "NEW" in p.units
    assert h.next_undo_label == "add unit"
    assert h.undo() == "add unit" and model_hash(p) == start
    assert h.can_redo and not h.can_undo
    assert h.redo() == "add unit" and model_hash(p) == after


def test_next_redo_label_names_the_step_redo_would_run() -> None:
    p = mini3()
    h = History(p)
    assert h.next_redo_label is None
    h.execute("a", [Put("units", Unit(id="A1", name="n", subsystem="s"))])
    h.execute("b", [Put("units", Unit(id="B1", name="n", subsystem="s"))])
    assert h.next_redo_label is None
    h.undo()
    assert h.next_redo_label == "b"
    h.undo()
    assert h.next_redo_label == "a"  # the next redo is the step undone last
    h.redo()
    assert h.next_redo_label == "b"
    h.execute("c", [Put("units", Unit(id="C1", name="n", subsystem="s"))])
    assert h.next_redo_label is None


def test_new_change_clears_redo() -> None:
    p = mini3()
    h = History(p)
    h.execute("a", [Put("units", Unit(id="A1", name="n", subsystem="s"))])
    h.undo()
    h.execute("b", [Put("units", Unit(id="B1", name="n", subsystem="s"))])
    assert not h.can_redo


def test_inconsistent_change_is_rolled_back() -> None:
    p = mini3()
    h = History(p)
    start = model_hash(p)
    with pytest.raises(TransactionError) as exc:
        h.execute("delete OBC", [Delete("units", "OBC")])  # interfaces still use it
    assert exc.value.problems
    assert model_hash(p) == start and not h.can_undo


def test_delete_with_dependants_in_one_transaction_is_allowed() -> None:
    p = mini3()
    h = History(p)
    h.execute("delete OBC", edit.ops_delete_unit(p, "OBC"))
    assert "OBC" not in p.units
    h.undo()
    assert "OBC" in p.units and "IF-TM-RW1" in p.interfaces


def test_failed_op_mid_transaction_applies_nothing() -> None:
    p = mini3()
    start = model_hash(p)
    with pytest.raises(KeyError):
        apply_ops(
            p, [Put("units", Unit(id="X1", name="n", subsystem="s")), Delete("units", "GHOST")]
        )
    assert model_hash(p) == start


def test_wrong_type_and_collection_fail_loudly() -> None:
    p = mini3()
    with pytest.raises(TypeError):
        apply_ops(p, [Put("interfaces", Unit(id="X1", name="n", subsystem="s"))])
    with pytest.raises(TypeError):
        apply_ops(p, [Put("nonsense", Unit(id="X1", name="n", subsystem="s"))])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_ops(p, [Delete("nonsense", "x")])  # type: ignore[arg-type]


def test_config_and_meta_ops_undo() -> None:
    p = mini3()
    h = History(p)
    cfg = evolve(p.config["derating"], placeholder=False)
    h.execute("confirm derating", [SetConfig(cfg), SetMeta(ProjectMeta(name="renamed"))])
    assert not p.config["derating"].placeholder and p.meta.name == "renamed"
    h.undo()
    assert p.config["derating"].placeholder and p.meta.name.startswith("mini3")


def test_read_only_project_rejects_changes() -> None:
    p = mini3()
    p.read_only = True
    with pytest.raises(TransactionError, match="read-only"):
        History(p).execute("x", [Put("units", Unit(id="A1", name="n", subsystem="s"))])


def test_existing_errors_do_not_block_unrelated_changes() -> None:
    p = mini3()
    p.units.pop("RW1")  # pre-existing inconsistency (as after a recovery)
    h = History(p)
    h.execute("rename", [Put("units", evolve(p.units["OBC"], name="renamed"))])
    assert p.units["OBC"].name == "renamed"
