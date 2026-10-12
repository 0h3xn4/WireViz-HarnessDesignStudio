# Software release document (SRelD)

DRD: ECSS-E-ST-40C Annex G. Version described: `1.0.0` (first written for `0.1.0`). Status: draft, not reviewed. Version 0.1.0 was released by the owner on 2026-10-09 with the engineering decisions still open; steps 12 and 13 of `../../docs/RELEASE.md` were waived (`../DEVIATIONS.md` T-27, T-30) and step 14 was given for 0.1.0 under T-31 (`../SIGNOFF.md`). Version 1.0.0 was released on the owner's instruction on 2026-10-12 (`../SIGNOFF.md`, `../DEVIATIONS.md` T-32).

## 1 to 3, 4. Introduction, references, terms, release overview
Item: Harness Design Studio (package `harness-design-studio`). Delivered as `.deb` and `.tar.gz` for Ubuntu 24.04+. Contents and integrity values: `scf.json` and `SHA256SUMS` (`SCF.md`).

## 5. Status of the software configuration item
- **5.1 Evolution since the previous version:** `../../CHANGELOG.md`, section `1.0.0` (0.1.0 plus the audit fixes; the first release `0.1.0` and the release candidates `0.1.0rc1` to `0.1.0rc8` are listed below it).
- **5.2 Known problems or limitations:** listed at the top of the changelog entries and in `../../docs/OPEN_DECISIONS.md`: the real derating and EMC values and the approved parts have **not** been supplied, so results rest on placeholders and example parts (D-11, D-12; recorded as "each project supplies them" in D-145); the harness boundary rule (D-10) and the title block (D-15) are recorded as the defaults the tool implements (D-144), as the assistant's defaults under the owner's delegation, not as an engineering confirmation (`../SIGNOFF.md`); waived by the owner and not done: packages not signed (T-19), usability sessions and screen-reader pass (T-27) and the other waivers T-18 to T-32 (`../DEVIATIONS.md`); buses with more than two ends are skipped with a warning. From this audit: wire surface temperature under load, partial-load factor L, bundle spacing, multipactor and bond resistance are not checked (named in the rule report as *not checked*).

## 6. Advice for use
Use the example data only for learning. Fill `config/` and the parts list before relying on a check (`../../docs/CONFIG.md`, `../../docs/PLACEHOLDERS.md`). Run the review checklist for every harness.

## 7. On-going changes
The improvements from the owner's UX/UI guideline document were made after the audit (D-132, D-140, D-141); `../../docs/UX_GUIDELINES_REVIEW.md` lists what was done, what is new and what is not applicable.
