# As-built results: how a recorded value is compared

This page explains how the tool compares what a technician recorded with what was designed and with the test limits of the project: the measured resistances of the tests, the cut lengths and the strip lengths (against a tolerance, when the project sets one). It is written from what the program does, and the numbers come from the `flatsat` example, where you can repeat them with `harness-design-studio asbuilt DIR` and `harness-design-studio explain DIR W001.T001`.

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The rule](#the-rule)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

The tool keeps what was recorded (`asbuilt/records.json`) and, for each value, says one of: **recorded** (there is nothing to compare it with), **as designed**, **differs from design**, **within limit**, **out of limit**, **not compared** (the limit of the project is not set), **missing** (the sheet asks for it and nobody recorded it) or **stale record** (the design no longer has the thing the record is about). It does not decide that a harness passed. `explain DIR HARNESS.T001` and `explain DIR WIRE` give one derivation (kind `asbuilt-result`) for each measured value and each cut length, with the inputs, the margin and the check; `asbuilt DIR` lists every value, `export` writes the same table as `system/asbuilt_report.csv` and `.md`, and the build workbook of a harness that has records has an *As-built* sheet.

## The rule

**A measured test value** is compared with the limit the Tests sheet prints (the same numbers, from `config/generation.json`, see [test limits](test-limits.md)):

- a continuity test: `margin = limit - measured`, where the limit is the largest resistance accepted as continuous (`test_continuity_max_ohm`, in ohm). Within the limit when the margin is not negative.
- an insulation test: `margin = measured - limit`, where the limit is the smallest insulation resistance (`test_isolation_min_mohm`, in Mohm). Within the limit when the margin is not negative.
- the test voltage that was applied is compared with `test_isolation_voltage_v` (in V): a different voltage is listed as *differs from design*; the tool does not judge it.

**A cut length** (`cut_length_m`) and the strip lengths (`strip_a_mm`, `strip_b_mm`) are compared with the designed value: `difference = recorded - designed`. A difference smaller than 1e-9 is *as designed*. **By default the tool applies no tolerance**, because it has none (D-11: it ships no value for what an engineer decides): any other difference is listed as *differs from design* with its size, a cut length that is a few millimetres long or short is listed, and whether that is acceptable is for a person.

**With a tolerance the project sets**, a length is judged like a test value against its limit. Two optional settings of `config/generation.json`, both in millimetres and both not set by default, give the tolerance: `asbuilt_cut_tolerance_mm` for the cut length and `asbuilt_strip_tolerance_mm` for both strip lengths (assumption A-ASBUILT-TOLERANCE). Then `distance = |recorded - designed|` in millimetres and `margin = tolerance - distance`. A length with a margin that is not negative (a distance equal to the tolerance counts) is *within limit*; one with a negative margin is **out of limit**. The line gives the recorded and the designed length, the margin (in the unit of the value: metres for a cut length, millimetres for a strip length), the tolerance and the key it came from. A length that is exactly as designed stays *as designed*, and a tolerance of 0 accepts no difference at all. The tolerance is the same for every wire; it does not follow the length, the gauge or the part. It is not read by generation and a release does not freeze it.

**The result a technician wrote** (`pass` or `fail`) is kept as written. A result `fail` is shown as out of limit. A result `pass` with a measured value that is out of its limit is shown as out of limit with the note *recorded as passed: the tool does not accept it*. The tool never changes a recorded value and never turns an out-of-limit value into a pass.

## The inputs and where they come from

| Input | Unit | Where it comes from |
| --- | --- | --- |
| Continuity resistance, insulation resistance, test voltage | ohm, Mohm, V | the records, `asbuilt/records.json`: `continuity_ohm`, `isolation_mohm`, `test_voltage_v` of the record of the test |
| Cut length, strip lengths | m, mm | the records: `cut_length_m`, `strip_a_mm`, `strip_b_mm` of the record of the wire |
| The limits and the test voltage | ohm, Mohm, V | `config/generation.json`: `test_continuity_max_ohm`, `test_isolation_min_mohm`, `test_isolation_voltage_v` |
| The designed length and strip lengths | m, mm | the design: the length of the wire (see [wire length](wire-length.md)) and `strip_a_mm`, `strip_b_mm` of the wire |
| The tolerance of a length (optional) | mm | `config/generation.json`: `asbuilt_cut_tolerance_mm`, `asbuilt_strip_tolerance_mm`; not set means no tolerance |

## The assumptions it rests on

- **The tests use the two assumptions of the test limits**, A-TEST-LIMITS (the limits are global numbers, they do not follow the length, gauge or part) and A-TEST-LIST (every wire and shield group is tested the same way).
- **A-ASBUILT-TOLERANCE.** A recorded length is judged against a tolerance only when the project sets one (`asbuilt_cut_tolerance_mm`, `asbuilt_strip_tolerance_mm`). Without one, no tolerance is applied and every difference is listed. With one, it is one number for every wire, in millimetres, the same on both sides of the designed length, and a distance equal to it is within. The tool supplies no value. What the tool asks of a harness that has records is described here and in [record what was built](../user-manual/record-what-was-built.md).
- A test is known by its number on the Tests sheet (`T001`) *and* by what it tests (its type and the wire column). If the design changes so that `T005` tests something else, the record of `T005` is shown as a stale record and the import of an old sheet refuses the row; the sheet is exported again.

## A worked example

`flatsat`, harness `W001`. The Tests sheet has `T001`, a continuity test of `W001-001` with the limit *1 ohm max*. A technician measures 0.4 ohm: `margin = 1 - 0.4 = 0.6 ohm`, *within limit*. Another test is recorded as 1.4 ohm: `margin = 1 - 1.4 = -0.4 ohm`, **out of limit**, and the report says so whatever result was written beside it. The designed length of `W001-001` is 3.45 m; a recorded cut length of 3.46 m gives `difference = 3.46 - 3.45 = 0.01 m`, listed as *differs from design (+10 mm; no tolerance applied)*.

With a cut tolerance of 10 mm (`asbuilt_cut_tolerance_mm` set to 10) the same 3.46 m is `distance = |3.46 - 3.45| = 0.01 m = 10 mm`, `margin = 10 - 10 = 0 mm`: *within limit* (a distance equal to the tolerance is within). A cut length of 3.50 m for `W001-002`, designed 3.45 m, is `distance = 50 mm`, `margin = 10 - 50 = -40 mm`: **out of limit**, "OUT OF TOLERANCE by 40 mm", and `asbuilt` ends with exit code 1 as for a test value out of its limit. `explain DIR W001-002` shows the same as a check: actual 50 mm, limit 10 mm, margin -40 mm, the key `config/generation.json: asbuilt_cut_tolerance_mm` as the source. A strip length has such a derivation (`Wire W001-001 strip A`) only when `asbuilt_strip_tolerance_mm` is set.

Repeat the calculation of one value with `harness-design-studio explain DIR W001.T001` (a test) or `harness-design-studio explain DIR W001-001` (a cut length), and list all of them with `harness-design-studio asbuilt DIR`.

## What happens when a value is missing

If a test has no measured value, the line says *missing* and the harness is *incomplete*. If the limit is not set in the project, a measured value is *not compared*, the derivation names `generation.test_continuity_max_ohm` (or the insulation key) as missing, and nothing is made up. A harness with no record at all is *not started*: nothing is missing from it.

## What the model does not do

- It does not say that a harness, a wire or a test passed, and it does not sign anything off. The report says in its first lines that it is not a sign-off.
- It applies no tolerance to a length unless the project sets one, and none to a voltage. It supplies no tolerance value.
- It does not accept an out-of-limit value. A deviation of the *design* can be accepted with the tool's own mechanism (`deviation`), with a reason; an as-built value that is out of its limit is not a finding of a design rule, and the way to record that it was looked at is a note and a non-conformance text in the record itself, kept in the journal with who wrote it and when.
- It does not read the numbers typed into the cells of the build workbook; the sheet to fill in is written by `export-asbuilt` and read back by `import-asbuilt`.

Next: [test limits](test-limits.md), [wire length](wire-length.md), [readiness](readiness.md), [the models](README.md), [record what was built](../user-manual/record-what-was-built.md)
