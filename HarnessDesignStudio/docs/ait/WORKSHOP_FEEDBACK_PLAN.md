# Plan for the workshop feedback (October 2026)

**Status (2026-10-25).** Feedback received on 2026-10-23 from a workshop with a systems engineer, an AIT engineer and an electrical engineer. The investigation of what version 1.7.0 does today is done (below). The owner answered the four decisions on 2026-10-25 (section *Decisions of the owner*); milestone M1 is built (below, *M1 as built*); M2 to M5 are not built.

## The feedback, in the owner's words, grouped

| # | Point | Theme |
| --- | --- | --- |
| 1 | all new devices are automatically named DEV, that is not good, they should have their own name | A |
| 2 | change the name of "units" to "devices" | A |
| 3 | the "problems" notification is annoying | A |
| 4 | export not working due to file not being loaded | A |
| 5 | what is RTN (maybe ground?) | A |
| 6 | should be able to edit the connector | B |
| 7 | there should be more editing of the harness itself (like twisting the cables, etc.) | B |
| 8 | more harness features (like add length, gauge, etc.) | B |
| 9 | visually should be able to see the connector also on the harness itself, when in diagram view | B |
| 10 | signal, but what about power on the pins? | B/C |
| 11 | connection between devices is constrained by signal type but the user needs to be able to connect with custom harnesses as well; select a specific connector on one device and connect it with a specifically selected connector of another device; currently not allowed without a signal type; take inspiration from Pickering interfaces | C |
| 12 | if there are two devices and their pins are already labelled, the tool should automatically create the correct pinout/harness/interface | C |
| 13 | every connector should be connectable to every other connector, but every pin must be correctly assigned to its counterpart | C |
| 14 | the tool should not make the connections for you; the user creates them and the tool checks and reviews them | C |
| 15 | the tool created a pinout itself instead of looking at what the user created; the user's pinout was disregarded | C |
| 16 | the user should not include interfaces themselves; they should be created from the user's input in the pinout | C |
| 17 | subsystems should be in a library, not visible in a blank project | D |
| 18 | a separate library interface that opens a new window (still too much in one window) | D |
| 19 | the library should be accessible to everyone (for example via "kladow") | D |
| 20 | instead of a nominal chain and a redundant chain, give the number of those devices | D |
| 21 | feed Sam's tool into Claude | D? |
| 22 | the tool is too overcrowded; the user feels overwhelmed too fast; they want to create harnesses simply and quickly | E |
| 23 | two user modes: one for systems engineers, one for electrical/AIT engineers | E |

Themes: **A** small fixes, **B** harness and connector editing, **C** the connection model, **D** library and redundancy, **E** modes and overload.

## What 1.7.0 does today (from the code)

**A.** *Naming:* "Add a device" opens no dialog; it makes `DEV1`, `DEV2`, … named "Device n" and the person overwrites the name in the Devices tab (`gui/main_window.py` `add_device_flow`, `core/devices.py` `ops_add_device`). The ID cannot be chosen in the app. *Units:* the interface already mixes "unit" and "device"; the word "unit" is on about 107 lines of `gui/strings.py`, in the CLI (`--unit`), in about 1,150 places of the documents and in the file format (`Unit`, `units`, `logical/units/<subsystem>.json`), which must stay. *Problems:* unrequested signals are the status-bar button *Problems (n)* (Full only), the inspector tab *Problems (n)*, the top-bar chip, the banners (out of date, locked), the diagram corner chip and the badges on cards and links; the Simple workspace hides only the button, the count and the pending link; there is no switch "problems only when I ask". *Export:* the dialog always opens and disables *Export* with an inline notice when the project is read-only, has damaged files (`recovered`, the text "could not be loaded"), has no folder (the in-memory sample or an unsaved project) or no harness; the most plausible causes of the report are the unsaved sample or a project with damaged files; the note on the Next step page says "You will choose a folder", but the dialog has no folder chooser; the Harness-tab Export button is greyed out with the reason only in its tooltip. *RTN:* only a signal name used as data (return of `PWR`, of `SIG`); the glossary says it in one line.

**B.** Wires: gauge, type, colour, length, label, note, strip lengths are editable, in bulk for the selected wires (not "all wires of the harness", except the strip lengths). Groups: twisted pair, shielded pair, quad, coax, overall shield; a group can be made and removed, not changed (kind, ends). Cable connectors of a harness a person made: part, label and four pin fields; **not** the part, gender, keying or pin set after creation; a generated harness gets its connectors from the device. The Diagram draws devices and links; connector pictures appear on the device card (Guided) or as port rows (Expert); a link ends at the device or at the port row, with no connector at the link end and no harness path; the Harness tab draws the connectors, pins and wires.

**C.** A link (`InterfaceInstance`) needs a signal type and two endpoints; a connector-to-connector link without a type does not exist. Generate allocates pins from the type's signals. A person's pinout is used by Generate only when the pins are **fixed** (found by name) or **assigned to an interface**; a pin that only has a typed signal is reserved and kept, but the allocator puts the interface's signals on other free pins, so the person's pinout is effectively disregarded. Nothing compares two devices' pin labels or builds a link from them. There is no "check only" mode; integrity rules cover a manual harness (dangling wires, shared pins, mating mismatch, shields), several design rules do nothing for wires without an interface, and no rule compares the signal across a link. A pin has no power or return flag: "power" means the signal belongs to a power-category type; the return gap is a Generate setting checked only on pins that carry an interface.

**D.** The device library is a plain file (`harness-device-library`, buttons *Save to library…* and *Add from library…*, `export-devices`/`import-devices`); there is no managed library, no library window and no subsystem entity (`Unit.subsystem` is a free-text field). The tool is offline by design (a test forbids network code), so a shared library today means a shared file or folder. Redundancy is a mirrored second device `-R` with mirrored links; there is no quantity.

**E.** Rail of 8 (7 in Simple), top bar of 15 items, three docks in Full; the only modes are Guided/Expert (diagram detail) and Simple/Full (workspace). A role does not exist; the places that decide what is shown are `areas.py`, `MainWindow._show_area`, `_apply_workspace` and the sub-tabs of the docks, which are not filtered anywhere. There is one top-level window; every dialog is modal; the controller is shared, so a second non-modal window with the Devices view is feasible but needs the main window's flows re-wired.

## Proposed milestones (order to be confirmed by the owner)

1. **M1, quick fixes (no model change).** A new device asks for its name (and an ID that can be edited) before it exists; the word "unit" becomes "device" in the interface, the help of the command line (`--device` as an alias of `--unit`) and the documents, the file format unchanged; a switch *Problems only when I ask* (menu action, Settings, per workspace) that silences the top-bar chip, the corner chip, the banners that are not errors and the badges, while the Checks area and the Check button keep working; export: the dialog offers *Save project…* first for the sample, the notice says which file is damaged, the Harness-tab button shows its reason beside it, the Next step note is corrected; RTN explained in the glossary and in the pin tooltip as "return (ground)". Needs from the owner: how the export failure was reached.
2. **M2, the pinout is the truth, the tool checks (the connection model).** See the decisions. A link between two connectors with a pin-by-pin map and no signal type; interfaces derived from the pinouts of the two devices; labelled pins on both devices give a proposed pairing that the person confirms; Generate keeps and uses the person's pinout as it is; a *Check my connections* review (no changes) with rules for the pairing: pin counterpart, signal and direction, power and return pairs, unconnected pins; power and return recognised on a pin.
3. **M3, harness and connector editing.** Edit a harness connector (part, gender, keying, pins), change a group's kind and ends, bulk edit of gauge, colour and length for all wires of a harness, connectors shown at the link ends in the Diagram and the harness path on request.
4. **M4, the library.** A library window (non-modal) with devices and subsystems (a set of devices with the links between them), a shared library folder that anyone can point to (a folder on a shared drive or in a repository; no network code in the tool), blank projects without subsystems; redundancy by number of devices.
5. **M5, roles.** A choice of role at the first start (systems engineer, electrical/AIT engineer) that decides rail, tabs and defaults.

## M1 as built (2026-10-25)

Milestone M1 is built on `master` and not released. What a person sees:

- **A new device asks for its name first (point 1).** *Edit > Add device > Device…* (Ctrl+Shift+N), the button of the empty diagram, the Next step button and the *Add device* tool of the Simple workspace open the dialog **Add device**: **Name** (required; hint *for example Star tracker*), **ID**, **Subsystem** (the subsystems of the project). The ID is suggested as soon as the name is typed: the first word, letters and digits, upper case, at most 8 characters, plus the first free number (*Star tracker* gives `STAR1`, then `STAR2`; *Gyro 3* gives `GYRO3`); it can be edited, and once edited it no longer follows the name. Reasons show under the fields (*A device needs a name.*, *A device needs an ID.*, *ID X is already used by another device.*), the button *Add device* stays off until the device can be added, and a note says *You can change the name, the ID and the subsystem later in the Devices tab.* The *New device…* of the pinout import wizard makes its ID from the name typed. The kinds of *Edit > Add device* (computer, power unit …) add a device at once as before.
- **The word device (point 2).** On screen, in the command line (`--device`; `--unit` is kept as another name) and in the documents *unit* is now *device*; the files keep `unit`. The left-panel tab *Units* is the **Device list**.
- **Show problem notices (point 3).** A check box in *View* (menu action `act-problem-notices`) and in *Settings > Editing*, stored per workspace; on by default in the Full workspace, off in the Simple workspace. Off hides the status-bar Problems button and count, the count on the inspector tab, the top-bar status chip, the diagram's corner chip, the problem, warning, pending and not-checked badges on the diagram, the pending-values link and the dismissible *out of date* banner. It never hides the read-only, locked, damaged-file and sample banners, the Check button and its result, the Checks area, the Problems panel (*View > Problems panel*, Ctrl+Shift+M), the Next step page and the error texts of dialogs: what explains why something cannot be done stays.
- **Export asks where to save first (point 4).** With harnesses and a project that has no folder yet (the sample held in memory, an unsaved project), Export (menu, top bar, Harness tab, Next step button, banner) first opens a folder chooser (*Choose an empty folder to save the project in. The files are then exported next to it*) and then the Export window opens on the new outputs folder. The damaged-files notice lists up to 5 file names (*and N more*). The Harness tab's Export button shows *Read-only: save a copy first* or *Asks where to save first* beside it. The Next step note says *Export first asks where to save the project.* How the failure of the workshop was reached is still not known; the two causes found in the code (the unsaved sample, damaged files) are now explained on screen.
- **RTN (point 5).** The pin cell of a signal named `RTN` has the tooltip *Return line: where the current of the signal comes back* (`GND`: *Ground*) in the Devices pin table and the Harness pin table; the glossary has the entry.

Open points of M1:

- The finding texts that reach a written output file still say *unit* (the cross-strap, isolated and look-alike findings and the descriptions of the design rules), because changing them would change generated files, which the rules below forbid.
- The left dock is 40 pixels wider than before, because the tab *Device list* is longer than *Units*.
- The tests of M1 are `tests/test_ui_new_device.py`, `tests/test_devices_new.py`, `tests/test_ui_problem_notices.py`, `tests/test_ui_export_flow.py` and `tests/test_pinout_cli.py`; the requirements are REQ-GUI-08, REQ-GUI-09, REQ-OUT-08 and REQ-GUI-10 in `docs/REQUIREMENTS.md`. The written files did not change (`python -m tools.output_hashes --check docs/ui/OUTPUT_HASHES_1.2.0.json`).

## Decisions of the owner (2026-10-25, decision D-172)

| # | Question | Answer |
| --- | --- | --- |
| 1 | The connection model | **Pinout first.** The person's pinout is the source of truth. A link joins two connectors pin by pin and needs no signal type. Interfaces are derived from the pinouts. Labelled pins on both devices give a proposed pairing that the person confirms. Generate keeps the pinout as it is. A review mode checks the connections and changes nothing. The interface-first way stays for projects that use it. |
| 2 | The order | **M1, M2, M3, M4, M5** as proposed. |
| 3 | The two roles | **The roles replace the Simple/Full workspace** of 1.7.0: a role chosen at the first start (systems engineer; electrical/AIT engineer), each a reduced workspace, with a switch that shows everything. |
| 4 | Sharing the library | **A shared folder or repository** that anyone points the tool at. The tool stays offline. |

Rules for all milestones: a field added to the model is optional and left out of the files while it is empty (so a project that does not use it keeps byte-identical files and outputs, proof `python -m tools.output_hashes --check docs/ui/OUTPUT_HASHES_1.2.0.json`); the file format stays compatible (`Unit`, `units`, `logical/units/` stay in the files even where the screen says *device*); generated files do not change because of a wording change in the interface; a decision that reverses D-10 or D-166 gets its own decision row when it is built.

## Not clear yet

"kladow" (what it is), "Sam's tool" (what it is and where the files are), and how the export failure was reached.
