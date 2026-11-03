# Overrides: a value set by hand, and what it does to the checks

This page explains the derivation *Overridden by the engineer* (`wire-override`) that `explain` gives for a wire whose gauge, wire type, colour or length you set yourself in place of the value the design gives. The how-to is in [Override a value and keep a history](../user-manual/override-and-keep-a-history.md).

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The equation](#the-equation)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [A worked example](#a-worked-example)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

A generated wire takes its gauge, wire type, colour and length from the design. When you set one of them by hand (`override DIR WIRE FIELD VALUE --reason TEXT`, or the **Reason** box of the wire editor), the tool keeps your value when the harness is generated again and records why. The other values of the wire still follow the design. A wire you drew by hand has no design value to replace, so it has no override.

## The equation

`value used = the value you set` (for each overridden field), and `value the design gives = what generation would set for the wire`.

The tool then runs the usual checks with the value you set. The derivation shows the consequence: the current the gauge may carry after derating and the voltage drop over the length, each as actual, limit and margin.

## The inputs and where they come from

| Input | Source |
| --- | --- |
| Value set | `overrides` of the wire in the harness file: one entry per field, each with its reason |
| Value the design would give | The same generation that sizes the wire, run without the override |
| Current limit and voltage drop | The derivations `wire-current-limit` and `wire-voltage-drop` of the wire, with the value you set |

Who set the value and when is in the journal of the project (`journal`), never in the design files, so two copies of a design with the same overrides have the same files and the same hash.

## A worked example

Set the gauge of a wire to 24 AWG with the reason "supplier stock". `explain DIR WIRE` starts with the derivation *Overridden by the engineer*: the value set (24), the value the design gives (for example 20), your reason, and the consequence, for instance that the current the gauge may carry is below the load and the margin is negative. The rule `current-over-wire` then reports an error that you can accept as a deviation with a reason (`deviation DIR FINDING --reason TEXT`).

## What happens when a value is missing

If the table of ampacity has no entry for the gauge you set, the derivation says so and names the missing entry instead of a number. The override is still kept.

## What the model does not do

It does not decide whether your value is right. It does not hide the difference between your value and the design's: both are shown, in the wire table ("Overridden"), the wire list, the build workbook, the drawing and the release comment.
