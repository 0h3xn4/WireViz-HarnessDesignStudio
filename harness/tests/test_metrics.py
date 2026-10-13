"""REQ-MET-01: Metrics tool (ECSS-Q-ST-80C 7.1.5)."""

from __future__ import annotations

import ast

import pytest

from tools import metrics


def test_complexity_counts_decisions() -> None:
    fn = ast.parse(
        "def f(a, b):\n    if a and b:\n        return 1\n    for x in a:\n        pass\n"
    ).body[0]
    assert metrics.complexity(fn) == 4  # 1 + if + and + for


def test_source_lines_skips_blanks_and_comments() -> None:
    assert metrics.source_lines("# c\n\nx = 1\n  # d\ny = 2\n") == 2


def test_collect_has_every_area_and_is_deterministic() -> None:
    a = metrics.collect()
    assert set(a) == set(metrics.AREAS)
    assert metrics.collect() == a
    core = a["core"]
    assert isinstance(core, dict) and core["source_lines"] > 1000


def test_a_coverage_option_without_a_file_is_a_usage_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert metrics.main(["--coverage"]) == 2
    captured = capsys.readouterr()
    assert "usage:" in captured.err and "Traceback" not in captured.err
