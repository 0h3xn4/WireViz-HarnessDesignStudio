# Security review (M9)

The tool runs offline on an engineer's workstation, reads project folders (which may come from Git, e-mail or a colleague) and spreadsheets, and writes files next to them. This review lists what could go wrong with hostile or damaged input and what was done. Each point has a test in `tests/test_security.py`, `tests/test_fuzz.py` or the loader tests.

## What the tool never does
- No network access (tested: sockets blocked, no network modules imported).
- No `eval`, `exec`, `pickle`, `subprocess`, `os.system`, `ctypes`, no YAML loader (an AST scan fails the test suite if one appears). The one exception is the design rule check helper process (D-128): `gui/drc_process.py` may use `subprocess` (it starts this same program with fixed arguments, no shell, no user data in the command) and `core/drc/worker.py` may use `pickle` (the project and the findings cross its own stdin/stdout pipes, between two copies of this program; nothing read from a project file or from the network is ever unpickled). The scan lists exactly these two files. The author line of the Revisions area (D-164) is read from the `.git` files of the project's repository by `core/vcs/gitinfo.py` (read-only, size-limited, no `git` program, no repository setting is read).
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
| Supply chain | Pinned dependencies, CycloneDX SBOM and licence report with every release and release candidate (the runtime packages and their licence texts, none rejected; for 0.1.0 the packages and their number are in the release report, [`release_0.1.0_report.md`](../compliance/evidence/release_0.1.0_report.md); for 1.0.0 to 1.3.0 `compliance/evidence/` keeps only the checksum lists, so that report is not repeated there), a reproducible wheel check. The fonts (Inter, JetBrains Mono, SIL OFL 1.1) and icons that the editor draws with are bundled with their licence texts and are never downloaded (`tools/collect_licences.py`; the Settings page of the editor lists them). |
| Design data in logs or messages | Validation messages name fields, not values (export-controlled data); the tool writes no log of design content. |

## Unsigned packages (Windows and macOS from 1.2.0)
A code signature tells the operating system who built a program and that it was not changed afterwards. Without one:

- **Windows** SmartScreen shows *Windows protected your PC* for the setup program and the editor until a signed build has earned reputation (a signature is the precondition, not the guarantee), and the user must choose **More info > Run anyway**.
- **macOS** Gatekeeper refuses the app on a plain double-click until the user opens it once with right-click > **Open** (or removes the quarantine mark with `xattr -dr com.apple.quarantine`). Apple Silicon requires some signature on every program, so the app carries an *ad hoc* signature that only keeps its files together; it names no developer and is not notarized.
- The user has **only the checksum** to know that a download is the file the release lists: one `SHA256SUMS` file on the release page covers every package. A checksum shows that a download is intact; it does not show who made it, so it is as trustworthy as the page it was read from.

What signing adds: the name of the publisher in the operating system's dialog, a check at install time that the files are unchanged since the build, and, with Apple's notarization, a scan by Apple and a ticket that lets Gatekeeper open the app without the manual step. It adds no protection against a bug in the tool, and it needs a certificate that costs money and a private key that must be guarded: the key lives only in the repository secrets listed here and is never in the repository or in a package.

The workflows can sign when these repository secrets exist (`.github/workflows/release.yml`; setup and what each does: [`RELEASE.md`](RELEASE.md), *Windows and macOS packages*). Without them every signing step is skipped and the packages are unsigned.

| Platform | Secrets |
| --- | --- |
| Windows | `WINDOWS_CERT_PFX_BASE64` (the `.pfx` certificate, base64) and `WINDOWS_CERT_PASSWORD` |
| macOS signing | `MACOS_CERT_P12_BASE64` (the Developer ID Application certificate as `.p12`, base64) and `MACOS_CERT_PASSWORD` |
| macOS notarization | `MACOS_NOTARY_APPLE_ID`, `MACOS_NOTARY_TEAM_ID` and `MACOS_NOTARY_PASSWORD` (an app-specific password, never the Apple ID password) |

Handling: the secrets are read only by the build jobs (never by the job that publishes), are passed to the build scripts through environment variables and temporary files in the runner's temporary folder, and are not printed. The build jobs of a pull request from a fork do not receive repository secrets. The workflows that run on branches `pkg/**` use no secrets at all.

## What the packages do on the machine
The Windows setup program installs for the current user only and writes to the install folder, the Start menu folder of the user, `HKCU\Environment\Path` (the install folder and its `cli` folder) and the uninstall entry under `HKCU`. It asks for no administrator rights, starts no service and no scheduled task, and contacts no server. The macOS app is a folder that is copied to Applications; it installs nothing else. The portable `.zip` writes nothing outside its folder. None of the three downloads anything when it is installed or run (the Windows smoke test blocks the programs from the network while they run).

## Accepted risks and limits
- The user guide opens in the system browser as a local file; the browser's own security applies.
- Names can contain look-alike or right-to-left Unicode characters. They are rendered as written; reviewers should compare IDs, which are ASCII only.
- A project folder is trusted to the extent that its files are valid; the tool does not sign or encrypt projects. Use your normal repository access control.
- The packages are not code-signed (D-19: no certificate provided): not the `.deb` and `.tar.gz`, and, from 1.2.0, not the Windows setup program and `.zip` and not the macOS `.dmg` (D-149). The consequences are described under *Unsigned packages* above.
- Fuzzing found and fixed five real bugs in M9 (and a sixth in the audit); it is not a proof. `HARNESS_FUZZ_EXAMPLES=5000 pytest tests/test_fuzz.py` runs a longer search.
