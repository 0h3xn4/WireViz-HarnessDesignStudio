"""SHA-256 of every file the tool writes for each packaged example, to show that a change of the user
interface left the written files alone (UI overhaul M6; the brief: SVG and PDF byte-identical to 1.2.0).

    python -m tools.output_hashes                       # print the hashes as JSON
    python -m tools.output_hashes --write FILE          # store them
    python -m tools.output_hashes --check FILE          # compare with a stored file; exit 1 on a difference

The stored file `docs/ui/OUTPUT_HASHES_1.2.0.json` was made with the release 1.2.0 (tag v1.2.0); a test
(`tests/test_output_hashes.py`) compares the current tool with it.
"""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

from harness_design_studio.core import templates
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.outputs.build import build_outputs

STORED = Path(__file__).resolve().parent.parent / "docs" / "ui" / "OUTPUT_HASHES_1.2.0.json"
EXAMPLES = ("first-steps", "minimal-satellite", "small-satellite", "flatsat")


def hashes() -> dict[str, dict[str, str]]:
    """example -> {path of a written file: sha256}, each example generated the way a user does."""
    out: dict[str, dict[str, str]] = {}
    for name in EXAMPLES:
        with tempfile.TemporaryDirectory(prefix="hashes-") as tmp:
            project = templates.create_project(Path(tmp) / name, name)
            if not project.harnesses:
                generate_project(project)
            files = build_outputs(project).files
        out[name] = {rel: hashlib.sha256(data).hexdigest() for rel, data in sorted(files.items())}
    return out


def differences(now: dict[str, dict[str, str]], then: dict[str, dict[str, str]]) -> list[str]:
    found: list[str] = []
    for name in sorted(set(now) | set(then)):
        a, b = now.get(name, {}), then.get(name, {})
        for rel in sorted(set(a) | set(b)):
            if a.get(rel) != b.get(rel):
                what = "missing now" if rel not in a else "new" if rel not in b else "changed"
                found.append(f"{name}/{rel}: {what}")
    return found


def main(argv: list[str]) -> int:
    got = hashes()
    if argv[:1] == ["--write"]:
        Path(argv[1]).write_text(json.dumps(got, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(
            f"{sum(len(v) for v in got.values())} files of {len(got)} examples written to {argv[1]}"
        )
        return 0
    if argv[:1] == ["--check"]:
        then = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        diff = differences(got, then)
        for line in diff:
            print(line)
        print("identical" if not diff else f"{len(diff)} difference(s)")
        return 1 if diff else 0
    print(json.dumps(got, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
