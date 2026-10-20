# Naming and title block

This page shows how to change the IDs the tool gives to harnesses, connectors and wires, and which fields the title block of a drawing shows.

## Before you start

- Both settings are files in the project's `config/` folder. They have the usual shape (`name`, `placeholder`, `values`; see [the shape of a config file](fill-in-engineering-values.md#the-shape-of-a-config-file)).
- Change them **before** you release anything. IDs are stable once a harness is released.
- The title block layout is a placeholder: the owner's decision D-15 (the company format) is open. The tool shows a generic title block whose fields you can choose. See [`OPEN_DECISIONS.md`](../OPEN_DECISIONS.md).
- Edit the files while the project is not open in the app.
- These patterns make the **IDs**. To print other text on the labels, give a wire, a connector or the harness a *label* in the app (since 1.4.0): a wire's and the harness's in the **Edit wire** tab, a box connector's on its card in the **Devices** tab. The ID does not change; `labels.csv` prints the label ([edit a wire](edit-a-wire.md)).

## 1. Name patterns: `config/naming.json`

The shipped file:

```
{
  "name": "naming",
  "placeholder": false,
  "values": {
    "box_connector": "{unit}-J{n:02d}",
    "cable_connector": "{harness}-P{n}",
    "harness": "W{n:03d}",
    "wire": "{harness}-{n:03d}"
  }
}
```

| Key | Used for | Default |
| --- | --- | --- |
| `harness` | a harness ID (`n` counts 1, 2, ...) | `W{n:03d}`, gives `W001` |
| `cable_connector` | the connectors on a harness | `{harness}-P{n}`, gives `W001-P1` |
| `wire` | a wire | `{harness}-{n:03d}`, gives `W001-001` |
| `shield` | a shield | `{harness}-S{n}` (not in the file; the default is used) |
| `branch` | a branch point | `{harness}-B{n}` |
| `segment` | a routing segment | `{harness}-L{n}` |

Add `shield`, `branch` or `segment` to the file if you want to change them. The key `box_connector` is in the file, but the program does not read it: connectors on a unit are always named like `OBC1-J01`.

Example. Set `"harness": "HN-{n:02d}"` and generate:

```
harness-design-studio generate wheel-link
```

The harnesses are now `HN-01` and `HN-02` (folders `outputs/harnesses/HN-01/` and so on), and their wires `HN-01-001`.

A pattern must give a different valid ID for every harness and number. If it does not, the tool says so and uses the default:

```
warning: [naming] The naming template 'naming.harness' is not valid; the default was used.
```

(That is what `"harness": "HN"` gives.) Valid IDs start with a letter and use letters, digits and `_ - .` only. The same fallback, with the same warning, happens when a pattern raises an error (`{x}` that does not exist), gives a reserved name such as `COM1`, repeats a name, or would give a name too long for the harness (the warning appears after the names are made). A pattern can no longer crash or hang the generation.

## 2. Title block: `config/titleblock.json`

The shipped file lists all ten fields, in order:

```
"fields": ["project", "harness_id", "title", "revision", "date",
           "author", "checker", "approver", "sheet", "status"]
```

Remove a field to hide it (the sheet number too: the output check then does not look for it), or reorder them. A name that is not in the list, a name twice, or anything that is not text is reported as a configuration error (`harness-design-studio validate` and `harness-design-studio config` show it, for example `config/titleblock.json: fields names a field that does not exist ('sheet2'). The fields are: project, harness_id, ...`) and the default fields (`project`, `harness_id`, `title`, `revision`, `status`, `sheet`) are drawn until it is fixed. An empty list also means the default. After a release the title block fields are frozen with the rest of the configuration ([change a released harness](change-a-released-harness.md)). With `["project", "harness_id", "revision", "status", "sheet"]` the title block of `HN-01` shows:

```
PROJECT         First steps: reaction wheel link
HARNESS ID      HN-01
REVISION        A
STATUS          draft
SHEET           1 / 1
```

(These are the texts found in the SVG of a test run, label and value. The layout on the sheet is not shown here.)

Date, author, checker and approver come from the harness itself. They show "-" until the harness has been reviewed and released ([release a harness](release-a-harness.md)).

## Common mistakes

- **Renaming after a release.** Released IDs are stable. Start from a project that has not been released, or start a new project.
- **A pattern without `{n}`.** Every harness would get the same ID. The tool falls back to the default and warns.
- **Expecting a company title block.** The format is open (D-15). Only the fields and their order are configurable.

More: [`CONFIG.md`](../CONFIG.md), [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).

Next: [export the outputs](export-the-outputs.md), [release a harness](release-a-harness.md)
