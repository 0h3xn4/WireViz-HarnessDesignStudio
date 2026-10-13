"""REQ-PROV-01: every set of outputs says which tool, design and settings made it."""

from __future__ import annotations

import json

from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import mini3, sat15


def test_provenance_names_tool_design_library_and_settings() -> None:
    p = mini3()
    out = build_outputs(p)
    doc = json.loads(out.files["system/provenance.json"])
    assert doc["tool_version"] == out.stamp.version and doc["model_hash"] == out.stamp.model_hash
    assert doc["library"]["parts"] == len(p.parts)
    assert doc["settings"]["derating"]["placeholder"] is True
    assert len(doc["settings"]["derating"]["values_sha256_16"]) == 16
    assert "WireViz is not used" in doc["export_notes"]


def test_provenance_is_deterministic_and_follows_the_settings() -> None:
    p = sat15()
    generate_project(p)
    a = build_outputs(p).files["system/provenance.json"]
    assert build_outputs(p).files["system/provenance.json"] == a
    old = p.config["derating"]
    from harness_design_studio.core.model import ConfigFile

    p.config["derating"] = ConfigFile(
        name="derating",
        placeholder=old.placeholder,
        values={**old.values, "max_voltage_drop_v": 1.0},
    )
    b = build_outputs(p).files["system/provenance.json"]
    assert json.loads(a)["settings"]["derating"] != json.loads(b)["settings"]["derating"]


def test_the_output_verifier_checks_the_provenance() -> None:
    p = sat15()
    generate_project(p)
    files = dict(build_outputs(p).files)
    assert verify_outputs(p, files).ok
    doc = json.loads(files["system/provenance.json"])
    doc["settings"]["derating"]["placeholder"] = False
    files["system/provenance.json"] = json.dumps(doc).encode()
    assert "out_provenance" in [i.code for i in verify_outputs(p, files).issues]
    del files["system/provenance.json"]
    assert "out_missing" in [i.code for i in verify_outputs(p, files).issues]
