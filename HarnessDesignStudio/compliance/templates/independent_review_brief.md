# Brief for the independent verifier and validator

For action A-01 (ECSS-E-ST-40C 5.6.2, 5.8.2; ECSS-Q-ST-80C 6.3.5.19). Fill in the first block, then send this file with the material below. The reviewer answers on `review_record.md`.

- Reviewer (name, organisation):
- Date of the review, and the tag or commit reviewed (`review-<name>`):
- Version reviewed (`harness --version`) and model hash of the sample project, if used:

## Independence
The reviewer must not have written the design, the code or the tests of the tool (ECSS-E-ST-40C 5.8.2; the developer assistant wrote the code and the first versions of the documents; the owner reviewed diffs). The reviewer states here that this is true, and names any earlier involvement:

Statement of independence and date:

## What is claimed, and what is not
- The tool is **ground engineering software of criticality category C** (approved by the owner, `compliance/docs/CRITICALITY.md`).
- The documents in `compliance/` say, per requirement, *partial*, *gap*, *human* or *not applicable*. **No document says "compliant"**; compliance is a decision of the owner after review. If you find a sentence that reads as a claim of compliance, record it as a finding.
- The tool never claims that a harness design is compliant; it reports which rules it checked and which it could not.
- Values from the standards are optional profiles and are still placeholders in every project until an engineer has reviewed the config (`docs/CONFIG.md`, `DEVIATIONS.md` T-13).

## Read, in this order
1. `compliance/SUMMARY.md`: what was done and what is open.
2. `compliance/DEVIATIONS.md` and `compliance/OPEN_ACTIONS.md`: tailoring, waivers, and what only people can do. Check that each waiver or approval names who gave it and when.
3. `docs/SPEC.md` and `docs/REQUIREMENTS.md`: what the owner asked for.
4. `compliance/traceability.csv` and `compliance/sdd_components.csv`: requirement to test, requirement to component.
5. `compliance/docs/SVerP.md`, `SVR.md`, `SValP_SVS.md`, `SUITP.md`: how verification and validation were planned, and what the developer reports.
6. `compliance/gap_analysis.md` and `compliance/compliance_matrix.csv`: the assessment against ECSS-E-ST-40C, ECSS-Q-ST-80C, ECSS-Q-ST-30-11C, ECSS-E-ST-20-07C and ESCC 3901. The requirement texts are abbreviated; the standard is authoritative.
7. `compliance/evidence/` and `compliance/metrics.json`: test results, release report, coverage.
8. `docs/RELEASE.md` and `docs/SECURITY.md`.

## Do yourself, do not take on trust
1. Install from the package or the source (`docs/INSTALL.md`) and run the tests (`pytest`; with `--cov` for the coverage gate). Compare the counts with the release report in `compliance/evidence/`.
2. Pick **ten requirements** at random from `compliance/traceability.csv`. For each: open the named test, confirm it really checks the requirement (not just that it passes), and break the code on purpose to see it fail.
3. Pick **ten rows** of `compliance/compliance_matrix.csv` with status *partial*. Read the cited evidence. Does it support "partial"? Would a stricter reader say *gap*?
4. Take a small harness (`harness new` from an example), generate, verify and export it. Check three pins, three wire lengths and one mass by hand against the outputs.
5. Check that a rule silent without its number says so (`unchecked-config` in the design rule report).
6. Check the release gate: change a released harness and see that the tool refuses.
7. Read one of the four standards' clauses that the assessment marks *human* and judge the reason.

## What to record
On `review_record.md`: each finding as a RID (blocking, major or minor), the requirement or document it concerns, and your proposed action. Also record: what you could not check and why; whether you consider verification (are we building it right) and validation (is it the right tool for the stated need) independently done for the parts you examined, and for which parts not.

## Out of scope
Whether a particular harness design is right (that is the design review of the project), ESCC part approval, and the choice of the software category (given by the owner).
