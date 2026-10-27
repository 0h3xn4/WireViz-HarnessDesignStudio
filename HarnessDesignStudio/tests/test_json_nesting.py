"""Deeply nested JSON is refused with the same answer on every Python version (3.14 reads it)."""

import pytest

from harness_design_studio.core.io import canonical
from harness_design_studio.core.io.canonical import MAX_NESTING, loads_strict


def nested(depth: int) -> bytes:
    return ("[" * depth + "]" * depth).encode()


def test_a_file_nested_deeper_than_the_limit_is_refused() -> None:
    with pytest.raises(RecursionError):
        loads_strict(nested(MAX_NESTING + 1))
    with pytest.raises(RecursionError):
        loads_strict(b"[" * 100000)  # not even closed: refused before it is parsed


def test_a_file_at_the_limit_is_read() -> None:
    assert loads_strict(nested(MAX_NESTING)) is not None


def test_objects_count_like_lists() -> None:
    deep = b'{"a":' * (MAX_NESTING + 1) + b"1" + b"}" * (MAX_NESTING + 1)
    with pytest.raises(RecursionError):
        loads_strict(deep)


def test_brackets_inside_text_are_not_nesting() -> None:
    text = '{"name": "' + "[" * 5000 + '", "other": "\\"' + "{" * 5000 + '"}'
    assert loads_strict(text.encode())["name"] == "[" * 5000


def test_a_big_flat_file_is_not_deep() -> None:
    rows = ",".join(f'{{"id": "W{i}", "pins": ["1", "2"]}}' for i in range(3000))
    assert len(loads_strict(f'{{"wires": [{rows}]}}'.encode())["wires"]) == 3000


def test_the_quick_count_and_the_exact_count_agree() -> None:
    for depth in (MAX_NESTING - 1, MAX_NESTING, MAX_NESTING + 1):
        assert canonical._nested_too_deeply(nested(depth).decode()) is (depth > MAX_NESTING)
