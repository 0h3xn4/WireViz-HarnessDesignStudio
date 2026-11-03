# Script the tool

This page shows how to run the tool from a script: with `--json` on the commands, when you work in a shell, and with the Python interface (`harness_design_studio.api`), when you work in Python. Both give the numbers the editor gives, as data you can count, compare and keep.

## Contents

- [Before you start](#before-you-start)
- [1. Take a command's result as JSON](#1-take-a-commands-result-as-json)
- [2. Write the outputs to another folder](#2-write-the-outputs-to-another-folder)
- [3. The Python interface](#3-the-python-interface)
- [4. Check a design](#4-check-a-design)
- [5. Ask how a number was made](#5-ask-how-a-number-was-made)
- [6. Read and set engineering values](#6-read-and-set-engineering-values)
- [7. Generate and export](#7-generate-and-export)
- [8. Handle errors](#8-handle-errors)
- [9. Worked examples](#9-worked-examples)
- [What stays the same](#what-stays-the-same)
- [Common mistakes](#common-mistakes)

## Before you start

- You have a practice project: `harness-design-studio new wheel-link --template first-steps`.
- For Python, the tool is installed in the Python you run (`pip install -e .` from the `HarnessDesignStudio` folder). The interface needs no screen and no Qt, and it uses no network.
- `generate`, `export` and `set_config` write into the project folder, as the commands of the same name do. Every function that writes takes the same lock as the editor and the command line, so a script and the editor never write at once.
- Nothing here changes a number. A function calls the function of the tool that the command calls, so `run_checks` finds what `drc` finds and `generate` makes what `harness-design-studio generate` makes.

## 1. Take a command's result as JSON

Add `--json` to a command. The lines of text are then not printed; one JSON document is. The exit code is the one the command has without the option (0 ok, 1 errors or a blocked step, 2 a project or an option that cannot be used).

```
harness-design-studio generate wheel-link --json
```

```
{
  "ok": true,
  "saved": true,
  "added": [],
  "changed": [],
  "unchanged": [
    "W001",
    "W002"
  ],
  "removed": [],
  "frozen": [],
  "kept_locks": [],
  "findings": [],
  "interfaces_checked": 2,
  "wires_checked": 6,
  "verify_issues": []
}
```

(The harnesses were generated before; a first run lists them under `added`.) The first key of every document is `ok`: true when the exit code is 0. Which commands take `--json`, and the keys of each document, are in the [command line reference](../CLI.md#json-output): every command that has a result in data form, from `new`, `validate`, `check`, `drc`, `verify`, `generate` and `export` to `config`, `library`, the imports and exports of data, `review`, `release`, `revise`, `diff`, `compare`, `log`, `migrate` and `merge-fix`.

The documents are made to be kept and compared:

- They hold no time, no user name and no absolute path.
- Lists are in a fixed order (by ID, as the text shows them). The same design gives the same bytes.
- A command that cannot run (a project that cannot be read, a wrong option) writes its message to the standard error as before and prints nothing to the standard output. A command that ran and was refused still prints its document, with `ok` false and the reasons in it: `generate` with errors (`saved` is false), `export` that failed its check, `release` that is blocked (`blockers`).

A few lines of Python read a document, here the open errors and warnings of the design rule check, and stop a build script when there is an error:

```
harness-design-studio drc wheel-link --json > drc.json
python -c "import json; d = json.load(open('drc.json')); print(d['open_errors'], d['open_warnings'])"
```

```
0 10
```

The exit code of `drc` is 1 when an error is open, so `harness-design-studio drc wheel-link --json > drc.json || exit 1` stops the script, and `drc.json` still holds the findings.

Each finding in `findings` has `id`, `rule`, `severity` (`error`, `warning` or `info`), `object_id`, `title`, `why`, `sources` (the requirement IDs of the rule), `can_waive`, `waived`, `waiver_justification` and `waiver_changed`. Each entry of `issues` (`validate`, `check`, `verify`, `generate`, `export`) has `severity`, `code`, `message`, `location` (a file of the project, relative to its folder) and `object_id`.

`explain OBJECT --json` prints a list of derivations, and `settings --json` its own document (without `ok`), both as before ([section 5](#5-ask-how-a-number-was-made)); `explain --all --out FOLDER --json` prints how many it wrote. `export-data DIR --out FOLDER --json` lists the files of the open data ([export the data](export-the-data.md)), and `export` and `generate` take `--run-record` for a record of the run outside every hash.

## 2. Write the outputs to another folder

`export` writes to `<project>/outputs`. Give it `--out` to write the same files to a folder of your choice, for example a build folder, without touching the project:

```
harness-design-studio export wheel-link --out build/wheel-link-outputs
```

```
34 files written to build/wheel-link-outputs (model <hash>).
```

The files are byte for byte the ones the plain `export` writes. The folder is made if it does not exist. With `--json` the document lists every file with its path below the folder, its size and its SHA-256, in path order, so two builds can be compared without opening a file. Other commands that write files have a place to put them already: `explain --all --out FOLDER`, `export-pinout -o FILE`, `export-devices FILE`, `export-subsystem FILE`, `templates FOLDER`, `schema FOLDER` and `new FOLDER`.

## 3. The Python interface

Import what you use from `harness_design_studio.api`. Everything in `api.__all__` is part of the interface and is kept stable ([what that means](#what-stays-the-same)); nothing else is.

```
from harness_design_studio.api import create_project, generate, run_checks

create_project("wheel-link", "first-steps")
print(generate("wheel-link").ok)
result = run_checks("wheel-link")
print(result.open_errors, result.open_warnings)
```

```
True
0 10
```

The functions, by what you do:

| To ... | Call | It does what the command does |
| --- | --- | --- |
| open a project | `load_project(folder)` returns a `Project` | opens the folder; nothing is written |
| save a `Project` you changed | `save_project(project, folder)` | the editor's save |
| list the examples | `list_templates()` | `new --list` |
| start a project | `create_project(folder, template, name)` | `new` |
| check the files | `validate(folder, merge_check=False)` | `validate`, and `check` with `merge_check=True` |
| run the design rules | `run_checks(project_or_folder)` | `drc` |
| list the rules | `list_rules()` | the rules of [`RULES.md`](../RULES.md) |
| check the harnesses and the outputs | `verify(folder, outputs=False)` | `verify` |
| make the harnesses | `generate(folder)` | `generate` |
| write the outputs | `export(folder, out=None, drawings=False)` | `export` |
| ask how a number was made | `explain(project_or_folder, object_id)`, `explain_all(...)`, `explain_finding(..., finding_id)` | `explain` |
| write all the derivations | `write_derivations(project_or_folder, out)` | `explain --all --out` |
| write every result as JSON and CSV | `export_data(project_or_folder, out, run_record=False, operator=None)` returns a `DataFiles` | `export-data` |
| read the engineering values | `get_config(project_or_folder)` | `config` |
| read every setting and where its value comes from | `get_settings(project_or_folder)` | `settings` |
| set an engineering value | `set_config(folder, file, key, value)` | what the editor's *Engineering values* dialog does |

A function that reads takes a folder or a `Project` you loaded; one that writes takes a folder. Results are small frozen dataclasses (`ValidationResult`, `CheckResult`, `GenerateResult`, `ExportResult` ...). Read a field (`result.open_errors`), or call `result.to_dict()` to get the dictionary that `--json` prints: a script and a shell pipeline see the same data. Nothing is printed and the program is never ended by a function; failures are exceptions ([section 8](#8-handle-errors)).

## 4. Check a design

`run_checks` runs every design rule and the checks of the diagram, and returns the findings, errors first, then by ID:

```
from harness_design_studio.api import run_checks

result = run_checks("wheel-link")
print(result.rules_run, result.ok)
for finding in result.findings:
    if finding.severity != "info":
        print(finding.id, "-", finding.title)
```

```
39 True
part-unapproved.EX-MICROD-15-F - Part EX-MICROD-15-F is not approved yet but is used (2 place(s))
...
```

`ok` is false when an error is open, the same condition that gives `drc` exit code 1. A waived finding is in the list, with `waived` true and its reason in `waiver_justification`. `result.placeholder_config` names the configuration files that are still placeholders: a result that depends on them is not a statement about the design (read [Fill in the engineering values](fill-in-engineering-values.md)). `validate` reports problems of the files, and `verify` the independent check of the harnesses against the interfaces.

## 5. Ask how a number was made

`explain` returns the derivation of the numbers of a wire, a harness, a part or an interface at a connector: the equation, the inputs with their units and where each comes from, the steps, the check against its limit, and what is missing.

```
from harness_design_studio.api import explain, explain_finding, load_project, run_checks

project = load_project("wheel-link")
for derivation in explain(project, "W001-001"):
    print(derivation.id, derivation.value, derivation.unit)
```

```
wire-length 0.35 m
wire-current-limit None A
wire-voltage-drop None V
wire-mass None g
```

A value of `None` means an input is not set yet; `derivation.missing` says which. `derivation.to_dict()` is the plain form with every input, step and assumption. `explain_all(project)` gives every derivation of the design, and `explain_finding(project, finding_id)` the calculation the editor's *Explain* shows for a finding (the wire for a current or voltage-drop finding, the contacts for a contact-current finding; an empty list for a finding of another rule). `write_derivations(project, "out")` writes `derivations.json` and `derivations.csv`, the files `harness-design-studio explain --all --out out` writes. The models behind them are in [`docs/models/`](../models/README.md).

## 6. Read and set engineering values

`get_config` lists every engineering value with its unit, what it is used for, whether it is set and where the value came from. `set_config` sets one, and checks it as the editor does:

```
from harness_design_studio.api import ConfigValueError, get_config, set_config

report = get_config("wheel-link")
print(report.set_count, "of", report.total, "set")
bundle = report.value("derating", "bundle_derating")
print(bundle.label, bundle.missing, bundle.used_by)

print(set_config("wheel-link", "derating", "bundle_derating", 0.8).value)
try:
    set_config("wheel-link", "derating", "bundle_derating", 1.5)
except ConfigValueError as error:
    print(error)
```

```
0 of 17 set
Bundle derating factor True wire sizing, wire current check
0.8
Bundle derating factor must be a number above 0 and at most 1.
```

`value` may be a number, text as a person types it (`"0,8"`, `"0.5 V"`, `"power + analog"`, `"20: 5, 22: 3.5"`), or `None` to clear it. A refused value changes no file. `placeholder=False` marks the file as reviewed; give it only when a person has reviewed the file. A value that a released harness uses cannot be changed (`TransactionError`, as in the editor).

## 7. Generate and export

`generate` plans the harnesses from the interfaces, checks them independently, and saves the project, unless there is an error. A refusal is a result, not an exception:

```
from harness_design_studio.api import export, generate

made = generate("wheel-link")
if not made.ok:
    for finding in made.findings:
        print(finding.severity, finding.message)
else:
    print(len(made.unchanged), "harnesses unchanged;", made.wires_checked, "wires checked")
    out = export("wheel-link", "build/outputs")
    print(out.written, len(out.files), "files")
```

```
2 harnesses unchanged; 6 wires checked
True 34 files
```

`export(folder, out=None, drawings=False)` returns the files with their size and SHA-256. It writes the PDF and SVG drawings only with `drawings=True`. When there is nothing to export (`blocked` is `nothing_to_export`) or the outputs fail their independent check (`outputs_failed_check`), nothing is written and `issues` says why.

## 8. Handle errors

Everything the tool refuses on purpose is an exception from one tree. Catch `HarnessError` to catch them all:

| Exception | When |
| --- | --- |
| `LoadError` | the folder is not a project, or cannot be read |
| `ProjectDamagedError` (a `LoadError`) | a project with damaged files; `.issues` lists them. `validate` reports the same without refusing |
| `ProjectLockedError` | the project is open in the editor or in another script |
| `SaveError` | a file could not be written; the earlier files are left as they were |
| `TransactionError` | a change was refused, for example because a release froze the value |
| `EditError` | an edit that cannot be done; `explain` raises it for an ID that has nothing to explain |
| `ConfigValueError` (an `EditError`) | a configuration value that is not acceptable |
| `TemplateError` | an unknown example, or a folder that is not empty |
| `ReadOnlyProjectError` | the project was saved by a newer version of the tool |
| `NoOutputsError` | `verify(..., outputs=True)` found no outputs folder |

## 9. Worked examples

[`docs/examples/scripting/`](../examples/scripting/README.md) holds three scripts, each run by a test so that it keeps working:

- `batch_projects.py` generates, checks and exports several projects and writes one summary table.
- `trade_study.py` copies the flatsat example, varies the bundle derating over a range, generates again for each value and tabulates the wire gauges, the findings and the worst voltage drop.
- `explain_everything.py` writes how every number of a project was made.

## What stays the same

The names in `api.__all__`, the signatures of the functions and the fields of the results do not change without notice. A test compares them with a stored snapshot, so a change can only be made on purpose; adding a field or an optional argument is allowed, removing or renaming one raises `API_VERSION` and is written in the [CHANGELOG](../../CHANGELOG.md). The keys of a `--json` document follow the same rule. The rules for people who change the interface are in [`api-stability.md`](../developer/api-stability.md). The interface is not a promise about the design: the example values are placeholders, and a script that passes its checks has shown nothing more than that the checks passed.

## Common mistakes

- **Running a script on your only copy of a project.** `generate`, `export` and `set_config` write into the folder. Work on a copy or keep the project in Git ([use Git and CI](use-git-and-ci.md)).
- **Reading `ok` as "the design is fine".** `ok` says the command ended with exit code 0. A design on placeholder values passes checks it did not make; look at `placeholder_config`.
- **Parsing the text of a command.** The text may be reworded between versions; the JSON keys are kept. Use `--json` or the Python interface.
- **Expecting a document when a command fails early.** A project that cannot be read gives a message on the standard error and exit code 2, and nothing on the standard output.
- **`ProjectLockedError`.** The editor or another script has the project open. Close it or wait.
- **Comparing results across versions of the tool.** A document carries the numbers of the version that made it; the model hash changes with the version.

More: [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).

Next: [use Git and CI](use-git-and-ci.md), [export the outputs](export-the-outputs.md), [fill in the engineering values](fill-in-engineering-values.md)
