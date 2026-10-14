"""Create the material for the usability tasks T1 to T8 in a folder (docs/usability/README.md).
Usage: python -m tools.usability_setup DIR"""

import shutil
import sys
from pathlib import Path

from harness_design_studio.core import edit
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Project
from harness_design_studio.core.samples import new_project, sat15_full


def _free_pair(project: Project) -> tuple[str, str, str]:
    """An interface type and two units that both still have a free connector for it."""
    for kind in sorted(project.interface_types):
        free = [u for u in sorted(project.units) if edit.free_connectors(project, u, kind)]
        if len(free) >= 2:
            return kind, free[0], free[1]
    raise RuntimeError("the sample has no pair of units with free connectors")


def build(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    save_project(new_project("Usability T1"), root / "t1-empty")
    full = sat15_full()
    save_project(full, root / "t6-t7-generated")
    kind, a, b = _free_pair(full)
    (root / "icd.csv").write_text(
        f"id,type,from,to\nIF-A,{kind},{a},{b}\nIF-B,not-a-type,{a},{b}\nIF-C,{kind},{a},NOPE\n"
    )
    broken = root / "t8-corrupt"
    shutil.rmtree(broken, ignore_errors=True)
    save_project(generate_and_return(), broken)
    victim = next((broken / "physical" / "harnesses").glob("*.json"))
    victim.write_text('{"id": "BROKEN", ')  # one damaged file; the rest must still load
    (root / "README.txt").write_text(
        "Task material for docs/usability. Open each folder with File > Open project.\n"
    )


def generate_and_return() -> Project:
    from harness_design_studio.core.samples import sat15

    p = sat15()
    generate_project(p)
    return p


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    build(Path(sys.argv[1]))
    print(f"material written to {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
