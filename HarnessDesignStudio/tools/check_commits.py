# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Check the commits of a pull request: the author address and the DCO sign-off (decision D-206).

Rules, for every commit in BASE..HEAD that is not a merge:
- the author address is a GitHub noreply address (`ID+name@users.noreply.github.com` or
  `name@users.noreply.github.com`) or the address of the AI assistant (`noreply@anthropic.com`);
  a private address in a public history is the thing this keeps out;
- the message has a `Signed-off-by: Name <address>` line whose address is the author address
  (the Developer Certificate of Origin, https://developercertificate.org), unless `--owner-pr` says
  that the owner of the repository opened the pull request: the owner directs the AI assistant and
  signs off by opening and merging the pull request (CONTRIBUTING.md).

Usage: python -m tools.check_commits BASE HEAD [--owner-pr]
Exit code 1 when a commit breaks a rule; the commits and the rule are printed.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

NOREPLY = re.compile(
    r"^(?:\d+\+)?[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?@users\.noreply\.github\.com$"
)
ALLOWED_OTHER = {"noreply@anthropic.com"}
SIGNOFF = re.compile(r"^Signed-off-by:\s+.+?\s+<([^<>\s]+)>\s*$", re.MULTILINE)
SEP = "\x1e"  # record separator between commits
FIELD = "\x1f"  # field separator inside a commit


def commits(base: str, head: str, cwd: Path | None = None) -> list[tuple[str, str, str]]:
    """(hash, author address, message) of every non-merge commit in base..head."""
    out = subprocess.run(
        ["git", "log", "--no-merges", f"--format=%H{FIELD}%ae{FIELD}%B{SEP}", f"{base}..{head}"],
        capture_output=True,
        text=True,
        check=True,
        cwd=cwd,
    ).stdout
    found = []
    for record in out.split(SEP):
        if record.strip():
            sha, email, message = record.strip("\n").split(FIELD, 2)
            found.append((sha.strip(), email.strip(), message))
    return found


def address_ok(email: str) -> bool:
    return bool(NOREPLY.match(email)) or email.lower() in ALLOWED_OTHER


def signed_off(email: str, message: str) -> bool:
    return any(m.lower() == email.lower() for m in SIGNOFF.findall(message))


def problems(found: list[tuple[str, str, str]], *, owner_pr: bool) -> list[str]:
    out = []
    for sha, email, message in found:
        if not address_ok(email):
            out.append(f"{sha[:10]}: the author address is not a GitHub noreply address")
        if not owner_pr and not signed_off(email, message):
            out.append(f"{sha[:10]}: no 'Signed-off-by: Name <address>' line for the author (DCO)")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("base")
    ap.add_argument("head")
    ap.add_argument("--owner-pr", action="store_true", help="the owner of the repository opened it")
    args = ap.parse_args(argv)
    found = commits(args.base, args.head)
    bad = problems(found, owner_pr=args.owner_pr)
    for line in bad:
        print(line, file=sys.stderr)
    print(f"{len(found)} commit(s) checked, {len(bad)} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
