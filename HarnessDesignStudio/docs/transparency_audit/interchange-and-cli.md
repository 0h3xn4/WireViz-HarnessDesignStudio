# Transparency audit, appendix E: interchange and the command line

This page is appendix E of the [transparency audit](../transparency_audit.md): the row-level catalogue for every file and format the tool reads or writes, the imports and the 29 commands. Each row names the file and line the reviewer opened. IDs read `IO-C<category>-<number>`; the categories and the tags `[SYS]`, `[ELEC]` and `[AIT]` are explained in section 1 of the audit. Paths beginning with `work/` are scratch projects the reviewer made while auditing; they are not in the repository. Nothing on this page was changed in the code: it is read-only.

## Contents

- [C1. Hard-coded constants, defaults, rules](#c1-hard-coded-constants-defaults-rules)
- [C2. Hidden assumptions](#c2-hidden-assumptions)
- [C3. Outputs without visible derivation](#c3-outputs-without-visible-derivation)
- [C4. Forced choices (cannot change)](#c4-forced-choices-cannot-change)
- [C5. Everything exchanged with other tools or files](#c5-everything-exchanged-with-other-tools-or-files)
- [C6. Customisation points that exist](#c6-customisation-points-that-exist)
- [Top findings](#top-findings)

**Scope.** Read in full: core/io/{canonical,fs,layout,loader,migrate,saver}.py, core/kicad.py, core/imports.py, core/pinout_import.py, core/library_import.py, core/device_library.py, core/subsystem_library.py, core/library_folder.py, core/schemas.py, cli/{__init__,main,data,changes,merge,start}.py (about 6,300 lines). Read in part, for what the import paths call: core/build_data_import.py (1-300, 300-end), core/build_data.py (104-135 via sed, rest by grep only), core/generate/lengths.py (116-202), core/configcheck.py (197-257), core/devices.py (905-1010), core/outputs/{stamp,provenance}.py, core/outputs/build.py (20-260), core/outputs/exports.py (57-120), core/recovery.py (1-140), core/mergefix.py (44-82), core/templates.py (1-102), core/model/{project,library,base}.py (parts), gui/recent.py, gui/app.py (1-40), gui/import_kinds.py (120-160, 395-560), resources/examples/templates/README.md. I ran `new`, `config`, `generate`, `export-pinout`, `export`, `--version` on a scratch project under audit-transparency/io-run/ (outside the repo). Persona tags: [SYS] systems, [ELEC] electrical, [AIT] assembly/integration/test. "GUI wizard" claims are limited to import_kinds.py/import_wizard.py headers I opened; anything else is marked unverified.

---

## C1. Hard-coded constants, defaults, rules

Columns: id | file:line | value or rule | what it does / feeds | unit | visible to user? | editable? | R | persona

| id | file:line | value / rule | effect | unit | visible? | editable? | R | persona |
|---|---|---|---|---|---|---|---|---|
| IO-C1-001 | core/imports.py:20-24 | `MAX_ROWS=20000, MAX_BYTES=8 MB, MAX_UNPACKED=64 MB, MAX_SCANNED_ROWS=100000, MAX_COLUMNS=200` | Size caps on every table import (parts, lengths, build data, pinout, interfaces); excess columns are cut silently (line 217) | rows, bytes, columns | only in error text when hit | none | R3 | SYS ELEC AIT |
| IO-C1-002 | core/imports.py:32-38 | `_ALIASES`: id=(interface,id,interfaceid,ifid,name), from=(...,source,src,a), to=(...,dest,target,b), redundancy=(...,side,redundant) | Header-to-field guess for the interface import; one-letter headers `a`/`b` become From/To | text | GUI map page (not CLI) | none | R3,R6 | SYS |
| IO-C1-003 | core/imports.py:248-251 | "unknown fields default to the field's position" | If a header is not recognised, column N is taken for field N silently; a wrong guess is only visible as row errors | - | no | none | R6,R12 | SYS |
| IO-C1-004 | core/imports.py:122-128 | `_delimiter`: comma, semicolon or tab, whichever is most frequent in the first non-empty line | Auto-detects CSV delimiter; no override | - | no | none | R3 | ELEC AIT |
| IO-C1-005 | core/imports.py:51,61-62,217 | CR/CRLF -> LF; every cell `.strip()`; rows with all-empty cells dropped | Whitespace and blank rows normalised on every import | - | no | none | R5 | SYS ELEC AIT |
| IO-C1-006 | core/imports.py:172,175-177 | only `utf-8-sig`; anything else rejected ("Save it as CSV UTF-8") | Excel/Windows cp1252 CSV (the usual ERP export) is refused, not converted | - | error text | none | R14 | ELEC AIT |
| IO-C1-007 | core/imports.py:182,198,205-208 | formats .csv .tsv .json .xlsx .xlsm; `data_only=True`; first *visible* sheet only | XLSX cached values read (a formula never recalculated; an uncached one reads as empty); other sheets ignored | - | CLI prints the sheet name (cli/data.py:387-388) | `skip_sheets` only in code (pinout "About") | R14 | ELEC AIT |
| IO-C1-008 | core/imports.py:85-86,104-109 | JSON table: dict with exactly one list value is unwrapped; bool -> "true"/"false"; nested value refused | Shapes an InvenTree/API JSON export into rows; header = keys in first-seen order | - | no | none | R14 | ELEC AIT |
| IO-C1-009 | core/imports.py:131-142 | row wider than header with non-empty overflow -> refuse | Guards the decimal-comma split; narrower rows padded with empty | - | error text | none | R12 | AIT |
| IO-C1-010 | core/imports.py:282-295,323 | match type/unit by casefolded ID *or* name; redundancy words `nominal|redundant|none` | Interface import resolves names case-insensitively; empty redundancy -> None (model default) | - | row results | none | R4 | SYS |
| IO-C1-011 | core/library_import.py:36-58 | `_ALIASES`: id=(ipn,partipn,...,id,partid,part,item,ref); mass_g=(massg,**mass,weight**,weightg); part_number=(...,number); approval=(...,status,approved,qualification) | Header-to-field map for parts / InvenTree import. `mass`/`weight` columns are read as **grams** whatever their real unit | g, g/m | no (CLI never prints the mapping; GUI map page unverified) | none | R3,R5 | ELEC AIT |
| IO-C1-012 | core/library_import.py:28-34 | Importable fields are only id, category, manufacturer, part_number, description, specification, approval, pin_count, mass_g, mass_per_m_g, mates_with, tool, conductors | **No field for `ratings`** (contact current, voltage); those columns are ignored without any warning (unlike pinout import) | - | no | none | R7,R12 | ELEC |
| IO-C1-013 | core/library_import.py:180,204-209 | part ID = ID column, else part-number column; IDs that differ only in case from an existing ID are refused | Identity rule for parts | - | row message | none | R14 | AIT |
| IO-C1-014 | core/library_import.py:98-107 | category taken from the first path step (split on `/ > \| \\`) that is one of six categories or its plural | `Connectors/D-Sub` -> connector; other text refused | text | row message | none | R4 | ELEC AIT |
| IO-C1-015 | core/library_import.py:225-227 | blank approval cell -> keep old approval, **new part gets "pending"** | Default approval status | - | no | none | R7 | SYS AIT |
| IO-C1-016 | core/library_import.py:244-248 | `"unverified": False` forced on every imported part | An import clears the "example data" flag the part may have carried, without asking | - | no | none | R7,R8 | SYS ELEC |
| IO-C1-017 | core/library_import.py:114-129 | `MAX_PIN_COUNT=1000`; number = digits with a point or one decimal comma; no exponent, sign, thousands separator ("1,234" refused) | Mass/pin-count parsing | g, pins | row message | none | R5,R12 | ELEC AIT |
| IO-C1-018 | core/library_import.py:253-254,269-274 | `tool` only for category contact; `conductors` 1..64 only for category wire; ignored for other categories | Silent drop of a column value that does not fit the category | - | no | none | R12 | AIT |
| IO-C1-019 | core/library_import.py:315-327 | library info fields name/version/source/date; date must be YYYY-MM-DD | One record for the whole library (see C4) | date | `describe_library` line, provenance.json | CLI `--library-*` | R9 | SYS |
| IO-C1-020 | core/pinout_import.py:43-60 | `_ALIASES`: signal=(...,net,netname,**function**); contact_part=(cablecontact,contactpart,...,**contact**); pin=(...,contact,number); mode=(mode,allocation,**fixed**) | One heading can serve two fields (`Function` is the signal when no Signal column; `Contact` is the pin when no Pin column) | - | CLI `--column` can override; mapping not printed | partial (`--column`) | R3,R6 | ELEC AIT |
| IO-C1-021 | core/pinout_import.py:62-67 | `_UNSTORED`: description, remarks, remark, notes, note, comment, comments, voltage, current, class | These columns are warned about and dropped. A pin has no field for current/voltage/class | - | warning (line 189-192) | none | R7,R12 | ELEC |
| IO-C1-022 | core/pinout_import.py:68-72 | `_YES={yes,y,true,x,1,fixed}`; gender words: male/m/plug/**pin**/pins, female/f/socket/receptacle | Fixed-pin and gender vocabulary | - | no | none | R3 | ELEC AIT |
| IO-C1-023 | core/pinout_import.py:219 | default connector name `"J01"` when no Connector column | Rows without a connector all go to J01 | - | CLI `--connector` | `--connector` | R6 | AIT |
| IO-C1-024 | core/devices.py:912-921,979-990 | mode words free/auto/fixed/locked/lock; termination only `crimp|solder|unspecified`, blank -> unspecified | Termination vocabulary; anything else ("splice", "ring lug") is a refused row | - | row message | none | R3,R4 | AIT |
| IO-C1-025 | core/pinout_import.py:209,223-224 | a column headed exactly "Fixed" is yes/no | Changes how the Mode column is read | - | no | none | R6 | ELEC |
| IO-C1-026 | core/kicad.py:28,60-61 | `MAX_BYTES=32 MB, MAX_DEPTH=64, MAX_ATOMS=4,000,000` | Netlist size caps | - | error text | none | R3 | ELEC |
| IO-C1-027 | core/kicad.py:29-30,153,231 | symbol fields `HarnessConnector`, `HarnessPart`; field names lower-cased, spaces and underscores removed | The only KiCad-side vocabulary the tool reads | text | cli/data.py:140,147 help | none | R3,R14 | ELEC |
| IO-C1-028 | core/kicad.py:266-276 | `clean_net`: strip sheet path (`/power/28V` -> `28V`); `unconnected-*` and `Net-(*` -> no signal | Net-name-to-signal rule. Two sheets' `/a/28V` and `/b/28V` collapse into one signal | text | CLI prints per-connector counts only | `--signal-map` (rename, not the rule) | R1,R7 | ELEC |
| IO-C1-029 | core/kicad.py:319,327-331,351-353 | default `prefix="J"` (every component whose ref starts with it); connector ID default `<unit>-<ref>` | Which components are connectors; what the connector is called | text | CLI help | `--prefix --ref --connector` | R3,R6 | ELEC AIT |
| IO-C1-030 | core/kicad.py:470-478 | new connector: `role="box"`, `name=ref`, `gender="unspecified"` | Defaults on a netlist-created connector (gender is not read from KiCad) | - | no | edit afterwards | R7 | ELEC AIT |
| IO-C1-031 | core/kicad.py:399-411,455-460 | pin count vs part; for all-numeric pin sets, pins 1..N not in the netlist are created as spare | Fills missing pins silently to the part's pin_count | pins | no (only in result) | none | R7 | ELEC |
| IO-C1-032 | core/kicad.py:416-441 | fixed=True for every pin with a signal; `interface_id=None`; a locked pin is never changed (warning only) | Netlist is authoritative for unlocked pins and overwrites signal/fixed | - | warnings printed | lock a pin | R7 | ELEC |
| IO-C1-033 | core/ids.py:7-8 (read via cat) | `ID_RE ^[A-Za-z][A-Za-z0-9_.\-]{0,63}$`; `PIN_RE ^[A-Za-z0-9][A-Za-z0-9_.\-]{0,15}$` | Naming rule for every imported ID/pin; KiCad pin names such as `~`, `A/1`, > 16 chars are refused | chars | row message | none | R3 | ELEC AIT |
| IO-C1-034 | core/generate/lengths.py:117-118,159 | `_NUMBER` digits with point/comma (no sign, no exponent); `MAX_LENGTH_M=10000`; `round(x*scale, 9)` | Segment length import; stored in **metres** rounded to 1 nm | m | row message | none | R5 | AIT |
| IO-C1-035 | cli/data.py:30,317 | `UNITS={"mm":0.001,"m":1.0,"cm":0.01}`, default `mm` (lengths) | Only three length units; no inch | mm/cm/m | CLI help | `--unit` (3 values) | R5 | AIT |
| IO-C1-036 | core/generate/lengths.py:124,130-139 and cli/data.py:312 | length columns read **by position** (harness, segment, length); a numeric first row is rejected | Headings ignored for `import-lengths` | - | description text | none | R6 | AIT |
| IO-C1-037 | core/build_data.py:104-122 | `_mm`: every `,` replaced by `.`; allowed 0..100000 mm | "1,234" is read as 1.234 mm, not 1234 | mm | error only if out of range | none | R5,R12 | AIT |
| IO-C1-038 | core/build_data_import.py:35-64 | heading aliases normalised to letters+digits: `stripamm|stripa`, `stripbmm|stripb`, `lengthmm|length` | The unit in a heading is not parsed: "Strip A (in)" is not recognised, "Strip A" is taken as **mm** | mm | description text | none | R5 | AIT |
| IO-C1-039 | core/build_data_import.py:65-71,133-139 | `KINDS` order strips, contacts, accessories, tools: the first kind whose needed headings are present wins | Table kind is guessed from headings; a table fitting two kinds becomes the first | - | GUI/CLI print kind label | none | R6 | AIT |
| IO-C1-040 | core/build_data_import.py:13,229-238 | accessory kind: casefold, space/`-` -> `_`; quantity default 1; ID default ACC-001.. | Silent defaults for accessories | - | row message | none | R3 | AIT |
| IO-C1-041 | core/configcheck.py:197-224 | ampacity CSV: gauge int 0..40 (AWG only), amps > 0, `,`->`.`, duplicate gauge refused, first row skipped if non-numeric | Loads `derating.ampacity_a_by_awg`; **replaces the entire table**; carries no temperature/bundle/insulation conditions, source or date | A | CLI prints count | `--ampacity-csv` | R2,R3,R9 | ELEC |
| IO-C1-042 | core/device_library.py:75-81 | `FORMAT harness-device-library`, `VERSION 1`, `MAX_BYTES 8 MB, MAX_DEVICES 500, MAX_CONNECTORS 64, MAX_PARTS 5000, MAX_TYPES 2000` | Device library caps | - | error text | none | R3 | SYS |
| IO-C1-043 | core/device_library.py:203-212,268,589 | `_portable`: allocated signal, interface_id and `locked` removed; unit zone set to None | What travels with a device (pin design yes, allocation no) | - | docstring, CLI description | none | R7 | ELEC |
| IO-C1-044 | core/device_library.py:279,312-318 | `_RANK` not_approved 0 < pending 1 < approved 2: merge never lowers a part's approval | Rule when saving into an existing library file | - | note text | none | R7 | SYS |
| IO-C1-045 | core/device_library.py:494-504,597-612 | free ID: `base-2`, `base-3`, truncated to 64; connector renumber `<new>-J01..` when the tail does not fit | Auto-renaming of devices/connectors on import | - | plan note | none | R14 | SYS |
| IO-C1-046 | core/device_library.py:680-685 | parts added from a file keep **the file's approval** ("approved" arrives as approved) | Approval status is imported with a note, not re-decided | - | note | none | R7 | SYS ELEC |
| IO-C1-047 | core/subsystem_library.py:66-70,285-309 | `MAX_DEVICES 100`, `MAX_CONNECTIONS 2000`; imported devices placed with `free_slot` in one lane, zone from x | Layout of imported subsystem; subsystem name overwrites every device's `subsystem` | - | no | none | R7 | SYS |
| IO-C1-048 | core/library_folder.py:44-45,123-128 | `MAX_FILES=2000`, `MAX_DEPTH=3`; hidden folders and links skipped; only `*.json` | What a library folder scan sees | - | problems list | none | R14 | SYS |
| IO-C1-049 | core/io/fs.py:41-49; core/library_folder.py:351; core/subsystem_library.py:161-163 | `slug`: NFKD ascii, lower, `[^a-z0-9_-]`->`-`, max 60 chars; device file `<ID>.json` or `devices.json`; subsystem file `subsystem-<slug>.json` | File naming of libraries and grouped project files | - | no | none | R3 | SYS |
| IO-C1-050 | core/io/canonical.py:13,69 | JSON: sorted keys, indent 2, UTF-8, no NaN; `MAX_NESTING=1000` | Format of every project file; floats written with Python repr | - | docs only | none | R10 | SYS |
| IO-C1-051 | core/io/loader.py:63 | `MAX_FILE_BYTES = 64 MB` | A larger project file is an error, not read | bytes | issue text | none | R3 | SYS |
| IO-C1-052 | core/io/layout.py:24-28 | `MANAGED_RE`: only listed file names/folders are loaded (`config/*.json`, `library/*.json`, `logical/...`, `physical/...`, `baselines/*/*.json`, ...) | Anything else in the folder (hand notes, extra JSON) is ignored with an info issue (loader.py:83-85) | - | info issue | none | R3 | SYS |
| IO-C1-053 | core/io/saver.py:177-180,275-277 | `.gitignore` content fixed (`*.bak .harness.lock .harness.lock.takeover .*.tmp .harness-recovery/ .migration-backup-v*/`), written only if absent | Decides what Git sees | - | docs | none | R9 | SYS |
| IO-C1-054 | core/io/fs.py:25,270,280-289 | lock file `.harness.lock` holds pid, host, since (epoch s), boot id, start ticks; guard `.harness.lock.takeover` | Single-writer lock; guard file stays in the folder (seen after `generate`) | s | message on conflict | delete file by hand | R8 | SYS |
| IO-C1-055 | core/recovery.py:21-22 | `.harness-recovery/session.json`; delay 1500 ms (gui/controller.py:59, seen by grep only) | Autosave journal of the open project | ms | restore dialog (gui/main_window.py:4319, grep only) | none (unverified) | R8 | SYS |
| IO-C1-056 | gui/recent.py:15-16; gui/app.py:16-18 | `KEY="home/recent"`, `LIMIT=8`; QSettings IniFormat, user scope, org/app "HarnessDesigner" | Recent-project list and UI settings in a per-user INI | - | no | none | R3 | SYS |
| IO-C1-057 | core/outputs/stamp.py:34-61 | CSV: first line `# harness-design-studio <ver> model <12 hex>`; cells starting `= + - @ TAB CR` get a leading `'` unless a plain number | Every CSV that leaves the tool is modified this way | - | docs/OUTPUTS.md only | none | R9,R14 | ELEC AIT |
| IO-C1-058 | core/outputs/stamp.py:22-24; provenance.py:20-22; build.py:25-27 | stamp = version + first 12 hex of model hash; `values_sha256_16` of each config; manifest sha256 per file | Provenance granularity | - | file contents | none | R9 | SYS ELEC |
| IO-C1-059 | core/outputs/exports.py:102 and 113-117 (docstring) | XLSX zip timestamps fixed to 2000-01-01 | No real creation time in any output | date | no | none | R9 | SYS AIT |
| IO-C1-060 | cli/changes.py:54,112-114,159 | `--date` default = `date.today()` (local clock); outputs folder = `<project>/outputs` | The only place a clock enters project data | date | CLI help | `--date` | R8 | SYS |
| IO-C1-061 | cli/data.py:574-579 | import source text = `<file name> (sha256 <first 12 hex>)` | Provenance of a parts import (truncated hash; file name only, no path/date) | - | `library` command, provenance.json | `--library-source` | R14 | SYS ELEC |
| IO-C1-062 | core/io/migrate.py:131-137,141 | v0->v1: `tool`->`tool_version`; `redundant:bool` -> `side` ("redundant" if exactly `True`, else "nominal") | Only migration that exists | - | "migrated" info issue | none | R8 | SYS |
| IO-C1-063 | cli/main.py:22-24,331-348 | exit codes 0 ok, 1 errors/blocked, 2 usage/unreadable, 130 interrupt | CLI contract | - | module doc, templates/ci/build.sh | none | R11 | SYS |
| IO-C1-064 | core/templates.py:49-58; cli/start.py:21 | default template `blank`; `new` also writes `.gitattributes` | New projects start with all config files `placeholder:true`, values null (resources/examples/projects/blank/config/derating.json) | - | `config` report | edit files | R2,R3 | SYS ELEC |

---

## C2. Hidden assumptions

| id | file:line | assumption | why it matters | R | persona |
|---|---|---|---|---|---|
| IO-C2-001 | core/library_import.py:53 (+ 120-129) | `mass`/`weight` columns are grams; `mass_per_m` grams per metre; no unit parsing or conversion | An ERP/InvenTree export in kg is imported 1000x too small without a message; mass budget and mass-with-margin follow | R5 | SYS ELEC AIT |
| IO-C2-002 | core/build_data.py:108-117, build_data_import.py:38-39 | strip lengths and accessory lengths are millimetres whatever the heading says; any "," is a decimal point | "1,234" -> 1.234 mm; "Strip A (in)" is not matched at all | R5,R12 | AIT |
| IO-C2-003 | core/generate/lengths.py:127,159 | file length x scale -> metres, rounded to 9 decimals; no check that the number was a segment length vs wire length | A mm file imported with `--unit m` (default is mm, line 317) gives 1000x lengths up to the 10,000 m cap | R5 | AIT ELEC |
| IO-C2-004 | core/configcheck.py:206-221 | ampacity table = amperes per AWG for one unspecified condition set; derating factors are separate config values | Engineer cannot tell from the file what temperature, bundle size, insulation or altitude the amps are for; source/date are not stored | R2,R9 | ELEC |
| IO-C2-005 | core/kicad.py:266-276,416-423 | signal identity = KiCad net name with the sheet path cut off; first pin wins when the name repeats on a connector | Same-named nets on different sheets merge; only a warning for same-name pins on one connector (kicad.py:420-423) | R12 | ELEC |
| IO-C2-006 | core/kicad.py:132-169, 38-51 | Read from the netlist but dropped: `design/source`, component `value`, `footprint`, pin `pintype`; only `pinfunction` is used when asked | KiCad electrical pin type (input/output/power_in) and the schematic file/revision never reach the project; the pin `direction` is not filled from it | R7,R14 | ELEC |
| IO-C2-007 | core/kicad.py:470-478 | gender "unspecified", role "box", connector name = KiCad reference, part from field/CLI/existing | New connector has no electrical rating; contact gender left for later | R7 | ELEC AIT |
| IO-C2-008 | core/pinout_import.py:62-67,189-192 | pinout columns Voltage, Current, Class, Remarks, Notes are dropped | The warning names the column but the values (e.g. pin current) are gone from the project; no place to keep them | R7 | ELEC |
| IO-C2-009 | core/imports.py:198,217 | XLSX values are the cached values, each `str(c).strip()` | A float cell 1.0 may be read as "1.0" (a pin "1.0" is not pin "1": unverified here); dates become text; formulas not recalculated | R5 | ELEC AIT |
| IO-C2-010 | core/imports.py:122-128, 172 | delimiter and encoding guessed, not shown | A semicolon CSV with commas in the header line can be split wrongly; not reported | R6 | ALL |
| IO-C2-011 | core/library_import.py:225-227 | missing approval cell = "pending" (new) or unchanged; the *meaning* of approval words is supplied by the user per import and not stored | The mapping `--approved Approved --pending Review ...` is not saved with the library; a re-import must repeat it | R2,R8 | SYS |
| IO-C2-012 | core/library_import.py:244-248 | an imported part always becomes `unverified=False` | The "example data, no engineer checked" marker (which blocks/flags releases) is cleared by any import that touches the part | R7 | SYS ELEC |
| IO-C2-013 | core/device_library.py:534-548,680-685 | a file part/type that fails validation is dropped with a note; unknown interface type is left out; unknown contact part removed from the pin | A device arrives with fewer parts/types than the file says; only plan notes tell | R12 | SYS ELEC AIT |
| IO-C2-014 | core/device_library.py:517-522,622-625 | project's own part/type wins over the file's when they differ | A re-imported device can silently use different ratings/mass than the library's; only a note | R4,R7 | SYS ELEC |
| IO-C2-015 | core/device_library.py:157-161, 91-108 | library/subsystem files carry no tool version, date, author, source project or hash (only `format`, `version`, content) | A shared device library cannot be traced to the project/revision that produced it | R9 | SYS |
| IO-C2-016 | core/subsystem_library.py:333-337 | importing a subsystem overwrites each device's `subsystem` with the file's name | Original grouping lost | R7 | SYS |
| IO-C2-017 | core/outputs/exports.py:79-99 | `system/export.json` holds units, interface types, interfaces, box connectors, harnesses, parts, links only: **no config values (derating, resistivity, margins, test limits), no waivers, no change log, no library_info** | Another tool reading the JSON sees results but not the numbers they were derived with | R9,R10,R14 | ELEC SYS |
| IO-C2-018 | core/outputs/provenance.py:46-49 | settings are recorded as `placeholder` flag + 16-hex hash of values only | An auditor can detect a change but cannot read which derating/margin was used | R9 | ELEC |
| IO-C2-019 | core/outputs/stamp.py:22-24; io/layout.py:193-198 | model hash = SHA-256 of all serialised project files with `tool_version` blanked; stamp shows 12 hex only | Identical hash across tool versions; the hash does not distinguish what changed | R9 | SYS |
| IO-C2-020 | core/outputs/provenance.py:4; exports.py:102 | no timestamps, no user, no host, no path in any output ("equal design, equal bytes") | Good for diffing, but an as-built record or test table has no "when/who" | R8,R9 | AIT SYS |
| IO-C2-021 | core/outputs/stamp.py:38-46 | text cells starting `- + = @` are prefixed with `'` in CSV | A signal named `+28V`, `-5V_A` or a pin note beginning "=" leaves as `'+28V`; test equipment/ERP import reads a different key | R14 | ELEC AIT |
| IO-C2-022 | core/outputs/stamp.py:54-56 vs core/imports.py:48-74 | tool's CSV starts with a `#` comment line; only pinout import skips it (pinout_import.py:90-91) | `wirelist.csv`/`box_pinouts.csv` cannot be fed back to `import-build-data`/`import-lengths` unchanged; spreadsheet/pandas readers treat the stamp as a header row | R10,R14 | AIT ELEC |
| IO-C2-023 | core/io/layout.py:77-90,149-170 | file name = slug of subsystem; "file names only group data" | Renaming a subsystem moves objects between files (Git diff noise); loading does not care | R8 | SYS |
| IO-C2-024 | core/model/base.py:24-26 | `extra="forbid", strict=True` on every model | Unknown fields in a project file (custom notes, vendor attributes, units/comment keys) are not tolerated: the object is quarantined (loader.py:179-184) | R3,R13 | ALL |
| IO-C2-025 | docs/FILE_FORMAT.md:63-67 vs core/model/base.py:29-33 | schema version stays 1 while fields are added (sparse fields, omitted when default) | Old tool + new file may fail to load objects; the version number alone does not say what a file contains | R9 | SYS |
| IO-C2-026 | core/io/migrate.py:131-137,150 | migration keeps only `redundant is True` as redundant, other values -> nominal; unreadable `project.json` is assumed current; no migration record is stored in the project | A silent semantic default; the only trace is the `.migration-backup-v0/` folder | R8 | SYS |
| IO-C2-027 | core/io/saver.py:190-196,261-266 | recovered projects write `quarantine.json` / `quarantine/files/` verbatim | Rejected data preserved; good. Note: not visible in the UI beyond issues (unverified) | R8 | SYS |
| IO-C2-028 | cli/main.py:139-163 | `generate` = generate + verify + save in one step; no `--dry-run` | The CLI writes the project when checks pass; a user cannot preview changes first | R6,R8 | SYS |
| IO-C2-029 | cli/main.py:385-420 | write lock only for mutating commands; read commands run without; leftover `.harness.lock.takeover` | Reader may read half-way state while a writer runs (writes are atomic per file, but not across files) | R8 | SYS |
| IO-C2-030 | core/outputs/build.py:241-242 (`durable=False`) | outputs are written without fsync | A crash can leave outputs inconsistent with manifest; manifest check detects it | R9 | AIT |
| IO-C2-031 | cli/data.py:441-453 | loading an ampacity table does not clear `placeholder:true`; the message only tells the user to do it by hand | Results built on an imported (maybe demo) table keep the placeholder marker, but nothing says which table | R9 | ELEC |
| IO-C2-032 | cli/data.py:696-699 | a signal-map CSV: first row skipped if its first cell is one of net/name/kicad/from/net name; other rows with < 2 cells dropped silently | A map entry can vanish without notice | R12 | ELEC |
| IO-C2-033 | core/kicad.py:210,215 | XML netlist with DOCTYPE/entity refused; stdlib ElementTree otherwise | Security rule, fine; cosmetic for engineers | - | ALL |

---

## C3. Outputs without visible derivation

| id | file:line | what the user sees / what is not shown | R | persona |
|---|---|---|---|---|
| IO-C3-001 | cli/data.py:527-545 | `import-parts` prints per-row OK/ERROR but never the column mapping it guessed or which header became which field | R1,R6 | ELEC AIT |
| IO-C3-002 | cli/data.py:711-727 | `import-netlist` prints "OK added J01 (N signal pin(s))" but not the net -> signal mapping per pin (what `clean_net` produced or which nets became "no signal") | R1,R6 | ELEC |
| IO-C3-003 | cli/data.py:773-779 | `import-pinout` shows connector/pin counts; before/after values of pins are not shown (preview exists in GUI wizard: import_kinds.py `preview` rows; CLI does not) | R6,R7 | ELEC AIT |
| IO-C3-004 | cli/data.py:605-622 | `import-lengths` prints OK/ERROR per row, not the metre value stored or the old value | R1,R5 | AIT |
| IO-C3-005 | cli/data.py:634-652 | `import-build-data` shows "strip A 6 mm (was 5 mm)" in row messages (build_data_import.py:228-234): the one import with before/after; contacts/tools rows say "contact X, tool Y" only | R1 | AIT |
| IO-C3-006 | cli/main.py:192; core/outputs/stamp.py:22 | "(model e01643bd29d1)": a 12-hex hash of the whole serialised project; no way to see which files/values it covers or to diff two hashes | R9 | SYS |
| IO-C3-007 | cli/data.py:513-515; core/configcheck.py:231-257 | `config` lists what is missing, never the values in force (no `config show`) | R2,R3 | ELEC |
| IO-C3-008 | cli/main.py:149-153 | `generate` prints findings and counts; the per-object "rule: reason" lines kept in `generated/generation.json` ("provenance") have no CLI view (observed in the file) | R1 | SYS ELEC |
| IO-C3-009 | cli/main.py:449-452 | `migrate` prints one line "Migrated; originals kept ..." with no list of what was changed | R8 | SYS |
| IO-C3-010 | cli/main.py:117-127; core/io/loader.py:383-392 | "File differs from the tool's own formatting" names the file, not the lines | R8 | SYS |
| IO-C3-011 | cli/changes.py:129-138 | `compare` states what is *not* compared (generation record, baseline contents, outputs) - good; but no count of unchanged objects | R8 | SYS |
| IO-C3-012 | core/device_library.py:586,621-632 | device/part/type renamed or left out: notes only in the plan text; nothing stored | R8,R14 | SYS |
| IO-C3-013 | cli/data.py:574-579, 593 | `describe_library` line is the only persistent statement of where parts came from; one line, 12-hex hash | R14 | SYS ELEC |
| IO-C3-014 | cli/main.py:166-198 | `export` prints "34 files written" and verifies "independently"; the verifier's checks (core/outputs/verify.py) not listed in output | R1,R12 | AIT |

---

## C4. Forced choices (cannot change)

| id | file:line | forced choice | R | persona |
|---|---|---|---|---|
| IO-C4-001 | cli/main.py:189; cli/changes.py:159 | Outputs always go to `<project>/outputs`; `export` has no `--out`, no file/format selection (only `--drawings`) | R10,R14 | AIT ELEC |
| IO-C4-002 | cli/main.py (whole) | No `--json`/machine-readable output for any command except stdout CSV of `export-pinout` and Markdown of `drc`/`diff`/`compare`; results are text lines | R10,R11 | SYS |
| IO-C4-003 | core/outputs/build.py:135-171 | Fixed output set and column layouts; no template for column order/names for ERP/test equipment | R10,R14 | AIT |
| IO-C4-004 | cli/data.py:310-313,317; imports.py | `import-lengths` columns by position only; units mm/cm/m only | R5,R14 | AIT |
| IO-C4-005 | core/library_import.py:28-34 | Parts import cannot carry `ratings` (contact current/voltage) or notes; no column-to-field override on the CLI (only the pinout command has `--column`) | R3,R7 | ELEC |
| IO-C4-006 | core/pinout_import.py:312; core/library_import.py:166-169; core/generate/lengths.py:177; core/build_data_import.py:171 | One bad row blocks the whole import ("Nothing was changed"); no "import good rows, list the rest" | R6,R7 | AIT ELEC |
| IO-C4-007 | core/devices.py:912-921 | Termination limited to crimp / solder / unspecified; contact size is free text (core/model/physical.py:31) | R4,R13 | AIT |
| IO-C4-008 | core/library_import.py:98-107; core/model/library.py:11 | Part categories fixed to six; unknown category refused | R13 | ELEC AIT |
| IO-C4-009 | core/model/base.py:24-26 | No user-defined fields on any object; no free "source", "requirement", "comment" attribute persisted in project files; JSON config files cannot hold comments (canonical JSON, io/canonical.py:13) | R3,R13 | ALL |
| IO-C4-010 | core/library_import.py:315-327 | One library record (name/version/source/date) for the whole project: every parts import overwrites `source`; no per-part source | R9,R14 | SYS ELEC |
| IO-C4-011 | core/imports.py:172-177 | Only UTF-8 text; delimiter not selectable | R14 | ELEC AIT |
| IO-C4-012 | core/ids.py:7-8 | ID <= 64 chars, letter first; pin <= 16 chars; no way to keep a vendor/KiCad name as the visible ID | R14 | ELEC AIT |
| IO-C4-013 | core/kicad.py:319-331,351; cli/data.py:112-125 | A netlist import serves one device at a time; connectors chosen by reference prefix; sheet-path info removed | R14 | ELEC |
| IO-C4-014 | core/device_library.py:17-19; subsystem_library.py:16-20 | Device/subsystem import never replaces an existing device, only adds with a new ID; the project's own parts win; a subsystem is all-or-nothing | R7 | SYS |
| IO-C4-015 | core/library_folder.py:370-376 | A subsystem library file is never overwritten; the user must pick a new name or delete the file | R8 | SYS |
| IO-C4-016 | core/library_folder.py:44-45 | Library folder: one folder per user (QSettings), depth 3, 2000 files | R3 | SYS |
| IO-C4-017 | core/io/saver.py:211-216,247 | Read-only project when saved by a newer version; recovered project cannot overwrite its folder; any upgrade makes a backup folder | R8 | SYS |
| IO-C4-018 | core/io/saver.py:224-229 | A save is refused while the integrity check has errors (unless a recovery copy) | R7 | SYS |
| IO-C4-019 | cli/main.py:139-163 | `generate` cannot be run without saving; no way to keep a draft in memory from the CLI | R6 | SYS |
| IO-C4-020 | core/generate/lengths.py:151-152 | Segment-length import is refused for a released harness (error per row); no override with justification | R7,R8 | AIT |
| IO-C4-021 | core/io/layout.py:24-28 | Only whitelisted file names are read; adding a user file type (extra tables) is impossible without code | R13 | ALL |

---

## C5. Everything exchanged with other tools or files

### C5-a Files and formats read or written

Columns: id | file:line | file/format, location | user told? | provenance carried | R | persona

| id | file:line | file / format and location | told? | provenance | R | persona |
|---|---|---|---|---|---|---|
| IO-C5-001 | core/io/layout.py:99-148; saver.py:252-259 | **Project folder**: `project.json`, `config/*.json` (derating, emc, generation, naming, segmentation, segregation, titleblock), `library/*.json` + `library/manifest.json`, `logical/units|interfaces/<subsystem-slug>.json`, `logical/{layout,links,interface_types}.json`, `physical/connectors/*.json`, `physical/harnesses/<id>.json`, `generated/generation.json`, `changelog.json`, `waivers.json`, `baselines/<harness>/<id>.json` | docs/FILE_FORMAT.md | `project.json` has name, description, schema_version, tool_version of last save; no timestamp, no author | R3,R9 | ALL |
| IO-C5-002 | core/io/saver.py:257-273 | `*.bak` beside every changed file (one generation); removed objects renamed `*.bak` | no (gitignored) | none | R8 | SYS |
| IO-C5-003 | core/io/fs.py:63-67,142-146 | `.<name>.<8>.tmp` temp files during save; swept by next save | no | none | - | - |
| IO-C5-004 | core/io/fs.py:269-289 | `.harness.lock` (JSON pid/host/since/boot/start) and `.harness.lock.takeover` guard; the guard is left in the folder (observed) | message on conflict | host name + pid | R8 | SYS |
| IO-C5-005 | core/recovery.py:21-22,41-79 | `.harness-recovery/session.json`: whole project (all files as strings, base fingerprint, quarantine) | restore prompt (gui, unverified) | `base_fingerprint` of disk files | R8 | SYS |
| IO-C5-006 | core/io/saver.py:283-315 | `.migration-backup-v<N>/` full copy of original files before an upgrade (built as `.partial`, renamed) | CLI message `MIGRATED`; result.backup_dir | none | R8 | SYS |
| IO-C5-007 | core/io/saver.py:261-266 | `quarantine.json`, `quarantine/files/<rel>` for unreadable data | issues | none | R8 | SYS |
| IO-C5-008 | core/io/saver.py:275-277; core/mergefix.py:56-62; templates.py:91 | `.gitignore` (written by every save if absent), `.gitattributes` (written by `new` and, via mergefix.write_gitattributes, by merge-fix; not by plain save) | docs, `new` | none | R9 | SYS |
| IO-C5-009 | core/io/loader.py:366-380 | disk fingerprint: SHA-256 over managed JSON files; used to detect changes by Git/other users before save | error on save | hash only | R14 | SYS |
| IO-C5-010 | gui/app.py:16-18; gui/recent.py:15-69; gui/main_window.py (keys via grep: project/last, ui/*, tour/done, tree/expanded, layout/<hash>, export/open_after, library folder) | Per-user QSettings INI (e.g. `~/.config/HarnessDesigner/HarnessDesigner.ini` on Linux; path unverified): recent projects, last project, UI mode/role/user name (`ui/user`), theme, geometry, library folder path | Settings page (partial, unverified) | none | R3 | SYS |
| IO-C5-011 | core/io/canonical.py; core/schemas.py:81-105; cli/start.py:68-86 | **JSON Schemas** (`harness-design-studio schema FOLDER`): one per file kind, `editor-settings.json` for VS Code | CLI message | none; "generated from the model" | R3,R13 | SYS |
| IO-C5-012 | core/templates.py:94-102; cli/start.py:46-51 | **Import templates** copied to a folder: interfaces.csv, approved-parts.csv, segment-lengths.csv, strip-lengths.csv, pin-contacts.csv, accessories.csv, signal-map.csv, wheel-connectors.net, ampacity-DEMO-ONLY.csv, config-demo-values/, ci/ scripts, checklists | CLI message | EXAMPLE rows | R3 | ALL |
| IO-C5-013 | core/imports.py:145-229 | **Read**: CSV, TSV, JSON (list of flat records), XLSX/XLSM (first visible sheet) | CLI prints sheet name | none stored (except parts: name + 12-hex sha) | R14 | ELEC AIT |
| IO-C5-014 | core/kicad.py:199-250 | **Read**: KiCad netlist S-expression (.net) or XML, UTF-8/16/32 | no | not stored (design/source discarded) | R14 | ELEC |
| IO-C5-015 | core/device_library.py:75-161 | **Read/write**: device library JSON `harness-device-library` v1 (anywhere on disk); `.bak` kept by `atomic_write_bytes` (fs.py:97-105) | CLI line | none | R9,R14 | SYS |
| IO-C5-016 | core/subsystem_library.py:66,154-158 | **Read/write**: subsystem library JSON `harness-subsystem-library` v1 | CLI line | none | R9,R14 | SYS |
| IO-C5-017 | core/library_folder.py:135-157,335-377 | **Library folder** (shared drive/Git checkout): scanned (read) and written only by Save to library | UI/CLI text | none | R14 | SYS |
| IO-C5-018 | core/outputs/build.py:24-27,196-231 | **Outputs** `<project>/outputs/`: `manifest.json` (format, generator_version, model_hash, content_hash, placeholder_config, per-file sha256+bytes); `harnesses/<id>/{wirelist,pinouts,bom,mass_length,tests,labels,accessories}.csv`, `<id>.xlsx`, PDF/SVG drawings; `system/{bom,mass_length,mating_matrix,traceability,box_pinouts,drc_findings,changelog}.csv`, `drc_report.md`, `revision_report.md`, `export.json`, `provenance.json`, `system.xlsx`, diagram SVG/PDF | CLI line | stamp comment, manifest, provenance.json | R9,R10 | ALL |
| IO-C5-019 | core/outputs/stamp.py:54-61 | CSV: first line `# harness-design-studio <ver> model <12hex>`; LF endings, comma, UTF-8 (no BOM), apostrophe prefix rule | docs only | version + model hash | R9,R14 | ELEC AIT |
| IO-C5-020 | cli/data.py:940-975 | `export-pinout`: stdout CSV or .csv/.tsv/.xlsx; folder must exist; plain `write_bytes` (not atomic, no `.bak`) | message | stamp (version + hash) | R10 | ELEC AIT |
| IO-C5-021 | cli/data.py:518-520, 435 | ampacity CSV read from any path | message | not stored | R14 | ELEC |
| IO-C5-022 | cli/data.py:682-700 | signal-map file (CSV or JSON) | no | not stored | R14 | ELEC |
| IO-C5-023 | core/outputs/xlsx_env.py (opened only by import in imports.py:188) | XLSX read via openpyxl wrapper (`xlsx_env.load_workbook`); contents unverified | - | - | - | - |

### C5-b Exchange paths: what is assumed or dropped, what the engineer can see, what leaves, with what provenance

| path | assumed or dropped on import | what the engineer sees about the source | what leaves the tool (and provenance) | R | persona |
|---|---|---|---|---|---|
| **KiCad netlist** (kicad.py) | Net name -> signal via `clean_net` (sheet path cut, `unconnected-`/`Net-(` -> none); first pin wins for repeated names; all signal pins become `fixed`; value, footprint, pintype, design/source dropped; gender "unspecified"; spare pins 1..N filled for numeric pins | Per-connector OK line, warnings, unmatched signals list (cli/data.py:711-727); no per-pin table in CLI | Pinouts via `export-pinout`/`box_pinouts.csv`/`export.json` (stamp = version + model hash). No KiCad file name or hash recorded in the project, so a changed netlist cannot be detected | R1,R14 | ELEC |
| **Pinout table CSV/XLSX** (pinout_import.py) | Headings by alias; "Function" doubles as signal; Voltage/Current/Class/Remarks dropped with warning; blank termination = unspecified; "Fixed" column special; connector default J01; contact size free text; bad row blocks all | Row-level results, warnings (GUI also shows preview and map page: import_kinds.py:541-560 only partly read) | `export-pinout` writes the same columns as `box_pinouts.csv` (connector, role, mates with, part, pin, signal, interface, wires, spare), read back only by `import-pinout` (comment line skipped, line 90) | R10,R14 | ELEC AIT |
| **Parts / InvenTree / approved-parts list** (library_import.py) | IPN = ID; Name/Description = description; mass/weight = g; ratings, notes not importable and not warned; approval words from user; `unverified` cleared; tool only for contacts | CLI row results; `library` line "source: file (sha256 12hex)" overwritten by each import | Parts leave in `export.json`, `bom.csv`, `provenance.json` (library name/version/source/date/counts by approval); no per-part origin | R9,R14 | ELEC AIT SYS |
| **Build-data CSVs** (strip lengths, pin contacts, accessories, part tools) | Kind guessed from headings; strip/accessory lengths mm; "," read as decimal point; empty cell leaves value; ACC-nnn numbering; harness optional if unique | Row messages with before/after for strips; no source stored | `wirelist.csv`, `labels.csv`, `accessories.csv`, build workbook `<id>.xlsx`; stamp only; values show no "imported from" | R10,R14 | AIT |
| **Lengths file** (lengths.py + cli/data.py:597) | By position; unit from `--unit` (default mm); stored in metres rounded to 1 nm; <= 10,000 m; released harness refused | Row OK/ERROR only | `mass_length.csv`, `wirelist.csv` lengths; no record of the file or unit used | R5,R14 | AIT |
| **Ampacity CSV** (configcheck.py:197) | gauge int 0..40, amps > 0, whole-table replace; `placeholder` stays true | "Loaded N gauges into config/derating.json" | `config/derating.json` (plain JSON, no comment/source/unit key); outputs carry only `values_sha256_16` | R2,R9 | ELEC |
| **Device library / subsystem library files** | project parts/types win; file approvals kept; invalid records dropped with note; IDs auto-suffixed; zone cleared | plan rows and notes (CLI prints them; nothing stored) | The same files can be shared via Git/drive; no tool version, no date, no source project in them | R9,R14 | SYS |
| **Spreadsheets / ERP / test equipment** (outputs) | n/a | `manifest.json` lists sha256 per file and the model hash (detects edits of outputs); `placeholder_config` names unreviewed config files | CSV with `#` first line and apostrophe-prefixed cells; XLSX with an "About" sheet carrying the stamp; `export.json` without config values | R9,R10,R14 | AIT ELEC |

### C5-c Source memory and change detection (R14)

- Imports of netlist, pinout, lengths, build data, ampacity, devices, subsystems: no source file name, path, date or hash is stored in the project. Only the parts import stores `name (sha256 12hex)` (cli/data.py:549,574-579; gui/import_kinds.py:142-146,403-406), as one project-wide string.
- Nothing re-reads an import source later, so "source changed since import" cannot be detected for any import. The library folder is rescanned on demand (library_folder.py:248-253) but a device in the project keeps no link to its library file.
- Changes are detectable for project files (`disk_fingerprint`, loader.py:366-380) and for outputs (manifest sha256, build.py:24-47).
- Import history: the change log is written by `review`/`release`/`revise` only (cli/changes.py:160-175); History labels like "Import pinout (2 connectors, 36 pins)" (pinout_import.py:157-161) are undo labels; persistent record unverified (not found in files read).

### C5-d Command line (R11)

| command | file:line | reads | writes | notes |
|---|---|---|---|---|
| `validate`, `check` | main.py:58-62,108-136 | project | none | `check` adds non-canonical-file and merge-leftover checks; text output; exit 0/1/2 |
| `migrate` | main.py:449-452; saver.py:334-348 | project | project + `.migration-backup-v<N>` | refuses if errors/read-only |
| `generate` | main.py:139-163 | project | project (`generated/`, harnesses), `.gitignore`, lock guard | no dry-run; not saved if findings have errors |
| `drc` | main.py:201-212 | project | stdout Markdown | exit 1 for unwaived errors |
| `export [--drawings]` | main.py:166-198 | project | `outputs/` | verified before writing; removes old drawings if `--drawings` absent |
| `verify [--outputs]` | main.py:215-241 | project, outputs | none | |
| `new`, `templates`, `schema` | start.py:43-86 | bundled examples | new folder | folder must be empty |
| `merge-fix` | merge.py:116-172 | project | `generated/generation.json`, project | undoes on failure |
| `review`, `release`, `revise`, `diff`, `compare`, `log` | changes.py:127-188 | project(s) | project, outputs (release re-stamps, `_restamp`) | `--by` free text, `--date` default today |
| `config`, `library` | data.py:433-515, 582-594 | project, ampacity CSV | project | exit 1 while values missing |
| `import-parts`, `import-lengths`, `import-build-data`, `import-netlist`, `import-pinout`, `import-devices`, `import-subsystem` | data.py:523-937 | table/netlist/library file | project | `--dry-run` on all; lock taken (main.py:385-420) |
| `export-pinout`, `export-devices`, `export-subsystem` | data.py:810-975 | project | file or stdout | folder must exist |

- Python API: the core is GUI-free (core/__init__.py docstring: "Headless core ... enforced by tests") and the CLI calls `load_project`, `generate_project`, `build_outputs`, `plan_*_import`, `History(project).execute` directly, so the same calculations are reachable from Python. **No documented Python API or scripting guide was found in docs/ (README/docs grep for `load_project|import harness_design_studio` returned nothing).** The only automation docs are CLI exit codes and `templates/ci/build.sh`.
- Machine-readable output: `export.json` (documented in docs/OUTPUTS.md, per exports.py:57), `provenance.json`, `manifest.json`; command results are plain text only.
- Batch: shell scripts only (`ci/build.sh`, GitHub workflow); `--version` prints `harness 1.11.1` (main.py:71) although the program is named `harness-design-studio`.

### C5-e Schema versions and migration

- `SCHEMA_VERSION = 1` (core/model/project.py:16). `schema_version_of` (migrate.py:144-150): missing = 0; an unreadable `project.json` is treated as current. Newer file -> read-only (loader.py:340-343); older -> `MIGRATIONS[v]` applied to raw JSON in memory (loader.py:344-347), "nothing changes until you save", then `.migration-backup-v<N>/` is made on save.
- Only `v0 -> v1` exists (migrate.py:141). Documented as lossless; what changes: `tool` -> `tool_version`; `redundant` bool -> `side` ("redundant" only if `is True`).
- Later additions did not raise the version (docs/FILE_FORMAT.md:63; base.py:29-33), so a "version 1" file may need a specific tool version; no per-file feature list.
- No migration entry in change log or project metadata.

---

## C6. Customisation points that exist

| id | file:line | what the engineer can change | R | persona |
|---|---|---|---|---|
| IO-C6-001 | cli/data.py:92-109 | `--approved/--pending/--rejected` value lists and `--category` for parts import; unknown status words are refused, never guessed | R3,R7 | SYS ELEC |
| IO-C6-002 | cli/data.py:337-349; library_import.py:305-327 | `--library-name/-version/-source/-date` stored in `library/manifest.json` | R9 | SYS |
| IO-C6-003 | cli/data.py:118-161 | Netlist: `--device --ref --prefix --connector REF=ID --part REF=PART --signal-map (inline, CSV or JSON) --pin-function --dry-run`; KiCad fields `HarnessConnector`, `HarnessPart` | R3,R14 | ELEC |
| IO-C6-004 | cli/data.py:162-219,759-767 | Pinout: `--column FIELD=HEADING`, `--new-device --subsystem --part --default-part --gender --connector --replace --dry-run` | R3,R6 | ELEC AIT |
| IO-C6-005 | cli/data.py:316-319 | Lengths `--unit mm|cm|m`, `--dry-run` | R5 | AIT |
| IO-C6-006 | cli/data.py:48-77 | `config --ampacity-csv`, `--counterparts`, `--distinct-roles on|off`, `--apply-profile ecss-q-st-30-11c|ecss-e-st-20-07c` (marks values placeholder until reviewed) | R2,R3 | ELEC SYS |
| IO-C6-007 | core/io/canonical.py; docs/FILE_FORMAT.md | All config and project data is plain sorted JSON; hand edits are detected (`non_canonical_files`, loader.py:383-392) and merge line by line in Git | R3 | ALL |
| IO-C6-008 | core/schemas.py:81-105; cli/start.py:68-86 | JSON Schemas + VS Code settings for completion and checks while editing by hand | R3,R13 | SYS |
| IO-C6-009 | core/kicad.py:309-320 | `plan_netlist_import` arguments are an API: refs, prefix, ids, parts, signal_map, use_pin_function | R11 | ELEC |
| IO-C6-010 | core/device_library.py:225-276,433-458; subsystem_library.py:185-223 | Export devices/subsystems to shareable JSON; conflicts refused unless `--replace`; `new_ids` under another ID | R14 | SYS |
| IO-C6-011 | core/library_folder.py:135-157 | Shared library folder (drive or Git), read-only unless Save to library | R14 | SYS |
| IO-C6-012 | cli/changes.py:62-80 | Release overrides with justification: `--accept-placeholders REASON`, `--accept-unapproved-parts REASON` (>= 10 chars, kept in change log and baseline) | R7,R8 | SYS |
| IO-C6-013 | core/outputs/build.py:24-47,196-231; cli/main.py:83 | `manifest.json` (sha256 per file), `export.json`, `provenance.json`; `--drawings` switch | R9,R10 | ALL |
| IO-C6-014 | cli/main.py:331-348; templates/ci/build.sh | Documented exit codes and CI scripts for automation | R11 | SYS |
| IO-C6-015 | core/pinout_import.py:90-93 | The tool's own `export-pinout` CSV/XLSX reads back in `import-pinout` (comment line / About sheet skipped) | R14 | ELEC AIT |
| IO-C6-016 | core/mergefix.py; cli/merge.py | `.gitattributes` + `merge-fix` for generation record conflicts | R8 | SYS |

---

## Top findings

1. **Parts import cannot carry ratings and drops other columns silently** (IO-C1-012, IO-C4-005): contact current, voltage and notes have no import field and no warning; the derating logic uses `ratings` (config key `contact_rating_key`). [ELEC]
2. **Ampacity table has no conditions, source or units record** (IO-C1-041, IO-C2-004, IO-C2-031): one CSV replaces the whole table; temperature, bundle, insulation and source/date are not stored; only a 16-hex hash reaches outputs. [ELEC]
3. **`export.json` and `provenance.json` omit the config values** (IO-C2-017, IO-C2-018): another tool or a reviewer cannot see derating, resistivity, margins or test limits that produced a number; only `values_sha256_16`. [ELEC SYS]
4. **KiCad import discards pin type, source, footprint and collapses same-named nets across sheets; no source memory** (IO-C2-005, IO-C2-006, IO-C5-014): electrical intent from the schematic is lost and a changed netlist cannot be detected. [ELEC]
5. **Units and decimal handling on build data are fixed and partly wrong-by-default** (IO-C1-037, IO-C1-038, IO-C2-001, IO-C2-003): strip/accessory lengths always mm, any comma becomes a decimal point ("1,234" -> 1.234 mm), lengths default `--unit mm`, mass/weight assumed grams. [AIT ELEC]
6. **CSV exports are altered for other tools and cannot be re-imported** (IO-C1-057, IO-C2-021, IO-C2-022): a `#` stamp line, `'` prefix on `+28V`/`-5V`, and no comment-skip in lengths/build-data/parts readers. [AIT ELEC]
7. **No import remembers its source; only parts keep a single overwritten string** (IO-C5 section c, IO-C4-010): no file, date or hash for pinouts, lengths, strips, contacts, netlists, devices; R14 change detection impossible. [ALL]
8. **No JSON output, no output folder choice, no documented Python API** (IO-C4-001, IO-C4-002, C5-d): the core is headless and usable from Python, but nothing documents it, and `config` shows only what is missing, not the values in force (IO-C3-007). [SYS ELEC AIT]

(Also notable: imported parts clear `unverified` and device-library parts bring the file's approval (IO-C1-016, IO-C1-046); `extra="forbid"` blocks any user-defined field (IO-C2-024, IO-C4-009).)

Next: [the audit](../transparency_audit.md), [appendix D](outputs.md), [appendix F](editing-and-change-control.md)
