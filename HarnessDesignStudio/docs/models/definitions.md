# Definitions: what the tool fixes because it is a definition

Most of what a result depends on is a **setting** you can change ([selectable models](selectable-models.md), [the configuration](../CONFIG.md)) or an **assumption** the tool says it makes ([the assumptions](README.md#the-assumptions-built-into-the-program)). A few things are neither: they are fixed because they are a definition or a numerical device, not an engineering choice. `harness-design-studio settings DIR` lists them after the assumptions, and a test (`tests/test_settings.py`) fails on a number in a calculation that is none of the three, so that a new constant cannot slip into the code unseen. This page says what each one is, where it lives, and what it does to a result.

## Contents

- [`D-AWG`: the cross-section of a gauge](#d-awg-the-cross-section-of-a-gauge)
- [`D-LIMIT-TOLERANCE`: a value at its limit is not over it](#d-limit-tolerance-a-value-at-its-limit-is-not-over-it)
- [`D-DATA-ROUNDING`: numbers in the data files](#d-data-rounding-numbers-in-the-data-files)
- [`D-IMPORT-LENGTH-BOUND`: the largest length that is accepted](#d-import-length-bound-the-largest-length-that-is-accepted)
- [`D-TWISTED`: which constructions are twisted](#d-twisted-which-constructions-are-twisted)
- [`D-MM-TO-M`: millimetres to metres](#d-mm-to-m-millimetres-to-metres)
- [What a definition is not](#what-a-definition-is-not)

## `D-AWG`: the cross-section of a gauge

**Title:** The cross-section of a gauge. **Lives in:** `core/units.py`.

The AWG diameter is 0.127 mm × 92^((36 − n)/39) and the cross-section is that of a solid round conductor, π/4 × d², for the gauges 0 to 40. The voltage drop ([wire sizing](wire-sizing.md)) divides by this cross-section; the explanation of a wire shows it as the step *Cross-section A*, and the screens and explanations write it beside the gauge (`24 AWG (0.205 mm²)`, three significant digits). The data files hold it in full as a column of its own (`export-data`, column *Cross-section (mm²)*).

*Worked example.* For AWG 24: d = 0.127 × 92^(12/39) = 0.51054 mm, and A = π/4 × 0.51054² = 0.20473 mm². `harness-design-studio explain DIR W001-001` on the `flatsat` example prints this as `Cross-section A: π/4 × d², d = 0.127 mm × 92^((36 − 24)/39) = 0.20473 mm²`. A stranded conductor, a plated one or a conductor of another standard has another area; the tool does not know it.

## `D-LIMIT-TOLERANCE`: a value at its limit is not over it

**Title:** A value at its limit is not over it. **Lives in:** `core/generate/sizing.py` (`exceeds`).

A value within one billionth (relative) of its limit is taken to be *at* the limit, not over it. Sizing and every design rule that compares a number with a limit call the same function, so the generator and the rule agree at the exact limit; without it, a current of 0.8 A against a limit computed as 2 × (0.6 × 0.9) could be "over" by floating-point noise in one place and "within" in another. An extension rule uses the same comparison ([extend the tool](../user-manual/extend-the-tool.md)).

*Worked example.* A wire that carries exactly its derated limit passes; one that carries 1.0000001 times its limit fails. The *Check* line of an explanation, `within the limit, 0 A to spare`, is this comparison.

## `D-DATA-ROUNDING`: numbers in the data files

**Title:** Numbers in the data files. **Lives in:** `core/outputs/tables.py` (`data_num`).

A number written to a data file or table is rounded to 9 decimals and written without an exponent, so that sums carry no floating-point noise (`0.3`, not `0.30000000000000004`) and the same design gives the same bytes. The open data (`export-data`) and the output tables use it, and the script that reproduces a result from the files ([export the data](../user-manual/export-the-data.md)) asks for agreement to the same 9 decimals. The explanation on screen shows the number to the digits that matter, not rounded to 9 decimals.

*Worked example.* The voltage drop of `W001-001` is 0.4583591010499786 V in the calculation and `0.45835910105` in `wire_sizing.csv`.

## `D-IMPORT-LENGTH-BOUND`: the largest length that is accepted

**Title:** Largest length that is accepted. **Lives in:** `core/generate/lengths.py` (`MAX_LENGTH_M`) and `core/model`.

A length above 10,000 m is refused, from an import and from a hand edit: it is a unit mistake (millimetres read as metres), not a harness. The limit is not a design limit and is not a setting; a length at or below it is accepted whatever it is. The accessory lengths in the build data are bounded the same way in millimetres (100,000 mm) as a guard against a typing slip. The conversion on import and the echo of what was converted are on the page [units on import](import-units.md).

*Worked example.* A row of `import-lengths` whose value is 12000 (metres) is refused with the reason `'12000' is too large (a length can be at most 10000 m)`.

## `D-TWISTED`: which constructions are twisted

**Title:** Which constructions are twisted. **Lives in:** `core/settings.py` (`TWISTED_CONSTRUCTIONS`).

The constructions `twisted_pair`, `twisted_shielded_pair`, `quad` and `twinax` are twisted. The take-up of twisting (`model.twist_takeup_fraction`) is applied to the wires of these constructions only, and only when the length model is `path_loops_allowance_twist` ([selectable models](selectable-models.md#length-model)). The list is a definition, not a setting: which constructions twist is a property of the construction. How much length twisting takes up is a setting, and is 0 by default.

*Worked example.* With the model `path_loops_allowance_twist`, `twist_takeup_fraction` 0.05 and no allowance, a twisted pair with a path of 3.25 m and two loops of 0.1 m has the length (3.25 + 0.2) × 1.05 = 3.6225 m; a single wire of the same path stays 3.45 m. `explain DIR WIRE` names the take-up as a step.

## `D-MM-TO-M`: millimetres to metres

**Title:** Millimetres to metres. **Lives in:** `core/outputs/tables.py` (`bom_contributions`).

An accessory length in millimetres is divided by 1000 to give metres, in the bill of materials ([bill of materials](bom.md)): the quantity of a part counted in metres is the sum of `length_mm × quantity / 1000`.

*Worked example.* Four pieces of 250 mm of sleeving are 250 × 4 / 1000 = 1 m in the bill of materials.

## What a definition is not

- It is not a claim that the definition is the right one for your programme: the AWG formula is the usual one for a solid conductor; if your wires are specified by another area, the number you use is yours.
- It is not changeable in `config/*.json`. A definition that you need to change is a request to make it a setting, with today's value as its default.
- It is not an assumption: an assumption is a modelling choice (a round trip, a bundle of all wires) and is listed with its settings on the pages of the models.

Next: [the models](README.md), [wire sizing](wire-sizing.md), [selectable models](selectable-models.md), [the final audit](../transparency_final_audit.md)
