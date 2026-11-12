# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg,func-returns-value"
"""REQ-MIGRATE-06, M7a (D-228): the journal that merges. `journal.jsonl` holds one entry per line, written by adding
lines at the end; each entry is chained to its parent on its own line of work, so the entries that
two Git branches added are both valid after Git kept both sides' lines (`merge=union`); the reader
takes kinds it does not know, orders the entries the same way whatever the order of the lines, and
still finds a changed or removed entry; `merge-fix` records the merge; the step from format 1 to 2
moves `journal.json` to `journal.jsonl` and keeps every chain value. The merges are real ones, made
with the `git` program (skipped when it is not installed)."""

import json
import random
import shutil
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import configcheck, journal, records, templates
from harness_design_studio.core.commands import History, SetConfig
from harness_design_studio.core.io import canonical, upgrade
from harness_design_studio.core.io.layout import JOURNAL_FILE, journal_bytes, model_hash, serialize
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.mergefix import (
    GITATTRIBUTES,
    GITATTRIBUTES_1,
    add_journal_union,
    conflict_files,
    plan_merge_fix,
    record_journal_merge,
    take_both_sides,
)
from harness_design_studio.core.model import Journal, JournalEntry, JournalError
from harness_design_studio.core.model.journal import FIRST_CHAIN, KINDS, shown_kind
from harness_design_studio.core.outputs.build import build_outputs
from tests.migration_support import as_format, as_old_journal
from tests.test_gitinfo import needs_git
from tests.test_journal import Clock
from tests.test_merge_fix import git, tree


@pytest.fixture
def clock(monkeypatch):
    return Clock(monkeypatch)


@pytest.fixture
def folder(tmp_path, clock):
    templates.create_project(tmp_path / "p", "flatsat", journal=True)
    return tmp_path / "p"


def set_value(folder: Path, key: str, value: float) -> None:
    """Open the project as a person would, change one value of `derating`, save."""
    p = load_project(folder).project
    History(p).execute(key, [SetConfig(configcheck.with_value(p.config["derating"], key, value))])
    save_project(p, folder)


def lines(folder: Path) -> list[dict]:
    return [json.loads(x) for x in (folder / JOURNAL_FILE).read_bytes().splitlines()]


def write_lines(folder: Path, rows: list[dict]) -> None:
    (folder / JOURNAL_FILE).write_bytes(b"".join(canonical.dumps_line(r) for r in rows))


def row(when: str, author: str = "Ann", obj: str = "project", new: object = 1, kind="edit"):
    return {
        "kind": kind, "object": obj, "field": "x", "old": None, "new": new, "reason": "",
        "when": when, "author": author, "tool_version": "t",
    }  # fmt: skip


def at(second: int) -> str:
    return f"2026-11-12T10:{second // 60:02d}:{second % 60:02d}Z"


# ---- the file -------------------------------------------------------------------------------------


def test_the_journal_is_one_canonical_line_per_entry_and_reads_back(folder, clock):
    set_value(folder, "temperature_derating", 0.8)
    set_value(folder, "bundle_derating", 0.7)
    assert not (folder / "journal.json").exists()
    data = (folder / JOURNAL_FILE).read_bytes()
    raw = data.splitlines(keepends=True)
    assert len(raw) == 3 and all(x.endswith(b"\n") and x.count(b"\n") == 1 for x in raw)
    parsed = lines(folder)
    assert [canonical.dumps_line(x) for x in parsed] == raw  # canonical, no pretty-printing
    assert all("seq" not in x and "parent" in x for x in parsed)
    assert parsed[0]["parent"] == FIRST_CHAIN
    assert [x["parent"] for x in parsed[1:]] == [x["chain"] for x in parsed[:-1]]
    p = load_project(folder).project
    assert [e.seq for e in p.journal] == [1, 2, 3]
    assert [e.chain for e in p.journal] == [x["chain"] for x in parsed]
    assert serialize(p)[JOURNAL_FILE] == data  # a save of the same journal writes the same bytes


def test_a_save_only_adds_lines_at_the_end(folder, clock):
    set_value(folder, "temperature_derating", 0.8)
    before = (folder / JOURNAL_FILE).read_bytes()
    set_value(folder, "bundle_derating", 0.7)
    after = (folder / JOURNAL_FILE).read_bytes()
    assert after.startswith(before) and len(after.splitlines()) == len(before.splitlines()) + 1


def test_the_journal_is_outside_the_hash_and_every_output(folder, clock):
    set_value(folder, "temperature_derating", 0.8)
    p = load_project(folder).project
    with_journal, outputs = model_hash(p), build_outputs(p, drawings=False).files
    p.journal = None
    assert JOURNAL_FILE not in serialize(p)
    assert model_hash(p) == with_journal
    assert build_outputs(p, drawings=False).files == outputs


def test_a_new_journal_tells_git_to_keep_both_sides(tmp_path, clock):
    templates.create_project(tmp_path / "p", "blank", journal=True)
    text = (tmp_path / "p" / ".gitattributes").read_text(encoding="utf-8")
    assert text == GITATTRIBUTES and "journal.jsonl merge=union" in text.splitlines()


def test_the_lines_survive_windows_line_ends_and_empty_lines(folder, clock):
    set_value(folder, "temperature_derating", 0.8)
    path = folder / JOURNAL_FILE
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n") + b"\r\n\n")
    result = load_project(folder)
    assert not result.has_errors and len(result.project.journal) == 2


def test_a_line_that_is_not_json_names_its_line(folder, clock):
    set_value(folder, "temperature_derating", 0.8)
    path = folder / JOURNAL_FILE
    path.write_bytes(path.read_bytes() + b'{"kind": \n')
    result = load_project(folder)
    found = [i for i in result.issues if i.code == "invalid_json"]
    assert found and "line 3" in found[0].message


# ---- what the reader accepts ------------------------------------------------------------------------


def test_a_kind_this_version_does_not_know_is_read_and_shown_as_other(folder, clock, capsys):
    p = load_project(folder).project
    p.journal = p.journal.appended([row(at(5), kind="signoff")])
    (folder / JOURNAL_FILE).write_bytes(journal_bytes(p.journal))
    result = load_project(folder)
    assert not result.has_errors
    last = list(result.project.journal)[-1]
    assert last.kind == "signoff" and shown_kind(last.kind) == "other"
    assert "[other]" in journal.render([last])
    assert records.journal_report(result.project).entries[-1].kind == "signoff"  # the data as it is
    assert "merge" in KINDS and shown_kind("merge") == "merge"
    set_value(folder, "temperature_derating", 0.8)  # a save keeps the line
    assert any(x["kind"] == "signoff" for x in lines(folder))
    assert main(["journal", str(folder)]) == 0
    assert "[other]" in capsys.readouterr().out


@pytest.mark.parametrize("kind", ["Sign off", "", "x" * 41, "1st"])
def test_a_kind_that_is_not_a_short_word_is_damage(kind):
    with pytest.raises(ValueError):
        Journal().appended([row(at(1), kind=kind)])


def test_a_line_that_is_there_twice_is_read_once(folder, clock):
    set_value(folder, "temperature_derating", 0.8)
    rows = lines(folder)
    write_lines(folder, [*rows, rows[1], rows[0]])
    result = load_project(folder)
    assert not result.has_errors and len(result.project.journal) == 2
    set_value(folder, "bundle_derating", 0.7)  # the next save drops the copies
    assert len(lines(folder)) == 3


# ---- tamper evidence ----------------------------------------------------------------------------------


def damaged(folder: Path) -> str:
    result = load_project(folder)
    found = [i.message for i in result.issues if i.code == "journal_damaged"]
    assert found and result.project.journal is None and result.project.recovered
    return found[0]


def three_entries(folder: Path) -> list[dict]:
    set_value(folder, "temperature_derating", 0.8)
    set_value(folder, "bundle_derating", 0.7)
    return lines(folder)


def test_a_changed_line_is_found(folder, clock):
    rows = three_entries(folder)
    rows[1]["new"] = 0.95
    write_lines(folder, rows)
    assert "line 2 was changed" in damaged(folder)
    with pytest.raises(Exception, match="blocked"):
        save_project(load_project(folder).project, folder)  # a damaged record is not written over


def test_a_removed_line_is_found(folder, clock):
    rows = three_entries(folder)
    write_lines(folder, [rows[0], rows[2]])
    assert "follows an entry that is not in the journal" in damaged(folder)


def test_a_line_put_in_with_a_made_up_chain_is_found(folder, clock):
    rows = three_entries(folder)
    forged = {**rows[1], "reason": "not what happened"}
    write_lines(folder, [*rows[:2], forged, rows[2]])
    assert "was changed" in damaged(folder)


def test_a_number_on_a_new_entry_is_found(folder, clock):
    rows = three_entries(folder)
    rows[1]["seq"] = 2
    write_lines(folder, rows)
    assert "both a number and a parent" in damaged(folder)


def test_a_merge_entry_that_names_a_removed_entry_is_found():
    base = Journal().appended([row(at(1))])
    a = base.appended([row(at(2), "Ann")])
    b = base.appended([row(at(3), "Bob")])
    both = Journal((*a.lines, b.lines[-1]))
    merged = journal.merged(both)
    assert len(merged.heads()) == 1
    without = [e for e in merged.lines if e.chain != a.lines[-1].chain]
    with pytest.raises(JournalError, match="not in the journal"):
        Journal(without)


# ---- the order ---------------------------------------------------------------------------------------


def two_branches(*, ann: list[int], bob: list[int]) -> tuple[Journal, Journal]:
    base = Journal().appended([row(at(1), "Base"), row(at(2), "Base")])
    a = base.appended([row(at(s), "Ann", new=s) for s in ann])
    b = base.appended([row(at(s), "Bob", new=s) for s in bob])
    return a, b


def union(a: Journal, b: Journal) -> Journal:
    """What Git's union merge makes of the two files: the common lines, then ours, then theirs."""
    common = len(a.lines) - len([e for e in a.lines if e not in b.lines])
    return Journal((*a.lines, *b.lines[common:]))


def test_the_order_is_by_time_then_author_whatever_the_order_of_the_lines():
    a, b = two_branches(ann=[5, 9], bob=[5, 7])
    ab, ba = union(a, b), union(b, a)
    assert list(ab) == list(ba)
    assert [(e.author, e.new) for e in ab][2:] == [("Ann", 5), ("Bob", 5), ("Bob", 7), ("Ann", 9)]
    assert [e.seq for e in ab] == list(range(1, 7))
    assert len(ab.heads()) == 2 and len(journal.merged(ab).heads()) == 1


def test_an_entry_never_comes_before_its_parent_even_with_a_wrong_clock():
    a, b = two_branches(ann=[50, 3], bob=[4])  # Ann's clock went back
    order = [(e.author, e.new) for e in union(a, b)]
    assert order.index(("Ann", 50)) < order.index(("Ann", 3))


def test_entries_of_format_1_come_first_with_their_numbers():
    from tests.migration_support import old_journal_payload

    plain = Journal().appended([row(at(10)), row(at(11))])
    old = [JournalEntry.model_validate(x) for x in old_journal_payload(plain)["journal"]]
    later = Journal(old).appended([row(at(1), "Early clock")])
    assert [e.seq for e in later] == [1, 2, 3] and later[2].author == "Early clock"
    assert later[2].parent == old[-1].chain and later[0].stored() == old[0].stored()


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_random_branches_and_shuffled_lines_read_the_same(seed):
    """A property test with a fixed seed: up to four branches of random length and random times
    (some earlier than their parent), forked from random places, their lines shuffled and some
    doubled: the journal reads without damage, in one order, every entry after its parent, and a
    changed or removed entry is still found."""
    rnd = random.Random(seed)
    trunk = Journal().appended([row(at(rnd.randrange(60)), "Base", new=i) for i in range(4)])
    every = list(trunk.lines)
    tips = 0
    for b in range(rnd.randint(2, 4)):
        start = rnd.randrange(len(trunk.lines))
        fork = Journal(trunk.lines[: start + 1])
        added = [row(at(rnd.randrange(3600)), rnd.choice("ABC"), new=f"{b}.{i}") for i in range(rnd.randint(1, 5))]  # fmt: skip
        grown = fork.appended(added)
        every += grown.lines[len(fork.lines) :]
        tips += 1
    reference = Journal(every)
    for _ in range(5):
        shuffled = every + rnd.sample(every, 3)
        rnd.shuffle(shuffled)
        j = Journal(shuffled)
        assert list(j) == list(reference) and len(j) == len(every)
        assert [e.seq for e in j] == list(range(1, len(every) + 1))
    place = {e.chain: e.seq for e in reference}
    assert all(place.get(e.parent, 0) < e.seq for e in reference)
    assert 1 <= len(reference.heads()) <= tips + 1
    merged = journal.merged(reference) if len(reference.heads()) > 1 else reference
    assert len(merged.heads()) == 1
    inner = [e for e in reference if e not in reference.heads()]
    gone = rnd.choice(inner)
    with pytest.raises(JournalError):
        Journal([e for e in every if e.chain != gone.chain])
    victim = rnd.choice(every)
    body = {**victim.model_dump(mode="json"), "reason": "changed"}
    with pytest.raises(JournalError):
        Journal([JournalEntry.model_validate(body) if e is victim else e for e in every])


# ---- the step from format 1 to 2 -------------------------------------------------------------------------


def v1_project_with_a_journal(folder: Path) -> Path:
    set_value(folder, "temperature_derating", 0.8)
    set_value(folder, "bundle_derating", 0.7)
    (folder / ".gitattributes").write_text(GITATTRIBUTES_1, encoding="utf-8")
    return as_format(folder, 1)


def test_the_upgrade_moves_the_journal_keeps_every_chain_and_adds_one_entry(folder, clock, capsys):
    root = v1_project_with_a_journal(folder)
    old_bytes = (root / "journal.json").read_bytes()
    old = json.loads(old_bytes)["journal"]
    assert [x["seq"] for x in old] == [1, 2, 3] and all("parent" not in x for x in old)
    assert main(["migrate", str(root), "--dry-run"]) == 0
    dry = capsys.readouterr().out
    assert "new      journal.jsonl" in dry and "removed  journal.json" in dry
    assert "changed  .gitattributes" in dry and "journal entries: 3 -> 4" in dry
    assert main(["migrate", str(root)]) == 0
    assert "journal.jsonl merge=union" in capsys.readouterr().out
    backup = root / ".migration-backup-v1"
    assert (backup / "journal.json").read_bytes() == old_bytes  # the backup holds the old file
    record = json.loads((backup / upgrade.RECORD_NAME).read_text(encoding="utf-8"))
    assert record["status"] == "complete" and "journal.json" in record["files"]["before"]
    assert "journal.jsonl" in record["files"]["after"]
    assert not (root / "journal.json").exists() and (root / "journal.json.bak").exists()
    now = lines(root)
    assert now[:3] == old  # carried over as they were: number, chain, no parent
    migrated = now[3]
    assert migrated["parent"] == old[-1]["chain"] and "seq" not in migrated
    assert migrated["reason"] == "migrated from format 1"
    result = load_project(root)
    assert not result.has_errors and [e.seq for e in result.project.journal] == [1, 2, 3, 4]
    assert (root / ".gitattributes").read_text(encoding="utf-8") == GITATTRIBUTES
    set_value(root, "temperature_derating", 0.9)  # later entries follow on
    assert len(load_project(root).project.journal) == 5


def test_a_rolled_back_upgrade_puts_journal_json_back(folder, clock):
    root = v1_project_with_a_journal(folder)
    old_bytes = (root / "journal.json").read_bytes()

    def fail() -> None:
        raise OSError("disk full")

    with pytest.raises(upgrade.UpgradeFailed) as caught:
        upgrade.upgrade_project(root, on_written=fail)
    assert caught.value.rolled_back
    assert (root / "journal.json").read_bytes() == old_bytes
    assert not (root / JOURNAL_FILE).exists()
    assert (root / ".gitattributes").read_text(encoding="utf-8") == GITATTRIBUTES_1


def test_a_format_2_project_with_journal_json_is_read_and_moved_on_the_next_save(folder, clock):
    """A build of `master` before M7a wrote format 2 with `journal.json` (D-228)."""
    set_value(folder, "temperature_derating", 0.8)
    as_old_journal(folder)
    (folder / ".gitattributes").unlink()
    old = json.loads((folder / "journal.json").read_bytes())["journal"]
    result = load_project(folder)
    assert not result.has_errors and len(result.project.journal) == 2
    assert any(i.code == "journal_old_layout" for i in result.issues)
    set_value(folder, "bundle_derating", 0.7)
    assert (folder / "journal.json.bak").is_file() and not (folder / "journal.json").exists()
    now = lines(folder)
    assert now[:2] == old and now[2]["parent"] == old[-1]["chain"]
    again = load_project(folder)
    assert not again.has_errors and len(again.project.journal) == 3
    assert not any(i.code == "journal_old_layout" for i in again.issues)
    assert "journal.jsonl merge=union" in (folder / ".gitattributes").read_text(encoding="utf-8")


def test_with_both_files_the_entries_of_both_are_read(folder, clock):
    """`journal.json` of a branch that a build before M7a kept writing (one more entry of format 1),
    beside the `journal.jsonl` of a branch that this tool saved."""
    from tests.migration_support import old_journal_payload

    set_value(folder, "temperature_derating", 0.8)
    as_old_journal(folder)
    longer = folder.parent / "longer"
    shutil.copytree(folder, longer)
    set_value(folder, "bundle_derating", 0.7)  # journal.jsonl: 2 entries of format 1 and a new one
    set_value(longer, "bundle_derating", 0.55)
    other = load_project(longer).project.journal
    (folder / "journal.json").write_bytes(canonical.dumps(old_journal_payload(other)))
    result = load_project(folder)
    assert not result.has_errors
    entries = list(result.project.journal)
    assert len(entries) == 4 and [e.seq for e in entries] == [1, 2, 3, 4]
    assert [e.first_format for e in entries] == [True, True, True, False]
    assert len(result.project.journal.heads()) == 2


# ---- .gitattributes -----------------------------------------------------------------------------------


def test_the_gitattributes_get_the_journal_line_once(tmp_path):
    assert add_journal_union(tmp_path) == "written"
    assert (tmp_path / ".gitattributes").read_text(encoding="utf-8") == GITATTRIBUTES
    assert add_journal_union(tmp_path) == "present"
    (tmp_path / ".gitattributes").write_text(GITATTRIBUTES_1, encoding="utf-8")
    assert add_journal_union(tmp_path) == "updated"
    (tmp_path / ".gitattributes").write_text("*.png binary", encoding="utf-8")
    assert add_journal_union(tmp_path) == "added"
    text = (tmp_path / ".gitattributes").read_text(encoding="utf-8")
    assert text.startswith("*.png binary\n#\n") and text.endswith("journal.jsonl merge=union\n")
    assert add_journal_union(tmp_path) == "present"


def test_a_linked_gitattributes_is_left_alone(tmp_path):
    (tmp_path / "elsewhere").write_text("x", encoding="utf-8")
    (tmp_path / ".gitattributes").symlink_to(tmp_path / "elsewhere")
    assert add_journal_union(tmp_path) == "skipped"
    assert (tmp_path / "elsewhere").read_text(encoding="utf-8") == "x"


# ---- both sides of a conflict -------------------------------------------------------------------------


def test_take_both_sides_keeps_ours_then_theirs():
    text = b"a\n<<<<<<< HEAD\nours\n||||||| base\nold\n=======\ntheirs\n>>>>>>> ann\nz\n"
    assert take_both_sides(text) == b"a\nours\ntheirs\nz\n"
    assert take_both_sides(b"<<<<<<< x\nours\n=======\ntheirs\n>>>>>>> y") == b"ours\ntheirs\n"


@pytest.mark.parametrize(
    "text",
    [b"<<<<<<< HEAD\nours\n", b"<<<<<<< HEAD\nours\n>>>>>>> x\n", b"=======\n", b">>>>>>> x\n"],
)
def test_take_both_sides_refuses_markers_that_are_not_well_formed(text):
    with pytest.raises(ValueError):
        take_both_sides(text)


# ---- real merges --------------------------------------------------------------------------------------


def start(tmp_path: Path, attributes: bool = True) -> Path:
    """A repository with the project `design` made by `new` (which starts a journal), committed."""
    git(tmp_path, "init", "-q", "-b", "main")
    design = tmp_path / "design"
    assert main(["new", str(design), "--template", "first-steps"]) == 0
    if not attributes:
        (design / ".gitattributes").unlink()
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "start")
    return design


def work(tmp_path: Path, who: str, value: float, *, generate: bool = False) -> None:
    """A branch of its own on which `who` changes a value of `derating` (and presses Generate)."""
    git(tmp_path, "checkout", "-q", "main")
    git(tmp_path, "checkout", "-q", "-b", who)
    design = tmp_path / "design"
    key = {"ann": "temperature_derating", "bob": "bundle_derating"}[who]
    p = load_project(design).project
    History(p).execute(key, [SetConfig(configcheck.with_value(p.config["derating"], key, value))])
    journal.set_author(who)
    try:
        save_project(p, design)
    finally:
        journal.set_author(None)
    if generate:
        assert main(["--author", who, "generate", str(design)]) == 0
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", who)


def journal_of(design: Path) -> Journal:
    result = load_project(design)
    assert not any(i.code == "journal_damaged" for i in result.issues)
    found = result.project.journal
    assert found is not None
    return found


@needs_git
def test_two_branches_that_both_add_entries_merge_without_a_conflict(tmp_path, capsys):
    design = start(tmp_path)
    work(tmp_path, "ann", 0.8)
    work(tmp_path, "bob", 0.7)
    merged = git(tmp_path, "merge", "-q", "--no-edit", "ann", check=False)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert conflict_files(design) == []
    j = journal_of(design)
    authors = {e.author for e in j}
    assert {"ann", "bob"} <= authors
    heads = j.heads()
    assert sorted(h.author for h in heads) == ["ann", "bob"]
    assert main(["validate", str(design)]) == 0
    capsys.readouterr()
    assert main(["--author", "bob", "merge-fix", str(design)]) == 0
    assert "one merge entry" in capsys.readouterr().out
    after = journal_of(design)
    last = list(after)[-1]
    assert (last.kind, last.author) == ("merge", "bob")
    assert sorted(last.new["heads"]) == sorted(h.chain for h in heads)
    assert len(after.heads()) == 1 and len(after) == len(j) + 1
    assert main(["merge-fix", str(design)]) == 0  # nothing more to record
    assert "Nothing to fix" in capsys.readouterr().out
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "merge recorded")
    assert main(["validate", str(design)]) == 0


@needs_git
def test_merge_fix_says_the_journal_was_merged_in_json(tmp_path, capsys):
    design = start(tmp_path)
    work(tmp_path, "ann", 0.8)
    work(tmp_path, "bob", 0.7)
    git(tmp_path, "merge", "-q", "--no-edit", "ann")
    capsys.readouterr()
    assert main(["merge-fix", str(design), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["result"] == "journal_merged"


@needs_git
def test_without_the_union_line_merge_fix_keeps_both_sides_of_the_journal(tmp_path):
    design = start(tmp_path, attributes=False)
    work(tmp_path, "ann", 0.8)
    work(tmp_path, "bob", 0.7)
    assert git(tmp_path, "merge", "ann", check=False).returncode != 0
    assert conflict_files(design) == [JOURNAL_FILE]
    assert b"<<<<<<<" in (design / JOURNAL_FILE).read_bytes()
    plan = plan_merge_fix(design)
    assert plan.ok and plan.new_journal is not None
    assert main(["merge-fix", str(design)]) == 0
    j = journal_of(design)
    assert {"ann", "bob"} <= {e.author for e in j} and len(j.heads()) == 1
    assert list(j)[-1].kind == "merge"
    assert main(["check", str(design)]) == 0


@needs_git
def test_both_generate_the_record_conflicts_and_the_journal_does_not(tmp_path):
    design = start(tmp_path)
    work(tmp_path, "ann", 0.8, generate=True)
    work(tmp_path, "bob", 0.7, generate=True)
    assert git(tmp_path, "merge", "ann", check=False).returncode != 0
    assert conflict_files(design) == ["generated/generation.json"]  # the journal merged
    assert len(journal_of(design).heads()) == 2
    assert main(["merge-fix", str(design)]) == 0
    j = journal_of(design)
    assert "merge" in [e.kind for e in j]
    assert len(j.heads()) == 1
    assert main(["verify", str(design)]) == 0
    git(tmp_path, "add", "-A")
    assert git(tmp_path, "commit", "-q", "-m", "merge", check=False).returncode == 0


@needs_git
def test_a_damaged_journal_after_a_merge_is_refused_and_nothing_changes(tmp_path, capsys):
    design = start(tmp_path)
    work(tmp_path, "ann", 0.8)
    work(tmp_path, "bob", 0.7)
    git(tmp_path, "merge", "-q", "--no-edit", "ann")
    rows = lines(design)
    rows[1]["reason"] = "changed"
    write_lines(design, rows)
    before = tree(design)
    capsys.readouterr()
    assert main(["merge-fix", str(design)]) == 1
    assert "journal" in capsys.readouterr().err
    assert tree(design) == before


def test_record_journal_merge_does_nothing_without_a_journal_file(tmp_path, clock):
    templates.create_project(tmp_path / "p", "blank")
    assert record_journal_merge(tmp_path / "p") == 0


# ---- the autosave of the editor --------------------------------------------------------------------


def test_the_autosave_of_a_project_with_a_change_journal_restores_it(folder, clock):
    from harness_design_studio.core import recovery

    set_value(folder, "temperature_derating", 0.8)
    p = load_project(folder).project
    History(p).execute(
        "x", [SetConfig(configcheck.with_value(p.config["derating"], "bundle_derating", 0.55))]
    )
    recovery.write_journal(p, folder)
    assert recovery.journal_differs_from_disk(folder)
    restored = recovery.read_journal(folder)
    assert restored is not None and not restored.has_errors
    assert list(restored.project.journal) == list(p.journal)
    save_project(restored.project, folder)
    assert len(load_project(folder).project.journal) == 3
