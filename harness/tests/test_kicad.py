"""KiCad netlist import and fixed pinouts (D-123)."""

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import edit
from harness_design_studio.core.commands import Delete, History, apply_ops
from harness_design_studio.core.generate.engine import generate_project, plan_generation
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.kicad import (
    NetlistError,
    clean_net,
    parse_netlist,
    plan_netlist_import,
    read_netlist,
)
from harness_design_studio.core.model import Project, evolve
from harness_design_studio.core.samples import mini3
from harness_design_studio.core.verify import verify_project

FIXTURE = Path(__file__).parent / "fixtures" / "kicad" / "unit.net.xml"
MAP = {"28V": "PWR", "GND": "RTN"}


def test_parse_reads_components_pins_and_symbol_fields() -> None:
    n = read_netlist(FIXTURE)
    assert set(n.components) == {"J1", "J2", "U1"}
    j1 = n.components["J1"]
    assert j1.fields == {"harnessconnector": "TST1-J01", "harnesspart": "EX-MICROD-9-F"}
    assert {k: v.net for k, v in j1.pins.items() if k in ("1", "3", "8", "9")} == {
        "1": "/TX+",
        "3": "/io/RX+",
        "8": "unconnected-(J1-Pin_8)",
        "9": "Net-(J1-Pad9)",
    }
    assert n.components["J2"].pins["3"].function == "Pin_3" and n.source.endswith("unit.kicad_sch")


@pytest.mark.parametrize(
    "raw,want",
    [("/TX+", "TX+"), ("/io/RX+", "RX+"), ("GND", "GND"), ("Net-(J1-Pad9)", None), ("/Net-(J1-Pad9)", None), ("unconnected-(J1-Pin_8)", None), ("", None), ("  /28V ", "28V")],
)  # fmt: skip
def test_net_names_are_cleaned(raw: str, want: str | None) -> None:
    assert clean_net(raw) == want


def project_with_unit() -> Project:
    return mini3()


def test_plan_creates_connectors_with_fixed_pins_and_reports_what_is_left_to_decide() -> None:
    p = project_with_unit()
    plan = plan_netlist_import(p, read_netlist(FIXTURE), "OBC", signal_map=MAP)
    rows = {r.ref: r for r in plan.rows}
    assert (
        rows["J1"].ok
        and rows["J1"].connector_id == "TST1-J01"
        and rows["J1"].action == "added"
        and rows["J1"].pins == 4
    )
    assert not rows["J2"].ok and "HarnessPart" in rows["J2"].message  # no part known for J2
    assert plan.unmatched_signals == {}
    plan2 = plan_netlist_import(
        p, read_netlist(FIXTURE), "OBC", signal_map=MAP, parts={"J2": "EX-DSUB-9-F"}
    )
    assert plan2.ok_count == 2
    History(p).execute("import", plan2.ops)
    j1, j2 = p.connectors["TST1-J01"], p.connectors["OBC-J2"]
    pins = {pin.id: pin for pin in j1.pins}
    assert (pins["1"].signal, pins["1"].fixed, pins["4"].signal) == ("TX+", True, "RX-")
    assert (
        pins["8"].signal is None and pins["9"].signal is None and not pins["9"].fixed
    )  # unconnected and unnamed nets
    assert (
        len(j1.pins) == 9
    )  # pins the netlist never mentions are added as spare (library part has 9)
    assert [(x.id, x.signal) for x in j2.pins if x.signal] == [
        ("1", "PWR"),
        ("2", "RTN"),
        ("3", "RTN"),
    ]
    assert j1.unit_id == "OBC" and j1.role == "box"
    assert any("RTN" in w and "pins 2 and 3" in w for w in plan2.warnings)


def test_unmapped_names_are_listed_not_guessed() -> None:
    p = project_with_unit()
    plan = plan_netlist_import(p, read_netlist(FIXTURE), "OBC", parts={"J2": "EX-DSUB-9-F"})
    assert set(plan.unmatched_signals) == {"28V"}
    assert all(
        r.ok for r in plan.rows
    )  # the import still works; generation will say a signal is missing


def test_errors_per_row_and_unit() -> None:
    p = project_with_unit()
    n = read_netlist(FIXTURE)
    assert not plan_netlist_import(p, n, "NOPE").rows[0].ok
    assert "not in the netlist" in plan_netlist_import(p, n, "OBC", refs=["J9"]).rows[0].message
    assert "No component starts" in plan_netlist_import(p, n, "OBC", prefix="X").rows[0].message
    assert (
        "cannot be a connector ID"
        in plan_netlist_import(p, n, "OBC", refs=["J1"], connector_ids={"J1": "../x"})
        .rows[0]
        .message
    )
    assert (
        "belongs to another unit"
        in plan_netlist_import(p, n, "RW1", refs=["J1"], connector_ids={"J1": "OBC-J01"})
        .rows[0]
        .message
    )
    assert (
        "not a connector part"
        in plan_netlist_import(p, n, "OBC", refs=["J1"], parts={"J1": "EX-WIRE-SINGLE"})
        .rows[0]
        .message
    )
    dup = plan_netlist_import(
        p,
        n,
        "OBC",
        refs=["J1", "J2"],
        connector_ids={"J1": "SAME", "J2": "SAME"},
        parts={"J1": "EX-DSUB-9-F", "J2": "EX-DSUB-9-F"},
    )
    assert [r.ok for r in dup.rows] == [True, False] and "already used" in dup.rows[1].message


def test_updating_an_existing_connector_keeps_what_the_netlist_does_not_say() -> None:
    p = project_with_unit()
    # the netlist names its part (EX-MICROD-9-F); give the box connector that part so that only
    # what the netlist does not say is compared
    p.connectors["OBC-J01"] = evolve(p.connectors["OBC-J01"], part_id="EX-MICROD-9-F")
    box = p.connectors["OBC-J01"]
    plan = plan_netlist_import(
        p, read_netlist(FIXTURE), "OBC", refs=["J1"], connector_ids={"J1": "OBC-J01"}
    )
    assert plan.rows[0].action == "updated"
    History(p).execute("import", plan.ops)
    new = p.connectors["OBC-J01"]
    assert new.part_id == box.part_id and {x.id for x in new.pins} >= {x.id for x in box.pins}
    assert [x.signal for x in new.pins[:4]] == ["TX+", "TX-", "RX+", "RX-"]


# ---- generation honours the fixed pinout ---------------------------------------------------------


def with_fixed_connector() -> Project:
    p = project_with_unit()
    plan = plan_netlist_import(p, read_netlist(FIXTURE), "OBC", refs=["J1"], signal_map=MAP)
    History(p).execute("import", plan.ops)
    History(p).execute("free the RS-422 port", [Delete("interfaces", "IF-TM-RW1")])
    ops, iid = edit.ops_add_interface(p, "rs422", "OBC", "RW1", from_connector="TST1-J01")
    History(p).execute("connect", ops)
    return p


def test_generated_wires_use_the_fixed_pins_and_the_verifier_agrees() -> None:
    p = with_fixed_connector()
    generate_project(p)
    iid = next(i for i in p.interfaces if i != "IF-PWR-RW1")
    pins = {pin.signal: pin for pin in p.connectors["TST1-J01"].pins if pin.interface_id == iid}
    assert {s: x.id for s, x in pins.items()} == {"TX+": "1", "TX-": "2", "RX+": "3", "RX-": "4"}
    assert all(x.fixed for x in pins.values())
    assert verify_project(p).ok
    reasons = p.generation.provenance["pin:TST1-J01.1"]  # type: ignore[union-attr]
    assert any("fixed by the unit design" in line for line in reasons)


def test_regeneration_is_idempotent_and_deleting_the_interface_frees_the_pins() -> None:
    p = with_fixed_connector()
    generate_project(p)
    before = model_hash(p)
    plan = plan_generation(p)
    assert plan.empty
    apply_ops(p, plan.ops)
    assert model_hash(p) == before
    iid = next(i for i in p.interfaces if i != "IF-PWR-RW1")
    History(p).execute("delete", edit.ops_delete_interface(p, iid))
    apply_ops(p, plan_generation(p).ops)
    box = p.connectors["TST1-J01"]
    assert all(x.interface_id is None for x in box.pins) and [x.signal for x in box.pins[:4]] == [
        "TX+",
        "TX-",
        "RX+",
        "RX-",
    ]  # still named, no longer connected


def test_a_signal_the_fixed_pinout_does_not_have_is_an_error_not_a_guess() -> None:
    p = with_fixed_connector()
    box = p.connectors["TST1-J01"]
    apply_ops(
        p,
        [
            __import__("harness_design_studio.core.commands", fromlist=["Put"]).Put(
                "connectors",
                evolve(
                    box,
                    pins=[
                        evolve(x, signal=None, fixed=False) if x.id == "4" else x for x in box.pins
                    ],
                ),
            )
        ],
    )
    plan = plan_generation(p)
    assert any(
        f.code == "pin_allocation" and "fixed pinout and no free pin named RX-" in f.message
        for f in plan.report.findings
    )


def test_fixed_pins_survive_save_and_load(tmp_path: Path) -> None:
    p = with_fixed_connector()
    generate_project(p)
    save_project(p, tmp_path / "p")
    q = load_project(tmp_path / "p").project
    assert q.connectors["TST1-J01"] == p.connectors["TST1-J01"] and model_hash(q) == model_hash(p)


# ---- CLI ----------------------------------------------------------------------------------------


def test_cli_dry_run_apply_and_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    save_project(mini3(), tmp_path / "p")
    base = ["import-netlist", str(tmp_path / "p"), str(FIXTURE), "--unit", "OBC"]
    assert cli_main([*base, "--ref", "J1", "--dry-run"]) == 0
    assert "TST1-J01" not in load_project(tmp_path / "p").project.connectors
    out = capsys.readouterr().out
    assert "OK added TST1-J01" in out and "28V" not in out  # J2 not selected
    assert cli_main(base) == 1  # J2 has no part: nothing is applied
    assert "HarnessPart" in capsys.readouterr().out
    smap = tmp_path / "map.csv"
    smap.write_text("net,signal\n28V,PWR\nGND,RTN\n")
    assert cli_main([*base, "--part", "J2=EX-DSUB-9-F", "--signal-map", str(smap)]) == 0
    loaded = load_project(tmp_path / "p").project
    assert {x.id: x.signal for x in loaded.connectors["OBC-J2"].pins if x.signal} == {
        "1": "PWR",
        "2": "RTN",
        "3": "RTN",
    }
    assert cli_main(["import-netlist", str(tmp_path / "p"), str(FIXTURE), "--unit", "NOPE"]) == 1
    bad = tmp_path / "bad.xml"
    bad.write_text("<export><components")
    assert cli_main(["import-netlist", str(tmp_path / "p"), str(bad), "--unit", "OBC"]) == 2
    assert cli_main([*base, "--connector", "oops"]) == 2


def test_cli_signal_map_json_and_pin_function(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    save_project(mini3(), tmp_path / "p")
    smap = tmp_path / "map.json"
    smap.write_text('{"28V": "PWR"}')
    assert (
        cli_main(
            [
                "import-netlist",
                str(tmp_path / "p"),
                str(FIXTURE),
                "--unit",
                "OBC",
                "--ref",
                "J2",
                "--part",
                "J2=EX-DSUB-9-F",
                "--signal-map",
                str(smap),
                "--dry-run",
            ]
        )
        == 0
    )
    assert "GND" in capsys.readouterr().out  # unmapped, listed
    smap.write_text("[1, 2]")
    assert (
        cli_main(
            [
                "import-netlist",
                str(tmp_path / "p"),
                str(FIXTURE),
                "--unit",
                "OBC",
                "--signal-map",
                str(smap),
            ]
        )
        == 2
    )
    assert (
        cli_main(
            [
                "import-netlist",
                str(tmp_path / "p"),
                str(FIXTURE),
                "--unit",
                "OBC",
                "--ref",
                "J1",
                "--pin-function",
                "--dry-run",
            ]
        )
        == 0
    )


# ---- hostile and damaged files --------------------------------------------------------------------


@pytest.mark.parametrize(
    "data",
    [
        b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><export>&b;</export>',
        b'<!DOCTYPE export SYSTEM "file:///etc/passwd"><export/>',
        b"<export><!ENTITY x 'y'></export>",
        b"<not-a-netlist/>", b"<export", b"", b"\x00\x01\x02", b"<export>" + b"<a>" * 100_000,
    ],
)  # fmt: skip
def test_hostile_or_wrong_files_are_refused_politely(data: bytes) -> None:
    with pytest.raises(NetlistError):
        parse_netlist(data)


def test_oversized_netlist_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from harness_design_studio.core import kicad

    monkeypatch.setattr(kicad, "MAX_BYTES", 10)
    with pytest.raises(NetlistError, match="too large"):
        parse_netlist(b"<export>" + b" " * 50 + b"</export>")


def test_a_netlist_with_odd_content_is_still_read() -> None:
    n = parse_netlist(
        b'<export><components><comp ref="J1"/><comp/><comp ref="J2"><fields><field>no name</field></fields></comp></components><nets><net name="X"><node ref="J1" pin="1"/><node ref="J9" pin="1"/><node ref="J2"/></net></nets></export>'
    )
    assert (
        set(n.components) == {"J1", "J2"}
        and set(n.components["J1"].pins) == {"1"}
        and not n.components["J2"].pins
    )


@settings(max_examples=60, deadline=None, suppress_health_check=list(HealthCheck))
@given(st.binary(max_size=500), st.integers(0, 2000), st.binary(max_size=20))
def test_random_damage_to_a_real_netlist_never_raises_anything_but_netlist_error(
    noise: bytes, at: int, patch: bytes
) -> None:
    raw = FIXTURE.read_bytes()
    for data in (noise, raw[:at], raw[:at] + patch + raw[at:], raw[:at] + raw[at + len(patch) :]):
        try:
            n = parse_netlist(data)
        except NetlistError:
            continue
        base = mini3()
        plan = plan_netlist_import(base, n, "OBC", parts={"J1": "EX-DSUB-9-F", "J2": "EX-DSUB-9-F"})
        assert plan.ok_count <= len(plan.rows)
        if plan.ops:  # whatever the damaged file said, the accepted part never breaks the model
            assert not [
                i for i in check_integrity(edit.clone_with(base, plan.ops)) if i.severity == "error"
            ]


SEXPR = FIXTURE.with_name("unit.net")  # KiCad's default netlist format, as the editor writes it


def test_the_default_s_expression_netlist_reads_like_the_xml_one() -> None:
    a, b = read_netlist(SEXPR), read_netlist(FIXTURE)
    assert a.components.keys() == b.components.keys()
    assert {r: c.pins for r, c in a.components.items()} == {
        r: c.pins for r, c in b.components.items()
    }
    assert a.components["J1"].fields == b.components["J1"].fields


@pytest.mark.parametrize(
    "text",
    ['(export (design', "(export))", "(export) (export)", "hello", '(export (a "unterminated', "(" * 200 + ")" * 200, "(other)"],
)  # fmt: skip
def test_damaged_s_expressions_are_refused_with_a_message(text: str) -> None:
    with pytest.raises(NetlistError):
        parse_netlist(text.encode())


def test_s_expression_with_quotes_and_escapes() -> None:
    n = parse_netlist(b'(export (components (comp (ref "J1") (value "a \\"b\\" c")))(nets))')
    assert n.components["J1"].value == 'a "b" c'


def test_cli_signal_map_pairs_on_the_command_line(tmp_path: Path) -> None:
    save_project(mini3(), tmp_path / "p")
    base = ["import-netlist", str(tmp_path / "p"), str(FIXTURE), "--unit", "OBC", "--ref", "J2"]
    args = [*base, "--part", "J2=EX-DSUB-9-F", "--signal-map", "28V=PWR", "--signal-map", "GND=RTN"]
    assert cli_main(args) == 0
    pins = load_project(tmp_path / "p").project.connectors["OBC-J2"].pins
    assert {x.id: x.signal for x in pins if x.signal} == {"1": "PWR", "2": "RTN", "3": "RTN"}
    assert cli_main([*base, "--part", "J2=EX-DSUB-9-F", "--signal-map", "=PWR"]) == 2
