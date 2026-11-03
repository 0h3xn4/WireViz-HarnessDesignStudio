# Labels and colours

This page explains the text printed on the labels of a wire and of a cable connector, and the colour a wire has. It is written from what the program does (`core/outputs/tables.py`, `core/wirecolours.py`, `core/generate/engine.py`), and the examples come from the `flatsat` example, where you can repeat them with `harness-design-studio explain DIR W001-001` (a wire) and `explain DIR W001-P1` (a connector).

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The label of a wire](#the-label-of-a-wire)
- [The label of a connector](#the-label-of-a-connector)
- [The colour of a wire](#the-colour-of-a-wire)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

The *Labels* table and the *Labels* sheet of the build workbook list the labels to print. The text is made by one function for each kind of label, and `explain` calls the same function: kind `wire-label` (the two labels of a wire), `connector-label` (a cable connector) and `wire-colour`.

## The label of a wire

A wire has two labels, `ID-A` and `ID-B`, one for each end. Each reads

`wire ID` + ` name` + ` to far end` + ` [EMC class]`

- the **name** is the label a person gave the wire (the *Label* field), else its **signal**, else nothing (only the ID is printed). The signal of a wire is the label of the link of its interface type: `PWR`, or `TX+/RX+` for a wire between two different signal names;
- the **far end** is the connector and pin at the other end (`W001-P11.1` on label A);
- the **EMC class** of the interface type is added in brackets when the type has one, so that personnel see the category (ECSS-E-ST-20-07C 4.2.13.1 d is cited by ID).

## The label of a connector

A cable connector prints its **name**: the label of the connector, else the label of the device connector it plugs into, else nothing; then `(ID mates DEVICE-CONNECTOR)`. With no name the text is `ID mates DEVICE-CONNECTOR`.

## The colour of a wire

Generation gives a wire the colour that `generation.wire_colour_by_signal` lists for its signal. For a wire labelled `TX+/RX+` the whole label is looked up first, then each name in turn. A signal that is not in the table gets **no colour**, and the build workbook shows it as a check that blocks (*Wires without a colour*, see [readiness](readiness.md)). A colour a person typed on the wire, or imported, is kept at generation. `explain` says which of the three applies: from the table (and which key), typed or imported, or none. The IEC 60757 code (`RD` for red) is from a table of the tool that only names colours; a name it does not know is kept as typed.

## The inputs and where they come from

| Input | Source |
| --- | --- |
| Label of a wire or connector | The design (typed by a person). |
| Signal | The wire; it comes from the interface type (`core/generate/wiring.py`). |
| EMC class | The interface type (`emc_class`). |
| Far end | The wire. |
| Colour table | `config/generation.json: wire_colour_by_signal` |
| Colour of the wire | The wire. |
| Pattern of the wire IDs | `config/naming.json: wire` |

## The assumptions it rests on

- **A-LABEL-FORMAT.** The form of a label is built into the tool; only the words come from the design.
- **A-COLOUR-TABLE.** A wire gets the colour of its signal from the table and no other; the colour names and codes decide nothing.

## A worked example

`harness-design-studio explain DIR W001-001` on the `flatsat` example prints:

- **Wire labels:** `W001-001-A "W001-001 PWR to W001-P11.1"` and `W001-001-B "W001-001 PWR to W001-P2.1"`. The wire has no label of its own, so the name is its signal `PWR`; the interface type has no EMC class, so there is no tag.
- **Colour: red.** It is the entry `PWR` of `wire_colour_by_signal`; the IEC 60757 code is `RD`.

## What happens when a value is missing

A wire with neither a label nor a signal prints only its ID. A wire with no colour has the derivation *Colour* with no result, and names the table entry or the colour to set.

## What the model does not do

- It does not choose a label for you or check that labels are unique across harnesses.
- It does not invent a colour: a signal that is not in the table stays without one.
- It does not know the colour of a wire in the hardware; the table is a convention of the project.

Next: [shields](shields.md), [readiness](readiness.md), [the models](README.md)
