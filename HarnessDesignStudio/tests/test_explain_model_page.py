# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""`explain` prints the link to the model page (owner decision 15): the code knows the page of
`docs/models/` of each kind of derivation (`core/derive_kinds.py`), and now the output says it. The
text ends with `Model page: docs/models/<page>.md`; `explain --json` has the key `model_page` on each
derivation. The files of `explain --all` (`derivations.json`) do not have the key."""

import json
from pathlib import Path

import pytest

from harness_design_studio import api
from harness_design_studio.cli.jsonout import SHAPES
from harness_design_studio.cli.main import main
from harness_design_studio.core import templates
from harness_design_studio.core.derive import Derivation, explain_object
from harness_design_studio.core.derive_kinds import KINDS, page_of

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def flat(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("mp") / "flat"
    templates.create_project(folder, "flatsat")
    return folder


def _explain(capsys: pytest.CaptureFixture[str], folder: Path, obj: str, *more: str) -> str:
    capsys.readouterr()
    assert main(["explain", str(folder), obj, *more]) == 0
    return capsys.readouterr().out


def test_every_kind_has_a_model_page_that_exists() -> None:
    for kind in KINDS:
        d = Derivation(kind, "x", "q", None, "", "e")
        assert d.model_page == f"docs/models/{page_of(kind)}", kind
        assert (ROOT / d.model_page).is_file(), kind
    assert Derivation("x-not-a-kind", "x", "q", None, "", "e").model_page == ""


def test_the_text_of_a_part_ends_with_the_one_model_page_of_its_kind(
    flat: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _explain(capsys, flat, "EX-WIRE-SINGLE")
    assert out.rstrip("\n").splitlines()[-1] == "Model page: docs/models/bom.md"
    assert out.count("Model page:") == 1


def test_the_text_of_a_test_names_the_test_limits_page(
    flat: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _explain(capsys, flat, "W001.T001")
    assert out.rstrip("\n").splitlines()[-1] == "Model page: docs/models/test-limits.md"


def test_the_text_of_a_wire_names_each_page_once_in_the_order_of_the_derivations(
    flat: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _explain(capsys, flat, "W004-003")
    lines = out.rstrip("\n").splitlines()
    pages = [ln for ln in lines if ln.startswith("Model page: ")]
    assert lines[-len(pages) :] == pages  # they are the last lines, after every derivation
    names = [ln.removeprefix("Model page: ") for ln in pages]
    assert len(names) == len(set(names))
    assert names[:3] == [
        "docs/models/wire-length.md", "docs/models/wire-sizing.md", "docs/models/mass.md",
    ]  # fmt: skip
    found = explain_object(api.load_project(flat), "W004-003")
    assert set(names) == {d.model_page for d in found}
    assert all((ROOT / n).is_file() for n in names)


def test_the_page_comes_after_the_history_when_the_project_has_a_journal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "j"
    templates.create_project(folder, "flatsat")
    assert main(["journal", str(folder), "--start"]) == 0
    assert main(["override", str(folder), "W004-003", "colour", "pink", "--reason", "customer request"]) == 0  # fmt: skip
    out = _explain(capsys, folder, "W004-003")
    assert "History of W004-003" in out
    assert out.rstrip("\n").splitlines()[-1].startswith("Model page: docs/models/")
    assert out.index("History of W004-003") < out.index("Model page:")


def test_json_has_the_key_on_every_derivation_in_the_listed_order(
    flat: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    found = json.loads(_explain(capsys, flat, "W004-003", "--json"))
    assert found
    shape = list(SHAPES["explain OBJECT"])
    for d in found:
        # `text` (a result that is a text) comes after `missing`, and the new key is the last
        assert [k for k in d if k != "text"] == shape, d["id"]
        assert list(d)[-1] == "model_page"
        assert d["model_page"] == f"docs/models/{page_of(d['id'])}"
        assert (ROOT / d["model_page"]).is_file()
    assert {d["id"]: d["model_page"] for d in found}["gauge"] == "docs/models/wire-sizing.md"


def test_the_files_of_explain_all_do_not_have_the_key(flat: Path, tmp_path: Path) -> None:
    written = api.write_derivations(flat, tmp_path / "d")
    assert written.count > 0
    text = (tmp_path / "d" / "derivations.json").read_text(encoding="utf-8")
    assert "model_page" not in text
    project = api.load_project(flat)
    assert all("model_page" not in d.to_dict() for d in explain_object(project, "W004-003"))
    assert all("model_page" in d.to_explain_dict() for d in explain_object(project, "W004-003"))
