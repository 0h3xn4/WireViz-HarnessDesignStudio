# Wire sizing: the current a wire may carry and its voltage drop

This page explains how the tool decides the gauge of a wire and how it checks the wire afterwards: the current its gauge may carry after derating, and the voltage drop over its length. It is written from what the program does, and the numbers in the example come from the `flatsat` example, where you can repeat them.

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The equations](#the-equations)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [The choice of the gauge](#the-choice-of-the-gauge)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [Where else the same numbers are used](#where-else-the-same-numbers-are-used)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

For every wire that carries an interface with a known current, **Generate** chooses the smallest conductor (the highest AWG number) in the ampacity table whose derated current limit is not below the current. It then makes the conductor larger, one listed size at a time, until the voltage drop is not above the limit. If no listed gauge carries the current, or none keeps the drop under the limit, it stops with an error and says which. A wire you size by hand (gauge, part, colour or length) is kept as you set it and is not sized again; the design rules still check it. `explain DIR WIRE` shows the two limits as the derivations of kind `wire-current-limit` and `wire-voltage-drop`, and the search that picked the gauge as the derivation of kind `gauge`.

## The equations

The derated current limit of a gauge:

> limit = base ampacity of the gauge × bundle factor K × temperature factor

The voltage drop over a wire:

> ΔV = I × ρ × L / A × n

where I is the current of the interface in A, ρ the resistivity of the conductor in Ω·m, L the length of the wire in m, A the cross-section of the conductor in m² and n the number of conductors counted. The cross-section A is that of a solid round conductor of the AWG diameter, d = 0.127 mm × 92^((36 − AWG)/39), so A = π/4 × d². The screen and the explanations name a gauge with this cross-section, `24 AWG (0.205 mm²)`; the files the tool writes keep the plain gauge, and `export-data` has the cross-section as a column of its own (`area_mm2`; [export the data](../user-manual/export-the-data.md)).

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
- **A-DC-SOLID.** The drop is a DC drop in a solid round conductor. There is no temperature rise of the conductor, no contact resistance, no stranding factor and no AC effect. ρ is the value of the configuration. Stays built in: the settings of the model choose the resistivity, not the method; stranding, contact resistance or an AC effect would be a different equation and not a number to type.
- **A-BUNDLE-ALL.** The bundle factor is taken for the number of all wires of the harness, signal wires and unloaded wires included, each taken as fully loaded. A harness is not divided into bundles, and the length term of the standard's table is taken as 1, the conservative case. A harness of 50 wires therefore gets a much lower limit for every wire than a bundle of 5 power wires would.
- **A-TEMP-FACTOR.** The temperature factor is the single number of the configuration. It is not computed from an ambient temperature, a wire's temperature rating or the insulation.
- **A-AMPACITY-AWG.** The base ampacity depends on the AWG only. It does not depend on the wire part, the insulation, the stranding or the environment.

## A worked example

In the program, select the wire and open **Show the calculation** in the **Why** tab; it shows the same text. `harness-design-studio explain DIR W001-001` on the `flatsat` example (a 0.8 A power wire, `IF-010`, in harness `W001`) prints:

- **Derated current limit: 1.08 A.** The base ampacity of AWG 24 (0.205 mm²) is 2 A; the bundle factor K is 0.6 and the temperature factor 0.9, so the combined factor is 0.6 × 0.9 = 0.54 and the limit is 2 × 0.54 = 1.08 A. The wire carries 0.8 A: within the limit, 0.28 A to spare.
- **Voltage drop: 0.458359 V.** I = 0.8 A, ρ = 1.7e-08 Ω·m, L = 3.45 m (the length of the wire), AWG 24, so A = 0.20473 mm², and n = 2 because the interface type is in the category power. The resistance of the conductors counted is 1.7e-08 × 3.45 / 2.0473e-07 × 2 = 0.572949 Ω, and the drop is 0.8 × 0.572949 = 0.458359 V. The limit is 1 V: within the limit, 0.541641 V to spare.

`--json` prints the same as data, for a spreadsheet or a script. The command changes and writes nothing.

## The choice of the gauge

`explain DIR WIRE` shows the search that picked the gauge as the derivation of kind `gauge` (it follows the length of the wire). It replays the search with the function that **Generate** calls (`size_wire` in `core/generate/sizing.py`), with the same inputs, and prints what that function returns: the settings it used, every gauge it tried in order, the limit of each after derating, the first that carries the current, then the drop of each gauge tried from there on, and the first that keeps the drop within its limit. There is no second implementation of the search that could drift from the first: a test compares the gauge of the derivation with the gauge of the wire on the four packaged examples. The derivation rests on A-AMPACITY-AWG, A-BUNDLE-ALL, A-TEMP-FACTOR, A-DC-SOLID and A-ROUND-TRIP. The check it ends with is the current of the wire against the derated limit of the gauge taken.

The replay is run on the design and the settings as they are now. If the wire still has a gauge from an earlier generation and the search would now give another, the derivation says so (it names both) and does not change the wire; **Generate** again follows the design.

A gauge that nobody searched for says so: for a gauge set with a reason the derivation shows the reason and the gauge the search gives now; for a locked wire (no reason recorded) or a wire drawn by hand it says that generation keeps the wire as it is. A wire whose interface has no current gets the default gauge of the interface type or the configuration, and the derivation says that. When no gauge carries the current, or none keeps the drop within its limit, the derivation shows every gauge tried and the result is "none", with the same words as the error of **Generate**. When a value is missing it names it, as the other derivations do.

The derivation is computed when you ask for it. `explain DIR --all --out FOLDER` does not contain it, so `derivations.json` and `derivations.csv` are the same as before it existed.

`harness-design-studio explain DIR W004-003` on the `flatsat` example (a 5 A power wire, `IF-003`, 3.2 m) prints these steps:

- The combined factor is K × temperature = 0.6 × 0.9 = 0.54.
- AWG 26, 24, 22, 20 and 18 are too small for 5 A: their limits are 1 × 0.54 = 0.54 A, 1.08 A, 1.62 A, 2.7 A and 3.78 A.
- AWG 16 carries it: 10 × 0.54 = 5.4 A.
- The drop of AWG 16 is 5 × 1.7e-08 × 3.2 / 1.3087e-06 × 2 = 0.415681 V, within the limit of 1 V, so no larger conductor is tried: the gauge is AWG 16 (1.31 mm²), and the wire carries 5 A of the 5.4 A it may.

## What happens when a value is missing

The tool never guesses an engineering value. If a configuration value or an input is not set, the gauge stays undecided, and the derivation says exactly which values are missing: `explain` prints "Not decided yet, because these are not set" and names them (for example `derating.temperature_derating` or "the current of the interface (set Max current on the interface)"). In the `first-steps` and `small-satellite` examples nothing is sized for this reason: the derating values are not set.

## Where else the same numbers are used

The design rules `current-over-wire` and `voltage-drop` use exactly these numbers: the generator and the rules call the same functions for the derated limit and for the drop, and the same comparison, so they cannot disagree at the exact limit. The derivation calls them too and shows the same verdict as the rule. The rule `bundle-current` uses a related limit and is explained on its own page when it is written; the check of the contacts is on the [contact current](contact-current.md) page.

## What the model does not do

- It does not choose a wire part: the part is set by the construction of the interface, not by the gauge.
- It tries the gauges of the ampacity table only, from the smallest conductor up, and takes the first that passes: it does not weigh mass or cost against a larger gauge.
- It does not check the gauge against the contact that crimps it (a crimp range) or the strip length.
- It does not compute a temperature from the current, and it does not consider the length of a bundle.
- It does not offer another method (a different drop model, a bundle defined by the loaded wires). These are planned as selectable models, with today's behaviour as the default.

Next: [the models](README.md), [the design rules](../RULES.md), [the configuration](../CONFIG.md)

The length that the voltage drop uses is explained on the [wire length](wire-length.md) page.
