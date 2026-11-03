# Shield groups and shield ends

This page explains which wires form a shield group and why the group has the ends it has. It is written from what the program does (`core/generate/shields.py`, used by generation and by `explain`), and the examples come from the `flatsat` example, where you can repeat them with `harness-design-studio explain DIR W001-S1` or `explain DIR W005-S4`.

## Contents

- [What the tool decides](#what-the-tool-decides)
- [Which wires form a group](#which-wires-form-a-group)
- [The ends](#the-ends)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

Generation makes one shield group for each shield or twisted pair a harness needs, with its wires and its two ends. `explain DIR GROUP` (or `HARNESS.GROUP`, or the wire in the group) gives a derivation of kind `shield-group`: why the group exists, why it has these ends, and how the ends compare with the grounding concept. The cut list shows the group of each wire (*Shield group*).

## Which wires form a group

The group follows the construction and the shielding of the interface type:

| Interface type | Groups made |
| --- | --- |
| `single` construction | none |
| `coax` | one group of kind `coax` for each wire |
| `quad` | one group of kind `quad` |
| a pair of signals (the signals with the same `pair`; the way out and the way back of a power or ground type) | one `twisted_pair`, or a `shielded_pair` when the type shields per pair |
| shielding `overall` | one more group of kind `overall_shield` over all wires of the interface |

A group a person made is kept.

## The ends

Every generated group except a coax gets the ends `shield_end_a` and `shield_end_b` of `config/generation.json` (`backshell_360`, `pigtail` or `floating`). While one is not set, `floating` is used and generation says so. A **coax** shield is bonded at both ends (`backshell_360`), fixed by the file format. A twisted pair has no shield to ground, and the rules skip it.

The rules that look at the ends are `shield-unterminated` (both ends floating), `shield-wrong-end` (the ends differ from the grounding concept) and `shield-bonding` (both ends are `backshell_360`, when `config/emc.json: shield_bonding` asks for it); each is explained with the ends it saw.

## The inputs and where they come from

| Input | Source |
| --- | --- |
| Construction, shielding, pairs | The interface type. |
| The wires of the interface | The harness. |
| Ends of the concept | `config/generation.json: shield_end_a`, `shield_end_b` |
| Bonding required | `config/emc.json: shield_bonding` |

## The assumptions it rests on

- **A-SHIELD-GROUPS.** A group follows the construction and the shielding of the interface type.
- **A-SHIELD-ENDS.** The ends are the grounding concept of the project, except a coax.

## A worked example

`harness-design-studio explain DIR W001-S1` on the `flatsat` example prints **twisted_pair, end A backshell_360, end B floating**: the wires `W001-001` and `W001-002` are the pair `power` of `IF-010` (type `power_primary`, shielding none), twisted together. The ends are the concept (`backshell_360` and `floating`), and the comparison says *equal*.

`explain DIR W005-S4` prints **coax, end A backshell_360, end B backshell_360**: the type `rf_coax` is a coax, so each wire is a shield, with the ends fixed by the file format; the concept (`backshell_360`/`floating`) does not apply.

## What happens when a value is missing

If a shield end of the concept is not set, the derivation says that `floating` is used until `shield_end_a` and `shield_end_b` are set. A group no rule of the generator makes today (the design changed since generation) is named, with the advice to generate again. A group made by hand says so.

## What the model does not do

- It does not know where a shield is grounded in the hardware, only the end type typed in the concept.
- It does not check the resistance of a shield bond; the check list names what needs measurements.
- It does not choose between pigtail and backshell: that is the project's concept.

Next: [labels and colours](labels-and-colours.md), [rule limits](rule-limits.md), [the models](README.md)
