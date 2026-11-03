# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg,func-returns-value"
"""S4 (D-191, R8): the change journal. It reproduces the history of a project from its first edit (who,
when, old, new, reason), is append-only, is a file of its own that no hash and no output holds, and
exists only in a project that asked for one."""

import json
import os
import shutil
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_design_studio.cli.main import main
from harness_design_studio.core import checks, configcheck, drc, journal, part_approval, templates
from harness_design_studio.core.commands import Delete, History, Put, SetConfig
from harness_design_studio.core.errors import SaveError
from harness_design_studio.core.io.layout import model_hash, serialize
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import ChangeEntry, Journal, JournalError, evolve
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.wires import plan_override


class Clock:
    """A clock and an author that tests set: every call of `now()` is one second later."""

    def __init__(self, monkeypatch, who="Ann Engineer"):
        self.n = 0
        self.who = who
        monkeypatch.setattr(journal, "now", self.now)
        monkeypatch.setattr(journal, "author", lambda: self.who)

    def now(self) -> str:
        self.n += 1
        return f"2026-11-03T10:00:{self.n:02d}Z"


@pytest.fixture
def clock(monkeypatch):
    return Clock(monkeypatch)


@pytest.fixture
def folder(tmp_path, clock):
    templates.create_project(tmp_path / "p", "flatsat", journal=True)
    return tmp_path / "p"


def edit_and_save(folder, label, ops_of):
    """Open the project as a person would, make one edit, save."""
    p = load_project(folder).project
    History(p).execute(label, ops_of(p))
    save_project(p, folder)
    return p


def lines(p) -> list[str]:
    return journal.render(p.journal).splitlines()


# ---- the history of a scripted sequence of edits -----------------------------------------------


def test_the_journal_reproduces_the_history_from_the_first_edit(folder, clock):
    first = load_project(folder).project
    assert [e.kind for e in first.journal] == ["start"]
    # 1. a configuration value
    edit_and_save(
        folder,
        "temperature",
        lambda p: [
            SetConfig(configcheck.with_value(p.config["derating"], "temperature_derating", 0.8))
        ],
    )
    # 2. an override of a wire
    wid = load_project(folder).project.harnesses["W001"].wires[0].id
    edit_and_save(
        folder,
        "override",
        lambda p: plan_override(p, wid, "colour", "pink", "colour code of the program"),
    )

    # 3. a waiver
    def waive(p):
        f = next(f for f in drc.run(p) if f.rule == "connector-lookalike")
        return [checks.waive_op(f, "Keyed differently in the drawing, see ICD")]

    waived = edit_and_save(folder, "waive", waive)
    waived_id = next(iter(waived.waivers))
    # 4. the approval of a part
    edit_and_save(folder, "approve", lambda p: part_approval.ops_approve_part(p, "EX-DSUB-9-F"))
    # 5. a regeneration that changes the harnesses
    p = load_project(folder).project
    from harness_design_studio.core.generate.engine import generate_project

    generate_project(p)
    save_project(p, folder)

    p = load_project(folder).project
    assert [e.seq for e in p.journal] == list(range(1, len(p.journal) + 1))
    assert {e.author for e in p.journal} == {"Ann Engineer"}
    assert all(e.when.startswith("2026-11-03T10:00:") for e in p.journal)
    kinds = [(e.kind, e.object, e.field) for e in p.journal]
    assert kinds[0] == ("start", "project", "journal")
    assert ("config", "config:derating.temperature_derating", "value") in kinds
    config = next(e for e in p.journal if e.object == "config:derating.temperature_derating")
    assert (config.old, config.new) == (0.9, 0.8)
    over = next(e for e in p.journal if e.kind == "override")
    assert over.object == f"wire:{wid}" and over.field == "colour"
    assert over.new == "pink" and over.reason == "colour code of the program"
    waiver = next(e for e in p.journal if e.kind == "waiver")
    assert waiver.object == f"waiver:{waived_id}" and waiver.field == "(added)"
    assert waiver.reason == "Keyed differently in the drawing, see ICD"
    approval = next(e for e in p.journal if e.kind == "approval")
    assert (approval.object, approval.field) == ("part:EX-DSUB-9-F", "approval")
    assert (approval.old, approval.new) == ("pending", "approved")
    # the times are in the order of the saves
    assert [e.when for e in p.journal] == sorted(e.when for e in p.journal)
    # and the text a person reads names who, when, what, from what to what, and why
    text = journal.render(p.journal)
    assert "#1 2026-11-03T10:00:01Z Ann Engineer [start] project journal" in text
    assert "[config] config:derating.temperature_derating value: 0.9 -> 0.8" in text
    assert "(reason: colour code of the program)" in text


def test_a_regeneration_is_one_entry_for_each_harness_with_counts_and_hashes(folder, clock):
    from harness_design_studio.core.generate.engine import generate_project

    p = load_project(folder).project
    History(p).execute(
        "temperature",
        [SetConfig(configcheck.with_value(p.config["derating"], "bundle_derating", 0.3))],
    )
    save_project(p, folder)
    before = model_hash(p)
    generate_project(p)
    save_project(p, folder)
    gen = [e for e in p.journal if e.kind == "generate"]
    assert gen, "the new bundle factor changes the gauges, so harnesses change"
    assert len({e.object for e in gen}) == len(
        gen
    )  # one entry for each harness, not for each field
    assert all(
        e.object.startswith("harness:W") and e.field == "generate"
        for e in gen
        if e.object != "project"
    )
    one = gen[0]
    assert one.old["model_hash"] == before[:12]
    assert one.new["model_hash"] == model_hash(p)[:12]
    assert one.new["wires_changed"] > 0 and one.new["wires_added"] == 0 == one.new["wires_removed"]
    wire_entries = [e for e in p.journal if e.object.startswith("wire:") and e.kind != "override"]
    assert wire_entries == []  # no entry for the fields generation changed


def test_a_save_with_no_change_adds_nothing(folder, clock):
    p = load_project(folder).project
    n = len(p.journal)
    save_project(p, folder)
    save_project(load_project(folder).project, folder)
    assert len(load_project(folder).project.journal) == n
    assert clock.n == 1  # (the clock was read once, for the start)


def test_a_change_of_a_release_is_recorded_with_its_comment(folder, clock):
    p = load_project(folder).project
    entry = ChangeEntry(
        id="C0001",
        harness_id="W001",
        revision="A",
        kind="release",
        by="B. Boss",
        when="2026-11-03",
        comment="Released for the vibration test",
    )
    History(p).execute(
        "release",
        [Put("changelog", entry), Put("harnesses", evolve(p.harnesses["W001"], status="released"))],
    )
    save_project(p, folder)
    mine = [e for e in p.journal if e.kind == "release"]
    assert {(e.object, e.field) for e in mine} == {
        ("harness:W001", "release"),
        ("harness:W001", "status"),
    }
    note = next(e for e in mine if e.field == "release")
    assert note.reason == "Released for the vibration test" and note.new["by"] == "B. Boss"


def test_many_objects_arriving_together_are_one_entry(folder, clock):
    from harness_design_studio.core.model import Part

    p = load_project(folder).project
    parts = [Part(id=f"BULK-{i:03d}", category="wire") for i in range(40)]
    History(p).execute("import", [Put("parts", x) for x in parts])
    save_project(p, folder)
    mine = [e for e in p.journal if e.object.startswith("part:")]
    assert len(mine) == 1 and mine[0].kind == "import" and mine[0].new == "40 objects"


def test_adding_and_deleting_an_object_is_recorded(folder, clock):
    from harness_design_studio.core.model import Part

    p = load_project(folder).project
    History(p).execute("add", [Put("parts", Part(id="LOOSE-1", category="wire"))])
    save_project(p, folder)
    History(p).execute("delete", [Delete("parts", "LOOSE-1")])
    save_project(p, folder)
    mine = [(e.field, e.kind) for e in p.journal if e.object == "part:LOOSE-1"]
    assert mine == [("(created)", "edit"), ("(removed)", "edit")]


# ---- append-only -------------------------------------------------------------------------------


def test_the_api_refuses_to_change_or_remove_an_earlier_entry(folder, clock):
    p = load_project(folder).project
    j = p.journal
    first = j[0]
    with pytest.raises(JournalError, match="append-only"):
        j[0] = first
    with pytest.raises(JournalError, match="append-only"):
        del j[0]
    for name in ("amend", "remove", "replace", "insert", "pop", "clear"):
        with pytest.raises(JournalError, match="append-only"):
            getattr(j, name)()
    with pytest.raises(ValidationError):  # an entry is a frozen object
        first.reason = "changed"  # type: ignore[misc]
    assert j[0] == first and len(j) == 1


def test_entries_can_only_be_added_at_the_end(folder, clock):
    p = load_project(folder).project
    j = p.journal
    more = j.appended(
        [
            dict(
                kind="edit",
                object="project",
                field="name",
                old="a",
                new="b",
                when="2026-11-03T10:00:09Z",
                author="X",
                tool_version="1",
            )
        ]
    )
    assert [e.seq for e in more] == [1, 2] and len(j) == 1  # the first journal is not changed
    assert more[0] == j[0]


def tamper(folder: Path, fn) -> None:
    path = folder / "journal.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data["journal"])
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def two_entries(folder):
    edit_and_save(
        folder,
        "temperature",
        lambda p: [
            SetConfig(configcheck.with_value(p.config["derating"], "temperature_derating", 0.8))
        ],
    )
    edit_and_save(
        folder,
        "bundle",
        lambda p: [SetConfig(configcheck.with_value(p.config["derating"], "bundle_derating", 0.7))],
    )


def test_a_changed_entry_makes_validate_report_a_damaged_journal(folder, clock, capsys):
    two_entries(folder)
    tamper(folder, lambda entries: entries[1].update(new=0.95))
    assert main(["validate", str(folder)]) == 1
    out = capsys.readouterr().out
    assert "journal_damaged" in out and "entry 2 was changed" in out
    result = load_project(folder)
    assert result.project.journal is None and result.project.recovered
    with pytest.raises(SaveError):
        save_project(result.project, folder)  # a damaged record is never written over


def test_a_removed_entry_makes_validate_report_a_damaged_journal(folder, clock, capsys):
    two_entries(folder)
    tamper(folder, lambda entries: entries.pop(1))
    assert main(["validate", str(folder)]) == 1
    assert "journal_damaged" in capsys.readouterr().out


def test_an_entry_put_in_makes_validate_report_a_damaged_journal(folder, clock, capsys):
    two_entries(folder)

    def put_in(entries):
        extra = dict(entries[1])
        extra["seq"] = 2
        entries.insert(1, extra)

    tamper(folder, put_in)
    assert main(["validate", str(folder)]) == 1
    assert "journal_damaged" in capsys.readouterr().out


def test_a_journal_that_is_not_a_list_of_entries_is_damaged(folder, clock):
    (folder / "journal.json").write_text('{"journal": 5}\n', encoding="utf-8")
    result = load_project(folder)
    assert any(i.code == "journal_damaged" for i in result.issues) and result.has_errors


def test_a_whole_journal_validates(folder, clock, capsys):
    two_entries(folder)
    assert main(["validate", str(folder)]) == 0
    assert "journal_damaged" not in capsys.readouterr().out


# ---- where it lives: not in the model hash, not in any output, not in the design files ---------


def test_the_journal_is_not_part_of_the_model_hash_or_the_outputs(folder, clock):
    p = load_project(folder).project
    with_journal = model_hash(p)
    outputs = build_outputs(p, drawings=False).files
    assert "journal.json" in serialize(p)
    p.journal = None
    assert "journal.json" not in serialize(p)
    assert model_hash(p) == with_journal
    assert build_outputs(p, drawings=False).files == outputs
    assert not any("journal" in name for name in outputs)


def test_the_same_design_saved_at_another_time_by_another_person_has_the_same_design_files(
    tmp_path, monkeypatch
):
    a, b = tmp_path / "a", tmp_path / "b"
    Clock(monkeypatch, "Ann")
    templates.create_project(a, "flatsat", journal=True)
    Clock(monkeypatch, "Bob").n = 40
    templates.create_project(b, "flatsat", journal=True)

    def tree(root):
        return {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*.json"))
            if "outputs" not in p.parts
        }

    ta, tb = tree(a), tree(b)
    assert ta.pop("journal.json") != tb.pop("journal.json")
    assert ta == tb
    for data in ta.values():
        assert b"Ann" not in data and b"2026-11" not in data


# ---- opt-in: a project that has no journal is opened and saved as it was -----------------------


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".bak" not in p.name and not p.name.startswith(".harness.")
    }


@pytest.mark.parametrize(
    "template", ["blank", "first-steps", "minimal-satellite", "small-satellite", "flatsat"]
)
def test_a_project_without_a_journal_is_unchanged_byte_for_byte_after_open_and_save(
    tmp_path, template
):
    folder = tmp_path / "p"
    templates.create_project(folder, template)
    before = tree_bytes(folder)
    assert "journal.json" not in before
    p = load_project(folder).project
    assert p.journal is None
    save_project(p, folder)
    assert tree_bytes(folder) == before
    # and after an edit, still no journal is made
    History(p).execute(
        "x", [SetConfig(configcheck.with_value(p.config["derating"], "bundle_derating", 0.4))]
    )
    save_project(p, folder)
    assert "journal.json" not in tree_bytes(folder)


def test_create_project_makes_a_journal_only_when_asked(tmp_path):
    templates.create_project(tmp_path / "a", "flatsat")
    templates.create_project(tmp_path / "b", "flatsat", journal=True)
    assert not (tmp_path / "a" / "journal.json").exists()
    assert (tmp_path / "b" / "journal.json").is_file()


def test_the_new_command_starts_a_journal_unless_told_not_to(tmp_path, clock, capsys):
    assert main(["new", str(tmp_path / "a"), "--template", "first-steps"]) == 0
    assert main(["new", str(tmp_path / "b"), "--template", "first-steps", "--no-journal"]) == 0
    assert (tmp_path / "a" / "journal.json").is_file()
    assert not (tmp_path / "b" / "journal.json").exists()
    assert load_project(tmp_path / "a").project.journal[0].kind == "start"
    assert main(["validate", str(tmp_path / "a")]) == 0


def test_journal_start_begins_a_journal_for_an_existing_project(tmp_path, clock, capsys):
    folder = tmp_path / "p"
    templates.create_project(folder, "flatsat")
    before = tree_bytes(folder)
    assert main(["journal", str(folder)]) == 0
    assert "has no change journal" in capsys.readouterr().out
    assert tree_bytes(folder) == before
    assert main(["journal", str(folder), "--start"]) == 0
    after = tree_bytes(folder)
    assert set(after) - set(before) == {"journal.json"}
    assert {k: v for k, v in after.items() if k != "journal.json"} == before
    assert main(["journal", str(folder), "--start"]) == 0
    assert "has a journal already" in capsys.readouterr().out
    assert len(load_project(folder).project.journal) == 1


# ---- reading it --------------------------------------------------------------------------------


def test_cli_journal_prints_filters_and_gives_json(folder, clock, capsys):
    two_entries(folder)
    capsys.readouterr()
    assert main(["journal", str(folder)]) == 0
    text = capsys.readouterr().out
    assert text.count("\n") == 3 and "Ann Engineer" in text
    assert main(["journal", str(folder), "--since", "1"]) == 0
    assert capsys.readouterr().out.count("\n") == 2
    assert main(["journal", str(folder), "--object", "derating.bundle_derating"]) == 0
    only = capsys.readouterr().out
    assert only.count("\n") == 1 and "0.7" in only
    assert main(["journal", str(folder), "--object", "derating", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)["entries"]
    assert [d["object"] for d in data] == [
        "config:derating.temperature_derating",
        "config:derating.bundle_derating",
    ]
    assert main(["journal", str(folder), "--object", "nothing"]) == 0
    assert "No entries match" in capsys.readouterr().out


def test_explain_shows_the_history_of_a_wire(folder, clock, capsys):
    wid = load_project(folder).project.harnesses["W001"].wires[0].id
    edit_and_save(
        folder, "override", lambda p: plan_override(p, wid, "colour", "pink", "colour code")
    )
    capsys.readouterr()
    assert main(["explain", str(folder), wid]) == 0
    out = capsys.readouterr().out
    assert f"History of {wid} (from the change journal)" in out
    assert "Ann Engineer" in out and "colour code" in out and "[override]" in out


def test_explain_of_a_project_without_a_journal_has_no_history(tmp_path, capsys):
    templates.create_project(tmp_path / "p", "flatsat")
    wid = load_project(tmp_path / "p").project.harnesses["W001"].wires[0].id
    assert main(["explain", str(tmp_path / "p"), wid]) == 0
    assert "History of" not in capsys.readouterr().out


# ---- who is working ----------------------------------------------------------------------------


def test_the_author_is_the_option_then_the_environment_then_git_then_the_user(
    tmp_path, monkeypatch
):
    git = tmp_path / "gitconfig"
    git.write_text("[user]\n\tname = Git Person\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(git))
    monkeypatch.delenv("HARNESS_AUTHOR", raising=False)
    monkeypatch.setenv("USER", "login")
    journal.set_author(None)
    assert journal.author() == "Git Person"
    monkeypatch.setenv("HARNESS_AUTHOR", "From Env")
    assert journal.author() == "From Env"
    journal.set_author("From Option")
    try:
        assert journal.author() == "From Option"
    finally:
        journal.set_author(None)
    monkeypatch.delenv("HARNESS_AUTHOR")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.chdir(tmp_path)
    assert journal.author() == "login"
    monkeypatch.delenv("USER")
    monkeypatch.delenv("USERNAME", raising=False)
    monkeypatch.delenv("LOGNAME", raising=False)  # resolve_author reads it after USER and USERNAME
    assert journal.author() == "unknown"


def test_the_author_option_of_the_command_line_names_the_author(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "now", lambda: "2026-11-03T10:00:00Z")
    try:
        assert (
            main(
                [
                    "--author",
                    "Option Person",
                    "new",
                    str(tmp_path / "p"),
                    "--template",
                    "first-steps",
                ]
            )
            == 0
        )
        assert load_project(tmp_path / "p").project.journal[0].author == "Option Person"
    finally:
        journal.set_author(None)


# ---- saving stays quick ------------------------------------------------------------------------


@pytest.mark.perf
def test_the_journal_does_not_slow_a_save(tmp_path, clock):
    """One edit and a save, with and without a journal: the comparison of the files that changed is
    all the journal costs."""
    with_j, without = tmp_path / "with", tmp_path / "without"
    templates.create_project(with_j, "flatsat", journal=True)
    templates.create_project(without, "flatsat")

    def once(folder) -> float:
        p = load_project(folder).project
        best = 1e9
        for k in range(5):
            History(p).execute(
                "x",
                [
                    SetConfig(
                        configcheck.with_value(
                            p.config["derating"], "bundle_derating", 0.3 + k / 100
                        )
                    )
                ],
            )
            t = time.perf_counter()
            save_project(p, folder)
            best = min(best, time.perf_counter() - t)
        return best

    a, b = once(with_j), once(without)
    assert a < b * 2.5 + 0.05, (a, b)
    assert a < 1.0


def test_journal_text_of_a_new_project_is_canonical_and_whole(tmp_path, clock):
    from harness_design_studio.core.io.loader import non_canonical_files

    folder = tmp_path / "p"
    templates.create_project(folder, "flatsat", journal=True)
    p = load_project(folder).project
    assert non_canonical_files(folder, p) == []
    assert isinstance(p.journal, Journal)
    shutil.rmtree(folder)
