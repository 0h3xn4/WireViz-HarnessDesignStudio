# Architecture for a new contributor

This page gives a new contributor the shape of the code and the rules to keep, in a few minutes, and points to the pages that hold the details.

## Contents

- [The picture](#the-picture)
- [Where things are](#where-things-are)
- [The rules](#the-rules)
- [Adding things](#adding-things)
- [Where to read more](#where-to-read-more)

## The picture

Harness Design Studio is a Python program with three layers inside `harness/src/harness_design_studio/`:

```
gui/   the editor (PySide6): draws the diagram and the panels; thin
cli/   the `harness` command: a thin shell over the same core
core/  everything else: the model, the rules, generation, outputs, change control
```

`gui` and `cli` use `core`. `core` never uses `gui`, `cli` or anything that talks to a network. A test checks this (`tests/test_architecture.py`, `tests/test_offline.py`).

The data flow, from left to right:

```
project folder (JSON) -> load -> model -> commands (edit, undo, redo)
                                       -> generate -> harnesses, with a reason for each choice
                                       -> checks and design rules -> findings
                                       -> outputs (SVG, PDF, CSV, XLSX, YAML, JSON), then an independent verifier
```

The project folder is the source of truth. Everything generated can be generated again.

## Where things are

The full, current layout of `core/` is in [`../ARCHITECTURE.md`](../ARCHITECTURE.md), section 2 (it was rewritten from the source tree), and in the generated component table [`compliance/sdd_components.csv`](../../compliance/sdd_components.csv). Do not copy it. A short map:

| Folder or file | What is in it |
| --- | --- |
| `core/model/` | The model objects (units, interfaces, connectors, wires, harnesses, parts, config). Immutable and strict. |
| `core/commands.py` | `History`: every change is a list of operations run as one transaction, with undo and redo. |
| `core/edit.py` | Pure functions that build those lists of operations for the diagram. |
| `core/io/` | Load, save (atomic writes), migrate. A damaged file is set aside and the rest of the project still loads. |
| `core/generate/` | Segmentation, wiring, pin allocation, sizing, lengths, mass, naming, explanations, the engine. |
| `core/verify.py` | The independent check of a generation. |
| `core/drc/` | The design rules and their report. |
| `core/outputs/` | The writers and the independent output verifier. |
| `core/vcs/` | Release, revisions, baselines, diff, change log. |
| `core/kicad.py`, `core/library_import.py`, `core/imports.py` | The importers. |
| `cli/` | One module per group of commands; `main.py` builds the parser. |
| `gui/` | `controller.py` (the only thing that changes the project), `main_window.py` and `shell.py` (the window), `canvas.py`, the views (`project_tree.py`, `inspector.py`, `harness_view.py`, `lists_panel.py`, `checks_panel.py`, `releases_panel.py`), the dialogs (`export_dialog.py`, `import_wizard.py`, `new_project_dialog.py`, `config_dialog.py`), the shared parts (`tables.py`, `states.py`, `icons.py`, `theme.py`), `panels.py`, `dialogs.py`, `strings.py` (all UI text). [`../DESIGN.md`](../DESIGN.md) says how they fit. |
| `resources/` | The offline user guide (HTML), the example projects, the templates, fonts. |
| `tools/` | Maintenance scripts, outside the package ([`tools.md`](tools.md)). |
| `tests/` | The tests and their golden files ([`setup-and-tests.md`](setup-and-tests.md)). |

## The rules

These come from [`../../CLAUDE.md`](../../CLAUDE.md) and the decisions in [`../DECISIONS.md`](../DECISIONS.md). Each is checked by a test or by review.

1. **Clean-room.** Never copy or import code from `../src/wireviz` at the repository root. It is GPL-3.0 and a separate program (decision D-01). WireViz is only an export target: the tool writes WireViz-style YAML.
2. **Offline.** `core` must not import `gui`, `cli` or any network module. The tool never uses the network. A test blocks sockets and scans the imports.
3. **One way to change the model.** All changes go through commands and transactions (`evolve()` and `History.execute`). The GUI never changes the model directly.
4. **Deterministic.** Sort by stable IDs. No timestamps in generated data. Canonical JSON. The same design gives the same bytes. Do not put dates or history wording into provenance.
5. **Never invent standard values.** A derating factor, a current rating or a mass is a `PLACEHOLDER` (`null`) until a person supplies it, and results say so. Profiles fill only unset values and cite a requirement ID that exists. A rule that needs a number stays silent without it and is listed as *not checked*.
6. **Independent verifiers.** `core/verify.py` and `core/outputs/verify.py` must not import the generator or the writers. They derive their expectations from the project.
7. **No design data in logs.**
8. **All UI text in `gui/strings.py`.** New controls need an accessible name (`tests/test_accessibility.py` fails otherwise).
9. **Every new dependency** is recorded with name, version and licence in `DECISIONS.md`.
10. **Tests first.** Every bug fix gets a regression test.
11. **Speed.** Keep edits under 100 ms at stress size; use the change delta, never rebuild the whole scene for a local change (`tests/test_gui_perf.py`).
12. **Say what is open.** Do not make the examples look reviewed; demo values stay `"placeholder": true` (D-129). Never claim compliance with a standard.

## Adding things

| You add | Do |
| --- | --- |
| A design rule | Write the check, register it in `RULES`, add a positive case to `POSITIVE` in `tests/test_drc.py`, then `python -m tools.gen_rule_docs`. If it needs a number, keep it silent without it and list it in `standard_rules.unchecked`. |
| A command line command | Add it under `cli/`, add its examples to `tools/gen_cli_docs.py`, document it in the user guide, then `python -m tools.gen_cli_docs` and `python -m tools.build_guide`. |
| An output file | Build it in `build_outputs`, add its check to `core/outputs/verify.py` with a mutation test, regenerate the goldens, document it in [`../OUTPUTS.md`](../OUTPUTS.md). |
| A change to an example | `python -m tools.build_examples`. If the tutorial prints something that changed, update `docs/GETTING_STARTED.md` and its pictures. |
| A module | Give it a docstring (a test fails without one), then `python -m tools.gen_sdd_components`. |

## Where to read more

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md): the stack choice, the layout, the key mechanisms (locks, explain, verifier, helper process for the rule check, recovery).
- [`../DECISIONS.md`](../DECISIONS.md): every decision with its reason.
- [`../SECURITY.md`](../SECURITY.md): what hostile input was considered and how it is handled.
- [`../FILE_FORMAT.md`](../FILE_FORMAT.md): the project files.
- [`../SPEC.md`](../SPEC.md) and [`../REQUIREMENTS.md`](../REQUIREMENTS.md): what the tool must do.

Next: [setup and tests](setup-and-tests.md), [docs maintenance](docs-maintenance.md)
