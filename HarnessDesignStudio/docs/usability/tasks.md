# Task cards (read one at a time)

| Card | Task | Limit | Success when |
| --- | --- | --- | --- |
| T1 | Start a new project. Build a diagram with 5 units and 4 interfaces, then generate the harness plans. | 15 min | Plans exist and the participant can say what was generated; no manual opened |
| T2 | You want to connect two units but one is greyed out. Find out why and fix it. | 5 min | States the reason and fixes it |
| T3 | Make the power unit redundant and clear the warnings that appear. | 8 min | No open warnings, or a waiver with a sensible reason |
| T4 | Import `icd.csv` (it has two mistakes). | 8 min | Finds and understands both bad rows; one Undo reverts the import |
| T5 | Find every signal that reaches the connector `OBC1-J01`. | 30 s | Lists them from the Interfaces table or the Drawings area |
| T6 | Lock one pin, change a connector, generate again. | 10 min | Lock kept; understands the report |
| T7 | Release a harness. Then change the design. What happens, and can you release again? | 10 min | Understands "locked" or "out of date" and names the next step |
| T8 | Open `corrupt/`. Save what you can without touching the original. | 8 min | Salvaged copy saved; original untouched |

The cards name no buttons. In the Simple workspace (the first-run default of 1.7.0) a project opens on the Next step page and the Project tab, the Inspector and the Interfaces and Units tables are closed until **Show panels** (T5 uses one of them; Ctrl+Shift+T opens the Interfaces table). Do not tell the participant where things are; note what they do about it. The material for the tasks is made by `python -m tools.usability_setup` (README).
