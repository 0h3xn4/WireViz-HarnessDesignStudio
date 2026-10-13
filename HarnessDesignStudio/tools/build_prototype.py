"""Assemble the single-file clickable prototype from the design tokens (offline, no CDN).

Usage: python -m tools.build_prototype  ->  prototype/index.html
"""

import json
from pathlib import Path

from harness_design_studio.gui.tokens import CATEGORIES, DARK, FONT_MONO, FONT_UI, LIGHT

ROOT = Path(__file__).resolve().parents[1] / "prototype"


def css_vars(tokens: dict[str, str]) -> str:
    return "".join(f"--{k}:{v};" for k, v in tokens.items())


def build() -> str:
    html = (ROOT / "template.html").read_text(encoding="utf-8")
    app = (ROOT / "app.js").read_text(encoding="utf-8")
    replacements = {
        "/*TOKENS_LIGHT*/": css_vars(LIGHT),
        "/*TOKENS_DARK*/": css_vars(DARK),
        "/*FONT_UI*/": FONT_UI,
        "/*FONT_MONO*/": FONT_MONO,
        "/*CATEGORIES_JSON*/": json.dumps(CATEGORIES),
        "/*APP_JS*/": app,
    }
    for key, value in replacements.items():
        html = html.replace(key, value)
    return html


def main() -> int:
    (ROOT / "index.html").write_text(build(), encoding="utf-8")
    print(f"wrote {ROOT / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
