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

### 2026-11-10: version 1.17.1rc1, a longer version string (the stored hashes are written again; nothing else changes)

- **Before.** The stored hashes (`docs/ui/OUTPUT_HASHES_BASELINE.json`, `tests/fixtures/numbers/snapshot.json`, `tests/fixtures/migration/hashes.json`) were made with a six-character version (`BASE_VERSION` 1.10.0), and the comparison replaced the stamp of 1.17.0 with it.
- **Now.** The release candidate `1.17.1rc1` has nine characters. The comparison cannot replace a stamp of another length (a PDF stores byte offsets), so the three files were written again with `1.17.1rc1`, and `BASE_VERSION` is `1.17.1rc1`.
- **Why.** The first release made by the signing workflow is a release candidate (the owner, 2026-11-10, D-218 and D-219).
- **What moved.** Only the version stamp and the hashes that include it (the model hash, and the SHA-256 of each written file). The diff of the three files holds no other change: no number, no finding, no text.

### 2026-11-05: the written block diagram shows the looks of the devices (a written file changes on purpose, for every project)

- **Before.** Each card of `system/block_diagram.svg` and `.pdf` (and of the SVG, PDF and PNG of Export diagram) was a white box with the ID and the name, for example, for the device `OBC` of the `mini3` sample:

  ```
  <rect x="10" y="22" width="44" height="12" fill="#ffffff" stroke="#000000" stroke-width="0.4"/>
  <text x="11.5" y="26.6" font-size="3" font-weight="bold" ...>OBC</text>
  <text x="11.5" y="31" font-size="2.4" ...>On-board computer</text>
  ```
- **Now.** Each card has a band down the left edge in the colour of the family of the device and a badge with the picture of its kind in the shape of the family (the looks the window has, [telling devices apart](user-manual/telling-devices-apart.md)), and the text starts to the right of the badge. The same card:

  ```
  <rect x="10" y="22" width="44" height="12" fill="#ffffff" stroke="#000000" stroke-width="0.4"/>
  <path d="M 10.2 22.2 L 11.6 22.2 L 11.6 33.8 L 10.2 33.8 Z" fill="#3730c9"/>
  <path d="M 14.4 24.5 L 18.6 24.5 C 19.373 24.5 20 25.127 ... Z" fill="#3730c9"/>
  <path d="M 15.547 26.701 L 17.453 26.701 ... " fill="none" stroke="#ffffff" stroke-width="0.433" stroke-linecap="round" stroke-linejoin="round"/>
  <text x="21.4" y="26.6" font-size="3" font-weight="bold" ...>OBC</text>
  <text x="21.4" y="31" font-size="2.4" ...>On-board computer</text>
  ```

  Below the diagram, right of the key to the lines, a key lists the kinds of device the project has, each with its picture (not while every device is a plain box). The colours are the light theme's (the file is paper). An ID is set smaller when it does not fit beside the badge (before, it was cut with `~`); a name is cut with `~` at about 21 characters (before, about 28). The page size, the lanes, the lines, their colours and dashes, the title block and the legend of the lines are unchanged. In the PDF the same shapes are path operators.
- **What moves.** Only `system/block_diagram.svg` and `system/block_diagram.pdf` of every project, and the `manifest.json` that lists their hash and size. Checked by building the outputs of the four examples with the tool before and after and comparing every file, `manifest.json` included: the only files that differ are those three. No number, no table, no other drawing (`harness_overview` keeps its plain boxes), no model hash and no project file moves. `python -m tools.numbers_snapshot --check tests/fixtures/numbers/snapshot.json` shows only the 22 block diagram entries of the 11 scenarios as different from the old file; no wire, finding or other file moved.
- **Renewed with the tools, not by hand.** `docs/ui/OUTPUT_HASHES_BASELINE.json` (8 lines: the SVG and the PDF of the 4 examples; `BASE_VERSION` stays 1.10.0), `tests/fixtures/numbers/snapshot.json` (22 lines), `tests/fixtures/outputs/mini3.json`, `sat15.json`, `sat15_full.json` (2 lines each) and the readable `tests/fixtures/outputs/mini3/system/block_diagram.svg`. No picture of a document embeds the written block diagram, so none was renewed.
- **Same bytes everywhere.** The looks come from the model alone. The pictures are path data made once (`core/pictograms.py`) with every coordinate rounded to four decimals when it is made, and the files write at most three decimals with no exponent and no locale, so a sine that differs in its last binary digit on Windows does not change a byte (`tests/test_block_diagram_looks.py`).
- **Why.** Owner decision on the device looks: *should the exported and written diagram show these looks too? yes, without breaking anything*.
- **Agreed.** The owner (the request above). The independent check (`verify --outputs`) still passes.

### 2026-11-05: a label in `diagram/marks.json` is stored as a place along its line (no result moves)

- **Before.** A label that a person dragged (the pill of an interface, the label of a connection, the connector box at an end) was stored as a free offset from its automatic place: `{"id": "interface:IF-1", "dx": 12.0, "dy": -6.0}` (releases 1.14.0 and 1.15.0).
- **Now.** It is stored as its place along the line it belongs to, a fraction of the length of the line: `{"id": "interface:IF-1", "t": 0.35}`. The bend of a connection and the vertical piece of a route stay offsets (`dx`, `dy`). A mark of the old form is still read; the editor turns it into `t` when the diagram is drawn and writes that at the next save. A tool older than 1.16.0 sets a mark with `t` aside as unreadable (the project still opens).
- **What moves.** Only the text of `diagram/marks.json`, and only in a project whose labels were dragged. The file is not part of the model hash, the baselines, the journal or any written output, so no number, no written file and no model hash changes (`tests/test_diagram_marks.py`, `tests/test_linepos.py`).
- **Why.** Owner feedback on 1.14.0: a label must stay on its line and keep its place when devices move.
- **Agreed.** The owner (the feedback above), within decision D-199.

### 2026-11-04: `export.json` states the unit of every number (a written file changes on purpose)

- **Before.** A number in `system/export.json` had a unit only when its name said so (`length_m`, `max_current_a`). `parts[].pin_count`, `parts[].conductors`, `harnesses[].accessories[].quantity`, the gauge `gauge_awg` and the keys of `parts[].ratings` had none; a reader of the file alone had to know them. A wire read `{"gauge_awg": 22, "length_m": 1.2, ...}` and the file said no more.
- **Now.** The same file with one more top-level object `field_units` (sorted with the other keys), for example `"harnesses[].wires[].length_m": "m"`, `"harnesses[].wires[].gauge_awg": "AWG"`, `"parts[].mass_per_m_g": "g/m"`, `"parts[].ratings.contact_current_a": "A"`, `"parts[].pin_count": "none (count of pins)"`. A rating a project names itself gets the unit its name ends in (`_a`, `_v`, `_c`, `_g`, `_mm`, `_ohm`) and otherwise `not stated (...)`. The units are SI-style symbols; `AWG` is the wire gauge; `none (...)` says what a number without a unit is.
- **What moves.** Only the file `system/export.json`: it gains `field_units` and nothing else changes in it (no field renamed or moved, `format_version` 1, the key `units` still holds the devices). Checked with the tool on the four examples and the eleven scenarios of the snapshot: every other written file is byte for byte as before, and the model hash is unchanged (the project is not changed). The baseline `docs/ui/OUTPUT_HASHES_BASELINE.json` (4 lines, `BASE_VERSION` stays 1.10.0 because the version string keeps its length), `tests/fixtures/numbers/snapshot.json` (11 lines) and the golden outputs (`tests/fixtures/outputs/*.json` and the readable `mini3/system/export.json`) are renewed for this reason.
- **Why.** Requirement R5 of the transparency work (D-191): the last gap in the units of the written files.
- **Agreed.** Not put to the owner: the change is additive and a reader of the file is not affected (D-195). The owner can ask for another name or a different form of the units.
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

### 2026-11-04: overrides and deviations are marked on the tests (no result moves)

- **Before.** An override or a deviation was marked on the checks, the drawing, the DRC report, the *Start here* sheet and the release comment, but not on the tests: `tests.csv` and the *Tests* sheet of the build workbook did not say that the wire under test had been set by hand or that an error of it had been accepted.
- **Now.** For a harness in which a test is about such a wire, `tests.csv` has a last column `Deviations` and the *Tests* sheet has the band *Overrides and deviations* above the table and the same last column; the as-built report adds `design: ...` to the note of a measured test line. The cell holds the field or the rule and the reason, never a name or a time.
- **What moves.** Nothing for an existing output: a project without an override and without a deviation writes the same bytes (`tests/test_output_hashes.py` and `tests/test_numbers_snapshot.py` are unchanged), and so does a harness of a project that has them but no test about a marked wire. No number, finding or limit changes.
- **Why.** The final audit (R7) found that a test sheet handed to a technician did not show that the wire had been overridden or the error accepted.
- **Agreed.** Within the transparency work (decisions D-191 (3) and D-193); the owner's review of this change is still to come. Test: `tests/test_deviation_marks.py`.

Next: [the changelog](../CHANGELOG.md), [the decisions](DECISIONS.md), [the developer notes on the tools](developer/tools.md)
