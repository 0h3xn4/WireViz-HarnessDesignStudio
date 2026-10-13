"""Regenerate the golden output digests (and the readable mini3 text outputs) on purpose.
Usage: python -m tools.gen_output_goldens   (then review the diff)"""

import json
import shutil
from pathlib import Path

from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.samples import mini3, sat15, sat15_full
from tests.helpers import output_digests

ROOT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "outputs"


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, make in (("mini3", mini3), ("sat15", sat15), ("sat15_full", sat15_full)):
        p = make()
        if name != "sat15_full":
            generate_project(p)
        files = build_outputs(p).files
        (ROOT / f"{name}.json").write_text(
            json.dumps(output_digests(files), indent=1, sort_keys=True) + "\n"
        )
        if name == "mini3":
            text = ROOT / "mini3"
            shutil.rmtree(text, ignore_errors=True)
            for rel, data in files.items():
                if rel.endswith((".csv", ".svg", ".yaml", ".md", ".json")):
                    (text / rel).parent.mkdir(parents=True, exist_ok=True)
                    (text / rel).write_bytes(data)


if __name__ == "__main__":
    main()
