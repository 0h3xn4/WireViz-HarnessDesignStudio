# Requirements (seed, traceable to SPEC.md)

Tests reference these IDs in their docstrings. Extended each milestone.

| ID | Requirement | Source | Verified by |
| --- | --- | --- | --- |
| REQ-OFFLINE-01 | The application makes no network calls and imports no networking modules. | SPEC Part 1, hard constraint 1 | `tests/test_offline.py`, frozen self-test under `unshare -n` |
| REQ-ARCH-01 | The core has no GUI, CLI or network imports. | SPEC Part 4, Architecture | `tests/test_architecture.py` |
| REQ-LIC-01 | Shipped dependencies are permissive or LGPL only; SBOM and licence report are produced per release. | SPEC Part 1, hard constraint 3 | `tests/test_licences.py`, `tools/gen_sbom.py` |
| REQ-SEC-01 | The release check scans the shipped dependencies for known vulnerabilities; a scan that could not run is a failure, never a pass. | ECSS-E-ST-40C 5.9.4 | `tests/test_vulnerability_check.py`, `tools/check_vulnerabilities.py` |
| REQ-PKG-01 | A self-contained package runs without admin rights and without internet. | SPEC Part 1, hard constraint 2 | `tools/build_installer.py`, `--selftest` in CI |
| REQ-BUILD-01 | Builds are reproducible from pinned versions. | SPEC Part 1, hard constraint 3 | `tools/check_reproducible.py` |
| REQ-I18N-01 | All UI strings live in one module. | SPEC Part 1, hard constraint 8 | `gui/strings.py` (review) |
| REQ-MODEL-01 | IDs are safe as file names and on drawings; SI/AWG helpers. | SPEC Part 1 (7), Part 2 | `tests/test_units_ids.py` |
| REQ-MODEL-02 | Strict, immutable model; no coercion or unknown fields. | SPEC Part 4 (engineering practice) | `tests/test_model.py` |
| REQ-INTEGRITY-01 | Referential integrity and duplicate IDs are checked on load, save and every transaction. | SPEC Part 4 (data integrity) | `tests/test_integrity.py` |
| REQ-IO-01 | Human-readable, diffable, deterministic files; byte-identical round trip. | SPEC Part 1 (6) | `tests/test_io.py` |
| REQ-RECOVERY-01 | Corrupt files open in recovery mode; nothing is dropped silently. | SPEC Part 4 (data integrity) | `tests/test_recovery.py`, `tests/test_fuzz.py` |
| REQ-ATOMIC-01 | Atomic saves, backups, plain-language disk errors. | SPEC Part 4 (data integrity, robustness) | `tests/test_atomic_lock.py` |
| REQ-LOCK-01 | Same project open twice is detected; on-disk change is detected. | SPEC Part 4 (data integrity) | `tests/test_atomic_lock.py`, `tests/test_io.py` |
| REQ-MIGRATE-01 | Lossless migrations that keep the original files. | SPEC Part 4 (data integrity) | `tests/test_migrate.py` |
| REQ-TX-01 | Model changes are transactions with consistent undo/redo. | SPEC Part 4 (robustness) | `tests/test_commands.py`, `tests/test_soak.py` |
| REQ-SOAK-01 | Random edit/undo/save/reload sequences keep the model consistent. | SPEC Part 4 (testing) | `tests/test_soak.py` |
| REQ-FUZZ-01 | The loader survives random and malformed input. | SPEC Part 4 (testing) | `tests/test_fuzz.py` |
| REQ-LIB-01 | Starter library is clearly unverified example data with no invented numbers. | SPEC Part 2 (parts library), Part 4 (rules) | `tests/test_library_config.py` |
| REQ-CFG-01 | Rule configuration lives in files; standards numbers are placeholders. | SPEC Part 4 (architecture, rules) | `tests/test_library_config.py` |
| REQ-CLI-01 | `harness validate` / `check` / `migrate` with meaningful exit codes. | SPEC Part 4 (architecture) | `tests/test_cli_project.py` |
| REQ-UX-01 | Design tokens meet WCAG 2.2 AA and category colours stay distinguishable under simulated colour blindness (dE >= 20). | SPEC Part 3 (accessibility, visual design) | `tests/test_tokens.py` |
| REQ-UX-02 | The prototype supports the ten journeys, works offline and logs no console errors. | SPEC Part 3 (UX process 1 and 2) | `tests/test_prototype.py` |
| REQ-UX-03 | The committed prototype matches the generator and is self-contained. | SPEC Part 1 (offline) | `tests/test_prototype_build.py` |
| REQ-GUI-01 | The Qt editor supports the UX journeys (add units, connect safely, table and import, redundancy and findings, delete and undo, modes, search, files, recovery, read-only). | UX.md section 3 | `tests/test_gui_journeys.py` |
| REQ-EDIT-01 | Diagram edits are validated operations that compose into transactions. | SPEC Part 3 (foolproof) | `tests/test_edit.py` |
| REQ-EDIT-02 | Units saved without positions get deterministic, non-overlapping ones. | UX.md section 6 | `tests/test_autoplace.py` |
| REQ-CHECK-01 | Logical findings state what, why and how to fix; fixes are safe; waivers need a justification. | SPEC Part 3 (DRC) | `tests/test_checks.py` |
| REQ-IMPORT-01 | Imports show a per-row preview and apply as one undo step. | SPEC Part 4 (imports) | `tests/test_imports.py`, GUI import tests |
| REQ-JOURNAL-01 | Autosave journal inside the project folder; restore after a crash. | SPEC Part 4 (data integrity) | `tests/test_recovery_journal.py`, GUI recovery tests |
| REQ-PERF-01 | The editor stays responsive at 200 units, 2,000 interfaces, 20,000 wires. | SPEC Part 3 (performance) | `tests/test_gui_perf.py`, `tools/bench_gui.py` |
| REQ-GEN-01 | Regeneration of an unchanged project is byte-identical and produces an empty plan. | SPEC Part 2 (deterministic generation) | `tests/test_generate.py` |
| REQ-GEN-02 | Generated harnesses keep stable IDs; released harnesses, locked wires and locked pins are never changed. | SPEC Part 2 (regeneration merge) | `tests/test_generate.py`, `tests/test_generate_parts.py` |
| REQ-GEN-03 | Sizing, mass and lengths never guess: missing inputs are listed. | SPEC placeholders rule | `tests/test_generate_parts.py` |
| REQ-VER-01 | An independent verifier detects missing, swapped, duplicated and outdated wiring. | SPEC Part 2 (verification) | `tests/test_generate.py` |
| REQ-PERF-02 | Generating 2,000 interfaces and 20,000 wires takes under 10 s. | SPEC Part 3 (performance) | `tests/test_generate.py`, `tools/bench_generate.py` |
| REQ-GUI-02 | Generate shows a preview, applies as one undo step, shows status, the independent check and Explain. | UX.md | `tests/test_gui_generate.py` |
| REQ-DRC-01 | Every design rule has a positive test (fires on a violation) and a negative test (quiet on a clean project). | SPEC Part 3 (DRC), Part 5 (tests) | `tests/test_drc.py` |
| REQ-DRC-02 | Findings state what, why and how to fix; warnings are waivable with justification, errors are not; waivers persist and appear in the report. | SPEC Part 3 (DRC) | `tests/test_drc.py` |
| REQ-DRC-03 | A check that cannot run because of placeholders says so. | SPEC placeholders rule | `tests/test_drc.py` |
| REQ-DRC-04 | Design rules run in the background and never block edits; Show, Fix and Waive work from the Problems panel. | SPEC Part 3 (DRC, performance) | `tests/test_gui_drc.py` |
| REQ-OUT-01 | Every output type is produced from the model, deterministically (equal model, equal bytes), and carries the generator version and model hash. | SPEC Part 3 (outputs) | `tests/test_outputs.py` |
| REQ-OUT-02 | Golden-file tests for every output type on three reference projects. | PLAN M5 | `tests/test_outputs.py`, `tests/fixtures/outputs/` |
| REQ-OUT-03 | Drawings stay legible in greyscale: harness drawings draw wire colours on a dark outline and also write every colour as a code; system diagrams use dark colours plus dash patterns. | SPEC Part 3 (accessibility, print) | `tests/test_outputs.py` |
| REQ-OUT-04 | Stale and modified outputs are detected in the CLI and the editor. | PLAN M5 | `tests/test_outputs.py`, `tests/test_gui_outputs.py` |
| REQ-VER-02 | Verifier v2 checks every artefact against the design; each check has a mutation test. | PLAN M5 | `tests/test_outputs.py` |
| REQ-OUT-05 | Outputs never invent numbers: undecided gauges, unknown lengths, masses and test limits are written as such. | SPEC placeholders rule | `tests/test_outputs.py` |
| REQ-CC-01 | Releasing needs a name and comment and is blocked by verifier or rule errors, stale plans or outputs, undecided gauges and unknown lengths; it writes a baseline and a change log entry. | SPEC Part 5 (change control) | `tests/test_change_control.py` |
| REQ-CC-02 | Released harnesses, the interfaces they carry and the pins they use cannot be edited or deleted; a new revision unlocks and keeps the old baseline. | SPEC Part 3 (released items locked) | `tests/test_change_control.py` |
| REQ-CC-03 | The diff of two baselines, or of the working design against a baseline, lists added, removed and changed objects exactly (property test). | PLAN M6 acceptance | `tests/test_change_control.py` |
| REQ-CC-04 | A released harness that no longer matches its baseline is reported (rule and `harness check`). | PLAN M6 | `tests/test_change_control.py` |
| REQ-CC-05 | Title blocks, change log table and revision report come from the data; the editor offers review, release, new revision, changes (marked on the diagram) and change log. | SPEC Part 3 (outputs, UX) | `tests/test_change_control.py`, `tests/test_gui_changes.py` |
| REQ-CC-06 | A release is blocked while a configuration file is marked as a placeholder, unless the releaser gives a written reason, which is kept in the change log and the baseline (D-135). | Owner decision 2026-10-08 | `tests/test_change_control.py`, `tests/test_gui_changes.py` |
| REQ-CC-07 | A release is blocked while the harness uses a part that is not approved or is example data, unless the releaser gives a written reason, which is kept in the change log and the baseline (D-136). | Owner decision 2026-10-08 | `tests/test_change_control.py`, `tests/test_gui_changes.py` |
| REQ-M7-01 | Every interactive control has an accessible name; text is at least 10 px at every UI scale; the canvas announces its content and the accessible alternative. | SPEC Part 3 (accessibility) | `tests/test_accessibility.py` |
| REQ-M7-02 | Random editing for thousands of steps keeps every invariant (integrity, rejected steps change nothing, save and load round trip, verifier clean after generation). | PLAN M7 soak test | `tests/test_soak.py`, `tools/soak.py` |
| REQ-M7-03 | The user guide, rule reference and configuration reference are complete and in sync with the program. | SPEC Part 5 (docs) | `tests/test_docs.py` |
| REQ-M7-04 | Ubuntu packages: `.tar.gz` with install and uninstall scripts, and a reproducible `.deb`. | D-110 | `tests/test_installers.py`, `tools/release_check.py` |
| REQ-M7-05 | The usability kit computes SUS and success correctly and prepares the task material. | UX.md section 9 | `tests/test_usability_kit.py` |
| REQ-NUM-01 | Sizing arithmetic (AWG diameter and area, ampacity derating, voltage drop) agrees with exact arithmetic and with the defining points of the AWG scale. | ECSS-Q-ST-80C 7.1.7 | `tests/test_numerics.py` |
| REQ-TRACE-01 | Every tool requirement names the file that verifies it, and the traceability report is current. | ECSS-E-ST-40C 5.8.3 | `tests/test_trace.py`, `tools/trace.py` |
| REQ-TRACE-02 | The SDD has a component table (layer, purpose, dependencies) and a requirement-to-component trace, generated from the code and current. | ECSS-E-ST-40C 5.5.2, Annex F 6 | `tests/test_sdd_components.py`, `tools/gen_sdd_components.py` |
| REQ-MET-01 | Size, complexity and test metrics are collected by a tool. | ECSS-Q-ST-80C 7.1.5 | `tests/test_metrics.py`, `tools/metrics.py` |
| REQ-SCF-01 | Every delivery has a configuration file and SHA-256 values. | ECSS-Q-ST-80C 6.2.4.11 | `tests/test_scf.py`, `tools/gen_scf.py` |
| REQ-STD-01 | Every design rule names the standard requirements it serves; a rule can only cite a requirement that exists in `compliance/requirements`. | audit gap B-12 | `tests/test_drc.py` |
| REQ-STD-02 | Standard value profiles are opt-in (`harness config --apply-profile`), cite the requirement each value comes from, fill only unset values, keep the placeholder flag, and invalid values are reported. | D-131; ECSS-Q-ST-30-11C 6.11.2, 6.32.4, 6.32.5 | `tests/test_profiles.py` |
| REQ-STD-03 | Rules from the supplied standards (connector and wire voltage, temperature margin, mating cycles, one manufacturer per connector pair, wire specification, power and return pins, bundle current) are silent until their numbers exist, say what they could not check, and cite their requirement IDs. | ECSS-Q-ST-30-11C 6.11, 6.12, 6.32; ESCC 3901 4.4 | `tests/test_standard_rules.py`, `tests/test_drc.py` |
| REQ-STD-04 | EMC wiring checks (shield bonding at both ends, one bundle per EMC class) are opt-in, and the EMC class appears on wire lists and labels only when classes are used; the output verifier checks it. | ECSS-E-ST-20-07C 4.2.13 | `tests/test_standard_rules.py`, `tests/test_outputs.py` |
| REQ-STD-05 | Pin allocation can leave an unassigned contact between power and return; without the setting nothing changes. | ECSS-Q-ST-30-11C 6.11.3 a | `tests/test_standard_rules.py` |
| REQ-STD-06 | The mapping of the standard's family-group codes to the tool's part classes is recorded as a worksheet that states only what the supplied text says and cites existing requirements. | ECSS-Q-ST-30-11C 6.11, 6.12, 6.32 | `tests/test_family_group_mapping.py` |
| REQ-PROV-01 | Every set of outputs includes `system/provenance.json` (tool version, model hash, library, settings with placeholder flags, design counts); the output verifier checks it against the design. | UX/UI guidelines "Provenance on every output" | `tests/test_provenance.py` |
| REQ-LOC-01 | Messages about damaged project files give the file, and the line and column of the damage or the line of the set-aside object, and never quote file content. | UX/UI guidelines "error messages point to the exact line" | `tests/test_error_locations.py` |
| REQ-SCHEMA-01 | `harness schema FOLDER` writes JSON Schemas of the project files, made from the model, with an editor settings fragment; nothing is downloaded; the schemas cover every key the tool writes. | UX/UI guidelines "schema-driven editing" | `tests/test_schemas.py` |
| REQ-GUI-03 | The editor offers File > New project from an example (blank, first-steps, small-satellite), the same examples as `harness new`. | UX/UI guidelines "templates as empty states" | `tests/test_gui_journeys.py` |
| REQ-GUI-04 | The toolbar filter shows one signal class, connector or bundle and fades the rest without changing the project; it stays on when the diagram changes and follows a new project. | UX/UI guidelines "navigation for large harnesses" | `tests/test_gui_filters.py` |
| REQ-UX-04 | The interface uses the design tokens of IBM Carbon (White and Gray 100 themes) and the bundled IBM Plex fonts; the font licence ships with the program; nothing is fetched. | UX/UI guidelines "Foundation" | `tests/test_fonts.py`, `tests/test_tokens.py` |
| REQ-GUI-05 | The connector part picker shows what each part is (description, maker, pins, specification, approval, ratings) in the list tooltip and under the picker. | UX/UI guidelines "component library picker" | `tests/test_gui_journeys.py` |
| REQ-LIB-02 | The parts library records its name, version, source and date (date entered by a person, YYYY-MM-DD, never read from a clock); `harness library` shows and sets them, `harness import-parts` records the file name and its SHA-256; provenance and the editor show them. | UX/UI guidelines "version, date and source visible" | `tests/test_library_source.py` |
