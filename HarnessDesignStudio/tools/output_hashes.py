"""SHA-256 of every file the tool writes (a workbook by its members) for each packaged example, to show that a change of the user
interface (or of anything else that must not touch the written files) left them alone.

    python -m tools.output_hashes                       # print the hashes as JSON
    python -m tools.output_hashes --write FILE          # store them
    python -m tools.output_hashes --check FILE          # compare with a stored file; exit 1 on a difference

The stored file `docs/ui/OUTPUT_HASHES_BASELINE.json` is the baseline; a test
(`tests/test_output_hashes.py`) compares the current tool with it. Every file the tool writes names the
version of the tool in its header or title block, so a newer version differs in those bytes only: before
hashing, the current version string is replaced by `BASE_VERSION` (both have the same length, so no
offset of a PDF moves). The model hash includes the version a project was saved with, so each example
(and its generation record) is first given `BASE_VERSION`. Nothing else may differ.

The baseline is renewed on purpose, with a reviewed reason in `CHANGELOG.md` and `docs/DECISIONS.md`, when a
release changes a written file for good (release 1.10, D-182: the shield ends of a coax, the cable-pin
Signal cells, the Requirement column), and when the version string changes its length (1.9.x to 1.10.0,
1.99.x to 1.100.0): write it again with this tool and set `BASE_VERSION` to the version then current. The
file `docs/ui/OUTPUT_HASHES_1.2.0.json` is the baseline of releases 1.2.0 to 1.9.0, kept as the record of
what those releases wrote; nothing compares with it any more.
"""

import hashlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

from harness_design_studio import __version__
from harness_design_studio.core import templates
from harness_design_studio.core.drc import RULES
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import evolve
from harness_design_studio.core.outputs.build import build_outputs

STORED = Path(__file__).resolve().parent.parent / "docs" / "ui" / "OUTPUT_HASHES_BASELINE.json"
EXAMPLES = ("first-steps", "minimal-satellite", "small-satellite", "flatsat")
BASE_VERSION = "1.9.0"  # the version of the tool that wrote the stored hashes
BASE_RULES = 39  # the number of design rules then; a rule added later is given as in the baseline
# A new kind of file is the one thing the check lets through (none now); every file of the baseline is compared.
ADDED_AFTER_BASE: tuple[str, ...] = ()


def as_in_base_version(data: bytes) -> bytes:
    """The bytes of a file with the version stamp of the release the hashes were made with."""
    if len(RULES) != BASE_RULES and len(str(len(RULES))) == len(str(BASE_RULES)):
        data = data.replace(
            f"Rules run: {len(RULES)}.".encode(), f"Rules run: {BASE_RULES}.".encode()
        )
    if __version__ == BASE_VERSION or len(__version__) != len(BASE_VERSION):
        return data
    return data.replace(__version__.encode(), BASE_VERSION.encode())


def digest(rel: str, data: bytes) -> str:
    """SHA-256 of a file. A workbook (.xlsx) is a zip whose container bytes depend on the zip
    library of the platform (the same sheets compress differently on Windows), so it is hashed by
    the names and the bytes of its members; every other file is hashed as it is."""
    if rel.endswith(".xlsx"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            parts = sorted(
                (n, hashlib.sha256(as_in_base_version(z.read(n))).hexdigest()) for n in z.namelist()
            )
        return hashlib.sha256(json.dumps(parts).encode()).hexdigest()
    return hashlib.sha256(as_in_base_version(data)).hexdigest()


def hashes() -> dict[str, dict[str, str]]:
    """example -> {path of a written file: sha256}, each example generated the way a user does."""
    out: dict[str, dict[str, str]] = {}
    for name in EXAMPLES:
        with tempfile.TemporaryDirectory(prefix="hashes-") as tmp:
            project = templates.create_project(Path(tmp) / name, name)
            if not project.harnesses:
                generate_project(project)
            project.meta = evolve(project.meta, tool_version=BASE_VERSION)
            if project.generation is not None:
                project.generation = evolve(project.generation, generator_version=BASE_VERSION)
            files = build_outputs(project).files
        out[name] = {rel: digest(rel, data) for rel, data in sorted(files.items())}
    return out


def differences(now: dict[str, dict[str, str]], then: dict[str, dict[str, str]]) -> list[str]:
    found: list[str] = []
    for name in sorted(set(now) | set(then)):
        a, b = now.get(name, {}), then.get(name, {})
        for rel in sorted(set(a) | set(b)):
            if a.get(rel) != b.get(rel):
                if rel not in b and rel.endswith(ADDED_AFTER_BASE):
                    continue
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
