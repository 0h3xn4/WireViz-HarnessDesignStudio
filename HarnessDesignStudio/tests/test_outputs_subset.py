"""SC-12 investigation: `build_outputs(harness_ids=...)` is for tests and tools, not for a partial
export into the outputs folder. These tests record why, so nobody builds an export dialog on
`write_outputs` with a subset without first changing the verifier and the manifest rules.

If one of them starts to fail because the behaviour was deliberately changed (a safe `select=`),
rewrite it to state the new guarantee."""

from pathlib import Path

from harness_design_studio.core.outputs.build import (
    build_outputs,
    damaged_files,
    exported_harnesses,
    outputs_content_state,
    write_outputs,
)
from harness_design_studio.core.outputs.verify import read_folder, verify_outputs
from tests.test_change_control import full


def test_a_subset_changes_the_system_roll_ups() -> None:
    p = full()
    first, second = sorted(p.harnesses)[:2]
    whole = build_outputs(p)
    part = build_outputs(p, harness_ids=[first])
    assert {k for k in part.files if k.startswith("harnesses/")} == {
        k for k in whole.files if k.startswith(f"harnesses/{first}/")
    }
    changed = {k for k in part.files if k.startswith("system/") and part.files[k] != whole.files[k]}
    assert {"system/bom.csv", "system/mass_length.csv"} <= changed  # they list only the subset
    assert second not in part.files["system/mass_length.csv"].decode()


def test_the_verifier_expects_every_harness_so_a_subset_is_reported_as_wrong() -> None:
    p = full()
    part = build_outputs(p, harness_ids=[sorted(p.harnesses)[0]])
    codes = {i.code for i in verify_outputs(p, part.files).issues}
    assert {"out_missing", "out_bom", "out_mass"} <= codes


def test_writing_a_subset_over_a_full_export_deletes_the_other_harnesses(tmp_path: Path) -> None:
    p = full()
    first = sorted(p.harnesses)[0]
    folder = tmp_path / "outputs"
    write_outputs(p, folder)
    assert exported_harnesses(folder) == set(p.harnesses)
    write_outputs(p, folder, build_outputs(p, harness_ids=[first]))
    assert exported_harnesses(folder) == {first}  # the files of the others are gone
    # and the manifest still calls the folder current, though it no longer holds the whole design
    assert outputs_content_state(p, folder) == "current"
    assert damaged_files(folder) == []
    assert any(i.code == "out_missing" for i in verify_outputs(p, read_folder(folder)).issues)
