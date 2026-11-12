# Final report: legal protection, phases 1 and 2

Date: 2026-11-10. Written by an AI (Claude, through Claude Code) for the project owner. This is not legal advice. There is no website: the owner discarded the website plan (phases 3 and 4) on 2026-11-10, after the design study and a first build. Nothing of it is in the repository, and nothing was published (D-217).

## 1. What changed

All changes are in one pull request, merged into `master` on 2026-11-10 after you allowed the merge:
[#200](https://github.com/0h3xn4/WireViz-HarnessDesignStudio/pull/200) (commit `0cc3cc4c`; 847 files, most of them one header line). Decisions D-205 to D-216 in `docs/DECISIONS.md`. Master took D-203 and D-204 for other work while this one was open, so the decisions of this work were renumbered.

| Area | What is now true |
|---|---|
| Licence (L-1) | `HarnessDesignStudio/` is GPL-3.0-only. `LICENSE`, `NOTICE`, an SPDX header in every source file, `REUSE.toml` for the other files, `reuse lint` in CI, the licence text in the About dialog and in the package metadata. |
| One text (rule 6) | Every legal text is written once, in `compliance/legal/texts.md`, and copied word for word to READMEs, About dialog, first-start notice, packages and release pages. A test fails when a copy drifts. Another test fails on promise words. "Clean-room" is retired (D-211). |
| Free and without data (L-2, L-3) | D-206 and D-207. The privacy statement says the app sends nothing and collects no personal data. |
| Contributions (L-4) | `CONTRIBUTING.md`, pull request template and a CI check for the sign-off line and a noreply author address (DCO). |
| Notices in written files | Every file the tool writes carries the notice. This changes the files once, on purpose; the reference outputs and the output baseline were written again (D-214). "Independent check" is now "self-check" (D-215). |
| Third parties | Inventory, SBOM and notices are made from the built package, for Linux and Windows, and are inside every package. CI compares the package with the committed inventory and checks the licences against an allow-list. A tool fetches the source of the LGPL and GPL parts (Qt for Python, Qt, Ubuntu libraries). |
| Supply chain | All actions are pinned to commits. Workflows have the least permissions. New workflow `harness-legal.yml` (REUSE, commit check, pip-audit, dependency review, CodeQL). The release workflow signs with Sigstore (no key) and adds build attestations. `SECURITY.md`, `SUPPORT.md`, issue templates. |
| Records | The audit, the risk register (33 risks), this checklist of owner items, 14 questions for a lawyer, two annexes and a release record template, all in `compliance/legal/`. |

Not changed, by the rules of the brief: no release, tag, release asset or history; no repository setting; nothing in `src/wireviz`, `docs/`, `examples/` or `tutorial/`.

## 2. What was checked, and how

| Check | Result |
|---|---|
| Full test suite, Python 3.14, 6595 tests | passed (6 skipped: tests that need a non-root user, or the real-platform lane) |
| `ruff format`, `ruff check`, `mypy` (666 files) | clean |
| `reuse lint` (1773 files) | clean |
| Drift test of the legal texts, promise-word test, WireViz independence test | passed |
| Output hashes against the new baseline | passed (outputs differ from before only by the added notices) |
| CI on the pull request: `test` on Ubuntu and Windows, packaging on Linux and Windows, real-platform lanes (xcb at two scales, Windows), `reuse`, `commits`, `pip-audit`, CodeQL analysis | all green |
| Scans for personal data in the files and the history | done by pattern search; results in `legal-audit.md`, area 6 and 7 |

## 3. What could not be checked

- **The release workflow.** The signing, the attestation and the source-fetch steps have never run. The first release made with them is their first test (F1). *Update of 2026-11-11:* they ran to the end in the release candidate 1.17.1rc2, published as a pre-release (tag `v1.17.1rc2` on `7fae805`, release workflow run 43067874134, second attempt). Still open: one download verified with `cosign` and the attestation, as `docs/INSTALL.md` says, and the full release later. *Later on 2026-11-11:* the full release 1.17.1 is prepared (D-225); the owner decided to skip the check from outside the workflow, so it was not done. *Later still on 2026-11-11:* 1.17.1 is published as the latest full release (lightweight tag `v1.17.1` on `cb72a3c`, release workflow run 43117202544, first attempt); every job passed, with the signing, the attestation and the source step (`compliance/SIGNOFF.md`, *Publication of 1.17.1*). *Update of 2026-11-12:* the release candidate 2.0.0rc1 is published as a pre-release (annotated tag `v2.0.0rc1` on `8d1c268`, made by the tag workflow of D-227; release workflow run 43175697733, first attempt); every job passed again, with the signing, the attestation and the source step, and 1.17.1 stays the latest full release (`compliance/SIGNOFF.md`, *Publication of 2.0.0rc1*). *Later on 2026-11-12:* the full release 2.0.0 is prepared (D-230; not tagged yet), the program of 2.0.0rc1 with the fixes of its end-to-end test (pull request 226).
- **The Windows packages.** The Windows inventory comes from the published 1.17.0 zip with the network stripping of #204 applied by the same tool. Nobody built a Windows package with the new build. The Windows build hooks ran only through the inventory tool.
- **The CodeQL alert check.** It is red on the pull request: 100 alerts, 20 of them errors. The pull request touched every file (the headers), so old alerts count as new. I fixed the three in new code. I cannot read the list from here. Read it in the Security tab and tell me which to fix (F12). Merge was not blocked by it, as agreed.
- **Dependency review.** It is skipped until the Dependency graph setting is on (C, F10).
- **Secrets scan.** I could not run gitleaks; the command is in D1.
- **Registers.** I could not reach trademark registers (D2).
- **Real screens.** No person looked at the new first-start notice on a real display; the tests run offscreen and on the real-platform lanes.

## 4. Decisions

**Answered by the owner on 2026-11-10** (recorded as D-218): the country is **Germany** (A1); no one else has a claim on the tool and D-186 is read in the legally safest way, private use by the owner alone (A2, A3); tag `v1.15.0` was made by the owner (A4); the 20 existing releases follow **option (b)**, a new release with a superseded note, and no old release is edited (B1); the history is **accepted as it is, no rewrite**, and future commits use the noreply address (B2); Dependency graph and private vulnerability reporting are to be switched on, by the owner, because no tool of the assistant changes a setting (C); the first signed release is a **release candidate** (F1).

**Still needed from you** (the full list, with a reason for each, is in [`owner-checklist.md`](owner-checklist.md), F15):

1. **Settings** (section 5): Dependency graph, the variable `DEPENDENCY_GRAPH`, private vulnerability reporting, and the noreply address on your computers (B2).
2. **Workshop people, other Studio projects, example data** (A5 to A7).
3. **Upstream files** changed against your decision (B3), **data that may not be public** (B4), **names and trademarks** (B5), **what the app records about people** (B6, F5), **export control** (B7), **a lawyer** (B8). For a lawyer, Q-14 now holds the German-law questions.

## 5. Settings you must change (I cannot change them)

From section C of the checklist: turn on the Dependency graph and set the repository variable `DEPENDENCY_GRAPH`, so that dependency review runs; turn on private vulnerability reporting (for `SECURITY.md`); check the Actions settings (F3, disable `main.yml` if you do not need it); branch protection and the required checks; GitHub Pages only when you approve the website.

## 6. Residual risk

The register has 33 risks. After this work: 4 closed, 6 mitigated, 8 partly done or implemented but untested, and 15 that wait for a decision or are open. Likelihood and impact are not lowered, because a measure that is not yet tested or decided does not remove the risk.

The risks that stay high until you act:

- Ownership and third-party claims (LR-02, LR-03, LR-26): only you can answer.
- Personal data in history (LR-08) and in unreviewed images and text (LR-09, LR-31).
- Old releases without a licence, notices or signatures (LR-27, LR-28). They stay public.
- Names and trademarks (LR-19, LR-24).
- Export control and product-liability rules for a tool used in spacecraft work (LR-12, LR-13). I make no judgement on either.

Questions for a lawyer are in [`lawyer-questions.md`](lawyer-questions.md), Q-1 to Q-14. Start with Q-1 (copyright in AI-written code), Q-4 and Q-7 (liability and the intended-use text), Q-5 (country and website), Q-11 (third-party text and runtime DLLs).

## 7. What I did after the owner's instruction "continue as per your recommendation"

Recorded in D-216 so that you can undo each one: the choices are in section F of the checklist (F1 to F13). Two items changed after the merge of #204 (offline evidence kit), which now strips network-related libraries from the package:

- **F7** is partly solved by #204: the Qt network library and the Kerberos libraries are no longer in the Linux package.
- **F13**: the committed inventory is the published 1.17.0 package with that stripping applied. For every release, make the inventory again from the package the release workflow built.

## 8. Next step

None from me. The website plan is discarded (D-217): no site folder, no Pages workflow, no site tests. The Pages items in section C of the checklist need no action. If you want a site later, the brief's phase 3 is the start; the legal texts, the privacy statement of the app and the screenshot tool `tools/gui_screenshots.py` already exist.
