# Screen-reader pass (manual part of the accessibility audit, D-115)

The automated audit (`tests/test_accessibility.py`) checks names on controls, text size at every scale, keyboard reach and the canvas announcement. It cannot check what a screen reader says. This pass does, with a person using **Orca** on Ubuntu 24.04. Known limit (D-76, D-118, UX.md Q15): the canvas items are not exposed one by one; the **Interface table** and the **Outline** tab are the item-by-item accessible views. This pass judges whether those views are enough, and records what is not.

## Set up
1. Install the build under test; record the version (`harness --version`) and the model hash of the sample project on the result sheet.
2. Turn Orca on (Super+Alt+S). Start the editor from the application menu. Use a scaling of 100 % first, then 200 %.
3. Use only the keyboard. Do not look at the screen if the tester normally works without it. Open the sample project that the first start offers, or `harness new` a project from an example.

## What to try (one row per item on the result sheet)
| # | Item | Pass when |
| --- | --- | --- |
| 1 | Start the editor | The window title and the first focus are announced; the tour or the empty state is readable |
| 2 | Move between the tabs: the main tabs (Diagram, Harness, Lists, Checks, Releases; Ctrl+1 to Ctrl+5), the right panel (Inspector, Why, Problems) and the bottom tabs (Problems, To-do, Interface table, Harness plans, Outline); F6 moves between the panels | Each tab name is announced; focus order is logical |
| 3 | Interface table | Rows and column headers are announced; a row can be selected and edited from the keyboard |
| 4 | Outline tab | Units, interfaces and harnesses can be walked item by item; the selection is announced |
| 5 | Diagram (canvas) | The announcement of unit and interface counts and of the selection is understandable; Tab and Enter move between units and links; what is missing is written down |
| 6 | Add a unit and an interface | The dialogs have named fields; errors are announced, not only coloured |
| 7 | Generate the plans | The preview dialog can be read and confirmed; the report is readable |
| 8 | Problems panel | Each finding is announced with severity and the requirement ID; a finding can be opened from the keyboard |
| 9 | Release dialog | Every field and button has a name; the consequence of release is read out |
| 10 | Command palette (Ctrl+K) | Typing a command or an ID is announced; results can be chosen from the keyboard |
| 11 | Undo and redo | Their effect is announced or visible in a readable place |
| 12 | Colour not alone | Everything shown by colour (category, status, severity) is also available as text |
| 13 | Scaling 200 % | No text is cut off; controls are still reachable |

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
