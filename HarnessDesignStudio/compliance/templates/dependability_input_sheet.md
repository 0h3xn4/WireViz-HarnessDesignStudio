# Input sheet for the software dependability and safety analysis (A-07)

For ECSS-Q-ST-80C 6.2.2.2 to 6.2.2.9. The analysis itself is a task of the owner's safety side: it needs the severity categories of ECSS-Q-ST-30 and the rules of ECSS-Q-ST-40, which were not supplied (A-18), and it must be done by a person. This sheet gives that person the facts about the software so the analysis does not start from nothing.

**Status of every cell: proposed by the developer assistant, not judged by a safety engineer.** The failure modes below are the ones the developer could think of from the code; a person must add the ones that were not thought of. No severity or probability is entered: those belong to the analysis.

## 1. System context
The tool is ground engineering software (category C, `compliance/docs/CRITICALITY.md`). It does not act on flight hardware. A fault matters when a wrong or incomplete output is built into a harness: the harness definition (wire lists, pinouts, drawings, labels, test tables) is what the manufacturer builds from. Compensating provisions claimed by the owner's category choice: the independent verifiers inside the tool, the human design review and release of each harness, and the inspection and electrical test of the manufactured harness.

## 2. Failure modes per component
Columns: **Failure mode** (what the software does wrong); **Effect on the harness** (what follows if nothing catches it); **Prevented or detected by** (what exists today, with the test that exercises it); **Residual** (what is not covered).

| Component | Failure mode | Effect on the harness | Prevented or detected by | Residual |
| --- | --- | --- | --- | --- |
| `core/generate`, `core/verify.py` | A wire joins the wrong pin, or a connection is missing, duplicated or on a pin that is not free | Wrong continuity on the built harness; possible short between power and return | The independent verifier re-derives the connections without the generator's code (`tests/test_generate.py`, `tests/test_generate_parts.py`); the electrical test table checks each wire; the human design review | The verifier's independence is kept by review only, not by a test (`CRITICALITY.md` section 3) |
| `core/generate/sizing.py` | A gauge is too small for the current, or a derating factor is applied wrongly | Overheated wire | Rules in the design rule check read the same numbers independently (`tests/test_drc.py`, `tests/test_standard_rules.py`); a rule without its number says "not checked" | The numbers themselves are placeholders until the owner supplies them (D-11); the surface temperature is not computed (T-15) |
| `core/drc` | A rule misses a violation, or a waiver hides one | A design error reaches the outputs without a warning | Every rule has a positive case and stays quiet on a clean project (`tests/test_drc.py`); waivers need a written reason and are listed in the report | A rule that was never written; rules that depend on analyses outside the tool (listed under *not checked*) |
| `core/outputs` and `core/outputs/verify.py` | A file differs from the model: a wire missing from the list, a wrong label, a stale file | The manufacturer builds from a wrong document | The output verifier re-reads the files and compares with the model, with a mutation test for each check (`tests/test_outputs.py`); every file carries the model hash; stale outputs are detected | Layout of the drawing (it is a diagram, not to scale) is checked only by golden files and by eye |
| `core/vcs` (release, baselines, locks) | A released harness is changed silently, or a release is recorded for a design that was not checked | The built harness does not match the released revision | Locks are enforced in the transaction layer; release plans are run through the same layer (`tests/test_change_control.py`) | A release succeeds while config files are placeholders or parts are unapproved (open owner question) |
| `core/io`, `core/model`, `core/commands.py` | A project file is corrupt, partly lost on save, or read wrongly | Silent loss of design data | Atomic saves, backups and file locks (`tests/test_atomic_lock.py`); strict model with integrity checks on load, save and every transaction (`tests/test_integrity.py`); recovery mode that drops nothing silently (`tests/test_recovery.py`); fuzzing and soak tests (`tests/test_fuzz.py`, `tests/test_soak.py`) | Failures of the disk or the file system below the tool |
| `core/imports.py`, `core/kicad.py`, `core/library_import.py` | An import reads a value wrongly (a unit, a pin, a part) | Wrong design data from the start | Imports are previewed, one undo reverts them, errors name file, line and column; the verifiers check the result (`tests/test_imports.py`, `tests/test_kicad.py`) | The source data (netlist, parts list) are taken as given |
| `core/migrate` | A migration changes data on opening an older project | Silent change of an old design | Lossless migrations keep the original files (`tests/test_migrate.py`) | A downgrade is not possible (D-133) |
| `gui` | The editor shows a state different from the model, or an edit is applied wrongly | The user decides on wrong information | Every change goes through the transaction layer; the controller shows deltas of the model, not its own state (journey tests: `tests/test_gui_journeys.py`) | Display faults in the canvas; accessibility pass not done (A-12) |
| Packaging and installation (`tools/build_deb.py`, `packaging/`) | The delivered program differs from the tested one | Unknown behaviour | Checksums of the deliverables, reproducible wheel, self-test of the installed package, SBOM (`../../docs/RELEASE.md`) | Packages are not signed (D-19, A-08) |
| Dependencies (PySide6, pydantic, openpyxl and others) | A library has a defect or a vulnerability | Any of the above | Pinned versions, SBOM, licence check at each release | No automatic vulnerability watch (A-08) |

## 3. Failure propagation (6.2.2.10)
The question the analysis must answer: can a fault in a D component (GUI, examples, tools) cause a C component to fail? The developer's argument is that the GUI changes the project only through the transaction layer, which runs the integrity check, and that the verifiers do not trust the GUI. This is an argument, not a proof; the safety engineer should try to break it (for example by looking for a path that writes project files without the transaction layer).

## 4. What the analysis should decide
1. The severity of each failure effect, using the categories of ECSS-Q-ST-30.
2. Whether category C stays right for the whole tool, or whether any component needs B (the choice was made without ECSS-Q-ST-30; `PHASE0.md`).
3. Which failure modes need a further measure (for example a second independent verifier, a test, a restriction in the release gate).
4. The result, with the name of the person and the date, entered in `CRITICALITY.md` section 4.

## 5. Questions the developer cannot answer
- Is a wrong gauge or a missing wire the worst credible effect, or can a fault in the tool contribute to something worse?
- Which of the tool's outputs are checked again by someone else before manufacture in the owner's programme (the compensating provision depends on it)?
- Is the harness test (continuity and isolation) always performed on the finished harness?
