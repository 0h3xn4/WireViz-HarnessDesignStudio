# Extend the tool

This page shows how to add a rule, a table or a reader to a project without changing the tool: first with a data file, which runs no code, and then, if a data file cannot say what you need, with a Python plug-in. Both are off until the project turns them on, and Python code does not run until you have also said that you trust that exact code.

## Contents

- [Before you start](#before-you-start)
- [1. Look at what the project has](#1-look-at-what-the-project-has)
- [2. Add a rule with a data file](#2-add-a-rule-with-a-data-file)
- [3. Add a table or a lookup table](#3-add-a-table-or-a-lookup-table)
- [4. Turn it on](#4-turn-it-on)
- [5. See the finding and its explanation](#5-see-the-finding-and-its-explanation)
- [6. A Python plug-in](#6-a-python-plug-in)
- [7. Trust a plug-in, or take the trust back](#7-trust-a-plug-in-or-take-the-trust-back)
- [What an extension changes, and what it leaves alone](#what-an-extension-changes-and-what-it-leaves-alone)
- [Security: what the tool does and does not do](#security-what-the-tool-does-and-does-not-do)
- [Common mistakes](#common-mistakes)

## Before you start

- An **extension** lives in the folder `extensions/` of the project, beside `project.json`. The tool never writes into it except `enabled.json`, and a save of the project leaves it as it is.
- A **data file** (`extensions/NAME.json`) describes rules, tables and lookup tables. Its conditions are written in a small expression language that can read documented values and do arithmetic, and nothing else. It cannot run a program.
- A **Python plug-in** (`extensions/plugins/NAME.py`, or an installed package) is code. Use it for what a data file cannot say, for example comparing the wires of a harness with each other.
- `extensions/enabled.json` lists which files and which plug-ins the project uses. **A file that is not listed there does nothing.**
- The extra rules have the prefix `x-` (the rule `min-gauge-power` of a file is `x-min-gauge-power`), so that you can tell them from the 39 rules of the tool at a glance. A finding of such a rule says where it comes from.

The examples below are in [`docs/examples/extensions/`](../examples/extensions/README.md). Copy that folder into a project as `extensions/` to try them.

## 1. Look at what the project has

```
harness-design-studio extensions my-design
```

Without options it lists what the extensions of the project add: the data files (with their name, version, SHA-256 and whether they are enabled), the plug-ins (with whether they are enabled and trusted, and the state), and the items they register (rules, tables, lookup tables, fields, importers). `--all` lists the built-in items too, so that you see the tool's own rules in the same table. `--json` prints the same as data, and in the editor **Help > Extensions...** shows it.

A project with no `extensions/` folder says so, and nothing is added to the tool.

## 2. Add a rule with a data file

Write `extensions/minimum-wire-gauge-power.json`:

```json
{
  "format": "harness-design-studio-extension",
  "format_version": 1,
  "name": "minimum-wire-gauge-power",
  "version": "1.0.0",
  "parameters": {
    "thinnest_awg": { "value": 22, "unit": "AWG", "source": "your standard or your decision" }
  },
  "rules": [
    {
      "id": "min-gauge-power",
      "title": "Minimum wire gauge for power",
      "severity": "warning",
      "applies_to": "wire",
      "when": "wire.category == 'power'",
      "condition": "wire.gauge_awg <= param('thinnest_awg')",
      "unit": "AWG",
      "message": "Wire {object} ({wire.signal}) is AWG {actual}, thinner than the AWG {limit} allowed for power",
      "why": "A thin wire in a power line heats up and drops more voltage than the line was planned for.",
      "how": "Choose a gauge with a number at or below the limit (a thicker wire) for this wire."
    }
  ]
}
```

Read it as: *for every wire where the category is power, the gauge must be at most the parameter*. The rule finds a problem where the **condition is false**.

- `applies_to` is the kind of object the rule runs over: `wire`, `connector`, `interface` or `harness`. `when` (optional) says which objects it is about.
- `condition` is an expression ([the list of fields and functions](../developer/extensions.md#the-expression-language)). When it is a comparison, the tool takes the **actual value** (the left side), the **limit** (the right side) and the **margin** from it, and puts them in the message (`{actual}`, `{limit}`, `{margin}`, `{over}`) and in the explanation. The margin is the room that is left: positive when the rule holds, negative when it does not.
- A number that is a limit belongs in `parameters`, with its unit and where it comes from, not hidden in the condition. The explanation shows it.
- A value that is not known (a wire without a gauge) makes the condition *not known*. The rule then says nothing about that wire, and the Checks tab shows the rule as *not checked* with the names of those wires: silence is not a pass.
- `severity` is `error`, `warning` or `info`. A warning can be waived like any other; an error cannot unless the rule says `"waivable": true`.

## 3. Add a table or a lookup table

A **table** is an extra output file, written by `export` as `system/extensions/NAME.csv`: one row for every object, columns made from fields and expressions.

```json
"tables": [
  {
    "name": "power-wires",
    "title": "The power wires with their cross-section and current",
    "applies_to": "wire",
    "where": "wire.category == 'power'",
    "sort": "wire.id",
    "columns": [
      { "header": "Wire", "value": "wire.id" },
      { "header": "Gauge", "value": "wire.gauge_awg", "unit": "AWG" },
      { "header": "Cross-section", "value": "round(wire.mm2, 3)", "unit": "mm2" },
      { "header": "Table ampacity", "value": "lookup('ampacity-example', wire.gauge_awg)", "unit": "A" }
    ]
  }
]
```

A value that is not known is written as `unknown`. The file carries the same version and model stamp as the other tables, and the manifest lists it.

A **lookup table** holds values of your own, for example an ampacity table, that an expression reads with `lookup('name', key)`:

```json
"lookups": [
  {
    "name": "ampacity-example", "key": "AWG gauge", "unit": "A",
    "source": "where the numbers come from", "mode": "exact",
    "values": { "20": 11.0, "22": 7.0, "24": 5.0 }
  }
]
```

`mode` says what happens when the key is not in the table: `exact` (nothing is found), `next_up` (the first listed key at or above), `next_down` (the last listed key at or below) or `interpolate` (a straight line between the neighbours, never beyond the table).

## 4. Turn it on

A file does nothing until the project lists it. Either write `extensions/enabled.json`:

```json
{
  "format": "harness-design-studio-extensions-enabled",
  "format_version": 1,
  "declarative": ["minimum-wire-gauge-power.json"],
  "plugins": []
}
```

or run

```
harness-design-studio extensions my-design --enable minimum-wire-gauge-power.json
```

`--disable NAME` takes it out again. Then check that the file is in order:

```
harness-design-studio validate my-design
```

A problem in a file is reported with the file, the line, the path inside the file and the key, for example:

```
extensions/minimum-wire-gauge-power.json:12: rules[0].condition: column 1: unknown field 'wire.gauge' (did you mean wire.gauge_awg?)
```

`harness-design-studio schema my-design/schemas` writes the JSON Schema of the two files (`extension.schema.json` and `extensions-enabled.schema.json`), so that an editor such as VS Code completes the keys and checks them as you type. A file with a problem is not applied at all, and the other files are. It never stops `generate`, `drc` or `export`: the check says in its own finding (`x-extension-problem`) that an enabled file was not applied, so that its silence is not read as a pass.

## 5. See the finding and its explanation

```
harness-design-studio drc my-design
harness-design-studio explain my-design W001-001
```

`drc` lists the findings of the extension rules with the others, and its report says `Rules run: 40` instead of 39 and names every extension in force with its hash. In the editor the Checks tab shows the rule as a row of its own; its details say *This rule is not part of the tool* and name the file, its version and its hash. **Explain** on a finding opens the same derivation as for a rule of the tool: the equation, the inputs with their units and sources (a field of the design, a parameter of the file with its source, a setting of the project, a lookup table), the actual value, the limit and the margin.

`harness-design-studio extensions my-design --docs` prints the rules the project enables as a Markdown table in the form of [`RULES.md`](../RULES.md) (why, how to fix, requirement IDs, and the file or plug-in each comes from), and their derivations are in the files `explain --all --out FOLDER` writes.

## 6. A Python plug-in

A plug-in is a Python file with a declaration and a function `register`. The file `plugins/duplicate-signal-wires.py` of the examples adds a rule that no two wires of a harness carry the same signal between the same two connectors:

```python
PLUGIN = {"name": "duplicate-signal-wires", "version": "1.0.0", "api": 1, "kinds": ["rule"]}


def register(api):
    def check(project):
        for harness in project.harnesses.values():
            # yield api.Hit(harness.id, "one sentence about this problem") for each problem
            yield from ()

    api.rule(
        "x-duplicate-signal-wires",
        title="Duplicate signal wires",
        severity="warning",
        why="...",
        how="...",
        compares="the signal and the two connectors of each wire ...",
        check=check,
    )
```

The declaration is read **without running the file**, so that you can see what the code is before you trust it. A rule needs `why`, `how` and `compares` (one sentence that says what it compares): that sentence is its explanation. What a plug-in may add is limited to rules, fields (values an expression can read), tables and importers. [The developer page](../developer/extensions.md#python-plug-ins) lists the calls.

To use it, put the name in `plugins` of `enabled.json`. It is listed as *untrusted* and is not loaded.

An installed package can be a plug-in too: it declares an entry point in the group `harness_design_studio.plugins` that names its module. It is listed, hashed and gated in the same way.

## 7. Trust a plug-in, or take the trust back

```
harness-design-studio trust my-design duplicate-signal-wires
```

The command shows what the code is (name, version, kinds, file, SHA-256, number of lines) and the sentence about the risk, and asks you to **type the plug-in's name**. `--yes` confirms without asking, for a script. Read the file first: the command does not run it, and neither does anything else until you have trusted it. In the editor, opening a project that enables an untrusted plug-in shows a window with the same facts and a button *Show the code*; **Help > Extensions...** has *Trust...* and *Take back trust* for the selected plug-in.

- The trust is kept **in your own settings folder** (`~/.config/harness-design-studio/trusted_plugins.json` on Linux, `%APPDATA%\HarnessDesignStudio\trusted_plugins.json` on Windows), not in the project. A project you clone from someone else cannot say that its code is trusted, and your colleague's trust does not travel to your computer.
- The trust is tied to the **name and the SHA-256 of the code**. If the file changes by one byte (an edit, a Git merge, an update of a package), the trust is gone: the plug-in is listed as *untrusted* again and is not loaded until you trust the new code.
- `harness-design-studio trust my-design NAME --revoke` takes the trust back.
- `harness-design-studio trust my-design` lists the plug-ins of the project and whether each is trusted.
- A plug-in that cannot be loaded (an error in the file, a wrong declaration, a name that is already taken) is listed with the reason and is not loaded. It does not stop the tool; the check says in `x-extension-problem` that something enabled was not applied.

A plug-in can also add a reader for a file. `harness-design-studio import-plugin my-design NAME FILE --dry-run` runs it and shows what it would change.

## What an extension changes, and what it leaves alone

- A project that enables nothing is **unchanged**: the same findings, the same output files, byte for byte, and `Rules run: 39`.
- A project that enables extensions says so wherever it matters: in `drc` and its report, in `system/provenance.json` and the manifest of the outputs (name, version and SHA-256 of every enabled file and every loaded plug-in), and in the Checks tab.
- An extension cannot replace or change a rule, a table or a number of the tool: its names are its own (`x-` for rules) and a name that is already taken is refused. It adds checks and tables; the generation of wires, the sizing and the mass are the tool's.
- A finding of an extension rule is a statement of the rule you wrote. The tool does not say that the rule is right, and an extension is not a part of the tool that was tested with it. Whether the rule belongs to the design is a decision of the person who writes it.

## Security: what the tool does and does not do

- A data file is only read. The expression language has no way to call a program, open a file or reach the network: it has fields, arithmetic and a fixed list of functions, and nothing is handed to Python's own evaluator.
- A Python plug-in is code. **A trusted plug-in runs with the rights of the person who trusted it:** it can read and write the files that person can and use the network of the computer. **The tool has no sandbox and does not claim one.** What the tool does is limit *when* the code runs: only if the project enables it and you trusted that exact code, in a store that a cloned project cannot write.
- The hash is a check that the code is the code you trusted. It says nothing about whether the code is good. Read a plug-in before you trust it, or trust only code from a source you trust, and treat a changed plug-in like a new one.
- Trusting is about the computer, not the project: a plug-in you trust is trusted for every project that enables it on that computer.

## Common mistakes

- **A file in `extensions/` that does nothing.** It is not in `enabled.json`. `harness-design-studio extensions` shows it as *not enabled*.
- **A plug-in that is enabled and not loaded.** It is not trusted yet, or it changed since you trusted it. The command and the window say which.
- **A rule that never fires.** A value it reads may not be known (a wire without a gauge): the Checks tab shows it as *not checked* and names the wires. Or its `when` is false for every object.
- **A limit hidden in the condition.** Put numbers that mean something in `parameters` with a unit and a source, so that the explanation shows where they come from.
- **Saving the project under another name and losing the extensions.** *Save as* writes the project files; it does not copy `extensions/`. Copy the folder yourself (with `enabled.json`).
- **Expecting an extension to change the generated wires.** It adds checks and tables. To change what generation does, change the settings ([see what the tool assumes](see-what-the-tool-assumes.md)).

Next: [the developer page for extensions](../developer/extensions.md), [read and fix problems](read-and-fix-problems.md), [see what the tool assumes](see-what-the-tool-assumes.md), [the command reference](../CLI.md)
