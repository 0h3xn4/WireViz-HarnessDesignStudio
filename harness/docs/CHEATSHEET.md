# Cheat sheet

One page. Every command is explained in [`CLI.md`](CLI.md); `harness COMMAND --help` prints the same in a terminal.

## The loop

```
harness new my-design --template first-steps   # start a project that has units (harness new --list shows the examples)
harness generate my-design                # make harnesses, connectors, pins, wires
harness check my-design                   # validate, plus leftovers of Git merges and edits to released harnesses
harness drc my-design                     # the full design rule check, as a report
harness export my-design                  # drawings, wire lists, pinouts, BOM, test tables
harness verify my-design --outputs        # an independent check of the exported files
```

Run the loop again after every change. Generating twice without a change changes nothing (the second run prints "0 added").

The command line cannot add units or interfaces. The loop works on a project that already has them: an example such as `first-steps`, or your own design after you added the units in the app. On a `blank` project `generate` finds 0 interfaces and `export` stops with `error: there are no harnesses to export; run harness generate first.`

## Bring in data

| You have | Command |
| --- | --- |
| the example import files, demo values and CI scripts | `harness templates my-templates` (the folder must be new or empty) |
| interfaces in a table | app only: **File > Import interfaces** |
| a parts list | `harness import-parts DIR parts.csv --approved Approved` |
| segment lengths | `harness import-lengths DIR lengths.csv --unit mm` |
| unit connectors in KiCad | `harness import-netlist DIR file.net --unit RW1 --prefix J --connector J1=RW1-J01 --dry-run` |
| engineering values | edit `config/*.json`, see [`CONFIG.md`](CONFIG.md); `harness config DIR` lists what is missing |

Add `--dry-run` to any import to see what it would do first. Other commands (`compare`, `schema`, `library`, `migrate`, and options such as `config --ampacity-csv`) are in [`CLI.md`](CLI.md).

## Release and change

```
harness review  DIR W001 --by "Name"                                   # submit for review
harness release DIR W001 --by "Name" --comment "why, 10+ characters"   # baseline, change log entry, lock
harness revise  DIR W001 --by "Name" --comment "why, 10+ characters"   # open a new revision of a released harness
harness diff    DIR W001                                               # what changed against the baseline
harness log     DIR                                                    # the change log
```

The comment must have at least 10 characters. A release is blocked while checks fail, while a configuration file is a placeholder, or while the harness uses parts that are not approved. You can release anyway with `--accept-placeholders REASON` and `--accept-unapproved-parts REASON`; the reason is kept in the change log.

## Exit codes

`0` success (warnings allowed), `1` the project has errors or a step is blocked, `2` usage error or an unreadable project (also a project with damaged files), `130` interrupted with Ctrl-C.

## In the app

| Keys | Action |
| --- | --- |
| Ctrl+N, Ctrl+O | new project, open project |
| Ctrl+S, Ctrl+Shift+S | save, save as |
| Ctrl+Shift+I | import interfaces (a table) |
| Ctrl+Q | quit |
| Ctrl+K | command palette: type a command or an ID |
| Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z | undo, redo |
| Ctrl+=, Ctrl+-, Ctrl+0 | zoom in, out, fit |
| C, Esc | start the Connect tool, back to Select (Esc also clears the selection) |
| Tab, Enter or Space | move between units and links, select |
| Shift+arrows | move the selected unit |
| Delete | delete the selected item (after showing what it affects) |
| F1 | the user guide |

## What is where

```
my-design/
  project.json        name and description
  config/             engineering values (rules you or your programme supply)
  library/            parts and interface types
  logical/            units and interfaces (what you draw)
  physical/           connectors and harnesses (what the tool generates)
  generated/          how the last generation was made (for explanations)
  outputs/            drawings and lists (safe to delete and regenerate)
  changelog.json      release history
  baselines/          the frozen copy of each released harness (written at release)
```

Put the folder in Git. Everything except `outputs/` is meant to be reviewed as text.

## Words you will meet

| Word | Meaning |
| --- | --- |
| unit | a box: computer, power unit, wheel, sensor |
| interface | a connection need between two units: power, RS-422, CAN, ... |
| harness | a bundle of wires with connectors that carries interfaces |
| *pending* | a value is missing; nothing was invented |
| *not checked* | a rule could not run because its numbers are not supplied |
| placeholder | a configuration file nobody has reviewed yet |
| baseline | the frozen copy stored at release |

More: [`CONCEPTS.md`](CONCEPTS.md) and the glossary in the user guide.

Next: [user manual](user-manual/README.md), [`CLI.md`](CLI.md), [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).
