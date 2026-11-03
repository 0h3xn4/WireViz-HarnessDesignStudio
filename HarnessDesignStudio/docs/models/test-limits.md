# Test limits: where the numbers of the test sheet come from

This page explains the three numbers on the test sheet of a harness (and of the build workbook): the largest resistance of a continuity test, the smallest insulation resistance, and the insulation test voltage. It is written from what the program does, and the numbers come from the `flatsat` example, where you can repeat them with `harness-design-studio explain DIR W001` or `explain DIR W001.T001`.

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The rule](#the-rule)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

The test sheet lists tests. The tool decides which tests there are, and writes the three limits. It does not decide the limits: they are numbers of the project. `explain DIR HARNESS` gives one derivation (kind `test-limit`) for each limit, with the unit, the key it comes from, the tests that use it and the text as written on the sheet. `explain DIR HARNESS.T001` (the harness ID, a dot and the test number of the sheet) explains the limits one test uses.

## The rule

The sheet has, in this order: one **continuity** test for each wire (end to end, limit: the largest resistance), one **insulation** test for each wire against every other wire and shield (limit: the smallest resistance, at the test voltage), and one **insulation** test for each shield group against every wire. The tests are numbered `T001`, `T002`, and so on, in that order.

`limit = the value of generation.<key>`, the same for every test of that type in every harness.

## The inputs and where they come from

| Limit | Unit | Key | Used by |
| --- | --- | --- | --- |
| Largest continuity resistance | ohm | `config/generation.json: test_continuity_max_ohm` | every continuity test |
| Smallest insulation resistance | Mohm | `config/generation.json: test_isolation_min_mohm` | every insulation test |
| Insulation test voltage | V | `config/generation.json: test_isolation_voltage_v` | every insulation test |

The program ships no value (D-11): a project that has not set a key gets *TBD (placeholder)* on the sheet. While the file `generation.json` is marked as not reviewed, `explain` says that the number is a placeholder.

## The assumptions it rests on

- **A-TEST-LIMITS.** The three limits are global numbers: they do not follow the length, the gauge, the part or any standard, and the tool records no source for them.
- **A-TEST-LIST.** Every wire and every shield group is tested the same way; there is no sampling and no test of a pair of conductors against each other.

## A worked example

`harness-design-studio explain DIR W001.T001` on the `flatsat` example prints:

- **Largest continuity resistance: 1 ohm.** The test is `T001`, continuity, `W001-P2.1` to `W001-P11.1`. The number is `test_continuity_max_ohm` of `config/generation.json`, and 18 tests of the harness use it (`T001` to `T018`). On the sheet it reads *1 ohm max*.
- The insulation tests (`T019` and on) use 100 Mohm min at 500 V.

## What happens when a value is missing

If `test_continuity_max_ohm` is not set, the derivation has no value, names `generation.test_continuity_max_ohm` as missing, and says that the sheet shows *TBD (placeholder)* until it is set. The tool does not put a number in its place.

## What the model does not do

- It does not derive a limit from the wire, the length or a standard. Whether 1 ohm is the right limit for a wire is the project's decision.
- It does not read results back: the workbook is a document to write on, and the results typed into it are not read by the tool.
- It does not say that a harness has passed a test.

Next: [readiness](readiness.md), [the models](README.md), [the configuration](../CONFIG.md)
