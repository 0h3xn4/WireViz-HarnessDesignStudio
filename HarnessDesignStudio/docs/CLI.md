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

An import whose file says what the project already holds changes nothing, prints `Already up to date.` and ends with 0, so it can run again on every build. Every command that changes a project takes the same lock as the app, so the two never write at once. The commands that import data (`import-parts`, `import-lengths`, `import-build-data`, `import-netlist`, `import-pinout`, `import-devices`) accept `--dry-run`: they show what they would do and change nothing; `config --ampacity-csv` does not. The option `--author NAME` (given before the command) names who is making the changes of a run in the change journal of a project that has one; the environment variable `HARNESS_AUTHOR` does the same, and without either the journal uses the name Git has (`user.name`), then the user of the computer.

What an import prints. Every import that reads a file says what it read before it lists the rows: `Read 12 row(s) of segment lengths from lengths.csv (sha256 117043908312).`, `Columns read: harness -> harness, segment -> segment, length -> length`, a line `warning: the column 'Notes' is not read; its values are not imported.` for every column that is left out, and the unit: `Unit: length in mm (assumed; --unit says another).` or `Unit: length in in (given with --unit).`. A value that is converted is shown with the value as written, its unit and the value stored: `Converted, row 2 (ZZ-1): 0.25 kg = 250 g`; `import-lengths` shows it on the line of its row, `row 2: OK W001 / W001-L1: 850 mm = 0.85 m`. A row that is dropped says why: `row 3: ERROR Harness 'W009' does not exist`. An import that is applied (not with `--dry-run`) records the file in the project, in `imports/records.json` (kind, file name, SHA-256, rows read, rows dropped with the reason, values converted, columns read and left out, unit, tool version; no time and no absolute path), and ends with `Import record: lengths:lengths.csv written to imports/records.json.`; importing the same file again replaces its record, and an unchanged file changes nothing. `harness-design-studio imports` lists the records and shows whether a source file has changed since. With `--json` every import prints the same facts as the last key, `import` (the record, with `record_written` true when this run wrote it, and the `warnings` of `import-build-data`), and `imports --json` prints `records_file`, `count`, `sources_changed` and the `imports` with their `status` and `current_sha256`.

The examples show the form of each command with example names. They do not all work on any project: `release` is blocked until its conditions are met (placeholder configuration, unapproved parts, missing gauges and lengths; see [`GETTING_STARTED.md`](GETTING_STARTED.md)), and `revise` works only on a released harness.

## Contents

- [JSON output](#json-output): `--json` on every command that has a result in data form
- Start: [`new`](#harness-design-studio-new), [`templates`](#harness-design-studio-templates), [`schema`](#harness-design-studio-schema)
- Check: [`validate`](#harness-design-studio-validate), [`check`](#harness-design-studio-check), [`drc`](#harness-design-studio-drc), [`verify`](#harness-design-studio-verify)
- Explain: [`explain`](#harness-design-studio-explain), [`settings`](#harness-design-studio-settings)
- Overrides and change history: [`override`](#harness-design-studio-override), [`deviation`](#harness-design-studio-deviation), [`journal`](#harness-design-studio-journal)
- Generate and export: [`generate`](#harness-design-studio-generate), [`export`](#harness-design-studio-export), [`export-data`](#harness-design-studio-export-data)
- Team use with Git: [`merge-fix`](#harness-design-studio-merge-fix)
- Bring in data: [`config`](#harness-design-studio-config), [`library`](#harness-design-studio-library), [`import-parts`](#harness-design-studio-import-parts), [`import-lengths`](#harness-design-studio-import-lengths), [`import-netlist`](#harness-design-studio-import-netlist), [`import-pinout`](#harness-design-studio-import-pinout), [`import-devices`](#harness-design-studio-import-devices), [`import-subsystem`](#harness-design-studio-import-subsystem), [`import-build-data`](#harness-design-studio-import-build-data), [`imports`](#harness-design-studio-imports)
- Write data out: [`export-pinout`](#harness-design-studio-export-pinout), [`export-devices`](#harness-design-studio-export-devices), [`export-subsystem`](#harness-design-studio-export-subsystem)
- Review, release and change: [`review`](#harness-design-studio-review), [`release`](#harness-design-studio-release), [`revise`](#harness-design-studio-revise), [`diff`](#harness-design-studio-diff), [`log`](#harness-design-studio-log), [`compare`](#harness-design-studio-compare)
- Extend the tool: [`extensions`](#harness-design-studio-extensions), [`trust`](#harness-design-studio-trust), [`import-plugin`](#harness-design-studio-import-plugin)
- Maintenance: [`migrate`](#harness-design-studio-migrate)

## JSON output

Every command that has a result in data form takes `--json`. The usual text lines are then not printed; one JSON document is, and the exit code is the one the command has without the option (the table above). It has no time, no user name and no absolute path, its lists are in a fixed order (by ID, as the text shows them) and the same design gives the same bytes, so it can be compared and kept in Git. `ok` comes first and is true when the exit code is 0. A command that cannot run at all (a project that cannot be read, a wrong option) writes its message to the standard error as before and prints nothing to the standard output; a command that ran and was refused (`generate` with errors, `export` that failed its check, `release` that is blocked) still prints its document, with `ok` false and the reasons in it. The same documents are what the Python interface gives ([`user-manual/script-the-tool.md`](user-manual/script-the-tool.md)).

`explain OBJECT --json` prints a list of derivations and `settings --json` the document of settings, definitions and assumptions, both as they did before (neither has an `ok`); `explain --all --out FOLDER --json` prints the document below. `export --out FOLDER` writes the outputs to FOLDER instead of `<project>/outputs`. `export` and `generate` take `--run-record [--author NAME]`: the record of the run (`run_record.json`) is then written into the outputs folder, outside every hash, and their document gains the key `run_record` (the name of the file); without the option no record is written and the document is as listed. `config` prints every engineering value with its unit, its use, whether it is set and where it came from, and the values it refused, in the order of the hand-over list.

| Command | Keys of the document |
| --- | --- |
| `new` | `ok`, `name`, `template`, `devices`, `interfaces` |
| `new --list` | `ok`, `templates` |
| `templates`, `schema` | `ok`, `count`, `files` |
| `validate`, `check` | `ok`, `devices`, `interfaces`, `connectors`, `harnesses`, `errors`, `warnings`, `issues` |
| `drc` | `ok`, `model_hash`, `rules_run`, `open_errors`, `open_warnings`, `open_notes`, `waived`, `placeholder_config`, `findings` |
| `verify` | `ok`, `interfaces_checked`, `wires_checked`, `stale`, `issues` |
| `settings` | `settings`, `definitions`, `assumptions` |
| `explain --all` | `ok`, `count`, `without_value`, `files` |
| `export-data` | `ok`, `count`, `model_hash`, `files`, `run_record` |
| `generate` | `ok`, `saved`, `added`, `changed`, `unchanged`, `removed`, `frozen`, `kept_locks`, `findings`, `interfaces_checked`, `wires_checked`, `verify_issues` |
| `export` | `ok`, `written`, `blocked`, `model_hash`, `drawings_removed`, `file_count`, `files`, `issues` |
| `merge-fix` | `ok`, `result`, `conflicts`, `problem`, `generate`, `check` |
| `config` | `ok`, `set_count`, `total`, `values`, `problems`, `placeholder_files`, `waiting_for_decision`, `counterpart_pairs`, `release_distinct_roles`, `changes` |
| `library` | `ok`, `name`, `version`, `source`, `date`, `changed` |
| `import-parts` | `ok`, `dry_run`, `changed`, `ready`, `problems`, `rows`, `library`, `import` |
| `import-lengths` | `ok`, `dry_run`, `changed`, `ready`, `problems`, `hint`, `rows`, `import` |
| `import-build-data` | `ok`, `dry_run`, `changed`, `kind`, `counts`, `rows`, `import` |
| `import-netlist` | `ok`, `dry_run`, `changed`, `rows`, `warnings`, `unmatched_signals`, `import` |
| `import-pinout` | `ok`, `dry_run`, `changed`, `connectors`, `pins`, `rows`, `warnings`, `unmatched_signals`, `import` |
| `import-devices` | `ok`, `dry_run`, `changed`, `rows`, `notes`, `import` |
| `import-devices --list` | `ok`, `devices` |
| `import-subsystem` | `ok`, `dry_run`, `changed`, `name`, `connections`, `rows`, `notes`, `import` |
| `imports` | `ok`, `records_file`, `count`, `sources_changed`, `imports` |
| `import-subsystem --show` | `ok`, `name`, `description`, `devices`, `connectors`, `connections`, `device_list` |
| `export-pinout` | `ok`, `device`, `pin_rows`, `columns`, `rows`, `written` |
| `export-devices` | `ok`, `devices`, `connectors`, `notes` |
| `export-subsystem` | `ok`, `name`, `devices`, `connectors`, `connections` |
| `review`, `release`, `revise` | `ok`, `action`, `by`, `blockers`, `outputs` |
| `diff` | `ok`, `harness`, `from`, `to`, `added`, `removed`, `changed`, `changes` |
| `compare` | `ok`, `added`, `removed`, `changed`, `changes`, `not_compared` |
| `log` | `ok`, `harness`, `entries` |
| `migrate` | `ok`, `migrated` |
| `journal` | `ok`, `has_journal`, `count`, `entries` |
| `journal --start` | `ok`, `started`, `file` |
| `override` | `ok`, `wire`, `action`, `changed`, `overrides`, `derivation` |
| `deviation` | `ok`, `action`, `finding`, `count`, `deviations` |
| `extensions` | `ok`, `has_folder`, `enabled_declarative`, `enabled_plugins`, `files`, `plugins`, `items`, `issues` |
| `trust` | `ok`, `action`, `name`, `version`, `sha256`, `lines`, `where`, `trusted`, `changed` |
| `import-plugin` | `ok`, `dry_run`, `changed`, `importer`, `rows`, `notes` |

## Start

### harness-design-studio new

Create a project folder from one of the bundled examples. `harness-design-studio new --list` shows them. The folder must not exist yet or be empty. The new project starts a change journal (journal.json: who changed what, when and why) unless you give --no-journal.

`harness-design-studio new [folder] [options]`

| Argument | Meaning |
| --- | --- |
| `folder` | the new project folder |
| `--template TEMPLATE` | which example to start from (default blank) |
| `--name NAME` | project name (default: the example's name) |
| `--list` | list the examples and exit |
| `--no-journal` | do not start a change journal (journal.json) for the new project |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio new --list
harness-design-studio new --list --json
harness-design-studio new my-design --name "My first design"
harness-design-studio new wheel-link --template first-steps
```

### harness-design-studio templates

Copy the bundled templates for the imports, CI scripts and the review checklist. The folder must not exist yet or be empty.

`harness-design-studio templates folder [options]`

| Argument | Meaning |
| --- | --- |
| `folder` | where to put the templates |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio templates my-templates
harness-design-studio templates my-templates --json
```

### harness-design-studio schema

Write one JSON Schema per kind of project file, made from the program's own model, and a settings fragment that maps the files to them. For people who edit project files by hand. Nothing is downloaded. The folder must not exist yet or be empty.

`harness-design-studio schema folder [options]`

| Argument | Meaning |
| --- | --- |
| `folder` | where to put the schemas (for example my-design/schemas) |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio schema my-design/schemas
harness-design-studio schema my-design/schemas --json
```

## Check

### harness-design-studio validate

check a project folder for errors and inconsistencies

`harness-design-studio validate project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio validate my-design
harness-design-studio validate my-design --json
```

### harness-design-studio check

validate, plus detect problems left behind by Git merges

`harness-design-studio check project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio check my-design
harness-design-studio check my-design --json
```

### harness-design-studio drc

run the design rule check and print the report (waived findings included)

`harness-design-studio drc project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio drc my-design > drc-report.md
harness-design-studio drc my-design --json > drc-findings.json
```

### harness-design-studio verify

independently verify the generated harnesses against the interfaces

`harness-design-studio verify project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |
| `--outputs` | also check <project>/outputs against the design |

Examples:

```
harness-design-studio verify my-design
harness-design-studio verify my-design --outputs
harness-design-studio verify my-design --json
```

## Explain

### harness-design-studio explain

Show how the numbers and decisions of one object were made. For a wire: its length, the current its gauge may carry after derating, the voltage drop over it and its share of the mass, then its label, its colour, its shield group and the pins at its ends. For a harness: its mass, whether it is ready to build and each check behind that, its test limits, why its interfaces share it, its shield groups and its connectors; HARNESS.T001 explains the limits of one test. For an interface: which harness carries it and why, its connectors, the contact current and its pins. For a connector: why it is the connector (or the mating part) and its label; for CONNECTOR.PIN: why the signal is on that pin; for a shield group (W001-S1): why it exists and its ends. For a part: why the bill of materials has its quantity. For INTERFACE.CONNECTOR (the object of a current-over-contact finding): the limit of the contacts. For each: the equation, the inputs with their units and where each comes from (a key of config/*.json, a field of the design or the program), the intermediate results, what the result is checked against, and the assumptions built into the program that it rests on. The numbers are the ones `generate` and `drc` use. `--json` prints the same as data (a list). With `--all --out FOLDER` it writes every derivation of the project to FOLDER as `derivations.json` and `derivations.csv`: no time, user or path is in them, so the same design gives the same files; with `--json` as well it prints how many it wrote instead of the line of text. Without `--out` nothing is written.

`harness-design-studio explain project [OBJECT] [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `OBJECT` | a wire (W001-001), a harness (W001), a test (W001.T001), an interface (IF-001), a connector (GPSU1-J01), a pin (MTQ1-J01.1), a shield group (W001-S1), a part (EX-WIRE-SINGLE) or INTERFACE.CONNECTOR (IF-001.GPSU1-J01) |
| `--json` | print the derivations as JSON |
| `--all` | every derivation of the project (instead of OBJECT) |
| `--out OUT` | with --all: the folder for derivations.json and derivations.csv |

Examples:

```
harness-design-studio explain wheel-link W001-001
harness-design-studio explain wheel-link W001
harness-design-studio explain wheel-link EX-WIRE-SINGLE
harness-design-studio explain wheel-link --all --out wheel-link-derivations
harness-design-studio explain wheel-link IF-001.GPSU1-J01
harness-design-studio explain wheel-link W001-001 --json
harness-design-studio explain wheel-link --all --out wheel-link-derivations --json
```

### harness-design-studio settings

The Assumptions page on the command line. For every setting: the value in force, its unit, whether it is set by the project, the tool's own default (the behaviour before the setting existed) or not set, what depends on it and where the number comes from; then the assumptions built into the tool, each with the settings that parameterise it, and the fixed definitions. `--json` prints the same as data. `--set FILE.KEY=VALUE` (VALUE is JSON, for example model.service_loops_per_wire=0) changes one value; it is refused, and nothing is changed, when the value is outside its range.

`harness-design-studio settings project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--json` | print the settings as JSON |
| `--set FILE.KEY=VALUE` | set one value (VALUE as JSON, for example model.service_loops_per_wire=0); repeat for several (repeatable) |

Examples:

```
harness-design-studio settings wheel-link
harness-design-studio settings wheel-link --json
harness-design-studio settings wheel-link --set model.service_loops_per_wire=0
```

## Overrides and change history

### harness-design-studio override

Override a value of a generated wire deliberately: `override DIR WIRE FIELD VALUE --reason TEXT` (FIELD is gauge_awg, part_id, colour or length_m). A reason is required and is refused when it is empty. The tool keeps the value when the harnesses are generated again, records the reason with the wire (who and when in the journal), flags the wire everywhere, and explains the consequences: the value the design would give, and the current limit and voltage drop of the value you set. `--clear FIELD` gives one field back to generation (the value is cleared; the next `generate` gives the wire the design's value). With no FIELD it shows the overrides of the wire. A released harness cannot be changed.

`harness-design-studio override project wire [field] [value] [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `wire` | wire ID, for example W001-001 |
| `field` | gauge_awg, part_id, colour or length_m |
| `value` | the value to set |
| `--reason REASON` | why (required with a value) |
| `--clear FIELD` | give this field back to generation |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio override wheel-link W001-001 gauge_awg 20 --reason "Heater load added after CDR, see ECR-114"
harness-design-studio override wheel-link W001-001 length_m 2.4 --reason 'Measured on the mock-up'
harness-design-studio override wheel-link W001-001
harness-design-studio override wheel-link W001-001 --clear gauge_awg
```

### harness-design-studio deviation

A deviation accepts an error of an electrical rule (wire current, voltage drop, contact current, bundle current, working voltage, temperature margin) with a reason, keeps it visible everywhere marked as a deviation, and lets a release go on. `deviation DIR` lists them, with who and when from the journal; `deviation DIR FINDING --reason TEXT` records one (FINDING is the finding ID of `drc`, for example current-over-wire.W001-001; the reason is at least 10 characters); `--remove` takes it back. A deviation does not meet the requirement: it records that a person accepted the error.

`harness-design-studio deviation project [finding] [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `finding` | the finding ID |
| `--reason REASON` | why the error is accepted (at least 10 characters) |
| `--remove` | take the deviation back |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio deviation wheel-link
harness-design-studio deviation wheel-link current-over-wire.W001-001 --reason "Accepted by the PA board, NCR-17"
harness-design-studio deviation wheel-link current-over-wire.W001-001 --remove
```

### harness-design-studio journal

The change journal: an entry for every change of a design input, a configuration value, an override, a waiver or deviation, a part approval and a release, with who made it, when (UTC), the value before and after, and the reason where the model holds one. Entries are made when the project is saved, so every way of changing it is recorded; generation is one entry for each harness. The journal is the file journal.json, which a project has only if you start one (`new` starts one; `--start` starts one for an existing project): it is append-only, an entry cannot be changed or removed, and a damaged journal is reported by `validate`. It is not part of the model hash or of any written output. The author is the global option `--author`, else the environment variable HARNESS_AUTHOR, else the name Git has (`user.name`), else the user of the computer. `--json` prints the entries as one document; `--object` selects one object (W001-001, wire:W001-001, derating.bundle_derating); `--since SEQ` the entries after number SEQ.

`harness-design-studio journal project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |
| `--since SEQ` | only entries numbered above SEQ |
| `--object ID` | only entries about this object |
| `--start` | start a journal for a project that has none (writes journal.json) |

Examples:

```
harness-design-studio journal wheel-link
harness-design-studio journal wheel-link --start
harness-design-studio journal wheel-link --object W001-001
harness-design-studio journal wheel-link --since 12 --json
harness-design-studio --author 'A. Engineer' override wheel-link W001-001 colour red --reason 'Colour code of the program'
```

## Generate and export

### harness-design-studio generate

generate harnesses from the interfaces and save the project

`harness-design-studio generate project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |
| `--run-record` | also write run_record.json (time in UTC, operator, tool version, platform, Python version, model hash) next to the files: it is outside every hash, and written only with this option |
| `--author NAME` | with --run-record: who ran it (default: the environment variable HARNESS_AUTHOR, then the Git user.name, then the user of the system) |

Examples:

```
harness-design-studio generate my-design
harness-design-studio generate my-design --json
harness-design-studio generate my-design --run-record
```

### harness-design-studio export

write the build workbook of every harness, the tables and exports to <project>/outputs and verify them (add --drawings for the PDF drawings)

`harness-design-studio export project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |
| `--run-record` | also write run_record.json (time in UTC, operator, tool version, platform, Python version, model hash) next to the files: it is outside every hash, and written only with this option |
| `--author NAME` | with --run-record: who ran it (default: the environment variable HARNESS_AUTHOR, then the Git user.name, then the user of the system) |
| `--drawings` | also write the PDF and SVG drawings of the harnesses (off by default: the build workbook is the main output) |
| `--out OUT` | the folder to write the outputs to (default: <project>/outputs) |

Examples:

```
harness-design-studio export my-design
harness-design-studio export my-design --drawings
harness-design-studio export my-design --out my-outputs --json
harness-design-studio export my-design --run-record --author "A. Engineer"
```

### harness-design-studio export-data

Write the numbers behind the outputs to FOLDER as open data. For each result a JSON file (with a format number, the tool version, the model hash, the columns with their units and the rows) and a CSV file with the same rows and the unit in each heading: wire_sizing (current, gauge and its cross-section in mm², ampacity, the derating factors, the bundle size, the limit, the length, the voltage drop and its limit and margin, the part), segmentation_groups and segmentation_interfaces, pin_allocation, rule_results (actual, limit, margin, verdict), readiness, lengths (with the basis of each), mass and mass_wires, bom and bom_contributions, findings, test_limits and settings (every setting in force with its value, unit and origin); also configuration.json (the configuration files as the tool used them, with their placeholder flags) and provenance.json (tool version, model hash, the files imported, and a hash of every other file written). No file holds a time, a user name or a path, so the same design written twice gives the same bytes. With --run-record, run_record.json is written beside them (time, operator, tool version): it is not part of the set. The project is not changed. `--json` prints the list of files.

`harness-design-studio export-data project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--out OUT` | the folder for the files (made if missing) |
| `--run-record` | also write run_record.json (time in UTC, operator, tool version, platform, Python version, model hash) next to the files: it is outside every hash, and written only with this option |
| `--author NAME` | with --run-record: who ran it (default: the environment variable HARNESS_AUTHOR, then the Git user.name, then the user of the system) |
| `--json` | print the list of files as JSON |

Examples:

```
harness-design-studio export-data my-design --out my-design-data
harness-design-studio export-data my-design --out my-design-data --json
harness-design-studio export-data my-design --out my-design-data --run-record --author "A. Engineer"
```

## Team use with Git

### harness-design-studio merge-fix

After a Git merge in which two people each pressed Generate, `generated/generation.json` conflicts. This command keeps this branch's version of that one file, then runs `generate` (which writes the record again for the merged design) and `check`. It refuses, and changes nothing, when any other file of the project is in conflict, and it writes nothing itself apart from that record and what `generate` writes. Commit the result afterwards.

`harness-design-studio merge-fix project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio merge-fix my-design
harness-design-studio merge-fix my-design --json
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
| `--distinct-roles DISTINCT_ROLES` | on: a release needs an author, a checker and a person who releases that are three different people, a date that is not earlier than the project's change log and not more than a day ahead, and takes a missing name from Git (sets naming.release_distinct_roles); off: the setting is taken out again (the default) (one of off, on) |
| `--apply-profile NAME` | fill the unset values from a standard profile (ecss-q-st-30-11c, ecss-e-st-20-07c); values you already set are kept; the files stay placeholders until you review them |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio config my-design
harness-design-studio config my-design --json
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
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio library my-design
harness-design-studio library my-design --json
harness-design-studio library my-design --library-version 4 --library-source "ESCC part data, supplier file" --library-date 2026-09-30
```

### harness-design-studio import-parts

Import parts with their approval status. Say what the approval values in your list mean; unknown values are rejected, never guessed. A column headed with the name of a rating (contact_current_a, rated_voltage_v, dielectric_withstand_v, max_temp_c, mating_cycles, shield_insulated, conductive_finish) is read into the ratings of the part. Masses are read in grams unless --mass-unit says another unit. The import says which columns it read and which it left out, and records the file (name, SHA-256, rows, columns, conversions) in imports/records.json; see `harness-design-studio imports`.

`harness-design-studio import-parts project file [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `file` | the file to read |
| `--approved APPROVED` | a value of the approval column that means approved (repeat) (repeatable) |
| `--pending PENDING` | a value that means not decided yet (repeat) (repeatable) |
| `--rejected REJECTED` | a value that means not approved (repeat) (repeatable) |
| `--category CATEGORY` | category for rows that have none (connector, contact, backshell, wire, sleeving, label) |
| `--mass-unit MASS_UNIT` | unit of the mass columns (mass per metre: this unit per metre); default g, the unit the columns have always been read in (one of g, kg, lb, oz) |
| `--dry-run` | show the preview only |
| `--library-name LIBRARY_NAME` | name of the parts library |
| `--library-version LIBRARY_VERSION` | version of the parts data |
| `--library-source LIBRARY_SOURCE` | where the data comes from (default for import-parts: the file name and its SHA-256) |
| `--library-date YYYY-MM-DD` | date of the data |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio import-parts my-design parts.csv --approved Approved --pending Review --rejected Rejected --dry-run
harness-design-studio import-parts my-design parts.csv --approved Approved --dry-run --json
harness-design-studio import-parts my-design connectors.xlsx --approved Yes --category connector
harness-design-studio import-parts my-design erp-export.csv --approved Released --mass-unit kg
```

### harness-design-studio import-lengths

Import segment lengths, for example exported from the mechanical CAD. The columns are read by position (harness, segment, length), not by their headings. Numbers are written with a point (12.5) or, in a quoted cell, a decimal comma (12,5). The unit of the length column is millimetres unless --unit says another. The command echoes what it did: the unit, and for every row `row N: OK HARNESS / SEGMENT: READ UNIT = STORED m` (the value as written, the unit it was read in, the metres that were stored); a row that is dropped says why (`row N: ERROR reason`); a column that is not read is named in a warning. The file (name, SHA-256, rows, the conversions) is recorded in imports/records.json.

`harness-design-studio import-lengths project file [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `file` | the file to read |
| `--unit UNIT` | unit of the length column (default mm, the unit it has always been read in; the echo says whether the unit was given or assumed) (one of cm, ft, in, m, mm) |
| `--dry-run` | show what would be done and change nothing |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio import-lengths my-design lengths.csv --unit mm --dry-run
harness-design-studio import-lengths my-design lengths.csv --dry-run --json
harness-design-studio import-lengths my-design lengths-in-inches.csv --unit in
```

### harness-design-studio import-netlist

Create or update the box connectors of one device from a KiCad netlist (the .net file the schematic editor exports, or kicad-cli sch export netlist; S-expression and XML both work). Pins get fixed signals; generation connects interfaces to the pin of the same name. The import record keeps the design source of the netlist (the name of the schematic file) and the KiCad pin type of every pin, and says which parts of the components it did not import. The user guide has a chapter on it.

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
| `--pin-direction` | also set the direction of a pin that has none from the KiCad pin type (input, output, bidirectional; other types set nothing) |
| `--dry-run` | show what would be done and change nothing |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio import-netlist my-design wheel.net --device RW1 --prefix J --connector J1=RW1-J01 --signal-map CAN_H=CANH --dry-run
harness-design-studio import-netlist my-design wheel.net --device RW1 --dry-run --json
harness-design-studio import-netlist my-design wheel.net --device RW1 --pin-direction
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
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio import-pinout my-design gyro-pinout.csv --device GYRO1 --default-part MY-HD-9-F --dry-run
harness-design-studio import-pinout my-design gyro-pinout.csv --device GYRO1 --default-part MY-HD-9-F --dry-run --json
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
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio import-devices my-design device-library.json --list
harness-design-studio import-devices my-design device-library.json --dry-run --json
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
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio import-subsystem my-design wheel-drive.json --show
harness-design-studio import-subsystem my-design wheel-drive.json --dry-run
harness-design-studio import-subsystem my-design wheel-drive.json --dry-run --json
```

### harness-design-studio import-build-data

Import the build data of a technician from a table. The kind is told by the column headings (any case; other columns are ignored): strip lengths (Wire, Strip A (mm), Strip B (mm); Harness is optional while the wire ID is unique), pin contacts (Harness, Connector, Pin, Contact; Tool is optional and sets the crimp tool of that contact part), accessories (Harness, Kind, Part, Target, Position, Length (mm), Quantity, Note; ID is optional, else they are numbered ACC-001 ...) or part tools (Part, Tool). An empty cell leaves the value as it is. A pin of a harness made by Generate takes its contact from the device's pin (Devices tab) and refuses the row. The preview lists every row; a row with a problem stops the whole import and nothing is changed. Templates: strip-lengths.csv, pin-contacts.csv and accessories.csv (harness-design-studio templates FOLDER).

`harness-design-studio import-build-data project file [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `file` | the file to read |
| `--unit UNIT` | unit of the strip and accessory lengths (default mm, the unit they have always been read in; they are stored in millimetres) (one of cm, ft, in, m, mm) |
| `--dry-run` | show the preview only |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio import-build-data my-design strip-lengths.csv --dry-run
harness-design-studio import-build-data my-design strip-lengths.csv --dry-run --json
harness-design-studio import-build-data my-design pin-contacts.csv
harness-design-studio import-build-data my-design accessories.csv
harness-design-studio import-build-data my-design strip-lengths-in-inches.csv --unit in
```

### harness-design-studio imports

List the import records of a project (imports/records.json): for every import the kind, the source file name, the number of rows read, dropped and converted, the unit, and a short SHA-256. A source that can be reached (its path inside the project folder, or a file you name with --source) is compared with the recorded SHA-256 and marked `source changed` when it differs; the other sources are marked `not checked (no path)` or `source not found`. The record holds no time and no absolute path. With --json the records and their status are printed as one JSON document. With --check the command ends with 1 when a source has changed, so a build can stop on it.

`harness-design-studio imports project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | the project folder |
| `--source FILE` | a file to compare with the record of the same file name, for a source outside the project folder (repeatable) |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |
| `--check` | end with exit code 1 when a source has changed |

Examples:

```
harness-design-studio imports my-design
harness-design-studio imports my-design --check
harness-design-studio imports my-design --json --source cad/lengths.csv
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
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio export-pinout my-design --device GYRO1
harness-design-studio export-pinout my-design --device GYRO1 -o gyro-pinout.xlsx
harness-design-studio export-pinout my-design --device GYRO1 --json
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
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio export-devices my-design device-library.json --device GYRO1
harness-design-studio export-devices my-design device-library.json --device OBC1 --device PCU1
harness-design-studio export-devices my-design device-library.json --device OBC1 --json
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
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio export-subsystem my-design wheel-drive.json --device OBC1 --device RW1 --name "Wheel drive"
harness-design-studio export-subsystem my-design wheel-drive.json --device OBC1 --name "Wheel drive" --json
```

## Review, release and change

### harness-design-studio review

submit a draft harness for review

`harness-design-studio review project harness [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `harness` | harness ID, for example W001 |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |
| `--by BY` | your name (recorded in the change log; required, except in a project that requires different people (release_distinct_roles): there the name from Git, `user.name`, is used when you leave it out and Git has one) |
| `--date DATE` | YYYY-MM-DD (default: today) |

Examples:

```
harness-design-studio review my-design W001 --by "A. Engineer"
harness-design-studio review my-design W001 --by "A. Engineer" --json
```

### harness-design-studio release

release a harness: baseline, change log entry and lock (blocked while checks fail)

`harness-design-studio release project harness [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `harness` | harness ID, for example W001 |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |
| `--by BY` | your name (recorded in the change log; required, except in a project that requires different people (release_distinct_roles): there the name from Git, `user.name`, is used when you leave it out and Git has one) |
| `--comment COMMENT` | what changed or why (at least 10 characters) |
| `--date DATE` | YYYY-MM-DD (default: today) |
| `--checker CHECKER` | who checked it (title block; required in a project that requires different people) |
| `--accept-placeholders REASON` | release although configuration files are still placeholders: the reason (at least 10 characters) is kept in the change log and the baseline |
| `--accept-unapproved-parts REASON` | release although the harness uses parts that are not approved (or are example data): the reason (at least 10 characters) is kept in the change log and the baseline |

Examples:

```
harness-design-studio release my-design W001 --by "A. Engineer" --comment "First release" --checker "B. Checker"
harness-design-studio release my-design W001 --by "A. Engineer" --comment "First release" --json
```

### harness-design-studio revise

start a new revision of a released harness

`harness-design-studio revise project harness [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `harness` | harness ID, for example W001 |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |
| `--by BY` | your name (recorded in the change log; required, except in a project that requires different people (release_distinct_roles): there the name from Git, `user.name`, is used when you leave it out and Git has one) |
| `--comment COMMENT` | what changed or why (at least 10 characters) |
| `--date DATE` | YYYY-MM-DD (default: today) |

Examples:

```
harness-design-studio revise my-design W001 --by "A. Engineer" --comment "Connector change"
harness-design-studio revise my-design W001 --by "A. Engineer" --comment "Connector change" --json
```

### harness-design-studio diff

show what changed in a harness since a baseline (or between two baselines)

`harness-design-studio diff project harness [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `harness` | harness ID, for example W001 |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |
| `--from REV_FROM` | baseline revision to compare from (default: latest) |
| `--to REV_TO` | baseline revision to compare to (default: the working design) |

Examples:

```
harness-design-studio diff my-design W001
harness-design-studio diff my-design W001 --from A
harness-design-studio diff my-design W001 --json
```

### harness-design-studio log

print the change log

`harness-design-studio log project [harness] [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |
| `harness` | limit to one harness |

Examples:

```
harness-design-studio log my-design
harness-design-studio log my-design W001
harness-design-studio log my-design --json
```

### harness-design-studio compare

Compare two project folders object by object.

`harness-design-studio compare old new [options]`

| Argument | Meaning |
| --- | --- |
| `old` | the project folder to compare from |
| `new` | the project folder to compare with |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio compare old-checkout new-checkout
harness-design-studio compare old-checkout new-checkout --json
```

## Extend the tool

### harness-design-studio extensions

Lists the extensions of a project (the folder `extensions/`): the declarative files (rules, tables and lookup tables written as data) and the Python plug-ins, each with its name, version, source, SHA-256, whether the project enables it and, for Python code, whether you trust it. Without options it lists what the extensions add; with --all it lists the built-in items too. Nothing in the folder runs unless the project enables it in `extensions/enabled.json`, and Python code is not even imported unless you have also trusted that exact code (`trust`). --enable NAME and --disable NAME change enabled.json (NAME is a file such as min-gauge.json, or the name of a plug-in). Exit 1 while something the project enables is not applied.

`harness-design-studio extensions project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--all` | also list the built-in items |
| `--docs` | print the rules of the extensions as a Markdown page, in the form of docs/RULES.md (why, how to fix, requirement IDs, the file or plug-in each comes from) |
| `--enable NAME` | enable a declarative file (its file name) or a plug-in (its name) in extensions/enabled.json; repeat for several (repeatable) |
| `--disable NAME` | take a file or a plug-in out of extensions/enabled.json; repeat for several (repeatable) |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio extensions my-design
harness-design-studio extensions my-design --all
harness-design-studio extensions my-design --docs > extension-rules.md
harness-design-studio extensions my-design --enable minimum-wire-gauge-power.json
harness-design-studio extensions my-design --json
```

### harness-design-studio trust

Python code is never loaded unless the project enables it and you trusted that exact code. Without NAME this lists the plug-ins of the project and whether each is trusted. With NAME it shows what the code is (name, version, file, SHA-256, number of lines) and asks you to type the plug-in's name to confirm; --yes confirms without asking (for scripts). The trust is kept in YOUR settings folder, not in the project, so a project you clone cannot trust itself; it is tied to the hash, so a change of the code takes it away. --revoke takes trust back. A plug-in runs with your rights: it can read and write the files you can and use the network of this computer. The tool has no sandbox. Trust it only if you have read it or you trust who wrote it.

`harness-design-studio trust project [NAME] [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `NAME` | the plug-in (as `extensions` lists it) |
| `--revoke` | take back the trust of this plug-in |
| `--yes` | confirm without asking (for scripts) |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio trust my-design
harness-design-studio trust my-design duplicate-signal-wires
harness-design-studio trust my-design duplicate-signal-wires --yes
harness-design-studio trust my-design duplicate-signal-wires --revoke
```

### harness-design-studio import-plugin

Run an importer registered by a plug-in of the project (see `extensions`) on a file. The importer proposes the changes; --dry-run shows them and changes nothing.

`harness-design-studio import-plugin project NAME file [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `NAME` | the importer, as `extensions` lists it |
| `file` | the file to read |
| `--dry-run` | show the preview only |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio import-plugin my-design my-importer data.csv --dry-run
harness-design-studio import-plugin my-design my-importer data.csv --dry-run --json
```

## Maintenance

### harness-design-studio migrate

upgrade an old-format project in place (originals are kept)

`harness-design-studio migrate project [options]`

| Argument | Meaning |
| --- | --- |
| `project` | project folder |
| `--json` | print the result as one JSON document instead of text (same exit code; no time, user name or absolute path in it) |

Examples:

```
harness-design-studio migrate my-design
harness-design-studio migrate my-design --json
```
