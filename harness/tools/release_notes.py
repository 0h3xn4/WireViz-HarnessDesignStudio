"""Check a release tag and write the notes of the GitHub release page (used by .github/workflows/release.yml).

Usage: python -m tools.release_notes check TAG
       python -m tools.release_notes notes TAG SHA256SUMS OUT
`check` fails unless TAG is `v` plus the version in pyproject.toml, CHANGELOG.md has a section for
that version and nothing is left under `## Unreleased`. `notes` writes the page text: one sentence
saying what the packages are not, the changelog section of the version and the SHA-256 table.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from tools.release_check import unreleased_text

ROOT = Path(__file__).resolve().parents[1]
CAVEAT = (
    "The packages are not signed, the configuration values are placeholders and the parts are "
    "example parts: this release is not a statement of compliance with any standard."
)


def project_version(root: Path = ROOT) -> str:
    meta = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(meta["project"]["version"])


def section(changelog: str, version: str) -> str | None:
    """The text under the `## <version>` heading (up to the next `## `), or None without one."""
    match = re.search(
        rf"^## {re.escape(version)}(?:[ \t][^\n]*)?\n(.*?)(?=^## |\Z)", changelog, re.M | re.S
    )
    return match.group(1).strip() if match else None


def problems(tag: str, version: str, changelog: str) -> list[str]:
    found = []
    if tag != f"v{version}":
        found.append(
            f"the tag is {tag} but the version in pyproject.toml is {version} (want v{version})"
        )
    body = section(changelog, version)
    if body is None:
        found.append(f"CHANGELOG.md has no '## {version}' heading")
    elif not body:
        found.append(f"the CHANGELOG.md section {version} is empty")
    if unreleased_text(changelog):
        found.append("CHANGELOG.md still has text under '## Unreleased'")
    return found


def notes(version: str, changelog: str, sums: str) -> str:
    rows = []
    for line in sums.splitlines():
        digest, _, name = line.partition("  ")
        if digest and name:
            rows.append(f"| `{name}` | `{digest}` |")
    table = "\n".join(["| File | SHA-256 |", "| --- | --- |", *rows])
    return (
        f"{CAVEAT}\n\n{section(changelog, version) or ''}\n\n## Checksums\n\n{table}\n\n"
        "Check a download with `sha256sum -c SHA256SUMS` in the folder that holds the files.\n"
    )


def main(argv: list[str]) -> int:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    version = project_version()
    if len(argv) == 2 and argv[0] == "check":
        found = problems(argv[1], version, changelog)
        for item in found:
            sys.stderr.write(f"error: {item}\n")
        if not found:
            sys.stdout.write(f"{argv[1]}: version {version}, changelog section found\n")
        return 1 if found else 0
    if len(argv) == 4 and argv[0] == "notes":
        found = problems(argv[1], version, changelog)
        if found:
            sys.stderr.write("error: " + "; ".join(found) + "\n")
            return 1
        sums = Path(argv[2]).read_text(encoding="utf-8")
        Path(argv[3]).write_text(notes(version, changelog, sums), encoding="utf-8")
        return 0
    sys.stderr.write(__doc__ or "")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
