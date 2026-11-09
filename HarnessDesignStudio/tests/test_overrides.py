# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg,func-returns-value"
"""S4 (D-191, R7): a value of a generated wire set by hand is an override with a reason. The model, the
edit functions and the command line refuse one without a reason; generation keeps it; `explain` says
what the design would have given and what the set value does to the checks; a project whose wires are
locked from before reasons were kept opens and saves as it did."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_design_studio.cli.main import main
from harness_design_studio.core import templates
from harness_design_studio.core.commands import History, Put, apply_ops
from harness_design_studio.core.derive import explain_wire, render
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.generate.engine import generate_project, plan_generation
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Part, Wire, evolve
from harness_design_studio.core.samples import sat15
from harness_design_studio.core.wires import (
    LEGACY_REASON,
    find_wire,
    plan_clear_override,
    plan_override,
    plan_wire_edit,
    plan_wire_reset,
)


@pytest.fixture
def project():
    p = sat15()
    generate_project(p)
    p.parts["EX-WIRE-22"] = Part(id="EX-WIRE-22", category="wire")
    return p


def a_wire(p) -> Wire:
    return next(w for h in p.harnesses.values() for w in h.wires if not w.manual)


def regenerate(p) -> None:
    apply_ops(p, plan_generation(p).ops)


def wire_dict(**extra) -> dict:
    base = dict(id="W1-1", from_connector="a", from_pin="1", to_connector="b", to_pin="1")
    return {**base, **extra}


# ---- the model ---------------------------------------------------------------------------------


@pytest.mark.parametrize("reason", ["", "   ", "\n\t "])
def test_the_model_refuses_an_override_without_a_reason(reason):
    with pytest.raises(ValidationError):
        Wire(**wire_dict(gauge_awg=20, locked=True, overrides={"gauge_awg": reason}))


def test_the_model_refuses_an_override_that_is_not_one_of_the_four_values():
    with pytest.raises(ValidationError, match="cannot be overridden"):
        Wire(**wire_dict(locked=True, overrides={"note": "why"}))


def test_the_model_refuses_an_override_of_a_value_the_wire_does_not_have():
    with pytest.raises(ValidationError, match="needs a value"):
        Wire(**wire_dict(locked=True, overrides={"gauge_awg": "why"}))


def test_the_model_refuses_an_override_on_a_wire_that_is_not_locked():
    with pytest.raises(ValidationError, match="must be locked"):
        Wire(**wire_dict(gauge_awg=20, overrides={"gauge_awg": "why"}))


def test_a_wire_without_overrides_is_written_as_before():
    w = Wire(**wire_dict(gauge_awg=20, locked=True))
    assert "overrides" not in w.model_dump(mode="json")
    w2 = Wire(**wire_dict(gauge_awg=20, locked=True, overrides={"gauge_awg": "ECR-7"}))
    assert w2.model_dump(mode="json")["overrides"] == {"gauge_awg": "ECR-7"}


# ---- the edit functions ------------------------------------------------------------------------


@pytest.mark.parametrize("reason", [None, "", "  "])
@pytest.mark.parametrize("field,value", [("gauge_awg", 20), ("colour", "pink"), ("length_m", 9.0)])
def test_an_edit_of_a_generated_wire_without_a_reason_is_refused(project, field, value, reason):
    w = a_wire(project)
    with pytest.raises(EditError, match="needs a reason"):
        plan_wire_edit(project, [w.id], {field: value}, reason=reason)
    with pytest.raises(EditError, match="needs a reason"):
        History(project).execute("x", plan_wire_edit(project, [w.id], {field: value}))


def test_label_and_note_need_no_reason(project):
    w = a_wire(project)
    assert plan_wire_edit(project, [w.id], {"label": "Bus A", "note": "twist"})


def test_a_wire_a_person_drew_needs_no_reason_because_nothing_is_overridden(project):
    from harness_design_studio.core.wires import plan_add_wire

    h = next(iter(project.harnesses.values()))
    c = sorted(h.connectors, key=lambda c: c.id)
    ops = plan_add_wire(project, h.id, c[0].id, c[0].pins[-1].id, c[1].id, c[1].pins[-1].id)
    apply_ops(project, ops)
    new = next(w for w in project.harnesses[h.id].wires if w.manual)
    apply_ops(project, plan_wire_edit(project, [new.id], {"gauge_awg": 20}))
    got = find_wire(project, new.id)[1]
    assert got.gauge_awg == 20 and got.locked and got.overrides == {}


def test_an_edit_with_a_reason_records_it_for_each_value_set(project):
    w = a_wire(project)
    History(project).execute(
        "x", plan_wire_edit(project, [w.id], {"gauge_awg": 20, "colour": "pink"}, reason=" ECR-7 ")
    )
    got = find_wire(project, w.id)[1]
    assert got.locked and got.gauge_awg == 20 and got.colour == "pink"
    assert got.overrides == {"gauge_awg": "ECR-7", "colour": "ECR-7"}


def test_a_second_override_keeps_the_first_with_its_own_reason(project):
    w = a_wire(project)
    apply_ops(project, plan_override(project, w.id, "gauge_awg", 20, "first reason"))
    apply_ops(project, plan_override(project, w.id, "colour", "pink", "second reason"))
    assert find_wire(project, w.id)[1].overrides == {
        "gauge_awg": "first reason",
        "colour": "second reason",
    }


def test_plan_override_needs_a_reason_and_a_known_field(project):
    w = a_wire(project)
    with pytest.raises(EditError, match="needs a reason"):
        plan_override(project, w.id, "gauge_awg", 20, "")
    with pytest.raises(EditError, match="Only gauge_awg"):
        plan_override(project, w.id, "note", "x", "why")


def test_an_override_with_the_same_value_and_reason_changes_nothing(project):
    w = a_wire(project)
    apply_ops(project, plan_override(project, w.id, "gauge_awg", 20, "why"))
    assert plan_override(project, w.id, "gauge_awg", 20, "why") == []


def test_reset_gives_the_wire_back_and_forgets_the_overrides(project):
    w = a_wire(project)
    apply_ops(project, plan_override(project, w.id, "gauge_awg", 20, "why"))
    apply_ops(project, plan_wire_reset(project, [w.id]))
    got = find_wire(project, w.id)[1]
    assert not got.locked and got.overrides == {}


def test_clearing_one_override_clears_the_value_and_unlocks_the_last_one(project):
    w = a_wire(project)
    apply_ops(project, plan_override(project, w.id, "gauge_awg", 20, "one"))
    apply_ops(project, plan_override(project, w.id, "colour", "pink", "two"))
    apply_ops(project, plan_clear_override(project, w.id, "gauge_awg"))
    got = find_wire(project, w.id)[1]
    assert got.gauge_awg is None and got.locked and got.overrides == {"colour": "two"}
    apply_ops(project, plan_clear_override(project, w.id, "colour"))
    got = find_wire(project, w.id)[1]
    assert not got.locked and got.overrides == {}
    with pytest.raises(EditError, match="not overridden"):
        plan_clear_override(project, w.id, "colour")


def test_a_wire_locked_before_reasons_were_kept_keeps_what_it_kept_and_says_so(project):
    w = a_wire(project)
    h = find_wire(project, w.id)[0]
    old = evolve(w, locked=True)  # the form of a project from before: locked, no reason
    apply_ops(
        project, [Put("harnesses", evolve(h, wires=[old if x.id == w.id else x for x in h.wires]))]
    )
    apply_ops(project, plan_override(project, w.id, "colour", "pink", "now with a reason"))
    got = find_wire(project, w.id)[1]
    assert got.overrides["colour"] == "now with a reason"
    for f in ("gauge_awg", "part_id", "length_m"):
        if getattr(w, f) is not None:
            assert got.overrides[f] == LEGACY_REASON


def test_a_released_harness_cannot_be_overridden(project):
    w = a_wire(project)
    h = find_wire(project, w.id)[0]
    apply_ops(project, [Put("harnesses", evolve(h, status="released"))])
    with pytest.raises(EditError, match="released"):
        plan_override(project, w.id, "gauge_awg", 20, "why")


# ---- regeneration and the explanation ----------------------------------------------------------


def test_an_override_survives_regeneration_and_the_other_values_follow_the_design(project):
    w = a_wire(project)
    generated = w
    apply_ops(project, plan_override(project, w.id, "gauge_awg", 22, "ECR-9: heater load added"))
    # the colour is not overridden: it is the design's, and stays so when generation runs again
    regenerate(project)
    generate_project(project)
    got = find_wire(project, w.id)[1]
    assert got.gauge_awg == 22 and got.overrides == {"gauge_awg": "ECR-9: heater load added"}
    assert got.locked and got.part_id == generated.part_id and got.length_m == generated.length_m


def test_the_values_that_are_not_overridden_follow_the_design_again(project):
    w = a_wire(project)
    h = find_wire(project, w.id)[0]
    apply_ops(project, plan_override(project, w.id, "colour", "pink", "program colour code"))
    moved = evolve(find_wire(project, w.id)[1], gauge_awg=30)  # something stale in a free value
    apply_ops(
        project,
        [
            Put(
                "harnesses",
                evolve(
                    h,
                    wires=[moved if x.id == w.id else x for x in find_wire(project, w.id)[0].wires],
                ),
            )
        ],
    )
    generate_project(project)
    got = find_wire(project, w.id)[1]
    assert got.colour == "pink"
    assert got.gauge_awg != 30  # sized again by the design


@pytest.fixture
def flatsat(tmp_path):
    templates.create_project(tmp_path / "p", "flatsat")
    return tmp_path / "p", load_project(tmp_path / "p").project


def test_explain_wire_with_an_override(flatsat):
    _folder, p = flatsat
    h = next(iter(p.harnesses.values()))
    w = h.wires[0]
    designed = w.gauge_awg
    apply_ops(p, plan_override(p, w.id, "gauge_awg", 26, "Smaller connector, see ECR-12"))
    found = explain_wire(p, w.id)
    assert found[0].id == "wire-override"
    text = render(found[0])
    assert "Overridden by the engineer" in found[0].quantity
    assert "Smaller connector, see ECR-12" in text and "overridden by the engineer" in text
    assert f"Gauge the design would give = {designed} AWG" in text
    assert "Gauge set by the engineer = 26 AWG" in text
    # the consequence: actual, limit and margin of the check on the set value
    limit = next(d for d in found if d.id == "wire-current-limit")
    assert limit.check is not None and not limit.check.passes
    assert limit.check.margin < 0 and "over the limit by" in limit.check.text
    assert found[0].check is not None and not found[0].check.passes
    assert "Consequences" in found[0].reference and "over the limit" in found[0].reference


def test_explain_wire_without_an_override_is_unchanged(flatsat):
    _folder, p = flatsat
    w = next(iter(p.harnesses.values())).wires[0]
    assert [d.id for d in explain_wire(p, w.id)] == [
        "wire-length",
        "wire-current-limit",
        "wire-voltage-drop",
        "wire-mass",
    ]


def test_the_length_derivation_names_the_override(flatsat):
    _folder, p = flatsat
    w = next(iter(p.harnesses.values())).wires[0]
    apply_ops(p, plan_override(p, w.id, "length_m", 0.5, "mock-up measurement"))
    length = next(d for d in explain_wire(p, w.id) if d.id == "wire-length")
    assert "overridden by the engineer (reason: mock-up measurement)" in render(length)


# ---- old projects open and save unchanged ------------------------------------------------------


def lock_without_reason(p, wire_id: str) -> None:
    h = find_wire(p, wire_id)[0]
    wires = [evolve(w, locked=True) if w.id == wire_id else w for w in h.wires]
    apply_ops(p, [Put("harnesses", evolve(h, wires=wires))])


def folder_bytes(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".bak" not in p.name and not p.name.startswith(".")
    }


def test_a_project_with_locked_wires_and_no_reasons_opens_and_saves_byte_for_byte(tmp_path):
    folder = tmp_path / "p"
    p = templates.create_project(folder, "flatsat")
    for h in p.harnesses.values():
        lock_without_reason(p, h.wires[0].id)
    save_project(p, folder)
    before = folder_bytes(folder)
    assert all(b"overrides" not in v for k, v in before.items() if "harnesses" in k)
    assert "journal.json" not in before
    loaded = load_project(folder).project
    assert all(not w.overrides for h in loaded.harnesses.values() for w in h.wires)
    assert any(w.locked for h in loaded.harnesses.values() for w in h.wires)
    save_project(loaded, folder)
    assert folder_bytes(folder) == before
    assert json.loads(before["project.json"])["schema_version"] == 1  # no migration is needed


def test_a_locked_wire_with_no_reason_is_still_kept_whole_by_generation(project):
    w = a_wire(project)
    lock_without_reason(project, w.id)
    kept = find_wire(project, w.id)[1]
    generate_project(project)
    assert find_wire(project, w.id)[1] == kept


def test_the_files_of_a_project_hold_no_name_and_no_time_for_an_override(tmp_path):
    folder = tmp_path / "p"
    p = templates.create_project(folder, "flatsat", journal=True)
    w = next(iter(p.harnesses.values())).wires[0]
    History(p).execute("x", plan_override(p, w.id, "gauge_awg", 20, "ECR-7"))
    save_project(p, folder)
    design = [v for k, v in folder_bytes(folder).items() if k != "journal.json"]
    blob = b"\n".join(design).decode("utf-8")
    assert "ECR-7" in blob
    for e in p.journal:
        assert e.when not in blob and (e.author not in blob or e.author == "unknown")


# ---- the command line --------------------------------------------------------------------------


def run(*args) -> int:
    return main([str(a) for a in args])


def test_cli_override_without_a_reason_is_refused_and_changes_nothing(flatsat, capsys):
    folder, p = flatsat
    wid = next(iter(p.harnesses.values())).wires[0].id
    before = folder_bytes(folder)
    assert run("override", folder, wid, "gauge_awg", "20") == 1
    assert "needs a reason" in capsys.readouterr().err
    assert run("override", folder, wid, "gauge_awg", "20", "--reason", "  ") == 1
    assert folder_bytes(folder) == before


def test_cli_override_with_a_reason_sets_it_keeps_it_and_explains_the_consequences(flatsat, capsys):
    folder, p = flatsat
    wid = next(iter(p.harnesses.values())).wires[0].id
    assert run("override", folder, wid, "gauge_awg", "26", "--reason", "Smaller connector") == 0
    out = capsys.readouterr().out
    assert "Smaller connector" in out and "Gauge the design would give" in out
    assert "over the limit" in out
    got = find_wire(load_project(folder).project, wid)[1]
    assert got.gauge_awg == 26 and got.overrides == {"gauge_awg": "Smaller connector"}
    assert run("generate", folder) == 0
    again = find_wire(load_project(folder).project, wid)[1]
    assert again.gauge_awg == 26 and again.overrides == got.overrides


def test_cli_override_clear_gives_the_field_back(flatsat, capsys):
    folder, p = flatsat
    wid = next(iter(p.harnesses.values())).wires[0].id
    designed = find_wire(p, wid)[1].gauge_awg
    assert run("override", folder, wid, "gauge_awg", "26", "--reason", "x y z") == 0
    assert run("override", folder, wid, "--clear", "gauge_awg") == 0
    assert "run `generate`" in capsys.readouterr().out
    assert run("generate", folder) == 0
    got = find_wire(load_project(folder).project, wid)[1]
    assert got.gauge_awg == designed and not got.locked and got.overrides == {}


def test_cli_override_lists_what_a_wire_has(flatsat, capsys):
    folder, p = flatsat
    wid = next(iter(p.harnesses.values())).wires[0].id
    assert run("override", folder, wid) == 0
    assert "has no override" in capsys.readouterr().out
    assert run("override", folder, wid, "colour", "pink", "--reason", "colour code") == 0
    capsys.readouterr()
    assert run("override", folder, wid) == 0
    assert "colour code" in capsys.readouterr().out


def test_the_derivations_export_carries_the_overrides(flatsat, tmp_path):
    folder, p = flatsat
    wid = next(iter(p.harnesses.values())).wires[0].id
    assert run("override", folder, wid, "colour", "pink", "--reason", "colour code") == 0
    out = tmp_path / "d"
    assert run("explain", folder, "--all", "--out", out) == 0
    data = json.loads((out / "derivations.json").read_text(encoding="utf-8"))
    mine = [d for d in data["derivations"] if d["id"] == "wire-override"]
    assert len(mine) == 1 and mine[0]["subject"] == f"Wire {wid}"
    assert any("colour code" in i["source"] for i in mine[0]["inputs"])
    assert "wire-override" in (out / "derivations.csv").read_text(encoding="utf-8")
    assert all(
        d["id"] != "wire-override" for d in data["derivations"] if d["subject"] != f"Wire {wid}"
    )


# ---- the outputs flag overrides, and only when there are some ----------------------------------


def test_the_outputs_show_overrides_only_when_a_project_has_them(flatsat, tmp_path):
    from harness_design_studio.core.outputs.build import build_outputs
    from harness_design_studio.core.outputs.verify import verify_outputs

    _folder, p = flatsat
    plain = build_outputs(p, drawings=False)
    h = next(iter(p.harnesses.values()))
    assert b"Overrides" not in plain.files[f"harnesses/{h.id}/wirelist.csv"]
    apply_ops(p, plan_override(p, h.wires[0].id, "colour", "pink", "colour code"))
    marked = build_outputs(p, drawings=False)
    wl = marked.files[f"harnesses/{h.id}/wirelist.csv"].decode()
    assert wl.splitlines()[1].endswith(",Overrides")
    assert "colour: colour code" in wl
    other = next(x for x in p.harnesses.values() if x.id != h.id)
    assert b"colour code" not in marked.files[f"harnesses/{other.id}/wirelist.csv"]
    report = verify_outputs(p, marked.files)
    assert report.ok, [i.message for i in report.issues]
    # a harness with no override keeps its cut list as before (the column is per harness)
    from io import BytesIO

    from openpyxl import load_workbook

    from harness_design_studio.core.outputs.buildsheet import FILE_SUFFIX

    book = load_workbook(BytesIO(marked.files[f"harnesses/{other.id}/{other.id}{FILE_SUFFIX}"]))
    assert next(book["Cut list"].iter_rows(values_only=True))[-1] == "Note"


def test_the_build_workbook_has_the_override_column_and_section(flatsat):
    from io import BytesIO

    from openpyxl import load_workbook

    from harness_design_studio.core.outputs.build import build_outputs
    from harness_design_studio.core.outputs.buildsheet import FILE_SUFFIX

    _folder, p = flatsat
    h = next(iter(p.harnesses.values()))
    apply_ops(p, plan_override(p, h.wires[0].id, "colour", "pink", "colour code"))
    data = build_outputs(p, drawings=False).files[f"harnesses/{h.id}/{h.id}{FILE_SUFFIX}"]
    wb = load_workbook(BytesIO(data))
    cut = [[c.value for c in row] for row in wb["Cut list"].iter_rows()]
    assert cut[0][-1] == "Override"
    assert any(row[-1] and "colour code" in str(row[-1]) for row in cut[1:])
    start = " ".join(str(c.value) for row in wb["Start here"].iter_rows() for c in row if c.value)
    assert "Overrides and deviations" in start and "colour code" in start


def test_the_drawing_notes_the_overrides(flatsat):
    from harness_design_studio.core.outputs.drawing import _extras

    _folder, p = flatsat
    h = next(iter(p.harnesses.values()))
    assert not any("OVERRIDE" in line for line in _extras(h, p))
    apply_ops(p, plan_override(p, h.wires[0].id, "colour", "pink", "colour code"))
    h = p.harnesses[h.id]
    assert any("OVERRIDE" in line and "colour code" in line for line in _extras(h, p))


def test_a_released_harness_shows_its_overrides_in_the_release_record(flatsat):
    from harness_design_studio.core.deviations import release_note

    _folder, p = flatsat
    h = next(iter(p.harnesses.values()))
    assert release_note(p, h) == ""
    apply_ops(p, plan_override(p, h.wires[0].id, "colour", "pink", "colour code"))
    note = release_note(p, p.harnesses[h.id])
    assert note.startswith(" [Released with 1 overridden value(s)") and "colour code" in note
