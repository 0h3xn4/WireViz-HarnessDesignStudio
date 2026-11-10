# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""S8: declarative extensions (rules, tables and lookup tables written as data).

What is checked: a rule fires and does not fire against hand values with the exact actual value,
limit and margin; the explanation of an extension rule is the S1 derivation; a file with a problem is
reported with its file, line, path and key and never stops generation, the check or the export; a
file the project does not enable does nothing; and a project that enables nothing is byte-identical
to one without the folder."""

import copy
import hashlib
import json
import pickle
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import derive, drc
from harness_design_studio.core.checks import Finding, find
from harness_design_studio.core.drc import by_rule
from harness_design_studio.core.drc.base import Hit
from harness_design_studio.core.extensions import manager
from harness_design_studio.core.extensions.declarative import Lookup, lookup_value
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Project
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.validation import validate_folder
from tests.ext_helpers import (
    ext_file,
    gauge_rule,
    generated,
    set_wire,
    with_extensions,
    write_extensions,
)


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> Project:
    return generated(tmp_path_factory.mktemp("ext-base"))


@pytest.fixture
def project(base: Project) -> Project:
    return copy.deepcopy(base)


def findings(p: Project, rule: str = "x-gauge") -> list[Finding]:
    return [f for f in drc.run(p) if f.rule == rule]


# ---- a rule fires and does not fire, with exact numbers -------------------------------------------------


def test_an_upper_limit_fires_above_it_and_not_at_it(project: Project, tmp_path: Path) -> None:
    write_extensions(tmp_path, {"t.json": ext_file(rules=[gauge_rule()])})
    with_extensions(project, tmp_path)
    set_wire(project, "W001-001", gauge_awg=24)
    set_wire(project, "W001-002", gauge_awg=22)  # at the limit: not over it
    set_wire(project, "W001-003", gauge_awg=20)
    hit = {f.object_id: f for f in findings(project)}
    assert "W001-001" in hit and "W001-002" not in hit and "W001-003" not in hit
    assert hit["W001-001"].title == "Wire W001-001 is AWG 24, limit 22, margin -2"
    assert hit["W001-001"].severity == "warning"
    assert hit["W001-001"].id == "x-gauge.W001-001"


def test_the_derivation_carries_the_exact_actual_limit_and_margin(
    project: Project, tmp_path: Path
) -> None:
    write_extensions(tmp_path, {"t.json": ext_file(rules=[gauge_rule()])})
    with_extensions(project, tmp_path)
    set_wire(project, "W001-001", gauge_awg=24)
    (d,) = derive.explain_finding(project, "x-gauge", "W001-001")
    assert d.id == "rule-limit" and d.check is not None
    assert (d.check.actual, d.check.limit, d.check.margin, d.check.passes) == (
        24.0,
        22.0,
        -2.0,
        False,
    )
    assert d.value == 24.0 and d.unit == "AWG"
    assert d.equation == "this rule holds when wire.gauge_awg <= 22"
    assert [i.name for i in d.inputs] == ["wire.gauge_awg"] and d.inputs[0].value == 24
    assert "over the limit by 2 AWG" in d.check.text
    set_wire(project, "W001-001", gauge_awg=20)
    (ok,) = derive.explain_finding(project, "x-gauge", "W001-001")
    assert ok.check is not None
    assert (ok.check.actual, ok.check.limit, ok.check.margin, ok.check.passes) == (
        20.0,
        22.0,
        2.0,
        True,
    )
    assert "2 AWG to spare" in ok.check.text


def test_a_lower_limit_has_its_margin_the_other_way(project: Project, tmp_path: Path) -> None:
    rule = gauge_rule(
        id="thin",
        condition="wire.length_m >= 4",
        message="{object}: {actual} m of {limit} m, short by {over}",
        unit="m",
    )
    write_extensions(tmp_path, {"t.json": ext_file(rules=[rule])})
    with_extensions(project, tmp_path)
    set_wire(project, "W001-001", length_m=3.0)
    set_wire(project, "W001-002", length_m=4.0)
    set_wire(project, "W001-003", length_m=4.5)
    hit = {f.object_id: f.title for f in findings(project, "x-thin")}
    assert hit["W001-001"] == "W001-001: 3 m of 4 m, short by 1"
    assert "W001-002" not in hit and "W001-003" not in hit
    (d,) = derive.explain_finding(project, "x-thin", "W001-003")
    assert d.check is not None and (d.check.actual, d.check.limit, d.check.margin) == (
        4.5,
        4.0,
        0.5,
    )


def test_the_limit_can_be_a_field_a_setting_a_parameter_and_a_lookup(
    project: Project, tmp_path: Path
) -> None:
    doc = ext_file(
        parameters={"share": {"value": 0.5, "unit": "", "source": "a test value"}},
        lookups=[{"name": "amp", "unit": "A", "values": {"24": 0.6, "26": 0.2}}],
        rules=[
            gauge_rule(
                id="share",
                condition="wire.current_a <= wire.ampacity_limit_a * param('share')",
                unit="A",
                message="{object} {actual} A > {limit} A",
            ),
            gauge_rule(
                id="table",
                condition="wire.current_a <= lookup('amp', wire.gauge_awg)",
                unit="A",
                message="{object} {actual} A > {limit} A",
            ),
        ],
    )
    write_extensions(tmp_path, {"t.json": doc})
    with_extensions(project, tmp_path)
    # W001-001 is AWG 24 and carries 0.8 A; the derated limit of its gauge is 1.08 A
    (share,) = [f for f in findings(project, "x-share") if f.object_id == "W001-001"]
    assert share.title == "W001-001 0.8 A > 0.54 A"
    (table,) = [f for f in findings(project, "x-table") if f.object_id == "W001-001"]
    assert table.title == "W001-001 0.8 A > 0.6 A"
    (d,) = derive.explain_finding(project, "x-table", "W001-001")
    names = [i.name for i in d.inputs]
    assert "lookup amp[24]" in names and "wire.current_a" in names
    assert next(i for i in d.inputs if i.name == "lookup amp[24]").value == 0.6
    assert d.check is not None and d.check.margin == pytest.approx(-0.2)


def test_a_setting_is_read_with_its_origin(project: Project, tmp_path: Path) -> None:
    rule = gauge_rule(
        id="drop",
        condition="wire.voltage_drop_v <= setting('derating.max_voltage_drop_v')",
        unit="V",
        message="{object} drops {actual} V",
    )
    write_extensions(tmp_path, {"t.json": ext_file(rules=[rule])})
    with_extensions(project, tmp_path)
    cfg = project.config["derating"]
    from harness_design_studio.core.model import ConfigFile

    project.config["derating"] = ConfigFile(
        name="derating", placeholder=False, values={**cfg.values, "max_voltage_drop_v": 0.5}
    )
    hit = {f.object_id for f in findings(project, "x-drop")}
    assert "W001-005" in hit and "W001-001" not in hit  # 0.5912 V and 0.4584 V
    (d,) = derive.explain_finding(project, "x-drop", "W001-005")
    setting = next(i for i in d.inputs if i.name == "Largest voltage drop")
    assert setting.value == 0.5 and "config/derating.json: max_voltage_drop_v" in setting.source


def test_the_fields_are_the_numbers_the_tool_already_gives(project: Project) -> None:
    """A field calls the function the generator and the rules call, so it cannot disagree with them."""
    from harness_design_studio.core.extensions.declarative import contexts
    from harness_design_studio.core.extensions.fields import BUILTIN_FIELDS

    defs = {d.id: d for d in BUILTIN_FIELDS}
    ctx = dict(contexts(project, "wire"))["W001-005"]
    drop = derive.explain_wire(project, "W001-005")[2]
    limit = derive.explain_wire(project, "W001-005")[1]
    length = derive.explain_wire(project, "W001-005")[0]
    assert defs["wire.voltage_drop_v"].fn(ctx) == pytest.approx(drop.value)
    assert defs["wire.ampacity_limit_a"].fn(ctx) == pytest.approx(limit.value)
    assert defs["wire.length_m"].fn(ctx) == pytest.approx(length.value)
    assert defs["wire.mm2"].fn(ctx) == pytest.approx(0.20473030814712212)


def test_the_when_guard_limits_the_objects_and_an_unknown_value_is_not_checked(
    project: Project, tmp_path: Path
) -> None:
    rule = gauge_rule(id="power", when="wire.category == 'power'", condition="wire.gauge_awg <= 20")
    write_extensions(tmp_path, {"t.json": ext_file(rules=[rule])})
    with_extensions(project, tmp_path)
    found = {f.object_id for f in findings(project, "x-power")}
    power = {
        w.id
        for h in project.harnesses.values()
        for w in h.wires
        if (i := project.interfaces.get(w.interface_id or ""))
        and project.interface_types[i.type_id].category == "power"
    }
    assert found and found <= power
    set_wire(project, "W001-001", gauge_awg=None)  # not known: the rule can say nothing
    assert "W001-001" not in {f.object_id for f in findings(project, "x-power")}
    result = next(r for r in by_rule.run_by_rule(project) if r.rule_id == "x-power")
    assert result.status == "fail"  # others fail; the unknown one is named in the notes
    assert any("W001-001" in n and "not known" in n for n in result.notes)
    (d,) = derive.explain_finding(project, "x-power", "W001-001")
    assert (
        d.check is None
        and "wire.gauge_awg is not known" in d.missing
        and d.text.startswith("not known")
    )


def test_a_rule_that_could_look_at_nothing_is_not_checked_never_pass(
    project: Project, tmp_path: Path
) -> None:
    rule = gauge_rule(id="never", condition="wire.length_m <= 1000 and harness.mass_g <= 0")
    rule2 = gauge_rule(
        id="blank", when="wire.colour == 'no such colour'", condition="wire.gauge_awg <= 1"
    )
    write_extensions(tmp_path, {"t.json": ext_file(rules=[rule2])})
    with_extensions(project, tmp_path)
    r = next(r for r in by_rule.run_by_rule(project) if r.rule_id == "x-blank")
    assert r.status == "pass" and r.count == 0  # it applied to nothing: that is a pass, not a gap
    for h in project.harnesses.values():
        for w in h.wires:
            set_wire(project, w.id, gauge_awg=None)
    write_extensions(tmp_path, {"t.json": ext_file(rules=[gauge_rule(id="blank")])})
    manager.refresh(project)
    r = next(r for r in by_rule.run_by_rule(project) if r.rule_id == "x-blank")
    assert r.status == "not_checked" and r.notes and r.missing
    del rule


# ---- the other kinds of object ----------------------------------------------------------------------------


def test_rules_for_connectors_interfaces_and_harnesses(project: Project, tmp_path: Path) -> None:
    rules = [
        gauge_rule(
            id="pins",
            applies_to="connector",
            when="connector.role == 'cable'",
            condition="connector.pins <= 4",
            unit="pins",
            message="{object} has {actual} pins",
        ),
        gauge_rule(
            id="amps",
            applies_to="interface",
            condition="interface.max_current_a <= 0.5",
            unit="A",
            message="{object} carries {actual} A",
        ),
        gauge_rule(
            id="count",
            applies_to="harness",
            condition="harness.wires <= 20",
            unit="",
            message="{object} has {actual} wires of {limit}; {harness.id}",
        ),
    ]
    write_extensions(tmp_path, {"t.json": ext_file(rules=rules)})
    with_extensions(project, tmp_path)
    assert findings(project, "x-pins") and all(
        "pins" in f.title for f in findings(project, "x-pins")
    )
    w2 = findings(project, "x-count")
    assert {f.object_id for f in w2} == {
        h.id for h in project.harnesses.values() if len(h.wires) > 20
    }
    assert w2[0].title.endswith(f"wires of 20; {w2[0].object_id}")
    amps = findings(project, "x-amps")
    assert amps and all((project.interfaces[f.object_id].max_current_a or 0) > 0.5 for f in amps)


# ---- lookup tables ----------------------------------------------------------------------------------------


def _lk(mode: str, *points: tuple[str, float]) -> Lookup:
    return Lookup("t", mode, tuple(points))


def test_the_modes_of_a_lookup_table() -> None:
    pts = (("20", 11.0), ("22", 7.0), ("26", 3.0))
    assert lookup_value(_lk("exact", *pts), 22) == 7.0
    assert lookup_value(_lk("exact", *pts), 23) is None
    assert lookup_value(_lk("exact", *pts), None) is None
    assert lookup_value(_lk("next_up", *pts), 23) == 3.0  # the first key at or above
    assert lookup_value(_lk("next_up", *pts), 27) is None
    assert lookup_value(_lk("next_down", *pts), 23) == 7.0  # the last key at or below
    assert lookup_value(_lk("next_down", *pts), 19) is None
    assert lookup_value(_lk("interpolate", *pts), 24) == pytest.approx(5.0)
    assert lookup_value(_lk("interpolate", *pts), 21) == pytest.approx(9.0)
    assert lookup_value(_lk("interpolate", *pts), 30) is None  # never beyond the table
    text = Lookup("c", "exact", (("red", 1.0), ("blue", 2.0)))
    assert lookup_value(text, "blue") == 2.0 and lookup_value(text, "green") is None


# ---- a table ----------------------------------------------------------------------------------------------


def test_a_table_has_its_columns_rows_and_order(project: Project, tmp_path: Path) -> None:
    table = {
        "name": "power", "title": "Power wires", "applies_to": "wire",
        "where": "wire.category == 'power' and wire.harness == 'W001'",
        "sort": "wire.length_m",
        "columns": [
            {"header": "Wire", "value": "wire.id"},
            {"header": "Length", "value": "wire.length_m", "unit": "m"},
            {"header": "AWG", "value": "wire.gauge_awg"},
            {"header": "mm2", "value": "round(wire.mm2, 3)"},
            {"header": "Fixed", "value": "wire.locked"},
        ],
    }  # fmt: skip
    write_extensions(tmp_path, {"t.json": ext_file(tables=[table])})
    with_extensions(project, tmp_path)
    set_wire(project, "W001-001", gauge_awg=None, length_m=9.0)
    ((name, rows),), notes = manager.tables_for(project)
    assert name == "power" and not notes
    assert rows[0] == ["Wire", "Length (m)", "AWG", "mm2", "Fixed"]
    by_id = {r[0]: r for r in rows[1:]}
    assert by_id["W001-001"] == ["W001-001", "9", "unknown", "unknown", "no"]
    assert by_id["W001-002"] == ["W001-002", "3.45", "24", "0.205", "no"]
    lengths = [float(r[1]) for r in rows[1:]]
    assert lengths == sorted(lengths)  # sorted by the expression, ties in the order of the design
    assert all(r[0].startswith("W001") for r in rows[1:])
    outputs = build_outputs(project, drawings=False)
    assert "system/extensions/power.csv" in outputs.files
    text = outputs.files["system/extensions/power.csv"].decode()
    assert (
        text.splitlines()[2] == "Wire,Length (m),AWG,mm2,Fixed"
        and "W001-002,3.45,24,0.205,no" in text
    )


def test_a_cell_that_cannot_be_worked_out_says_error_and_is_reported(
    project: Project, tmp_path: Path
) -> None:
    table = {
        "name": "bad",
        "title": "t",
        "applies_to": "harness",
        "columns": [{"header": "x", "value": "harness.name + 1"}],
    }
    write_extensions(tmp_path, {"t.json": ext_file(tables=[table])})
    with_extensions(project, tmp_path)
    ((_, rows),), notes = manager.tables_for(project)
    assert rows[1] == ["error"] and notes and "works on numbers" in notes[0]


# ---- a file with a problem --------------------------------------------------------------------------------


def issues_of(tmp_path: Path, doc: object) -> list[str]:
    text = doc if isinstance(doc, str) else json.dumps(doc, indent=1)
    write_extensions(tmp_path, {"bad.json": text})
    ext = manager.discover(tmp_path)
    assert ext is not None
    return [i.render() for i in ext.issues]


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        (
            {"rules.0.condition": "wire.gauge <= 3"},
            "rules[0].condition: column 1: unknown field 'wire.gauge'",
        ),
        (
            {"rules.0.condition": "__import__('os')"},
            "rules[0].condition: column 1: a name cannot begin with an underscore",
        ),
        ({"rules.0.condition": "open('x')"}, "not in the whitelist"),
        ({"rules.0.when": "wire.category.upper()"}, "rules[0].when:"),
        (
            {"rules.0.severity": "fatal"},
            "rules[0].severity: 'fatal' is not one of error, warning, info",
        ),
        (
            {"rules.0.applies_to": "pin"},
            "rules[0].applies_to: 'pin' is not one of wire, connector, interface, harness",
        ),
        ({"rules.0.surprise": 1}, "rules[0].surprise: unknown key 'surprise'"),
        (
            {"rules.0.message": "{nothing} here"},
            "rules[0].message: the placeholder {nothing} is not known",
        ),
        ({"rules.0.id": "Bad Id"}, "rules[0].id: 'Bad Id' is not an acceptable name"),
        ({"rules.0.how": ""}, "rules[0].how: must not be empty"),
        ({"rules.0.condition": 5}, "rules[0].condition: expected a text, found a number"),
        ({"rules.0.requirements": "R1"}, "rules[0].requirements: expected a list"),
        ({"version": None}, "version: expected a text, found null"),
        ({"format_version": 2}, "format_version: must be 1"),
        ({"format": "x"}, "format: must be 'harness-design-studio-extension'"),
        ({"rules": "no"}, "rules: expected a list, found a text"),
        ({"rules.0.condition": "param('missing')"}, "unknown parameter 'missing'"),
        ({"rules.0.condition": "lookup('missing', 1)"}, "unknown lookup table 'missing'"),
    ],
)
def test_every_problem_names_the_file_the_line_the_path_and_the_key(
    tmp_path: Path, change: dict[str, object], fragment: str
) -> None:
    doc = ext_file(rules=[gauge_rule()])
    for path, value in change.items():
        node: Any = doc
        *head, last = path.split(".")
        for part in head:
            node = node[int(part)] if part.isdigit() else node[part]
        if last.isdigit():
            node[int(last)] = value
        else:
            node[last] = value
    found = issues_of(tmp_path, doc)
    assert any(fragment in line for line in found), found
    assert all(line.startswith("extensions/bad.json:") for line in found)


def test_the_line_of_a_problem_is_the_line_of_its_key(tmp_path: Path) -> None:
    text = """{
  "format": "harness-design-studio-extension",
  "format_version": 1,
  "name": "t",
  "version": "1",
  "rules": [
    {
      "id": "r",
      "title": "T",
      "severity": "warning",
      "applies_to": "wire",
      "condition": "wire.gauge <= 3",
      "message": "m",
      "why": "w",
      "how": "h"
    }
  ]
}
"""
    assert issues_of(tmp_path, text) == [
        "extensions/bad.json:12: rules[0].condition: column 1: unknown field 'wire.gauge' (did you mean wire.gauge_awg?)"
    ]


@pytest.mark.parametrize(
    ("text", "line", "fragment"),
    [
        ('{\n "a": 1,\n}\n', 3, "a key (a text in double quotes) was expected"),
        ('{"a": 1 "b": 2}', 1, "a comma or a closing brace was expected"),
        ('{"a": 1, "a": 2}', 1, "'a' is there twice"),
        ("[1, 2", 1, "closing bracket"),
        ("{'a': 1}", 1, "key"),
        ('{"a": NaN}', 1, "unexpected character"),
        ("// note\n{}", 1, "unexpected character"),
        ("", 1, "ends before a value"),
        ('{"a": 01}', 1, "not a number"),
    ],
)
def test_a_file_that_is_not_json_is_reported_with_its_line(
    tmp_path: Path, text: str, line: int, fragment: str
) -> None:
    (found,) = issues_of(tmp_path, text)
    assert found.startswith(f"extensions/bad.json:{line}:") and fragment in found, found


def test_a_file_that_is_not_text_a_link_or_too_large_is_reported(tmp_path: Path) -> None:
    folder = write_extensions(tmp_path, {"a.json": "{}", "b.json": "{}", "c.json": "{}"})
    (folder / "a.json").write_bytes(b"\xff\xfe\x00")
    (folder / "b.json").write_text(" " * (1024 * 1024 + 1))
    (folder / "c.json").unlink()
    try:
        (folder / "c.json").symlink_to(folder / "b.json")
    except OSError:
        pytest.skip("no symbolic links here")
    ext = manager.discover(tmp_path)
    assert ext is not None
    text = "\n".join(i.render() for i in ext.issues)
    assert "not UTF-8" in text and "larger than" in text and "link is not followed" in text


def test_two_files_cannot_claim_one_rule_and_the_first_keeps_it(tmp_path: Path) -> None:
    write_extensions(
        tmp_path,
        {
            "a.json": ext_file("a", rules=[gauge_rule()]),
            "b.json": ext_file("b", rules=[gauge_rule()]),
        },
    )
    ext = manager.discover(tmp_path)
    assert ext is not None
    status = {f.file: f.status for f in ext.files}
    assert status == {"a.json": "applied", "b.json": "broken"}
    assert any(
        "'x-gauge' is already provided by extensions/a.json" in i.render() for i in ext.issues
    )


def test_the_prefix_x_is_added_once(tmp_path: Path) -> None:
    write_extensions(
        tmp_path, {"a.json": ext_file(rules=[gauge_rule(id="x-already"), gauge_rule(id="plain")])}
    )
    ext = manager.discover(tmp_path)
    assert ext is not None and sorted(r.id for f in ext.parsed for r in f.rules) == [
        "x-already",
        "x-plain",
    ]


# ---- a broken extension never stops the tool -----------------------------------------------------------------


def test_a_broken_extension_is_reported_and_stops_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = generated(tmp_path)
    root = tmp_path / "proj"
    save_project(project, root)
    write_extensions(
        root,
        {"good.json": ext_file("good", rules=[gauge_rule(id="ok")]), "broken.json": "{ not json"},
    )
    # validate says so (as a warning: the project itself is fine)
    result, extra = validate_folder(root)
    messages = [i.message for i in extra if i.code == "extension_problem"]
    assert any("broken.json:1:" in m and "not valid JSON" in m for m in messages)
    assert not any(i.severity == "error" for i in [*result.issues, *extra])
    # the check runs, the good file applies, the broken one is a finding of its own
    loaded = load_project(root).project
    rules = {f.rule for f in drc.run(loaded)}
    assert "x-ok" in rules and "x-extension-problem" in rules
    problem = next(f for f in drc.run(loaded) if f.rule == "x-extension-problem")
    assert "broken.json" in problem.title and "was not applied" in problem.title
    (d,) = derive.explain_finding(loaded, "x-extension-problem", problem.object_id)
    assert d.id == "rule-check"
    # generate and export still work
    assert main(["generate", str(root)]) == 0
    assert main(["export", str(root)]) == 0
    out = capsys.readouterr().out
    assert "files written" in out
    assert main(["validate", str(root)]) == 0  # warnings do not fail validate
    assert main(["extensions", str(root)]) == 1  # but something enabled is not applied


def test_a_rule_that_raises_is_reported_and_the_others_still_run(
    project: Project, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_extensions(tmp_path, {"t.json": ext_file(rules=[gauge_rule(id="a"), gauge_rule(id="b")])})
    with_extensions(project, tmp_path)
    rt = manager.runtime(project)
    assert rt is not None
    boom = rt.rules[0]

    def explode(_p: Project) -> Iterator[Hit]:
        raise RuntimeError("boom")

    rt.rules[0] = replace(boom, check=explode)
    found = drc.run(project)
    assert {f.rule for f in found} >= {"x-b", "x-extension-problem"}
    assert not [f for f in found if f.rule == "x-a"]
    assert any(
        "x-a" in f.title and "RuntimeError" in f.title
        for f in found
        if f.rule == "x-extension-problem"
    )


# ---- opt-in per project ----------------------------------------------------------------------------------------


def test_a_file_the_project_does_not_enable_does_nothing(project: Project, tmp_path: Path) -> None:
    write_extensions(tmp_path, {"t.json": ext_file(rules=[gauge_rule()])}, enabled=[])
    with_extensions(project, tmp_path)
    assert not findings(project)
    assert manager.rules_for(project) == []
    ext = project.extensions
    assert ext is not None and [(f.file, f.status, f.rules) for f in ext.files] == [
        ("t.json", "disabled", 1)
    ]
    items = manager.listing(project)["items"]
    assert any(i["name"] == "x-gauge" and i["enabled"] is False for i in items)
    assert manager.provenance(project) == []
    assert manager.loaded(project) == []


def test_a_folder_without_enabled_json_enables_nothing(project: Project, tmp_path: Path) -> None:
    folder = write_extensions(tmp_path, {"t.json": ext_file(rules=[gauge_rule()])})
    (folder / "enabled.json").unlink()
    with_extensions(project, tmp_path)
    assert not findings(project) and manager.rules_for(project) == []


def test_a_project_without_extensions_is_byte_identical(tmp_path: Path) -> None:
    """A project with no extensions folder, one with an empty folder, and one with files that are not
    enabled write the same bytes and give the same findings."""
    plain = generated(tmp_path / "a")
    folder = tmp_path / "p"
    save_project(plain, folder)
    assert load_project(folder).project.extensions is None
    reference = build_outputs(load_project(folder).project, drawings=False)
    ref_findings = [(f.id, f.title) for f in drc.run(load_project(folder).project)]
    ref_report = by_rule.run_by_rule(load_project(folder).project)

    (folder / "extensions").mkdir()
    write_extensions(
        folder,
        {
            "t.json": ext_file(
                rules=[gauge_rule()],
                tables=[
                    {
                        "name": "t",
                        "title": "t",
                        "applies_to": "wire",
                        "columns": [{"header": "a", "value": "wire.id"}],
                    }
                ],
            )
        },
        enabled=[],
    )
    other = load_project(folder).project
    assert other.extensions is not None
    got = build_outputs(other, drawings=False)
    assert {k: hashlib.sha256(v).hexdigest() for k, v in got.files.items()} == {
        k: hashlib.sha256(v).hexdigest() for k, v in reference.files.items()
    }
    assert [(f.id, f.title) for f in drc.run(other)] == ref_findings
    assert [(r.rule_id, r.status) for r in by_rule.run_by_rule(other)] == [
        (r.rule_id, r.status) for r in ref_report
    ]
    assert len(drc.all_rules(other)) == len(drc.RULES) == 39
    assert find(other) == find(load_project(folder).project)


def test_the_extension_folder_is_left_alone_by_a_save_and_is_not_project_data(
    tmp_path: Path,
) -> None:
    project = generated(tmp_path / "a")
    folder = tmp_path / "p"
    save_project(project, folder)
    write_extensions(folder, {"t.json": ext_file(rules=[gauge_rule()])})
    before = (folder / "extensions" / "t.json").read_bytes()
    loaded = load_project(folder).project
    save_project(loaded, folder)
    assert (folder / "extensions" / "t.json").read_bytes() == before
    from harness_design_studio.core.io.layout import model_hash

    assert model_hash(loaded) == model_hash(load_project(folder).project)
    assert not any(i.code == "unrecognized_file" for i in load_project(folder).issues)


# ---- the run, the report and the other process --------------------------------------------------------------------


def test_the_report_and_the_findings_table_say_what_is_in_force(
    project: Project, tmp_path: Path
) -> None:
    write_extensions(tmp_path, {"t.json": ext_file(rules=[gauge_rule()])})
    with_extensions(project, tmp_path)
    from harness_design_studio.core.drc.report import render_markdown

    text = render_markdown(project)
    assert "Rules run: 40." in text and "Extension in force: declarative t 1.0.0, sha256" in text
    outputs = build_outputs(project, drawings=False)
    manifest = json.loads(outputs.manifest(project))
    assert [e["name"] for e in manifest["extensions"]] == ["t"]
    prov = json.loads(outputs.files["system/provenance.json"])
    assert (
        prov["extensions"][0]["kind"] == "declarative"
        and len(prov["extensions"][0]["sha256"]) == 64
    )
    assert "x-gauge" in outputs.files["system/drc_findings.csv"].decode()


def test_the_project_travels_to_the_rule_check_process(project: Project, tmp_path: Path) -> None:
    """The check runs in a helper process that receives a pickled project: the extension rules must
    be found there too (the helper reads the files again and rebuilds what runs)."""
    write_extensions(tmp_path, {"t.json": ext_file(rules=[gauge_rule()])})
    with_extensions(project, tmp_path)
    here = [(f.id, f.title) for f in drc.run(project)]
    manager._RUNTIMES.clear()
    there = pickle.loads(pickle.dumps(project))  # noqa: S301
    assert there.extensions is not None
    assert [(f.id, f.title) for f in drc.run(there)] == here
    assert any(i == "x-gauge.W001-001" for i, _t in here)


def test_a_waiver_applies_to_an_extension_finding(project: Project, tmp_path: Path) -> None:
    write_extensions(tmp_path, {"t.json": ext_file(rules=[gauge_rule()])})
    with_extensions(project, tmp_path)
    f = next(x for x in drc.run(project) if x.rule == "x-gauge" and x.object_id == "W001-001")
    assert f.can_waive  # a warning can be waived
    err = gauge_rule(id="hard", severity="error")
    write_extensions(tmp_path, {"t.json": ext_file(rules=[err])})
    manager.refresh(project)
    h = next(x for x in drc.run(project) if x.rule == "x-hard")
    assert h.severity == "error" and not h.can_waive
    write_extensions(
        tmp_path,
        {"t.json": ext_file(rules=[gauge_rule(id="hard", severity="error", waivable=True)])},
    )
    manager.refresh(project)
    assert next(x for x in drc.run(project) if x.rule == "x-hard").can_waive


def test_requirement_ids_travel_with_the_finding(project: Project, tmp_path: Path) -> None:
    write_extensions(
        tmp_path, {"t.json": ext_file(rules=[gauge_rule(requirements=["REQ-1", "REQ-2"])])}
    )
    with_extensions(project, tmp_path)
    f = next(x for x in drc.run(project) if x.rule == "x-gauge")
    assert f.sources == ("REQ-1", "REQ-2")
    (d,) = derive.explain_finding(project, "x-gauge", f.object_id)
    assert "REQ-1, REQ-2" in d.reference
