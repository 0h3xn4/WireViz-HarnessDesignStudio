# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,attr-defined,arg-type"
"""REQ-IO-02. Release 1.9 (W3): the planners of `core/links.py` work in one pass. Release 1.8.1 made
a harness from a link of 1,000 pairs in 31.7 s (quadratic: each wire read every ID of the project
and rebuilt the harness) and looked up every link again for each connector.

Two kinds of test. The call counts are exact and need no clock: the number of times the project is
scanned does not grow with the number of pairs. The timings (marked `perf`, so they run alone) say
how the time grows, not how long it takes: ten times the work may cost about ten times the time,
never a hundred times, so the limit is a ratio, plus one generous absolute limit scaled by
HARNESS_TIME_FACTOR (tests/helpers.py)."""

import time
from collections.abc import Callable

import pytest

from harness_design_studio.core import links, wires
from harness_design_studio.core.model import Connector, Pin
from tests.helpers import within
from tests.links_gen import big_link_project


def count_calls(monkeypatch: pytest.MonkeyPatch, module: object, name: str) -> list[int]:
    """Count the calls of `module.name` (the original still runs)."""
    calls = [0]
    original = getattr(module, name)

    def counted(*args: object, **kwargs: object) -> object:
        calls[0] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, counted)
    return calls


@pytest.mark.parametrize("pairs", [5, 60, 300])
def test_making_a_harness_scans_the_project_the_same_number_of_times_for_any_number_of_pairs(
    monkeypatch: pytest.MonkeyPatch, pairs: int
) -> None:
    p = big_link_project(pairs)
    ids = count_calls(monkeypatch, wires, "used_ids")
    index = count_calls(monkeypatch, links, "link_pin_index")
    from harness_design_studio.core.generate import naming

    namer = count_calls(monkeypatch, naming, "namer_for")
    ops, _hid = links.plan_create_harness(p, "L1")
    assert len(ops[0].obj.wires) == pairs  # type: ignore[attr-defined]
    # the wires are added by one call: the IDs of the project and the naming pattern are read once
    # for all of them (1.8.1 read both once per wire), and the links are indexed once
    assert (ids[0], index[0], namer[0]) == (1, 1, 1)


def test_a_review_of_all_links_reads_the_links_once(monkeypatch: pytest.MonkeyPatch) -> None:
    p = big_link_project(4, links=30)
    index = count_calls(monkeypatch, links, "link_pin_index")
    links.check_links(p)
    assert index[0] == 1  # 1.8.1 read all links twice for each link


def best_of(runs: int, work: Callable[[], object]) -> float:
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        work()
        best = min(best, time.perf_counter() - start)
    return best


def grows_like_the_work(small: float, big: float, factor: int, what: str) -> None:
    """Time grew by less than `factor` squared (a quadratic cost would be ~factor^2 x); the
    allowance is generous (a linear cost is about `factor` x) so a noisy machine does not fail it."""
    ratio = big / max(small, 1e-4)
    assert ratio < factor * factor * 0.6, f"{what}: x{factor} the work took x{ratio:.1f} the time"


@pytest.mark.perf
def test_making_a_harness_grows_with_the_pairs_not_with_their_square() -> None:
    small_p, big_p = big_link_project(200), big_link_project(1000)
    small = best_of(3, lambda: links.plan_create_harness(small_p, "L1"))
    big = best_of(3, lambda: links.plan_create_harness(big_p, "L1"))
    grows_like_the_work(small, big, 5, "plan_create_harness")
    within(big, 5.0, "a harness from a link of 1,000 pairs, s (1.8.1: 31.7 s)")


@pytest.mark.perf
def test_the_proposal_for_two_connectors_with_nothing_in_common_grows_linearly() -> None:
    def project(pins: int):  # type: ignore[no-untyped-def]
        p = big_link_project(pins)
        p.links.clear()
        for cid, prefix in (("A-J01", "OUT"), ("B-J01", "IN")):
            c: Connector = p.connectors[cid]
            p.connectors[cid] = c.model_copy(
                update={"pins": [Pin(id=str(k + 1), signal=f"{prefix}{k}") for k in range(pins)]}
            )
        return p

    small_p, big_p = project(200), project(1000)
    small = best_of(3, lambda: links.propose_pairs(small_p, "A-J01", "B-J01"))
    big = best_of(3, lambda: links.propose_pairs(big_p, "A-J01", "B-J01"))
    grows_like_the_work(small, big, 5, "propose_pairs")
    within(big, 2.0, "the proposal for 1,000 pins against 1,000 pins, s")


@pytest.mark.perf
def test_the_review_of_all_links_grows_with_the_links_not_with_their_square() -> None:
    small_p, big_p = big_link_project(8, links=60), big_link_project(8, links=300)
    small = best_of(3, lambda: links.check_links(small_p))
    big = best_of(3, lambda: links.check_links(big_p))
    grows_like_the_work(small, big, 5, "check_links")
    within(big, 2.0, "the review of 300 links, s")
