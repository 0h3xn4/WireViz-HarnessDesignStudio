"""Preparation for the data the owner will provide later (D-11 values, D-12 parts list, D-13 lengths)."""

from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import configcheck, drc
from harness_design_studio.core.commands import History, Put
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.generate.lengths import plan_length_import
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.library_import import guess_mapping, plan_parts_import
from harness_design_studio.core.model import Project, Segment, evolve
from harness_design_studio.core.samples import sat15, sat15_full


def with_values(p, **per_file):  # type: ignore[no-untyped-def]
    for name, values in per_file.items():
        p.config[name] = configcheck.with_value(p.config[name], "x", None).model_copy(
            update={"values": {**p.config[name].values, **values}}
        )
    return p


# ---- D-11: engineering values ---------------------------------------------------------------------


def test_every_need_exists_in_the_default_configuration_and_is_missing_at_first() -> None:
    p = sat15()
    for need in configcheck.NEEDS:
        assert need.key in p.config[need.file].values, f"{need.file}.{need.key}"
    assert len(configcheck.missing(p)) == len(configcheck.NEEDS)
    assert configcheck.validate(p) == []  # unset values are missing, not invalid
    text, ok = configcheck.report(p)
    assert (
        not ok
        and "MISSING config/derating.json ampacity_a_by_awg" in text
        and "Needed for:" in text
    )


def test_the_full_example_is_complete_and_valid_except_what_it_leaves_out() -> None:
    p = sat15_full()
    text, _ = configcheck.report(p)
    assert configcheck.validate(p) == []
    assert "MISSING config/derating.json bundle_derating" not in text


@pytest.mark.parametrize(
    "file,key,value",
    [
        ("derating", "bundle_derating", 1.5), ("derating", "bundle_derating", 0), ("derating", "temperature_derating", "high"),
        ("derating", "contact_current_factor", True), ("derating", "spare_pin_fraction", 1.0), ("derating", "max_voltage_drop_v", -1),
        ("derating", "ampacity_a_by_awg", {"20": 5.0, "24": 9.0}),  # a thinner wire may not carry more
        ("derating", "ampacity_a_by_awg", {"twenty": 5.0}), ("derating", "ampacity_a_by_awg", {"20": 0}), ("derating", "ampacity_a_by_awg", {}),
        ("generation", "conductor_resistivity_ohm_m", 0), ("generation", "shield_end_a", "grounded"), ("generation", "power_signal_gap_pins", 1.5),
        ("generation", "service_loop_m", -0.1), ("segregation", "category_pairs_to_separate", [["power"]]), ("emc", "conflicting_class_pairs", "A,B"),
    ],
)  # fmt: skip
def test_invalid_values_are_rejected_with_a_reason(file: str, key: str, value: object) -> None:
    p = sat15()
    p.config[file] = configcheck.with_value(p.config[file], key, value)
    issues = configcheck.validate(p)
    assert issues and issues[0].object_id == f"{file}.{key}" and key in issues[0].message


@pytest.mark.parametrize(
    "file,key,value",
    [("derating", "bundle_derating", 0.8), ("derating", "spare_pin_fraction", 0.0), ("derating", "ampacity_a_by_awg", {"24": 2.0, "20": 5.0}),
     ("generation", "shield_end_b", "pigtail"), ("generation", "power_signal_gap_pins", 2), ("emc", "conflicting_class_pairs", [["A", "B"]])],
)  # fmt: skip
def test_valid_values_pass(file: str, key: str, value: object) -> None:
    p = sat15()
    p.config[file] = configcheck.with_value(p.config[file], key, value)
    assert configcheck.validate(p) == []


def test_an_invalid_value_is_an_unwaivable_rule_error() -> None:
    p = sat15()
    p.config["derating"] = configcheck.with_value(p.config["derating"], "bundle_derating", 7)
    found = [f for f in drc.run(p) if f.rule == "config-invalid"]
    assert found and found[0].severity == "error" and not found[0].can_waive


def test_ampacity_csv_is_read_with_or_without_header_and_decimal_commas() -> None:
    table, problems = configcheck.plan_ampacity_import(
        [["awg", "amps"], ["24", "2,0"], ["20", "5"], ["18", "7.5"]]
    )
    assert problems == [] and table == {"24": 2.0, "20": 5.0, "18": 7.5}
    assert configcheck.plan_ampacity_import([["20", "5"]])[0] == {"20": 5.0}
    for bad in (
        [["20", "x"]],
        [["20"]],
        [["20", "5"], ["20", "6"]],
        [["99", "5"]],
        [["20", "-3"]],
        [],
        [["awg", "amps"]],
    ):
        assert configcheck.plan_ampacity_import(bad)[1], bad


def test_cli_config_lists_missing_loads_a_table_and_validates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    save_project(sat15(), tmp_path / "p")
    assert cli_main(["config", str(tmp_path / "p")]) == 1
    assert "MISSING config/derating.json ampacity_a_by_awg" in capsys.readouterr().out
    csv_file = tmp_path / "amp.csv"
    csv_file.write_text("awg,amps\n24,2\n22,3\n20,5\n")
    assert (
        cli_main(["config", str(tmp_path / "p"), "--ampacity-csv", str(csv_file)]) == 1
    )  # still other values missing
    out = capsys.readouterr().out
    assert (
        "Loaded 3 gauges" in out
        and "ampacity_a_by_awg" not in out.split("Loaded")[1].split("MISSING")[0] + "x"
    )
    loaded = load_project(tmp_path / "p").project
    assert loaded.config["derating"].values["ampacity_a_by_awg"] == {
        "24": 2.0,
        "22": 3.0,
        "20": 5.0,
    }
    bad = tmp_path / "bad.csv"
    bad.write_text("20,5\n24,9\n")  # thinner wire carries more: rejected
    assert cli_main(["config", str(tmp_path / "p"), "--ampacity-csv", str(bad)]) == 1
    assert (
        load_project(tmp_path / "p").project.config["derating"].values["ampacity_a_by_awg"]["24"]
        == 2.0
    )


def test_cli_config_exit_code_zero_when_everything_is_set(tmp_path: Path) -> None:
    p = sat15_full()
    for need in configcheck.missing(p):  # fill what the example leaves out, with test-only values
        value: object = 0.5
        if "pairs" in need.key:
            value = [["power", "analog"]]
        elif need.key.startswith("shield_end"):
            value = "pigtail"
        elif need.key == "power_signal_gap_pins":
            value = 1
        elif need.key == "ampacity_a_by_awg":
            value = {"20": 5.0}
        p.config[need.file] = configcheck.with_value(p.config[need.file], need.key, value)
    save_project(p, tmp_path / "p")
    assert cli_main(["config", str(tmp_path / "p")]) == 0


# ---- D-12: approved parts list --------------------------------------------------------------------

HEADER = ["Part number", "Manufacturer", "Description", "Category", "Status", "Pins", "Mass g"]


def test_parts_import_maps_columns_and_statuses_and_never_guesses() -> None:
    p = sat15()
    table = [
        HEADER,
        ["XYZ-9", "ACME", "9-pin socket", "connector", "EPPL", "9", "11,5"],
        ["WIR-1", "ACME", "single wire", "wire", "pending review", "", ""],
        ["BAD-1", "ACME", "?", "connector", "maybe", "", ""],
        ["BAD-2", "ACME", "?", "gadget", "EPPL", "", ""],
        ["BAD 3", "ACME", "?", "connector", "EPPL", "", ""],
        ["BAD-4", "ACME", "?", "connector", "EPPL", "nine", ""],
        ["", "ACME", "?", "connector", "EPPL", "", ""],
        ["BAD-5", "ACME", "?", "connector", "EPPL", "", "-3"],
    ]
    assert guess_mapping(HEADER) == {
        "part_number": 0,
        "manufacturer": 1,
        "description": 2,
        "category": 3,
        "approval": 4,
        "pin_count": 5,
        "mass_g": 6,
    }
    plan = plan_parts_import(
        p, table, guess_mapping(HEADER), approved=["EPPL"], pending=["pending review"]
    )
    ok = [r for r in plan.rows if r.ok]
    assert [r.part_id for r in ok] == ["XYZ-9", "WIR-1"] and all(r.action == "added" for r in ok)
    assert [r.row_number for r in plan.rows if not r.ok] == [4, 5, 6, 7, 8, 9]
    assert (
        "not in your approved" in plan.rows[2].message and "is not one of" in plan.rows[3].message
    )
    History(p).execute("import", plan.ops)
    part = p.parts["XYZ-9"]
    assert (part.approval, part.pin_count, part.mass_g, part.unverified, part.manufacturer) == (
        "approved",
        9,
        11.5,
        False,
        "ACME",
    )
    assert p.parts["WIR-1"].approval == "pending"


def test_parts_import_updates_existing_parts_and_keeps_unlisted_fields() -> None:
    p = sat15()
    old = p.parts["EX-DSUB-9-F"]
    table = [["id", "status"], ["EX-DSUB-9-F", "REJECTED"]]
    plan = plan_parts_import(
        p, table, {"id": 0, "approval": 1}, approved=["ok"], rejected=["rejected"]
    )
    assert [r.action for r in plan.rows] == ["updated"] and len(plan.ops) == 1
    History(p).execute("import", plan.ops)
    new = p.parts["EX-DSUB-9-F"]
    assert (
        new.approval == "not_approved"
        and new.pin_count == old.pin_count
        and new.category == old.category
    )


def test_parts_import_without_status_keeps_pending_for_new_parts() -> None:
    p = sat15()
    plan = plan_parts_import(
        p, [["id", "category"], ["NEW-1", "wire"]], {"id": 0, "category": 1}, approved=[]
    )
    op = plan.ops[0]
    assert (
        plan.ok_count == 1
        and isinstance(op, Put)
        and getattr(op.obj, "approval", None) == "pending"
    )


def test_cli_import_parts_preview_apply_and_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    save_project(sat15(), tmp_path / "p")
    f = tmp_path / "parts.csv"
    f.write_text("Part number,Category,Status\nNEW-1,connector,A\nNEW-2,wire,X\n")
    assert (
        cli_main(["import-parts", str(tmp_path / "p"), str(f), "--approved", "A"]) == 1
    )  # X is not explained
    assert "not in your approved" in capsys.readouterr().out
    assert "NEW-1" not in load_project(tmp_path / "p").project.parts
    assert (
        cli_main(
            [
                "import-parts",
                str(tmp_path / "p"),
                str(f),
                "--approved",
                "A",
                "--rejected",
                "X",
                "--dry-run",
            ]
        )
        == 0
    )
    assert "NEW-1" not in load_project(tmp_path / "p").project.parts
    assert (
        cli_main(
            ["import-parts", str(tmp_path / "p"), str(f), "--approved", "A", "--rejected", "X"]
        )
        == 0
    )
    parts = load_project(tmp_path / "p").project.parts
    assert parts["NEW-1"].approval == "approved" and parts["NEW-2"].approval == "not_approved"
    nocol = tmp_path / "nocol.csv"
    nocol.write_text("foo,bar\n1,2\n")
    assert cli_main(["import-parts", str(tmp_path / "p"), str(nocol)]) == 2


# ---- D-13: lengths (CAD export, KiCad users) ----------------------------------------------------


def project_with_segments() -> Project:
    p = sat15()
    generate_project(p)
    h = p.harnesses["W010"]
    apply = History(p)
    apply.execute(
        "segments",
        [
            Put(
                "harnesses",
                evolve(
                    h,
                    segments=[
                        Segment(
                            id="W010-L1", from_node=h.connectors[0].id, to_node=h.connectors[1].id
                        )
                    ],
                ),
            )
        ],
    )
    return p


def test_length_import_converts_millimetres_and_decimal_commas() -> None:
    p = project_with_segments()
    plan = plan_length_import(
        p, [["harness", "segment", "length_mm"], ["W010", "W010-L1", "1250,5"]], scale=0.001
    )
    assert plan.rows[0].ok
    History(p).execute("lengths", plan.ops)
    assert p.harnesses["W010"].segments[0].length_m == pytest.approx(1.2505)


def test_cli_import_lengths_default_unit_is_millimetres(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    save_project(project_with_segments(), tmp_path / "p")
    f = tmp_path / "len.csv"
    f.write_text("harness,segment,length\nW010,W010-L1,800\nW010,NOPE,5\n")
    assert (
        cli_main(["import-lengths", str(tmp_path / "p"), str(f)]) == 1
    )  # one bad row blocks everything
    assert load_project(tmp_path / "p").project.harnesses["W010"].segments[0].length_m is None
    f.write_text("harness,segment,length\nW010,W010-L1,800\n")
    assert cli_main(["import-lengths", str(tmp_path / "p"), str(f), "--dry-run"]) == 0
    assert cli_main(["import-lengths", str(tmp_path / "p"), str(f)]) == 0
    assert load_project(tmp_path / "p").project.harnesses["W010"].segments[
        0
    ].length_m == pytest.approx(0.8)
    f.write_text("harness,segment,length\nW010,W010-L1,0.5\n")
    assert cli_main(["import-lengths", str(tmp_path / "p"), str(f), "--unit", "m"]) == 0
    assert load_project(tmp_path / "p").project.harnesses["W010"].segments[
        0
    ].length_m == pytest.approx(0.5)
    assert capsys.readouterr().out
