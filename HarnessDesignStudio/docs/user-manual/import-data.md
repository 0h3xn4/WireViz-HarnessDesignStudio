# Import data

This page shows how to bring data you already have into a project: a list of interfaces, your approved parts list and the lengths of the routes, always with a preview first.

## Contents

- [Before you start](#before-you-start)
- [Interfaces from a table (app only)](#interfaces-from-a-table-app-only)
- [Approved parts list](#approved-parts-list)
- [Segment lengths](#segment-lengths)
- [Other imports](#other-imports)
- [Where the library data come from](#where-the-library-data-come-from)
- [Common mistakes](#common-mistakes)

## Before you start

- You have a practice project: `harness new wheel-link --template first-steps`.
- Starting files for every import are in the templates. Copy them once:

```
harness templates my-templates
```

```
15 files written to my-templates. Start with my-templates/README.md.
```

(On a 0.1.0 package there is one file fewer: `design-worksheet.md` is not in the 0.1.0 packages.)

- Every import shows what it would do. On the command line add `--dry-run`: the rows are listed and nothing changes. Run the command again without it to apply.
- Files can be CSV (commas, semicolons or tabs between columns; UTF-8) or Excel (`.xlsx`, the first **visible** sheet, not the one that was active when the file was saved; the import says `Reading sheet 'Parts' (the first visible sheet of the workbook).`). A number with a decimal comma needs quotes (`"1,5"`) when commas separate the columns. At most 20,000 rows and 8 MB. Details: [`IMPORTS.md`](../IMPORTS.md).
- A CSV file with a quote that is never closed (or is followed by other text in the cell) is refused with its line number, and nothing is imported: `error: Line 2: unbalanced quote. A " opens a text that is never closed, or is followed by other text. Remove the stray quote or write it twice ("") inside a quoted cell. Nothing was imported.` (exit code 2).
- An import that would change something a **release froze** (a part, an interface type or a configuration value that a released harness uses) is blocked, in the preview and in the real run, with exit code 1 ([change a released harness](change-a-released-harness.md)).

## Interfaces from a table (app only)

Importing interfaces works in the app. There is no command for it. (GUI, not run: the steps are described from the program's code. The column names and messages are the program's.)

1. Open the project. Choose **File > Import > Import interfaces…** (Ctrl+Shift+I), or press **Import interfaces from CSV / XLSX…** under **Bring in data** in the **Palette** tab, or press Enter on **Interfaces** under **Imports** in the **Project** tab.
2. Press **Open file…** and pick a `.csv` or `.xlsx` file. You can also paste CSV text into the box. Try `my-templates/interfaces.csv`:

```
id,type,from,to,redundancy
IF-010,RS-422,OBC1,PCDU1,nominal
IF-011,Primary power,PCDU1,OBC1,nominal
```

3. Check the **column matching** (Interface ID, Interface type, From unit, To unit, Redundancy). The tool guesses it from the headings; change a choice if it guessed wrong. `redundancy` is optional.
4. Read the **preview**. Each row says "✓ OK" or "✕" with the reason, for example `Unit 'RW9' does not exist`. The line under it says, for example, "1 of 2 rows can be imported; 1 have errors and will be skipped."
5. Press **Import N rows (one undo step)**. Rows with errors are skipped and the good rows are applied. **Undo** takes all of them back at once. For an Excel file the window names the sheet it read ("file.xlsx (sheet: Parts)"). If the text can no longer be read (for example after you pasted something that is not a table), the OK button is turned off.

Rules for a row: the two units must exist already; `type` is the name or ID of an interface type (for example `RS-422`); each unit needs a free connector that can carry the type.

## Approved parts list

The starter library has only example parts, none of them approved. Your programme's approved parts list replaces them. You say what the approval values in your file mean. The tool never decides that a part is approved.

```
harness import-parts wheel-link my-templates/approved-parts.csv --approved Approved --pending Review --rejected Rejected --dry-run
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
harness import-parts wheel-link my-templates/approved-parts.csv --approved Approved --pending Review --rejected Rejected
```

```
Imported 5 part(s). Project parts library (version 0), source: approved-parts.csv (sha256 b3e2067afea8), date: not recorded.
```

(That is the last line. The five `row ...: OK` lines come before it.)

- Columns are matched by heading: part number, manufacturer, description, category, specification, approval status, pin count, mass, mass per metre, mating part.
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
harness drc wheel-link
```

```
Open: 1 error(s), 7 warning(s), 8 note(s). Waived: 0.
```

```
harness generate wheel-link
harness export wheel-link
harness drc wheel-link
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

The columns are read **by position**: harness, segment, length. Generate once first, because the segment IDs (`W001-L1`) belong to the generated harnesses. Without them every row fails: "Harness 'W001' does not exist".

```
harness generate wheel-link
harness import-lengths wheel-link my-templates/segment-lengths.csv --unit mm --dry-run
```

```
row 2: OK
row 3: OK
2 length(s) ready, 0 row(s) with problems.
Dry run: nothing was changed.
```

```
harness import-lengths wheel-link my-templates/segment-lengths.csv --unit mm
harness generate wheel-link
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

## Other imports

| You have | Do |
| --- | --- |
| A current-by-gauge table | `harness config DIR --ampacity-csv FILE` ([fill in the engineering values](fill-in-engineering-values.md#2-load-the-current-by-gauge-table)) |
| A unit's connector pinout in KiCad | `harness import-netlist` ([import KiCad pinouts](import-kicad-pinouts.md)) |
| Values from a standard | `harness config DIR --apply-profile NAME` ([fill in the engineering values](fill-in-engineering-values.md#values-from-a-standard-profiles)) |

## Where the library data come from

`harness import-parts` records the file name and its SHA-256 checksum as the **source** of the parts library. You can say more, and set the date of the data yourself (the tool does not read the clock for it):

```
harness library wheel-link
harness library wheel-link --library-source "Programme parts list, issue 3" --library-date 2026-09-30
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

Next: [import KiCad pinouts](import-kicad-pinouts.md), [fill in the engineering values](fill-in-engineering-values.md), [export the outputs](export-the-outputs.md)
