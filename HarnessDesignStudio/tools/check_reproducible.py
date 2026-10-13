"""Build the wheel twice with a fixed SOURCE_DATE_EPOCH and require identical hashes."""

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_hash() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "SOURCE_DATE_EPOCH": "1700000000"}
        cmd = [sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", tmp, str(ROOT)]
        subprocess.run(cmd, check=True, env=env)
        (wheel,) = Path(tmp).glob("*.whl")
        return hashlib.sha256(wheel.read_bytes()).hexdigest()


def main() -> int:
    first, second = build_hash(), build_hash()
    print(first, second)
    return 0 if first == second else 1


if __name__ == "__main__":
    raise SystemExit(main())
