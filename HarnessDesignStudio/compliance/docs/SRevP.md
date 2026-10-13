# Software review plan (SRevP)

DRD: ECSS-E-ST-40C Annex P. Status: draft, not reviewed. Reviews need the owner (action A-02).

## 1 to 3. Introduction, references, terms
See `SDP.md`.

## 4. Review title and project
One plan for all reviews of the Harness Design Studio. Subject: the repository state at a tag `review-<name>` (`CMP.md`).

## 5. Reference documents
All documents in `README.md` of this folder.

## 6. Review objectives
SRR: system context and requirements baseline are agreed (`SRS.md`). PDR: architecture agrees with requirements (`SDD.md`). CDR: design, tests and plans agree; code verified. QR: validation complete (`SValP_SVS.md`). AR: acceptance by the owner. Reviews may be held together because the project is small; that is a tailoring decision for the owner.

## 7. Expected results
Review report with decisions and RIDs, filed in `compliance/reviews/` (folder created at the first review).

## 8. Review process
Material is sent to the reviewer at least a week before; the reviewer records RIDs on the form below; the developer answers each RID; the owner closes the review by signing the report.

## 9. Review schedule
Not set. The owner proposes dates.

## 10. Documentation subject to review
The matrix of documents against reviews is Table A-1 of ECSS-E-ST-40C (not copied here); for this project all documents of this folder are submitted at the first review.

## 11. Participants
Owner (chair); a reviewer who is not the developer (A-01); the developer assistant (presents, does not decide).

## 12. Logistics
Remote, files from the repository.

## 13. RID form
The form is `../templates/review_record.md` (the reviewer's brief is `../templates/independent_review_brief.md`). Contents: RID number; document and clause; finding; severity (blocking, major, minor); proposed action; answer; closure.
