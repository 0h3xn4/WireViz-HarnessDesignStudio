"""The name a person has told Git (`git config user.name`), read without starting Git (1.9.0).

A release asks who you are. When the project asks for different people in a release
(`roles.py`) and nobody typed a name, the name Git has for this person is the default. It is
read the way `gitinfo.py` reads a commit (D-164): the `git` program is not started, the files
are read-only and size-limited, and a file that cannot be read gives "not known", never an error.
Only the one value `user.name` is looked up. Not followed: `include` and `includeIf` lines, the
system file and the worktree file; a name is never made up when none is found.

Order, the last one wins as in Git: the user's file in the XDG folder, the user's `~/.gitconfig`,
the `config` of the repository around the project folder. `GIT_CONFIG_GLOBAL` replaces the two user
files, as it does for Git (`/dev/null` means none).
"""

import os
import re
from pathlib import Path

from .gitinfo import find_git_dir

__all__ = ["configured_name"]

MAX_CONFIG = 64 * 1024
_SECTION = re.compile(r'\[\s*([A-Za-z0-9.-]+)(\s+"(?:[^"\\]|\\.)*")?\s*\]')
_KEY = re.compile(r"([A-Za-z][A-Za-z0-9-]*)\s*(?:=\s*(.*))?$")


def configured_name(start: Path | None = None) -> str | None:
    """The `user.name` that applies to the repository around `start` (or the user's own files when
    there is no repository), or None when none is set."""
    found: str | None = None
    for file in _files(start):
        value = _user_name(file)
        if value is not None:
            found = value
    return found


def _files(start: Path | None) -> list[Path]:
    out: list[Path] = []
    override = os.environ.get("GIT_CONFIG_GLOBAL")
    if override is not None:
        out.append(Path(override))
    else:
        try:
            home = Path.home()
        except RuntimeError, OSError:
            home = None
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            out.append(Path(xdg) / "git" / "config")
        elif home is not None:
            out.append(home / ".config" / "git" / "config")
        if home is not None:
            out.append(home / ".gitconfig")
    if start is not None:
        repo = find_git_dir(start)
        if repo is not None:
            out.append(repo[1] / "config")
    return out


def _user_name(file: Path) -> str | None:
    try:
        with file.open("rb") as f:
            text = f.read(MAX_CONFIG).decode("utf-8")
    except OSError, UnicodeError, ValueError:
        return None
    section = ""
    found: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("["):
            m = _SECTION.match(line)
            if m is None:
                section = ""
                continue
            section = m.group(1).casefold() if m.group(2) is None else ""  # [user "x"]: not ours
            line = line[m.end() :].strip()
        if not line or line[0] in "#;":
            continue
        m2 = _KEY.match(line)
        if (
            section == "user"
            and m2
            and m2.group(1).casefold() == "name"
            and m2.group(2) is not None
        ):
            found = _value(m2.group(2)) or found
    return found


def _value(text: str) -> str | None:
    """The value of one line: quotes and the escapes Git knows (\\\\, \\", \\n, \\t, \\b), a `#` or
    `;` outside quotes starts a comment, spaces around it are dropped. None for a value that is
    empty or has a control character."""
    out: list[str] = []
    quoted = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            mapped = {"n": "\n", "t": "\t", "b": "\b", '"': '"', "\\": "\\"}.get(nxt)
            if mapped is None:
                return None
            out.append(mapped)
            i += 2
            continue
        if ch == '"':
            quoted = not quoted
        elif not quoted and ch in "#;":
            break
        else:
            out.append(ch)
        i += 1
    if quoted:
        return None
    value = "".join(out).strip()
    if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    return value
