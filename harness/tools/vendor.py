"""Download every pinned wheel into a local folder for offline installs (run on a connected host).

Install later without network:  pip install --no-index --find-links wheelhouse harness-design-studio[gui]
"""

import subprocess
import sys
from pathlib import Path


def main(dest: str = "wheelhouse", extras: str = "gui,dev") -> int:
    Path(dest).mkdir(exist_ok=True)
    cmd = [sys.executable, "-m", "pip", "download", "--dest", dest, f".[{extras}]"]
    if subprocess.run(cmd, check=False).returncode:
        return 1
    # the build backend (pyproject.toml, [build-system]) is needed to build the wheel offline
    backend = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--dest",
        dest,
        "setuptools==84.0.0",
    ]  # this setuptools builds wheels itself: the separate, unpinned `wheel` package is not needed
    return subprocess.run(backend, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:3]))
