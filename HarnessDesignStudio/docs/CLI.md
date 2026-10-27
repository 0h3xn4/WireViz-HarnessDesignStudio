# Command line reference

Generated from the program by `python -m tools.gen_cli_docs`; do not edit by hand. `project` is a project folder. Run `harness-design-studio COMMAND --help` for the same text in a terminal. `harness` still works as a short alias of `harness-design-studio` (the same program).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | success (warnings are allowed) |
| 1 | the project has errors, or a step is blocked (for example a release, or an import or `config` that found problems and changed nothing, or an import of a file with nothing in it) |
| 2 | usage error, or a project or file that could not be read |
| 130 | interrupted with Ctrl-C |

A project with damaged files (a file that is not valid, a link, over 64 MB or unreadable) is refused with exit 2 and the damaged file named by every command that reports on it or changes it: `drc`, `verify`, `export`, `generate`, `config`, `library`, `log`, `diff`, `compare`, `review`, `release`, `revise`, `migrate` and the imports. Only `validate` and `check` read it and list the damage (exit 1), so you can see what to repair. With Ctrl-C a command prints `interrupted` and ends with 130 (if it was saving, run `harness-design-studio validate`). A reader that closes the pipe (`harness-design-studio generate | head -1`) does not stop the command: it still finishes and saves.

An import whose file says what the project already holds changes nothing, prints `Already up to date.` and ends with 0, so it can run again on every build. Every command that changes a project takes the same lock as the app, so the two never write at once. The commands that import data (`import-parts`, `import-lengths`, `import-build-data`, `import-netlist`, `import-pinout`, `import-devices`) accept `--dry-run`: they show what they would do and change nothing; `config --ampacity-csv` does not.

The examples show the form of each command with example names. They do not all work on any project: `release` is blocked until its conditions are met (placeholder configuration, unapproved parts, missing gauges and lengths; see [`GETTING_STARTED.md`](GETTING_STARTED.md)), and `revise` works only on a released harness.

## Contents

- Start: [`new`](#harness-design-studio-new), [`templates`](#harness-design-studio-templates), [`schema`](#harness-design-studio-schema)
- Check: [`validate`](#harness-design-studio-validate), [`check`](#harness-design-studio-check), [`drc`](#harness-design-studio-drc), [`verify`](#harness-design-studio-verify)
- Generate and export: [`generate`](#harness-design-studio-generate), [`export`](#harness-design-studio-export)
- Bring in data: [`config`](#harness-design-studio-config), [`library`](#harness-design-studio-library), [`import-parts`](#harness-design-studio-import-parts), [`import-lengths`](#harness-design-studio-import-lengths), [`import-netlist`](#harness-design-studio-import-netlist), [`import-pinout`](#harness-design-studio-import-pinout), [`import-devices`](#harness-design-studio-import-devices), [`import-subsystem`](#harness-design-studio-import-subsystem), [`import-build-data`](#harness-design-studio-import-build-data)
- Write data out: [`export-pinout`](#harness-design-studio-export-pinout), [`export-devices`](#harness-design-studio-export-devices), [`export-subsystem`](#harness-design-studio-export-subsystem)
- Review, release and change: [`review`](#harness-design-studio-review), [`release`](#harness-design-studio-release), [`revise`](#harness-design-studio-revise), [`diff`](#harness-design-studio-diff), [`log`](#harness-design-studio-log), [`compare`](#harness-design-studio-compare)
- Maintenance: [`migrate`](#harness-design-studio-migrate)

## Start

### harness-design-studio new

Create a project folder from one of the bundled examples. `harness-design-studio new --list` shows them. The folder must not exist yet or be empty.

`harness-design-studio new [folder] [options]`

| Argument | Meaning |
| --- | --- |
| `folder` | the new project folder |
| `--template TEMPLATE` | which example to start from (default blank) |
| `--name NAME` | project name (default: the example's name) |
| `--list` | list the examples and exit |

Examples:

```
harness-design-studio new --list
harness-design-studio new my-design --name "My first design"
harness-design-studio new wheel-link --template first-steps
```

### harness-design-studio templates

Copy the bundled templates for the imports, CI scripts and the review checklist. The folder must not exist yet or be empty.

`harness-design-studio templates folder`

| Argument | Meaning |
| --- | --- |
| `folder` | where to put the templates |

Examples:

```
harness-design-studio templates my-templates
```

### harness-design-studio schema

Write one JSON Schema per kind of project file, made from the program's own model, and a settings fragment that maps the files to them. For people who edit project files by hand. Nothing is downloaded. The folder must not exist yet or be empty.

`harness-design-studio schema folder`

| Argument | Meaning |
| --- | --- |
| `folder` | where to put the schemas (for example my-design/schemas) |

Examples:

```
harness-design-studio schema my-design/schemas
```

## Check

### harness-design-studio validate

check a project folder for errors and inconsistencies

`harness-design-studio validate project`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |

Examples:

```
harness-design-studio validate my-design
```

### harness-design-studio check

validate, plus detect problems left behind by Git merges

`harness-design-studio check project`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |

Examples:

```
harness-design-studio check my-design
```

### harness-design-studio drc

run the design rule check and print the report (waived findings included)

`harness-design-studio drc project`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |

Examples:

```
harness-design-studio drc my-design > drc-report.md
```

### harness-design-studio verify

independently verify the generated harnesses against the interfaces

`harness-design-studio verify project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--outputs` | also check <project>/outputs against the design |

Examples:

```
harness-design-studio verify my-design
harness-design-studio verify my-design --outputs
```

## Generate and export

### harness-design-studio generate

generate harnesses from the interfaces and save the project

`harness-design-studio generate project`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |

Examples:

```
harness-design-studio generate my-design
```

### harness-design-studio export

write the build workbook of every harness, the tables and exports to <project>/outputs and verify them (add --drawings for the PDF drawings)

`harness-design-studio export project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--drawings` | also write the PDF and SVG drawings of the harnesses (off by default: the build workbook is the main output) |

Examples:

```
harness-design-studio export my-design
harness-design-studio export my-design --drawings
```

## Bring in data

### harness-design-studio config

Hand-over checklist for the engineering values (derating, grounding, test limits ...). Exit 1 while something is missing or invalid.

`harness-design-studio config project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `--ampacity-csv AMPACITY_CSV` | CSV with a gauge column and an amperes column; sets derating.ampacity_a_by_awg |
| `--counterparts WORDS` | the words that are the two ends of one line, for the link review and the pairing, for example 'TX=RX, MOSI=MISO' (sets naming.signal_counterparts); 'default' goes back to the table the tool ships with, 'none' pairs equal names only |
| `--apply-profile NAME` | fill the unset values from a standard profile (ecss-q-st-30-11c, ecss-e-st-20-07c); values you already set are kept; the files stay placeholders until you review them |

Examples:

```
harness-design-studio config my-design
harness-design-studio config my-design --ampacity-csv ampacity.csv
harness-design-studio config my-design --apply-profile ecss-q-st-30-11c
harness-design-studio config my-design --counterparts "TX=RX, MOSI=MISO, OUT=IN"
```

### harness-design-studio library

Without options: print the library's name, version, source and date. With options: record them. The date is the date of the data (YYYY-MM-DD) and is entered by you; the tool never reads the clock into a project.

`harness-design-studio library project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `--library-name LIBRARY_NAME` | name of the parts library |
| `--library-version LIBRARY_VERSION` | version of the parts data |
| `--library-source LIBRARY_SOURCE` | where the data comes from (default for import-parts: the file name and its SHA-256) |
| `--library-date YYYY-MM-DD` | date of the data |

Examples:

```
harness-design-studio library my-design
harness-design-studio library my-design --library-version 4 --library-source "ESCC part data, supplier file" --library-date 2026-09-30
```

### harness-design-studio import-parts

Import parts with their approval status. Say what the approval values in your list mean; unknown values are rejected, never guessed.

`harness-design-studio import-parts project file [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `file` | the file to read |
| `--approved APPROVED` | a value of the approval column that means approved (repeat) (repeatable) |
| `--pending PENDING` | a value that means not decided yet (repeat) (repeatable) |
| `--rejected REJECTED` | a value that means not approved (repeat) (repeatable) |
| `--category CATEGORY` | category for rows that have none (connector, contact, backshell, wire, sleeving, label) |
| `--dry-run` | show the preview only |
| `--library-name LIBRARY_NAME` | name of the parts library |
| `--library-version LIBRARY_VERSION` | version of the parts data |
| `--library-source LIBRARY_SOURCE` | where the data comes from (default for import-parts: the file name and its SHA-256) |
| `--library-date YYYY-MM-DD` | date of the data |

Examples:

```
harness-design-studio import-parts my-design parts.csv --approved Approved --pending Review --rejected Rejected --dry-run
harness-design-studio import-parts my-design connectors.xlsx --approved Yes --category connector
```

### harness-design-studio import-lengths

Import segment lengths, for example exported from the mechanical CAD. The columns are read by position (harness, segment, length), not by their headings. Numbers are written with a point (12.5) or, in a quoted cell, a decimal comma (12,5).

`harness-design-studio import-lengths project file [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `file` | the file to read |
| `--unit UNIT` | unit of the length column (default mm) (one of cm, m, mm) |
| `--dry-run` | show what would be done and change nothing |

Examples:

```
harness-design-studio import-lengths my-design lengths.csv --unit mm --dry-run
```

### harness-design-studio import-netlist

Create or update the box connectors of one device from a KiCad netlist (the .net file the schematic editor exports, or kicad-cli sch export netlist; S-expression and XML both work). Pins get fixed signals; generation connects interfaces to the pin of the same name. The user guide has a chapter on it.

`harness-design-studio import-netlist project netlist [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `netlist` | the netlist file to read |
| `--device, --unit DEVICE` | the device these connectors belong to, for example OBC1 (--unit is the older name) |
| `--ref REF` | reference of a connector in the netlist, for example J1 (repeat; default: every component starting with --prefix) (repeatable) |
| `--prefix PREFIX` | reference prefix that marks connectors (default J) |
| `--connector REF=ID` | connector ID for a reference, for example J1=OBC1-J01 (default: the symbol field HarnessConnector, else <device>-<ref>) (repeatable) |
| `--part REF=PART` | library part for a new connector (default: the symbol field HarnessPart, or the existing connector's part) (repeatable) |
| `--signal-map NAME=SIGNAL|FILE` | translate a KiCad net name to an interface signal name (repeatable), or a CSV (net name, signal) or JSON object file of such pairs (repeatable) |
| `--pin-function` | use the pin names of the symbol instead of the net names as signals |
| `--dry-run` | show what would be done and change nothing |

Examples:

```
harness-design-studio import-netlist my-design wheel.net --device RW1 --prefix J --connector J1=RW1-J01 --signal-map CAN_H=CANH --dry-run
```

### harness-design-studio import-pinout

Create or update the box connectors of one device from a table: one row per pin with the connector, the pin, the signal, whether the device fixes it, a contact size and a termination. Columns are matched by their headings (Connector, Pin, Signal, Mode or Fixed, Contact size, Termination, Part, Gender); columns the project cannot store, such as a description or a voltage, are named in a warning and left out. A row with a problem stops the whole import; nothing is changed then. A new connector needs a library part (a Part column, --part J1=PART or --default-part). The user guide has a chapter on it.

`harness-design-studio import-pinout project file [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `file` | the file to read |
| `--device, --unit DEVICE` | the device the connectors belong to, for example GYRO1 (--unit is the older name) |
| `--new-device NAME` | create the device with this name when it does not exist |
| `--subsystem SUBSYSTEM` | subsystem of a new device (default: the most used one) |
| `--part REF=PART` | library part for a new connector, for example J1=MY-HD-9-F (repeat) (repeatable) |
| `--default-part DEFAULT_PART` | library part for new connectors that have none |
| `--gender GENDER` | gender of new connectors (default: the part's) (one of female, male) |
| `--connector CONNECTOR` | connector for rows of a table that has no Connector column (default J01) |
| `--column FIELD=HEADING` | use this column for a field when the headings are not recognised, for example pin=Contact (repeat) (repeatable) |
| `--replace` | drop the pins of an existing connector that the table does not name (default: keep them) |
| `--dry-run` | show the preview only |

Examples:

```
harness-design-studio import-pinout my-design gyro-pinout.csv --device GYRO1 --default-part MY-HD-9-F --dry-run
harness-design-studio import-pinout my-design icd.xlsx --device CAM1 --new-device "Camera" --part J1=MY-HD-9-F --part J2=MY-HD-15-M
```

### harness-design-studio import-devices

Add the devices of a device library file with their connectors, pinouts, parts and interface types. A device never replaces one of the project: a taken ID gets the next free one (GYRO1 becomes GYRO1-2). Parts and interface types the project already has are kept as they are. Use --list to see what the file holds.

`harness-design-studio import-devices project file [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `file` | the file to read |
| `--device, --unit DEVICE` | a device of the file to add (repeat; default: all; --unit is the older name) (repeatable) |
| `--list` | list the devices of the file and stop |
| `--dry-run` | show the preview only |

Examples:

```
harness-design-studio import-devices my-design device-library.json --list
harness-design-studio import-devices my-design device-library.json --device GYRO1 --dry-run
```

### harness-design-studio import-subsystem

Add the devices of a subsystem library file with their connectors and pinouts, and the connections between them, as one step. The subsystem of every added device becomes the name of the subsystem. Nothing of the project is replaced: a taken device ID gets the next free one (OBC1 becomes OBC1-2) and the connections follow. It is all or nothing: when one device or connection cannot be added, nothing is. Use --show to see what the file holds.

`harness-design-studio import-subsystem project file [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `file` | the file to read |
| `--show` | show what the file holds and stop |
| `--dry-run` | show the preview only |

Examples:

```
harness-design-studio import-subsystem my-design wheel-drive.json --show
harness-design-studio import-subsystem my-design wheel-drive.json --dry-run
```

### harness-design-studio import-build-data

Import the build data of a technician from a table. The kind is told by the column headings (any case; other columns are ignored): strip lengths (Wire, Strip A (mm), Strip B (mm); Harness is optional while the wire ID is unique), pin contacts (Harness, Connector, Pin, Contact; Tool is optional and sets the crimp tool of that contact part), accessories (Harness, Kind, Part, Target, Position, Length (mm), Quantity, Note; ID is optional, else they are numbered ACC-001 ...) or part tools (Part, Tool). An empty cell leaves the value as it is. A pin of a harness made by Generate takes its contact from the device's pin (Devices tab) and refuses the row. The preview lists every row; a row with a problem stops the whole import and nothing is changed. Templates: strip-lengths.csv, pin-contacts.csv and accessories.csv (harness-design-studio templates FOLDER).

`harness-design-studio import-build-data project file [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `file` | the file to read |
| `--dry-run` | show the preview only |

Examples:

```
harness-design-studio import-build-data my-design strip-lengths.csv --dry-run
harness-design-studio import-build-data my-design pin-contacts.csv
harness-design-studio import-build-data my-design accessories.csv
```

## Write data out

### harness-design-studio export-pinout

Write the rows of system/box_pinouts.csv that belong to one device (connector, pin, signal, interface, wires, spare) to a file, or to the screen as CSV. The format follows the file name (.csv, .tsv or .xlsx; another ending is refused). The rows are the ones export writes, so the file compares with an interface control document.

`harness-design-studio export-pinout project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `--device, --unit DEVICE` | the device to write, for example GYRO1 (--unit is the older name) |
| `--output, -o OUTPUT` | the file to write (default: CSV on the screen) |

Examples:

```
harness-design-studio export-pinout my-design --device GYRO1
harness-design-studio export-pinout my-design --device GYRO1 -o gyro-pinout.xlsx
```

### harness-design-studio export-devices

Write one or more devices, their box connectors with every pin (signal, function, contact size, termination), and the parts and interface types they name to a device library file (JSON). A file that exists is added to and the other devices in it stay. A device with the same ID in the file that differs is NOT replaced unless you say --replace; a part never gets a lower approval than the file has. What generation allocated in this project does not travel. The folder of the file must exist.

`harness-design-studio export-devices project file [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `file` | the device library file to write or add to |
| `--device, --unit DEVICE` | a device to save, for example GYRO1 (repeat for more; --unit is the older name) (repeatable) |
| `--replace` | replace a device of the same ID in the file that differs (without it that is refused) |

Examples:

```
harness-design-studio export-devices my-design device-library.json --device GYRO1
harness-design-studio export-devices my-design device-library.json --device OBC1 --device PCU1
```

### harness-design-studio export-subsystem

Write devices with their connectors and pinouts, and the connections between them, to a subsystem library file (JSON), so the set can be added to another project in one step. A connection with an end on a device that is not chosen is left out. A file that exists is never replaced unless you say --replace. The folder of the file must exist.

`harness-design-studio export-subsystem project file [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `file` | the subsystem library file to write |
| `--device, --unit DEVICE` | a device of the subsystem, for example OBC1 (repeat for more; --unit is the older name) (repeatable) |
| `--name NAME` | the name of the subsystem |
| `--description DESCRIPTION` | what the subsystem is (optional) (default ) |
| `--notes NOTES` | notes for whoever adds it (optional) (default ) |
| `--replace` | replace the file when it exists |

Examples:

```
harness-design-studio export-subsystem my-design wheel-drive.json --device OBC1 --device RW1 --name "Wheel drive"
```

## Review, release and change

### harness-design-studio review

submit a draft harness for review

`harness-design-studio review project harness [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `harness` | harness ID, for example W001 |
| `--by BY` | your name (recorded in the change log) |
| `--date DATE` | YYYY-MM-DD (default: today) |

Examples:

```
harness-design-studio review my-design W001 --by "A. Engineer"
```

### harness-design-studio release

release a harness: baseline, change log entry and lock (blocked while checks fail)

`harness-design-studio release project harness [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `harness` | harness ID, for example W001 |
| `--by BY` | your name (recorded in the change log) |
| `--comment COMMENT` | what changed or why (at least 10 characters) |
| `--date DATE` | YYYY-MM-DD (default: today) |
| `--checker CHECKER` | who checked it (title block) |
| `--accept-placeholders REASON` | release although configuration files are still placeholders: the reason (at least 10 characters) is kept in the change log and the baseline |
| `--accept-unapproved-parts REASON` | release although the harness uses parts that are not approved (or are example data): the reason (at least 10 characters) is kept in the change log and the baseline |

Examples:

```
harness-design-studio release my-design W001 --by "A. Engineer" --comment "First release" --checker "B. Checker"
```

### harness-design-studio revise

start a new revision of a released harness

`harness-design-studio revise project harness [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `harness` | harness ID, for example W001 |
| `--by BY` | your name (recorded in the change log) |
| `--comment COMMENT` | what changed or why (at least 10 characters) |
| `--date DATE` | YYYY-MM-DD (default: today) |

Examples:

```
harness-design-studio revise my-design W001 --by "A. Engineer" --comment "Connector change"
```

### harness-design-studio diff

show what changed in a harness since a baseline (or between two baselines)

`harness-design-studio diff project harness [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `harness` | harness ID, for example W001 |
| `--from REV_FROM` | baseline revision to compare from (default: latest) |
| `--to REV_TO` | baseline revision to compare to (default: the working design) |

Examples:

```
harness-design-studio diff my-design W001
harness-design-studio diff my-design W001 --from A
```

### harness-design-studio log

print the change log

`harness-design-studio log project [harness]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `harness` | limit to one harness |

Examples:

```
harness-design-studio log my-design
harness-design-studio log my-design W001
```

### harness-design-studio compare

Compare two project folders object by object.

`harness-design-studio compare old new`

| Argument | Meaning |
| --- | --- |
| `old` | the project folder to compare from |
| `new` | the project folder to compare with |

Examples:

```
harness-design-studio compare old-checkout new-checkout
```

## Maintenance

### harness-design-studio migrate

upgrade an old-format project in place (originals are kept)

`harness-design-studio migrate project`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |

Examples:

```
harness-design-studio migrate my-design
```
