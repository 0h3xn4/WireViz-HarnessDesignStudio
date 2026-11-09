# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type,attr-defined,index,union-attr"
"""REQ-OUT-10 and REQ-OUT-11: what the written outputs and the independent verifier do with a loose
cable end (M4a and M4b of the 2.0 programme, D-201).

REQ-OUT-10 (M4a): the build workbook of a harness that has one gets a ninth check, *Ends not
decided*, which always blocks *Ready to build*, in the generator and again in the independent
verifier (`core/outputs/verify.py`); a harness without one has the eight checks and the same sheet as
before. The part `TBD-CONNECTOR` is not counted among the parts that are not approved.

REQ-OUT-11 (M4b): every written output names the end as an open end, with the words of D-201
decision 2: the part `TBD-CONNECTOR (loose end)`, the mate `open end`, the label `W009-P2 open end`,
one BOM line `(open end)` (approval *to fill in*, the number of ends) and no `TBD-CONNECTOR` line,
the mass never counted and reported as missing, the tests at the end `(open end)` and *test when the
end is decided*, the as-built sheet without a lot for the placeholder part, the drawing with a dashed
open end, the Connectors sheet *open end, to fill in*, `explain` and the change reports. The
verifier words all of it again, and the golden set `tests/fixtures/outputs/loose_ends*` holds it."""

import io
from pathlib import Path

import pytest
from openpyxl import load_workbook

from harness_design_studio.core import drc
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.manual_harness import TBD_PART_ID, plan_resolve_loose_end
from harness_design_studio.core.outputs import buildsheet
from harness_design_studio.core.outputs.build import build_outputs, write_outputs
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.verify import verify_project
from tests.helpers import copy_project
from tests.loose_support import generated_loose


@pytest.fixture(scope="module")
def loose_root(tmp_path_factory) -> Path:
    return generated_loose(tmp_path_factory.mktemp("loose") / "p")


def start_here(data: bytes) -> dict[str, str]:
    """The *Start here* sheet as label -> the number or answer next to it."""
    wb = load_workbook(io.BytesIO(data), data_only=True)
    rows = [list(r) for r in wb["Start here"].iter_rows(values_only=True)]
    return {str(r[0]): str(r[1]) for r in rows if r and r[0] is not None and len(r) > 1}


def verifier_errors(p, files=None):
    report = verify_outputs(p, files if files is not None else build_outputs(p).files)
    return [e.message for e in report.issues if e.severity == "error"]


def test_the_independent_verifier_passes_every_written_output_of_the_project(loose_root):
    p = load_project(loose_root).project
    assert verifier_errors(p) == []
    assert [e for e in verify_project(p).issues if e.severity == "error"] == []


def test_a_complete_harness_with_a_loose_end_is_not_ready_to_build(loose_root):
    p = load_project(loose_root).project
    checks = {c.label: c for c in buildsheet.readiness(p, p.harnesses["W013"])}
    assert checks["Wires without a length"].open == 0  # every wire is complete ...
    assert TBD_PART_ID not in checks["Parts that are not approved"].items  # not counted twice
    ninth = checks["Ends not decided"]
    assert (ninth.open, ninth.blocking, ninth.status, ninth.items) == (1, True, "TO FIX", ("W013-P2",))  # fmt: skip
    assert "Plug the open end into a device" in ninth.todo
    assert len(checks) == 9
    plain = {c.label for c in buildsheet.readiness(p, p.harnesses["W001"])}
    assert "Ends not decided" not in plain and len(plain) == 8


def test_the_ninth_check_blocks_even_when_the_setting_blocks_nothing(loose_root, tmp_path):
    from harness_design_studio.core.model import ConfigFile

    p = load_project(copy_project(loose_root, tmp_path / "p")).project
    p.config["model"] = ConfigFile(
        name="model", placeholder=False, values={"readiness_blocking": []}
    )
    checks = buildsheet.readiness(p, p.harnesses["W013"])
    assert [c.status for c in checks if c.label == "Ends not decided"] == ["TO FIX"]
    assert all(c.blocking is False for c in checks if c.label != "Ends not decided")
    assert verifier_errors(p) == []  # the verifier agrees: still "Ready to build: no"


def test_the_start_here_sheet_says_no_until_the_end_is_decided(loose_root, tmp_path):
    p = load_project(copy_project(loose_root, tmp_path / "p")).project
    before = start_here(build_outputs(p).files["harnesses/W013/W013_build.xlsx"])
    assert before["Ready to build"].startswith("no") and before["Ends not decided"] == "1"
    apply_ops(p, plan_resolve_loose_end(p, "W013", "W013-P2", "EX-MICROD-9-M"))
    after = start_here(build_outputs(p).files["harnesses/W013/W013_build.xlsx"])
    assert "Ends not decided" not in after
    assert verifier_errors(p) == []


def test_the_verifier_refuses_a_workbook_that_says_yes_to_a_loose_end(loose_root, monkeypatch):
    """The generator and the verifier are two implementations: when the generator stops writing the
    ninth check, the verifier names the workbook."""
    p = load_project(loose_root).project
    real = buildsheet.readiness
    monkeypatch.setattr(
        buildsheet,
        "readiness",
        lambda pr, h: [c for c in real(pr, h) if c.label != "Ends not decided"],
    )
    files = build_outputs(p).files
    monkeypatch.undo()
    errors = verifier_errors(p, files)
    assert any("Start here" in e and "Ends not decided" in e for e in errors) or any(
        "wrong 'Ready to build' answer" in e for e in errors
    )


def test_a_project_with_no_loose_end_writes_the_same_start_here_sheet_as_before(tmp_path):
    """Byte-identity is held by the output baseline (`tools.output_hashes`), run before every push;
    here the point is that the ninth check is absent."""
    from harness_design_studio.core.samples import sat15_full

    p = sat15_full()
    for h in p.harnesses.values():
        assert "Ends not decided" not in {c.label for c in buildsheet.readiness(p, h)}
    write_outputs(p, tmp_path / "o")
    assert verifier_errors(p) == []


def test_the_design_rule_counts_only_the_ends_in_use(loose_root):
    p = load_project(loose_root).project
    hit = next(f for f in drc.run(p) if f.rule == "part-unapproved" and "TBD" in f.object_id)
    assert hit.title.startswith("5 cable end(s) have no connector chosen yet (loose end)")


# ---- M4b: the words of a loose end in every written output (REQ-OUT-11) -------------------------


def _text(files, rel):
    return files[rel].decode()


@pytest.fixture(scope="module")
def loose_files(loose_root):
    p = load_project(loose_root).project
    return p, build_outputs(p).files


def test_the_pinout_table_names_the_part_and_the_mate_of_an_open_end(loose_files):
    _p, files = loose_files
    text = _text(files, "harnesses/W009/pinouts.csv")
    assert "W009-P2,loose,open end,TBD-CONNECTOR (loose end),1,PWR,,W009-001,no" in text
    assert "W009-P1,cable,PCDU1-J10,EX-MICROD-9-M,1,PWR" in text  # the plugged end as before
    assert ",TBD-CONNECTOR," not in text and "loose,," not in text


def test_the_label_of_an_open_end_says_open_end(loose_files):
    _p, files = loose_files
    text = _text(files, "harnesses/W009/labels.csv")
    assert "W009-P2,connector,W009-P2 open end,1" in text
    assert "mates -" not in text
    assert "W009-001-A,wire,W009-001 PWR to W009-P2.1,1" in text  # wire labels name the pin


def test_the_label_formats_word_an_open_end_too(loose_root, tmp_path):
    from harness_design_studio.core.model import ConfigFile
    from harness_design_studio.core.outputs import tables

    p = load_project(loose_root).project
    c = next(x for x in p.harnesses["W009"].connectors if x.id == "W009-P2")
    for fmt, extra, want in (
        ("compact", {}, "W009-P2 open end"),
        ("descriptive", {}, "W009-P2 open end"),
        ("custom", {"label_connector_template": "{connector} to {mates}"}, "W009-P2 to open end"),
    ):
        p.config["model"] = ConfigFile(
            name="model", placeholder=False, values={"label_format": fmt, **extra}
        )
        assert tables.connector_label_text(p, c) == want


def test_the_bom_counts_the_ends_on_one_open_end_line(loose_files):
    _p, files = loose_files
    harness = _text(files, "harnesses/W011/bom.csv")
    assert (
        "(open end),connector,,,Connector not chosen yet (loose end),to fill in,2,ea,,W011"
        in harness
    )
    system = _text(files, "system/bom.csv")
    assert (
        "(open end),connector,,,Connector not chosen yet (loose end),to fill in,5,ea,,W009;W011;W012;W013"
        in system
    )
    for text in (harness, system, _text(files, "harnesses/W009/bom.csv")):
        assert TBD_PART_ID + "," not in text  # no line for the placeholder part
    assert "(open end)" not in _text(files, "harnesses/W010/bom.csv")  # plugged: an ordinary BOM


def test_the_mass_of_an_open_end_is_never_counted(loose_root, tmp_path):
    """Even a mass a person gave the placeholder part is not a mass of the end: the mass stays what
    is known and the end is listed as missing data, in the generator and in the verifier."""
    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import evolve
    from harness_design_studio.core.outputs import tables

    p = load_project(copy_project(loose_root, tmp_path / "p")).project
    before = tables.mass_length(p, [p.harnesses["W013"]])[1]
    apply_ops(p, [Put("parts", evolve(p.parts[TBD_PART_ID], mass_g=50.0))])
    row = tables.mass_length(p, [p.harnesses["W013"]])[1]
    assert row == before
    assert row[5] == "16" and row[8] == "no"
    assert row[9] == "mass of open end W013-P2 (no connector chosen yet)"
    assert verifier_errors(p) == []


def test_a_test_at_an_open_end_waits_for_the_end(loose_files):
    _p, files = loose_files
    text = _text(files, "harnesses/W009/tests.csv")
    assert (
        "T001,continuity,W009-P1.1,W009-P2.1 (open end),test when the end is decided,1 ohm max,,W009-001"
        in text
    )
    assert "continuous" not in text  # nothing claims a connector that does not exist
    assert "T005,isolation,W009-P1.1,all other wires and shields,isolated," in text
    both = _text(files, "harnesses/W011/tests.csv")  # both ends loose: the isolation waits too
    assert "T004,isolation,W011-P1.1 (open end),all other wires and shields,test when the end is decided," in both  # fmt: skip
    assert "continuous" in _text(files, "harnesses/W010/tests.csv")


def test_the_wireviz_file_names_the_part_of_an_open_end(loose_files):
    _p, files = loose_files
    assert 'type: "TBD-CONNECTOR (loose end)"' in _text(files, "harnesses/W009/wireviz.yaml")


def test_the_drawing_shows_an_open_end(loose_files):
    _p, files = loose_files
    svg = _text(files, "harnesses/W009/drawing_A3_s1.svg")
    assert 'data-ref="part/W009-P2">TBD-CONNECTOR (loose end), 4-pin</text>' in svg
    assert 'data-ref="end/W009-P2">open end</text>' in svg
    assert "gender not set" not in svg  # the plugged end has a gender; the open end needs none
    assert 'stroke-dasharray="1.2 0.8"' in svg
    plugged = _text(files, "harnesses/W010/drawing_A3_s1.svg")
    assert "open end" not in plugged and 'data-ref="end/' not in plugged
    pdf = files["harnesses/W009/drawing_A3.pdf"]
    assert b"(open end) Tj" in pdf and b"(TBD-CONNECTOR \\(loose end\\), 4-pin) Tj" in pdf


def test_the_build_workbook_says_open_end_to_fill_in(loose_files):
    from harness_design_studio.core.outputs.verify import _xlsx_values

    _p, files = loose_files
    data = files["harnesses/W009/W009_build.xlsx"]
    sheets = _xlsx_values(data)
    heads = [row[0] for row in sheets["Connectors"] if row and "   ·   " in row[0]]
    assert heads == [
        "W009-P1   ·   EX-MICROD-9-M   ·   male   ·   mates with PCDU1-J10",
        "W009-P2   ·   TBD-CONNECTOR (loose end)   ·   open end, to fill in",
    ]
    parts = {row[0]: row for row in sheets["Parts"][1:]}
    assert parts["(open end)"][5:8] == ["to fill in", "1", "ea"] and TBD_PART_ID not in parts
    wb = load_workbook(io.BytesIO(data))
    cell = next(r[5] for r in wb["Parts"].iter_rows() if r[0].value == "(open end)")
    assert cell.fill.fgColor.rgb.endswith("FFE699")  # amber, like every value to fill in


def test_the_as_built_sheet_asks_no_lot_of_the_placeholder_part(loose_root, tmp_path):
    from harness_design_studio.core import asbuilt
    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import AsBuiltRecord
    from harness_design_studio.core.model.asbuilt import record_id

    p = load_project(copy_project(loose_root, tmp_path / "p")).project
    rows = asbuilt.template_rows(p, "W009")
    assert not any(r[0] == "part" and r[2] == TBD_PART_ID for r in rows)
    assert ["connector", "W009", "W009-P2", "open end: no connector chosen yet"] in [r[:4] for r in rows]  # fmt: skip
    assert ["test", "W009", "T001", "W009-P1.1 to W009-P2.1 (open end)"] in [r[:4] for r in rows]
    rec = AsBuiltRecord(id=record_id("harness", "W009", "W009"), kind="harness", harness_id="W009", subject="W009", built_by="AB")  # fmt: skip
    apply_ops(p, [Put("asbuilt", rec)])
    report = asbuilt.report_rows(p, "W009")
    assert not any(TBD_PART_ID in cell for row in report for cell in row)
    assert verifier_errors(p) == []


def test_explain_says_open_end(loose_root):
    from harness_design_studio.core.derive import explain_object

    p = load_project(loose_root).project
    found = {d.quantity: d for d in explain_object(p, "W009-P2")}
    choice = found["Choice of connector"]
    assert choice.text == "Open end: no device connector and no part chosen yet"
    assert "mates with None" not in str(choice) and "connector None" not in str(choice)
    label = found["Connector label"]
    assert label.text == "W009-P2 open end" and "mates -" not in str(label)
    for name in (TBD_PART_ID, "(open end)"):  # the placeholder part leads to the line of the ends
        (bom,) = explain_object(p, name)
        assert bom.subject == "Part (open end)" and bom.value == 5
        assert "no connector part is chosen yet" in " ".join(bom.missing)
    mass = next(d for d in explain_object(p, "W009") if d.id == "harness-mass")
    assert any("open end" in i.source for i in mass.inputs)


def test_the_change_reports_name_a_loose_end(loose_root, tmp_path):
    from harness_design_studio.core.manual_harness import plan_unplug
    from harness_design_studio.core.vcs.diff import diff_projects, render_markdown
    from harness_design_studio.core.vcs.timeline import diff_rows

    before = load_project(loose_root).project
    after = load_project(copy_project(loose_root, tmp_path / "p")).project
    apply_ops(after, plan_unplug(after, "W010", "W010-P2"))
    diff = diff_projects(before, after)
    text = render_markdown("unplug", diff)
    assert "- Loose end `W010-P2`" in text and "Cable connector `W010-P2`" not in text
    assert "- Cable connector `W010-P1`" not in text  # untouched
    assert {r.kind_name for r in diff_rows(diff) if r.id == "W010-P2"} == {"Loose end"}
    back = render_markdown("plug", diff_projects(after, before))
    assert "- Cable connector `W010-P2`" in back  # plugged again: a cable connector


def test_the_export_keeps_the_data_of_an_open_end(loose_files):
    """`system/export.json` is data: the role and the placeholder part as stored, no words added."""
    import json

    _p, files = loose_files
    doc = json.loads(files["system/export.json"])
    end = next(
        c
        for h in doc["harnesses"]
        if h["id"] == "W009"
        for c in h["connectors"]
        if c["id"] == "W009-P2"
    )
    assert (end["role"], end["part_id"], end.get("mates_with")) == ("loose", TBD_PART_ID, None)
    assert "open end" not in files["system/export.json"].decode()


@pytest.mark.parametrize(
    ("target", "expect"),
    [
        ("part_text", "The pinout table of W009"),
        ("mates_text", "The pinout table of W009"),
    ],
)
def test_the_verifier_refuses_a_pinout_that_drops_the_words(
    loose_root, monkeypatch, target, expect
):
    """The generator and the verifier are two implementations: a generator that writes an open end
    as an ordinary connector is caught."""
    from harness_design_studio.core.outputs import tables

    p = load_project(loose_root).project
    plain = {"part_text": lambda c: c.part_id, "mates_text": lambda c: c.mates_with or ""}
    monkeypatch.setattr(tables, target, plain[target])
    files = build_outputs(p).files
    monkeypatch.undo()
    assert any(expect in e for e in verifier_errors(p, files))


def test_the_verifier_refuses_outputs_that_count_or_name_an_open_end_wrongly(loose_files):
    p, files = loose_files
    bad = dict(files)

    def swap(rel, old, new):
        data = bad[rel]
        assert old.encode() in data, (rel, old)
        bad[rel] = data.replace(old.encode(), new.encode())

    swap("system/bom.csv", "to fill in,5,ea", "to fill in,4,ea")
    swap("harnesses/W009/labels.csv", "W009-P2 open end", "W009-P2 mates -")
    swap("harnesses/W009/tests.csv", "test when the end is decided", "continuous")
    swap("harnesses/W009/mass_length.csv", "mass of open end W009-P2 (no connector chosen yet)", "mass of connector part TBD-CONNECTOR")  # fmt: skip
    swap("harnesses/W009/wireviz.yaml", '"TBD-CONNECTOR (loose end)"', '"TBD-CONNECTOR"')
    swap("harnesses/W009/drawing_A3_s1.svg", ">open end</text>", "></text>")
    errors = verifier_errors(p, bad)
    for what in (
        "The system BOM", "The labels of W009", "The test list of W009",
        "The mass and length of W009", "The WireViz file of W009", "The drawing of W009",
    ):  # fmt: skip
        assert any(what in e for e in errors), what


def test_the_verifier_refuses_a_workbook_that_shows_an_open_end_as_a_connector(
    loose_root, monkeypatch
):
    from harness_design_studio.core.outputs import tables

    p = load_project(loose_root).project
    monkeypatch.setattr(tables, "is_open_end", lambda c: False)
    files = build_outputs(p).files
    monkeypatch.undo()
    errors = verifier_errors(p, files)
    assert any("(Connectors) shows W009-P2 wrongly as a loose end" in e for e in errors)


# ---- the golden set -----------------------------------------------------------------------------


def test_the_outputs_of_the_loose_end_project_match_the_golden_set(loose_files):
    """`python -m tools.gen_output_goldens` writes it; renew it only on purpose and review it."""
    import json

    from tests.helpers import FIXTURES, output_digests
    from tests.loose_support import golden_text_files

    _p, files = loose_files
    root = FIXTURES / "outputs"
    golden = json.loads((root / "loose_ends.json").read_text(encoding="utf-8"))
    got = output_digests(files)
    assert sorted(got) == sorted(golden)
    assert [k for k in got if got[k] != golden[k]] == []
    text = golden_text_files(files)
    assert len(text) > 30
    for rel, data in text.items():
        assert (root / "loose_ends" / rel).read_bytes() == data, rel
