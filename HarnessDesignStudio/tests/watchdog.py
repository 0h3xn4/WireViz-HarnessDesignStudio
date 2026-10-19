"""A time limit for a test that must not hang: SIGALRM where there is one, a timer elsewhere."""

import _thread
import signal
import threading
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def watchdog(seconds: int, message: str) -> Iterator[None]:
    """Raise AssertionError(message) if the block runs longer than `seconds`."""
    if hasattr(signal, "SIGALRM"):

        def alarm(*_a: object) -> None:
            raise AssertionError(message)

        previous = signal.signal(signal.SIGALRM, alarm)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
        return
    # Windows has no SIGALRM: a timer interrupts the main thread (works for Python code that loops)
    fired = threading.Event()

    def interrupt() -> None:
        fired.set()
        _thread.interrupt_main()

    timer = threading.Timer(seconds, interrupt)
    timer.daemon = True
    timer.start()
    try:
        yield
    except KeyboardInterrupt:
        if fired.is_set():
            raise AssertionError(message) from None
        raise
    finally:
        timer.cancel()
