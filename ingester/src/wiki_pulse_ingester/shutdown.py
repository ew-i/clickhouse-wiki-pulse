import time


class Shutdown:
    """Shutdown flag set from a signal handler.

    Deliberately lock-free: threading.Event.set() takes a lock that the interrupted
    main thread may already hold, so calling it from a handler can deadlock.
    """

    def __init__(self) -> None:
        self.requested = False

    def request(self, *_signal_args: object) -> None:
        self.requested = True

    def pause(self, seconds: float) -> None:
        if not self.requested:
            time.sleep(seconds)
