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

Never edit a generated file by hand. Change its source (or the program) and run the command. A test fails while the file is stale. All commands run from the `HarnessDesignStudio/` folder with the development environment active ([`setup-and-tests.md`](setup-and-tests.md)). The first seven commands below were run on a clean checkout: each printed a line about what it wrote (the last three also print a summary) and left `git status` clean.

| File | Source | Regenerate | Test that fails if stale |
| --- | --- | --- | --- |
| `docs/RULES.md` | the rule registry in `core/drc/` | `python -m tools.gen_rule_docs` | `test_docs.py::test_rule_reference_is_up_to_date` |
| `docs/CLI.md` | the `harness-design-studio` argument parser and the examples in `tools/gen_cli_docs.py` | `python -m tools.gen_cli_docs` | `test_docs.py::test_cli_reference_is_up_to_date` |
| `src/harness_design_studio/resources/guide/index.html` (the **F1** guide) | `docs/guide/USER_GUIDE.md` | `python -m tools.build_guide` | `test_docs.py::test_guide_html_is_up_to_date` |
| the example projects in `src/harness_design_studio/resources/examples/projects/` | the editing functions and `tools/build_examples.py` | `python -m tools.build_examples` | `test_examples.py` |
| `compliance/compliance_matrix.csv` | `compliance/requirements/*.csv` and `compliance/assessment/*.csv` | `python -m tools.build_compliance_matrix` | `test_compliance_matrix.py` |
| `compliance/traceability.csv` | `docs/REQUIREMENTS.md` and the tests | `python -m tools.trace` | `test_trace.py` |
| `compliance/sdd_components.csv` | the module docstrings and imports | `python -m tools.gen_sdd_components` | `test_sdd_components.py` |
| `docs/ui/OUTPUT_HASHES_1.2.0.json` | the files the four packaged examples write, as made by release 1.2.0 (tag `v1.2.0`) | `python -m tools.output_hashes --write FILE` was run once, in a checkout of that tag | `test_output_hashes.py` compares the current tool with it. Do **not** regenerate it with a newer tool: it is the reference that shows a change left the written files alone ([`tools.md`](tools.md#checks-and-measurements)). |
| `compliance/metrics.json` | the source tree | `python -m tools.metrics --write` | none. It is a snapshot taken at a milestone; a run today gives different numbers, so run it only on purpose. |
| `compliance/requirements/*.csv` | the five standards (PDF) | `python -m tools.extract_requirements STANDARDS_FOLDER` | none. Needs the PDFs, which are not in the repository, and `pdftotext`. Not run for this page. |
| the `LICENSES` folder inside every package (the licence texts of the shipped runtime packages, of Inter and JetBrains Mono, and of the icons) | the installed runtime packages and the bundled fonts | `python -m tools.collect_licences DEST` (the package builds call it) | `test_installers.py`, `test_packages_windows.py`, `test_ui_settings.py` (the texts the About page shows are the same strings). The build fails when a text is missing |
| the numbers in `docs/ui/PERF_BASELINE.md` | measurements on the flatsat example and the stress project | `python -m tools.ui_perf` and `python -m tools.bench_gui`, run by hand; the page is written by hand | none. Timings depend on the machine; say which machine, and compare only runs on one machine |
| `dist/release-docs/*` (SBOM, licence report, SCF, `SHA256SUMS`, release report) | the build | `python -m tools.gen_sbom`, `python -m tools.gen_scf`, `python -m tools.release_check` | not committed; made at release time ([`release.md`](release.md)) |

The tutorial `docs/GETTING_STARTED.md` is not generated, but `test_docs.py` runs its commands and compares the model hash it quotes. When what the tutorial prints changes, change the text (and the pictures) in the same commit.

`docs/FLATSAT_EXAMPLE.md` is checked against the `flatsat` example by `test_examples.py`: the counts and the per-harness wire numbers must match.

## Pictures

| Pictures | Made by | Notes |
| --- | --- | --- |
| `docs/ux/qt/*.png` (the editor) | `QT_QPA_PLATFORM=offscreen python -m tools.gui_screenshots` | 26 pictures at 1440 x 900 (light theme): 01 to 13 show the built-in sample (tour, Guided and Expert, connecting, problems, import preview, delete, waiver, palette, dark theme, 150 %); 14 and up show the flatsat example (project tree and inspector, Harness, Lists, Checks, engineering values, plans out of date, export window, released locks, Releases, new revision, new project, import wizard, release dialog). The script waits for the design rule check and for messages to go away, so it takes about a minute. The project path in the status bar is a fixed folder under the system temp folder, so that runs match. In repeated runs on the machine used, 24 of the 26 files came out identical every time; 06 and 07 now and then differ by about a hundred pixels of one link route. Check `git diff --stat` and keep only meaningful changes. The status bar shows the time of the last check, so every file differs from the committed one by a few pixels on every run; only `02-guided-main.png` is used by a document (the tutorial), and it was redone for 1.6.0, the other files were left as made by 1.3.0. |
| `docs/ui/screenshots/before/*.png` and `after/*.png` (the UI overhaul: release 1.2.0 and 1.3.0) | `QT_QPA_PLATFORM=offscreen python -m tools.ui_screenshots OUT` (`OUT` is `docs/ui/screenshots/after`; never run it without a folder, it would overwrite `before`) | Every area, tab, panel, menu and dialog on the flatsat example at 1440 x 900, plus narrow, wide, scaled, empty and stress variants, each in the light and the dark theme (`_light`, `_dark` in the name): 87 files in `before`, 103 in `after` when this page was checked. The script runs each theme and part in a process of its own; how long it takes was not timed for this page. `before` is the record of 1.2.0 made with that version's editor: do not refresh it. The comparison text is [`../ui/BEFORE_AFTER.md`](../ui/BEFORE_AFTER.md) (not generated; edit it when `after` changes). |
| `docs/img/flatsat-overview.png`, `flatsat-focus.png` | `QT_QPA_PLATFORM=offscreen python -m tools.flatsat_screenshots` | The diagram only (the docks are hidden), 1600 x 1000 window, legend open. Two runs gave identical files. |
| `docs/img/edit-wire-tab.png`, `docs/img/devices-tab.png`, `docs/img/connectors-tab.png` | `QT_QPA_PLATFORM=offscreen python -m tools.tab_screenshots` | The whole window (1760 x 1000, light theme): the first two on the flatsat example, for `user-manual/edit-a-wire.md` and `user-manual/define-a-device.md`; the third on a harness made by hand in a new project, for `user-manual/build-a-harness-by-hand.md`. Redraw them when the tab changes. |
| `docs/img/w001-drawing.png`, `docs/img/block-diagram.png` (the tutorial) | no script in the repository | They are the exported SVG sheets of the tutorial project, rendered to PNG with Qt's SVG renderer and cropped. They carry the tool version and the model hash of the tutorial, so redo them when the version or the hash changes (they were redone for 1.6.0, hash `a7fa21787017`). To redo them: run the first three commands of the tutorial and `export` in a scratch folder (`new wheel-link --template first-steps`, `generate`, `export`); render `outputs/harnesses/W001/drawing_A3_s1.svg` and `outputs/system/block_diagram.svg` offscreen (`QT_QPA_PLATFORM=offscreen`) with `QSvgRenderer` into a 2382 x 1684 image (the A3 sheet at about 5.67 pixels per millimetre) on a white ground; the SVG names `Courier New, Courier, monospace`, which Qt does not map by itself, so render a copy of the file with `font-family="Liberation Mono"` (any metric-compatible monospace face); keep the harness sheet whole and crop the block diagram to its content (the sheet border left out, about 734 x 639 pixels). Check that the version and the hash at the bottom of the drawing equal the ones the tutorial prints. |
| `docs/ux/screens/*.png` (the HTML prototype, history) | `python -m tools.ux_screenshots` (needs Playwright) | Kept as history. Do not refresh. |

The numbers in the notes of the first row (how many files were identical between runs) were measured with an earlier editor and were not measured again for the interface of 1.3.0. There are no pictures of the generate preview and the wire colours window.

## Add or change a page

1. **Where.** Pages of the tool go in `HarnessDesignStudio/docs/`. Their names are UPPER_CASE (`GETTING_STARTED.md`). The sub-folders `user-manual/` and `developer/` use lower-case words joined by hyphens. Do not create a name that differs from an existing one only by case.
2. **Shape.** The first sentence says what the page is for. A page of more than about 100 lines gets a `## Contents` list of links right after that sentence. The last line is `Next: [..](..), [..](..)`. See [Style rules](#style-rules).
3. **Link it.** Add the page to the index of its folder (`docs/README.md`, `docs/user-manual/README.md` or `docs/developer/README.md`). Link a hard term the first time you use it to [`GLOSSARY.md`](../GLOSSARY.md) and add the term there if it is missing.
4. **Commands and output.** Run every command you show, in a scratch folder, and paste the real output. Output that depends on the machine (a model hash, a date) is marked as such.
5. **Anchors.** GitHub makes a heading's anchor by lower-casing the text, dropping punctuation and backticks, and replacing spaces with hyphens: `## 2. Add units` is `#2-add-units`. A link to a heading that you rename breaks. Search for the old anchor before you rename: `grep -rn "old-anchor" --include=*.md .`.
6. **Check.** Run the two checks in the next section.
7. **If the page describes the program,** check the button and menu names against `gui/strings.py` and `gui/main_window.py`, the names of the areas and tabs against `gui/areas.py`, and the command names and options against `harness-design-studio COMMAND --help`.
8. **Things only on `master`.** If a page uses something that is not in the latest release yet (it is listed under `## Unreleased` in [`../../CHANGELOG.md`](../../CHANGELOG.md)), say so on the page. Where a page keeps a note for people who have the 0.1.0 packages, say "not in the 0.1.0 packages".

To change the in-app guide, edit `docs/guide/USER_GUIDE.md` and run `python -m tools.build_guide`. Keep paragraphs under 700 characters, name only buttons that exist, and document every new command in it (`test_docs.py` checks all three).

## Check the links

**1. The project's test** (every relative link and anchor in `README.md`, `CLAUDE.md`, `CHANGELOG.md` and every Markdown file under `docs/`, sub-folders included, and in the templates' `README.md`; see [`setup-and-tests.md`](setup-and-tests.md#4-the-tests-that-read-the-documents)):

```
pytest -q tests/test_docs_links.py tests/test_docs.py
```

**2. The offline link checker** `lychee` over every Markdown file, from the repository root. It also covers the files the test does not read: the compliance records, `CONTRIBUTING.md` and the Markdown files at the repository root. Download the Linux release of [lychee](https://github.com/lycheeverse/lychee/releases) (this page was checked with version 0.24.2), then:

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
- Say "not in the 0.1.0 packages" for anything that 0.1.0 lacks and keep that note only where it still helps someone who has 0.1.0 installed. Say "not in the latest release yet" for anything that is only under `## Unreleased`.
- The packages hold the documents as they were at the tag: the in-app guide (`docs/guide/USER_GUIDE.md`, built into the package) and `packaging/ubuntu/README.txt` are not updated by a later change on `master` until the next release. The 1.0.0 packages were built from commit `0c6a96a`, the 1.3.0 packages from `e7cf531` (tag `v1.3.0`), the 1.4.0 packages from `1427aad` (tag `v1.4.0`), the 1.5.0 packages from `4365368` (tag `v1.5.0`) and the 1.6.0 packages from `21f4716` (tag `v1.6.0`); the pages written after those commits (for example the publication record) are on `master` only.
- Numbers that appear in many pages (the count of design rules, the count of examples, the exit codes) are easy to leave stale: after a change, search the documents for the old number (for example, search for the old number of design rules when a rule is added).
- GitHub Markdown only: no HTML, no extensions that GitHub does not render.
- A fenced `python` block is checked by `ruff format --check .` (CI and the release check run it). Write it in ruff's layout or run `ruff format .` on the page.

## Documents that are not ours

The WireViz documents (`docs/*.md` at the repository root, `tutorial/`, `examples/`, `src/wireviz/`) belong to upstream. Do not edit them to describe Harness Design Studio. The README of WireViz is kept twice, and refreshing it is described in [`upstream-sync.md`](upstream-sync.md).

Next: [upstream sync](upstream-sync.md), [tools](tools.md), [release](release.md)
