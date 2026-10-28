"""Release 1.9 (F-05): two people each press Generate. The `.gitattributes` of a new project, the
reader of the Git index and `merge-fix`. The merges are real ones, made with the `git` program
(skipped when it is not installed); the tool itself never starts `git` (D-164)."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core.mergefix import (
    GENERATION_FILE,
    GITATTRIBUTES,
    conflict_files,
    plan_merge_fix,
    take_our_side,
    write_gitattributes,
)
from harness_design_studio.core.templates import TEMPLATES
from harness_design_studio.core.vcs.gitindex import unmerged_paths
from tests.test_gitinfo import ENV, GIT, needs_git

TEMPLATE_FILE = (
    Path(__file__).resolve().parents[1]
    / "src/harness_design_studio/resources/examples/templates/ci/gitattributes"
)


def git(folder: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    done = subprocess.run(  # noqa: S603 (tests only: fixed arguments)
        [GIT or "git", *args], cwd=folder, env=ENV, check=False, capture_output=True, text=True
    )
    if check and done.returncode != 0:
        raise AssertionError(f"git {args}: {done.stdout}{done.stderr}")
    return done


def tree(folder: Path) -> dict[str, str]:
    """Every file of a folder (not `.git`, the lock files and the `.bak` copies, which Git ignores)
    with a digest of its bytes."""
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
        and ".git/" not in p.as_posix()
        and not p.name.startswith(".harness.lock")
        and p.suffix != ".bak"
    }


def edit_name(project: Path, unit_file: str, old: str, new: str) -> None:
    path = project / "logical" / "units" / unit_file
    path.write_text(path.read_text().replace(old, new))


def start(tmp_path: Path, attributes: bool = True) -> Path:
    """A repository with the project `design` made by `new`, generated and committed."""
    git(tmp_path, "init", "-q", "-b", "main")
    design = tmp_path / "design"
    assert main(["new", str(design), "--template", "first-steps"]) == 0
    assert main(["generate", str(design)]) == 0
    if not attributes:
        (design / ".gitattributes").unlink()
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "start")
    return design


def branch(tmp_path: Path, name: str, unit_file: str, old: str, new: str, run: bool = True) -> None:
    git(tmp_path, "checkout", "-q", "main")
    git(tmp_path, "checkout", "-q", "-b", name)
    edit_name(tmp_path / "design", unit_file, old, new)
    if run:
        assert main(["generate", str(tmp_path / "design")]) == 0
    git(tmp_path, "commit", "-q", "-am", name)


def two_generated_branches(tmp_path: Path, attributes: bool = True) -> Path:
    """Ann and Bob change different devices and both press Generate; Bob merges Ann's branch."""
    design = start(tmp_path, attributes)
    branch(tmp_path, "ann", "power.json", '"Power unit 1"', '"Power unit one"')
    branch(tmp_path, "bob", "avionics.json", '"Computer 1"', '"Computer one"')
    merged = git(tmp_path, "merge", "ann", check=False)
    assert merged.returncode != 0
    return design


# ---- the file that a new project gets --------------------------------------------------------


def test_new_writes_the_gitattributes_once(tmp_path: Path) -> None:
    assert main(["new", str(tmp_path / "a"), "--template", "blank"]) == 0
    path = tmp_path / "a" / ".gitattributes"
    assert path.read_text() == GITATTRIBUTES
    assert "generated/generation.json merge=binary" in GITATTRIBUTES
    assert main(["generate", str(tmp_path / "a")]) == 0  # saving never removes or rewrites it
    assert path.read_text() == GITATTRIBUTES
    path.write_text("# mine\n")
    assert write_gitattributes(tmp_path / "a") is False
    assert path.read_text() == "# mine\n"


@pytest.mark.parametrize("template", [t.name for t in TEMPLATES])
def test_every_example_ships_the_gitattributes(template: str) -> None:
    from harness_design_studio.resources import examples_path

    root = examples_path()
    assert root is not None
    assert (root / "projects" / template / ".gitattributes").read_text() == GITATTRIBUTES


def test_the_template_file_is_the_same_text() -> None:
    assert TEMPLATE_FILE.read_text() == GITATTRIBUTES
    readme = TEMPLATE_FILE.parent.parent / "README.md"
    assert "`ci/gitattributes`" in readme.read_text()


def test_the_gitattributes_is_part_of_the_package_data() -> None:
    text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    assert "examples/**/.gitattributes" in text


# ---- real merges ------------------------------------------------------------------------------


@needs_git
def test_with_the_attributes_the_record_conflicts_without_markers(tmp_path: Path) -> None:
    design = two_generated_branches(tmp_path)
    record = design / GENERATION_FILE
    assert git(tmp_path, "diff", "--name-only", "--diff-filter=U").stdout.split() == [
        "design/generated/generation.json"
    ]
    assert b"<<<<<<<" not in record.read_bytes()
    json.loads(record.read_text())  # still valid JSON, our side
    assert unmerged_paths(design) == [GENERATION_FILE]
    assert unmerged_paths(tmp_path) == ["design/generated/generation.json"]
    assert conflict_files(design) == [GENERATION_FILE]
    # the edits of both people are in the files
    assert "Power unit one" in (design / "logical/units/power.json").read_text()
    assert "Computer one" in (design / "logical/units/avionics.json").read_text()
    # the stale record is what `verify` (and so the CI script) catches
    assert main(["verify", str(design)]) == 1


@needs_git
def test_without_the_attributes_the_record_has_markers(tmp_path: Path) -> None:
    design = two_generated_branches(tmp_path, attributes=False)
    assert b"<<<<<<<" in (design / GENERATION_FILE).read_bytes()
    assert main(["check", str(design)]) == 1  # merge_conflict
    assert conflict_files(design) == [GENERATION_FILE]


@needs_git
def test_when_only_one_person_pressed_generate_there_is_no_conflict(tmp_path: Path) -> None:
    start(tmp_path)
    branch(tmp_path, "ann", "power.json", '"Power unit 1"', '"Power unit one"')
    branch(tmp_path, "bob", "avionics.json", '"Computer 1"', '"Computer one"', run=False)
    assert git(tmp_path, "merge", "ann", check=False).returncode == 0
    assert conflict_files(tmp_path / "design") == []


@pytest.mark.parametrize("attributes", [True, False], ids=["binary", "markers"])
@needs_git
def test_merge_fix_does_what_the_manual_recipe_does(tmp_path: Path, attributes: bool) -> None:
    design = two_generated_branches(tmp_path, attributes)
    # the recipe of the manual, on a copy of the repository
    copy = tmp_path.parent / (tmp_path.name + "-recipe")
    subprocess.run(["cp", "-a", str(tmp_path), str(copy)], check=True)
    git(copy, "checkout", "--ours", "design/generated/generation.json")
    assert main(["generate", str(copy / "design")]) == 0
    assert main(["check", str(copy / "design")]) == 0
    # the command
    assert main(["merge-fix", str(design)]) == 0
    assert conflict_files(design) == [GENERATION_FILE] or not attributes  # Git's index stays
    assert b"<<<<<<<" not in (design / GENERATION_FILE).read_bytes()
    assert main(["check", str(design)]) == 0
    assert main(["verify", str(design)]) == 0
    assert tree(design) == tree(copy / "design")
    # the merge can be finished
    git(tmp_path, "add", "-A")
    assert git(tmp_path, "commit", "-q", "-m", "merge", check=False).returncode == 0
    assert unmerged_paths(design) == []
    assert main(["merge-fix", str(design)]) == 0  # nothing left to do


@needs_git
def test_which_side_is_kept_does_not_change_the_result(tmp_path: Path) -> None:
    design = two_generated_branches(tmp_path, attributes=False)
    theirs = tmp_path.parent / (tmp_path.name + "-theirs")
    subprocess.run(["cp", "-a", str(tmp_path), str(theirs)], check=True)
    git(theirs, "checkout", "--theirs", "design/generated/generation.json")
    assert main(["generate", str(theirs / "design")]) == 0
    assert main(["merge-fix", str(design)]) == 0
    assert tree(design) == tree(theirs / "design")


@needs_git
def test_merge_fix_refuses_when_another_file_conflicts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    design = start(tmp_path)
    branch(tmp_path, "ann", "power.json", '"Power unit 1"', '"Annas power unit"')
    branch(tmp_path, "bob", "power.json", '"Power unit 1"', '"Bobs power unit"')
    assert git(tmp_path, "merge", "ann", check=False).returncode != 0
    assert set(conflict_files(design)) == {GENERATION_FILE, "logical/units/power.json"}
    before = tree(design)
    capsys.readouterr()
    assert main(["merge-fix", str(design)]) == 1
    err = capsys.readouterr().err
    assert "logical/units/power.json" in err and "nothing was changed" in err
    assert tree(design) == before


@needs_git
def test_two_new_connections_get_the_same_id_and_conflict_in_links_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A-23, as the manual says it: merge-fix leaves this to the people (the IDs are not changed)."""
    from harness_design_studio.core.commands import apply_ops
    from harness_design_studio.core.io.loader import load_project
    from harness_design_studio.core.io.saver import save_project
    from harness_design_studio.core.links import plan_add_link
    from harness_design_studio.core.samples import mini3

    git(tmp_path, "init", "-q", "-b", "main")
    design = tmp_path / "design"
    save_project(mini3(), design)
    write_gitattributes(design)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "start")
    for name, a, b in (("ann", "OBC-J01", "RW1-J02"), ("bob", "PCDU-J02", "OBC-J02")):
        git(tmp_path, "checkout", "-q", "main")
        git(tmp_path, "checkout", "-q", "-b", name)
        project = load_project(design).project
        ops, link_id = plan_add_link(project, a, b)
        assert link_id == "L1"  # both branches use the next free number
        apply_ops(project, ops)
        save_project(project, design)
        git(tmp_path, "add", "-A")
        git(tmp_path, "commit", "-q", "-m", name)
    assert git(tmp_path, "merge", "ann", check=False).returncode != 0
    assert conflict_files(design) == ["logical/links.json"]
    before = tree(design)
    capsys.readouterr()
    assert main(["merge-fix", str(design)]) == 1
    assert "logical/links.json" in capsys.readouterr().err
    assert tree(design) == before


@needs_git
def test_merge_fix_refuses_markers_in_a_hand_made_file_too(tmp_path: Path) -> None:
    design = two_generated_branches(tmp_path)
    marked = design / "config" / "emc.json"
    marked.write_text("<<<<<<< HEAD\n{}\n=======\n{}\n>>>>>>> ann\n")
    before = tree(design)
    assert main(["merge-fix", str(design)]) == 1
    assert tree(design) == before


@needs_git
def test_merge_fix_leaves_a_hand_made_harness_alone(tmp_path: Path) -> None:
    from harness_design_studio.core.commands import apply_ops
    from harness_design_studio.core.io.loader import load_project
    from harness_design_studio.core.io.saver import save_project
    from harness_design_studio.core.manual_harness import plan_new_harness

    git(tmp_path, "init", "-q", "-b", "main")
    design = tmp_path / "design"
    assert main(["new", str(design), "--template", "first-steps"]) == 0
    assert main(["generate", str(design)]) == 0
    project = load_project(design).project
    ops, hid = plan_new_harness(project, "Heater harness")
    apply_ops(project, ops)
    save_project(project, design)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "start")
    hand = [p for p in (design / "physical" / "harnesses").glob("*.json") if hid in p.read_text()]
    assert len(hand) == 1
    kept = hand[0].read_bytes()
    branch(tmp_path, "ann", "power.json", '"Power unit 1"', '"Power unit one"')
    branch(tmp_path, "bob", "avionics.json", '"Computer 1"', '"Computer one"')
    assert git(tmp_path, "merge", "ann", check=False).returncode != 0
    assert main(["merge-fix", str(design)]) == 0
    assert hand[0].read_bytes() == kept


@needs_git
def test_merge_fix_does_nothing_when_nothing_conflicts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    design = start(tmp_path)
    before = tree(design)
    assert main(["merge-fix", str(design)]) == 0
    assert "Nothing to fix" in capsys.readouterr().out
    assert tree(design) == before


def test_merge_fix_on_a_folder_that_is_no_project(tmp_path: Path) -> None:
    assert main(["merge-fix", str(tmp_path)]) == 2


@needs_git
def test_a_refused_generate_puts_the_record_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    design = two_generated_branches(tmp_path, attributes=False)
    before = tree(design)
    monkeypatch.setattr("harness_design_studio.cli.main._generate", lambda path: 1)
    assert main(["merge-fix", str(design)]) == 1
    assert "changed nothing" in capsys.readouterr().err
    assert tree(design) == before  # the markers are back exactly as they were


@needs_git
def test_a_project_with_other_damage_is_not_touched(tmp_path: Path) -> None:
    design = two_generated_branches(tmp_path, attributes=False)
    (design / "logical" / "units" / "power.json").write_text("{ not json")
    before = tree(design)
    assert main(["merge-fix", str(design)]) == 2  # a damaged project is refused, as by generate
    assert tree(design) == before


# ---- the pieces --------------------------------------------------------------------------------

HUNK = b'{\n<<<<<<< HEAD\n  "a": 1,\n=======\n  "a": 2,\n>>>>>>> ann\n  "b": 3\n}\n'


def test_take_our_side_keeps_the_first_part_of_every_hunk() -> None:
    assert take_our_side(HUNK) == b'{\n  "a": 1,\n  "b": 3\n}\n'
    two = HUNK + HUNK
    assert take_our_side(two).count(b'"a": 1') == 2
    assert take_our_side(b"no conflict\n") == b"no conflict\n"


def test_take_our_side_drops_the_common_ancestor_of_the_diff3_style() -> None:
    text = b"<<<<<<< HEAD\nours\n||||||| base\nancestor\n=======\ntheirs\n>>>>>>> ann\nrest\n"
    assert take_our_side(text) == b"ours\nrest\n"


def test_take_our_side_keeps_windows_line_ends() -> None:
    assert take_our_side(b"<<<<<<< HEAD\r\nours\r\n=======\r\ntheirs\r\n>>>>>>> x\r\nrest\r\n") == (
        b"ours\r\nrest\r\n"
    )


@pytest.mark.parametrize(
    "text",
    [
        b"<<<<<<< HEAD\nours\n",  # no end
        b"<<<<<<< HEAD\nours\n>>>>>>> x\n",  # no middle
        b">>>>>>> x\n",  # no start
        b"<<<<<<< a\n<<<<<<< b\n=======\n>>>>>>> x\n",  # nested
    ],
)
def test_take_our_side_refuses_markers_that_are_not_well_formed(text: bytes) -> None:
    with pytest.raises(ValueError):
        take_our_side(text)


def test_the_plan_for_a_record_that_cannot_be_used(tmp_path: Path) -> None:
    (tmp_path / "generated").mkdir()
    (tmp_path / "project.json").write_text("{}")
    record = tmp_path / GENERATION_FILE
    record.write_bytes(b"<<<<<<< HEAD\n{\n=======\n{}\n>>>>>>> x\n")
    plan = plan_merge_fix(tmp_path)
    assert plan.conflicts == [GENERATION_FILE] and not plan.ok and "JSON" in plan.problem
    record.write_bytes(b'<<<<<<< HEAD\n{"other": 1}\n=======\n{}\n>>>>>>> x\n')
    assert "not a generation record" in plan_merge_fix(tmp_path).problem
    record.write_bytes(b'<<<<<<< HEAD\n{"input_hash": "x"}\n=======\n{}\n>>>>>>> x\n')
    plan = plan_merge_fix(tmp_path)
    assert plan.ok and plan.new_record == b'{"input_hash": "x"}\n'
    record.write_bytes(b"<<<<<<< HEAD\n{\n")  # a start without an end is not a conflict hunk
    assert plan_merge_fix(tmp_path).conflicts == []


def test_conflict_files_skips_the_git_folder_and_the_backups(tmp_path: Path) -> None:
    marked = b"<<<<<<< HEAD\na\n=======\nb\n>>>>>>> x\n"
    for rel in (".git/x", ".harness-recovery/x", ".migration-backup-v1/x", "quarantine/x"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(marked)
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs" / "list.csv").write_bytes(marked)
    assert conflict_files(tmp_path) == ["outputs/list.csv"]


# ---- the Git index ---------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["2", "4"])
@needs_git
def test_the_index_reader_agrees_with_git(tmp_path: Path, version: str) -> None:
    design = two_generated_branches(tmp_path, attributes=True)
    git(tmp_path, "update-index", "--index-version", version)
    listed = sorted(
        {ln.split("\t")[1] for ln in git(tmp_path, "ls-files", "-u").stdout.splitlines()}
    )
    assert listed == ["design/generated/generation.json"]
    assert unmerged_paths(tmp_path) == listed
    assert unmerged_paths(design) == ["generated/generation.json"]
    assert unmerged_paths(design / "logical") == []
    git(tmp_path, "add", "-A")
    assert unmerged_paths(tmp_path) == []


@needs_git
def test_the_index_reader_reads_the_extended_flags_of_version_3(tmp_path: Path) -> None:
    design = two_generated_branches(tmp_path, attributes=True)
    (design / "new-file.txt").write_text("x")
    git(tmp_path, "add", "--intent-to-add", "design/new-file.txt")  # an entry with extended flags
    assert (tmp_path / ".git" / "index").read_bytes()[4:8] == (3).to_bytes(4, "big")
    assert unmerged_paths(tmp_path) == ["design/generated/generation.json"]


def test_the_index_reader_gives_none_when_it_does_not_know(tmp_path: Path) -> None:
    assert unmerged_paths(tmp_path) is None  # no repository
    (tmp_path / ".git").mkdir()
    assert unmerged_paths(tmp_path) == []  # no index yet
    (tmp_path / ".git" / "index").write_bytes(b"not an index")
    assert unmerged_paths(tmp_path) is None
    (tmp_path / ".git" / "index").write_bytes(b"DIRC" + (9).to_bytes(4, "big") + bytes(4))
    assert unmerged_paths(tmp_path) is None  # a version it does not know
    (tmp_path / ".git" / "index").write_bytes(
        b"DIRC" + (2).to_bytes(4, "big") + (5).to_bytes(4, "big")
    )
    assert unmerged_paths(tmp_path) is None  # five entries announced, none there
