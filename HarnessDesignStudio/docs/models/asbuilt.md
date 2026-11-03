# As-built results: how a recorded value is compared

This page explains how the tool compares what a technician recorded with what was designed and with the test limits of the project: the measured resistances of the tests, the cut lengths and the strip lengths. It is written from what the program does, and the numbers come from the `flatsat` example, where you can repeat them with `harness-design-studio asbuilt DIR` and `harness-design-studio explain DIR W001.T001`.

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

**A cut length** (`cut_length_m`) and the strip lengths (`strip_a_mm`, `strip_b_mm`) are compared with the designed value: `difference = recorded - designed`. A difference smaller than 1e-9 is *as designed*; any other difference is listed as *differs from design* with its size. **The tool applies no tolerance**, because it has none (D-11: it ships no value for what an engineer decides): a cut length that is a few millimetres long or short is listed, and whether that is acceptable is for a person.

**The result a technician wrote** (`pass` or `fail`) is kept as written. A result `fail` is shown as out of limit. A result `pass` with a measured value that is out of its limit is shown as out of limit with the note *recorded as passed: the tool does not accept it*. The tool never changes a recorded value and never turns an out-of-limit value into a pass.

## The inputs and where they come from

| Input | Unit | Where it comes from |
| --- | --- | --- |
| Continuity resistance, insulation resistance, test voltage | ohm, Mohm, V | the records, `asbuilt/records.json`: `continuity_ohm`, `isolation_mohm`, `test_voltage_v` of the record of the test |
| Cut length, strip lengths | m, mm | the records: `cut_length_m`, `strip_a_mm`, `strip_b_mm` of the record of the wire |
| The limits and the test voltage | ohm, Mohm, V | `config/generation.json`: `test_continuity_max_ohm`, `test_isolation_min_mohm`, `test_isolation_voltage_v` |
| The designed length and strip lengths | m, mm | the design: the length of the wire (see [wire length](wire-length.md)) and `strip_a_mm`, `strip_b_mm` of the wire |

## The assumptions it rests on

- **No new assumption ID.** The comparison uses the two assumptions of the test limits, A-TEST-LIMITS (the limits are global numbers, they do not follow the length, gauge or part) and A-TEST-LIST (every wire and shield group is tested the same way), and adds none of its own. What the tool asks of a harness that has records, and the fact that it applies no tolerance to a length, are described here and in [record what was built](../user-manual/record-what-was-built.md).
- A test is known by its number on the Tests sheet (`T001`) *and* by what it tests (its type and the wire column). If the design changes so that `T005` tests something else, the record of `T005` is shown as a stale record and the import of an old sheet refuses the row; the sheet is exported again.

## A worked example

`flatsat`, harness `W001`. The Tests sheet has `T001`, a continuity test of `W001-001` with the limit *1 ohm max*. A technician measures 0.4 ohm: `margin = 1 - 0.4 = 0.6 ohm`, *within limit*. Another test is recorded as 1.4 ohm: `margin = 1 - 1.4 = -0.4 ohm`, **out of limit**, and the report says so whatever result was written beside it. The designed length of `W001-001` is 3.45 m; a recorded cut length of 3.46 m gives `difference = 3.46 - 3.45 = 0.01 m`, listed as *differs from design (+10 mm; no tolerance applied)*.

## What happens when a value is missing

If a test has no measured value, the line says *missing* and the harness is *incomplete*. If the limit is not set in the project, a measured value is *not compared*, the derivation names `generation.test_continuity_max_ohm` (or the insulation key) as missing, and nothing is made up. A harness with no record at all is *not started*: nothing is missing from it.

## What the model does not do

- It does not say that a harness, a wire or a test passed, and it does not sign anything off. The report says in its first lines that it is not a sign-off.
- It does not apply a tolerance to a length, a strip length or a voltage.
- It does not accept an out-of-limit value. A deviation of the *design* can be accepted with the tool's own mechanism (`deviation`), with a reason; an as-built value that is out of its limit is not a finding of a design rule, and the way to record that it was looked at is a note and a non-conformance text in the record itself, kept in the journal with who wrote it and when.
- It does not read the numbers typed into the cells of the build workbook; the sheet to fill in is written by `export-asbuilt` and read back by `import-asbuilt`.

Next: [test limits](test-limits.md), [wire length](wire-length.md), [readiness](readiness.md), [the models](README.md), [record what was built](../user-manual/record-what-was-built.md)
