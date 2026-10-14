"""Time load/save/integrity/transaction on a stress-size project (SPEC: 200 units, 2,000
interfaces, 150 harnesses, 20,000 wires). Usage: python -m tools.bench_stress"""

import tempfile
import time
from pathlib import Path

from harness_design_studio.core.commands import History, Put
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import (
    Connector,
    Endpoint,
    Harness,
    InterfaceInstance,
    Pin,
    Project,
    Unit,
    Wire,
    evolve,
)
from harness_design_studio.core.starter import starter_interface_types, starter_parts


def build(
    units: int = 200, interfaces: int = 2000, harnesses: int = 150, wires: int = 20000
) -> Project:
    p = Project()
    p.parts = {x.id: x for x in starter_parts()}
    p.interface_types = {x.id: x for x in starter_interface_types()}
    subsystems = [f"sub{i}" for i in range(12)]
    for i in range(units):
        p.units[f"U{i:03d}"] = Unit(id=f"U{i:03d}", name=f"Unit {i}", subsystem=subsystems[i % 12])
    pins = [Pin(id=str(k)) for k in range(1, 16)]
    for i in range(units):
        cid = f"U{i:03d}-J01"
        p.connectors[cid] = Connector(
            id=cid, name="J01", role="box", part_id="EX-DSUB-15-F", unit_id=f"U{i:03d}", pins=pins
        )
    for n in range(interfaces):
        a, b = n % units, (n * 7 + 1) % units
        a, b = (a, b) if a != b else (a, (b + 1) % units)
        p.interfaces[f"IF{n:04d}"] = InterfaceInstance(
            id=f"IF{n:04d}", name=f"i{n}", type_id="rs422",
            endpoints=[Endpoint(unit_id=f"U{a:03d}"), Endpoint(unit_id=f"U{b:03d}")],
        )  # fmt: skip
    per = wires // harnesses
    for hn in range(harnesses):
        src, dst = f"U{hn % units:03d}-J01", f"U{(hn * 3 + 1) % units:03d}-J01"
        if src == dst:
            dst = f"U{(hn + 2) % units:03d}-J01"
        ws = [
            Wire(
                id=f"H{hn:03d}-{k:03d}",
                from_connector=src,
                from_pin=str(k % 15 + 1),
                to_connector=dst,
                to_pin=str(k % 15 + 1),
                signal=f"S{k}",
            )  # fmt: skip
            for k in range(per)
        ]
        p.harnesses[f"H{hn:03d}"] = Harness(id=f"H{hn:03d}", name=f"Harness {hn}", wires=ws)
    return p


def timed(label: str, fn):  # type: ignore[no-untyped-def]
    t = time.perf_counter()
    result = fn()
    print(f"{label:28} {time.perf_counter() - t:7.2f} s")
    return result


def main() -> None:
    p = timed("build model", build)
    timed("integrity check", lambda: check_integrity(p))
    timed("model hash (serialise)", lambda: model_hash(p))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "stress"
        timed("save (full)", lambda: save_project(p, root))
        timed("save (unchanged)", lambda: save_project(p, root))
        r = timed("load", lambda: load_project(root))
        assert not r.has_errors, r.issues[:3]
        h = History(r.project)
        u = r.project.units["U001"]
        timed("one transaction", lambda: h.execute("rename", [Put("units", evolve(u, name="x"))]))


if __name__ == "__main__":
    main()
