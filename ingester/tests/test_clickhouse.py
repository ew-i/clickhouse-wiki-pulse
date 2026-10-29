from dataclasses import astuple

import pytest
from clickhouse_connect.driver.exceptions import DatabaseError, OperationalError

from wiki_pulse_ingester import clickhouse
from wiki_pulse_ingester.clickhouse import MAX_ATTEMPTS, Batcher, ClickHouseWriter, retry
from wiki_pulse_ingester.model import COLUMNS
from wiki_pulse_ingester.shutdown import Shutdown


class FakeClient:
    def __init__(self, *failures):
        self._failures = list(failures)
        self.inserts = []
        self.attempts = 0
        self.settings = None

    def insert(self, table, rows, column_names, settings):
        self.attempts += 1
        if self._failures:
            raise self._failures.pop(0)
        self.inserts.append((table, rows, column_names))
        self.settings = settings


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(clickhouse, "RETRY_DELAY_SECONDS", 0)


def titles(batches):
    return [[change.title for change in batch] for batch in batches]


def failing(*errors, then="ok"):
    outcomes = iter([*errors, then])

    def action():
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return action


def test_batcher_flushes_when_full(make_change, clock):
    written = []
    batcher = Batcher(written.append, max_rows=2, max_seconds=60, clock=clock)

    batcher.add(make_change("a"))
    batcher.add(make_change("b"))
    batcher.add(make_change("c"))

    assert titles(written) == [["a", "b"]]


def test_batcher_flushes_when_oldest_row_is_due(make_change, clock):
    written = []
    batcher = Batcher(written.append, max_rows=100, max_seconds=5, clock=clock)

    batcher.add(make_change("a"))
    clock.now = 5
    batcher.add(make_change("b"))

    assert titles(written) == [["a", "b"]]


def test_batch_age_counts_from_first_row_not_last_flush(make_change, clock):
    written = []
    batcher = Batcher(written.append, max_rows=100, max_seconds=5, clock=clock)

    clock.now = 100
    batcher.add(make_change())

    assert written == []


def test_flushing_an_empty_batch_writes_nothing(clock):
    written = []

    Batcher(written.append, max_rows=1, max_seconds=1, clock=clock).flush()

    assert written == []


def test_retry_waits_out_an_unreachable_server_indefinitely():
    outages = [OperationalError("connection refused")] * (MAX_ATTEMPTS * 3)

    assert retry(failing(*outages), "test", Shutdown()) == "ok"


def test_retry_recovers_from_a_brief_server_error():
    assert retry(failing(DatabaseError("too many parts")), "test", Shutdown()) == "ok"


def test_retry_treats_repeated_other_errors_as_permanent():
    errors = [TypeError("bad row")] * MAX_ATTEMPTS

    with pytest.raises(TypeError):
        retry(failing(*errors), "test", Shutdown())


def test_retry_gives_up_once_shutdown_is_requested():
    shutdown = Shutdown()
    shutdown.request()

    with pytest.raises(OperationalError):
        retry(failing(OperationalError("down")), "test", shutdown)


def test_writer_inserts_rows_in_column_order(make_change):
    client = FakeClient()
    changes = [make_change("a"), make_change("b")]

    ClickHouseWriter(client, Shutdown()).write(changes)

    assert client.inserts == [("recent_changes", [astuple(c) for c in changes], COLUMNS)]
    assert client.settings == {"deduplicate_blocks_in_dependent_materialized_views": 1}


def test_writer_drops_a_batch_that_keeps_failing_instead_of_stalling(make_change):
    client = FakeClient(*[TypeError("bad row")] * MAX_ATTEMPTS)
    writer = ClickHouseWriter(client, Shutdown())

    writer.write([make_change("poison")])
    writer.write([make_change("next")])

    assert client.attempts == MAX_ATTEMPTS + 1
    assert [rows[0][COLUMNS.index("title")] for _, rows, _ in client.inserts] == ["next"]
