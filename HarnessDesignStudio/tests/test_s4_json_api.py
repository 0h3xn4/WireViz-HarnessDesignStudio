# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg"
"""S4 meets S6 and S7: `override`, `journal` and `deviation` print one JSON document, the scripting
interface does the same things with the same data, and an import is an entry of the journal while
the import record stays out of the model hash."""

import json

import pytest

from harness_design_studio import api
from harness_design_studio.cli.jsonout import SHAPES
from harness_design_studio.cli.main import main
from harness_design_studio.core import drc, journal, templates
from harness_design_studio.core.io import layout
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.wires import find_wire

LENGTHS = "harness,segment,length\nW001,W001-L1,850\nW002,W002-L1,900\n"


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(journal, "now", lambda: "2026-11-03T11:30:00Z")
    monkeypatch.setenv("HARNESS_AUTHOR", "Ann Engineer")  # `author=` and `--author` come first


@pytest.fixture
def folder(tmp_path):
    api.create_project(tmp_path / "p", "flatsat")
    return tmp_path / "p"


def doc(capsys, *argv, rc=0):
    assert main([*map(str, argv), "--json"]) == rc, argv
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is (rc == 0)
    return out


def a_wire(folder) -> str:
    return next(w.id for w in load_project(folder).project.harnesses["W001"].wires if not w.manual)


def test_the_documents_have_the_keys_of_their_shapes(folder, capsys):
    wid = a_wire(folder)
    assert list(doc(capsys, "journal", folder)) == list(SHAPES["journal"])
    assert list(doc(capsys, "override", folder, wid)) == list(SHAPES["override"])
    assert list(doc(capsys, "deviation", folder)) == list(SHAPES["deviation"])
    bare = folder.parent / "bare"
    api.create_project(bare, "flatsat", journal=False)
    assert doc(capsys, "journal", bare, "--start")["started"] is True
    assert list(doc(capsys, "journal", bare, "--start")) == list(SHAPES["journal --start"])


def test_override_and_deviation_in_json(folder, capsys):
    wid = a_wire(folder)
    got = doc(capsys, "override", folder, wid, "gauge_awg", 26, "--reason", "Smaller connector")
    assert got["action"] == "set" and got["changed"] is True
    assert got["overrides"] == [{"field": "gauge_awg", "value": 26, "reason": "Smaller connector"}]
    assert got["derivation"]["id"] == "wire-override"
    again = doc(capsys, "override", folder, wid, "gauge_awg", 26, "--reason", "Smaller connector")
    assert again["changed"] is False
    entries = doc(capsys, "journal", folder, "--object", wid)["entries"]
    assert [e["kind"] for e in entries] == ["override"] and entries[0]["author"] == "Ann Engineer"
    finding = next(
        f for f in drc.run(load_project(folder).project) if f.rule == "current-over-wire"
    )
    listed = doc(capsys, "deviation", folder, finding.id, "--reason", "Accepted, NCR-17 refers")
    assert listed["action"] == "record" and listed["deviations"][0]["id"] == finding.id
    assert "Ann Engineer" in doc(capsys, "deviation", folder)["deviations"][0]["by"]
    assert doc(capsys, "deviation", folder, finding.id, "--remove")["action"] == "remove"
    cleared = doc(capsys, "override", folder, wid, "--clear", "gauge_awg")
    assert cleared["action"] == "clear" and cleared["changed"] is True


def test_a_refusal_prints_no_document(folder, capsys):
    wid = a_wire(folder)
    assert main(["override", str(folder), wid, "gauge_awg", "26", "--reason", " ", "--json"]) == 1
    got = capsys.readouterr()
    assert got.out == "" and "reason" in got.err


def test_the_interface_gives_the_same_data_as_the_command(folder, capsys):
    wid = a_wire(folder)
    result = api.set_override(folder, wid, "colour", "pink", "customer request", author="Bo")
    assert result.changed and result.overrides[0].reason == "customer request"
    assert result.derivation is not None and result.derivation.id == "wire-override"
    assert result.to_dict()["overrides"] == doc(capsys, "override", folder, wid)["overrides"]
    shown = api.get_overrides(folder, wid)
    assert shown.to_dict() | {"action": "set", "changed": True} == result.to_dict()
    report = api.get_journal(folder, object_id=wid)
    assert [e.author for e in report.entries] == ["Bo"] and report.has_journal
    assert report.to_dict()["entries"] == doc(capsys, "journal", folder, "--object", wid)["entries"]
    cleared = api.clear_override(folder, wid, "colour")
    assert cleared.changed and cleared.overrides == ()
    assert api.get_journal(folder, since=10_000).entries == ()


def test_deviations_through_the_interface(folder):
    wid = a_wire(folder)
    api.set_override(folder, wid, "gauge_awg", 26, "Smaller connector, ECR-12")
    finding = next(
        f for f in drc.run(load_project(folder).project) if f.rule == "current-over-wire"
    )
    with pytest.raises(api.EditError):
        api.accept_deviation(folder, finding.id, "short")
    done = api.accept_deviation(folder, finding.id, "Accepted by the PA board", author="Cy")
    assert done.finding == finding.id and "Cy" in done.deviations[0].by
    assert [d.id for d in api.list_deviations(folder)] == [finding.id]
    assert api.remove_deviation(folder, finding.id).action == "remove"
    assert api.list_deviations(folder) == []


def test_the_interface_starts_a_journal_when_asked(tmp_path):
    api.create_project(tmp_path / "a", "first-steps", journal=False)
    assert not (tmp_path / "a" / "journal.json").exists()
    assert api.get_journal(tmp_path / "a").has_journal is False
    assert api.start_journal(tmp_path / "a", author="Di") is True
    assert api.start_journal(tmp_path / "a") is False
    assert api.get_journal(tmp_path / "a").entries[0].author == "Di"


def test_an_import_is_a_journal_entry_and_the_record_is_not_in_the_hash(tmp_path, capsys):
    dest = tmp_path / "design"
    templates.create_project(dest, "first-steps", journal=True)
    assert main(["generate", str(dest)]) == 0
    before = layout.model_hash(load_project(dest).project)
    (dest / "lengths.csv").write_text(LENGTHS, encoding="utf-8")
    assert main(["import-lengths", str(dest), str(dest / "lengths.csv")]) == 0
    project = load_project(dest).project
    assert project.import_records, "the import left a record"
    imports = [e for e in project.journal if e.kind == "import" and e.object.startswith("import:")]
    assert (
        imports and imports[0].field == "(recorded)" and imports[0].new["source"] == "lengths.csv"
    )
    assert imports[0].new["rows_read"] == 2
    kept = dict(project.import_records)
    project.import_records.clear()
    without = layout.model_hash(project)
    project.import_records.update(kept)
    assert layout.model_hash(project) == without
    assert before != without  # the lengths themselves are part of the design
    # journal.json is out of the hash and so is imports/records.json: the bytes of the file system say so
    assert journal.files_hash(layout.serialize(project, tool_version="")) == without
    save_project(project, dest)
    assert (dest / "imports" / "records.json").is_file()


# ---- S5: one operator, the open data and the screen -----------------------------------------------


def test_the_journal_and_the_run_record_resolve_the_operator_in_one_place(monkeypatch, tmp_path):
    from harness_design_studio.core import run_record

    config = tmp_path / "gitconfig"
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    config.write_text('[user]\n\tname = "Git Name"\n', encoding="utf-8")
    monkeypatch.delenv("HARNESS_AUTHOR", raising=False)
    assert journal.resolve_author(None, environ={}) == "Git Name"
    assert run_record.resolve_operator(None, environ={}) == "Git Name"
    assert run_record.resolve_operator(" Given ", environ={}) == journal.resolve_author("Given")
    config.write_text("", encoding="utf-8")
    for env in ({"USER": "u"}, {"USERNAME": "w"}, {"LOGNAME": "l"}, {}):
        assert run_record.resolve_operator(None, environ=env) == journal.resolve_author(
            None, environ=env
        )
    journal.set_author("Via option")
    try:
        assert journal.author() == "Via option"
    finally:
        journal.set_author(None)


def test_the_author_before_the_command_reaches_the_journal_of_a_command_with_its_own_author(
    tmp_path,
):
    a, b = tmp_path / "a", tmp_path / "b"
    api.create_project(a, "first-steps")
    api.create_project(b, "first-steps")
    assert main(["--author", "Eve", "generate", str(a)]) == 0
    assert main(["generate", str(b), "--run-record", "--author", "Fay"]) == 0
    for dest, who in ((a, "Eve"), (b, "Fay")):
        entries = load_project(dest).project.journal
        assert {e.author for e in entries if e.kind == "generate"} == {who}


def test_the_open_data_says_only_whether_there_is_a_journal_and_counts_overrides(folder):
    from harness_design_studio.core import open_data

    wid = a_wire(folder)
    project = load_project(folder).project
    files = open_data.data_files(project)
    assert json.loads(files["provenance.json"])["design"]["journal"] == "present"
    assert b"Ann Engineer" not in b"".join(files.values()) and b"2026-11-03" not in b"".join(
        files.values()
    )
    assert "overrides.wires" not in {r["id"] for r in json.loads(files["settings.json"])["rows"]}
    api.set_override(folder, wid, "colour", "pink", "customer request")
    project = load_project(folder).project
    got = json.loads(open_data.data_files(project)["settings.json"])
    assert [r["value"] for r in got["rows"] if r["id"] == "overrides.wires"] == [1]
    project.journal = None
    prov = json.loads(open_data.data_files(project)["provenance.json"])
    assert prov["design"]["journal"] == "absent"


def test_a_gauge_override_shows_its_cross_section_on_the_screen_only(folder):
    from harness_design_studio.core.derive import explain_wire, render
    from harness_design_studio.gui.harness_view import wire_hand_lock

    wid = a_wire(folder)
    api.set_override(folder, wid, "gauge_awg", 24, "supplier stock")
    project = load_project(folder).project
    tip, word = wire_hand_lock(find_wire(project, wid)[1])
    assert tip is not None
    assert "gauge_awg 24 (0.205 mm²): supplier stock" in tip and word
    shown = render(next(d for d in explain_wire(project, wid) if d.id == "wire-override"))
    assert "24 AWG (0.205 mm²)" in shown
    written = (folder / "journal.json").read_text(encoding="utf-8")
    assert "mm²" not in written


# ---- S8: extensions are design inputs the journal records, and are outside the hash ---------------


def test_the_journal_records_the_extension_files_and_the_hash_ignores_them(folder):
    from harness_design_studio.core.io.layout import outside_the_hash

    for rel in (
        "journal.json",
        "imports/records.json",
        "extensions/enabled.json",
        "asbuilt/x.json",
    ):
        assert outside_the_hash(rel), rel
    assert not outside_the_hash("config/derating.json")
    before = layout.model_hash(load_project(folder).project)
    ext = folder / "extensions"
    ext.mkdir()
    (ext / "enabled.json").write_bytes(b'{"declarative": [], "plugins": []}\n')
    (ext / "rule.json").write_bytes(b'{"format": 1}\r\n')  # bytes as they are, CRLF included
    project = load_project(folder).project
    assert layout.model_hash(project) == before
    save_project(project, folder)
    got = [e for e in load_project(folder).project.journal if e.object.startswith("extension:")]
    assert [(e.kind, e.object, e.field) for e in got] == [
        ("config", "extension:enabled.json", "(added)"),
        ("config", "extension:rule.json", "(added)"),
    ]
    save_project(load_project(folder).project, folder)  # nothing changed: nothing recorded
    assert len([e for e in load_project(folder).project.journal if "extension:" in e.object]) == 2
    (ext / "rule.json").write_bytes(b'{"format": 2}\n')
    (ext / "enabled.json").unlink()
    save_project(load_project(folder).project, folder)
    last = [e for e in load_project(folder).project.journal if "extension:" in e.object][2:]
    assert [(e.object, e.field) for e in last] == [
        ("extension:enabled.json", "(removed)"),
        ("extension:rule.json", "(changed)"),
    ]
