# Security review (M9)

The tool runs offline on an engineer's workstation, reads project folders (which may come from Git, e-mail or a colleague) and spreadsheets, and writes files next to them. This review lists what could go wrong with hostile or damaged input and what was done. Each point has a test in `tests/test_security.py`, `tests/test_fuzz.py` or the loader tests.

## What the tool never does
- No network access (tested: sockets blocked, no network modules imported).
- No `eval`, `exec`, `pickle`, `subprocess`, `os.system`, `ctypes`, no YAML loader (an AST scan fails the test suite if one appears). The one exception is the design rule check helper process (D-128): `gui/drc_process.py` may use `subprocess` (it starts this same program with fixed arguments, no shell, no user data in the command) and `core/drc/worker.py` may use `pickle` (the project and the findings cross its own stdin/stdout pipes, between two copies of this program; nothing read from a project file or from the network is ever unpickled). The scan lists exactly these two files.
- No macros, formulas or scripts from project data are executed.

## Threats and measures
| Threat | Measure |
| --- | --- |
| A project file with broken, truncated, deeply nested, binary or duplicate-key JSON | Every file is parsed strictly; a bad file is set aside (quarantine) with a plain message, the rest loads, and the original folder cannot be overwritten (`recovered` projects refuse to save over it). Nesting too deep for the parser is reported, not raised. |
| Well-formed JSON with wrong types or impossible values | Strict immutable models; invalid objects are quarantined individually. Fuzzing (random mutations of every file) checks that anything accepted survives integrity checks, rules, generation, outputs and the verifiers. A project whose interface type file is damaged no longer crashes generation (found by fuzzing). |
| IDs or names used to escape the folder (`../x`, `a/b`, device names) | IDs allow letters, digits, `_ - .` only, start with a letter, no reserved names; file names derive from IDs or sanitised revision letters. Free text (names, notes) is never used in a path. |
| Symbolic links in a project folder pointing at other files or folders | Ignored with a warning (`symlink_ignored`); their content is never read or copied into a quarantine file. Nothing is ever written or deleted behind a link: saving and exporting check every file (at any depth) against its root before they write or delete, and refuse the whole operation if a folder on the way is a link out of it. Temporary files get unique names and are created exclusively, and a backup (`.bak`) or temporary file that is a link is replaced, never followed. |
| A gigantic project file | Files above 64 MB are refused unread. |
| A spreadsheet that is a zip bomb or has millions of empty rows or columns | `.xlsx` files are limited to 8 MB packed, 64 MB unpacked and 2,000 parts; at most 100,000 rows are scanned and 200 columns read; CSV is limited to 8 MB and 20,000 rows. Tested with a crafted bomb (refused in under 5 s). Bare CR line endings and stray characters no longer raise (found by fuzzing). |
| Formula injection: a cell like `=HYPERLINK(...)` in an export opened in a spreadsheet program | CSV cells that start with `= + - @` (and are not numbers) are written with a leading `'`; XLSX cells are stored as text, never formulas. Tested with hostile names. |
| Markup injection in SVG, PDF, YAML, Markdown | SVG text is XML-escaped (tested well-formed with `<script>` in names); PDF strings are escaped; YAML scalars are JSON-quoted. Markdown reports contain user text as written (a reader may see backticks or link syntax; nothing is executed). |
| A manifest or journal that lists paths outside the output folder, or is damaged | Only files listed in the previous manifest are deleted, and only if the path is relative, contains no `..` and lies behind no link. Damaged manifests, journals and outputs are findings (`out_unreadable`, ignored journal), not crashes (fuzzed). |
| Two instances overwriting each other, or an interrupted save | Project lock, atomic writes with backups, autosave journal inside the project folder (existing since M1). |
| Supply chain | Pinned dependencies, CycloneDX SBOM and licence report with every release and release candidate (the runtime packages and their licence texts, none rejected; the packages and their number are in the release report, [`release_0.1.0_report.md`](../compliance/evidence/release_0.1.0_report.md)), reproducible wheel check. |
| Design data in logs or messages | Validation messages name fields, not values (export-controlled data); the tool writes no log of design content. |

## Accepted risks and limits
- The user guide opens in the system browser as a local file; the browser's own security applies.
- Names can contain look-alike or right-to-left Unicode characters. They are rendered as written; reviewers should compare IDs, which are ASCII only.
- A project folder is trusted to the extent that its files are valid; the tool does not sign or encrypt projects. Use your normal repository access control.
- The `.deb` and `.tar.gz` are not code-signed (D-19: no certificate provided).
- Fuzzing found and fixed five real bugs in M9 (and a sixth in the audit); it is not a proof. `HARNESS_FUZZ_EXAMPLES=5000 pytest tests/test_fuzz.py` runs a longer search.
