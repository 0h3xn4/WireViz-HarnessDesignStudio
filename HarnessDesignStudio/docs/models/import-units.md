# Units on import: how a value in a file becomes a value in the project

This page explains the conversions the imports make: the unit a file is read in, the factor, the rounding, and what is shown and recorded. It is written from what the program does, and the numbers can be repeated with the templates (`harness-design-studio templates DIR`).

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The conversions](#the-conversions)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

Nothing is converted unless the file's unit is known. A file has no unit in it, so the import reads a column in the unit it has always read it in, unless you say another with an option. Every import that converts says which unit it used and whether you gave it or it assumed it, and shows every converted value as it was written and as it is stored.

## The conversions

- Segment lengths (`import-lengths`): `stored metres = value × metres per unit`, rounded to 9 decimals (1 nm).
- Strip lengths and accessory lengths (`import-build-data`): `stored millimetres = value × (metres per unit ÷ 0.001)`, rounded to 6 decimals.
- Mass of parts (`import-parts`): `stored grams = value × grams per unit`, rounded to 9 decimals. A mass per metre is read in the same unit per metre.
- The current of the ampacity table is amperes and the ratings of a part are read as the numbers they are; neither is converted.

| Unit | Metres per unit | Grams per unit |
| --- | --- | --- |
| mm | 0.001 | |
| cm | 0.01 | |
| m | 1 | |
| in | 0.0254 | |
| ft | 0.3048 | |
| g | | 1 |
| kg | | 1000 |
| lb | | 453.59237 |
| oz | | 28.349523125 |

The inch and the foot are the international ones (exactly 0.0254 m and 0.3048 m); the pound and the ounce are the avoirdupois ones.

## The inputs and where they come from

| Input | Unit | Source |
| --- | --- | --- |
| The unit of a length column | mm, cm, m, in, ft | `--unit` of the command, or the unit box of the wizard. Without it: millimetres. |
| The unit of a mass column | g, kg, lb, oz | `--mass-unit` of `import-parts`. Without it: grams. The wizard reads grams. |
| The value | as written | A cell of the file: digits with a point or one decimal comma. |

## The assumptions it rests on

- **A unit that is not given is assumed.** A column is read in the default unit (millimetres for lengths, grams for masses) when no unit is given. The import prints `Unit: length in mm (assumed; --unit says another).` and records `unit` without `unit_given`.
- **A decimal comma is a decimal point.** A comma between digits in a length (the segment, strip and accessory lengths) is read as a decimal point (`1,5` is 1.5 and `1,234` is 1.234), never as a thousands separator. The build data import lists each such cell. The parts import refuses `1,234` instead of guessing which it is.
- **Position, not heading.** The columns of a segment length file are read by position, not by heading.

## A worked example

`segment-lengths.csv` of the templates has the rows `W001,W001-L1,850` and `W002,W002-L1,900`. Without `--unit`:

```
Unit: length in mm (assumed; --unit says another).
row 2: OK W001 / W001-L1: 850 mm = 0.85 m
row 3: OK W002 / W002-L1: 900 mm = 0.9 m
```

With `--unit in` the same file reads 850 in = 21.59 m and 900 in = 22.86 m (850 × 0.0254 and 900 × 0.0254). With `--unit m` it reads 850 m and 900 m. A file written in metres and read as millimetres therefore shows as `5.0 mm = 0.005 m`, and the person sees the error before anything is stored.

## What the model does not do

- It does not guess the unit from the size of the numbers or from a heading. A heading that names another unit than the option (`Strip A (mm)` with `--unit in`) is named in a warning.
- It does not convert the other quantities of a file (currents, voltages, temperatures, cycles): they are read as the numbers they are.
- It does not keep the original file; it keeps its name and its SHA-256 in the import record (`imports/records.json`), so that a changed file is noticed.

Next: [the imports](../IMPORTS.md), [the models of the tool](README.md).
