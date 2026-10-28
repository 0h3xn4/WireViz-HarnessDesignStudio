# mypy: allow-untyped-calls
"""Time what one edit costs on a project of 200 devices, and what the autosave journal and the
export cost. Usage: python -m tools.bench_incremental [--repeat N] [--section NAME ...]

Sections: edit (an edit through `History.execute`), journal (the autosave journal), export (the
build workbooks of the flatsat example), undo (memory held by one undo step). Every number is the
median of `--repeat` runs (default 5); the machine is shared and noisy, so run the whole script
three times and compare medians. The project is the stress project of `tools.bench_stress` (200
devices, 2,000 interfaces, 150 hand-made harnesses with 20,000 wires) plus two more connectors of 40
named pins on every device and a link from every device to the next one (a pinout-first project of that size)."""

import argparse
import gc
import statistics
import sys
import tempfile
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path

from harness_design_studio.core import templates, wires
from harness_design_studio.core.commands import History, Put
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import Connector, Link, Pin, PinPair, Project, evolve
from tools.bench_stress import build

SIGNALS = ("TX", "RX", "PWR", "RTN", "CLK", "CS", "MOSI", "MISO", "GND", "CANH", "CANL", "SDA")


def dense(devices: int = 200, links: int = 200) -> Project:
    """The stress project with three named 40-pin connectors on every device and `links` links."""
    p = build(units=devices)
    for n, unit in enumerate(p.units.values()):
        for k in (2, 3):
            cid = f"{unit.id}-J{k:02d}"
            pins = [Pin(id=str(i + 1), signal=SIGNALS[(i + n) % len(SIGNALS)]) for i in range(40)]
            p.connectors[cid] = Connector(
                id=cid, name=f"J{k:02d}", role="box", part_id="EX-DSUB-15-F", unit_id=unit.id,
                pins=pins,
            )  # fmt: skip
    units = list(p.units)
    for n in range(links):  # a connector of one device to a different connector of the next one
        a, b = units[n % devices], units[(n + 1) % devices]
        pairs = [PinPair(a_pin=str(i + 1), b_pin=str(i + 1)) for i in range(20)]
        p.links[f"L{n:03d}"] = Link(
            id=f"L{n:03d}", a_connector=f"{a}-J02", b_connector=f"{b}-J03", pairs=pairs
        )
    return p


def timed(fn: Callable[[], object], repeat: int) -> tuple[float, float, float]:
    """(median, min, max) of `repeat` runs, in milliseconds."""
    runs = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        runs.append((time.perf_counter() - t) * 1000)
    return statistics.median(runs), min(runs), max(runs)


def show(label: str, stats: tuple[float, float, float], unit: str = "ms") -> None:
    med, low, high = stats
    print(f"  {label:46} {med:9.1f} {unit}   (min {low:.1f}, max {high:.1f})")


def section_edit(repeat: int) -> None:
    from harness_design_studio.core import commands, integrity

    print("edit: History.execute on the dense 200-device project")
    p = dense()
    h = History(p)
    calls = [0]
    original = integrity.check_integrity

    def counting(project: Project):  # type: ignore[no-untyped-def]
        calls[0] += 1
        return original(project)

    integrity.check_integrity = counting
    if hasattr(commands, "check_integrity"):
        commands.check_integrity = counting
    try:
        n = [0]
        first_unit = next(iter(p.units))
        some_connector = f"{first_unit}-J02"
        some_harness = next(iter(p.harnesses))
        wire_id = p.harnesses[some_harness].wires[0].id

        def rename_unit() -> None:
            n[0] += 1
            h.execute("rename", [Put("units", evolve(p.units[first_unit], name=f"x{n[0]}"))])

        def edit_connector() -> None:
            n[0] += 1
            c = p.connectors[some_connector]
            h.execute("connector", [Put("connectors", evolve(c, name=f"J{n[0]}"))])

        def edit_wire() -> None:
            n[0] += 1
            h.execute("wire", wires.plan_wire_edit(p, [wire_id], {"note": f"n{n[0]}"}))

        rename_unit()  # the first call fills the caches
        show("full integrity check, nothing changed", timed(lambda: original(p), repeat))
        for label, fn in (
            ("rename a device", rename_unit),
            ("edit a device connector", edit_connector),
            ("edit a wire (one of 20,000)", edit_wire),
        ):
            calls[0] = 0
            stats = timed(fn, repeat)
            show(label, stats)
            print(f"  {'  full checks per edit':46} {calls[0] / repeat:9.1f}")
    finally:
        integrity.check_integrity = original
        if hasattr(commands, "check_integrity"):
            commands.check_integrity = original


def section_journal(repeat: int) -> None:
    from PySide6.QtCore import QCoreApplication

    from harness_design_studio.core.io.layout import serialize
    from harness_design_studio.gui.controller import EditorController

    print("journal: the autosave journal of the dense 200-device project")
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "p"
        ctl = EditorController(journal_delay_ms=10_000, drc_delay_ms=600_000)
        p = dense()
        ctl._install(p, root, None)
        n = [0]

        def edit() -> None:
            n[0] += 1
            ctl.update_unit(next(iter(p.units)), name=f"edit {n[0]}")

        def tick() -> float:
            edit()
            t = time.perf_counter()
            ctl._timer.timeout.emit()  # what the timer does 1.5 s after an edit
            return (time.perf_counter() - t) * 1000

        wait = getattr(ctl, "wait_journal", lambda: None)
        first = tick()
        wait()
        print(
            f"  {'first journal after the project was opened':46} {first:9.1f} ms on the GUI thread"
        )
        gui, total = [], []
        for _ in range(repeat):
            t = time.perf_counter()
            gui.append(tick())
            wait()
            app.processEvents()
            total.append((time.perf_counter() - t) * 1000)
        show("GUI thread, one edit then the journal", (statistics.median(gui), min(gui), max(gui)))
        show("until the journal is on disk", (statistics.median(total), min(total), max(total)))
        journal = root / ".harness-recovery" / "session.json"
        if journal.is_file():
            print(f"  {'journal size':46} {journal.stat().st_size / 1e6:9.1f} MB")
        edit()
        show("serialize(project) after one edit", timed(lambda: serialize(p), repeat))
        ctl.release()


def section_export(repeat: int) -> None:
    from harness_design_studio.core.outputs import buildsheet
    from harness_design_studio.core.outputs.build import build_outputs

    Font = buildsheet._S["Font"]  # the class the workbook code uses (see outputs/xlsx_env.py)

    print("export: the flatsat example, without drawings")
    with tempfile.TemporaryDirectory() as tmp:
        project = templates.create_project(Path(tmp) / "flatsat", "flatsat")
        if not project.harnesses:
            generate_project(project)
        count = [0]
        original = Font.__init__

        def counting(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            count[0] += 1
            original(self, *args, **kwargs)

        if hasattr(buildsheet, "_font"):
            buildsheet._font.cache_clear()
        Font.__init__ = counting
        try:
            build_outputs(project, drawings=False)
        finally:
            Font.__init__ = original
        print(f"  {'openpyxl Font objects built by one export':46} {count[0]:9d}")
        show(
            "build_outputs (no drawings)",
            timed(lambda: build_outputs(project, drawings=False), max(1, repeat // 2)),
        )


def section_undo(repeat: int) -> None:
    print("undo: memory kept by one undo step (a wire note edited)")
    with tempfile.TemporaryDirectory() as tmp:
        flat = templates.create_project(Path(tmp) / "flatsat", "flatsat")
        if not flat.harnesses:
            generate_project(flat)
    for name, p in (("flatsat example", flat), ("dense 200-device project", dense())):
        h = History(p)
        hid = max(p.harnesses, key=lambda i: len(p.harnesses[i].wires))
        wire_id = p.harnesses[hid].wires[0].id
        h.execute("warm", wires.plan_wire_edit(p, [wire_id], {"note": "warm"}))
        gc.collect()
        tracemalloc.start()
        before = tracemalloc.get_traced_memory()[0]
        steps = 10
        for k in range(steps):
            h.execute("wire", wires.plan_wire_edit(p, [wire_id], {"note": f"n{k}"}))
        gc.collect()
        grown = tracemalloc.get_traced_memory()[0] - before
        tracemalloc.stop()
        print(f"  {name:46} {grown / steps / 1024:9.0f} kB per step")


SECTIONS = {
    "edit": section_edit,
    "journal": section_journal,
    "export": section_export,
    "undo": section_undo,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else "")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--section", nargs="*", choices=sorted(SECTIONS), default=list(SECTIONS))
    args = parser.parse_args()
    for name in args.section:
        SECTIONS[name](args.repeat)


if __name__ == "__main__":
    main()
