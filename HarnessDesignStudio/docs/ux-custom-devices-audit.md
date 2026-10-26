# Custom devices: audit and design proposal (October 2026)

Status: **approved by the owner on 14 October 2026; built in stages B1 to B7 (see [Owner decisions](#owner-decisions-14-october-2026)).** Until then this page was a proposal and nothing was built. The UX standard says audit first, then approval, then build; this page is the audit (sections 1 to 4) and the proposal (sections 5 and 6). It follows the style of [`ux-audit.md`](ux-audit.md) and [`DESIGN.md`](DESIGN.md).

The feedback behind it, from the owner: *many users, especially electrical and AIT engineers, are missing a core functionality of the tool: to create custom devices and define the interfaces down to each pin themselves.* This page does not assume the feedback is right or wrong; it reports what the code does, with evidence, and then proposes a way to close what is missing.

## Contents

- [Summary](#summary)
- [1. What was audited and how](#1-what-was-audited-and-how)
- [2. What the data model already supports](#2-what-the-data-model-already-supports)
- [3. What a user can do today](#3-what-a-user-can-do-today)
- [4. The gap](#4-the-gap)
- [5. Proposal](#5-proposal)
- [6. Questions and decisions for the owner](#6-questions-and-decisions-for-the-owner)
- [Appendix: commands that were run](#appendix-commands-that-were-run)
- [Owner decisions (14 October 2026)](#owner-decisions-14-october-2026)

## Summary

**What exists.** The data model and the generator can already describe a device down to each pin: a unit, any number of box connectors on it, each with a list of pins (a pin has a name or number, a signal name, `fixed`, `locked` and an owning interface), a library part per connector with its pin count and its mating part, interface types with named signals and directions, and a pin allocator that either places signals itself or honours a pinout fixed by the device. A hand-written project folder with a custom 6-pin connector (pins `A1`, `A2`, `3`, `4`, `5`, `6`), a custom part pair, a custom 3-signal interface type and two interfaces on the same connector validated, generated, passed the verifier and exported a correct pinout (appendix, run 1). Every change is one undoable `History` step, and a release locks the pins and parts it uses.

**What is missing.** Everything a person would click. The editor has **no way to create a device of one's own, to add or remove a connector, to see or edit a single pin, to say which pins an interface uses, to define a connector part or an interface type, or to import a pinout from a spreadsheet**. The only ways in are 14 built-in unit templates, a CSV import that carries only a part's *pin count*, a KiCad netlist import that needs the unit and the part to exist already, and editing JSON by hand. Details and evidence: sections 3 and 4 (19 numbered gaps, CD-G1 to CD-G19).

**What a pin cannot hold today** (so a pin table would have blank columns): a function description, a direction, a voltage or current class, a note. Direction and class exist only on the *interface type* (and can be shown from there); the rest would need a format change, which is an owner decision (section 5.9).

**The proposal in 15 lines.**

1. One new place for all of it: a **Devices** main tab (Ctrl+6), opened from the tree (Ctrl+Enter on a unit) or by **Add > Device…** (Ctrl+Shift+N). Header, connector list, **pin table**, "Pinout as exported" preview, inline checks; the right dock keeps Inspector, Why and Problems.
2. The pin table edits the fields that already exist: pin, signal, mode (free, fixed, locked), interface, contact size and termination (hidden by default). Direction and class are **derived and read-only** from the interface type; they are never guessed.
3. Per-pin interface assignment writes `locked` + `interface_id` + `signal` (the engine already honours it) and the signal-by-name route writes `fixed`; "Fill from interface type" puts `CANH`, `CANL`, `CANGND` on the selected pins.
4. Three journeys, each with a step target: from scratch (8 steps, no dialog), from a CSV pinout (wizard, 4 pages, one undo step), from an existing part or an existing device (duplicate, **Ctrl+D**, already exists).
5. Parts and interface types get the same treatment: create a connector part (and its mating half) and an interface type inline; the tool never marks a new part approved.
6. Everything is a `core/edit.py` plan (`ops_add_device`, `ops_add_connector`, `ops_set_pin`, `ops_assign_pins`, `ops_set_pinout`, ...), tested without Qt, applied through `History`; the GUI stays thin.
7. **No file-format change is needed** for this proposal: every field it writes exists. Anything beyond (pin description, direction, class, device revision) needs a version bump and a migration and is **flagged as an owner decision**.
8. Generation, the design rules and the outputs are **unchanged**: the editor writes what a hand-edit writes (proved in appendix run 1).
9. Inline checks (`pinout_problems`) are editor-only; no rule is added to the 34 design rules unless the owner asks.
10. States: a device in a released harness shows the same lock banner as everything else, with "Start new revision…". One hole in today's locks (a spare pin of a connector that a released cable mates with can be deleted, giving a `mate-mismatch` error, appendix run 4) must be closed before pins become editable.
11. Undo: one step per cell, paste, import or connector change, with a name ("Undo Edit pin J1.A2").
12. Keyboard: arrows, F2, Tab, Insert, Delete, paste of tab-separated rows, Ctrl+Z; every control has a name and a tooltip with its shortcut.
13. Build order, seven small pull requests: core ops and checks, lock hardening, read-only Devices tab, editing, add-device flows, pinout import with a CLI twin, then the two owner-decision pieces (device file, format change).
14. Rough size: the seven pull requests are about M + S + M + L + M + M + S (legend as in the audit: S under a day, M a few days, L about a week).
15. Eleven questions for the owner in section 6. The two that gate the first useful build are CD-Q6 (lock hole) and CD-Q10 (a sixth main tab); the two with the largest reach are CD-Q1 (which pin columns an ICD needs, a format change) and CD-Q4 (where reusable devices live).

## 1. What was audited and how

- Code read: `core/model/` (all files), `core/edit.py`, `core/commands.py`, `core/generate/pins.py` and `engine.py`, `core/templates.py`, `core/library_import.py`, `core/kicad.py`, `core/imports.py`, `core/integrity.py`, `core/vcs/locks.py` and `lockview.py`, `core/drc/rules.py`, `core/outputs/tables.py`; `gui/panels.py`, `inspector.py`, `project_tree.py`, `main_window.py`, `import_kinds.py`, `import_wizard.py`, `tables.py`; the documents [`FILE_FORMAT.md`](FILE_FORMAT.md), [`CONCEPTS.md`](CONCEPTS.md), [`KICAD.md`](KICAD.md), [`IMPORTS.md`](IMPORTS.md), [`DECISIONS.md`](DECISIONS.md), [`RULES.md`](RULES.md).
- Run: the command line on the `first-steps` and `flatsat` examples and on four project folders edited by hand (appendix); the real editor offscreen on the `flatsat` example, light theme, 1500 x 950, pictures made with `widget.grab()` in [`ux/custom-devices/`](ux/custom-devices/). A throwaway script made them; no program code was added to the repository.
- Not covered: a real display, screen readers, Windows and macOS (the app is Ubuntu only), and **no user was observed**. The statement that electrical and AIT engineers expect a pin table is the owner's; the expectations in section 4 are what such an editor is normally taken to mean (a pin table, per-pin interface assignment, pinout import and export, a device library), not measured needs. Questions that only the owner or those users can answer are in section 6.

Evidence for the pictures:

| Picture | Shows |
|---|---|
| [`01-palette-add-unit.png`](ux/custom-devices/01-palette-add-unit.png) | The palette: "Add a unit" is a list of the 14 built-in templates, nothing else |
| [`02-project-tree.png`](ux/custom-devices/02-project-tree.png), [`03-tree-add-menu.png`](ux/custom-devices/03-tree-add-menu.png) | The tree and its Add menu: only **Unit…** and **Interface…** |
| [`05-expert-inspector-unit.png`](ux/custom-devices/05-expert-inspector-unit.png) | A unit in Expert mode: ID, name, chain; zone and subsystem are read-only; one card per connector with a part combo box and nothing about pins |
| [`06-inspector-part-readonly.png`](ux/custom-devices/06-inspector-part-readonly.png), [`07-inspector-interface-type-readonly.png`](ux/custom-devices/07-inspector-interface-type-readonly.png) | A part and an interface type are shown as a read-only table of properties |
| [`08-harness-tab-pins.png`](ux/custom-devices/08-harness-tab-pins.png), [`09-lists-pinouts.png`](ux/custom-devices/09-lists-pinouts.png) | The only pin tables in the editor belong to a generated harness; the cable connector rows of Lists > Pinouts have an empty Signal column |
| [`10-import-interfaces-dialog.png`](ux/custom-devices/10-import-interfaces-dialog.png), [`12-file-import-menu.png`](ux/custom-devices/12-file-import-menu.png), [`13-import-wizard-netlist.png`](ux/custom-devices/13-import-wizard-netlist.png) | The five imports (interfaces, parts, lengths, ampacity, KiCad netlist); no pinout table import |
| [`11-diagram-expert-unit.png`](ux/custom-devices/11-diagram-expert-unit.png) | The diagram in Expert mode, zoomed in on OBC1: each connector is a port with its name, a picture of its family and its pin count ("J02 31"); the pins themselves are not drawn |

## 2. What the data model already supports

Everything below is in the strict, frozen pydantic models; unknown fields are rejected (`extra="forbid"`), so a field that is not in this table cannot be written.

| ID | Thing | What the model holds | Who can set it today | Evidence |
|---|---|---|---|---|
| CD-M1 | **Unit** (the device) | `id`, `name`, `subsystem`, `zone`, `side` (nominal, redundant, none), `mass_relevant`, `notes`. No device kind, no mass, no description beyond `notes` | GUI: ID, name, chain (`side`) only; subsystem and zone are read-only. Files: all | [`logical.py:19`](../src/harness_design_studio/core/model/logical.py#L19), [`edit.py:934`](../src/harness_design_studio/core/edit.py#L934) (`ops_update_unit` allows name, side, notes, mass_relevant), picture 05 |
| CD-M2 | **Box connector** | `id`, `name`, `role` (`box` for a device), `part_id`, `unit_id`, `gender` (male, female, unspecified), `keying`, `carries` (interface types it is meant for; empty means any), `notes`, `pins`. Any number per unit; IDs are unique project-wide | GUI: only its **part** (Expert mode combo box). Gender is derived from the words male/female in the part's description when a template creates it; `keying`, `carries`, `gender` have no GUI. Files: all | [`physical.py:29`](../src/harness_design_studio/core/model/physical.py#L29), [`describe.py:36`](../src/harness_design_studio/core/describe.py#L36), [`panels.py:599`](../src/harness_design_studio/gui/panels.py#L599) |
| CD-M3 | **Pin** | `id` (the number or name: letters, digits, `_ - .`, 1 to 16 characters, so `A1`, `3`, `SHELL` are fine, `5V+` and `Pin 1` are not), `signal` (free text, up to 200 characters), `contact_size`, `termination` (crimp, solder, unspecified), `locked`, `fixed`, `interface_id`. **One field serves as number and as name.** | Files; KiCad import (id, signal, fixed); generation (`signal`, `interface_id`). GUI: never | [`physical.py:17`](../src/harness_design_studio/core/model/physical.py#L17), [`ids.py:9`](../src/harness_design_studio/core/ids.py#L9) |
| CD-M4 | **Not in the model** (per pin or per connector) | direction, voltage or current class, function description, note, pair or shield group, pin position or face drawing, contact gauge range. `contact_size` and `termination` exist but **nothing reads them** except the copy to the cable connector | n/a | `grep` of `contact_size`, `termination` in `src/`: [`engine.py:574`](../src/harness_design_studio/core/generate/engine.py#L574) only |
| CD-M5 | **Parts library** | `Part`: `category` (connector, contact, backshell, wire, sleeving, label), manufacturer, part number, specification, description, `approval` (approved, pending, not_approved), `unverified`, `pin_count` (1 to 1000), `mates_with` (the mating part), masses, `ratings`. A connector part carries **only the number of pins**, not their names | CSV or XLSX import of an approved-parts list (columns by header); files. GUI: no editor, the part picker only lists | [`library.py:18`](../src/harness_design_studio/core/model/library.py#L18), [`library_import.py:24`](../src/harness_design_studio/core/library_import.py#L24), picture 06 |
| CD-M6 | **Interface type** | `id`, `name`, `category` (power, data, analog, rf, pyro, discrete, thermal, ground, other), `signals` (each `name`, `direction` out/in/bidir/passive, `pair`), `construction`, `impedance_ohm`, `shielding`, `emc_class`, `default_gauge_awg`, `unverified`. The tool ships 17 | Files only. The tree says "No interface types yet." for an empty project and offers no Add | [`logical.py:35`](../src/harness_design_studio/core/model/logical.py#L35), [`strings.py:1441`](../src/harness_design_studio/gui/strings.py#L1441), picture 07 |
| CD-M7 | **Interface** and its pins | An interface has two `endpoints` (unit and optional box connector, `auto` flag); an interface with more than two ends is skipped ("multi-drop interfaces ... are not generated yet"). The interface does **not** name pins: pins name the interface (`Pin.interface_id`) | GUI: type, two units, connector (auto or chosen). Pins: generation, or files | [`logical.py:49`](../src/harness_design_studio/core/model/logical.py#L49), [`segmentation.py:109`](../src/harness_design_studio/core/generate/segmentation.py#L109) |
| CD-M8 | **Two ways a pin gets its signal** | (a) *Auto*: the allocator picks free pins, power first, pairs side by side, spare pins left (`allocate`); a pin the user typed a signal on without an interface is kept as locked. (b) *Fixed*: if **any** pin of a connector has `fixed` and a `signal`, the **whole connector** is allocated by name: each signal goes to the free fixed pin of the same name, never moved; a missing name is an error for that interface and nothing is placed on unnamed pins. (c) *Locked* with `interface_id` and `signal`: the pin keeps that signal for that interface in either mode | Files, KiCad import (fixed). The app has no button for `locked` ([`CONCEPTS.md`](CONCEPTS.md#words-you-will-meet)) | [`pins.py:118`](../src/harness_design_studio/core/generate/pins.py#L118), [`engine.py:421`](../src/harness_design_studio/core/generate/engine.py#L421), appendix runs 1 and 3 |
| CD-M9 | **Mating** | A harness has a **cable connector** per box connector with `mates_with` = the box connector, the library `mates_with` part (else the same part, with a warning), the opposite gender, the same keying and **the same pin ids** (copied from the box; signals are not copied). Rule `mate-mismatch` compares gender, mating part, **pin count** and keying | Generation only | [`engine.py:555`](../src/harness_design_studio/core/generate/engine.py#L555), [`rules.py:153`](../src/harness_design_studio/core/drc/rules.py#L153) |
| CD-M10 | **Size and ports in the diagram** | A unit is a card whose height follows its connector count (`expert_height`) and whose picture is guessed from its name and connector families. In Expert each connector is a **port** with its name, a picture of its family and its **pin count** ("J02 31"); the **pins are not drawn**. A custom device with any number of connectors already fits | automatic | [`edit.py:41`](../src/harness_design_studio/core/edit.py#L41), [`DESIGN.md`](DESIGN.md#state-marks-canvas), picture 11 |
| CD-M11 | **Directions of signals** | Live on the *interface type*: a signal is `out`, `in`, `bidir` or `passive` relative to the two ends; rule `direction-conflict` and the wiring use them. A pin has no direction of its own; a device's direction can be **derived** from the type of the interface on the pin | Files only | [`wiring.py:31`](../src/harness_design_studio/core/generate/wiring.py#L31), [`rules.py:223`](../src/harness_design_studio/core/drc/rules.py#L223) |
| CD-M12 | **Locks of a device in a released harness** | The unit's design fields (all but name, notes, zone), the box connector's part, gender and keying, and the pins that carry a released interface are locked; spare pins and other pins stay editable | Enforced in `History.execute` | [`locks.py:45`](../src/harness_design_studio/core/vcs/locks.py#L45), [`lockview.py:42`](../src/harness_design_studio/core/vcs/lockview.py#L42) |
| CD-M13 | **Checks that look at a device's pins** | Integrity: `duplicate_pin` (exact text), `too_many_pins` (more pins than the part's `pin_count`), `unknown_part`, `wrong_part_category`. Design rules: `pin-floating`, `signal-unassigned`, `spare-pins-low`, `connector-lookalike`, `mate-mismatch`, `direction-conflict` (they read generated harnesses or interfaces, not a standalone device). Nothing checks a device's pinout on its own | automatic | [`integrity.py:51`](../src/harness_design_studio/core/integrity.py#L51), [`RULES.md`](RULES.md) |
| CD-M14 | **Undo** | Any list of `Put` and `Delete` operations is one `History` step with undo and redo (200 steps); an edit that would break integrity is rolled back | all edits | [`commands.py:174`](../src/harness_design_studio/core/commands.py#L174); a pin edit as a bare `Put` was run and undone (appendix run 5) |

## 3. What a user can do today

"Steps" are what the person does, counted from the experiments in the appendix. **Works** means a complete, safe route exists; **works but hard** means it is possible but needs file editing, a script or workarounds; **missing** means no route.

| ID | Task | GUI | Command line | Project files by hand | Verdict |
|---|---|---|---|---|---|
| CD-T1 | Create a custom device (unit) | Only from the 14 templates ([`edit.py:135`](../src/harness_design_studio/core/edit.py#L135); pictures 01, 03): one click, then rename. You cannot choose the subsystem, the connectors or their parts; the template's are used | `new` copies a whole example; `import-netlist` needs `--unit` to exist ("Unit 'NEWDEV' does not exist", appendix run 6) | Yes: a unit file, plus a connector file; 7 steps for the first working device (run 1) | **works but hard** (files only) |
| CD-T2 | Define its connectors (type, gender, count) | Count and carried types: fixed by the template; no add or remove. Part: one combo box per connector (Expert), and it does **not** resize the pins or update the gender (9 pins stay 9 with a 31-pin male part, gender stays female, run 5). Gender, keying, carries: no control | `import-netlist` creates or updates a connector of an existing unit with an existing part, gender `unspecified` | Yes, one JSON object per connector | **works but hard** (files); **missing** in the GUI |
| CD-T3 | Define every pin of a connector (number or name) | A template makes pins `1` to `N` of the part; renaming or adding pins: no | KiCad import: pin numbers from the netlist | Yes: a list of `{"id": ...}`; one object per pin, any text up to 16 characters | **works but hard** |
| CD-T4 | Give each pin a function / signal name | No | KiCad import (net name or pin function, `--signal-map`) | Yes (`signal`, free text) | **works but hard** |
| CD-T5 | Give a pin a direction, a voltage class, a description | No field exists | No | **Not possible**: not in the model (CD-M4). Direction and class can only be *derived* from an interface type | **missing** |
| CD-T6 | Say a pin is fixed by the device or auto-allocated | No (`fixed` and `locked` have no control) | `import-netlist` marks every imported pin with a signal `fixed` | Yes | **works but hard** |
| CD-T7 | Define an interface on the device and say which pins it uses (CAN on 3, 4, 5 of J1; power on A1, A2) | Interfaces: yes (type, two units, connector). Choosing pins: **no**; Guided and Expert let the allocator pick. One interface per connector: "J01 already carries IF-010. One interface per connector." ([`edit.py:426`](../src/harness_design_studio/core/edit.py#L426)) | No | Yes: `fixed` pins named like the interface type's signals, or `locked` pins with `interface_id`; **two interfaces on one connector worked** (run 1) although the GUI refuses it | **works but hard** (files); **missing** in the GUI |
| CD-T8 | Define a custom connector part (pin count, mating half) | No; the part picker lists library parts only | `import-parts` from a CSV (`pin count`, `mating part`; the approval words are yours) | Yes (`library/connector.json`) | **works** through CSV, **works but hard** for one part |
| CD-T9 | Define a custom interface type (signals, directions, pairs) | No | No | Yes (`logical/interface_types.json`) | **works but hard** (files) |
| CD-T10 | Edit or delete a pin or connector later, with undo | No control. Undo works for everything the GUI does | No | Yes, but there is no undo except Git; the open editor offers "reload" when the folder changed ([`controller.py:1058`](../src/harness_design_studio/gui/controller.py#L1058)) | **missing** in the GUI; **works but hard** in files |
| CD-T11 | Copy a device | Yes: **Ctrl+D** or Edit > Duplicate copies the unit and its connectors **with their pins** (pin signals that came from generation are cleared; `fixed` and `locked` ones stay), new IDs, same lane ([`edit.py:1084`](../src/harness_design_studio/core/edit.py#L1084)) | No | Copy the files | **works** (inside one project) |
| CD-T12 | Reuse a device as a template or library entry across projects | The template list is the code's `TEMPLATES`; "Importing your own template list is deferred" ([`DECISIONS.md` D-67](DECISIONS.md)). No export or import of a unit | No | Copy the unit file, the connector file, and every part and interface type they use, by hand | **missing** (works but hard by copying files) |
| CD-T13 | Import a pinout from a spreadsheet | `Import approved parts` reads a **part list** (pin count only); `Import interfaces` reads links; nothing reads connector, pin, signal rows (pictures 10, 12, 13) | `import-parts` (same) | Convert the sheet to a KiCad-style netlist with a script, then `import-netlist --unit` (works for pins and signals; the unit and part must exist; gender stays unspecified; run 7) | **missing** (works but hard through a netlist) |
| CD-T14 | Import a pinout from KiCad | Wizard page "KiCad netlist": pick the file, **pick an existing unit**, see the rows, apply (one undo step); needs library parts and signal names that match the interface types | `import-netlist` | n/a | **works** (for an existing unit and part); the tree and wizard do not create the unit |
| CD-T15 | See the pinout of a device | No view of a device's pins. The Harness tab pin table and Lists > Pinouts show the pins of a **generated harness's cable connectors** (the Harness tab fills the signal from the box pin, the Lists table leaves it empty: pictures 08 and 09) | `export` writes `system/box_pinouts.csv` (every box connector: pin, signal, interface, wires, spare) | Read the JSON | **works but hard** (after Generate and Export) |
| CD-T16 | Check the pinout | Not on its own. Generation errors name a missing signal on a fixed pinout; integrity refuses duplicate pins and too many pins; free-text signals and `a1` next to `A1` pass silently (run 3) | `validate`, `drc` (rules in CD-M13) | same | **works but hard** (only through Generate and the rules) |
| CD-T17 | Change a device that a released harness uses | Refused with the reason for locked fields; **but** deleting a spare pin of a box connector a released cable mates with is allowed and ends in a `mate-mismatch` error (run 4) | same | same | **works with a hole** (CD-G15) |

## 4. The gap

What electrical and AIT engineers are taken to expect of "custom devices down to each pin", set against section 3:

| Expected capability | What exists | Verdict |
|---|---|---|
| A **device editor**: create a device, add connectors, choose gender and part | The model has all of it; the GUI has none of it | missing in the GUI |
| A **pin table** per connector: number, name, function, signal, direction, class, remarks | Pin number and signal name exist; direction and class only through the interface type; function description and remarks do not exist | partly in the model, missing in the GUI |
| **Per-pin interface assignment** ("CAN on 3, 4, 5") | Exists in the engine (`fixed`, `locked` + `interface_id`); no GUI; the GUI forbids two interfaces on one connector | missing in the GUI |
| **Pinout import and export** (spreadsheet in, ICD-style table out) | Out: `box_pinouts.csv` after Export. In: none (KiCad only) | export works but hard; import missing |
| A **device library** (reuse across projects) | Duplicate inside a project; built-in templates only; "deferred" in D-67 | missing |
| Custom **parts** and **interface types** | CSV import for parts; nothing for types | partly |

The numbered gaps, with the evidence for each:

| ID | Gap | Sev | Evidence | Fix in the proposal |
|---|---|---|---|---|
| CD-G1 | **A device can only be made from one of 14 templates.** No custom unit, subsystem, connector set | high | [`edit.py:135`](../src/harness_design_studio/core/edit.py#L135), [`panels.py:152`](../src/harness_design_studio/gui/panels.py#L152), [`strings.py:1458`](../src/harness_design_studio/gui/strings.py#L1458) (`{"unit": "Unit…", "interface": "Interface…"}`), pictures 01 and 03; [`DECISIONS.md` D-67](DECISIONS.md) | CD-J1, CD-C1 |
| CD-G2 | **No operation adds or removes a connector** (`grep "ops_.*connector"` finds only `ops_set_endpoint_connector` and `ops_set_connector_part`) | high | [`edit.py:880`](../src/harness_design_studio/core/edit.py#L880), [`edit.py:903`](../src/harness_design_studio/core/edit.py#L903) | CD-C2, CD-C3 |
| CD-G3 | **No way to see or edit a pin in the editor.** Pins appear only in generated harnesses; the Expert inspector shows a part and a "carries" line | high | [`panels.py:599`](../src/harness_design_studio/gui/panels.py#L599), pictures 05, 08, 09 | CD-C4 to CD-C6, section 5.3 |
| CD-G4 | **No per-pin interface assignment in the editor.** The engine honours `fixed` and `locked` + `interface_id`, but only a file edit sets them; `locked` "has no button" | high | [`pins.py:118`](../src/harness_design_studio/core/generate/pins.py#L118), [`CONCEPTS.md`](CONCEPTS.md#words-you-will-meet), appendix runs 1 and 3 | CD-C7 |
| CD-G5 | **Changing a connector's part does not resize its pins or update its gender** | medium | appendix run 5: `EX-MICROD-9-F` 9 pins to `EX-MICROD-31-M` gives 9 pins, gender `female`; [`edit.py:903`](../src/harness_design_studio/core/edit.py#L903) only sets `part_id` | CD-C3 |
| CD-G6 | **Gender, keying and carried types of a connector cannot be edited** | medium | `grep` for `keying` and `carries` in `gui/` and the controller: nothing writes them | CD-C3 |
| CD-G7 | **Parts only come from a CSV import** (pin count only, no pin names) and the part inspector is read-only; the tree says "Import an approved parts list." | medium | [`library_import.py:24`](../src/harness_design_studio/core/library_import.py#L24), [`strings.py:1440`](../src/harness_design_studio/gui/strings.py#L1440), picture 06 | CD-C9 |
| CD-G8 | **Interface types cannot be created or edited** except in the JSON file | medium | [`strings.py:1441`](../src/harness_design_studio/gui/strings.py#L1441), picture 07 | CD-C10 |
| CD-G9 | **One interface per connector in the GUI**, although the engine allocates several interfaces on one connector (appendix run 1) | medium | [`edit.py:426`](../src/harness_design_studio/core/edit.py#L426) | CD-Q3 |
| CD-G10 | **A pin has no direction, class, description or note** to hold what an ICD row says; KiCad's pin type is read and thrown away | medium | [`physical.py:17`](../src/harness_design_studio/core/model/physical.py#L17), [`kicad.py:42`](../src/harness_design_studio/core/kicad.py#L42) (`pin_type` is set, never used) | derived columns now; format change = CD-Q1 |
| CD-G11 | **A device's own pinout is not visible in the editor**; only after Generate (cable side) or in the exported `box_pinouts.csv` | high | pictures 08, 09; [`tables.py:110`](../src/harness_design_studio/core/outputs/tables.py#L110) | CD-C11, section 5.3 |
| CD-G12 | **No pinout import from a spreadsheet** | high | pictures 12, 13; [`IMPORTS.md`](IMPORTS.md) lists five imports; appendix run 7 for the workaround | CD-J2, CD-C12 |
| CD-G13 | **No device reuse across projects**: no export or import of a unit; the template list is code | medium | [`DECISIONS.md` D-67](DECISIONS.md), [`UX.md`](UX.md) question 5 (asked of users; D-67 says it needs the owner's list) | CD-J5, CD-Q4 |
| CD-G14 | **A device's pinout is not checked on its own.** Free-text signals, a signal on two pins, `a1` next to `A1`, an incomplete interface (CANH without CANL) all pass until Generate or a design rule trips over them | medium | appendix run 3; [`integrity.py:117`](../src/harness_design_studio/core/integrity.py#L116) compares ids exactly | CD-K1 to CD-K8 |
| CD-G15 | **Lock hole.** With W001 released, deleting a spare pin of the box connector it mates with is accepted and the result is `W001-P1 does not fit MTQ1-J01: 9 pins against 8` (`mate-mismatch`, error, not waivable) | high once pins are editable | appendix run 4; [`locks.py:45`](../src/harness_design_studio/core/vcs/locks.py#L45) compares only the pins that carry a released interface | CD-C13, CD-Q6 |
| CD-G16 | **Multi-drop buses are skipped**: a CAN bus with three nodes is two or three two-end interfaces | low (known) | [`segmentation.py:109`](../src/harness_design_studio/core/generate/segmentation.py#L109) | out of scope |
| CD-G17 | **Mixing is not possible within one connector**: one `fixed` pin with a signal turns the whole connector into "by name only"; unnamed pins are never used | low (a design choice that must be told to the user) | [`pins.py:118`](../src/harness_design_studio/core/generate/pins.py#L118), [`KICAD.md`](KICAD.md#what-fixed-does) | wording in the connector header, section 5.3 |
| CD-G18 | **Cable-side pins carry no signal**, so Lists > Pinouts shows an empty Signal column for every cable connector while the wires are listed (the Harness tab fills it from the box pin) | low (incidental; not part of the request) | picture 09; [`tables.py:84`](../src/harness_design_studio/core/outputs/tables.py#L75), [`harness_view.py:162`](../src/harness_design_studio/gui/harness_view.py#L162) | none; reported for the owner |
| CD-G19 | **Hand editing is possible but unforgiving**: no undo, group files are re-sorted and renamed on the next save (`gyro.json` became `aocs.json`, with `.bak` copies), and a custom signal must match an interface type's signal names exactly or the connector reports "no free pin named ..." | low | appendix runs 1 and 3. A positive: `harness-design-studio schema DIR` writes JSON Schemas that complete and check the keys in VS Code ([`FILE_FORMAT.md`](FILE_FORMAT.md#editing-files-by-hand-json-schemas)) | n/a |

What already works and must not be disturbed: strict validation of every id, duplicates refused, one undo step per change, locks refuse edits with a reason, the allocator and verifier agree with hand-written pinouts, outputs are byte-reproducible.

## 5. Proposal

### 5.1 Principles

1. **One place, one table.** The pin table of a connector is the centre of the work, as the wire table is for a harness; the diagram stays the place for units and links (standard principle 1: lists and tables are views of the same selection).
2. **Only what the model holds.** Every editable cell writes an existing field. A column the model cannot hold is either **derived and read-only** (direction and class, from the interface type) or **absent** (description); it is never an empty promise.
3. **Nothing invented.** A direction or class is shown only when the pin's signal matches a signal of an interface type; otherwise the cell is empty with a tooltip saying why. A new part is created `pending` and never approved by the tool; a new interface type is `unverified`.
4. **Nothing silent, everything undoable.** One `History` step per action, named.
5. **Validation inline**, next to the cell, never a message box; locked items refuse with the reason and "Start new revision…" (existing pattern, [`DESIGN.md`](DESIGN.md#project-tree-inspector-and-why)).
6. **Headless first.** Every action is a plan in `core` (tests without Qt), the view only calls it.

### 5.2 User journeys

| ID | Journey | Target | Steps |
|---|---|---|---|
| CD-J1 | **A custom device from scratch**: a gyro unit with one 9-pin connector, power on `A1`, `A2`, CAN on `3`, `4`, `5` | at most 8 steps, no dialog, under two minutes with the keyboard | 1. **Ctrl+Shift+N** (Add > Device…): a draft device appears in a free slot of the diagram and the Devices tab opens with its Name focused. 2. Type the name, Tab to subsystem (a combo box of existing ones that also takes new text), Enter. 3. **Ctrl+Shift+C** adds a connector: a row in the connector list with a part picker that searches the library; the first entry is "New part…" (pin count, mating half; see CD-J3). Enter. 4. The pin table fills with rows `1` to `9` (the part's pin count); rename `1` to `A1` and `2` to `A2` (F2, type, Enter). 5. Select `A1`, `A2`, **Fill from interface type…** (Ctrl+L), choose Primary power: `PWR`, `RTN` are written; select `3` to `5`, fill from "CAN with ground". 6. The header shows what the connector can carry (derived from the complete types, editable) and asks nothing else. 7. Check the inline notes under the table (Section 5.3). 8. Ctrl+S. Undo is available after every step. |
| CD-J2 | **From a CSV or XLSX pinout** (an ICD table exported from a spreadsheet) | wizard of 4 pages, one undo step | File > Import > **Device pinout…** (the import wizard, a new kind beside the five): 1. kind and file. 2. map the columns (connector, pin, signal, mode, contact size, termination; headers matched by name as the parts import does), choose **the device** (an existing unit, or "New device named ..."), the part per connector (a column or one value for all), gender. 3. preview with one line per row and the reason for each refused row ("row 17: pin 'A 1' cannot be used"); a list with a bad row is not imported, as for parts and the netlist. 4. result with what stays pending (signals that match no interface type, parts still `pending`). Apply = one step "Import pinout (2 connectors, 36 pins)". The command line twin `import-pinout DIR FILE --unit U [--part J1=PART] [--dry-run]` uses the same planner (CD-Q8). |
| CD-J3 | **From an existing part or device** | 3 to 4 steps | (a) In the Devices tab: **+ From part…**, pick a library part: pins `1` to `N`, gender from the part's description, mating part from the library. (b) **Ctrl+D** on a device copies it with its pins (exists today), then edit. (c) In the part picker "New part…" creates a connector part (pin count, manufacturer, part number) and, when asked, its mating half with the opposite gender description; approval `pending`. (d) Copy pin rows between devices: Ctrl+C in the table, Ctrl+V in the other (tab-separated, as the other tables copy). |
| CD-J4 | **Change it later** | 1 step per change | Click a cell and type; Delete clears a signal; **Shift+Delete** deletes the pin row (the impact line says "used by IF-011 on pins 3 and 4; W003 will be out of date"); Ctrl+Z undoes. In a released harness the field is disabled with the reason and a "Start new revision…" button, as in the Inspector. |
| CD-J5 | **Reuse across projects** | 2 steps | Devices tab > **Export device…** writes `NAME.device.json` (unit, its connectors, the parts and interface types they use, in the project's own object shapes); Add > **Device from file…** previews and adds it (new IDs when they clash, parts and types merged by ID with a conflict list). Depends on CD-Q4. |
| CD-J6 | **AIT: look up and compare a pinout** | 2 steps | Open the device (Ctrl+Enter in the tree), the preview shows the pinout as it is exported; **Export pinout…** writes the CSV or XLSX of that device (the existing `box_pinouts` table filtered to it), ready to compare with the ICD. A released device is shown read-only with its lock chip. |

### 5.3 The Devices tab

Placement in the window (all of the existing layout stays): the main tabs become Diagram, Harness, Lists, Checks, Releases and **Devices** (Ctrl+6). It plugs in through `MainWindow.install_view("devices", ...)` like the Harness and Lists views; a unit selected on the diagram or in the tree is the device shown. The right dock keeps Inspector, Why and Problems; selecting a pin opens its reasons in Why (box pin reasons exist already). Guided mode keeps hiding connectors on the canvas and inspector; its hint text gets a link "Open in Devices (Ctrl+6)". The sixth tab is a departure from the five tabs of the standard: CD-Q10.

```
+--------------------------------------------------------------------------------------------+
| Device  GYRO1  [Gyro unit            ]  Subsystem [aocs   v]  Chain [nominal v]   Draft    |
| 1 connector, 9 pins, 5 signals set, 1 interface    [Duplicate] [Export device...]          |
+-----------------+--------------------------------------------------------------------------+
| CONNECTORS      | GYRO1-J01   Part [MY-HD-9-F v]  Gender [female v]  Keying [      ]           |
|  > J01  9 pins  | Pin allocation: Fixed pinout (this table is the truth)   Carries: CAN, PWR  |
|    J02  15 pins |                                                                          |
|  [+ Connector]  | Pin   Signal     Mode      Interface   Direction  Class  Wire     State   |
|  [+ From part]  | A1    PWR        Fixed     IF-010      in         power  W002-001 Auto    |
|                 | A2    RTN        Fixed     IF-010      passive    power  W002-002 Auto    |
|                 | 3     CANH       Fixed     IF-011      bidir      data   W003-001 Auto    |
|                 | 4     CANL       Fixed     IF-011      bidir      data   W003-002 Auto    |
|                 | 5     CANGND     Fixed     IF-011      -          data   W003-003 Auto    |
|                 | 6                Free                                             spare   |
|                 | ...                                                                      |
|                 | 2 notes: CANGND is on no interface type signal ...                        |
+-----------------+--------------------------------------------------------------------------+
| PINOUT AS EXPORTED (read only, the rows of system/box_pinouts.csv for this device)   [Export]|
+--------------------------------------------------------------------------------------------+
```

| ID | Piece | Contents and rules |
|---|---|---|
| CD-S1 | **Header** | ID (rename uses `ops_rename_unit`), name, subsystem, chain, state chip (Draft, In use, Locked, section 5.5), counts, Duplicate (same as Ctrl+D), Export device. Tab order is header, connector list, pin table, preview. |
| CD-S2 | **Connector list** (left) | One row per box connector: name, pin count, a chip for problems and lock. `+ Connector`, `+ From part`, Delete (with the impact: interfaces that end on it lose their connector and become `no-connector` notes; harnesses that are hand-made block it, as for units, [`edit.py:507`](../src/harness_design_studio/core/edit.py#L507)). |
| CD-S3 | **Connector card** | Part picker (searchable, shows `part_summary`); changing the part asks inline "Resize the pins to 31? Set gender from the part?" with one checkbox each and applies both in the same step (fixes CD-G5); gender, keying, notes; **Carries** as removable chips with the suggestion "complete for: CAN" (types whose signals are all on this connector's pins); **Pin allocation** stated in words: "Fixed pinout" when any pin is fixed with a signal, "Automatic" otherwise, with the sentence that fixed means *every* signal of every interface on this connector must have a pin of its name (CD-G17). |
| CD-S4 | **Pin table** (`tables.TableView`, made editable) | Columns below. Sorting is off by default (the order of entry carries meaning); Ctrl+C and Ctrl+Shift+C copy, Ctrl+V pastes tab-separated rows from a spreadsheet; spare pins stay visible here (a device editor must show every pin), a filter box narrows. |
| CD-S5 | **Pinout as exported** | A read-only table that is exactly the rows `outputs/system/box_pinouts.csv` will contain for this device (`tables.box_pinouts` filtered): what you see is what you ship. |
| CD-S6 | **Inline notes** | Under the table, one line per problem with the row it belongs to; a click selects the cell. Rows carry a state chip (error, warning, info) from `states.py`, never a colour alone. |
| CD-S7 | **Empty state** | "No devices yet. Add one with Ctrl+Shift+N, or import a pinout." with one enabled button, as the other tabs do. |

Pin table columns (the "model" column says what is written; "derived" columns are read-only):

| Column | Model | Editable | Notes |
|---|---|---|---|
| Pin | `Pin.id` | yes | monospace; validated as an id of at most 16 characters, unique ignoring case |
| Signal | `Pin.signal` | yes | a combo box of the project's signal names grouped by interface type, and free text; free text is allowed and marked "no interface type uses this name" (CD-K4) |
| Mode | `Pin.fixed`, `Pin.locked` | yes | Free, Fixed, Locked (words, not colours); "Fixed" = the device defines it |
| Interface | `Pin.interface_id` | via **Assign to interface…** | shows the interface and, for generated assignments, the "Auto-filled" chip; assigning writes Locked + interface + signal |
| Direction | from `InterfaceType.signals[].direction` | derived | empty with a tooltip when the signal is unknown; never guessed |
| Class | from `InterfaceType.category` and `emc_class` | derived | "power", "data", ... |
| Wire | from the generated harnesses | derived | the wire that ends on this pin through the cable connector |
| Contact size, Termination | `Pin.contact_size`, `Pin.termination` | yes | **hidden by default**: no output or rule reads them today (CD-M4) |
| State | chip | | spare, auto-filled, problems from CD-K1 to CD-K8, lock |

Columns an ICD usually has and the model cannot hold: function description, remarks, voltage, current. They are **not** shown. If the owner wants them: CD-Q1 and section 5.9.

Interface assignment, in detail. In the pin table select the pins, then **Assign to interface…** (context menu or Ctrl+Enter): the list holds the interfaces that have an end on this device and the new-interface flow (Ctrl+I) as its last entry. Choosing IF-011 (CAN with ground) puts its signals on the selected pins in order (`CANH`, `CANL`, `CANGND`; the dialog-free form is a small popup with the signal order editable by drag or by typing the pin for each signal) and writes `locked`, `interface_id` and `signal`. Choosing "this pin is part of the device design" writes `fixed` and the signal only. If the interface has no connector chosen yet on this end, the same step sets the end's connector to this one (`ops_set_endpoint_connector`, one step).

Inline checks (editor only; `edit.pinout_problems(project, connector_id)`; **none is added to the 34 design rules**):

| ID | Check | Severity |
|---|---|---|
| CD-K1 | A pin id that is not usable, or two ids equal ignoring case (`A1` and `a1`) | error |
| CD-K2 | More pins than the part's pin count (the integrity rule already refuses it in `History`); fewer pins than the part has: "6 of 9 pins defined" | error; info |
| CD-K3 | The same signal on two pins | warning (as the KiCad import says) |
| CD-K4 | A signal that no interface type has (free text) | info: nothing can connect to it |
| CD-K5 | An incomplete interface type on a fixed connector (CANH without CANL) | warning |
| CD-K6 | A locked pin whose interface does not end on this connector, or whose signal is not a signal of the interface's type | error |
| CD-K7 | Gender unspecified while the part's description says nothing: `mate-mismatch` and the cable gender cannot be judged | warning |
| CD-K8 | `carries` names a type the pins cannot complete | warning |

### 5.4 Keyboard model

Every shortcut goes into a menu and into the tooltip as "text (shortcut)", every control has an accessible name, F6 moves between the diagram, tree, Devices tab and dock as it does now. Keys marked "table" act only while the pin table has the focus.

| Key | Action |
|---|---|
| Ctrl+6 | Show the Devices tab |
| Ctrl+Shift+N | Add device (free; Ctrl+N stays "new project") |
| Ctrl+Enter (tree, diagram) | Open the selected unit in Devices (the tree already opens objects with Ctrl+Enter) |
| Ctrl+Shift+C | Add connector to the device |
| Arrows, Tab, Shift+Tab (table) | Move between cells, wrapping to the next row |
| F2 or Enter (table) | Edit the cell; Enter commits and goes down, Esc cancels |
| Insert (table) | Insert a pin after the current one (next free number) |
| Delete (table) | Clear the cell (signal) |
| Shift+Delete (table) | Delete the selected pins, after the impact line |
| Space (table) | Cycle the Mode of the selected pins |
| Ctrl+L (table) | Fill the selected pins from an interface type |
| Ctrl+Enter (table) | Assign the selected pins to an interface |
| Ctrl+C, Ctrl+Shift+C, Ctrl+V (table) | Copy cells, copy with header, paste tab-separated rows (one undo step) |
| Ctrl+Z, Ctrl+Y | Undo, redo (global, as now) |

### 5.5 States: draft, in use, locked, read-only

A device has no state of its own in the file; the state is worked out from the project each time, as locks are today (`lockview`).

| State | How it is known | What can change | What the tab shows |
|---|---|---|---|
| **Draft** | no interface ends on the device | everything | chip "Draft" |
| **In use** | at least one interface ends on it, or a *draft* generated harness uses it | everything; an edit that changes pins or signals used by a generated draft harness makes the plans out of date (the existing banner and chip), the next Generate rebuilds them; **a hand-made harness (not generated) that uses a pin blocks a pin delete or rename**, as it blocks a unit delete today ([`edit.py:507`](../src/harness_design_studio/core/edit.py#L507)) | chip "In use" and the list of interfaces and harnesses (the "Used in" table, `core/usedby.py`) |
| **Locked** (released) | a released harness carries an interface of the device (`lockview` kinds `unit`, `box_connector`, `box_pin`) | the fields `lockview` allows (names, notes, zone for the unit; spare pins' signal, contact size and so on); the **pin set** (ids and count) of every connector a released cable mates with is frozen (CD-G15, CD-C13) | the lock chip with the harness and revision, the sentence from `lock_reason`, fields disabled with the reason as tooltip, **Start new revision…**; nothing is discoverable only by failing |
| **Read-only project** | newer format, damaged project, locked folder | nothing | the existing read-only banner ("Use Save as") |

What is **not** proposed: a state or revision of the device itself ("pinout reviewed", "approved"). The format has none; it is CD-Q2.

### 5.6 Undo

One `History` step per action, labelled for the Undo menu ([`DESIGN.md`](DESIGN.md#the-window), "Undo and Redo name the step"): "Add device GYRO1", "Add connector GYRO1-J01", "Edit pin J01.A2", "Paste 9 pins into J01", "Assign pins 3-5 to IF-011", "Delete pins A1, A2 of J01", "Change part of J01 and resize pins", "Import pinout (2 connectors, 36 pins)". A cell commits on Enter, Tab or leaving the cell (one step per cell); a paste, a fill, an import and a part change are one step each. Undo never crosses a saved release record (existing rule). `History` already does this for any list of `Put` and `Delete` (appendix run 5).

### 5.7 Headless functions needed

Edit logic goes to `core/edit.py` as the project's rule says; because that file is already 1,163 lines the device functions could live in a new module `core/devices.py` that `edit.py` re-exports (every new module needs a docstring and `python -m tools.gen_sdd_components`). All return `list[Op]` (plans), raise `EditError` with a plain sentence, and are applied by `History.execute`; none imports Qt.

| ID | Function | What it does | Reuses |
|---|---|---|---|
| CD-C1 | `ops_add_device(project, *, unit_id, name, subsystem, side="nominal", zone=None, x=None, y=None) -> (ops, unit_id)` | a `Unit` and its placement, no connectors | `_check_new_id`, `free_slot`, `zone_of_x` as `ops_add_unit` |
| CD-C2 | `ops_add_connector(project, unit_id, *, part_id, name=None, gender=None, keying=None, carries=(), pin_ids=None) -> (ops, connector_id)` | next free `<unit>-Jnn`, pins `1`..`N` from the part or the ids given, gender from `part_gender` unless given | `unit_connectors`, `part_gender` |
| CD-C3 | `ops_update_connector(...)`, `ops_change_part(project, connector_id, part_id, *, resize=True, regender=True)`, `connector_delete_impact`, `ops_delete_connector` | edit name, gender, keying, carries, notes; part change that also resizes pins and sets the gender (fixes CD-G5) without changing the existing `ops_set_connector_part`; delete with the same impact logic as `delete_impact` | `delete_impact` |
| CD-C4 | `ops_set_pin(project, connector_id, pin_id, **changes)` | `signal`, `contact_size`, `termination`, `fixed`, `locked`; refuses a change a lock forbids | `evolve`, `check_locks` through `History` |
| CD-C5 | `ops_add_pins`, `ops_delete_pins`, `ops_rename_pin` | with the casefold uniqueness check; a rename keeps the pin's signal and interface and is refused when a wire of a hand-made or released harness uses the pin (a generated draft harness only becomes out of date) | `delete_impact` style |
| CD-C6 | `ops_set_pinout(project, connector_id, rows)` | one `Put` for a paste, a fill or an import: the whole pin list | one undo step |
| CD-C7 | `ops_assign_pins(project, connector_id, pin_ids, interface_id, signals=None)`, `ops_unassign_pins` | writes `locked`, `interface_id`, `signal`; checks the interface has an end on this unit and the signals belong to its type; sets the end's connector if empty | `ops_set_endpoint_connector` |
| CD-C8 | `suggest_carries(project, connector_id) -> list[str]`, `fill_from_type(project, connector_id, pin_ids, type_id)` | the types complete on the pins; the pin-by-pin signal fill | `InterfaceType.signals` |
| CD-C9 | `ops_add_part`, `ops_update_part`, `ops_add_part_pair` | a connector part and its mating half (`mates_with` both ways), approval `pending`, `unverified` true; never `approved` | `Put("parts", ...)`; locks already protect parts of a released harness |
| CD-C10 | `ops_add_interface_type`, `ops_update_interface_type` | signals with direction and pair; `unverified` true | locks already protect types of a released harness |
| CD-C11 | `pinout_table(project, unit_id) -> Table` | the `box_pinouts` rows of one device (the preview and the export) | `outputs.tables.box_pinouts` |
| CD-C12 | `plan_pinout_import(project, table, mapping, *, unit_id, parts, gender, ...) -> PinoutPlan` | one result per row with its reason, `ops` for the connectors, `unmatched_signals`, `warnings`; the same shape as `PartsPlan` and `NetlistPlan` | `library_import.guess_mapping`, `imports.read_table`, `kicad.NetlistPlan` |
| CD-C13 | `device_state(project, unit_id)`, `pin_set_frozen(project, connector_id)` | draft, in use, locked and the sentence; the freeze of the pin set of a connector a released cable mates with (planner refuses; tightening `check_locks` itself is CD-Q6) | `lockview.locked_objects`, `lock_reason` |
| CD-C14 | `pinout_problems(project, connector_id) -> list[PinProblem]` | CD-K1 to CD-K8 | `check_pin_id`, `known_signals` |
| CD-C15 | `devices.export_device`, `devices.plan_device_import` | the device file (CD-J5), only if the owner decides CD-Q4 | the models' own `model_dump` |

### 5.8 Effect on generation, rules and outputs

**None.** The editor writes the same fields a hand edit writes, and a hand-written custom device already generates, verifies and exports (appendix run 1: `0 error(s)` from the verifier, a correct `box_pinouts.csv`, the same wires on both ends). A test will pin that down: a device built by the editor and the same device written by hand give byte-identical files, and a second Generate is empty (CD-X4). Three things would change something and are therefore **decisions, not part of the base proposal**: allowing two interfaces on one connector in the GUI (changes `connector_compat`, CD-Q3), tightening `check_locks` instead of only the planner (changes refusals, CD-Q6), and turning inline checks into design rules (changes the rule count of 34, `RULES.md`, the DRC goldens and the compliance matrix, CD-Q7).

### 5.9 File format: what is enough, what is not

**Enough as it is (no format change, no version bump, no migration):** the Unit, Connector (all of its fields), Pin (`id`, `signal`, `fixed`, `locked`, `interface_id`, `contact_size`, `termination`), Part (`pin_count`, `mates_with`, approval) and InterfaceType (signals, direction, pair, category) objects, and the existing file layout (`logical/units`, `physical/connectors`, `library/connector.json`, `logical/interface_types.json`). Journeys CD-J1 to CD-J4 and CD-J6 need nothing else.

**A format change would be needed, and is an owner decision (CD-Q1, CD-Q2, CD-Q4), for any of:**

| ID | Wanted | Would add |
|---|---|---|
| CD-F1 | Function description and remarks per pin | `Pin.description`, `Pin.notes` |
| CD-F2 | Pin direction, voltage or current class of its own, not from an interface type | `Pin.direction`, `Pin.class` (and what they mean) |
| CD-F3 | Connector face drawing (pin positions) | pin layout per part |
| CD-F4 | A reviewed or approved state, or a revision, of a device pinout | a field on Connector or Unit |
| CD-F5 | Devices stored in the project's library (not only in a separate file) | `library/devices.json` |

If any is chosen the cost is large, and it has to be decided knowingly:

- A change to the files needs `schema_version` 2 with a migration function in `core/io/migrate.py` and a fixture of the old format ([`FILE_FORMAT.md`](FILE_FORMAT.md#versions-and-migration)). An older tool then opens a version 2 project read-only (`newer_version`, [`loader.py:337`](../src/harness_design_studio/core/io/loader.py#L337)); without the bump an older tool would set the new files aside as invalid, because models reject unknown fields.
- The saver writes **every** field, defaults included (the pins above show `"fixed": false`). A new field therefore changes the bytes of every connector file, hence **every `model_hash`** and **every golden fixture** (`mini3`, `sat15`, the output goldens, the tutorial's quoted hash in `GETTING_STARTED.md`). Unless the saver is taught to leave a default out, which is itself a change to the writer. "Output file contents and byte-reproducibility" are on the list of things the UX standard says never to change, so this needs the owner's explicit word.
- The format has grown before without a bump when a field was optional with a default (`Pin.fixed`, [`FILE_FORMAT.md`](FILE_FORMAT.md#generation-additions-pins-mating-locks-generation-record-schema-version-stays-1)); that precedent is mentioned for completeness and **is not relied on here**.
- Recommended if wanted: one bump bundling CD-F1, CD-F2 and CD-F4, with the saver omitting defaults so existing hashes stay.

A **device file** for reuse (CD-J5) is not a change to the project format, but it is a new documented file kind with its own version; that is a decision too (CD-Q4). The proposal builds it last.

### 5.10 Tests needed

Tests first, as the project's rule says; every item fails without the change.

| ID | Test | Where |
|---|---|---|
| CD-X1 | Each plan of CD-C1 to CD-C10: ops result, error sentences, ids (casefold), limits (16 characters, 1000 pins, part pin count), refusal on a read-only project, undo and redo restore the project exactly | new `tests/test_edit_device.py` (headless) |
| CD-X2 | A hypothesis sequence of random device edits with undo and redo ends in the same project; integrity stays clean after every step | `tests/test_edit_device.py` |
| CD-X3 | Locks: pin set frozen when a released cable mates; spare pin signal editable; locked fields refused with the sentence `lockview` gives (the existing test compares them); `device_state` for the four states | `tests/test_vcs_lockview.py` pattern, new cases |
| CD-X4 | Equivalence: a device from the plans equals a hand-written fixture byte for byte, a second `generate` plan is empty, `verify` and `drc` report no new finding, the rule count stays 34 | new fixture `tests/fixtures/projects/custom_device` |
| CD-X5 | `plan_pinout_import`: good rows, bad ids, duplicate pins, unknown part, gender words, decimal separators of the contact size, a released harness blocks, CSV and XLSX (`read_table`) | `tests/test_data_import.py` pattern |
| CD-X6 | Inline checks CD-K1 to CD-K8, each with a positive and a quiet case | new |
| CD-X7 | GUI: keyboard-only journeys CD-J1, CD-J2 (wizard), CD-J4; every control has an accessible name (`test_accessibility.py`); tab order; light and dark; read-only project; released device; 1280 x 720; empty project; 1000 pins | new `tests/test_ux_devices.py` |
| CD-X8 | Performance: one cell edit under 100 ms with 1000 pins and 100 units; dirty regions counted as `test_gui_perf.py` does | `tests/test_gui_perf.py` |
| CD-X9 | Docs: the user guide names the new buttons (`test_guide_names_buttons_that_exist`), CLI docs list `import-pinout` (`tools.gen_cli_docs`), links resolve | `tests/test_docs.py`, `tests/test_docs_links.py` |
| CD-X10 | A usability session with six people (three electrical, three AIT) with the existing kit (`tools.usability_setup`): journeys CD-J1 and CD-J2, SUS | `docs/usability/` |

### 5.11 Effort and build order

Legend as in [`ux-audit.md`](ux-audit.md): S under a day, M a few days, L about a week or more. These are estimates, not measurements.

| ID | Pull request | Contents | Effort | Needs |
|---|---|---|---|---|
| CD-B1 | **Core: connectors, pins, checks** | CD-C2 to CD-C6, CD-C8, CD-C11, CD-C14, tests CD-X1, CD-X2, CD-X6; no GUI | M | none |
| CD-B2 | **Core: lock hardening** | CD-C13 (planner refusals, `device_state`), tests CD-X3; closes CD-G15 in the new paths | S | CD-Q6 |
| CD-B3 | **Devices tab, read only** | tab and slot, header, connector list, pin table over `DictTableModel`, preview, Export pinout; makes the pinout visible (CD-G11) and is useful on its own | M | CD-Q10 |
| CD-B4 | **Devices tab, editing** | an editable `TableView` (cell editors, paste, Insert, Delete, keyboard model), connector card, undo labels, inline notes; tests CD-X7, CD-X8 | L | CD-B1, CD-B2, CD-B3 |
| CD-B5 | **Add device, from part, assign** | CD-C1, CD-C7, CD-C9, CD-C10; Add > Device…, + From part, Fill from interface type, Assign to interface, New part, New interface type | M | CD-B4 |
| CD-B6 | **Pinout import and CLI** | CD-C12, wizard page "Device pinout", `import-pinout`, `export-pinout`, docs, test CD-X5, CD-X9 | M | CD-Q8 |
| CD-B7 | **Docs and a usability session** | user-manual page "Define a device", cheatsheet, guide, CD-X10 | S | CD-B5 |
| CD-B8 | Device file export and import (CD-C15) | | L | CD-Q4 |
| CD-B9 | Format version 2 (CD-F1, CD-F2, CD-F4), migration, goldens | | L | CD-Q1, CD-Q2 |

Recommended order: B1, B2, B3 (value early: you can finally *see* a device), B4, B5, B6, B7; B8 and B9 only after the decisions. Each is a pull request of its own, tests first, `ruff`, `mypy`, the generated documents rebuilt (`gen_sdd_components`, `build_guide`, `gen_cli_docs`, `trace`), the CHANGELOG line, and the golden fixtures **unchanged** (B1 to B7).

### 5.12 Acceptance, as the standard asks

Keyboard only; light and dark; a 100-unit project; a project full of placeholders; a released harness; an empty project; 1280 x 720 and 4K; tests green; no hard-coded colour or pixel size; every string in `gui/strings.py`; validation inline; edits under 100 ms. And the owner's own sentence as the test of the whole: an electrical engineer can define a 25-pin device with its signals and put CAN on three named pins in a few minutes without opening a file.

## 6. Questions and decisions for the owner

| ID | Question | Why it matters | Blocks |
|---|---|---|---|
| CD-Q1 | Which columns must a pin row have for your ICDs? Function description, remarks, voltage, current, direction of its own? | Anything the model cannot hold is a format change (section 5.9): `schema_version` 2, migration, every `model_hash` and golden changes unless the writer is changed | CD-B9 |
| CD-Q2 | Must a device pinout be *reviewed or approved* separately from a harness release? Who signs it? | The format has no such state; today only harnesses are released and lock their devices | CD-B9 |
| CD-Q3 | May the GUI allow **two interfaces on one connector** (a connector with power and CAN)? | The engine already generates it; the GUI refuses it ("One interface per connector"); it changes `connector_compat` and the Guided auto-choice | CD-B5 |
| CD-Q4 | Where do reusable devices live: a file you exchange (`NAME.device.json`), a folder per user, the project's library, or Git copies? | A new file kind (or a format change) and a version for it | CD-B8 |
| CD-Q5 | Is a part made in the editor allowed to be used in a draft with approval `pending`? (The proposal: yes, always `pending`, `unverified`, the existing warning `part-unapproved` stays; the tool never approves.) | D-12: the tool never decides what is approved | CD-B5 |
| CD-Q6 | Close the lock hole (CD-G15) in the planner only, or also in `check_locks` (a refusal that is new for files edited by hand and for the API)? | The second changes what is refused and so touches rule logic | CD-B2 |
| CD-Q7 | Keep the pinout checks as inline notes, or make some of them design rules? | A rule changes the rule count (34), `RULES.md`, the DRC goldens, the compliance matrix | none |
| CD-Q8 | Add the commands `import-pinout` and `export-pinout`? | New commands are additions to the command line behaviour; they need documentation (`gen_cli_docs`) | CD-B6 |
| CD-Q9 | Pin names: is `[A-Za-z0-9_.-]`, 16 characters enough? Do you need a pin *number* and a pin *name* as two things (D-sub `A1` and `SHIELD`)? Gender: edit it directly, or keep deriving it from the part's description? | One field serves as number and name today; splitting is a format change | CD-B4 |
| CD-Q10 | May the Devices view be a **sixth main tab** (Ctrl+6)? The standard lists five. Alternatives: a panel inside the Diagram tab, or a large inspector. | Layout of the whole window | CD-B3 |
| CD-Q11 | Is the connector face drawing (pin positions) needed, or is the table enough? Mass and size of a device? | Both are format changes and drawing work | none |

The owner decisions that gate the first useful build are **CD-Q6** and **CD-Q10**; CD-B1 can start without any decision.

## Appendix: commands that were run

All in scratch folders outside the repository, with the tool at `1.0.0` from this branch. `M` is `python -m harness_design_studio.cli.main`.

1. **Hand-written custom device, end to end.** `M new p2 --template first-steps`; wrote `logical/units/gyro.json` (a unit), `physical/connectors/gyro.json` (connector `GYRO1-J1` with pins `A1 PWR`, `A2 RTN`, `3 CANH`, `4 CANL`, `5 CANGND`, `6`, all `fixed` but the last), two parts in `library/connector.json` (`MY-HD-6-F`, `MY-HD-6-M`, `pin_count` 6, `mates_with` each other), the interface type `can3` (CANH, CANL as a pair, CANGND) in `logical/interface_types.json`, and two interfaces on `GYRO1-J1` (`power_primary` from `PCDU1-J01`, `can3` from `OBC1-J01`). `M validate .` gave `4 units, 4 interfaces, 10 connectors, 0 harnesses: 0 error(s), 0 warning(s)`; `M generate .` gave `1 added ... 4 interfaces and 11 wires checked: 0 error(s)` (the first time an interface was skipped because I had left a connector empty: `[interface_skipped] IF-010 was not generated: a connector has not been chosen on every end`); the generated pins were `A1`/`A2` to `IF-010` and `3`/`4`/`5` to `IF-011`; `M export .` wrote 49 files and `outputs/system/box_pinouts.csv` lists `GYRO1-J1,box,,MY-HD-6-F,3,CANH,IF-011,W003-001,no` and the free pin 6 as spare. After the first save the files were regrouped: `gyro.json` became `aocs.json` with `.bak` copies.
2. **What a template unit looks like in files.** `physical/connectors/aocs.json` of `first-steps`: every pin is written with all seven fields (`contact_size`, `fixed`, `id`, `interface_id`, `locked`, `signal`, `termination`).
3. **Locked pin and free text.** On `RW1-J02` I set pins `10` to `13` to `TX+ TX- RX+ RX-`, `locked`, `interface_id` `IF-002`: `generate` kept them (`4 locked pin(s) kept`). A free-text signal `HEATER_ENABLE` on pin `20` passed `validate` and `generate` with no message. Renaming two pins of `RW1-J01` to `A1` and `a1` also passed `validate` (`0 error(s), 0 warning(s)`) and `generate`.
4. **Lock hole.** `M new p6 --template flatsat; M export p6; M release p6 W001 ...` (with the two `--accept-` options), then in Python on the released project: editing the signal of a used pin of `MTQ1-J01` was refused ("This change was blocked because it touches released items"); deleting a spare pin (`3`) and setting a signal on another spare pin were **accepted**; `drc` then reported `mate-mismatch`: `W001-P1 does not fit MTQ1-J01: 9 pins against 8`.
5. **Part change and undo.** `ops_set_connector_part(p, "RW1-J01", "EX-MICROD-31-M")` on `first-steps`: before `EX-MICROD-9-F`, 9 pins, `female`; after `EX-MICROD-31-M`, **9 pins, `female`**. `ops_duplicate_unit` made `RW2` with connectors of 9 and 21 pins and undo removed it. A bare `Put` of a connector with one pin changed (signal `TX+`) was undone by `History.undo`. `len(edit.TEMPLATES)` is 14.
6. **Netlist import needs the unit.** `M import-netlist p3 wheel-connectors.net --unit NEWDEV --dry-run` printed `Unit 'NEWDEV' does not exist` and exited 1. `M import-parts ... approved-parts.csv` reads part rows (id, category, pin count, approval words), not pins.
7. **A CSV pinout through a netlist.** A six-row CSV (`pin,signal`) was turned by a ten-line script into a netlist with one component `J1` (fields `HarnessConnector`, `HarnessPart`); `M import-netlist p7 gyro.net --unit GYRO1 --dry-run` printed `J1: OK added GYRO1-J1 (5 signal pin(s))` and `Signals that match no interface type ...: CANGND: GYRO1-J1 pin 5`. The unit and the part had to be written by hand first.
8. **Pictures.** `MainWindow` on a copy of the `flatsat` example, Expert mode, `widget.grab()` for each dock, menu and dialog; the run printed `units 23 connectors 109 parts 28 types 17`.

Next: the owner's decisions in section 6, then the first build step (CD-B1).

## Owner decisions (14 October 2026)

The owner approved building the custom device editor (CD-B1 to CD-B7 of section 5.11) and decided the open questions of section 6 as follows.

| ID | Decision | What it means for the build |
|---|---|---|
| CD-Q6 | Close the lock hole (CD-G15) **only in the new editor's planners**. Do **not** change `check_locks` or any rule logic. | The planners refuse to change the pin set (ids and count) of a connector that a released cable connector mates with (`pin_set_frozen`). A hand edit or another caller of `History` is refused exactly as before. |
| CD-Q10 | **Yes**: the Devices view is a sixth main tab (Ctrl+6). | Plugged in through `MainWindow.install_view("devices", ...)`. |
| CD-Q1 | **No file-format change now.** Only the fields the model has today are used. | The pin columns that need a format change (description, remarks, own direction, voltage, current) are **not built**. They stay a documented future option (CD-B9, section 5.9). |
| CD-Q4 | The reusable device file (CD-B8) and format version 2 (CD-B9) are **not built now**. | CD-C15 and CD-J5 stay in the proposal as future options. |

Not decided by the owner, so the default of the proposal stands:

| ID | Default that stands |
|---|---|
| CD-Q2 | No separate "pinout reviewed" state. |
| CD-Q3 | The GUI keeps refusing two interfaces on one connector; `connector_compat` is not changed. |
| CD-Q5 | A part made in the editor is always `pending` and `unverified`; the tool never approves. |
| CD-Q7 | Pinout checks are inline notes only; no new design rule, the rule count stays 34. |
| CD-Q8 | The commands `import-pinout` and `export-pinout` are added and documented. |
| CD-Q9 | The pin id rule stays (`[A-Za-z0-9_.-]`, 16 characters); gender stays derived from the part, with an explicit edit of the connector's gender field only where the model already has it. |
| CD-Q11 | No connector face drawing. |

## Build status (14 October 2026)

What was built of the proposal, in the order of section 5.11, each as a small branch that left the whole program working. Nothing in the file format, the design rules (the count is still 34), the generator or the outputs was changed; `check_locks` is unchanged (CD-Q6). "Partly" says what is missing.

| ID | What | Status | Where |
|---|---|---|---|
| CD-B1 | Core: connectors, pins, checks | done | `core/devices.py`, `tests/test_edit_device.py` |
| CD-B2 | Core: lock hardening in the planners, `device_state` | done | `core/devices.py` (`pin_set_frozen`, `pin_lock_reason`, `device_state`) |
| CD-B3 | Devices tab, read only (Ctrl+6) | done | `gui/devices_view.py`, `tests/test_ux_devices.py` |
| CD-B4 | Devices tab, editing | done | `gui/devices_pin_table.py`, `gui/devices_view.py`, `tests/test_ux_devices_edit.py` |
| CD-B5 | Add device, from part, assign, parts, types | done | `gui/devices_dialogs.py`, `core/devices.py` |
| CD-B6 | Pinout import and the two commands | done | `core/pinout_import.py`, `cli/data.py`, `gui/import_kinds.py`, `gui/import_wizard.py` |
| CD-B7 | Docs | done, without the usability session | `docs/user-manual/define-a-device.md`, guide, cheatsheet, `CLI.md` |
| CD-B8 | Device file (export and import of a device) | not built (owner decision CD-Q4) | |
| CD-B9 | Format version 2 (description, remarks, direction, voltage, current, review state) | not built (owner decisions CD-Q1, CD-Q2) | |

| ID | Status | Note |
|---|---|---|
| CD-C1 | done | `ops_add_device`, `ops_update_device`, `default_subsystem` |
| CD-C2 | done | `ops_add_connector`, `next_connector_name` |
| CD-C3 | done | `ops_update_connector`, `plan_change_part`, `ops_change_part` (fixes CD-G5; the old `ops_set_connector_part` is unchanged, the Inspector's picker now uses `ops_change_part`), `connector_delete_impact`, `ops_delete_connector` |
| CD-C4 | done | `ops_set_pin` (also `mode`) |
| CD-C5 | done | `ops_add_pins`, `ops_delete_pins`, `ops_rename_pin`, `pin_impact` |
| CD-C6 | done | `ops_set_pinout`, `plan_pin_rows`, `ops_paste_rows`, `rows_from_grid` |
| CD-C7 | done | `ops_assign_pins`, `ops_unassign_pins` |
| CD-C8 | done | `suggest_carries`, `fill_from_type` |
| CD-C9 | done | `ops_add_part`, `ops_add_part_pair`, `ops_update_part` (never `approved`) |
| CD-C10 | done | `ops_add_interface_type`, `ops_update_interface_type`, `parse_signal_lines` (always `unverified`) |
| CD-C11 | done | `pinout_table` (`box_pinouts` filtered), `pin_rows` |
| CD-C12 | done | `plan_pinout_import` in `core/pinout_import.py` |
| CD-C13 | done | `pin_set_frozen`, `pin_lock_reason`, `device_state` |
| CD-C14 | done | `pinout_problems` |
| CD-C15 | not built | owner decision CD-Q4 |
| CD-J1 | done | with the keyboard; the part picker is on the left of the connector list, Ctrl+Shift+C goes to it while the connector list has the focus (in the pin table the same keys copy with the header row) |
| CD-J2 | done | four-page wizard and `import-pinout`; a sheet is one undo step; the unstored columns are named |
| CD-J3 | partly | (a) "+ From part" is the part picker of "Add connector"; (b) Ctrl+D; (c) New part with its mating half; (d) copy and paste of pin rows between devices work through the clipboard |
| CD-J4 | done | |
| CD-J5 | not built | owner decision CD-Q4 |
| CD-J6 | done | the preview and Export pinout, and `export-pinout` |
| CD-S1 to CD-S7 | done, except "Export device…" | header, connector list, card, pin table, preview, notes, empty state |
| CD-K1 to CD-K8 | done | inline notes under the table; K8 and K5 only on a fixed pinout, as the engine reads it |
| CD-X1, CD-X2 | done | `tests/test_edit_device.py` (a Hypothesis run of random edits with undo and redo) |
| CD-X3 | done | the same file: the hole in `check_locks` is shown and closed in the planner, `device_state` for the four states |
| CD-X4 | done | `tests/test_device_equivalence.py`, fixture `tests/fixtures/projects/custom_device` |
| CD-X5 | done | `tests/test_pinout_import.py`, `tests/test_pinout_cli.py` |
| CD-X6 | done | each check with a positive and a quiet case |
| CD-X7 | partly | keyboard journeys, names, tab order, read-only, released, empty, 1280 x 720, 1000 pins, light and dark for the read-only view; the editor is drawn in the light theme only |
| CD-X8 | done | one cell edit under 100 ms at 1000 pins and 100 units, in the planner and in the view |
| CD-X9 | done | guide, cheatsheet, `CLI.md` (`import-pinout`, `export-pinout`), links |
| CD-X10 | **open** | the usability session with six people (three electrical, three AIT) needs people; nothing here was observed on a real screen by a user. Use `tools.usability_setup` with the journeys CD-J1 and CD-J2 |

**Later changes (the table above stays as it was on 14 October).** The device file that CD-B8, CD-C15 and CD-J5 proposed and CD-Q4 set aside was built afterwards, in 1.4.0, as the *device library file* (`core/device_library.py`, the buttons *Save to library…* and *Add from library…* of the Devices tab, `export-devices` and `import-devices`; D-165; the format is in [`FILE_FORMAT.md`](FILE_FORMAT.md), "Device library file"). CD-B9 (format version 2) was not built: the schema version is still 1, and the optional pin fields that were added later (a function, 1.4.0; a cable contact part, 1.7.0) are left out of the files while empty. The design rules number 35 since 1.4.0 (`pin-shared`), not 34; they number 39 once links exist (`link-unpaired` and three more).

Deviations and things to know: the connector part of a new device is chosen from the library before pins exist (no "device from a pinout" page without a part); the Add menu entry is **Device…** under **Edit > Add unit**; a part change in the Devices tab asks on one line, in the Inspector it is applied at once; the diagram does not move the units below a device that grew (use **Arrange diagram**).
