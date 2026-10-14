"""Rebuild the example projects shipped with the tool (`harness-design-studio new --list`).

The projects are made with the tool's own editing functions, so they are valid by construction and
always in the current file format. Run `python -m tools.build_examples` after changing a sample or
the file format; a test fails while the shipped folders differ from what this script writes.
The hand-written templates next to them (`templates/`) are not touched.
"""

import shutil
import sys
from pathlib import Path

from harness_design_studio.core import drc, edit
from harness_design_studio.core.commands import History
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Project, evolve
from harness_design_studio.core.samples import new_project, sat15

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src" / "harness_design_studio" / "resources" / "examples" / "projects"

# name -> (title, one line shown by `harness-design-studio new --list`)
PROJECTS = {
    "blank": ("My project", "An empty project: the starter parts and interface types, no units."),
    "first-steps": (
        "First steps: reaction wheel link",
        "Three units, a power link and an RS-422 link. Nothing is generated yet: start here.",
    ),
    "minimal-satellite": (
        "Minimal satellite",
        "Seven units, nominal only: power, computer, radio, wheel and sun sensor. Adapt it.",
    ),
    "small-satellite": (
        "Small satellite (reference)",
        "14 units with nominal and redundant chains. Generate it to see a realistic system.",
    ),
    "flatsat": (
        "Flatsat (EXAMPLE numbers, not engineering data)",
        "A complete bench: 23 flight and ground units, generated, with example numbers.",
    ),
}


def _blank() -> Project:
    return new_project(PROJECTS["blank"][0])


def _first_steps() -> Project:
    p = new_project(PROJECTS["first-steps"][0])
    p.meta = evolve(
        p.meta,
        description="Power control unit, on-board computer and a reaction wheel. "
        "Generate the harnesses to see what the tool makes of two interfaces.",
    )
    history = History(p)
    for template, lane, y in (("power", 0, 40.0), ("computer", 0, 280.0), ("actuator", 1, 150.0)):
        ops, _ = edit.ops_add_unit(p, template, edit.lane_x(lane), y)
        history.execute("add unit", ops)
    for type_id, a, b in (("power_primary", "PCDU1", "RW1"), ("rs422", "OBC1", "RW1")):
        ops, iid = edit.ops_add_interface(p, type_id, a, b)
        history.execute("add interface", ops)
        if type_id == "power_primary":
            history.execute("set current", edit.ops_update_interface(p, iid, max_current_a=2.0))
    return p


def _minimal_satellite() -> Project:
    p = new_project(PROJECTS["minimal-satellite"][0])
    p.meta = evolve(
        p.meta,
        description="A small spacecraft without redundancy: solar array, battery, power control unit, "
        "on-board computer, transceiver, one reaction wheel and a sun sensor. "
        "Copy it, then rename, add and remove units to describe your own spacecraft.",
    )
    history = History(p)
    units = (
        ("solar_array", 0, 40.0), ("battery", 0, 200.0), ("pdu", 0, 360.0), ("computer_xl", 0, 520.0),
        ("transceiver", 1, 40.0), ("actuator", 1, 200.0), ("sun_sensor", 1, 360.0),
    )  # fmt: skip
    for template, lane, y in units:
        ops, _ = edit.ops_add_unit(p, template, edit.lane_x(lane), y)
        history.execute("add unit", ops)
    sa, bat, pcdu, obc, trx, rw, ss = (
        sorted(u for u in p.units if u.startswith(prefix))[0]
        for prefix in ("SA", "BAT", "PCDU", "OBC", "TRX", "RW", "SS")
    )
    wiring = (
        ("power_primary", sa, pcdu, 3.0), ("power_primary", bat, pcdu, 5.0),
        ("power_primary", pcdu, obc, 1.0), ("power_primary", pcdu, trx, 2.0),
        ("power_primary", pcdu, rw, 2.0), ("power_primary", pcdu, ss, 0.2),
        ("can", obc, pcdu, None), ("can", obc, rw, None), ("rs422", obc, trx, None),
        ("analog", obc, ss, None), ("can", obc, bat, None),
    )  # fmt: skip
    for type_id, a, b, current in wiring:
        ops, iid = edit.ops_add_interface(p, type_id, a, b)
        history.execute("add interface", ops)
        if current is not None:
            history.execute("set current", edit.ops_update_interface(p, iid, max_current_a=current))
        if (
            type_id == "power_primary"
        ):  # example value, so that the diagram shows what a rail delivers
            history.execute("set voltage", edit.ops_update_interface(p, iid, voltage_v=28.0))
    history.execute("arrange", edit.ops_arrange(p))
    return p


# (id, template, lane, y, name, notes) per unit of the flatsat, in reading order
_FLATSAT_UNITS: tuple[tuple[str, str, int, float, str, str], ...] = (
    ("SCOE1", "computer_xl", 0, 40, "Checkout system (SCOE)", "EGSE: sends commands, records telemetry. Ground equipment, never flies."),
    ("GPSU1", "power", 0, 300, "Ground power supply", "EGSE: replaces the launch umbilical on the bench. Ground equipment."),
    ("RFSU1", "payload", 0, 520, "RF test equipment", "EGSE: closes the RF link by cable instead of antennas. Ground equipment."),
    ("OBC1", "computer_xl", 1, 40, "On-board computer", "Engineering model. One spare data connector is left for your own additions."),
    ("RIU1", "computer_xl", 1, 280, "Remote interface unit", "Collects the analog, discrete and thermistor signals so that the computer needs fewer connectors."),
    ("PCDU1", "pdu", 1, 520, "Main power control and distribution unit", "Receives ground power, solar array and battery; feeds the bus and the AOCS distribution unit."),
    ("BAT1", "battery", 1, 760, "Battery", "Engineering model or battery simulator."),
    ("SA1", "solar_array", 1, 900, "Solar array simulator", "Replaces the solar array on the bench."),
    ("TRX1", "transceiver", 1, 1040, "S-band transceiver", "Its antenna port goes to the RF test equipment."),
    ("PDU2", "pdu", 2, 40, "AOCS power distribution unit", "Feeds wheels, star trackers, sun sensors and the magnetorquer; also one heater line."),
    ("RW1", "actuator", 2, 280, "Reaction wheel 1", "Wheels 1 to 4 form a pyramid."),
    ("RW2", "actuator", 2, 410, "Reaction wheel 2", ""),
    ("RW3", "actuator", 2, 540, "Reaction wheel 3", ""),
    ("RW4", "actuator", 2, 670, "Reaction wheel 4", ""),
    ("ST1", "sensor", 2, 800, "Star tracker 1", ""),
    ("ST2", "sensor", 2, 930, "Star tracker 2", ""),
    ("SS1", "sun_sensor", 2, 1060, "Sun sensor 1", ""),
    ("SS2", "sun_sensor", 2, 1190, "Sun sensor 2", ""),
    ("MTQ1", "magnetorquer", 2, 1320, "Magnetorquer system", "Driver electronics for the three coils, one unit."),
    ("PL1", "payload", 3, 40, "Imager payload", "Data over Ethernet to the computer, test interface over RS-422 to the checkout system."),
    ("HTR1", "heater_panel", 3, 300, "Heater panel 1", ""),
    ("HTR2", "heater_panel", 3, 430, "Heater panel 2", ""),
    ("PYRO1", "pyro", 3, 560, "Deployment pyro unit", "On the bench the pyro lines go to a simulator, not to initiators."),
)  # fmt: skip

# (type, from, to, name, max current in A or None); a link is made in this order
_FLATSAT_LINKS: tuple[tuple[str, str, str, str, float | None], ...] = (
    ("power_primary", "GPSU1", "PCDU1", "Ground power to PCDU", 5.0),
    ("power_primary", "SA1", "PCDU1", "Solar array to PCDU", 4.0),
    ("power_primary", "BAT1", "PCDU1", "Battery to PCDU", 5.0),
    ("power_primary", "PCDU1", "OBC1", "Power for the computer", 1.5),
    ("power_primary", "PCDU1", "RIU1", "Power for the remote interface unit", 0.5),
    ("power_primary", "PCDU1", "TRX1", "Power for the transceiver", 2.0),
    ("power_primary", "PCDU1", "PL1", "Power for the payload", 3.0),
    ("power_primary", "PCDU1", "PYRO1", "Power for the pyro unit", 0.3),
    ("power_primary", "PCDU1", "PDU2", "Feed of the AOCS distribution unit", 5.0),
    ("power_primary", "PDU2", "RW1", "Power for wheel 1", 0.8),
    ("power_primary", "PDU2", "RW2", "Power for wheel 2", 0.8),
    ("power_primary", "PDU2", "RW3", "Power for wheel 3", 0.8),
    ("power_primary", "PDU2", "RW4", "Power for wheel 4", 0.8),
    ("power_primary", "PDU2", "ST1", "Power for star tracker 1", 0.3),
    ("power_primary", "PDU2", "ST2", "Power for star tracker 2", 0.3),
    ("power_primary", "PDU2", "SS1", "Power for sun sensor 1", 0.05),
    ("power_primary", "PDU2", "SS2", "Power for sun sensor 2", 0.05),
    ("power_primary", "PDU2", "MTQ1", "Power for the magnetorquer system", 0.6),
    ("heater", "PCDU1", "HTR1", "Heater line 1", 0.5),
    ("heater", "PDU2", "HTR2", "Heater line 2", 0.5),
    ("rs422", "SCOE1", "GPSU1", "Control of the ground power supply", None),
    ("ethernet", "SCOE1", "OBC1", "Commands and telemetry from the checkout system", None),
    ("rs422", "SCOE1", "PL1", "Payload test interface", None),
    ("ethernet", "SCOE1", "RFSU1", "Control of the RF test equipment", None),
    ("rf_coax", "TRX1", "RFSU1", "RF link by cable", None),
    ("can", "OBC1", "PCDU1", "PCDU housekeeping", None),
    ("can", "OBC1", "PDU2", "AOCS distribution housekeeping", None),
    ("can", "OBC1", "RIU1", "Remote interface unit bus", None),
    ("can", "OBC1", "RW1", "Wheel 1 bus", None),
    ("can", "OBC1", "RW2", "Wheel 2 bus", None),
    ("can", "OBC1", "RW3", "Wheel 3 bus", None),
    ("can", "OBC1", "RW4", "Wheel 4 bus", None),
    ("rs422", "OBC1", "TRX1", "Transceiver data", None),
    ("rs422", "OBC1", "ST1", "Star tracker 1 data", None),
    ("rs422", "OBC1", "ST2", "Star tracker 2 data", None),
    ("ethernet", "OBC1", "PL1", "Payload data", None),
    ("can", "RIU1", "BAT1", "Battery monitoring", None),
    ("analog", "RIU1", "SS1", "Sun sensor 1 signal", None),
    ("analog", "RIU1", "SS2", "Sun sensor 2 signal", None),
    ("discrete", "RIU1", "MTQ1", "Magnetorquer drive", None),
    ("discrete", "RIU1", "PYRO1", "Pyro arm and fire", None),
    ("thermistor", "RIU1", "HTR1", "Panel 1 temperature", None),
    ("thermistor", "RIU1", "HTR2", "Panel 2 temperature", None),
    ("thermistor", "RIU1", "SA1", "Array temperature", None),
)  # fmt: skip


def _flatsat() -> Project:
    """A complete flatsat: the flight units of a small spacecraft on a table, with the ground
    equipment around them, generated, with EXAMPLE numbers filled in (see `_demo_values`)."""
    from harness_design_studio.core.commands import Put, SetZones
    from harness_design_studio.core.generate.engine import generate_project

    p = new_project(PROJECTS["flatsat"][0])
    p.meta = evolve(
        p.meta,
        description="A flatsat: the electronics of a small spacecraft laid out on a bench, with the "
        "ground equipment (checkout system, power supply, RF equipment) that drives them. "
        "Generated, with example numbers filled in so that every output has content. "
        "The numbers and parts are for learning only.",
    )
    history = History(p)
    history.execute("zones", [SetZones(("egse", "bus", "aocs", "payload"))])
    for uid, template, lane, y, name, notes in _FLATSAT_UNITS:
        ops, _ = edit.ops_add_unit(p, template, edit.lane_x(lane), y, unit_id=uid, name=name)
        history.execute("add unit", ops)
        extra = {"subsystem": "egse"} if lane == 0 else {}
        history.execute("describe", [Put("units", evolve(p.units[uid], notes=notes, **extra))])
    for type_id, a, b, name, current in _FLATSAT_LINKS:
        ops, iid = edit.ops_add_interface(p, type_id, a, b, name=name)
        history.execute("add interface", ops)
        if current is not None:
            history.execute("set current", edit.ops_update_interface(p, iid, max_current_a=current))
        if (
            type_id == "power_primary"
        ):  # example value, so that the diagram shows what a rail delivers
            history.execute("set voltage", edit.ops_update_interface(p, iid, voltage_v=28.0))
    history.execute("arrange", edit.ops_arrange(p))  # no overlaps, ordered to shorten links
    _demo_values(p)
    generate_project(p)
    _demo_lengths(p)
    generate_project(p)
    errors = [f for f in drc.run(p) if f.severity == "error"]
    if errors:  # an example must open without errors
        raise SystemExit(f"flatsat has {len(errors)} design rule errors, first: {errors[0].title}")
    return p


def _demo_values(p: Project) -> None:
    """EXAMPLE engineering values, invented for the demonstration. The configuration files stay
    marked as placeholders, so every result built on them still says so."""
    from harness_design_studio.core.commands import Put, apply_ops
    from harness_design_studio.core.model.config import ConfigFile

    def cfg(name: str, **values: object) -> None:
        old = p.config[name]
        p.config[name] = ConfigFile(
            name=name, placeholder=old.placeholder, values={**old.values, **values}
        )

    cfg("segmentation", mode="per_zone_pair")  # links between two zones share one bundle
    cfg("derating", ampacity_a_by_awg={"26": 1.0, "24": 2.0, "22": 3.0, "20": 5.0, "18": 7.0, "16": 10.0},
        bundle_derating=0.6, temperature_derating=0.9, contact_current_factor=0.5, max_voltage_drop_v=1.0)  # fmt: skip
    cfg(
        "generation",
        wire_colour_by_signal={"PWR": "red", "RTN": "black", "CANH": "yellow", "CANL": "green"},
    )  # EXAMPLE colours, drawn on the harness drawing
    cfg("generation", conductor_resistivity_ohm_m=1.7e-8, service_loop_m=0.1, shield_end_a="backshell_360",
        shield_end_b="floating", mass_margin_fraction=0.1, test_continuity_max_ohm=1.0,
        test_isolation_min_mohm=100.0, test_isolation_voltage_v=500.0)  # fmt: skip
    for part in list(p.parts.values()):
        if part.category == "connector":
            apply_ops(
                p, [Put("parts", evolve(part, mass_g=12.0, ratings={"contact_current_a": 12.0}))]
            )
        elif part.category == "wire":
            apply_ops(p, [Put("parts", evolve(part, mass_per_m_g=4.0))])


def _demo_lengths(p: Project) -> None:
    """EXAMPLE segment lengths in metres: short on the bench, longer towards the ground equipment."""
    from harness_design_studio.core.commands import Put, apply_ops
    from harness_design_studio.core.model import Segment

    for h in list(p.harnesses.values()):
        segs = [
            Segment(
                id=g.id, from_node=g.from_node, to_node=g.to_node, length_m=0.5 + 0.25 * (k % 8)
            )
            for k, g in enumerate(h.segments)
        ]
        apply_ops(p, [Put("harnesses", evolve(h, segments=segs))])


def _small_satellite() -> Project:
    p = sat15()
    p.meta = evolve(
        p.meta,
        name=PROJECTS["small-satellite"][0],
        description="Redundant computer and power unit, battery, solar array, transceiver, payload, "
        "star tracker, two wheels, sun sensor, magnetorquer and a heater panel.",
    )
    History(p).execute("arrange", edit.ops_arrange(p))  # tall units must not overlap in expert mode
    return p


BUILDERS = {
    "blank": _blank,
    "first-steps": _first_steps,
    "minimal-satellite": _minimal_satellite,
    "small-satellite": _small_satellite,
    "flatsat": _flatsat,
}


def build(target: Path = TARGET) -> None:
    for name, make in BUILDERS.items():
        folder = target / name
        # built next to the old folder and swapped in, so a failure leaves the old example alone
        fresh = target / f".{name}.new"
        if fresh.exists():
            shutil.rmtree(fresh)
        try:
            save_project(make(), fresh)
            for stray in fresh.rglob("*.bak"):
                stray.unlink()
            if folder.exists():
                shutil.rmtree(folder)
            fresh.rename(folder)
        finally:
            shutil.rmtree(fresh, ignore_errors=True)


def main() -> int:
    build()
    print(f"example projects written to {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
