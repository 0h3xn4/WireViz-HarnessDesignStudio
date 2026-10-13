"""REQ-LOC-01: messages about damaged project files say where (file, line, column) and never quote content."""

from __future__ import annotations

import json
from pathlib import Path

from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.samples import mini3


def saved(tmp_path: Path) -> Path:
    save_project(mini3(), tmp_path / "p")
    return tmp_path / "p"


def test_a_syntax_error_names_line_and_column(tmp_path: Path) -> None:
    root = saved(tmp_path)
    f = root / "logical" / "interface_types.json"
    text = f.read_text(encoding="utf-8").splitlines()
    text[4] = text[4] + " SECRET-VALUE"  # breaks the syntax on line 5
    f.write_text("\n".join(text), encoding="utf-8")
    result = load_project(root)
    bad = [i for i in result.issues if i.code == "invalid_json"]
    assert bad and "at line 5, column" in bad[0].message
    assert "SECRET-VALUE" not in bad[0].message  # content is never quoted
    assert bad[0].location == "logical/interface_types.json"


def test_a_bad_byte_names_its_position(tmp_path: Path) -> None:
    root = saved(tmp_path)
    f = root / "logical" / "interface_types.json"
    f.write_bytes(b'{"x": "\xff"}')
    bad = [i for i in load_project(root).issues if i.code == "invalid_json"]
    assert bad and "UTF-8 at byte" in bad[0].message


def test_a_set_aside_object_is_located_by_line(tmp_path: Path) -> None:
    root = saved(tmp_path)
    f = next((root / "logical" / "units").glob("*.json"))
    data = json.loads(f.read_text(encoding="utf-8"))
    victim = data["units"][0]["id"]
    data["units"][0]["zone"] = 12345  # wrong type
    f.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    text = f.read_text(encoding="utf-8")
    line = text[: text.index(f'"id": "{victim}"')].count("\n") + 1
    msgs = [i.message for i in load_project(root).issues if i.code == "quarantined"]
    assert msgs and f"(line {line})" in msgs[0], msgs
    assert "12345" not in msgs[0]
