# Software configuration file (SCF)

The DRD for the SCF is ECSS-M-ST-40 Annex E, which was **not supplied**; the layout below is the project's own and is not claimed to meet that DRD (ECSS-Q-ST-80C 6.2.4.3, 6.2.4.4, 6.2.4.10, 6.2.4.11).

`python -m tools.gen_scf` writes, for each release, into `dist/release-docs/`:

- `scf.json`: package name and version; commit id; dependencies with pinned versions; SHA-256 of every source, test, tool, packaging, documentation and compliance file; the aggregate **source integrity value** (SHA-256 over the sorted list of files and hashes); the delivered packages with size and SHA-256.
- `SHA256SUMS`: the delivered packages in `sha256sum -c` format.

Verification by the recipient: `sha256sum -c SHA256SUMS` in the folder with the packages. This detects damage in transfer; it does not protect against someone replacing both files. Signing is open (action A-08).

Recompute the source integrity value from a checkout with the same tool and compare it with `scf.json`.
