import json

import pytest
import requests

from wiki_pulse_ingester import wikimedia
from wiki_pulse_ingester.model import RecentChange
from wiki_pulse_ingester.wikimedia import (
    ServerSentEvent,
    WikimediaStream,
    parse_changes,
    parse_server_sent_events,
)

URL = "https://stream.example/recentchange"


class FakeResponse:
    def __init__(self, lines, status_error=None):
        self._lines = lines
        self._status_error = status_error
        self.encoding = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        if self._status_error:
            raise self._status_error

    def iter_lines(self, decode_unicode):
        assert decode_unicode and self.encoding == "utf-8"
        return iter(self._lines)


@pytest.fixture
def requests_get(monkeypatch):
    calls, responses = [], []

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return responses.pop(0)

    monkeypatch.setattr(wikimedia.requests, "get", fake_get)
    fake_get.calls, fake_get.responses = calls, responses
    return fake_get


def test_sse_lines_are_grouped_into_events():
    lines = ["id: 1", "data: {", "data: }", "", ":heartbeat", "", "data: x", ""]

    assert list(parse_server_sent_events(lines)) == [
        ServerSentEvent("1", "{\n}"),
        ServerSentEvent(None, "x"),
    ]


def test_canaries_and_malformed_payloads_are_skipped(edit_event):
    canary = {**edit_event, "meta": {**edit_event["meta"], "domain": "canary"}}
    payloads = ["not json", json.dumps({"no": "meta"}), json.dumps(canary), json.dumps(edit_event)]

    assert list(parse_changes(payloads)) == [RecentChange.from_event(edit_event)]


@pytest.mark.parametrize(
    "payload",
    ["null", "[1, 2]", "42", '{"meta": null}', '{"meta": {"dt": 5}}', '{"meta": {"dt": "x"}}'],
)
def test_payloads_of_unexpected_shape_are_skipped_not_fatal(payload):
    assert list(parse_changes([payload])) == []


def test_stream_requests_sse_with_user_agent(requests_get):
    requests_get.responses.append(FakeResponse(["data: a", ""]))

    assert list(WikimediaStream(URL, "agent/1.0").payloads()) == ["a"]
    call = requests_get.calls[0]
    assert call["url"] == URL and call["stream"] is True
    assert call["headers"] == {"Accept": "text/event-stream", "User-Agent": "agent/1.0"}


def test_reconnect_resumes_after_last_event_with_an_id(requests_get):
    requests_get.responses += [
        FakeResponse(["id: 7", "data: a", "", "data: b", ""]),
        FakeResponse([]),
    ]
    stream = WikimediaStream(URL, "agent/1.0")

    list(stream.payloads())
    list(stream.payloads())

    assert "Last-Event-ID" not in requests_get.calls[0]["headers"]
    assert requests_get.calls[1]["headers"]["Last-Event-ID"] == "7"


def test_http_errors_propagate(requests_get):
    requests_get.responses.append(FakeResponse([], status_error=requests.HTTPError("503")))

    with pytest.raises(requests.HTTPError):
        list(WikimediaStream(URL, "agent/1.0").payloads())
