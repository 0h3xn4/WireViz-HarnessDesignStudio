# Segmentation: why a wire is in this harness

This page explains why the interfaces of a project end up in the harnesses they are in. It is written from what the program does (`core/generate/segmentation.py`), and the examples come from the `flatsat` example, where you can repeat them with `harness-design-studio explain DIR W005` (a harness) or `explain DIR IF-001` (an interface).

## Contents

- [What the tool decides](#what-the-tool-decides)
- [The rule](#the-rule)
- [The inputs and where they come from](#the-inputs-and-where-they-come-from)
- [The assumptions it rests on](#the-assumptions-it-rests-on)
- [A worked example](#a-worked-example)
- [What happens when a value is missing](#what-happens-when-a-value-is-missing)
- [What the model does not do](#what-the-model-does-not-do)

## What the tool decides

Generation puts every interface that has two devices, two connectors and a type into exactly one harness; interfaces that share a **group key** share the harness. `explain DIR HARNESS` gives a derivation of kind `segmentation`: the mode, the settings that keep things apart, the key, each interface of the harness with its devices, zones, chain and class, and the line the generator recorded. `explain DIR INTERFACE` says which harness carries the interface and why, or, when none does, the reason the interface was skipped (no connector on one end, a device that does not exist, more than two devices...).

## The rule

The key depends on `segmentation.mode`:

| Mode | Interfaces share a harness when they have the same |
| --- | --- |
| `per_connector_pair` (default) | pair of device connectors, and chain |
| `per_unit_pair` | pair of devices, chain and class |
| `per_zone_pair` | pair of zones, chain and class |

- The **chain** is the redundancy (nominal or redundant) of the interface. With `segregation.forbid_nominal_with_redundant` on (the default) the two chains never share a harness.
- The **class** is `pyro` for a pyro interface (while `forbid_pyro_with_other` is on), otherwise the class of its category in `segregation.category_pairs_to_separate` (categories that must stay apart get different classes), otherwise `main`. In `per_connector_pair` mode the connector decides and the class is not part of the key; the tool notes it when one harness mixes classes.
- The **zone** of a device is the field *Zone* of the device. A device with no zone is in the zone *no zone*.

## The inputs and where they come from

| Input | Source |
| --- | --- |
| Mode | `config/segmentation.json: mode` |
| Keep chains apart, keep pyro apart | `config/segregation.json: forbid_nominal_with_redundant`, `forbid_pyro_with_other` (default yes) |
| Category pairs kept apart | `config/segregation.json: category_pairs_to_separate` |
| Devices, zones, connectors, chain | The design. |

## The assumptions it rests on

- **A-SEGMENT-MODE.** The mode decides which interfaces share a harness; the segregation settings keep chains, pyro lines and listed categories apart.
- **A-ZONE.** The zone of a device is a field of the device. Dragging a device box into another zone in the block diagram rewrites that field (the editor says so in a message), and the grouping per zone pair changes with it. Stays built in: it states where the zone is kept (a field of the device); how the zones group the harnesses is the setting `segmentation.mode`.

## A worked example

`harness-design-studio explain DIR IF-001` on the `flatsat` example (mode `per_zone_pair`) prints that `IF-001` is in harness `W005`: *3 interfaces share it: bus to egse*. The key is `zp|nominal|main|bus|egse`: the chain is nominal, the class is main, and the zones are `bus` (`PCDU1`) and `egse` (`GPSU1`). The other two interfaces of `W005` are `IF-022` and `IF-025`, which also connect a device in `bus` with a device in `egse`.

## What happens when a value is missing

A mode that is not one of the three is not used: the default is, and the derivation says so. A harness that no group of the current design matches (the design changed since it was generated) is reported as *generate the harnesses again*. A harness drawn by hand has no segmentation rule.

## What the model does not do

- It does not decide where a harness is routed or how long it is.
- It does not merge two groups by itself: a project that wants fewer harnesses chooses a coarser mode.
- It does not segment by geometry: zones are names typed by people.

Next: [pin allocation](pin-allocation.md), [wire length](wire-length.md), [the models](README.md)
