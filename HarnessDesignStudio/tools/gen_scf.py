"""Software configuration file and integrity values of a delivery.

ECSS-Q-ST-80C 6.2.4.3, 6.2.4.4, 6.2.4.8 to 6.2.4.11 (gap G-07). Writes, into dist/release-docs:
  scf.json     version, source commit, pinned dependencies, SHA-256 of every source file, and an
               aggregate source integrity value; the deliverables found in dist/ with size and SHA-256
  SHA256SUMS   the deliverables in the format of `sha256sum -c`; the names are relative to dist/,
               so check them with `cd dist && sha256sum -c release-docs/SHA256SUMS`
Deterministic: no dates. The content of ECSS-M-ST-40 Annex E (the SCF DRD) was not supplied, so the
layout is the project's own; compliance/docs/SCF.md says so.
Usage: python -m tools.gen_scf [OUT_DIR]
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FOLDERS = ("src", "tools", "packaging", "tests", "docs", "compliance")
SOURCE_FILES = ("pyproject.toml", "README.md", "CLAUDE.md", "CHANGELOG.md")
DELIVERABLE_SUFFIXES = (
    ".deb",
    ".tar.gz",
    ".exe",
    ".zip",
)  # Linux, Windows (setup, portable)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def source_files(root: Path) -> list[Path]:
    files = [root / f for f in SOURCE_FILES if (root / f).is_file()]
    for folder in SOURCE_FOLDERS:
        files += [
            p
            for p in (root / folder).rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and p.suffix != ".pyc"
            and not any(part.endswith(".egg-info") for part in p.parts)  # pip -e / wheel build
        ]
    return sorted(set(files), key=lambda p: p.relative_to(root).as_posix())


def commit(root: Path) -> str:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return done.stdout.strip()


def build_scf(root: Path = ROOT, dist: Path | None = None) -> dict[str, object]:
    meta = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = meta["project"]["version"]
    manifest = {p.relative_to(root).as_posix(): sha256(p) for p in source_files(root)}
    aggregate = hashlib.sha256(
        "".join(f"{k} {v}\n" for k, v in manifest.items()).encode()
    ).hexdigest()
    deliverables: dict[str, dict[str, object]] = {}
    folder = dist if dist is not None else root / "dist"
    if folder.is_dir():
        for p in sorted(folder.iterdir()):
            if p.is_file() and version in p.name and p.name.endswith(DELIVERABLE_SUFFIXES):
                deliverables[p.name] = {"bytes": p.stat().st_size, "sha256": sha256(p)}
    return {
        "name": meta["project"]["name"],
        "version": version,
        "source_commit": commit(root),
        "dependencies": meta["project"]["dependencies"]
        + meta["project"]["optional-dependencies"]["gui"],
        "source_integrity_sha256": aggregate,
        "source_files": manifest,
        "deliverables": deliverables,
    }


def main(out: str = "dist/release-docs") -> int:
    scf = build_scf(ROOT)
    files: dict[str, str] = scf["source_files"]  # type: ignore[assignment]
    delivered: dict[str, dict[str, object]] = scf["deliverables"]  # type: ignore[assignment]
    if not delivered:
        sys.stderr.write(
            f"error: no package (.deb, .tar.gz, .exe or .zip) of version {scf['version']} in dist/: build the package first\n"
        )
        return 1
    out_dir = ROOT / out
    out_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(scf, indent=2, sort_keys=True) + "\n"
    (out_dir / "scf.json").write_text(text, encoding="utf-8")
    sums = "".join(f"{v['sha256']}  {k}\n" for k, v in sorted(delivered.items()))
    (out_dir / "SHA256SUMS").write_text(sums, encoding="utf-8")
    sys.stdout.write(
        f"{scf['version']}: {len(files)} source files, {len(delivered)} deliverables, "
        f"integrity {scf['source_integrity_sha256']}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:2]))
