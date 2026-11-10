# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Check a release tag and write the notes of the GitHub release page (used by .github/workflows/release.yml).

Usage: python -m tools.release_notes check TAG
       python -m tools.release_notes notes TAG SHA256SUMS OUT [--root DIR]
       python -m tools.release_notes complete SHA256SUMS
`check` fails unless TAG is `v` plus the version in pyproject.toml, CHANGELOG.md has a section for
that version, `docs/releases/<version>.md` (the highlights) exists and nothing is left under
`## Unreleased`. `notes` writes the page text: what the tool is, a download table with one row
for each package that is in SHA256SUMS, how to install and check them, the highlights, the full
changelog section folded away, and the SHA-256 table. `--root` is the `HarnessDesignStudio` folder
of the tagged checkout (default: this one); the highlights file is looked for there first and then
here, so that the notes of an older tag can be written again with a newer version of this script.
`complete` fails unless SHA256SUMS lists a file of every kind in PACKAGES (the .deb, the .tar.gz,
and the Windows setup program and zip): a release that lacks one is not made.
"""

from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The release workflow runs `check` and `notes` before (or without) installing the package, so the
# legal texts are imported from the source folder (they need the standard library only).
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from harness_design_studio.core import legal_texts  # noqa: E402
from tools.release_check import unreleased_text  # noqa: E402

REPO_URL = "https://github.com/0h3xn4/wireviz_harness-design-studio"
SIGNED_FROM = (1, 17, 1)  # the first release made by the workflow that signs (decision D-213)
CAVEAT_UNSIGNED = (
    "The packages are not signed, the configuration values are placeholders and the parts are "
    "example parts: this release is not a statement of compliance with any standard."
)
CAVEAT_SIGNED = (
    "The packages are signed with Sigstore (see *Check your download*), the configuration values "
    "are placeholders and the parts are example parts: this release is not a statement of "
    "compliance with any standard."
)
COSIGN_VERIFY = (
    "cosign verify-blob --bundle <file>.sigstore.json "
    "--certificate-identity-regexp '(?i)^https://github.com/0h3xn4/wireviz_harness-design-studio/"
    "\\.github/workflows/release\\.yml@refs/tags/v' "
    "--certificate-oidc-issuer https://token.actions.githubusercontent.com <file>"
)


def is_signed(version: str) -> bool:
    """Releases from `SIGNED_FROM` on are signed and attested; earlier ones are not."""
    parts = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    return parts is not None and tuple(int(p) for p in parts.groups()) >= SIGNED_FROM


LEGAL_SECTION = (
    "## Status, licence and limits\n\n"
    + f"{legal_texts.DISCLAIMER}\n\n"
    + f"{legal_texts.INTENDED_USE}\n\n"
    + f"{legal_texts.PROJECT_STATUS} {legal_texts.NOT_REVIEWED}\n\n"
    + f"{legal_texts.AI_AUTHORSHIP} {legal_texts.COPYRIGHT_SCOPE}\n\n"
    + f"{legal_texts.LICENCE}\n\n"
    + f"{legal_texts.NON_AFFILIATION} {legal_texts.TRADEMARKS}"
)
INTRO = (
    "**Harness Design Studio** is an offline tool for designing the electrical harnesses of a "
    "spacecraft. You describe the devices and the interfaces between them; the tool generates the "
    "harnesses, checks them against design rules and writes the drawings, wire lists and test "
    "tables. It makes no network connection, and the same design gives byte-identical files for the same version of the tool."
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
            'has no Windows code-signing certificate, so Windows SmartScreen shows "Windows '
            'protected your PC": choose **More info**, then **Run anyway**.',
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


def missing_packages(version: str, names: list[str]) -> list[str]:
    """The kinds of package (by their file name pattern) for which `names` holds no file."""
    have = {package.key for package, _ in _found(version, names)}
    return [
        package.pattern.format(v=version).replace("\\", "")
        for package in PACKAGES
        if package.key not in have
    ]


def _first_paragraph(text: str) -> str:
    return text.strip().split("\n\n", 1)[0].strip()


def notes(version: str, changelog: str, sums: str, highlights: str | None = None) -> str:
    rows = parse_sums(sums)
    names = [name for name, _ in rows]
    found = _found(version, names)
    body = section(changelog, version) or ""
    lead = (highlights or "").strip() or _first_paragraph(body)
    signed = is_signed(version)
    parts = [INTRO, f"> {CAVEAT_SIGNED if signed else CAVEAT_UNSIGNED}"]

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
            + "\n\nNothing needs the network after installing. Full instructions, including what to do when something fails: "
            f"[`INSTALL.md`]({REPO_URL}/blob/v{version}/HarnessDesignStudio/docs/INSTALL.md)."
        )

    sums_table = "\n".join(
        ["| File | SHA-256 |", "| --- | --- |", *(f"| `{n}` | `{d}` |" for n, d in rows)]
    )
    keys = {package.key for package, _ in found}
    commands = []
    if keys & {"deb", "tar"} or not keys:
        commands.append("`sha256sum -c SHA256SUMS` (Linux)")
    if keys & {"win-setup", "win-zip"} or not keys:
        commands.append("`Get-FileHash <file> -Algorithm SHA256` in PowerShell (Windows)")
    parts.append(
        "## Check your download\n\n"
        f"{sums_table}\n\n"
        "Put the file you downloaded and `SHA256SUMS` in one folder, then run "
        + ", ".join(commands)
        + " and compare the result with the table. "
        + (
            "Every file is also signed with Sigstore (the `.sigstore.json` file beside it) and has "
            "a build provenance attestation. Check the signature with "
            f"`{COSIGN_VERIFY}` (install cosign first) and the attestation with "
            "`gh attestation verify <file> --repo 0h3xn4/wireviz_harness-design-studio`. The "
            "same commands, per platform, are in "
            f"[`INSTALL.md`]({REPO_URL}/blob/v{version}/HarnessDesignStudio/docs/INSTALL.md)."
            if signed
            else "The packages are not signed, so this check is the only proof that a download "
            "is intact."
        )
    )
    parts.append(LEGAL_SECTION)
    parts.append(
        "## Good to know\n\n"
        "- By default the tool ships no derating or EMC values and no approved parts list; each "
        "project supplies them (the optional standard profiles write ECSS table values that stay "
        "placeholders until you review them). Until then results say *pending* or *not checked*.\n"
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
    if len(argv) == 2 and argv[0] == "complete":
        names = [name for name, _ in parse_sums(Path(argv[1]).read_text(encoding="utf-8"))]
        absent = missing_packages(version, names)
        for item in absent:
            sys.stderr.write(f"error: no file {item} in {argv[1]}\n")
        return 1 if absent else 0
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
