import logging
import signal

import requests
from pydantic import ValidationError

from wiki_pulse_ingester.clickhouse import RETRY_DELAY_SECONDS, Batcher, ClickHouseWriter, connect
from wiki_pulse_ingester.config import Settings
from wiki_pulse_ingester.shutdown import Shutdown
from wiki_pulse_ingester.wikimedia import WikimediaStream, parse_changes

log = logging.getLogger(__name__)


def run(stream: WikimediaStream, batcher: Batcher, shutdown: Shutdown) -> None:
    """Pump changes into the batcher until shutdown. Whatever is buffered is flushed on the
    way out, even if the loop dies on an unexpected error."""
    try:
        while not shutdown.requested:
            try:
                for change in parse_changes(stream.payloads()):
                    batcher.add(change)
                    if shutdown.requested:
                        break
            except requests.RequestException as exc:
                log.warning("stream interrupted (%s), reconnecting", exc)
                batcher.flush()
                shutdown.pause(RETRY_DELAY_SECONDS)
    finally:
        batcher.flush()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        settings = Settings()
    except ValidationError as exc:
        raise SystemExit(f"invalid configuration: {exc}") from None

    # Signals only raise a flag; the loops notice it and wind down, so a
    # batch is never interrupted halfway through an insert.
    shutdown = Shutdown()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, shutdown.request)

    client = connect(settings, shutdown)
    try:
        writer = ClickHouseWriter(client, shutdown)
        batcher = Batcher(writer.write, settings.batch_max_rows, settings.batch_max_seconds)
        stream = WikimediaStream(str(settings.wikimedia_stream_url), settings.user_agent)
        run(stream, batcher, shutdown)
    finally:
        client.close()
    log.info("shut down cleanly")


if __name__ == "__main__":
    main()
