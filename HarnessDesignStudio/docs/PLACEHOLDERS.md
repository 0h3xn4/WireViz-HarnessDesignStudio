# Placeholder values an engineer must fill in

The tool never invents numbers from standards. These shipped values are placeholders; `harness-design-studio validate` reports `placeholder_config` while any remain. Set `"placeholder": false` in the file once reviewed.

| File (`config/`) | What is needed | Owner | Needed for |
| --- | --- | --- | --- |
| `derating.json` | contact current factor, bundle derating, max ambient temperature, max voltage drop, spare pin fraction (all `null`) | EE / program standard (ECSS-Q-ST-30-11 or program rules) | wire sizing and the current, voltage drop and spare pin checks |
| `emc.json` | EMC classes and their rules (`null`) | EMC engineer | the EMC separation checks |
| `generation.json` | conductor resistivity, service loop, mass margin, pin gaps, shield ends, test limits (all `null`); the wire parts are example parts | EE | wire sizing, lengths, mass, shield checks and the test tables |
| `segregation.json` | which category pairs must be separated (`null`); the nominal/redundant and pyro rules are on by default | EE | the separation checks |
| `segmentation.json` | confirm the harness boundary rule (default `per_connector_pair`: one harness for each pair of unit connectors; `per_unit_pair` and `per_zone_pair` group more interfaces into one harness) | Owner (DECISIONS D-10) | how interfaces are grouped into harnesses |
| `titleblock.json` | company title block layout | Owner (D-15) | the title block of the drawings |

`naming.json` is not in the table: it ships with `"placeholder": false`, because the name patterns are a style choice and not an engineering value. That is why `harness-design-studio validate` lists six placeholder files, not seven.

The templates (`harness-design-studio templates FOLDER`) contain a set of **demo values** for these files so that wire sizing, voltage drop and test limits can be seen working. They are not engineering data and the files stay `"placeholder": true` (D-129). Replace them with your programme's values.

Library: every starter part (Micro-D 9, 15, 21, 25 and 31 pin, RJ45, SMA, wires, sleeving, labels, and some older D-sub, MDM, circular and TNC parts) is `unverified: true`, `approval: "pending"`, with no mass or ratings. Import or enter real parts before any result is trusted.
Interface types: starter types are `unverified`; impedance, EMC class and default gauge are `null`.

## Wire sizing, lengths, mass and shields (all defaults are `null`; generation reports what is missing)
| File (`config/`) | Key | Effect while `null` |
| --- | --- | --- |
| `derating.json` | `ampacity_a_by_awg` (e.g. `{"20": amps}`), `bundle_derating`, `temperature_derating`, `max_voltage_drop_v` | wire gauge stays "pending" |
| `generation.json` | `conductor_resistivity_ohm_m` | voltage-drop check skipped, gauge pending |
| `generation.json` | `power_signal_gap_pins` | 0 used, noted in the provenance |
| `generation.json` | `service_loop_m` | 0 used; lengths exclude service loops |
| `generation.json` | `mass_margin_fraction` | no margin shown |
| `generation.json` | `shield_end_a`, `shield_end_b` | shield grounding concept left floating |
| `generation.json` | `wire_part_by_construction` | example library parts (not qualified) |
Library parts need `mass_g` and `mass_per_m_g` for a complete mass; otherwise the result lists what is missing.

## Design rule checks: what keeps a rule silent
| File (`config/`) | Key | Rules that stay silent (and say "not checked") while `null` |
| --- | --- | --- |
| `derating.json` | `contact_current_factor` | current over contact |
| `derating.json` | `ampacity_a_by_awg`, `bundle_derating`, `temperature_derating` | current over wire |
| `derating.json` | `max_voltage_drop_v` (with `generation.conductor_resistivity_ohm_m`) | voltage drop |
| `derating.json` | `spare_pin_fraction` | spare pins low |
| `generation.json` | `shield_end_a`, `shield_end_b` (grounding concept) | shield unterminated, shield wrong end |
| `segregation.json` | `category_pairs_to_separate`, e.g. `[["power", "analog"]]` | category mixed |
| `emc.json` | `conflicting_class_pairs`, e.g. `[["A", "B"]]` (format chosen by the tool; the owner may change it) | EMC mixed |
| `derating.json` | `bundle_factor_by_count` | bundle current; replaces `bundle_derating` in wire sizing and in current over wire |
| `derating.json` | `connector_voltage_factor_withstand`, `connector_voltage_factor_rated` | connector voltage |
| `derating.json` | `wire_voltage_factor` | wire voltage |
| `derating.json` | `max_ambient_temperature_c` with `connector_temperature_margin_c`, `wire_temperature_margin_c` | temperature margin |
| `derating.json` | `max_mating_cycles` | mating cycles |
| `generation.json` | `power_return_gap_pins` | power return adjacent |
| `emc.json` | `shield_bonding`, `same_class_one_bundle` | shield bonding, shield parts, EMC class split |
Part ratings: `ratings.contact_current_a` on connector parts (key name set by `derating.contact_rating_key`); the rules of the standard profiles (D-131) also need `rated_voltage_v`, `dielectric_withstand_v`, `max_temp_c`, `mating_cycles`, `conductive_finish`, `shield_insulated` on the parts. A rule whose part has no such rating is silent for that part, and `unchecked-config` names the part. A wire the current or voltage-drop checks must skip (no gauge, no length, no bundle factor for its wire count) is listed there too.

## Test limits, title block and mass data
| File (`config/`) | Key | Effect while `null` |
| --- | --- | --- |
| `generation.json` | `test_continuity_max_ohm`, `test_isolation_min_mohm`, `test_isolation_voltage_v` | test tables show "TBD (placeholder)" |
| `titleblock.json` | `fields` (order and choice of title block fields; D-15) | default field list; date, author, checker, approver show "-" until a release records them |
| library | `mass_g`, `mass_per_m_g` on parts | mass tables say which data is missing |

## Build data (1.7.0): empty until a person enters it
These are not placeholder values in a config file; they are optional fields of the design that the tool never fills in or computes. While one is empty, the build workbook shows `to fill in` on an amber cell and its *Start here* sheet counts what is open, and the tables leave the column out when nothing in the project uses it.

| Where | Field | Needed for |
| --- | --- | --- |
| `physical/harnesses/<ID>.json`, a wire | `strip_a_mm`, `strip_b_mm` (the insulation stripped at each end) | the strip columns of the cut list and the wire list |
| `physical/connectors/<unit>.json`, a pin of a unit (copied to the cable pin by Generate; on a harness made by hand, the pin of the cable connector) | `contact_part` (a library part of the category `contact`) | the *Contact* column of the connector blocks and the pinouts, and the contact lines of the BOM |
| `library/contact.json`, a part | `tool` (the crimp tool or its setting) | the *Tool* column of the connector blocks |
| `physical/harnesses/<ID>.json` | `accessories` (sleeving, heat shrink, labels, backshells) | the *Accessories* sheet, `accessories.csv` and the BOM lines of accessory parts |

How to enter them: [enter the build data](user-manual/enter-the-build-data.md).

Next: [`CONFIG.md`](CONFIG.md), [fill in engineering values](user-manual/fill-in-engineering-values.md).
