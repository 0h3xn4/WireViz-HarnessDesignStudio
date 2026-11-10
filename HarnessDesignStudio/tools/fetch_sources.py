# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Fetch the corresponding source of the LGPL and GPL components of a release (decision D-213).

    python -m tools.fetch_sources INVENTORY.json --out DIR

The inventory is the file `tools/third_party.py inventory` wrote for the Linux package. The tool
fetches

- the Qt for Python source (`pyside-setup-everywhere-src-<version>.tar.xz`) and the Qt modules that
  the package carries (qtbase, qtsvg, qtwayland), each of the version of the Qt libraries in the
  package, from download.qt.io, and checks each against the `md5sums.txt` that Qt publishes beside it;
- the Debian source package (`.dsc`, `.orig.tar.*`, `.debian.tar.*`) of every library of the
  operating system that the package carries, in the version in the inventory, with `apt-get source`
  (the machine needs `deb-src` lines; the release workflow adds them).

It writes `SOURCES.txt` into DIR: the file name, size and SHA-256 of everything it fetched. The
release workflow attaches the files to the release page, which is where the notices file says the
source is. The tool stops with an error when a file cannot be fetched or does not match.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

QT_BASE = "https://download.qt.io/official_releases"
QT_MODULES = ("qtbase", "qtsvg", "qtwayland")


def qt_downloads(version: str) -> list[tuple[str, str, str]]:
    """(file name, URL, URL of the md5sums.txt beside it) for the Qt sources of `version`."""
    major_minor = ".".join(version.split(".")[:2])
    sub = f"{QT_BASE}/qt/{major_minor}/{version}/submodules"
    out = [
        (
            f"{m}-everywhere-src-{version}.tar.xz",
            f"{sub}/{m}-everywhere-src-{version}.tar.xz",
            f"{sub}/md5sums.txt",
        )
        for m in QT_MODULES
    ]
    pyside = f"{QT_BASE}/QtForPython/pyside6/PySide6-{version}-src"
    name = f"pyside-setup-everywhere-src-{version}.tar.xz"
    out.append((name, f"{pyside}/{name}", f"{pyside}/md5sums.txt"))
    return out


def debian_packages(inventory: Mapping[str, Any]) -> list[tuple[str, str]]:
    """(package, version) of every Debian package behind a library of the Linux package."""
    seen: dict[str, str] = {}
    for row in inventory["components"]:
        if (
            row["kind"] == "system"
            and row["origin"].startswith("dpkg")
            and row["version"] != "unknown"
        ):
            seen[row["name"]] = row["version"]
    return sorted(seen.items())


def qt_version(inventory: Mapping[str, Any]) -> str:
    for row in inventory["components"]:
        if row["kind"] == "qt" and re.fullmatch(r"\d+\.\d+\.\d+", row["version"]):
            return str(row["version"])
    raise SystemExit("the inventory names no Qt version")


def _get(url: str) -> bytes:
    if not url.startswith("https://"):
        raise SystemExit(f"only https is used: {url}")
    with urllib.request.urlopen(url, timeout=600) as response:  # noqa: S310 - https only, checked above
        return bytes(response.read())


def fetch_qt(version: str, out: Path) -> list[Path]:
    got = []
    for name, url, sums_url in qt_downloads(version):
        data = _get(url)
        sums = _get(sums_url).decode("utf-8", "replace")
        want = next((ln.split()[0] for ln in sums.splitlines() if ln.strip().endswith(name)), None)
        if want is None or hashlib.md5(data).hexdigest() != want:  # noqa: S324 - the check Qt publishes
            raise SystemExit(f"{name}: does not match the md5sums.txt that Qt publishes beside it")
        (out / name).write_bytes(data)
        got.append(out / name)
    return got


def fetch_debian(packages: list[tuple[str, str]], out: Path) -> list[Path]:
    before = {p.name for p in out.iterdir()}
    for name, version in packages:
        result = subprocess.run(  # noqa: S603 - our own arguments, no shell
            ["apt-get", "source", "--download-only", f"{name}={version}"],
            cwd=out,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise SystemExit(f"apt-get source {name}={version} failed:\n{result.stderr[-600:]}")
    return sorted(p for p in out.iterdir() if p.name not in before)


def manifest(files: list[Path]) -> str:
    rows = ["name\tbytes\tsha256"]
    for f in sorted(files):
        rows.append(f"{f.name}\t{f.stat().st_size}\t{hashlib.sha256(f.read_bytes()).hexdigest()}")
    return "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("inventory", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--skip-debian", action="store_true", help="only the Qt sources")
    args = ap.parse_args(argv)
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    files = fetch_qt(qt_version(inventory), args.out)
    if not args.skip_debian:
        files += fetch_debian(debian_packages(inventory), args.out)
    (args.out / "SOURCES.txt").write_text(manifest(files), encoding="utf-8")
    print(f"{len(files)} source file(s) in {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
