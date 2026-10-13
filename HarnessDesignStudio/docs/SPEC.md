# Spacecraft Harness Design Tool: Specification

> Source of truth for the project. Decisions that resolve open questions live in `DECISIONS.md`.

## Part 1: Role, context and constraints

### Working mode
Senior software engineer building a desktop application for spacecraft electrical harness design. Read this file completely, ask clarifying questions in one batch, propose an architecture and milestone plan. Where the spec is silent, choose the simplest option and record it in `docs/DECISIONS.md` with a one-line rationale. Where the spec is ambiguous in a way that affects the data model or file format, stop and ask.

### Product goal
A fully offline desktop tool in which a user draws a system block diagram (units, their connectors and the interfaces between them). The tool derives every physical harness needed to realise those connections and produces a complete, clear, visually polished harness plan for each one. Usable by systems and software engineers, not only electrical engineers. Excellent, foolproof UX is a primary requirement, equal in priority to correctness of generated harnesses. Reliability and robustness have the same priority: the tool documents flight hardware and a silent error in a wire list is unacceptable.

### Users
- **Systems engineers** define units, interfaces and connectivity logically. Never forced to pick pins or wire gauges.
- **Software engineers** see which data buses and discrete signals reach which unit and connector, with clear signal names.
- **Electrical/harness engineers** refine physical details: connector types, pin allocation, wire types, shielding, splices, lengths; release drawings for manufacturing.
- **Reviewers and AIT staff** read outputs, check them against the design, use them for integration and continuity/isolation testing.

### Hard constraints
1. **Completely offline.** No network calls of any kind: no telemetry, analytics, crash upload, update check, licence check, CDN fonts, map tiles or remote schemas. All fonts, icons and libraries bundled. Automated test fails if any networking module is imported or a socket is opened at runtime.
2. **Runs on locked-down workstations** without admin rights and internet. Self-contained installer or portable build. *Now: Ubuntu 24.04 and newer only (D-110, D-127); the original list was Windows 10/11, RHEL/Rocky 8+ and Ubuntu LTS.*
3. **Only permissively licensed or LGPL dependencies** allowing closed internal use. SBOM (CycloneDX or SPDX) and licence report with every release. Pin all versions; reproducible builds from a vendored or mirrored package set.
4. **Sensitive data.** Project files may contain export-controlled information. Never write project content to logs, temp files outside the project folder, or crash dumps. Logs stay local and contain no design data by default.
5. **Data is the source of truth, drawings are generated.** Users edit the model and regenerate.
6. **Human-readable, diffable file format.** Plain text (JSON or YAML), stable key ordering and stable IDs, split into several files where it helps Git merges. Schema version and migration path.
7. **Units:** SI throughout (mm, m, g, kg, A, V, °C). Wire sizes in AWG with mm² alongside.
8. **Language:** UI and outputs in English. All UI strings in one place for later translation.

## Part 2: Data model and harness generation

### Data model (two layers)
Logical layer and physical layer, linked so every physical item traces back to a logical one.

**Logical layer**
- **Unit:** ID, name, subsystem, location/zone, nominal or redundant side, mass-relevant flag, notes.
- **Interface type:** *(baseline since D-130: RS-422, RS-485 and CAN for communication, Ethernet for high data rates, Micro-D connectors, SMA for RF)* reusable template: power (primary, secondary), RS-422/RS-485, SpaceWire, CAN, MIL-STD-1553B, LVDS, I²C, analog, thermistor, heater, discrete/bilevel, pyro, RF coax, ground/chassis. Defines signals (e.g. SpaceWire = 4 differential pairs, Data/Strobe in/out), required wire construction (twisted pair, twisted shielded pair, quad, coax), impedance, shielding and grounding rules, EMC class, default gauge.
- **Interface instance:** connection between two (or more, for buses) units using one interface type, with name, direction, nominal/redundant flag, max current, voltage, optional requirement ID.

**Physical layer**
- **Connector:** belongs to a unit (box connector, J) or a harness (cable connector, P). References a library part. Gender, shell size, keying/polarisation, contact arrangement, per-contact current rating.
- **Pin/contact:** signal assignment, contact size, crimp or solder type, locked flag for manual allocations.
- **Wire:** ID, signal, gauge, type, colour or marking, insulation, from-pin, to-pin, length, mass per metre from library.
- **Cable/bundle element:** twisted pairs, shielded groups, overall shields, including shield termination (360° backshell, pigtail to pin, floating) at each end.
- **Harness:** set of wires and cable connectors with ID, name, revision, routing segments, branch points, total length and computed mass.
- **Splice, in-line connector, feedthrough/bulkhead, test connector** are first-class objects.

**Parts library:** separate, versioned, editable library of connectors, contacts, backshells, wires, sleeving, labels. Each part has manufacturer, part number, specification (e.g. ESCC or MIL), approval status (approved/pending/not approved), mass and ratings. Ship a starter library of common space connectors (D-sub, micro-D, MDM, MIL-DTL-38999-style circular, SMA/TNC coax) clearly marked as unverified example data.

### Block diagram editor
- Drag units from a palette onto a canvas, add connectors to units, draw interfaces between units by picking an interface type.
- Units grouped by zone or panel; nominal vs redundant chains in clearly different visual styles.
- Multi-drop buses, power distribution from one source to many loads, hierarchical diagrams (subsystem view expands into units).
- Alternate table view of all interfaces (ICD-style spreadsheet) in sync with the canvas.
- Import units and interfaces from CSV/XLSX using a column-mapping dialog.

### Harness generation
Deterministic: same input always produces the same output, IDs and pin allocation, so a small change gives a small diff.
1. **Segmentation.** Default: one harness per pair of unit connectors, merged when both ends share a routing zone and merge rules allow. User can override grouping, split harnesses, insert in-line connectors at panel breaks, hinge lines, separation planes, test points. All rules configurable per project.
2. **Segregation rules** block or warn when harnesses or connectors mix forbidden categories: nominal with redundant; power with sensitive analog or data; pyro with anything else; EMC classes per the project's grounding and EMC concept. Redundant chains never share a connector or harness.
3. **Pin allocation.** Automatic, respecting: contact current rating with derating; required spare pins (configurable, e.g. 10%); differential pairs on adjacent pins; power and return pins grouped; separation between power and signal pins; shield and chassis pins; user-locked pins never moved. Report why each rule-driven placement was chosen.
4. **Wire sizing.** Gauge from current, length, allowed voltage drop and derating (per-wire, bundle, temperature). Derating values from a project table (ECSS-Q-ST-30-11 or program rules). Never hard-code a standard's numbers.
5. **Lengths and mass.** From user-entered routing segments (point-to-point with branch points) plus per-end service loops. Optional import from CAD CSV. Mass per harness from wires, connectors, backshells, shielding, sleeving, tie-downs, with configurable margin.
6. **Mis-mating prevention.** Warn when two connectors on the same unit, or two in-line connectors in the same zone, have identical type, size, gender and keying.
7. **Naming.** Configurable schemes for harnesses (`W101`), connectors (`J1`/`P1` or `UNIT-J01`), wires. IDs stable once released, never silently renumbered.

## Part 3: Validation, outputs and usability

### Design rule check (DRC)
Runs continuously in the background and on demand. Each finding: severity (error, warning, info), plain-language message a non-EE understands, link selecting the offending object, suggested fix. Warnings can be waived with mandatory justification, saved and shown in reports. At least:
- Unassigned signals, unused or floating pins, duplicate IDs, dangling wires.
- Gender or connector-type mismatch between mating halves.
- Driver-to-driver or receiver-only connections on data interfaces.
- Current above contact or wire rating after derating; voltage drop above limit.
- Missing or inconsistent shield termination; shield grounded at the wrong end per grounding concept.
- Segregation violations (nominal/redundant, power/signal, pyro, EMC class).
- Identical connectors at risk of mis-mating.
- Parts not approved in the project parts list.
- Logical/physical model inconsistencies.

### Outputs per harness
All generated from the model, with title block: project, harness ID, title, revision, date, author, checker, approver, sheet number, status (draft, in review, released). PDF (vector, A4 and A3, multi-sheet) and SVG; tables also CSV and XLSX.
1. **Harness drawing:** connectors with pin faces or pin tables, wires with IDs, gauges, colours, twisted pairs and shields with standard symbols, splices, branch points, segment lengths, labels, notes.
2. **Wire list (from-to):** wire ID, signal, from connector/pin, to connector/pin, gauge, type, colour, length, shield group.
3. **Connector pinout tables** for every box and cable connector, including spares.
4. **BOM** with part numbers, quantities, approval status.
5. **Mass and length report** per harness and system totals, with margin.
6. **Test tables:** continuity and insulation/isolation lists from the wire list.
7. **Label list** for wire and connector markers.
8. **DRC report** including waived findings and justifications.

System-level outputs: block diagram, harness overview diagram (coloured by nominal/redundant), connector mating matrix, interface-to-harness traceability matrix, complete revision diff report. Also export to WireViz YAML per harness and to a documented JSON format.

### Visual design
- Clean, modern, high-contrast, suitable for screen and black-and-white print; colour never the only carrier of meaning.
- One visual language across editor and outputs: unit shapes, connector symbols, signal-category colours (power, data, analog, RF, pyro), nominal solid / redundant dashed.
- Automatic readable harness drawing layout with minimal crossings; user nudges persist.
- Light and dark editor themes; outputs always print theme.
- Smooth zoom/pan, minimap, search for any ID.

### UX and UI design (top priority)
The tool succeeds only if a systems engineer who has never seen it can produce a correct, reviewable harness plan without training, and an expert finds it faster than current tools.

**Measurable targets**
- First-time systems engineer, using only in-app guidance, builds a 5-unit block diagram and generates its harness plans in under 15 minutes.
- Core tasks at least 90% success in usability tests; SUS at least 80.
- No core task requires the manual.
- No crash, power loss or wrong click loses more than the last few seconds of work.

**Foolproof: prevent errors**
- Only valid actions possible. When drawing an interface, compatible connectors highlight; incompatible ones are greyed out with a tooltip explaining why.
- Pick from lists wherever possible. Free text validated as typed (ID format, duplicates, units).
- Sensible defaults, every auto-filled value visibly marked until a person confirms it.
- Destructive actions (deleting a connected unit, regenerating over manual edits, releasing a harness) first show exactly what is affected, and are undoable. Released items are locked.
- Regeneration never silently discards manual overrides; it shows what it kept and changed.
- Unlimited undo/redo, autosave, crash recovery, automatic local snapshots.

**Helpful: guide the user**
- First run opens a sample project and offers a skippable, replayable interactive tour.
- Empty states explain the next step.
- Project status panel works as a clickable to-do list.
- Every DRC message states what is wrong, why it matters, how to fix it, with one-click fix where possible.
- An "Explain" action on any generated item: why this harness, why this pin, why this gauge.
- Plain-language labels with the domain term in a tooltip; built-in glossary.
- Offline contextual help from every dialog and panel.
- **Guided mode** (logical layer only, physical details auto-filled and marked unreviewed) and **expert mode** (all physical details). Switching modes never changes data.

**Useful: fast for experts**
- Command palette (Ctrl+K) for every action, global search by ID or name.
- Keyboard shortcuts, multi-select, bulk edit, copy/paste of units with connectors.
- One-step redundant chain creation from a nominal one, with mirrored naming.
- Canvas and table views always in sync.
- Cross-highlighting of a wire, signal or connector across block diagram, harness drawing, wire list and pinout.
- Live preview of the harness drawing while editing.
- Project and interface templates.

**Visual design system**
- Defined before building screens: colour tokens, typography scale, 4/8 px grid, one bundled icon set, reusable components. Used everywhere including outputs.
- Calm layout: canvas centre, palette left, properties right, problems and status bottom. Collapsible panels, progressive disclosure.
- Distinct visual states: selected, hover, error, warning, auto-filled, locked, released.
- Consistent terminology everywhere.

**Accessibility and responsiveness**
- WCAG 2.2 AA contrast, colour-blind-safe palette, full keyboard operation, UI scaling 100% to 200%, high-DPI and multi-monitor correct.
- Feedback within 100 ms; progress indicator for anything over 1 s; long operations in background, cancellable, never freeze the UI.
- Performance: at least 200 units, 2,000 interfaces, 150 harnesses, 20,000 wires stay responsive (interactive edits under 100 ms, full regeneration under 10 s on a typical engineering laptop).

**UX process**
1. Before any GUI, write `docs/UX.md`: personas, 10 most important user journeys, information architecture, wireframes (SVG or ASCII), design system.
2. Build a clickable prototype of the main journeys for review before the full editor.
3. After each milestone, walk every journey, render screenshots of each screen (e.g. Qt offscreen), list UX issues; fix high-severity ones before moving on.
4. Usability tests with 3 to 5 real users per persona; findings are priority bugs.
5. When UX and implementation convenience conflict, choose UX and state the cost.

## Part 4: Architecture, quality and process

### Change management and collaboration
- Projects live in a folder that works well under Git.
- Each harness has a revision and status. Releasing freezes IDs and creates a baseline snapshot.
- Built-in visual diff between any two baselines or working state vs baseline: added, removed, changed units, interfaces, pins, wires, as list and highlighted on diagrams.
- Per-harness change log: what, who, why (short mandatory comment on release).
- No server. Several people work on different subsystems as separate files that merge cleanly.

### Architecture
- **Headless core** (data model, file I/O, generation, DRC, output generators) separate from the **GUI**. Core has no GUI or network imports.
- **CLI** exposes the core: `harness validate project/`, `harness export project/ --all`.
- Generation rules, derating tables, naming schemes, segregation rules in **project configuration files**, not code.
- Propose the stack with a short comparison of two or three options, justified against hard constraints. Strong default: Python with PySide6 (Qt, LGPL), pure-Python core, PyInstaller or similar for offline packaging.
- PDF and SVG rendering use only bundled components and fonts.

### Reliability and robustness (top priority)
Outputs are used to build and test flight hardware. When in doubt the tool must refuse, warn or stop rather than produce a plausible but wrong output.

**Correct outputs, verified independently**
- Independent **output verifier**, a separate code path from the generator, reading generated wire lists, pinouts, BOMs and drawing data back and checking against the model. Every logical signal appears end to end exactly once, both ends of every wire agree with pinout tables, BOM quantities match drawings, no pin used twice.
- Verifier runs after every generation and before any release. Release impossible while it reports errors.
- Every output carries generator version and a hash of the model state.
- **Stale-output detection:** outputs flagged outdated everywhere when the model changes; cannot be released.
- Deterministic generation, reproducible on any machine.

**Data integrity**
- Atomic saves (temp file, flush, rename); keep previous version as backup.
- Validate schema and referential integrity on every load and save.
- Corrupt files open in **recovery mode** showing what is wrong and salvaging the rest. Never crash on bad files, never silently drop data.
- Lossless schema migrations, keep original file, tested against fixtures of every previous version.
- Files from a newer tool version open read-only with a clear warning.
- Detect same project open twice and on-disk changes (e.g. Git pull); offer safe reload.
- `harness check` detects inconsistent states after Git merges.

**Robust against bad input and failures**
- All model changes are transactions with consistent undo history.
- Imports (CSV/XLSX, parts library, CAD lengths) show preview and per-row error report before changing anything; applied as one undoable step.
- Handle full disks, read-only folders, unreliable network drives, permission errors, Unicode and special characters, long Windows paths.
- No unhandled exception crashes the app. Global handler saves a recovery snapshot, shows a plain-language message, writes a local log without design data.
- Cancelling a long operation leaves no partial results.
- Invariant checks after every transaction in debug builds, and on demand via "Verify project" in release builds.

**Testing for reliability**
- At least 90% line coverage in the core; positive and negative tests for 100% of DRC and generation rules.
- Fuzz and property-based tests for the file loader, importers and generation engine.
- Automated **soak test**: thousands of random edits, undo/redo, saves, reloads, with invariant and verifier checks after each step.
- End-to-end GUI tests of main journeys (pytest-qt).
- Every fixed bug gets a regression test.
- CI runs the full suite on every target OS.
- Written release checklist: tests green, verifier clean on all reference projects, SBOM and licence report, version stamped.

**Engineering practice**
- Strict static typing, explicit error types, no silently swallowed exceptions.
- Core functions validate inputs and fail loudly.
- Semantic versioning, changelog per release, tool version stored in every project file.
- Ask early whether the tool needs formal qualification (ECSS-E-ST-40C, ECSS-Q-ST-80C); if so keep requirements, design, tests and traceability in a supporting form from the start.

### Quality
- Unit tests for data model, every DRC rule, pin allocator, wire sizing.
- Property-based tests: generation deterministic; regenerating an unchanged model produces byte-identical files.
- Golden-file tests for every output type on at least three reference projects: minimal 3-unit; realistic small satellite (~15 units, nominal/redundant OBC, PCDU, battery, solar array, payload, transceiver, AOCS sensors and actuators, heaters, thermistors); stress project at performance target size.
- Offline test runs in CI.
- Static typing and linting in CI; no warnings on main.
- Short user guide (Markdown, also bundled as offline HTML or PDF) with guided-mode and expert-mode walkthroughs, plus developer docs for file format and rule configuration.

### Milestones (detailed plan in `docs/PLAN.md`)
M0 Foundation; M1 Model and files; M2 Block diagram (UX.md and prototype reviewed first); M3 Generation; M4 DRC; M5 Outputs; M6 Change control; M7 Polish.

### Rules while working
- Never add a dependency needing network at runtime; list every new dependency with licence in `docs/DECISIONS.md`.
- Never invent numerical values from standards (derating, current ratings, mass). Use clearly labelled placeholders in configuration and tell the owner which need an engineer.
- Keep `CLAUDE.md` updated with build, test, run commands and conventions.
- At the end of each session summarise: done, tested, next, UX targets met or open.

## Open decisions
See `DECISIONS.md` for how each was resolved or defaulted.
