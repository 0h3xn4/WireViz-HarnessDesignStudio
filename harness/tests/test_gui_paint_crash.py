"""Editing then painting must never crash the editor (a stale item rectangle in the scene index
once ended the whole program with a segmentation fault). Each scenario runs in its own process,
so a crash shows up as a failing test instead of ending the test run."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

ROOT = Path(__file__).resolve().parent.parent

PRELUDE = """
import random, shutil, sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from harness_design_studio.resources import examples_path
from tests.gui_helpers import DialogScript, make_window

tmp = Path(sys.argv[1])
win = make_window(tmp)
app = QApplication.instance()
ctl = win.ctl
DialogScript(win)  # every confirmation is answered with OK

def paint():
    app.processEvents()
    win.view.grab()
    app.processEvents()

def load_flatsat():
    dst = tmp / "flatsat"
    shutil.copytree(examples_path() / "projects" / "flatsat", dst)
    ctl.open_path(dst)
    paint()

def most_connected():
    count = {u: 0 for u in ctl.project.units}
    for i in ctl.project.interfaces.values():
        for e in i.endpoints:
            count[e.unit_id] += 1
    return max(count, key=lambda u: (count[u], u))
"""

SCENARIOS = {
    "guided_delete_connected_unit": """
        load_flatsat()
        ctl.select("unit", most_connected())
        win.act_delete.trigger()
        paint()
    """,
    "expert_delete_connected_unit": """
        load_flatsat()
        win.act_expert.trigger()
        paint()
        ctl.select("unit", most_connected())
        win.act_delete.trigger()
        paint()
    """,
    "expert_add_unit_then_undo": """
        win.act_expert.trigger()
        paint()
        win.palette_panel.add_buttons["payload"].click()
        paint()
        win.act_undo.trigger()
        paint()
    """,
    "delete_interface_then_undo": """
        iid = sorted(ctl.project.interfaces)[0]
        ctl.select("interface", iid)
        win.act_delete.trigger()
        paint()
        win.act_undo.trigger()
        paint()
    """,
    "random_delete_undo_redo": """
        from harness_design_studio.core.samples import sat15
        ctl._install(sat15(), None, None, sample=True)
        paint()
        for mode in ("guided", "expert"):
            if mode == "expert":
                win.act_expert.trigger()
                paint()
            for seed in range(4):
                rnd = random.Random(seed)
                for _ in range(30):
                    units = sorted(ctl.project.units)
                    r = rnd.random()
                    if r < 0.5 and units:
                        ctl.select("unit", rnd.choice(units))
                        win.act_delete.trigger()
                    elif r < 0.7:
                        win.act_undo.trigger()
                    elif r < 0.8:
                        win.act_redo.trigger()
                    else:
                        ifaces = sorted(ctl.project.interfaces)
                        if ifaces:
                            ctl.select("interface", rnd.choice(ifaces))
                            win.act_delete.trigger()
                    paint()
                for _ in range(40):
                    win.act_undo.trigger()
                paint()
    """,
}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_editing_then_painting_does_not_crash(name: str, tmp_path: Path) -> None:
    script = PRELUDE + textwrap.dedent(SCENARIOS[name]) + "\nprint('survived')\n"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "src"), env.get("PYTHONPATH", "")])
    done = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert done.returncode == 0, f"exit {done.returncode}\n{done.stderr[-2000:]}"
    assert "survived" in done.stdout
