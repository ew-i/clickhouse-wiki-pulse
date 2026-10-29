import pytest
import requests

from wiki_pulse_ingester import __main__ as app
from wiki_pulse_ingester.clickhouse import Batcher
from wiki_pulse_ingester.shutdown import Shutdown


class FakeStream:
    """Each call to payloads() is one connection, played from the next script."""

    def __init__(self, *connections):
        self._connections = list(connections)
        self.connects = 0

    def payloads(self):
        self.connects += 1
        return self._connections.pop(0)()


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(app, "RETRY_DELAY_SECONDS", 0)


@pytest.fixture
def written():
    return []


@pytest.fixture
def batcher(written):
    return Batcher(written.append, max_rows=100, max_seconds=60)


def titles(batches):
    return [[change.title for change in batch] for batch in batches]


def test_shutdown_stops_reading_and_flushes_the_partial_batch(make_payload, batcher, written):
    shutdown = Shutdown()

    def connection():
        yield make_payload("a")
        shutdown.request()
        yield make_payload("b")
        yield make_payload("never read")

    app.run(FakeStream(connection), batcher, shutdown)

    assert titles(written) == [["a", "b"]]


def test_dropped_stream_flushes_then_reconnects(make_payload, batcher, written):
    shutdown = Shutdown()

    def dropped():
        yield make_payload("a")
        raise requests.ConnectionError("reset by peer")

    def resumed():
        yield make_payload("b")
        shutdown.request()

    stream = FakeStream(dropped, resumed)
    app.run(stream, batcher, shutdown)

    assert stream.connects == 2
    assert titles(written) == [["a"], ["b"]]


def test_unexpected_error_still_flushes_the_buffered_batch(make_payload, batcher, written):
    def crashing():
        yield make_payload("a")
        raise RuntimeError("bug")

    with pytest.raises(RuntimeError):
        app.run(FakeStream(crashing), batcher, Shutdown())

    assert titles(written) == [["a"]]
