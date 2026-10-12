# Software release document (SRelD)

DRD: ECSS-E-ST-40C Annex G. Version described: `0.1.0`. Status: draft, not reviewed. Released by the owner on 2026-10-09 with the engineering decisions still open; steps 12 and 13 of `../../docs/RELEASE.md` were waived (`../DEVIATIONS.md` T-27, T-30) and step 14 was given for 0.1.0 under T-31 (`../SIGNOFF.md`).

## 1 to 3, 4. Introduction, references, terms, release overview
Item: Harness Design Studio (package `harness-design-studio`). Delivered as `.deb` and `.tar.gz` for Ubuntu 24.04+. Contents and integrity values: `scf.json` and `SHA256SUMS` (`SCF.md`).

## 5. Status of the software configuration item
- **5.1 Evolution since the previous version:** `../../CHANGELOG.md`, section `0.1.0` (this is the first release; the release candidates `0.1.0rc1` to `0.1.0rc8` are listed below it). The section *Unreleased (after 0.1.0)* describes later changes on `master` that are not in this version.
- **5.2 Known problems or limitations:** listed at the top of the changelog entries and in `../../docs/OPEN_DECISIONS.md`: still open at this release and **not done**: the harness boundary rule (D-10), the title block (D-15), and the real derating and EMC values and approved parts, which have **not** been supplied (D-11, D-12), so results rest on placeholders and example parts (`../SIGNOFF.md`); waived by the owner and not done: packages not signed (T-19), usability sessions and screen-reader pass (T-27) and the other waivers T-18 to T-31 (`../DEVIATIONS.md`); buses with more than two ends are skipped with a warning. From this audit: wire surface temperature under load, partial-load factor L, bundle spacing, multipactor and bond resistance are not checked (named in the rule report as *not checked*).

## 6. Advice for use
Use the example data only for learning. Fill `config/` and the parts list before relying on a check (`../../docs/CONFIG.md`, `../../docs/PLACEHOLDERS.md`). Run the review checklist for every harness.

## 7. On-going changes
The improvements from the owner's UX/UI guideline document were made after the audit (D-132, D-140, D-141); `../../docs/UX_GUIDELINES_REVIEW.md` lists what was done, what is new and what is not applicable.
