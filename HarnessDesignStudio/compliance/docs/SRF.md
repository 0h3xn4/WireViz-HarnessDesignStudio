# Software reuse file (SRF)

DRD: ECSS-E-ST-40C Annex N. Status: draft, not reviewed. Reused software is third-party open-source software used as libraries; there is no earlier project software and no software reused from a previous development of the owner. WireViz (GPL-3.0, in the same repository at `../src/wireviz`) is **not** used, copied or imported (clean-room rule; WireViz YAML is an export format only).

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
| IBM Plex Sans 1.1.0, IBM Plex Mono 2.5.0 (WOFF2 font files, not Python packages) | npm packages `@ibm/plex-sans`, `@ibm/plex-mono` | SIL OFL 1.1 | interface typefaces, bundled in `src/harness_design_studio/resources/fonts` with the licence text (D-132) |
| development tools (pytest, hypothesis, mypy, ruff, coverage, cyclonedx-bom, pip-licenses, playwright) | pinned in `pyproject.toml` | MIT, BSD, Apache, MPL | not shipped |

## 5. Compatibility with the project
All run on Python 3.12+ on Ubuntu 24.04. Versions are pinned and the wheel build is reproducible (`tools/check_reproducible.py`).

## 6. Reuse analysis conclusion
Suitable. The functional and quality fit is demonstrated by the tests that exercise them through the tool; security aspects (ECSS-Q-ST-80C 6.2.7.3 b) are covered by the hostile-input tests (`../../docs/SECURITY.md`). Not done: a review of the upstream problem lists and a vulnerability check, which need network access and a person (action A-08).

## 7. Detailed results of evaluation
Licence check: all runtime packages allowed; none rejected (`tests/test_licences.py`).

## 8. Corrective actions
None open.

## 9. Configuration status
Versions in `pyproject.toml`; the delivered set is in `scf.json` of the release.
