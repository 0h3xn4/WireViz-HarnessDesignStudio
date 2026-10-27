# Software development plan (SDP)

DRD: ECSS-E-ST-40C Annex O. Status: approved by the owner on 2026-10-08 (approval given in the working session; the owner is also customer and supplier, so no independent reviewer, see A-01).

## 1. Introduction, 2. Reference documents, 3. Terms
Software: Harness Design Studio. See `SPAP.md` and `../../docs/SPEC.md`.

## 4. Software project management approach
- **4.1 Objectives and priorities:** correctness and traceability of generated harness data first; offline operation; then usability and speed (`../../docs/SPEC.md` parts 1 and 3).
- **4.2 Master schedule:** milestones M0 to M9 are done (`../../docs/PLAN.md`); the October audit (`../../docs/AUDIT.md`); this compliance audit (phases 0 to 4). Next planned work after the audit was the improvement of the tool from the owner's UX/UI guideline document; that, and the later releases, are recorded in `../../CHANGELOG.md`: 1.1.0 (the editor rebuilt against the new UX standard, the Devices tab), 1.2.0 (Windows and macOS packages, D-149; macOS removed after 1.5.0, D-168) 1.3.0 (the UI overhaul, D-150 to D-159, with its own milestones M1 to M9 and a final milestone in `../../docs/ui/UI_OVERHAUL_PLAN.md`; these are not the milestones M0 to M9 above), 1.4.0 (the feedback of the AIT engineers, D-160 to D-165, plan `../../docs/ait/AIT_FEEDBACK_PLAN.md`, with milestones M1 to M5 of its own), 1.5.0 (a harness made by hand, D-166; a clear start on Linux, D-167) 1.6.0 (macOS removed, D-168; an *Add a device* button on the blank project) and 1.7.0 (the test users of 1.6.0, D-169 to D-171: a build workbook, the build data, a simple workspace in two stages; plan `../../docs/ait/TEST_USER_FEEDBACK_PLAN.md`), the latest published release (2026-10-22). Added 2026-10-20 and extended 2026-10-22; the owner's approval of 2026-10-08 was for the earlier text.
- **4.3 Assumptions, dependencies, constraints:** Ubuntu 24.04+ and, from 1.2.0, Windows 10 and 11 (D-149; macOS was supported from 1.2.0 to 1.5.0 and removed, D-168), Python 3.14+, PySide6 (packages carry their own Python and Qt, D-167); no network; open points need the owner (D-10, D-11, D-12, D-15; `../../docs/OPEN_DECISIONS.md`).
- **4.4 Work breakdown:** `core` (model, generate, drc, outputs, vcs, io), `cli`, `gui`, `resources`, `tools`, `packaging`, `tests`, `docs`, `compliance`.
- **4.5 Risk management:** `SPAP.md` 5.6.
- **4.6 Monitoring and control:** CI on every pull request and every push to the default branch (`harness-ci.yml`; `harness-platforms.yml` runs the suite on Windows); `CHANGELOG.md`; milestone reports (`SPAMR.md`).
- **4.7 Staffing:** the owner decides and reviews; the developer assistant implements. No independent verifier (A-01).
- **4.8 Procurement, 4.9 supplier management:** none; third-party libraries pinned and recorded (`SRF.md`).

## 5. Software development approach
- **5.1 Strategy:** incremental, test first, small commits that name the requirement or decision they serve; the design is the source of truth and outputs are generated.
- **5.2 Life cycle:** 5.2.1 incremental milestones with a gate document each (`../../docs/demos/`); 5.2.2 there is no system development cycle around the tool; 5.2.3 reviews: see `SRevP.md`.
- **5.3 Standards and techniques:** `STANDARDS.md`.
- **5.4 Development and test environment:** `STANDARDS.md` and `../../CLAUDE.md` (commands); tests run offscreen; the GUI is tested with pytest-qt.
- **5.5 Documentation plan:** 5.5.1 documents are Markdown in the repository; 5.5.2 and 5.5.3 listed in `README.md` of this folder and `../../docs/README.md`; 5.5.4 documentation standards: plain language, every command in the guide is run by a test (`tests/test_docs.py`).
- **5.6 Tailoring traceability:** applicability at category C in `../requirements/ECSS-E-ST-40C.csv` (column cat_C) and the assessment in `../compliance_matrix.csv`. Deviations: `../DEVIATIONS.md`.
