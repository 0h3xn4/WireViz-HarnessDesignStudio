# Project file format (schema version 1)

A project is a folder of small, canonical JSON files: UTF-8, 2-space indent, sorted keys, `\n` line endings, trailing newline. The same model always produces the same bytes, so Git diffs show only real changes.

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
physical/connectors/<subsystem>.json {"connectors": [...]}   box connectors, grouped by their unit's subsystem
physical/harnesses/<id>.json      one harness with its connectors, wires, splices, shields, branch points, segments
generated/generation.json         the last generation record (provenance for Explain)
outputs/                          written by `harness-design-studio export` (see OUTPUTS.md); safe to delete and regenerate
changelog.json                    the change log (append-only; entries cannot be deleted)
baselines/<harness ID>/<baseline ID>.json   frozen snapshot made at each release
.gitignore                        written once: *.bak, lock files, temp files, .harness-recovery/, .migration-backup-v*/
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
The loader sets aside (reports, keeps in `quarantine.json`) an object with a number outside these ranges, and the editor refuses such an edit: wire gauge (AWG) 0 to 40, whole numbers; `length_m` of a wire or segment 0 to 10000; `max_current_a`, `voltage_v`, `impedance_ohm` above 0; part `pin_count` 1 to 1000; `mass_g`, `mass_per_m_g` and each `ratings` value 0 or more; `default_gauge_awg` 0 to 40; `next_harness_number` 1 or more; `schema_version` 1 or more. A missing value (`null`) is still allowed everywhere it was. What you see when a value is set aside on load (here a wire with gauge 99 and a length of -3 in a harness file):

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
- `waivers.json`: `id` is `<rule>.<object>`; `justification` is mandatory (at least 10 characters).
- Autosave journal: the full set of project files as text in `.harness-recovery/session.json`, written (atomically) 1.5 s after the last change while a project folder is open; removed on save; offered for restore on the next open if it differs from the files on disk. Never written for the unsaved sample project, so no project content leaves the project folder.
- Not in the project: the theme, the interface size, *Reduce motion*, the recent projects and the layout of the window (which area and tab was open, where the panels were; kept for each project) are per-user settings in the editor's settings file (`HarnessDesigner.ini`, [`INSTALL.md`](INSTALL.md#where-things-are-stored)), never in a project folder. The format did not change with the new interface of version 1.3.0: a project saved by 1.2.0 or earlier opens as it is.

## Generation additions: pins, mating, locks, generation record (schema version stays 1)
All optional with defaults; projects saved before them load unchanged.
- `Pin.interface_id`: interface that owns the pin (set by generation; locked pins are never reassigned).
- `Pin.fixed`: the signal is defined by the unit design (imported from KiCad, `docs/KICAD.md`). Generation connects interfaces to the pin of the same name and never moves it. Default `false`.
- `Connector.mates_with`: on a cable connector, the box connector it mates with.
- `Wire.locked`: gauge, part, colour and length were set by a person; regeneration keeps them.
- `Wire.manual` and `ShieldGroup.manual` (1.4.0): a wire or a twisting or shield group that a person made; generation keeps it as it is, never matches it to an interface, and says when it cannot keep it. Written only when `true`.
- `Wire.label` and `Wire.note` (1.4.0): text for the wire labels instead of the signal name, and a remark. Written only when set; a project without them is byte-identical to one saved by 1.3.0, and 1.3.0 quarantines the fields when it opens a project that uses them.
- `Harness.generated`, `group_key`, `interfaces`: set for generated harnesses; manual harnesses keep `generated: false`.
- `Part.mates_with`: library connector parts that mate with it.
- `generated/generation.json`: the last generation record: `input_hash`, `generator_version`, `next_harness_number`, `placeholders_used`, and `provenance` (object key to list of "rule: reason" lines; the data behind Explain).
- `config/generation.json`: generation settings (see PLACEHOLDERS.md).

## Change control additions: review, release, baselines, change log (schema version stays 1)
- `Harness.author`, `checker`, `approver`, `released_on` (all optional): who put the harness into review, who checked and released it, and the release date (YYYY-MM-DD). `status` is `draft`, `in_review` or `released`; `revision` is letters.
- `baselines/<harness ID>/<baseline ID>.json`: `id` (`<harness>.<revision>`), `harness_id`, `revision`, `released_on`, `by`, `comment`, `content_hash`, `snapshot` (`units`, `interfaces`, `connectors` = box connectors, `harnesses` = the released harness, and the records listed below). Written once at release; never edited by the tool.
- `snapshot.parts`, `interface_types`, `config` and `waivers` record what the release froze (see "What a release freezes"). They are optional: a baseline made by an earlier version has none of them, is read without them and written back unchanged, and `harness-design-studio check` compares nothing for it.

### What a release freezes
A released harness locks, besides itself: the design fields of the interfaces it carries (not name, notes, requirement), the units those interfaces connect (not name, notes, zone), the box connectors it plugs into or that carry its interfaces (part, gender, keying and the pins of its interfaces), and, new in this version:
- **parts it uses**: the part of each of its connectors, the part of each wire, the part of the box connectors above, and the counterpart named in `mates_with` of those parts. Every field but `notes` is frozen (approval, mass, `pin_count`, `unverified`, ratings, part number, ...).
- **interface types** of the interfaces it carries (every field but `name` and `notes`).
- **configuration its checks and outputs read**: all values of `derating`, `emc`, `segregation` and `titleblock`, and in `generation` the keys `conductor_resistivity_ohm_m`, `mass_margin_fraction`, `power_return_gap_pins`, `shield_end_a`, `shield_end_b`, `test_continuity_max_ohm`, `test_isolation_min_mohm` and `test_isolation_voltage_v`. These apply to every harness, so they are frozen while any harness is released. `segmentation`, `naming`, the other `generation` keys (which only decide how new harnesses are made) and the `placeholder` flags stay editable.
- **waivers** that name the harness or one of its objects are recorded in the baseline but not locked: a waiver can be added or changed after a release (the change log and `harness-design-studio compare` show it).

The editor and the data commands (`import-parts`, `config`; `library` only records the source of the data and is not affected) refuse a change to a frozen item with the reason and "start a new revision" (exit 1, also with `--dry-run`); `harness-design-studio check` reports a hand edit as `released_modified`. Allowed at any time: adding parts and interface types, editing and deleting those no released harness uses, and notes and names. To change a frozen item: `harness-design-studio revise` the harness (every released harness for configuration), make the change, release again.
- `changelog.json`: `{"changelog": [{id (C0001...), harness_id, revision, kind (review | release | new_revision), by, when, comment}]}`.
- `outputs/manifest.json` gained `content_hash` (see D-104).

## Editing files by hand: JSON Schemas

`harness-design-studio schema my-design/schemas` writes one JSON Schema per kind of file, made from the same strict models the loader uses (so they cannot drift), and `editor-settings.json` with the `json.schemas` entries that map the project's files to them for VS Code. With them an editor completes keys, shows the allowed values and underlines mistakes before the tool ever sees the file. Nothing is downloaded. The tool itself does not need the schemas.

`library/manifest.json` holds `name`, `version`, `source` and `date` of the parts library (the last two may be `null`).

Next: [`CONFIG.md`](CONFIG.md), [`OUTPUTS.md`](OUTPUTS.md).
