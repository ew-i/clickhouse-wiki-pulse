import logging
import time
from collections.abc import Callable
from dataclasses import astuple
from typing import TypeVar

import clickhouse_connect
from clickhouse_connect.driver.client import Client
from clickhouse_connect.driver.exceptions import OperationalError

from wiki_pulse_ingester.config import Settings
from wiki_pulse_ingester.model import COLUMNS, RecentChange
from wiki_pulse_ingester.shutdown import Shutdown

DATABASE = "wiki"
TABLE = "recent_changes"
# A retried insert must not be counted twice by the rollup's materialized view.
INSERT_SETTINGS = {"deduplicate_blocks_in_dependent_materialized_views": 1}
RETRY_DELAY_SECONDS = 2.0
MAX_ATTEMPTS = 3

log = logging.getLogger(__name__)

T = TypeVar("T")


def retry(action: Callable[[], T], description: str, shutdown: Shutdown) -> T:
    attempt = 0
    while True:
        attempt += 1
        try:
            return action()
        except Exception as exc:
            if shutdown.requested or not _worth_retrying(exc, attempt):
                raise
            log.warning("%s failed (%s), retrying", description, exc)
            shutdown.pause(RETRY_DELAY_SECONDS)


def _worth_retrying(exc: Exception, attempt: int) -> bool:
    """An unreachable server is waited out; any other error is permanent after a few tries."""
    return isinstance(exc, OperationalError) or attempt < MAX_ATTEMPTS


def connect(settings: Settings, shutdown: Shutdown) -> Client:
    return retry(
        lambda: clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password.get_secret_value(),
            database=DATABASE,
        ),
        "connecting to ClickHouse",
        shutdown,
    )


class ClickHouseWriter:
    def __init__(self, client: Client, shutdown: Shutdown):
        self._client = client
        self._shutdown = shutdown

    def write(self, changes: list[RecentChange]) -> None:
        """Insert a batch. A batch that cannot be inserted is logged and dropped, so one
        bad row cannot stall ingestion."""
        rows = [astuple(change) for change in changes]
        try:
            retry(
                lambda: self._client.insert(
                    TABLE, rows, column_names=COLUMNS, settings=INSERT_SETTINGS
                ),
                f"insert of {len(rows)} rows",
                self._shutdown,
            )
        except Exception:
            log.exception("dropping %d rows that could not be inserted", len(rows))
            return
        log.info("inserted %d rows", len(rows))


class Batcher:
    def __init__(
        self,
        write: Callable[[list[RecentChange]], None],
        max_rows: int,
        max_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._write = write
        self._max_rows = max_rows
        self._max_seconds = max_seconds
        self._clock = clock
        self._batch: list[RecentChange] = []
        self._started_at = 0.0

    def add(self, change: RecentChange) -> None:
        if not self._batch:
            self._started_at = self._clock()
        self._batch.append(change)
        if self._is_full() or self._is_due():
            self.flush()

    def flush(self) -> None:
        if self._batch:
            self._write(self._batch)
            self._batch = []

    def _is_full(self) -> bool:
        return len(self._batch) >= self._max_rows

    def _is_due(self) -> bool:
        return self._clock() - self._started_at >= self._max_seconds
