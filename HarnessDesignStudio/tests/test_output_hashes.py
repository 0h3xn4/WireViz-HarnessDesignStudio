"""A change that must not touch the written files leaves every file the tool writes alone (UI overhaul M6,
renewed for release 1.10, D-182): the SHA-256 of each output file of each packaged example equals the one
in `docs/ui/OUTPUT_HASHES_BASELINE.json`, apart from the version stamp the files carry
(`tools.output_hashes.as_in_base_version`). A change that does touch them renews the baseline on purpose."""

import json

from tools.output_hashes import STORED, differences, hashes


def test_every_written_file_of_every_example_is_byte_identical_to_the_baseline() -> None:
    then = json.loads(STORED.read_text(encoding="utf-8"))
    assert differences(hashes(), then) == []
    assert sum(len(v) for v in then.values()) > 500  # (the file is not an empty promise)
