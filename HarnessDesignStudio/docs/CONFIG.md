# Configuration reference

Rules live in `config/*.json` inside the project, not in code. There are seven files. Every file except `naming.json` has `"placeholder": true` until an engineer has reviewed it; set it to `false` afterwards. (`naming.json` ships with `"placeholder": false`, because name patterns are a style choice, not an engineering value.) Values shown as `null` are placeholders: results say so and the affected checks say *not checked*. Which standard to take values from is for you to decide; the tool ships none. `harness-design-studio config DIR` lists what is missing and checks what is set (ranges, table order); see IMPORTS.md. Generation runs the same check: a value that is set but invalid is reported as an error in the generation result and treated as unset (the gauge stays *pending*); the tool never uses it.

## Contents

- [The shape of a file](#the-shape-of-a-file)
- [What is checked (ranges)](#what-is-checked-ranges)
- [`segmentation.json`](#segmentationjson)
- [`segregation.json`](#segregationjson)
- [`derating.json`](#deratingjson)
- [`generation.json`](#generationjson)
- [`emc.json`](#emcjson)
- [`naming.json`](#namingjson), with [`signal_counterparts`](#the-words-for-the-two-ends-of-a-line-since-190) and [`release_distinct_roles`](#different-people-in-a-release-since-190)
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

Keys that are left out stay unset (`null`). `harness-design-studio validate` accepts this file, and `harness-design-studio config DIR` counts the four keys as set. Put a key outside `values` and the file is rejected: `harness-design-studio validate` prints `ERROR quarantined: ... bundle_derating: Extra inputs are not permitted`, sets the file aside and falls back to the built-in placeholder for that file. A new project already contains all seven files with every key; edit those instead of writing one from scratch.

## What is checked (ranges)

`harness-design-studio config DIR`, `harness-design-studio validate`, the editor (rule `config-invalid`) and generation all use the same checks. A value that is set but outside its range is an error that names the file, the key and the limit (`config/generation.json: default_gauge_awg must be a whole number from 0 to 40.`); generation reports it and treats the value as unset, and never uses it. `null` (not decided) is never an error.

| Value | Allowed |
| --- | --- |
| `bundle_derating`, `temperature_derating`, `contact_current_factor`, `connector_voltage_factor_withstand`, `connector_voltage_factor_rated`, `rf_power_factor`, `wire_voltage_factor` | a number above 0 and at most 1 |
| `bundle_factor_by_count` | a table of wire count (1 or more) to K, each K above 0 and at most 1, not rising as the count grows |
| `partial_load_factor` | `below_25_percent`, `25_to_50_percent` and `above_50_percent`, each above 0 and at most 2 |
| `ampacity_a_by_awg` | gauges are whole numbers 0 to 40, amperes above 0, and a thinner wire (higher AWG number) never carries more than a thicker one |
| `spare_pin_fraction` | 0 or more, below 1 |
| `max_voltage_drop_v`, `conductor_resistivity_ohm_m`, `test_continuity_max_ohm`, `test_isolation_min_mohm`, `test_isolation_voltage_v` | above 0 |
| `service_loop_m`, `mass_margin_fraction`, `connector_temperature_margin_c`, `wire_temperature_margin_c` | 0 or more |
| `power_signal_gap_pins`, `power_return_gap_pins` | a whole number, 0 or more |
| `default_gauge_awg` | a whole number from 0 to 40 |
| `max_mating_cycles` | a whole number, 1 or more |
| `max_ambient_temperature_c` | a temperature in degC above -273.15 |
| `shield_end_a`, `shield_end_b` | `backshell_360`, `pigtail` or `floating` (not for a coax: its outer conductor is always bonded at both ends, `backshell_360`, since 1.10) |
| `category_pairs_to_separate`, `conflicting_class_pairs` | a list of pairs of two different names, each pair once (`["A","B"]` and `["B","A"]` are the same pair) |
| `forbid_nominal_with_redundant`, `forbid_pyro_with_other` | `true` or `false` |
| `classes` (emc) | a list of non-empty class names |
| `contact_rating_key` | the name of a part rating |
| `titleblock.fields` | known field names, each at most once, written as text (see below) |
| `signal_counterparts` (naming) | a list of pairs of two different words made of letters, no word in two pairs; an empty list is allowed (see below) |
| `release_distinct_roles` (naming) | `true` or `false` (see below) |

Numbers are written as numbers, not as text (`"0.5"` is not accepted). The limits of the project data itself (a wire gauge 0 to 40, a length 0 to 10000 m, a pin count 1 to 1000, ...) are in [`FILE_FORMAT.md`](FILE_FORMAT.md#number-ranges). While a harness is released, most of these files are frozen: see [`FILE_FORMAT.md`](FILE_FORMAT.md#what-a-release-freezes).

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
| `shield_end_a`, `shield_end_b` | grounding concept: `backshell_360`, `pigtail` or `floating` for each end (a coax is the exception: its outer conductor is bonded at both ends, so the rule `shield-wrong-end` does not compare it with the concept) |
| `wire_colour_by_signal` | optional, absent by default: colour of the wire for each signal name, for example `{"PWR": "red", "RTN": "black"}`. Used when a wire has no colour of its own. The build workbook shows the wire in that colour with its name and IEC 60757 code (BK, RD, ...), and the harness drawing, when it is written, draws it in that colour. The tool defines no colours of its own. **Edit > Wire colours...** in the editor sets it from a list (undoable); a wire between two different signals (labelled `TX+/RX+`) takes the colour of the first |
| `test_continuity_max_ohm`, `test_isolation_min_mohm`, `test_isolation_voltage_v` | limits printed in the test tables |

## `emc.json`
| Key | Meaning |
| --- | --- |
| `classes` | a list of the EMC class names your project uses, kept for reference. No rule reads it. The class of an interface is the `emc_class` of its interface type, and the rules compare those with `conflicting_class_pairs` |
| `conflicting_class_pairs` | pairs of EMC classes that must not share a harness, for example `[["A", "B"]]` |

## `naming.json`
| Key | Default | Meaning |
| --- | --- | --- |
| `harness` | `W{n:03d}` | name of a harness (`W001`) |
| `box_connector` | `{unit}-J{n:02d}` | in the shipped file, but the generator does not read it: a device's connectors are always named `<unit>-Jnn` (`RW1-J01`) |
| `cable_connector` | `{harness}-P{n}` | cable connector of a harness (`W001-P1`) |
| `wire` | `{harness}-{n:03d}` | wire (`W001-001`) |
| `shield` | `{harness}-S{n}` | shield (`W001-S1`) |
| `branch` | `{harness}-B{n}` | branch point |
| `segment` | `{harness}-L{n}` | routing segment |

### The words for the two ends of a line (since 1.9.0)

Not a name pattern but a style choice of the same kind: the words that are the two ends of one line. The review of connections and the pairing proposal split a signal name into words (`UART_TX` is UART, TX; `SPW_DOUT+` is SPW, DOUT, +) and pair a transmit word with its receive word when everything else in the two names is the same, with or without a prefix (`UART_TX` and `RX`, `SPW_DOUT+` and `SPW_DIN+`, `MOSI` and `MISO`). Two equal names that both carry a transmit word (or both a receive word) are never paired by the proposal and are warned about in the review.

| Key | Default | Meaning |
| --- | --- | --- |
| `signal_counterparts` | not set: `[["TX","RX"], ["TXD","RXD"], ["TXP","RXP"], ["TXN","RXN"], ["DOUT","DIN"], ["MOSI","MISO"], ["SDO","SDI"]]` | a list of pairs of words; the first word of a pair is the transmit word, the second the receive word; case does not matter |

Example for a program that also names its lines `OUT` and `IN`: `"signal_counterparts": [["TX","RX"], ["MOSI","MISO"], ["OUT","IN"]]` (a list replaces the default table, so repeat the pairs you still want). Each word is made of letters only (digits and signs such as `+`, `-` and `_` are separators in a name, not parts of a word), and a word is in one pair only. An empty list `[]` means no counterparts at all: only equal names are paired. The key is left out of new projects and out of the shipped file, so the files of an existing project do not change. A value that is not valid is an error of the check (`config/naming.json: signal_counterparts ...`, rule `config-invalid`, also reported by generation) and the default table is used until it is corrected. `harness-design-studio config DIR --counterparts "TX=RX, MOSI=MISO, OUT=IN"` writes it (`default` takes the key out again, `none` writes `[]`); `config DIR` then lists it. A pin can also say which way it runs (`Pin.direction`, [`FILE_FORMAT.md`](FILE_FORMAT.md#links-and-pin-roles-m2-schema-version-stays-1)); where it does, the directions decide before the names.

The shipped file lists only the first four keys; `shield`, `branch` and `segment` use the defaults above until you add them. A pattern that does not give a different valid ID for every number (tried up to 200; a reserved name such as COM1 is not valid) is reported and the default is used. IDs are stable once released.

### Different people in a release (since 1.9.0)

Off unless a project switches it on, and then a release works exactly as it did: one name can author, check and release a harness, and the dates are only compared with the last entry of the same harness. The setting is for a project that wants the four-eyes principle of change control written down.

| Key | Default | Meaning |
| --- | --- | --- |
| `release_distinct_roles` | not set (the same as `false`) | `true`: the author, the checker and the person who releases a harness are three different people |

While it is `true`:

- **Three different people.** The author is the person who put the harness into review (`harness-design-studio review`, **Submit for review** in the editor); a harness that was never submitted has no author and is refused with the sentence *Nobody is recorded as the author of W001 ...*. The checker (`--checker`, *Checked by*) must be named. The person who releases (`--by`, *Your name*) is the approver. Two of the three with the same name are refused with *The checker and the person who releases it must be different people, but both are 'Z'.* Names are compared without regard to letter case, width and extra spaces (`ada  LOVELACE` is `Ada Lovelace`); the tool cannot know that two different spellings are one person, so a team that wants more must agree on one spelling.
- **The date.** The date of a review, a release and a new revision may not be earlier than the latest date in the change log or in a baseline of the **whole project** (not only of the same harness: `The date 2026-03-01 is earlier than the latest entry of the project's change log (2026-03-05, W002). Use that date or a later one.`), and not more than one day after today (a day, because two places do not have the same clock: `The date 2027-01-01 is more than 1 day after today (2026-10-28). Use today's date.`). The rule that a date may not be earlier than the last entry of the same harness holds with or without the setting. The other two parts of the rule are not applied without the setting, because a project may have recorded its releases in another order or may state a release date in the future on purpose.
- **The name from Git.** When `--by` is left out, the name that Git has for the person (`user.name`) is used and the command says so (`Name taken from Git (user.name): Ann Author.`); in the editor it is the name the dialog starts with when none was saved before. The `git` program is not started: the tool reads `user.name` from the Git configuration files, in this order, the last one winning: `$XDG_CONFIG_HOME/git/config` (or `~/.config/git/config`), `~/.gitconfig`, and the `config` of the repository around the project folder (`GIT_CONFIG_GLOBAL` replaces the first two, as it does for Git). `include` lines, the system file and the environment variable `GIT_AUTHOR_NAME` are not read. When Git has no name, nothing is made up and `--by` is required as before.

`harness-design-studio config DIR --distinct-roles on` writes the key and `--distinct-roles off` takes it out again, so a project that switches it on and off again has its file back byte for byte; `config DIR` lists it while it is on. `naming.json` is not frozen by a release, so the setting can be switched at any time; it never changes a harness that is released already. It does not make the harness plans out of date. A value that is not `true` or `false` is an error of the check (`config/naming.json: release_distinct_roles must be true or false.`, rule `config-invalid`) and the setting stays off. The editor has no switch for it yet: in the editor the dialogs follow the file, and the file is edited with the command or by hand.

## `titleblock.json`
| Key | Meaning |
| --- | --- |
| `fields` | which title block fields appear, in order: `project`, `harness_id`, `title`, `revision`, `date`, `author`, `checker`, `approver`, `sheet`, `status`. None is mandatory (leave `sheet` out to hide the sheet number). A name that is not in this list, a name twice, or an entry that is not text is a configuration error; the default fields are drawn until it is fixed. Empty or missing means the default: `project`, `harness_id`, `title`, `revision`, `status`, `sheet` |

## Optional values from the supplied standards (D-131)

None of these is set by default. `harness-design-studio config DIR --apply-profile ecss-q-st-30-11c` (and `ecss-e-st-20-07c`) fills the ones that are still unset and keeps what you set; each value cites the requirement it comes from in the command output and in `src/harness_design_studio/core/standard_profiles.py`. A file the profile changes is set to `"placeholder": true` again, even if you had reviewed it before, because the new values are not reviewed; set it back to `false` after your review. A rule that needs one of these values or a part rating stays silent without it, and the rule `unchecked-config` says what was not checked.

### `derating.json`, additional keys
| Key | Meaning | Source (requirement ID) |
| --- | --- | --- |
| `connector_voltage_factor_withstand` | working voltage as a fraction of the connector's dielectric withstanding voltage (0.25) | ECSS-Q-ST-30-11_0140051 |
| `connector_voltage_factor_rated` | working voltage as a fraction of the rated voltage (0.75); the lower of the two limits applies | ECSS-Q-ST-30-11_0140051 |
| `connector_temperature_margin_c` | degrees below the maximum rating (30) | ECSS-Q-ST-30-11_0140051 |
| `rf_power_factor` | RF power as a fraction of the rating (0.75); recorded, no rule yet (no RF power on interfaces) | ECSS-Q-ST-30-11_0140058 |
| `wire_voltage_factor` | working voltage as a fraction of the wire's rated voltage (0.5) | ECSS-Q-ST-30-11_0140213 |
| `wire_temperature_margin_c` | degrees below the manufacturer's maximum for the wire surface (50); only the ambient part is checked (`max_ambient_temperature_c`), self-heating needs a thermal analysis | ECSS-Q-ST-30-11_0140213 |
| `bundle_factor_by_count` | table: number of wires to factor K (above 0, at most 1, not rising with the count). A bundle uses the next listed count; replaces `bundle_derating` in sizing and in the rules `current-over-wire` and `bundle-current`, which use one limit (the ampacity times K times `temperature_derating`; `bundle-current` takes an unset `temperature_derating` as 1). The single wire current is your `ampacity_a_by_awg`. | ECSS-Q-ST-30-11_0140218 |
| `partial_load_factor` | table L for partly loaded bundles; recorded, not applied (the report says so) | ECSS-Q-ST-30-11_0140220 |
| `max_mating_cycles` | mating cycles a connector may be used for (50) | ECSS-Q-ST-30-11_0140056 |

### `generation.json`, additional key
`power_return_gap_pins`: unassigned contacts left between the supply and the return pin of a power interface (1). Default (unset): they sit side by side, as before. ECSS-Q-ST-30-11_0140052.

### `emc.json`, additional keys
| Key | Meaning |
| --- | --- |
| `shield_bonding` | `both_ends_backshell`: every shield must be bonded at both ends through a 360 degree backshell (ECSS-E-ST-20-07_0080041, 0080042) |
| `same_class_one_bundle` | `true`: interfaces of one EMC class between two devices should run in one harness (ECSS-E-ST-20-07_0080035) |

### Part ratings used by the rules (keys of `ratings` in the parts library)
`rated_voltage_v`, `dielectric_withstand_v`, `max_temp_c`, `mating_cycles` (connectors and wires as stated above). A part without the rating the rule needs is listed under *not checked*. The part fields `manufacturer` and `specification` are used by the rules `connector-manufacturer` and `wire-specification`.

Next: [`PLACEHOLDERS.md`](PLACEHOLDERS.md), [fill in engineering values](user-manual/fill-in-engineering-values.md).
