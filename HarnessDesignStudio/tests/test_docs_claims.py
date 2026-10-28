"""1.8.1: documentary claims the 1.8.0 audit found false or stale stay corrected (F-14, F-05, F-13)."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _all_markdown() -> list[Path]:
    skip = ("releases", "audit")
    found = [ROOT / "README.md", *DOCS.rglob("*.md")]
    return [p for p in found if not any(s in p.parts or s in p.name.lower() for s in skip)]


def test_the_cheatsheet_does_not_put_interface_types_in_library(tmp_path: Path) -> None:
    sheet = _text(DOCS / "CHEATSHEET.md")
    library_line = next(ln for ln in sheet.splitlines() if ln.strip().startswith("library/"))
    assert "interface type" not in library_line
    assert "interface_types.json" in sheet
    # the real project agrees: the interface types are a file of logical/, none is in library/
    from harness_design_studio.cli.main import main

    assert main(["new", str(tmp_path / "p"), "--template", "blank"]) == 0
    assert (tmp_path / "p" / "logical" / "interface_types.json").is_file()
    assert not list((tmp_path / "p" / "library").glob("*interface*"))


@pytest.mark.parametrize("name", ["CONCEPTS.md", "FAQ.md", "GLOSSARY.md"])
def test_no_page_says_the_tool_contains_no_engineering_numbers(name: str) -> None:
    text = _text(DOCS / name)
    assert not re.search(
        r"(tool|program) contains[^.]{0,6}\bno\b[^.]{0,30}(engineering )?numbers", text
    )
    assert "tool contains none" not in text
    assert "--apply-profile" in text, f"{name} does not mention what --apply-profile writes"


def test_the_profile_values_are_named_in_concepts_and_the_manual() -> None:
    concepts = _text(DOCS / "CONCEPTS.md")
    assert "ECSS-Q-ST-30-11C" in concepts and "ECSS-E-ST-20-07C" in concepts
    assert "placeholder" in concepts.split("--apply-profile", 1)[1][:400]
    manual = _text(DOCS / "user-manual" / "fill-in-engineering-values.md")
    assert "Out of the box the tool holds" not in manual
    assert "ECSS-Q-ST-30-11C" in manual.split("Out of the box", 1)[1][:500]


def test_the_merge_claims_name_the_generation_record() -> None:
    concepts = _text(DOCS / "CONCEPTS.md")
    git = _text(DOCS / "user-manual" / "use-git-and-ci.md")
    for text in (concepts, git):
        assert "generated/generation.json" in text
        assert "edit different parts and merge cleanly" not in text
        assert "different parts of a design merge cleanly" not in text
    # the sample conflict is the file that really conflicts, with the way out beside it
    assert "[generated/generation.json]" in git
    assert "git checkout --ours design/generated/generation.json" in git
    assert "generate design" in git.split("git checkout --ours", 1)[1][:200]
    assert "check design" in git.split("git checkout --ours", 1)[1][:300]
    # the command that does it, and the file that keeps markers out of the record (1.9)
    troubleshooting = _text(DOCS / "TROUBLESHOOTING.md")
    for text in (concepts, git, troubleshooting):
        assert "merge-fix" in text
    assert "harness-design-studio merge-fix design" in git
    assert ".gitattributes" in git and "ci/gitattributes" in git
    assert "logical/links.json" in git  # the other files that conflict by design


def test_two_generated_branches_really_conflict_only_in_the_record(tmp_path: Path) -> None:
    """The procedure of the manual: take either side, generate, check."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not installed")
    from harness_design_studio.cli.main import main

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [git, "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )

    assert run("init", "-q", "-b", "main").returncode == 0
    assert main(["new", str(tmp_path / "design"), "--template", "first-steps"]) == 0
    assert main(["generate", str(tmp_path / "design")]) == 0
    # a project made before 1.9 has no .gitattributes; with it the file has no markers (see
    # tests/test_merge_fix.py)
    (tmp_path / "design" / ".gitattributes").unlink()
    run("add", "-A")
    assert run("commit", "-qm", "start").returncode == 0

    def change(branch: str, unit_file: str, old: str, new: str) -> None:
        run("checkout", "-q", "main")
        assert run("checkout", "-q", "-b", branch).returncode == 0
        path = tmp_path / "design" / "logical" / "units" / unit_file
        path.write_text(path.read_text().replace(old, new))
        assert main(["generate", str(tmp_path / "design")]) == 0
        assert run("commit", "-qam", branch).returncode == 0

    change("ann", "power.json", '"Power unit 1"', '"Power unit one"')
    change("bob", "avionics.json", '"Computer 1"', '"Computer one"')
    merged = run("merge", "ann")
    assert merged.returncode != 0
    conflicted = run("diff", "--name-only", "--diff-filter=U").stdout.split()
    assert conflicted == ["design/generated/generation.json"], conflicted
    assert main(["check", str(tmp_path / "design")]) == 1  # merge_conflict
    assert run("checkout", "--ours", "design/generated/generation.json").returncode == 0
    assert main(["generate", str(tmp_path / "design")]) == 0
    assert main(["check", str(tmp_path / "design")]) == 0


def test_the_readme_says_which_role_opens_on_the_next_step_page() -> None:
    readme = _text(ROOT / "README.md")
    assert ": it opens on the *Next step* page" not in readme
    step = next(
        ln for ln in readme.splitlines() if ln.lstrip().startswith("5. **Open it in the app**")
    )
    assert "A Systems engineer lands on the **Next step** page" in step
    assert "an Electrical / AIT engineer lands on the diagram" in step


def _tour(readme: str) -> str:
    return readme.split("## The 10-minute tour", 1)[1].split("\n## ", 1)[0]


def test_the_readme_is_short_and_its_first_screen_is_not_release_history() -> None:
    """F-13: about 60 lines, the status and the release history live in docs/STATUS.md."""
    readme = _text(ROOT / "README.md")
    assert len(readme.splitlines()) <= 70
    first_screen = "\n".join(readme.splitlines()[:30])
    assert "## The 10-minute tour" in first_screen
    for history in ("published on", "Version `1.", "tag `v1.", "on commit `"):
        assert history not in readme, history
    assert "docs/STATUS.md" in readme and "Honest limits" in first_screen
    status = _text(DOCS / "STATUS.md")
    # what the README said is there, word for word
    assert "Version `1.8.0` (decisions D-172 to D-176;" in status
    assert "published on 2026-10-26 as the tag `v1.8.0` on commit `1f7431e`" in status
    assert "**Version `1.0.0`**, released on the repository owner's instruction" in status
    assert "macOS support was removed on 2026-10-21 (decision D-168)" in status
    root = _text(ROOT.parent / "README.md")
    assert "HarnessDesignStudio/docs/STATUS.md" in root
    assert "**Version `1.7.0`**" not in root and "**Version `1.7.0`**" in status


def test_the_readme_tour_uses_commands_of_getting_started() -> None:
    from tests.test_docs import _commands_in

    tour = _tour(_text(ROOT / "README.md"))
    shown = [
        ln.strip() for ln in tour.splitlines() if ln.strip().startswith("harness-design-studio")
    ]
    assert len(shown) == 8, shown
    tutorial = _commands_in(DOCS / "GETTING_STARTED.md")
    for command in shown:
        if command != "harness-design-studio --version":
            assert any(t.startswith(command) for t in tutorial), command
    assert "GETTING_STARTED.md" in _text(ROOT / "README.md")


def test_the_readme_tour_names_screens_that_exist_and_quotes_real_output(tmp_path: Path) -> None:
    from harness_design_studio.gui import strings
    from tests.test_docs import _commands_in, _run_document

    tour = _tour(_text(ROOT / "README.md"))
    # the screens of the app step
    for label in (
        strings.AREA_NEXT,
        strings.AREA_MODEL,
        strings.AREA_CHECKS,
        strings.AREA_DRAWINGS,
        strings.TAB_WHY,
        strings.ROLE_DIALOG_TITLE,
        strings.A_OPEN,
    ):
        assert label in tour, label
    assert "View > Role" in strings.ROLE_DIALOG_LATER and "File > Open project" in tour
    # the lines the text says you should see are what the commands print
    results = _run_document(
        ROOT / "README.md",
        tmp_path,
        {},
        not_output=frozenset({"harness-design-studio export wheel-link#0"}),
    )
    assert len(results) == len(_commands_in(ROOT / "README.md")) == 8
    printed = "\n".join(out for _cmd, out in results)
    quoted = re.findall(r"`([^`]*(?:added,|files written to)[^`]*)`", tour)
    assert len(quoted) == 3, quoted
    for line in quoted:
        assert line in printed, line
    # the files the text names are written
    assert (
        tmp_path / "wheel-link" / "outputs" / "harnesses" / "W001" / "W001_build.xlsx"
    ).is_file()


def test_no_page_says_the_command_line_cannot_add_devices() -> None:
    for page in _all_markdown():
        text = _text(page)
        assert "command line cannot add devices" not in text, page
        assert "command line cannot add them" not in text, page
    sheet = _text(DOCS / "CHEATSHEET.md")
    for command in ("import-pinout --new-device", "import-devices", "import-subsystem"):
        assert command in sheet
