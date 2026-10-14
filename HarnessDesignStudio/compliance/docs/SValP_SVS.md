# Software validation plan and specification (SValP, SVS)

DRDs: ECSS-E-ST-40C Annex J and Annex L, combined because the project is small. Status: draft, not reviewed.

## 1 to 3. Introduction, references, terms, 4. overview
See `SDP.md`, `SRS.md`.

## SValP 4 to 9
- **Planning:** validation shows that the tool does what the owner needs (`../../docs/SPEC.md`). Organization: the owner or a person nominated by the owner validates; the developer assistant prepares the material. Independence: the person who validates must not have written the design (ECSS-Q-ST-80C 6.3.5.19, action A-01).
- **Tasks and approach:** (1) run the validation tests below on the packaged program on a clean Ubuntu 24.04 machine without network (`../../docs/RELEASE.md` step 12); (2) usability sessions with representative users (`../../docs/usability/README.md`, SUS score and task success); (3) run the tutorial `../../docs/GETTING_STARTED.md` word for word; (4) design review of a real project using the review checklist.
- **Testing facilities:** Ubuntu 24.04 VM, the `.deb` and the `.tar.gz`.
- **Control procedures:** SPRs (`PROBLEM_REPORTING.md`).
- **System level:** the owner's own acceptance of the generated documents for a real harness; not testable by the developer.

## SVS 5 to 11: validation test cases
| ID | Case | Input | Expected result | Pass/fail |
| --- | --- | --- | --- | --- |
| VAL-01 | Offline operation | start the packaged program with networking disabled; run `--selftest` | prints `selftest ok` | `../../docs/RELEASE.md` step 12 |
| VAL-02 | Tutorial | the commands of `GETTING_STARTED.md` on `first-steps` | outputs and model hash as quoted | `tests/test_docs.py` runs it |
| VAL-03 | Generation | `small-satellite` example | no verifier error; 2nd generation empty | `tests/test_generate.py` |
| VAL-04 | Release gate | release a harness with an undecided gauge | refused with reasons | `tests/test_change_control.py` |
| VAL-05 | Rule check silence | default project with a current but no derating values | report says *not checked* | `tests/test_drc.py` |
| VAL-06 | Standard profile | `harness config DIR --apply-profile ecss-q-st-30-11c` | unset values filled, cited, placeholder kept | `tests/test_profiles.py` |
| VAL-07 | Usability | five users, ten tasks | SUS and success per `docs/usability` | **not done** (action A-12; material: `docs/usability/`) |
| VAL-08 | Real harness | owner's real design | outputs accepted by the owner | **not done** (action A-13; checklist: `compliance/templates/real_harness_acceptance.md`) |

Items that cannot be validated by test: VAL-07, VAL-08 and the correctness of the engineering values, which belong to the owner (D-10, D-11, D-12). Test platform: as above.
