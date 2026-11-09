# Extensions: the registry, the file format, the plug-in API

This page is for people who write extensions for the tool or change the code behind them (`core/extensions/`). The page for people who use them is [Extend the tool](../user-manual/extend-the-tool.md). The decision behind it is D-191 (5): declarative extensions first, Python entry points second, both opt-in per project with a prompt that names the code, and the name and version of every extension in the record of what made a result.

## Contents

- [What it is](#what-it-is)
- [The registry](#the-registry)
- [Declarative extensions](#declarative-extensions)
- [The expression language](#the-expression-language)
- [Fields](#fields)
- [Python plug-ins](#python-plug-ins)
- [Trust](#trust)
- [Provenance](#provenance)
- [Stability](#stability)
- [Security: what this is not](#security-what-this-is-not)
- [Where the code is](#where-the-code-is)
- [The tests](#the-tests)
- [What is not done](#what-is-not-done)

## What it is

A project folder may hold `extensions/`. It holds data files (`*.json`) that add rules, output tables and lookup tables, Python plug-ins (`plugins/*.py`), and `enabled.json` that lists which of them the project uses. The loader (`core/io/loader.py`) calls `extensions.attach` when that folder exists and sets `project.extensions`; a project without the folder never reaches any of this code (`project.extensions` is `None`, and every hook in the shared modules tests for that first). `project.extensions` is plain data that can be pickled, because the design rule check runs in a helper process that gets a copy of the project and builds the rules again from it.

The hooks in the rest of the tool are small and additive: `drc.run` adds the findings of the extension rules, `drc.all_rules` and `by_rule.run_by_rule` list them, `derive.is_explainable` and `derive_rules.explain_rule` explain them, `outputs.build` writes the tables and lists the extensions in the manifest and `provenance.json`, `validation.validate_folder` reports the problems, `schemas.schemas` exports the two schemas, and the command line and the editor show the lists.

## The registry

`core/extensions/registry.py` has one list of everything the tool can run, built-in and extension together. An `Item` has a kind, a name, a version, a source, an origin, the SHA-256 of the file or code it comes from, one sentence, and the object itself.

| Kind | What it is | Built-in items | Extensions can add |
| --- | --- | --- | --- |
| `rule` | a design rule | the 39 of `drc.RULES` | data files and plug-ins |
| `field` | a value an expression can read | the fields below | plug-ins |
| `model` | a calculation model offered as a setting (`model.bundle_basis` ...) | the choices of `config/model.json` | nothing (listed for completeness) |
| `table` | an output table written by `export` | the tables `export` writes | data files and plug-ins |
| `lookup` | a table of values for `lookup(...)` | none | data files |
| `importer` | a reader of an outside file | the importers of the tool | plug-ins |

The built-in items are registered by `builtins.install()` through the same `Registry.register` call an extension uses. The registry of the tool (`REGISTRY`) holds the built-in items only; what a project enables is added to a copy of it (`Registry.layered`) in `manager.runtime(project)`, so two projects never see each other's extensions. The name of a kind is unique: a second registration is refused, so an extension cannot replace a rule, a table or a field of the tool or of another extension. `harness-design-studio extensions DIR` and `api.list_extensions` print the registry of a project with, for each item, its name, version, kind, source (`built-in`, `declarative`, `plugin`), origin, SHA-256, whether it is enabled and whether it is trusted.

`manager.loaded(project)` is the list `(name, version, kind, sha256)` of the enabled data files and loaded plug-ins of a project, in a fixed order. `manager.provenance(project)` is the same list as dictionaries (name, version, kind, file, sha256). It is the `extensions` list of the run record (`core/run_record.py`, `make` fills it when the project has extensions and the caller gives none), and it is written, only when not empty, to `system/provenance.json` and the manifest of the outputs and to the `provenance.json` of `export-data` (`core/open_data.py`).

## Declarative extensions

One file is one JSON document. The format is described once, in `core/extensions/schema.py` (`FILE`, `ENABLED`), and both the check of a file and the JSON Schema written by `harness-design-studio schema` come from that description, so they cannot differ. Top-level keys: `format` (`harness-design-studio-extension`), `format_version` (1), `name`, `version`, `description`, `parameters`, `lookups`, `rules`, `tables`.

- **`parameters`**: a map from a name to `{"value", "unit", "source", "description"}`, read in expressions as `param('name')`.
- **`lookups`**: `{"name", "mode", "key", "unit", "source", "values"}`; `mode` is `exact`, `next_up`, `next_down` or `interpolate`.
- **`rules`**: `{"id", "title", "severity", "applies_to", "when", "condition", "message", "unit", "why", "how", "requirements", "waivable"}`. The tool makes the rule ID `x-<id>`. A rule finds a problem for an object of `applies_to` (`wire`, `connector`, `interface` or `harness`) where `when` is true (or absent) and `condition` is false. The condition is explained by the S1 derivation (`rule-limit`): the equation, the inputs, the actual value, the limit and the margin, which are taken from the comparison that makes the condition false (the left side, the right side, and `limit - actual` for `<` and `<=`, `actual - limit` for `>` and `>=`). The message may use `{object}`, `{actual}`, `{limit}`, `{margin}`, `{over}`, `{unit}`, `{rule}`, `{title}` and any field the rule can read, written `{wire.gauge_awg}`. A condition that is not known for an object (a value it reads is `null`) gives no finding; `by_rule` shows the rule as *not checked* and names the objects.
- **`tables`**: `{"name", "title", "applies_to", "where", "sort", "columns": [{"header", "value", "unit"}]}`. Written as `system/extensions/<name>.csv`, a cell that is not known is `unknown`, a number is written as the other tables write it (`data_num`).

A file is read by `declarative.read_file`: the shape first (every problem with its path), then every expression with the parser, against the fields that exist for the `applies_to` of the rule or table. Every problem is an `ExtIssue` with the file, the line (the line of the key, from `jsonpos.py`, which reads standard JSON and remembers where each key and item is), the path (`rules[0].condition`) and the message. A file with a problem is not applied, and the others are. Problems are reported by `validate` (as warnings), `extensions`, the page Help > Extensions and the finding `x-extension-problem`, which the check adds when something *enabled* is not applied.

`x-extension-problem` is not a rule of the tool and is not part of the 39: it is made by the extension code, only for a project that has an `extensions/` folder with something enabled that is not applied, and it has an explanation like the others.

## The expression language

`core/extensions/expr.py` has a tokenizer, a recursive-descent parser and a tree walker, written for this. Nothing is handed to `eval`, `exec`, `compile` or `ast` (a test reads the module and fails if it did). A name in an expression can only be one of: a literal, a field `scope.name` of the tables below, one of the functions below, or `true`, `false`, `null`, `and`, `or`, `not`, `in`. There is no attribute access, no call of a method, no name that begins with an underscore, no assignment, no comprehension. An expression is at most 600 characters, 120 nodes and 24 levels deep, and `**` takes a whole exponent from 0 to 6.

Grammar, from the loosest binding: `or`; `and`; `not`; one comparison (`==`, `!=`, `<`, `<=`, `>`, `>=`, `in`; not chained); `+` `-`; `*` `/` `%`; unary `-`; `**`; a literal, a list `[a, b]`, a bracket, a field or a call. Texts are written in single or double quotes.

Semantics: a value that is not known is `null`; arithmetic and ordering comparisons with it give `null`; `and`/`or`/`not` follow three-valued logic; a condition that is `null` is *not known*, not passed and not failed. Comparisons use the tool's own tolerance (`sizing.exceeds`: within one billionth of a limit is at the limit, D-LIMIT-TOLERANCE), so an extension rule and a built-in rule agree at the exact limit. A type that does not fit (a text plus a number, a division by zero) is an error for that object only: the rule reports that it could not be worked out, the others go on.

| Function | What it does |
| --- | --- |
| `abs` | absolute value |
| `min` | the smallest of the numbers |
| `max` | the largest of the numbers |
| `round` | round(x, digits): rounded to 0 to 9 decimals |
| `floor` | the whole number below |
| `ceil` | the whole number above |
| `sqrt` | square root |
| `lower` | text in lower case |
| `upper` | text in upper case |
| `startswith` | startswith(text, start): true when the text begins so |
| `endswith` | endswith(text, end): true when the text ends so |
| `contains` | contains(text, part): true when the part is in the text |
| `len` | the length of a text or a list |

| Form | What it does |
| --- | --- |
| `if` | if(condition, then, otherwise): only the chosen branch is worked out |
| `setting` | setting('file.key'): the value a setting has in this project (its default when unset) |
| `param` | param('name'): a parameter of the extension file (`parameters`) |
| `lookup` | lookup('table', key): a value of a lookup table of the extension file |

The first argument of `setting`, `param` and `lookup` must be a text in quotes naming something that exists (a setting of `core/settings.py` that is not a table, a parameter of the file, a lookup table of the file), checked when the file is read.

## Fields

A rule or a table that applies to an object can read the fields of that object and of its surroundings: a `wire` rule reads `wire`, `harness` (the harness of the wire) and `interface`; a `connector` rule reads `connector` and `harness`; an `interface` rule reads `interface`; a `harness` rule reads `harness`. A field of a scope that does not apply is not known. Every field calls the function the tool already uses for the same number, so it cannot disagree with a table or a rule of the tool; a test compares them.

| Field | Unit | Type | What it is |
| --- | --- | --- | --- |
| `wire.id` |  | text | The wire's ID. |
| `wire.harness` |  | text | The ID of the harness the wire is in. |
| `wire.signal` |  | text | The signal the wire carries. |
| `wire.gauge_awg` | AWG | number | The gauge as the AWG number (a larger number is a thinner wire); not known while unset. |
| `wire.mm2` | mm2 | number | The cross-section of the gauge in mm2 (a solid round conductor of the AWG diameter, definition D-AWG). |
| `wire.length_m` | m | number | The length: the wire's own, else the sum of the routing segments between its connectors; not known without either. |
| `wire.colour` |  | text | The wire colour as written. |
| `wire.part` |  | text | The library wire part. |
| `wire.interface` |  | text | The ID of the interface the wire implements. |
| `wire.category` |  | text | The category of the interface type the wire carries (power, ground, signal ...). |
| `wire.construction` |  | text | The construction of the interface type (single, twisted_pair ...). |
| `wire.emc_class` |  | text | The EMC class of the interface type. |
| `wire.current_a` | A | number | The largest current of the interface the wire implements; not known when none is given. |
| `wire.voltage_v` | V | number | The voltage of the interface the wire implements; not known when none is given. |
| `wire.ampacity_limit_a` | A | number | The current the wire's gauge may carry after the bundle and temperature derating (the limit of the rule current-over-wire); not known while a derating value is missing. |
| `wire.voltage_drop_v` | V | number | The voltage the wire drops at the interface current (the figure of the rule voltage-drop); not known while an input is missing. |
| `wire.locked` |  | flag | True when a person set the gauge, colour, part and length and generation keeps them. |
| `connector.id` |  | text | The connector's ID. |
| `connector.name` |  | text | The connector's name. |
| `connector.role` |  | text | box, cable, inline, feedthrough, test or loose (a cable end with no connector chosen yet). |
| `connector.part` |  | text | The library part. |
| `connector.gender` |  | text | male, female or unspecified. |
| `connector.unit` |  | text | The device a box connector belongs to. |
| `connector.harness` |  | text | The harness a cable connector belongs to. |
| `connector.pins` |  | number | The number of pins. |
| `connector.pins_used` |  | number | The number of pins that carry a signal. |
| `interface.id` |  | text | The interface's ID. |
| `interface.name` |  | text | The interface's name. |
| `interface.type` |  | text | The ID of the interface type. |
| `interface.category` |  | text | The category of the type. |
| `interface.construction` |  | text | The construction of the type. |
| `interface.emc_class` |  | text | The EMC class of the type. |
| `interface.redundancy` |  | text | none, nominal or redundant. |
| `interface.max_current_a` | A | number | The largest current; not known when none is given. |
| `interface.voltage_v` | V | number | The voltage; not known when none is given. |
| `interface.requirement` |  | text | The requirement ID the interface traces to. |
| `interface.endpoints` |  | number | The number of ends. |
| `interface.wires` |  | number | The number of wires that implement it, in every harness. |
| `harness.id` |  | text | The harness's ID. |
| `harness.name` |  | text | The harness's name. |
| `harness.revision` |  | text | The revision letter. |
| `harness.status` |  | text | draft, in_review or released. |
| `harness.wires` |  | number | The number of wires. |
| `harness.connectors` |  | number | The number of cable connectors. |
| `harness.length_m` | m | number | The sum of the wire lengths; not known while a wire has none. |
| `harness.mass_g` | g | number | The mass from the library data without the margin; not known while a part has no mass. |

A plug-in can register more fields (`api.field`).

## Python plug-ins

A plug-in is a module. Its name, version, API version and kinds are declared in a literal at the top level, which the tool reads without running the module:

```python
PLUGIN = {
    "name": "my-rules",
    "version": "1.0.0",
    "api": 1,
    "kinds": ["rule", "field"],
    "description": "what it is",
}


def register(api): ...
```

`register(api)` is called once, after the gate (below). The object `api` (`core/extensions/pluginapi.py`) has these calls; everything registered goes into the registry with the plug-in's name, version and hash.

| Call | What it adds |
| --- | --- |
| `api.rule(id, *, title, severity, why, how, check, compares, sources=(), waivable=None, explain=None)` | a design rule. `id` starts with `x-`. `check(project)` yields `api.Hit(object_id, title, key=None)` for each problem. `compares` is one sentence that says what the rule compares; it is the rule's explanation (a rule without it is refused). `explain(project, object_id)` may return a longer statement for one object |
| `api.field(scope, name, fn, *, unit="", doc, kind="number")` | a value expressions can read as `scope.name`; `fn(context)` gets `context.project`, `.harness`, `.wire`, `.connector`, `.interface` and returns a number, a text, a flag or `None` |
| `api.table(name, build, *, title)` | an output table; `build(project)` returns the rows, header first, as texts |
| `api.importer(name, read, *, suffixes=(".csv",), doc)` | a reader; `read(project, path)` returns `PluginImport(ops, rows, notes)`. Run it with `import-plugin`; the ops are applied as one change |

A plug-in that declares a kind and registers another, registers nothing, registers a name that is taken, raises while loading, or is written for another API version is not loaded, and the reason is listed. The kinds a plug-in may add are `rule`, `field`, `table` and `importer`.

Two places are searched: `<project>/extensions/plugins/*.py` (one file per plug-in; links are not followed) and installed packages that declare an entry point in the group `harness_design_studio.plugins` whose value is the module (`my_package.plugin`); the entry point's name must be the plug-in's name. For an installed package the hash is made over all its `.py` files (path and hash of each, in path order) and the declaration is read from the module's source in the package; a package whose files the tool cannot read gets no hash and cannot be trusted.

## Trust

Python code is imported only if **all** of these hold (`plugins.info_for` and `plugins.load`, the only place that imports plug-in code):

1. the project lists the plug-in's name in `extensions/enabled.json`;
2. the user trusted that exact code: the pair (name, SHA-256) is in the trust store (`trust.py`);
3. its declaration is valid and names the API version of the tool.

The trust store is `trusted_plugins.json` in the user's settings folder (`~/.config/harness-design-studio/` or `$XDG_CONFIG_HOME/harness-design-studio/` on Linux, `%APPDATA%\HarnessDesignStudio\` on Windows, replaced by `HARNESS_DESIGN_STUDIO_CONFIG_DIR` when that is set; the tests use it). It holds names, versions, hashes and where the code was; no time and no project path. It is never inside the project, so a repository that is cloned cannot trust itself. A name has one trusted hash at a time: trusting new code of a name takes the trust of the old code away, and a change of the code is another hash, so the old trust does not apply.

The loader does not use the file system twice for one file: the bytes that were hashed are the bytes that run (`_VerifiedLoader` is given them), and no cached bytecode is read or written for a plug-in. For an installed package the hash is computed again just before the import. The check is repeated in every process that loads a project: the helper process of the rule check re-reads the trust store and re-imports the plug-ins itself, so that revoking trust applies to the next check.

The commands and windows: `harness-design-studio trust DIR [NAME] [--revoke] [--yes]` (shows name, version, kinds, file, hash and lines; asks for the name to be typed; `--yes` for scripts; with `--json` and no `--yes` it never asks and never trusts); the question in the editor when a project that enables an untrusted plug-in is opened (`gui/extensions_dialog.py`, `TrustDialog`: the same facts, *Show the code*, the name to be typed, *Not now* as the default); and Help > Extensions.

## Provenance

`manager.provenance(project)` lists every enabled data file (name, version, file, SHA-256) and every loaded plug-in (name, version, file or package, SHA-256) in a fixed order. It is written, only when it is not empty, as `extensions` in `system/provenance.json` and in the manifest of the outputs, and `drc` and its report name each extension in force (`Extension in force: ...`) and count the extension rules in `Rules run`. The key is left out when a project enables nothing, so such a project writes the same bytes as before (`python -m tools.output_hashes --check docs/ui/OUTPUT_HASHES_BASELINE.json` and `python -m tools.numbers_snapshot --check tests/fixtures/numbers/snapshot.json` say *identical*). A finding of an extension rule has the ID prefix `x-`; the Checks tab says in the details of the rule where it comes from, and the derivation names the file (or the plug-in), its version and its hash.

## Stability

The following are stable across minor versions of the tool and change only with `PLUGIN_API_VERSION` or `format_version`: the format of the data files (new optional keys are not a break), the names and meaning of the fields in the table above, the functions of the expression language, the calls of `api` for plug-ins, the entry-point group, the layout of `trusted_plugins.json`, and the keys of `extensions --json`. A field can be added; one is not removed or changed in meaning without a new `format_version`. The wording of messages is not covered.

A plug-in sees the model (`Project` and what it holds) as the rest of the tool does. The model is not frozen the way `harness_design_studio.api` is (see [api-stability](api-stability.md)): a plug-in that reads the model directly can break when the model changes; one that only registers fields, rules, tables and importers through `api`, and reads the project through the scripting interface, is as stable as that interface.

## Security: what this is not

- **There is no sandbox.** A trusted plug-in is Python code running in the process of the tool, with the rights of the user: it can read and write that user's files and use the network. The trust store decides *whether* code runs, not *what* it does.
- The hash proves that the code is the code that was trusted. It does not say that the code is safe.
- Trust is per computer and per user, not per project: a plug-in that was trusted for one project runs in every project of that user that enables it.
- A data file cannot run anything: the expression language reaches fields, arithmetic and a fixed list of functions only. A data file can still write a wrong rule, and a table can name a file in `system/extensions/` only by the name given in the file (names are restricted to lower-case letters, digits, `-` and `_`).
- The tool is internal and offline. An installed plug-in is code from a package; installing it is the first decision, trusting it the second.

## Where the code is

| Module | What it holds |
| --- | --- |
| `core/extensions/registry.py` | `Item`, `Registry`, the kinds, `REGISTRY` |
| `core/extensions/builtins.py` | registers the built-in rules, fields, models, tables and importers |
| `core/extensions/expr.py`, `jsonpos.py` | the expression language, the JSON reader that knows lines |
| `core/extensions/schema.py` | the description of the two files; the check; the JSON Schemas |
| `core/extensions/declarative.py` | reading a file, running a rule, explaining it, making a table, lookup tables |
| `core/extensions/fields.py` | the built-in fields and the scopes |
| `core/extensions/plugins.py`, `pluginapi.py`, `trust.py` | finding and gating plug-ins, the API they get, the trust store |
| `core/extensions/manager.py` | a project's folder: `discover`, `runtime`, the rules, tables, listing, provenance |
| `cli/extensions_cmd.py` | `extensions`, `trust`, `import-plugin` |
| `gui/extensions_dialog.py` | the page and the question in the editor |

## The tests

`tests/test_extensions_expr.py` (the parser refuses `__import__`, attribute access and calls outside the whitelist, and the arithmetic and tolerance are exact), `test_extensions_declarative.py` (a rule fires and does not fire against hand values with the exact actual value, limit and margin; the messages of a broken file name file, line, path and key; a broken file stops nothing; a project that enables nothing is byte-identical), `test_extensions_plugins.py` (a module with a side effect at import is not executed unless enabled and trusted; trusted code loads; a changed byte takes the trust away; a clone cannot trust itself; failures are reported; entry points), `test_extensions_cli.py`, `test_extensions_examples.py` (the examples of `docs/examples/extensions/` work) and `test_extensions_gui.py`. The test that every rule is explained (`tests/test_s1_rules.py`) is extended to the registry in `test_extensions_plugins.py`. This page's list of fields and functions is checked against the code by `test_extensions_docs.py`.

## What is not done

- A plug-in cannot add a calculation model (the choices of `config/model.json` are the tool's) or change a rule, a table or a number of the tool. It adds checks, fields, tables and readers.
- Declarative rules run over one object at a time; a rule that needs two objects together (the wires of a harness against each other) is a plug-in.
- The tool has no sandbox for plug-ins and no signature check of packages.
- An importer registered by a plug-in is run with `import-plugin`; the import wizard of the editor does not list it.

Next: [Extend the tool](../user-manual/extend-the-tool.md), [api-stability](api-stability.md), [architecture](architecture.md), [the models](../models/README.md)
