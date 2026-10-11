# Generate harnesses

This page shows how to turn your units and links into harnesses (connectors, pins and wires), check the result, and read why the tool made each choice.

## Contents

- [Before you start](#before-you-start)
- [1. Generate](#1-generate)
- [2. Check the result on its own](#2-check-the-result-on-its-own)
- [3. Read why a wire is the way it is](#3-read-why-a-wire-is-the-way-it-is)
- [How links become harnesses](#how-links-become-harnesses)
- [Keep a choice of your own](#keep-a-choice-of-your-own)
- [Common mistakes](#common-mistakes)

## Before you start

- You have a project with units and links. For a quick start make one: `harness new wheel-link --template first-steps` (see [draw the design](draw-the-design.md)).
- A **harness** is a bundle of wires with connectors that carries the links between two units. You never draw it. The tool generates it from your design, and it can generate it again at any time.
- Wire gauges (thicknesses) stay *pending* until the engineering values exist. That is normal. See [fill in the engineering values](fill-in-engineering-values.md).

## 1. Generate

**In the app** (GUI, not run)

1. Press **Generate harnesses** in the toolbar.
2. A window shows a **preview** of what would be added, changed and removed. Nothing changes until you press **Apply**. (**Cancel** leaves the project as it was.)
3. To take it back, press **Undo** (Ctrl+Z). One Undo reverses the whole generation.

If there is nothing to generate the app says so ("There is nothing to generate yet. Add units and connect them with interfaces first." or "Harnesses are already up to date. Nothing to change.").

**On the command line**

```
harness generate wheel-link
```

```
2 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
```

Two harnesses were made, one for each pair of connectors the two links use: `W001` carries the RS-422 link (four wires) and `W002` carries power (two wires). The project is saved. If the project has errors, nothing is saved.

Run the same command again:

```
harness generate wheel-link
```

```
0 added, 0 changed, 2 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
```

Generating again keeps the IDs, never touches a released harness, and gives the same bytes for the same design, so Git diffs show real changes only.

## 2. Check the result on its own

The tool checks its own result with a second program path that shares no code with the generator. In the app the **Harness plans** tab shows "Independent check: …". On the command line:

```
harness verify wheel-link
```

```
2 interfaces and 6 wires checked: 0 error(s)
```

Exit code 0 means no errors. 1 means the project has errors. 2 means a usage error or a folder that cannot be read.

## 3. Read why a wire is the way it is

In the app, open the **Harness plans** tab (bottom) and select a harness, for example `W002`:

- The wire list shows each wire with its signal, ends, **AWG** (gauge), **Length (m)** and **Colour**.
- The **Why** tab (right of the list) names the rule behind every wire, pin, gauge and length. This is the tool's answer to "why is it like this?".
- The **Drawing** tab previews the sheet that [export](export-the-outputs.md) writes. **Previous sheet** and **Next sheet** page through it.

There is no command line version of the **Why** tab. The same reasons are stored in `generated/generation.json` in the project, under `provenance`.

## How links become harnesses

By default one harness is made for each pair of unit connectors. The setting is in `config/segmentation.json`:

```
{
  "name": "segmentation",
  "placeholder": true,
  "values": {
    "mode": "per_connector_pair"
  }
}
```

| `mode` | One harness for each ... |
| --- | --- |
| `per_connector_pair` (default) | pair of unit connectors |
| `per_unit_pair` | pair of units |
| `per_zone_pair` | pair of zones (links between the same two lanes) |

With the `minimal-satellite` example (11 links), the default makes 11 harnesses. After changing `mode` to `per_unit_pair` and running `harness generate` again, the report is `10 added, 0 changed, 0 unchanged, 11 removed`: ten harnesses replace the eleven. The new ones get new IDs (`W012` to `W021`), and the files of the old ones stay in `physical/harnesses/` with the ending `.json.bak`. (`minimal-satellite` is newer than the 0.1.0 packages; see the [changelog](../../CHANGELOG.md#unreleased-after-010).)

Whatever the mode:

- Nominal and redundant chains never share a harness, and pyro lines (firing circuits) never share a harness with other lines.
- This rule is a placeholder until the owner decides it (decision D-10 in [`DECISIONS.md`](../DECISIONS.md)). The file keeps `"placeholder": true`.
- A link between **more than two units** (a bus) is not generated yet (D-116). It is skipped with the note "multi-drop interfaces (more than two units) are not generated yet".

The file has a wrapper: the setting is under `values`. A key at the top level is refused. See [fill in the engineering values](fill-in-engineering-values.md#the-shape-of-a-config-file).

## Keep a choice of your own

Generation may change a wire or a pin you edited. To keep a value, mark it as locked.

- In a wire's entry in `physical/harnesses/<ID>.json`, set `"locked": true`. Generation then keeps the gauge, colour, part and length you put there. Without the lock it writes its own value again.
- In a pin's entry, `"locked": true` keeps the pin where it is. The report counts them: "0 locked pin(s) kept".
- The app does not have a button to lock a wire or a pin. Its wire list only shows a **Locked** column.

This was checked on the command line with `first-steps`: a wire set to gauge 20 and colour `red` with `"locked": true` kept both after `harness generate`, and a wire set to gauge 20 without the lock went back to the tool's own value (here no gauge, because the derating values are still placeholders). Edit the file while the project is not open in the app. If it is open, the app reports "Project changed on disk" and offers to reload.

## Common mistakes

- **"there are no harnesses to export; run `harness generate` first."** You have not generated yet, or the project has no links. Generate first.
- **A blank project generates nothing.** The command line cannot add units. Add units and links in the app ([draw the design](draw-the-design.md)), or start from an example.
- **Gauge says *pending*.** Not a fault. A value is missing: run `harness config DIR` ([fill in the engineering values](fill-in-engineering-values.md)). The power link also needs its **Max current (A)**.
- **"The model changed after the harness plans were generated."** You changed the design after generating. Generate again.

More: [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).

Next: [read and fix problems](read-and-fix-problems.md), [fill in the engineering values](fill-in-engineering-values.md), [export the outputs](export-the-outputs.md)
