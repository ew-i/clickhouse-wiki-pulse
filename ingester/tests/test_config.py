import pytest
from pydantic import ValidationError

from wiki_pulse_ingester.config import Settings

ENV_VARS = [
    "CLICKHOUSE_HOST",
    "CLICKHOUSE_PORT",
    "CLICKHOUSE_USER",
    "CLICKHOUSE_PASSWORD",
    "WIKIMEDIA_STREAM_URL",
    "BATCH_MAX_ROWS",
    "BATCH_MAX_SECONDS",
    "CONTACT",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults():
    settings = Settings()

    assert settings.clickhouse_host == "localhost"
    assert settings.clickhouse_port == 8123
    assert str(settings.wikimedia_stream_url).endswith("/v2/stream/recentchange")
    assert (settings.batch_max_rows, settings.batch_max_seconds) == (5000, 5.0)


def test_env_overrides_are_converted_to_their_types(monkeypatch):
    monkeypatch.setenv("CLICKHOUSE_PORT", "9123")
    monkeypatch.setenv("BATCH_MAX_ROWS", "10")
    monkeypatch.setenv("BATCH_MAX_SECONDS", "0.5")

    settings = Settings()

    assert (settings.clickhouse_port, settings.batch_max_rows, settings.batch_max_seconds) == (
        9123,
        10,
        0.5,
    )


def test_empty_env_vars_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("CLICKHOUSE_PORT", "")
    monkeypatch.setenv("CONTACT", "")

    settings = Settings()

    assert (settings.clickhouse_port, settings.contact) == (8123, "unknown")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CLICKHOUSE_PORT", "70000"),
        ("BATCH_MAX_ROWS", "0"),
        ("BATCH_MAX_SECONDS", "soon"),
        ("WIKIMEDIA_STREAM_URL", "stream.wikimedia.org"),
    ],
)
def test_invalid_values_are_rejected(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError, match=name.lower()):
        Settings()


def test_password_is_hidden_from_logs(monkeypatch):
    monkeypatch.setenv("CLICKHOUSE_PASSWORD", "hunter2")

    settings = Settings()

    assert "hunter2" not in repr(settings)
    assert settings.clickhouse_password.get_secret_value() == "hunter2"


def test_user_agent_carries_contact(monkeypatch):
    monkeypatch.setenv("CONTACT", "ops@example.org")

    assert Settings().user_agent == "clickhouse-wiki-pulse/0.1 (ops@example.org)"
