# Mass: how the mass of a wire and of a harness is made

This page explains the mass the tool gives a wire and a harness: the number in the mass and length table, the build workbook and the readiness check. It is written from what the program does, and the numbers come from the `flatsat` example, where you can repeat them.

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The equations](#the-equations)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

For each harness the tool adds up the mass of its connectors and the mass of its wires, shows the total of what is known, and adds a margin. It does not weigh anything: every mass comes from the parts library of the project, and every length from the wire (see [wire length](wire-length.md)).

## The equations

- A wire: `m = mass per metre of its part × L / conductors of the part`
- A harness: `m = the sum of the connector masses + the sum of the wire masses`
- With margin: `m × (1 + mass margin fraction)`

## The inputs and where they come from

| Input | Unit | Source |
| --- | --- | --- |
| Mass of a connector | g | The connector part of the library: `mass_g`. |
| Mass per metre of a wire part | g/m | The wire part of the library: `mass_per_m_g`. |
| Conductors of the wire part | none | The wire part of the library: `conductors` (1 for a single wire, 2 for a twisted pair part). |
| Length of the wire | m | [Wire length](wire-length.md). |
| Mass margin fraction | none | `config/generation.json`: `mass_margin_fraction`. |

The project records no source for a mass unless the note of the part says so.

## The assumptions it rests on

- **A-MASS-SCOPE.** The mass counts each connector of the harness and each wire. It does not count contacts, backshells, accessories (sleeving, heat shrink, labels), splices, solder or shield terminations. A part without a mass is named as missing and never replaced by a guess. The margin is added to the total only.
- **A-MASS-CONDUCTORS.** A wire carries its share of a multi-conductor part: the mass per metre of a twisted pair part is divided by its 2 conductors for each of its two wires, so that the cable is counted once.

## A worked example

`harness-design-studio explain DIR W001` on the `flatsat` example prints the mass of the harness `W001`:

- **Mass: 456.4 g.** 18 connectors of part `EX-MICROD-9-M` at 12 g make 216 g. 18 wires of part `EX-WIRE-SINGLE` (4 g/m, 1 conductor), 60.1 m in all, make 240.4 g. The total is 216 + 240.4 = 456.4 g. The margin fraction is 0.1, so the margin is 45.64 g and the mass with margin is 502.04 g.
- For one wire, `explain DIR W001-001` ends with its share: 4 g/m × 3.45 m / 1 = 13.8 g.

In the program, select the harness or the wire and open **Show the calculation** in the **Why** tab for the same text.

## What happens when a value is missing

A mass is never made up. When a connector part has no mass, a wire part has no mass per metre, or a wire has no length, the derivation names it, and the total is "the total of what is known", which is also what the mass and length table says (*Complete: no*).

## What the model does not do

- It does not count what the audit lists as left out (see the assumption A-MASS-SCOPE): a harness with sleeving and backshells weighs more than this number.
- It does not know the real mass of a part; it uses the library.
- The margin is one fraction of the whole total, not a margin per part.

Next: [bill of materials](bom.md), [wire length](wire-length.md), [wire sizing](wire-sizing.md), [the models](README.md), [changes to results](../changes.md)
