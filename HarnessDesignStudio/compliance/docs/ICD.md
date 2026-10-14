# Software interface control document (ICD)

DRD: ECSS-E-ST-40C Annex E. Status: draft, not reviewed.

## 1 to 4. Introduction, references, terms, overview
The Harness Design Studio has no software interface to other running programs. Its interfaces are files, the command line and one helper process.

## 5. Requirements and design
### 5.1 General
Interfaces are specified in the documents named below; this ICD lists them and their identification.

### 5.2 Interface requirements and 5.3 design
| Interface | Direction | Format and limits | Specified in |
| --- | --- | --- | --- |
| IF-PROJECT project folder | read, write | canonical JSON files, atomic saves, schema version, quarantine of bad files | `../../docs/FILE_FORMAT.md` |
| IF-CLI command line | in, out | `harness` commands, exit codes 0, 1, 2 | `../../docs/CLI.md` (generated from the program) |
| IF-IMPORT-CSV/XLSX | read | parts, interfaces, lengths; size limits 8 MB, 20 000 rows | `../../docs/IMPORTS.md` |
| IF-NETLIST KiCad netlist | read | S-expression or XML | `../../docs/KICAD.md` |
| IF-OUTPUTS outputs folder | write | SVG, PDF, CSV, XLSX, YAML (WireViz style), JSON, Markdown; deterministic bytes; stamp with version and model hash | `../../docs/OUTPUTS.md` |
| IF-DRC helper process | internal | chunked pickle messages over stdin and stdout between the editor and `--drc-worker`; only the two allowed files may use it | `../../docs/ARCHITECTURE.md`, D-128, `../../docs/SECURITY.md` |
| IF-PROFILE standard profiles | in | `config/*.json` keys, `harness config --apply-profile` | `../../docs/CONFIG.md`, D-131 |
| IF-DELIVERY release files | out | `.deb`, `.tar.gz`, `scf.json`, `SHA256SUMS`, SBOM | `SCF.md`, `../../docs/RELEASE.md` |

## 6. Validation requirements
Each interface has tests: `tests/test_io.py`, `tests/test_cli*.py`, `tests/test_imports.py`, `tests/test_kicad.py`, `tests/test_outputs.py`, `tests/test_drc_process.py`, `tests/test_profiles.py`, `tests/test_installers.py`.

## 7. Traceability
`../traceability.csv` (REQ-IO-01, REQ-CLI-01, REQ-IMPORT-01, REQ-OUT-01, REQ-DRC-04, REQ-STD-02).
