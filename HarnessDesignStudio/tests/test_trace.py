"""REQ-TRACE-01: Requirement traceability (ECSS-E-ST-40C 5.8.3; ECSS-Q-ST-80C 6.2.6.12)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tools import trace

ROOT = Path(__file__).resolve().parent.parent


def test_every_requirement_is_traced_to_something() -> None:
    rows = trace.build()
    assert len(rows) >= 50
    bad = [r[0] for r in rows if r[5] not in ("traced", "verified-by-file-only", "review-only")]
    assert not bad, bad


def test_traceability_file_is_current() -> None:
    with (ROOT / "compliance" / "traceability.csv").open(newline="", encoding="utf-8") as f:
        assert list(csv.reader(f)) == [trace.HEADER, *trace.build()]


def test_a_file_that_names_a_requirement_contains_tests() -> None:
    """`traced` means a test file mentions the ID (tools/trace.py); at least make sure that such a
    file defines test functions, so a mention in a helper module or a leftover cannot count.
    Whether the mentioning test really checks the requirement stays a review question."""
    import ast

    empty = []
    for rid, files in trace.tests_naming().items():
        for name in files:
            tree = ast.parse((ROOT / "tests" / name).read_text(encoding="utf-8"))
            if not any(
                isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name.startswith("test_")
                for n in ast.walk(tree)
            ):
                empty.append(f"{rid} in {name}")
    assert not empty, empty


def test_a_missing_standard_pdf_is_found_before_any_list_is_rewritten(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tools import extract_requirements as er

    folder = tmp_path / "pdfs"
    folder.mkdir()
    (folder / next(iter(er.STANDARDS.values()))).write_bytes(b"%PDF-1.4")  # only the first one

    def not_called(*_a: object, **_k: object) -> None:
        raise AssertionError("a standard was processed although another PDF is missing")

    monkeypatch.setattr(er, "to_text", not_called)
    monkeypatch.setattr(er, "write", not_called)
    assert er.main(str(folder)) == 2
    assert capsys.readouterr().err.count("missing:") == len(er.STANDARDS) - 1
