# Screen-reader pass (manual part of the accessibility audit, D-115)

The automated audit (`tests/test_accessibility.py`) checks names on controls, text size at every scale, keyboard reach and the canvas announcement. It cannot check what a screen reader says. This pass does, with a person using **Orca** on Ubuntu 24.04. Known limit (D-76, D-118, UX.md Q15): the canvas items are not exposed one by one; the **Interfaces** and **Units** tables and the **project tree** are the item-by-item accessible views (the *Outline* tab and the bottom tabs of the editor of 1.0.0 are gone; the window of 1.3.0 is described in [`../UX.md`](../UX.md#14-the-ui-overhaul-version-130-october-2026)). This pass judges whether those views are enough, and records what is not. The table of items was rewritten for the interface of 1.3.0 from the program text (`gui/areas.py`, `gui/main_window.py`); it has not been run by a person, and nobody has tried a screen reader on the Windows package (macOS is not supported since 1.6.0, D-168).

## Set up
1. Install the build under test; record the version (`harness-design-studio --version`) and the model hash of the sample project on the result sheet.
2. Turn Orca on (Super+Alt+S). Start the editor from the application menu. Use a scaling of 100 % first, then 200 %.
3. Use only the keyboard. Do not look at the screen if the tester normally works without it. Open the sample project that the first start offers, or `harness-design-studio new` a project from an example.

## What to try (one row per item on the result sheet)
| # | Item | Pass when |
| --- | --- | --- |
| 1 | Start the editor | The window title and the first focus are announced; the tour or the empty state is readable |
| 2 | Move between the areas of the navigation rail (Home, Model, Checks, Drawings, Outputs, Revisions, Settings; Ctrl+7 opens Home and Ctrl+, Settings), the main tabs (Diagram, Harness, Lists, Checks, Releases, Devices; Ctrl+1 to Ctrl+6), the left panel (Project, Units, Interfaces), the right panel (Inspector, Why, Problems) and the Problems panel at the bottom (Ctrl+Shift+M); F6 moves between the panels | Each area and tab name is announced; focus order is logical |
| 3 | Interfaces and Units tables (Ctrl+Shift+T, Ctrl+Shift+J) | Rows and column headers are announced; a row can be selected and a cell edited from the keyboard (Enter edits, Esc cancels) |
| 4 | Project tree | Units, interfaces and harnesses can be walked item by item; the selection is announced |
| 5 | Diagram (canvas) | The announcement of unit and interface counts and of the selection is understandable; Tab and Enter move between units and links; what is missing is written down |
| 6 | Add a unit and an interface | The dialogs have named fields; errors are announced, not only coloured |
| 7 | Generate the plans (the Generate step of the top bar) | The preview dialog can be read and confirmed; the report is readable; the state of the three steps Generate, Check and Release is announced |
| 8 | Problems panel (Ctrl+Shift+M) and the Problems tab of the inspector | Each finding is announced with severity, rule, object and message (the cards of the inspector's tab also name the requirement ID); a finding can be opened from the keyboard |
| 9 | Release dialog (the Release step) | Every field and button has a name; the consequence of release is read out |
| 10 | Command palette (Ctrl+K) | Typing a command or an ID is announced; results can be chosen from the keyboard |
| 11 | Undo and redo | Their effect is announced or visible in a readable place |
| 12 | Colour not alone | Everything shown by colour (category, status, severity) is also available as text |
| 13 | Scaling 200 % (Settings > Appearance > interface size, or View > Interface size) | No text is cut off; controls are still reachable |
| 14 | Settings page (Ctrl+,): the sections Appearance, Editing, Project, Keyboard shortcuts, About, Licences | The section list and every control are announced with their names; a setting that is changed is applied and its new value can be read |
| 15 | Outputs: the list of exported files | Each file is announced with its state (matches the export, changed since, missing, not in the export) as a word, not only a colour, and with its SHA-256 |

## Result sheet
Copy this block for each tester and build.

```
Tester (role, experience with Orca):
Build (version, model hash):
Date:
Item | Pass / partly / fail | What was announced, what was missing
1  |
2  |
...
Blocking barriers (a task that cannot be done):
Other remarks:
```

## After the pass
- Each fail or partly is a problem report (`compliance/docs/PROBLEM_REPORTING.md`) with the item number, the screen-reader output, and the severity.
- Update UX.md Q15 and D-115 with the result and the date. Do not mark the audit done while a blocking barrier is open.
- Record the pass in `compliance/docs/SValP_SVS.md` under VAL-07 next to the usability sessions.
