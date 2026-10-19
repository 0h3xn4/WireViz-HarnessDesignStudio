# mypy: disable-error-code="no-untyped-def"
"""The optional timing log (HARNESS_UI_TIMING=1) writes one line per timed step, and only then."""

import pytest

from harness_design_studio.gui import timing


def test_nothing_is_written_unless_the_variable_is_set(monkeypatch, capsys) -> None:
    monkeypatch.delenv("HARNESS_UI_TIMING", raising=False)
    with timing.timed("quiet step"):
        pass
    assert capsys.readouterr().err == ""


def test_a_timed_step_writes_its_label_and_flags_slow_ones(monkeypatch, capsys) -> None:
    monkeypatch.setenv("HARNESS_UI_TIMING", "1")
    with timing.timed("fast step"):
        pass
    monkeypatch.setattr(timing, "SLOW_MS", -1)
    with timing.timed("slow step"):
        pass
    lines = capsys.readouterr().err.splitlines()
    assert lines[0].startswith("[ui-timing] fast step ") and lines[0].endswith(" ms")
    assert lines[1].startswith("[ui-timing] slow step ") and lines[1].endswith("SLOW")


def test_the_step_is_still_timed_when_it_raises(monkeypatch, capsys) -> None:
    monkeypatch.setenv("HARNESS_UI_TIMING", "1")
    with pytest.raises(ValueError), timing.timed("failing step"):
        raise ValueError("x")
    assert "failing step" in capsys.readouterr().err
