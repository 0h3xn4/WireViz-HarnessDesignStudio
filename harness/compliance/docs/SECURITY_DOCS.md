# Software security management plan, analysis report and risk treatment plan

ECSS-E-ST-40C 5.11 and Table A-1 (SSMP, SSAR, SRTP); ECSS-Q-ST-80C 6.2.9. The standards supplied give no DRD for these documents, so the structure below is the project's own. Status: draft, not reviewed. The security standards the clauses refer to (for example ECSS-E-ST-40 5.11 security references, ECSS-Q-ST-80 6.2.9 methods "agreed between customer and supplier") were not supplied.

## Security management plan
- Security is part of `SPAP.md` section 6.4.
- Sensitivity: project files may be export-controlled; the tool never writes design data to logs or sends anything over a network (`../../docs/SPEC.md` hard constraint 4 and 1).
- Measures: `../../docs/SECURITY.md`; tests `tests/test_security.py`, `tests/test_offline.py`, `tests/test_fuzz.py`.
- Operations and maintenance: dependency versions are pinned and recorded; no automatic update; known vulnerabilities in the shipped dependencies are scanned automatically at each release (`python -m tools.check_vulnerabilities`, step 8a of `../../docs/RELEASE.md`, D-134; the build host needs network access, and a scan that cannot run fails the release check); the output is kept in the release evidence (action A-08).

## Security analysis report
Threat list and measures: `../../docs/SECURITY.md` (hostile project files, spreadsheets, injection into outputs, symlinks, oversized files, concurrent writers, supply chain). Method: review of each place the tool reads or writes data, plus fuzzing. Results: five defects found and fixed in M9 and one in the audit; none known open. The analysis has not been reviewed by a security specialist, and no agreed method exists (6.2.9.3 b): action A-08.

## Security risk treatment plan
| Risk | Treatment | Residual risk (accepted by the owner?) |
| --- | --- | --- |
| Look-alike or right-to-left characters in names | IDs are ASCII only; reviewers compare IDs | accepted in `../../docs/SECURITY.md`, owner confirmation open |
| Packages not signed | `SHA256SUMS`; the owner chose not to sign packages (2026-10-08, `../DEVIATIONS.md` T-19) | waived by the owner; reason not stated |
| Project folders are neither signed nor encrypted | use repository access control | accepted in `../../docs/SECURITY.md`, owner confirmation open |
| Vulnerable dependency | pinned versions, SBOM, vulnerability scan in every release check (`tools/check_vulnerabilities.py`, D-134) | scan is automatic; a person reads its result at the release; review of the security analysis by a person still open (A-08) |
| Helper process uses pickle between two trusted programs of the same package | allowed in two files only, tested | accepted by design (D-128) |
