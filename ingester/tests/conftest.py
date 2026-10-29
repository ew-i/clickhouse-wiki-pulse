import json

import pytest

from wiki_pulse_ingester.model import RecentChange


@pytest.fixture
def edit_event():
    return {
        "meta": {"dt": "2026-10-26T11:00:00Z", "domain": "de.wikipedia.org"},
        "wiki": "dewiki",
        "server_name": "de.wikipedia.org",
        "type": "edit",
        "namespace": 0,
        "title": "ClickHouse",
        "user": "Alice",
        "bot": False,
        "minor": True,
        "length": {"old": 100, "new": 150},
        "revision": {"old": 1, "new": 2},
        "comment": "typo",
    }


@pytest.fixture
def make_change(edit_event):
    def make(title="ClickHouse"):
        return RecentChange.from_event({**edit_event, "title": title})

    return make


@pytest.fixture
def make_payload(edit_event):
    def make(title="ClickHouse"):
        return json.dumps({**edit_event, "title": title})

    return make


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return FakeClock()
