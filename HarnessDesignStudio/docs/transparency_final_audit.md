# The final audit of the transparency work

This page is the last stage (S10) of the transparency work (decisions D-191 and D-193, [the plan](transparency_plan.md)). It goes through the 14 requirements of [the first audit](transparency_audit.md) one by one and says, for each, what the first audit found, what was built, what the evidence is and what is still not true. It claims **no compliance, no certification and no sign-off**: it is the account of an author who has read its own work against a list, and the owner's review is still to come. Where something could not be made true, it is written here and not left out.

## Contents

- [The short version](#the-short-version)
- [The 14 requirements](#the-14-requirements)
- [What the tool was not, and is now](#what-the-tool-was-not-and-is-now)
- [The definition of done](#the-definition-of-done)
- [The 16 numbers, traced again](#the-16-numbers-traced-again)
- [The owner's open decisions](#the-owners-open-decisions)
- [The limits of this verification](#the-limits-of-this-verification)
- [How to repeat it](#how-to-repeat-it)

## The short version

| Req | First audit (section 6) | Now | The gap that remains, in a few words |
| --- | --- | --- | --- |
| R1 Explain view | partial | built (step 0, S1) | the search that picks a gauge is not itself explained; the Explain window does not show the link to its documentation page |
| R2 Assumptions panel | partial | built (S2); two more assumptions made settings and the 3 limit rules given IDs since | 13 of 34 assumptions stay built in on purpose: each is a statement about the method and not a number or a choice among alternatives, with the reason listed under *Stays built in, why* |
| R3 Externalised configuration | partial | built (S2); comments in the files built as opt-in (1.13.0) | the comments `_about` are off unless asked for and are refreshed by `settings --annotate`, not by every save |
| R4 Selectable models | partial | built (S3), in part | six models; segmentation, first fit, connector choice and the labels stay one method each |
| R5 Units everywhere | partial | built (S5, S6) | every number of `export.json` states its unit (`field_units`, D-195); the files keep the plain AWG gauge; other written files still name units only in their headers and field names |
| R6 Workflow visibility | partial | built (S9) | the intermediates are inspectable as files and by `explain`; only some can be edited (the settings, the overrides, the as-built records); nothing was looked at on a real display |
| R7 Overrides | partial | built (S4) | a lock from an earlier version is kept as it was, with no reason; open decision |
| R8 Change history | partial | built (S4) | the author is not authenticated; two Git branches can conflict in `journal.json`; open decision |
| R9 Provenance | partial | built (S5, S6, S8) | the run record is outside every hash on purpose, so nothing in a hash says when |
| R10 Open data | partial | built (S5) | the GUI Export does not offer it; open decision |
| R11 Scriptable | partial | built (S7) | the API is version 1 and young; nothing but its own snapshot has used it |
| R12 Explainable warnings | partial | built (S1, S4); the three IDs added since | a yes/no rule shows what it compared, not a number; `A-PIN-ONE-WIRE` is built in |
| R13 Extensibility | missing | built (S8) | no sandbox for Python plug-ins; trust is per user and computer; open decision |
| R14 Visible data links | partial | built (S6) | a source file that moved is reported as not found, not followed |

**What is true:** every requirement above has code, a document and tests behind it, and the definition of done of the brief passes as automated tests (section [The definition of done](#the-definition-of-done)): any of 16 numbers is traced with the tool's own surfaces in well under a minute; five built-in choices and a rule of an extension file are changed without editing code and the result and its explanation follow as a hand calculation says; a result is reproduced from an exported folder alone on all four examples; and each rule that compares a number with a limit explains a finding with the actual value, the limit, the margin and the source of every input. **What is not true:** that anyone has looked at the result on a screen, that the numbers are right for a programme (the examples carry placeholder values), and that the pages of S9 (workflow, as-built, roles) have been looked at by a person.

## The 14 requirements

Pull request numbers are those of `docs/transparency_plan.md`: audit #141; step 0 #142; the first explanations #143, #144, #145 (wire length), #146 (mass), #148 (bill of materials), #149 (contact current), #150 (derivations as files), #153 (a finding opens its calculation); S1 #158; S2 and S3 #155; S4 #160; S5 #159; S6 #156; S7 #157; S8 #161; S9 #162; S10 the pull request of this page.

### R1. Explain view

- **First audit:** partial. The Why tab had stored lines; no equation, constants or sources; nothing for length, mass, BOM, colour, shield ends, labels, test limits, readiness or the connector choice; no command-line explain.
- **Built:** `core/derive.py` (the records `Derivation`, `Input`, `Step`, `Check` and the explanations of a wire, a harness, a part), `core/derive_build.py` (readiness, test limits), `core/derive_layout.py` (pin allocation, segmentation, connector choice, labels, colours, shields), `core/derive_rules.py` (the limit of every design rule), `core/derive_export.py` (every derivation as `derivations.json` and `.csv`), `cli/explain.py`, `api.explain`, `api.explain_finding`, `gui/explain_dialog.py` and the *Show the calculation* part of the Why tab. Twenty kinds of derivation (`core/derive_kinds.py`), each with a page in [the models](models/README.md). Stages: step 0 to #153, and S1 (#158).
- **Evidence:** `tests/test_derivations.py` compares each derivation with the number it explains, wire by wire, to the last digit; `tests/test_s1_rules.py` (every rule of the registry has an explanation; the verdict of the check is the verdict of the rule); `tests/test_s1_build_layout.py` (every kind a project makes is listed with its page); `tests/test_models_docs_complete.py` (no kind without a page); `tests/test_trace_16_numbers.py`. Commands: `harness-design-studio explain DIR OBJECT [--json]`, `explain DIR --all --out FOLDER`.
- **Remaining gaps:** (1) The *decision* of a gauge, the search that picks the smallest conductor whose derated limit carries the current and then grows it until the drop is within the limit, is described on [wire sizing](models/wire-sizing.md) but is not itself a derivation: `explain` shows the limits of the gauge that is on the wire, not why it is that gauge. (2) The page of the documentation for a derivation is known to the code (`derive_kinds.page_of`, `page_of_rule`) and tested, but the Explain window and the text of `explain` do not print the link. (3) An explanation for an *override* shows the consequences for the current limit and the drop, not for every other rule.

### R2. Assumptions panel

- **First audit:** partial. Values of the config files only; hard-coded model choices not listed; no "assumptions active in this analysis"; fallbacks not listed.
- **Built:** `core/assumptions.py` (34 assumptions with IDs, 21 of them settings and 13 built in), `core/settings.py` (64 settings, each with unit, description, default, source and range, and 6 definitions), `harness-design-studio settings DIR [--json] [--set FILE.KEY=VALUE]` (S2, #155), **Help > Assumptions...** in the editor, and [see what the tool assumes](user-manual/see-what-the-tool-assumes.md). Every derivation names the assumptions it rests on; every setting says whether its value is the project's, the tool's default (the behaviour before the setting existed) or not set.
- **Evidence:** `tests/test_settings.py` (every key is registered and documented; the defaults are what the tool did before; a test walks the calculation modules and fails on a number that is neither a setting, a definition nor a listed exception); `tests/test_models_docs_complete.py` (every assumption on a page, every setting in `CONFIG.md`, every definition on [definitions](models/definitions.md)); `tests/test_definition_of_done.py` (b).
- **Built since (assumptions that became settings):** `A-BOM-CONTACTS` and `A-BOM-NO-ALLOWANCE` were built in and are settings now: `model.bom_contact_spare_fraction` and `model.bom_wire_allowance_fraction`, each 0 by default (the quantities of the bill of materials are what they were; a test of the default and of a changed value against a hand calculation is `tests/test_bom_allowance.py`). Of the 14 assumptions that were built in these were the two that are a number the project can sensibly choose; the other 12 are not, as the table says.
- **Remaining gaps:** 13 assumptions are `built in` and cannot be changed without editing the program. They are listed and documented, each with the reason below. The number-in-code walk is a static scan of the calculation modules; it cannot see a constant that is built from other numbers. Four settings do nothing yet and say so (`emc.classes`, `naming.box_connector`, `derating.rf_power_factor`, `derating.partial_load_factor`).

#### Stays built in, why

Each of these is a statement about how a result is made (what is counted, in which order, by which form) and holds no number the project could choose, or a choice whose alternatives would be a different method and not a value. Whether another method should be offered is for the owner. The same sentence is on the page of the model.

| Assumption | Why it is not a setting |
| --- | --- |
| `A-DC-SOLID` | its settings (`drop_model` and the resistivity values) choose the resistivity, not the method; stranding, contact resistance or an AC effect would be a different equation |
| `A-PATH-UNIQUE` | whether a path is unique is a property of the drawn segments; an allowance you want is the cut allowance of the length model |
| `A-MASS-CONDUCTORS` | it is what the mass per metre of a multi-conductor part means (the cable counted once), an identity of the library |
| `A-CONTACT-SHARED` | the model does not say how many contacts carry the current of an interface (supply and return pins belong to one interface), so a split would need an input the project does not have; the factor is a setting |
| `A-READY-SCOPE` | it states what the answer is made from (the eight checks); which of them block is the setting `readiness_blocking` |
| `A-TEST-LIST` | it states which tests exist (one for each wire, one for each shield group); the limits are settings (`A-TEST-LIMITS`) |
| `A-PIN-FIRST-FIT` | first fit is the algorithm; what moves the result (the category order, the gaps) is a setting |
| `A-ZONE` | it states where the zone is kept (a field of the device); how zones group harnesses is `segmentation.mode` |
| `A-LABEL-FORMAT` | the layout of a label is a form, not a value |
| `A-SHIELD-GROUPS` | it turns a construction into a shield group, which follows the construction; the grounding of the ends is a setting |
| `A-CONNECTOR-CHOICE` | first free connector in ID order is a method, marked as made for you until a person confirms it |
| `A-BUNDLE-CURRENT` | counting an unset temperature factor as 1 is how the rule treats a missing value; a number would let it look like an engineering choice |
| `A-PIN-ONE-WIRE` | one wire to a pin is the limit of `pin-shared`; a design that needs two in a contact waives the finding with a reason (new, see R12) |

### R3. Externalised configuration

- **First audit:** partial. Seven JSON files with validation and profiles; no comments, units or sources in the files; model constants in code.
- **Built:** the constants of the model are the keys of the new optional file `config/model.json` (S2, S3; 16 keys, each with today's behaviour as its default); a project without the file is written byte for byte as before; `docs/CONFIG.md` describes every key; `configuration.json` of `export-data` carries the files as the tool used them.
- **Evidence:** `tests/test_settings.py`, `tests/test_selectable_models.py`, `tests/test_settings.py::test_a_project_without_model_json_is_written_as_before`, `tests/test_numbers_snapshot.py` and `tests/test_output_hashes.py` (identical with the defaults).
- **Built since (1.13.0, open decision 13):** the comments in the files themselves, as an opt-in. A config file may carry the reserved top-level key `_about`: for every setting of the file its `label`, `unit`, `range`, `source`, `what`, `used_by`, `default` and `assumption`, made from the registry. `harness-design-studio settings DIR --annotate` writes or refreshes it in every existing config file (and creates nothing else), `--no-annotate` takes it out, `new --annotate-config` starts a project with it, the scripting interface has `annotate_config`. It is never a setting; it is outside the model hash, the generation inputs, the numbers and every written output (a test compares the model hash, the outputs and the open data with and without it); a project without it is written byte for byte as before; `validate` and `config` warn, naming file and key, when an entry differs from the registry. The engineering values page of the editor shows the range and the source in the tooltip of each value. See [`CONFIG.md`](CONFIG.md#comments-in-the-files-about).
- **Evidence (comments):** `tests/test_config_about.py`.
- **Remaining gaps:** the comments are opt-in and are written by the command, not by each save, so a file that was annotated and then meets a newer version of the tool says so with a warning until `--annotate` is run again; they are a copy of the registry (the registry stays the one source), not a place to type your own notes; JSON still has no comments, so `_about` is data that is ignored, not a comment a JSON parser skips. A file holds the values, the `placeholder` flag and, if asked, the comments; a reason for a change is in the journal (R8), not in the file.

### R4. Selectable models

- **First audit:** partial. No alternatives for sizing, drop, mass, length, pin allocation, readiness; the active choice not shown.
- **Built (S3, #155):** `model.bundle_basis` (`all_wires`, `loaded_wires`, `busiest_segment`), `model.length_model` (`path_plus_loops`, `path_loops_allowance_twist`), `model.drop_model` (`dc_solid`, `dc_at_ambient`), `model.mass_model` (`connectors_and_wires`, `full_bom`), `model.pin_allocation_categories`, `model.readiness_blocking`; one function for the bundle count (`core/generate/bundle.py`) that sizing, the rules and the explanation all call. The page [selectable models](models/selectable-models.md) lists every key, every value and the equation of each; an explanation names the model in force.
- **Evidence:** `tests/test_selectable_models.py` (each alternative against a hand calculation; the default reproduces the numbers); `tests/test_definition_of_done.py` (b3, b4, b5: a bundle basis, the drop model and the readiness list changed with `settings --set`, the result and the explanation follow a hand calculation); the numbers snapshot is identical with the defaults.
- **Remaining gaps:** the pin allocation strategy is the order of the categories, not another strategy (first fit is `A-PIN-FIRST-FIT`, built in); the connector choice, the segmentation keys, the label format and the colour table each have one method (the segmentation mode and the colour table are settings, the method is not selectable); there is no AC or skin-effect model of the drop, no mass model that counts splices or backshells.

### R5. Units everywhere

- **First audit:** partial. No mm² beside AWG; dimensionless factors unlabelled; import units fixed and partly silent; `export.json` fields without units.
- **Built:** the cross-section in mm² beside every gauge a person reads, on screen and in explanations (decision D2, S5, #159; definition `D-AWG`); `area_mm2` in data; units in every heading of the open data; `import-lengths --unit mm|cm|m|in|ft`, `import-build-data --unit`, `import-parts --mass-unit g|kg|lb|oz` with the unit echoed as given or assumed (S6, #156; [units on import](models/import-units.md)).
- **Evidence:** `tests/test_gauge_area.py`, `tests/test_ui_gauge_area.py`, `tests/test_import_records.py`, `tests/test_open_data.py`; `tests/test_definition_of_done.py` checks that a *difference* of two gauges is not given a cross-section.
- **Built since (D-195):** `export.json` has an object `field_units` that states the unit of every numeric field (one table in `core/outputs/export_units.py`; `tests/test_export_units.py` holds it against the model and against real files; the gauge is `AWG`, a number without a unit says what it is).
- **Remaining gaps:** the written files keep the plain gauge on purpose (owner's decision D2); a dimensionless factor has unit `""` in `settings`; `provenance.json` (counts, `format_version`) and `manifest.json` (`format_version`, `bytes`) have numbers whose name says what they count and no unit entry; the project's own JSON files (`config/*.json`, the model files) carry the unit in the field name or in the registry, not in the file (R3); `field_units` is in `export.json` only, not in the open-data JSON files, whose headings carry the units. A margin of two gauge numbers in the explanation of an extension rule was shown as `2 AWG (33.6 mm²)`, a cross-section for a difference; this audit found and fixed it (`core/units.py`, `with_area`).

### R6. Workflow visibility

- **First audit:** partial. No consumes/produces per step; intermediates not inspectable or editable.
- **Built (S9, #162):** `core/workflow.py` is the one source of the nine steps of the tool, each with what it uses and makes, its intermediates (what can be inspected and changed) and a status computed from the project with the steps that block it; it is read by `workflow DIR [--outputs] [--json]`, `api.get_workflow`, `docs/user-manual/follow-the-workflow.md` (its tables are made from the code) and a closed-by-default disclosure on the Next step page. The intermediates are also files: `export-data` (sizing, segmentation, pin allocation, lengths, mass, BOM, readiness, test limits). The as-built capture and the three roles are listed under "what it is not" below.
- **Evidence:** `tests/test_s9_workflow.py` (the page tables equal the code; mutation tests for a step that names a file, output, table or command the tool does not have), `tests/test_ui_role_pages.py`, `tests/test_open_data.py`.
- **Remaining gaps:** only some intermediates can be edited in the tool (settings, overrides, as-built records); the sizing candidates and the segmentation groups can be read, not changed. No screen was reviewed.

### R7. Overrides

- **First audit:** partial. One lock for four values; no reason, author or date; not flagged in exports; errors cannot be waived.
- **Built (S4, #160):** a per-field **override** (`Wire.overrides`: field name to reason) of the gauge, wire type, colour or length, refused without a reason in the model, the Edit wire tab, *Edit all wires* and `harness-design-studio override DIR WIRE FIELD VALUE --reason TEXT`; generation keeps the values an override names; `explain` starts with *Overridden by the engineer* (the value set, the reason, the value the design would give, the consequences for the current limit and the drop); flagged in the wire table and list, the cut list, *Start here* sheet and *Tests* sheet of the workbook (the band *Overrides and deviations* above the tests), the column `Deviations` of `tests.csv` for the tests of a marked wire, the note of a measured test in the as-built report, beneath the drawing, in `derivations.json` and in the release record, only for a project that has an override or a deviation. **Recorded deviations** (D-191 (3)): an error of an electrical rule can be accepted with a reason (`harness-design-studio deviation`), stays on every list and output marked DEVIATION and does not meet the requirement. Page: [overrides](models/overrides.md), [override and keep a history](user-manual/override-and-keep-a-history.md).
- **Evidence:** `tests/test_overrides.py`, `tests/test_deviations.py`, `tests/test_ui_overrides_journal.py`, `tests/test_deviation_marks.py` (the marks on the tests and the output check that reads them); a project with no override, deviation or journal opens and saves byte for byte as before.
- **Remaining gaps:** a wire *locked in an earlier version* keeps all four values as before and is shown as "Locked, no reason recorded": open decision 1. Only four values are overridable; a pin or a connector lock is still the earlier lock. A deviation applies to seven rules (`current-over-wire`, `current-over-contact`, `voltage-drop`, `bundle-current`, `connector-voltage`, `wire-voltage`, `temperature-margin`), not to the others. The marks on the tests carry the field or rule and the reason but not who and when (those are in the journal, which no output holds, so that equal designs give equal bytes); a deviation on a connector of an interface marks every wire of that interface, not one pin.

### R8. Change history

- **First audit:** partial. A change log for review, release and revision; nothing for edits, configuration or overrides between releases; no old/new; no time of day.
- **Built (S4, #160):** `core/journal.py`, the file `journal.json`, `harness-design-studio journal DIR [--json] [--since SEQ] [--object ID] [--start]`, *Help > Change history...*, `api.get_journal`: who changed which field, when, from what to what and why, for design inputs, configuration values, overrides, waivers, part approvals and releases, and one entry for each harness a generation changed. It is append-only (each entry carries a chain value), written when the project is saved, and is in no hash and no written output.
- **Evidence:** `tests/test_journal.py` (the journal reproduces the history from the first edit; a changed, removed or inserted entry is reported by `validate`; the same design saved at another time by another person has the same design files), `tests/test_journal_incremental.py`, `tests/test_recovery_journal.py`.
- **Remaining gaps:** the author is whatever `--author`, `HARNESS_AUTHOR`, the Git name or the user of the computer says: not authenticated. `journal.json` is a file two Git branches can both add to, and then it conflicts on merge. A project has a journal only if it has the file: an older project without one has no history before the day it starts one. Open decision 2.

### R9. Provenance

- **First audit:** partial. Stamp line, `provenance.json`, `manifest.json`, `input_hash`; no configuration values, operator or imports; `export.json` without configuration.
- **Built:** `export-data` writes `configuration.json` (the configuration files as the tool used them, with their placeholder flags), `settings.json` (every setting in force with its origin) and `provenance.json` (tool version, model hash, the files that are still placeholders, the library, the size of the design, the imports and the SHA-256 of every file written) beside the tables; the run record (`run_record.json`: time in UTC to the second, operator, tool version, platform, Python version, model hash, extensions) is written only with `--run-record` and is outside every hash and the manifest (S5, #159); every import is recorded in `imports/records.json` (S6, #156); every enabled extension and plug-in is named with its version and SHA-256 (S8, #161).
- **Evidence:** `tests/test_open_data.py` (no data file holds a time, a user name or a path; the run record exists only when asked and is in no hash), `tests/test_import_records.py`, `tests/test_extensions_cli.py`.
- **Remaining gaps:** by decision D-191 (1) the written files carry no timestamp, so nothing inside a hash says *when*; the run record says it, beside the files, if it is asked for. The place of the run record is open decision 5.

### R10. Open data

- **First audit:** partial. 88 files per export and `export.json`; intermediates, configuration, lengths, mass, BOM and findings not in JSON.
- **Built (S5, #159):** `harness-design-studio export-data DIR --out FOLDER` and `api.export_data`: 34 data files for the flatsat (a JSON and a CSV for each of `wire_sizing`, `lengths`, `segment_lengths`, `segmentation_groups`, `segmentation_interfaces`, `pin_allocation`, `rule_results`, `findings`, `readiness`, `mass`, `mass_wires`, `bom`, `bom_contributions`, `test_limits`, `parts`, `settings`, with `configuration.json` and `provenance.json`); unit in each heading, a `format` number; two of the files are read back by importers; `docs/examples/open-data/reproduce.py` recomputes the sizing from the files with no import of the tool.
- **Evidence:** `tests/test_open_data.py`; `tests/test_definition_of_done.py` (c), on all four examples, from a folder copied away from the project, in an isolated interpreter.
- **Remaining gaps:** the GUI **Export** does not offer the open data: command line and API only (open decision 6). The reproduction script recomputes the sizing and the bill of materials, not every table (the segmentation, pin allocation and readiness tables are read, not recomputed, because they are decisions, not equations).

### R11. Scriptable

- **First audit:** partial. 29 documented commands; no documented Python API, no JSON output, no explain command.
- **Built (S7, #157):** `harness_design_studio.api` (no Qt, prints nothing, never ends the program), `--json` on every command with a result in data form, `export --out FOLDER`, three worked examples (a batch, a trade study, every derivation as files) and [script the tool](user-manual/script-the-tool.md); the names, signatures and result fields are frozen by a snapshot (`tests/fixtures/api_snapshot.json`; [api stability](developer/api-stability.md)).
- **Evidence:** `tests/test_api.py`, `tests/test_api_stability.py` (the interface in a process where Qt cannot be imported), `tests/test_cli_json.py` (every command, keys, exit codes, the same bytes twice, no absolute path), `tests/test_scripting_examples.py`; this stage's tests use the public names (`api.explain`, `api.explain_finding`, `api.export_data`, `api.run_checks`).
- **Remaining gaps:** `API_VERSION` is 1, and the interface has had no user but its own tests and examples. `core.derive.explain_finding`, which takes a rule and an object, is not in the interface (the interface takes a finding ID); the editor and the Explain window use the core function.

### R12. Explainable warnings

- **First audit:** partial. One fixed sentence per rule; no derivation, no configuration key, no override path.
- **Built (S1, #158; #153):** the limit of each of the 39 rules and of the logical rules has a derivation: for the 12 rules that compare a number with a limit the equation, the inputs with units and sources, the steps and the check (actual, limit, margin, verdict); for the others a statement *this rule is a yes/no check: it compares X with Y*; actual, limit and margin are columns of the findings table in the open data; the **Explain** button of the Checks tab works for every rule; the deviation (R7) is the override path for an error. [Rule limits](models/rule-limits.md).
- **Evidence:** `tests/test_s1_rules.py` (the verdict of the derivation is the verdict of the rule for every object); `tests/test_definition_of_done.py` (d): for one finding of each of the 12 limit rules, `api.explain_finding` gives actual, limit, margin, a source on every input and no unknown.
- **Built since (owner decision 16):** the three limit rules that cited no assumption ID now have one, and their findings and `explain` list it under *Rests on*: `pin-shared` rests on `A-PIN-ONE-WIRE` (built in: one wire to a pin is the limit), `wire-voltage` on `A-WIRE-VOLTAGE` (a setting: `derating.wire_voltage_factor`) and `emc-class-split` on `A-EMC-ONE-BUNDLE` (a setting: `emc.same_class_one_bundle`; the limit of one bundle is the reading of the standard built into the rule). Their numbers and findings are unchanged. All 12 limit rules now name an assumption (`tests/test_definition_of_done.py` (d) asserts it).
- **Remaining gaps:** a yes/no rule shows what it compared, not a number. Whether `A-PIN-ONE-WIRE` should be a setting (a limit of 2 wires on a pin) is for the owner; it was left built in because a second wire in a contact is a crimp the tool does not model.

### R13. Extensibility

- **First audit:** missing.
- **Built (S8, #161):** a registry of everything the tool can run (`core/extensions/registry.py`: the 39 rules, the fields, the models, the tables, the lookup tables, the importers, each with kind, name, version, source and SHA-256), **declarative extensions** (rules, output tables and lookup tables in `extensions/*.json`, in a small expression language with its own parser, no `eval`), and **Python plug-ins** (entry point group `harness_design_studio.plugins` or `extensions/plugins/NAME.py`) that are never imported unless the project enables them and the user trusted that exact code. `harness-design-studio extensions DIR`, `trust`, `import-plugin`; *Help > Extensions...*; [extend the tool](user-manual/extend-the-tool.md), [for developers](developer/extensions.md), examples in `docs/examples/extensions/`.
- **Evidence:** `tests/test_extensions_expr.py`, `test_extensions_declarative.py`, `test_extensions_plugins.py`, `test_extensions_cli.py`, `test_extensions_examples.py`, `test_extensions_gui.py`, `test_extensions_docs.py`; `tests/test_definition_of_done.py` (b6): the parameter of an extension rule is edited in its file and the finding, its actual, limit and margin change as a hand calculation says.
- **Remaining gaps:** there is **no sandbox**: a trusted plug-in runs with the rights of the user who trusted it (`docs/SECURITY.md`); the trust store is per user and computer, so a colleague must trust the same code again; the severity of an extension that is enabled but not applied is the stage's choice (open decision 3). An extension's rules are not part of the 39 and are never in `docs/RULES.md`.

### R14. Visible data links

- **First audit:** partial. Pin-to-pin links; library source typed by hand; stale-generation flag; no source, time or hash for imports; no source-changed flag.
- **Built (S6, #156):** every applied import writes `imports/records.json` (kind, name, SHA-256, rows read, rows dropped with the reason, values converted as written / unit / as stored, columns read and left out, unit given or assumed, tool version; no time, operator or absolute path); `harness-design-studio imports DIR [--check] [--source FILE]` compares the hash of each reachable source with the recorded one (`unchanged`, `source changed`, `source not found`, `not checked (no path)`); the import wizard and the Next step page say *source changed*; every import echoes what it read, left out and converted; the parts import reads ratings; the netlist import keeps the pin type and the name of the schematic; the tool's own CSVs can be read back by every importer. [Units on import](models/import-units.md).
- **Evidence:** `tests/test_import_records.py`, `tests/test_ui_import_records.py`, `tests/test_data_import.py`.
- **Remaining gaps:** a source that moved is `source not found`, not followed; the time of an import is not recorded (by D-191 (1)); the source of the parts library is still a text typed by hand (this work did not change it).

## What the tool was not, and is now

The owner's brief listed what the tool was not. The status of each, in one line:

| It was not | Now | State |
| --- | --- | --- |
| Constants as settings | 64 settings with unit, default, source and range; a test fails on a number hidden in a calculation module | done; 13 assumptions remain built in on purpose, listed with the reason |
| Selectable models | bundle basis, length, drop, mass, pin allocation order, readiness | done, in part (see R4) |
| Overrides with reason and history | per-field overrides with a reason; the journal; deviations | done; the legacy lock is open decision 1 |
| Import records | `imports/records.json`, `imports`, units and echoes on every import | done |
| A scripting API | `harness_design_studio.api` and `--json` on every command | done; version 1 |
| Plug-ins | declarative and Python extensions behind enable and trust | done; no sandbox |
| As-built capture for Electrical and AIT | `asbuilt/records.json`, `export-asbuilt`, `import-asbuilt`, `asbuilt`, the as-built report and sheet, the As-built page; three roles (Systems, Electrical, AIT) | done (S9, #162); the tool applies no tolerance to cut and strip lengths; a release neither freezes nor gates on the records |
| Explanations for readiness and the other rules | `explain` for readiness and its eight checks, test limits, pin allocation, segmentation, labels, colours, shields and the limit of every rule | done |

## The definition of done

The brief's four tests, as automated tests (`tests/test_definition_of_done.py`; results as the runs report them):

| Test | What is asserted | Where |
| --- | --- | --- |
| (a) Any number traced in under a minute | the 16 numbers of the audit, each resolved with `explain`, `export-data` and `settings --json` only, complete, and under 60 s each (scaled by `HARNESS_TIME_FACTOR`); three are asked again cold in the definition-of-done file | `tests/test_trace_16_numbers.py`, `tests/test_definition_of_done.py::test_a_...`, [the trace results](transparency_trace_results.md) |
| (b) Change any assumption, constant, margin or rule without editing code | six changes made with `settings --set` or by editing an extension file: the conductors counted in the drop (0.458359 V to 0.229180 V), the service loops (3.45 m to 3.25 m and 3.55 m), the bundle basis (limit 3.6 A to 6.3 A), the drop model (x 1.1572), the readiness list (yes to no, 18 wires without strip length), a rule of an extension file (margin -2, -1, then no finding); each value is compared with a hand calculation written in the test, and each explanation names the new value and the key | `tests/test_definition_of_done.py::test_b1` to `test_b6` |
| (c) Reproduce a colleague's result from an exported file | the script that imports nothing of the tool, on `first-steps`, `minimal-satellite`, `small-satellite` and `flatsat`, on a copy of the export folder alone, in the same process and in an isolated interpreter | `tests/test_definition_of_done.py::test_c_...`, `tests/test_open_data.py` |
| (d) Explain a result in a review | for a finding of each of the 12 rules that compare a number with a limit: actual, limit, margin (negative), a unit, a source on every input, no input without a value, no "unknown", and the assumptions or the reference line | `tests/test_definition_of_done.py::test_d_...` |

(b) found and fixed one defect on the way: with the conductors counted changed, the source of the input *Conductors counted n* still said "2 for power and ground, 1 otherwise". It now names `config/model.json: return_path_conductors` or `single_path_conductors` and says whether the category is one of `return_path_categories`.

## The 16 numbers, traced again

[The trace results](transparency_trace_results.md) is the table of the 16 numbers of the first audit's section 8, with the command that gives each and what it resolved to. The first audit's reviewer needed 3 to 25 minutes for each by reading code, files and documents; the tool's own surfaces give each of them in seconds (the test asserts under a minute; the seconds are printed by `python -m tools.trace_numbers`, not stored, so that the page stays the same bytes). Two limits of that comparison: the audit's minutes were a person's and these are the tool's, so what the test shows is that no step now needs the code, a file search or a document; and the reviewer of the first audit found three numbers fully traceable, eleven reproducible through configuration or code and two that stopped at a choice made in code, while here every one of the 16 resolves to an equation or a definition, inputs with a source and the assumptions. The one thing that does not resolve is the *search* that chose the gauge (R1, gap 1).

## The owner's open decisions

Collected from the reports of the stages. Each is a choice the agents made and the owner has not confirmed; none is hidden in the code, each is described here.

1. **Legacy lock or per-field override on regeneration (S4).** A wire locked before reasons were kept keeps all four values (gauge, part, colour, length) when generated again and is shown as *Locked, no reason recorded*. The alternative is to turn such a lock into per-field overrides when it is next regenerated, each needing a reason.
2. **`journal.json`: merge conflicts and an unauthenticated author (S4).** The journal is one append-only file; two Git branches that both add entries conflict when merged. The author is taken from `--author`, `HARNESS_AUTHOR`, the Git name or the user of the computer, and nobody checks it.
3. **Trust for plug-ins, and the severity of an extension that is enabled but not applied (S8).** Trust is kept per user and computer, keyed to the SHA-256 of the code, outside the project, so a cloned repository cannot trust itself and a colleague trusts again. How seriously the tool reports an extension a project enables that is not applied (not trusted, or broken) is the stage's choice.
4. **`derivations.json` format 3 (S5).** The format number went from 2 to 3 for the cross-section of a gauge (`area_mm2`, decision D2); a reader that checks the format number must be told.
5. **The place of the run record (S5).** It is written beside the outputs, not in `manifest.json` and in no hash. Another place (a folder of its own) is possible.
6. **Whether the GUI Export offers the open data (S5).** Today `export-data` is the command line and the API only.
7. **The apostrophe un-escape in stamped CSVs (S6).** The tool marks text that starts with `+`, `-`, `=` or `@` with an apostrophe so a spreadsheet does not run it; every importer now gives the text back without the apostrophe, and skips the stamp line of the tool's own files.
8. **Extra read-summary lines on the importers (S6).** Every file import prints `Read N row(s) ...`, the columns read and a `warning:` for each column left out, before the rows; the lines printed before are printed as before.
9. **The strictness of the Electrical and AIT role split (S9).** Electrical shows everything except the As-built page; AIT hides the model areas and the diagram-edit menu entries. Say if the split should be stricter.
10. **A length tolerance for as-built records (S9).** The tool lists the difference between the designed and the actual cut and strip lengths and applies no tolerance.
11. **The release gate and as-built records (S9).** A release does not freeze the records and the gate ignores them; the outputs go stale when the records change.
12. **The values that count as needed for an as-built record (S9).** Fixed in the code: serial, who built and inspected, a lot per part, cut length, crimp tool for crimped pins, and a result with its measured value per test. Confirm they are the right ones.

Added by this audit, for the owner to decide:

13. **Per-key metadata in the JSON files themselves (R3).** Built as an opt-in in 1.13.0: the reserved key `_about` of each `config/*.json` (`settings DIR --annotate`, `--no-annotate`, `new --annotate-config`), outside every hash and output. What remains for the owner: whether it should be on by default for new projects (today `new` writes none unless `--annotate-config`), whether a save should refresh a stale one by itself (today only the command does, and `validate` warns), and whether a team wants its own notes per key (not built; `_about` is the tool's text).
14. **Whether the choice of a gauge should be a derivation (R1).** It would add the search (the candidates tried, the limit of each, the drop of each) to `explain`.
15. **Whether the Explain window and `explain` should print the link to the page of the model** (R1; the code has it, the screens do not show it).
16. **Whether the three limit rules without an assumption ID should get one** (R12). Done: `A-PIN-ONE-WIRE`, `A-WIRE-VOLTAGE` and `A-EMC-ONE-BUNDLE`. What remains: whether `A-PIN-ONE-WIRE` should be a setting.
17. **The number of the release** (the plan: 1.12.0, a later minor, or 2.0.0 for the file-format changes), decided with the owner now that S10 is done.

## The limits of this verification

- **Nobody has looked at a real display.** The tests of the editor run with Qt's offscreen platform; they check texts, widgets and states, not what a person sees. No screen was reviewed for any of the stages, including the Why tab, the Explain window, the Assumptions window, the extensions dialog and the change history.
- **No compliance and no sign-off is claimed.** Neither the tool nor its documents make a claim of compliance; a standard is cited by its ID and title only, and no clause is reproduced. The example values (`flatsat`, `first-steps`) are placeholders for learning, not engineering data, and the tool records no source for them unless the project does.
- **Test counts are not asserted here.** How many tests passed, on Linux and on Windows, is what the continuous integration runs and the local runs reported at the time; this page states no number it did not read from a run. The focused runs of this stage were of the tests named in the pull request, not of the whole suite.
- **The author of the work is the author of the tests.** The tests were written by the agents that wrote the code, against hand calculations written in the tests; an independent review by a person is still to come.
- **The timings are the tool's, not a person's.** A person reading a derivation takes longer than the tool takes to give it.
- **The Python plug-ins are not sandboxed.** The trust prompt names the code; it does not limit it.
- **The S9 pages were not looked at by a person**: the workflow disclosure, the As-built page and the three roles are checked by tests with Qt's offscreen platform only.

## How to repeat it

```
python -m tools.trace_numbers              # the 16 numbers, with the seconds of each
python -m tools.trace_numbers --check      # is docs/transparency_trace_results.md current?
python -m pytest tests/test_models_docs_complete.py tests/test_trace_16_numbers.py tests/test_definition_of_done.py
harness-design-studio explain DIR W001-001        # any of the numbers, by hand
harness-design-studio settings DIR --json         # the settings, assumptions and definitions
harness-design-studio export-data DIR --out FOLDER && python docs/examples/open-data/reproduce.py FOLDER
```

Next: [the plan](transparency_plan.md), [the first audit](transparency_audit.md), [the trace results](transparency_trace_results.md), [the models](models/README.md), [the open decisions](OPEN_DECISIONS.md)
