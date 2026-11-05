# Readiness: what "Ready to build" means

This page explains the answer *Ready to build* on the first sheet (*Start here*) of the build workbook of a harness, and the eight checks behind it. It is written from what the program does, and the numbers come from the `flatsat` example, where you can repeat them with `harness-design-studio explain DIR W001`.

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The rule](#the-rule)
- [The eight checks](#the-eight-checks)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

For each harness the workbook says *yes* or *no* to *Ready to build*. The tool works the answer out from the model alone, with the same function that writes the sheet (`buildsheet.readiness`). `explain DIR HARNESS` shows the answer (kind `readiness`), then one derivation for each of the eight checks (kind `readiness-check`) with the count and the list of what is open: the wire IDs, or `CONNECTOR.PIN` for a pin.

## The rule

`Ready to build = yes` when none of the checks named in `model.readiness_blocking` has an open item.

The other checks are notes: the sheet shows their open items, and they do not change the answer. By default the first four checks block. The answer is a *yes* even when the values it rests on are placeholders; the sheet then writes *yes (values rest on placeholder configuration: ...)* and `explain` names the files.

## The eight checks

| Check | A wire, pin or part is open when | Blocks by default |
| --- | --- | --- |
| Wires without a length | no length is stored on the wire and its path through the routing segments is not complete | yes |
| Wires without a gauge | the gauge (AWG) is not decided | yes |
| Wires without a colour | the colour is empty | yes |
| Wires without a part | the wire names no wire part of the library | yes |
| Pins in use without a termination | a pin with a wire on it still has the termination *unspecified* | no |
| Wires without strip lengths | the strip length at either end is empty | no |
| Pins in use without a contact part | a pin with a wire on it names no contact part | no |
| Parts that are not approved | a part used by a connector or wire of the harness is not in the parts list, or its approval is not *approved* | no |

## The inputs and where they come from

| Input | Source |
| --- | --- |
| Which checks block | `config/model.json: readiness_blocking` (the tool's default is the first four checks above). |
| Wires, pins and parts of the harness | The design. |
| Placeholder files | The configuration files still marked as not reviewed. They change the wording of a *yes*, not the answer. |

## The assumptions it rests on

- **A-READY-CHECKS.** Which checks decide the answer is a setting (`model.readiness_blocking`).
- **A-READY-SCOPE.** The answer looks at the eight checks of the sheet and at nothing else: not at design rule errors, the release state or sign-off of the harness, the test limits or the values of the configuration. A *yes* is not a statement that the harness passes its design checks or may be built. Stays built in: it states what the answer is made from (the eight checks of the sheet); which of them block is already the setting `readiness_blocking`.

## A worked example

`harness-design-studio explain DIR W001` on the `flatsat` example prints, after the mass:

- **Ready to build: yes (values rest on placeholder configuration: derating, emc, generation, segmentation, segregation, titleblock).** The four checks that block have nothing open. Four notes are open: 36 pins without a termination, 18 wires without strip lengths, 36 pins without a contact part and 2 parts that are not approved (`EX-MICROD-9-M`, `EX-WIRE-SINGLE`). *Check: no check that blocks is open*, with actual 0 and limit 0.
- `explain DIR W001` also lists each check on its own, for example *Wires without a colour: 0 open*. Take the colour off one wire and the answer becomes *no*, the check reads *1 open; this check blocks Ready to build*, the open item is the wire ID, and the text says what to do (*Set the colour of the signal ... or of the wire*).
- Set `readiness_blocking` to `["Parts that are not approved"]` in `config/model.json` and the colour check turns into a note while the unapproved parts block.

## What happens when a value is missing

A check with open items is not an error of the tool: it is the list of what a person has to do. The derivation names each open item and, for a check that blocks, the sentence of the sheet that says what to do.

## What the model does not do

- It does not look at the design rules. A harness with a current finding can be *ready to build*.
- It does not look at the release state or at who signed.
- It does not check that the test limits are set, or that the values of the configuration are reviewed (it only says when they are placeholders).
- It does not decide whether the harness can be built; it lists what the workbook is still missing.

Next: [test limits](test-limits.md), [the models](README.md), [changes to results](../changes.md)
