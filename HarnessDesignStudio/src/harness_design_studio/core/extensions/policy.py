"""The switch that turns Python plug-ins off on a computer (REQ-OFFLINE-05, D-203).

A trusted Python plug-in runs with the rights of the person who trusted it and could use the network
(`docs/SECURITY.md`). An IT department that does not want that on its computers can turn Python
plug-ins off entirely, in either of two ways:

* the **machine-wide policy file** (`policy_path()`): on Linux `/etc/harness-design-studio/policy.json`,
  on Windows `%ProgramData%\\HarnessDesignStudio\\policy.json`. Only an administrator can write
  there when the folder is made by one, so a user cannot turn the switch back on. While the file
  exists, Python plug-ins are off unless it says exactly `{"python_plugins": "allowed"}`; a file
  that cannot be read or is not understood also turns them off (the switch fails closed);
* the **environment variable** `HARNESS_DESIGN_STUDIO_NO_PLUGINS` set to anything but empty or `0`
  (for one session, a script, a CI job, or a machine-wide variable).

Either one is enough; nothing can turn plug-ins back on that one of them turned off, and neither has
a value that turns on anything that is off by default. While plug-ins are off, no plug-in module is
ever imported, whatever the project enables or the user trusted; the plug-ins are listed with the
state `blocked` and the reason. Declarative extensions (rules, tables and lookup tables written as
data, which the tool reads and never runs) are not affected.

The path of the policy file is fixed on purpose: no environment variable or setting can move it,
because that would let a user point the program at a file of their own. Tests replace
`policy_path` itself.
"""

import json
import os
import sys
from pathlib import Path

ENV_NO_PLUGINS = "HARNESS_DESIGN_STUDIO_NO_PLUGINS"
POLICY_KEY = "python_plugins"
ALLOWED = "allowed"
OFF = "off"
MAX_POLICY_BYTES = 64 * 1024


def policy_path() -> Path:
    """Where the machine-wide policy file is looked for."""
    if sys.platform == "win32":
        base = os.environ.get("PROGRAMDATA") or "C:\\ProgramData"
        return Path(base) / "HarnessDesignStudio" / "policy.json"
    return Path("/etc/harness-design-studio/policy.json")


def _env_says_off() -> bool:
    value = os.environ.get(ENV_NO_PLUGINS, "").strip()
    return value not in ("", "0")


def _policy_says_off(path: Path) -> str:
    """Why the policy file turns plug-ins off ("" when there is no file or it allows them)."""
    try:
        if not path.exists() and not path.is_symlink():
            return ""
        with path.open("rb") as fh:
            data = fh.read(MAX_POLICY_BYTES + 1)
    except OSError as exc:
        return f"the policy file {path} exists but could not be read ({exc.strerror or exc})"
    if len(data) > MAX_POLICY_BYTES:
        return f"the policy file {path} is larger than {MAX_POLICY_BYTES // 1024} KiB"
    try:
        doc = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError, ValueError, RecursionError:
        return f"the policy file {path} is not valid JSON"
    value = doc.get(POLICY_KEY) if isinstance(doc, dict) else None
    if value == ALLOWED:
        return ""
    if value == OFF:
        return f'the policy file {path} says "{POLICY_KEY}": "{OFF}"'
    return f'the policy file {path} does not say "{POLICY_KEY}": "{ALLOWED}"'


def plugins_blocked() -> str:
    """The reason Python plug-ins are off on this computer, in a full sentence; "" when they are not.
    Asked each time (cheap: one file test and one environment variable), so a change takes effect
    for the next project that is opened."""
    reasons = []
    if _env_says_off():
        reasons.append(f"the environment variable {ENV_NO_PLUGINS} is set")
    file_reason = _policy_says_off(policy_path())
    if file_reason:
        reasons.append(file_reason)
    if not reasons:
        return ""
    return (
        "Python plug-ins are switched off on this computer ("
        + "; ".join(reasons)
        + "): no plug-in is imported, whatever the project enables or you trusted. "
        "Data-only extensions (rules and tables written as data) still apply."
    )
