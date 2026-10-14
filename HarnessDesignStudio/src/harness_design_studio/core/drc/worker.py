"""Child process that runs the design rule check, so the editor's interpreter stays free.

Protocol on stdin/stdout (binary, both directions): an 8-byte big-endian length, then a pickle.
The parent sends a project in pieces (see project_messages) and gets the findings back in pieces,
then ("done",), or ("error", traceback text). The child
exits when stdin closes, so it never outlives the editor. Only pipes are used (no network).
Both ends are this program's own code and data, which is why pickle is fine here.
"""

import contextlib
import os
import pickle
import struct
import sys
import traceback
from collections.abc import Iterator
from copy import copy
from typing import IO

from harness_design_studio.core.model import Project

_HEADER = struct.Struct(">Q")
MAX_MESSAGE = 1 << 31  # refuse absurd lengths from a corrupted pipe


def send(stream: IO[bytes], obj: object) -> None:
    data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    stream.write(_HEADER.pack(len(data)))
    stream.write(data)
    stream.flush()


def receive(stream: IO[bytes]) -> object | None:
    """The next message, or None when the other side closed the pipe."""
    head = _read_exactly(stream, _HEADER.size)
    if head is None:
        return None
    (size,) = _HEADER.unpack(head)
    if size > MAX_MESSAGE:
        raise ValueError("message too large")
    body = _read_exactly(stream, size)
    if body is None:
        return None
    message: object = pickle.loads(body)  # noqa: S301 (our own process on the other end)
    return message


def _read_exactly(stream: IO[bytes], n: int) -> bytes | None:
    chunks: list[bytes] = []
    while n > 0:
        chunk = stream.read(n)
        if not chunk:
            return None
        chunks.append(chunk)
        n -= len(chunk)
    return b"".join(chunks)


# Collections sent piece by piece, with how many entries go in one message. One message is one
# pickle call, which holds the sender's interpreter lock; small messages let the editor's thread
# (in the same process as the sender) run in between.
CHUNKS = {
    "parts": 300, "interface_types": 300, "units": 300, "interfaces": 300, "connectors": 300,
    "harnesses": 10, "placements": 300, "waivers": 300, "baselines": 50, "changelog": 300,
}  # fmt: skip
FINDING_CHUNK = 1000


def project_messages(project: Project) -> Iterator[tuple[object, ...]]:
    """The messages that carry a project: a header without the big collections, their entries in
    pieces, then "go"."""
    header = copy(project)
    for name in CHUNKS:
        setattr(header, name, {})
    yield ("begin", header)
    for name, size in CHUNKS.items():
        items = list(getattr(project, name).items())
        for start in range(0, len(items), size):
            yield ("items", name, items[start : start + size])
    yield ("go",)


def main() -> int:
    from harness_design_studio.core import drc

    # Findings go back over a private copy of stdout; anything else that prints must not corrupt it.
    out = os.fdopen(os.dup(sys.stdout.fileno()), "wb")
    sys.stdout = sys.stderr
    with contextlib.suppress(OSError):
        os.nice(5)  # the editor matters more than its background check
    stdin = sys.stdin.buffer
    project: Project | None = None
    while True:
        try:
            msg = receive(stdin)
        except (ValueError, pickle.UnpicklingError, EOFError):
            return 1
        if msg is None:
            return 0
        if not isinstance(msg, tuple) or not msg:
            return 1
        try:
            if msg[0] == "begin":
                project = msg[1]
            elif msg[0] == "items" and project is not None:
                getattr(project, msg[1]).update(msg[2])
            elif msg[0] == "go" and project is not None:
                found = drc.run(project)
                for start in range(0, len(found), FINDING_CHUNK):
                    send(out, ("findings", found[start : start + FINDING_CHUNK]))
                send(out, ("done",))
            else:
                return 1
        except BrokenPipeError:
            return 0
        except Exception:  # reported to the editor, which shows nothing but keeps working
            try:
                send(out, ("error", traceback.format_exc()))
            except BrokenPipeError:
                return 0


if __name__ == "__main__":
    raise SystemExit(main())
