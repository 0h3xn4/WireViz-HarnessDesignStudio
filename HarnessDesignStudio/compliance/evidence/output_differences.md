# Differences in generated outputs during Phase 2

Each entry: commit, what changed in generated files (drawings, BOMs, reports) and why. Files not named were byte-identical to the baseline (`baseline_tests.txt`).

| Step | Changed | Why |
| --- | --- | --- |
| B-12/B-06 requirement citations | `system/drc_report.md` of mini3, sat15, sat15_full (and their digests in `tests/fixtures/outputs`); `tests/fixtures/drc/sat15.md`; `docs/RULES.md` | findings of rules that serve a standard requirement now end with `Requirement: <ID>`. Drawings, wire lists, BOMs, pinouts, labels and the model hash are unchanged. |
| B-01/B-02/B-03/B-04/B-05/B-11 rules (8 new rules, silent without their numbers) | `system/drc_report.md` of mini3, sat15, sat15_full: the line `Rules run: 22` is now `Rules run: 32`; `tests/fixtures/drc/sat15.md` the same; `docs/RULES.md` (8 new rows) | The new rules find nothing in the reference projects because none carries the optional numbers or ratings. Drawings, wire lists, BOMs, pinouts, labels, model hash: unchanged. |
| UX: provenance file | new file `system/provenance.json` in every output set (and its digest in the golden JSON files); `tests/fixtures/outputs/mini3/system/provenance.json` | UX/UI guidelines, provenance on every output. No existing file changes. |
| UX: requirement IDs as data | `system/drc_findings.csv` has a new last column `Requirement` | findings of rules that serve a standard requirement carry its ID. The DRC report text is byte-identical to before this step. |
| Library source and date (D-133) | every output file that carries the model hash in its stamp (the hash changed once because `library/manifest.json` has two more keys); `system/provenance.json` has `source` and `date` in `library`; mini3, sat15 and example project files | the manifest gained `source` and `date`. Content of drawings, lists and BOMs is otherwise unchanged. |
