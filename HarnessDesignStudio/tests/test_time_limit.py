"""E-F1: the default time factor is 2, CI's explicit factor wins, and a slow run names its numbers."""

import pytest

from tests.helpers import time_factor, time_limit, within

# (they use the limit helpers, so they run with the other timing tests; no clock is read)
pytestmark = pytest.mark.perf


def test_the_default_factor_is_two(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARNESS_TIME_FACTOR", raising=False)
    assert time_factor() == 2.0
    assert time_limit(10) == 20.0


def test_an_explicit_factor_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_TIME_FACTOR", "3")
    assert time_factor() == 3.0
    assert time_limit(10) == 30.0


def test_a_slow_run_says_the_measured_value_the_limit_and_the_factor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HARNESS_TIME_FACTOR", "2")
    within(19.9, 10, "stress")  # under 20: passes
    with pytest.raises(AssertionError) as caught:
        within(21, 10, "stress")
    message = str(caught.value)
    assert "stress: measured 21, limit 20" in message and "HARNESS_TIME_FACTOR 2" in message
