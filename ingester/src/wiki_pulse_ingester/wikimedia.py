import json
import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

import requests

from wiki_pulse_ingester.model import RecentChange

STREAM_TIMEOUT_SECONDS = (10, 60)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServerSentEvent:
    id: str | None
    data: str


def parse_server_sent_events(lines: Iterable[str]) -> Iterator[ServerSentEvent]:
    event_id, data = None, []
    for line in lines:
        if line == "":
            if data:
                yield ServerSentEvent(event_id, "\n".join(data))
            event_id, data = None, []
        elif line.startswith("id:"):
            event_id = line.removeprefix("id:").strip()
        elif line.startswith("data:"):
            data.append(line.removeprefix("data:").lstrip())


class WikimediaStream:
    def __init__(self, url: str, user_agent: str):
        self._url = url
        self._user_agent = user_agent
        self._last_event_id: str | None = None

    def payloads(self) -> Iterator[str]:
        with requests.get(
            self._url, headers=self._headers(), stream=True, timeout=STREAM_TIMEOUT_SECONDS
        ) as response:
            response.raise_for_status()
            response.encoding = "utf-8"
            for event in parse_server_sent_events(response.iter_lines(decode_unicode=True)):
                self._last_event_id = event.id or self._last_event_id
                yield event.data

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "text/event-stream", "User-Agent": self._user_agent}
        if self._last_event_id:
            headers["Last-Event-ID"] = self._last_event_id
        return headers


def is_canary(event: dict[str, Any]) -> bool:
    """Wikimedia injects synthetic health-check events into the stream."""
    return event.get("meta", {}).get("domain") == "canary"


def parse_changes(payloads: Iterable[str]) -> Iterator[RecentChange]:
    for payload in payloads:
        try:
            event = json.loads(payload)
            if is_canary(event):
                continue
            change = RecentChange.from_event(event)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            log.warning("skipping malformed event (%r): %.200s", exc, payload)
            continue
        yield change
