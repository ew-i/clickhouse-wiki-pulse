import os
import signal
import time

from wiki_pulse_ingester.shutdown import Shutdown


def test_signal_handler_sets_the_flag():
    shutdown = Shutdown()
    previous = signal.signal(signal.SIGUSR1, shutdown.request)
    try:
        os.kill(os.getpid(), signal.SIGUSR1)
    finally:
        signal.signal(signal.SIGUSR1, previous)

    assert shutdown.requested


def test_pause_is_skipped_once_shutdown_is_requested():
    shutdown = Shutdown()
    shutdown.request()

    started = time.monotonic()
    shutdown.pause(10)

    assert time.monotonic() - started < 1
