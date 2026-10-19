"""A change of the user interface must leave every file the tool writes alone (UI overhaul M6): the
SHA-256 of each output file of each packaged example equals the one made with release 1.2.0."""

import json

from tools.output_hashes import STORED, differences, hashes


def test_every_written_file_of_every_example_is_byte_identical_to_release_1_2_0() -> None:
    then = json.loads(STORED.read_text(encoding="utf-8"))
    assert differences(hashes(), then) == []
    assert sum(len(v) for v in then.values()) > 500  # (the file is not an empty promise)
