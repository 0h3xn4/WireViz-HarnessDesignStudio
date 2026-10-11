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
outputs/                          written by `harness export` (see OUTPUTS.md); safe to delete and regenerate
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
- **Strict typing:** no type coercion (a string is never accepted for a number), unknown fields are rejected, `NaN`/`Infinity` are rejected, duplicate JSON keys are rejected, control characters are rejected in names and notes.
- **Lists are sorted by ID** on save, except where order carries meaning (`endpoints`, `signals`, a connector's `pins` keep their order of entry).
- `null` means "not yet decided". The tool never fills engineering numbers on its own.

## Versions and migration
`schema_version` is an integer in `project.json`. A missing value means version 0.
- **Older file:** opened with an in-memory migration (`migrated` info message). Nothing on disk changes until you save; saving (or `harness migrate`) first copies every original file to `.migration-backup-v<N>/`.
- **Newer file:** opened read-only (`newer_version` warning); entities the tool does not understand are quarantined and listed.
- Each migration is one function in `core/io/migrate.py`, tested against a fixture of the old format (`tests/fixtures/v0_project`).

## Recovery mode
A file that is not valid JSON/UTF-8, has duplicate keys, a wrong structure, or an invalid object does not stop loading: the bad part is reported (`quarantined`, `invalid_json`, `merge_conflict`, ...) and kept in memory as quarantine. The message says where: the line and column of a syntax error, the byte of a bad character, or the line where a set-aside object starts. It never quotes the content of the file (it may be export-controlled). A project with quarantined data **cannot overwrite its folder**. "Save as" writes a new folder with `quarantine.json` (rejected objects, verbatim) and `quarantine/files/` (unreadable files, verbatim), so nothing is lost.

## Saving
Each file is written to a temp file, flushed, `fsync`ed and renamed; the previous version is kept as `<file>.bak`. Only changed files are written. Files for deleted objects are renamed to `.bak`, not erased. A crash can leave some files updated and others not, but every file is whole; `harness validate` / `harness check` report cross-file inconsistencies, and saves are refused while integrity errors exist. If the folder changed on disk since opening (e.g. a Git pull), a save with the opening fingerprint is refused.

## Locking
`.harness.lock` (pid, host name, start time; no design data) prevents opening one project twice. A lock whose process no longer exists on the same host is taken over; a lock from another host is respected.

## Hash
`model_hash` is the SHA-256 of all canonical files with the saving tool's version blanked. Every output file carries its first 12 characters, so a printed sheet can be traced to the exact model.

## Editor additions: connector use, layout, waivers, autosave (schema version stays 1)
All additions are optional with defaults, so projects saved before them load unchanged (tested against `tests/fixtures/m1_project`) and are upgraded on the next save.
- `Connector.carries`: list of interface-type IDs the connector is meant for (empty means any).
- `Endpoint.auto`: true while the connector was chosen by the tool and not yet confirmed by a person.
- `logical/layout.json`: ordered `zones` (diagram lanes) and one `placements` entry per unit (`id` is the unit ID, `x`/`y` in scene units). Units without a placement are placed deterministically at load (`edit.ops_autoplace`).
- `waivers.json`: `id` is `<rule>.<object>`; `justification` is mandatory (at least 10 characters).
- Autosave journal: the full set of project files as text in `.harness-recovery/session.json`, written (atomically) 1.5 s after the last change while a project folder is open; removed on save; offered for restore on the next open if it differs from the files on disk. Never written for the unsaved sample project, so no project content leaves the project folder.

## Generation additions: pins, mating, locks, generation record (schema version stays 1)
All optional with defaults; projects saved before them load unchanged.
- `Pin.interface_id`: interface that owns the pin (set by generation; locked pins are never reassigned).
- `Pin.fixed`: the signal is defined by the unit design (imported from KiCad, `docs/KICAD.md`). Generation connects interfaces to the pin of the same name and never moves it. Default `false`.
- `Connector.mates_with`: on a cable connector, the box connector it mates with.
- `Wire.locked`: gauge, part, colour and length were set by a person; regeneration keeps them.
- `Harness.generated`, `group_key`, `interfaces`: set for generated harnesses; manual harnesses keep `generated: false`.
- `Part.mates_with`: library connector parts that mate with it.
- `generated/generation.json`: the last generation record: `input_hash`, `generator_version`, `next_harness_number`, `placeholders_used`, and `provenance` (object key to list of "rule: reason" lines; the data behind Explain).
- `config/generation.json`: generation settings (see PLACEHOLDERS.md).

## Change control additions: review, release, baselines, change log (schema version stays 1)
- `Harness.author`, `checker`, `approver`, `released_on` (all optional): who put the harness into review, who checked and released it, and the release date (YYYY-MM-DD). `status` is `draft`, `in_review` or `released`; `revision` is letters.
- `baselines/<harness ID>/<baseline ID>.json`: `id` (`<harness>.<revision>`), `harness_id`, `revision`, `released_on`, `by`, `comment`, `content_hash`, `snapshot` (`units`, `interfaces`, `connectors` = box connectors, `harnesses` = the released harness). Written once at release; never edited by the tool.
- `changelog.json`: `{"changelog": [{id (C0001...), harness_id, revision, kind (review | release | new_revision), by, when, comment}]}`.
- `outputs/manifest.json` gained `content_hash` (see D-104).

## Editing files by hand: JSON Schemas

`harness schema my-design/schemas` writes one JSON Schema per kind of file, made from the same strict models the loader uses (so they cannot drift), and `editor-settings.json` with the `json.schemas` entries that map the project's files to them for VS Code. With them an editor completes keys, shows the allowed values and underlines mistakes before the tool ever sees the file. Nothing is downloaded. The tool itself does not need the schemas.

`library/manifest.json` holds `name`, `version`, `source` and `date` of the parts library (the last two may be `null`).

Next: [`CONFIG.md`](CONFIG.md), [`OUTPUTS.md`](OUTPUTS.md).
