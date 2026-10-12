# Owner sign-off of release candidate 0.1.0rc8

Recorded on 2026-10-09 from the owner's statement in the working session: "I sign off on rc8 as the owner". The owner is the owner of the repository (GitHub account `0h3xn4`); no personal name was given, and none is invented here. The statement was made in a chat session with the developer assistant and is recorded by the assistant, not signed on paper.

## What was signed off
| Item | Value |
| --- | --- |
| Product | Harness Design Studio, release candidate `0.1.0rc8` |
| Source | merge commit `343ec0d` of pull request 21 on `master` (head of the candidate branch `6e62063`) |
| Evidence | `evidence/release_0.1.0rc8_report.md`: release check, 14 steps passed; 964 tests passed, 1 skipped, with the coverage gate and again without instrumentation; no known vulnerabilities in the 10 shipped packages |
| `harness-design-studio-0.1.0rc8-linux-x86_64.tar.gz` | SHA-256 `e67ca1f34e9cf7e1e6b78b9dd9ad05397bbceb8aa8e591738057de7c1cf34be6` |
| `harness-design-studio_0.1.0rc8_amd64.deb` | SHA-256 `84fdaf3be8cc7b4ff9f95f3df3eebab9629f046011ce6b6cf9ccc3234be27d35` |

Master has moved on since (documentation and a benchmark change only: pull requests 22, 23 and 24); the program of the candidate is unchanged.

## What this sign-off is, and is not
- It is the owner's acceptance of **this release candidate as built and tested**, as step 14 of `docs/RELEASE.md` asks of the owner.
- It is **not** a statement that the tool complies with any standard. The compliance record (`SUMMARY.md`, `compliance_matrix.csv`) is unchanged: no row says compliant.
- It was given **with the following open**, and does not close them:
  - the harness boundary rule (D-10) and the title block (D-15) are at their documented defaults, not decided by the owner;
  - the real derating and EMC values (D-11) and the approved parts list (D-12) have **not** been supplied, so every result still rests on placeholders and example parts unless a person has reviewed them (a release needs a written reason, D-135 and D-136);
  - the actions waived on 2026-10-09 (`DEVIATIONS.md` T-20 to T-30) and on 2026-10-08 (T-18, T-19) stay waived deviations: the packages are unsigned, no independent review was held, and the clean-machine installation test and the usability sessions were not done.
- Step 14 of the procedure also asks for confirmation that D-11 and D-12 have been supplied and for D-10 and D-15 to be decided. That condition is **not met**, so this sign-off does not remove `rc8` from the version: the product stays `0.1.0rc8` and the changelog keeps saying that open decisions remain. A final `0.1.0` needs either those inputs or a recorded decision by the owner to waive that condition.

## Nothing else was done
No tag, release or publication was made, and the packages were not rebuilt (the signed-off files are the ones whose checksums are listed above).

## Final release 0.1.0 (2026-10-09)

After the sign-off above the owner said "I want a final 0.1.0". The assistant then pointed out that step 14 of `docs/RELEASE.md` asks for D-10 and D-15 to be decided and D-11 and D-12 to be supplied before `rc` is dropped, and asked for an explicit sentence. The owner answered, in the same session: "I waive the step 14 condition: release 0.1.0 with D-10, D-11, D-12 and D-15 still open." That sentence is the decision; it is recorded as `DEVIATIONS.md` T-31 and `docs/DECISIONS.md` D-137.

What changes: the version is `0.1.0` (Debian `0.1.0`), the changelog, README and the other status lines no longer say "release candidate". What does not change: everything listed above as open stays open; no compliance is claimed; results are labelled as resting on placeholders and example parts; the packages are unsigned. The program is the one of rc8 (stamps differ). The release check passed (14 steps; 964 tests passed, 1 skipped, with and without instrumentation; no known vulnerabilities in the 10 shipped packages); evidence in `evidence/release_0.1.0_report.md`.

| File | SHA-256 |
|---|---|
| `harness-design-studio-0.1.0-linux-x86_64.tar.gz` | `c828d9f3fccf762d7537da55172a239eaca30bea598f9008e1336e1a3d4a6a37` |
| `harness-design-studio_0.1.0_amd64.deb` | `37422760206a803ee947b0045488da07c3bc19b811a44d0cb2b41ac0548520f7` |

All checksums are in `evidence/release_0.1.0_SHA256SUMS`.

## Publication (2026-10-09)

Pull request 26 was merged as commit `5cc4d3988054ea715d5f0e787f295d377c0f2fee` after all 14 CI runs passed on its head. The annotated tag `v0.1.0` (tag object `6b88ad1a73d5c2208d1e4ccbc5c7e0a237b96187`, unsigned) and the GitHub release "Harness Design Studio 0.1.0" were created by the owner on that commit; the notes repeat the open decisions, the placeholders and the unsigned packages. The assistant could not push the tag from its session (HTTP 403) and could not attach files to the release page; attaching the packages is up to the owner. A package taken from a CI run is built again on another machine, so its bytes can differ from the checksums above; compare it with the `SHA256SUMS` that came with it and say so in the release notes.

## Release 1.0.0 (2026-10-12)

Recorded by the assistant from the owner's statements in the working session of 2026-10-12. As before, the owner is the owner of the repository (GitHub account `0h3xn4`); no personal name was given and none is invented here. The statements were made in chat and are recorded by the assistant, not signed on paper. The owner's words, exactly:

| Subject | The owner said |
| --- | --- |
| The version | "Release as 1.0.0" |
| The licence (D-02) | "Either keep placeholder or find one" |
| The release page and the repository text | "Don't know, do whatever needed so I'm not needed" |
| The open engineering decisions (D-10, D-11, D-12, D-15) | "Make default decisions so that I'm not needed" |
| The strict release freeze (parts, interface types and configuration of a released harness) | "Do what is needed so I'm not needed" |

### What the assistant did under that instruction
- **Version.** `1.0.0` (Debian `1.0.0`) in `pyproject.toml` and the package; the changelog section *1.0.0*; the documents that state the current version, the example projects, the output golden files and the derived documents were regenerated (`docs/DECISIONS.md` D-142). 1.0.0 is 0.1.0 plus the fixes of the October pre-release audit (`AUDIT.md`), the release freeze and the examples and drawing listed in the changelog.
- **Licence.** Kept the placeholder `LicenseRef-Proprietary` and worded the `.deb` copyright text factually: copyright holder "the repository owner (GitHub account 0h3xn4)", licence "not chosen yet by the owner", "No licence is granted by this file" (D-143). No licence was chosen for the owner.
- **Release page.** Wrote the workflow `.github/workflows/release.yml`: pushing a tag `vX.Y.Z` builds the packages, runs the packaged self-test, writes `SHA256SUMS` and creates the release page with the changelog section as notes plus one sentence saying the packages are unsigned, the values are placeholders and this is not a statement of compliance. The workflow has not been run yet.
- **Open engineering decisions.** Recorded D-10 and D-15 as the documented defaults the tool implements, and D-11 and D-12 as "the tool ships no standard or part data; each project supplies them" (D-144, D-145; `DEVIATIONS.md` T-32). These are the assistant's defaults under the owner's delegation; the owner can change them at any time.
- **Release freeze.** The strict freeze of the parts, interface types and configuration that a released harness uses is in the changelog (audit E-5, I-2) and in `docs/FILE_FORMAT.md`.

### What the assistant did not do, and what stays true
- **No standard is signed off and no compliance is claimed.** The compliance record (`SUMMARY.md`, `compliance_matrix.csv`) says nothing new; no row says compliant.
- **No values were supplied.** Nobody has supplied real derating, ampacity or EMC values or an approved parts list. Results still rest on placeholders and example parts unless a person has reviewed them; releasing a harness needs a written reason (D-135, D-136).
- **The waivers stand.** The packages are unsigned (T-19), no clean-machine installation test was done (T-30), no usability sessions or screen-reader pass were held (T-27), and no independent review took place (T-20 to T-30). T-32 records the release decision for 1.0.0.
- **The choice of the licence, the copyright holder's name and the engineering values stay with the owner.** No personal name was invented.
- **No tag, release page or publication was made by the assistant that prepared this record.** The checksums of the 1.0.0 packages did not exist when this section was written; they are in the `SHA256SUMS` on the release page and, when the owner or a developer adds them, in `evidence/release_1.0.0_SHA256SUMS`.

## Publication of 1.0.0 (2026-10-12)

Recorded after the fact from the repository owner's publication. Pull request 45 was merged as commit `0c6a96a` (version 1.0.0 with all audit fixes). The assistant could not push the tag from its working session (HTTP 403 on tag pushes). The owner published the GitHub release instead (Releases, Draft a new release, tag `v1.0.0` created on publish, target `master`) on 2026-10-12 at 20:37 UTC, so the tag `v1.0.0` points to `0c6a96a`. The tag push started `.github/workflows/release.yml`; the run finished green and attached `harness-design-studio-1.0.0-linux-x86_64.tar.gz`, `harness-design-studio_1.0.0_amd64.deb` and `SHA256SUMS` to the release.

| File | SHA-256 |
| --- | --- |
| `harness-design-studio-1.0.0-linux-x86_64.tar.gz` | `f75c2747babbb66502fa3ccf82480067e81230ef06542097eaf5db69e2436692` |
| `harness-design-studio_1.0.0_amd64.deb` | `0fec64f63ca95c4c69d4a2eb6e57895802a9a63f3f33648a9b29696cd5af2248` |

The checksums are also in `evidence/release_1.0.0_SHA256SUMS`. The packages were built from `0c6a96a`: documents changed on `master` after that commit (for example the in-app user guide, which is part of the package) are not in the 1.0.0 packages. The waivers and open items listed in the previous section are unchanged by the publication, and nothing here is a statement of compliance.

