# Release compliance record: version X.Y.Z

Copy this file to `release-record-X.Y.Z.md` in this folder for every release and fill it in before the release page is published (decision D-210; `docs/RELEASE.md`, the release checklist). Keep the record: it is the evidence of what was checked. A record is a statement of what was done. It is not a statement that the release complies with anything.

Not legal advice. Facts only: write "not done" and the reason where a line was not done.

## The release

| Item | Entry |
|---|---|
| Version | |
| Tag | `vX.Y.Z` |
| Release date | |
| Commit (full SHA) | |
| Made by (workflow run, link) | |
| Release page | |

## Checks that ran (with the command or the run and its result)

| Check | Result | Where |
|---|---|---|
| Full test suite (`pytest -n auto -m "not perf"`, then `pytest -m perf`) | | |
| No-network test (`tests/test_offline.py`) | | |
| Site tests (once the website exists) | | |
| `pip-audit` (workflow `harness-legal.yml`, job `pip-audit`) | | |
| `reuse --root HarnessDesignStudio lint` | | |
| Promise words and legal texts (`tests/test_promise_words.py`, `tests/test_legal_texts.py`) | | |
| Licence allow-list and inventory drift (`python -m tools.check_third_party`) | | |
| CodeQL and dependency review (last run on the commit) | | |
| Commit check (author addresses, sign-offs) | | |

Findings of `pip-audit` that were not fixed, each with the decision and the reason:

## What is in the packages

| Item | Entry |
|---|---|
| SBOM (CycloneDX) per package format, file names and SHA-256 | |
| Third-party inventory (`third-party-inventory-X.Y.Z.md`) matches the built packages | yes / no |
| `THIRD_PARTY_NOTICES.txt`, `LICENSE` and `NOTICE` inside every package (checked by listing each package) | .deb / .tar.gz / Windows zip / Windows setup |
| Source archives of the LGPL and GPL components attached to the release (names, SHA-256) | |
| Open source offer text in `THIRD_PARTY_NOTICES.txt` | |

## Signing and provenance

| Item | Entry |
|---|---|
| Every package, `SHA256SUMS` and the SBOM signed with cosign (keyless); the `.sigstore.json` bundle names | |
| Build provenance attestations made (`actions/attest-build-provenance`), link | |
| Signature and attestation checked after the release with the commands in `docs/INSTALL.md` | yes / no |
| `SHA256SUMS` attached | yes / no |

## Release page

| Item | Entry |
|---|---|
| The page holds the disclaimer, the intended use and the project status (section "Status, licence and limits") | yes / no |
| Texts equal `compliance/legal/texts.md` (the drift test passed) | yes / no |
| Website version and date updated in its one place | yes / no / no website yet |

## Open risks

List the risks of `risk-register.md` that are still open for this release, and any new risk found. Review `risk-register.md` and write the date of the review here:

| Risk | Status |
|---|---|
| | |

## Sign-off of the owner

The owner reads this record and decides to publish. Name or handle, and date:
