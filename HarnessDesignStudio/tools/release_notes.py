"""Check a release tag and write the notes of the GitHub release page (used by .github/workflows/release.yml).

Usage: python -m tools.release_notes check TAG
       python -m tools.release_notes notes TAG SHA256SUMS OUT [--root DIR]
`check` fails unless TAG is `v` plus the version in pyproject.toml, CHANGELOG.md has a section for
that version, `docs/releases/<version>.md` (the highlights) exists and nothing is left under
`## Unreleased`. `notes` writes the page text: what the tool is, a download table with one row
for each package that is in SHA256SUMS, how to install and check them, the highlights, the full
changelog section folded away, and the SHA-256 table. `--root` is the `HarnessDesignStudio` folder
of the tagged checkout (default: this one); the highlights file is looked for there first and then
here, so that the notes of an older tag can be written again with a newer version of this script.
"""

from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from tools.release_check import unreleased_text

ROOT = Path(__file__).resolve().parents[1]
REPO_URL = "https://github.com/0h3xn4/WireViz-HarnessDesignStudio"
CAVEAT = (
    "The packages are not signed, the configuration values are placeholders and the parts are "
    "example parts: this release is not a statement of compliance with any standard."
)
INTRO = (
    "**Harness Design Studio** is an offline tool for designing the electrical harnesses of a "
    "spacecraft. You describe the units and the interfaces between them; the tool generates the "
    "harnesses, checks them against design rules and writes the drawings, wire lists and test "
    "tables. It never uses the network, and the same design always gives byte-identical files."
)


@dataclass(frozen=True)
class Package:
    """One kind of package: how to recognise its file name and what to tell the reader."""

    key: str
    pattern: str  # regular expression for the whole file name; {v} is the version
    system: str
    kind: str
    install: str  # one line for the table
    steps: tuple[str, ...]  # the lines of the "Install" section (Markdown)


PACKAGES: tuple[Package, ...] = (
    Package(
        "deb",
        r"harness-design-studio_{v}_amd64\.deb",
        "Ubuntu 24.04 or newer (64-bit)",
        "Debian package",
        "Double-click it, or run `sudo apt install ./<file>`",
        (
            "**Ubuntu:** `sudo apt install ./harness-design-studio_{v}_amd64.deb` installs the "
            "program for everyone. It needs a few system libraries that a normal Ubuntu desktop "
            "has; if one is missing, apt fetches it from your Ubuntu sources (the only time "
            "anything is downloaded). Then start `harness-design-studio-gui` or use "
            "`harness-design-studio` on the command line.",
        ),
    ),
    Package(
        "tar",
        r"harness-design-studio-{v}-linux-x86_64\.tar\.gz",
        "Linux (64-bit), without administrator rights",
        "Tarball",
        "Extract it and run `./install.sh`",
        (
            "**Linux, no administrator rights:** `tar xzf harness-design-studio-{v}-linux-x86_64"
            ".tar.gz && cd harness-design-studio && ./install.sh` (installs into your home "
            "folder; the system libraries of a normal Ubuntu desktop must be there).",
        ),
    ),
    Package(
        "win-setup",
        r"harness-design-studio-{v}-windows-x86_64-setup\.exe",
        "Windows 10 and 11 (64-bit)",
        "Installer",
        "Run it; installs for your user, no administrator rights needed",
        (
            "**Windows:** run `harness-design-studio-{v}-windows-x86_64-setup.exe`. It installs "
            "for your user (no administrator rights) and adds a Start menu entry and the "
            "commands `harness-design-studio` and `harness-design-studio-gui`. The package is "
            'not signed, so Windows SmartScreen shows "Windows protected your PC": choose '
            "**More info**, then **Run anyway**.",
        ),
    ),
    Package(
        "win-zip",
        r"harness-design-studio-{v}-windows-x86_64\.zip",
        "Windows 10 and 11 (64-bit)",
        "Portable zip",
        "Extract it anywhere and run `harness-design-studio-gui.exe`",
        (
            "**Windows, portable:** extract `harness-design-studio-{v}-windows-x86_64.zip` to a "
            "folder and run `harness-design-studio-gui.exe` in it; nothing is installed.",
        ),
    ),
    Package(
        "mac-arm",
        r"harness-design-studio-{v}-macos-arm64\.dmg",
        "macOS 13 or newer, Apple Silicon (M1 and later)",
        "Disk image",
        "Open it and drag the app to Applications",
        (
            "**macOS:** open the `.dmg` and drag **Harness Design Studio** to Applications. The "
            "app is not signed or notarized, so the first start needs a right-click on the app, "
            "**Open**, then **Open** again. The command line tool is inside the app: "
            "`/Applications/Harness Design Studio.app/Contents/MacOS/harness-design-studio`.",
        ),
    ),
    Package(
        "mac-intel",
        r"harness-design-studio-{v}-macos-x86_64\.dmg",
        "macOS 13 or newer, Intel Macs",
        "Disk image",
        "Open it and drag the app to Applications",
        (),  # the steps are the ones of the Apple Silicon image
    ),
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


def highlights_file(version: str, root: Path = ROOT) -> Path:
    return root / "docs" / "releases" / f"{version}.md"


def problems(tag: str, version: str, changelog: str, root: Path | None = None) -> list[str]:
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
    if root is not None and not highlights_file(version, root).is_file():
        found.append(f"docs/releases/{version}.md (the highlights of the release page) is missing")
    return found


def parse_sums(sums: str) -> list[tuple[str, str]]:
    """(file name, digest) for every line of a SHA256SUMS file."""
    rows = []
    for line in sums.splitlines():
        digest, _, name = line.partition("  ")
        if digest and name:
            rows.append((name.strip(), digest.strip()))
    return rows


def _found(version: str, names: list[str]) -> list[tuple[Package, str]]:
    found = []
    for package in PACKAGES:
        regex = re.compile(package.pattern.format(v=re.escape(version)))
        for name in names:
            if regex.fullmatch(name):
                found.append((package, name))
    return found


def _first_paragraph(text: str) -> str:
    return text.strip().split("\n\n", 1)[0].strip()


def notes(version: str, changelog: str, sums: str, highlights: str | None = None) -> str:
    rows = parse_sums(sums)
    names = [name for name, _ in rows]
    found = _found(version, names)
    body = section(changelog, version) or ""
    lead = (highlights or "").strip() or _first_paragraph(body)
    parts = [INTRO, f"> {CAVEAT}"]

    if found:
        table = ["| For | Download | How to install |", "| --- | --- | --- |"]
        for package, name in found:
            table.append(f"| {package.system} | `{name}` ({package.kind}) | {package.install} |")
        parts.append("## Download\n\n" + "\n".join(table))
    other = [name for name in names if name not in {n for _, n in found}]
    if other:
        parts.append("Other files: " + ", ".join(f"`{name}`" for name in other) + ".")

    parts.append(f"## What is new in {version}\n\n{lead}")
    parts.append(
        "<details>\n<summary>The full list of changes</summary>\n\n"
        f"{body}\n\n</details>\n\n"
        f"The same text is in [`CHANGELOG.md`]({REPO_URL}/blob/v{version}/HarnessDesignStudio/"
        "CHANGELOG.md)."
    )

    steps = [step.format(v=version) for package, _ in found for step in package.steps]
    if steps:
        parts.append(
            "## Install\n\n"
            + "\n\n".join(f"- {step}" for step in steps)
            + "\n\nNothing needs the network after installing, and the tool never opens a "
            "network connection. Full instructions, including what to do when something fails: "
            f"[`INSTALL.md`]({REPO_URL}/blob/v{version}/HarnessDesignStudio/docs/INSTALL.md)."
        )

    sums_table = "\n".join(
        ["| File | SHA-256 |", "| --- | --- |", *(f"| `{n}` | `{d}` |" for n, d in rows)]
    )
    keys = {package.key for package, _ in found}
    commands = []
    if keys & {"deb", "tar"} or not keys:
        commands.append("`sha256sum -c SHA256SUMS` (Linux)")
    if keys & {"mac-arm", "mac-intel"} or not keys:
        commands.append("`shasum -a 256 -c SHA256SUMS` (macOS)")
    if keys & {"win-setup", "win-zip"} or not keys:
        commands.append("`Get-FileHash <file> -Algorithm SHA256` in PowerShell (Windows)")
    parts.append(
        "## Check your download\n\n"
        f"{sums_table}\n\n"
        "Put the file you downloaded and `SHA256SUMS` in one folder, then run "
        + ", ".join(commands)
        + " and compare the result with the table. The packages are not signed, so this "
        "check is the only proof that a download is intact."
    )
    parts.append(
        "## Good to know\n\n"
        "- The tool ships no derating or EMC values and no approved parts list; each project "
        "supplies them. Until then results say *pending* or *not checked*.\n"
        "- The results are an aid to a designer's work, not a certificate; check them before "
        "you rely on them.\n"
        f"- Documents: [user manual]({REPO_URL}/blob/v{version}/HarnessDesignStudio/docs/"
        f"user-manual/README.md), [getting started]({REPO_URL}/blob/v{version}/"
        "HarnessDesignStudio/docs/GETTING_STARTED.md)."
    )
    return "\n\n".join(parts) + "\n"


def _option(argv: list[str], name: str) -> tuple[list[str], str | None]:
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[:i] + argv[i + 2 :], argv[i + 1]
    return argv, None


def main(argv: list[str]) -> int:
    argv, root_option = _option(argv, "--root")
    root = Path(root_option).resolve() if root_option else ROOT
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    version = project_version(root)
    if len(argv) == 2 and argv[0] == "check":
        found = problems(argv[1], version, changelog, root)
        for item in found:
            sys.stderr.write(f"error: {item}\n")
        if not found:
            sys.stdout.write(f"{argv[1]}: version {version}, changelog section found\n")
        return 1 if found else 0
    if len(argv) == 4 and argv[0] == "notes":
        # the highlights of an older tag may only exist in the newer checkout that runs this
        found = [p for p in problems(argv[1], version, changelog) if "highlights" not in p]
        if found:
            sys.stderr.write("error: " + "; ".join(found) + "\n")
            return 1
        sums = Path(argv[2]).read_text(encoding="utf-8")
        highlights = next(
            (
                path.read_text(encoding="utf-8")
                for path in (highlights_file(version, root), highlights_file(version, ROOT))
                if path.is_file()
            ),
            None,
        )
        Path(argv[3]).write_text(notes(version, changelog, sums, highlights), encoding="utf-8")
        return 0
    sys.stderr.write(__doc__ or "")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
