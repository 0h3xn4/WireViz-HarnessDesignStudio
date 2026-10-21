# Software reuse file (SRF)

DRD: ECSS-E-ST-40C Annex N. Status: draft, not reviewed; the versions below were compared with `pyproject.toml` and the development environment on 2026-10-21 (version 1.6.0). Reused software is third-party open-source software used as libraries; there is no earlier project software and no software reused from a previous development of the owner. WireViz (GPL-3.0, in the same repository at `../src/wireviz`) is **not** used, copied or imported (clean-room rule; WireViz YAML is an export format only).

## 1 to 3. Introduction, references, terms
`../../docs/DECISIONS.md` (D-31 to D-42, D-73, D-125) records each choice. `../../dist/release-docs/licence-report.md` and `sbom.cdx.json` are produced by `python -m tools.gen_sbom` for each release.

## 4. Presentation of the software intended to be reused
| Package | Version | Licence | Use |
| --- | --- | --- | --- |
| pydantic, pydantic_core, annotated-types, typing_extensions, typing-inspection | 2.13.5, 2.46.5, 0.8.0, 4.16.0, 0.4.4 | MIT, PSF-2.0 | strict data model |
| openpyxl, et_xmlfile | 3.1.5, 2.0.0 | MIT | XLSX import and export |
| defusedxml | 0.7.1 | PSF-2.0 | safe XML parsing of spreadsheets |
| PySide6-Essentials, shiboken6 | 6.11.2 | LGPL-3.0 (alternatively GPL) | GUI (shipped dynamically linked with licence texts) |
| PyInstaller | 6.22.3 | GPL-2.0+ with bootloader exception | packaging only, not shipped |
| Inter 4.1 (Regular, Medium, SemiBold) and JetBrains Mono 2.304 (Regular, Medium) (TrueType files, unmodified; not Python packages) | github.com/rsms/inter release 4.1 (`extras/ttf`), github.com/JetBrains/JetBrainsMono release 2.304 (`fonts/ttf`) | SIL OFL 1.1 | interface and monospace typefaces, bundled in `src/harness_design_studio/resources/fonts` with the licence texts (D-150, replacing IBM Plex of D-132) |
| Lucide icon outlines (lucide-static 1.56.0; a few derive from Feather) | lucide.dev | ISC (Feather: MIT) | the path strings of the interface icons in `gui/icons.py`, drawn with QPainter; no package is installed and no SVG file is shipped (D-146, in the program since 1.1.0) |
| Inno Setup 6 (builds the Windows setup program; preinstalled on the GitHub Windows runner) | not pinned in `pyproject.toml`; `docs/RELEASE.md` names version 6 | Inno Setup licence (D-38) | packaging only, not shipped |
| development tools (pytest, pytest-cov, pytest-qt, pytest-xdist, hypothesis, mypy, ruff, coverage, cyclonedx-bom, pip-licenses, pip-audit, playwright) | pinned in `pyproject.toml` | MIT, BSD, Apache, MPL | not shipped |

## 5. Compatibility with the project
All run on Python 3.12+ on Ubuntu 24.04 and, from 1.2.0, on Windows 10 and 11 (D-149; the whole test suite runs on both in CI; macOS was removed, D-168). Versions are pinned and the wheel build is reproducible (`tools/check_reproducible.py`).

## 6. Reuse analysis conclusion
Suitable. The functional and quality fit is demonstrated by the tests that exercise them through the tool; security aspects (ECSS-Q-ST-80C 6.2.7.3 b) are covered by the hostile-input tests (`../../docs/SECURITY.md`). Not done: a review of the upstream problem lists and a vulnerability check, which need network access and a person (action A-08).

## 7. Detailed results of evaluation
Licence check: all runtime packages allowed; none rejected (`tests/test_licences.py`).

## 8. Corrective actions
None open.

## 9. Configuration status
Versions in `pyproject.toml`; the delivered set is in `scf.json` of the release.
