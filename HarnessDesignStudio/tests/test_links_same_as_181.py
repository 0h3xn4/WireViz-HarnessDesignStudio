# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,attr-defined,arg-type"
"""REQ-IO-02. Release 1.9 (W3) rewrote the pairing, the review and `plan_create_harness` to work in
one pass and to read the counterpart words from the project. With no pin direction set and the
table the tool ships with, every answer must be the one release 1.8.1 gave: `tests/reference/
links_181.py` is that code, verbatim, and these tests compare the two on generated projects (seeded,
so a failure names the seed) and on generated signal names."""

import dataclasses
import random

import pytest

from harness_design_studio.core import links, wires
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.edit import EditError, clone_with
from harness_design_studio.core.model import PinPair, Project, evolve
from tests.links_gen import VOCABULARY, generated_project
from tests.reference import links_181 as old

SEEDS = range(60)


def as_tuples(findings: list) -> list[tuple]:  # type: ignore[type-arg]
    return [dataclasses.astuple(f) for f in findings]


def outcome(fn, *args):  # type: ignore[no-untyped-def]
    """The result of a planner, or the sentence of the refusal."""
    try:
        return ("ok", fn(*args))
    except EditError as exc:
        return ("refused", str(exc))


def random_names(rng: random.Random, count: int) -> list[str]:
    """Names built the way vendors build them: a prefix, a word, a sign, a number."""
    parts = ("UART", "SPW", "SPI", "IF", "", "", "A", "B1", "TM", "TC")
    words = ("TX", "RX", "TXD", "RXD", "DOUT", "DIN", "MOSI", "MISO", "SDO", "SDI", "TXP", "RXN",
             "CLK", "PWR", "RTN", "DATA", "")  # fmt: skip
    signs = ("", "", "+", "-", "_P", "_N", "1", "2")
    out = []
    for _ in range(count):
        name = "_".join(x for x in (rng.choice(parts), rng.choice(words)) if x) + rng.choice(signs)
        out.append(name.lower() if rng.random() < 0.2 else name)
    return out


def test_name_relation_and_same_side_are_the_old_ones_on_generated_names() -> None:
    rng = random.Random(181)
    names = random_names(rng, 160) + list(VOCABULARY) + [None, "", " "]  # type: ignore[list-item]
    for x in names:
        for y in names:
            assert links.name_relation(x, y) == old.name_relation(x, y), (x, y)
            assert links.same_side(x, y) == old.same_side(x, y), (x, y)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_pairing_proposal_is_the_old_one(seed: int) -> None:
    p = generated_project(seed, links=0, devices=4)
    ids = sorted(p.connectors)
    for a in ids:
        for b in ids:
            if p.connectors[a].unit_id == p.connectors[b].unit_id:
                continue
            new, was = links.propose_pairs(p, a, b), old.propose_pairs(p, a, b)
            assert dataclasses.astuple(new) == dataclasses.astuple(was), (seed, a, b)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_proposal_beside_other_links_is_the_old_one(seed: int) -> None:
    p = generated_project(seed, links=5)  # some pins are taken by links already
    ids = sorted(p.connectors)
    for a in ids[:4]:
        for b in ids[-4:]:
            if p.connectors[a].unit_id == p.connectors[b].unit_id:
                continue
            new, was = links.propose_pairs(p, a, b), old.propose_pairs(p, a, b)
            assert dataclasses.astuple(new) == dataclasses.astuple(was), (seed, a, b)


def scrambled(seed: int) -> Project:
    """A generated project whose links are paired at random, pins used twice and pins that do not
    exist included, so the review has something to say about every code."""
    p = generated_project(seed, links=6)
    rng = random.Random(seed)
    for lid, link in sorted(p.links.items()):
        a, b = p.connectors[link.a_connector], p.connectors[link.b_connector]
        pins_a = [x.id for x in a.pins] + ["99"]
        pins_b = [x.id for x in b.pins] + ["98"]
        count = rng.randint(1, len(pins_a))
        pairs = [PinPair(a_pin=rng.choice(pins_a), b_pin=rng.choice(pins_b)) for _ in range(count)]
        p.links[lid] = evolve(link, pairs=pairs)
    return p


@pytest.mark.parametrize("seed", SEEDS)
def test_the_review_of_every_link_is_the_old_one(seed: int) -> None:
    for p in (generated_project(seed, links=6), scrambled(seed)):
        assert as_tuples(links.check_links(p)) == as_tuples(old.check_links(p))
        for link in p.links.values():
            assert as_tuples(links.check_link(p, link)) == as_tuples(old.check_link(p, link))


def test_the_review_has_something_to_say_in_every_code() -> None:
    seen = {f.code for s in SEEDS for f in links.check_links(scrambled(s))} | {
        f.code for s in SEEDS for f in links.check_links(generated_project(s, links=6))
    }
    assert seen >= {
        "link_dangling", "link_pin_reused", "link_direction_conflict", "link_signal_mismatch",
        "link_pin_unpaired", "link_power_without_return",
    }  # fmt: skip


@pytest.mark.parametrize("seed", SEEDS)
def test_pins_in_links_and_the_derived_interfaces_are_the_old_ones(seed: int) -> None:
    p = generated_project(seed, links=6)
    for cid in p.connectors:
        assert links.pins_in_links(p, cid) == old.pins_in_links(p, cid)
        for lid in list(p.links) + ["none"]:
            assert links.pins_in_links(p, cid, except_link=lid) == old.pins_in_links(
                p, cid, except_link=lid
            )
        assert [x.id for x in links.links_of_connector(p, cid)] == [
            x.id for x in old.links_of_connector(p, cid)
        ]
    assert [dataclasses.astuple(d) for d in links.derived_interfaces(p)] == [
        dataclasses.astuple(d) for d in old.derived_interfaces(p)
    ]


@pytest.mark.parametrize("seed", SEEDS)
def test_create_harness_makes_the_old_harness(seed: int) -> None:
    p = generated_project(seed, links=6)
    for lid in sorted(p.links):
        new = outcome(links.plan_create_harness, p, lid)
        was = outcome(old.plan_create_harness, p, lid)
        assert new == was, (seed, lid)
        if new[0] == "ok":  # the second harness of the project is named after the first
            q = clone_with(p, new[1][0])
            assert outcome(links.plan_create_harness, q, lid) == outcome(
                old.plan_create_harness, q, lid
            )
            for other in sorted(q.links):
                assert outcome(links.plan_create_harness, q, other) == outcome(
                    old.plan_create_harness, q, other
                ), (seed, lid, other)


def test_the_generated_projects_make_harnesses_and_refuse_some() -> None:
    """The comparison above is not empty: most links make a harness, some are refused."""
    results = [
        outcome(links.plan_create_harness, p, lid)[0]
        for p in (generated_project(s, links=6) for s in SEEDS)
        for lid in sorted(p.links)
    ]
    assert results.count("ok") >= 100 and results.count("refused") >= 1


@pytest.mark.parametrize("seed", SEEDS)
def test_adding_a_link_and_setting_pairs_are_the_old_ones(seed: int) -> None:
    p = generated_project(seed, links=3)
    ids = sorted(p.connectors)
    rng = random.Random(seed)
    for _ in range(12):
        a, b = rng.sample(ids, 2)
        assert outcome(links.plan_add_link, p, a, b) == outcome(old.plan_add_link, p, a, b)
    for lid in sorted(p.links):
        link = p.links[lid]
        pins_a = [x.id for x in p.connectors[link.a_connector].pins]
        pins_b = [x.id for x in p.connectors[link.b_connector].pins]
        rng.shuffle(pins_b)
        pairs = list(zip(pins_a, pins_b, strict=False))[: rng.randint(0, len(pins_a))]
        assert outcome(links.plan_set_pairs, p, lid, pairs) == outcome(
            old.plan_set_pairs, p, lid, pairs
        )


def test_adding_many_wires_at_once_is_adding_them_one_after_the_other() -> None:
    done = 0
    for seed, lid in [
        (s, i) for s in range(12) for i in sorted(generated_project(s, links=6).links)
    ]:
        p = generated_project(seed, links=6)
        res = outcome(old.plan_create_harness, p, lid)
        if res[0] != "ok":
            continue
        done += 1
        q = clone_with(p, res[1][0])
        hid = res[1][1]
        h = q.harnesses[hid]
        # the wires of the harness are taken off, then put back in one go and one by one
        bare = clone_with(q, [])
        bare.harnesses[hid] = h.model_copy(update={"wires": []})
        ends = [(w.from_connector, w.from_pin, w.to_connector, w.to_pin, w.signal) for w in h.wires]
        batch = wires.plan_add_wires(bare, hid, ends)
        step = clone_with(bare, [])
        for fc, fp, tc, tp, sig in ends:
            apply_ops(step, wires.plan_add_wire(step, hid, fc, fp, tc, tp, signal=sig))
        if ends:
            assert batch[0].obj == step.harnesses[hid]  # type: ignore[attr-defined]
            assert batch[0].obj.wires == h.wires  # type: ignore[attr-defined]
        else:
            assert batch == []
    assert done >= 20


def test_adding_wires_refuses_with_the_same_sentences() -> None:
    p = generated_project(3, links=6)
    lid = next(i for i in sorted(p.links) if outcome(old.plan_create_harness, p, i)[0] == "ok")
    ops, hid = old.plan_create_harness(p, lid)
    q = clone_with(p, ops)
    h = q.harnesses[hid]
    c1, c2 = h.connectors[0].id, h.connectors[1].id
    for ends in (
        [(c1, "1", c2, "no-such-pin", None)],
        [("nobody", "1", c2, "1", None)],
        [(c1, "1", c1, "1", None)],
    ):
        one = outcome(
            lambda e=ends: wires.plan_add_wire(q, hid, e[0][0], e[0][1], e[0][2], e[0][3])
        )
        many = outcome(wires.plan_add_wires, q, hid, ends)
        assert one[0] == many[0] == "refused" and one[1] == many[1], ends
    with pytest.raises(EditError):
        wires.plan_add_wires(q, "nope", [(c1, "1", c2, "1", None)])
