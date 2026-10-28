# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,attr-defined,arg-type,call-arg,assignment,misc,type-arg"
"""REQ-IO-02, audit A-8. `History.execute` used to run the whole integrity check twice per edit. It
now asks an `IntegrityTracker`, which looks again only at what differs from the state it saw last.
The answer must be the one the whole check gives. `tests/reference/integrity_181.py` is the check as
release 1.8.1 had it (verbatim); these tests compare the tracker and the current `check_integrity`
with it on generated projects after random edits that are applied without any check (so the
projects are broken in all the ways an edit can break one), after undoing them, and after changes
made behind the tracker's back (as generation does). The generators are seeded: a failure names
the seed and the step."""

import contextlib
import dataclasses
import random
from collections import Counter

import pytest

from harness_design_studio.core import integrity, wires
from harness_design_studio.core.commands import Delete, History, Put, apply_ops
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.integrity import IntegrityTracker, check_integrity
from harness_design_studio.core.issues import errors
from harness_design_studio.core.links import plan_create_harness
from harness_design_studio.core.model import (
    Accessory,
    Endpoint,
    Harness,
    Part,
    PinPair,
    Project,
    Segment,
    ShieldGroup,
    Unit,
    evolve,
)
from harness_design_studio.core.samples import mini3, sat15
from tests.links_gen import generated_project
from tests.reference import integrity_181 as old
from tools.bench_stress import build

SEEDS = range(40)
STEPS = 30
BOGUS = ("NOPE-1", "GHOST", "x9")
COLLECTIONS = (
    "parts", "units", "interface_types", "interfaces", "links", "connectors", "harnesses",
    "placements", "baselines", "changelog",
)  # fmt: skip


def keys_of(issues) -> Counter:
    return Counter(i.key() for i in errors(issues))


def whole_check_old(p: Project) -> Counter:
    old._CACHE.clear()
    return keys_of(old.check_integrity(p))


def whole_check_new(p: Project) -> Counter:
    integrity._CACHE.clear()
    return keys_of(check_integrity(p))


def starting_project(seed: int) -> Project:
    """A project with devices, interfaces, links, generated and hand-made harnesses."""
    kind = seed % 4
    if kind == 0:
        p = sat15()
        generate_project(p)
    elif kind == 1:
        p = mini3()
        generate_project(p)
    elif kind == 2:
        p = generated_project(seed, devices=5, connectors_per_device=2, pins=6, links=4)
        for lid in sorted(p.links):
            with contextlib.suppress(EditError):  # a link that cannot make a harness
                ops, _hid = plan_create_harness(p, lid)
                apply_ops(p, ops)
    else:
        p = build(units=6, interfaces=12, harnesses=5, wires=60)
        p.links.update(generated_project(seed, devices=3, links=2).links)
    return with_references(p, random.Random(seed))


def with_references(p: Project, rng: random.Random) -> Project:
    """Give every harness an accessory, a shield group and a wire that name things which exist, so
    that deleting those things later breaks something."""
    parts, interfaces = sorted(p.parts), sorted(p.interfaces)
    for hid, h in list(p.harnesses.items()):
        if not h.wires:
            continue
        w = h.wires[0]
        wires_ = list(h.wires)
        if interfaces:
            wires_[-1] = evolve(wires_[-1], interface_id=rng.choice(interfaces))
        p.harnesses[hid] = evolve(
            h,
            wires=wires_,
            accessories=[
                *h.accessories,
                Accessory(id="ACC-1", kind="sleeving", part_id=rng.choice(parts), target=w.id),
            ],
            shields=[*h.shields, ShieldGroup(id="SG-1", kind="overall_shield", wire_ids=[w.id])],
            interfaces=[*h.interfaces, *(interfaces[:1] if interfaces else [])],
        )
    return p


def pick(rng: random.Random, items):
    items = sorted(items)
    return rng.choice(items) if items else None


def apply_if_possible(p: Project, ops):
    """The undo ops, or None when the model refuses (a key that is not there any more)."""
    try:
        return apply_ops(p, ops)
    except KeyError, TypeError:
        return None


def one_edit(p: Project, rng: random.Random):
    """`random_edit`, or nothing when the model would not even build the object."""
    try:
        return random_edit(p, rng)
    except ValueError:  # pydantic's ValidationError: this combination cannot be an object
        return None


def random_edit(p: Project, rng: random.Random):
    """A random change, as a list of ops (nothing checks it): it may well leave the project broken."""
    kind = rng.choice(
        ("delete", "delete", "connector", "connector", "harness", "harness", "wire", "wire",
         "part", "interface", "type", "link", "unit", "case", "baseline", "group", "dupwire")
    )  # fmt: skip
    if kind == "delete":
        coll = rng.choice(COLLECTIONS)
        key = pick(rng, getattr(p, coll))
        return [Delete(coll, key)] if key else None
    if kind == "connector":
        coll = rng.choice(("connectors", "connectors", "harness"))
        if coll == "connectors":
            cid = pick(rng, p.connectors)
            if cid is None:
                return None
            c = p.connectors[cid]
        else:
            hid = pick(rng, p.harnesses)
            if hid is None or not p.harnesses[hid].connectors:
                return None
            h = p.harnesses[hid]
            c = rng.choice(h.connectors)
        changes = rng.choice((
            {"mates_with": rng.choice([pick(rng, p.connectors), *BOGUS, None])},
            {"part_id": rng.choice([pick(rng, p.parts), *BOGUS])},
            {"unit_id": rng.choice([pick(rng, p.units), *BOGUS, None])},
            {"role": rng.choice(("box", "cable", "inline"))},
            {"carries": rng.choice([[], [pick(rng, p.interface_types)], list(BOGUS[:1])])},
            {"pins": c.pins[: max(0, len(c.pins) - 1)]},
            {"pins": [*c.pins, *c.pins[:1]]},
            {"pins": [evolve(x, interface_id=rng.choice([pick(rng, p.interfaces), BOGUS[0], None])) for x in c.pins[:2]] + c.pins[2:]},
            {"pins": [evolve(x, contact_part=rng.choice([pick(rng, p.parts), BOGUS[0], None])) for x in c.pins[:2]] + c.pins[2:]},
            {"name": f"n{rng.randrange(99)}"},
        ))  # fmt: skip
        if changes.get("mates_with") is None and "mates_with" in changes:
            changes = {"mates_with": None}
        new = evolve(c, **changes)
        if coll == "connectors":
            return [Put("connectors", new)]
        return [
            Put("harnesses", evolve(h, connectors=[new if x is c else x for x in h.connectors]))
        ]
    if kind in ("harness", "wire", "dupwire", "group"):
        hid = pick(rng, p.harnesses)
        if hid is None:
            return None
        h = p.harnesses[hid]
        if kind == "harness":
            changes = rng.choice((
                {"generated": not h.generated},
                {"interfaces": [*h.interfaces, rng.choice([pick(rng, p.interfaces), BOGUS[0]])]},
                {"connectors": [*h.connectors, *h.connectors[:1]]},
                {"connectors": h.connectors[1:]},
                {"segments": [*h.segments, Segment(id=f"S{rng.randrange(999)}", from_node=BOGUS[0], to_node=pick(rng, [c.id for c in h.connectors]) or BOGUS[1])]},
                {"accessories": [*h.accessories, Accessory(id=f"A{rng.randrange(9)}", kind="sleeving", part_id=rng.choice([pick(rng, p.parts), BOGUS[0]]), target=rng.choice([BOGUS[0], None]))]},
                {"name": f"renamed{rng.randrange(99)}"},
                {"wires": []},
            ))  # fmt: skip
            return [Put("harnesses", evolve(h, **changes))]
        if kind == "group":
            ids = [w.id for w in h.wires][:3] + [rng.choice(BOGUS)]
            return [Put("harnesses", evolve(h, shields=[*h.shields, ShieldGroup(id=f"G{rng.randrange(9)}", kind="overall_shield", wire_ids=ids)]))]  # fmt: skip
        if not h.wires:
            return None
        if kind == "dupwire":
            other = pick(rng, p.harnesses)
            src = p.harnesses[other].wires
            if not src:
                return None
            return [Put("harnesses", evolve(h, wires=[*h.wires, rng.choice(src)]))]
        w = rng.choice(h.wires)
        ends = [c.id for c in h.connectors] + list(p.connectors) + list(BOGUS)
        changes = rng.choice((
            {"from_connector": rng.choice(ends)},
            {"to_connector": rng.choice(ends)},
            {"from_pin": rng.choice(("1", "2", "99"))},
            {"to_pin": rng.choice(("1", "2", "99"))},
            {"part_id": rng.choice([pick(rng, p.parts), BOGUS[0], None])},
            {"interface_id": rng.choice([pick(rng, p.interfaces), BOGUS[0], None])},
            {"note": f"x{rng.randrange(99)}"},
            {"to_connector": w.from_connector, "to_pin": w.from_pin},
        ))  # fmt: skip
        return [Put("harnesses", evolve(h, wires=[evolve(w, **changes) if x is w else x for x in h.wires]))]  # fmt: skip
    if kind == "part":
        pid = pick(rng, p.parts)
        if pid is None:
            return None
        if rng.random() < 0.4:
            return [Delete("parts", pid)]
        part = p.parts[pid]
        changes = rng.choice((
            {"category": rng.choice(("connector", "contact", "wire", "sleeving"))},
            {"pin_count": rng.choice((1, 2, 40, None))},
            {"mates_with": rng.choice([pick(rng, p.parts), pid, BOGUS[0], None])},
            {"description": f"d{rng.randrange(99)}"},
        ))  # fmt: skip
        return [Put("parts", evolve(part, **changes))]
    if kind == "interface":
        iid = pick(rng, p.interfaces)
        if iid is None:
            return None
        i = p.interfaces[iid]
        eps = list(i.endpoints)
        changes = rng.choice((
            {"type_id": rng.choice([pick(rng, p.interface_types), BOGUS[0]])},
            {"endpoints": eps[:1]},
            {"endpoints": [*eps[:1], Endpoint(unit_id=BOGUS[0])]},
            {"endpoints": [Endpoint(unit_id=e.unit_id, connector_id=rng.choice([pick(rng, p.connectors), BOGUS[0], None])) for e in eps]},
            {"name": f"i{rng.randrange(99)}"},
        ))  # fmt: skip
        return [Put("interfaces", evolve(i, **changes))]
    if kind == "type":
        tid = pick(rng, p.interface_types)
        if tid is None:
            return None
        t = p.interface_types[tid]
        sigs = list(t.signals)
        changes = rng.choice(({"signals": [*sigs, *sigs[:1]]}, {"signals": sigs[:-1] or sigs}, {"name": f"t{rng.randrange(99)}"}))  # fmt: skip
        return [Put("interface_types", evolve(t, **changes))]
    if kind == "link":
        lid = pick(rng, p.links)
        if lid is None:
            return None
        link = p.links[lid]
        pairs = list(link.pairs)
        changes = rng.choice((
            {"a_connector": rng.choice([pick(rng, p.connectors), BOGUS[0]])},
            {"b_connector": rng.choice([pick(rng, p.connectors), link.a_connector])},
            {"pairs": [*pairs, *pairs[:1]]},
            {"pairs": [*pairs, PinPair(a_pin="99", b_pin="98")]},
            {"harness_id": rng.choice([pick(rng, p.harnesses) or "", BOGUS[0], ""])},
            {"note": f"n{rng.randrange(99)}"},
        ))  # fmt: skip
        return [Put("links", evolve(link, **changes))]
    if kind == "unit":
        uid = pick(rng, p.units)
        if uid is None:
            return None
        return [Put("units", evolve(p.units[uid], name=f"u{rng.randrange(99)}"))]
    if kind == "case":
        coll = rng.choice(("units", "parts", "harnesses", "interfaces"))
        key = pick(rng, getattr(p, coll))
        if key is None:
            return None
        obj = getattr(p, coll)[key]
        return [Put(coll, evolve(obj, id=key.swapcase() if key.swapcase() != key else key + "x"))]
    if kind == "baseline":
        bid = pick(rng, p.baselines)
        if bid is None:
            return None
        return [Put("baselines", evolve(p.baselines[bid], harness_id=rng.choice([BOGUS[0], pick(rng, p.harnesses) or BOGUS[1]])))]  # fmt: skip
    return None


@pytest.mark.parametrize("seed", SEEDS)
def test_tracker_gives_the_errors_of_the_whole_check(seed: int) -> None:
    rng = random.Random(seed)
    p = starting_project(seed)
    tracker = IntegrityTracker(p)
    assert tracker.errors() == whole_check_old(p) == whole_check_new(p), (seed, "start")
    undo: list = []
    for step in range(STEPS):
        what = rng.random()
        if what < 0.2 and undo:  # undo a few of the edits, newest first
            for _ in range(rng.randrange(1, 4)):
                if undo:
                    apply_ops(p, undo.pop())
        else:
            ops = one_edit(p, rng)
            if not ops:
                continue
            backward = apply_if_possible(p, ops)
            if backward is None:
                continue
            undo.append(backward)
        if rng.random() < 0.7:  # now and then several edits pass between two looks
            expected = whole_check_old(p)
            assert tracker.errors() == expected, (seed, step, "tracker")
            assert whole_check_new(p) == expected, (seed, step, "check_integrity")


@pytest.mark.parametrize("seed", range(6))
def test_tracker_follows_changes_made_behind_its_back(seed: int) -> None:
    """Generation, a restore or a test replaces whole collections without telling anyone."""
    rng = random.Random(seed)
    p = starting_project(seed)
    tracker = IntegrityTracker(p)
    tracker.errors()
    for step in range(6):
        choice = rng.randrange(3)
        if choice == 0:
            p.harnesses = dict(list(p.harnesses.items())[: rng.randrange(0, len(p.harnesses) + 1)])
        elif choice == 1:
            q = starting_project(seed + 100 + step)
            for name in rng.sample(COLLECTIONS, 3):
                setattr(p, name, dict(getattr(q, name)))
        else:
            for _ in range(5):
                ops = one_edit(p, rng)
                if ops:
                    apply_if_possible(p, ops)
        assert tracker.errors() == whole_check_old(p), (seed, step)


def test_the_whole_check_still_reports_every_issue_of_release_181() -> None:
    """The refactoring of `check_integrity` (shared pieces, a harness check that no longer copies
    every device connector) changed no finding, no wording and no order."""
    for seed in range(30):
        rng = random.Random(seed)
        p = starting_project(seed)
        for _ in range(12):
            ops = one_edit(p, rng)
            if ops:
                apply_if_possible(p, ops)
        old._CACHE.clear()
        integrity._CACHE.clear()
        assert [dataclasses.astuple(i) for i in check_integrity(p)] == [
            dataclasses.astuple(i) for i in old.check_integrity(p)
        ], seed


def test_the_checks_the_tracker_leaves_out_can_only_warn() -> None:
    """`_check_mating` and the placement check are not run by the tracker: they must never be
    able to report an error (if one ever does, the tracker has to run it)."""
    for seed in range(40):
        rng = random.Random(seed)
        p = starting_project(seed)
        for _ in range(15):
            ops = one_edit(p, rng)
            if ops:
                apply_if_possible(p, ops)
            for issue in [*integrity._check_mating(p), *integrity._placement_issues(p)]:
                assert issue.severity != "error", issue


def test_an_edit_checks_only_what_it_touched() -> None:
    p = build(units=20, interfaces=40, harnesses=15, wires=300)
    h = History(p)
    tracker = h._tracker()
    tracker.errors()
    everything = tracker.checked
    assert everything >= len(p.harnesses) + len(p.connectors)
    h.execute("rename", [Put("units", evolve(p.units["U001"], name="renamed"))])
    assert tracker.checked == 0  # nothing reads a device name
    wid = p.harnesses["H003"].wires[0].id
    h.execute("note", wires.plan_wire_edit(p, [wid], {"note": "a note"}))
    assert tracker.checked == 1  # the one harness
    cid = "U002-J01"
    h.execute("connector", [Put("connectors", evolve(p.connectors[cid], name="J9"))])
    # the harnesses that wire to U002-J01 read it; the others do not
    users = {x.id for x in p.harnesses.values() if any(cid in (w.from_connector, w.to_connector) for w in x.wires)}  # fmt: skip
    assert tracker.checked == 1 + len(users)
    assert len(users) < len(p.harnesses)


def test_a_refused_edit_names_the_problem_and_changes_nothing() -> None:
    p = build(units=6, interfaces=12, harnesses=4, wires=40)
    h = History(p)
    hid = next(iter(p.harnesses))
    wire = p.harnesses[hid].wires[0]
    bad = evolve(wire, to_connector="NOPE-1")
    before = dict(p.harnesses)
    with pytest.raises(TransactionError) as caught:
        h.execute("break a wire", [Put("harnesses", evolve(p.harnesses[hid], wires=[bad, *p.harnesses[hid].wires[1:]]))])  # fmt: skip
    assert any("NOPE-1" in m for m in caught.value.problems)
    assert p.harnesses == before
    # the edit is refused every time, and a good one still passes
    with pytest.raises(TransactionError):
        h.execute("break a wire", [Put("harnesses", evolve(p.harnesses[hid], wires=[bad, *p.harnesses[hid].wires[1:]]))])  # fmt: skip
    h.execute("rename", [Put("harnesses", evolve(p.harnesses[hid], name="fine"))])
    assert p.harnesses[hid].name == "fine"


def test_a_second_error_of_the_same_kind_is_new() -> None:
    """The old rule: an error that was there before may stay, one more of the same code and
    object does not pass."""
    p = build(units=4, interfaces=6, harnesses=2, wires=20)
    hid = next(iter(p.harnesses))
    h0 = p.harnesses[hid]
    w0, w1 = h0.wires[0], h0.wires[1]
    p.harnesses[hid] = evolve(h0, wires=[evolve(w0, to_connector="NOPE-1"), *h0.wires[1:]])
    history = History(p)
    h1 = p.harnesses[hid]
    with pytest.raises(TransactionError):
        history.execute("one more", [Put("harnesses", evolve(h1, wires=[h1.wires[0], evolve(w1, to_connector="NOPE-1"), *h1.wires[2:]]))])  # fmt: skip
    # a different, unrelated edit passes although the project already has an error
    history.execute("rename", [Put("units", evolve(p.units["U001"], name="ok"))])


def test_the_tracker_starts_again_for_another_project() -> None:
    a, b = mini3(), sat15()
    history = History(a)
    history.execute("rename", [Put("units", evolve(next(iter(a.units.values())), name="x"))])
    history.project = b
    unit = Unit(id="ZZ1", name="Z", subsystem="s")
    history.execute("add", [Put("units", unit)])
    assert history._tracker().project is b


def test_a_harness_called_project_decides_how_a_device_connector_is_judged() -> None:
    """`_check_connector` asks for the harness named like its owner; for a device connector the
    owner is the word "project", so a harness with that ID changes the answer (an unknown mate is
    a warning in a generated harness). The tracker must see it."""
    p = mini3()
    cid = next(iter(p.connectors))
    p.connectors[cid] = evolve(p.connectors[cid], mates_with="NOPE-1")
    tracker = IntegrityTracker(p)
    assert tracker.errors() == whole_check_old(p)
    h = Harness(id="project", name="Odd one", generated=False)
    p.harnesses["project"] = h
    assert tracker.errors() == whole_check_old(p)
    p.harnesses["project"] = evolve(h, generated=True)
    assert tracker.errors() == whole_check_old(p)
    del p.harnesses["project"]
    assert tracker.errors() == whole_check_old(p)


def hand_made() -> Project:
    """The generated harnesses of mini3, handed over to a person (so an orphan is an error). The
    largest harness lists an interface, a wire names another, a wire names a part and an accessory
    names one more, and each of the four is used by nothing else, so deleting it can only be seen
    by the check that reads it."""
    p = mini3()
    generate_project(p)
    template = next(iter(p.interfaces.values()))
    for iid in ("IFA", "IFB"):
        p.interfaces[iid] = evolve(template, id=iid)
    p.parts["PW"] = Part(id="PW", category="wire")
    p.parts["PACC"] = Part(id="PACC", category="sleeving")
    big = max(p.harnesses.values(), key=lambda x: len(x.wires))
    wires_ = list(big.wires)
    wires_[0] = evolve(wires_[0], interface_id="IFB", part_id="PW")
    box = p.connectors["OBC-J02"]
    wires_[1] = evolve(wires_[1], from_connector=box.id, from_pin=box.pins[-1].id)
    p.harnesses[big.id] = evolve(
        big,
        wires=wires_,
        interfaces=[*big.interfaces, "IFA"],
        accessories=[Accessory(id="ACC-1", kind="sleeving", part_id="PACC", target=wires_[0].id)],
    )
    p.parts["PCON"] = Part(id="PCON", category="contact")
    big = p.harnesses[big.id]
    first = big.connectors[0]
    pins = [evolve(first.pins[0], contact_part="PCON"), *first.pins[1:]]
    p.harnesses[big.id] = evolve(big, connectors=[evolve(first, pins=pins), *big.connectors[1:]])
    for hid, h in list(p.harnesses.items()):
        p.harnesses[hid] = evolve(h, generated=False)
    return p


SCENARIOS = {
    "interface listed by a harness": lambda p, h: [Delete("interfaces", "IFA")],
    "interface of a wire": lambda p, h: [Delete("interfaces", "IFB")],
    "part of an accessory": lambda p, h: [Delete("parts", "PACC")],
    "part of a wire": lambda p, h: [Delete("parts", "PW")],
    "category of the part of a wire": lambda p, h: [
        Put("parts", evolve(p.parts["PW"], category="contact"))
    ],  # fmt: skip
    "contact part of a pin": lambda p, h: [Delete("parts", "PCON")],
    "part of a harness connector": lambda p, h: [Delete("parts", h.connectors[0].part_id)],
    "category of a connector's part": lambda p, h: [
        Put("parts", evolve(p.parts[h.connectors[0].part_id], category="wire"))
    ],  # fmt: skip
    "pins of a part": lambda p, h: [
        Put("parts", evolve(p.parts[h.connectors[0].part_id], pin_count=1))
    ],  # fmt: skip
    "device connector at the end of a wire": lambda p, h: [Delete("connectors", "OBC-J02")],
    "pins of a device connector at the end of a wire": lambda p, h: [
        Put("connectors", evolve(p.connectors["OBC-J02"], pins=p.connectors["OBC-J02"].pins[:-1]))
    ],  # fmt: skip
    "device of a device connector": lambda p, h: [
        Delete("units", next(c.unit_id for c in p.connectors.values() if c.unit_id))
    ],  # fmt: skip
    "connector a cable connector mates with": lambda p, h: [
        Delete("connectors", next(c.mates_with for c in h.connectors if c.mates_with))
    ],  # fmt: skip
    "a wire ID used in two harnesses": lambda p, h: [
        Put(
            "harnesses",
            evolve(
                next(x for x in p.harnesses.values() if x.id != h.id),
                wires=[*next(x for x in p.harnesses.values() if x.id != h.id).wires, h.wires[0]],
            ),
        )
    ],  # fmt: skip
}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_every_thing_a_check_reads_makes_it_run_again(name: str) -> None:
    p = hand_made()
    h = max(p.harnesses.values(), key=lambda x: len(x.wires))
    tracker = IntegrityTracker(p)
    assert tracker.errors() == whole_check_old(p)
    ops = SCENARIOS[name](p, h)
    apply_ops(p, ops)
    expected = whole_check_old(p)
    assert expected != Counter(), "the scenario must break something, or it proves nothing"
    assert tracker.errors() == expected
    assert whole_check_new(p) == expected
