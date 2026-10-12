# Open decisions and their options

> **Historical.** Written for the owner as of the October 2026 audit, before 0.1.0 was released. The owner released 0.1.0 with D-10, D-11, D-12 and D-15 still open ([`SIGNOFF.md`](../compliance/SIGNOFF.md), [`DEVIATIONS.md`](../compliance/DEVIATIONS.md) T-31), so the options below are still the options, but "you" and "after the audit" refer to that time. The current status is in [`SIGNOFF.md`](../compliance/SIGNOFF.md).

Status after the October audit. Decided by you: D-11 and D-12 will be supplied later (the tool is prepared, see below), D-13 KiCad is the CAD tool, D-20 not needed.

## D-10 Harness boundary rule (what goes into one harness)
| Option | Result | Good for | Cost |
| --- | --- | --- | --- |
| **A. One harness per pair of connectors** (current default, `per_connector_pair`) | many small harnesses, each a cable between exactly two connectors | modular units with one cable per connector; simplest drawings and tests | many drawings; no shared trunk |
| **B. One harness per pair of units** (`per_unit_pair`) | all connectors between two units become one multi-connector harness | box-to-box cable sets built as one assembly | still point to point |
| **C. One harness per pair of routing zones** (`per_zone_pair`) | one trunk per zone pair with all signals running along it | flight looms that follow the structure and break out near the units | needs the branch and segment model fully used (breakouts, in-line connectors, trunk lengths); more drawing work |
| **D. A rule plus your overrides** | A, B or C as the default, and a table "interface to harness" you can edit; locked assignments are never changed | real projects where the manufacturing split is decided by people | an editor for the table and a clear report of what moved |

Always on, whatever you choose: nominal and redundant chains and pyro lines never share a harness. Extra rules you can add: split by segregation or EMC class, maximum wires or pins per harness, in-line connectors at panel breaks.
What I need from you: what one drawing in your manufacturing package is (a cable between two connectors, a box-to-box set, or a whole loom), and whether trunks with breakouts are used.
My recommendation: keep A until the answer is known; choose C only if you build looms.

## D-15 Title block
| Option | Result | Needs from you |
| --- | --- | --- |
| **A. Generic, configurable** (current) | fields and order from `config/titleblock.json`, fixed layout | nothing; you choose the field list |
| **B. Your company template** | the tool fills named fields into your empty frame | an SVG, PDF or DXF of the empty title block and frame, and which field goes where |
| **C. A standard layout** (ISO 7200 style fields: owner, title, document number, revision, date, sheet, size, status, approvals) | a fixed standard block | which standard your program follows |
| **D. B or C plus extras** | revision history table on the drawing, logo, legal text, zone markers on the frame | the same, plus the wording and the logo |

Also decide: how the document number is built from project and harness ID, which languages, and whether the drawing carries a revision table.
My recommendation: B if a template exists (exact look, least rework), otherwise C.

## Prepared for what you will supply
- **D-11 values**: `harness config DIR` lists every missing value and what depends on it, validates values when they arrive (ranges, table order), loads the ampacity table from a CSV; invalid values are rule errors. See `docs/IMPORTS.md`.
- **D-12 approved parts list**: `harness import-parts` with column matching and a statement from you of what each approval value means. A program-specific format can be added as a mapping once you can show a sample file.
- **D-13 lengths**: `harness import-lengths` (CSV, millimetres by default). KiCad is the source of unit connector pinouts; the lengths come as a table. `harness import-netlist` reads the connector pinouts from a KiCad netlist (D-123, D-124, `docs/KICAD.md`); it was checked on one real KiCad 10.0.6 export.
