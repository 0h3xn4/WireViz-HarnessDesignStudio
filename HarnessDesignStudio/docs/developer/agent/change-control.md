# Change control, releases of a harness: notes for agents

These sections were moved word for word from [`CLAUDE.md`](../../../CLAUDE.md) on 2026-10-29 (decision D-182); only this introduction is new. Read them when you work on revisions, baselines, the release freeze or the review workflow of a harness.

## Change control layout (M6)
`core/vcs/` (`release` plans, `locks` enforced in `History.execute`, `diff`, `snapshot`, `hashing` content hash, `report` change log and revision report, `consistency` released-vs-baseline), `cli/changes.py`. Format: `docs/FILE_FORMAT.md`; decisions D-102 to D-109.
- Release, new revision and review are plans of ops run through `History`; never write baselines or the change log directly.
- Anything that may change a released harness must pass `check_locks`; `apply_ops` bypasses it on purpose (generation, loaders, tests), so keep new editing paths on `History`.
- Generation's input hash must not include release bookkeeping (status); the outputs gate uses `content_hash`.
- Add a diffable object kind in `vcs/diff.py` (`_flatten_*`) and its name in `KIND_NAMES`.

