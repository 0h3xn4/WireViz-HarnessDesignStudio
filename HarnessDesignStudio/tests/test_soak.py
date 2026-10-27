"""M7: a short soak run in CI; `python -m tools.soak 5000 <seed>` runs the long one."""

from pathlib import Path
from typing import Any

import pytest

from tools.soak import run_soak


@pytest.mark.slow
@pytest.mark.parametrize("seed", [11, 12])
def test_random_editing_keeps_every_invariant(seed: int, tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = run_soak(400, seed, tmp_path)
    assert r.steps == 400 and r.applied > 100 and r.generations > 5 and r.roundtrips >= 7


def test_a_redo_that_does_not_restore_the_model_is_caught(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The undo-then-redo check once compared the model with nothing and could not fail."""

    def broken_redo(self: Any) -> str:
        step = self._redo.pop()  # the step moves back to the undo list but is not applied
        self._undo.append(step)
        return str(step.label)

    monkeypatch.setattr("tools.soak.History.redo", broken_redo)
    with pytest.raises(AssertionError, match="undo then redo"):
        run_soak(400, 11, tmp_path)
