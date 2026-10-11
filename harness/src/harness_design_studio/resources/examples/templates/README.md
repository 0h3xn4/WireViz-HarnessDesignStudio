# Templates

Files to copy and adapt. Get them with `harness templates FOLDER`.

| File | Use it for | How |
| --- | --- | --- |
| `interfaces.csv` | importing interfaces between units | app: **File > Import interfaces** |
| `approved-parts.csv` | importing your approved parts list (five example rows: Micro-D and RJ45 parts of the starter library and one D-sub part; three are Approved, one is Review, one is Rejected) | `harness import-parts DIR approved-parts.csv --approved Approved --pending Review --rejected Rejected` |
| `segment-lengths.csv` | importing harness segment lengths (millimetres) | `harness import-lengths DIR segment-lengths.csv --unit mm` |
| `wheel-connectors.net` | a KiCad netlist for the unit connectors of `RW1` in the `first-steps` project | `harness import-netlist DIR wheel-connectors.net --unit RW1 --prefix J --connector J1=RW1-J01 --connector J2=RW1-J02 --dry-run` |
| `signal-map.csv` | renaming KiCad net names to interface signal names, for netlists whose net names differ (`CAN_H` to `CANH`, `TXP` to `TX+`); not needed for `wheel-connectors.net`, whose net names already match | add `--signal-map signal-map.csv` to `import-netlist` |
| `config-demo-values/` | **learning only**: example engineering values so that wire sizing, voltage drop and test limits show up | copy the four files over `DIR/config/` of a practice project |
| `ampacity-DEMO-ONLY.csv` | **learning only**: a current-by-gauge table in the format `harness config --ampacity-csv` reads | `harness config DIR --ampacity-csv ampacity-DEMO-ONLY.csv` |
| `ci/build.sh` | a script that validates, generates, checks and exports a project, with the exit codes | `sh ci/build.sh DIR` |
| `ci/github-actions.yml` | the same as a GitHub Actions workflow for a design repository | copy to `.github/workflows/` |
| `design-worksheet.md` | planning a design on paper before using the tool: units, interfaces, and the data you do not have yet | print it or copy it next to your design and fill it in |
| `design-review-checklist.md` | a list of things to look at before a harness is released | copy next to your design |

## Read this before using the demo values

The values in `config-demo-values/` and `ampacity-DEMO-ONLY.csv` are **not from any standard and not engineering data**. They exist so that you can see what the tool does when the numbers are filled in. The files stay marked `"placeholder": true`, so every result built on them still says so. For a real design your own programme's values replace them (see `docs/CONFIG.md`), and only then is `"placeholder"` set to `false`.

## The CSV files

- Header names are matched by meaning, so `from` is also read from `source`, `part number` from `pn` or `mpn`, and so on (see `docs/IMPORTS.md`). Order of columns does not matter.
- CSV files may use commas, semicolons or tabs. A decimal comma needs quotes (`"1,5"`) when commas separate the columns.
- Excel files (`.xlsx`) work too. The first sheet is read.
- Every import first shows what it would do. With the command line, add `--dry-run`; nothing is changed until you run it again without it.
