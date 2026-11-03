"""D-191, S2: the registry of settings is complete, no model constant hides in the code, and a
setting changes the result and its explanation (the defaults reproduce today's numbers: the numbers
snapshot says so)."""

import ast
import re
from pathlib import Path

import pytest

from harness_design_studio.core import configcheck, settings, templates
from harness_design_studio.core.derive import explain_wire
from harness_design_studio.core.drc import run as run_drc
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.generate.lengths import wire_length
from harness_design_studio.core.generate.sizing import voltage_drop_v
from harness_design_studio.core.model import ConfigFile, Project
from harness_design_studio.core.model.config import default_configs

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "harness_design_studio"


# ---- the registry is complete --------------------------------------------------------------


def _known_keys() -> set[tuple[str, str]]:
    keys = {(f, k) for f, c in default_configs().items() for k in c.values}
    keys |= {(n.file, n.key) for n in configcheck.NEEDS + configcheck.OPTIONAL_NEEDS}
    keys |= set(configcheck.FIELD_INFO)
    return keys


def test_every_key_the_tool_knows_is_a_registered_setting() -> None:
    missing = [k for k in _known_keys() if settings.setting(*k) is None]
    assert not missing, missing
    assert len({s.id for s in settings.SETTINGS}) == len(settings.SETTINGS)  # no key twice


def test_every_key_of_the_reference_page_is_registered_and_every_setting_is_documented() -> None:
    text = (ROOT / "docs" / "CONFIG.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^\| `([a-z_0-9]+)`", text, re.M))
    documented |= {
        k
        for ks in re.findall(r"^\| ((?:`[a-z_0-9]+`(?:, )?)+) \|", text, re.M)
        for k in re.findall(r"`([a-z_0-9]+)`", ks)
    }
    registered = {s.key for s in settings.SETTINGS}
    # the page has rows that are not keys (a part rating, a table column): only the registered keys matter
    absent = sorted(k for k in registered if k not in documented and k not in text)
    assert not absent, f"not described in docs/CONFIG.md: {absent}"


def test_each_setting_says_what_it_is() -> None:
    for s in settings.SETTINGS:
        assert s.label and s.what and s.used_by and s.source and s.range, s.id
        assert s.kind in {"number", "whole", "choice", "flag", "table", "pairs", "names", "text"}
        if s.assumption:
            from harness_design_studio.core.assumptions import ASSUMPTIONS

            assert s.assumption in ASSUMPTIONS, s.id
        if s.kind == "choice":
            assert s.choices, s.id
    ids = [d.id for d in settings.DEFINITIONS]
    assert len(ids) == len(set(ids))


# ---- no model constant hides in the code ----------------------------------------------------

# Every number other than 0, 1, 2 and -1 in the modules that calculate, with why it is not a setting.
# A number that is not here fails the test (add it to the registry, or here with its reason); a
# line here that no longer matches fails it too, so the list cannot go stale.
CALCULATION_MODULES = (
    "core/generate/sizing.py", "core/generate/lengths.py", "core/generate/mass.py",
    "core/generate/pins.py", "core/generate/segmentation.py", "core/generate/engine.py",
    "core/generate/wiring.py", "core/drc/rules.py", "core/drc/standard_rules.py",
    "core/outputs/tables.py", "core/units.py", "core/derive.py", "core/pairing.py",
    "core/routing.py", "core/derive_export.py", "core/derive_build.py", "core/derive_layout.py",
    "core/derive_rules.py", "core/generate/shields.py",
)  # fmt: skip
_AWG = "definition D-AWG (gauges 0 to 40, the AWG formula)"
_TICK = "a progress fraction of the progress bar: no result depends on it"
_SHOWN = "how many names a message shows: no result depends on it"
_GEOMETRY = "geometry of the drawn router: no engineering value depends on it"
EXEMPT: dict[tuple[str, float], str] = {
    ("core/derive.py", 1e-06): "unit conversion mm2 to m2",
    ("core/derive.py", 1e-09): "definition D-LIMIT-TOLERANCE (the tolerance of a float comparison)",
    ("core/derive.py", 6): _SHOWN,
    ("core/derive_build.py", 8): _SHOWN,
    ("core/derive_layout.py", 8): _SHOWN,
    ("core/derive_rules.py", 8): _SHOWN,
    ("core/drc/rules.py", 3): "a position in a sort key tuple",
    ("core/drc/rules.py", 4): "a position in a sort key tuple",
    ("core/drc/rules.py", 40): _AWG,
    ("core/derive_export.py", 3): "the format number of derivations.json (format 3, S5)",
    ("core/drc/rules.py", 6): "the length of the hash prefix that makes a finding ID",
    ("core/drc/standard_rules.py", 1000): "the largest pin count of the file format",
    ("core/generate/engine.py", 0.02): _TICK,
    ("core/generate/engine.py", 0.05): _TICK,
    ("core/generate/engine.py", 0.15): _TICK,
    ("core/generate/engine.py", 0.2): _TICK,
    ("core/generate/engine.py", 0.7): _TICK,
    ("core/generate/engine.py", 0.95): _TICK,
    ("core/generate/engine.py", 3): _SHOWN,
    ("core/generate/engine.py", 40): _AWG,
    (
        "core/generate/lengths.py",
        0.001,
    ): "definition of the unit: metres in one mm (docs/models/import-units.md)",
    (
        "core/generate/lengths.py",
        0.01,
    ): "definition of the unit: metres in one cm (docs/models/import-units.md)",
    (
        "core/generate/lengths.py",
        0.0254,
    ): "definition of the unit: metres in one inch (docs/models/import-units.md)",
    (
        "core/generate/lengths.py",
        0.3048,
    ): "definition of the unit: metres in one foot (docs/models/import-units.md)",
    ("core/generate/lengths.py", 10000.0): "definition D-IMPORT-LENGTH-BOUND",
    ("core/generate/lengths.py", 3): _SHOWN,
    ("core/generate/lengths.py", 512): "size of a cache: no result depends on it",
    ("core/generate/lengths.py", 9): "definition D-DATA-ROUNDING (9 decimals)",
    ("core/generate/mass.py", 1000): "definition D-MM-TO-M",
    ("core/generate/sizing.py", 1e-06): "unit conversion mm2 to m2",
    ("core/generate/sizing.py", 1e-09): "definition D-LIMIT-TOLERANCE",
    ("core/generate/sizing.py", 40): _AWG,
    ("core/outputs/tables.py", 1000): "definition D-MM-TO-M",
    ("core/outputs/tables.py", 8): "the position of a column in the BOM header",
    ("core/outputs/tables.py", 9): "definition D-DATA-ROUNDING",
    ("core/pairing.py", 6): _SHOWN,
    ("core/routing.py", 12.0): _GEOMETRY,
    ("core/routing.py", 14.0): _GEOMETRY,
    ("core/routing.py", 16.0): _GEOMETRY,
    ("core/routing.py", 18.0): _GEOMETRY,
    ("core/routing.py", 40): _GEOMETRY,
    ("core/routing.py", 6): _GEOMETRY,
    ("core/units.py", 0.127): _AWG,
    ("core/units.py", 36): _AWG,
    ("core/units.py", 39): _AWG,
    ("core/units.py", 4): "the 4 of pi/4 x d2, the area of a circle",
    ("core/units.py", 40): _AWG,
    ("core/units.py", 92): _AWG,
}


def _literals() -> set[tuple[str, float]]:
    found: set[tuple[str, float]] = set()
    for rel in CALCULATION_MODULES:
        tree = ast.parse((SRC / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, int | float)
                and not isinstance(node.value, bool)
                and node.value not in (0, 1, 2, -1)
            ):
                found.add((rel, node.value))
    return found


def test_no_number_hides_in_the_calculation_modules() -> None:
    found = _literals()
    assert found - set(EXEMPT) == set(), "a number in the code that is neither a setting nor listed"
    assert set(EXEMPT) - found == set(), "a listed number that is no longer in the code"


def test_the_conductors_counted_and_the_service_loops_are_not_in_the_code_any_more() -> None:
    for rel, what in (
        ("core/generate/engine.py", "2 * loop"),
        ("core/drc/rules.py", 'in ("power", "ground")'),
        ("core/derive.py", 'in ("power", "ground")'),
    ):
        assert what not in (SRC / rel).read_text(encoding="utf-8"), (rel, what)


# ---- a setting changes the result and its explanation ---------------------------------------


@pytest.fixture
def flat(tmp_path: Path) -> Project:
    return templates.create_project(tmp_path / "flat", "flatsat")


def _with_model(project: Project, **values: object) -> None:
    project.config["model"] = ConfigFile(name="model", placeholder=False, values=dict(values))


def test_the_defaults_are_what_the_tool_did_before(flat: Project) -> None:
    assert (
        settings.drop_conductors(flat, "power") == 2
        and settings.drop_conductors(flat, "ground") == 2
    )
    assert settings.drop_conductors(flat, "data") == 1 and settings.service_loops(flat) == 2
    assert settings.effective(flat, "model", "service_loops_per_wire").origin == "default"
    assert settings.effective(flat, "derating", "bundle_derating").origin == "project"
    assert settings.effective(flat, "derating", "spare_pin_fraction").origin == "unset"


def test_the_service_loops_setting_changes_the_length_and_says_so(flat: Project) -> None:
    h = flat.harnesses["W001"]
    wire = h.wires[0]
    assert wire.length_m == 3.45  # segments 3.25 m and two loops of 0.1 m
    _with_model(flat, service_loops_per_wire=0)
    assert not [i for i in configcheck.validate(flat) if (i.object_id or "").startswith("model.")]
    generate_project(flat)
    again = next(w for w in flat.harnesses["W001"].wires if w.id == wire.id)
    assert again.length_m == 3.25
    length = explain_wire(flat, wire.id)[0]
    assert length.value == 3.25 and "0 × service loop" in length.equation
    assert any(s.label.startswith("Service loops (0)") for s in length.steps)


def test_the_return_path_setting_changes_the_drop_in_the_rule_and_in_the_explanation(
    flat: Project,
) -> None:
    power = next(
        w for h in flat.harnesses.values() for w in h.wires
        if flat.interfaces[w.interface_id or ""].max_current_a and w.gauge_awg
        and flat.interface_types[flat.interfaces[w.interface_id or ""].type_id].category == "power"
    )  # fmt: skip
    base = explain_wire(flat, power.id)[2]
    assert base.value is not None
    _with_model(flat, return_path_conductors=1)
    once = explain_wire(flat, power.id)[2]
    assert once.value is not None and abs(once.value * 2 - base.value) < 1e-9
    i = flat.interfaces[power.interface_id or ""]
    h = next(h for h in flat.harnesses.values() if power in h.wires)
    rho = flat.config["generation"].values["conductor_resistivity_ohm_m"]
    assert once.value == voltage_drop_v(
        i.max_current_a or 0, rho, wire_length(h, power) or 0, power.gauge_awg or 0, 1
    )
    # a project whose rule would now pass: the limit is what decides, and the rule reads the same setting
    findings = {f.object_id for f in run_drc(flat) if f.rule == "voltage-drop"}
    assert (power.id in findings) == (not once.check.passes if once.check else False)


def test_a_wrong_model_setting_is_refused_with_its_name(flat: Project) -> None:
    _with_model(flat, service_loops_per_wire=9, nonsense=1, return_path_categories="power")
    messages = [
        i.message for i in configcheck.validate(flat) if (i.object_id or "").startswith("model.")
    ]
    assert any("service_loops_per_wire must be a whole number from 0 to 4" in m for m in messages)
    assert any("nonsense is not a setting" in m for m in messages)
    assert any("return_path_categories must be a list" in m for m in messages)


# ---- the command ----------------------------------------------------------------------------


def test_settings_lists_everything_and_says_where_each_value_comes_from(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    from harness_design_studio.cli.main import main

    templates.create_project(tmp_path / "flat", "flatsat")
    assert main(["settings", str(tmp_path / "flat")]) == 0
    text = capsys.readouterr().out
    assert "service_loops_per_wire = 2   [the tool's own default]" in text
    assert "bundle_derating = 0.6   [set by the project (placeholder: not reviewed)]" in text
    assert "A-SERVICE-LOOP (setting)" in text and "D-AWG" in text
    assert main(["settings", str(tmp_path / "flat"), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert len(doc["settings"]) == len(settings.SETTINGS) and doc["definitions"]
    by_id = {s["id"]: s for s in doc["settings"]}
    assert by_id["model.return_path_conductors"]["origin"] == "default"
    assert by_id["derating.spare_pin_fraction"]["origin"] == "unset"


def test_settings_changes_a_value_and_refuses_one_outside_its_range(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_design_studio.cli.main import main

    templates.create_project(tmp_path / "flat", "flatsat")
    flat = str(tmp_path / "flat")
    assert main(["settings", flat, "--set", "model.service_loops_per_wire=0"]) == 0
    assert (tmp_path / "flat" / "config" / "model.json").exists()
    assert main(["settings", flat, "--set", "model.service_loops_per_wire=9"]) == 1
    err = capsys.readouterr().err
    assert "must be a whole number from 0 to 4" in err and "Nothing was changed" in err
    text = (tmp_path / "flat" / "config" / "model.json").read_text(encoding="utf-8")
    assert '"service_loops_per_wire": 0' in text  # the refused value was not written
    assert main(["settings", flat, "--set", "nonsense.key=1"]) == 2
    assert main(["settings", flat, "--set", "model.service_loops_per_wire"]) == 2


def test_a_project_without_model_json_is_written_as_before(tmp_path: Path) -> None:
    from harness_design_studio.core.io.loader import load_project

    project = templates.create_project(tmp_path / "flat", "flatsat")
    assert "model" not in project.config
    assert not (tmp_path / "flat" / "config" / "model.json").exists()
    assert "model" not in load_project(tmp_path / "flat").project.config


def test_the_assumptions_window_shows_the_page_of_the_settings_command(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("PySide6")
    from harness_design_studio.gui.assumptions_dialog import AssumptionsDialog
    from harness_design_studio.gui.theme import ThemeManager

    project = templates.create_project(tmp_path / "flat", "flatsat")
    dialog = AssumptionsDialog(None, ThemeManager(), project)
    qtbot.addWidget(dialog)
    assert dialog.text.toPlainText() == settings.render(project)
    assert dialog.text.isReadOnly() and dialog.text.accessibleName()
    assert "A-ROUND-TRIP" in dialog.text.toPlainText()


def test_help_assumptions_opens_the_window(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("PySide6")
    from tests.gui_helpers import make_window

    win = make_window(tmp_path)
    qtbot.addWidget(win)
    opened: list[object] = []
    win.run_dialog = lambda d: opened.append(d)  # type: ignore[method-assign,assignment,return-value]
    win.act_assumptions.trigger()
    assert len(opened) == 1 and type(opened[0]).__name__ == "AssumptionsDialog"
    from PySide6.QtWidgets import QMenu

    help_menu = win.menuBar().actions()[-1].menu()
    assert isinstance(help_menu, QMenu) and win.act_assumptions in help_menu.actions()
