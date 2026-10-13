"""Licence report for installed runtime dependencies, failing on anything outside the allow-list.

Usage: python -m tools.licence_report OUT.md [PYTHON]  (PYTHON = interpreter of the shipped env)
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# Whole words only ("Miscellaneous" must not pass as MIT, "limited use" must not pass as ISC).
# MPL is not listed: the policy is permissive or LGPL only.
ALLOWED_WORDS = ("mit", "bsd", "apache", "isc", "python software foundation", "psf", "python-2.0",
                 "lgpl", "lesser general public", "unlicense", "zlib", "0bsd", "cc0",
                 "public domain", "hpnd")  # fmt: skip
REJECTED_RE = re.compile(r"(?<![a-z])(a?gpl)|general public license", re.IGNORECASE)
OWN = {"harness-design-studio"}
DEV_ONLY = OWN | {
    "pip-licenses", "pyinstaller", "cyclonedx-bom", "pytest", "pytest-cov", "pytest-qt",
    "hypothesis", "mypy", "ruff",
}  # fmt: skip


def classify(licence: str) -> str:
    """Return 'allowed' or 'rejected'. SPDX `AND` needs all parts allowed, `OR` any part."""
    text = licence.strip().lower()
    if not text or "unknown" in text:
        return "rejected"
    if ";" in text:  # pip-licenses joins multiple classifiers; be conservative: all must pass
        return "allowed" if all(classify(p) == "allowed" for p in text.split(";")) else "rejected"
    if " or " in text:
        return (
            "allowed" if any(classify(p) == "allowed" for p in text.split(" or ")) else "rejected"
        )
    if " and " in text:
        return (
            "allowed" if all(classify(p) == "allowed" for p in text.split(" and ")) else "rejected"
        )
    if "lgpl" in text or "lesser general public" in text:
        # the LGPL part is fine, but a plain GPL named next to it ("GPL-3.0 with LGPL exception") is not
        plain = re.sub(r"lgpl[\w.+-]*|lesser general public licen[sc]e", " ", text)
        return "rejected" if REJECTED_RE.search(plain) else "allowed"
    if REJECTED_RE.search(text):
        return "rejected"
    words = (rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])" for w in ALLOWED_WORDS)
    return "allowed" if any(re.search(p, text) for p in words) else "rejected"


def main(out: str, python: str = sys.executable) -> int:
    raw = subprocess.run(
        [sys.executable, "-m", "piplicenses", "--python", python, "--format=json", "--with-system"],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    rows = [r for r in json.loads(raw) if r["Name"].lower() not in DEV_ONLY]
    lines = [
        "# Licence report",
        "",
        "| Package | Version | Licence | Status |",
        "| --- | --- | --- | --- |",
    ]
    bad = 0
    for r in sorted(rows, key=lambda r: r["Name"].lower()):
        status = classify(r["License"])
        bad += status == "rejected"
        lines.append(f"| {r['Name']} | {r['Version']} | {r['License']} | {status} |")
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} packages, {bad} rejected")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:3]))
