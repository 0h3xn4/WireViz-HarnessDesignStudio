# Project file format (schema version 1)

A project is a folder of small, canonical JSON files: UTF-8, 2-space indent, sorted keys, `\n` line endings, trailing newline. The same model always produces the same bytes, so Git diffs show only real changes.

The screen says *device*, the files say *unit*: what the program shows as a device is stored as a `unit` (the folder `logical/units/`, the key `units`, the field `unit_id`). Version 1.7.0 and earlier called it a unit on the screen too. This page keeps the words of the files.

## Contents

- [Rules](#rules)
- [Versions and migration](#versions-and-migration)
- [Recovery mode](#recovery-mode)
- [Saving](#saving)
- [Locking](#locking)
- [Saving: file modes and temporary files](#saving-file-modes-and-temporary-files)
- [Number ranges](#number-ranges)
- [Hash](#hash)
- [Editor additions](#editor-additions-connector-use-layout-waivers-autosave-schema-version-stays-1)
- [Generation additions](#generation-additions-pins-mating-locks-generation-record-schema-version-stays-1)
- [Build data additions](#build-data-additions-170-schema-version-stays-1)
- [Links and pin roles](#links-and-pin-roles-m2-schema-version-stays-1)
- [Change control additions](#change-control-additions-review-release-baselines-change-log-schema-version-stays-1)
- [Device library file](#device-library-file-140-not-part-of-a-project)
- [Subsystem library file](#subsystem-library-file-m4-not-part-of-a-project)
- [Editing files by hand: JSON Schemas](#editing-files-by-hand-json-schemas)

```
project.json                      name, description, schema_version, tool_version (last saving tool)
config/<name>.json                segmentation, segregation, derating, generation, naming, emc, titleblock (seven files)
library/manifest.json             library name and version
library/<category>.json           {"parts": [...]} for connector, contact, backshell, wire, sleeving, label
logical/interface_types.json      {"interface_types": [...]}
logical/layout.json               {"zones": [...], "placements": [{id, x, y}]}  diagram lanes and unit positions
waivers.json                      {"waivers": [...]}  written only when a finding has been waived
logical/units/<subsystem>.json    {"units": [...]}
logical/interfaces/<subsystem>.json  {"interfaces": [...]}   grouped by the subsystem of the first endpoint
logical/links.json                {"links": [...]}  pin-to-pin links of two device connectors; written only when there is a link
physical/connectors/<subsystem>.json {"connectors": [...]}   box connectors, grouped by their unit's subsystem
physical/harnesses/<id>.json      one harness with its connectors, wires, splices, shields, branch points, segments, accessories
generated/generation.json         the last generation record (provenance for Explain)
outputs/                          written by `harness-design-studio export` (see OUTPUTS.md); safe to delete and regenerate
changelog.json                    the change log (append-only; entries cannot be deleted)
baselines/<harness ID>/<baseline ID>.json   frozen snapshot made at each release
.gitignore                        written once: *.bak, lock files, temp files, .harness-recovery/, .migration-backup-v*/
.gitattributes                    written once by `harness-design-studio new` (not by a save): Git treats generated/generation.json as binary (no conflict markers), see merge-fix; not part of the project format
.harness-recovery/session.json    autosave journal of an open project (not part of the project; ignore in Git)
```

Every `config/<name>.json` has the same shape, a wrapper with the file's name, the placeholder flag and the values:

```
{"name": "derating", "placeholder": true, "values": {"bundle_derating": 0.8}}
```

A key written outside `values` is rejected, the file is set aside (`quarantined`) and the built-in placeholder is used instead. [`CONFIG.md`](CONFIG.md) shows a complete file and lists the keys of all seven.

## Rules
- **Group file names are cosmetic.** Loading never depends on them; two subsystems whose names slug to the same file simply share it. Harness files must be named `<harness id>.json` (otherwise a warning).
- **IDs** match `[A-Za-z][A-Za-z0-9_.-]{0,63}`, no trailing dot, no Windows device names (`CON`, `NUL`, `COM1`, ...). Pin names allow a leading digit and up to 16 characters. IDs must be unique ignoring case. Connector IDs are unique across the whole project (box and harness connectors share one namespace), as are wire IDs.
- **Strict typing:** no type coercion (a string is never accepted for a number), unknown fields are rejected, `NaN`/`Infinity` are rejected, duplicate JSON keys are rejected, control characters are rejected in names and notes, and so are line and paragraph separators, the byte-order mark and private-use characters (direction controls and zero-width characters are still accepted). Dates (library date, release date, change log date) are written exactly `YYYY-MM-DD`.
- **Lists are sorted by ID** on save, except where order carries meaning (`endpoints`, `signals`, a connector's `pins` keep their order of entry).
- `null` means "not yet decided". The tool never fills engineering numbers on its own.

## Versions and migration
`schema_version` is an integer in `project.json`. A missing value means version 0.
- **Older file:** opened with an in-memory migration (`migrated` info message). Nothing on disk changes until you save; saving (or `harness-design-studio migrate`) first copies every original file to `.migration-backup-v<N>/`.
- **Newer file:** opened read-only (`newer_version` warning); entities the tool does not understand are quarantined and listed.
- Each migration is one function in `core/io/migrate.py`, tested against a fixture of the old format (`tests/fixtures/v0_project`).

## Recovery mode
A file that is not valid JSON/UTF-8, has duplicate keys, a wrong structure, or an invalid object does not stop loading: the bad part is reported (`quarantined`, `invalid_json`, `merge_conflict`, ...) and kept in memory as quarantine. The message says where: the line and column of a syntax error, the byte of a bad character, or the line where a set-aside object starts. It never quotes the content of the file (it may be export-controlled). A project file that is a link, larger than 64 MB or unreadable counts as damaged in the same way, and so does a file with a lone surrogate escape (`\ud800`), which cannot be written back as UTF-8. A project with quarantined data **cannot overwrite its folder**. "Save as" writes a new folder with `quarantine.json` (rejected objects, verbatim) and `quarantine/files/` (unreadable files, verbatim), so nothing is lost.

## Saving
Each file is written to a temp file, flushed, `fsync`ed and renamed; the previous version is kept as `<file>.bak`. Only changed files are written. Files for deleted objects are renamed to `.bak`, not erased. A crash can leave some files updated and others not, but every file is whole; `harness-design-studio validate` / `harness-design-studio check` report cross-file inconsistencies, and saves are refused while integrity errors exist. If the folder changed on disk since opening (e.g. a Git pull), a save with the opening fingerprint is refused.

## Locking
`.harness.lock` (pid, host name, start time, and on Linux the boot id of the computer and the start time of the process; no design data) prevents opening one project twice. A lock is taken over when it is stale: its process no longer exists, the computer was restarted since (other boot id), or the process number now belongs to another program (other process start time). A lock from another computer is respected, because it cannot be checked; the error names the lock file, and deleting that file is the way out when nobody has the project open. Locks made by older versions have no boot id and process start time and are checked by process number only. The lock is decided under a second, empty file next to it, `.harness.lock.takeover` (it stays in the folder after the first locked command; it holds no data, is ignored by the `.gitignore` the tool writes and may be deleted when nothing has the project open). A folder that is neither empty nor a project gets no lock and no helper file. The editor opens a project whose lock cannot be taken (for example on read-only media) read-only, with the note "This project was opened read-only because it cannot be locked for editing here" and the reason; a command that has to write says `error: a file or folder could not be used (...)` and ends with 2.

## Saving: file modes and temporary files
New files get the mode `0666` minus the user's umask (an existing file keeps its mode). A file that is a link is replaced by the new file and has no `.bak`; saving never reads through a link. Temporary files of a save are `.<file>.<8 characters>.tmp`; a later save removes the ones a killed save left behind (only names of that form in the project folder and the managed folders). The upgrade of an old project keeps its original files in `.migration-backup-vN/`, built as `.migration-backup-vN.partial` and renamed when complete; if that name already exists as anything but a real folder the upgrade is refused.

## Number ranges
The loader sets aside (reports, keeps in `quarantine.json`) an object with a number outside these ranges, and the editor refuses such an edit: wire gauge (AWG) 0 to 40, whole numbers; `length_m` of a wire or segment 0 to 10000; `strip_a_mm`, `strip_b_mm` of a wire and `length_mm` of an accessory 0 to 100000 (millimetres; a guard against a typing slip, not a design limit); `quantity` of an accessory a whole number from 1 to 9999; `max_current_a`, `voltage_v`, `impedance_ohm` above 0; part `pin_count` 1 to 1000; `mass_g`, `mass_per_m_g` and each `ratings` value 0 or more; `default_gauge_awg` 0 to 40; `next_harness_number` 1 or more; `schema_version` 1 or more. A missing value (`null`) is still allowed everywhere it was. What you see when a value is set aside on load (here a wire with gauge 99 and a length of -3 in a harness file):

```
ERROR   quarantined: A harness could not be loaded and was set aside: wires.0.gauge_awg: Input should be less than or equal to 40; wires.1.length_m: Input should be greater than or equal to 0 (line 452) [physical/harnesses/W001.json]
```

The whole object that holds the value is set aside (here the harness), the message names the field and the limit but never the value, and every command except `validate` and `check` then refuses the project with exit 2 until the file is corrected ([`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)).

## Hash
`model_hash` is the SHA-256 of all canonical files with the saving tool's version blanked. Every output file carries its first 12 characters, so a printed sheet can be traced to the exact model.

## Editor additions: connector use, layout, waivers, autosave (schema version stays 1)
All additions are optional with defaults, so projects saved before them load unchanged (tested against `tests/fixtures/m1_project`) and are upgraded on the next save.
- `Connector.carries`: list of interface-type IDs the connector is meant for (empty means any).
- `Endpoint.auto`: true while the connector was chosen by the tool and not yet confirmed by a person.
- `logical/layout.json`: ordered `zones` (diagram lanes) and one `placements` entry per unit (`id` is the unit ID, `x`/`y` in scene units). Units without a placement are placed deterministically at load (`edit.ops_autoplace`).
- `waivers.json`: `id` is `<rule>.<object>`; `justification` is mandatory (at least 10 characters); `finding_hash` (12 hexadecimal characters, optional, left out while empty; 1.11) is a hash of the rule and the statement of the finding that was waived: when the finding says something else later, the waiver no longer applies and the DRC report lists the finding under *Waivers that no longer fit*. A waiver without it applies as before.
- Autosave journal: the full set of project files as text in `.harness-recovery/session.json`, written (atomically) 1.5 s after the last change while a project folder is open; removed on save; offered for restore on the next open if it differs from the files on disk. Never written for the unsaved sample project, so no project content leaves the project folder.
- Not in the project: the theme, the interface size, *Reduce motion*, the recent projects and the layout of the window (which area and tab was open, where the panels were; kept for each project) are per-user settings in the editor's settings file (`HarnessDesigner.ini`, [`INSTALL.md`](INSTALL.md#where-things-are-stored)), never in a project folder. The format did not change with the new interface of version 1.3.0: a project saved by 1.2.0 or earlier opens as it is.

## Generation additions: pins, mating, locks, generation record (schema version stays 1)
All optional with defaults; projects saved before them load unchanged.
- `Pin.interface_id`: interface that owns the pin (set by generation; locked pins are never reassigned).
- `Pin.fixed`: the signal is defined by the unit design (imported from KiCad, `docs/KICAD.md`). Generation connects interfaces to the pin of the same name and never moves it. Default `false`.
- `Connector.mates_with`: on a cable connector, the box connector it mates with.
- `Wire.locked`: gauge, part, colour and length were set by a person; regeneration keeps them.
- `Pin.function`, `Connector.label` and `Harness.label` (1.4.0): free text a person gives a pin, a connector (box or cable end) and a harness. Written only when set; generation copies the function of a box pin to its cable pin and keeps the labels.
- `Wire.manual` and `ShieldGroup.manual` (1.4.0): a wire or a twisting or shield group that a person made; generation keeps it as it is, never matches it to an interface, and says when it cannot keep it. Written only when `true`.
- `Wire.label` and `Wire.note` (1.4.0): text for the wire labels instead of the signal name, and a remark. Written only when set; a project without them is byte-identical to one saved by 1.3.0, and 1.3.0 quarantines the fields when it opens a project that uses them.
- `Connector.locked` (workshop milestone M3, D-174): on a cable connector of a harness that Generate made, a person edited its part, gender, keying or pin details (the *Connectors* tab); generation keeps those values (the pins' IDs, their number and their contacts still follow the device connector) and names the connector in `locked_data_lost` when it cannot keep it. Written only when `true`; a project with no edited connector is byte-identical to one saved before.
- `Harness.generated`, `group_key`, `interfaces`: set for generated harnesses; a harness made by hand (*New harness*, 1.5.0) keeps `generated: false`. Releases 1.5.0 and 1.6.0 added no field: a project saved by 1.4.0 opens as it is.
- **How the 1.4.0 fields stay out of old projects.** The fields above that say "written only when set" are the model's *sparse* fields (`OMIT_WHEN_DEFAULT` in `core/model/base.py`): `Pin.function`, `Connector.label`, `Harness.label`, `Wire.label`, `Wire.note`, `Wire.manual` and `ShieldGroup.manual` (and, since the workshop milestone M3, `Connector.locked`). While a field has its default value it is left out of the file, so a project that does not use the feature keeps byte-identical files and the same model hash.
- `Part.mates_with`: library connector parts that mate with it.
- `generated/generation.json`: the last generation record: `input_hash`, `generator_version`, `next_harness_number`, `placeholders_used`, and `provenance` (object key to list of "rule: reason" lines; the data behind Explain).
- `config/generation.json`: generation settings (see PLACEHOLDERS.md).

## Build data additions (1.7.0; schema version stays 1)
Every field is optional and *sparse*: it is left out of the file while it is empty, so a project that does not use the build data keeps byte-identical files and the same model hash. They are a person's values: the tool sets none and computes nothing from them.
- `Wire.strip_a_mm`, `Wire.strip_b_mm`: the insulation stripped at the From end and at the To end, in millimetres. Generation keeps them, like the label and the note (they do not lock the wire).
- `Pin.contact_part`: the ID of a library part of the category `contact`, the contact the cable side uses on that pin. A person sets it on the pin of a unit (`physical/connectors/`), and generation copies it to the pin of the cable connector; on a harness made by hand it is set on the cable connector's own pin. A device library file carries it with the pin and, in its `parts`, the contact part itself (a part the project has already is kept as the project has it).
- `Part.tool`: the crimp tool, or its setting, of a part (free text; meant for a contact part), in `library/<category>.json`.
- `Harness.accessories`: a list of accessories, in the harness file, sorted by `id`. An accessory has `id`, `kind` (`sleeving`, `heat_shrink`, `label`, `backshell` or `other`), `part_id` (a library part or `null`), `target` (a connector or a wire of this harness, or `null` for the harness itself), `position` (words), `length_mm` (one piece), `quantity` (1 to 9999, default 1) and `note`. Generation keeps the accessories whose target still exists and names the others in a `locked_data_lost` warning.
- **Integrity.** An accessory whose `target` is not a connector or a wire of its harness is an error, `dangling_accessory`; two accessories with one ID in a harness are `duplicate_id`. Accessories are part of their harness for change control: a released harness is locked with them, and a release freezes the contact parts of its pins and the parts of its accessories like any part it uses (see "What a release freezes").
- Older tools: 1.6.0 and earlier do not know these fields; they set the fields aside and say so when they open a project that uses them (decision D-170), as for the fields of 1.4.0.

```
"accessories": [
  {"id": "ACC-002", "kind": "heat_shrink", "length_mm": 30.0, "note": "part not chosen yet", "part_id": null, "position": "50 mm from the P1 end", "quantity": 2, "target": "W001-P1"}
]
```

(One accessory of the practice project, as `physical/harnesses/W001.json` holds it, shown on one line here; the file itself has one key per line.) How to enter the values: [`user-manual/enter-the-build-data.md`](user-manual/enter-the-build-data.md).

## Links and pin roles (M2; schema version stays 1)
A *link* joins a connector of one device to a connector of another, pin to pin. The pinout is the truth: the tool proposes the pairs from the signal names on the pins and a person accepts or changes them. Everything here is optional and left out of the files while empty, so a project that uses none of it keeps byte-identical files, the same model hash and the same outputs. An older tool (1.7.0 and earlier) does not know `logical/links.json` and `Pin.role`; it sets them aside and says so when it opens a project that uses them, as for the earlier optional fields.
- `logical/links.json`: `{"links": [...]}`, sorted by `id`, **written only when the project has at least one link** (the file is removed again when the last link is deleted). A link has `id` (`L1`, `L2` ... unless a person chose another), `a_connector` and `b_connector` (IDs of box connectors, of two different devices), `pairs` (a list of `{"a_pin": ..., "b_pin": ...}`, the pin of the first connector and the pin of the second; the order is the order a person saw) and, only when used, `name` (a label), `harness_id` (the harness made from the link with *Create harness*) and `note`. A connector can be in several links; a pin can be in one pair of one link only.
- `Pin.role` (in `physical/connectors/`): `power`, `return`, `ground`, `signal`, `shield` or `spare`. Empty (and then left out) means *derived from the signal name*: `power` for a signal of an interface type of the power category (RTN excepted), `return` for RTN, `ground` for GND or the ground category, `signal` for any other signal. A person sets it where the name does not say it (a heater return, a spare pin).
- `Pin.direction` (in `physical/connectors/`, since 1.9.0; the schema version stays 1): which way the signal runs at this pin, seen from the device: `in`, `out` or `bidir`. Empty (and then left out of the file) means *not set*: the link review and the pairing proposal then take the direction from the interface types, as before. When it is set it decides first: `link_direction_conflict` is judged from the two directions set (output against output, input against input), also for the signals of one-directional types that the review otherwise exempts, and two equal transmit-looking or receive-looking names (`UART_TX` on both sides) are neither paired nor warned about when both pins have a direction, because the directions, not the names, say whether they fit. The pinout tables (`system/box_pinouts.csv`, `pinouts.csv`, `export-pinout`) get a last column `Direction` (`in`, `out`, `bidirectional`) **only while at least one pin has a direction**, so every existing file stays byte-identical; the pinout import reads it back. It is part of the JSON Schema of `physical/connectors/*.json` (`harness-design-studio schema`). A cable connector made from a link does not copy it. An older tool (1.8.1 and earlier) does not know the field and sets the file aside, as for the earlier optional fields.
- The words that are the two ends of one line (TX and RX, MOSI and MISO ...) are a setting of the project, not of the code: `config/naming.json` key `signal_counterparts` (a list of pairs of words, see [`CONFIG.md`](CONFIG.md#namingjson)); while it is not set the table the tool ships with is used, so no file changes.
- What a link carries (CAN, power ...) is **not stored**: it is worked out from the pins when it is shown (`core/links.py`, `derived_interfaces`).
- **Integrity.** `dangling_link` (a connector of the link is not a connector of a device), `link_pin_missing` (a paired pin does not exist), `link_pin_reused` (a pin in two pairs of a link, or in two links), `link_same_device` (both connectors on one device), and `unknown_harness` when `harness_id` names a harness that does not exist; all errors. The design rules `link-unpaired`, `link-direction`, `link-signal-mismatch` and `link-power-return` review the pairing; a project without links gives them nothing to report.
- **Change control.** A link is an object of the diff (`link`, its pairs read `1-3, 2-4`). A link whose `harness_id` is a released harness is locked with it: the change or deletion is refused with the reason, and a new link cannot name a released harness. The baseline of a harness made from a link records the link in `snapshot.links` (left out when the harness has none), and `harness-design-studio check` reports a hand edit of it as `released_modified`. Deleting a device deletes its links; deleting the harness clears `harness_id`; a pin that a link pairs cannot be deleted or renamed before the link changes.
- `system/export.json` has a `links` key only when the project has links.

```
{"links": [{"a_connector": "OBC-J01", "b_connector": "RW1-J02", "id": "L1", "pairs": [{"a_pin": "1", "b_pin": "3"}, {"a_pin": "3", "b_pin": "1"}]}]}
```

## Change control additions: review, release, baselines, change log (schema version stays 1)
- `Harness.author`, `checker`, `approver`, `released_on` (all optional): who put the harness into review, who checked and released it, and the release date (YYYY-MM-DD). `status` is `draft`, `in_review` or `released`; `revision` is letters.
- `baselines/<harness ID>/<baseline ID>.json`: `id` (`<harness>.<revision>`), `harness_id`, `revision`, `released_on`, `by`, `comment`, `content_hash`, `snapshot` (`units`, `interfaces`, `connectors` = box connectors, `harnesses` = the released harness, and the records listed below). Written once at release; never edited by the tool.
- `snapshot.parts`, `interface_types`, `config` and `waivers` record what the release froze (see "What a release freezes"). They are optional: a baseline made by an earlier version has none of them, is read without them and written back unchanged, and `harness-design-studio check` compares nothing for it.

### What a release freezes
A released harness locks, besides itself: the design fields of the interfaces it carries (not name, notes, requirement), the units those interfaces connect (not name, notes, zone), the box connectors it plugs into or that carry its interfaces (part, gender, keying, the pins of its interfaces and, since 1.9.0, every pin that one of its wires ends on, so also for a harness made from a connection or by hand: the pin and all its fields are frozen, the other pins of the connector stay editable), and, new in this version:
- **parts it uses**: the part of each of its connectors, the part of each wire, the contact part of each of its pins and the part of each of its accessories (1.7.0), the part of the box connectors above, and the counterpart named in `mates_with` of those parts. Every field but `notes` is frozen (approval, mass, `pin_count`, `unverified`, ratings, part number, ...).
- **interface types** of the interfaces it carries (every field but `name` and `notes`).
- **configuration its checks and outputs read**: all values of `derating`, `emc`, `segregation` and `titleblock`, and in `generation` the keys `conductor_resistivity_ohm_m`, `mass_margin_fraction`, `power_return_gap_pins`, `shield_end_a`, `shield_end_b`, `test_continuity_max_ohm`, `test_isolation_min_mohm` and `test_isolation_voltage_v`. These apply to every harness, so they are frozen while any harness is released. `segmentation`, `naming`, the other `generation` keys (which only decide how new harnesses are made) and the `placeholder` flags stay editable.
- **waivers** that name the harness or one of its objects are recorded in the baseline but not locked: a waiver can be added or changed after a release (the change log and `harness-design-studio compare` show it).

The editor and the data commands (`import-parts`, `config`; `library` only records the source of the data and is not affected) refuse a change to a frozen item with the reason and "start a new revision" (exit 1, also with `--dry-run`); `harness-design-studio check` reports a hand edit as `released_modified`. Allowed at any time: adding parts and interface types, editing and deleting those no released harness uses, and notes and names. To change a frozen item: `harness-design-studio revise` the harness (every released harness for configuration), make the change, release again.
- `changelog.json`: `{"changelog": [{id (C0001...), harness_id, revision, kind (review | release | new_revision), by, when, comment}]}`.
- `outputs/manifest.json` gained `content_hash` (see D-104).

## Device library file (1.4.0; not part of a project)

A device library (`harness-device-library`, D-165) is one JSON file that is kept outside any project. Its top level is `format` (the text `harness-device-library`), `version` (1), `devices`, `parts` and `interface_types`. A device is `{"unit": {...}, "connectors": [...]}` with the same fields as a unit in `logical/units/<subsystem>.json` and a box connector in `physical/connectors/<subsystem>.json` of a project (box connectors only, every pin with its `signal`, `function`, `contact_size`, `termination`, `fixed` and, since 1.7.0, `contact_part`); `parts` and `interface_types` are the records of `library/<category>.json` and `logical/interface_types.json` that the connectors name, the contact parts of the pins among them. The zone of a unit and the allocations that generation made on a pin (`interface_id`, `locked`, a signal that was given for an interface) are left out. The file is written sorted by ID with two-space indent. A reader refuses a file of a higher `version`, a file over 8 MB, over 500 devices or over 64 connectors in a device. Importing never changes the project outside what the plan names; see `docs/user-manual/define-a-device.md`.

## Subsystem library file (M4; not part of a project)

A subsystem library (`harness-subsystem-library`, D-175) is one JSON file that holds **one subsystem**: a set of devices with the connections between them. It is kept outside any project, in the **library folder** that a team shares (a shared drive or a Git checkout) next to the device library files. The tool tells the two kinds apart by `format`; any other `.json` file in the folder is ignored. The top level is:

| Field | Meaning |
| --- | --- |
| `format` | the text `harness-subsystem-library` |
| `version` | `1`; a reader refuses a higher number and says so |
| `name` | the name of the subsystem (1 to 200 characters, no control characters); it becomes the `subsystem` of every device that is added |
| `description` | one or two lines for whoever finds it in the library (may be empty) |
| `notes` | optional notes for whoever adds it |
| `devices` | the devices, each `{"unit": {...}, "connectors": [...]}` exactly as in the [device library file](#device-library-file-140-not-part-of-a-project); at least one, at most 100 |
| `parts`, `interface_types` | the records that the connectors of the devices name, as in the device library file |
| `connections` | the links of `logical/links.json` between connectors of the devices: `{"id", "name", "a_connector", "b_connector", "pairs": [{"a_pin", "b_pin"}], "note"}`; at most 2000 |

The connection ends are the **connector IDs of the file** (the `id` of a connector under `devices`), so a connection keeps its meaning when the devices get other IDs in a project: the planner maps the connector IDs of the file to the new ones. A connection with an end on a device that is not in the file is left out when the file is written, and a connection whose end is not a connector of the file makes the whole subsystem refuse to be added. `harness_id` is never written (a harness belongs to a project). The file is written with two-space indent and a final new line; a reader refuses a file over 8 MB.

```
{
  "format": "harness-subsystem-library",
  "version": 1,
  "name": "Wheel drive",
  "description": "OBC and a reaction wheel",
  "notes": "",
  "devices": [{"unit": {"id": "OBC", ...}, "connectors": [{"id": "OBC-J01", ...}]}, {"unit": {"id": "RW1", ...}, "connectors": [...]}],
  "parts": [...],
  "interface_types": [...],
  "connections": [{"id": "L1", "a_connector": "OBC-J01", "b_connector": "RW1-J02", "pairs": [{"a_pin": "1", "b_pin": "1"}]}]
}
```

Adding a subsystem (`plan_subsystem_import`, `import-subsystem`, the library window) adds the devices (a taken ID gets the next free one: `OBC` becomes `OBC-2`, and its connectors follow), sets `Unit.subsystem` of each to the `name`, adds the connections between the new connectors (a taken connection ID gets the next free `L<n>`), puts the devices in a free place of one lane, and does all of it as one undo step. It is all or nothing and never changes an object that the project has. The file name that the tool writes is `subsystem-<name made safe>.json`; the tool never replaces a file of that name. Nothing is added to a project file that does not use the library: no field of the model changed.

## Editing files by hand: JSON Schemas

`harness-design-studio schema my-design/schemas` writes one JSON Schema per kind of file, made from the same strict models the loader uses (so they cannot drift), and `editor-settings.json` with the `json.schemas` entries that map the project's files to them for VS Code. With them an editor completes keys, shows the allowed values and underlines mistakes before the tool ever sees the file. Nothing is downloaded. The tool itself does not need the schemas.

`library/manifest.json` holds `name`, `version`, `source` and `date` of the parts library (the last two may be `null`).

Next: [`CONFIG.md`](CONFIG.md), [`OUTPUTS.md`](OUTPUTS.md).
