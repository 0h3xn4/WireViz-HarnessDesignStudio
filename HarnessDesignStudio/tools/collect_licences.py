"""Collect the licence texts of the shipped runtime packages into a LICENSES folder.

Qt for Python (PySide6, shiboken6) is LGPL-3.0: its licence text, and the GPL-3 text it refers to,
ship with the package. The texts of the other packages come from their own metadata. The build
fails when a runtime package has no licence file or when the LGPL text cannot be found.

Usage: python -m tools.collect_licences DEST
"""

import re
import shutil
import sys
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement

from harness_design_studio.gui.licences import LUCIDE_LICENCES as LUCIDE_LICENCES

COMMON = Path("/usr/share/common-licenses")  # Debian and Ubuntu base-files
BUNDLED = (
    Path(__file__).resolve().parents[1] / "packaging" / "licences"
)  # the same texts, for Windows builds
LICENCE_FILE = re.compile(r"(^|/)(licen[sc]e|copying|notice|authors)[^/]*$", re.IGNORECASE)


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def runtime_distributions(root: str = "harness-design-studio") -> dict[str, metadata.Distribution]:
    """The installed distributions the app needs at run time: its dependencies (and the `gui` extra),
    and theirs, never the `dev` extra."""
    found: dict[str, metadata.Distribution] = {}
    todo = [(root, {"gui"})]
    while todo:
        name, extras = todo.pop()
        key = _norm(name)
        if key in found:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        found[key] = dist
        for line in dist.requires or []:
            req = Requirement(line)
            if req.marker is not None and not any(
                req.marker.evaluate({"extra": e}) for e in (extras | {""})
            ):
                continue
            todo.append((req.name, set()))
    found.pop(_norm(root), None)
    return found


def collect(dest: Path) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    rows, problems, lgpl = [], [], False
    for key, dist in sorted(runtime_distributions().items()):
        meta = dist.metadata
        licence = (
            meta.get("License-Expression")
            or meta.get("License")
            or ", ".join(
                c.split("::")[-1].strip()
                for c in meta.get_all("Classifier", [])
                if "License ::" in c
            )
        )
        lgpl = lgpl or "lgpl" in licence.lower() or "lesser general" in licence.lower()
        rows.append(f"{meta['Name']} {meta['Version']}: {licence or 'see its files'}")
        files = [f for f in (dist.files or []) if LICENCE_FILE.search(f.as_posix())]
        if not files and "lgpl" not in licence.lower():
            problems.append(f"{meta['Name']} ships no licence file")
        for f in files:
            target = dest / key / Path(f.as_posix()).name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(str(dist.locate_file(f))), target)
    fonts = Path(__file__).resolve().parents[1] / "src/harness_design_studio/resources/fonts"
    for key, label, text in (
        ("inter", "Inter 4.1 (font)", "OFL-1.1-Inter.txt"),
        ("jetbrains-mono", "JetBrains Mono 2.304 (font)", "OFL-1.1-JetBrains-Mono.txt"),
    ):
        ofl = fonts / text  # the bundled fonts are not Python packages: record them here
        if ofl.is_file():
            rows.append(f"{label}: OFL-1.1")
            (dest / key).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ofl, dest / key / ofl.name)
        else:
            problems.append(f"the licence text of the bundled {label} is missing")
    rows.append(
        "Lucide icon outlines in gui/icons.py (lucide-static 1.56.0): ISC; some derive from Feather: MIT"
    )
    (dest / "lucide").mkdir(parents=True, exist_ok=True)
    (dest / "lucide" / "LICENSE.txt").write_text(LUCIDE_LICENCES, encoding="utf-8")
    if lgpl:
        for name in ("LGPL-3", "GPL-3"):
            src = COMMON / name
            if not src.is_file():
                src = (
                    BUNDLED / name
                )  # no Debian base-files on Windows: use the copy in the repository
            if not src.is_file():
                problems.append(f"{COMMON / name} and {src} not found")
                continue
            shutil.copyfile(src, dest / f"{name}.txt")
    (dest / "README.txt").write_text(
        "Licences of the components shipped with Harness Design Studio\n"
        "====================================================\n\n"
        + "\n".join(rows)
        + "\n\nQt for Python (PySide6, shiboken6) is used under the GNU Lesser General Public "
        "License version 3 (LGPL-3.txt, which refers to GPL-3.txt). It is a separate library in "
        "this package: you may replace it with another build of the same version. Its source is "
        "available from the Qt Project (https://code.qt.io, Qt for Python).\n",
        encoding="utf-8",
    )
    if problems:
        raise SystemExit("Licence texts are incomplete:\n- " + "\n- ".join(problems))
    return rows


if __name__ == "__main__":
    for row in collect(Path(sys.argv[1])):
        print(row)
