"""Reference projects. `mini3` is the minimal 3-unit example used by tests and the first-run sample."""

from .model import (
    Connector,
    Endpoint,
    Harness,
    InterfaceInstance,
    Pin,
    Placement,
    Project,
    ProjectMeta,
    Unit,
    Wire,
    evolve,
)
from .starter import starter_interface_types, starter_parts


def _pins(*signals: tuple[str, str | None]) -> list[Pin]:
    return [Pin(id=pid, signal=sig) for pid, sig in signals]


def new_project(name: str = "Untitled project") -> Project:
    """An empty project with the starter library, interface types and default lanes."""
    p = Project(meta=ProjectMeta(name=name))
    p.parts = {x.id: x for x in starter_parts()}
    p.interface_types = {x.id: x for x in starter_interface_types()}
    return p


def mini3() -> Project:
    """OBC, PCDU and a reaction wheel: one power interface, one RS-422 link, one hand-made harness."""
    p = Project(
        meta=ProjectMeta(name="mini3 (example data)", description="Minimal 3-unit example.")
    )
    p.parts = {x.id: x for x in starter_parts()}
    p.interface_types = {x.id: x for x in starter_interface_types()}
    for uid, name, sub, zone in (
        ("OBC", "On-board computer", "avionics", "panel-A"),
        ("PCDU", "Power control and distribution unit", "power", "panel-A"),
        ("RW1", "Reaction wheel 1", "aocs", "panel-B"),
    ):
        p.units[uid] = Unit(id=uid, name=name, subsystem=sub, zone=zone, side="nominal")

    def box(cid: str, unit: str, part: str, carries: list[str], pins: list[Pin]) -> Connector:
        return Connector(id=cid, name=cid.rsplit("-", 1)[1], role="box", part_id=part, unit_id=unit,
                         gender="female" if part.endswith("-F") else "male", carries=carries, pins=pins)  # fmt: skip

    data_pins = _pins(("1", None), ("2", None), ("3", None), ("4", None), ("5", None))
    pwr_pins = [
        Pin(id="1", signal="PWR", interface_id="IF-PWR-RW1"),
        Pin(id="2", signal="RTN", interface_id="IF-PWR-RW1"),
        Pin(id="3"),
    ]  # allocated by hand for the manual harness W001
    free = _pins(("1", None), ("2", None), ("3", None))
    for conn in (
        box("OBC-J01", "OBC", "EX-MICROD-25-F", ["rs422", "rs485", "can", "discrete"], data_pins),
        box("OBC-J02", "OBC", "EX-MICROD-9-F", ["power_primary"], free),
        box("OBC-J03", "OBC", "EX-MICROD-15-F", ["rs422", "can"], free),
        box("PCDU-J01", "PCDU", "EX-MICROD-9-F", ["power_primary"], pwr_pins),
        box("PCDU-J02", "PCDU", "EX-MICROD-9-F", ["power_primary"], free),
        box("PCDU-J03", "PCDU", "EX-MICROD-15-F", ["discrete", "rs422"], free),
        box("RW1-J01", "RW1", "EX-MICROD-9-M", ["power_primary"], pwr_pins),
        box("RW1-J02", "RW1", "EX-MICROD-15-M", ["rs422", "can"], data_pins),
    ):
        p.connectors[conn.id] = conn
    p.interfaces["IF-PWR-RW1"] = InterfaceInstance(
        id="IF-PWR-RW1", name="RW1 power", type_id="power_primary", redundancy="nominal",
        flow="a_to_b",
        endpoints=[Endpoint(unit_id="PCDU", connector_id="PCDU-J01"),
                   Endpoint(unit_id="RW1", connector_id="RW1-J01")],
    )  # fmt: skip
    p.interfaces["IF-TM-RW1"] = InterfaceInstance(
        id="IF-TM-RW1", name="RW1 command and telemetry", type_id="rs422", redundancy="nominal",
        flow="bidirectional",
        endpoints=[Endpoint(unit_id="OBC", connector_id="OBC-J01"),
                   Endpoint(unit_id="RW1", connector_id="RW1-J02")],
    )  # fmt: skip
    for uid, x, y, zone in (
        ("OBC", 30.0, 60.0, "panel-A"),
        ("PCDU", 30.0, 300.0, "panel-A"),
        ("RW1", 470.0, 170.0, "panel-B"),
    ):
        p.placements[uid] = Placement(id=uid, x=x, y=y)
        p.units[uid] = evolve(p.units[uid], zone=zone)
    p.harnesses["W001"] = Harness(
        id="W001", name="PCDU to RW1 power",
        connectors=[
            Connector(id="W001-P1", name="P1", role="cable", part_id="EX-MICROD-9-M", gender="male", mates_with="PCDU-J01",
                      pins=_pins(("1", "PWR"), ("2", "RTN"), ("3", None))),
            Connector(id="W001-P2", name="P2", role="cable", part_id="EX-MICROD-9-F", gender="female", mates_with="RW1-J01",
                      pins=_pins(("1", "PWR"), ("2", "RTN"), ("3", None))),
        ],
        wires=[
            Wire(id="W001-001", signal="PWR", from_connector="W001-P1", from_pin="1",
                 to_connector="W001-P2", to_pin="1", interface_id="IF-PWR-RW1"),
            Wire(id="W001-002", signal="RTN", from_connector="W001-P1", from_pin="2",
                 to_connector="W001-P2", to_pin="2", interface_id="IF-PWR-RW1"),
        ],
    )  # fmt: skip
    return p


def _run(p: Project, ops: list) -> None:  # type: ignore[type-arg]
    from .commands import History

    History(p).execute("build sample", ops)


def sat15() -> Project:
    """A realistic small satellite (example data): redundant OBC and PCDU, battery, solar array,
    transceiver, payload, star tracker, two wheels, sun sensor, magnetorquer and a heater panel."""
    from . import edit
    from .commands import SetZones

    p = new_project("sat15 (example data)")
    p.meta = evolve(p.meta, description="About 15 units with nominal and redundant chains.")
    _run(p, [SetZones(("bus", "aocs", "payload"))])
    layout: list[tuple[str, int, float]] = [  # template, lane, y
        ("computer_xl", 0, 40), ("pdu", 0, 260), ("battery", 0, 480), ("solar_array", 0, 650),
        ("star_tracker", 1, 40), ("actuator", 1, 200), ("actuator", 1, 360), ("sun_sensor", 1, 520),
        ("magnetorquer", 1, 680), ("transceiver", 2, 40), ("payload", 2, 220), ("heater_panel", 2, 400),
    ]  # fmt: skip
    for tpl, lane, y in layout:
        key = "sensor" if tpl == "star_tracker" else tpl
        ops, _ = edit.ops_add_unit(p, key, edit.lane_x(lane), y)
        _run(p, ops)
    u = {t: sorted(x for x in p.units if x.startswith(edit.TEMPLATES[t].prefix))
         for t in ("computer_xl", "pdu", "battery", "solar_array", "sensor", "actuator", "sun_sensor", "magnetorquer", "transceiver", "payload", "heater_panel")}  # fmt: skip
    obc, pcdu, bat, sa = u["computer_xl"][0], u["pdu"][0], u["battery"][0], u["solar_array"][0]
    st, rw1, rw2 = u["sensor"][0], u["actuator"][0], u["actuator"][1]
    ss, mtq, trx, pl, htr = (
        u["sun_sensor"][0],
        u["magnetorquer"][0],
        u["transceiver"][0],
        u["payload"][0],
        u["heater_panel"][0],
    )
    wiring = [
        ("power_primary", pcdu, obc), ("power_primary", pcdu, trx), ("power_primary", pcdu, pl), ("power_primary", pcdu, st),
        ("power_primary", pcdu, rw1), ("power_primary", pcdu, rw2), ("power_primary", pcdu, ss), ("power_primary", pcdu, mtq),
        ("heater", pcdu, htr), ("power_primary", bat, pcdu), ("power_primary", sa, pcdu),
        ("can", obc, pcdu), ("can", obc, bat), ("rs422", obc, trx), ("ethernet", obc, pl), ("rs422", obc, st),
        ("can", obc, rw1), ("can", obc, rw2), ("analog", obc, ss), ("discrete", obc, mtq), ("thermistor", obc, htr),
        ("thermistor", obc, sa),
    ]  # fmt: skip
    for type_id, a, b in wiring:
        ops, _iid = edit.ops_add_interface(p, type_id, a, b)
        _run(p, ops)
    for unit in (pcdu, obc):  # redundant chains for the two critical units
        result = edit.ops_redundant_copy(p, unit)
        _run(p, result.ops)
    return p


def stress_project(
    units: int = 200, interfaces: int = 2000, zones: int = 12, signals: int = 10
) -> Project:
    """Stress-size example (SPEC: 200 units, 2,000 interfaces, about 150 harnesses, 20,000 wires).

    Interfaces use one multi-core type with `signals` passive conductors, so 2,000 of them make
    20,000 wires. Zone-pair segmentation then yields a few dozen to about 150 harnesses.
    """
    from .model import InterfaceType, SignalDef

    p = new_project(f"stress ({units} units, example data)")
    zone_names = [f"zone-{k:02d}" for k in range(zones)]
    p.zones = zone_names
    p.interface_types["multicore"] = InterfaceType(
        id="multicore", name="Multi-core cable", category="discrete", construction="single",
        signals=[SignalDef(name=f"C{k + 1}", direction="passive") for k in range(signals)], unverified=True,
    )  # fmt: skip
    per_unit = -(-2 * interfaces // units) + 2  # connector ends per unit, with some slack
    pins = [Pin(id=str(k)) for k in range(1, 22)]
    for n in range(units):
        uid = f"U{n:03d}"
        p.units[uid] = Unit(id=uid, name=f"Unit {n}", subsystem=f"sub{n % 12}", zone=zone_names[n % zones], side="redundant" if n % 7 == 0 else "nominal")  # fmt: skip
        p.placements[uid] = Placement(
            id=uid, x=10 + (n % zones) * 430 + 20, y=40 + (n // zones) * 160
        )
        for k in range(per_unit):
            cid = f"{uid}-J{k + 1:02d}"
            p.connectors[cid] = Connector(id=cid, name=f"J{k + 1:02d}", role="box", part_id="EX-MDM-21-F", unit_id=uid, gender="female", carries=["multicore"], pins=pins)  # fmt: skip
    free = {uid: [f"{uid}-J{k + 1:02d}" for k in range(per_unit)] for uid in p.units}
    ids = sorted(p.units)
    made = 0
    step = 1
    while made < interfaces:
        a = ids[(made * 7) % units]
        b = ids[(made * 7 + step) % units]
        if a == b or not free[a] or not free[b]:
            step += 1
            if step > units:
                break
            continue
        ca, cb = free[a].pop(0), free[b].pop(0)
        iid = f"IF-{made + 1:04d}"
        side = p.units[a].side
        p.interfaces[iid] = InterfaceInstance(
            id=iid, name=f"link {made + 1}", type_id="multicore", redundancy=side,
            endpoints=[Endpoint(unit_id=a, connector_id=ca), Endpoint(unit_id=b, connector_id=cb)],
        )  # fmt: skip
        made += 1
        step = (step % 11) + 1
    p.config["segmentation"] = evolve(p.config["segmentation"], values={"mode": "per_zone_pair"})
    return p


def sat15_full() -> Project:
    """`sat15` generated, with EXAMPLE engineering values filled in so every output has content
    (gauges, lengths, masses). The numbers are invented for demonstration and are not engineering
    data; the project name says so."""
    from .commands import Put, apply_ops
    from .generate.engine import generate_project
    from .model import Segment
    from .model.config import ConfigFile

    p = sat15()
    p.meta = evolve(p.meta, name="sat15 full (EXAMPLE numbers, not engineering data)")

    def cfg(name: str, **values: object) -> None:
        old = p.config[name]
        p.config[name] = ConfigFile(
            name=name, placeholder=old.placeholder, values={**old.values, **values}
        )

    cfg("derating", ampacity_a_by_awg={"26": 1.0, "24": 2.0, "22": 3.0, "20": 5.0, "18": 7.0, "16": 10.0},
        bundle_derating=0.6, temperature_derating=0.9, contact_current_factor=0.5, max_voltage_drop_v=1.0)  # fmt: skip
    cfg("generation", conductor_resistivity_ohm_m=1.7e-8, service_loop_m=0.1, shield_end_a="backshell_360",
        shield_end_b="floating", mass_margin_fraction=0.1, test_continuity_max_ohm=1.0,
        test_isolation_min_mohm=100.0, test_isolation_voltage_v=500.0)  # fmt: skip
    for iface in list(p.interfaces.values()):
        category = p.interface_types[iface.type_id].category
        if category in ("power", "thermal"):
            apply_ops(
                p,
                [
                    Put(
                        "interfaces",
                        evolve(iface, max_current_a=2.0 if category == "power" else 1.0),
                    )
                ],
            )
    for part in list(p.parts.values()):
        if part.category == "connector":
            apply_ops(
                p, [Put("parts", evolve(part, mass_g=12.0, ratings={"contact_current_a": 5.0}))]
            )
        elif part.category == "wire":
            apply_ops(p, [Put("parts", evolve(part, mass_per_m_g=4.0))])
    generate_project(p)
    for h in list(p.harnesses.values()):
        segs = [
            Segment(id=g.id, from_node=g.from_node, to_node=g.to_node, length_m=1.0 + 0.25 * k)
            for k, g in enumerate(h.segments)
        ]
        apply_ops(p, [Put("harnesses", evolve(h, segments=segs))])
    generate_project(p)
    return p
