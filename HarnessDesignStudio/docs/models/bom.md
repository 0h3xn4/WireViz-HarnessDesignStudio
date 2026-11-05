# Bill of materials: why a part has the quantity it has

This page explains the quantity the tool puts in the bill of materials (`bom.csv` of a harness and `system/bom.csv`): what is counted, in which unit, and what is not. It is written from what the program does, and the numbers come from the `flatsat` example, where you can repeat them.

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The equations](#the-equations)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

For every part used in a harness the bill of materials has one line for each unit the part is counted in: `ea` (each) or `m` (metres). A part used both ways has two lines. The quantity is the sum of what every harness adds, and the tool writes it with one function; the explanation lists what that function counted. `explain DIR PART` shows each line as a derivation of kind `part-bom`.

## The equations

- Connector parts: one for each connector of a harness.
- Contact parts: one for each pin that names a contact part **and** has a wire attached. With `model.bom_contact_spare_fraction` above 0 (it is 0 by default) the spares are added for each harness and contact part: the fraction of the contacts used, rounded up to a whole contact.
- Accessory parts without a length: their quantity. With a length: `length (mm) × quantity / 1000`, in metres.
- Wire parts, in metres: the sum of the lengths of the wires that name the part, each divided by the conductors of the part (a twisted pair part has 2, so the cable is counted once). With `model.bom_wire_allowance_fraction` above 0 (0 by default) that sum is multiplied by `1 + fraction`.

## The inputs and where they come from

| Input | Unit | Source |
| --- | --- | --- |
| The part, its category, approval and conductors | none | The parts library of the project. |
| Which connectors, wires and accessories a harness has | none | The generated harness, and what you changed or added. |
| The length of each wire | m | [Wire length](wire-length.md) (it includes the service loops). |
| The allowance on the wire and the spare contacts | none | `config/model.json`: `bom_wire_allowance_fraction`, `bom_contact_spare_fraction` (0 unless set; [selectable models](selectable-models.md#allowance-and-spares-in-the-bill-of-materials)). |
| Which pins have a wire | none | The wires of the harness. |

## The assumptions it rests on

- **A-BOM-CONTACTS** (a setting). A contact part is counted once for each pin that has a wire, and not for a pin nobody uses. By default no spare contact is added; `model.bom_contact_spare_fraction` adds that fraction of the contacts used, per harness and part, rounded up.
- **A-BOM-NO-ALLOWANCE** (a setting). What is drawn is counted: by default no spares, overage, cut allowance or waste. `model.bom_wire_allowance_fraction` adds a fraction of the wire metres; a connector part and an accessory part never get an allowance. A wire with no length adds nothing to the metres and is counted in the column *Wires without length*.

## A worked example

`harness-design-studio explain DIR EX-WIRE-SINGLE` on the `flatsat` example prints, for the wire part:

- **BOM quantity (m): 165.2 m.** Harness `W001` has 18 wires of the part, 60.1 m in all; `W002` 4 wires, 13.8 m; `W003` 2 wires, 1.4 m; `W004` 12 wires, 40.4 m; `W005` 3 wires, 10.1 m; `W006` 12 wires, 39.4 m. Each wire is one conductor of the part, so the metres are the sum of the lengths divided by 1, and the sum is 165.2 m.

`explain DIR EX-MICROD-9-M` shows the connector part counted by harness: 18 + 5 + 2 + 11 + 2 + 9 = 47 `ea`.

## What happens when a value is missing

When a wire has no length, the explanation says how many wires of the part add nothing and names the first of them. When a part is not in the parts library, it says so: its category and approval are unknown. A quantity is never made up.

## What the model does not do

- It adds no spares or waste unless you set the two fractions above, and it does not round up to a pack size or a reel (the only rounding is the whole number of spare contacts).
- It does not count the solder, the heat shrink of a splice, the labels' ink or anything that is not a part of the project's library.
- It does not know prices or lead times.

Next: [mass](mass.md), [wire length](wire-length.md), [the models](README.md), [changes to results](../changes.md)
