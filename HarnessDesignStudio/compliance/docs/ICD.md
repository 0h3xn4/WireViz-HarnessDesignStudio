# Software interface control document (ICD)

DRD: ECSS-E-ST-40C Annex E. Status: draft, not reviewed; brought up to version 1.7.0 (2026-10-22) for the interfaces added in 1.4.0, 1.5.0 and 1.7.0 and the platforms of D-168.

## 1 to 4. Introduction, references, terms, overview
The Harness Design Studio has no software interface to other running programs. Its interfaces are files, the command line and one helper process.

## 5. Requirements and design
### 5.1 General
Interfaces are specified in the documents named below; this ICD lists them and their identification.

### 5.2 Interface requirements and 5.3 design
| Interface | Direction | Format and limits | Specified in |
| --- | --- | --- | --- |
| IF-PROJECT project folder | read, write | canonical JSON files, atomic saves, schema version, quarantine of bad files | `../../docs/FILE_FORMAT.md` |
| IF-CLI command line | in, out | `harness-design-studio` commands (`harness` is a kept alias), exit codes 0, 1, 2 | `../../docs/CLI.md` (generated from the program) |
| IF-START packaged editor program | in, out | `harness-design-studio-gui` with `--version`, `--selftest`, `--check-system` (prints what is missing and the `sudo apt install` line, exit code 3, when a Linux library or the desktop session is missing; 1.5.0) and `--drc-worker` (internal) | D-167, `../../docs/INSTALL.md`, `../../docs/RELEASE.md` |
| IF-IMPORT-CSV/XLSX | read | parts, interfaces, lengths, ampacity table, device pinouts; CSV, TSV, JSON and XLSX (from 1.4.0 also the column names of an InvenTree export file, read offline); size limits 8 MB, 20 000 rows | `../../docs/IMPORTS.md` |
| IF-DEVLIB device library file | read, write | one JSON file (`harness-device-library`, version 1) with devices, their connectors and pinouts, parts and interface types, kept outside any project (1.4.0); `export-devices`, `import-devices` and the Devices tab | `../../docs/FILE_FORMAT.md`, D-165 |
| IF-BUILDDATA build data tables | read | strip lengths, pin contacts, accessories and crimp tools; CSV, TSV, JSON and XLSX, the kind told by the column headings; `import-build-data` (with `--dry-run`) and the editor (1.7.0) | `../../docs/IMPORTS.md`, D-170 |
| IF-GIT last commit | read | the `.git` files of the repository around the project folder, read without starting `git` and without a network; only the author's name is kept (1.4.0) | D-164, `../../docs/SECURITY.md` |
| IF-NETLIST KiCad netlist | read | S-expression or XML | `../../docs/KICAD.md` |
| IF-OUTPUTS outputs folder | write | SVG, PDF, CSV, XLSX (since 1.7.0 also the build workbook `<ID>_build.xlsx` of each harness), YAML (WireViz style), JSON, Markdown; deterministic bytes; stamp with version and model hash; the PDF and SVG drawings of the harnesses only with `export --drawings` (1.7.0) | `../../docs/OUTPUTS.md` |
| IF-DRC helper process | internal | chunked pickle messages over stdin and stdout between the editor and `--drc-worker`; only the two allowed files may use it | `../../docs/ARCHITECTURE.md`, D-128, `../../docs/SECURITY.md` |
| IF-PROFILE standard profiles | in | `config/*.json` keys, `harness config --apply-profile` | `../../docs/CONFIG.md`, D-131 |
| IF-DELIVERY release files | out | `.deb`, `.tar.gz`, and from 1.2.0 the Windows setup program (`.exe`) and `.zip` (the macOS `.dmg` files of 1.2.0 to 1.5.0 are no longer built, D-168), `scf.json`, `SHA256SUMS`, SBOM | `SCF.md`, `../../docs/RELEASE.md` |

## 6. Validation requirements
Each interface has tests: `tests/test_io.py`, `tests/test_cli*.py`, `tests/test_imports.py`, `tests/test_kicad.py`, `tests/test_outputs.py`, `tests/test_drc_process.py`, `tests/test_profiles.py`, `tests/test_installers.py`, `tests/test_device_library.py`, `tests/test_inventree_import.py`, `tests/test_gitinfo.py`, `tests/test_build_data.py`, `tests/test_build_workbook.py`, `tests/test_build_data_outputs.py`.

## 7. Traceability
`../traceability.csv` (REQ-IO-01, REQ-CLI-01, REQ-IMPORT-01, REQ-OUT-01, REQ-DRC-04, REQ-STD-02, REQ-LIB-03, REQ-LIB-04, REQ-VCS-01, REQ-START-01, REQ-OUT-06, REQ-OUT-07, REQ-WIRE-06, REQ-PIN-03, REQ-ACC-01). IF-START is described by D-167 and verified by REQ-START-01.
