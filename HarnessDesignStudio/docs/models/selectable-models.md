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
- [What makes a harness not ready to build](#what-makes-a-harness-not-ready-to-build)
- [Allowance and spares in the bill of materials](#allowance-and-spares-in-the-bill-of-materials)
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
| `readiness_blocking` | Wires without a length, Wires without a gauge, Wires without a colour, Wires without a part | the checks whose open items make *Ready to build* no | A-READY-CHECKS |
| `bom_wire_allowance_fraction` | `0` | the fraction of the wire metres added to a wire part in the bill of materials | A-BOM-NO-ALLOWANCE |
| `bom_contact_spare_fraction` | `0` | the fraction of the contacts used added as spares, for each harness and contact part, rounded up | A-BOM-CONTACTS |

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

## What makes a harness not ready to build

`readiness_blocking` is the list of checks of the build workbook whose open items turn *Ready to build* into **no**. The default is the first four (length, gauge, colour, part); the others (termination, strip length, contact part, approval) are notes. Add a name to make a check blocking, or remove one to make it a note. A name that is not a check of the workbook is refused. The same list decides the verdict of the release check.

## Allowance and spares in the bill of materials

The bill of materials counts what is drawn (A-BOM-NO-ALLOWANCE, A-BOM-CONTACTS), and both numbers below are 0 until you set them, so a project without them gets the quantities it always got.

| Key | Adds | Example |
| --- | --- | --- |
| `bom_wire_allowance_fraction` | that fraction of the wire metres of every wire part, as a line of kind *wire allowance* for each wire | in the `flatsat` example `EX-WIRE-SINGLE` is 165.2 m; with 0.1 it is 165.2 + 16.52 = 181.72 m, and `explain DIR EX-WIRE-SINGLE` shows the allowance and the fraction as an input |
| `bom_contact_spare_fraction` | for each harness and contact part, that fraction of the contacts used, rounded up to a whole contact, as a line of kind *contact spare* | a harness that uses 9 contacts of a part, with 0.25: 9 × 0.25 = 2.25, rounded up to 3 spares for that harness; each harness is rounded on its own |

The allowance applies to the metres of wire parts only: a connector part, an accessory part and a length in the drawings or the wire list never get one, and the mass, the cut lengths and the test sheet do not change (the mass model `full_bom` counts what is drawn, not what is ordered). The allowance is a fraction of the metres counted for the part (for a twisted pair part those are already divided by its conductors). A wire with no length adds neither metres nor allowance.

## What the choices do not do

- They do not change the rule limits: `current-over-wire` still compares the current with the ampacity table times K times the temperature factor; only K's count changes.
- They do not make a model right for your programme. A default is **the number the tool has always used**, not a number a standard asked for; choosing is your engineering decision.
- They add no new design rule.

Next: [wire sizing](wire-sizing.md), [wire length](wire-length.md), [mass](mass.md), [see what the tool assumes](../user-manual/see-what-the-tool-assumes.md), [the configuration](../CONFIG.md#modeljson)
