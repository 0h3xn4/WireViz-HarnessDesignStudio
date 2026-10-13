"""REQ-UX-03: the committed prototype is exactly what the build script produces from the tokens."""

import re
from pathlib import Path

from tools.build_prototype import build

ROOT = Path(__file__).resolve().parents[1]


def test_committed_prototype_is_up_to_date() -> None:
    committed = (ROOT / "prototype" / "index.html").read_text(encoding="utf-8")
    assert committed == build(), "run `python -m tools.build_prototype` and commit the result"


def test_prototype_is_self_contained_and_offline() -> None:
    html = (ROOT / "prototype" / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"""(src|href)\s*=\s*["']https?://""", html)
    assert "@import" not in html and "fetch(" not in html and "XMLHttpRequest" not in html
    assert not re.search(r"https?://", html.replace("http://www.w3.org", ""))
