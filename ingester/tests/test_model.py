import re
from datetime import UTC, datetime
from pathlib import Path

from wiki_pulse_ingester.model import COLUMNS, RecentChange

SCHEMA = Path(__file__).parents[2] / "schema" / "01_tables.sql"


def test_event_maps_to_change(edit_event):
    change = RecentChange.from_event(edit_event)

    assert change.event_time == datetime(2026, 10, 26, 11, tzinfo=UTC)
    assert (change.wiki, change.type, change.title, change.user) == (
        "dewiki",
        "edit",
        "ClickHouse",
        "Alice",
    )
    assert (change.is_bot, change.is_minor) == (False, True)
    assert (change.length_old, change.length_new, change.rev_id) == (100, 150, 2)


def test_missing_optional_fields_get_defaults():
    change = RecentChange.from_event({"meta": {"dt": "2026-10-26T11:00:00Z"}, "length": None})

    assert (change.wiki, change.length_new, change.rev_id, change.is_bot) == ("", 0, 0, False)


def test_null_fields_get_defaults_so_the_insert_cannot_fail_on_them():
    change = RecentChange.from_event(
        {"meta": {"dt": "2026-10-26T11:00:00Z"}, "title": None, "namespace": None, "user": None}
    )

    assert (change.title, change.namespace, change.user) == ("", 0, "")


def test_columns_match_the_table_schema():
    table = re.search(
        r"CREATE TABLE IF NOT EXISTS wiki\.recent_changes\s*\((.*?)\)\s*ENGINE",
        SCHEMA.read_text(),
        re.DOTALL,
    )
    schema_columns = re.findall(r"^\s*(\w+)\s+\w", table.group(1), re.MULTILINE)

    assert schema_columns == COLUMNS
