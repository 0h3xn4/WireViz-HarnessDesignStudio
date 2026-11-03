# The scripting interface: what is stable

This page is for people who change `harness_design_studio/api.py`, the `--json` documents of the commands, or the code behind them. It says what must not change without a decision, and how to change it on purpose. The page for people who use the interface is [Script the tool](../user-manual/script-the-tool.md).

## Contents

- [What is covered](#what-is-covered)
- [The rules](#the-rules)
- [Change the interface on purpose](#change-the-interface-on-purpose)
- [Add a function or a field](#add-a-function-or-a-field)
- [Where the code is](#where-the-code-is)
- [The tests](#the-tests)

## What is covered

- **`harness_design_studio.api`.** The names in `__all__`, the signature of every function, the fields and methods of every result type, and the base classes of every exception. `tests/fixtures/api_snapshot.json` records all of them.
- **The `--json` documents of the commands.** The keys, in order, are listed in `SHAPES` in `cli/jsonout.py`; `docs/CLI.md` is made from it. The documents of `validate`, `check`, `drc`, `verify`, `generate`, `export` and `config` are the `to_dict()` of the result types of the interface, so they cannot differ from it.
- **The examples** in `docs/examples/scripting/`. They may import only the names in `api.__all__`; a test reads their imports.

What is not covered: anything not in `__all__`; the wording of a message, a title, an issue or a finding (a script should read codes and IDs, not sentences); the model hash and the numbers, which belong to the version of the tool that made them; the order of keys inside a nested object that the table of `SHAPES` does not list.

## The rules

1. **No behaviour of its own.** A function of the interface calls the function the command calls. It loads, locks, calls and saves; it does not compute a design result, and it does not choose between results. If the command line and the interface need the same logic, the logic goes into `core/` and both call it (as `core/validation.py` does for `validate`).
2. **One place for the data.** The result types and the functions that build them from the objects of the tool are in `core/records.py`. The command line prints `to_dict()` of the same objects (`cli/jsonout.py`, `Report`), so a document and a result are the same by construction. Do not build a second dictionary for a command.
3. **No Qt, no printing, no ending the program.** `api.py` and everything it imports at module level must not import `PySide6`, the `gui` package or the `cli` package. A function never calls `print`, `input` or `sys.exit`. `tests/test_api_stability.py` imports the interface in a process where Qt cannot be imported and runs the main functions there.
4. **Plain data in and out.** Paths as `str` or `os.PathLike`, results as frozen dataclasses with `to_dict()`, lists as tuples inside a result. A result holds no time, no user name and no absolute path.
5. **Errors are one tree under `HarnessError`.** A refusal that is a result of the design (a generation with errors, an export that fails its check) is a result with `ok` false; a misuse or a failure of the environment is an exception. A new exception is a subclass of an existing one.
6. **Writing takes the lock.** A function that writes into a project folder takes the project lock, as the editor and the commands do, and writes what the command of the same name writes (the tests compare the files byte for byte).
7. **Nothing the tool writes changes.** A change to the interface or to a `--json` document must leave every written output file as it was: `python -m tools.numbers_snapshot --check tests/fixtures/numbers/snapshot.json` and `python -m tools.output_hashes --check docs/ui/OUTPUT_HASHES_BASELINE.json` both say *identical*.

## Change the interface on purpose

A change that can break a script is: removing or renaming a name in `__all__`, removing or renaming a parameter, making an optional parameter required, changing the type of a field or the meaning of a value, removing a key from a `--json` document, or moving an exception out of its place in the tree. Adding a name, an optional parameter, a field or a key is not.

1. Make the change and the test that shows it.
2. Run `python -m tools.gen_api_snapshot`. Read the diff of `tests/fixtures/api_snapshot.json`: it must show exactly the change you meant.
3. If the change can break a script, raise `API_VERSION` in `api.py` (and regenerate the snapshot again), and say what changed and how to adapt in the `CHANGELOG.md` entry, under *Changed*.
4. For a `--json` document change `SHAPES` and run `python -m tools.gen_cli_docs`.
5. Update [Script the tool](../user-manual/script-the-tool.md) and the examples. The examples must still run: they are tests.
6. Prefer to keep the old name for a release: leave it in `__all__`, make it call the new one, and say in its docstring that it is kept for older scripts and what to use instead.

## Add a function or a field

1. Put the result type and the function that builds it from the objects of the tool in `core/records.py`, with a `to_dict()`.
2. Add the function to `api.py` and to `__all__`, with a docstring that says what it does, what it returns and when it raises. A test fails for an exported function without one.
3. If a command has the same result, give the command `--json` and add its keys to `SHAPES`; print `to_dict()` of the same object.
4. Test it against the command: the same files on disk, the same numbers, the same findings (see `tests/test_api.py`, `tests/test_cli_json.py`).
5. `python -m tools.gen_api_snapshot`, `python -m tools.gen_cli_docs`, `python -m tools.build_guide` if the guide changed, `python -m tools.gen_sdd_components`.

## Where the code is

| What | Where |
| --- | --- |
| The interface | `src/harness_design_studio/api.py` |
| Result types, `to_dict()`, the builders | `src/harness_design_studio/core/records.py` |
| What `validate` and `check` look at | `src/harness_design_studio/core/validation.py` (used by the command and the interface) |
| `--json`: the options, `Report`, `SHAPES` | `src/harness_design_studio/cli/jsonout.py`; each command in `cli/*.py` |
| The snapshot and its generator | `tests/fixtures/api_snapshot.json`, `tools/gen_api_snapshot.py` |
| The examples and their README | `docs/examples/scripting/` |

## The tests

| Test | What it keeps true |
| --- | --- |
| `tests/test_api_stability.py` | the snapshot; every exported name has a docstring; the interface works where Qt cannot be imported |
| `tests/test_api.py` | each function does what its command does (same files, same findings, same numbers), the errors, the lock, plain data, nothing printed |
| `tests/test_cli_json.py` | every command takes `--json`; each document has the keys the reference lists; the exit codes; the same bytes twice; no absolute path; equal to the interface |
| `tests/test_scripting_examples.py` | the examples run and import only `api.__all__` |
