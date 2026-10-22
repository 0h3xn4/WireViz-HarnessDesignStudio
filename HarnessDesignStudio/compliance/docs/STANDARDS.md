# Design, coding and tool standards

Status: approved by the owner on 2026-10-08 (approval given in the working session; the owner is also customer and supplier, so no independent reviewer, see A-01). The rows Build, Platform and CI of the table below were brought up to date for 1.2.0 on 2026-10-20 and for 1.6.0 (macOS removed, D-168) on 2026-10-21 (checked again for 1.7.0 on 2026-10-22: no change was needed); the owner's approval was given for the earlier text (D-149 and D-168 are the owner's decisions on the platforms).

Addresses ECSS-Q-ST-80C 5.6.1.1 to 5.6.2.3, 6.3.3.2, 6.3.3.4, 6.3.4.1 to 6.3.4.5 (gap G-06). These standards already exist as practice in `CLAUDE.md`, `pyproject.toml` and the CI workflow; this document makes them one mandatory list.

## Tools and environment

| Item | Choice | Where fixed |
| --- | --- | --- |
| Language | Python 3.12 or newer | `pyproject.toml` |
| GUI toolkit | PySide6 (LGPL) | `pyproject.toml`, `docs/DECISIONS.md` |
| Data model | pydantic v2, strict, immutable | `core/model` |
| Tests | pytest, hypothesis; 90 % branch and statement coverage on `core` | `pyproject.toml` |
| Static checks | ruff (E, F, W, I, B, UP, SIM, S), `mypy --strict` | `pyproject.toml` |
| Build | pinned versions, reproducible wheel, PyInstaller package, `.deb`; from 1.2.0 also the Windows setup program and `.zip` (the macOS `.dmg` of 1.2.0 to 1.5.0 is no longer built, D-168) | `tools/check_reproducible.py`, `tools/build_deb.py`, `tools/build_windows.py` |
| Platform | Ubuntu 24.04 and newer and Windows 10 and 11 (64-bit) (Windows from 1.2.0) | D-149 (supersedes D-127, Ubuntu only), D-168 (removes macOS) |
| CI | `.github/workflows/harness-ci.yml` (at the repository root: jobs `changes`, `docs`, `test` and `package-on-24-04`; a change to documents only runs the `docs` job instead of the full suite, D-138); since 1.2.0 `harness-platforms.yml` runs the suite on Windows, `harness-packages.yml` builds the Windows packages on branches `pkg/**`, and `release.yml` (on a `v*` tag) builds and tests the four packages and publishes the release page | |

Suitability (5.6.1.2, 5.6.2.2): chosen because they are permissive or LGPL licensed, run offline, and allow strict static checking; every dependency is recorded with version and licence in `docs/DECISIONS.md` and the SBOM.

## Design standards (6.3.3.2, 6.3.3.4)

Mandatory: `core` does not import `gui`, `cli` or network modules (`tests/test_architecture.py`, `tests/test_offline.py`); all model changes go through commands and transactions; generation is a pure function of the design; the verifier shares no code with the generator; outputs are deterministic. Advisory: keep functions small (complexity is reported by `tools/metrics.py`; proposed limit: values above 30 are listed in each milestone report with a reason; the tool has functions above it today, see `compliance/metrics.json`).
Adherence is verified by the tests named, by `ruff`, `mypy` and by review of each diff.

## Coding standards (6.3.4.1 to 6.3.4.5)

Mandatory: `ruff format` and `ruff check` clean; `mypy --strict` clean; no `print` of design data and no design data in logs; no evaluation of data, no starting of programs and no `pickle` outside the files `tests/test_security.py` allows, no network (`tests/test_offline.py`); names, UI strings in `gui/strings.py`; tests first, a regression test with every bug fix; no invented standard values (placeholder instead). Low-level languages: none used; the whole product is Python (6.3.4.5). The security aspects of 6.3.4.1 are the `S` rules of ruff and `tests/test_security.py`.
Review with the customer (6.3.4.4): this document is sent to the owner with the other plans (open action A-05).

## Verification of correct use of the tools (5.6.1.3)

CI runs the static checks and tests on every pull request and on every push to the default branch (a change to documents only runs the document checks, D-138); a failing run blocks merging by the owner's practice, not by a technical lock (the owner waived the protection on 2026-10-08: `../DEVIATIONS.md` T-18).
