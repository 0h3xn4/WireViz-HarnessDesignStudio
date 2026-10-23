# Import data

This page shows how to bring data you already have into a project: a list of interfaces, your approved parts list, the lengths of the routes and (since 1.7.0) the build data of a technician, always with a preview first.

## Contents

- [Before you start](#before-you-start)
- [Interfaces from a table (app only)](#interfaces-from-a-table-app-only)
- [Approved parts list](#approved-parts-list)
- [Segment lengths](#segment-lengths)
- [Build data: strip lengths, contacts, accessories](#build-data-strip-lengths-contacts-accessories)
- [Other imports](#other-imports)
- [Where the library data come from](#where-the-library-data-come-from)
- [Common mistakes](#common-mistakes)

## Before you start

- You have a practice project: `harness-design-studio new wheel-link --template first-steps`.
- Starting files for every import are in the templates. Copy them once:

```
harness-design-studio templates my-templates
```

```
18 files written to my-templates. Start with my-templates/README.md.
```

(On a 0.1.0 package the command writes 14 files: `design-worksheet.md` is not in the 0.1.0 packages. The three files for the build data, `strip-lengths.csv`, `pin-contacts.csv` and `accessories.csv`, have been in the templates since 1.7.0.)

- Every import shows what it would do. In the app, **File > Import** starts one wizard for six kinds of file (interfaces, approved parts, segment lengths, the ampacity table, a device pinout and a KiCad netlist): choose the file, match the columns, read every row with its reason, then import. On the command line add `--dry-run`: the rows are listed and nothing changes. Run the command again without it to apply.
- Files can be CSV or TSV (commas, semicolons or tabs between columns; UTF-8), JSON (a list of flat records, as an export of a parts program writes it; since 1.4.0) or Excel (`.xlsx`, the first **visible** sheet, not the one that was active when the file was saved; the import says `Reading sheet 'Parts' (the first visible sheet of the workbook).`). A number with a decimal comma needs quotes (`"1,5"`) when commas separate the columns. At most 20,000 rows and 8 MB. Details: [`IMPORTS.md`](../IMPORTS.md).
- A CSV file with a quote that is never closed (or is followed by other text in the cell) is refused with its line number, and nothing is imported: `error: Line 2: unbalanced quote. A " opens a text that is never closed, or is followed by other text. Remove the stray quote or write it twice ("") inside a quoted cell. Nothing was imported.` (exit code 2).
- An import that would change something a **release froze** (a part, an interface type or a configuration value that a released harness uses) is blocked, in the preview and in the real run, with exit code 1 ([change a released harness](change-a-released-harness.md)).

## Interfaces from a table (app only)

Importing interfaces works in the app. There is no command for it. (GUI, not run: the steps are described from the program's code. The column names and messages are the program's.)

1. Open the project. Choose **File > Import > Import interfaces…** (Ctrl+Shift+I), or press Enter on **Interfaces** under **Imports** in the **Project** tab (the Simple workspace keeps that tab closed: use the menu, or **Show panels**). The **Import data** wizard opens with *Interfaces* chosen. It is the same wizard for the other kinds of file ([other imports](#other-imports)).
2. Press **Choose file…** and pick a `.csv`, `.tsv`, `.json` or `.xlsx` file. To import text instead, press **Paste table text instead…**: the older window opens, with a box for CSV text. Try `my-templates/interfaces.csv`:

```
id,type,from,to,redundancy
IF-010,RS-422,OBC1,PCDU1,nominal
IF-011,Primary power,PCDU1,OBC1,nominal
```

3. Press **Next**. Page 2, **Match the columns and check the first rows**, shows the **column matching** (Interface ID, Interface type, From unit, To unit, Redundancy). The tool guesses it from the headings; change a choice if it guessed wrong, and the rows are read again. `redundancy` is optional. A file of more than 1,500 rows is read in the background, with a progress line and **Cancel**, so the window does not stop.
4. Press **Next**. Page 3, **Conflicts and placeholders**, lists every row with its result and the reason, for example "Skipped: Unit 'RW9' does not exist", and says, for example, "1 of 2 rows can be imported; 1 have problems. Rows with a problem are skipped; the others are imported." **Only rows that need attention** hides the rows that are fine.
5. Press **Next**. Page 4, **Import**, says what will be imported. Press the button named after the import, for example **Import 1 row**. Rows with problems are skipped and the good rows are applied, as one undo step: **Undo** takes all of them back at once. For an Excel file the wizard names the sheet it read.

Rules for a row: the two units must exist already; `type` is the name or ID of an interface type (for example `RS-422`); each unit needs a free connector that can carry the type.

## Approved parts list

**From InvenTree (since 1.4.0).** Export the parts table of InvenTree as CSV, TSV, JSON or XLSX and import that file as it is: the `IPN` column is read as the part ID (the `ID` of InvenTree is a database number), `Name` or `Description` as the description, `MPN` as the part number, `Manufacturer`, `Weight` and `Category` as they are named; a category path such as `Connectors/D-Sub` is read as `connector` (a category the tool does not have is refused with its row). Nothing connects to an InvenTree server: the tool never uses the network. You still say what the approval values mean, as for any list.

The starter library has only example parts, none of them approved. Your programme's approved parts list replaces them. You say what the approval values in your file mean. The tool never decides that a part is approved. In the app use **File > Import > Import approved parts…**: the wizard asks which words in the file mean approved, not decided and not approved. The command line does the same:

```
harness-design-studio import-parts wheel-link my-templates/approved-parts.csv --approved Approved --pending Review --rejected Rejected --dry-run
```

```
row 2: OK updated EX-MICROD-9-F
row 3: OK updated EX-MICROD-9-M
row 4: OK updated EX-MICROD-15-F
row 5: OK updated EX-RJ45-F
row 6: OK updated EX-DSUB-9-F
5 part(s) ready, 0 row(s) with problems.
Dry run: nothing was changed.
```

Run it again without `--dry-run`:

```
harness-design-studio import-parts wheel-link my-templates/approved-parts.csv --approved Approved --pending Review --rejected Rejected
```

```
Imported 5 part(s). Project parts library (version 0), source: approved-parts.csv (sha256 b3e2067afea8), date: not recorded.
```

(That is the last line. The five `row ...: OK` lines come before it.)

- Columns are matched by heading: part number, manufacturer, description, category, specification, approval status, pin count, mass, mass per metre, mating part, and (since 1.7.0) `Tool` or `Crimp tool`, the crimp tool of a part of the category *contact* ([enter the build data](enter-the-build-data.md#2-contacts-and-crimp-tools)).
- Every row needs a category: a `category` column, or `--category connector` for the whole file.
- A value that is in none of your lists is an error for that row, and then **nothing** is written:

```
row 2: OK updated EX-MICROD-9-F
row 3: OK updated EX-MICROD-9-M
row 4: OK updated EX-MICROD-15-F
row 5: ERROR Approval status 'Review' is not in your approved, pending or rejected lists; say what it means
row 6: ERROR Approval status 'Rejected' is not in your approved, pending or rejected lists; say what it means
3 part(s) ready, 2 row(s) with problems.
Nothing was changed.
```

(That is the output when `--pending` and `--rejected` are left out.) The command exits with 1.

- You can repeat an option: `--approved Yes --approved Approved`.
- Numbers must be plain: digits with a point (`12.5`) or one decimal comma (`1,5`, in quotes when commas separate the columns). `1e3`, `1_0`, `-0` and `1,234` (is that 1.234 or a thousand?) are refused, and each message names the field and the row: `row 3: ERROR Mass (g) '1,234' could mean 1.234 or a thousands separator; write it with a point`. A pin count is a whole number from 1 to 1000: `row 4: ERROR Pin count '0' is not a whole number from 1 to 1000`.
- A part ID may appear once in the file: `row 3: ERROR 'P1' is already in row 2 of this file; each part may appear once`. A file with two columns that both hold the approval status is refused (`error: Two columns of the file are both about the approval status; keep only one.`, exit code 2).
- After a release, importing a part that a released harness uses is blocked: `error: This change was blocked because it touches released items.` followed by one line per part. New parts and parts no released harness uses can still be imported.
- Imported parts are no longer marked as example data.

The import changes the library, so the harness plans and outputs are out of date. Check, then make them current:

```
harness-design-studio drc wheel-link
```

```
Open: 1 error(s), 7 warning(s), 8 note(s). Waived: 0.
```

```
harness-design-studio generate wheel-link
harness-design-studio export wheel-link
harness-design-studio drc wheel-link
```

```
Open: 0 error(s), 7 warning(s), 8 note(s). Waived: 0.
```

The error says "The model changed after the harness plans were generated." That is what the check is for. After generating and exporting again it is gone, and the three parts you approved no longer warn (10 warnings before, 7 now). The rest stay warnings until their parts are approved too. (The numbers are for a `first-steps` project that was generated before the import.)

## Segment lengths

Lengths measured outside the tool (a CAD program or a spreadsheet) come in as a table. KiCad has none. A starting file is `segment-lengths.csv`:

```
harness,segment,length
W001,W001-L1,850
W002,W002-L1,900
```

In the app use **File > Import > Import segment lengths…**. The columns are read **by position**: harness, segment, length. Generate once first, because the segment IDs (`W001-L1`) belong to the generated harnesses. Without them every row fails: "Harness 'W001' does not exist".

```
harness-design-studio generate wheel-link
harness-design-studio import-lengths wheel-link my-templates/segment-lengths.csv --unit mm --dry-run
```

```
row 2: OK
row 3: OK
2 length(s) ready, 0 row(s) with problems.
Dry run: nothing was changed.
```

```
harness-design-studio import-lengths wheel-link my-templates/segment-lengths.csv --unit mm
harness-design-studio generate wheel-link
```

```
Lengths imported. Generate harnesses again to update the wire lengths.
0 added, 2 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
```

`--unit` is `mm` (the default), `cm` or `m`. A length is a plain number from 0 to 10000 m. One bad row stops the whole import:

```
row 3: ERROR 'abc' is not a length (digits with a decimal point or comma)
1 length(s) ready, 1 row(s) with problems.
Nothing was changed.
```

To find the segment IDs, open the generated harness in the **Harness** tab, or look in `physical/harnesses/W001.json` under `segments`.

## Build data: strip lengths, contacts, accessories

*Since 1.7.0.* `harness-design-studio import-build-data DIR FILE` reads a table of the data a technician needs. The kind of table is found from the column headings (any case, other columns are ignored): strip lengths (`Wire`, `Strip A (mm)`, `Strip B (mm)`, optional `Harness`), pin contacts (`Harness`, `Connector`, `Pin`, `Contact`, optional `Tool`), accessories (`Harness`, `Kind`, `Part`, `Target`, `Position`, `Length (mm)`, `Quantity`, `Note`, optional `ID`) and the crimp tool of parts (`Part`, `Tool`). It works as the other imports do: one line per row, the summary, `--dry-run` to write nothing, and a refused row means exit code 1 and nothing is changed. An empty cell leaves a value alone, and the same file imported twice changes nothing. The templates `strip-lengths.csv`, `pin-contacts.csv` and `accessories.csv` hold example rows.

```
harness-design-studio import-build-data wheel-link my-templates/strip-lengths.csv --dry-run
```

```
Import strip lengths: 2 row(s) read.
row 2: OK strip A 6 mm, strip B 6 mm
row 3: OK strip A 6 mm, strip B 5 mm
2 added, 0 changed, 0 unchanged, 0 refused.
Dry run: nothing was changed.
```

(The rows of the template are examples with example numbers; `Comment` is ignored.) There is no window for this import in the app; the values have their own fields there. Every case, with its output: [enter the build data](enter-the-build-data.md).

## Other imports

| You have | Do |
| --- | --- |
| A current-by-gauge table | **File > Import > Import engineering values: ampacity table…**, or `harness-design-studio config DIR --ampacity-csv FILE` ([fill in the engineering values](fill-in-engineering-values.md#2-load-the-current-by-gauge-table)) |
| A unit's connector pinout in KiCad | **File > Import > Import KiCad netlist…**, or `harness-design-studio import-netlist` ([import KiCad pinouts](import-kicad-pinouts.md)) |
| A device's pinout as a table | **File > Import > Import device pinout…**, or `harness-design-studio import-pinout` ([define a device](define-a-device.md#take-the-pinout-from-a-spreadsheet)) |
| Strip lengths, contacts, accessories or crimp tools as a table | `harness-design-studio import-build-data DIR FILE` (command line only; [enter the build data](enter-the-build-data.md)) |
| A device from another project | **Add from library…** in the Devices tab, or `harness-design-studio import-devices` ([define a device](define-a-device.md#use-a-device-in-another-project)) |
| Values from a standard | `harness-design-studio config DIR --apply-profile NAME` ([fill in the engineering values](fill-in-engineering-values.md#values-from-a-standard-profiles)) |

## Where the library data come from

`harness-design-studio import-parts` records the file name and its SHA-256 checksum as the **source** of the parts library. You can say more, and set the date of the data yourself (the tool does not read the clock for it):

```
harness-design-studio library wheel-link
harness-design-studio library wheel-link --library-source "Programme parts list, issue 3" --library-date 2026-09-30
```

```
Project parts library (version 0), source: approved-parts.csv (sha256 b3e2067afea8), date: not recorded.
Project parts library (version 0), source: Programme parts list, issue 3, data of 2026-09-30.
```

(Before any import the first line reads "source: not recorded, date: not recorded.")

The editor shows the same line under the part picker, and every export carries it in `system/provenance.json`.

## Common mistakes

- **"Harness 'W001' does not exist" for every row of the lengths file.** The harnesses are not generated yet, or the columns are in another order.
- **A part approval value is not accepted.** List every value of your file under `--approved`, `--pending` or `--rejected`.
- **"1,234" is refused.** Write `1.234` or `1234`. The tool does not guess which you mean.
- **"This change was blocked because it touches released items."** A released harness uses that part. Start a new revision first.
- **Errors appear after an import.** The library or the lengths changed, so the plans are out of date. Generate and export again.
- **Importing interfaces on the command line.** It is app only.

More: [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).

Next: [import KiCad pinouts](import-kicad-pinouts.md), [fill in the engineering values](fill-in-engineering-values.md), [enter the build data](enter-the-build-data.md), [export the outputs](export-the-outputs.md)
