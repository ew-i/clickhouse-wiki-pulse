# clickhouse-wiki-pulse

Real-time analytics on every edit made to Wikipedia and its sister projects,
built on ClickHouse.

A small Python service consumes the public
[Wikimedia EventStreams](https://stream.wikimedia.org/?doc) feed (roughly
30–60 events per second across all wikis), batches the events into ClickHouse,
and a materialized view keeps per-minute rollups up to date. A Grafana
dashboard reads from those rollups.

## Quick start

Requires Docker.

```bash
make up                # or: docker compose up -d --build
```

To change the default passwords or the contact sent to Wikimedia, set
`CLICKHOUSE_PASSWORD`, `GRAFANA_ADMIN_PASSWORD` or `CONTACT` in a `.env` file
first.

- Dashboard: http://localhost:3000 (anonymous read access; admin/admin to edit)
- ClickHouse SQL console: http://localhost:8123/play (user `wiki`, password `changeme` unless set in `.env`)
- Ingester logs: `make logs`
- Storage and index stats: `make stats`

## Architecture

```
stream.wikimedia.org ──SSE──▶ ingester (Python)
                                 │  batches of ≤5000 rows / ≤5 s
                                 ▼
                       wiki.recent_changes        (MergeTree, raw events, 30-day TTL)
                                 │  materialized view, runs on every insert
                                 ▼
                       wiki.edits_per_minute      (AggregatingMergeTree)
                                 │
                                 ▼
                              Grafana
```

## Data source and license

Event data comes from the
[Wikimedia EventStreams](https://wikitech.wikimedia.org/wiki/Event_Platform/EventStreams_HTTP_Service)
service. Wikipedia content is available under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The ingester
sends a descriptive `User-Agent` header, as Wikimedia's
[User-Agent policy](https://foundation.wikimedia.org/wiki/Special:MyLanguage/Policy:User-Agent_policy) asks.
Set `CONTACT` in `.env` to your own URL or email address.

The code in this repository is MIT licensed.
