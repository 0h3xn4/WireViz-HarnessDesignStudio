"""The trust store: which Python code the person using this computer has agreed to run.

Python code of a plug-in is never imported unless the project enables it **and** the exact code is
in this store. The store is in the *user's* settings folder, not in the project, so a cloned
repository cannot trust itself: whoever sends a project cannot also say that its code is trusted.

An entry is the plug-in's name and the SHA-256 of its source (a project plug-in: the bytes of its
file as they are on disk; an installed one: the bytes of the Python files of its distribution). A
change of one byte is another hash and the old trust does not apply to it. Trust can be taken back
(`revoke`). The store holds names, versions, hashes and where the code was; no time, no project
path.

A trusted plug-in runs with the rights of the person who trusted it. The tool has no sandbox.
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from harness_design_studio.core.errors import HarnessError

FORMAT = "harness-design-studio-trusted-plugins"
FORMAT_VERSION = 1
FILE_NAME = "trusted_plugins.json"
ENV_DIR = (
    "HARNESS_DESIGN_STUDIO_CONFIG_DIR"  # replaces the settings folder (tests, shared machines)
)


class TrustError(HarnessError):
    """The trust store cannot be read or written."""


@dataclass(frozen=True)
class Trusted:
    name: str
    sha256: str
    version: str = ""
    where: str = ""  # "project plug-in extensions/plugins/x.py" or "installed package y"


def settings_dir() -> Path:
    """The user's settings folder of the tool (not created here)."""
    override = os.environ.get(ENV_DIR)
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "HarnessDesignStudio"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "harness-design-studio"


def store_path() -> Path:
    return settings_dir() / FILE_NAME


def read() -> list[Trusted]:
    """Every entry. A missing store is empty; one that cannot be read trusts nothing."""
    path = store_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except OSError, ValueError:
        return []
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        return []
    out: list[Trusted] = []
    for row in data.get("trusted", []):
        if (
            isinstance(row, dict)
            and isinstance(row.get("name"), str)
            and isinstance(row.get("sha256"), str)
            and len(row["sha256"]) == 64
        ):
            out.append(
                Trusted(
                    row["name"],
                    row["sha256"],
                    str(row.get("version", "")),
                    str(row.get("where", "")),
                )
            )
    return out


def _write(entries: list[Trusted]) -> None:
    rows = sorted(entries, key=lambda t: (t.name, t.sha256))
    doc = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "trusted": [
            {"name": t.name, "sha256": t.sha256, "version": t.version, "where": t.where}
            for t in rows
        ],
    }
    path = store_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".part")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        raise TrustError(
            f"the list of trusted plug-ins could not be written ({exc.strerror})"
        ) from exc


def is_trusted(name: str, sha256: str) -> bool:
    return any(t.name == name and t.sha256 == sha256 for t in read())


def trusted_hashes(name: str) -> list[str]:
    return [t.sha256 for t in read() if t.name == name]


def trust(name: str, sha256: str, version: str = "", where: str = "") -> None:
    """Record that this exact code is trusted. A name has one trusted hash at a time: trusting new
    code under a name takes the trust of the earlier code of that name away."""
    entries = [t for t in read() if t.name != name]
    entries.append(Trusted(name, sha256, version, where))
    _write(entries)


def revoke(name: str, sha256: str | None = None) -> int:
    """Take trust back: of one hash, or of every hash of the name. Returns how many entries went."""
    entries = read()
    keep = [t for t in entries if not (t.name == name and (sha256 is None or t.sha256 == sha256))]
    if len(keep) != len(entries):
        _write(keep)
    return len(entries) - len(keep)
