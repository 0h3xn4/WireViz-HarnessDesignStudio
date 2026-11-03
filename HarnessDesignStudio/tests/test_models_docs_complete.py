"""D-191, S10: no model, rule or assumption of the tool is left without a page.

`docs/models/` explains every calculation. This test ties it to the code, so that adding something to
the code without documenting it fails here:

(a) every registered rule (the 39 of `drc.RULES`, which the extension registry lists as its built-in
    items, and the rules of the editor's own checks) has a section in `docs/RULES.md`, an explanation
    (`derive_rules.INFO`) and a page of `docs/models/` that a reader of the explanation is sent to;
(b) every kind of derivation (`core/derive_kinds.py`) maps to a page that exists, names the kind and
    is written in the order of the other pages, with a worked example that `explain` repeats;
(c) every assumption of `core/assumptions.py` is described on a page of `docs/models/`, every ID a
    page names exists, and a setting that parameterises an assumption is on a page that names it;
(d) every setting of `core/settings.py` is in `docs/CONFIG.md` under its file, and every key and
    choice value of `model.json` is on the page of the selectable models;
(e) every definition (`D-*`) is listed, with its text, on a page;
(f) the contents page links every page of the folder, and every link of it leads to a page;
and the pages that finish the work (the final audit and the trace results) are linked from the places
that must name them. The built-in tables and importers of the registry are in the output and import
references."""

import re
from pathlib import Path

import pytest

from harness_design_studio.core import settings
from harness_design_studio.core.assumptions import ASSUMPTIONS
from harness_design_studio.core.derive import EXPLAINABLE_RULES, OTHER_RULES
from harness_design_studio.core.derive_kinds import KINDS, page_of, page_of_rule
from harness_design_studio.core.derive_rules import INFO
from harness_design_studio.core.drc import RULES
from harness_design_studio.core.extensions.builtins import install
from harness_design_studio.core.extensions.registry import REGISTRY

DOCS = Path(__file__).resolve().parent.parent / "docs"
MODELS = DOCS / "models"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _pages() -> dict[str, str]:
    return {p.name: _read(p) for p in sorted(MODELS.glob("*.md"))}


PAGES = _pages()
CONTENT_PAGES = {n: t for n, t in PAGES.items() if n != "README.md"}
RULES_MD = _read(DOCS / "RULES.md")
CONFIG_MD = _read(DOCS / "CONFIG.md")
ALL_RULES = [r.id for r in RULES] + list(OTHER_RULES)


def _section(text: str, heading: str) -> str:
    """The text of the section whose `## heading` line contains `heading`, up to the next one."""
    parts = re.split(r"^## ", text, flags=re.M)
    return next(p for p in parts[1:] if heading in p.splitlines()[0])


# ---- (a) rules --------------------------------------------------------------------------------------


def test_a_every_registered_rule_has_a_row_in_the_rule_reference() -> None:
    install()
    registered = [i.name for i in REGISTRY.items("rule")]
    assert registered == [r.id for r in RULES] and len(registered) == 39
    for rule_id in ALL_RULES:
        if (
            rule_id == "verify-mismatch"
        ):  # reported by the independent verifier, in the closing section
            assert f"`{rule_id}`" in RULES_MD.split("## Also reported as errors")[1], rule_id
        else:
            assert f"| `{rule_id}` |" in RULES_MD, f"{rule_id} has no row in docs/RULES.md"
    # the reference is for built-in rules only: an extension's rules are not in it
    assert not re.search(r"\| `x-[a-z-]+` \|", RULES_MD)


def test_a_every_rule_has_an_explanation_and_a_page_to_be_sent_to() -> None:
    assert set(INFO) == set(ALL_RULES) == set(EXPLAINABLE_RULES)
    rule_limits = PAGES["rule-limits.md"]
    for rule_id in ALL_RULES:
        info = INFO[rule_id]
        assert info.form in ("limit", "yes-no") and info.compares, rule_id
        page = page_of_rule(rule_id)
        assert (MODELS / page).is_file(), (rule_id, page)
        assert f"`{rule_id}`" in rule_limits, f"{rule_id} is not in docs/models/rule-limits.md"
        # the page the explanation names is a page that talks about the rule
        assert f"`{rule_id}`" in PAGES[page] or rule_id in PAGES[page], (rule_id, page)
        assert page_of_rule(rule_id) in {page_of(k) for k in KINDS}, rule_id


def test_a_the_three_rules_of_step_one_are_sent_to_their_own_models() -> None:
    assert page_of_rule("current-over-wire") == "wire-sizing.md"
    assert page_of_rule("voltage-drop") == "wire-sizing.md"
    assert page_of_rule("current-over-contact") == "contact-current.md"
    assert (
        page_of_rule("spare-pins-low") == "rule-limits.md"
    )  # every other rule: the page of the limits
    with pytest.raises(KeyError):
        page_of_rule("x-a-rule-of-an-extension")  # an extension's rule is not a rule of the tool


def test_a_the_built_in_tables_and_readers_of_the_registry_are_in_the_references() -> None:
    install()
    outputs = _read(DOCS / "OUTPUTS.md")
    imports = _read(DOCS / "IMPORTS.md")
    for table in REGISTRY.items("table"):
        assert table.name in outputs or table.name.replace("_", "-") in outputs, table.name
    for reader in REGISTRY.items("importer"):
        assert f"import-{reader.name}" in imports or reader.name in imports, reader.name
    selectable = PAGES["selectable-models.md"]
    for model in REGISTRY.items("model"):
        assert model.name.removeprefix("model.") in selectable, model.name


# ---- (b) kinds of derivation -------------------------------------------------------------------------


def test_b_every_kind_of_derivation_has_a_page_that_names_it_and_is_written_in_the_usual_order() -> (
    None
):
    assert len(KINDS) >= 20
    for kind, (page, what) in KINDS.items():
        assert what, kind
        assert (MODELS / page).is_file(), (kind, page)
        text = PAGES[page]
        assert f"`{kind}`" in text, f"{page} does not name the kind `{kind}`"
        for heading in (
            "## Contents",
            "## What the tool decides",
            "## A worked example",
            "## What the model does not do",
        ):
            assert heading in text, f"{page} has no '{heading}'"
        assert "explain" in _section(text, "A worked example").lower(), (
            f"the worked example of {page} says no command that repeats it"
        )


def test_b_every_derivation_page_says_what_it_does_not_do_and_cites_standards_by_id_and_title_only() -> (
    None
):
    for name, text in CONTENT_PAGES.items():
        if name in {p for p, _w in KINDS.values()}:
            assert "does not" in _section(text, "What the model does not do"), name
        # a clause is cited by ID, never quoted: no long quotation marks around a sentence of a standard
        assert not re.search(r"ECSS-[A-Z]-ST-[0-9A-Z-]+C?[^.\n]{0,40}\"[^\"]{120,}\"", text), name


# ---- (c) assumptions ---------------------------------------------------------------------------------


def test_c_every_assumption_is_described_on_a_page_and_every_named_assumption_exists() -> None:
    assert len(ASSUMPTIONS) >= 31
    for a in ASSUMPTIONS:
        where = [n for n, t in CONTENT_PAGES.items() if re.search(rf"\b{re.escape(a)}\b", t)]
        assert where, f"{a} is described on no page of docs/models/"
        assert re.search(rf"\b{re.escape(a)}\b", PAGES["README.md"]), (
            f"{a} is not in the list of the README"
        )
    named = set(re.findall(r"\bA-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b", "\n".join(PAGES.values())))
    assert named <= set(ASSUMPTIONS), (
        f"a page names an assumption that does not exist: {sorted(named - set(ASSUMPTIONS))}"
    )


def test_c_a_setting_that_parameterises_an_assumption_is_on_a_page_that_names_the_assumption() -> (
    None
):
    for s in settings.SETTINGS:
        if not s.assumption:
            continue
        pages = [n for n, t in CONTENT_PAGES.items() if s.assumption in t]
        assert any(s.key in CONTENT_PAGES[n] for n in pages), (
            f"{s.id} parameterises {s.assumption}, but no page that names it names the key"
        )


# ---- (d) settings and choices ------------------------------------------------------------------------


def test_d_every_setting_is_in_the_configuration_reference_under_its_file() -> None:
    assert (DOCS / "CONFIG.md").is_file()
    for s in settings.SETTINGS:
        sections = [
            p
            for p in re.split(r"^## ", CONFIG_MD, flags=re.M)[1:]
            if f"`{s.file}.json`" in p.splitlines()[0]
        ]
        assert sections, f"docs/CONFIG.md has no section for {s.file}.json"
        optional = _section(CONFIG_MD, "Optional values from the supplied standards")
        assert any(f"`{s.key}`" in p for p in sections) or f"`{s.key}`" in optional, (
            f"{s.id} is not described under {s.file}.json in docs/CONFIG.md"
        )


def test_d_every_key_and_choice_of_the_model_file_is_on_the_page_of_the_selectable_models() -> None:
    page = PAGES["selectable-models.md"]
    model_keys = [s for s in settings.SETTINGS if s.file == "model"]
    assert len(model_keys) >= 14
    table = [line for line in page.splitlines() if line.startswith("| `")]
    for s in model_keys:
        row = next((line for line in table if line.startswith(f"| `{s.key}` |")), None)
        assert row is not None, f"model.{s.key} has no row in the table of every key of model.json"
        for choice in s.choices:
            assert f"`{choice}`" in page, f"model.{s.key}: the value {choice} is not on the page"
        default = s.default
        if isinstance(default, tuple):
            assert all(name in row for name in default), (s.key, row)
        elif isinstance(default, float):
            assert f"`{default:g}`" in row, (s.key, default, row)
        elif default is not None:
            assert f"`{default}`" in row, (s.key, default, row)


# ---- (e) definitions ---------------------------------------------------------------------------------


def test_e_every_definition_is_listed_with_its_text_on_a_page() -> None:
    assert len(settings.DEFINITIONS) >= 6
    page = PAGES["definitions.md"]
    for d in settings.DEFINITIONS:
        assert re.search(rf"^## `?{re.escape(d.id)}`?", page, re.M) or f"`{d.id}`" in page, d.id
        assert d.title in page, f"the title of {d.id} is not on the page"
        assert d.where.split(" (")[0] in page, f"the place of {d.id} ({d.where}) is not on the page"
    named = set(re.findall(r"\bD-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\b", "\n".join(PAGES.values())))
    assert named <= {d.id for d in settings.DEFINITIONS}, sorted(
        named - {d.id for d in settings.DEFINITIONS}
    )


# ---- (f) the contents page ---------------------------------------------------------------------------


def test_f_the_contents_page_links_every_page_and_every_page_is_linked() -> None:
    readme = PAGES["README.md"]
    linked = set(re.findall(r"\]\(([A-Za-z0-9_-]+\.md)(?:#[^)]*)?\)", readme))
    pages = set(CONTENT_PAGES)
    assert pages <= linked, f"pages that the contents page does not link: {sorted(pages - linked)}"
    for name in linked:
        assert (MODELS / name).is_file(), f"README.md links {name}, which is not in the folder"
    # and the table of the README gives each content page a row with the command that shows it
    table = _section(readme, "The models")
    for name in pages:
        if name == "definitions.md":
            continue
        assert f"({name})" in table, f"{name} has no row in the table of the models"


def test_f_the_final_audit_and_the_trace_are_linked_where_a_reader_looks_for_them() -> None:
    for page in ("transparency_final_audit.md", "transparency_trace_results.md"):
        assert (DOCS / page).is_file(), page
    for where in (DOCS / "README.md", MODELS / "README.md", DOCS / "transparency_plan.md"):
        assert "transparency_final_audit.md" in _read(
            where
        ) or "(../transparency_final_audit.md" in _read(where), where
    assert "transparency_trace_results.md" in _read(DOCS / "transparency_final_audit.md")
