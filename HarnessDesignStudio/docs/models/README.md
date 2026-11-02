# Models of the tool

This folder explains, for engineers, every calculation the tool makes: the equation, the inputs and where each comes from, the assumptions built into the program, what it is checked against, and a worked example you can repeat. It grows with the transparency work (decision D-191): a page is written for a model when its derivation is shown by the tool.

## Contents

- [How to use these pages](#how-to-use-these-pages)
- [The models](#the-models)
- [The assumptions built into the program](#the-assumptions-built-into-the-program)

## How to use these pages

Every page follows the same order: what the tool decides, the equation, the inputs (with unit and source), what it rests on, a worked example from a packaged project, and what the model does not do. The worked examples are real: the numbers were produced with `harness-design-studio explain` on the `flatsat` example, and the command prints the same derivation for your own wire.

## The models

| Page | What it covers | Shown by the tool as |
| --- | --- | --- |
| [Wire length](wire-length.md) | The length of a wire: the segments of its path, the service loops, or a length stored on the wire | `harness-design-studio explain DIR WIRE` |
| [Contact current](contact-current.md) | What the contacts of a connector may carry: the check of the rule `current-over-contact` | `harness-design-studio explain DIR INTERFACE.CONNECTOR` |
| [Bill of materials](bom.md) | Why a part has the quantity it has: connectors, contacts, wires in metres, accessories | `harness-design-studio explain DIR PART` |
| [Mass](mass.md) | The mass of a wire and of a harness: connectors, wires by part, the share of a multi-conductor part, the margin | `harness-design-studio explain DIR WIRE_OR_HARNESS` |
| [Wire sizing](wire-sizing.md) | The gauge of a wire: the current it may carry after derating, and its voltage drop | `harness-design-studio explain DIR WIRE` |

Still to come, in the order of the plan: the limits of the other design rules (the contact current is done), pin allocation and segmentation, the test limits and "Ready to build".

## The assumptions built into the program

Some of what a calculation rests on is not a number you type into `config/*.json` but a choice built into the program. Each has an ID, and a derivation names the ones it uses. Today they are: A-ROUND-TRIP, A-DC-SOLID, A-BUNDLE-ALL and A-PATH-UNIQUE, A-MASS-SCOPE, A-MASS-CONDUCTORS, A-BOM-CONTACTS, A-BOM-NO-ALLOWANCE and A-CONTACT-SHARED (built in), and A-TEMP-FACTOR, A-AMPACITY-AWG and A-SERVICE-LOOP (a value of the configuration, but one single number or table with no model behind it). They are described on the [wire sizing page](wire-sizing.md#the-assumptions-it-rests-on) and the [wire length page](wire-length.md#the-assumptions-it-rests-on) the [mass page](mass.md#the-assumptions-it-rests-on) the [bill of materials page](bom.md#the-assumptions-it-rests-on) and the [contact current page](contact-current.md#the-assumptions-it-rests-on). The aim of the work is that every built-in choice becomes a visible, documented setting; until then it is listed, not hidden.

Next: [contact current](contact-current.md), [bill of materials](bom.md), [mass](mass.md), [wire length](wire-length.md), [wire sizing](wire-sizing.md), [changes to results](../changes.md), [the configuration](../CONFIG.md)
