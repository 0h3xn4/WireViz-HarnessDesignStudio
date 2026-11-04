# Importing outside data

Everything is previewed row by row and applied as one undo step (CLI: nothing is written if any row has a problem, and `--dry-run` shows the rows without changing anything). Every import says what it read, what it left out and which unit it used, and an import that is applied is recorded in the project: [what an import records](#what-an-import-records). An import that would change something a release froze is blocked: both the preview and the real run say what is blocked and exit with 1. The command line has imports for parts, segment lengths, device pinouts, KiCad netlists, device library files, (since 1.7.0) the build data and (since 1.8.0) subsystem library files; importing interfaces is app only. The ampacity table loads with `config --ampacity-csv`. `harness-design-studio imports` lists what was imported and whether a source file has changed since.

Starting files for every import below are in the templates (`harness-design-studio templates FOLDER`): `interfaces.csv`, `approved-parts.csv`, `segment-lengths.csv`, `strip-lengths.csv`, `pin-contacts.csv`, `accessories.csv` (the last three are new in 1.7.0), `wheel-connectors.net`, `signal-map.csv` and `ampacity-DEMO-ONLY.csv`. They are written for the `first-steps` example (`harness-design-studio new DIR --template first-steps`), so you can try each one before using your own data. Walk-through: [`GETTING_STARTED.md`](GETTING_STARTED.md), parts 7 and 8.

## Interfaces (CSV or XLSX)
App only: **File > Import > Import interfaces…** (Ctrl+Shift+I), also reached from the project tree. It opens the import wizard that the other kinds use (file, columns with a live preview, conflicts, apply); **Paste table text instead…** on its first page opens the older dialog, which takes CSV text that you paste. There is no command line command for this import, so a script or CI job cannot do it. Columns: id, type, from, to, redundancy (optional); headers are matched by name (`from` is also read from `from device` (or `from unit`), `source` or `a`; `to` from `to device` (or `to unit`), `destination`, `target` or `b`; the type from `interface type`, `kind` or `protocol`). The devices must exist; `type` is an interface type's name or ID. Each row needs a free connector on both devices that can carry the type; a row that cannot be placed says why and nothing is applied.

## The import wizard (app)

File > Import offers six kinds, all through the same wizard: interfaces, approved parts, segment lengths, the ampacity table (engineering values), a device pinout and a KiCad netlist. Each ends with one undo step. A file with more than 1,500 rows is read in the background with a progress line and Cancel, so a table of 20,000 rows does not freeze the window (D-156).

## File formats
CSV files may use commas, semicolons or tabs between columns (the header line decides), UTF-8 with or without a byte order mark. A number with a decimal comma must be in quotes when commas separate the columns (`"1,5"`), or the file must use semicolons; a row with more columns than the header is refused rather than cut off. At most 20,000 rows and 8 MB; XLSX files are read from the first visible sheet (not the one that was active when the file was saved), and the import names the sheet it read. In a CSV file a quote that is never closed, or that is followed by other text in the cell, is refused with the line number and nothing is imported. Only regular files are read (not pipes or devices). The CSV and TSV files that the tool writes itself (`bom.csv`, `box_pinouts.csv` ...) start with a line `# harness-design-studio VERSION model HASH`; every reader skips that line, and gives back the text that the tool marked with a leading apostrophe so that a spreadsheet would not run it as a formula (`'+28V` is read as `+28V`), so what the tool exports can be imported again. A file that is not the tool's own is read exactly as it is.

## Approved parts list (D-12)
The file can be `.csv`, `.tsv`, `.json` (a list of records) or `.xlsx`, and can be the export of a parts program such as InvenTree: the `IPN` column is read as the part ID (the `ID` of InvenTree is a database number), `Name` or `Description` as the description, `MPN` as the part number, and a category path such as `Connectors/D-Sub` as `connector`. Nothing connects to a server (D-165). What the approval values mean is still yours to say.

`harness-design-studio import-parts DIR FILE --approved A --approved Yes --pending Review --rejected X [--category connector] [--dry-run]`

- Every row needs a category (a `category` column or `--category`); a row without one is refused ("Category '(empty)' is not one of ...").
- Columns are matched by header: part ID or part number, manufacturer, description, category, specification, approval status, pin count, mass (g), mass per metre (g/m), mating part, ratings (below), and (since 1.7.0) `Tool` or `Crimp tool` (the crimp tool of a part of the category *contact*) and (since 1.11) `Conductors` (a whole number from 1 to 64: how many conductors one metre of a *wire* part carries, 2 for a twisted pair; the bill of materials and the mass count the metres of the cable, not of every conductor).
- **Ratings.** A column headed with the name of a rating is read into the ratings of the part (`Part.ratings`, the values the rules read): `contact_current_a` (the key `config/derating.json` calls `contact_rating_key` is read as well), `rated_voltage_v`, `dielectric_withstand_v`, `max_temp_c`, `mating_cycles`, `shield_insulated` and `conductive_finish`. Spaces, brackets and case do not matter (`Contact current (A)` is `contact_current_a`; so is `ratings.contact_current_a`). A cell is a plain number; an empty cell leaves the rating as it is; a rating that is not a number refuses its row. A file without such a column imports exactly as before.
- **Units.** The mass columns are read in grams (per metre: grams per metre). `--mass-unit kg|lb|oz` says that they are in another unit; the import converts, shows each converted value (`Converted, row 2 (ZZ-1): 0.25 kg = 250 g`) and records them. Without the option the unit is assumed to be grams, and the import says so (`Unit: mass in g (assumed; --mass-unit says another).`).
- **Columns that are not read** are named in a warning (`warning: the column 'Notes' is not read; its values are not imported.`); before, the import left them out without a word.
- **You say what the approval values mean** with `--approved`, `--pending`, `--rejected` (repeat for several values). A value in none of the lists is an error for that row. The tool never decides that something is approved.
- Numbers are plain: digits with a point (`12.5`), or one decimal comma (`1,5`). `1e3`, `1_0`, `-0` and `1,234` (thousands or decimals?) are refused with a message to write them with a point. The pin count is a whole number from 1 to 1000.
- A part ID may appear once in the file; a second row with the same ID is an error row. Two columns that both look like the approval status are refused.
- A row that cannot be used says which field is wrong (for example `Description: String should have at most 200 characters`).
- New parts are added; existing parts are updated with the columns that are filled in. Imported parts are no longer marked as example data.
- Parts that are used but not approved stay design rule warnings until the list marks them approved.
- A program-specific format (for example an EPPL or DCL export) can be added as a column mapping once you can show an example file.

## Engineering values (D-11)
`harness-design-studio config DIR` is the hand-over checklist: which derating, grounding, test-limit and separation values are still missing, what depends on each, and which values that are set are invalid (for example a factor above 1, or an ampacity table in which a thinner wire carries more). Invalid values are also rule errors in the editor.

`harness-design-studio config DIR --ampacity-csv FILE` loads the current-by-gauge table from a two-column CSV (gauge, amperes; header optional; decimal commas accepted). It is validated before anything is written. The other values are edited in `config/*.json` (see CONFIG.md); set `"placeholder": false` in a file once it is reviewed.

Until the values exist, wire gauges stay "pending", the affected checks say "not checked", and a harness cannot be released while a wire has no gauge or length. To see the machinery work first, the templates contain **demo** values (`config-demo-values/`, `ampacity-DEMO-ONLY.csv`); they are not engineering data and the files stay marked as placeholders.

## Segment lengths from a CAD or spreadsheet (D-13)
`harness-design-studio import-lengths DIR FILE [--unit mm|cm|m|in|ft] [--dry-run]` with three columns read **by position**: harness ID, segment ID, length (the headings are not matched, unlike the other imports; default unit millimetres, decimal commas accepted). A length is a plain number from 0 to 10000 m; a bad row (a minus sign, text, too large) stops the whole import. Run `harness-design-studio generate DIR` afterwards so the wire lengths follow.

The import **echoes every value it converts**: the value as written, the unit it was read in and the metres that were stored, on the line of its row (`row 2: OK W001 / W001-L1: 850 mm = 0.85 m`). A bare `5.0` in a file without `--unit` is read as millimetres and shows as `5.0 mm = 0.005 m`; the line `Unit: length in mm (assumed; --unit says another).` says that the unit was assumed, and `Unit: length in in (given with --unit).` that it was given. A row that is dropped says why (`row 3: ERROR Harness 'W009' does not exist`), and a column beyond the third is named in a warning, because the columns are read by position.

Device pinouts from a spreadsheet: `harness-design-studio import-pinout DIR FILE --device D [--new-device NAME] [--default-part PART] [--part J1=PART] [--column FIELD=HEADING] [--replace] [--dry-run]`, or **File > Import > Import device pinout…**. One row is one pin. The headings are matched by name (Connector, Pin, Signal, Mode or Fixed, Contact size, Termination, Function, Direction, Part, Gender); a column the project cannot hold (a description, remarks, a voltage) is named in a warning and left out. A *Direction* column (also `Dir`, `Pin direction`, `IO mode`) is read since 1.9.0: `in`, `out` or `bidirectional` (also Input, Output, I/O, inout); an empty cell, `n/a` or `passive` leaves the direction unset; any other word (Power, Ground ...) stops the whole import with the row named, because a direction is never guessed. A new connector needs a library part. A bad row stops the whole import. Every column that is not read is named in a warning. `harness-design-studio export-pinout DIR --device U` writes the pinout of a device in the same shape, and its CSV and XLSX can be read back (the comment line and the About sheet of the tool's own files are skipped). User manual: [define a device](user-manual/define-a-device.md). The heading *Cable contact* (or *Contact part*) names the contact part of the cable side of a pin (since 1.7.0).

KiCad: it is used for the electronics inside each device, so it is where each device connector's pinout comes from. It has no harness segment lengths; those come from a plain table as above. The connector pinouts are read from a KiCad netlist with `harness-design-studio import-netlist` (see `docs/KICAD.md`). The import record keeps what the netlist says that the pins have no field for: the KiCad **pin type** of every imported pin (`OBC1-J01.3` is `power_in`) and the name of the **schematic** the netlist was made from (the file name only; KiCad writes a path, which is not kept). The component value and the footprint are named as not imported. With `--pin-direction` the pin types `input`, `output` and `bidirectional` also fill the direction (`in`, `out`, `bidir`) of a pin that has none; the other types (`passive`, `power_in` ...) say nothing about a direction and set nothing.

## Build data: strip lengths, contacts, accessories, crimp tools (1.7.0)
`harness-design-studio import-build-data DIR FILE [--dry-run]` reads a `.csv`, `.tsv`, `.json` or `.xlsx` table (the same readers as the other imports, first visible sheet). The kind is told by the column headings, in any case; other columns are ignored:

| Kind | Headings | What it sets |
| --- | --- | --- |
| Strip lengths | `Wire`, `Strip A (mm)`, `Strip B (mm)`; `Harness` optional while the wire ID is unique | the strip length at the From and the To end of a wire (0 to 100,000 mm) |
| Pin contacts | `Harness`, `Connector`, `Pin`, `Contact`; `Tool` optional | the contact part (category *contact*) of a pin of a cable connector of a harness made by hand; `Tool` sets the crimp tool of that contact part. A pin of a harness made by Generate is refused: its contact comes from the pin of the device |
| Accessories | `Harness`, `Kind`, `Part`, `Target`, `Position`, `Length (mm)`, `Quantity`, `Note`; `ID` optional | an accessory of a harness; `Kind` is sleeving, heat_shrink, label, backshell or other; `Target` is a connector or a wire of the harness, empty means the harness; without an `ID` the rows are numbered `ACC-001`, ... |
| Part tools | `Part`, `Tool` | the crimp tool of a part |

The strip lengths and the accessory lengths are read as millimetres, as the headings say; `--unit cm|m|in|ft` says that a file has them in another unit (they are stored in millimetres), and a heading that names another unit than `--unit` (for example `Strip A (mm)` with `--unit in`) is named in a warning. A decimal comma is read as a decimal point (`"1,5"` is 1.5 mm; the importer cannot tell 1,234 from 1.234) and the import lists each such cell (`Converted, row 2: 1,5 mm = 1.5 mm`). It prints one line per row and `N added, N changed, N unchanged, N refused.` One refused row means exit code 1 and nothing is changed; `--dry-run` writes nothing. An empty cell leaves a value as it is (it never clears one), and the same file imported twice changes nothing. A table whose headings fit no kind is refused with exit code 2. There is no import window in the app for it. User manual: [enter the build data](user-manual/enter-the-build-data.md).

## As-built records (S9)

`harness-design-studio import-asbuilt DIR FILE [--dry-run]` reads the sheet that `export-asbuilt` writes (or any table with the same headings; `.csv`, `.tsv`, `.json` or `.xlsx`) and keeps its records in `asbuilt/records.json`. Columns are found by their headings; the unit of a number column is the one in its heading and every converted value is listed; an empty cell never clears a value; a row the design cannot take is refused and then nothing is changed. The import is recorded in `imports/records.json` as kind `asbuilt`. [Record what was built](user-manual/record-what-was-built.md) has the columns, the units and an example.

## Devices from a device library file (1.4.0)
`harness-design-studio export-devices DIR FILE --device D [--device E ...]` saves devices with their connectors, pinouts, parts and interface types to a JSON file that lives outside any project (a file that exists is added to). `harness-design-studio import-devices DIR FILE [--device D] [--list] [--dry-run]` adds them to another project; a device never replaces one of the project (a taken ID becomes `GYRO1-2`). In the app: **Save to library…** and **Add from library…** on the Devices tab. This is not a kind of the import wizard. The file is described in [`FILE_FORMAT.md`](FILE_FORMAT.md#device-library-file-140-not-part-of-a-project); steps: [define a device](user-manual/define-a-device.md).

A subsystem library file (since 1.8.0: devices with their connectors and the connections between them) is written with `harness-design-studio export-subsystem DIR FILE --device D [--device E ...] --name NAME [--replace]` and added with `harness-design-studio import-subsystem DIR FILE [--show] [--dry-run]`, all or nothing and as one undo step. In the app: the library window (**File > Library…**). The file is described in [`FILE_FORMAT.md`](FILE_FORMAT.md#subsystem-library-file-m4-not-part-of-a-project).

## What an import records

Every import that is applied keeps a record of the file it read in `imports/records.json` of the project (a project that never imported has no such file). The record is the answer to "where did this data come from, and what did the tool do to it?":

```
{
  "imports": [
    {
      "columns_read": [{"column": "harness", "field": "harness"}, {"column": "segment", "field": "segment"}, {"column": "length", "field": "length"}],
      "converted_count": 2,
      "dropped_count": 0,
      "id": "lengths:segment-lengths.csv",
      "kind": "lengths",
      "rows_converted": [
        {"field": "length", "item": "W001 / W001-L1", "read": "850", "row": 2, "stored": "0.85 m", "unit": "mm"},
        {"field": "length", "item": "W002 / W002-L1", "read": "900", "row": 3, "stored": "0.9 m", "unit": "mm"}
      ],
      "rows_read": 2,
      "sha256": "117043908312d3e7ba3fa0ca5ab598d6ba831d6a63e0990df7bcf9c5eb514648",
      "source_name": "segment-lengths.csv",
      "source_path": "data/segment-lengths.csv",
      "tool_version": "1.13.0",
      "unit": "mm"
    }
  ]
}
```

| Field | Holds |
| --- | --- |
| `id`, `kind` | `<kind>:<file name>`; the kinds are `parts`, `interfaces`, `lengths`, `strip-lengths`, `pin-contacts`, `accessories`, `part-tools`, `pinout`, `netlist`, `ampacity`, `devices` and `subsystem`. Importing the same file again replaces its record; the same file name under another kind is another record |
| `source_name`, `source_path` | The file name. The path only when the file lies inside the project folder, relative to it (`data/segment-lengths.csv`); never an absolute path. `sheet` names the sheet of a workbook |
| `sha256` | The SHA-256 of the file's bytes |
| `rows_read` | Data rows of a table (the connectors of a netlist, the devices of a library file) |
| `columns_read`, `columns_ignored` | The column headings that were read, each with the field it was read as, and the headings that were left out |
| `dropped_count`, `rows_dropped` | Rows that were not imported, each with its row number (the heading row is row 1) and the reason |
| `converted_count`, `rows_converted` | Values that were converted: the cell as written, the unit it was read in, the value stored with its unit |
| `unit`, `unit_given` | The unit the values were read in, and whether the person gave it (`true`) or the tool assumed it (left out) |
| `tool_version` | The version of the tool that imported |
| `notes`, `pin_types` | Other things read from the source: the schematic a KiCad netlist was made from, the pin type of each imported pin |

At most 200 rows are listed in `rows_dropped` and `rows_converted`; the counts are always the whole number. The file holds **no time and no operator** (the tool never reads a clock or a user name into project data, so the same import always gives the same bytes). The record is **not part of the design**: it is not in the model hash, not in any output file, and a project with and without it gives the same files. It is part of the project, so it is saved and loaded with it, written to the autosave journal, and one undo step takes the import and its record back together. The JSON schema of the file is exported by `harness-design-studio schema` (`import-records.schema.json`). The wizard shows the same facts on its pages: the columns that are not read and an assumed unit on the check page, and a line on the last page that the record is kept.

**As data.** With `--json` every import command prints one JSON document (see `docs/CLI.md`); its last key, `import`, holds this same record (kind, file name, SHA-256, rows read, columns read and left out, rows dropped, values converted, unit) and `record_written`, which is `true` when this run wrote the record (never in a dry run). `imports --json` lists the records with `status` and `current_sha256`. No time, user name or absolute path is in either.

**Has the source changed?** `harness-design-studio imports DIR` compares the SHA-256 of every source it can reach now with the recorded one: a source inside the project folder is found by its recorded path, any other by a file you name with `--source FILE` (matched by file name). The status is `unchanged`, `source changed`, `source not found` or `not checked (no path)`; `--check` ends with exit code 1 when a source has changed, so a build can stop on it, and `--json` prints the records and their status. In the app the first page of the import wizard lists the earlier imports and marks a source that changed with the words *source changed*, and the Next step page says it once in a quiet line; neither appears while the project has no record. To take the new content, import the file again.

## Which export is read by which importer

What the tool writes can be read again where the importers know the shape. The files of `export-data` ([export the data](user-manual/export-the-data.md)) have no comment line.

| Written by | File | Read by |
| --- | --- | --- |
| `export-data DIR --out FOLDER` | `segment_lengths.csv` (or `.json`): harness, segment, length in metres, the nodes of the segment | `import-lengths DIR FILE --unit m` (the first three columns, by position; only segments that have a length are listed, because a row without one stops the import) |
| `export-data` | `parts.csv`: part, category, manufacturer, part number, description, specification, approval, pin count, mass, mass per metre, mates with, tool, conductors | `import-parts DIR FILE --approved approved --pending pending --rejected not_approved` (the `Ratings` and `Example data` columns are not read) |
| `export-pinout DIR --device D` | CSV or XLSX of the pins of a device | `import-pinout` (the comment line and the About sheet are skipped) |
| `export-devices`, `export-subsystem` | a library file | `import-devices`, `import-subsystem` |
| `export-data` | the other tables (`wire_sizing`, `rule_results`, `bom`, `findings`, ...) | none: they are results, not inputs |

The CSV files of `export` (the wire list, the pinouts, the bill of materials ...) start with the line `# harness-design-studio VERSION model HASH`. Every importer skips that line, so an output file can be read back as it is, for example `system/bom.csv` by `import-parts` and a file of segment lengths with the line by `import-lengths`. The files of `export-data` have no such line. `provenance.json` of `export-data` lists the files the project imported (the record of each: kind, file name, SHA-256, rows read and dropped, values converted).

## Where the library data come from

`harness-design-studio import-parts` records the file name and its SHA-256 as the library's **source**. Say more with `--library-source`, `--library-version`, `--library-name` and `--library-date YYYY-MM-DD` (the date of the data, which you enter; the tool does not read the clock). The date is written exactly `YYYY-MM-DD`; any other field that is empty, too long or has control characters is named in the message. `harness-design-studio library DIR` shows what is recorded and `harness-design-studio library DIR --library-source "..." --library-date 2026-09-30` sets it without an import. The editor shows the same line under the part picker and every export carries it in `system/provenance.json`.

Next: [import data (user manual)](user-manual/import-data.md), [`KICAD.md`](KICAD.md).
