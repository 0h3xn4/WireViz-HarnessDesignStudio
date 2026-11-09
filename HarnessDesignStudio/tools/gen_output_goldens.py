"""Regenerate the golden output digests (and the readable mini3 text outputs) on purpose.
Usage: python -m tools.gen_output_goldens   (then review the diff)

`loose_ends` (M4b of the 2.0 programme, D-201) is the project with loose cable ends of
`tests/loose_support.py` (the flatsat example and five harnesses a person drew): the digest of
every file, and the text files of the drawn harnesses and the system BOM and mass to read."""

import json
import shutil
import tempfile
from pathlib import Path

from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.samples import mini3, sat15, sat15_full
from tests.helpers import output_digests
from tests.loose_support import generated_loose, golden_text_files

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
    with tempfile.TemporaryDirectory() as tmp:
        p = load_project(generated_loose(Path(tmp) / "loose")).project
    files = build_outputs(p).files
    (ROOT / "loose_ends.json").write_text(
        json.dumps(output_digests(files), indent=1, sort_keys=True) + "\n"
    )
    text = ROOT / "loose_ends"
    shutil.rmtree(text, ignore_errors=True)
    for rel, data in golden_text_files(files).items():
        (text / rel).parent.mkdir(parents=True, exist_ok=True)
        (text / rel).write_bytes(data)


if __name__ == "__main__":
    main()
