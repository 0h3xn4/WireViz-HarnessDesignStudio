"""M7: the user guide, rule reference and configuration reference stay true to the program."""

import re
from pathlib import Path

import pytest

from harness_design_studio.cli.main import build_parser
from harness_design_studio.core.model.config import default_configs
from tests.helpers import PROGRAMS, program_path
from tools.build_guide import SOURCE, TARGET, convert
from tools.gen_rule_docs import TARGET as RULES_MD
from tools.gen_rule_docs import render

ROOT = Path(__file__).resolve().parents[1]


def test_guide_html_is_up_to_date() -> None:
    assert TARGET.read_text() == convert(SOURCE.read_text()), "run: python -m tools.build_guide"


def test_every_guide_table_row_has_the_cells_of_its_header() -> None:
    """An escaped bar in a cell (`a\\|b`) once split the cell and broke the row."""
    from html.parser import HTMLParser

    class Rows(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.tables: list[list[int]] = []
            self.depth = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == "table":
                self.tables.append([])
            elif tag == "tr":
                self.tables[-1].append(0)
            elif tag in ("td", "th"):
                self.tables[-1][-1] += 1

    rows = Rows()
    rows.feed(TARGET.read_text())
    assert rows.tables
    for table in rows.tables:
        assert set(table) == {table[0]}, table
    html = convert("| a | b |\n|---|---|\n| `x \\| y` | z |\n")
    assert "<td><code>x | y</code></td><td>z</td>" in html and "\\" not in html


def test_guide_internal_links_resolve() -> None:
    html = TARGET.read_text()
    ids = set(re.findall(r'id="([^"]+)"', html))
    for anchor in re.findall(r'href="#([^"]+)"', html):
        assert anchor in ids, anchor


def test_guide_documents_every_cli_command() -> None:
    parser = build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    text = SOURCE.read_text()
    for name in sub.choices:  # type: ignore[union-attr]
        assert f"`harness-design-studio {name}" in text, (
            f"the guide does not document 'harness-design-studio {name}'"
        )


def test_guide_names_buttons_that_exist() -> None:
    from harness_design_studio.gui import strings

    text = SOURCE.read_text()
    shown = " ".join(str(v) for v in vars(strings).values() if isinstance(v, str))
    for label in (
        "Generate harnesses",
        "Export outputs",
        "Submit for review",
        "Release…",
        "New revision…",
        "Changes…",
        "Change log…",
        "Interface table",
        "Problems",
        "To do",
        "Waive",
        "Save salvaged copy",
    ):
        assert label in text and label.rstrip("…") in shown, label


def test_guide_has_no_wall_of_text() -> None:
    """Short paragraphs and steps: no paragraph longer than 700 characters."""
    for para in re.split(r"\n\s*\n", SOURCE.read_text()):
        if not para.lstrip().startswith(("|", "#", "-", "1.", "```")):
            assert len(para) <= 700, para[:60]


def test_rule_reference_is_up_to_date() -> None:
    assert RULES_MD.read_text() == render(), "run: python -m tools.gen_rule_docs"


def test_every_configuration_key_is_documented() -> None:
    text = (ROOT / "docs" / "CONFIG.md").read_text()
    for name, cfg in default_configs().items():
        assert f"`{name}.json`" in text, name
        if name in ("naming", "titleblock"):
            continue
        for key in cfg.values:
            assert f"`{key}`" in text, f"{name}.{key} is not documented in docs/CONFIG.md"


def test_help_menu_opens_the_guide(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("PySide6")
    from tests.gui_helpers import make_window

    w = make_window(tmp_path)
    qtbot.addWidget(w)
    opened = []
    w.open_url = lambda url: opened.append(url.toLocalFile()) or True  # type: ignore[assignment,func-returns-value]
    assert w.act_guide.shortcut().toString() == "F1"
    w.act_guide.trigger()
    assert opened and opened[0].endswith("guide/index.html") and Path(opened[0]).is_file()


def test_cli_reference_is_up_to_date() -> None:
    from tools.gen_cli_docs import EXAMPLES, TARGET, render

    assert TARGET.read_text() == render(), "run: python -m tools.gen_cli_docs"
    parser = build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    assert set(EXAMPLES) == set(sub.choices or ())  # type: ignore[union-attr]


def test_cli_examples_name_real_commands_and_options() -> None:
    """Every example line parses with the real parser (paths need not exist)."""
    import shlex

    from tools.gen_cli_docs import EXAMPLES

    parser = build_parser()
    for lines in EXAMPLES.values():
        for line in lines:
            argv = shlex.split(line.split(" > ")[0])[1:]
            parser.parse_args(argv)


def _fenced_blocks(markdown: Path) -> list[list[str]]:
    blocks: list[list[str]] = []
    inside = False
    for line in markdown.read_text().splitlines():
        if line.startswith("```"):
            inside = not inside
            if inside:
                blocks.append([])
        elif inside:
            blocks[-1].append(line)
    return blocks


def _is_command(line: str) -> bool:
    return line.startswith(tuple(f"{p} " for p in PROGRAMS) + ("cp ",))


def _commands_in(markdown: Path) -> list[str]:
    """Command lines (harness-design-studio ..., harness ..., cp ...) from the fenced blocks of a
    document, in order."""
    return [ln.strip() for block in _fenced_blocks(markdown) for ln in block if _is_command(ln)]


def _quoted_outputs(markdown: Path) -> dict[int, list[str]]:
    """The block that follows a block of commands, by the index of the block's last command: the
    output the text quotes for it (or a file the text shows; the tests list those)."""
    out: dict[int, list[str]] = {}
    blocks = _fenced_blocks(markdown)
    index = -1
    for k, block in enumerate(blocks):
        index += sum(_is_command(ln) for ln in block)
        if (
            any(_is_command(ln) for ln in block)
            and _is_command(block[-1])
            and k + 1 < len(blocks)
            and blocks[k + 1]
            and not _is_command(blocks[k + 1][0])
        ):
            out[index] = blocks[k + 1]
    return out


MASK = re.compile(r"\b[0-9a-f]{12}\b")


def _quoted_lines_are_real(quoted: list[str], real: str) -> list[str]:
    """The quoted lines (hashes masked, `...` and blank lines skipped) that the real output lacks."""
    # (the documents write paths with "/"; on Windows the tool prints them with "\\")
    have = {MASK.sub("<hash>", ln.strip().replace("\\", "/")) for ln in real.splitlines()}
    return [
        ln
        for ln in quoted
        if ln.strip() not in ("", "...") and MASK.sub("<hash>", ln.strip()) not in have
    ]


def _run_document(
    markdown: Path,
    tmp: Path,
    expected: dict[str, list[int]],
    not_output: frozenset[str] = frozenset(),
) -> list[tuple[str, str]]:
    """Run every command of a document in order, in a scratch folder, and check the exit codes.
    `expected` lists, per command start, the codes of its successive runs (default: 0).
    The output that the text quotes after a block of commands must be what the command prints
    (hashes masked); `not_output` names the blocks that show a file instead, as
    `"<command>#<run number>"` (the first run is 0)."""
    import os
    import subprocess

    env = {**os.environ, "PATH": program_path(tmp.parent / f"{tmp.name}-programs")}
    seen: dict[str, int] = {}
    results: list[tuple[str, str]] = []
    quoted = _quoted_outputs(markdown)
    for number, command in enumerate(_commands_in(markdown)):
        key = next((k for k in expected if command.startswith(k)), command)
        n = seen.get(key, 0)
        seen[key] = n + 1
        want = expected.get(key, [0])[min(n, len(expected.get(key, [0])) - 1)]
        done = subprocess.run(
            ["sh", "-c", command], cwd=tmp, env=env, capture_output=True, text=True, check=False
        )
        assert done.returncode == want, (
            f"{markdown.name}: `{command}` exited {done.returncode}, expected {want}\n"
            f"{done.stdout[-600:]}{done.stderr[-600:]}"
        )
        run_number = sum(c == command for c, _ in results)  # earlier runs of this very command
        if number in quoted and f"{command}#{run_number}" not in not_output:
            missing = _quoted_lines_are_real(quoted[number], done.stdout + done.stderr)
            assert not missing, (
                f"{markdown.name}: the text quotes output of `{command}` that the tool does not "
                f"print:\n{missing}\nreal output:\n{(done.stdout + done.stderr)[:1500]}"
            )
        results.append((command, done.stdout))
    return results


def test_getting_started_commands_work_in_order(tmp_path: Path) -> None:
    """The tutorial is run word for word, so it cannot drift from the program."""
    doc = ROOT / "docs" / "GETTING_STARTED.md"
    results = _run_document(
        doc,
        tmp_path,
        {
            "harness-design-studio release wheel-link": [
                1,
                1,
                0,
            ],  # blocked, blocked on placeholders, accepted
            "harness-design-studio config wheel-link": [1],  # exit 1 while values are missing
            "harness-design-studio drc wheel-link": [
                0,
                1,
                0,
            ],  # the library import makes the plans stale (1)
        },
        # the block after this export shows two lines of a file, checked below
        not_output=frozenset({"harness-design-studio export wheel-link#1"}),
    )
    wirelist = (
        tmp_path / "wheel-link" / "outputs" / "harnesses" / "W002" / "wirelist.csv"
    ).read_text()
    shown = [ln for ln in doc.read_text().splitlines() if ln.startswith("W002-00")]
    assert shown and all(ln in wirelist for ln in shown), shown
    # the model hash quoted in the text is the one the first export prints
    first_export = next(
        out for cmd, out in results if cmd == "harness-design-studio export wheel-link"
    )
    printed = re.search(r"model ([0-9a-f]{12})", first_export)
    assert printed and f"(model {printed.group(1)})" in doc.read_text(), (
        "the model hash in docs/GETTING_STARTED.md is out of date: "
        f"{printed.group(1) if printed else '?'}"
    )
    assert f"Model hash: `{printed.group(1)}`" in doc.read_text()
    assert (tmp_path / "wheel-link" / "outputs" / "manifest.json").is_file()
    assert (tmp_path / "my-first-design" / "project.json").is_file()


def test_readme_quick_start_commands_work(tmp_path: Path) -> None:
    _run_document(ROOT / "README.md", tmp_path, {})


def _run_example(name: str, tmp: Path) -> str:
    """new, validate, generate, drc, export and verify of one template; all the output, joined."""
    import os
    import subprocess

    env = {**os.environ, "PATH": program_path(tmp.parent / f"{tmp.name}-programs")}
    folder = f"my-{name}"
    steps = [
        f"harness-design-studio new {folder} --template {name}",
        f"harness-design-studio validate {folder}",
        f"harness-design-studio generate {folder}",
        f"harness-design-studio drc {folder}",
        f"harness-design-studio export {folder}",
        f"harness-design-studio verify {folder} --outputs",
    ]
    out = []
    for step in steps:
        done = subprocess.run(
            ["sh", "-c", step], cwd=tmp, env=env, capture_output=True, text=True, check=False
        )
        out.append(f"## {step}\n{done.stdout}{done.stderr}")
    return "\n".join(out)


def test_the_examples_readme_quotes_what_the_tool_prints(tmp_path: Path) -> None:
    """The counts and output lines on docs/examples/README.md are those of a real run."""
    doc = ROOT / "docs" / "examples" / "README.md"
    sections = re.split(r"^## ", doc.read_text(), flags=re.M)
    names = ("blank", "first-steps", "minimal-satellite", "small-satellite", "flatsat")
    real = {n: _run_example(n, tmp_path) for n in names}
    seen = set()
    for section in sections:
        name = section.split("\n", 1)[0].strip()
        if name not in names:
            continue
        seen.add(name)
        lines: list[str] = []
        inside = False
        for line in section.splitlines():
            if line.startswith("```"):
                inside = not inside
            elif inside and not _is_command(line):
                lines.append(line)
        prose = re.sub(r"```.*?```", "", section, flags=re.S)
        for span in re.findall(r"`([^`]*(?:files written|error\(s\))[^`]*)`", prose):
            if not span.startswith(("harness-design-studio ", "harness ", "error:")):
                lines.append(span)
        assert len(lines) > 3, name
        missing = _quoted_lines_are_real(lines, real[name])
        assert not missing, f"docs/examples/README.md, {name}: the tool does not print {missing}"
    assert seen == set(names)
    # the table at the end quotes the number of exported files and the findings of drc
    for row in re.findall(r"^\| `([\w-]+)` \|.*$", doc.read_text(), re.M):
        line = next(ln for ln in doc.read_text().splitlines() if ln.startswith(f"| `{row}` |"))
        files = re.search(r"\| (\d+) files \|", line)
        if files:
            assert f"{files.group(1)} files written to" in real[row], row
        found = re.search(r"(\d+) errors, (\d+) warnings, (\d+) notes", line)
        if found:
            e, w, n = found.groups()
            assert f"Open: {e} error(s), {w} warning(s), {n} note(s)." in real[row], row


def test_the_guide_converter_leaves_code_alone_and_quotes_link_targets() -> None:
    from tools.build_guide import inline

    assert inline("`*.csv and *.xlsx`") == "<code>*.csv and *.xlsx</code>"
    assert inline("a *b* and `c*d* e`") == "a <em>b</em> and <code>c*d* e</code>"
    assert inline('[x](a"onmouseover="y)') == '<a href="a&quot;onmouseover=&quot;y">x</a>'
    assert inline("[`code`](u.md)") == '<a href="u.md"><code>code</code></a>'
