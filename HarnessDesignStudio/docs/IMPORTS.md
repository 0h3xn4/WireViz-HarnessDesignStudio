# Importing outside data

Everything is previewed row by row and applied as one undo step (CLI: nothing is written if any row has a problem, and `--dry-run` shows the rows without changing anything). An import that would change something a release froze is blocked: both the preview and the real run say what is blocked and exit with 1. The command line has imports for parts, segment lengths, device pinouts, KiCad netlists, device library files and (since 1.7.0) the build data; importing interfaces is app only. The ampacity table loads with `config --ampacity-csv`.

Starting files for every import below are in the templates (`harness-design-studio templates FOLDER`): `interfaces.csv`, `approved-parts.csv`, `segment-lengths.csv`, `strip-lengths.csv`, `pin-contacts.csv`, `accessories.csv` (the last three are new in 1.7.0), `wheel-connectors.net`, `signal-map.csv` and `ampacity-DEMO-ONLY.csv`. They are written for the `first-steps` example (`harness-design-studio new DIR --template first-steps`), so you can try each one before using your own data. Walk-through: [`GETTING_STARTED.md`](GETTING_STARTED.md), parts 7 and 8.

## Interfaces (CSV or XLSX)
App only: **File > Import > Import interfaces…** (Ctrl+Shift+I), also reached from the project tree. It opens the import wizard that the other kinds use (file, columns with a live preview, conflicts, apply); **Paste table text instead…** on its first page opens the older dialog, which takes CSV text that you paste. There is no command line command for this import, so a script or CI job cannot do it. Columns: id, type, from, to, redundancy (optional); headers are matched by name (`from` is also read from `from unit`, `source` or `a`; `to` from `to unit`, `destination`, `target` or `b`; the type from `interface type`, `kind` or `protocol`). The units must exist; `type` is an interface type's name or ID. Each row needs a free connector on both units that can carry the type; a row that cannot be placed says why and nothing is applied.

## The import wizard (app)

File > Import offers six kinds, all through the same wizard: interfaces, approved parts, segment lengths, the ampacity table (engineering values), a device pinout and a KiCad netlist. Each ends with one undo step. A file with more than 1,500 rows is read in the background with a progress line and Cancel, so a table of 20,000 rows does not freeze the window (D-156).

## File formats
CSV files may use commas, semicolons or tabs between columns (the header line decides), UTF-8 with or without a byte order mark. A number with a decimal comma must be in quotes when commas separate the columns (`"1,5"`), or the file must use semicolons; a row with more columns than the header is refused rather than cut off. At most 20,000 rows and 8 MB; XLSX files are read from the first visible sheet (not the one that was active when the file was saved), and the import names the sheet it read. In a CSV file a quote that is never closed, or that is followed by other text in the cell, is refused with the line number and nothing is imported. Only regular files are read (not pipes or devices).

## Approved parts list (D-12)
The file can be `.csv`, `.tsv`, `.json` (a list of records) or `.xlsx`, and can be the export of a parts program such as InvenTree: the `IPN` column is read as the part ID (the `ID` of InvenTree is a database number), `Name` or `Description` as the description, `MPN` as the part number, and a category path such as `Connectors/D-Sub` as `connector`. Nothing connects to a server (D-165). What the approval values mean is still yours to say.

`harness-design-studio import-parts DIR FILE --approved A --approved Yes --pending Review --rejected X [--category connector] [--dry-run]`

- Every row needs a category (a `category` column or `--category`); a row without one is refused ("Category '(empty)' is not one of ...").
- Columns are matched by header: part ID or part number, manufacturer, description, category, specification, approval status, pin count, mass (g), mass per metre (g/m), mating part, and (since 1.7.0) `Tool` or `Crimp tool` (the crimp tool of a part of the category *contact*).
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
`harness-design-studio import-lengths DIR FILE [--unit mm|cm|m] [--dry-run]` with three columns read **by position**: harness ID, segment ID, length (the headings are not matched, unlike the other imports; default unit millimetres, decimal commas accepted). A length is a plain number from 0 to 10000 m; a bad row (a minus sign, text, too large) stops the whole import. Run `harness-design-studio generate DIR` afterwards so the wire lengths follow.

Device pinouts from a spreadsheet: `harness-design-studio import-pinout DIR FILE --unit U [--new-device NAME] [--default-part PART] [--part J1=PART] [--column FIELD=HEADING] [--replace] [--dry-run]`, or **File > Import > Import device pinout…**. One row is one pin. The headings are matched by name (Connector, Pin, Signal, Mode or Fixed, Contact size, Termination, Part, Gender); a column the project cannot hold (a description, remarks, a voltage, a direction) is named in a warning and left out. A new connector needs a library part. A bad row stops the whole import. `harness-design-studio export-pinout DIR --unit U` writes the pinout of a device in the same shape, and its CSV and XLSX can be read back (the comment line and the About sheet of the tool's own files are skipped). User manual: [define a device](user-manual/define-a-device.md). The heading *Cable contact* (or *Contact part*) names the contact part of the cable side of a pin (since 1.7.0).

KiCad: it is used for the electronics inside each unit, so it is where each unit connector's pinout comes from. It has no harness segment lengths; those come from a plain table as above. The connector pinouts are read from a KiCad netlist with `harness-design-studio import-netlist` (see `docs/KICAD.md`).

## Build data: strip lengths, contacts, accessories, crimp tools (1.7.0)
`harness-design-studio import-build-data DIR FILE [--dry-run]` reads a `.csv`, `.tsv`, `.json` or `.xlsx` table (the same readers as the other imports, first visible sheet). The kind is told by the column headings, in any case; other columns are ignored:

| Kind | Headings | What it sets |
| --- | --- | --- |
| Strip lengths | `Wire`, `Strip A (mm)`, `Strip B (mm)`; `Harness` optional while the wire ID is unique | the strip length at the From and the To end of a wire (0 to 100,000 mm) |
| Pin contacts | `Harness`, `Connector`, `Pin`, `Contact`; `Tool` optional | the contact part (category *contact*) of a pin of a cable connector of a harness made by hand; `Tool` sets the crimp tool of that contact part. A pin of a harness made by Generate is refused: its contact comes from the pin of the unit |
| Accessories | `Harness`, `Kind`, `Part`, `Target`, `Position`, `Length (mm)`, `Quantity`, `Note`; `ID` optional | an accessory of a harness; `Kind` is sleeving, heat_shrink, label, backshell or other; `Target` is a connector or a wire of the harness, empty means the harness; without an `ID` the rows are numbered `ACC-001`, ... |
| Part tools | `Part`, `Tool` | the crimp tool of a part |

It prints one line per row and `N added, N changed, N unchanged, N refused.` One refused row means exit code 1 and nothing is changed; `--dry-run` writes nothing. An empty cell leaves a value as it is (it never clears one), and the same file imported twice changes nothing. A table whose headings fit no kind is refused with exit code 2. There is no import window in the app for it. User manual: [enter the build data](user-manual/enter-the-build-data.md).

## Devices from a device library file (1.4.0)
`harness-design-studio export-devices DIR FILE --unit U [--unit V ...]` saves devices with their connectors, pinouts, parts and interface types to a JSON file that lives outside any project (a file that exists is added to). `harness-design-studio import-devices DIR FILE [--unit U] [--list] [--dry-run]` adds them to another project; a device never replaces one of the project (a taken ID becomes `GYRO1-2`). In the app: **Save to library…** and **Add from library…** on the Devices tab. This is not a kind of the import wizard. The file is described in [`FILE_FORMAT.md`](FILE_FORMAT.md#device-library-file-140-not-part-of-a-project); steps: [define a device](user-manual/define-a-device.md).

## Where the library data come from

`harness-design-studio import-parts` records the file name and its SHA-256 as the library's **source**. Say more with `--library-source`, `--library-version`, `--library-name` and `--library-date YYYY-MM-DD` (the date of the data, which you enter; the tool does not read the clock). The date is written exactly `YYYY-MM-DD`; any other field that is empty, too long or has control characters is named in the message. `harness-design-studio library DIR` shows what is recorded and `harness-design-studio library DIR --library-source "..." --library-date 2026-09-30` sets it without an import. The editor shows the same line under the part picker and every export carries it in `system/provenance.json`.

Next: [import data (user manual)](user-manual/import-data.md), [`KICAD.md`](KICAD.md).
