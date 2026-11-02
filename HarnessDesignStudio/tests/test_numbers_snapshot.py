"""The numbers the tool gives are kept on purpose (D-191, step 0 of the transparency work): the gauge,
length, part, colour and lock of every wire, every finding with its text, and the SHA-256 of every
written file, for the packaged examples and for the situations an engineer meets them in (a hand
override, the ECSS profile, a lower ampacity, a bundle table of one's own, the three ways to group
interfaces into harnesses). A change that moves one of them on purpose renews
`tests/fixtures/numbers/snapshot.json` with a reviewed reason in `docs/changes.md`."""

import json

from tools.numbers_snapshot import SCENARIOS, STORED, differences, snapshots


def test_every_number_and_written_file_is_as_the_snapshot_holds_it() -> None:
    then = json.loads(STORED.read_text(encoding="utf-8"))
    assert differences(snapshots(), then) == []


def test_the_snapshot_is_not_an_empty_promise() -> None:
    then = json.loads(STORED.read_text(encoding="utf-8"))
    assert set(then) == set(SCENARIOS)
    assert sum(len(v["wires"]) for v in then.values()) > 500
    assert sum(len(v["files"]) for v in then.values()) > 1000
    override = then["flatsat-override"]["wires"]
    assert sum(1 for w in override if w[7]) == 2  # the two hand-edited wires are locked and kept
    tight = then["flatsat-tight"]["findings"]
    assert any(
        f[1] == "error" and "allows" in f[2] for f in tight
    )  # a current finding with numbers


def test_a_moved_number_is_named_by_what_a_reader_can_act_on() -> None:
    then = json.loads(STORED.read_text(encoding="utf-8"))
    now = json.loads(STORED.read_text(encoding="utf-8"))
    wire = now["flatsat"]["wires"][0]
    wire[3] = (wire[3] or 0) + 2  # a gauge changed
    now["flatsat"]["findings"].append(["x.y", "error", "a new finding"])
    first_file = sorted(now["flatsat"]["files"])[0]
    now["flatsat"]["files"][first_file] = "0" * 64
    found = differences(now, then)
    assert any(line.startswith(f"flatsat: wire {wire[1]}:") for line in found)
    assert any("finding x.y" in line for line in found)
    assert f"flatsat: file {first_file} changed" in found
