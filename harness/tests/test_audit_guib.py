"""Regression tests for the editor findings of the October audit: design rule check failures,
read-only sessions, settings, export guards, generation errors (offscreen Qt)."""

import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QLabel  # noqa: E402

from harness_design_studio.core import drc  # noqa: E402
from harness_design_studio.core.commands import History, Put  # noqa: E402
from harness_design_studio.core.generate.engine import (  # noqa: E402
    generate_project,
    plan_generation,
)
from harness_design_studio.core.io.saver import save_project  # noqa: E402
from harness_design_studio.core.model import (  # noqa: E402
    Connector,
    Endpoint,
    InterfaceInstance,
    Pin,
    Project,
    Unit,
    evolve,
)
from harness_design_studio.core.model.config import ConfigFile  # noqa: E402
from harness_design_studio.core.recovery import journal_path  # noqa: E402
from harness_design_studio.core.samples import mini3, new_project, sat15  # noqa: E402
from harness_design_studio.gui import drc_process, strings  # noqa: E402
from harness_design_studio.gui.controller import Delta, EditorController  # noqa: E402
from harness_design_studio.gui.drc_process import DrcProcess, run_check  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.gui_helpers import DialogScript, make_window  # noqa: E402

# ---- the design rule check must say so when it fails ------------------------------------------


def _failing_window(qtbot: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A window on sat15 whose rule check raises (patched before the check can start)."""
    monkeypatch.setenv(drc_process.DISABLE_ENV, "1")
    monkeypatch.setattr(drc, "run", _boom)
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._drc_timer.setInterval(30)
    w.ctl._install(sat15(), None, None)
    return w


def _boom(project):  # type: ignore[no-untyped-def]
    raise ValueError("rule exploded")


def test_a_failing_rule_check_is_reported_not_shown_as_all_clear(
    qtbot: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    win = _failing_window(qtbot, tmp_path, monkeypatch)
    qtbot.waitUntil(lambda: win.ctl.drc_error is not None, timeout=10000)
    qtbot.waitUntil(lambda: win.ctl._drc_worker is None, timeout=10000)
    assert not win.ctl.drc_current
    assert strings.DRC_FAILED.format("rule exploded") == win.ctl.drc_error
    win.tabs.setCurrentWidget(win.problems)
    texts = " ".join(x.text() for x in win.problems.findChildren(QLabel))
    assert "all " not in texts and "No problems" not in texts
    assert "Design rule check failed: rule exploded" in texts
    state = win.problems.findChild(QLabel, "drc-state")
    assert state is not None and state.text() == strings.DRC_FAILED.format("rule exploded")
    assert win.ctl.severity_counts()[0] >= 1
    assert win.ctl._drc_timer.isActive() is False  # no endless retry loop


def test_a_good_check_after_a_failure_clears_the_message(qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    win = _failing_window(qtbot, tmp_path, monkeypatch)
    qtbot.waitUntil(lambda: win.ctl.drc_error is not None, timeout=10000)
    monkeypatch.undo()
    monkeypatch.setenv(drc_process.DISABLE_ENV, "1")
    unit = next(iter(win.ctl.project.units.values()))
    win.ctl.run("rename", [Put("units", evolve(unit, name="Renamed"))])
    qtbot.waitUntil(lambda: win.ctl.drc_current, timeout=10000)
    assert win.ctl.drc_error is None
    assert all(f.rule != "drc-failed" for f in win.ctl.findings())


# Stub helpers: they answer as soon as they start, then read (and ignore) the project.
_STUB = (
    "import sys, struct, pickle, time\n"
    "out = sys.stdout.buffer\n"
    "def send(o):\n"
    "    d = pickle.dumps(o); out.write(struct.pack('>Q', len(d)) + d); out.flush()\n"
    "{body}\n"
    "sys.stdin.buffer.read()\n"
)
_BODIES = {
    "garbage": "out.write(struct.pack('>Q', 10) + b'notapickle'); out.flush()",
    "huge": "out.write(struct.pack('>Q', 1 << 40)); out.flush()",
    "error": "send(('error', 'boom traceback'))",
    "wrongtype": "send(('findings', [1, 2, 3])); send(('done',))",
    "short": "send(('findings',))",
    "hang": "pass",
}


@pytest.fixture
def project():  # type: ignore[no-untyped-def]
    p = sat15()
    generate_project(p)
    return p


@pytest.mark.parametrize("mode", ["garbage", "huge", "error", "wrongtype", "short"])
def test_a_helper_that_answers_badly_is_not_trusted(mode, project, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    code = _STUB.format(body=_BODIES[mode])
    monkeypatch.setattr(drc_process, "worker_command", lambda: [sys.executable, "-c", code])
    helper = DrcProcess()
    try:
        with pytest.raises(Exception):  # noqa: B017, PT011 (any failure, never findings)
            helper.run(project)
        assert not helper.alive
    finally:
        helper.close()


@pytest.mark.parametrize("mode", ["garbage", "huge", "error", "wrongtype", "short"])
def test_run_check_falls_back_in_this_process_when_the_helper_is_bad(  # type: ignore[no-untyped-def]
    mode, project, monkeypatch
) -> None:
    code = _STUB.format(body=_BODIES[mode])
    monkeypatch.setattr(drc_process, "worker_command", lambda: [sys.executable, "-c", code])
    drc_process._shared.close()
    try:
        assert run_check(project) == drc.run(project)
    finally:
        drc_process._shared.close()


def test_a_helper_that_never_answers_is_killed_after_the_deadline(project, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    code = _STUB.format(body=_BODIES["hang"])
    monkeypatch.setattr(drc_process, "worker_command", lambda: [sys.executable, "-c", code])
    monkeypatch.setattr(drc_process, "CHECK_TIMEOUT_S", 1.0)
    helper = DrcProcess()
    try:
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            helper.run(project)
        assert time.monotonic() - start < 15
        assert not helper.alive
    finally:
        helper.close()


def test_close_does_not_wait_behind_a_stuck_check(project, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    code = _STUB.format(body=_BODIES["hang"])
    monkeypatch.setattr(drc_process, "worker_command", lambda: [sys.executable, "-c", code])
    monkeypatch.setattr(drc_process, "CHECK_TIMEOUT_S", 600.0)
    helper = DrcProcess()
    outcome: list[object] = []

    def work() -> None:
        try:
            outcome.append(helper.run(project))
        except Exception as exc:  # the stuck check ends with an error once the child is gone
            outcome.append(exc)

    thread = threading.Thread(target=work)
    thread.start()
    deadline = time.monotonic() + 10
    while not helper.alive and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.3)
    start = time.monotonic()
    helper.close()
    assert time.monotonic() - start < 10
    thread.join(10)
    assert not thread.is_alive() and outcome and isinstance(outcome[0], Exception)


# ---- read-only sessions stay read-only ---------------------------------------------------------


def _pair(tmp_path: Path, qtbot):  # type: ignore[no-untyped-def]
    folder = tmp_path / "p"
    save_project(mini3(), folder)
    a = make_window(tmp_path / "a")
    b = make_window(tmp_path / "b")
    qtbot.addWidget(a)
    qtbot.addWidget(b)
    a.open_project(folder)
    a.ctl.add_unit("sensor")
    a.ctl.write_journal_now()
    assert journal_path(folder).exists()
    return folder, a, b


def test_restoring_a_journal_in_a_read_only_session_keeps_it_read_only(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder, _a, b = _pair(tmp_path, qtbot)
    answers = iter([0, 0])  # open read-only, then Restore
    b.ask_choice = lambda t, x, btns: next(answers)  # type: ignore[assignment]
    assert b.open_project(folder)
    assert b.ctl.read_only and b.ctl._lock is None
    assert "ST1" in b.ctl.project.units  # the journal content is shown
    assert b.ctl.add_unit("computer") is None  # still cannot edit
    before = sorted((folder / "logical/units").iterdir())
    with pytest.raises(Exception):  # noqa: B017, PT011
        b.ctl.save()
    assert sorted((folder / "logical/units").iterdir()) == before
    b.ask_choice = lambda t, x, btns: 1  # type: ignore[assignment]  # closing: discard


def test_reload_keeps_a_read_only_session_read_only(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder, _a, b = _pair(tmp_path, qtbot)
    answers = iter([0, 1])  # read-only, then Discard
    b.ask_choice = lambda t, x, btns: next(answers)  # type: ignore[assignment]
    b.open_project(folder)
    unit_file = next((folder / "logical/units").glob("*.json"))
    unit_file.write_text(unit_file.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert b.ctl.disk_changed()
    b.ask_choice = lambda t, x, btns: 0  # type: ignore[assignment]
    b.check_disk()
    assert b.ctl.read_only
    assert b.ctl.add_unit("computer") is None
    b.ask_choice = lambda t, x, btns: 1  # type: ignore[assignment]  # closing: discard


def test_discarding_in_a_read_only_session_leaves_the_other_windows_journal(
    qtbot: Any, tmp_path: Path
) -> None:
    folder, _a, b = _pair(tmp_path, qtbot)
    answers = iter([0, 1])  # read-only, then Discard
    b.ask_choice = lambda t, x, btns: next(answers)  # type: ignore[assignment]
    b.open_project(folder)
    assert b.ctl.read_only
    assert journal_path(folder).exists()


def test_save_as_from_a_read_only_session_leaves_the_other_windows_journal(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder, _a, b = _pair(tmp_path, qtbot)
    answers = iter([0, 1])
    b.ask_choice = lambda t, x, btns: next(answers)  # type: ignore[assignment]
    b.open_project(folder)
    b.ctl.save_as(tmp_path / "copy")
    assert journal_path(folder).exists()
    assert not b.ctl.read_only


def test_restore_that_fails_says_so(qtbot, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    folder, a, _b = _pair(tmp_path, qtbot)
    a.ctl.release()
    w = make_window(tmp_path / "w")
    qtbot.addWidget(w)
    w.ask_choice = lambda t, x, btns: 0  # type: ignore[assignment]
    monkeypatch.setattr(EditorController, "restore_journal", lambda self: False)
    w.open_project(folder)
    assert w.toasts.messages[-1] == strings.RESTORE_FAILED


def test_restore_works_for_a_project_with_integrity_errors(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "p"
    save_project(mini3(), folder)
    (folder / "logical/units").mkdir(parents=True, exist_ok=True)
    victim = sorted((folder / "logical/units").glob("*.json"))[-1]
    victim.unlink()  # a missing file: dangling references, but the project is not "recovered"
    w = make_window(tmp_path / "w")
    qtbot.addWidget(w)
    w.open_project(folder)
    assert w.ctl.add_unit("sensor")
    w.ctl.write_journal_now()
    w.ctl.release()
    w2 = make_window(tmp_path / "w2")
    qtbot.addWidget(w2)
    w2.ctl.open_path(folder)
    assert w2.ctl.journal_available()
    assert w2.ctl.restore_journal() is True
    assert "ST1" in w2.ctl.project.units
    w2.ctl.release()


# ---- export is refused where the command line refuses it --------------------------------------


def test_export_refuses_a_read_only_project(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "g"
    p = sat15()
    generate_project(p)
    save_project(p, folder)
    a = make_window(tmp_path / "a")
    b = make_window(tmp_path / "b")
    qtbot.addWidget(a)
    qtbot.addWidget(b)
    a.open_project(folder)
    b.ask_choice = lambda t, x, btns: 0  # type: ignore[assignment]
    b.open_project(folder)
    assert b.ctl.read_only
    b.export_flow()
    assert b.toasts.messages[-1] == strings.EXPORT_READ_ONLY
    assert not (folder / "outputs").exists()


def test_export_refuses_a_damaged_project(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "g"
    p = sat15()
    generate_project(p)
    save_project(p, folder)
    victim = sorted((folder / "logical/units").glob("*.json"))[0]
    victim.write_bytes(victim.read_bytes()[:30])
    w = make_window(tmp_path / "w")
    qtbot.addWidget(w)
    w.open_project(folder)
    assert w.ctl.project.recovered
    w.export_flow()
    assert w.toasts.messages[-1] == strings.EXPORT_DAMAGED
    assert not (folder / "outputs").exists()


# ---- hand-edited settings must not stop the editor from starting ------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "[ui]\nscale=abc\n",
        "[ui]\nscale=1.5\n",
        "[ui]\nscale=\n",
        "[ui]\nscale=99999999999\n",
        "[ui]\ngeometry=garbage\n",
        "[ui]\nmode=@@\ntheme=pink\nminimap=maybe\n",
    ],
)
def test_bad_settings_fall_back_to_defaults(text, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    ini = tmp_path / "bad.ini"
    ini.write_text(text, encoding="utf-8")
    w = MainWindow(QSettings(str(ini), QSettings.Format.IniFormat), ThemeManager(), first_run=False)
    qtbot.addWidget(w)
    assert w.theme.scale > 0
    w.ctl.release()


# ---- generation that fails is not "up to date" ------------------------------------------------


def _full_connectors_project() -> Project:
    p = new_project("t")
    for uid, zone in (("A", "panel-A"), ("B", "panel-B")):
        p.units[uid] = Unit(id=uid, name=uid, subsystem="x", zone=zone, side="nominal")
        p.connectors[f"{uid}-J01"] = Connector(
            id=f"{uid}-J01",
            name="J01",
            role="box",
            part_id="EX-MICROD-25-F",
            unit_id=uid,
            gender="female",
            pins=[Pin(id=str(i)) for i in range(1, 5)],
        )

    def iface(iid: str) -> None:
        p.interfaces[iid] = InterfaceInstance(
            id=iid,
            name=iid,
            type_id="rs422",
            endpoints=[
                Endpoint(unit_id="A", connector_id="A-J01"),
                Endpoint(unit_id="B", connector_id="B-J01"),
            ],
        )

    iface("IF-1")
    generate_project(p)
    iface("IF-2")
    return p


def test_generation_errors_are_never_reported_as_up_to_date(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    p = _full_connectors_project()
    w.ctl._install(p, None, None)
    plan = plan_generation(w.ctl.project)
    assert plan.report.errors, "the setup must produce a pin allocation error"
    script = DialogScript(w, accept=False)
    w.generate_flow()
    assert len(script.seen) == 1  # the preview dialog, with the errors, is shown
    assert strings.GEN_UP_TO_DATE not in w.toasts.messages
    shown = " ".join(
        script.seen[0].findings.item(i).text()  # type: ignore[attr-defined]
        for i in range(script.seen[0].findings.count())  # type: ignore[attr-defined]
    )
    assert "IF-2" in shown


def test_apply_generation_with_errors_does_not_claim_up_to_date() -> None:
    ctl = EditorController()
    p = _full_connectors_project()
    ctl.project = p
    ctl.history = History(p)
    seen: list[str] = []
    ctl.message.connect(lambda text, _u: seen.append(text))
    plan = plan_generation(p)
    assert plan.report.errors
    ctl.apply_generation(plan)
    assert strings.GEN_UP_TO_DATE not in seen
    assert seen[-1] == strings.GEN_WITH_ERRORS.format(len(plan.report.errors))


# ---- a lone surrogate must not crash Save or autosave -----------------------------------------


def _with_surrogate(w) -> None:  # type: ignore[no-untyped-def]
    p = w.ctl.project
    name = next(iter(p.config))
    old = p.config[name]
    p.config[name] = ConfigFile(
        name=name, placeholder=old.placeholder, values={**old.values, "extra": "x\ud800y"}
    )


def test_save_with_an_unwritable_character_shows_a_message(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "p"
    save_project(mini3(), folder)
    w = make_window(tmp_path / "w")
    qtbot.addWidget(w)
    w.open_project(folder)
    _with_surrogate(w)
    assert w.save_flow() is False
    assert "not valid text" in w.toasts.messages[-1]
    w.ask_folder = lambda title: str(tmp_path / "copy")  # type: ignore[assignment]
    assert w.save_as_flow() is False
    assert "not valid text" in w.toasts.messages[-1]


def test_autosave_with_an_unwritable_character_does_not_raise(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "p"
    save_project(mini3(), folder)
    w = make_window(tmp_path / "w")
    qtbot.addWidget(w)
    w.open_project(folder)
    w.ctl.add_unit("sensor")
    _with_surrogate(w)
    w.ctl.write_journal_now()
    assert "not valid text" in " ".join(w.toasts.messages)


# ---- small controller fixes -------------------------------------------------------------------


def test_connect_from_is_cleared_when_its_unit_disappears() -> None:
    ctl = EditorController()
    ctl._install(new_project("t"), None, None)
    a = ctl.add_unit("computer")
    b = ctl.add_unit("computer")
    assert a and b
    ctl.begin_connect("rs422")
    ctl.pick(a)
    assert ctl.connect_from is not None
    ctl.select("unit", a)
    ctl.delete_selected()
    assert ctl.connect_from is None
    ctl.pick(b)  # starts a new connection instead of raising
    assert ctl.connect_from is not None and ctl.connect_from.unit_id == b


def test_pick_survives_a_source_unit_that_is_gone() -> None:
    ctl = EditorController()
    ctl._install(new_project("t"), None, None)
    a = ctl.add_unit("computer")
    b = ctl.add_unit("computer")
    assert a and b
    ctl.begin_connect("rs422")
    ctl.pick(a)
    del ctl.project.units[a]  # changed behind the controller's back
    ctl.pick(b)  # no exception
    assert not ctl.project.interfaces


def test_deleting_an_interface_reports_the_units_at_its_ends() -> None:
    ctl = EditorController()
    ctl._install(new_project("t"), None, None)
    a = ctl.add_unit("computer")
    b = ctl.add_unit("computer")
    assert a and b
    assert ctl.add_interface_between("rs422", a, b)
    iid = next(iter(ctl.project.interfaces))
    deltas: list[Delta] = []
    ctl.changed.connect(deltas.append)
    ctl.select("interface", iid)
    ctl.delete_selected()
    assert {a, b} <= deltas[-1].units
    ctl.undo()
    assert {a, b} <= deltas[-1].units
