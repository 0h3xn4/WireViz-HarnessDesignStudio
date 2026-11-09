# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type,attr-defined,index,union-attr"
"""REQ-OUT-10: what the written outputs and the independent verifier do with a loose cable end
(M4a of the 2.0 programme, D-201). The build workbook of a harness that has one gets a ninth check,
*Ends not decided*, which always blocks *Ready to build*, in the generator and again in the
independent verifier (`core/outputs/verify.py`); a harness without one has the eight checks and the
same sheet as before. The part `TBD-CONNECTOR` is not counted among the parts that are not approved.

What is NOT done here, and is the work of M4b: the words of a loose end in the pinout and connector
tables, the connector labels, the bill of materials, the mass and test tables, the as-built sheet,
the drawing and the Connectors sheet of the build workbook. Until then those outputs list the end as
an ordinary connector with the part `TBD-CONNECTOR`; the tests below pin that state down, so M4b has
to change them on purpose."""

import io
from pathlib import Path

import pytest
from openpyxl import load_workbook

from harness_design_studio.core import drc
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.manual_harness import TBD_PART_ID, plan_resolve_loose_end
from harness_design_studio.core.outputs import buildsheet
from harness_design_studio.core.outputs.build import build_outputs, write_outputs
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.verify import verify_project
from tests.helpers import copy_project
from tests.loose_support import build_loose


@pytest.fixture(scope="module")
def loose_root(tmp_path_factory) -> Path:
    root = build_loose(tmp_path_factory.mktemp("loose") / "p")
    p = load_project(root).project
    generate_project(p)
    save_project(p, root)
    return root


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


def test_the_outputs_of_a_loose_end_are_unchanged_until_m4b(loose_root):
    """Pinned on purpose: the pinout and BOM list the end as an ordinary connector with the part
    TBD-CONNECTOR. M4b changes the words (D-201); this test changes with it."""
    p = load_project(loose_root).project
    files = build_outputs(p).files
    assert "W009-P2,loose,,TBD-CONNECTOR,1,PWR" in files["harnesses/W009/pinouts.csv"].decode()
    assert "TBD-CONNECTOR" in files["harnesses/W009/bom.csv"].decode()


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
