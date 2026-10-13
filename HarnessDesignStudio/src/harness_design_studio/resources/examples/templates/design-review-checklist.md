# Harness design review checklist

Copy this next to your design and tick it off for each harness before you release it. The tool checks most of this for you; the list says where to look.

Project: ____________  Harness: ______  Revision: ___  Reviewer: ____________  Date: ____________

## Before the review
- [ ] `harness check DIR` prints no error.
- [ ] `harness generate DIR` changes nothing (the harnesses are up to date).
- [ ] `harness verify DIR` finds no error.
- [ ] `harness export DIR` ran after the last change, and **Harness plans** says the outputs are up to date.

## Look at
- [ ] **Problems** tab: no error, every warning fixed or waived with a reason you agree with.
- [ ] **To-do** tab is empty or every item is understood.
- [ ] No interface shows *auto-filled*: a person confirmed every connector the tool chose.
- [ ] `harness config DIR`: nothing is missing; every file is reviewed and no longer marked `placeholder`.
- [ ] Every wire has a gauge (none *pending*) and a length.
- [ ] The **Why** tab explains each choice you did not expect.
- [ ] Parts: every used part is approved in your parts list.

## If you use the ECSS profiles (`harness config DIR --apply-profile ...`)
These points cannot be checked by the tool. The requirement IDs are in `compliance/requirements` of the tool's repository.
- [ ] Connector savers are used during equipment tests; mating cycles of every connector are counted and stay within the limit (ECSS-Q-ST-30-11C 6.11.3 b and e, 6.12.3 a and c).
- [ ] The contact assignments of connectors close to each other cannot cause damage if a wrong connector is mated (6.11.3 c).
- [ ] RF power keeps a 6 dB margin before multipactor (6.12.3 b), by analysis.
- [ ] Where the conditions of 6.32.4 b are not met, a thermal analysis exists (6.32.4 c); the temperature of every component connected to a wire is compatible with the wire (6.32.4 d).
- [ ] The bundle derating assumes every wire in the harness carries current; if wires are in cold redundancy or never carry current together, the factor L of Table 6-42 was applied by hand or justified (6.32.5.2).
- [ ] Bundles of different EMC categories are 5 cm apart or screened where they run in parallel (ECSS-E-ST-20-07C 4.2.13.1 c); the EMC category is visible on wires and labels (4.2.13.1 d).
- [ ] Cables outside the structure have individual shields (4.2.12.2 a); shields are not used as current paths except coax (4.2.13.2 a); shields have an insulating sheath (4.2.13.2 b); connectors for shielded wires have a conductive finish (4.2.13.2 c).
- [ ] The DC resistance of shield bonds is 5 mOhm or less and between the bonding stud and each connector housing 10 mOhm or less, measured (4.2.13.2 d, e; 4.2.11.2 g).
- [ ] Wire parts cite the detail specification they are procured to, and materials evidence comes from the manufacturer (ESCC 3901 4.4, 4.5).

## Drawings and lists
- [ ] Drawing: connectors, pins and signals match the unit documents.
- [ ] Wire list, pinouts and BOM agree with the drawing.
- [ ] Mass and length tables look plausible.
- [ ] Test tables list the limits your programme requires.

## Release
- [ ] The release comment says what this revision is for.
- [ ] After the release: exported again, drawings show *released*, the change log has the entry.
