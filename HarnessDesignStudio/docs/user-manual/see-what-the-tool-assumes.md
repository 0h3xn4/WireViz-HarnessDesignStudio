# See what the tool assumes

This page shows how to find out what the tool takes for granted when it makes a number: the values it reads from your project, the choices that are built into it, and where each one comes from. Use it before you rely on a result, and in a review when someone asks *why is this number what it is?*

## Contents

- [Before you start](#before-you-start)
- [1. List the settings and the assumptions](#1-list-the-settings-and-the-assumptions)
- [2. Read a line](#2-read-a-line)
- [3. Change a setting](#3-change-a-setting)
- [4. Use the data in a spreadsheet or a script](#4-use-the-data-in-a-spreadsheet-or-a-script)
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

## 3. Change a setting

```
harness-design-studio settings wheel-link --set model.service_loops_per_wire=0
```

The value is JSON (a number, `true`, a list, a table). It is checked against the range of the setting, and **nothing is changed when it is outside**: you get the same message as from `validate`. A change that moves a result moves it by the rule of the setting, and the explanation of the number says so: `explain wheel-link W001-001` shows *0 × service loop*. Generate again to apply it to the harnesses. Values of the engineering files can also be changed in the editor ([fill in the engineering values](fill-in-engineering-values.md)).

## 4. Use the data in a spreadsheet or a script

`harness-design-studio settings wheel-link --json` prints the same as data: for every setting its ID, label, unit, value, origin, default, what it does, what uses it, its source and range, and for every assumption the IDs of its settings.

## Choose how a number is made

Some numbers can be made in more than one way. `model.json` holds the choice (the bundle basis, the length model, the voltage drop model, the mass model, the pin order, what blocks *Ready to build*), and the default is what the tool always did. Change it with `--set` as above, for example `settings wheel-link --set model.mass_model='"full_bom"'`. Every choice, its equation and its default are on the page [selectable models](../models/selectable-models.md); `explain` names the model in force.

## Common mistakes

- **Reading *the tool's own default* as an approved value.** It is the number the tool has always used, not a number a standard asked for. Whether it is right for your programme is your decision; set the value to make it yours.
- **Expecting a setting to change a harness at once.** A setting changes what the next **Generate** makes; the explanations and the checks follow it at once.
- **A key that is not a setting.** A typo in `model.json` is reported by name: `nonsense is not a setting of the model`.

Next: [fill in the engineering values](fill-in-engineering-values.md), [the models](../models/README.md), [the configuration reference](../CONFIG.md)
