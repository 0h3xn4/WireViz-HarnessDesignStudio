# Concepts: how the tool thinks

Read this once, in ten minutes, and the rest of the documentation will make sense. No spacecraft or harness knowledge is needed beyond what the words mean.

## Contents

- [The idea in one picture](#the-idea-in-one-picture)
- [The things in a design](#the-things-in-a-design)
- [The standards the tool starts from](#the-standards-the-tool-starts-from)
- [Guided and Expert](#guided-and-expert)
- [From design to harness: generation](#from-design-to-harness-generation)
- [Problems, rules and waivers](#problems-rules-and-waivers)
- [Placeholders: what the tool does not know](#placeholders-what-the-tool-does-not-know)
- [Review, release, revision](#review-release-revision)
- [Outputs](#outputs)
- [What is on disk](#what-is-on-disk)
- [What the tool does not do](#what-the-tool-does-not-do)
- [Words you will meet](#words-you-will-meet)

## The idea in one picture

```
 YOU DRAW                      THE TOOL MAKES                    THE TOOL WRITES
 ────────                      ──────────────                    ───────────────
 units                         harnesses                         build workbook (xlsx)
 interfaces between them  ──►  connectors, pins, wires    ──►    wire lists, pinouts, BOM
 (and some engineering         (with a reason for each           test tables, labels
  values you decide)            choice)                          block diagram, change log

       ▲                              │                                  │
       │                              ▼                                  ▼
       └──────────  checks: "problems" and design rules  ◄──────────  verified before writing
```

**Your design is the source of truth.** You describe *what must be connected*. The tool works out *how* (which connector, which pin, which wire) and writes everything down. Change the design, generate again, and every drawing and list follows. Generated results are not edited as drawings; what you want to keep (a wire's gauge, colour or length, a wire you draw yourself, a label, a pin's function) is set in the app and stays when you generate again, so nothing can drift apart.

## The things in a design

| Word | What it is | Example |
| --- | --- | --- |
| **Unit** | A box in the spacecraft with connectors on it. | `OBC1` (on-board computer), `PCDU1` (power unit), `RW1` (reaction wheel) |
| **Interface type** | A kind of connection and its signals. The tool ships 17 (RS-422, RS-485, CAN, Ethernet, primary power, ...). | *RS-422* has the signals `TX+`, `TX-`, `RX+`, `RX-` |
| **Interface** | One connection of a type between two units. This is what *you* add. | `IF-002`: RS-422 from `OBC1` to `RW1` |
| **Connector** | A plug or socket, which may carry a label (new in 1.4.0). On a unit it is a *box connector*; on a harness it is a *cable connector* that mates with a box connector. | `RW1-J02` on the wheel; `W001-P2` on the cable |
| **Pin** | One contact of a connector. It carries one signal and may have a *function* (free text, new in 1.4.0). | pin 3 of `RW1-J02` carries `RX+`, function "Wheel command receive" |
| **Harness** | A bundle of wires with its connectors that carries interfaces between units. **Generated** from interfaces, or made by hand with *New harness* (new in 1.5.0); individual wires can be edited, and wires can be added by hand (new in 1.4.0). | `W001`: `OBC1-J01` to `RW1-J02` |
| **Wire** | One conductor between two pins, with a gauge, a part and a length, and optionally a colour, a label, a note and the strip length at each end (new in 1.7.0). Two wires may share a pin. | `W001-001`: `TX+`, pin 1 to pin 3 |
| **Accessory** | Something on a harness besides its wires and connectors: sleeving, heat shrink, a label, a backshell. It says what it goes on, where (in words), how long and how many (new in 1.7.0). | `ACC-001`: sleeving on `W001-001` |
| **Segment** | A stretch of the physical route a bundle follows; wire lengths are sums of segments. | `W001-L1` |
| **Zone** | A lane of the diagram (a panel or compartment). Units sit in zones. | `panel-A`, `panel-B` |
| **Nominal / redundant** | The main chain of units and its backup. They never share a connector or harness. | `PCDU1` and `PCDU1-R` |

## The standards the tool starts from

The starter library and the units you add follow one baseline (D-130):

| For | Baseline | Notes |
| --- | --- | --- |
| Communication | **RS-422, RS-485, CAN** | what the starter units carry |
| High data rates (for example a payload) | **Ethernet** | an alternative to the three above, on an RJ45 connector |
| Power and data connectors | **Micro-D 9, 15, 21, 25 and 31 pin** | power: 9 pin. For data the size follows how many interface types the connector carries: 1 type 9, 2 types 15, 3 types 21, 4 types 25, more 31 |
| RF | **SMA** | one connector per RF link |

Other interface types (SpaceWire, MIL-STD-1553B, LVDS, I2C, analog, discrete, pyro ...) and older connector parts (D-sub, MDM, circular, TNC) stay in the library for projects that need them. All parts are **examples** with fictional part numbers, none approved: your approved parts list ([`IMPORTS.md`](IMPORTS.md)) replaces them. Unit connectors are female and the cable connector is the male half that mates with it.

## Guided and Expert

- **Guided** (the default): you work with units and interfaces only. The tool chooses connectors and pins and marks its choices *auto-filled* until a person confirms them.
- **Expert**: you also see every connector and can choose the exact one for each end.

Switching never changes data. Start in Guided.

## From design to harness: generation

Pressing **Generate** (or `harness-design-studio generate DIR`) does four things:

1. **Groups** the interfaces into harnesses. By default one harness per pair of unit connectors.
2. **Allocates pins**: power first, pairs side by side, spare pins left free, pins you locked never moved.
3. **Makes wires** for every signal, picks a part and, when it has the numbers, a gauge.
4. **Checks itself** with a separate verifier that does not share code with the generator.

You always see a **preview** first; nothing changes until you **Apply**, and **Undo** takes it back. Generating again keeps IDs, locked choices, the wires you edited or drew, and your labels, and never touches a released harness. The same design always gives byte-identical results, so Git diffs show real changes only.

Every choice has a reason. Open the **Harness** tab (the Drawings area), pick a harness, select a wire, connector or pin, and read the rule behind it in **Why** (gauge and length included).

## Problems, rules and waivers

The tool checks your design all the time, in two layers:

- **Quick checks** run instantly on every edit (an interface with no connector, an isolated unit, ...).
- **Design rules** (35 of them, listed in [`RULES.md`](RULES.md)) run in the background a moment after you stop editing: connector look-alikes, unapproved parts, pin reuse, separation, current limits, and more.

Each finding is an **error** (must be fixed), a **warning** (fix it, or **waive** it with a written reason of at least 10 characters), or a **note** (information). Waived warnings stay in the report with their reason, so a reviewer sees them.

## Placeholders: what the tool does not know

The tool contains **no engineering numbers from any standard**: no derating factors, no wire current ratings, no EMC rules, no part masses. Your programme decides those. Until you enter them they are *placeholders*:

- Wire gauges stay **pending**.
- Checks that need a number say **not checked** instead of silently passing.
- `harness-design-studio config DIR` lists exactly what is missing and what depends on it.

The files that hold these values are in the project's `config/` folder and are described in [`CONFIG.md`](CONFIG.md). The examples ship a set of **demo values for learning**; they are not engineering data (see [`../src/harness_design_studio/resources/examples/templates/README.md`](../src/harness_design_studio/resources/examples/templates/README.md)).

## Review, release, revision

A harness has a **status**: `draft`, then optionally `in_review`, then `released`.

- **Release** needs a person's name and a comment (at least 10 characters). It is blocked while something is missing (a wire without a gauge or length, unresolved errors) and the reasons are listed in plain words. It is also blocked while a configuration file is still marked `"placeholder": true`, unless you give a written reason (`--accept-placeholders`), which is kept in the change log and the baseline. The same goes for parts: a release is blocked while the harness uses a part that is not approved (or is example data), unless you give a written reason (`--accept-unapproved-parts`).
- A released harness is **locked**: it, the interfaces it carries and the pins it uses cannot be edited, and neither can the parts, interface types and configuration values it uses. A **baseline** (frozen snapshot) and a **change log** entry are stored.
- To change it you start a new **revision** (A, B, C ...). The old revision stays.

The release check looks at the harness itself and at the placeholder mark of the configuration files. It cannot tell whether the values are right; that stays your decision and your responsibility.

In the app the work goes in three steps, shown in the top bar: **Generate**, **Check** (the design rules) and **Release…**. Each shows what is done and what is next, and a step that has to wait says what to do first.

## Outputs

**Export…** writes a folder `outputs/` into the project: per harness a **build workbook** (an Excel file to build the harness from: what is ready, the cut list with the strip lengths, one block per connector with the contact and crimp tool of each pin, parts, accessories, labels and a test sheet to fill in), wire list, pinouts, BOM, mass and length, test tables, labels, a WireViz-style YAML file and an Excel workbook of the data tables; for the system a block diagram, harness overview, BOM, matrices, the design rule report, the change log and one JSON of the whole model. Every file carries the tool version and a **model hash**, a fingerprint of the design, so a printed sheet can be traced to the exact design it came from.

The PDF and SVG drawings of the harnesses are optional and written only when you ask for them (`--drawings`, or the check box **Include the PDF drawings**); the build workbook is the main output (new in 1.7.0). Outputs are checked independently before they are written. `outputs/` is always safe to delete and regenerate.

## What is on disk

A project is a **folder of small JSON files**. Commit it to Git.

```
my-project/
  project.json            name and format version
  config/                 the engineering values (placeholders until you fill them in)
  library/                parts: connectors, wires, sleeving, labels
  logical/                interface types, units, interfaces, diagram layout
  physical/               box connectors, generated harnesses
  generated/              the record of the last generation (the reasons for the Why tab)
  baselines/  changelog.json   written at release; never edit by hand
  outputs/                everything exported (safe to delete)
```

Files are written in a fixed format, so two people editing different parts of a design merge cleanly. Details: [`FILE_FORMAT.md`](FILE_FORMAT.md).

## What the tool does not do

- It does not invent standard values (see Placeholders).
- It does not route cables in 3D; lengths come from you ([`IMPORTS.md`](IMPORTS.md)).
- It does not draw electronics: KiCad does that, and the tool can read unit connector pinouts from a KiCad netlist ([`KICAD.md`](KICAD.md)).
- It does not generate buses with more than two ends yet; such links are skipped with a warning. (You can draw such wires yourself in the *Edit wire* tab, and several wires may share a pin.)
- It does not decide what a soldered joint needs: a pin can say *solder* or *crimp* and the lists show it, nothing more yet. Likewise a pin can name its contact, a contact part its crimp tool, a wire its strip lengths and a harness its accessories (new in 1.7.0, [enter the build data](user-manual/enter-the-build-data.md)), but the tool does not choose them, does not check that a contact fits a pin or that a length is sensible, and shows `to fill in` where you have not said.
- It never uses the network.

## Words you will meet

- **Baseline**: a frozen snapshot made when a harness is released.
- **Model hash**: a fingerprint of the whole design, printed on every output.
- **Auto-filled**: a connector the tool chose; unconfirmed until a person looks at it.
- **Locked** (wire or pin): a choice you made that generation will keep. You set it in the app (a wire in the **Edit wire** tab since 1.4.0, a pin in the **Devices** tab) or by editing the harness file (`"locked": true`).
- **Released (locked)**: a harness that can no longer be edited; start a new revision.
- **DRC**: design rule check, the background rules listed in [`RULES.md`](RULES.md).
- **Fixed pin**: a pin whose signal is defined by the unit itself (imported from KiCad); generation never moves it.

Next: do it yourself in [`GETTING_STARTED.md`](GETTING_STARTED.md).
