"""The numbers the tool gives today, kept on purpose so that no change of the transparency work (D-191)
moves one of them unseen.

`docs/ui/OUTPUT_HASHES_BASELINE.json` already holds every file the four packaged examples write. This
adds what that file does not hold: the same examples in the situations an engineer meets them in, each
generated, checked and written the way a user does it:

- the example as it ships (the numbers are readable: gauge, length, part, colour, lock of every wire, every
  finding with its text);
- `flatsat-override`: a gauge outside the ampacity table, and a length and colour typed by hand, then
  Generate again (the wires are locked and kept);
- `flatsat-ecss`: the ECSS profile of the standard values applied, then Generate again;
- `flatsat-tight`: a lower ampacity for AWG 24 and AWG 22, so current findings carry numbers;
- `flatsat-own-bundle-table`: a bundle factor table of the user's own;
- `small-satellite-per-*`: the three ways to group interfaces into harnesses.

For each scenario the file stores the SHA-256 of every written file (a workbook by its members, the version
stamp as in the base version, as `tools.output_hashes` does) and the readable numbers above. A change that
moves a number on purpose renews the file with a reviewed reason in `docs/changes.md`:

    python -m tools.numbers_snapshot --write tests/fixtures/numbers/snapshot.json
    python -m tools.numbers_snapshot --check tests/fixtures/numbers/snapshot.json
"""

import copy
import json
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from harness_design_studio.core import standard_profiles, templates
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.drc import run as run_drc
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import ConfigFile, Project, evolve
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.wires import plan_wire_edit
from tools.output_hashes import BASE_VERSION, digest

STORED = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "numbers" / "snapshot.json"
EXAMPLES = ("first-steps", "minimal-satellite", "small-satellite", "flatsat")


def _set(project: Project, file: str, **values: object) -> None:
    """Set values in a configuration file the way an engineer who has reviewed it would."""
    base = project.config[file]
    project.config[file] = ConfigFile(
        name=file, placeholder=False, values={**copy.deepcopy(base.values), **values}
    )


def _first_wires(project: Project, n: int) -> list[str]:
    ids = [w.id for h in sorted(project.harnesses.values(), key=lambda h: h.id) for w in h.wires]
    return sorted(ids)[:n]


def _override(project: Project) -> None:
    first, second = _first_wires(project, 2)
    apply_ops(project, plan_wire_edit(project, [first], {"gauge_awg": 28}))
    apply_ops(project, plan_wire_edit(project, [second], {"length_m": 1.0, "colour": "red"}))
    generate_project(project)


def _ecss(project: Project) -> None:
    for cfg in standard_profiles.plan_profile(project, "ecss-q-st-30-11c").configs:
        project.config[cfg.name] = cfg
    generate_project(project)


def _tight(project: Project) -> None:
    table = dict(project.config["derating"].values.get("ampacity_a_by_awg") or {})
    table.update({"22": 0.4, "24": 0.3})
    _set(project, "derating", ampacity_a_by_awg=table)


def _own_bundle_table(project: Project) -> None:
    _set(project, "derating", bundle_factor_by_count={"1": 1, "5": 0.7, "20": 0.5, "100": 0.4})
    generate_project(project)


def _mode(mode: str) -> Callable[[Project], None]:
    def apply(project: Project) -> None:
        _set(project, "segmentation", mode=mode)
        generate_project(project)

    return apply


SCENARIOS: dict[str, tuple[str, Callable[[Project], None] | None]] = {
    **{name: (name, None) for name in EXAMPLES},
    "flatsat-override": ("flatsat", _override),
    "flatsat-ecss": ("flatsat", _ecss),
    "flatsat-tight": ("flatsat", _tight),
    "flatsat-own-bundle-table": ("flatsat", _own_bundle_table),
    "small-satellite-per-connector-pair": ("small-satellite", _mode("per_connector_pair")),
    "small-satellite-per-unit-pair": ("small-satellite", _mode("per_unit_pair")),
    "small-satellite-per-zone-pair": ("small-satellite", _mode("per_zone_pair")),
}


def snapshot(name: str) -> dict[str, object]:
    example, change = SCENARIOS[name]
    with tempfile.TemporaryDirectory(prefix="numbers-") as tmp:
        project = templates.create_project(Path(tmp) / name, example)
        if not project.harnesses:
            generate_project(project)
        if change is not None:
            change(project)
        project.meta = evolve(project.meta, tool_version=BASE_VERSION)
        if project.generation is not None:
            project.generation = evolve(project.generation, generator_version=BASE_VERSION)
        files = build_outputs(project).files
        wires = [
            [
                h.id,
                w.id,
                w.signal,
                w.gauge_awg,
                w.length_m,
                w.part_id,
                w.colour,
                w.locked,
                w.strip_a_mm,
                w.strip_b_mm,
            ]
            for h in sorted(project.harnesses.values(), key=lambda h: h.id)
            for w in sorted(h.wires, key=lambda w: w.id)
        ]
        findings = [[f.id, f.severity, f.title] for f in run_drc(project)]
    return {
        "wires": wires,
        "findings": findings,
        "files": {rel: digest(rel, data) for rel, data in sorted(files.items())},
    }


def snapshots() -> dict[str, dict[str, object]]:
    return {name: snapshot(name) for name in SCENARIOS}


def differences(now: dict[str, dict[str, object]], then: dict[str, dict[str, object]]) -> list[str]:
    """What moved, named by scenario and by what a reader can act on: the wire, the finding, the file."""
    found: list[str] = []
    for name in sorted(set(now) | set(then)):
        a, b = now.get(name), then.get(name)
        if a is None or b is None:
            found.append(f"{name}: {'missing now' if a is None else 'new scenario'}")
            continue
        wa = {str(w[1]): w for w in a["wires"]}  # type: ignore[attr-defined]
        wb = {str(w[1]): w for w in b["wires"]}  # type: ignore[attr-defined]
        for wid in sorted(set(wa) | set(wb)):
            if wa.get(wid) != wb.get(wid):
                found.append(f"{name}: wire {wid}: {wb.get(wid)} -> {wa.get(wid)}")
        fa = {f[0]: f for f in a["findings"]}  # type: ignore[attr-defined]
        fb = {f[0]: f for f in b["findings"]}  # type: ignore[attr-defined]
        for fid in sorted(set(fa) | set(fb)):
            if fa.get(fid) != fb.get(fid):
                found.append(f"{name}: finding {fid}: {fb.get(fid)} -> {fa.get(fid)}")
        da, db = a["files"], b["files"]
        for rel in sorted(set(da) | set(db)):  # type: ignore[call-overload]
            if da.get(rel) != db.get(rel):  # type: ignore[attr-defined]
                found.append(f"{name}: file {rel} changed")
    return found


def main(argv: list[str]) -> int:
    got = snapshots()
    if argv[:1] == ["--write"]:
        Path(argv[1]).write_text(json.dumps(got, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"{len(got)} scenarios written to {argv[1]}")
        return 0
    if argv[:1] == ["--check"]:
        diff = differences(got, json.loads(Path(argv[1]).read_text(encoding="utf-8")))
        for line in diff:
            print(line)
        print("identical" if not diff else f"{len(diff)} difference(s)")
        return 1 if diff else 0
    print(json.dumps(got, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
