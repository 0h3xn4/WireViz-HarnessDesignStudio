# See what the tool assumes

This page shows how to find out what the tool takes for granted when it makes a number: the values it reads from your project, the choices that are built into it, and where each one comes from. Use it before you rely on a result, and in a review when someone asks *why is this number what it is?*

## Contents

- [Before you start](#before-you-start)
- [1. List the settings and the assumptions](#1-list-the-settings-and-the-assumptions)
- [2. Read a line](#2-read-a-line)
- [3. Change a setting](#3-change-a-setting)
- [4. Use the data in a spreadsheet or a script](#4-use-the-data-in-a-spreadsheet-or-a-script)
- [5. Put the same text into the files you edit by hand (optional)](#5-put-the-same-text-into-the-files-you-edit-by-hand-optional)
- [Common mistakes](#common-mistakes)

## Before you start

- A **setting** is a value a result depends on that you can choose. Most are in `config/*.json` ([the reference](../CONFIG.md)); the choices that used to be built into the program are in `config/model.json`.
- An **assumption** is something the tool takes for granted when it calculates, for example that a power wire is counted twice in the voltage drop. Each has an ID such as `A-ROUND-TRIP`; the explanation of a number names the ones it rests on ([wire sizing](../models/wire-sizing.md)).
- A **definition** is a fixed part of a calculation that is not an engineering choice, for example the formula of the AWG cross-section.

## 1. List the settings and the assumptions

```
harness-design-studio settings wheel-link
```

The output has three parts: every setting with its value, then the assumptions built into the tool, then the fixed definitions. In the editor, **Help > Assumptions…** opens the same text in a window.

## 2. Read a line

```
  bundle_derating = 0.6   [set by the project (placeholder: not reviewed)]
      Bundle derating factor. One factor K for the wires of a bundle. Used by: wire sizing, wire current check. Source: ...
```

- **The value** and its unit. A value that is not set says *not set* and what stays undecided or excluded until it is.
- **Where it comes from.** *Set by the project* (it is in a file of the project; *placeholder: not reviewed* while the file still says so), *the tool's own default* (the behaviour of the tool before the setting existed: no number changes when you leave it), or *not set*.
- **Used by** and **Source**: what depends on it and who decides it, or the clause it comes from when a standard profile supplied it.
- In the second part, each assumption lists the settings that parameterise it with their values, so you see at once that `A-SERVICE-LOOP` is two loops of the `service_loop_m` of your project.
- **A wire gauge is shown with its cross-section.** Wherever the screen or an explanation names a gauge, the cross-section follows it: `24 AWG (0.205 mm²)` (three significant digits: `40 AWG (0.00501 mm²)`, `16 AWG (1.31 mm²)`), and in the table of ampacities `AWG 24 (0.205 mm²): 2.0`. The cross-section is that of a solid round conductor of the AWG diameter (the definition `D-AWG`), the one the voltage drop uses. It is for reading: the files the tool writes (the drawings, the lists, the workbook, the design rule report) keep the plain gauge, and the values you type and the files you edit are the plain number.

## 3. Change a setting

```
harness-design-studio settings wheel-link --set model.service_loops_per_wire=0
```

The value is JSON (a number, `true`, a list, a table). It is checked against the range of the setting, and **nothing is changed when it is outside**: you get the same message as from `validate`. A change that moves a result moves it by the rule of the setting, and the explanation of the number says so: `explain wheel-link W001-001` shows *0 × service loop*. Generate again to apply it to the harnesses. Values of the engineering files can also be changed in the editor ([fill in the engineering values](fill-in-engineering-values.md)).

## 4. Use the data in a spreadsheet or a script

`harness-design-studio settings wheel-link --json` prints the same as data: for every setting its ID, label, unit, value, origin, default, what it does, what uses it, its source and range, and for every assumption the IDs of its settings. To keep the settings in force with a result, `harness-design-studio export-data wheel-link --out FOLDER` writes them as `settings.json` and `settings.csv` beside every table of the design, and the configuration files as the tool used them ([export the data](export-the-data.md)).

## 5. Put the same text into the files you edit by hand (optional)

JSON has no comments, so `config/derating.json` shows a number and not its unit, range or source. Run

```
harness-design-studio settings wheel-link --annotate
```

and every config file of the project gets a top-level key `_about` with, for each setting, the unit, the range, where the number comes from, what uses it, its default and the assumption it belongs to: the text of step 2, next to the value, in the editor of your choice. `--no-annotate` takes it out again. It is off unless you ask (`new --annotate-config` starts a project with it) and it is only a comment: it is not a setting, it does not change any number or written file, and a project with it has the same model hash as one without. `validate` and `config` warn when the text in the file is out of date; `--annotate` refreshes it. In the editor, the box of each value on the engineering values page shows the range and the source as its tooltip. Details: [`CONFIG.md`](../CONFIG.md#comments-in-the-files-about).

## Choose how a number is made

Some numbers can be made in more than one way. `model.json` holds the choice (the bundle basis, the length model, the voltage drop model, the mass model, the pin order, what blocks *Ready to build*, and the spare contacts and the allowance on the wire in the bill of materials, which are 0 until you set them), and the default is what the tool always did. Change it with `--set` as above, for example `settings wheel-link --set model.mass_model='"full_bom"'`. Every choice, its equation and its default are on the page [selectable models](../models/selectable-models.md); `explain` names the model in force.

## Common mistakes

- **Reading *the tool's own default* as an approved value.** It is the number the tool has always used, not a number a standard asked for. Whether it is right for your programme is your decision; set the value to make it yours.
- **Expecting a setting to change a harness at once.** A setting changes what the next **Generate** makes; the explanations and the checks follow it at once.
- **A key that is not a setting.** A typo in `model.json` is reported by name: `nonsense is not a setting of the model`.

Next: [export the data](export-the-data.md), [fill in the engineering values](fill-in-engineering-values.md), [the models](../models/README.md), [the configuration reference](../CONFIG.md)
