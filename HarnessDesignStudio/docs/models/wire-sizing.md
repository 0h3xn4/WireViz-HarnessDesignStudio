# Wire sizing: the current a wire may carry and its voltage drop

This page explains how the tool decides the gauge of a wire and how it checks the wire afterwards: the current its gauge may carry after derating, and the voltage drop over its length. It is written from what the program does, and the numbers in the example come from the `flatsat` example, where you can repeat them.

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The equations](#the-equations)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [Where else the same numbers are used](#where-else-the-same-numbers-are-used)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

For every wire that carries an interface with a known current, **Generate** chooses the smallest conductor (the highest AWG number) in the ampacity table whose derated current limit is not below the current. It then makes the conductor larger, one listed size at a time, until the voltage drop is not above the limit. If no listed gauge carries the current, or none keeps the drop under the limit, it stops with an error and says which. A wire you size by hand (gauge, part, colour or length) is kept as you set it and is not sized again; the design rules still check it.

## The equations

The derated current limit of a gauge:

> limit = base ampacity of the gauge × bundle factor K × temperature factor

The voltage drop over a wire:

> ΔV = I × ρ × L / A × n

where I is the current of the interface in A, ρ the resistivity of the conductor in Ω·m, L the length of the wire in m, A the cross-section of the conductor in m² and n the number of conductors counted. The cross-section A is that of a solid round conductor of the AWG diameter, d = 0.127 mm × 92^((36 − AWG)/39), so A = π/4 × d².

## The inputs and where they come from

| Input | Unit | Where it comes from |
| --- | --- | --- |
| Base ampacity of the gauge | A | `config/derating.json`: `ampacity_a_by_awg`. One table by AWG. |
| Bundle factor K | 1 | `config/derating.json`: `bundle_derating` (one factor), or `bundle_factor_by_count` (a table by number of wires; it replaces the single factor). When the table equals the one of the ECSS profile it is Table 6-41 of ECSS-Q-ST-30-11C. |
| Number of wires in the bundle | wires | Every wire of the harness. See assumption A-BUNDLE-ALL. |
| Temperature factor | 1 | `config/derating.json`: `temperature_derating`. One number. |
| Current I | A | The interface of the wire: Max current. |
| Resistivity ρ | Ω·m | `config/generation.json`: `conductor_resistivity_ohm_m`. |
| Length L | m | The length of the wire itself if it has one, otherwise the sum of the routing segments of its harness between its two connectors. |
| Conductors counted n | 1 | 2 for an interface of the category power or ground, 1 for every other. See assumption A-ROUND-TRIP. |
| Voltage drop limit | V | `config/derating.json`: `max_voltage_drop_v`. |

The project records no source (standard, clause or test report) for the ampacity table, the temperature factor, the resistivity or the drop limit: they are the values you entered. `harness-design-studio config --apply-profile ecss-q-st-30-11c` fills in the standard's values where a setting is empty.

## The assumptions it rests on

These are choices built into the program. They are listed so that nobody has to say "the tool computed it". Today they cannot be changed without editing the program, except the two that are a value of the configuration.

- **A-ROUND-TRIP.** The voltage drop of a wire of a power or ground interface counts the current going out and coming back: n is 2, and the return is taken to have the same gauge and length as the wire itself. For every other category n is 1. A return of another gauge would give a different drop that this model does not see.
- **A-DC-SOLID.** The drop is a DC drop in a solid round conductor. There is no temperature rise of the conductor, no contact resistance, no stranding factor and no AC effect. ρ is the value of the configuration.
- **A-BUNDLE-ALL.** The bundle factor is taken for the number of all wires of the harness, signal wires and unloaded wires included, each taken as fully loaded. A harness is not divided into bundles, and the length term of the standard's table is taken as 1, the conservative case. A harness of 50 wires therefore gets a much lower limit for every wire than a bundle of 5 power wires would.
- **A-TEMP-FACTOR.** The temperature factor is the single number of the configuration. It is not computed from an ambient temperature, a wire's temperature rating or the insulation.
- **A-AMPACITY-AWG.** The base ampacity depends on the AWG only. It does not depend on the wire part, the insulation, the stranding or the environment.

## A worked example

In the program, select the wire and open **Show the calculation** in the **Why** tab; it shows the same text. `harness-design-studio explain DIR W001-001` on the `flatsat` example (a 0.8 A power wire, `IF-010`, in harness `W001`) prints:

- **Derated current limit: 1.08 A.** The base ampacity of AWG 24 (0.205 mm²) is 2 A; the bundle factor K is 0.6 and the temperature factor 0.9, so the combined factor is 0.6 × 0.9 = 0.54 and the limit is 2 × 0.54 = 1.08 A. The wire carries 0.8 A: within the limit, 0.28 A to spare.
- **Voltage drop: 0.458359 V.** I = 0.8 A, ρ = 1.7e-08 Ω·m, L = 3.45 m (the length of the wire), AWG 24, so A = 0.20473 mm², and n = 2 because the interface type is in the category power. The resistance of the conductors counted is 1.7e-08 × 3.45 / 2.0473e-07 × 2 = 0.572949 Ω, and the drop is 0.8 × 0.572949 = 0.458359 V. The limit is 1 V: within the limit, 0.541641 V to spare.

`--json` prints the same as data, for a spreadsheet or a script. The command changes and writes nothing.

## What happens when a value is missing

The tool never guesses an engineering value. If a configuration value or an input is not set, the gauge stays undecided, and the derivation says exactly which values are missing: `explain` prints "Not decided yet, because these are not set" and names them (for example `derating.temperature_derating` or "the current of the interface (set Max current on the interface)"). In the `first-steps` and `small-satellite` examples nothing is sized for this reason: the derating values are not set.

## Where else the same numbers are used

The design rules `current-over-wire` and `voltage-drop` use exactly these numbers: the generator and the rules call the same functions for the derated limit and for the drop, and the same comparison, so they cannot disagree at the exact limit. The derivation calls them too and shows the same verdict as the rule. The rules `bundle-current` and the contact rules use related limits and are explained on their own pages as they are written.

## What the model does not do

- It does not choose a wire part: the part is set by the construction of the interface, not by the gauge.
- It does not check the gauge against the contact that crimps it (a crimp range) or the strip length.
- It does not compute a temperature from the current, and it does not consider the length of a bundle.
- It does not offer another method (a different drop model, a bundle defined by the loaded wires). These are planned as selectable models, with today's behaviour as the default.

Next: [the models](README.md), [the design rules](../RULES.md), [the configuration](../CONFIG.md)

The length that the voltage drop uses is explained on the [wire length](wire-length.md) page.
