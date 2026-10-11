# Changelog

This repository has two changelogs, one for each tool, and this page says where to find them.

| Tool | Changelog | Latest version |
| --- | --- | --- |
| **Harness Design Studio** (`harness/`) | [`harness/CHANGELOG.md`](harness/CHANGELOG.md) | `0.1.0`, released 2026-10-09. The section *Unreleased (after 0.1.0)* lists what is on `master` and not in the 0.1.0 packages. |
| **WireViz** (`src/wireviz`, upstream) | [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | `0.4.1`. It is WireViz's own file, unchanged. |

The two version numbers are unrelated. `harness --version` prints the version of Harness Design Studio; `wireviz --version` prints WireViz's.

`master` of this repository is ahead of the released Harness Design Studio 0.1.0 and still prints `0.1.0`. To tell which one you have, run `harness new --list`: the 0.1.0 packages list three examples, a build from `master` lists five.

Next: [documentation index](docs/README.md).
