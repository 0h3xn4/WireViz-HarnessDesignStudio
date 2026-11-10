# Owner checklist

Date: 2026-11-09 (Phase 1). Everything here is something only the owner (GitHub account `0h3xn4`) can do or decide. Each item has a one-line reason. Mark an item `[x]` when done, or write `declined` and the date when you choose not to do it. Not legal advice.

Related files: `legal-audit.md` (findings), `risk-register.md` (`LR-` numbers), `lawyer-questions.md` (`Q-` numbers).

## A. Answers needed before Phase 2 starts (Checkpoint 1)

- [ ] **A1. Where do you live (country, and state or region if it matters)?** It decides the content of the privacy notice, whether an imprint is required (for example an Impressum in Germany), and which consumer, export and product-liability rules a lawyer must check. Do not write a street address in any file of the repo. (LR-29, Q-5)
- [ ] **A2. What did "used internally and never shared" (D-186) mean on 2026-10-29?** Only you, or a group at an organisation? Nothing in the repository defines it. (LR-02)
- [ ] **A3. Does any employer, client, university or agency have a claim on the tool, the examples or the ideas?** Was any part built on employer time, equipment or data? Your brief says no. The documents contain many "your company" and "your IT" sentences (AI-written), and a tag by another person exists (A4). I need your explicit answer, because the GPL grant depends on it. (LR-02)
- [ ] **A4. Tag `v1.15.0` was created by another named person with an address at a company domain.** Who is this person? Whose computer or account made the tag? Did this person write, review or publish anything? I do not name the person in files. The name and address are in `git cat-file -p v1.15.0`. (LR-03)
- [ ] **A5. Who took part in the workshop and the AIT-engineer feedback (D-172, `SIGNOFF.md:129`, the usability kit)?** Did they agree that their feedback is used and public? Was real project data shown? (LR-02)
- [ ] **A6. Are SpaceMissionStudio, SystemDesignStudio, Requirements Studio, Budget Studio, AIT Logbook and ICD Studio your own projects?** They are named in `docs/ui/UI_OVERHAUL.md`, `docs/TIPS.md` and `docs/DOCS_AUDIT.md`. Are they public? Do they share code with this tool? (LR-26)
- [ ] **A7. Is any example data (`flatsat`, `small-satellite`, `minimal-satellite`, test fixtures) taken from a real project, a real mission or a datasheet?** The flatsat project says "EXAMPLE numbers, not engineering data". I found no real names, but I cannot see your intent. (LR-12)
- [ ] **A8. Python 3.14.** The sandbox has no Python 3.14, so I cannot run the test suite yet. Do you want me to (a) find a way to install 3.14 here, or (b) rely on CI runs on the pull request branch? (LR-33)

## B. Decisions I need from you

### B1. Existing releases (20 releases, 1.0.0 to 1.17.0)

- [ ] Choose how to handle them (brief 2.9 step 8). Both options will be prepared.
  - (a) Add licence, notices and signatures to the existing release assets. This changes release assets. Packages themselves stay as they are, so they would still hold the gaps in `audit-annex-third-party.md`.
  - (b) Publish one new release with every fix and mark the old ones as superseded in their text. **My recommendation:** (b). The old packages cannot be made complete without rebuilding them.
  - Also decide: the four macOS releases (1.2.0 to 1.5.0) cannot be rebuilt. Keep them with a superseded note, or ask GitHub to remove the assets (not decided by me).
  - Reason: release assets and release texts are public records. I will not edit or delete any release without your OK.

### B2. History findings (full scan in `legal-audit.md`, area 6)

- [ ] **Mailbox address on 98 commits and tag `v1.14.0`.** Is this address private? If yes, decide: accept, or approve a history rewrite. A rewrite gives new commit IDs, breaks old links, forks and tags (20 release tags and their commit links), and cannot remove copies that others already have. I will not start without your OK, and I will first write the exact steps and the order. (LR-08)
- [ ] **A second personal address on 3 commits and in 2 commit messages** (`5668c62c`, `839e98f0`, `e8f3b01b`). Same decision. (LR-08)
- [ ] **Upstream contributors' addresses** are in the upstream part of the history. I recommend you do nothing: it is upstream's history and a rewrite would break the fork.
- [ ] **No secret or token was found** by my regular-expression scan. Run gitleaks yourself for a second opinion (see D1).
- [ ] **Use the GitHub noreply address for future commits:**
  1. Open <https://github.com/settings/emails>.
  2. Tick "Keep my email addresses private" and "Block command line pushes that expose my email".
  3. Copy your noreply address from the same page. It looks like `ID+0h3xn4@users.noreply.github.com` (the ID is a number shown there).
  4. In every clone: `git config user.name "0h3xn4"` and `git config user.email "<your noreply address>"`. Do not use `--global` unless you want it for all repositories.
  5. I will add a CI check that fails when a new commit has another author address (it will only look at commits after the fork point and after a date you confirm).

### B3. Upstream files changed against your decision (LR-07)

- [ ] Choose: (a) restore `src/wireviz/*.py`, `setup.py`, `.gitignore`, `MANIFEST.in`, `docs/README.md` and `.github/workflows/main.yml` to the fork base `e4fe099f` byte for byte, or (b) keep the changes, add a modification notice, and correct every sentence that says "unchanged". Brief rule 3 forbids me to change these files without your OK, and that includes restoring them.
- [ ] Decide what happens to `.github/workflows/main.yml` (inherited upstream workflow, no `permissions`, runs on every push): disable it, restrict it, or keep it. (LR-16)

### B4. Data that may not be public (area 7)

- [ ] **ECSS and ESCC requirement text** in `compliance/requirements/*.csv` (about 1,900 rows, up to 600 characters each) and `compliance_matrix.csv`. Keep, cut to IDs and clause numbers, or remove from the public repo? I delete nothing without your decision. (LR-09, Q-6)
- [ ] **Optional ECSS profile values** in `core/standard_profiles.py`. They were transcribed by an AI and no person checked them. Keep with an "unchecked" marker, or remove the profiles? (LR-11)
- [ ] **Root `AUDIT.md`** (265 KB, public, lists unfixed upstream bugs and early defects). Keep it public? (LR-31)
- [ ] **View the screenshots.** I viewed 2 of 383. Look at `docs/ux/`, `docs/ui/screenshots/` and `docs/img/` for personal data before the website uses them.

### B5. Names and trademarks (area 9)

- [ ] **Run the searches in section D2** and write the result here: `____`. I do not rename anything. (LR-19)
- [ ] **The aliases `harness` and `harness-gui`.** The CLI of a DevOps company is also called `harness`. D-147 forbids removing aliases without a recorded decision. Keep, rename or remove? (LR-19)
- [ ] **Publisher name** in the Windows installer and **maintainer line** in the `.deb` ("Harness Design Studio maintainers"). Which handle should show: `0h3xn4`? No real name is used unless you decide so. (LR-24)

### B6. Output and app changes that touch what users see (brief 2.4 step 3 and rule 3)

- [ ] **User name and host name in files** (LR-20). The run record, the journal and release records hold the operator name (typed, Git `user.name`, or OS user). The project lock file holds the host name. Options: keep and tell users in the privacy statement; or stop recording the OS user and host name. Reports go to you first.
- [ ] **Wording of "Independent check"** (becomes "self-check") and **notice next to "released" / "approved" status** in drawings and workbooks. This changes generated output (reference outputs are updated once, deliberately). (LR-10)
- [ ] **A marker for a harness released on placeholder values** in drawings and workbooks. (LIA-7)

### B7. Export control

- [ ] **Ask an export-control specialist?** The tool is for spacecraft harness design. I found no ITAR or EAR markings and no real programme data. I cannot judge whether publishing such a tool is controlled in your country. This is not a question I can answer. (LR-12, Q-8)

### B8. Lawyer

- [ ] **Have a lawyer review `lawyer-questions.md`?** It is written to be handed over as it is. Without a lawyer, residual risks LR-12, LR-13, LR-14 and LR-29 stay open. Decision and date: `____`.

## C. Repository and account settings (brief 2.10 step 4, Phase 2 step 2.10)

I cannot see or change these. I will not change settings without your OK. Status as far as the public GitHub API shows is in brackets.

- [ ] Two-factor authentication on your GitHub account (not visible).
- [ ] Branch protection on `master`: pull requests required, status checks **required** (the list of required checks is empty today), no force pushes (the ruleset "Protect main" exists: pull request required, 0 approvals, force push and deletion blocked).
- [ ] A **tag ruleset** for `v*` (none today) and **immutable releases** (not set on any release).
- [ ] Secret scanning and push protection (both enabled).
- [ ] Private vulnerability reporting (not visible; `SECURITY.md` in Phase 2 depends on it).
- [ ] Dependabot security alerts (security updates are disabled today).
- [ ] Code scanning (CodeQL) default setup or the workflow I add (not visible).
- [ ] **Dependency graph** (Settings, Code security): switch it on. The dependency review job of `harness-legal.yml` cannot run without it (it stops with "not supported on this repository"); the job is skipped until you also add the repository variable `DEPENDENCY_GRAPH` with the value `true` (Settings > Secrets and variables > Actions > Variables).
- [ ] Disable the inherited upstream WireViz workflow `main.yml` if not needed (see B3).
- [ ] Remove the four stale workflow registrations in the Actions tab (platform probe, probe mac perf, win lock probe, release dry run) if you do not need their history (not visible in files).
- [ ] Check which repository secrets exist (`WINDOWS_CERT_PFX_BASE64`, `WINDOWS_CERT_PASSWORD`, any macOS secrets). Remove those that are not used.
- [ ] Default workflow token permission "read" and the fork pull-request approval policy.
- [ ] Decide whether to enable Issues (disabled today). `SUPPORT.md` and the templates assume issues are answered at your discretion.
- [ ] Pages (Phase 4 only, after your OK): Source "GitHub Actions"; "Enforce HTTPS".

## D. Things you can run yourself

### D1. gitleaks (second opinion on secrets; I could not run it)

```bash
gitleaks detect --source . --log-opts="--all" --redact -v
```

### D2. Trademark and name searches (I could not reach the registers)

Run these and note the date and result in `owner-checklist.md` or `legal-audit.md`. A free name in a search is not clearance.

1. USPTO: <https://tmsearch.uspto.gov/>. Search `harness design studio` and `harness` in classes 009 and 042. Open the HARNESS registrations Reg. 5409033 and 6548553 in <https://tsdr.uspto.gov/> and note the owner. (Aggregator sites disagree on the owner.)
2. EUIPO: <https://www.euipo.europa.eu/eSearch/> and TMview <https://www.tmdn.org/tmview/>, classes 9 and 42.
3. WIPO Global Brand Database: <https://branddb.wipo.int/>. Search `harness design studio`, `harnessdesignstudio`, `harness studio`, `harness designer`.
4. The register of your own country (for example UK <https://trademarks.ipo.gov.uk/ipo-tmtext>, Germany <https://register.dpma.de/>).
5. Web, GitHub, PyPI and npm for the exact name variants. Known similar names: EPLAN Harness proD Studio, EMCoS Harness Studio, Siemens Capital Harness, TE HarnWare, Zuken E3, GitHub projects named `harness-studio`.
6. Read at source: <https://harness.io/legal/trademark> and <https://ecss.nl/license-agreement-disclaimer/> (the reproduction clause of the ECSS documents).
7. GitHub Pages limits and terms: <https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits>.
8. The imprint and accessibility rules of your country, or a lawyer.

## E. Items that come later

- [ ] After Phase 2: read the pull request, the test and CI results and the updated risk register, then give your OK for Phase 3 (Checkpoint 2).
- [ ] Before Phase 3 design work: OK for the palette, fonts, wireframe and section content (Checkpoint 3a).
- [ ] Before Phase 4: confirm the Pages settings. Merge, deploy and the live check only after your OK.
- [ ] Imprint: only if your country requires it. Placeholders I will leave for you: name, postal address, contact. I will not invent them.
- [ ] Contact route on the website: a GitHub profile link or an issue, not a personal e-mail, unless you decide otherwise.
- [ ] Final report: mark every item here `done` or `declined` before the definition of done is met.

## F. Added after Phase 2 (things I did on "continue as per your recommendation", and what they leave for you)

Each item says what was done and what only you can do or decide. Mark `[x]` when done.

- [ ] **F1. The first signed release.** The release workflow now signs with Sigstore and attaches the SBOMs, the inventory, the notices and the source of the LGPL and GPL components. **I could not run it**, so the first release made with it is its first test. Decide when to make one (the release pages say "signed" from 1.17.1 on, `tools/release_notes.py`, `SIGNED_FROM`). Then ask me to check one file with the commands of `docs/INSTALL.md`. I recommend a release candidate tag first (for example `v1.17.1-rc1`): the workflow marks it as a pre-release.
- [ ] **F2. The releases 1.0.0 to 1.17.0** are not edited (B1). My recommendation, option (b): the first release with the legal fixes says in its notes that the older ones are superseded. I did not touch any release page or asset. The v1.0.0 page still says "clean-room".
- [ ] **F3. `main.yml`** (the inherited WireViz workflow) is kept, with pinned actions and `permissions: contents: read`. Disable it in the Actions tab if you do not need it (C).
- [ ] **F4. Commit sign-off (DCO).** `tools/check_commits.py` requires a `Signed-off-by` line and a GitHub noreply author address on every commit of a pull request, **except** that a pull request opened by you (the repository owner) needs no sign-off line (the commits of the AI assistant are yours to merge). Say if you want the sign-off for those too: then I add `git commit -s` with your noreply identity.
- [ ] **F5. App privacy statement.** It says nothing is sent and no personal data is collected. It does not yet say that the run record and the journal can hold your name (Git `user.name` or the operating-system user) and that the project lock file holds the host name. Decide (B6): keep and say so in the statement, or stop recording the system user and the host name.
- [ ] **F6. Windows packages.** The Microsoft runtime DLLs and the Mesa `opengl32sw.dll` are listed in the notices with a licence label, but their redistribution terms were not read at the source. Decide whether to keep them, and ask a lawyer (Q-11).
- [ ] **F7. Ubuntu libraries in the Linux packages.** (After the merge of #204 the Qt network library and the Kerberos libraries are stripped from the package and from the committed inventory; the rest of this item still holds for the GTK theme plug-in.) 79 libraries of Ubuntu are in the `.deb` and `.tar.gz`. About 43 of them come only from an optional GTK theme plug-in and from `libQt6Network`, which the app does not use. Removing them reduces the source and notice duty and the size. I did not remove anything, because it changes what the packages hold (a decision, and it needs a package test on a clean machine).
- [ ] **F8. Qt-internal third-party code.** The notices point to the Qt list ("Third-Party Licenses Used in Qt") and do not copy each text. A lawyer should say whether that is enough (Q-11).
- [ ] **F9. `docs/DOCS_AUDIT.md`** (a file under the root `docs/`) still uses the word "clean-room" and names the other "Studio" products. I did not touch `docs/` (brief rule 3). Tell me if I may change it.
- [ ] **F10. Private vulnerability reporting** must be switched on (C) for `.github/SECURITY.md` to work.
- [ ] **F11. Review the screenshots** (B4) before the website uses them. I viewed 2 of 383.
- [ ] **F12. CodeQL, first run.** The new CodeQL workflow found 101 alerts (20 errors, 54 warnings, 27 notes) on the first pull request, because every file counted as changed (the licence headers). The three in new code were fixed. I could not list the others (the alert list is not readable from here). Read them in the repository's Security tab, Code scanning, and tell me which to fix. Most are probably in older code and in tests.
- [ ] **F13. The committed inventory comes from the published package.** (Since 2026-11-10 the published package with the network stripping of #204 applied by `tools.build_installer.strip_network_capable`; the Windows one is not checked by a real build.) The Linux inventory of 1.17.0 in `compliance/legal/` was made from the published 1.17.0 tarball (built on a CI runner), not from a package built in my sandbox: a package built with another Python bundles other system libraries (the CI check found 11 more). For every release, make the inventory again from the package the release workflow built (`docs/RELEASE.md`, the legal checklist) and commit it.
