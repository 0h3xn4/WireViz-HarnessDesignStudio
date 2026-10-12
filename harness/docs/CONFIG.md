# Configuration reference

Rules live in `config/*.json` inside the project, not in code. There are seven files. Every file except `naming.json` has `"placeholder": true` until an engineer has reviewed it; set it to `false` afterwards. (`naming.json` ships with `"placeholder": false`, because name patterns are a style choice, not an engineering value.) Values shown as `null` are placeholders: results say so and the affected checks say *not checked*. Which standard to take values from is for you to decide; the tool ships none. `harness config DIR` lists what is missing and checks what is set (ranges, table order); see IMPORTS.md. Generation runs the same check: a value that is set but invalid is reported as an error in the generation result and treated as unset (the gauge stays *pending*); the tool never uses it.

## Contents

- [The shape of a file](#the-shape-of-a-file)
- [`segmentation.json`](#segmentationjson)
- [`segregation.json`](#segregationjson)
- [`derating.json`](#deratingjson)
- [`generation.json`](#generationjson)
- [`emc.json`](#emcjson)
- [`naming.json`](#namingjson)
- [`titleblock.json`](#titleblockjson)
- [Optional values from the supplied standards (D-131)](#optional-values-from-the-supplied-standards-d-131)

## The shape of a file

Every file is a wrapper with three fields: `name` (the file's name without `.json`), `placeholder` and `values`. **The keys of the tables below go inside `values`**, never at the top level. A complete `config/derating.json` with four keys set (the numbers are the demo values of the templates, for learning only, not engineering data):

```json
{
  "name": "derating",
  "placeholder": true,
  "values": {
    "ampacity_a_by_awg": {
      "20": 5.0,
      "22": 3.0
    },
    "bundle_derating": 0.8,
    "max_voltage_drop_v": 0.5,
    "temperature_derating": 0.9
  }
}
```

Keys that are left out stay unset (`null`). `harness validate` accepts this file, and `harness config DIR` counts the four keys as set. Put a key outside `values` and the file is rejected: `harness validate` prints `ERROR quarantined: ... bundle_derating: Extra inputs are not permitted`, sets the file aside and falls back to the built-in placeholder for that file. A new project already contains all seven files with every key; edit those instead of writing one from scratch.

## `segmentation.json`
| Key | Meaning |
| --- | --- |
| `mode` | how interfaces are grouped into harnesses: `per_connector_pair` (default), `per_unit_pair`, `per_zone_pair` |

## `segregation.json`
| Key | Meaning |
| --- | --- |
| `forbid_nominal_with_redundant` | nominal and redundant chains never share a harness or connector (default true) |
| `forbid_pyro_with_other` | pyro lines never share a harness or connector (default true) |
| `category_pairs_to_separate` | list of category pairs that must not share a harness, for example `[["power", "analog"]]` |

## `derating.json`
| Key | Meaning |
| --- | --- |
| `contact_current_factor` | fraction of the contact rating that may be used |
| `bundle_derating` | factor for wires in a bundle |
| `temperature_derating` | factor for the maximum ambient temperature |
| `max_ambient_temperature_c` | hottest ambient temperature; the `temperature-margin` rule compares it with the part ratings |
| `max_voltage_drop_v` | allowed voltage drop over a wire path |
| `spare_pin_fraction` | share of pins that must stay spare |
| `ampacity_a_by_awg` | current in amperes per gauge, for example `{"20": 5.0}` |
| `contact_rating_key` | which entry of a connector part's `ratings` is the contact current (default `contact_current_a`) |

## `generation.json`
| Key | Meaning |
| --- | --- |
| `wire_part_by_construction` | library wire part used for each construction (example parts by default) |
| `default_gauge_awg` | gauge when none is decided |
| `service_loop_m` | extra length added at each end |
| `conductor_resistivity_ohm_m` | for the voltage drop calculation |
| `power_signal_gap_pins` | empty pins between power and signal pins |
| `mass_margin_fraction` | margin added to masses |
| `shield_end_a`, `shield_end_b` | grounding concept: `backshell_360`, `pigtail` or `floating` for each end |
| `wire_colour_by_signal` | optional, absent by default: colour of the wire for each signal name, for example `{"PWR": "red", "RTN": "black"}`. Used when a wire has no colour of its own. The harness drawing draws the wire in that colour and writes its IEC 60757 code (BK, RD, ...). The tool defines no colours of its own. **Edit > Wire colours...** in the editor sets it from a list (undoable); a wire between two different signals (labelled `TX+/RX+`) takes the colour of the first |
| `test_continuity_max_ohm`, `test_isolation_min_mohm`, `test_isolation_voltage_v` | limits printed in the test tables |

## `emc.json`
| Key | Meaning |
| --- | --- |
| `classes` | EMC classes (format is yours to define) |
| `conflicting_class_pairs` | pairs of EMC classes that must not share a harness, for example `[["A", "B"]]` |

## `naming.json`
| Key | Default | Meaning |
| --- | --- | --- |
| `harness` | `W{n:03d}` | name of a harness (`W001`) |
| `box_connector` | `{unit}-J{n:02d}` | in the shipped file, but the generator does not read it: a unit's connectors are always named `<unit>-Jnn` (`RW1-J01`) |
| `cable_connector` | `{harness}-P{n}` | cable connector of a harness (`W001-P1`) |
| `wire` | `{harness}-{n:03d}` | wire (`W001-001`) |
| `shield` | `{harness}-S{n}` | shield (`W001-S1`) |
| `branch` | `{harness}-B{n}` | branch point |
| `segment` | `{harness}-L{n}` | routing segment |

The shipped file lists only the first four keys; `shield`, `branch` and `segment` use the defaults above until you add them. A pattern that does not give a different valid ID for every number (tried up to 200; a reserved name such as COM1 is not valid) is reported and the default is used. IDs are stable once released.

## `titleblock.json`
| Key | Meaning |
| --- | --- |
| `fields` | which title block fields appear, in order: `project`, `harness_id`, `title`, `revision`, `date`, `author`, `checker`, `approver`, `sheet`, `status`. None is mandatory (leave `sheet` out to hide the sheet number). A name that is not in this list, a name twice, or an entry that is not text is a configuration error; the default fields are drawn until it is fixed. Empty or missing means the default: `project`, `harness_id`, `title`, `revision`, `status`, `sheet` |

## Optional values from the supplied standards (D-131)

None of these is set by default. `harness config DIR --apply-profile ecss-q-st-30-11c` (and `ecss-e-st-20-07c`) fills the ones that are still unset and keeps what you set; each value cites the requirement it comes from in the command output and in `src/harness_design_studio/core/standard_profiles.py`. The file stays `"placeholder": true` until you review it. A rule that needs one of these values or a part rating stays silent without it, and the rule `unchecked-config` says what was not checked.

### `derating.json`, additional keys
| Key | Meaning | Source (requirement ID) |
| --- | --- | --- |
| `connector_voltage_factor_withstand` | working voltage as a fraction of the connector's dielectric withstanding voltage (0.25) | ECSS-Q-ST-30-11_0140051 |
| `connector_voltage_factor_rated` | working voltage as a fraction of the rated voltage (0.75); the lower of the two limits applies | ECSS-Q-ST-30-11_0140051 |
| `connector_temperature_margin_c` | degrees below the maximum rating (30) | ECSS-Q-ST-30-11_0140051 |
| `rf_power_factor` | RF power as a fraction of the rating (0.75); recorded, no rule yet (no RF power on interfaces) | ECSS-Q-ST-30-11_0140058 |
| `wire_voltage_factor` | working voltage as a fraction of the wire's rated voltage (0.5) | ECSS-Q-ST-30-11_0140213 |
| `wire_temperature_margin_c` | degrees below the manufacturer's maximum for the wire surface (50); only the ambient part is checked (`max_ambient_temperature_c`), self-heating needs a thermal analysis | ECSS-Q-ST-30-11_0140213 |
| `bundle_factor_by_count` | table: number of wires to factor K. A bundle uses the next listed count; replaces `bundle_derating` in sizing and in the rule `bundle-current`. The single wire current is your `ampacity_a_by_awg`. | ECSS-Q-ST-30-11_0140218 |
| `partial_load_factor` | table L for partly loaded bundles; recorded, not applied (the report says so) | ECSS-Q-ST-30-11_0140220 |
| `max_mating_cycles` | mating cycles a connector may be used for (50) | ECSS-Q-ST-30-11_0140056 |

### `generation.json`, additional key
`power_return_gap_pins`: unassigned contacts left between the supply and the return pin of a power interface (1). Default (unset): they sit side by side, as before. ECSS-Q-ST-30-11_0140052.

### `emc.json`, additional keys
| Key | Meaning |
| --- | --- |
| `shield_bonding` | `both_ends_backshell`: every shield must be bonded at both ends through a 360 degree backshell (ECSS-E-ST-20-07_0080041, 0080042) |
| `same_class_one_bundle` | `true`: interfaces of one EMC class between two units should run in one harness (ECSS-E-ST-20-07_0080035) |

### Part ratings used by the rules (keys of `ratings` in the parts library)
`rated_voltage_v`, `dielectric_withstand_v`, `max_temp_c`, `mating_cycles` (connectors and wires as stated above). A part without the rating the rule needs is listed under *not checked*. The part fields `manufacturer` and `specification` are used by the rules `connector-manufacturer` and `wire-specification`.

Next: [`PLACEHOLDERS.md`](PLACEHOLDERS.md), [fill in engineering values](user-manual/fill-in-engineering-values.md).
