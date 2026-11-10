# Final report: legal protection, phases 1 and 2

Date: 2026-11-10. Written by an AI (Claude, through Claude Code) for the project owner. This is not legal advice. The website (phases 3 and 4) is not part of this report: it waits for your OK on the design plan.

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
| Records | The audit, the risk register (33 risks), this checklist of owner items, 13 questions for a lawyer, two annexes and a release record template, all in `compliance/legal/`. |

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

- **The release workflow.** The signing, the attestation and the source-fetch steps have never run. The first release made with them is their first test (F1).
- **The Windows packages.** The Windows inventory comes from the published 1.17.0 zip with the network stripping of #204 applied by the same tool. Nobody built a Windows package with the new build. The Windows build hooks ran only through the inventory tool.
- **The CodeQL alert check.** It is red on the pull request: 100 alerts, 20 of them errors. The pull request touched every file (the headers), so old alerts count as new. I fixed the three in new code. I cannot read the list from here. Read it in the Security tab and tell me which to fix (F12). Merge was not blocked by it, as agreed.
- **Dependency review.** It is skipped until the Dependency graph setting is on (C, F10).
- **Secrets scan.** I could not run gitleaks; the command is in D1.
- **Registers.** I could not reach trademark registers (D2).
- **Real screens.** No person looked at the new first-start notice on a real display; the tests run offscreen and on the real-platform lanes.

## 4. Decisions still needed from you

The full list, with a reason for each, is in [`owner-checklist.md`](owner-checklist.md). The ones that matter most:

1. **Country** (A1). It decides the privacy notice and whether an imprint is needed. It blocks the website text.
2. **The meaning of D-186 and the claims of others** (A2 to A6): who "used internally" meant, employer or client claims, the workshop people, the other "Studio" projects. The GPL grant depends on your answer.
3. **Tag `v1.15.0`** was made by another person (A4).
4. **The 20 existing releases** (B1). My recommendation: one new release with every fix, and a "superseded" note in its text. I did not touch any release.
5. **History** (B2): a mailbox address on 98 commits. A rewrite breaks 20 release tags and links; I do not start without your OK.
6. **Upstream files** changed against your decision (B3), **data that may not be public** (B4), **names and trademarks** (B5), **what the app records about people** (B6, F5), **export control** (B7), **a lawyer** (B8).
7. **The first signed release** (F1). I recommend a release candidate tag first.

## 5. Settings you must change (I do not change them)

From section C of the checklist: turn on the Dependency graph and set the repository variable `DEPENDENCY_GRAPH`, so that dependency review runs; turn on private vulnerability reporting (for `SECURITY.md`); check the Actions settings (F3, disable `main.yml` if you do not need it); branch protection and the required checks; GitHub Pages only when you approve the website.

## 6. Residual risk

The register has 33 risks. After this work: 4 closed, 6 mitigated, 8 partly done or implemented but untested, and 15 that wait for a decision or are open. Likelihood and impact are not lowered, because a measure that is not yet tested or decided does not remove the risk.

The risks that stay high until you act:

- Ownership and third-party claims (LR-02, LR-03, LR-26): only you can answer.
- Personal data in history (LR-08) and in unreviewed images and text (LR-09, LR-31).
- Old releases without a licence, notices or signatures (LR-27, LR-28). They stay public.
- Names and trademarks (LR-19, LR-24).
- Export control and product-liability rules for a tool used in spacecraft work (LR-12, LR-13). I make no judgement on either.

Questions for a lawyer are in [`lawyer-questions.md`](lawyer-questions.md), Q-1 to Q-13. Start with Q-1 (copyright in AI-written code), Q-4 and Q-7 (liability and the intended-use text), Q-5 (country and website), Q-11 (third-party text and runtime DLLs).

## 7. What I did after the owner's instruction "continue as per your recommendation"

Recorded in D-216 so that you can undo each one: the choices are in section F of the checklist (F1 to F13). Two items changed after the merge of #204 (offline evidence kit), which now strips network-related libraries from the package:

- **F7** is partly solved by #204: the Qt network library and the Kerberos libraries are no longer in the Linux package.
- **F13**: the committed inventory is the published 1.17.0 package with that stripping applied. For every release, make the inventory again from the package the release workflow built.

## 8. Next step

Phase 3, the website. I will write the design study of the app (colours, fonts, icons, the licence of every asset), the plan of the page and the text, and stop for your OK before I write any site code (checkpoint 3a). Nothing is deployed before your OK.
