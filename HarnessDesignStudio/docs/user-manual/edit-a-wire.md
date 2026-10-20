# Edit a wire

This page shows how to change one wire after the tool has generated it: its gauge, type, colour, length, a label for the wire labels, and a note.

> **New in 1.4.0.** Before 1.4.0 the app had no way to change a single wire (only the colour of a whole signal, see [set wire colours](set-wire-colours.md)). The steps in the app are described from the program's code and its tests; the program was not watched on a screen while this page was written.

## Before you start

- You have a generated project with a harness that is not released. A released harness is locked: start a new revision first ([change a released harness](change-a-released-harness.md)).
- The tool generates the wires, and generates them again whenever you press **Generate**. A value that you type for a wire stays; the rest follows the design.
- The tool sets **no gauge or colour of its own** on your behalf: what you type is what is kept.

## 1. Pick the wires

1. Choose **Drawings** on the rail, then the harness.
2. Click a wire in the **Wires** table or on the drawing. To change several wires at once, select several rows (Ctrl or Shift and click).
3. Open the **Edit wire** tab beside **Why**. It names the wire and the two pins it joins. For several wires it says how many are selected, and a field that differs between them is empty and says *various*.

## 2. Change the fields

| Field | What it is | Kept when you generate again? |
| --- | --- | --- |
| **Gauge (AWG)** | A whole number, for example `22`. | Yes: the wire is locked. |
| **Type** | A wire part of the project's parts library. | Yes: the wire is locked. |
| **Colour** | A colour of the IEC 60757 list (black, brown, red, ...) or your own text. A colour the tool does not know is drawn grey. | Yes: the wire is locked. |
| **Length (m)** | The length in metres, for example `1.5` (a comma works too). | Yes: the wire is locked. |
| **Label** | Text that the wire labels print instead of the signal name. | Always. |
| **Note** | Your remark. It appears in the wire list. | Always. |

Only the fields you touch change; the others stay as they are on every selected wire. Press **Apply** (or Ctrl+Enter). The change is one step in the undo list (Ctrl+Z).

A mistake is said in words under the form (a gauge that is not a whole number, a length that is not a number, a type that is not a wire part of the library) and nothing is changed.

Gauge, type, colour and length lock the wire, so the **Locked** column of the wire table shows it and the line under the fields says *Your values*. A label or a note alone does not lock the wire.

## 3. Give a wire back to generation

Select the wires and press **Reset to generated**. They are unlocked: the next **Generate** sets their gauge, type, colour and length from the design again (with placeholder values the gauge is *pending* again). Their label and note stay.

You cannot clear a gauge, type, colour or length on one wire; use **Reset to generated** instead.

## What shows up in the outputs

- The **wire list** gets two columns, **Label** and **Note**, as soon as any wire in the project has one. A project without labels and notes keeps the wire list it had before.
- The **wire labels** (`labels.csv`) print the label in place of the signal name: `W001-0003 Heater supply to J2.4`.
- The independent check (`harness-design-studio verify DIR --outputs`) compares both with the design.

## What cannot be edited here yet

The pins a wire joins follow the interfaces and the pin assignment of the devices (the **Devices** tab; see [define a device](define-a-device.md)). Adding a wire by hand, joining several wires to one pin and stating the twisting of a group are planned for the next steps of version 1.4.0 (`docs/ait/AIT_FEEDBACK_PLAN.md`) and are not in the program yet.

## Common mistakes

- **Typing a gauge and finding the wire "locked".** That is intended: a value you type is yours. Use **Reset to generated** to hand it back.
- **Expecting a label to change the drawing.** The label is for the wire labels and the lists; the drawing shows the signal name.
- **Editing a wire of a released harness.** The form is off and says why. Start a new revision.

More: [`FILE_FORMAT.md`](../FILE_FORMAT.md) (the fields `Wire.label` and `Wire.note`), [`OUTPUTS.md`](../OUTPUTS.md).

Next: [set wire colours](set-wire-colours.md), [export the outputs](export-the-outputs.md)
