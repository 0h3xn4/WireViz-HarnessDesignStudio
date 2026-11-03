# Changes to results

This page records every change of the transparency work (D-191) that moves something an engineer could see in a result: a number, a text that is stored in a project, or a written file. Each entry says what it was before, what it is now, why, and who agreed. A change that is only a new feature that a project does not use is not listed here (the [changelog](../CHANGELOG.md) has it); a change that moves a number is listed here before it is made.

## Contents

- [The rule](#the-rule)
- [How the numbers are kept](#how-the-numbers-are-kept)
- [Entries](#entries)

## The rule

The tool gives the numbers it gives today, and they do not change unless a defect is found. A defect that moves a number is recorded here with the number before and after, and is fixed only with the owner's agreement, one at a time. Before any refactoring, the numbers are captured by a test (below). A written file stays byte-identical for a project that does not use a new feature; where a change moves written files on purpose, the stored baselines are renewed with the reason given here.

## How the numbers are kept

Two stored files hold what the tool writes today, and two tests compare with them:

| File | Holds | Test | Renew with |
| --- | --- | --- | --- |
| `docs/ui/OUTPUT_HASHES_BASELINE.json` | The SHA-256 of every file the four packaged examples write | `tests/test_output_hashes.py` | `python -m tools.output_hashes --write docs/ui/OUTPUT_HASHES_BASELINE.json` |
| `tests/fixtures/numbers/snapshot.json` | For eleven scenarios (the four examples, and the flatsat with a hand override, with the ECSS profile, with a lower ampacity and with a bundle table of its own, and the small satellite in the three ways to group interfaces into harnesses): the gauge, length, part, colour and lock of every wire, every finding with its text, and the SHA-256 of every written file | `tests/test_numbers_snapshot.py` | `python -m tools.numbers_snapshot --write tests/fixtures/numbers/snapshot.json` |

When a test fails, it names what moved: the wire, the finding or the file. Renew a file only for a change that is listed under Entries.

## Entries

### 2026-11-02: `validate` runs the check of the configuration values

- **Before.** `harness-design-studio validate` did not check the values of `config/*.json`. With `bundle_derating` set to 1.5 it printed `0 error(s)` and exited 0, while `generate` stopped with `config_invalid`, `config` showed the file as INVALID and `drc` exited 1. `docs/CONFIG.md` says all of them use the same checks.
- **Now.** `validate` runs the same check (`configcheck.validate`): it prints `ERROR config_invalid: config/derating.json: bundle_derating must be a number above 0 and at most 1.` and exits 1.
- **What moves.** Nothing is written and no number changes. A project whose values are all valid gets the same output as before. A project with a value that `generate` already refused now also fails `validate`.
- **Why.** Found by the transparency audit (defect D1): a user who validates first was told the project was clean.
- **Agreed.** Owner, 2026-11-02 ("all as per your recommendations"). Test: `tests/test_validate_config.py`.

### 2026-11-02: the bundle table is cited as the standard only when it is

- **Before.** The note on a sized wire read `bundle factor K 0.7 for 10 wires (Table 6-41)` whenever a table of bundle factors was set, also when the table was the user's own.
- **Now.** `(Table 6-41)` is written only when the table equals the one of the ECSS profile (`standard_profiles.BUNDLE_K`). For any other table the note reads `(table of config/derating.json, bundle_factor_by_count)`.
- **What moves.** No number: the factor, the gauge and every finding are the same. The note is stored in the generation record of the project, and the model hash covers it, so a project that has a table of bundle factors of its own gets a new model hash, and so every file it writes carries the new hash. A project with the ECSS table, with a single bundle factor, or with none is written as before. In the snapshot only the scenario `flatsat-own-bundle-table` moved (all 120 files, by the hash; no wire and no finding), and it was renewed for this reason.
- **Why.** Found by the transparency audit (defect D4): the standard was named for a table that is not the standard's.
- **Agreed.** Owner, 2026-11-02 (decision 4 of D-191: keep today's behaviour, make it visible). Test: `tests/test_bundle_citation.py`.

### 2026-11-03: `import-lengths` echoes every converted value; every import says what it read

- **Before.** `import-lengths` printed `row 2: OK` for every accepted row. A bare `5.0` in a file read as millimetres became 0.005 m, and nothing said so (defect D8 of the audit). The other imports left out the columns they had no field for without a word, and said nothing of the unit they assumed.
- **Now.** `row 2: OK W001 / W001-L1: 5.0 mm = 0.005 m`, and before the rows `Read ...`, `Columns read: ...`, a `warning:` for every column that is not read and `Unit: length in mm (assumed; --unit says another).`. `--unit` takes `in` and `ft` as well, and `--mass-unit` and `--unit` of `import-build-data` exist; their defaults are the units the columns have always been read in.
- **What moves.** Only text on the screen of the command line. No stored value, no number, no written file and no model hash changes; `tests/test_numbers_snapshot.py` and `tools/output_hashes` are unchanged.
- **Why.** Owner decision D-193 (how `import-lengths` shows the converted metres): an echo of every converted value, rows dropped listed with the reason.
- **Agreed.** The echo of the converted values in `import-lengths`: owner, D-193. The same read summary (rows read, checksum, columns read, columns not read, unit) on every other import was accepted by the project coordinator; it is not covered by D-193. Tests: `tests/test_import_records.py`.

### 2026-11-03: the tool's own CSV files are read back as they were written

- **Before.** The stamp line `# harness-design-studio VERSION model HASH` that starts every CSV the tool writes was read as the heading row by the lengths, build data and parts imports. `import-pinout` skipped the line but gave back the text a spreadsheet would run as a formula (`'+28V`) with its apostrophe, so a pin with the signal `+28V` came back as `'+28V`.
- **Now.** A file that starts with that exact line is the tool's own: the line is skipped in every reader and the apostrophe is taken away again. A file that does not start with it is read exactly as before.
- **What moves.** Only what is read from a stamped file. Nothing that was imported correctly before changes; a pin signal that had come back with an apostrophe now comes back without it.
- **Why.** Found by the transparency audit (IO-C2-021, IO-C2-022): what the tool exports could not be imported again.
- **Agreed.** Skipping the stamp line: step 6 of the plan (the tool's own CSV files must be readable by its importers). Taking the apostrophe away again belongs to the same readability; this is an agent decision, accepted by the project coordinator, still to be confirmed by the owner in the release notes. Test: `tests/test_import_records.py`.

### 2026-11-03: the import record (new file, no result moves)

- **Before.** Only the parts import remembered a file name (and a short checksum), as one text for the whole library.
- **Now.** Every applied import writes `imports/records.json` (see `docs/FILE_FORMAT.md`).
- **What moves.** Nothing. The file is left out of a project that has no import, the model hash does not cover it (`layout.model_hash` skips it), and no output file carries it: a project with and without it gives the same hash and the same bytes. `tests/test_import_records.py` checks the hash and the manifest of the outputs.
- **Why.** Requirement R14 of the audit: a data link has a source, a checksum and a way to see that the source changed.
- **Agreed.** Owner, D-193 (no time and no operator in project data, so the record has none).

Next: [the changelog](../CHANGELOG.md), [the decisions](DECISIONS.md), [the developer notes on the tools](developer/tools.md)
