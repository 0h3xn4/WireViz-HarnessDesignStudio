"""The design rule check runs in a helper process so that it cannot hold up the editor."""

import os
import subprocess
import sys
import threading
import time

import pytest

from harness_design_studio.core import drc
from harness_design_studio.core.drc import worker
from harness_design_studio.core.edit import clone_with
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import Project
from harness_design_studio.core.samples import sat15
from harness_design_studio.gui import drc_process
from harness_design_studio.gui.drc_process import DrcProcess, run_check
from tests.helpers import time_limit


@pytest.fixture
def project():  # type: ignore[no-untyped-def]
    p = sat15()
    generate_project(p)
    return p


@pytest.fixture
def helper():  # type: ignore[no-untyped-def]
    h = DrcProcess()
    yield h
    h.close()


def test_the_helper_gives_the_same_findings_as_a_check_in_this_process(project, helper) -> None:  # type: ignore[no-untyped-def]
    assert helper.run(project) == drc.run(project)
    assert helper.alive


def test_the_process_is_reused_and_replaced_after_it_dies(project, helper) -> None:  # type: ignore[no-untyped-def]
    first = helper.run(project)
    pid = helper._proc.pid  # type: ignore[union-attr]
    assert helper.run(project) == first and helper._proc.pid == pid  # type: ignore[union-attr]
    helper._proc.kill()  # type: ignore[union-attr]
    helper._proc.wait()  # type: ignore[union-attr]
    assert not helper.alive
    assert helper.run(project) == first and helper._proc.pid != pid  # type: ignore[union-attr]


def test_run_check_falls_back_when_the_helper_cannot_start(project, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(drc_process, "worker_command", lambda: ["/nonexistent/program"])
    drc_process._shared.close()
    assert run_check(project) == drc.run(project)


def test_the_check_can_be_kept_in_this_process(project, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    drc_process._shared.close()
    monkeypatch.setenv(drc_process.DISABLE_ENV, "1")
    assert run_check(project) == drc.run(project)
    assert not drc_process._shared.alive


def test_a_packaged_program_is_started_with_the_worker_flag(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    assert drc_process.worker_command()[1:] == ["-P", "-m", "harness_design_studio.core.drc.worker"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert drc_process.worker_command() == [sys.executable, "--drc-worker"]


def test_pieces_rebuild_the_project(project) -> None:  # type: ignore[no-untyped-def]
    messages = list(worker.project_messages(project))
    assert messages[0][0] == "begin" and messages[-1] == ("go",)
    rebuilt: Project = messages[0][1]  # type: ignore[assignment]
    for msg in messages[1:-1]:
        getattr(rebuilt, str(msg[1])).update(msg[2])  # type: ignore[attr-defined]
    for name in worker.CHUNKS:
        assert getattr(rebuilt, name) == getattr(project, name), name
    assert rebuilt.zones == project.zones and rebuilt.meta == project.meta


def test_the_worker_ends_when_its_input_closes() -> None:
    with subprocess.Popen(
        drc_process.worker_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as proc:
        assert proc.stdin is not None
        proc.stdin.close()
        assert proc.wait(timeout=30) == 0


def test_the_worker_stops_on_a_message_it_does_not_understand() -> None:
    with subprocess.Popen(
        drc_process.worker_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as proc:
        assert proc.stdin is not None
        worker.send(proc.stdin, ("go",))  # no project was sent first
        assert proc.wait(timeout=30) == 1


def test_a_check_does_not_hold_up_the_calling_threads_neighbour() -> None:
    """While a big check runs in the helper, another thread of the editor's process is never kept
    waiting long (a check in a thread held the interpreter for 70 ms or more at a time)."""
    from tools.bench_stress import build

    project = clone_with(build(), [])
    run_check(project)  # starts the helper

    def longest_wait() -> float:
        stop = threading.Event()

        def work() -> None:
            run_check(project)
            stop.set()

        threading.Thread(target=work).start()
        worst, last = 0.0, time.perf_counter()
        while not stop.is_set():
            time.sleep(0.001)
            now = time.perf_counter()
            worst, last = max(worst, now - last), now
        return worst

    # A stall caused by the check shows in every run; a busy machine delays only some of them,
    # so the best of three runs is compared with the limit.
    try:
        best = min(longest_wait() for _ in range(3))
    finally:
        drc_process._shared.close()
    assert best * 1000 < time_limit(50), best


def test_no_helper_is_left_running_after_close(project) -> None:  # type: ignore[no-untyped-def]
    h = DrcProcess()
    h.run(project)
    proc = h._proc
    assert proc is not None
    h.close()
    assert proc.poll() is not None and not h.alive
    assert os.environ.get(drc_process.DISABLE_ENV) != "1"
