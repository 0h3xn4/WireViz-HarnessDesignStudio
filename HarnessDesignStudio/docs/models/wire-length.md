# Wire length: where the length of a wire comes from

This page explains the length the tool gives a wire: the number in the wire list, the cut list, the mass and the voltage drop. It is written from what the program does, and the numbers in the example come from the `flatsat` example, where you can repeat them.

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The equation](#the-equation)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [Three ways a length can be there](#three-ways-a-length-can-be-there)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

When **Generate** builds a harness, it lays routing segments between the connectors and gives every wire the length of the path through those segments between its two connectors, plus a service loop at each end. Everything that needs a length asks one function (`wire_length`): the wire list, the cut list, the mass, the voltage drop, the design rules and the release gate. Nothing else makes up a length.

## The equation

`L = sum of the routing segments between its connectors + 2 × service loop`

The path is the one path through the tree of segments from the connector at one end of the wire to the connector at the other.

## The inputs and where they come from

| Input | Unit | Source |
| --- | --- | --- |
| Length of each segment on the path | m | The segment of the harness: generated from the zones and chain, or entered or imported by you (**Import lengths**, or the segment table). The project records no source for a segment length. |
| Service loop | m | `config/generation.json`: `service_loop_m`. When it is not set, nothing is added and generation says so in a note. |
| Length stored on the wire | m | Only when a length was typed on the wire (**Edit wire**), imported, or kept from an earlier generation. |

## The assumptions it rests on

- **A-PATH-UNIQUE.** The length is the one path through the segments. If the segments form a loop there is no single length, the length stays undecided and the design rule `segment-loop` reports it. Bend radii, tolerances and the part of a connector inside its backshell are not added.
- **A-SERVICE-LOOP.** A generated wire is longer than its path by two service loops, one at each end, the same for every wire. It is a setting of the configuration (`service_loop_m`).

## A worked example

`harness-design-studio explain DIR W001-001` on the `flatsat` example prints, for the length:

- **Length: 3.45 m.** The path between the two connectors uses three segments: `W001-L3` 1.5 m, `W001-L1` 0.5 m and `W001-L12` 1.25 m, which sum to 3.25 m. The service loop of the configuration is 0.1 m, so the two loops add 0.2 m, and the generated length is 3.25 + 0.2 = 3.45 m. This is the length stored on the wire and the one the tables, the mass and the voltage drop use.

In the program, select the wire and open **Show the calculation** in the **Why** tab for the same text.

## Three ways a length can be there

The derivation says which one applies, so a number in the cut list is never of unknown origin:

1. **Generated.** The length stored on the wire equals the path through the segments plus two service loops. The derivation lists each segment and both loops.
2. **Entered by hand and locked.** A length typed on the wire with **Edit wire** locks the wire, and generation keeps it. The derivation shows it as *Length stored on the wire*. The segments are no longer used for this wire.
3. **Stored on the wire, origin not recorded.** A length that does not equal the path plus two service loops and is not locked: it was imported, or the segments or the service loop changed since generation. Generate again, or lock the length on purpose, to make the origin clear.

A wire with no length of its own is measured from the segments alone, without service loops, until Generate gives it one.

## What happens when a value is missing

A length is never made up. The derivation names what is missing: that the harness has no routing segments, that the segments do not give one path between the connectors (a loop, see `segment-loop`), or which segments have no length. Mass, the cut list and the voltage drop then say the same, because they use the same function.

## What the model does not do

- It does not add a bend radius, a tolerance, a cut allowance, the length inside a connector or backshell, or a strip length. Strip lengths are typed, per end, on the wire.
- It does not measure the harness: the segment lengths are yours, or from your CAD export.
- It does not give a service loop per wire or per end: one value, doubled.

Next: [wire sizing](wire-sizing.md), [the models](README.md), [changes to results](../changes.md)
