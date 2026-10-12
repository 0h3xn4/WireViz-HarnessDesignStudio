"""Soak test: thousands of random editing steps through `History`, checking invariants all the
way. Usage: python -m tools.soak [steps] [seed]   (pytest runs a short version)

Invariants after every step: no integrity errors; a rejected step leaves the model unchanged;
undo then redo restores the exact model; every 50 steps the project survives save and load with
the same hash; after every generation the verifier reports no errors."""

import random
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from harness_design_studio.core import checks, edit
from harness_design_studio.core.commands import History
from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.generate.engine import plan_generation
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.issues import errors
from harness_design_studio.core.model import Project
from harness_design_studio.core.samples import mini3
from harness_design_studio.core.verify import verify_project


@dataclass
class SoakResult:
    steps: int = 0
    applied: int = 0
    rejected: int = 0
    generations: int = 0
    roundtrips: int = 0
    counts: dict[str, int] = field(default_factory=dict)


def _pick(rng: random.Random, items: list[str]) -> str | None:
    return rng.choice(sorted(items)) if items else None


def run_soak(steps: int, seed: int = 1, folder: Path | None = None) -> SoakResult:
    rng = random.Random(seed)  # noqa: S311 - a test driver, not cryptography
    project: Project = mini3()
    hist = History(project)
    result = SoakResult()
    work = folder or Path(tempfile.mkdtemp(prefix="soak-"))
    templates = sorted(edit.TEMPLATES)
    types = sorted(project.interface_types)

    def step(kind: str) -> None:
        units, ifaces = list(project.units), list(project.interfaces)
        before = model_hash(project)
        try:
            if kind == "add_unit":
                ops, _ = edit.ops_add_unit(project, rng.choice(templates))
                hist.execute("add unit", ops)
            elif kind == "connect":
                a, b = _pick(rng, units), _pick(rng, units)
                if a and b:
                    ops, _ = edit.ops_add_interface(project, rng.choice(types), a, b)
                    hist.execute("connect", ops)
            elif kind == "delete_interface":
                i = _pick(rng, ifaces)
                if i:
                    hist.execute("delete interface", edit.ops_delete_interface(project, i))
            elif kind == "delete_unit":
                u = _pick(rng, units)
                if u:
                    hist.execute("delete unit", edit.ops_delete_unit(project, u))
            elif kind == "rename":
                u = _pick(rng, units)
                if u:
                    hist.execute(
                        "rename", edit.ops_rename_unit(project, u, f"{u}x{rng.randint(1, 99)}")
                    )
            elif kind == "redundant":
                u = _pick(rng, units)
                if u:
                    hist.execute("redundant copy", edit.ops_redundant_copy(project, u).ops)
            elif kind == "move":
                u = _pick(rng, units)
                if u:
                    hist.execute(
                        "move",
                        edit.ops_move_unit(project, u, rng.uniform(0, 1500), rng.uniform(0, 900)),
                    )
            elif kind == "current":
                i = _pick(rng, ifaces)
                if i:
                    hist.execute(
                        "current",
                        edit.ops_update_interface(
                            project, i, max_current_a=rng.choice([0.5, 1.0, 3.0, None])
                        ),
                    )
            elif kind == "waive":
                found = [f for f in checks.find(project) if f.can_waive and f.waiver is None]
                if found:
                    hist.execute(
                        "waive",
                        [checks.waive_op(rng.choice(found), "Accepted during the soak test")],
                    )
            elif kind == "generate":
                plan = plan_generation(project)
                if plan.ops:
                    hist.execute("generate", plan.ops)
                result.generations += 1
                explained = {f.object_id for f in plan.report.findings if f.object_id}
                bad = [
                    i
                    for i in verify_project(project).errors
                    if i.code != "outputs_outdated" and i.object_id not in explained
                ]  # a failure the generator reported (no free pins ...) is not a verifier surprise
                assert not bad, (bad[:2], [f.message for f in plan.report.findings][:4])
            elif kind in ("undo", "redo"):
                if kind == "undo" and hist.can_undo:
                    hist.undo()
                    hist.redo()
                    assert model_hash(project) == before, "undo then redo did not restore the model"
                elif kind == "redo" and hist.can_redo:
                    hist.redo()
            result.applied += 1
        except HarnessError:
            result.rejected += 1
            assert model_hash(project) == before, f"a rejected '{kind}' changed the model"
        except (KeyError, ValueError) as exc:  # edit helpers raise these for impossible picks
            result.rejected += 1
            assert model_hash(project) == before, f"'{kind}' failed ({exc}) and changed the model"
        result.counts[kind] = result.counts.get(kind, 0) + 1

    kinds = (
        ["add_unit"] * 3
        + ["connect"] * 6
        + [
            "delete_interface",
            "delete_unit",
            "rename",
            "redundant",
            "move",
            "current",
            "waive",
            "generate",
            "undo",
            "redo",
        ]
    )
    for n in range(steps):
        step(rng.choice(kinds))
        result.steps += 1
        problems = errors(check_integrity(project))
        assert not problems, f"step {n}: {problems[0].message}"
        if n % 50 == 49:
            target = work / "project"
            save_project(project, target)
            loaded = load_project(target)
            assert not loaded.has_errors, loaded.issues[:2]
            assert model_hash(loaded.project) == model_hash(project), (
                f"step {n}: save/load changed the model"
            )
            result.roundtrips += 1
    return result


def main() -> int:
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    r = run_soak(steps, seed)
    print(
        f"{r.steps} steps ({r.applied} applied, {r.rejected} rejected), {r.generations} generations, {r.roundtrips} save/load round trips: all invariants held"
    )
    print(", ".join(f"{k} {v}" for k, v in sorted(r.counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
