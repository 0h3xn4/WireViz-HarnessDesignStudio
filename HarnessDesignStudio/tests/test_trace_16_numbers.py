# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""D-191, S10: the trace test of 16 real numbers, repeated with the tool's own surfaces and timed.

The audit traced 16 numbers of the examples to their inputs by reading code, files and documents
(3 to 25 minutes each). `tools/trace_numbers.py` does it with `explain`, `export-data` and
`settings --json` only. What is checked: the 16 rows are the 16 of the audit; each resolves
completely (an equation, every input with a source, every configuration key a setting that
`settings --json` lists, every assumption listed, what is not set named) and agrees with the same
number in the exported files; each takes under a minute (`HARNESS_TIME_FACTOR` scales it for a slow
runner); `docs/transparency_trace_results.md` is what the tool writes (without the timings); and a
trace that loses a source is reported as incomplete, so that the test can fail.

The tests that trace the numbers take about 10 s together, so they are marked `slow` (pull requests
skip them; the master run and the release check run them)."""

import dataclasses
import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_design_studio import api
from tests.helpers import within
from tools import trace_numbers
from tools.trace_numbers import ROWS, TARGET, Resolution, Session, command, render_page

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def results(tmp_path_factory: pytest.TempPathFactory) -> Iterator[list[Resolution]]:
    yield trace_numbers.trace_all(tmp_path_factory.mktemp("trace"))


def _audit_minutes() -> dict[int, str]:
    text = (ROOT / "docs" / "transparency_audit.md").read_text(encoding="utf-8")
    section = text.split("## 8. The trace test: 16 real numbers", 1)[1].split("## 9.", 1)[0]
    found: dict[int, str] = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0].isdigit():
            found[int(cells[0])] = cells[5]
    return found


def test_the_rows_are_the_16_numbers_of_the_audit() -> None:
    assert [r.n for r in ROWS] == list(range(1, 17))
    audit = _audit_minutes()
    assert sorted(audit) == list(range(1, 17)), "the table of section 8 of the audit was not read"
    for r in ROWS:
        assert r.audit_minutes == audit[r.n], r.n
        assert r.objects or r.finding, r.n
        assert r.wants, r.n


@pytest.mark.slow
def test_every_number_resolves_completely(results: list[Resolution]) -> None:
    assert len(results) == 16
    for r in results:
        assert r.complete, (r.row.n, r.row.number, r.problems)
        assert r.resolved, r.row.n
        assert r.inputs or r.row.n in (16,), r.row.n  # a number that is pending has nothing to list
        for name, source, _kind in r.inputs:
            assert source.strip(), (r.row.n, name)


@pytest.mark.slow
def test_the_numbers_agree_with_the_exported_files(results: list[Resolution]) -> None:
    """Rows with a comparison against `export-data` found the same value there (a difference is a problem)."""
    compared = [r for r in results if r.row.cross]
    assert len(compared) >= 10
    assert all(r.complete for r in compared)


@pytest.mark.slow
@pytest.mark.perf
def test_every_number_is_traced_in_under_a_minute(results: list[Resolution]) -> None:
    for r in results:
        within(r.seconds, trace_numbers.LIMIT_SECONDS, f"number {r.row.n}: {r.row.number}")


@pytest.mark.slow
def test_the_committed_page_is_what_the_tool_writes(results: list[Resolution]) -> None:
    page = render_page(results)
    assert TARGET.read_text(encoding="utf-8") == page, "run: python -m tools.trace_numbers --update"
    assert "NOT COMPLETE" not in page
    assert page.count("< 60 s") == 16
    assert not re.search(r"\d+\.\d+ s\b", page), "the page holds a timing"
    assert not re.search(r"/(?:home|root|Users|var|tmp)/", page), "the page holds an absolute path"
    assert "C:\\" not in page


@pytest.mark.slow
def test_a_trace_that_loses_a_source_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The test can fail: an input without a source, or a key that is not a setting, is reported."""
    folders = trace_numbers.make_projects(tmp_path)
    row = ROWS[1]  # the voltage drop
    assert trace_numbers.resolve(row, Session(folders[row.project])).complete
    original = Session.explain

    def without_sources(self: Session, obj: str) -> list[api.Derivation]:
        return [
            dataclasses.replace(
                d, inputs=tuple(dataclasses.replace(i, source="") for i in d.inputs)
            )
            for d in original(self, obj)
        ]

    monkeypatch.setattr(Session, "explain", without_sources)
    lost = trace_numbers.resolve(row, Session(folders[row.project]))
    assert not lost.complete and any("has no source" in p for p in lost.problems)

    def invented_key(self: Session, obj: str) -> list[api.Derivation]:
        return [
            dataclasses.replace(
                d,
                inputs=tuple(
                    dataclasses.replace(i, source="config/derating.json: no_such_key")
                    for i in d.inputs
                ),
            )
            for d in original(self, obj)
        ]

    monkeypatch.setattr(Session, "explain", invented_key)
    wrong = trace_numbers.resolve(row, Session(folders[row.project]))
    assert any("is not a setting" in p for p in wrong.problems)

    monkeypatch.setattr(Session, "explain", original)
    unknown = dataclasses.replace(
        ROWS[2], wants=(dataclasses.replace(ROWS[2].wants[0], value=9.99),)
    )
    assert not trace_numbers.resolve(unknown, Session(folders[unknown.project])).complete


@pytest.mark.slow
def test_the_command_and_the_python_interface_give_the_same_derivation(tmp_path: Path) -> None:
    folders = trace_numbers.make_projects(tmp_path)
    folder = folders[trace_numbers.FLATSAT]
    printed = json.loads(command("explain", str(folder), "W001-001", "--json"))
    assert printed == [d.to_explain_dict() for d in api.explain(folder, "W001-001")]
    assert {d["id"] for d in printed} >= {"wire-length", "wire-current-limit", "wire-voltage-drop"}
