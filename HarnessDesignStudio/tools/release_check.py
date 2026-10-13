"""Run the release checklist (docs/RELEASE.md) and write dist/release-docs/release-report.md.
Ubuntu only. Usage: python -m tools.release_check [--quick]   (--quick skips the long steps)"""

import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
Result = tuple[bool, str]
QUICK = False  # set by main: a quick run is not a release, so the release-time checks are skipped
# Skipped tests that may stay in a release run: (text of the reason, condition under which it is fine).
# Everything else (no Chromium, no poppler, no PySide6 ...) means a check did not run: the gate fails.
ALLOWED_SKIPS: list[tuple[str, Callable[[], bool]]] = [
    ("needs POSIX non-root", lambda: os.geteuid() == 0),  # the container builds as root
]


def run(cmd: list[str], timeout: int = 3600, env: dict[str, str] | None = None) -> tuple[int, str]:
    p = subprocess.run(
        cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False, env=env
    )
    return p.returncode, (p.stdout + p.stderr).strip()


def tail(text: str, n: int = 2) -> str:
    return " | ".join(text.splitlines()[-n:])


def _selftest_line(out: str) -> str:
    return next((ln for ln in out.splitlines() if "selftest" in ln), "no selftest output")


def unreleased_text(changelog: str) -> str:
    """What is written under the `## Unreleased` heading (up to the next `## `), without blanks."""
    match = re.search(r"^## Unreleased[^\n]*\n(.*?)(?=^## |\Z)", changelog, re.M | re.S)
    return match.group(1).strip() if match else ""


def tag_exists(version: str) -> bool | None:
    """Whether the git tag v<version> exists; None when git cannot tell."""
    code, out = run(["git", "tag", "-l", f"v{version}"])
    return None if code else bool(out.strip())


def versions() -> Result:
    from harness_design_studio import __version__

    pyproject = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M)
    # the section "Unreleased" collects changes after the last release; the version is the next one
    change = re.search(r"^## (?!Unreleased)(\S+)", (ROOT / "CHANGELOG.md").read_text(), re.M)
    found = {
        "__init__": __version__,
        "pyproject": pyproject.group(1) if pyproject else "?",
        "CHANGELOG": change.group(1) if change else "?",
    }
    detail = ", ".join(f"{k} {v}" for k, v in found.items())
    if len(set(found.values())) != 1:
        return False, detail
    if QUICK:
        return True, detail
    # a release is a new version: the old one must not be reused, and nothing may be left unreleased
    tagged = tag_exists(__version__)
    if tagged is None:
        return False, f"{detail}; git cannot list the tags, so a reused version cannot be ruled out"
    if tagged:
        return (
            False,
            f"{detail}; the tag v{__version__} already exists: a release needs a new version",
        )
    if unreleased_text((ROOT / "CHANGELOG.md").read_text()):
        return (
            False,
            f"{detail}; CHANGELOG.md still has text under '## Unreleased': rename it to the version",
        )
    return True, f"{detail}; v{__version__} is not tagged yet, nothing is left under Unreleased"


def lint() -> Result:
    steps = [["ruff", "format", "--check", "."], ["ruff", "check", "."], ["mypy"]]
    for cmd in steps:
        code, out = run([sys.executable, "-m", *cmd])
        if code:
            return False, f"{' '.join(cmd)}: {tail(out)}"
    return True, "ruff format, ruff check, mypy --strict clean"


def skipped_tests(out: str) -> tuple[int, list[str]]:
    """The number of skipped tests in a `pytest -rs` output and the reasons that are not allowed."""
    total, refused = 0, []
    for count, where, reason in re.findall(r"^SKIPPED \[(\d+)\] (\S+?): (.*)$", out, re.M):
        total += int(count)
        if not any(text in reason and fine() for text, fine in ALLOWED_SKIPS):
            refused.append(f"{where} {reason}")
    return total, refused


def run_suite(extra: list[str]) -> Result:
    """The test suite with the skips counted: a silent skip is a check that did not run."""
    env = {**os.environ, "HARNESS_REQUIRE_BROWSER": "1"}  # no Chromium: fail, do not skip
    code, out = run(
        [sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", *extra], env=env
    )
    total, refused = skipped_tests(out)
    last = tail(re.sub(r"^SKIPPED .*$", "", out, flags=re.M).strip(), 1)
    detail = f"{last}; {total} skipped"
    if refused:
        detail += f", NOT allowed: {'; '.join(sorted(set(refused))[:4])}"
        return False, detail
    return code == 0, detail


def tests() -> Result:
    return run_suite(["--cov"])


def tests_plain() -> Result:
    """The same suite without coverage instrumentation (ECSS-Q-ST-80C 6.2.3.8): the result is
    the one that counts for the released code, since instrumentation changes timing."""
    return run_suite([])


def fuzz() -> Result:
    env = {**os.environ, "HARNESS_FUZZ_EXAMPLES": "300"}
    code, out = run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_fuzz.py",
            "tests/test_security.py",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        env=env,
    )
    return code == 0, tail(out, 1)


def soak() -> Result:
    code, out = run([sys.executable, "-m", "tools.soak", "3000", "7"])
    return code == 0, out.splitlines()[0] if out else "no output"


def targets() -> Result:
    from harness_design_studio.core import drc
    from harness_design_studio.core.commands import apply_ops
    from harness_design_studio.core.generate.engine import plan_generation
    from harness_design_studio.core.outputs.build import build_outputs
    from harness_design_studio.core.outputs.verify import verify_outputs
    from harness_design_studio.core.samples import stress_project
    from harness_design_studio.core.verify import verify_project

    p = stress_project()
    t = time.perf_counter()
    plan = plan_generation(p)
    gen = time.perf_counter() - t
    apply_ops(p, plan.ops)
    t = time.perf_counter()
    verify = verify_project(p)
    ver = time.perf_counter() - t
    t = time.perf_counter()
    drc.run(p)
    rules = time.perf_counter() - t
    t = time.perf_counter()
    out = build_outputs(p)
    build = time.perf_counter() - t
    t = time.perf_counter()
    ok = verify_outputs(p, out.files).ok
    check = time.perf_counter() - t
    ok = ok and verify.ok and gen < 10 and not [f for f in drc.run(p) if f.severity == "error"]
    return (
        ok,
        f"stress project: generate {gen:.1f} s (limit 10), verify {ver:.1f} s, rules {rules:.1f} s, outputs {build:.0f} s + check {check:.0f} s",
    )


def reference_projects() -> Result:
    from harness_design_studio.core.generate.engine import generate_project
    from harness_design_studio.core.outputs.build import build_outputs
    from harness_design_studio.core.outputs.verify import verify_outputs
    from harness_design_studio.core.samples import mini3, sat15, sat15_full
    from harness_design_studio.core.verify import verify_project

    for name, make in (("mini3", mini3), ("sat15", sat15), ("sat15_full", sat15_full)):
        p = make()
        if name != "sat15_full":
            generate_project(p)
        if not verify_project(p).ok or not verify_outputs(p, build_outputs(p).files).ok:
            return False, f"verifier reports errors on {name}"
    return True, "verifier and output verifier clean on mini3, sat15, sat15_full"


def sbom() -> Result:
    code, out = run([sys.executable, "-m", "tools.gen_sbom"])
    docs = ROOT / "dist" / "release-docs"
    return code == 0 and (docs / "sbom.cdx.json").is_file(), tail(out)


def vulnerabilities() -> Result:
    """Known vulnerabilities in the shipped dependencies (needs network on the build host)."""
    code, out = run([sys.executable, "-m", "tools.check_vulnerabilities"])
    return code == 0, tail(out)


def reproducible() -> Result:
    code, out = run([sys.executable, "-m", "tools.check_reproducible"])
    return code == 0, "wheel builds identically twice" if code == 0 else tail(out)


def integrity() -> Result:
    code, out = run([sys.executable, "-m", "tools.gen_scf"])
    docs = ROOT / "dist" / "release-docs"
    ok = code == 0 and (docs / "scf.json").is_file() and (docs / "SHA256SUMS").is_file()
    return ok, tail(out)


def package() -> Result:
    code, out = run([sys.executable, "-m", "tools.build_installer"])
    if code:
        return False, tail(out)
    code, out = run([sys.executable, "-m", "tools.build_deb"])
    if code:
        return False, tail(out)
    code, out = run(
        [str(ROOT / "dist" / "harness-design-studio" / "harness-design-studio-gui"), "--selftest"]
    )
    return code == 0 and "selftest ok" in out, f"tarball and deb built; {_selftest_line(out)}"


def deb_install() -> Result:
    from harness_design_studio import __version__

    deb = ROOT / "dist" / f"harness-design-studio_{__version__}_amd64.deb"
    with tempfile.TemporaryDirectory() as tmp:
        code, out = run(["dpkg-deb", "-x", str(deb), tmp])
        if code:
            return False, tail(out)
        code, out = run(
            [f"{tmp}/opt/harness-design-studio/harness-design-studio-gui", "--selftest"]
        )
        cli_code, cli_out = run(
            [f"{tmp}/opt/harness-design-studio/cli/harness-design-studio", "--version"]
        )
        new_code, new_out = run(
            [f"{tmp}/opt/harness-design-studio/cli/harness-design-studio", "new", "--list"]
        )
    return (
        code == 0
        and cli_code == 0
        and new_code == 0
        and "first-steps" in new_out
        and "selftest ok" in out,
        f"extracted deb runs: {_selftest_line(out)}; {cli_out}; examples present",
    )


STEPS: list[tuple[str, Callable[[], Result], bool]] = [
    ("Versions agree (pyproject, package, changelog)", versions, True),
    ("Lint and types", lint, True),
    ("Verifier clean on the reference projects", reference_projects, True),
    ("Performance targets on the stress project", targets, False),
    ("Soak test (3,000 random steps)", soak, False),
    ("Fuzzing and security tests (300 examples per target)", fuzz, False),
    ("Test suite and coverage gate", tests, False),
    ("Test suite without instrumentation", tests_plain, False),
    ("SBOM and licence report", sbom, False),
    ("Known vulnerabilities in the dependencies", vulnerabilities, False),
    ("Reproducible wheel", reproducible, False),
    ("Package (tar.gz, deb) and self-test", package, False),
    ("Installed package runs (deb extracted)", deb_install, False),
    ("Configuration file and SHA-256 of the deliverables", integrity, False),
]


def main() -> int:
    global QUICK
    quick = QUICK = "--quick" in sys.argv
    lines = ["# Release report", ""]
    failed = 0
    for name, step, fast in STEPS:
        if quick and not fast:
            lines.append(f"- SKIPPED: {name}")
            continue
        t = time.perf_counter()
        try:
            ok, detail = step()
        except Exception as exc:  # report, never crash the whole checklist
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        failed += not ok
        lines.append(
            f"- {'PASS' if ok else 'FAIL'}: {name} ({time.perf_counter() - t:.0f} s): {detail}"
        )
        print(lines[-1], flush=True)
    out = ROOT / "dist" / "release-docs"
    out.mkdir(parents=True, exist_ok=True)
    skipped = sum(line.startswith("- SKIPPED") for line in lines)
    if quick:  # a partial run must not overwrite the report of a full one, or pass for a release
        (out / "release-report-quick.md").write_text("\n".join(lines) + "\n")
        print(
            f"{failed} step(s) failed"
            if failed
            else f"quick checks passed ({skipped} steps skipped: NOT a release check)"
        )
        return 1 if failed else 0
    (out / "release-report.md").write_text("\n".join(lines) + "\n")
    print(f"{failed} step(s) failed" if failed else "release checklist passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
