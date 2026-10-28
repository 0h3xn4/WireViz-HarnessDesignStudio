# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,arg-type,misc"
"""REQ-JOURNAL-01, audit A-9. The autosave journal used to serialise the whole project on the GUI
thread after every pause (0.3 s at 200 devices, 0.6 s the first time). Now `serialize` rebuilds only
the files whose objects changed, `journal_bytes` encodes only those, and the editor writes the
journal in a worker thread. What a crash leaves behind must still be exactly the project: the
journal text is the one `canonical.dumps` made before, and reading it gives the same project."""

import random
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from harness_design_studio.core import recovery, wires  # noqa: E402
from harness_design_studio.core.commands import History, Put, apply_ops  # noqa: E402
from harness_design_studio.core.io import layout  # noqa: E402
from harness_design_studio.core.io.canonical import dumps  # noqa: E402
from harness_design_studio.core.io.layout import (  # noqa: E402
    forget_serialized_files,
    model_hash,
    serialize,
)
from harness_design_studio.core.io.saver import save_project  # noqa: E402
from harness_design_studio.core.model import QuarantinedItem, evolve  # noqa: E402
from harness_design_studio.core.recovery import (  # noqa: E402
    journal_bytes,
    journal_path,
    read_journal,
    write_journal,
)
from harness_design_studio.core.samples import mini3, sat15  # noqa: E402
from harness_design_studio.gui import controller as controller_module  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from tests.helpers import within  # noqa: E402
from tests.test_integrity_tracker import apply_if_possible, one_edit, starting_project  # noqa: E402
from tools.bench_stress import build  # noqa: E402


def old_journal_text(project, fingerprint) -> bytes:
    """The text `write_journal` made before the files were remembered: the payload through
    `canonical.dumps`, every file encoded again."""
    return dumps(
        {
            "base_fingerprint": fingerprint,
            "files": {rel: data.decode("utf-8") for rel, data in serialize(project).items()},
            "quarantine": [
                {"file": q.file, "kind": q.kind, "reason": q.reason, "raw": q.raw}
                for q in project.quarantine
            ],
            "quarantine_files": {},
        }
    )


@pytest.mark.parametrize("seed", range(12))
def test_serialising_again_after_edits_gives_the_bytes_of_a_fresh_pass(seed: int) -> None:
    rng = random.Random(seed)
    p = starting_project(seed)
    serialize(p)  # the files are remembered
    for step in range(15):
        ops = one_edit(p, rng)
        if ops and apply_if_possible(p, ops) is None:
            continue
        again = serialize(p)  # rebuilds only what changed
        hash_again = model_hash(p)
        forget_serialized_files()
        fresh = serialize(p)
        assert again == fresh, (seed, step)
        assert hash_again == model_hash(p), (seed, step)
        serialize(p)  # remember the state again for the next step


@pytest.mark.parametrize("seed", range(6))
def test_the_journal_text_is_what_canonical_dumps_made(seed: int) -> None:
    rng = random.Random(seed)
    p = starting_project(seed)
    p.quarantine.append(
        QuarantinedItem("logical/x.json", "unit", "not a unit", {"id": "?", "n": 1})
    )
    for step in range(8):
        ops = one_edit(p, rng)
        if ops and apply_if_possible(p, ops) is None:
            continue
        fingerprint = None if step % 2 else f"fp{step}"
        assert journal_bytes(p, base_fingerprint=fingerprint) == old_journal_text(p, fingerprint), (
            seed,
            step,
        )


def test_the_journal_restores_exactly_the_project(tmp_path: Path) -> None:
    root = tmp_path / "p"
    p = sat15()
    save_project(p, root)
    history = History(p)
    rng = random.Random(7)
    for step in range(6):  # edits that pass the integrity check, one journal after each
        unit = rng.choice(sorted(p.units))
        history.execute("rename", [Put("units", evolve(p.units[unit], name=f"renamed {step}"))])
        if step == 3:
            history.undo()
        write_journal(p, root, base_fingerprint="fp")
        restored = read_journal(root)
        assert restored is not None and not restored.has_errors
        assert serialize(restored.project) == serialize(p), step
        assert model_hash(restored.project) == model_hash(p), step


def test_an_edit_rebuilds_only_the_files_that_hold_it(monkeypatch) -> None:
    p = build(units=40, interfaces=80, harnesses=30, wires=600)
    serialize(p)
    built: list[str] = []
    real = layout.canonical.dumps

    def counting(data):
        built.append("file")
        return real(data)

    monkeypatch.setattr(layout.canonical, "dumps", counting)
    forget_serialized_files()
    serialize(p)
    cold = len(built)
    assert cold > 60  # every harness, every group, the library
    for label, ops in (
        ("a device", [Put("units", evolve(p.units["U001"], name="renamed"))]),
        ("a wire", wires.plan_wire_edit(p, [p.harnesses["H003"].wires[0].id], {"note": "x"})),
    ):
        apply_ops(p, ops)
        built.clear()
        serialize(p)
        # project.json and the settings are written again every time (a handful of small files);
        # the edit itself costs the one file that holds the object
        assert len(built) <= cold // 3, (label, len(built), cold)
        assert len(built) < 15, (label, len(built))
    built.clear()
    serialize(p)
    assert len(built) < 12  # nothing changed: only the small files that are not remembered


def test_fragments_of_unchanged_files_are_not_encoded_again(monkeypatch) -> None:
    p = build(units=20, interfaces=40, harnesses=10, wires=200)
    journal_bytes(p)
    encoded: list[int] = []
    real = recovery.json.dumps

    def counting(obj, *args, **kwargs):
        if isinstance(obj, str):
            encoded.append(len(obj))
        return real(obj, *args, **kwargs)

    monkeypatch.setattr(recovery.json, "dumps", counting)
    apply_ops(p, [Put("units", evolve(p.units["U001"], name="renamed"))])
    journal_bytes(p)
    big = [n for n in encoded if n > 20000]
    assert not big, "a file that did not change was encoded again"


# ---- the editor writes it in a worker thread ---------------------------------------------------


@pytest.fixture
def ctl(qapp, tmp_path: Path) -> Iterator[EditorController]:
    c = EditorController(journal_delay_ms=10_000, drc_delay_ms=600_000)
    root = tmp_path / "proj"
    save_project(mini3(), root)
    from harness_design_studio.core.io.loader import load_project

    c._install(load_project(root).project, root, None)
    yield c
    c.release()


def edit_unit(c: EditorController, name: str) -> None:
    unit = next(iter(c.project.units))
    assert c.update_unit(unit, name=name)


def test_the_timer_writes_the_journal_off_the_gui_thread(ctl, monkeypatch) -> None:
    threads: list[threading.Thread] = []
    real = controller_module.journal_bytes

    def spy(project, **kwargs):
        threads.append(threading.current_thread())
        return real(project, **kwargs)

    monkeypatch.setattr(controller_module, "journal_bytes", spy)
    edit_unit(ctl, "first")
    ctl._timer.timeout.emit()  # what the timer does after the pause
    assert ctl.wait_journal()
    assert threads and all(t is not threading.main_thread() for t in threads)
    restored = read_journal(ctl.root)
    assert restored is not None
    assert serialize(restored.project) == serialize(ctl.project)


def test_a_burst_of_edits_costs_one_write_and_one_more(ctl, monkeypatch) -> None:
    gate = threading.Event()
    calls: list[int] = []
    real = controller_module.journal_bytes

    def slow(project, **kwargs):
        calls.append(1)
        gate.wait(5)
        return real(project, **kwargs)

    monkeypatch.setattr(controller_module, "journal_bytes", slow)
    for n in range(8):
        edit_unit(ctl, f"burst {n}")
        ctl._timer.timeout.emit()
    gate.set()
    assert ctl.wait_journal()
    assert len(calls) == 2  # the first, and the one the later edits asked for
    restored = read_journal(ctl.root)
    assert restored is not None
    assert next(iter(restored.project.units.values())).name == "burst 7"


def test_a_late_write_does_not_bring_back_a_discarded_journal(ctl, monkeypatch) -> None:
    gate = threading.Event()
    real = controller_module.journal_bytes

    def slow(project, **kwargs):
        gate.wait(5)
        return real(project, **kwargs)

    monkeypatch.setattr(controller_module, "journal_bytes", slow)
    ctl._lock = object()  # type: ignore[assignment]  # discard only acts on a project it owns
    edit_unit(ctl, "to be discarded")
    ctl._timer.timeout.emit()  # the worker is busy serialising
    ctl.discard_journal()
    gate.set()
    assert ctl.wait_journal()
    assert not journal_path(ctl.root).exists()
    ctl._lock = None


def test_saving_clears_the_journal_and_nothing_writes_it_again(ctl) -> None:
    edit_unit(ctl, "one")
    ctl._timer.timeout.emit()
    assert ctl.wait_journal()
    assert journal_path(ctl.root).exists()
    ctl.save()
    assert not journal_path(ctl.root).exists()
    ctl._timer.timeout.emit()  # nothing is unsaved: no journal
    assert ctl.wait_journal()
    assert not journal_path(ctl.root).exists()


def test_a_failed_write_is_reported_once(ctl, monkeypatch) -> None:
    messages: list[str] = []
    ctl.message.connect(lambda text, _undo: messages.append(text))

    def refuse(root, data):
        raise controller_module.SaveError("the disk is full")

    monkeypatch.setattr(controller_module, "write_journal_bytes", refuse)
    for n in range(2):
        edit_unit(ctl, f"fail {n}")
        ctl._timer.timeout.emit()
        assert ctl.wait_journal()
    assert len(messages) == 1 and "the disk is full" in messages[0]
    assert ctl.journal_error_shown and not ctl.autosaves


def test_write_journal_now_is_still_synchronous(ctl) -> None:
    edit_unit(ctl, "now")
    ctl.write_journal_now()
    restored = read_journal(ctl.root)
    assert restored is not None
    assert next(iter(restored.project.units.values())).name == "now"
    QCoreApplication.processEvents()


@pytest.mark.perf
def test_the_gui_thread_hardly_notices_the_journal(qapp, tmp_path: Path) -> None:
    """At stress size the timer slot copies the project and starts the worker: milliseconds."""
    import time

    c = EditorController(journal_delay_ms=10_000, drc_delay_ms=600_000)
    try:
        c._install(build(), tmp_path / "stress", None)
        c.update_unit("U001", name="one")
        c._timer.timeout.emit()
        assert c.wait_journal(60000)  # the first write: everything is serialised
        c.update_unit("U001", name="two")
        t = time.perf_counter()
        c._timer.timeout.emit()
        spent = (time.perf_counter() - t) * 1000
        assert c.wait_journal(60000)
        within(spent, 50, "the GUI thread, one journal tick at 200 devices (ms)")
    finally:
        c.release()
