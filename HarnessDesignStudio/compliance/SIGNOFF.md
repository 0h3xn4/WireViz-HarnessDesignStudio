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

## Publication of 1.1.0 (2026-10-18 and 2026-10-19)

Recorded from the GitHub release page and the workflow runs; nobody has signed off 1.1.0 as the owner (`docs/RELEASE.md` step 14), and nothing here is a statement of compliance. The tag `v1.1.0` points to `f998cd9` (pull request 62, version 1.1.0). The repository owner published the GitHub release on 2026-10-18 at 22:17 UTC. The first release run, started by the tag push, hung at the step that installs and runs the `.deb`: it ran the commands of the source install, which come first on the `PATH`, instead of the installed program, and the editor of the source install has no `--selftest` (corrected by pull request 65, which runs the installed program by its full path). The packages were attached on 2026-10-19 at about 07:16 UTC by a run of the corrected workflow started by hand with the tag `v1.1.0`; its checks passed. The packages are not signed. The text of the release page was written again on 2026-10-19 at 14:47 UTC by the "notes only" run, which changed nothing else.

| File | SHA-256 |
| --- | --- |
| `harness-design-studio-1.1.0-linux-x86_64.tar.gz` | `f0e686e8e9555822b3bea1f496ff5f5c1b3ae4106c1925139ab7a6957f47ff6b` |
| `harness-design-studio_1.1.0_amd64.deb` | `6583aef962db6b94cce79afd9c9b9c4b0079bffd6c1a13da9c9e7c4d522ff95b` |

The checksums are also in `evidence/release_1.1.0_SHA256SUMS` (the same bytes as the `SHA256SUMS` file on the release page, 218 bytes). The waivers and open items of the sections above are unchanged by the publication.

## Publication of 1.2.0 (2026-10-19)

Recorded from the GitHub release page and the workflow run. Pull request 69 (version 1.2.0: Windows and macOS packages, decision D-149) was merged as commit `1cdd6a7`. The assistant that prepared it could not push the tag from its working session (tag pushes are refused); the repository owner created the tag `v1.2.0` on that commit through the release page on 2026-10-19 at 15:57 UTC. The tag push started `.github/workflows/release.yml` (run 39281825970). The Linux, Windows and two macOS build jobs built the packages and ran their smoke tests on the finished files; the last job attached the six packages and one `SHA256SUMS` to the release page at 16:19 UTC. The packages are not signed or notarized: no certificate secrets exist, so the signing steps were skipped. Nobody has signed off 1.2.0 as the owner, and nothing here is a statement of compliance. Before the tag, the whole test suite had passed on Linux, Windows and macOS for pull request 69.

| File | SHA-256 |
| --- | --- |
| `harness-design-studio-1.2.0-linux-x86_64.tar.gz` | `3fe2c00052738d4a545f6d5a2a6d6138103a0f5a5b16c275c6f3f48e587317d7` |
| `harness-design-studio-1.2.0-macos-arm64.dmg` | `8558a47aef363d9d6590e86c7beca707760025213dfa74e64d412208b805ac38` |
| `harness-design-studio-1.2.0-macos-x86_64.dmg` | `ca2eeeb1e1294bc3ab74fb059618caf7ede2a75f4c1f83f157bbd91d26faa038` |
| `harness-design-studio-1.2.0-windows-x86_64-setup.exe` | `638e1b5da83691a124ba6614632dd448b87f0c976ffa8fecbadc7766f194954c` |
| `harness-design-studio-1.2.0-windows-x86_64.zip` | `21654feef2a9e2c7ac5cd0de0505bae754c859a33765d5ff77e2cc6e6e2fbefb` |
| `harness-design-studio_1.2.0_amd64.deb` | `fb402a9775c3723631bf14ca74c08fa3bfadd724247729c5789e5eb12e55add5` |

The checksums are also in `evidence/release_1.2.0_SHA256SUMS` (the same bytes as the `SHA256SUMS` file on the release page, 671 bytes). The packages were built by the workflow on GitHub's machines; they have not been installed on a clean machine without a network by a person (the waiver T-30 stands).


## Publication of 1.3.0 (2026-10-20)

Recorded from the GitHub release page and the workflow run. Version 1.3.0 is the new user interface (the UI overhaul, decisions D-150 to D-159, pull requests 72 to 81); the last of them, the final milestone (pull request 81), was merged as commit `e7cf531`. The assistant that prepared it could not push the tag from its working session (tag pushes are refused with HTTP 403, `docs/RELEASE.md` step 15); the repository owner created the tag `v1.3.0` on that commit through the release page on 2026-10-20 at 06:22 UTC. The tag push started `.github/workflows/release.yml` (run 39380004795). The Linux, Windows and two macOS build jobs built the packages and ran their smoke tests on the finished files; the last job attached the six packages and one `SHA256SUMS` to the release page at 06:27 UTC. The packages are not signed or notarized: no certificate secrets exist, so the signing steps were skipped. Nobody has signed off 1.3.0 as the owner, and nothing here is a statement of compliance. Before the tag, the whole test suite had passed on Linux, Windows and macOS for pull request 81 (one Windows run during the overhaul stopped once with the exit code 3221226505 in `test_gui_paint_crash` and passed on the second run; the cause of that single failure is not known).

What did not change: the design model, the file format, the 34 design rules, the command line and the generated files. All 567 files that the four packaged examples write are identical to those of 1.2.0 apart from the tool version they record (`tools/output_hashes.py`, `docs/ui/OUTPUT_HASHES_1.2.0.json`, `tests/test_output_hashes.py`). Not met: the target of 250 ms for a change of the interface size (it takes about 1.1 s; D-158, D-159, `docs/ui/PERF_BASELINE.md`).

| File | SHA-256 |
| --- | --- |
| `harness-design-studio-1.3.0-linux-x86_64.tar.gz` | `5c97954d84f31354d5350859e2464b8ba216e807856a56ed20ca0ec72937197a` |
| `harness-design-studio-1.3.0-macos-arm64.dmg` | `5a12500c028d621df1fb71764abff077c3b3a346b11bb87480086d1bbc3dafeb` |
| `harness-design-studio-1.3.0-macos-x86_64.dmg` | `5d7faad8d7b8c46e47d7c98b23925774306e75e4d452b64349b34131f1958bc0` |
| `harness-design-studio-1.3.0-windows-x86_64-setup.exe` | `95b779aef6762de3dc790c98fa7ea7281c2c4332d113eb8517432c549f1e9c4d` |
| `harness-design-studio-1.3.0-windows-x86_64.zip` | `9092290ead2faeff1aa14927c2f3be29b325bc3c06f8426491119c867126ce26` |
| `harness-design-studio_1.3.0_amd64.deb` | `7c630296ce00ee01493eeb4ec5277f3df1400bcac742f11735728cf912a2323f` |

The checksums are also in `evidence/release_1.3.0_SHA256SUMS` (the same bytes as the `SHA256SUMS` file on the release page, 671 bytes, SHA-256 `d79c61d547535f003c7b848ddefa4b366e972e4d990ad1543056e4a231c3d6e5`). The packages were built by the workflow on GitHub's machines; they have not been installed on a clean machine without a network by a person (the waiver T-30 stands), the screen-reader pass was not held (T-27), and no independent review took place (T-20 to T-30). The waivers and open items of the sections above are unchanged by the publication.


## Publication of 1.4.0 (2026-10-20)

Recorded from the GitHub release page and the workflow run. Version 1.4.0 answers the feedback of the AIT engineers (decisions D-160 to D-165, pull requests 83 to 88); the last of them, the version preparation (pull request 88), was merged as commit `1427aad`. The assistant that prepared it could not push the tag from its working session (tag pushes are refused with HTTP 403, `docs/RELEASE.md` step 15). A first release `v1.4.0` that the repository owner published at 11:57 UTC pointed at commit `cd7d750`, the master of before the merges (version 1.3.0 and none of the 1.4.0 changes); its workflow run failed at the check that the tag matches the version and nothing was attached. That release and its tag were deleted, and the owner created the tag `v1.4.0` again on `1427aad` through the release page on 2026-10-20 at 12:27 UTC. The tag push started `.github/workflows/release.yml` (run 39422417101). The Linux, Windows and two macOS build jobs built the packages and ran their smoke tests on the finished files; the last job wrote one `SHA256SUMS`, the notes, and attached the six packages to the release page.

What did not change for existing work: the file format (schema version 1; every new field is optional and not written while it has its default value) and the generated files. All 567 files that the four packaged examples write are identical to those of 1.2.0 apart from the tool version they record (`tools/output_hashes.py`, `docs/ui/OUTPUT_HASHES_1.2.0.json`, `tests/test_output_hashes.py`). New: 35 design rules (one more), the commands `export-devices` and `import-devices`, and the optional fields described in `docs/FILE_FORMAT.md`.

| File | SHA-256 |
| --- | --- |
| `harness-design-studio-1.4.0-linux-x86_64.tar.gz` | `ee1313664ea3d0c325433d4c0fcbdbd1f2d089238821a07b37bbc133b6b23eeb` |
| `harness-design-studio-1.4.0-macos-arm64.dmg` | `798f74b2cfb677145627c335d36f569facbda7c15cd62a0b0d0a9ee08c1e85ad` |
| `harness-design-studio-1.4.0-macos-x86_64.dmg` | `63fb2057fbb15c08122d6322a94549abb33f6345be929362db15bd046f96864c` |
| `harness-design-studio-1.4.0-windows-x86_64-setup.exe` | `069aaddc26b736f17956c22c4011251062bdbfe79c5ce310dd2eca6669b5a7df` |
| `harness-design-studio-1.4.0-windows-x86_64.zip` | `b5f8caef559a45c41c70107aad691d45cab1ffdd57fd938068f7b13e67324b52` |
| `harness-design-studio_1.4.0_amd64.deb` | `e4454d4801bb4b39ef90095efaca4164074c4158716909be1bffe84b135e1136` |

The checksums are also in `evidence/release_1.4.0_SHA256SUMS` (the same bytes as the `SHA256SUMS` file on the release page, 671 bytes, SHA-256 `985bb580e94665aca097913dbefd0339e4d043c9960a40d5ae34dbb5fe5d2870`). The packages were built by the workflow on GitHub's machines; they have not been installed on a clean machine without a network by a person (the waiver T-30 stands), the screen-reader pass was not held (T-27), and no independent review took place (T-20 to T-30). The waivers and open items of the sections above are unchanged by the publication. Open for the AIT engineers to say: what soldering needs beyond the termination column of the pinout lists.


## Publication of 1.5.0 (2026-10-21)

Recorded from the GitHub release page and the workflow runs. Version 1.5.0 answers a second request of the AIT engineers, to create a project completely from scratch (a harness made by hand, D-166), and makes the packages say in plain words what a Linux machine lacks while CI proves that no package needs a Python on the machine (D-167); its pull requests are 91 to 93. The assistant that prepared it could not push the tag from its working session (tag pushes are refused with HTTP 403, `docs/RELEASE.md` step 15). The first release `v1.5.0`, which the repository owner created on commit `714d6d4` (the version preparation, pull request 93), failed in its workflow run 39568790457: both macOS smoke tests failed, not the packages. The test code added in pull request 92 removed `/usr/bin` from the environment of the packaged program (so the launcher script of the macOS app lost `dirname`) and did not know that the files of an app sit in `Contents/MacOS`, `Frameworks` and `Resources`; the release step was skipped and nothing was attached. Pull request 94 (commit `4365368`) fixed the test code, and the three platform builds were run again on a branch `pkg/smoke-macos-1.5.0` before it was merged. The owner then deleted that release and its tag and created the tag `v1.5.0` again on `4365368` through the release page on 2026-10-21 at 11:10 UTC. The tag push started `.github/workflows/release.yml` (run 39589971255). The Linux, Windows and two macOS build jobs built the packages and ran their smoke tests on the finished files; in the first attempt the upload of the Intel macOS package to GitHub's artifact store timed out five times (a failure of the GitHub service after the build and its smoke test had passed), so the release step was skipped; the failed jobs were run again once, and the last job wrote one `SHA256SUMS`, the notes, and attached the six packages to the release page at 11:43 UTC.

What did not change for existing work: the file format (schema version 1; no new field) and the generated files. All 567 files that the four packaged examples write are identical to those of 1.2.0 apart from the tool version they record (`tools/output_hashes.py`, `docs/ui/OUTPUT_HASHES_1.2.0.json`, `tests/test_output_hashes.py`). New: a harness made by hand (*New harness*, the *Connectors* tab, `core/manual_harness.py`), the start check of the Linux editor (`harness-design-studio-gui --check-system`), and the smoke tests of the packages without any Python in the environment.

| File | SHA-256 |
| --- | --- |
| `harness-design-studio-1.5.0-linux-x86_64.tar.gz` | `6eb5dd90b4aba3568d7360a1b3b46c3c86fdb7b1076679dea0316dd77369eb94` |
| `harness-design-studio-1.5.0-macos-arm64.dmg` | `c94f9962c80b5a191b7c38d276df2d320bdbadf939cf6e347c9c61c0756bda52` |
| `harness-design-studio-1.5.0-macos-x86_64.dmg` | `a4f5efb3c97bcb50c2c28e0896b282a180bf4a3a3b85a89d49cac86a41125e9d` |
| `harness-design-studio-1.5.0-windows-x86_64-setup.exe` | `bac9edef66c8a4fa33a2de83ede38d636c999e883c04d05ea4460a74a4f2081c` |
| `harness-design-studio-1.5.0-windows-x86_64.zip` | `32ab83c5bedc5a491381b54196fd0f937dae62fe9535439676236fee0be1f55b` |
| `harness-design-studio_1.5.0_amd64.deb` | `a08825b588c06a21f42b3734480b1dc4517131ec3d4a32f84e1c4bebb88806ce` |

The checksums are also in `evidence/release_1.5.0_SHA256SUMS` (the same bytes as the `SHA256SUMS` file on the release page, 671 bytes, SHA-256 `4142de336c962c640770e5c04696f1a4f129f2ddc1aa56829ba42a70ac794e10`). The packages were built by the workflow on GitHub's machines; they have not been installed on a clean machine without a network by a person (the waiver T-30 stands), the screen-reader pass was not held (T-27), and no independent review took place (T-20 to T-30). The waivers and open items of the sections above are unchanged by the publication. Open for the AIT engineers to say: what soldering needs beyond the termination column of the pinout lists. Not built: a command line equivalent of *New harness*.
