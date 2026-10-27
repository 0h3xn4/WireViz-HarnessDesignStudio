"""Projects with links for the tests of release 1.9 (W3): a seeded generator for the property tests
and a big one for the scaling test. Example names only; no engineering data."""

import random

from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.links import plan_add_link
from harness_design_studio.core.model import Connector, Part, Pin, Project, Unit
from harness_design_studio.core.samples import mini3

# Signal names a real pinout has: counterparts, same-name pairs, power, analog, names with a
# prefix, names with no transmit or receive word, and pins with no name at all.
VOCABULARY = (
    "TX", "RX", "TXD", "RXD", "UART_TX", "UART_RX", "TX+", "TX-", "RX+", "RX-", "TX_P", "TX_N",
    "RX_P", "RX_N", "SPW_DOUT+", "SPW_DIN+", "SPW_DOUT-", "SPW_DIN-", "MOSI", "MISO", "SDO", "SDI",
    "SCK", "CS", "PWR", "RTN", "GND", "CANH", "CANL", "SIG+", "SIG-", "HTR+", "HTR-", "FIRE+",
    "FIRE-", "SCL", "SDA", "D+", "D-", "CLK", "RESET", "tx", "Rx", "", "",
)  # fmt: skip
ROLES = ("", "", "", "", "power", "return", "ground", "signal", "spare", "shield")


def _part(pins: int) -> Part:
    return Part(id=f"GEN-{pins}", category="connector", pin_count=pins, description="generated")


def generated_project(
    seed: int,
    *,
    devices: int = 5,
    connectors_per_device: int = 2,
    pins: int = 8,
    links: int = 4,
    directions: bool = False,
) -> Project:
    """A project of `devices` devices with `connectors_per_device` connectors of up to `pins` pins
    each, named at random from `VOCABULARY` (about half of the connectors mirror the names of
    another one, so pairs exist), and up to `links` links made with the proposal. With
    `directions` some pins get a direction of their own."""
    rng = random.Random(seed)
    p = mini3()
    p.harnesses.clear()
    p.interfaces.clear()
    p.links.clear()
    p.connectors.clear()
    p.units.clear()
    p.placements.clear()
    part = _part(pins)
    p.parts[part.id] = part
    made: list[list[str]] = []
    for d in range(devices):
        uid = f"D{d + 1}"
        p.units[uid] = Unit(id=uid, name=f"Device {d + 1}", subsystem="generated")
        for k in range(connectors_per_device):
            if made and rng.random() < 0.5:
                base = rng.choice(made)
                names = [n if rng.random() < 0.85 else rng.choice(VOCABULARY) for n in base]
            else:
                names = [rng.choice(VOCABULARY) for _ in range(rng.randint(2, pins))]
            made.append(names)
            cid = f"{uid}-J{k + 1:02d}"
            built = []
            for n, name in enumerate(names):
                role = rng.choice(ROLES) if rng.random() < 0.2 else ""
                way = (
                    rng.choice(("in", "out", "bidir")) if directions and rng.random() < 0.5 else ""
                )
                built.append(Pin(id=str(n + 1), signal=name or None, role=role, direction=way))  # type: ignore[arg-type]
            p.connectors[cid] = Connector(
                id=cid, name=f"J{k + 1:02d}", role="box", part_id=part.id, unit_id=uid,
                gender="female", pins=built,
            )  # fmt: skip
    ids = sorted(p.connectors)
    for _ in range(links * 3):
        if len(p.links) >= links:
            break
        a, b = rng.sample(ids, 2)
        if p.connectors[a].unit_id == p.connectors[b].unit_id:
            continue
        ops, _lid = plan_add_link(p, a, b)
        apply_ops(p, ops)
    return p


def big_link_project(pairs: int, links: int = 1) -> Project:
    """Two devices joined by `links` links of `pairs` pairs each (a connector of `pairs` pins at
    each end per link), the names equal at both ends. The links are made, no harness yet."""
    p = mini3()
    p.harnesses.clear()
    p.interfaces.clear()
    p.links.clear()
    p.connectors.clear()
    p.units.clear()
    p.placements.clear()
    part = _part(pairs)
    p.parts[part.id] = part
    for uid in ("A", "B"):
        p.units[uid] = Unit(id=uid, name=f"Device {uid}", subsystem="generated")
    for k in range(links):
        for uid in ("A", "B"):
            cid = f"{uid}-J{k + 1:02d}"
            p.connectors[cid] = Connector(
                id=cid, name=f"J{k + 1:02d}", role="box", part_id=part.id, unit_id=uid,
                gender="female", pins=[Pin(id=str(n + 1), signal=f"S{n + 1}") for n in range(pairs)],
            )  # fmt: skip
        ops, _lid = plan_add_link(p, f"A-J{k + 1:02d}", f"B-J{k + 1:02d}")
        apply_ops(p, ops)
    return p
