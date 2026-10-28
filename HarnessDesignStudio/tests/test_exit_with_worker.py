"""The program may end while the autosave journal is still being written in the background.
Qt aborts the whole process ("QThread: Destroyed while thread is still running") when a running
thread is destroyed, so a script, a test or a crash path that never closes the window used to end
with signal 6 on a slow machine. A slow writer is simulated here, in a process of its own."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

ROOT = Path(__file__).resolve().parent.parent

SLOW_WRITER = """
import time
import harness_design_studio.gui.controller as _controller
_real = _controller.journal_bytes
def _slow(*args, **kwargs):
    time.sleep(1.5)  # a loaded machine
    return _real(*args, **kwargs)
_controller.journal_bytes = _slow
"""


def test_ending_the_program_waits_for_the_autosave_writer(tmp_path: Path) -> None:
    from tests.test_gui_paint_crash import PRELUDE, SCENARIOS

    scenario = textwrap.dedent(SCENARIOS["expert_delete_connected_unit"])
    script = SLOW_WRITER + PRELUDE + scenario + "\nprint('survived')\n"
    env = {"QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": f"{ROOT}:{ROOT / 'src'}"}
    done = subprocess.run(
        [sys.executable, "-W", "ignore", "-c", script, str(tmp_path)],
        cwd=ROOT,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 0, f"exit {done.returncode}\n{done.stderr[-1500:]}"
    assert "survived" in done.stdout
    assert "Destroyed while thread" not in done.stderr
    assert "already deleted" not in done.stderr
