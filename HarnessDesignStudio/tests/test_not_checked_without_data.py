"""1.8.1 (audit B-04, F-03): a rule that is ready to run but found nothing to look at says
"not checked", never "pass". Projects that have the data, and projects whose values are still
placeholders, are unchanged."""

from harness_design_studio.core import drc, edit
from harness_design_studio.core.drc import by_rule
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import Project
from harness_design_studio.core.model.config import ConfigFile
from harness_design_studio.core.samples import sat15

_BASE: Project | None = None
WIRE_RULES = ("current-over-contact", "current-over-wire", "voltage-drop")


def base() -> Project:
    global _BASE
    if _BASE is None:
        _BASE = sat15()
        generate_project(_BASE)
    return edit.clone_with(_BASE, [])


def set_cfg(p: Project, name: str, **values: object) -> None:
    old = p.config[name]
    p.config[name] = ConfigFile(name=name, placeholder=False, values={**old.values, **values})


def ready(p: Project) -> Project:
    """Every value the current, voltage and EMC rules read is set."""
    set_cfg(p, "derating", ampacity_a_by_awg={"26": 1.0, "20": 5.0, "16": 10.0},
            temperature_derating=0.9, bundle_derating=0.6, contact_current_factor=0.5,
            max_voltage_drop_v=1.0, connector_voltage_factor_rated=0.75,
            wire_voltage_factor=0.5, bundle_factor_by_count={"10": 0.6, "100": 0.4})  # fmt: skip
    set_cfg(p, "generation", conductor_resistivity_ohm_m=1.7e-8)
    set_cfg(p, "emc", conflicting_class_pairs=[["A", "B"]], same_class_one_bundle=True)
    return p


def strip_data(p: Project) -> Project:
    for k, i in list(p.interfaces.items()):
        p.interfaces[k] = i.model_copy(update={"max_current_a": None, "voltage_v": None})
    return p


def results(p: Project) -> dict[str, by_rule.RuleResult]:
    return {r.rule_id: r for r in by_rule.run_by_rule(p)}


def test_no_current_anywhere_is_not_checked_not_pass() -> None:
    r = results(strip_data(ready(base())))
    for rule in (*WIRE_RULES, "bundle-current"):
        assert r[rule].status == "not_checked", rule
        assert any("No interface has a current yet" in n for n in r[rule].notes), rule
    assert "contact current check" in r["current-over-contact"].notes[0]


def test_no_voltage_anywhere_is_not_checked_not_pass() -> None:
    r = results(strip_data(ready(base())))
    for rule in ("connector-voltage", "wire-voltage"):
        assert r[rule].status == "not_checked", rule
        assert any("No interface has a voltage yet" in n for n in r[rule].notes), rule


def test_no_emc_class_is_not_checked_not_pass() -> None:
    r = results(ready(base()))
    for rule in ("emc-mixed", "emc-class-split"):
        assert r[rule].status == "not_checked", rule
        assert any("No interface type has an EMC class yet" in n for n in r[rule].notes), rule


def test_each_rule_gets_one_note_and_the_note_is_a_plain_info_finding() -> None:
    notes = [f for f in drc.run(strip_data(ready(base()))) if f.rule == "unchecked-config"]
    titles = [f.title for f in notes]
    assert len(titles) == len(set(titles))
    assert all(f.severity == "info" for f in notes)
    assert sum("did not run" in t for t in titles) == 8


def test_with_the_data_present_the_rules_pass_as_before() -> None:
    p = ready(base())
    set_cfg(p, "emc", conflicting_class_pairs=[["A", "B"]], same_class_one_bundle=True)
    for k, i in list(p.interfaces.items()):
        p.interfaces[k] = i.model_copy(update={"max_current_a": 0.1, "voltage_v": 5.0})
    p.interface_types = {
        k: t.model_copy(update={"emc_class": "A"}) for k, t in p.interface_types.items()
    }
    findings = drc.run(p)
    assert not [f for f in findings if f.rule == "unchecked-config" and "did not run" in f.title]
    r = results(p)
    assert r["emc-mixed"].status == "pass"
    assert r["emc-class-split"].status in ("pass", "fail")  # it ran
    assert not [n for x in r.values() for n in x.notes if "did not run" in n]


def test_placeholder_values_stay_pending_and_raise_no_extra_note() -> None:
    p = strip_data(base())  # configuration still placeholder
    assert not [f for f in drc.run(p) if "did not run" in f.title and f.rule == "unchecked-config"]
    r = results(p)
    for rule in (*WIRE_RULES, "connector-voltage", "emc-mixed"):
        assert r[rule].status == "pending", rule


def test_an_empty_project_has_nothing_to_report() -> None:
    p = ready(base())
    p.interfaces.clear()
    p.harnesses.clear()
    assert not [f for f in drc.run(p) if f.title.startswith("No interface has a")]


# ---- F-03 ----------------------------------------------------------------------------------------


def bare_wires(p: Project, n: int) -> tuple[str, int]:
    """Take the interface off the first `n` wires of the first harness with enough wires."""
    h = next(h for h in sorted(p.harnesses.values(), key=lambda x: x.id) if len(h.wires) >= n)
    wires = [w.model_copy(update={"interface_id": None}) if k < n else w
             for k, w in enumerate(h.wires)]  # fmt: skip
    p.harnesses[h.id] = h.model_copy(update={"wires": wires})
    return h.id, n


def test_wires_without_an_interface_say_which_checks_did_not_run() -> None:
    p = ready(base())
    hid, n = bare_wires(p, 3)
    note = [f for f in drc.run(p) if f.rule == "unchecked-config" and "no interface" in f.title]
    assert len(note) == 1
    assert f"{n} wire(s) of harness {hid}" in note[0].title
    assert "Current, voltage-drop and bundle checks did not run" in note[0].title
    r = results(p)
    for rule in ("current-over-wire", "voltage-drop", "bundle-current"):
        assert any("no interface" in x for x in r[rule].notes), rule


def test_hand_made_wires_get_the_note_even_while_values_are_placeholders() -> None:
    p = base()
    bare_wires(p, 2)
    assert [f for f in drc.run(p) if f.rule == "unchecked-config" and "no interface" in f.title]


def test_wires_with_interfaces_raise_no_such_note() -> None:
    assert not [f for f in drc.run(ready(base())) if "have no interface" in f.title]
    assert len(drc.RULES) == 39


# ---- B-16: a harness with a connector and no wires can be exported with its drawings ------------


def test_a_harness_with_a_connector_and_no_wires_exports_with_drawings() -> None:
    from harness_design_studio.core.model import Connector, Harness, Pin, Unit
    from harness_design_studio.core.outputs.build import build_outputs
    from harness_design_studio.core.outputs.verify import verify_outputs
    from harness_design_studio.core.samples import new_project

    p = new_project("zero")
    p.units["A"] = Unit(id="A", name="A", subsystem="s", side="nominal")
    pins = [Pin(id=str(i)) for i in range(1, 10)]
    p.connectors["A-J01"] = Connector(
        id="A-J01", name="J01", role="box", part_id="EX-MICROD-9-F", unit_id="A",
        gender="female", pins=list(pins),
    )  # fmt: skip
    cable = Connector(
        id="W001-P1", name="P1", role="cable", part_id="EX-MICROD-9-M", gender="male",
        mates_with="A-J01", pins=list(pins),
    )  # fmt: skip
    p.harnesses["W001"] = Harness(id="W001", name="empty harness", connectors=[cable])
    files = build_outputs(p, drawings=True).files
    issues = [i for i in verify_outputs(p, files).issues if i.code == "out_drawing"]
    assert issues == []
