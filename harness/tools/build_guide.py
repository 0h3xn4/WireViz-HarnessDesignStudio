"""Build the offline user guide: docs/guide/USER_GUIDE.md -> src/harness_design_studio/resources/guide/index.html.
A small Markdown converter (headings, paragraphs, lists, tables, code, bold, italics, links), so
no extra dependency is needed. A test fails if the committed HTML is stale.
Usage: python -m tools.build_guide"""

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "guide" / "USER_GUIDE.md"
TARGET = ROOT / "src" / "harness_design_studio" / "resources" / "guide" / "index.html"

CSS = """
:root{--bg:#fff;--fg:#1b1b1f;--muted:#55555f;--line:#d0d0d8;--accent:#4a1fb8;--code:#f1f1f6}
@media (prefers-color-scheme: dark){:root{--bg:#16161a;--fg:#ececf1;--muted:#a8a8b3;--line:#3a3a44;--accent:#b79bff;--code:#23232b}}
body{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0}
main{max-width:46rem;margin:0 auto;padding:1rem 1rem 4rem}
nav{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:.5rem 1rem}
nav a{margin-right:1rem;color:var(--accent);white-space:nowrap}
h1,h2{line-height:1.2} h2{margin-top:2.2rem;border-bottom:1px solid var(--line);padding-bottom:.2rem}
code{background:var(--code);padding:.1em .3em;border-radius:3px;font-size:.92em}
pre{background:var(--code);padding:.8rem;overflow:auto;border-radius:6px}
table{border-collapse:collapse;width:100%;margin:1rem 0} th,td{border:1px solid var(--line);padding:.35rem .5rem;text-align:left;vertical-align:top}
a{color:var(--accent)} p,li{max-width:42rem}
"""


def inline(text: str) -> str:
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    return out


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"^\d+\.\s*", "", text.lower())).strip("-")


def split_row(line: str) -> list[str]:
    """The cells of a Markdown table row: split on `|`, but not on an escaped `\\|`, which is a
    literal bar inside the cell."""
    cells = re.split(r"(?<!\\)\|", line.strip().removeprefix("|").removesuffix("|"))
    return [c.strip().replace("\\|", "|") for c in cells]


def convert(md: str) -> str:
    lines = md.split("\n")
    body: list[str] = []
    toc: list[tuple[str, str]] = []
    k = 0
    while k < len(lines):
        line = lines[k]
        if line.startswith("```"):
            k += 1
            code = []
            while k < len(lines) and not lines[k].startswith("```"):
                code.append(lines[k])
                k += 1
            body.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
        elif m := re.match(r"^(#{1,3}) (.*)", line):
            level, text = len(m.group(1)), m.group(2)
            anchor = slug(text)
            if level == 2:
                toc.append((anchor, re.sub(r"^\d+\.\s*", "", text)))
            body.append(f'<h{level} id="{anchor}">{inline(text)}</h{level}>')
        elif line.startswith("|"):
            rows = []
            while k < len(lines) and lines[k].startswith("|"):
                rows.append(split_row(lines[k]))
                k += 1
            k -= 1
            head, data = rows[0], [r for r in rows[2:]]
            table = (
                "<table><thead><tr>"
                + "".join(f"<th>{inline(c)}</th>" for c in head)
                + "</tr></thead><tbody>"
            )
            table += "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in data
            )
            body.append(table + "</tbody></table>")
        elif re.match(r"^(\d+\.|-) ", line):
            ordered = bool(re.match(r"^\d+\. ", line))
            items = []
            while k < len(lines) and re.match(r"^(\d+\.|-) ", lines[k]):
                items.append(re.sub(r"^(\d+\.|-) ", "", lines[k]))
                k += 1
            k -= 1
            tag = "ol" if ordered else "ul"
            body.append(f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{tag}>")
        elif line.strip():
            para = [line]
            while (
                k + 1 < len(lines)
                and lines[k + 1].strip()
                and not re.match(r"^(#|\||```|\d+\. |- )", lines[k + 1])
            ):
                k += 1
                para.append(lines[k])
            body.append(f"<p>{inline(' '.join(para))}</p>")
        k += 1
    nav = "<nav>" + "".join(f'<a href="#{a}">{html.escape(t)}</a>' for a, t in toc) + "</nav>"
    title = re.match(r"# (.*)", md).group(1) if re.match(r"# (.*)", md) else "Guide"  # type: ignore[union-attr]
    return (
        f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>{nav}<main>\n"
        + "\n".join(body)
        + "\n</main></body></html>\n"
    )


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(convert(SOURCE.read_text()))
    print(f"wrote {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
