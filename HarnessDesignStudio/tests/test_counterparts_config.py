# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""REQ-DRC-05, REQ-IO-02. Release 1.9 (W3): the words that are the two ends of one line (TX and RX,
MOSI and MISO ...) are a setting of the project, `config/naming.json` `signal_counterparts`. While
it is not set the table the tool shipped with is used; the link review and the pairing read it;
it is checked like any other configuration value; `config --counterparts` sets it. No Qt."""

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import configcheck, counterparts
from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.drc import run as run_drc
from harness_design_studio.core.generate.engine import plan_generation
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.links import (
    check_link,
    counterparts_of,
    name_relation,
    plan_add_link,
    propose_pairs,
    same_side,
)
from harness_design_studio.core.model import Pin
from harness_design_studio.core.model.config import ConfigFile
from tests.helpers import pinout_project
from tests.reference import links_181 as old

KEY = counterparts.CONFIG_KEY


def with_table(table, p=None):
    p = p or pinout_project()
    base = p.config["naming"]
    p.config["naming"] = ConfigFile(
        name="naming", placeholder=base.placeholder, values={**base.values, KEY: table}
    )
    return p


def set_pins(p, cid, *signals):
    p.connectors[cid] = p.connectors[cid].model_copy(
        update={"pins": [Pin(id=str(k + 1), signal=s) for k, s in enumerate(signals)]}
    )


def issues(p):
    return [i for i in configcheck.validate(p) if i.object_id == f"naming.{KEY}"]


# ---- the default is the table the tool had -----------------------------------------------------


def test_the_default_table_is_the_one_release_181_had():
    assert counterparts.DEFAULT_COUNTERPARTS == old._TX_RX_WORDS
    assert pinout_project().config["naming"].values.get(KEY) is None  # not in a new project
    assert counterparts_of(pinout_project()) is counterparts.DEFAULT


def test_a_new_project_does_not_carry_the_key_so_its_files_stay_as_they_were():
    from harness_design_studio.core.samples import new_project

    assert KEY not in new_project().config["naming"].values


# ---- reading it --------------------------------------------------------------------------------


def test_a_table_of_the_project_decides_what_a_counterpart_is():
    p = pinout_project()
    assert name_relation("LINE_OUT", "LINE_IN", counterparts_of(p)) == ""
    q = with_table([["OUT", "IN"]])
    t = counterparts_of(q)
    assert name_relation("LINE_OUT", "line_in", t) == "counterpart"
    assert name_relation("TX", "RX", t) == ""  # TX and RX are not in this table
    assert same_side("LINE_OUT", "LINE_OUT", t) == "transmit"
    assert same_side("LINE_IN", "LINE_IN", t) == "receive"
    assert same_side("UART_TX", "UART_TX", t) == ""


def test_the_pairing_proposal_reads_the_table():
    p = pinout_project()
    set_pins(p, "OBC-J03", "LINE_OUT", "TX")
    set_pins(p, "PCDU-J03", "LINE_IN", "RX")
    assert [(x.a_pin, x.b_pin) for x in propose_pairs(p, "OBC-J03", "PCDU-J03").pairs] == [("2", "2")]  # fmt: skip
    q = with_table([["OUT", "IN"]], p)
    assert [(x.a_pin, x.b_pin) for x in propose_pairs(q, "OBC-J03", "PCDU-J03").pairs] == [("1", "1")]  # fmt: skip
    r = with_table([], p)  # no pairs at all: only equal names pair
    assert propose_pairs(r, "OBC-J03", "PCDU-J03").pairs == ()


def test_the_review_reads_the_table():
    p = pinout_project()
    set_pins(p, "OBC-J03", "LINE_OUT")
    set_pins(p, "PCDU-J03", "LINE_IN")
    ops, lid = plan_add_link(p, "OBC-J03", "PCDU-J03", [("1", "1")])
    apply_ops(p, ops)
    assert [f.code for f in check_link(p, p.links[lid])] == ["link_signal_mismatch"]
    q = with_table([["OUT", "IN"]], p)
    assert check_link(q, q.links[lid]) == []


def test_a_word_table_with_the_old_words_in_other_case_or_order_means_the_same():
    a = counterparts.Counterparts.of([["rx", "tx"], ["MISO", "MOSI"]])
    for x, y in (("TX", "RX"), ("UART_TX", "UART_RX"), ("MOSI", "MISO")):
        assert name_relation(x, y, a) == "counterpart"
    assert same_side("RX", "RX", a) == "transmit"  # the first word of a pair is the transmit one


# ---- checking it -------------------------------------------------------------------------------


@pytest.mark.parametrize("table", [None, [], [["TX", "RX"]], [["tx", "rx"], ["Mosi", "miso"]]])
def test_good_tables_and_no_table_are_not_a_problem(table):
    assert issues(with_table(table)) == []


@pytest.mark.parametrize(
    ("table", "why"),
    [
        ("TX=RX", "must be a list of pairs"),
        ({"TX": "RX"}, "must be a list of pairs"),
        ([["TX"]], "pairs of two words"),
        ([["TX", "RX", "X"]], "pairs of two words"),
        ([["TX", 3]], "pairs of two words"),
        ([["TX1", "RX1"]], "letters only"),
        ([["TX+", "RX+"]], "letters only"),
        ([["", "RX"]], "pairs of two words"),
        ([["TX", "tx"]], "one word twice"),
        ([["TX", "RX"], ["RX", "DIN"]], "uses the word 'rx' in two pairs"),
        ([["TX", "RX"], ["tx", "RXD"]], "uses the word 'tx' in two pairs"),
    ],
)
def test_bad_tables_are_named_in_a_sentence_and_the_default_is_used(table, why):
    p = with_table(table)
    (i,) = issues(p)
    assert i.severity == "error" and i.code == "config_invalid"
    assert i.message.startswith("config/naming.json: signal_counterparts ") and why in i.message
    assert counterparts_of(p) is counterparts.DEFAULT  # never half-used


def test_the_configuration_rule_of_the_design_check_reports_a_bad_table():
    p = with_table([["TX", "RX"], ["RX", "DIN"]])
    hits = [f for f in run_drc(p) if f.rule == "config-invalid" and KEY in f.title + f.object_id]
    assert len(hits) == 1


def test_generation_reports_a_bad_table_as_a_configuration_error():
    plan = plan_generation(with_table([["TX", "TX"]]))
    assert any(f.code == "config_invalid" and KEY in f.message for f in plan.report.findings)


# ---- the setting from the command line and the planner -----------------------------------------


def test_the_planner_reads_text_lists_and_the_words_default_and_none():
    p = pinout_project()
    plan = configcheck.plan_set_counterparts(p, "TX=RX, MOSI : MISO; dout/din")
    assert plan.ok and plan.value == [["TX", "RX"], ["MOSI", "MISO"], ["dout", "din"]]
    assert configcheck.plan_set_counterparts(p, "none").value == []
    assert configcheck.plan_set_counterparts(p, "default").value is None
    assert configcheck.plan_set_counterparts(p, "").value is None
    assert configcheck.plan_set_counterparts(p, [["OUT", "IN"]]).value == [["OUT", "IN"]]
    for bad in ("TX", "TX=RX=X", "TX1=RX1", "TX=RX, RX=DIN", [["a", "a"]], 7):
        assert configcheck.plan_set_counterparts(p, bad).error, bad


def test_the_planner_changes_only_this_key_and_clearing_removes_it():
    p = pinout_project()
    before = dict(p.config["naming"].values)
    History(p).execute("words", configcheck.plan_set_counterparts(p, "OUT=IN").ops)
    assert p.config["naming"].values == {**before, KEY: [["OUT", "IN"]]}
    History(p).execute("words", configcheck.plan_set_counterparts(p, "default").ops)
    assert p.config["naming"].values == before and KEY not in p.config["naming"].values


def test_the_configuration_report_names_the_table_only_when_the_project_sets_it():
    p = pinout_project()
    assert "counterparts" not in configcheck.report(p)[0]
    text = configcheck.report(with_table([["OUT", "IN"]], p))[0]
    assert "Signal counterparts: 1 pair of words set in config/naming.json" in text


def test_the_command_sets_reports_and_clears_the_table(tmp_path, capsys):
    save_project(pinout_project(), tmp_path / "p")
    root = str(tmp_path / "p")
    cli_main(["config", root, "--counterparts", "OUT=IN, TX=RX"])
    out = capsys.readouterr().out
    assert "Counterpart words: 2 pairs set in config/naming.json." in out
    assert "Signal counterparts: 2 pairs of words set" in out
    assert load_project(tmp_path / "p").project.config["naming"].values[KEY] == [["OUT", "IN"], ["TX", "RX"]]  # fmt: skip
    cli_main(["config", root, "--counterparts", "default"])
    assert "the table the tool ships with is used again" in capsys.readouterr().out
    assert KEY not in load_project(tmp_path / "p").project.config["naming"].values


def test_the_command_refuses_a_bad_table_and_changes_nothing(tmp_path, capsys):
    save_project(pinout_project(), tmp_path / "p")
    assert cli_main(["config", str(tmp_path / "p"), "--counterparts", "TX=RX, RX=DIN"]) == 1
    err = capsys.readouterr().err
    assert "uses the word 'rx' in two pairs" in err and "Nothing was changed." in err
    assert KEY not in load_project(tmp_path / "p").project.config["naming"].values
