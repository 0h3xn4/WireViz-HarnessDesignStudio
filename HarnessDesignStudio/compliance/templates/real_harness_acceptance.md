# Acceptance of the outputs for a real harness

For action A-13 (VAL-08; ECSS-Q-ST-80C 6.3.7). The owner takes a real design through the tool and decides whether the outputs can be used. The tool does not decide this, and a passing run of its own checks is not an acceptance.

## 1. Identification
- Project (folder, project name):
- Harness(es) and revision accepted (IDs):
- Tool version (`harness --version`), model hash (in `outputs/manifest.json` and `system/provenance.json`):
- Date, and who performed the review:
- Is this a design with real program data? (yes / no) If yes, where the data came from: ICD, netlist (`import-netlist`), parts list (`import-parts`), lengths (`import-lengths`):

## 2. Preconditions (stop here if any is "no")
| Question | Yes / no | Note |
| --- | --- | --- |
| The config files that matter for this design are real values, not placeholders (`harness config DIR`; derating, EMC, release rules) | | |
| The parts used are approved parts from the parts list the program uses (D-12), not the example parts (`unverified`) | | |
| The library record names its source and date (`harness library DIR`) | | |
| `harness verify DIR --outputs` is clean, and the design rule report lists what it did not check | | |
| The set of outputs was exported from this model hash (no "out of date" message) | | |

If a precondition is "no", the outputs can still be looked at, but this acceptance can only say "accepted for review", not "accepted for manufacture".

## 3. Check the outputs against the real design
For each file, compare with the source of truth (the design, the ICD, the datasheets). Sample at least the fraction stated in the last column; for a first real harness, check all of it.

| Output | What to check | Against | Sample | Result (ok / finding) |
| --- | --- | --- | --- | --- |
| `wirelist.csv` | each wire: both ends, signal, gauge, colour, length | ICD or netlist | all | |
| `pinouts.csv`, `box_pinouts.csv` | every pin: wire or spare, signal | connector drawings, ICD | all | |
| Drawing (`drawing_A3.pdf`, A4) | the same connections as the wire list; title block (project, revision, status, sheet n / N); legible when printed in greyscale | wire list, a printout | every sheet | |
| `bom.csv` | part numbers, quantities, metres of wire, wires without length, approval status | parts list | all | |
| `mass_length.csv` | lengths and mass; what it says is missing | measured or CAD lengths, datasheet masses | all | |
| `tests.csv` | one continuity test per wire, isolation tests, limits (limits read "TBD" until set) | the test procedure of the AIT team | all | |
| `labels.csv` | text of each label (connector, wire ends) | the labelling rules of the program | sample | |
| `mating_matrix.csv` | box connector to cable connector | mechanical drawing | all | |
| `drc_report.md`, `drc_findings.csv` | each finding understood; each waiver has a reason; the *not checked* list read | design review | all | |
| `traceability.csv` | interface to harness to wires | ICD | sample | |
| `system/block_diagram`, `harness_overview` | units, zones, harnesses | system design | all | |
| `provenance.json`, stamps | version, model hash, library, settings with placeholder flags | the above | once | |

## 4. Things the outputs cannot tell you
Wire surface temperature under load, the partial-load factor, bundle spacing, multipactor and bond resistances (deviations T-14 to T-16), harness routing geometry (the drawing is not to scale), and anything the design rule report lists as *not checked*. Record here who covers each, and where:

## 5. Findings
| # | Output and item | Finding | Severity (1 to 4, `PROBLEM_REPORTING.md`) | Problem report (issue number) |
| --- | --- | --- | --- | --- |
| 1 | | | | |

A wrong output that could reach a harness unnoticed (severity 1) means: stop, report, and re-check every harness made with that version.

## 6. Decision (owner)
- [ ] Accepted for manufacture
- [ ] Accepted for review only (a precondition in section 2 was "no")
- [ ] Not accepted; findings above

Name, signature, date:

After the decision: enter it in `compliance/docs/SValP_SVS.md` (VAL-08) and `compliance/OPEN_ACTIONS.md` (A-13).
