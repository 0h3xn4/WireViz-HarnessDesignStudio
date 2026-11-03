# Record what was built

This page shows how a technician writes down what was really built and measured (serial and lot numbers, the cut and strip lengths, the crimp tool, who built and who inspected, the result of each test), how those records are read into the project, compared with the design and the test limits, and printed in an as-built report. Use it at the bench, when the harness has been built and tested, and for a review of what was built.

> **New in the transparency work, stage S9 (decisions D-191, D-193; requirement R6).** The build workbook used to be write-only: what was typed into it was never read back. The records are kept in a new optional file, `asbuilt/records.json`. A project that has none is saved, hashed and exported byte for byte as before. **The tool never says that a harness passed and never signs anything off:** a value is *within its limit*, *out of its limit*, *not compared* or *missing*, and a value that is out of its limit stays so until a person records something else. The steps in the app are described from the program's texts and its tests; the program was not watched on a screen while this page was written. The commands were run, and the output is what they printed.

## Contents

- [What is recorded](#what-is-recorded)
- [Before you start](#before-you-start)
- [1. Write the sheet to fill in](#1-write-the-sheet-to-fill-in)
- [2. Fill it in](#2-fill-it-in)
- [3. Read it back](#3-read-it-back)
- [4. See what is missing and what is out of its limit](#4-see-what-is-missing-and-what-is-out-of-its-limit)
- [5. The as-built report](#5-the-as-built-report)
- [In the app](#in-the-app)
- [Who recorded it, and when](#who-recorded-it-and-when)
- [Common mistakes](#common-mistakes)

## What is recorded

One record for each thing a technician writes something down about. The record of a harness, a part, a wire, a connector, a pin or a test:

| Kind | `Item` in the sheet | What can be recorded |
| --- | --- | --- |
| harness | the harness ID | serial number(s), who built it, who inspected it, notes, a non-conformance |
| part | the part ID | the lot or batch of that part in this harness: the wire parts and connector parts the harness uses |
| wire | the wire ID | the cut length (m) and the strip length at each end (mm), as built; serial number(s); notes, a non-conformance |
| connector | the connector ID | serial number(s), notes, a non-conformance |
| pin | `CONNECTOR.PIN` | the crimp tool and its calibration ID, who built it |
| test | the test number of the Tests sheet (`T001`) | the result (`pass` or `fail`, as the person wrote it), the measured continuity resistance (ohm) or insulation resistance (Mohm), the test voltage that was applied (V), notes, a non-conformance |

Names of people are **text you type**; the tool does not authenticate anyone. The record holds no time and no user name: when the project keeps a change journal, the journal says who saved the records and when. The units are in the headings of the sheet and in the names of the fields (`cut_length_m`, `strip_a_mm`, `continuity_ohm`, `isolation_mohm`, `test_voltage_v`).

## Before you start

- A generated project with the test limits set. The limits are the ones of the Tests sheet (`config/generation.json`: `test_continuity_max_ohm`, `test_isolation_min_mohm`, `test_isolation_voltage_v`, see [test limits](../models/test-limits.md)). Without them a measured value is recorded but *not compared*. The practice project of this page is the `flatsat` example, which has them:

```
harness-design-studio new flatsat-build --template flatsat
```

## 1. Write the sheet to fill in

```
harness-design-studio export-asbuilt flatsat-build asbuilt-sheet.csv --harness W001
```

```
84 rows written to asbuilt-sheet.csv. Fill in the as-built columns and read the sheet back with `import-asbuilt`.
```

Use `.xlsx` instead of `.csv` for an Excel sheet. The sheet has one row for each thing that can be recorded: the harness, each part lot, each wire (with the **designed** length and strip lengths beside the empty columns), each connector, each crimped pin that is in use, and each test of the Tests sheet (with its limit). Without `--harness` it holds every harness. The as-built columns are empty, or hold what is recorded already, so a sheet can be filled in again.

## 2. Fill it in

Fill the as-built columns at the bench (*Serial number*, *Lot*, *Cut length (m)*, *Strip A (mm)*, *Strip B (mm)*, *Crimp tool*, *Crimp tool calibration ID*, *Built by*, *Inspected by*, *Result*, *Continuity (ohm)*, *Isolation (Mohm)*, *Test voltage (V)*, *Notes*, *Non-conformance*). Leave a cell empty when there is nothing to say. Do not change the columns *Kind*, *Harness* and *Item*, which say what the row is about. Rows can be left out, and columns that are not needed can be left out too. A file that has only the columns you filled in is read the same way:

```
Kind,Harness,Item,Serial number,Lot,Cut length (m),Built by,Inspected by,Result,Continuity (ohm),Isolation (Mohm),Test voltage (V)
harness,W001,W001,SN-0042,,,A. Technician,B. Inspector,,,,
part,W001,EX-WIRE-SINGLE,,LOT-2611-A,,,,,,,
wire,W001,W001-001,,,"3,46",,,,,,
wire,W001,W001-002,,,3.45,,,,,,
test,W001,T001,,,,,,pass,0.4,,
test,W001,T002,,,,,,pass,1.4,,
test,W001,T019,,,,,,pass,,250,500
```

The unit of a number column is the one in its heading: `(m)`, `(mm)`, `(cm)`, `(in)` or `(ft)` for lengths, `(ohm)` or `(mOhm)`, `(Mohm)` or `(Gohm)`, `(V)` or `(kV)`. A heading that says no unit is read in the unit the tool keeps (m, mm, ohm, Mohm, V). A decimal comma (`"3,46"`) is read as a point, and the import says so.

## 3. Read it back

```
harness-design-studio import-asbuilt flatsat-build bench.csv --dry-run
```

```
Read 7 row(s) of as-built records from bench.csv (sha256 4bf79a8ba4a7).
Columns read: Kind -> kind, Harness -> harness, Item -> item, Serial number -> serial_numbers, Lot -> lot, Cut length (m) -> cut_length_m, Built by -> built_by, Inspected by -> inspected_by, Result -> result, Continuity (ohm) -> continuity_ohm, Isolation (Mohm) -> isolation_mohm, Test voltage (V) -> test_voltage_v
Converted, row 4: 3,46 m = 3.46 m
row 2: OK harness W001: serial number, built by, inspected by
row 3: OK part EX-WIRE-SINGLE: lot
row 4: OK wire W001-001: cut length (m)
row 5: OK wire W001-002: cut length (m)
row 6: OK test T001: result, continuity (ohm)
row 7: OK test T002: result, continuity (ohm)
row 8: OK test T019: result, isolation (Mohm), test voltage (V)
7 added, 0 changed, 0 unchanged, 0 refused, 0 left out (nothing recorded in them).
Dry run: nothing was changed.
```

The file of the example is the one of step 2, saved as `bench.csv`. The import echoes what it read, the columns it left out (with a warning), the values it converted and every row with its result, as the other imports do (`import-lengths`, `import-build-data`). **If a row is refused, nothing is changed**: a row about a harness, wire, connector, pin or test that the design does not have, a test whose type or wire is not the one the design has now (the test list changed: write the sheet again), a result that is not `pass` or `fail`, a value that is not a number. An empty cell never clears what is recorded. Without `--dry-run` the records are kept in `asbuilt/records.json`, the file is recorded in `imports/records.json` (its name, SHA-256, rows, conversions; see [import data](import-data.md)), and the change is one undo step in the editor. The rows of the sheet that were not filled in (a sheet as it was handed out) are left out and counted. Importing the same sheet again changes nothing.

## 4. See what is missing and what is out of its limit

```
harness-design-studio asbuilt flatsat-build
```

```
W001: incomplete; 10 of 137 values recorded, 127 missing, 1 out of limit, 2 within limit, 1 different from the design, 0 not compared, 0 stale.
...
OUT OF LIMIT: W001 test T002: continuity resistance (ohm): 1.4 ohm measured, limit at most 1 ohm; recorded as passed: the tool does not accept it
DIFFERS FROM DESIGN: W001 wire W001-001: cut length (m): 3.46 m was built, 3.45 m is designed (+10 mm); no tolerance applied
MISSING: W001 part EX-MICROD-9-M: lot: to record
MISSING: W001 wire W001-003: cut length (m): to record
...
```

(The other harnesses say *not started*; the lines of the missing values are cut here.) The command ends with exit code 1 when a value is out of its limit, and with `--complete` also when a value is missing. `--json` prints the report as one document. What it says:

- **Missing**: what the sheet asks of a harness that has records and nobody recorded: its serial number and the names of who built and inspected it, the lot of each wire part and connector part, the cut length of every wire (and the strip lengths of the wires that have them in the design), the crimp tool and its calibration ID for every crimped pin in use, and the result and the measured value of every test. A harness with **no** record is *not started*: nothing is missing from it.
- **Out of limit**: the measured value is on the wrong side of the limit of the project (a continuity resistance above its limit, an insulation resistance below its limit), or the person who tested wrote `fail`. The report gives the actual value, the limit and the margin. A result `pass` written beside a value that is out of its limit does not change that: the line says so.
- **Within limit**, **not compared** (the limit is not set in the project: the tool does not make one up).
- **Differs from design**: a cut length, a strip length or a test voltage that is not the designed value, with the difference. **The tool applies no tolerance**; whether 10 mm too long is acceptable is for a person.
- **Stale record**: the record is about something the design no longer has.

`explain flatsat-build W001.T002` shows how one measured value was compared (kind `asbuilt-result`: the measured value and where it is recorded, the limit and its key, the margin and the check); [as-built results](../models/asbuilt.md) is the page of the model.

## 5. The as-built report

`export` writes two more files **only when the project has as-built records**: `outputs/system/asbuilt_report.md` (to print) and `outputs/system/asbuilt_report.csv` (the same lines for a spreadsheet), and the build workbook of a harness that has records has an extra sheet **As-built** before *About*. A project without records writes the files it always wrote, byte for byte (the output hashes are identical). The outputs are out of date, and the editor says so, when the records changed after they were written, although the design did not. The report says in its first lines that it is not a sign-off and does not say that a harness is compliant; it lists the summary of each harness, then the values out of their limit, missing, different from the design, stale and not compared, and the notes and non-conformances.

## In the app

The AIT engineer role ([choose your role](choose-your-role.md)) lists the area **As-built** on the rail; the other roles reach it with **Go > Go to As-built** (not listed for the Systems and Electrical engineer: use Ctrl+K) and the AIT engineer's Next step page has the button **As-built records…**. The page shows the number of records, a table of the values that need attention (out of limit, stale, different from the design, missing), a box **Show every value**, and two buttons: **Import the filled-in sheet…** and **Save the sheet to fill in…**. The same two are in **File > Import > Import as-built sheet…** and **File > Save the as-built sheet…**. An import is one undo step; a row the design cannot take is named and nothing is changed.

## Who recorded it, and when

The records hold no time and no user name. If the project keeps a change journal (`journal DIR`), each record that is added or changed is an entry of kind `asbuilt` with the author (`--author`, `HARNESS_AUTHOR`, the name Git has, the user of the computer), the time (UTC) and the old and new values; more than 25 records created in one save are one entry. A non-conformance or a note you write in a sheet is part of the record. To say that a deviation of the **design** was accepted, use the tool's own mechanism ([override and keep a history](override-and-keep-a-history.md)); an as-built value that is out of its limit is not a finding of a design rule.

## Common mistakes

- **Editing the cells of the build workbook and expecting the tool to read them.** It does not: write the sheet with `export-asbuilt`, fill that in, and import it.
- **A sheet written before the design changed.** A test number can mean something else after a change; the import refuses the row and says what the design has now. Write the sheet again; it holds what is recorded already.
- **Reading a green row as a pass.** *Within limit* says a number is inside the limit of the project, which is a number the project set (and, while its file is a placeholder, one that nobody reviewed). It does not say that the harness is good.
- **Typing `>200` for an insulation value.** A cell must be a number; a value the instrument shows as *greater than* is written as the number it showed, and the note says what the instrument said.

Next: [follow the workflow](follow-the-workflow.md), [as-built results](../models/asbuilt.md), [enter the build data](enter-the-build-data.md), [import data](import-data.md), [export the outputs](export-the-outputs.md).
