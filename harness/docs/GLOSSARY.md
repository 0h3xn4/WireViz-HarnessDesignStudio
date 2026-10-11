# Glossary

This page explains, in plain words, the words you meet in this tool and in spacecraft harness engineering.

## Contents

- [How to read this page](#how-to-read-this-page)
- [Words that mean two things here](#words-that-mean-two-things-here)
- A to Z: [A](#a) [B](#b) [C](#c) [D](#d) [E](#e) [F](#f) [G](#g) [H](#h) [I](#i) [K](#k) [L](#l) [M](#m) [N](#n) [O](#o) [P](#p) [R](#r) [S](#s) [T](#t) [U](#u) [V](#v) [W](#w) [Z](#z)

## How to read this page

Each entry says how this tool uses the word. Engineering numbers are never given here: the tool contains none from any standard, and your programme decides them (see [`PLACEHOLDERS.md`](PLACEHOLDERS.md)). The shorter lists of the same words in the user guide ([`guide/USER_GUIDE.md`](guide/USER_GUIDE.md), section 15) and in the app (**Help > Glossary**) are small subsets of this page.

**The marker `(general meaning)`.** An entry that ends with ` (general meaning)` explains a word from general engineering knowledge: this repository does not define the word. A sentence in such an entry that says how this tool uses the word does come from the repository. An entry without the marker is defined by this repository (its documents or its program). The three entries AIT, ICD and NCR are standard terms that this repository does not define; they were added for readers new to spacecraft engineering, and an engineer should check them against your programme's wording.

## Words that mean two things here

Six words are used in more than one sense. The documents say which sense they mean; this table is the quick check.

| Word | First meaning | Second meaning |
| --- | --- | --- |
| **Waive** | A person accepts one *warning* of the design rule check and writes a reason of at least 10 characters. It stays in the report. Errors cannot be waived. | In the compliance documents, *waived by the owner* means the owner accepted a departure from a standard requirement or a process step (a *deviation*, `T-NN`). It does not mean the requirement is met. See [`../compliance/DEVIATIONS.md`](../compliance/DEVIATIONS.md). |
| **Baseline** | A frozen snapshot of a harness stored when it is released, for `harness diff` and the change log. | The set of connector and interface standards the starter library follows (Micro-D for power and data, RS-422, RS-485, CAN, Ethernet, SMA; decision D-130). See [`CONCEPTS.md`](CONCEPTS.md). |
| **Zone** | A place on the spacecraft such as a panel, deck or compartment (`panel-A`). Harnesses can be grouped by pair of zones (`per_zone_pair`). | The *lane* of the diagram that stands for that place; a unit's zone is the lane it sits in. The `flatsat` example has a lane called `bus` that holds the central units: it is not a *bus* (a link shared by several units). |
| **Bundle** | Wires that run together. The derating checks treat the wires of one harness as one bundle. | Some screens use *bundle* to mean the harness itself (the toolbar filter *By bundle (harness)*). |
| **Cable / harness** | A *harness* is the generated object with an ID such as `W001`. | *Cable* means the physical item: in the outputs, the wires of one connector pair. With the default grouping one harness is one cable between two connectors; other groupings put several cables in one harness. A *cable connector* is a connector on a harness. |
| **Release** | To freeze a harness: a person's name and a comment, a baseline and a change-log entry; afterwards it cannot be edited until a new revision is started. | A *release* of the tool itself (version `0.1.0`, a *release candidate* `rc`): see [`RELEASE.md`](RELEASE.md). |

## A

- **A3 and A4**: Standard paper sizes: A4 is the usual office sheet and A3 is twice as large. Each harness drawing is exported as a PDF in both sizes, and as SVG for A3 only. See [`OUTPUTS.md`](OUTPUTS.md). (general meaning)
- **Air-gapped**: A computer that is not connected to any network. The tool works on one once you have the package. See [`INSTALL.md`](INSTALL.md). (general meaning)
- **AIT**: Assembly, integration and test: the phase in which a spacecraft's parts are put together and tested on the ground. The harness outputs of this tool (wire list, pinouts, test tables) are meant to be used in it. Standard meaning, not defined by this repository: an engineer should check it against your programme's wording. (general meaning)
- **Ampacity**: How much current a wire of a given gauge may carry, in amperes. You supply it as a table of gauge against amperes (`ampacity_a_by_awg`, loaded with `harness config --ampacity-csv`); derating factors are then applied when a wire is sized. The table must not show a thinner wire carrying more. See [`CONFIG.md`](CONFIG.md), [`IMPORTS.md`](IMPORTS.md). (general meaning)
- **Analog signal**: A signal whose voltage varies continuously, for example the output of a sun sensor, as opposed to a digital or on/off signal. The starter type `Analog signal` has a signal pair `SIG+` and `SIG-`. See [`FAQ.md`](FAQ.md). (general meaning)
- **AOCS**: Attitude and orbit control: the part of a spacecraft that measures and changes its orientation (attitude) and path. In the flatsat the `aocs` lane holds the reaction wheels, star trackers, sun sensors and the magnetorquer. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **Approved parts list**: The list of connectors, wires and other parts your programme has approved. You import it with `harness import-parts` and say what each approval value in your file means; the tool never decides that a part is approved. A used part that is not approved gives a warning and blocks a release unless you give a written reason. See [`IMPORTS.md`](IMPORTS.md).
- **Auto-filled**: A connector the tool chose for you in Guided mode. It stays marked auto-filled until a person confirms it. See [`CONCEPTS.md`](CONCEPTS.md).
- **AWG**: American Wire Gauge, a standard way to give a wire's conductor size as a number. A higher AWG number is a thinner wire, so a wire that must carry more current needs a lower AWG number. In this tool's messages, 'a larger gauge' means a thicker wire, which is a lower AWG number. See [`CONFIG.md`](CONFIG.md). (general meaning)

## B

- **Backshell**: The cover at the back of a connector where the cable enters. A backshell can connect a cable's shield to the connector body all the way round (a '360 degree' connection). See [`CONFIG.md`](CONFIG.md). (general meaning)
- **Baseline**: A frozen snapshot of a harness stored when it is released, so the released state can always be compared with later changes (`baselines/` in the project; `harness diff` uses it). Not to be confused with the *baseline* of connector and interface standards (see *Words that mean two things here* at the top). See [`CONCEPTS.md`](CONCEPTS.md).
- **BOM**: Bill of materials: the list of parts a harness needs, with quantities and each part's approval status (`bom.csv`). Connectors are counted; wires are listed by the metres whose length is known. See [`OUTPUTS.md`](OUTPUTS.md). (general meaning)
- **Bonding**: Connecting a shield electrically to the connector housing and so to the structure (chassis). The rule `shield-bonding` expects a shield to be bonded at both ends through the connector. See [`RULES.md`](RULES.md). (general meaning)
- **Branch point**: A point inside a harness where the wire route splits into branches. Together with connectors, branch points are the end points of routing segments. See [`OUTPUTS.md`](OUTPUTS.md).
- **Bundle**: A group of wires that run together. The derating checks treat all wires of one harness as one bundle, and some screens use 'bundle' to mean the harness itself. See [`CONFIG.md`](CONFIG.md).
- **Bundle factor**: A factor of at most 1 that reduces a wire's allowed current because it runs in a bundle with other wires, which heat each other. You supply it as `bundle_derating`, or as a table of wire count against factor (K). A second table (L) for partly loaded bundles is recorded but not applied. See [`CONFIG.md`](CONFIG.md), [`RULES.md`](RULES.md).
- **Bus (multi-drop link)**: A link that joins more than two units on the same wires. The tool does not generate harnesses for such links yet and skips them with a warning (D-116). Not to be confused with the `bus` lane of the flatsat example, which holds the central units of the spacecraft. See [`FAQ.md`](FAQ.md). (general meaning)

## C

- **Cable**: The physical item a harness describes: in OUTPUTS, 'the wires of one connector pair'. With the default grouping one harness is one cable between two connectors; other groupings make one harness out of several. The 'cable connector' is the connector on the harness side. See [`OUTPUTS.md`](OUTPUTS.md), [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md).
- **CAN**: Controller Area Network, a two-wire data bus that several units can share (starter signals `CANH` and `CANL`). One of the three baseline communication types. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Category**: A grouping. Interface categories are power, data, analog, RF, pyro, discrete, thermal, ground and other; rules use them to keep unlike interfaces apart (the toolbar calls them signal classes). Part categories are connector, contact, backshell, wire, sleeving and label. See [`CONFIG.md`](CONFIG.md), [`IMPORTS.md`](IMPORTS.md).
- **Change control**: The practice of recording who released or changed a harness, when and why, so an earlier state can be recovered and compared. In this tool it consists of releases, baselines, revisions and the change log. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Change log**: The append-only list of review, release and new-revision events, each with the person, time and comment. Entries cannot be deleted. `harness log` prints it. See [`FILE_FORMAT.md`](FILE_FORMAT.md).
- **Checksum (SHA-256)**: A short fingerprint computed from a file's bytes. If the fingerprint of the file you downloaded equals the published one, the file was not changed. The packages are not signed, so the checksum is the only check you have. See [`INSTALL.md`](INSTALL.md). (general meaning)
- **CI**: Continuous integration: a server that runs a project's checks automatically on every change. The templates include a GitHub Actions workflow that runs the harness checks this way. See [`HOWTO.md`](HOWTO.md). (general meaning)
- **Circular connector**: A connector family with a round shell. The starter library has a 19-pin 'MIL-DTL-38999-style' example. Kept for projects that need it. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Coax**: Coaxial cable: a cable with a centre conductor inside an insulator and a shield, used for radio-frequency signals. The starter type `RF coax` uses it with SMA connectors. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Cold redundancy**: A backup that is switched off until it is needed. Wires in cold redundancy do not carry current at the same time as the main ones. The review checklist asks you to apply, by hand or with a written reason, the bundle factor for partly loaded bundles (L) when this is the case; the tool records that factor but does not apply it. See [`CONFIG.md`](CONFIG.md) and the [`design-review-checklist.md`](../src/harness_design_studio/resources/examples/templates/design-review-checklist.md) template. (general meaning)
- **Conductor resistivity**: How strongly the wire material resists current, in ohm metres (`conductor_resistivity_ohm_m`). It is needed to compute the voltage drop along a wire; you supply it. See [`CONFIG.md`](CONFIG.md). (general meaning)
- **Configuration files (config/*.json)**: The files in a project's `config/` folder that hold its rules and engineering values: `derating` (current and voltage limits and factors), `emc` (EMC classes and which must be kept apart), `generation` (settings used when harnesses are made, such as service loop and shield grounding), `segmentation` (how interfaces are grouped into harnesses), `segregation` (which kinds of wire must not share a harness), `titleblock` (fields on the drawing sheet) and `naming` (ID patterns). A file is a placeholder until an engineer has reviewed it. See [`CONFIG.md`](CONFIG.md), [`PLACEHOLDERS.md`](PLACEHOLDERS.md).
- **Connector**: A plug or socket. A box connector sits on a unit (IDs such as `RW1-J02`); a cable connector sits on a harness (IDs such as `W001-P2`) and mates with a box connector. See [`CONCEPTS.md`](CONCEPTS.md).
- **Connector saver**: An adapter fitted to a connector during equipment tests, so that the real connector is mated and unmated fewer times. A requirement the tool cannot check; it is on the [`design-review-checklist.md`](../src/harness_design_studio/resources/examples/templates/design-review-checklist.md) template. (general meaning)
- **Continuity test**: A test that a wire conducts from one end to the other. The test table gives the largest resistance accepted as continuous (`test_continuity_max_ohm`). See [`OUTPUTS.md`](OUTPUTS.md). (general meaning)
- **Coverage gate**: A rule that the tests must execute at least 90% of the lines of the core code. `pytest --cov` enforces it. See [`RELEASE.md`](RELEASE.md).
- **Cross-strap**: A connection between a nominal unit and a redundant one, which lets one failure reach both chains. The tool warns about it; the suggested fix is to connect to a redundant copy instead, or you can waive the warning with a reason. See [`RULES.md`](RULES.md). (general meaning)

## D

- **Decision ID (D-NN)**: A numbered entry in the decision log, for example `D-10`. Each records a decision and its reason. Four are still open in version 0.1.0: D-10 (harness boundary rule), D-11 (engineering values), D-12 (approved parts list) and D-15 (title block). See [`DECISIONS.md`](DECISIONS.md), [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md).
- **Derating**: Deliberately using a wire or contact below its maximum rating, by multiplying the rating by a factor of at most 1 (for example for bundling, temperature or how much of a contact's rating is used). The factors come from your programme or standard; the tool supplies none, and wire gauges stay *pending* without them. See [`CONFIG.md`](CONFIG.md), [`PLACEHOLDERS.md`](PLACEHOLDERS.md). (general meaning)
- **Design rule check (DRC)**: The automatic checks the tool runs on your design, such as unapproved parts, wires that carry too much current or connectors that could be mixed up. `harness drc` prints the report; in the app the results appear in the Problems tab. Each finding is an error (must be fixed), a warning (fix or waive) or a note. See [`RULES.md`](RULES.md), [`CONCEPTS.md`](CONCEPTS.md).
- **Deviation (T-NN)**: A recorded departure from a standard requirement or a planned process step. Each is listed with an ID such as `T-19` in the compliance folder. 'Waived by the owner' means the owner accepted the departure; it does not mean the requirement is met. See [`compliance/DEVIATIONS.md`](../compliance/DEVIATIONS.md).
- **Differential pair**: Two wires that carry one signal as the voltage difference between them (for example `TX+` and `TX-`), usually twisted together so noise affects both equally. RS-422 and LVDS signals are carried this way. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Discrete / bilevel signal**: A simple on/off line with two states (bilevel), such as a command or status flag. The starter type has a signal `SIG` and a return `RTN`. See [`FAQ.md`](FAQ.md). (general meaning)
- **D-sub**: A connector family with a D-shaped metal shell, drawn as a tapered D. Older D-sub parts stay in the starter library; Micro-D is the baseline. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **DXF**: A CAD drawing file format. Decision D-15 offers to use your own title-block frame supplied as an SVG, PDF or DXF file. See [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md). (general meaning)

## E

- **ECSS**: European Cooperation for Space Standardization: the family of European space engineering standards. The tool cites requirements of ECSS-Q-ST-30-11C and ECSS-E-ST-20-07C in some rules and can fill values from them on request (see Standard profile). It does not claim compliance with any standard. See [`CONFIG.md`](CONFIG.md), [`RULES.md`](RULES.md). (general meaning)
- **EE**: Electrical engineer. PLACEHOLDERS.md names an EE as the owner of several engineering values. See [`PLACEHOLDERS.md`](PLACEHOLDERS.md). (general meaning)
- **EGSE**: Electrical ground support equipment: test and checkout equipment that stays on the ground and never flies. In the flatsat example the `egse` lane holds the checkout system (`SCOE1`), the ground power supply (`GPSU1`) and the RF test equipment (`RFSU1`). See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **EMC**: Electromagnetic compatibility: equipment must work without disturbing nearby equipment through electrical noise, and without being disturbed by it. In this tool it appears as EMC classes and rules that keep noisy and sensitive wires in separate harnesses. See [`CONFIG.md`](CONFIG.md), [`RULES.md`](RULES.md). (general meaning)
- **EMC class**: A label you define for interface types so that rules can say which classes must not share a harness (`emc.json`). No classes are set until an EMC engineer supplies them. See [`CONFIG.md`](CONFIG.md).
- **Engineering values**: The numbers an engineer must decide: derating factors, wire current ratings, EMC rules, test limits, part masses and ratings. The tool contains none from any standard. Until you enter them, results are marked pending or not checked. See [`PLACEHOLDERS.md`](PLACEHOLDERS.md), [`CONFIG.md`](CONFIG.md).
- **EPPL and DCL**: Names of programme-specific approved-parts list formats that a future import could read. The repository does not spell them out; ask your parts engineer. See [`IMPORTS.md`](IMPORTS.md).
- **ESCC**: European Space Components Coordination, which publishes specifications for space electronic components. Rules cite `ESCC3901` for approved parts and wire specifications. See [`RULES.md`](RULES.md). (general meaning)
- **Ethernet and RJ45**: Ethernet is the baseline alternative for high data rates, for example a payload. RJ45 is the common eight-contact plug and jack used for it; the starter parts call it `RJ45 8P8C`. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Example parts (EX-...)**: Parts in the starter library with fictional part numbers that start with `EX-`. They are marked unverified and not approved. Your approved parts list replaces them. See [`PLACEHOLDERS.md`](PLACEHOLDERS.md), [`IMPORTS.md`](IMPORTS.md).
- **Export-controlled**: Information that law restricts sharing with certain people or countries. Project files may contain it, so the tool never writes project content to logs, temporary files outside the project, or crash dumps. See [`FILE_FORMAT.md`](FILE_FORMAT.md). (general meaning)

## F

- **Fixed pin**: A pin whose signal is defined by the unit itself (imported from KiCad). Generation connects an interface signal to the pin of the same name and never moves it. See [`KICAD.md`](KICAD.md).
- **Flatsat**: A spacecraft's electronics laid out on a bench and joined with test harnesses, so the software and electrical interfaces can be tested before the spacecraft is built. The `flatsat` example also contains the ground equipment that drives it. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **Flight and ground units**: A flight unit is part of the spacecraft that will fly (flight hardware: outputs are used to build it, so the tool refuses to guess). A ground unit is test or checkout equipment that stays on the ground. The tool does not know which is which, so totals include both. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md), [`RULES.md`](RULES.md). (general meaning)

## G

- **Gauge**: The size of a wire's conductor, given in AWG in this tool. A gauge stays *pending* until current, derating values and length are known, because it is chosen as the smallest conductor that carries the current after derating and keeps the voltage drop within the limit. See [`GETTING_STARTED.md`](GETTING_STARTED.md). (general meaning)
- **Gender**: Whether a connector has pins (male) or sockets (female). Mating halves must have opposite genders. The generator gives a cable connector the opposite gender of the unit (box) connector it mates with; in the examples the unit connectors are female and the cable connectors male. See [`CONCEPTS.md`](CONCEPTS.md), [`USER_GUIDE.md`](guide/USER_GUIDE.md). (general meaning)
- **Golden file**: A stored copy of an expected output. A test regenerates the output and compares it with the golden file; any difference fails the test. See [`RELEASE.md`](RELEASE.md). (general meaning)
- **Ground / chassis**: The starter type for a ground (reference) connection, with one `GND` signal. The chassis is the spacecraft's metal structure, used as the electrical reference. See [`FAQ.md`](FAQ.md). (general meaning)
- **Guided and Expert mode**: Guided mode (the default): you work with units and interfaces, and the tool chooses connectors and pins. Expert mode: you also see every connector and can choose the exact one for each end. Switching never changes data. See [`CONCEPTS.md`](CONCEPTS.md).

## H

- **Harness**: A bundle of wires with the connectors at their ends that carries signals and power between units. In this tool a harness is generated from your interfaces, never drawn by hand; it has an ID such as `W001`, a revision and a status (draft, in review or released). See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Harness boundary rule**: The rule that decides which interfaces share one harness. The default is one harness per pair of unit connectors; `config/segmentation.json` can group by pair of units or pair of zones instead. The owner has not yet confirmed a final rule (decision D-10). See [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md), [`CONFIG.md`](CONFIG.md).
- **Heater**: A heating element on the spacecraft, powered through a heater line (starter signals `HTR+` and `HTR-`). Heaters and thermistors together keep equipment within a suitable temperature range (thermal control). See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)

## I

- **I2C**: Inter-Integrated Circuit: a two-wire serial link, with a data signal (`SDA`) and a clock (`SCL`), over short distances. The starter type also has a `GND` signal. Not part of the baseline. See [`FAQ.md`](FAQ.md). (general meaning)
- **ICD**: Interface control document: the document that records what is connected between two units or systems and how (connectors, pins, signals). Your programme's ICD, if it has one, is outside this repository. This tool does not read or write an ICD; the interfaces you enter, or import from a table, are its own data. (The file `compliance/docs/ICD.md` describes this tool's own file and command-line interfaces and is a different document.) Standard meaning, not defined by this repository: an engineer should check it against your programme's wording. (general meaning)
- **IDs in the examples**: Default ID patterns: `W001` is a harness, `RW1-J02` a unit (box) connector, `W001-P2` a cable connector on a harness, `W001-001` a wire, `W001-L1` a routing segment, and `IF-001` an interface (you choose interface IDs). A `-R` suffix marks a redundant copy of a unit, for example `PCDU1-R`. See [`CONCEPTS.md`](CONCEPTS.md).
- **IEC 60757**: An international standard for colour codes: each colour has a short code, for example BK for black and RD for red. The tool draws wire colours with these codes as text, so a black-and-white print loses nothing. The tool defines no colours of its own: you assign them (Edit > Wire colours...). See [`OUTPUTS.md`](OUTPUTS.md), [`CONFIG.md`](CONFIG.md). (general meaning)
- **Independent review**: A review of the work by a person other than the one who made it. Version 0.1.0 has none; the owner waived it. See [`compliance/DEVIATIONS.md`](../compliance/DEVIATIONS.md). (general meaning)
- **In-line connector**: A connector placed along a harness rather than on a unit, for example where the harness crosses from one panel to another. See [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md). (general meaning)
- **Interface**: One required connection between two units, of a given interface type, for example RS-422 from the computer to a wheel. You add interfaces; the tool turns them into connectors, pins and wires. See [`CONCEPTS.md`](CONCEPTS.md).
- **Interface type**: A kind of connection and its signals, for example RS-422, CAN or primary power. Seventeen ship with the tool. Each lists its signal names, the wire construction it needs (such as twisted shielded pair) and a category. See [`CONCEPTS.md`](CONCEPTS.md), [`FILE_FORMAT.md`](FILE_FORMAT.md).
- **ISO 7200**: A standard for the data fields of a drawing's title block. Decision D-15 offers 'ISO 7200 style fields': owner, title, document number, revision, date, sheet, size, status and approvals. See [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md). (general meaning)
- **Isolation test**: A test that wires which should be separate do not conduct to each other. The test table gives the smallest insulation resistance accepted (`test_isolation_min_mohm`) and the test voltage (`test_isolation_voltage_v`). See [`OUTPUTS.md`](OUTPUTS.md). (general meaning)

## K

- **Keying**: A physical coding on a connector so that only the right mate fits. Look-alike connectors are identical connectors on one unit that could be swapped by mistake; the fix is different keying or a different insert. See [`RULES.md`](RULES.md). (general meaning)
- **KiCad**: The program used to design the electronics inside each unit. The tool uses it only as the source of each unit connector's pinout, read from a netlist. See [`KICAD.md`](KICAD.md). (general meaning)

## L

- **Lane**: See Zone.
- **Locked**: A wire or pin whose position, gauge, part, colour or length you set by hand and marked locked, so generation keeps it. A released harness is also locked ('frozen'): it, its interfaces and the pins it uses cannot be edited until you start a new revision. See [`CONCEPTS.md`](CONCEPTS.md).
- **Logical and physical**: The logical layer is what must be connected (units, interface types, interfaces). The physical layer is how it is built (connectors, pins, wires, harnesses). The project folder keeps them in `logical/` and `physical/`. See [`CONCEPTS.md`](CONCEPTS.md), [`FILE_FORMAT.md`](FILE_FORMAT.md).
- **LVDS**: Low-voltage differential signalling: a fast data link on a differential pair (starter signals `D+` and `D-`). Not part of the baseline. See [`FAQ.md`](FAQ.md). (general meaning)

## M

- **Magnetorquer**: An electromagnet coil that turns the spacecraft by pushing against the Earth's magnetic field, used to control orientation. In the flatsat example one unit holds the driver electronics for three coils. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **Mass margin**: A margin added to computed masses (`mass_margin_fraction`). Mass totals count only what is known and say what is missing. See [`CONFIG.md`](CONFIG.md).
- **Mate and mating**: To plug two connector halves together. Mating halves must fit: opposite gender, same pin count and keying. A cable connector mates with exactly one unit (box) connector. See [`RULES.md`](RULES.md). (general meaning)
- **Mating cycles**: The number of times a connector can be plugged and unplugged before it wears out. The tool compares the permitted number you supply with the part's rating. See [`RULES.md`](RULES.md). (general meaning)
- **Mating matrix**: A table of which cable connector mates with which unit (box) connector (`mating_matrix.csv`). See [`OUTPUTS.md`](OUTPUTS.md).
- **MDM**: An older connector family kept in the starter library for projects that need it. The repository does not spell the abbreviation out. See [`CONCEPTS.md`](CONCEPTS.md).
- **Micro-D**: A small D-shaped connector family (drawn as a rounded block). The baseline for power and data, in 9, 15, 21, 25 and 31 pin sizes: power uses the 9 pin size, and for data the size follows how many interface types the connector carries. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Milestones M0 to M7**: The build stages of the tool: M0 Foundation, M1 Model and files, M2 Block diagram, M3 Generation, M4 Design rule checks, M5 Outputs, M6 Change control, M7 Polish (later work is recorded as M8 and M9 in `docs/demos/`). Documents say 'needed by M3' or 'additions in M4' to mean the stage in which a value or file was introduced. See [`PLAN.md`](PLAN.md).
- **MIL-STD-1553B**: A military and aerospace data bus standard that several units can share, on a twisted shielded pair (starter signals `BUS+` and `BUS-`). Not part of the baseline. See [`FAQ.md`](FAQ.md). (general meaning)
- **Model hash**: A fingerprint (SHA-256) of the whole design. Every output file carries its first 12 characters, so a printed sheet can be traced to the exact design it came from. If the design changes, the hash changes and exported outputs are marked out of date. See [`CONCEPTS.md`](CONCEPTS.md), [`FILE_FORMAT.md`](FILE_FORMAT.md).
- **Multipactor**: A radio-frequency breakdown effect that can occur in vacuum and damage RF parts. The tool cannot check it; it needs an RF analysis outside the tool and is on the [`design-review-checklist.md`](../src/harness_design_studio/resources/examples/templates/design-review-checklist.md) template. (general meaning)

## N

- **NCR**: Non-conformance report: a record that something built, bought or delivered does not meet its requirement, kept so that it can be reviewed and closed. This repository does not define the abbreviation; its records say that problem reports are GitHub issues and that nonconformances are labelled and handled by the owner (deviation T-23 in [`../compliance/DEVIATIONS.md`](../compliance/DEVIATIONS.md)). Standard meaning, not defined by this repository: an engineer should check it against your programme's wording. (general meaning)
- **Net**: In a KiCad netlist, a named electrical connection between pins, for example `CAN_H`. The tool cleans net names and maps them to its own signal names with `--signal-map`; names that match nothing are listed, never guessed. See [`KICAD.md`](KICAD.md). (general meaning)
- **Netlist**: A file exported from KiCad that lists the components and which pins are joined by which nets. The tool reads it to learn which signal is on each pin of a unit's connectors. Both KiCad's default `.net` text form and the XML form work. See [`KICAD.md`](KICAD.md), [`HOWTO.md`](HOWTO.md). (general meaning)
- **Nominal and redundant**: The main chain of units (nominal) and its backup copy (redundant). They never share a connector or harness, so one failure cannot take out both. A redundant copy of a unit is named with `-R` (for example `PCDU1-R`). See [`CONCEPTS.md`](CONCEPTS.md).

## O

- **On-board computer (OBC)**: The spacecraft's main computer. Its unit ID in the examples is `OBC1`. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Owner**: The owner of the repository, who set this tool's requirements, answered its design questions and made its decisions (a few are still open: see Decision ID). Sign-offs and waivers of process steps in the compliance records are the owner's statements; no personal name is recorded. See [`../compliance/SIGNOFF.md`](../compliance/SIGNOFF.md).

## P

- **Panel**: A panel of the spacecraft structure on which units are mounted. In the diagram, panels or compartments are drawn as lanes (see Zone). See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Parts library**: The versioned list of parts (connectors, contacts, backshells, wires, sleeving, labels) kept in `library/`. Each part has a manufacturer, part number, specification, approval status, mass and ratings. The starter library holds example parts only; `harness library` shows where your own library came from. See [`IMPORTS.md`](IMPORTS.md), [`FILE_FORMAT.md`](FILE_FORMAT.md).
- **Payload**: The part of a spacecraft that does its mission job, such as the imager in the flatsat example, as opposed to the units that keep the spacecraft running. Payloads often need Ethernet for high data rates. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **PCDU**: Power control and distribution unit: takes power from sources such as the solar array and the battery and distributes it to other units. The docs also call it the power unit, power control unit or main power distribution. Its ID in the examples is `PCDU1`. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **PDU**: Power distribution unit: here a second-level unit (such as `PDU2` in the AOCS lane) fed by the PCDU that supplies a group of units. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **Pending and not checked**: **Pending** means a value (usually a wire gauge) is missing because an input has not been supplied. **Not checked** means a rule could not run because its numbers have not been supplied. Both are deliberate: the tool does not invent engineering values and does not let a missing check look like a pass. See [`CONCEPTS.md`](CONCEPTS.md), [`PLACEHOLDERS.md`](PLACEHOLDERS.md).
- **Pigtail**: A way of terminating a shield: it is brought out as a short lead and connected to a pin of the connector instead of being clamped around the connector body. See [`CONFIG.md`](CONFIG.md). (general meaning)
- **Pin**: One contact of a connector. A pin carries one signal. Some messages say *contact* instead of pin: a contact rating is the current one contact may carry, and `contact_current_factor` is the fraction of it you allow. See [`CONCEPTS.md`](CONCEPTS.md), [`CONFIG.md`](CONFIG.md). (general meaning)
- **Pin gap**: Empty pins left between power pins and signal pins (`power_signal_gap_pins`), and between the supply and return pins of a power interface (`power_return_gap_pins`), to keep them apart. See [`CONFIG.md`](CONFIG.md).
- **Pinout**: A table of which signal is on which pin of a connector. The tool writes one for every cable connector (`pinouts.csv`) and for every unit connector (`box_pinouts.csv`). See [`OUTPUTS.md`](OUTPUTS.md). (general meaning)
- **Placeholder**: A value, or a whole configuration file, that nobody has reviewed yet. A file is marked `"placeholder": true` until an engineer reviews it and sets it to `false`. Results that rest on a placeholder say so, and a release is blocked unless you give a written reason. A default that the owner has not yet confirmed (such as the current harness grouping) is also called a placeholder. See [`CONCEPTS.md`](CONCEPTS.md), [`PLACEHOLDERS.md`](PLACEHOLDERS.md).
- **Power and return (PWR, RTN)**: A power interface uses two wires: `PWR`, which carries current to the unit, and `RTN` (return), which carries it back to the source. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Primary power and secondary power**: Two power interface types. Both carry a supply wire (`PWR`) and its return (`RTN`). The tool does not decide which of your power links is primary and which secondary; you choose the type for each interface. See [`FAQ.md`](FAQ.md).
- **Provenance**: The record of where an output came from: tool version, model hash, parts library and which configuration files were still placeholders (`system/provenance.json`). See [`OUTPUTS.md`](OUTPUTS.md).
- **Pyro**: Pyrotechnic: a firing line that sets off a small explosive device, for example to release or deploy something. The starter type `Pyro initiator` has the signals `FIRE+` and `FIRE-`. Pyro lines never share a harness or connector with other wires, to avoid accidental firing. See [`RULES.md`](RULES.md). (general meaning)

## R

- **Reaction wheel**: A spinning wheel inside a spacecraft. Speeding it up or slowing it down turns the spacecraft the other way, so it is used to control which way the spacecraft points. In the examples a wheel is a unit with a power link and an RS-422 data link. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **Release**: Freezing a harness. A release needs a person's name and a comment, and stores a baseline and a change-log entry. Afterwards the harness cannot be edited; to change it you start a new revision. A release is blocked while checks fail; configuration placeholders and unapproved parts block it too unless you give a written reason for each. See [`CONCEPTS.md`](CONCEPTS.md), [`HOWTO.md`](HOWTO.md).
- **Release candidate (rc)**: A build proposed for release, labelled with `rc` and a number in its version (for example `0.1.0rc8`). The `rc` is removed only after the owner signs off. See [`RELEASE.md`](RELEASE.md).
- **Release gate**: The conditions a harness must meet before it can be released: a comment of at least 10 characters, generation up to date, no open errors that belong to the harness, every wire with a gauge and a length, outputs exported from the current design and unmodified, configuration files reviewed, and parts approved. When one fails the release is *blocked* and the reason is printed (see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md#releasing)). The last two (placeholders, unapproved parts) can be overridden with a written reason. See [`HOWTO.md`](HOWTO.md), [`GETTING_STARTED.md`](GETTING_STARTED.md).
- **Requirement ID**: A number that names one requirement. IDs such as `REQ-OUT-03` are this project's own requirements (`REQUIREMENTS.md`). IDs such as `ECSS-Q-ST-30-11_0140051` name one requirement of a standard; rules cite them so you can see which requirement a finding serves. See [`RULES.md`](RULES.md), [`OUTPUTS.md`](OUTPUTS.md).
- **Revision**: A letter (A, B, C ...) that identifies a version of a harness. To change a released harness you start a new revision; the old one stays available. See [`CONCEPTS.md`](CONCEPTS.md), [`HOWTO.md`](HOWTO.md).
- **RF (radio frequency)**: Radio frequency: high-frequency signals such as those to and from an antenna, carried on coaxial cable. The starter type `RF coax` uses it. In the flatsat example an RF cable joins the transceiver and the RF test equipment in place of antennas. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **RIU**: Remote interface unit: collects the analog, discrete and thermistor signals from several devices so that the computer needs fewer connectors. Its ID in the flatsat is `RIU1`. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **RS-422**: A serial data link standard that sends each signal on a differential pair. In the starter library it has four signals: `TX+` and `TX-` (transmit pair) and `RX+` and `RX-` (receive pair). One of the three baseline communication types. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **RS-485**: A serial data standard like RS-422 but for a shared two-wire connection that several units can use. The starter type has the signals `A` and `B`. One of the three baseline communication types. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)

## S

- **S-band**: A radio frequency band commonly used for spacecraft communication. In the flatsat the transceiver `TRX1` is an S-band transceiver. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **SBOM and CycloneDX**: Software bill of materials: the list of software libraries shipped in a release, with versions and licences. A release writes one in CycloneDX format (`sbom.cdx.json`) together with a licence report; SPDX is another common format. See [`RELEASE.md`](RELEASE.md). (general meaning)
- **SCOE**: The checkout system of the flatsat example: ground equipment that sends commands to the spacecraft's computer and records telemetry. The repository does not spell the abbreviation out. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md).
- **Screen reader**: Software that reads the screen aloud for people who cannot see it. The Interface table and Outline tabs are the screen-reader friendly views of the diagram. See [`USER_GUIDE.md`](guide/USER_GUIDE.md). (general meaning)
- **Segment**: A stretch of the physical route a harness follows between two nodes (connectors or branch points). Wire lengths are sums of segments. Segment IDs look like `W001-L1`; lengths come from a table you import with `harness import-lengths`. See [`CONCEPTS.md`](CONCEPTS.md), [`IMPORTS.md`](IMPORTS.md).
- **Segmentation**: How interfaces are grouped into harnesses. The modes are `per_connector_pair` (the default), `per_unit_pair` and `per_zone_pair`; the choice is made in `config/segmentation.json`. See [`CONFIG.md`](CONFIG.md), [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md).
- **Segregation**: Keeping unlike wires apart so they do not share a harness or connector. Nominal and redundant chains are always kept apart, and so are pyro lines; you can add pairs of categories (for example power and analog) in `config/segregation.json`. See [`CONFIG.md`](CONFIG.md), [`RULES.md`](RULES.md).
- **Service loop**: Extra wire length added at each end for slack (`service_loop_m`). Wire lengths exclude it until you set a value. See [`CONFIG.md`](CONFIG.md). (general meaning)
- **Shield**: A conductive layer (braid or foil) around wires that reduces electrical noise getting in or out. The tool tracks shield groups, how each end is terminated and whether the connector and wire parts can support it. See [`RULES.md`](RULES.md), [`OUTPUTS.md`](OUTPUTS.md). (general meaning)
- **Shield termination**: How each end of a shield is connected: through a 360 degree backshell, by a pigtail, or left floating (not connected). A shield connected at neither end does not shield. You choose the concept for each end (`shield_end_a`, `shield_end_b`) and rules check it. See [`CONFIG.md`](CONFIG.md), [`RULES.md`](RULES.md). (general meaning)
- **Sleeving**: A protective covering over wires, such as braided sleeving (a part category in the library). In drawings, 'sleeve' is also used for the grey jacket drawn around a shield's wires, and a wire marker sleeve is a label. See [`OUTPUTS.md`](OUTPUTS.md). (general meaning)
- **SMA**: A small coaxial connector for radio-frequency (RF) signals. The baseline RF connector, one per RF link. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Soak test and fuzz test**: A fuzz test feeds a program many random or damaged inputs to look for crashes. A soak test runs thousands of random editing steps, with undo, saves and reloads, and checks that the project's invariants always hold. Both are release checks. See [`RELEASE.md`](RELEASE.md). (general meaning)
- **Solar array**: The panels that turn sunlight into electrical power for the spacecraft. In the flatsat example a solar array *simulator* replaces it on the bench. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **SpaceWire**: A data-link standard used on spacecraft, carried on several differential pairs. The starter type has eight signals (data and strobe, in and out). Not part of the baseline. See [`FAQ.md`](FAQ.md). (general meaning)
- **Spare pin**: A pin deliberately left unused so later changes need no new connector. You can require a share of spare pins (`spare_pin_fraction`); the rule stays silent until you set it. See [`CONFIG.md`](CONFIG.md). (general meaning)
- **Splice**: A joint where several wires are connected together inside a harness. See [`FILE_FORMAT.md`](FILE_FORMAT.md). (general meaning)
- **Standard profile**: A named set of values taken from a standard (`ecss-q-st-30-11c`, `ecss-e-st-20-07c`) that `harness config --apply-profile` can fill into unset values. It never overwrites what you set, prints the requirement each value comes from, and the files stay placeholders until an engineer has reviewed them. See [`CONFIG.md`](CONFIG.md).
- **Star tracker**: A sensor that finds the spacecraft's orientation by recognising star patterns. In the flatsat example it uses an RS-422 data link. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **String**: One complete chain of units with no backup copy. A 'single string' design has no redundant chain. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **Subsystem**: A named group of units, for example `egse` or `aocs`. Every unit has one; the project files for units and interfaces are split by subsystem. See [`FILE_FORMAT.md`](FILE_FORMAT.md).
- **Sun sensor**: A sensor that measures which direction the Sun is in, used to work out the spacecraft's orientation. In the examples it sends an analog signal. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)

## T

- **Telemetry and commands**: Telemetry is data the spacecraft sends about its own state; commands are the orders sent to it. In the flatsat the checkout system sends commands and records telemetry. (Engineers abbreviate the pair as TM/TC; the docs do not use that abbreviation.) See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **Test tables**: The tables in `tests.csv` for checking a built harness: one continuity test per wire and isolation tests between wires and shields. The pass limits are engineering values you supply; until then they read 'TBD (placeholder)'. See [`OUTPUTS.md`](OUTPUTS.md).
- **Thermistor**: A temperature sensor: a resistor whose resistance changes with temperature. The starter type `Thermistor` has the signals `T+` and `T-`. See [`FAQ.md`](FAQ.md). (general meaning)
- **Title block**: The box on every drawing sheet that identifies it: project, harness ID, title, revision, status, sheet number, tool stamp, and (once reviewed and released) author, checker, approver and date. Which fields appear is set in `config/titleblock.json`; your company's layout is still an open decision (D-15). See [`OUTPUTS.md`](OUTPUTS.md), [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md). (general meaning)
- **TNC**: A coaxial connector family for radio-frequency signals, like SMA but older in this library. Kept for projects that need it. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)
- **Traceability matrix**: A table of which interface is carried by which harness and wires (`traceability.csv`), so every requirement-level connection can be followed to the wires that build it. See [`OUTPUTS.md`](OUTPUTS.md). (general meaning)
- **Transceiver**: A radio unit that both transmits and receives; the spacecraft's link to the ground. The README calls it a radio. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **Trunk and breakout**: A trunk is the main run of a harness, shared by many wires; a breakout is where wires leave it towards individual units. A loom is a harness built that way, following the structure. Option C of decision D-10 would use them. See [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md). (general meaning)
- **Twisted pair**: Two wires twisted together to reduce noise. Used for most data and power pairs; when the pair is also shielded it is a twisted shielded pair. See [`CONCEPTS.md`](CONCEPTS.md). (general meaning)

## U

- **Umbilical**: The cable connection between the launch vehicle and ground equipment before launch, supplying power and carrying data. In the flatsat the ground power supply replaces it on the bench. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md). (general meaning)
- **Unit**: A box in the system with connectors on it, such as the on-board computer `OBC1`, the power unit `PCDU1` or a reaction wheel `RW1`. In the flatsat example, ground test equipment is also modelled as units. You add units; the tool connects them. See [`CONCEPTS.md`](CONCEPTS.md).
- **Unit ID prefixes**: Short unit IDs in the flatsat example: `BAT` battery, `SA` solar array simulator, `TRX` S-band transceiver, `ST` star tracker, `SS` sun sensor, `MTQ` magnetorquer system, `PL` imager payload, `HTR` heater panel, `PYRO` deployment pyro unit, `GPSU` ground power supply, `RFSU` RF test equipment. See [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md).
- **Usability session**: A test in which real users try the tool on set tasks while someone observes. The kit is in [`usability/README.md`](usability/README.md); the owner waived the sessions for version 0.1.0.

## V

- **VCM**: Not used by this tool. No command, file, output or page of this repository uses the abbreviation. If your programme uses it, take its meaning from your programme's documents.
- **Voltage drop**: The voltage lost along a wire because of its resistance; a long thin wire loses more. The tool checks it against the largest drop you allow (`max_voltage_drop_v`) and uses it when choosing the gauge. See [`RULES.md`](RULES.md), [`CONFIG.md`](CONFIG.md). (general meaning)
- **Voltage ratings**: Rated voltage is the voltage a part is designed for. Working voltage is the voltage actually applied. Dielectric withstanding voltage is the voltage its insulation is tested to withstand. Configuration entries limit the working voltage to a fraction of these ratings. See [`CONFIG.md`](CONFIG.md). (general meaning)

## W

- **Waiver**: A recorded decision to accept a warning, with a written reason of at least 10 characters. Errors cannot be waived. Waived warnings stay in the report with their reason, so a reviewer sees them. (In the compliance documents, *waived by the owner* is a different thing: see Deviation, and *Words that mean two things here*.) See [`CONCEPTS.md`](CONCEPTS.md).
- **Wire**: One conductor between two pins, with a gauge, a part and a length. A harness is made of wires; each has an ID such as `W001-001`. See [`CONCEPTS.md`](CONCEPTS.md).
- **Wire list**: A table with one row per wire: signal, interface, the connector and pin at each end, gauge, part, colour and length (`wirelist.csv`). See [`OUTPUTS.md`](OUTPUTS.md). (general meaning)
- **Wire sizing**: Choosing the gauge of each wire: the smallest gauge in your ampacity table that carries the interface's current after derating, then checked for voltage drop over the wire's length. It cannot run until the values and lengths exist. See [`GETTING_STARTED.md`](GETTING_STARTED.md). (general meaning)

## Z

- **Zone**: A lane of the diagram that stands for a place on the spacecraft such as a panel or compartment (for example `panel-A`). A unit's zone is the lane it sits in. Harnesses can be grouped by pair of zones (`per_zone_pair`). See [`CONCEPTS.md`](CONCEPTS.md).

Next: [`CONCEPTS.md`](CONCEPTS.md), [`FAQ.md`](FAQ.md), [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
