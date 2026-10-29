"""REQ-OUT-07 (decision D-187): a waiver records a short hash of the finding it was made for. While
the finding says the same, the waiver applies; when the statement changes, the finding is open again
and the DRC report says so. A waiver without the hash (made before, or by hand) applies as before,
and the field is left out of the file while it is empty."""

import json
from dataclasses import replace

import pytest

from harness_design_studio.core import checks, drc, edit
from harness_design_studio.core.commands import History, Put, apply_ops
from harness_design_studio.core.drc.report import changed_waivers, render_markdown
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Project, Waiver, evolve
from harness_design_studio.core.samples import sat15

_BASE: Project | None = None


def base() -> Project:
    global _BASE
    if _BASE is None:
        _BASE = sat15()
        generate_project(_BASE)
    return edit.clone_with(_BASE, [])


def _waived(p: Project) -> checks.Finding:
    f = next(x for x in drc.run(p) if x.rule == "connector-lookalike")
    History(p).execute("waive", [checks.waive_op(f, "Keyed by the cable clamps, see ICD 4.2")])
    return f


def test_a_new_waiver_records_the_hash_of_its_finding() -> None:
    p = base()
    f = _waived(p)
    w = p.waivers[f.id]
    assert w.finding_hash == checks.finding_hash(f)
    assert len(w.finding_hash or "") == 12


def test_the_finding_stays_waived_while_it_says_the_same() -> None:
    p = base()
    f = _waived(p)
    again = next(x for x in drc.run(p) if x.id == f.id)
    assert again.waiver is not None and not again.waiver_changed


def test_a_finding_that_changed_is_open_again_and_the_report_says_so() -> None:
    p = base()
    f = _waived(p)
    apply_ops(p, [Put("waivers", evolve(p.waivers[f.id], finding_hash="0" * 12))])
    again = next(x for x in drc.run(p) if x.id == f.id)
    assert again.waiver is None and again.waiver_changed
    assert [x.id for x in changed_waivers(drc.run(p))] == [f.id]
    text = render_markdown(p)
    assert "Waivers that no longer fit" in text and "Keyed by the cable clamps" in text


def test_a_waiver_without_the_hash_applies_as_before() -> None:
    p = base()
    f = _waived(p)
    apply_ops(p, [Put("waivers", evolve(p.waivers[f.id], finding_hash=None))])
    again = next(x for x in drc.run(p) if x.id == f.id)
    assert again.waiver is not None and not again.waiver_changed
    assert "Waivers that no longer fit" not in render_markdown(p)


def test_waiving_again_replaces_the_waiver_with_the_current_hash() -> None:
    p = base()
    f = _waived(p)
    apply_ops(p, [Put("waivers", evolve(p.waivers[f.id], finding_hash="f" * 12))])
    open_again = next(x for x in drc.run(p) if x.id == f.id)
    History(p).execute("waive", [checks.waive_op(open_again, "Checked again, still accepted")])
    now = next(x for x in drc.run(p) if x.id == f.id)
    assert now.waiver is not None and now.waiver.finding_hash == checks.finding_hash(now)


def test_the_hash_depends_on_the_statement_and_the_rule_only() -> None:
    f = checks.Finding("r.o", "r", "warning", "o", "Title", "Why", can_waive=True)
    assert checks.finding_hash(f) == checks.finding_hash(replace(f, why="Other why", object_id="x"))
    assert checks.finding_hash(f) != checks.finding_hash(replace(f, title="Another title"))
    assert checks.finding_hash(f) != checks.finding_hash(replace(f, rule="other"))


def test_with_waiver_leaves_a_finding_that_cannot_be_waived_alone() -> None:
    p = base()
    f = checks.Finding("r.o", "r", "error", "o", "Title", "Why", can_waive=False)
    p.waivers["r.o"] = Waiver(id="r.o", rule="r", object_id="o", justification="long enough text")
    assert checks.with_waiver(p, f) == f


def test_the_hash_is_left_out_of_the_file_while_empty_and_survives_save_and_load(tmp_path) -> None:  # type: ignore[no-untyped-def]
    w = Waiver(id="r.o", rule="r", object_id="o", justification="long enough text")
    assert "finding_hash" not in json.loads(w.model_dump_json())
    p = base()
    f = _waived(p)
    save_project(p, tmp_path / "p")
    q = load_project(tmp_path / "p").project
    assert q.waivers[f.id].finding_hash == p.waivers[f.id].finding_hash
    assert any(x.waiver for x in drc.run(q) if x.id == f.id)


def test_a_malformed_hash_is_refused() -> None:
    with pytest.raises(ValueError):
        Waiver(
            id="r.o", rule="r", object_id="o", justification="long enough text", finding_hash="XYZ"
        )
