# Family-group codes and the tool's part classes (action A-16)

ECSS-Q-ST-30-11C Rev.2 ties each derating table to **family-group codes**: Table 6-10 (connectors) to 02-01, 02-02, 02-03, 02-07 and 02-09; Table 6-11 (RF connectors) to 02-05; the rating of wires and cables (6.32.4a) to 13-01 to 13-03. The standard supplied here does not say what each code stands for; that is defined in documents that were not supplied (A-18). The tool's part classes are `connector`, `contact`, `backshell`, `wire`, `sleeving` and `label` (`core/model/library.py`).

`family_group_mapping.csv` (next to this file) lists, for each tool part class and connector style of the example library, what the **supplied text states** and what it does not. Nothing in it was invented: a line that needs a parts engineer says so, and the last column is left empty for the entry.

## What can be said from the supplied text
- **Wires** (`wire`): the standard speaks of "Wires and cables" for 13-01 to 13-03. The class matches. Which of the three codes a wire belongs to is not stated, and the tool does not need it, because 6.32.4a gives the same two rules to all three (voltage 50 %, surface temperature 50 C below the manufacturer's maximum).
- **RF connectors**: Table 6-11 is for "connectors RF" (02-05). The developer proposes that the coaxial styles (SMA, TNC) are RF connectors; the supplied text does not list the styles. The tool already uses the RF power factor only with interface types of category `rf`.
- **Other connectors**: Table 6-10 covers five codes. Which tool connector style (D-sub, Micro-D, MDM, circular, Ethernet RJ45) falls under which code, or under none, is **not stated**. This is the part that needs a parts engineer. An RJ45 jack may be outside the scope of Table 6-10.
- **Contacts, backshells, sleeving, labels**: no derating table is named for them in clauses 6.11, 6.12 and 6.32.

## What the tool does today (deviation T-16)
The standard value profile applies the Table 6-10 factors to **every** connector and the wire factors to **every** wire, and the RF power factor to RF interfaces. That is conservative where a style is in scope and not justified where it is outside the scope. The report already says the rule serves the clause; it cannot say the part is in the family.

## What is needed from a person
For each connector style the project uses: the family-group code (from the document that defines the codes) or "outside the standard", entered in the last column of `family_group_mapping.csv`. With those entries the tool could apply Table 6-10 and Table 6-11 only to the styles that belong to them. That change is not made yet; it needs your decision after the entries exist.
