"""Generate a CycloneDX SBOM and licence report for the RUNTIME dependencies only.

Builds a clean venv (offline from ./wheelhouse if present) so dev tools never appear.
Usage: python -m tools.gen_sbom [OUT_DIR]
"""

import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(out: str = "dist/release-docs") -> int:
    out_dir, env_dir = ROOT / out, ROOT / "build" / "runtime-env"
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(env_dir, ignore_errors=True)
    venv.create(env_dir, with_pip=True)
    py = env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    pip = [str(py), "-m", "pip", "install", "-q"]
    if (ROOT / "wheelhouse").is_dir():
        pip += ["--no-index", "--find-links", str(ROOT / "wheelhouse")]
    subprocess.run([*pip, f"{ROOT}[gui]"], check=True)
    sbom = out_dir / "sbom.cdx.json"
    subprocess.run(
        [sys.executable, "-m", "cyclonedx_py", "environment", "--of", "JSON",
         "--output-reproducible", "-o", str(sbom), str(py)],
        check=True,
    )  # fmt: skip
    from tools.licence_report import main as licence_main

    return licence_main(str(out_dir / "licence-report.md"), str(py))


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:2]))
