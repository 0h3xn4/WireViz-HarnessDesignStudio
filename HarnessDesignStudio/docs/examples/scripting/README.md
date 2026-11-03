# Scripting examples

This folder has three Python scripts that drive Harness Design Studio from code, to show how a batch, a trade study and a full explanation of a design are written. They use only the names listed in `harness_design_studio.api`, the scripting interface ([how to use it](../../user-manual/script-the-tool.md)), and each one is run by a test (`tests/test_scripting_examples.py`), so they stay working.

## Contents

- [Before you start](#before-you-start)
- [The scripts](#the-scripts)
- [Batch: generate, check and export several projects](#batch-generate-check-and-export-several-projects)
- [Trade study: vary one value](#trade-study-vary-one-value)
- [Explain everything](#explain-everything)
- [Write your own](#write-your-own)

## Before you start

- Python 3.14 or newer, and the tool installed in the same environment (`pip install -e .` from the `HarnessDesignStudio` folder, or the packaged tool's Python). Qt is not needed: the interface and these scripts work on a machine with no screen.
- No network is used. Each script runs in a few seconds.
- The scripts that make a project do so in a temporary folder, which is removed when they end. The example projects hold example values, not engineering data; a result printed here says nothing about whether a design is acceptable.
- `generate`, `export` and `set_config` write into the project folder they are given, as the commands of the same name do. A script you point at your own project therefore changes it: run it on a copy, or on a project kept in Git.

## The scripts

| Script | What it does | Writes |
| --- | --- | --- |
| [`batch_projects.py`](batch_projects.py) | Generates, checks and exports each project and writes one row for each | one CSV file |
| [`trade_study.py`](trade_study.py) | Copies the flatsat example, sets the bundle derating factor to each value in turn, generates again and measures | one CSV file |
| [`explain_everything.py`](explain_everything.py) | Writes how every number of a project was made | `derivations.json` and `derivations.csv` |

Run any of them from this folder:

```
python batch_projects.py batch-summary.csv
python trade_study.py trade-study.csv
python explain_everything.py derivations
```

## Batch: generate, check and export several projects

`batch_projects.py` with no folder names makes two of the bundled examples (`first-steps` and `minimal-satellite`), runs `generate`, `run_checks` and `export` on each, and writes `batch-summary.csv`: for each project the number of devices, interfaces, harnesses and wires, whether generation was accepted, the open errors, warnings and notes of the design rule check, the number of output files and the first 12 characters of the model hash. Name your own folders to use it on your projects:

```
python batch_projects.py summary.csv path/to/project-a path/to/project-b
```

The file has no time and no path in it, so two runs on the same design give the same bytes and the file can be compared or kept in Git.

## Trade study: vary one value

`trade_study.py` answers a question such as "what does a stricter bundle derating do to the wire gauges?". It sets `derating.bundle_derating` of a copy of the flatsat example to 0.5, 0.6, 0.8 and 1.0, generates the harnesses again each time, and writes one row for each value: the wire gauges that result (`AWG16x8` means eight wires of AWG 16), the open errors and warnings, and the worst voltage drop over all wires, in volts.

At 0.5 no wire gauge of the example's ampacity table can carry the current, so `generate` refuses (`generate_ok` is `False`), saves nothing, and the row holds only the number of errors it reported. The value is checked as the editor checks it: a factor above 1 raises `ConfigValueError`. The example values are placeholders; read the table as a demonstration of the method, not as a result.

To vary another value, change `FILE` and `KEY` at the top of the script. `get_config` lists the keys.

## Explain everything

`explain_everything.py` calls `write_derivations`, which writes what `harness-design-studio explain --all --out` writes: for every wire its length, the current limit of its gauge after derating, its voltage drop and its mass; for every harness its mass; for every part the quantity of the bill of materials; for every interface the current limit of its contacts. Then it prints what is not set, so that you know which inputs to supply first. Name a project folder to explain your own:

```
python explain_everything.py derivations path/to/project
```

## Write your own

- Start from the script that is closest, and keep to the names in `harness_design_studio.api.__all__`. The test of this folder fails if a script imports anything else from the tool.
- Read a result with its fields (`result.open_errors`) or as data (`result.to_dict()`); both are stable.
- Catch `HarnessError` for anything the tool refuses on purpose; `ProjectDamagedError`, `ProjectLockedError`, `ConfigValueError` and the others are subclasses of it.

Next: [script the tool](../../user-manual/script-the-tool.md), [the command line reference](../../CLI.md#json-output).
