# The transparency work: the plan to the complete release

This page is the working plan for the rest of the transparency work (decision D-191, audit `transparency_audit.md`). It exists because the owner decided on 2026-11-03 that the team-ready release must contain **all** of the 14 requirements, not the first part that version 1.12.0 would have carried. Nothing is released before the last stage here is done, tested and reviewed. It is a plan, not a statement of what exists: the changelog says what exists.

## Contents

- [Rules for every stage](#rules-for-every-stage)
- [What is done](#what-is-done)
- [The stages](#the-stages)
- [What closes each requirement](#what-closes-each-requirement)
- [The release](#the-release)
- [Decisions taken](#decisions-taken)

## Rules for every stage

These come from the owner's brief and from D-191 and do not change.

- **Regression first.** The numbers snapshot (`tools/numbers_snapshot.py`) and the output hash baseline stay *identical* unless a change of a result is agreed with the owner, case by case, and written in `docs/changes.md` with before and after.
- **Defaults are today's numbers.** A model choice or a constant that becomes a setting has today's behaviour as its default. A project that does not use a new feature is written byte-identically.
- **One stage, one pull request,** with tests that fail without the change, the documents in `docs/models/` and the user manual for what it adds, and a full test run. Nothing merges without the owner's word. Nothing is tagged by the agent.
- **The default screen stays clean.** Transparency is one click away.
- **A change of a file format** raises the schema version with a migration that is tested on every example, as in 1.8 to 1.11.
- **Standards are cited by ID and title only** (D-191 (9)).

## What is done

Merged to master or in an open pull request, as of 2026-11-03: the safety net (WP0), the derivations for wire sizing, wire length, mass, the bill of materials and the contact current, the Explain view in the Why tab, `explain` with `--all --out`, `docs/models/` for those five, a first registry of assumptions with IDs (`core/assumptions.py`, 12 entries), and, not yet merged, an *Explain* button on a finding of the three rules that have a calculation; and, in S5, the open data (`export-data`), the run record (`--run-record`) and mm² beside every AWG gauge on screen and in explanations.

## The stages

Each stage names what it delivers and when it is finished. The order is by dependency: a stage needs the ones above it that it names.

| Stage | Delivers | Finished when | Needs |
| --- | --- | --- | --- |
| **S1** Explanations for everything else | A derivation for every remaining number and every remaining design rule: readiness (each check and why it is red), test limits, pin allocation and segmentation (why a pin or a harness), label and wire-colour choices, shield ends, the connector choice, and the rules that carry a limit or a count (`bundle-current`, `spare-pins-low`, the temperature and voltage rules, the EMC and category rules, and the rest of the 39). Findings carry actual, limit and margin as data. | Every rule of `docs/RULES.md` and every number of every output is either explained by a derivation or listed, with the reason, as *derived from the library or typed by you* in `docs/models/`; a test walks the rule table and the output columns and fails on one that is neither. | |
| **S2** Constants and assumptions as settings | Every built-in assumption (the 12 IDs and the rest the audit catalogued: round trip, service loop count, K rule, first-fit order, rounding, label and test formats) becomes a named setting with value, unit, description, source and a default equal to today's number, in the configuration files (JSON, per-key metadata: D-191 (2)). An **Assumptions** page lists what is active in the current analysis and every fallback used for an unset value. | The registry has no hard-coded model constant outside it (a test greps the model code for numeric literals in the calculation paths and for the list of exceptions); changing a setting changes the result and its explanation; the snapshot is identical with the defaults. | S1 |
| **S3** Selectable models | Alternatives behind selectors, default = today: how the bundle factor is defined (all wires, per bundle, loaded wires), the voltage-drop model, the length model (service loop, cut and strip allowance, twist take-up), the mass model (scope), the pin allocation strategy, the readiness policy. The active choice is shown in the Assumptions page, in every explanation and in the provenance. | Each model has a page in `docs/models/`, a test that the default reproduces the snapshot, and a test of each alternative against a hand calculation. | S2 |
| **S4** Overrides and change history | A per-field override (field, value, reason, author, date) in place of one lock for four values; flagged in every view and export; re-validated, with the consequences explained. An append-only change journal for inputs, configuration and overrides (who, when, old, new, reason). Waivers and approvals carry author and date. A recorded deviation path for errors (D-191 (3)) for the electrical rules, shown on every output. | An override without a reason is refused; the journal reproduces the history of a project from its first edit; a released harness shows its overrides; old projects open unchanged (migration). | S2 |
| **S5** Provenance and open data | A run record (time, operator, tool version, plug-ins) kept **outside** the hashes (D-191 (1)); provenance that carries the configuration values and the imported files; JSON and CSV for every intermediate and final result (sizing table, segmentation groups, rule results with actual and limit, readiness checks, lengths, mass, BOM, findings); exports the tool can read back; mm² beside AWG on screen and in explanations (D-193). | A colleague's result can be reproduced from the exported files alone (a test does it for each example); the same design written twice still gives the same bytes. | S1, S2 |
| **S6** Data links and imports | An import record in the project (source file, hash, time, rows read and dropped, unit assumed, values converted) and a *source changed* flag; the echo of converted values on `import-lengths` (D-193); parts import with ratings; KiCad import keeps pin type and source; explicit units on every import; a warning for dropped columns; the `#` stamp line skipped in the readers. | Every import says what it read, dropped and converted; a changed source file is flagged; the tool's own CSVs can be read back by every importer. | S5 |
| **S7** Scripting | A documented, stable Python API over the core (load, generate, check, explain, export), `--json` and an output folder on every command, worked examples for a batch and a trade study. | The examples run in CI; the API is covered by tests that import only the public names. | S1 |
| **S8** Extensibility | A registry of rules, models, output tables and importers. **Declarative** extensions first (rules and tables from data files); **Python** entry points second; both opt-in per project with a trust prompt that names the code (D-191 (5)); every plug-in's name and version in the run record. | A declarative rule and a Python rule are added without editing the tool; a project that does not enable them is unchanged; an untrusted plug-in is not loaded. | S2, S3, S5, S7 |
| **S9** Workflow and the two roles | What each step consumes and produces, shown; the intermediates inspectable (and the editable ones editable); as-built capture for AIT (serial, lot, measured results) and the build workbook no longer write-only; Electrical and AIT as two roles if the tests with the engineers show it (D-191 (6)). | The workflow page matches the code (a test); an as-built record is imported, kept in the project and printed; the roles are tested on every page. | S4, S5 |
| **S10** Models documentation and final audit | `docs/models/` for every model, rule and assumption, tied to a test so that none is left out; the audit of the requirements again, with the trace test of the 16 numbers repeated and timed. | The definition of done of the brief passes: any number traced in under a minute, any assumption changed without editing code, a colleague's result reproduced from an exported file, a result explained in a review. | all |

## What closes each requirement

R1 and R12: S1. R2 and R3: S2. R4: S3. R5: S5 (and S6 for imports). R6: S9. R7 and R8: S4. R9 and R10: S5. R11: S7. R13: S8. R14: S6. Documentation and tests: every stage, completed by S10.

## The release

One release after S10, prepared and published the way 1.11.0 and 1.11.1 were: a pull request with the version, the changelog, the release page text, the regenerated files and the status lines; then the owner tags and publishes; then a publication record. Interim states are merged to master as they are finished, but **not released**. The number of the release (1.12.0 as prepared, a later minor, or 2.0.0 for the file-format changes) is decided with the owner when S10 is done. The preparation of 1.12.0 (pull request 151) is not used: it is replaced by the preparation of this release.

## Decisions taken

- 2026-11-03, owner: the team-ready release contains everything of the 14 requirements; nothing is released before (D-193).
- 2026-11-03, owner: **D2** the wire cross-section in mm² is shown next to every AWG gauge, on screen and in explanations; the written files keep the plain gauge unless the owner decides otherwise. **D8** `import-lengths` prints an echo of every converted value (D-193).
- 2026-11-02, owner: the ten decisions of the audit as recommended (D-191).

Next: [the audit](transparency_audit.md), [the models](models/README.md), [changes to results](changes.md)
