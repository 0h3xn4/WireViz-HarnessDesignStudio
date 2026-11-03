# Example extensions

Three small extensions for a project, to copy and change. They show what [Extend the tool](../../user-manual/extend-the-tool.md) describes: a rule written as data, a table written as data, and a rule written in Python. The numbers in them (the thinnest gauge for power, the ampacity table) are **made up for the documentation**; they are not from any standard and not a requirement of anyone. Put the values of your own standard in their place.

## Contents

- [The files](#the-files)
- [Try them](#try-them)
- [What you should see](#what-you-should-see)

## The files

| File | What it is |
| --- | --- |
| `minimum-wire-gauge-power.json` | A rule as data: a power wire must not be thinner than AWG 22 (a parameter with its unit and source). A warning that gives the actual gauge, the limit and the margin. |
| `power-wire-table.json` | A table as data (the power wires with their cross-section, current and the ampacity of a table of the project's own), the lookup table that holds those ampacities, and a rule that compares each wire's current with it. |
| `plugins/duplicate-signal-wires.py` | A rule as Python: no two wires of a harness carry the same signal between the same two connectors. A data file cannot say this, because it looks at one object at a time. It is code and runs only after you trust it. |
| `enabled.json` | Which of these the project uses. Nothing in the folder runs unless it is listed here. |

In the lists above, a file is written as a path relative to this folder: `minimum-wire-gauge-power.json`, `power-wire-table.json`, `plugins/duplicate-signal-wires.py` and `enabled.json`.

## Try them

Copy this folder, without this page, into a project as `extensions/`:

```
harness-design-studio new my-design --template flatsat
mkdir my-design/extensions
cp -r minimum-wire-gauge-power.json power-wire-table.json plugins enabled.json my-design/extensions/
harness-design-studio extensions my-design
harness-design-studio drc my-design
harness-design-studio export my-design
```

Then read the plug-in (`plugins/duplicate-signal-wires.py`) and decide whether you trust it:

```
harness-design-studio trust my-design duplicate-signal-wires
harness-design-studio drc my-design
```

## What you should see

- `extensions` lists two data files (enabled, applied), one plug-in (enabled, **not trusted**, not loaded), and the items they add: the rules `x-min-gauge-power` and `x-own-ampacity`, the table `power-wires`, the lookup table, and, once you trust it, `x-duplicate-signal-wires`.
- `drc` reports the thin power wires of the flatsat (AWG 24 and 26 against the example limit of AWG 22) as warnings with the IDs `x-min-gauge-power.W001-001` and so on, a note that the plug-in is enabled and not trusted (`x-extension-problem`) until you trust it, and `Rules run: 41`.
- `explain my-design W001-001` is unchanged; the Explain button of the Checks tab, or `harness_design_studio.api.explain_finding`, opens the derivation of `x-min-gauge-power` for `W001-001`: actual 24 AWG, limit 22 AWG, margin -2.
- `export` writes `system/extensions/power-wires.csv`, and `system/provenance.json` lists the extensions in force with their SHA-256.

A project that does not copy these files is not changed in any way.
