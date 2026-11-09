# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The third-party components of a built package: inventory, SBOM and notices (decision D-211).

The inventory is made from the package folder itself, not from the metadata of a build environment:
every Python distribution (its `.dist-info`), the Python runtime, Qt and its modules, the libraries
of the operating system that the Linux packages carry (each one found with `dpkg -S`, so the version
and the copyright file are the ones of the Debian package it came from), the fonts and icons, the
PyInstaller bootloader and, for the Windows packages, the Microsoft and Mesa libraries.

    python -m tools.third_party inventory PACKAGE_DIR --format linux|windows --version X.Y.Z --out DIR
    python -m tools.third_party check PACKAGE_DIR --format linux|windows --committed FILE.json

`inventory` writes, into DIR: `third-party-inventory-<version>-<format>.json` (the machine-readable
list), `third-party-inventory-<version>-<format>.md`, `sbom-<version>-<format>.cdx.json` (CycloneDX)
and `THIRD_PARTY_NOTICES-<format>.txt` (name, version, licence, copyright and the licence texts).
`check` fails when a file of the package is not in the committed inventory, when the inventory names
a file the package does not have, when a component has no known licence, or when a licence is not on
the allow-list of `tools/licence_report.py`.

The Qt for Python version is the Qt version (PySide6 6.11.2 carries Qt 6.11.2). Qt itself contains
code of other projects; their notices are listed in the Qt documentation ("Third-Party Licenses Used
in Qt") and are named once in the notices file, not copied here.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from email import message_from_string
from pathlib import Path
from typing import Any

from harness_design_studio.core import legal_texts
from tools.licence_report import classify

COMMON_LICENCES = Path("/usr/share/common-licenses")
DEBIAN_DOC = Path("/usr/share/doc")
QT_CHOICE = (
    "LGPL-3.0-only (chosen; Qt for Python and Qt are also offered under GPL-2.0-only, GPL-3.0-only "
    "and a commercial licence)"
)
PYINSTALLER_LICENCE = "GPL-2.0-or-later WITH Bootloader-exception"
UNKNOWN = "unknown"
# rows of LICENSES/README.txt that are not Python distributions
NOT_PYTHON_ROWS = {"inter", "jetbrains-mono", "lucide", "harness-design-studio"}

# Files that are not third-party components: the program itself and what belongs to the build.
OWN_PARTS = ("harness_design_studio", "harness-design-studio", "LICENSES", "LICENSE", "NOTICE")

# Windows libraries that cannot be asked of a package manager: file name pattern, component,
# licence. The order matters (first match wins). A DLL that matches none of them is "unclassified"
# and the check fails, so a new library never ships without a decision.
WINDOWS_TABLE: tuple[tuple[str, str, str, str], ...] = (
    (
        r"(?i)^(vcruntime140(_1)?|msvcp140(_\d)?|concrt140|vcomp140)\.dll$",
        "Microsoft Visual C++ Runtime",
        "LicenseRef-Microsoft-Redistributable (VC runtime)",
        "redistributable",
    ),
    (
        r"(?i)^ucrtbase\.dll$|^api-ms-win-.*\.dll$",
        "Microsoft Universal C Runtime",
        "LicenseRef-Microsoft-Redistributable (UCRT)",
        "redistributable",
    ),
    (
        r"(?i)^opengl32sw\.dll$",
        "Mesa 3D (software OpenGL) with LLVM",
        "MIT AND Apache-2.0 WITH LLVM-exception",
        "mesa",
    ),
    (r"(?i)^(libssl|libcrypto)-.*\.dll$", "OpenSSL", "Apache-2.0", "openssl"),
    (r"(?i)^libffi.*\.dll$", "libffi", "MIT", "libffi"),
    (r"(?i)^(zlib|libz).*\.dll$", "zlib", "Zlib", "zlib"),
    (r"(?i)^(libbz2|bz2).*\.dll$", "bzip2", "bzip2-1.0.6", "bzip2"),
    (r"(?i)^(liblzma|lzma).*\.dll$", "xz (liblzma)", "0BSD", "xz"),
    (r"(?i)^(sqlite3|sqlite).*\.dll$", "SQLite", "blessing", "sqlite"),
)

# The licence of each Ubuntu 24.04 package whose library the Linux packages carry, as its Debian
# copyright file states it (reviewed once for the audit of 2026-11-09, compliance/legal/audit-annex-
# third-party.md; most of these files are free text, not machine readable). A package that is not
# here has no known licence and fails the check: a person decides first (owner-checklist.md).
_X = "MIT"
SYSTEM_LICENCES: dict[str, str] = {
    **{p: _X for p in (
        "libx11-6", "libx11-xcb1", "libxau6", "libxcomposite1", "libxcursor1", "libxdamage1", "libxdmcp6",
        "libxext6", "libxfixes3", "libxi6", "libxinerama1", "libxrandr2", "libxrender1", "libxcb-cursor0",
        "libxcb-glx0", "libxcb-icccm4", "libxcb-image0", "libxcb-keysyms1", "libxcb-randr0",
        "libxcb-render-util0", "libxcb-render0", "libxcb-shape0", "libxcb-shm0", "libxcb-sync1", "libxcb-util1",
        "libxcb-xfixes0", "libxcb-xkb1", "libxkbcommon0", "libxkbcommon-x11-0", "libepoxy0", "libexpat1",
        "libffi8", "libharfbuzz0b", "libpixman-1-0", "libbrotli1", "libgssapi-krb5-2", "libk5crypto3",
        "libkrb5-3", "libkrb5support0", "libcom-err2",
    )},
    "libatk1.0-0t64": "LGPL-2.0-or-later", "libatk-bridge2.0-0t64": "LGPL-2.0-or-later",
    "libatspi2.0-0t64": "LGPL-2.0-or-later", "libblkid1": "LGPL-2.1-or-later", "libmount1": "LGPL-2.1-or-later",
    "libuuid1": "BSD-3-Clause", "libbsd0": "BSD-3-Clause AND ISC", "libbz2-1.0": "bzip2-1.0.6",
    "libcairo2": "LGPL-2.1-only OR MPL-1.1", "libcairo-gobject2": "LGPL-2.1-only OR MPL-1.1",
    "libcap2": "BSD-3-Clause OR GPL-2.0-only", "libssl3t64": "Apache-2.0", "libdatrie1": "LGPL-2.1-or-later",
    "libdbus-1-3": "AFL-2.1 OR GPL-2.0-or-later", "libfontconfig1": "HPND-sell-variant",
    "libfreetype6": "FTL OR GPL-2.0-or-later", "libfribidi0": "LGPL-2.1-or-later",
    "libgcc-s1": "GPL-3.0-or-later WITH GCC-exception-3.1", "libstdc++6": "GPL-3.0-or-later WITH GCC-exception-3.1",
    "libgcrypt20": "LGPL-2.1-or-later", "libgtk-3-0t64": "LGPL-2.0-or-later AND LGPL-2.1-or-later AND MIT",
    "libgdk-pixbuf-2.0-0": "LGPL-2.0-or-later AND LGPL-2.1-or-later AND CC0-1.0",
    "libglib2.0-0t64": "LGPL-2.1-or-later", "libgpg-error0": "LGPL-2.1-or-later",
    "libgraphite2-3": "LGPL-2.1-or-later OR MPL-1.1 OR GPL-2.0-or-later", "libjpeg-turbo8": "IJG AND BSD-3-Clause AND Zlib",
    "libkeyutils1": "LGPL-2.0-or-later", "liblz4-1": "BSD-2-Clause", "liblzma5": "public domain",
    "libmd0": "BSD-3-Clause AND ISC AND public domain", "libpango-1.0-0": "LGPL-2.0-or-later AND LGPL-2.1-or-later",
    "libpangocairo-1.0-0": "LGPL-2.0-or-later AND LGPL-2.1-or-later",
    "libpangoft2-1.0-0": "LGPL-2.0-or-later AND LGPL-2.1-or-later", "libpcre2-8-0": "BSD-3-Clause",
    "libpng16-16t64": "libpng-2.0", "libselinux1": "public domain", "libsystemd0": "LGPL-2.1-or-later",
    "libthai0": "LGPL-2.1-or-later", "zlib1g": "Zlib", "libzstd1": "BSD-3-Clause OR GPL-2.0-only",
}  # fmt: skip


@dataclass
class Component:
    name: str
    version: str
    licence: str
    kind: str
    origin: str
    files: list[str] = field(default_factory=list)
    copyright: str = ""
    texts: dict[str, str] = field(default_factory=dict)  # licence file name -> text

    def key(self) -> tuple[str, str]:
        return (self.name.lower(), self.version)


# ---- the inventory ------------------------------------------------------------------------------


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _read(path: Path, limit: int = 200_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def python_distributions(app: Path) -> list[Component]:
    """Every `.dist-info` in the package: name, version, licence and the licence files it carries."""
    out: list[Component] = []
    for info in sorted(app.rglob("*.dist-info")):
        meta = message_from_string(_read(info / "METADATA"))
        name, version = meta.get("Name", ""), meta.get("Version", "")
        if not name or _norm(name) == "harness-design-studio":
            continue
        licence = meta.get("License-Expression") or meta.get("License") or ""
        if (
            not licence or licence == UNKNOWN or len(licence) > 120
        ):  # a whole licence text is no name
            classifiers = [
                c.split("::")[-1].strip()
                for c in meta.get_all("Classifier", [])
                if "License ::" in c
            ]
            licence = (
                " OR ".join(classifiers)
                if classifiers
                else (meta.get("License-Expression") or UNKNOWN)
            )
        texts = {}
        for f in sorted(info.rglob("*")):
            if f.is_file() and re.search(r"(licen[sc]e|copying|notice|authors)", f.name, re.I):
                texts[f.relative_to(info).as_posix()] = _read(f)
        out.append(
            Component(
                name,
                version,
                licence,
                "python",
                "dist-info METADATA",
                [info.relative_to(app).as_posix()],
                _copyright_lines(texts),
                texts,
            )  # fmt: skip
        )
    seen = {_norm(c.name) for c in out}
    readme = app / "LICENSES" / "README.txt"  # written by tools/collect_licences.py at build time
    for line in _read(readme).splitlines():
        row = re.fullmatch(r"([A-Za-z0-9_.-]+) (\d[\w.+!-]*): (.+)", line.strip())
        if row is None or _norm(row.group(1)) in seen or _norm(row.group(1)) in NOT_PYTHON_ROWS:
            continue
        name, version, licence = row.groups()
        folder = app / "LICENSES" / _norm(name)
        texts = (
            {f.name: _read(f) for f in sorted(folder.glob("*")) if f.is_file()}
            if folder.is_dir()
            else {}
        )
        out.append(
            Component(
                name,
                version,
                licence,
                "python",
                "LICENSES/README.txt of the package (written at build time)",
                [f"LICENSES/{_norm(name)}/{n}" for n in texts],
                _copyright_lines(texts),
                texts,
            )  # fmt: skip
        )
        seen.add(_norm(name))
    return out


def _copyright_lines(texts: dict[str, str]) -> str:
    found: list[str] = []
    for text in texts.values():
        for line in text.splitlines():
            if (
                re.match(r"\s*(copyright\s*(\(c\)|©|\d{4})|\(c\)\s*\d{4})", line, re.I)
                and line.strip() not in found
            ):
                found.append(line.strip())
    return "\n".join(found[:8])


def qt_component(app: Path, dists: list[Component]) -> Component | None:
    """Qt 6.x from the Qt libraries beside PySide6 (the Qt version is the PySide6 version)."""
    libs = sorted(p for p in app.rglob("*") if re.search(r"(libQt6\w+\.so|Qt6\w+\.dll)", p.name))
    if not libs:
        return None
    version = next((d.version for d in dists if _norm(d.name).startswith("pyside6")), UNKNOWN)
    modules = sorted({re.sub(r"^(lib)?Qt6|\.so.*|\.dll$", "", p.name) for p in libs})
    plugins = sorted(p for p in app.rglob("*") if p.is_file() and "/plugins/" in p.as_posix())
    texts = {
        n: _read(app / "LICENSES" / n)
        for n in ("LGPL-3.txt", "GPL-3.txt")
        if (app / "LICENSES" / n).is_file()
    }
    return Component(
        f"Qt ({', '.join(modules)})", version, QT_CHOICE, "qt", "library file names; version of PySide6",
        [p.relative_to(app).as_posix() for p in [*libs, *plugins]],
        "Copyright (C) The Qt Company Ltd. and other contributors", texts,
    )  # fmt: skip


def _python_licence_texts() -> dict[str, str]:
    """The licence of CPython, from the interpreter that runs this tool (the one that built the
    package): `LICENSE.txt` of its standard library folder or of its installation."""
    base = Path(sys.base_prefix)
    for candidate in [
        *base.glob("lib/python3*/LICENSE.txt"),
        base / "LICENSE.txt",
        *base.glob("Lib/LICENSE.txt"),
    ]:
        if candidate.is_file():
            return {"PSF-LICENSE.txt": _read(candidate)}
    return {}


def runtime_component(app: Path) -> Component | None:
    libs = sorted(
        p
        for p in app.rglob("*")
        if re.fullmatch(r"(libpython3\.\d+\.so.*|python3\d*\.dll)", p.name)
    )
    if not libs:
        return None
    data = libs[0].read_bytes()
    minor = re.search(r"3\.?(\d\d)", libs[0].name)  # libpython3.14.so: 3.14; python314.dll: 3.14
    found = re.search(
        rb"(?<=\x00)3\.%s\.\d+(?=\x00)" % (minor.group(1).encode() if minor else rb"1\d"), data
    )  # Py_Version string
    version = found.group(0).decode() if found else UNKNOWN
    return Component(
        "CPython runtime", version, "PSF-2.0", "runtime", "library file name; version string inside it",
        [p.relative_to(app).as_posix() for p in libs],
        "Copyright (c) 2001 Python Software Foundation; All Rights Reserved",
        _python_licence_texts(),
    )  # fmt: skip


def _dpkg_owner(basename: str) -> str:
    for pattern in (
        f"/usr/lib/x86_64-linux-gnu/{basename}",
        f"/lib/x86_64-linux-gnu/{basename}",
        f"*/{basename}",
    ):
        try:
            out = subprocess.run(
                ["dpkg", "-S", pattern], capture_output=True, text=True, check=False
            ).stdout
        except OSError:
            return ""
        for line in out.splitlines():
            if ": " in line and not line.startswith("dpkg-query"):
                return line.split(":", 1)[0].split(",")[0].strip()
    return ""


def _dpkg_version(package: str) -> str:
    out = subprocess.run(
        ["dpkg-query", "-W", "-f=${Version}", package.split(":")[0]],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return out.strip() or UNKNOWN


def system_libraries(app: Path, claimed: set[str]) -> list[Component]:
    """The shared libraries that came from the build machine's operating system (Linux packages)."""
    by_pkg: dict[str, Component] = {}
    skip = ("/PySide6/", "/shiboken6/", "/lib-dynload/", "/pydantic_core/", "/yaml/", "/PIL/")
    for p in sorted(app.rglob("*.so*")):
        rel = p.relative_to(app).as_posix()
        if rel in claimed or any(s in f"/{rel}" for s in skip) or ".cpython-" in p.name:
            continue
        if p.is_dir() or re.fullmatch(r"libpython3\.\d+\.so.*", p.name):
            continue
        if re.match(
            r"lib(pyside6|shiboken6)", p.name
        ):  # the Qt for Python libraries: PySide6 and shiboken6
            continue
        if p.name.startswith("libicu"):  # ICU, built into the Qt wheel
            icu = by_pkg.setdefault(
                "icu",
                Component(
                    "ICU (libicudata, libicui18n, libicuuc)",
                    re.sub(r"\D*(\d+)$", r"\1", p.name),
                    "ICU AND Unicode-DFS-2016",
                    "system",
                    "libicu*.so.N beside Qt in the PySide6 wheel; the licence from the ICU project",
                ),
            )
            icu.files.append(rel)
            if not icu.texts:
                icu_doc = _read(
                    DEBIAN_DOC / "libicu74" / "copyright"
                )  # same licence; the bundled ICU is 73
                if icu_doc:
                    icu.texts = {"ICU licence (Debian copyright file of libicu74)": icu_doc}
                    icu.copyright = _copyright_lines(icu.texts)
            continue
        owner = _dpkg_owner(p.name)
        if not owner:
            by_pkg.setdefault(
                "",
                Component("unidentified shared library", "", UNKNOWN, "system", "no owner found"),
            ).files.append(rel)
            continue
        c = by_pkg.get(owner)
        if c is None:
            copy_file = DEBIAN_DOC / owner.split(":")[0] / "copyright"
            text = _read(copy_file)
            c = by_pkg[owner] = Component(
                owner.split(":")[0], _dpkg_version(owner), SYSTEM_LICENCES.get(owner.split(":")[0], UNKNOWN), "system",
                f"dpkg -S {p.name}; /usr/share/doc/{owner.split(':')[0]}/copyright",
                [], _copyright_lines({"copyright": text}), {"copyright": text} if text else {},
            )  # fmt: skip
        c.files.append(rel)
    return sorted(by_pkg.values(), key=lambda c: c.name)


def asset_components(app: Path) -> list[Component]:
    """Fonts, icons and the bootloader: what is in the package but is no Python distribution."""
    out: list[Component] = []
    fonts = sorted(app.rglob("*.ttf"))
    for key, name, version, licence in (
        ("Inter", "Inter (font)", "4.1", "OFL-1.1"),
        ("JetBrainsMono", "JetBrains Mono (font)", "2.304", "OFL-1.1"),
    ):
        files = [p for p in fonts if p.name.startswith(key)]
        if files:
            licences = [p for p in app.rglob("OFL-1.1-*.txt") if key.lower()[:5] in p.name.lower()]
            texts = {p.name: _read(p) for p in licences}
            out.append(
                Component(name, version, licence, "font", "file names; versions from decision D-150",
                          [p.relative_to(app).as_posix() for p in files + licences], _copyright_lines(texts), texts)
            )  # fmt: skip
    icons = app / "LICENSES" / "lucide"
    if icons.is_dir():
        texts = {p.name: _read(p) for p in icons.glob("*") if p.is_file()}
        out.append(
            Component("Lucide and Feather icon outlines (gui/icons.py)", "lucide-static 1.56.0", "ISC AND MIT", "icon",
                      "gui/icons.py", [], _copyright_lines(texts), texts)
        )  # fmt: skip
    try:
        from importlib.metadata import version as dist_version

        pyi = dist_version("pyinstaller")
    except Exception:  # noqa: BLE001 - the tool may run where PyInstaller is not installed
        pyi = UNKNOWN
    out.append(
        Component(
            "PyInstaller bootloader and runtime hooks",
            pyi,
            PYINSTALLER_LICENCE,
            "bootloader",
            "the packages are built with PyInstaller (tools/build_installer.py)",
            [
                p.relative_to(app).as_posix()
                for p in app.glob("harness-design-studio*")
                if p.is_file()
            ][:4],
            "Copyright (c) PyInstaller Development Team",
        )  # fmt: skip
    )
    return out


def windows_components(
    names: Iterable[str], claimed: Collection[str] = (), app: Path | None = None
) -> list[Component]:
    """Windows DLLs by file name, from the table; the rest is "unclassified" (a finding)."""
    found: dict[str, Component] = {}
    for rel in sorted(names):
        base = rel.rsplit("/", 1)[-1]
        if not base.lower().endswith(".dll") or rel in claimed:
            continue
        for pattern, name, licence, _kind in WINDOWS_TABLE:
            if re.match(pattern, base):
                c = found.setdefault(
                    name,
                    Component(
                        name,
                        UNKNOWN,
                        licence,
                        "windows-runtime",
                        "file name pattern (tools/third_party.py)",
                    ),
                )
                c.files.append(rel)
                if name == "OpenSSL" and app is not None and c.version == UNKNOWN:
                    hit = re.search(
                        rb"OpenSSL (\d+\.\d+\.\d+)", (app / rel).read_bytes()[:30_000_000]
                    )
                    c.version = hit.group(1).decode() if hit else UNKNOWN
                break
        else:
            if (
                "/PySide6/" in f"/{rel}"
                or "/pydantic_core/" in f"/{rel}"
                or ".cp3" in base
                or base.startswith(("Qt6", "shiboken6", "pyside6"))
                or "/lib-dynload/" in rel
            ):
                continue
            found.setdefault(
                "unclassified DLL",
                Component("unclassified DLL", "", UNKNOWN, "windows-runtime", "no rule"),
            ).files.append(rel)
    return list(found.values())


def inventory(app: Path, fmt: str) -> list[Component]:
    """The third-party components of the package folder `app`."""
    dists = python_distributions(app)
    qt = qt_component(app, dists)
    runtime = runtime_component(app)
    parts: list[Component] = [*dists]
    claimed: set[str] = set()
    for c in (qt, runtime):
        if c is not None:
            parts.append(c)
            claimed.update(c.files)
    if fmt == "linux":
        parts += system_libraries(app, claimed)
    else:
        parts += windows_components(
            (p.relative_to(app).as_posix() for p in app.rglob("*.dll")), claimed, app
        )
    parts += asset_components(app)
    merged: dict[tuple[str, str, str], Component] = {}
    for c in parts:  # the same distribution in `_internal` and `cli/_internal` is one component
        key = (c.kind, c.name.lower(), c.version)
        if key in merged:
            merged[key].files = sorted(set(merged[key].files) | set(c.files))
        else:
            merged[key] = c
    return sorted(merged.values(), key=lambda c: (c.kind, c.name.lower()))


# ---- the outputs --------------------------------------------------------------------------------


def to_json(parts: list[Component], version: str, fmt: str) -> str:
    rows = [
        {
            "name": c.name,
            "version": c.version,
            "licence": c.licence,
            "kind": c.kind,
            "origin": c.origin,
            "files": sorted(c.files),
        }
        for c in parts
    ]
    return (
        json.dumps(
            {"tool_version": version, "format": fmt, "components": rows}, indent=1, sort_keys=True
        )
        + "\n"
    )


def to_markdown(parts: list[Component], version: str, fmt: str) -> str:
    out = [
        f"# Third-party inventory {version} ({fmt})",
        "",
        "Made from the built package (`python -m tools.third_party inventory`), not from the metadata of a build "
        "environment. Not legal advice; a licence marked `unknown` or `LicenseRef-` needs a person's decision.",
        "",
        "| Component | Version | Licence | Kind | Source of the information | Files |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in parts:
        out.append(
            f"| {c.name} | {c.version} | {c.licence} | {c.kind} | {c.origin} | {len(c.files)} |"
        )
    return "\n".join(out) + "\n"


def to_cyclonedx(parts: list[Component], version: str, fmt: str) -> str:
    comps = []
    for c in parts:
        ref = f"{c.kind}:{_norm(c.name)}@{c.version}"
        comps.append(
            {
                "type": "library" if c.kind != "font" else "data",
                "bom-ref": ref,
                "name": c.name,
                "version": c.version,
                "licenses": [{"expression": c.licence}]
                if re.fullmatch(r"[A-Za-z0-9.+ -]+( (AND|OR|WITH) [A-Za-z0-9.+-]+)*", c.licence)
                else [{"license": {"name": c.licence}}],
                "properties": [
                    {"name": "kind", "value": c.kind},
                    {"name": "origin", "value": c.origin},
                ],
            }
        )
    doc = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": f"harness-design-studio-{fmt}",
                "version": version,
                "licenses": [{"license": {"id": "GPL-3.0-only"}}],
            }
        },
        "components": comps,
    }
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def referenced_common_licences(parts: list[Component]) -> dict[str, str]:
    names: set[str] = set()
    for c in parts:
        for text in c.texts.values():
            names.update(re.findall(r"/usr/share/common-licenses/([A-Za-z0-9][\w.+-]*)", text))
    return {n: _read(COMMON_LICENCES / n) for n in sorted(names) if (COMMON_LICENCES / n).is_file()}


def to_notices(
    parts: list[Component], version: str, fmt: str, also: list[Component] | None = None
) -> str:
    """The notices file. `also`: components of another package format that this one lacks; they are
    added under their own heading (the notices file in the repository covers both formats)."""
    out = [
        f"THIRD-PARTY NOTICES: Harness Design Studio {version} ({fmt} package)",
        "=" * 72,
        "",
        legal_texts.LICENCE
        + " This file lists the components of other authors that this package contains: name, "
        "version, licence, copyright notice and the licence text. The notices were made from the built package "
        "(tools/third_party.py).",
        "",
        "SOURCE CODE. For every component under the GNU General Public Licence or the GNU Lesser General Public "
        "Licence (Qt for Python and Qt, and the libraries of the operating system listed below) the corresponding "
        "source code is offered: source archives are attached to the release page of this version, and the "
        "package sources of the libraries named `Debian package` are in the Ubuntu 24.04 archive "
        "(https://archive.ubuntu.com/ubuntu/pool/) under the version given here. This offer is valid for at least "
        "three years after the release. The libraries are separate files in this package; you may replace them "
        "with another build of the same version (for Qt for Python: replace the files under the PySide6 folder).",
        "",
        'Qt contains code of other projects, listed in the Qt documentation under "Third-Party Licenses Used in Qt" '
        "for Qt 6 (https://doc.qt.io/qt-6/licenses-used-in-qt.html); the Qt libraries of this package are the "
        "unchanged libraries of the PySide6-Essentials wheel.",
        "",
    ]
    out += _blocks(parts)
    if also:
        out += ["=" * 72, "ADDITIONAL COMPONENTS OF THE WINDOWS PACKAGES", "=" * 72, ""]
        out += _blocks(also)
    common = referenced_common_licences([*parts, *(also or [])])
    for name, text in common.items():
        out += ["-" * 72, f"Licence text referenced above: {name}", "", text.strip(), ""]
    return "\n".join(out) + "\n"


def _blocks(parts: list[Component]) -> list[str]:
    out: list[str] = []
    for c in parts:
        out += [
            "-" * 72,
            f"{c.name}  {c.version}".rstrip(),
            f"Licence: {c.licence}",
            f"Kind: {c.kind}",
        ]
        if c.copyright:
            out += ["Copyright:", *("  " + ln for ln in c.copyright.splitlines())]
        for name, text in c.texts.items():
            out += ["", f"--- {name} ---", text.strip()]
        out.append("")
    return out


# ---- the check ----------------------------------------------------------------------------------


def problems(parts: list[Component]) -> list[str]:
    found = []
    for c in parts:
        if c.kind in ("windows-runtime",) and c.licence.startswith("LicenseRef-Microsoft"):
            continue  # a redistributable: a person decided (owner-checklist.md), recorded in the notices
        if c.licence == UNKNOWN or not c.licence.strip():
            found.append(f"{c.name} {c.version}: no known licence")
        elif classify(c.licence) == "rejected" and not c.licence.startswith(
            ("LGPL", "Qt", "GPL-2.0-or-later WITH")
        ):
            found.append(f"{c.name} {c.version}: licence not on the allow-list: {c.licence}")
    return found


def drift(parts: list[Component], committed: dict[str, Any]) -> list[str]:
    """Files of the package that the committed inventory does not list, and the other way round."""
    now = {f for c in parts for f in c.files}
    before = {f for row in committed.get("components", []) for f in row["files"]}
    out = [f"in the package, not in the inventory: {f}" for f in sorted(now - before)]
    out += [f"in the inventory, not in the package: {f}" for f in sorted(before - now)]
    return out


def package_folder(arg: Path, work: Path) -> Path:
    """A package folder, or a `.zip` (a Windows package) unpacked into `work`."""
    if arg.is_dir():
        return arg
    if arg.suffix == ".zip":
        with zipfile.ZipFile(arg) as z:
            z.extractall(work)
        entries = [p for p in work.iterdir() if p.is_dir()]
        return entries[0] if len(entries) == 1 and not list(work.glob("*.exe")) else work
    raise SystemExit(f"not a folder or a .zip: {arg}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("inventory", "check"):
        p = sub.add_parser(name)
        p.add_argument("package", type=Path)
        p.add_argument("--format", choices=("linux", "windows"), required=True)
        p.add_argument("--version", default="")
        if name == "inventory":
            p.add_argument("--out", type=Path, required=True)
            p.add_argument(
                "--also-windows",
                type=Path,
                help="a Windows package: its extra components go into THIRD_PARTY_NOTICES.txt",
            )
        else:
            p.add_argument("--committed", type=Path, required=True)
    args = ap.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        app = package_folder(args.package, Path(tmp))
        parts = inventory(app, args.format)
    bad = problems(parts)
    if args.cmd == "inventory":
        args.out.mkdir(parents=True, exist_ok=True)
        v, f = args.version, args.format
        (args.out / f"third-party-inventory-{v}-{f}.json").write_text(
            to_json(parts, v, f), encoding="utf-8"
        )
        (args.out / f"third-party-inventory-{v}-{f}.md").write_text(
            to_markdown(parts, v, f), encoding="utf-8"
        )
        (args.out / f"sbom-{v}-{f}.cdx.json").write_text(
            to_cyclonedx(parts, v, f), encoding="utf-8"
        )
        (args.out / f"THIRD_PARTY_NOTICES-{f}.txt").write_text(
            to_notices(parts, v, f), encoding="utf-8"
        )
        if args.also_windows is not None:
            with tempfile.TemporaryDirectory() as tmp2:
                other = inventory(package_folder(args.also_windows, Path(tmp2)), "windows")
            have = {c.key() for c in parts}
            extra = [c for c in other if c.key() not in have]
            (args.out / "THIRD_PARTY_NOTICES.txt").write_text(
                to_notices(parts, v, f, extra), encoding="utf-8"
            )
        print(f"{len(parts)} components, {len(bad)} problem(s)")
        for line in bad:
            print(f"problem: {line}", file=sys.stderr)
        return 1 if bad else 0
    committed = json.loads(args.committed.read_text(encoding="utf-8"))
    found = [*bad, *drift(parts, committed)]
    for line in found:
        print(line, file=sys.stderr)
    print(f"{len(parts)} components, {len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
