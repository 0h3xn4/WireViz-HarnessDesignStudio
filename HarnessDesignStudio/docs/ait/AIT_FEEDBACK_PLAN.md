# Plan for version 1.4.0: the feedback of the AIT engineers

This page says what the AIT engineers asked for, what the tool does about each point today (checked in the code of version 1.3.0), what version 1.4.0 changes and in which order. It is a plan and a record, not a promise: each milestone is a pull request with tests, and what is not built yet is marked.

**Status (2026-10-20).** All five milestones were built and published in version 1.4.0 (pull requests 83 to 88, tag `v1.4.0`). What is only partly done, in the words of the requirements: *#1* there is no live connection to InvenTree (the tool never uses the network); an export file of InvenTree is read offline. *#8* the last commit of the repository is shown; edits that are not committed yet and who made them are not. *#9* soldering is a pin's termination in the lists; what else it needs is for the AIT engineers to say. The rest is done as the table says. The plan below is kept as it was written, with the version 1.3.0 column as the starting point.

## The ten requirements and where they stand

| # | Requirement | In 1.3.0 | Milestone |
| --- | --- | --- | --- |
| 1 | The standard components library connected to InvenTree (nice to have) | missing; the tool has a project parts library (CSV or XLSX import) and never opens a network connection | M5 (the parts import reads an InvenTree export file, .csv .tsv .json .xlsx; no live connection, D-165) |
| 2 | Store connectors or devices with an editable pinout | a device can be defined down to each pin inside a project; nothing to reuse across projects | M5 (a device library file, D-165) |
| 3 | A function (name) on every pin | a pin has a name and a signal; no free-text function | M3 |
| 4 | Choose colour, gauge and type of wires | colour per signal only; gauge is calculated; the type comes from the library part; no way to set them for one wire | M1 |
| 5 | Every pin-to-pin wire editable | wires are generated; a hand choice needs `"locked": true` in the harness file and the app has no button | M1 (edit a wire), M2 (add, move and delete a wire) |
| 6 | Several cables on one pin | generation puts one signal on one pin; the file format has splices, nothing creates them | M2 |
| 7 | State the twisting | pairs come from the interface type; nothing per wire or cable | M2 |
| 8 | Version control: version, who made the last change | revision and a change log that names who reviewed, released or revised; nothing for edits between releases | M4 (the last commit of the Git repository around the project folder, read without starting Git, D-164) |
| 9 | Soldering | a pin has a termination (crimp, solder, unspecified) and nothing uses it | M3 (written to the lists; what else they want is to be discussed) |
| 10 | A label on connectors and on the harness | `labels.csv` is generated; the text cannot be edited; a harness has no label | M3 (and a wire label in M1) |

## Rules for every milestone

1. **Old projects open and behave as before.** Every new field is optional. A field that still has its default value is **not written** to the project files (`SparseEntity` in `core/model/base.py`), so a project that does not use a new feature keeps byte-identical files, the same model hash and the same outputs. The check is `python -m tools.output_hashes --check docs/ui/OUTPUT_HASHES_1.2.0.json` (567 files, apart from the version stamp) and `tests/test_output_hashes.py`.
2. **New output columns exist only when used**, like the EMC class column: a project without wire labels or notes gets the same wire list as before. The independent verifier (`core/outputs/verify.py`) learns every new column or text.
3. **The file format stays at schema version 1.** A project that uses a new field cannot be read completely by 1.3.0 (an older tool quarantines fields it does not know and says so); a project that does not use them can.
4. **Generation never destroys a person's choice.** What a person typed is kept when the harnesses are generated again; if it cannot be kept (the connector is gone) the tool says what was lost, as it does for locked wires today.
5. **Released harnesses stay locked.** Every edit goes through `History.execute` and `check_locks`; a new revision unlocks it.
6. **No engineering value is invented.** The tool offers the colours of IEC 60757 and the wire parts of the project library; it sets no gauge or colour of its own.
7. The rule "UI only" of the 1.3.0 overhaul does not apply to 1.4.0; the owner asked for this work. Everything else of the design rules in `CLAUDE.md` does.

## Milestones

- **M1, edit a wire** (requirements 4, 5, 10 in part). Per wire: gauge, type (library wire part), colour, length, a label text and a note. Gauge, type, colour and length lock the wire against regeneration; label and note are always kept. A wire can be reset to what generation would give. Where: `core/wires.py` (plans), the Harness tab (an *Edit wire* form beside *Why*), wire list and labels, verifier, change control, tests, manual page.
- **M2, wires that a person draws** (5, 6, 7). Add a wire between two pins of the connectors of a harness, move one end, delete it; generation keeps such wires. Several wires on one pin with a check that says so; twisting a set of wires (a twisted-pair group that a person makes).
- **M3, small additions** (3, 9, 10). A free-text function on every pin, a label on every connector and on the harness, the termination (soldered or crimped) in the pinouts and the wire list.
- **M4, who changed what** (8). A project version and, when the project folder is a Git repository, the last commit (who, when, what) next to the revision. It is read from the repository's own files, not with the `git` program (D-164), so the rule against `subprocess` keeps its single exception.
- **M5, reuse** (1, 2). A device and connector library that can be exported from one project and imported into another, and an import of an InvenTree export file into the parts library.

Each milestone ends with the output proof, the tests, the documents (manual, guide, file format, decisions) and a pull request that CI checks on Linux, Windows and macOS. The version becomes 1.4.0 with the last milestone.
