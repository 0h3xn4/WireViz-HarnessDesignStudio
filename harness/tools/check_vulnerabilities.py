"""Check the shipped dependencies for known vulnerabilities (ECSS-E-ST-40C 5.9.4; action A-08).

Reads the runtime SBOM written by `tools.gen_sbom` (dist/release-docs/sbom.cdx.json), turns its
components into pinned requirements and asks `pip-audit` (build host only, needs network access
there; the tool itself never does) whether any has a known vulnerability. Writes the full output to
dist/release-docs/vulnerability-report.txt.
Usage: python -m tools.check_vulnerabilities [SBOM]
Exit code: 0 none found, 1 vulnerabilities found, 2 the scan could not run (not a pass).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
# Installed in the runtime environment but not shipped with the program.
NOT_SHIPPED = {"pip", "setuptools", "wheel"}


def own_name() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["name"])


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirements(sbom: dict[str, Any], own: str) -> list[str]:
    skip = {norm(own), *map(norm, NOT_SHIPPED)}
    pins = {
        f"{c['name']}=={c['version']}"
        for c in sbom.get("components", [])
        if norm(c["name"]) not in skip and c.get("version")
    }
    return sorted(pins, key=str.lower)


def main(sbom_path: str | None = None) -> int:
    path = Path(sbom_path) if sbom_path else ROOT / "dist" / "release-docs" / "sbom.cdx.json"
    out = ROOT / "dist" / "release-docs" / "vulnerability-report.txt"
    if not path.is_file():
        print(f"no SBOM at {path}; run python -m tools.gen_sbom first")
        return 2
    reqs = requirements(json.loads(path.read_text(encoding="utf-8")), own_name())
    if not reqs:
        print("the SBOM lists no components")
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        req = Path(tmp) / "requirements.txt"
        req.write_text("\n".join(reqs) + "\n", encoding="utf-8")
        try:
            run = subprocess.run(
                [sys.executable, "-m", "pip_audit", "--requirement", str(req), "--no-deps",
                 "--disable-pip", "--progress-spinner", "off"],
                capture_output=True, text=True, timeout=600, check=False,
            )  # fmt: skip
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"the scan could not run: {exc}")
            return 2
    text = (run.stdout + run.stderr).strip()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"checked {len(reqs)} packages\n" + "\n".join(reqs) + "\n\n" + text + "\n")
    # pip-audit: 0 = nothing found, 1 = vulnerabilities found; other failures (no network, a
    # package missing from the index) must not read as a pass.
    if run.returncode == 0:
        print(f"no known vulnerabilities in {len(reqs)} packages")
        return 0
    if "vulnerab" in text.lower() and "found" in text.lower():
        print(text.splitlines()[0] if text else "vulnerabilities found")
        return 1
    print("the scan could not run: " + (text.splitlines()[-1] if text else "no output"))
    return 2


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:2]))
