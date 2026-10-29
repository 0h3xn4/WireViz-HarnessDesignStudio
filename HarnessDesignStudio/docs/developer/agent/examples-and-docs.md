# Examples, templates, documentation and the compliance set: notes for agents

These sections were moved word for word from [`CLAUDE.md`](../../../CLAUDE.md) on 2026-10-29 (decision D-182); only this introduction is new. Read them when you change an example project, a template, a document that a test reads, or the compliance files.

## Examples, templates and documentation
`core/templates.py` (`create_project`, `copy_import_templates`), `cli/start.py` (`harness-design-studio new`, `harness-design-studio templates`), `resources/examples/` (`projects/` built by `tools/build_examples.py`; `templates/` written by hand: CSV, netlist, CI scripts, review checklist, demo values), `resources.examples_path()` (also inside PyInstaller). Docs for newcomers: `docs/LEARNING_PATH.md`, `GETTING_STARTED.md`, `CONCEPTS.md`, `INSTALL.md`, `CHEATSHEET.md`, `FAQ.md`, `CLI.md`; map in `docs/README.md`. Examples: `blank`, `first-steps`, `minimal-satellite`, `small-satellite`, `flatsat` (generated, with EXAMPLE numbers; walkthrough `docs/FLATSAT_EXAMPLE.md`); the template `design-worksheet.md` is for planning on paper.
- Team use with Git (release 1.9, F-05): `new` writes a `.gitattributes` (`core/mergefix.py` `GITATTRIBUTES`, written once by `templates.create_project` and by `tools/build_examples.py`, shipped as `templates/ci/gitattributes`) that makes Git treat `generated/generation.json` as binary, and `merge-fix DIR` (`cli/merge.py`) keeps one side of that record, runs `generate` and `check`, and refuses when any other file is in conflict. It finds conflicts from markers and from the Git index (`core/vcs/gitindex.py`, read directly: the tool never starts `git`, `tests/test_security.py` forbids `subprocess`). `tests/test_merge_fix.py` makes real merges with `git`. `logical/links.json` (sequential IDs) and the change log still conflict by design (A-23, not fixed: a file-format change).
- A new CLI command needs an entry in `tools/gen_cli_docs.py` (group and examples) and in the user guide; a changed example needs `python -m tools.build_examples`.
- Demo values in the templates are for learning only, never engineering data, and stay `"placeholder": true` (D-129). Do not make the examples look reviewed.
- If you change what the tutorial prints (the example, the sizing, the drawings), update `docs/GETTING_STARTED.md` and `docs/img/` (a test checks the commands and the quoted model hash).

## Compliance audit (ECSS/ESCC)
`compliance/` (requirement lists, assessment, matrix, gap analysis, evidence, process documents), `core/standard_profiles.py` (optional value profiles, D-131), `core/drc/standard_rules.py` (rules that apply the supplied standards), `tools/extract_requirements.py`, `tools/build_compliance_matrix.py`, `tools/trace.py`, `tools/metrics.py`, `tools/gen_scf.py`.
- Never add a standard value as a default; profiles fill unset values only and cite a requirement ID that exists in `compliance/requirements` (a test checks it).
- A new rule that serves a requirement names it in `sources=`; a rule that needs a number stays silent without it and adds a line to `standard_rules.unchecked`.
- Rebuild after changing assessments: `python -m tools.build_compliance_matrix`, `python -m tools.trace`, and after adding or moving modules `python -m tools.gen_sdd_components` (every module needs a docstring); the outputs are checked for freshness by tests.

