# Documentation maintenance

This page shows which documents are generated and how to regenerate each one, how to add a page, and how to keep every link valid.

## Contents

- [Which documents are generated](#which-documents-are-generated)
- [Pictures](#pictures)
- [Add or change a page](#add-or-change-a-page)
- [Check the links](#check-the-links)
- [Style rules](#style-rules)
- [Documents that are not ours](#documents-that-are-not-ours)

## Which documents are generated

Never edit a generated file by hand. Change its source (or the program) and run the command. A test fails while the file is stale. All commands run from the `harness/` folder with the development environment active ([`setup-and-tests.md`](setup-and-tests.md)). The first seven commands below were run on a clean checkout: each printed nothing and left `git status` clean.

| File | Source | Regenerate | Test that fails if stale |
| --- | --- | --- | --- |
| `docs/RULES.md` | the rule registry in `core/drc/` | `python -m tools.gen_rule_docs` | `test_docs.py::test_rule_reference_is_up_to_date` |
| `docs/CLI.md` | the `harness` argument parser and the examples in `tools/gen_cli_docs.py` | `python -m tools.gen_cli_docs` | `test_docs.py::test_cli_reference_is_up_to_date` |
| `src/harness_design_studio/resources/guide/index.html` (the **F1** guide) | `docs/guide/USER_GUIDE.md` | `python -m tools.build_guide` | `test_docs.py::test_guide_html_is_up_to_date` |
| the example projects in `src/harness_design_studio/resources/examples/projects/` | the editing functions and `tools/build_examples.py` | `python -m tools.build_examples` | `test_examples.py` |
| `compliance/compliance_matrix.csv` | `compliance/requirements/*.csv` and `compliance/assessment/*.csv` | `python -m tools.build_compliance_matrix` | `test_compliance_matrix.py` |
| `compliance/traceability.csv` | `docs/REQUIREMENTS.md` and the tests | `python -m tools.trace` | `test_trace.py` |
| `compliance/sdd_components.csv` | the module docstrings and imports | `python -m tools.gen_sdd_components` | `test_sdd_components.py` |
| `compliance/metrics.json` | the source tree | `python -m tools.metrics --write` | none. It is a snapshot taken at a milestone; a run today gives different numbers, so run it only on purpose. |
| `compliance/requirements/*.csv` | the five standards (PDF) | `python -m tools.extract_requirements STANDARDS_FOLDER` | none. Needs the PDFs, which are not in the repository, and `pdftotext`. Not run for this page. |
| `dist/release-docs/*` (SBOM, licence report, SCF, `SHA256SUMS`, release report) | the build | `python -m tools.gen_sbom`, `python -m tools.gen_scf`, `python -m tools.release_check` | not committed; made at release time ([`release.md`](release.md)) |

The tutorial `docs/GETTING_STARTED.md` is not generated, but `test_docs.py` runs its commands and compares the model hash it quotes. When what the tutorial prints changes, change the text (and the pictures) in the same commit.

`docs/FLATSAT_EXAMPLE.md` is checked against the `flatsat` example by `test_examples.py`: the counts and the per-harness wire numbers must match.

## Pictures

| Pictures | Made by | Notes |
| --- | --- | --- |
| `docs/ux/qt/*.png` (the editor) | `QT_QPA_PLATFORM=offscreen python -m tools.gui_screenshots` | Takes about three seconds. On the machine used, two of the thirteen files (06 and 07) came out slightly different from the committed ones, so look at `git diff --stat` and keep only meaningful changes. |
| `docs/img/flatsat-overview.png`, `flatsat-focus.png` | `QT_QPA_PLATFORM=offscreen python -m tools.flatsat_screenshots` | Came out identical to the committed files. |
| `docs/img/w001-drawing.png`, `docs/img/block-diagram.png` (the tutorial) | no script in the repository | They are the exported SVG sheets of the tutorial project, rendered to PNG with Qt's SVG renderer and cropped. They carry the model hash of the tutorial, so redo them when the hash changes. |
| `docs/ux/screens/*.png` (the HTML prototype, history) | `python -m tools.ux_screenshots` (needs Playwright) | Kept as history. Do not refresh. |

Pictures of the harness plans tab, the generate preview, the release window and the wire colours window do not exist yet.

## Add or change a page

1. **Where.** Pages of the tool go in `harness/docs/`. Their names are UPPER_CASE (`GETTING_STARTED.md`). The sub-folders `user-manual/` and `developer/` use lower-case words joined by hyphens. Do not create a name that differs from an existing one only by case.
2. **Shape.** The first sentence says what the page is for. A page of more than about 100 lines gets a `## Contents` list of links right after that sentence. The last line is `Next: [..](..), [..](..)`. See [Style rules](#style-rules).
3. **Link it.** Add the page to the index of its folder (`docs/README.md`, `docs/user-manual/README.md` or `docs/developer/README.md`). Link a hard term the first time you use it to [`GLOSSARY.md`](../GLOSSARY.md) and add the term there if it is missing.
4. **Commands and output.** Run every command you show, in a scratch folder, and paste the real output. Output that depends on the machine (a model hash, a date) is marked as such.
5. **Anchors.** GitHub makes a heading's anchor by lower-casing the text, dropping punctuation and backticks, and replacing spaces with hyphens: `## 2. Add units` is `#2-add-units`. A link to a heading that you rename breaks. Search for the old anchor before you rename: `grep -rn "old-anchor" --include=*.md .`.
6. **Check.** Run the two checks in the next section.
7. **If the page describes the program,** check the button and menu names against `gui/strings.py` and `gui/main_window.py`, and the command names and options against `harness COMMAND --help`.
8. **Things only on `master`.** If a page uses something that is not in the 0.1.0 packages, say so on the page (see the `Unreleased` section of [`../../CHANGELOG.md`](../../CHANGELOG.md)).

To change the in-app guide, edit `docs/guide/USER_GUIDE.md` and run `python -m tools.build_guide`. Keep paragraphs under 700 characters, name only buttons that exist, and document every new command in it (`test_docs.py` checks all three).

## Check the links

**1. The project's test** (every relative link and anchor in the listed files; see [`setup-and-tests.md`](setup-and-tests.md#4-the-tests-that-read-the-documents)):

```
pytest -q tests/test_docs_links.py tests/test_docs.py
```

**2. The offline link checker** `lychee` over every Markdown file, from the repository root. It also covers the sub-folders, the root files and the compliance records, which the test does not. Download the Linux release of [lychee](https://github.com/lycheeverse/lychee/releases) (this page was checked with version 0.24.2), then:

```
lychee --offline --include-fragments --exclude-path compliance/requirements --exclude-path docs/upstream '**/*.md'
```

`--offline` checks only links inside the repository. `--include-fragments` also checks the `#anchor`. The two excluded paths are the extracted requirement lists and the untouched copy of the upstream README (whose relative links cannot resolve there on purpose). The command ends with a line like `🔍 1372 Total … 🚫 28 Errors` and lists each broken link with the file and the position. It exits with code 2 when there is a broken link. Fix the links, not the checker.

**3. External links** are not covered by either check, because the tool's documents otherwise need no network. Run `lychee --include-fragments --no-progress '**/*.md'` (without `--offline`) with the same excludes when you want to find dead web links. It was not run for this page.

## Style rules

For every page written for readers (not for the records in `compliance/`):

- Write for someone who knows a little Python and nothing about the tool or spacecraft engineering. Short sentences, plain words.
- One sentence at the top that says what the page is for. A copy-pasteable command for every step and the output you really get.
- Never claim compliance with a standard. Keep the wording of the records: "waived by the owner" accepts a deviation and does not meet the requirement.
- Never invent a feature, a value or a fact. If you could not check it, say so on the page.
- Mark steps that need the app, which cannot be run in an automatic test, so a reader knows what was driven and what was only read from the program text.
- Say "newer than the 0.1.0 packages" for anything that is only on `master`.
- GitHub Markdown only: no HTML, no extensions that GitHub does not render.

## Documents that are not ours

The WireViz documents (`docs/*.md` at the repository root, `tutorial/`, `examples/`, `src/wireviz/`) belong to upstream. Do not edit them to describe Harness Design Studio. The README of WireViz is kept twice, and refreshing it is described in [`upstream-sync.md`](upstream-sync.md).

Next: [upstream sync](upstream-sync.md), [tools](tools.md), [release](release.md)
