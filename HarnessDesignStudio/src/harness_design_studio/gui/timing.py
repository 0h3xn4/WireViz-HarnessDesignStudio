"""Optional timing log of the interface: set `HARNESS_UI_TIMING=1` and every timed step writes one
line with its duration to the standard error stream (for example `[ui-timing] theme apply 64 ms`).

Nothing is written, and nothing but a clock read is paid, when the variable is not set. Steps that
take longer than 50 ms on the GUI thread are the ones to move to a worker (docs/ui/PERF_BASELINE.md).
"""

import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

SLOW_MS = (
    50  # the longest a step may take on the GUI thread (docs/developer/agent/ui-design-rules.md)
)


def enabled() -> bool:
    return os.environ.get("HARNESS_UI_TIMING") == "1"


@contextmanager
def timed(label: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        if enabled():
            ms = (time.perf_counter() - start) * 1000
            flag = "  SLOW" if ms > SLOW_MS else ""
            print(f"[ui-timing] {label} {ms:.0f} ms{flag}", file=sys.stderr)
