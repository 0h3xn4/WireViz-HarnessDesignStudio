# The limit of every design rule

This page explains, for each design rule, what it compares and, when the comparison is a number against a limit, how the limit is derived. The Explain button of the Checks tab, the Why tab and `harness-design-studio explain` show the same derivation for the object of a finding. It is written from what the program does (`core/derive_rules.py` calls the functions the rules call), and the numbers come from the `flatsat` example. The findings themselves, and every written file, are unchanged.

## Contents

- [What the tool decides](#what-the-tool-decides)
- [Rules with a limit](#rules-with-a-limit)
- [Rules that are yes/no checks](#rules-that-are-yesno-checks)
- [Every rule](#every-rule)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

A design rule either compares a **number** with a limit (the current of a wire with the current its gauge may carry) or checks a **yes/no** condition (two connectors that do not fit). For every rule of the registry, the independent verification and the logical rules of the Problems panel, `explain_finding(rule, object)` gives a derivation. The Explain button of the Checks tab is there for every rule that has findings, and a test walks the whole registry and fails for a rule that has no explanation.

## Rules with a limit

The derivation (kind `rule-limit`) carries the equation, the inputs with unit and source, the steps and the **check**: the actual value, the limit, the margin (room left; for a minimum, what the value has over it) and the verdict. The verdict is the verdict of the rule: a finding exists exactly when the check fails (the comparison is the one the rules and the sizing share, so a value at its limit passes). The three rules that were explained first keep a kind of their own: `current-over-wire` and `voltage-drop` ([wire sizing](wire-sizing.md)), and `current-over-contact` ([contact current](contact-current.md)).

| Rule | Equation | Object of the finding | Settings and values |
| --- | --- | --- | --- |
| `spare-pins-low` | spare pins ≥ required share × pins of the connector | the device connector | `derating.spare_pin_fraction` |
| `connector-voltage` | working voltage ≤ the lower of (share of the withstanding voltage × withstanding voltage) and (share of the rated voltage × rated voltage) | `INTERFACE.CONNECTOR` | `derating.connector_voltage_factor_withstand`, `connector_voltage_factor_rated`; ratings `dielectric_withstand_v`, `rated_voltage_v` of the part |
| `wire-voltage` | working voltage ≤ share of the rated voltage × rated voltage | the wire | `derating.wire_voltage_factor`; rating `rated_voltage_v` of the wire part; assumption A-WIRE-VOLTAGE |
| `temperature-margin` | hottest ambient temperature ≤ maximum temperature of the part − margin | the connector or the wire | `derating.max_ambient_temperature_c`, `connector_temperature_margin_c`, `wire_temperature_margin_c`; rating `max_temp_c` |
| `mating-cycles` | rated mating cycles ≥ cycles the programme may use | `mating-cycles.PART` | `derating.max_mating_cycles`; rating `mating_cycles` |
| `power-return-adjacent` | unassigned contacts between the two pins ≥ contacts required | `CONNECTOR.PIN+PIN` | `generation.power_return_gap_pins` |
| `bundle-current` | current ≤ base ampacity × bundle factor K × temperature factor (1 when not set) | the wire | `derating.ampacity_a_by_awg`, `bundle_factor_by_count`, `temperature_derating`; `model.bundle_basis` |
| `pin-shared` | wires on a pin ≤ 1 | the harness | none: one wire to a pin is the limit of the rule; assumption A-PIN-ONE-WIRE (built in) |
| `emc-class-split` | bundles that carry one EMC class between two devices ≤ 1 | `emc-class.CLASS.UNIT.UNIT` | `emc.same_class_one_bundle`; none for the limit of one; assumption A-EMC-ONE-BUNDLE |

## Rules that are yes/no checks

A rule with no numeric limit says so: the derivation (kind `rule-check`) has the equation *this rule is a yes/no check: it compares X with Y*, the statement of the finding for the object, the configuration the rule reads with the values in force (or *not set: the rule is silent until it is*), what the rule saw at the object where that is cheap to show (the ends of a shield, the gender and part of two connectors, the approval of a part, the interfaces of a harness with their chain, category and class), the assumptions it rests on, and the *why it matters*, *how to fix it* and requirement IDs of the rule. The requirement IDs are cited by ID; the tool shows no text of a standard.

## Every rule

The table is written from the code (`python -m tools.gen_rule_limit_docs`), so a rule cannot be left out of it.

<!-- rule-table:start (python -m tools.gen_rule_limit_docs) -->

| Rule | Form | What it compares | Derivation |
| --- | --- | --- | --- |
| `duplicate-id` | yes/no check | how many times each connector, wire and pin ID is used with once | `rule-check` |
| `wire-dangling` | yes/no check | the connector and pin each wire end names with the connectors and pins the harness has | `rule-check` |
| `model-inconsistent` | yes/no check | the logical model (devices, interfaces, connectors) with the physical one (harnesses, wires, pins) for the mismatches the integrity check lists | `rule-check` |
| `segment-loop` | yes/no check | the routing segments of a harness with a tree: a loop gives a wire two possible routes | `rule-check` |
| `signal-unassigned` | yes/no check | each signal of an interface type with the pins of the connector at each end that carry it | `rule-check` |
| `pin-floating` | yes/no check | each pin that is named with a signal with the wires attached to it | `rule-check` |
| `pin-shared` | number against a limit | the number of wires on a pin with one | `rule-limit` |
| `mate-mismatch` | yes/no check | a cable connector with the device connector it plugs into: gender, mating part, number of pins and keying | `rule-check` |
| `direction-conflict` | yes/no check | the directions of the two signals a wire joins: two outputs or two inputs conflict | `rule-check` |
| `current-over-contact` | number against a limit | the current of an interface with the derated rating of the contacts of the connector at its end | `contact-current` |
| `current-over-wire` | number against a limit | the current of an interface with the derated ampacity of the wire's gauge | `wire-current-limit` |
| `voltage-drop` | number against a limit | the voltage drop over a wire at the current of its interface with the largest drop allowed | `wire-voltage-drop` |
| `spare-pins-low` | number against a limit | the number of spare pins of a connector with the required share of its pins | `rule-limit` |
| `shield-unterminated` | yes/no check | the two ends of each shield group with 'floating': both floating is not terminated | `rule-check` |
| `shield-wrong-end` | yes/no check | the ends of each shield group with the grounding concept of the project | `rule-check` |
| `chains-mixed` | yes/no check | the redundancy (nominal or redundant) of the interfaces in each harness and on each connector | `rule-check` |
| `pyro-mixed` | yes/no check | the categories of the interfaces in each harness and on each connector with 'pyro' | `rule-check` |
| `category-mixed` | yes/no check | the interface categories in a harness with the pairs the project keeps apart | `rule-check` |
| `emc-mixed` | yes/no check | the EMC classes in a harness with the pairs of classes that must stay apart | `rule-check` |
| `connector-lookalike` | yes/no check | the connectors of one device that are in use, by part, keying, gender and number of pins: identical ones can be mixed up | `rule-check` |
| `part-unapproved` | yes/no check | the approval of each part in use with 'approved', and whether it is marked as unverified example data | `rule-check` |
| `connector-voltage` | number against a limit | the working voltage of an interface with the lower of the shares of the withstanding and the rated voltage of the connector part | `rule-limit` |
| `wire-voltage` | number against a limit | the working voltage of an interface with the share of the rated voltage of the wire part | `rule-limit` |
| `temperature-margin` | number against a limit | the hottest ambient temperature with the maximum temperature of the part less the margin | `rule-limit` |
| `mating-cycles` | number against a limit | the rated mating cycles of a connector part with the cycles the programme may use | `rule-limit` |
| `connector-manufacturer` | yes/no check | the manufacturer of a cable connector's part with that of the device connector it mates with | `rule-check` |
| `wire-specification` | yes/no check | each approved wire part with its specification field: an empty field is a finding | `rule-check` |
| `shield-bonding` | yes/no check | the ends of each shield group with 'backshell_360' at both ends, when the project requires bonding | `rule-check` |
| `shield-parts` | yes/no check | the conductive finish of the connectors and the insulating sheath of the shielded wires with 'none' (rating 0) | `rule-check` |
| `emc-class-split` | number against a limit | the number of harnesses that carry one EMC class between two devices with one | `rule-limit` |
| `power-return-adjacent` | number against a limit | the unassigned contacts between a power and a return pin with the contacts required | `rule-limit` |
| `bundle-current` | number against a limit | the current of an interface with the derated ampacity of the wire's gauge in a bundle of its size | `rule-limit` |
| `link-unpaired` | yes/no check | each pin of a connection that has a signal with the pairs of that connection | `rule-check` |
| `link-direction` | yes/no check | the directions of the two pins of each pair of a connection | `rule-check` |
| `link-signal-mismatch` | yes/no check | the two signal names of each pair of a connection | `rule-check` |
| `link-power-return` | yes/no check | each power pair of a connection with a return pair on the same connection | `rule-check` |
| `config-invalid` | yes/no check | each value in config/*.json with the range it must lie in (the checks of configcheck) | `rule-check` |
| `released-modified` | yes/no check | each released harness with the baseline it was released as (its content hash) | `rule-check` |
| `unchecked-config` | yes/no check | the values and ratings each rule needs with what the project has set; it lists what could not be checked | `rule-check` |
| `verify-mismatch` | yes/no check | the wires and tables with what the interfaces require, worked out again by the independent check (core/verify) | `rule-check` |
| `cross-strap` | yes/no check | the side (nominal or redundant) of the two devices of an interface | `rule-check` |
| `no-connector` | yes/no check | each end of an interface with a chosen connector | `rule-check` |
| `unconfirmed` | yes/no check | the connector of each end of an interface with 'chosen by a person' (a tool choice is not confirmed) | `rule-check` |
| `isolated` | yes/no check | each device with the interfaces and connections that join it to another | `rule-check` |

<!-- rule-table:end -->

## The assumptions it rests on

- **A-SPARE-PINS.** A pin is spare when it has no interface and no signal; the fraction is not rounded.
- **A-CONNECTOR-VOLTAGE.** The limit is the lower of the limits that can be worked out.
- **A-AMBIENT-ONLY.** One ambient temperature, no self-heating of the conductor.
- **A-MATING-REQUIRED.** The cycles are a number the programme may use, not a count of matings.
- **A-RETURN-GAP.** Contacts between power and return are counted in the list of pins.
- **A-BUNDLE-CURRENT.** `bundle-current` uses the wire limit, needs the table of bundle factors, and counts an unset temperature factor as 1. Stays built in: counting an unset temperature factor as 1 is how the rule treats a missing value, and making it a number would let a missing value look like an engineering choice.
- **A-WIRE-VOLTAGE** (a setting). `wire-voltage` compares the working voltage of the interface with the share `derating.wire_voltage_factor` of the rated voltage of the wire part: one share for every wire, the rating of the part and not of this insulation.
- **A-PIN-ONE-WIRE** (built in). `pin-shared` allows one wire to a pin whatever the contact could hold; it is a statement about the method and not a number, so it is not a setting. A design that needs two wires in one contact waives the finding with a reason.
- **A-EMC-ONE-BUNDLE** (a setting). `emc-class-split` allows one bundle for one EMC class between two devices, the reading of ECSS-E-ST-20-07C 4.2.13.1 b built into the rule; only `emc.same_class_one_bundle`, which switches the rule on, is a setting.
- The assumptions of the first three rules (A-CONTACT-SHARED, A-AMPACITY-AWG, A-BUNDLE-ALL, A-TEMP-FACTOR, A-DC-SOLID, A-ROUND-TRIP) are on the pages of [contact current](contact-current.md) and [wire sizing](wire-sizing.md); those of the yes/no rules that depend on a built-in choice are on [segmentation](segmentation.md), [pin allocation](pin-allocation.md) and [shields](shields.md).

## A worked example

With `derating.spare_pin_fraction` set to 0.6, `harness-design-studio explain DIR OBC1-J13` on the `flatsat` example prints **Spare pins required: 4.8 pins**: the connector has 8 pins, so 0.6 × 8 = 4.8, and it has 4 spare pins, *short by 0.8 pins*. The finding says *OBC1-J13 has 4 spare pin(s) of 8, fewer than the required 60%*; the derivation carries the number the finding rounds away.

With the shares 0.25 of the withstanding voltage and 0.75 of the rated voltage (values of the project) and a part rated 200 V withstanding and 100 V rated, the limit is the lower of 50 V and 75 V: **50 V**, and an interface that works at 60 V is *over the limit by 10 V*.

## What happens when a value is missing

A limit that cannot be worked out has no value and names what is missing: the setting, or the rating of the part. A rule that is silent until a value is set (`pending`) stays silent; the Checks tab says which value it waits for. An object that does not exist gives no derivation.

## What the model does not do

- It does not change a finding or its verdict: the derivation reads the same functions the rule calls, and a test compares the two for every object.
- It does not say that a design complies with a requirement. A passing check is a comparison of two numbers of the project.
- It does not supply a value for a limit nobody set: the tool ships no derating, EMC or voltage values (D-11).

Next: [contact current](contact-current.md), [wire sizing](wire-sizing.md), [the models](README.md), [the design rules](../RULES.md)
