# Models of the tool

This folder explains, for engineers, every calculation the tool makes: the equation, the inputs and where each comes from, the assumptions built into the program, what it is checked against, and a worked example you can repeat. It grows with the transparency work (decision D-191): a page is written for a model when its derivation is shown by the tool.

## Contents

- [How to use these pages](#how-to-use-these-pages)
- [The models](#the-models)
- [Every derivation as files](#every-derivation-as-files)
- [Every result as files](#every-result-as-files)
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
| [Overrides](overrides.md) | A value set by hand in place of the design's, with its reason: the value, the value the design would give, and what the set value does to the checks | `harness-design-studio explain DIR WIRE` (the derivation *Overridden by the engineer*, `wire-override`) |
| [Units on import](import-units.md) | The unit a file is read in, the factors, the rounding, and what is shown and recorded when a value is converted | the echo of `import-lengths`, `import-parts`, `import-build-data`; `harness-design-studio imports DIR` |
| [Selectable models](selectable-models.md) | The choices in `config/model.json`: bundle basis, length, voltage drop, mass, pin order, what blocks "Ready to build" | `harness-design-studio settings DIR` |
| [Readiness](readiness.md) | "Ready to build" and the eight checks of the build workbook: which block, how many are open, which wires and pins | `harness-design-studio explain DIR HARNESS` |
| [Test limits](test-limits.md) | The continuity limit, the insulation limit and the test voltage of the test sheet: the key, the unit, "TBD (placeholder)" | `harness-design-studio explain DIR HARNESS` or `HARNESS.T001` |
| [Pin allocation](pin-allocation.md) | Why a signal is on a pin (the order of the categories, first fit, the gaps, locked pins) and why a connector is the connector of an interface | `harness-design-studio explain DIR CONNECTOR.PIN` or `CONNECTOR` |
| [Segmentation](segmentation.md) | Why the interfaces of a harness share it: the mode, the chain, the class, the zones | `harness-design-studio explain DIR HARNESS` or `INTERFACE` |
| [Labels and colours](labels-and-colours.md) | The text of the labels of a wire and a connector, and the colour of a wire | `harness-design-studio explain DIR WIRE` or `CONNECTOR` |
| [Shields](shields.md) | Which wires form a shield group and why the group has the ends it has | `harness-design-studio explain DIR GROUP` or `WIRE` |
| [As-built results](asbuilt.md) | How a recorded value is compared: a measured resistance with the test limit (actual, limit, margin), a cut length with the designed length; what the tool does not decide | `harness-design-studio asbuilt DIR`, `explain DIR HARNESS.T001` or `WIRE` (kind `asbuilt-result`) |
| [Rule limits](rule-limits.md) | The limit of every design rule, or, for a yes/no rule, what it compares | the Explain button of the Checks tab; `explain_finding` |

A rule that a project adds with an extension ([Extend the tool](../user-manual/extend-the-tool.md)) has a derivation too, in the same form: a data file's rule shows its condition as the equation, the fields, parameters, settings and lookup values it read as the inputs (each with its source, which for a parameter is the file and the key), and the actual value, the limit and the margin as the check (kind `rule-limit`); a Python rule says what it compares (kind `rule-check`). Both name the file or the plug-in, its version and its hash, and say that the rule is not part of the tool. A test asks `explain` about every rule of the registry, built-in and extension.

A test ties each kind of derivation the tool makes (`core/derive_kinds.py`) and each design rule (`core/derive_rules.py`) to a page of this folder, so that none is left out.

## Every derivation as files

`harness-design-studio explain DIR --all --out FOLDER` writes how every number of the project was made, so that a result can be checked from a file, put into a spreadsheet or read by a script:

- **`derivations.json`**: `format` (3), `tool_version`, the project name and the list of derivations, each with its `id` (the kind: `wire-length`, `wire-current-limit`, `wire-voltage-drop`, `wire-mass`, `harness-mass`, `wire-override` (a wire with an override), `part-bom`, `contact-current`, `readiness`, `readiness-check`, `test-limit`, `pin-allocation`, `connector-choice`, `segmentation`, `wire-label`, `connector-label`, `wire-colour`, `shield-group`, `asbuilt-result` (a project with as-built records), `rule-limit`, `rule-check`), `subject`, `quantity`, `value`, `unit`, `equation`, the `inputs` (name, value, unit, source), the `steps`, the `check` (actual, limit, unit, passes, margin, text), the `assumptions` (each with its ID, kind and where it lives in the program) and what is `missing`. A derivation whose result is a text (a label, a colour, a pin, a group, the answer to *Ready to build*) has the key `text`, and a step with a text has `text` and no number. This is the same record that `explain --json` prints for one object. An input that is a wire gauge (unit `AWG`) also has `area_mm2`, its cross-section (format 3). Format 1 had no `text` and no derivation of the kinds from `readiness` on; format 2 had no `area_mm2`.
- **`derivations.csv`**: one row for each derivation with the columns *Kind, Subject, Quantity, Value, Unit, Equation, Actual, Limit, Margin, Verdict, Assumptions, Missing, Text*. Filter *Verdict* on `fail` to see every limit that is exceeded, and *Missing* to see what the project has not set.

There is no time, user name or path in the files: the same design gives the same bytes, so two engineers can compare their files, and a change of the files means a change of the design, the configuration, the library or the tool. A value that is not set has an empty *Value* and says in *Missing* what to set; a result that is a text is in *Text*. After the derivations of the harnesses, wires, parts and contacts come those of the rules: one for each finding of the project (the limit of a rule with a number, what a yes/no rule compares). The files are written only to the folder you name; no project file is changed.

## Every result as files

`harness-design-studio export-data DIR --out FOLDER` writes the numbers the models above produce as a table for each result, so that a colleague can reproduce them from the files alone: `wire_sizing` (current, gauge, cross-section in mm², base ampacity, bundle size and K, temperature factor, derated limit, length, resistivity, voltage drop, limits, margins and verdicts: the quantities of [wire sizing](wire-sizing.md)), `lengths` and `segment_lengths` ([wire length](wire-length.md)), `mass` and `mass_wires` ([mass](mass.md)), `bom` and `bom_contributions` ([bill of materials](bom.md)), `readiness` ([readiness](readiness.md)), `test_limits` ([test limits](test-limits.md)), `pin_allocation` ([pin allocation](pin-allocation.md)), `segmentation_groups` and `segmentation_interfaces` ([segmentation](segmentation.md)), `rule_results` and `findings` ([rule limits](rule-limits.md)), `parts`, `settings` and the files `configuration.json` and `provenance.json`. Each table is a JSON and a CSV file with the unit in each heading and a `format` number; the same design gives the same bytes, and a script that imports only `csv` and `json` (`docs/examples/open-data/reproduce.py`) recomputes the limits, the voltage drops and the bill of materials of every packaged example to 9 decimals (a test does it). How to write and read them: [export the data](../user-manual/export-the-data.md). The run record (time, operator, tool version) is not in these files: it is written only with `--run-record`, beside them.

## The assumptions built into the program

Some of what a calculation rests on is not a number you type into `config/*.json` but a choice built into the program. Each has an ID, and a derivation names the ones it uses. Today they are: A-ROUND-TRIP, A-DC-SOLID, A-BUNDLE-ALL and A-PATH-UNIQUE, A-MASS-SCOPE, A-MASS-CONDUCTORS, A-BOM-CONTACTS, A-BOM-NO-ALLOWANCE and A-CONTACT-SHARED (built in; since S1 also A-READY-CHECKS, A-READY-SCOPE, A-TEST-LIMITS, A-TEST-LIST, A-PIN-ORDER, A-PIN-FIRST-FIT, A-SEGMENT-MODE, A-ZONE, A-LABEL-FORMAT, A-COLOUR-TABLE, A-SHIELD-GROUPS, A-SHIELD-ENDS, A-CONNECTOR-CHOICE, A-SPARE-PINS, A-CONNECTOR-VOLTAGE, A-AMBIENT-ONLY, A-MATING-REQUIRED, A-RETURN-GAP and A-BUNDLE-CURRENT, each on the page of the model it belongs to; the page [see what the tool assumes](../user-manual/see-what-the-tool-assumes.md) lists them with the settings that parameterise them), and A-TEMP-FACTOR, A-AMPACITY-AWG and A-SERVICE-LOOP (a value of the configuration, but one single number or table with no model behind it). They are described on the [wire sizing page](wire-sizing.md#the-assumptions-it-rests-on) and the [wire length page](wire-length.md#the-assumptions-it-rests-on) the [mass page](mass.md#the-assumptions-it-rests-on) the [bill of materials page](bom.md#the-assumptions-it-rests-on) and the [contact current page](contact-current.md#the-assumptions-it-rests-on). The aim of the work is that every built-in choice becomes a visible, documented setting; until then it is listed, not hidden.

Next: [rule limits](rule-limits.md), [readiness](readiness.md), [selectable models](selectable-models.md), [contact current](contact-current.md), [bill of materials](bom.md), [mass](mass.md), [wire length](wire-length.md), [wire sizing](wire-sizing.md), [changes to results](../changes.md), [the configuration](../CONFIG.md)
