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

Next: [the changelog](../CHANGELOG.md), [the decisions](DECISIONS.md), [the developer notes on the tools](developer/tools.md)
