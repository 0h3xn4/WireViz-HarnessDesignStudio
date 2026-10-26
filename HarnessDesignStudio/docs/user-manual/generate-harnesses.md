# Generate harnesses

This page shows how to turn your devices and links into harnesses (connectors, pins and wires), check the result, and read why the tool made each choice.

## Contents

- [Before you start](#before-you-start)
- [1. Generate](#1-generate)
- [2. Check the result on its own](#2-check-the-result-on-its-own)
- [3. Read why a wire is the way it is](#3-read-why-a-wire-is-the-way-it-is)
- [How links become harnesses](#how-links-become-harnesses)
- [Keep a choice of your own](#keep-a-choice-of-your-own)
- [Common mistakes](#common-mistakes)

## Before you start

- You have a project with devices and links. For a quick start make one: `harness-design-studio new wheel-link --template first-steps` (see [draw the design](draw-the-design.md)).
- A **harness** is a bundle of wires with connectors that carries the links between two devices. You do not draw it: the tool generates it from your design, and it can generate it again at any time. (A harness with no interface behind it you can make by hand: [build a harness by hand](build-a-harness-by-hand.md).)
- Wire gauges (thicknesses) stay *pending* until the engineering values exist. That is normal. See [fill in the engineering values](fill-in-engineering-values.md).

## 1. Generate

**In the app** (GUI, not run)

1. Press **Generate** in the top bar (**Design > Generate harnesses**, Ctrl+G). On the Next step page of the Simple workspace the button is **Generate the harnesses**; it does the same.
2. A window shows a **preview** of what would be added, changed and removed. Nothing changes until you press **Apply**. (**Cancel** leaves the project as it was.)
3. The **Harness** tab (the **Drawings** area of the rail) opens on the result. To take it back, press **Undo** (Ctrl+Z). One Undo reverses the whole generation.

Generate always covers every harness; the app has no way to generate only one. The **Generate** step in the top bar says what it knows: *not generated yet*, *the harness plans match the design* or *the design changed after the last generation* (hover it). In the last case the status chip says *Plans out of date* and a banner offers **Generate**.

If there is nothing to generate the app says so ("There is nothing to generate yet. Add devices and connect them with interfaces first." or "Harnesses are already up to date. Nothing to change."). If generation finds problems (for example an interface that has no free pins), the preview opens with the errors listed ("Some harnesses could not be generated (N problem(s)). Fix the connectors or interfaces named in the list, then generate again."). It never says "up to date" while errors are waiting. If you edit the project while the plan is being made, the plan is refused ("The project changed while the plan was being made, so nothing was applied. Press Generate again.").

**On the command line**

```
harness-design-studio generate wheel-link
```

```
2 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
```

Two harnesses were made, one for each pair of connectors the two links use: `W001` carries the RS-422 link (four wires) and `W002` carries power (two wires). The project is saved. If the project has errors, nothing is saved.

Run the same command again:

```
harness-design-studio generate wheel-link
```

```
0 added, 0 changed, 2 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
```

Generating again keeps the IDs, never touches a released harness, and gives the same bytes for the same design, so Git diffs show real changes only. (A project from an older version that has ten or more shields or segments in one harness shows those harnesses as *changed* once, because the generator now uses the order the files are saved in; after that it is stable.)

**Bad input is reported, not used.** Generation checks `config/*.json` first. A value that is set but impossible (a derating factor above 1, an ampacity table in which a thinner wire carries more, a gauge outside AWG 0 to 40, a negative or fractional pin gap, a number written as text, a wrong `default_gauge_awg` or `wire_colour_by_signal`) is an error in the result and is treated as unset, so the gauge stays *pending*:

```
error: [config_invalid] config/generation.json: default_gauge_awg must be a whole number from 0 to 40.
Not saved: fix the errors above first.
```

Nothing is saved while the result holds errors (exit code 1). A naming pattern that fails, gives a reserved name such as `COM1` or repeats a name is replaced by the default with a warning (`warning: [naming] ...`, see [naming and title block](naming-and-title-block.md)). An interface whose two ends are on one connector, that has fewer than two ends, or whose type repeats a signal name is skipped with a finding (`interface_skipped`) instead of being wired onto one pin. A locked wire or an entered segment length that cannot be carried over to the new plan is named in a warning (`locked_data_lost: W002: W002-001 cannot be carried over and will be lost.`); read it before you apply. A manual harness (one you made by hand, `generated: false`) that takes over an interface makes the generation status *stale*, and deleting a device that a manual harness plugs into is refused.

## 2. Check the result on its own

The tool checks its own result with a second program path that shares no code with the generator. In the app the header of the **Harness** tab shows a chip, *Check passed* or *Check found n problem(s)*; hover the chip to read "Independent check: …" and how long it took. (The **Check** step in the top bar is another check: it runs the design rules, see [read and fix problems](read-and-fix-problems.md).) On the command line:

```
harness-design-studio verify wheel-link
```

```
2 interfaces and 6 wires checked: 0 error(s)
```

Exit code 0 means no errors. 1 means the project has errors. 2 means a usage error or a folder that cannot be read.

## 3. Read why a wire is the way it is

In the app, open the **Harness** tab (Ctrl+2; **Drawings** on the rail) and pick a harness, for example `W002`, in the list at the top left.:

- **Connectors and pins** lists every pin with its signal and wire; a pin whose gauge or length is not known yet has a **Pending** chip, and one that the tool chose and nobody has reviewed an **Auto-filled** chip. Spare pins are hidden and counted under the table; **Show spare pins** shows them.
- **Wires** shows each wire with its signal, ends, **Gauge**, **Length**, **Colour** and **Locked** (the **Colour** column in the app is not in the 0.1.0 packages).
- **Why** names the rule behind the wire, connector or pin you select, including gauge and length. This is the tool's answer to "why is it like this?". **Show in Why panel** shows the same in the **Why** tab of the right panel.
- **Drawing** previews the drawing sheet. [Export](export-the-outputs.md) writes it as a PDF only when you ask for the drawings (the check box **Include the PDF drawings**, or `--drawings`). It takes the width and most of the height of the area, with the pin table, the wire table and the reasons under it. The wheel zooms, a drag pans, **Previous sheet** and **Next sheet** page through it, hovering a wire in the drawing or the table marks it in the other, and picking a wire in the drawing selects its link for the Inspector.

Beside **Why** are the tabs **Edit wire**, **Connectors** and **Accessories**, which change the harness: [edit a wire](edit-a-wire.md), [build a harness by hand](build-a-harness-by-hand.md), [enter the build data](enter-the-build-data.md).

There is no command line version of the **Why** pane. The same reasons are stored in `generated/generation.json` in the project, under `provenance`.

## How links become harnesses

By default one harness is made for each pair of device connectors. The setting is in `config/segmentation.json`:

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
| `per_connector_pair` (default) | pair of device connectors |
| `per_unit_pair` | pair of devices |
| `per_zone_pair` | pair of zones (links between the same two lanes) |

With the `minimal-satellite` example (11 links), the default makes 11 harnesses. After changing `mode` to `per_unit_pair` and running `harness-design-studio generate` again, the report is `1 added, 9 changed, 0 unchanged, 2 removed`: ten harnesses replace the eleven. Harnesses that keep a pair of devices keep their IDs (here `W001`, `W002` and `W005` to `W011`, nine of them changed), the new one gets the next free ID (`W012`), and the files of the old ones stay in `physical/harnesses/` with the ending `.json.bak`. A second run changes nothing. (`minimal-satellite` is not in the 0.1.0 packages; see the [changelog](../../CHANGELOG.md).)

Whatever the mode:

- Nominal and redundant chains never share a harness, and pyro lines (firing circuits) never share a harness with other lines.
- This rule is a placeholder until the owner decides it (decision D-10 in [`DECISIONS.md`](../DECISIONS.md)). The file keeps `"placeholder": true`.
- A link between **more than two devices** (a bus) is not generated yet (D-116). It is skipped with the note "multi-drop interfaces (more than two devices) are not generated yet".

The file has a wrapper: the setting is under `values`. A key at the top level is refused. See [fill in the engineering values](fill-in-engineering-values.md#the-shape-of-a-config-file).

## Keep a choice of your own

Generation may change a wire or a pin you edited. To keep a value, lock it.

- **A wire, in the app (since 1.4.0):** select it in the **Drawings** area and set its gauge, type, colour or length in the **Edit wire** tab. That locks the wire: Generate keeps those values, and **Reset to generated** hands it back. A label, a note and the strip lengths are always kept (they do not lock the wire), a wire you draw yourself is kept as it is, and so are the groups you make ([edit a wire](edit-a-wire.md)). If Generate cannot keep something (its interface is gone) it says so with the finding `locked_data_lost`. The same holds for the accessories of a harness (kept while the connector or wire they sit on is kept) and the contact of a pin, which Generate copies from the pin of the device to the cable connector ([enter the build data](enter-the-build-data.md)).
- **Many wires, in the app (workshop milestone M3):** **Edit all wires…** sets the gauge, type, colour and length of all wires of the harness, the selected ones or those of one signal in one step; they are locked exactly as an edited wire ([edit a wire](edit-a-wire.md#10-edit-all-wires)).
- **A connector of a generated harness (M3):** in the **Connectors** tab, change its part, gender or keying, or the signal, role, function, termination or contact size of a pin. The connector then belongs to you (`"locked": true` in its entry of `physical/harnesses/<ID>.json`): Generate keeps those values, while the name, the pins and the contact of each pin keep following the device. **Give back to Generate** hands it back; if the device connector is gone, `locked_data_lost` names it ([build a harness by hand](build-a-harness-by-hand.md#change-a-connector-and-its-pins)).
- **A group you made (M3):** **Change group…** changes its kind, wires and shield ends; Generate keeps the group ([edit a wire](edit-a-wire.md#9-change-a-group)).
- **A pin, in the app:** the *Mode* column of the **Devices** tab: *locked* keeps the pin where it is, *fixed* also fixes its signal. The report counts them: "0 locked pin(s) kept".
- **In the file:** a wire's entry in `physical/harnesses/<ID>.json` with `"locked": true` does the same as the Edit wire tab; a pin's entry with `"locked": true` the same as the Devices tab. A locked pin that already carries a signal stays where it is on a connector with a fixed pinout, and a locked fixed pin keeps its interface. In `per_unit_pair` mode a renamed device keeps its harness IDs, locked wires and lengths when the interfaces stay the same.

This was checked on the command line with `first-steps`: a wire set to gauge 20 and colour `red` with `"locked": true` kept both after `harness-design-studio generate`, and a wire set to gauge 20 without the lock went back to the tool's own value (here no gauge, because the derating values are still placeholders). Edit the file only while the project is not open in the app. If it is open, the app reports "Project changed on disk" and offers to reload.

## Common mistakes

- **"there are no harnesses to export; run `harness-design-studio generate` first."** You have not generated yet, or the project has no links. Generate first.
- **A blank project generates nothing.** The command line cannot add devices. Add devices and links in the app ([draw the design](draw-the-design.md)), or start from an example. A harness made by hand with **New harness…** is left alone by Generate.
- **Gauge says *pending*.** Not a fault. A value is missing: run `harness-design-studio config DIR` ([fill in the engineering values](fill-in-engineering-values.md)). The power link also needs its **Max current (A)**.
- **"The model changed after the harness plans were generated."** You changed the design after generating. Generate again.

More: [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).

Next: [read and fix problems](read-and-fix-problems.md), [fill in the engineering values](fill-in-engineering-values.md), [export the outputs](export-the-outputs.md)
