# Selectable models: choose how a number is made

Until version 1.12 some of the tool's calculations were fixed in the program. Each of them is now a **choice in `config/model.json`**, and the **default is exactly what the tool did before**, so a project that does not have the file gives the same numbers, byte for byte. This page lists the choices, the equation behind each, and what to expect when you change one. A choice that moves a result is shown by `explain`, which names the model in force.

## Contents

- [How to choose](#how-to-choose)
- [Every key of `model.json`](#every-key-of-modeljson)
- [Bundle basis](#bundle-basis)
- [Length model](#length-model)
- [Voltage drop model](#voltage-drop-model)
- [The return path](#the-return-path)
- [Mass model](#mass-model)
- [Pin allocation order](#pin-allocation-order)
- [Pin fit strategy](#pin-fit-strategy)
- [Connector choice](#connector-choice)
- [What makes a harness not ready to build](#what-makes-a-harness-not-ready-to-build)
- [What the choices do not do](#what-the-choices-do-not-do)

## How to choose

```
harness-design-studio settings DIR                                   # see what is in force
harness-design-studio settings DIR --set model.bundle_basis='"loaded_wires"'
harness-design-studio generate DIR                                   # apply it to the harnesses
```

A value outside the choices or the range is refused, and nothing is changed. The reference of every key is [`docs/CONFIG.md`](../CONFIG.md#modeljson). Generate again after a change of a model that shapes a harness (bundle basis, length, drop, pin order): the checks and the explanations follow at once, the harness files at the next generation.

## Every key of `model.json`

Every key of the file, its default (the number the tool has always used) and what it changes. The reference with the ranges is [`docs/CONFIG.md`](../CONFIG.md#modeljson); `harness-design-studio settings DIR` shows the value in force and where it comes from.

| Key | Default | What it changes | Assumption |
| --- | --- | --- | --- |
| `bundle_basis` | `all_wires` | which wires are counted for the bundle factor K | A-BUNDLE-ALL |
| `length_model` | `path_plus_loops` | how the length of a generated wire is made | A-SERVICE-LOOP |
| `service_loops_per_wire` | `2` | how many service loops are added to a generated wire (one at each end) | A-SERVICE-LOOP |
| `cut_allowance_m` | `0` | metres added to every generated wire by the model `path_loops_allowance_twist` | A-SERVICE-LOOP |
| `twist_takeup_fraction` | `0` | the extra length of a twisted construction, as a fraction, in the model `path_loops_allowance_twist` | A-SERVICE-LOOP |
| `drop_model` | `dc_solid` | the resistivity the voltage drop uses | A-DC-SOLID |
| `resistivity_temperature_coefficient` | `0.00393` | 1/K, for the model `dc_at_ambient` | A-DC-SOLID |
| `resistivity_reference_temperature_c` | `20` | degC, the temperature the resistivity is given for, for the model `dc_at_ambient` | A-DC-SOLID |
| `return_path_categories` | power, ground | the interface categories whose wires count the way out and the way back in the drop | A-ROUND-TRIP |
| `return_path_conductors` | `2` | the conductors counted for such a wire | A-ROUND-TRIP |
| `single_path_conductors` | `1` | the conductors counted for every other wire | A-ROUND-TRIP |
| `mass_model` | `connectors_and_wires` | what the mass counts | A-MASS-SCOPE |
| `pin_allocation_categories` | power, ground | the categories given pins first, in this order | A-PIN-ORDER |
| `pin_fit_strategy` | `first_fit` | which free run of pins a group of signals takes | A-PIN-FIRST-FIT |
| `connector_choice` | `first_free` | which free connector the tool takes for an interface | A-CONNECTOR-CHOICE |
| `readiness_blocking` | Wires without a length, Wires without a gauge, Wires without a colour, Wires without a part | the checks whose open items make *Ready to build* no | A-READY-CHECKS |

## Bundle basis

The factor K of `bundle_factor_by_count` (or `bundle_derating`) is looked up for a number of wires. `model.bundle_basis` says which wires are counted. Assumption A-BUNDLE-ALL.

| Value | The count is | Use when |
| --- | --- | --- |
| `all_wires` (default) | every wire of the harness | the conservative reading; wires are bundled along the whole harness |
| `loaded_wires` | only the wires that carry a current (an interface with a current, or a wire with one) | signal wires carry no meaningful heat |
| `busiest_segment` | the most wires in any routing segment of the wire's own path | the harness branches, and a branch holds few wires |

A generated harness routes every wire through the trunk, so `busiest_segment` gives the same count as `all_wires` there; it differs for a harness with branches that you drew by hand. The count is computed by one function (`core/generate/bundle.py`) that sizing, the rules `current-over-wire` and `bundle-current` and the explanation all call.

## Length model

`model.length_model`:

| Value | Length of a generated wire |
| --- | --- |
| `path_plus_loops` (default) | the sum of the segments of its path + `service_loops_per_wire` × `service_loop_m` |
| `path_loops_allowance_twist` | `(path + loops + cut_allowance_m) × (1 + twist_takeup_fraction)`, the take-up only for wires of a twisted construction |

A length typed on a wire is never changed by the model. `cut_allowance_m` and `twist_takeup_fraction` default to 0: choosing the model without setting them changes nothing, so the number you add is always yours. The number of loops is `service_loops_per_wire`: with 0 the `flatsat` wire `W001-001` is the path alone, 3.25 m, and with 3 it is 3.25 + 3 × 0.1 = 3.55 m (generate again after the change; `explain DIR W001-001` shows `3 × 0.1`). Which constructions are twisted is a definition, [`D-TWISTED`](definitions.md#d-twisted-which-constructions-are-twisted). Assumption A-SERVICE-LOOP; [wire length](wire-length.md).

## Voltage drop model

`model.drop_model`:

| Value | Resistivity used |
| --- | --- |
| `dc_solid` (default) | `generation.conductor_resistivity_ohm_m` as given |
| `dc_at_ambient` | `rho × (1 + alpha × (T − T_ref))` with `T` = `derating.max_ambient_temperature_c`, `alpha` = `resistivity_temperature_coefficient` (0.00393 1/K, annealed copper) and `T_ref` = `resistivity_reference_temperature_c` (20 degC) |

Both are DC drops of a solid round conductor (A-DC-SOLID); neither is an AC or skin-effect model. If `dc_at_ambient` is chosen and the ambient temperature is not set, the drop is *not checked* and the derivation says which value is missing. With the ambient temperature 60 degC and the defaults, the resistivity of the `flatsat` example grows by 1 + 0.00393 × (60 − 20) = 1.1572, and the drop of `W001-001` with it: 0.458359 V × 1.1572 = 0.530413 V. [Wire sizing](wire-sizing.md).

## The return path

`return_path_categories` (default power, ground) lists the interface categories whose wires are counted with their return in the voltage drop: the conductors counted are `return_path_conductors` (2, the way out and the way back, taken to have the same gauge and length). Every other category counts `single_path_conductors` (1). Assumption A-ROUND-TRIP. With `return_path_conductors` set to 1, the drop of the power wire `W001-001` is half of what it was, 0.229180 V instead of 0.458359 V, and `explain DIR W001-001` shows `Conductors counted n = 1` with the key as its source. A return of another gauge or length is not modelled. [Wire sizing](wire-sizing.md).

## Mass model

`model.mass_model`:

| Value | The mass counts |
| --- | --- |
| `connectors_and_wires` (default) | the connectors and the wires (A-MASS-SCOPE) |
| `full_bom` | those plus a contact part for every pin that has a wire and every accessory, each by the `mass_g` (or `mass_per_m_g` × length) of its part; a part without a mass is named as missing, never guessed |

[Mass](mass.md), [bill of materials](bom.md).

## Pin allocation order

`pin_allocation_categories` (default `power`, `ground`) lists the interface categories that are given pins first, in that order; every other category follows in its usual order. The categories listed also form the power group for `power_return_gap_pins`. Changing it moves signals to other pins, so it is a design decision, shown by `settings` and recorded with the harness.

## Pin fit strategy

`model.pin_fit_strategy` says which free run of pins a group of signals (a pair, a power block, a single signal) takes. The order of the categories (above) and the gaps `power_signal_gap_pins` and `power_return_gap_pins` stay as they are. Assumption A-PIN-FIRST-FIT.

| Value | A group takes | Use when |
| --- | --- | --- |
| `first_fit` (default) | the first free run of neighbouring pins from pin 1 up; the signals follow the power block after the gap | the usual reading; the connector fills from the first pin |
| `last_fit` | the last free run from the last pin down; power sits on the last pins and the signals below it, the gap between them; inside a group the pins still rise with the signal order | the free pins should stay at the start of the connector, for example for later additions at the front |
| `spread` | the first free run that has a free pin on each side of it, apart from the other pins of its own interface; when an interface does not fit that way it is placed by `first_fit` | a pin that is not used between two interfaces helps a bad contact, a probe or a later change |

A pin that is **locked** is never moved and never offered, a pin held by a released harness stays, a pair sits on neighbouring pins (a warning says when it cannot), and the `power_return_gap_pins` between the supply and return pin are kept by every strategy. On a connector with a **fixed pinout** the signal goes to the free pin of its name; `last_fit` takes the last such pin when a name occurs more than once, `spread` has nothing to spread. No pin ever carries two signals, and the result is the same every time.

Worked by hand on a connector of 12 pins with no gaps and three interfaces, a power interface (`PWR`, `RTN`) and two RS-422 interfaces `IF-A` and `IF-B` (the pairs `TX+ TX-` and `RX+ RX-`): `first_fit` gives power 1-2, `IF-A` 3-6, `IF-B` 7-10; `last_fit` gives power 11-12, `IF-A` 9-10 and 7-8, `IF-B` 5-6 and 3-4; `spread` gives power 1-2, a free pin 3, `IF-A` 4-7, a free pin 8, `IF-B` 9-12. A change of the strategy re-places the pins at the next generation (an earlier allocation is kept only while it was made by the same strategy), and `explain DIR CONNECTOR.PIN` names the strategy in force and its rule; for the default it keeps its text.

## Connector choice

When an interface is made without naming the connector at a device (the editor's Connect, an import, *Choose connectors automatically*), the tool chooses one and marks it *chosen by the tool, not confirmed*. `model.connector_choice` says which. The candidates are always the same: the connectors of the device that carry the interface type and that no interface ends on yet; a connector that is used, does not carry the type, or belongs to another device is never chosen. A connector a person picked is never changed. Assumption A-CONNECTOR-CHOICE.

| Value | The connector chosen | Use when |
| --- | --- | --- |
| `first_free` (default) | the first candidate in ID order | the devices have one connector per interface type |
| `fewest_spare_pins` | the candidate with the fewest pins left over once the interface is on it (best fit): pins available minus signals of the type, among the candidates with enough pins; ties by ID. Candidates with too few pins follow in ID order | a device has connectors of several sizes and the large ones should be kept for large interfaces |
| `most_spare_pins` | the candidate with the most pins left over; ties by ID | the small connectors should be kept for later, or room is wanted for added signals |

The pins *available* are the pins that are not locked and have no signal typed in by a person (a pin that carries a generated assignment counts, because generation rewrites it); on a connector with a fixed pinout they are the named, unlocked pins, and the interface fits when every signal of the type has a named pin. A hand count: an OBC with free connectors of 3, 9, 15, 4 and 15 pins and an interface of 4 signals has 3 pins too few on the first, then 5, 11, 0 and 11 pins left over; `first_free` takes the 3-pin connector (as it always did, and the pin allocation then reports too few pins), `fewest_spare_pins` the 4-pin connector, `most_spare_pins` the first of the two 15-pin connectors. `explain DIR CONNECTOR` shows the model in force and the candidates in its order with the numbers it chose from; for the default it keeps its text. Changing the model does not move a connector that is already chosen.

## What makes a harness not ready to build

`readiness_blocking` is the list of checks of the build workbook whose open items turn *Ready to build* into **no**. The default is the first four (length, gauge, colour, part); the others (termination, strip length, contact part, approval) are notes. Add a name to make a check blocking, or remove one to make it a note. A name that is not a check of the workbook is refused. The same list decides the verdict of the release check.

## What the choices do not do

- They do not change the rule limits: `current-over-wire` still compares the current with the ampacity table times K times the temperature factor; only K's count changes.
- They do not make a model right for your programme. A default is **the number the tool has always used**, not a number a standard asked for; choosing is your engineering decision.
- They add no new design rule.

Next: [wire sizing](wire-sizing.md), [wire length](wire-length.md), [mass](mass.md), [see what the tool assumes](../user-manual/see-what-the-tool-assumes.md), [the configuration](../CONFIG.md#modeljson)
