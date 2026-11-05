# Pin allocation and the choice of a connector

This page explains why a signal is on a pin of a device connector, and why a connector is the connector of an interface. It is written from what the program does (`core/generate/pins.py`, `core/checks.py`), and the examples come from the `flatsat` example, where you can repeat them with `harness-design-studio explain DIR MTQ1-J01.1` (a pin) and `explain DIR GPSU1-J01` (a connector).

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The order](#the-order)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [The choice of a connector](#the-choice-of-a-connector)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

When harnesses are generated, every signal of an interface gets a pin of the device connector at each end. `explain DIR CONNECTOR.PIN` (or the Why tab of a pin, a wire or an interface) gives a derivation of kind `pin-allocation` for the pin: what is on it and why, from the order of the categories, the gaps, the locks and the lines the generator recorded when it ran. The cable end of a connector has the same pin numbers, so asking for a pin of the cable connector explains the pin of the device connector it plugs into.

## The order

On one device connector the interfaces are placed in this order:

1. The categories listed in `model.pin_allocation_categories`, in the order listed (power, then ground, by default). They count as the *power group*: the signals of one interface are kept together as one block, with `power_return_gap_pins` unassigned contacts between them, and the first signal pin comes after `power_signal_gap_pins` free pins.
2. Every other category, by interface ID inside a category.

Inside that order each group of signals (a pair, a power block, a single signal) takes the **first free run of pins** in the order of the pin list, starting after the gap (this is the strategy `first_fit`; the setting `model.pin_fit_strategy` can choose `last_fit`, which fills from the last pin down, or `spread`, which leaves a free pin between interfaces, and `explain` names the one in force). A pair sits on neighbouring pins. Three things override the order:

- a pin that is **locked** is never moved, and a pin held by a released harness stays;
- a connector with a **fixed pinout** (the device design names every pin) gives each signal the free pin of its name;
- an earlier allocation is **kept** while it is still valid, so a small change makes a small difference.

## The inputs and where they come from

| Input | Source |
| --- | --- |
| The signal and interface on the pin | The device connector (the generated assignment, or a typed one). |
| The category of the interface | The interface type. |
| The order of the categories | `config/model.json: pin_allocation_categories` (default `power, ground`). |
| The pin fit strategy | `config/model.json: pin_fit_strategy` (default `first_fit`). |
| Pins between power and signal | `config/generation.json: power_signal_gap_pins` (0 is used, as a placeholder, while it is not set). |
| Contacts between power and return | `config/generation.json: power_return_gap_pins` (ECSS-Q-ST-30-11C requirement 0140052 is cited by ID). |
| Locked, fixed | The pin. |
| The lines recorded when it was generated | The Why tab (`core/why.py`): the derivation quotes them and does not repeat them. |

## The assumptions it rests on

- **A-PIN-ORDER.** The order of the categories and the gaps are settings.
- **A-PIN-FIRST-FIT.** First fit in the order of the pin list (the default of the setting `model.pin_fit_strategy`; `last_fit` and `spread` are the alternatives, see [selectable models](selectable-models.md#pin-fit-strategy)); an earlier choice is kept while it was made by the same strategy; locks and fixed pinouts win. Neighbours are neighbours in the list of pins, not a measured position.

## A worked example

`harness-design-studio explain DIR MTQ1-J01.1` on the `flatsat` example prints **PWR of IF-018 on pin 1**. The interface type `power_primary` has the category `power`, which is the first of the listed categories; the pin is the first of a block of two (PWR and RTN, *power and return grouped*); nothing lies ahead of it. The recorded line is *pin-allocation: PWR of IF-018 (power and return grouped)*. The gaps are 0 (`power_signal_gap_pins` is not set, a placeholder).

## The choice of a connector

A connector is chosen for an interface at a device by a person, or by the tool. When the tool chooses, it takes the **first free connector** of the device (in ID order) that carries the interface type, and the choice is marked *chosen by the tool, not confirmed* until a person confirms it (the finding `unconfirmed`). `explain DIR CONNECTOR` shows which connectors of the device carry the type and which was taken (kind `connector-choice`).

The **cable end** of a device connector is the part the library names as its mating part (`mates_with` of the device connector's part); a part with none is mated with itself, and generation says so. The gender is the opposite of the device connector's and the keying is copied. A cable connector that a person edited keeps its part, gender and keying.

- **A-CONNECTOR-CHOICE.** First free connector that carries the type; the cable end is the mating part.

## What happens when a value is missing

The gaps and the order always have a value (a default or a placeholder, named in the source of the input). A pin or connector that does not exist gives a derivation with no result that names it as missing.

## What the model does not do

- It does not replay the allocator. The pin is explained from what the generator left in the design and recorded, so a design edited by hand after generation is explained as it is now. A setting changed after generation changes the explanation of the order, not the pin, until the harnesses are generated again.
- It does not choose the connector part of a device: that is the device design or the library.
- It does not know the position of a pin on the connector face.

Next: [segmentation](segmentation.md), [the models](README.md), [what the tool assumes](../user-manual/see-what-the-tool-assumes.md)
