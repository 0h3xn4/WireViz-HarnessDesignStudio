# The user interface before and after (release 1.2.0 and 1.3.0)

Pictures: [`screenshots/before/`](screenshots/before/) (1.2.0) and [`screenshots/after/`](screenshots/after/) (1.3.0), each in a light and a dark theme, made by `python -m tools.ui_screenshots OUT` of the same tool version that is shown (the flatsat example, 1440 x 900, offscreen). Numbers: [`PERF_BASELINE.md`](PERF_BASELINE.md). Decisions: D-150 to D-159 in [`../DECISIONS.md`](../DECISIONS.md). The brief is [`UI_OVERHAUL.md`](UI_OVERHAUL.md), the plan [`UI_OVERHAUL_PLAN.md`](UI_OVERHAUL_PLAN.md).

## What a person sees

| | Before (1.2.0) | After (1.3.0) |
|---|---|---|
| The whole window | [diagram, light](screenshots/before/01-diagram-selected-1440x900_light.png), [dark](screenshots/before/01-diagram-selected-1440x900_dark.png) | [diagram, light](screenshots/after/01-diagram-selected-1440x900_light.png), [dark](screenshots/after/01-diagram-selected-1440x900_dark.png) |
| Where things are | six tabs on top, two tool bars, status chips in several places | a navigation rail (Home, Model, Checks, Drawings, Outputs, Revisions, Settings), one top bar, a Problems panel and a status bar |
| The work flow | buttons Generate, Check, Export beside many others | three steps Generate, Check and Release, each with its state and what is next; released work is marked as locked, with a banner |
| Colours and fonts | IBM Carbon colours, IBM Plex | one token source (`gui/theme/tokens.py`), Inter and JetBrains Mono, both themes switch live (145 ms, was 950) and pass the contrast test |
| The first screen | the diagram | [the Model area](screenshots/after/50-first-start_light.png) with the example project and the tour (the same as before); [Home](screenshots/after/14-area-home_light.png) is one click away on the rail (Ctrl+7): the open project, recent projects, the examples |
| Interfaces | a table you could type into one cell at a time | [a spreadsheet](screenshots/after/08-left-interfaces-tab_light.png): paste a block from Excel, edit several rows at once, Enter and Esc; and a [Units table](screenshots/after/08b-left-units-tab_light.png) |
| Checks | results, and an inspector tab | the same, with a marker when they are out of date, and a [Problems panel](screenshots/after/16-problems-panel_light.png) that goes to the object of every finding |
| Drawings | [the drawing and its tables side by side](screenshots/before/03-tab-harness_light.png) | [the drawing across the top, the tables under it](screenshots/after/03-tab-harness_light.png) |
| Imports | two ways in | [one wizard](screenshots/after/31-dlg-import-wizard-file_light.png) for six kinds of file; a large file is read in the background |
| Outputs | [lists](screenshots/before/04-tab-lists_light.png) | [the lists and every exported file](screenshots/after/04-tab-lists_light.png) with its SHA-256 and whether it still matches the export |
| Revisions | [differences](screenshots/before/36-releases-compare_light.png) | [differences tinted by the kind of change, and what a release locks](screenshots/after/36-releases-compare_light.png) |
| Settings | View menu entries | [a page](screenshots/after/15-area-settings_light.png) with Appearance (theme, size, reduce motion), Editing, Project, [keyboard shortcuts](screenshots/after/15b-settings-shortcuts_light.png), [About](screenshots/after/15c-settings-about_light.png) and [licences](screenshots/after/15d-settings-licences_light.png) |
| Small windows | [1150 x 400](screenshots/before/41-diagram-1150x400_light.png) | [1150 x 400](screenshots/after/41-diagram-1150x400_light.png) (the rail shows icons only) |

## How it behaves (flatsat example; the stress project is 200 units and 2,000 interfaces)

| | Before | After |
|---|---|---|
| Start to first interactive window | about 1.0 s | about 1.0 s |
| Switch theme | 950 / 710 ms | 145 / 79 / 73 ms |
| An edit in the stress project with the rule check on | 10.7 to 12.7 s | 85 to 460 ms |
| Change while the interface table is open (stress project) | 11.5 s | 118 ms |
| Read a 20,000-row import file | the window stopped for 550 ms, then 280 ms more | the longest pause is about 110 ms; the file is read in the background |
| Change the interface size | 760 to 800 ms | 1.0 to 1.1 s (**worse**; Qt re-reads the style sheet of about 1,250 widgets; a wait cursor shows) |

## What did not change

The design model, the file format, the 34 design rules, the command line and every generated file. All 567 files that the four example projects write were compared one by one with those of release 1.2.0 and are identical apart from the version of the tool that they record (`tools/output_hashes.py`; `tests/test_output_hashes.py` repeats it on every test run).

## What was found on the way

- Every edit of a project with a very large rule check result waited about 11 s for two lookups that scanned every wire once per finding (D-154).
- A busy Python thread made every Python callback of the window slow (each call into Qt gives the interpreter away and waits to get it back); the import thread now asks for a short switch interval (D-156).
- The Tab key did nothing in the project panel's tab bar: a tab widget without a visible bar was still a Tab stop (D-159).
- After the Interfaces and the Units tab, the left panel did not return to its width (D-159).

## What is left, and why

- Changing the interface size takes about a second (D-158).
- The Devices tab is not replaced by a spreadsheet (its pin table already pastes and edits by keyboard), the generated wire list is not editable, a new interface is not typed into a row of the table (D-153).
- Generate and Export still show a modal progress window (the work is in a background thread, so the window stays alive; a progress bar in the status bar would replace it).
- The inspector's Problems tab counts to-do groups (28 in the flatsat example) while the Problems panel counts findings (75).
- The keyboard shortcuts are shown and not editable.
- The packages are not signed, a screen-reader pass was not made (waived, `compliance/DEVIATIONS.md`) and the keyboard test is automatic; no person has used the new interface yet.
