"""The suite runs in parallel in CI (`pytest -n auto -m "not perf"`, then `pytest -m perf` alone).

Two things keep that sound: every test that asserts a wall-clock limit carries the `perf` marker
(otherwise it would run next to other workers and fail on load), and no test shares a fixed
file or folder with another test (otherwise two workers would trip over each other)."""

import ast
import re
from pathlib import Path

import pytest

HERE = Path(__file__).parent
CLOCKS = ("time_limit(", "within(", "perf_counter")  # a limit measured on the wall clock


def _marked(node: ast.FunctionDef, module_marked: bool) -> bool:
    text = " ".join(ast.unparse(d) for d in node.decorator_list)
    return module_marked or "mark.perf" in text


def _module_marked(tree: ast.Module) -> bool:
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in stmt.targets
        ):
            return "mark.perf" in ast.unparse(stmt.value)
    return False


def test_every_test_with_a_wall_clock_limit_is_marked_perf() -> None:
    """Parallel workers load the machine, so a limit in milliseconds is only fair when the test
    runs alone. CI runs `-m "not perf"` in parallel and `-m perf` serially afterwards."""
    unmarked: list[str] = []
    for path in sorted(HERE.glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        helpers = {
            n.name
            for n in tree.body
            if isinstance(n, ast.FunctionDef)
            and not n.name.startswith("test_")
            and any(c in (ast.get_source_segment(source, n) or "") for c in CLOCKS)
        }
        module_marked = _module_marked(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
                continue
            body = ast.get_source_segment(source, node) or ""
            timed = any(c in body for c in CLOCKS) or any(f"{h}(" in body for h in helpers)
            if timed and not _marked(node, module_marked):
                unmarked.append(f"{path.name}::{node.name}")
    assert not unmarked, "add @pytest.mark.perf to: " + ", ".join(unmarked)


def test_no_test_uses_a_fixed_folder_outside_its_own_tmp_path() -> None:
    """A literal /tmp path (or the shared temp folder) is one place for all workers. Tests use
    `tmp_path`; the editor's own settings are redirected per process in conftest.py."""
    shared = re.compile(r"""["']/(?:tmp|var/tmp|dev/shm)\b|gettempdir\(\)|tempfile\.mktemp\(""")
    found = [
        f"{path.name}:{number}"
        for path in sorted(HERE.glob("*.py"))
        if path.name != Path(__file__).name
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if shared.search(line)
    ]
    assert not found, "use tmp_path instead: " + ", ".join(found)


def test_the_ci_job_runs_both_halves_of_the_suite_and_keeps_the_coverage_gate() -> None:
    """`-m "not perf"` in parallel and `-m perf` alone are the whole suite only when both run, the
    second adds to the first one's coverage and is the one that applies the 90% gate on core."""
    workflow = HERE.parents[1] / ".github" / "workflows" / "harness-ci.yml"
    if not workflow.is_file():
        pytest.skip("the repository root is not here")
    job = workflow.read_text(encoding="utf-8")
    job = job[job.index("\n  test:") : job.index("\n  package-on-24-04:")]
    commands = [ln.split("run:", 1)[1].strip() for ln in job.splitlines() if "run: pytest" in ln]
    assert len(commands) == 2, commands
    parallel, alone = commands
    # a pull request leaves out the timing tests and the `slow` ones; every other run (master) only the
    # timing tests, so `slow` still runs before a release
    assert "-n auto" in parallel and "--cov " in parallel
    assert "'not perf and not slow'" in parallel and "|| 'not perf'" in parallel
    assert "github.event_name == 'pull_request'" in parallel
    assert "--cov-fail-under=0" in parallel  # a subset of the tests cannot judge the gate
    assert "-n " not in alone and "-m perf" in alone and "--cov-append" in alone
    assert "fail-under" not in alone  # pyproject.toml's 90 applies to the combined number
    assert "HARNESS_TIME_FACTOR" in job and "timeout-minutes:" in job
