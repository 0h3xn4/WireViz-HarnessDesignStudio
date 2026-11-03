# Follow the workflow

This page shows the whole work of the tool in one table: the nine steps from the devices to the as-built records, what each step **uses** and **makes** (project files, configuration, output files), the intermediate results you can look at and, where the tool allows it, change, and how to see where your own project stands. Use it when you want to know why an output is out of date, which file a step reads, or where a number you want to check was made.

> **New in the transparency work, stage S9 (decisions D-191, D-193; requirement R6).** The table below is made from one place in the program, `core/workflow.py`; the Next step page, the command `workflow` and the function `api.get_workflow` read the same place. A test fails if this page and the program disagree, or if a step names a file, an output, a table or a command that the tool does not have.

## Contents

- [The steps](#the-steps)
- [What you can look at, and change](#what-you-can-look-at-and-change)
- [See where your project stands](#see-where-your-project-stands)
- [On the Next step page](#on-the-next-step-page)
- [What the states mean](#what-the-states-mean)
- [What this does not do](#what-this-does-not-do)

## The steps

`<name>` stands for the part of a name that changes: `<subsystem>` is the subsystem of a device, `<harness>` the ID of a harness (`W001`), `<category>` a part category (`connector`, `wire`, `contact` ...), `<baseline>` the ID of a baseline. A name in the column *Uses* that is not a file path, for example *a device or subsystem file*, is a file you bring in.

<!-- workflow-table:start -->
| Step | What it does | Uses | Makes | Command | On screen |
| --- | --- | --- | --- | --- | --- |
| **Define the devices** | Put the devices of the system in the project, each with its connectors and pins. | `library/<category>.json`<br>*a device or subsystem file (import-devices, import-subsystem)* | `logical/units/<subsystem>.json`<br>`physical/connectors/<subsystem>.json` | `harness-design-studio import-devices` | Devices; Edit > Add device |
| **Connect them** | Say which devices talk to each other: interfaces of a type, or connections pin to pin. | `logical/units/<subsystem>.json`<br>`logical/interface_types.json` | `logical/interfaces/<subsystem>.json`<br>`logical/links.json` | - | Model; Edit > Connect |
| **Set the engineering values** | Give the project its derating, grounding, test limits and the choices of the models. | `library/<category>.json` | `config/derating.json`<br>`config/generation.json`<br>`config/segmentation.json`<br>`config/model.json`<br>`config/naming.json`<br>`config/titleblock.json` | `harness-design-studio config` | Design > Engineering values |
| **Generate the harnesses** | Allocate the pins, group the interfaces into harnesses, size and route the wires. | `logical/units/<subsystem>.json`<br>`logical/interfaces/<subsystem>.json`<br>`logical/links.json`<br>`physical/connectors/<subsystem>.json`<br>`config/derating.json`<br>`config/generation.json`<br>`config/segmentation.json`<br>`config/model.json`<br>`config/naming.json` | `physical/harnesses/<harness>.json`<br>`generated/generation.json` | `harness-design-studio generate` | Design > Generate harnesses |
| **Check the design** | Run the design rules and see what is open; accept a finding with a reason only where the tool allows it. | `physical/harnesses/<harness>.json`<br>`config/derating.json`<br>`config/model.json` | `system/drc_findings.csv`<br>`system/drc_report.md`<br>`waivers.json` | `harness-design-studio drc` | Checks |
| **Enter the build data** | Give the wires strip lengths and the pins their termination, contact and crimp tool, and add accessories. | `physical/harnesses/<harness>.json`<br>`library/contact.json`<br>*a strip-length, contact, accessory or tool sheet (import-build-data)* | `physical/harnesses/<harness>.json`<br>`library/contact.json` | `harness-design-studio import-build-data` | Drawings; the wire and connector editors |
| **Write the outputs** | Write the build workbook, the tables and the exports, and check them against the design. | `physical/harnesses/<harness>.json`<br>`config/generation.json`<br>`config/titleblock.json`<br>`config/naming.json`<br>`library/<category>.json` | `harnesses/<harness>/<harness>_build.xlsx`<br>`harnesses/<harness>/tests.csv`<br>`harnesses/<harness>/wirelist.csv`<br>`system/bom.csv`<br>`system/provenance.json`<br>`manifest.json` | `harness-design-studio export` | Design > Export |
| **Review and release** | Submit a harness for review, then release it: the release freezes what it was made from. | `physical/harnesses/<harness>.json`<br>`manifest.json`<br>`waivers.json` | `baselines/<harness>/<baseline>.json`<br>`changelog.json`<br>`system/revision_report.md`<br>`system/changelog.csv` | `harness-design-studio release` | Revisions |
| **Record what was built** | Write down serial and lot numbers, cut and strip lengths, tools and the measured test results, and compare them with the design and the test limits. | `harnesses/<harness>/<harness>_build.xlsx`<br>*the as-built sheet (export-asbuilt) filled in*<br>`config/generation.json` | `asbuilt/records.json`<br>`imports/records.json`<br>`system/asbuilt_report.md`<br>`system/asbuilt_report.csv` | `harness-design-studio import-asbuilt` | As-built |
<!-- workflow-table:end -->

`export` writes the files of the steps *Check the design* and *Review and release* too (the findings and the revision report); `drc` prints the same report on the screen. The table names only the files that matter for a step, not every file: [what each output file holds](../OUTPUTS.md).

## What you can look at, and change

The tool does not hide what it works out on the way. These are the intermediate results, where to look at them, and where to change them. "Change" means a way that is kept: the value you set is not overwritten by the next *Generate* (an override with a reason, see [override and keep a history](override-and-keep-a-history.md)), or it is a setting of the project.

<!-- workflow-inspect:start -->
| Step | Intermediate | Look at it | Change it |
| --- | --- | --- | --- |
| Define the devices | The pins of a device | Devices tab | edit them in the Devices tab |
| Connect them | The interfaces and their endpoints | Interface table | edit them in the table |
| Set the engineering values | Every setting, its value, its unit and where it comes from | settings DIR | config DIR --apply-profile, or the Engineering values window |
| Set the engineering values | What is still pending | config DIR | set the value; the file stays a placeholder until reviewed |
| Generate the harnesses | The candidates and the limits that sized each wire | explain DIR WIRE; export-data table wire_sizing | override DIR WIRE FIELD VALUE --reason TEXT |
| Generate the harnesses | The groups of the segmentation and why | explain DIR HARNESS; export-data tables segmentation_groups, segmentation_interfaces | the segmentation settings (settings DIR) |
| Generate the harnesses | The allocation of the signals to the pins | explain DIR CONNECTOR.PIN; export-data table pin_allocation | lock a pin in the Devices tab |
| Generate the harnesses | The derived lengths of the wires | explain DIR WIRE; export-data tables lengths, segment_lengths | import-lengths, or override a length |
| Check the design | The limit or comparison behind each finding | explain DIR --all; export-data tables rule_results, findings | the settings the rule reads (settings DIR) |
| Enter the build data | What is ready to build and what is open | explain DIR HARNESS; export-data table readiness | enter the missing data; settings DIR names the checks that block |
| Write the outputs | Every number as a table | export-data DIR --out FOLDER | - |
| Write the outputs | The test limits printed on the Tests sheet | explain DIR HARNESS.T001; export-data table test_limits | the three test limits in config/generation.json |
| Review and release | What a release froze, and what changed since | diff DIR HARNESS; log DIR HARNESS | start a new revision (revise) |
| Record what was built | What is missing, out of its limit or different from the design | asbuilt DIR; explain DIR HARNESS.T001 | import the sheet again with the corrected values |
<!-- workflow-inspect:end -->

`export-data DIR --out FOLDER` writes all of these as tables, with the unit in each heading ([export the data](export-the-data.md)); `explain DIR OBJECT` shows how one number was made ([see what the tool assumes](see-what-the-tool-assumes.md), the pages of [the models](../models/README.md)).

## See where your project stands

```
harness-design-studio workflow my-design
harness-design-studio workflow my-design --json
```

The command prints, for each step, a state and one sentence (*3 engineering values still to set*), the steps before it that block it, what it uses and makes, and the intermediates. It reads the project and the folder `my-design/outputs` (or the one you name with `--outputs`) and changes nothing. In a script: `api.get_workflow("my-design")`.

## On the Next step page

Open **Next step**, press **What this step uses and makes** under the steps. It is closed until you open it, so the page stays short. It shows the step you are on (what it uses, what it makes, what you can look at) and one line for each of the nine steps with its state. The top bar's three steps (Generate, Check, Release) and the six steps of the page are named from the same table.

## What the states mean

| State | Meaning |
| --- | --- |
| done | the step has been done and what it made matches the design |
| to do | not done yet |
| pending | something is missing that a person has to enter: engineering values, strip lengths, terminations, contacts, as-built values |
| out of date | what the step made is older than the design (generated plans, written outputs) |
| needs attention | a check failed with an error, or an as-built value is out of its limit |
| blocked | a step before it has to be done first; the command and the page name it |

*Done* never means approved or compliant. It says that the step was done and what it made matches the design.

## What this does not do

- It does not change the project, run a step for you or decide the order: you can do the steps in any order that the tool allows, and *blocked* only says what a step needs.
- It does not list every file of a project; the format of the files is in [the file format](../FILE_FORMAT.md) and the outputs in [the outputs](../OUTPUTS.md).
- It does not say that a design is ready to release; that is the check and the review.

Next: [choose your role](choose-your-role.md), [record what was built](record-what-was-built.md), [export the data](export-the-data.md), [the models](../models/README.md).
