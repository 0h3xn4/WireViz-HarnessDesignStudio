# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg,attr-defined"
"""As-built length tolerance (owner decision 10). The two optional settings `asbuilt_cut_tolerance_mm`
and `asbuilt_strip_tolerance_mm` of `config/generation.json` default to not set, which is what the
tool did before: no tolerance, every difference listed. With one set, a length within it is *within
limit* and a longer or shorter one is *out of limit*, with the margin, in the report, the command and
`explain` (assumption A-ASBUILT-TOLERANCE). Numbers worked out by hand on W001-001 of the flatsat
example, whose designed length is 3.45 m."""

import copy
import json
from pathlib import Path

import pytest

from harness_design_studio import api
from harness_design_studio.cli.jsonout import SHAPES
from harness_design_studio.cli.main import main
from harness_design_studio.core import asbuilt, configcheck, settings, templates
from harness_design_studio.core.assumptions import ASSUMPTIONS
from harness_design_studio.core.derive import explain_object
from harness_design_studio.core.generation_status import input_hash
from harness_design_studio.core.model import ConfigFile, Project, evolve
from tests.test_s9_asbuilt import line, record

CUT, STRIP = "asbuilt_cut_tolerance_mm", "asbuilt_strip_tolerance_mm"


def with_tolerance(project: Project, **values: object) -> Project:
    p = copy.deepcopy(project)
    g = p.config["generation"]
    p.config["generation"] = ConfigFile(
        name="generation", placeholder=g.placeholder, values={**g.values, **values}
    )
    return p


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Project:
    """flatsat with a cut length of 3.46 m (+10 mm) for W001-001 and 3.50 m (+50 mm) for W001-002
    (3.45 m is designed for both), 3.95 m for W001-003 (as designed), and strip A of 6.5 mm
    recorded for W001-001 against a designed 6 mm."""
    p = templates.create_project(tmp_path_factory.mktemp("tol") / "flat", "flatsat")
    h = p.harnesses["W001"]
    assert [round(w.length_m, 9) for w in h.wires if w.id in ("W001-001", "W001-002")] == [3.45, 3.45]  # fmt: skip
    p.harnesses["W001"] = evolve(
        h, wires=[evolve(w, strip_a_mm=6.0) if w.id == "W001-001" else w for w in h.wires]
    )
    record(p, {
        ("wire", "W001-001"): {"Cut length (m)": "3.46", "Strip A (mm)": "6.5"},
        ("wire", "W001-002"): {"Cut length (m)": "3.50"},
        ("wire", "W001-003"): {"Cut length (m)": "3.95"},
    })  # fmt: skip
    return p


# ---- not set: exactly what it was ---------------------------------------------------------------


def test_the_settings_are_registered_with_no_default_and_not_set_in_a_new_project(built) -> None:
    for key in (CUT, STRIP):
        s = settings.setting("generation", key)
        assert s is not None and s.default is None and s.unit == "mm" and s.kind == "number"
        assert s.assumption == "A-ASBUILT-TOLERANCE" and s.range == "0 or more"
        assert settings.effective(built, "generation", key).origin == "unset"
        assert key not in built.config["generation"].values
    assert ASSUMPTIONS["A-ASBUILT-TOLERANCE"].kind == "setting"


def test_without_a_tolerance_a_difference_is_listed_and_none_is_applied(built) -> None:
    ln = line(built, "wire", "W001-001", "cut length (m)")
    assert ln.status == asbuilt.DIFFERS and ln.margin == pytest.approx(0.01)
    assert ln.text == "3.46 m was built, 3.45 m is designed (+10 mm); no tolerance applied"
    far = line(built, "wire", "W001-002", "cut length (m)")
    assert far.status == asbuilt.DIFFERS and "no tolerance applied" in far.text
    assert line(built, "wire", "W001-003", "cut length (m)").status == asbuilt.AS_DESIGNED
    assert line(built, "wire", "W001-001", "strip A (mm)").status == asbuilt.DIFFERS
    rep = asbuilt.asbuilt_report(built)
    assert rep.out_of_limit == 0 and rep.count(asbuilt.WITHIN) == 0


def test_without_a_tolerance_the_cut_length_derivation_is_the_old_one(built) -> None:
    found = [d for d in explain_object(built, "W001-001") if d.id == "asbuilt-result"]
    assert [d.subject for d in found] == ["Wire W001-001"]  # no derivation for a strip length
    d = found[0]
    assert d.check is None and d.assumptions == () and d.value == pytest.approx(0.01)
    assert [i.name for i in d.inputs] == ["Cut length", "Designed length"]
    assert d.reference == "The tool applies no tolerance to a length: any difference is listed."


def test_the_keys_are_not_read_by_generation_so_setting_one_leaves_the_plans_current(built) -> None:
    both = with_tolerance(built, **{CUT: 5, STRIP: 0.2})
    assert input_hash(both) == input_hash(built)


# ---- set: within, on the edge, out --------------------------------------------------------------


def test_a_difference_within_the_cut_tolerance_is_within_limit_with_its_margin(built) -> None:
    # 3.46 - 3.45 = 0.01 m = 10 mm from the design; tolerance 15 mm: room 5 mm = 0.005 m
    ln = line(with_tolerance(built, **{CUT: 15}), "wire", "W001-001", "cut length (m)")
    assert ln.status == asbuilt.WITHIN and (ln.actual, ln.designed) == (3.46, 3.45)
    assert ln.margin == pytest.approx(0.005, abs=1e-12) and ln.unit == "m"
    assert "tolerance +/-15 mm (config/generation.json: asbuilt_cut_tolerance_mm, A-ASBUILT-TOLERANCE)" in ln.text  # fmt: skip
    assert ln.text.endswith("within the tolerance")


def test_a_difference_equal_to_the_tolerance_is_within_and_a_longer_one_is_out(built) -> None:
    edge = line(with_tolerance(built, **{CUT: 10}), "wire", "W001-001", "cut length (m)")
    assert edge.status == asbuilt.WITHIN and edge.margin == 0.0
    # W001-002: 3.50 - 3.45 = 0.05 m = 50 mm; tolerance 10 mm: exceeded by 40 mm = 0.04 m
    out = line(with_tolerance(built, **{CUT: 10}), "wire", "W001-002", "cut length (m)")
    assert out.status == asbuilt.OUT and out.margin == pytest.approx(-0.04, abs=1e-12)
    assert out.text.endswith("OUT OF TOLERANCE by 40 mm") and "+50 mm" in out.text


def test_a_cut_too_short_counts_like_a_cut_too_long(built) -> None:
    p = with_tolerance(built, **{CUT: 20})
    record(p, {("wire", "W001-003"): {"Cut length (m)": "3.90"}})  # -50 mm
    ln = line(p, "wire", "W001-003", "cut length (m)")
    assert ln.status == asbuilt.OUT and ln.margin == pytest.approx(-0.03, abs=1e-12)
    assert "-50 mm" in ln.text and "by 30 mm" in ln.text


def test_a_cut_exactly_as_designed_stays_as_designed_and_a_tolerance_of_zero_is_exact(
    built,
) -> None:
    p = with_tolerance(built, **{CUT: 0})
    assert line(p, "wire", "W001-003", "cut length (m)").status == asbuilt.AS_DESIGNED
    assert line(p, "wire", "W001-001", "cut length (m)").status == asbuilt.OUT  # 10 mm over 0


def test_the_strip_tolerance_is_its_own_and_applies_to_both_ends(built) -> None:
    # strip A: 6.5 recorded, 6 designed: 0.5 mm. Tolerance 0.4: out by 0.1 mm; 0.5: within, margin 0
    out = line(with_tolerance(built, **{STRIP: 0.4}), "wire", "W001-001", "strip A (mm)")
    assert out.status == asbuilt.OUT and out.margin == pytest.approx(-0.1, abs=1e-12)
    assert out.unit == "mm" and out.text.endswith("OUT OF TOLERANCE by 0.1 mm")
    edge = line(with_tolerance(built, **{STRIP: 0.5}), "wire", "W001-001", "strip A (mm)")
    assert edge.status == asbuilt.WITHIN and edge.margin == 0.0
    # the cut tolerance does not judge a strip length, nor the strip tolerance a cut length
    assert line(with_tolerance(built, **{CUT: 100}), "wire", "W001-001", "strip A (mm)").status == asbuilt.DIFFERS  # fmt: skip
    assert line(with_tolerance(built, **{STRIP: 100}), "wire", "W001-001", "cut length (m)").status == asbuilt.DIFFERS  # fmt: skip


def test_the_report_counts_the_lengths_out_of_tolerance_with_the_values_out_of_limit(built) -> None:
    p = with_tolerance(built, **{CUT: 10, STRIP: 0.5})
    rep = asbuilt.asbuilt_report(p)
    assert (
        rep.out_of_limit == 1 and rep.count(asbuilt.WITHIN) == 2
    )  # W001-002 out; 001 cut, strip A
    assert rep.count(asbuilt.DIFFERS) == 0
    s = next(h for h in rep.harnesses if h.harness_id == "W001")
    assert (s.out_of_limit, s.within_limit, s.differs) == (1, 2, 0)
    md = asbuilt.report_markdown(p, "stamp")
    assert "## Out of limit" in md and "W001-002" in md and "OUT OF TOLERANCE by 40 mm" in md


# ---- explain ---------------------------------------------------------------------------------------


def test_explain_shows_actual_limit_margin_and_source_of_the_tolerance(built) -> None:
    p = with_tolerance(built, **{CUT: 10})
    d = next(x for x in explain_object(p, "W001-002") if x.id == "asbuilt-result")
    assert d.assumptions == ("A-ASBUILT-TOLERANCE",) and d.value == pytest.approx(0.05)
    assert d.check is not None and not d.check.passes
    assert (d.check.actual, d.check.limit, d.check.unit) == (50.0, 10.0, "mm")
    assert d.check.margin == pytest.approx(-40.0) and "OUT OF TOLERANCE" in d.check.text
    tol = next(i for i in d.inputs if i.name == "Tolerance")
    assert (tol.value, tol.unit) == (10.0, "mm") and "config/generation.json: asbuilt_cut_tolerance_mm" in tol.source  # fmt: skip
    assert [s.label for s in d.steps] == [
        "Difference",
        "Distance from the designed value",
        "Margin",
    ]
    assert d.steps[1].value == 50.0 and d.steps[2].value == pytest.approx(-40.0)
    ok = next(x for x in explain_object(p, "W001-001") if x.id == "asbuilt-result")
    assert ok.check is not None and ok.check.passes and ok.check.margin == pytest.approx(0.0)


def test_explain_has_a_strip_length_derivation_only_when_the_strip_tolerance_is_set(built) -> None:
    p = with_tolerance(built, **{STRIP: 0.4})
    found = [d for d in explain_object(p, "W001-001") if d.id == "asbuilt-result"]
    assert [d.subject for d in found] == ["Wire W001-001", "Wire W001-001 strip A"]
    d = found[1]
    assert d.unit == "mm" and d.value == pytest.approx(0.5) and d.check is not None
    assert (d.check.actual, d.check.limit, d.check.passes) == (0.5, 0.4, False)
    assert d.check.margin == pytest.approx(-0.1)


def test_the_derivations_files_are_the_same_until_a_tolerance_is_set(built) -> None:
    from harness_design_studio.core.derive_export import explain_all

    base = [d.to_dict() for d in explain_all(built)]
    assert [d.to_dict() for d in explain_all(with_tolerance(built))] == base
    assert [d.to_dict() for d in explain_all(with_tolerance(built, **{CUT: None, STRIP: None}))] == base  # fmt: skip
    assert [d.to_dict() for d in explain_all(with_tolerance(built, **{CUT: 10}))] != base


# ---- the command and the data -----------------------------------------------------------------------


def test_the_asbuilt_command_and_its_json_report_an_out_of_tolerance_length(
    built, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_design_studio.core.io.saver import save_project

    folder = tmp_path / "p"
    save_project(with_tolerance(built, **{CUT: 10}), folder)
    assert main(["asbuilt", str(folder)]) == 1  # a value out of its limit
    out = capsys.readouterr().out
    assert "OUT OF LIMIT: W001 wire W001-002: cut length (m)" in out and "OUT OF TOLERANCE by 40 mm" in out  # fmt: skip
    assert main(["asbuilt", str(folder), "--json"]) == 1
    doc = json.loads(capsys.readouterr().out)
    assert list(doc) == list(SHAPES["asbuilt"])  # the document has the keys it had
    assert doc["out_of_limit"] == 1 and doc["within_limit"] == 1
    lines = {(x["subject"], x["field"]): x for x in doc["lines"]}
    out_line = lines[("W001-002", "cut length (m)")]
    assert (out_line["status"], out_line["actual"], out_line["designed"]) == ("out of limit", 3.5, 3.45)  # fmt: skip
    assert out_line["margin"] == pytest.approx(-0.04)
    save_project(built, tmp_path / "q")  # the same records without a tolerance: nothing out
    assert main(["asbuilt", str(tmp_path / "q")]) == 0
    assert "no tolerance applied" in capsys.readouterr().out


def test_the_scripting_interface_gives_the_same_report(built, tmp_path: Path) -> None:
    from harness_design_studio.core.io.saver import save_project

    folder = tmp_path / "p"
    save_project(with_tolerance(built, **{CUT: 10}), folder)
    assert api.get_asbuilt(folder).to_dict()["out_of_limit"] == 1


# ---- a wrong value ---------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [-1, "5", True, [1]])
def test_a_tolerance_that_is_not_a_number_of_zero_or_more_is_an_error_and_applies_nothing(built, bad) -> None:  # fmt: skip
    p = with_tolerance(built, **{CUT: bad})
    issues = configcheck.validate(p)
    assert [i.message for i in issues] == [f"config/generation.json: {CUT} must be a number of 0 or more."]  # fmt: skip
    assert issues[0].severity == "error" and issues[0].code == "config_invalid"
    assert line(p, "wire", "W001-001", "cut length (m)").status == asbuilt.DIFFERS


def test_null_or_zero_is_not_an_error(built) -> None:
    for value in (None, 0, 0.5):
        assert not configcheck.validate(with_tolerance(built, **{CUT: value, STRIP: value}))
