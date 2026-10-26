CREATE DATABASE IF NOT EXISTS wiki;

-- Raw events, one row per change on any Wikimedia wiki.
--
-- ORDER BY (wiki, type, event_time): almost every query filters on a wiki
-- and a time range, so the sparse primary index can skip whole granules.
-- Low-cardinality columns come first so the sort groups similar values
-- together, which also helps compression.
CREATE TABLE IF NOT EXISTS wiki.recent_changes
(
    event_time  DateTime64(3, 'UTC')   CODEC(DoubleDelta, ZSTD(1)),
    wiki        LowCardinality(String),
    server_name LowCardinality(String),
    type        LowCardinality(String), -- edit | new | log | categorize
    namespace   Int16,
    title       String                 CODEC(ZSTD(3)),
    user        String                 CODEC(ZSTD(3)),
    is_bot      Bool,
    is_minor    Bool,
    length_old  UInt32                 CODEC(T64, ZSTD(1)),
    length_new  UInt32                 CODEC(T64, ZSTD(1)),
    rev_id      UInt64                 CODEC(Delta, ZSTD(1)),
    comment     String                 CODEC(ZSTD(3))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (wiki, type, event_time)
TTL toDateTime(event_time) + INTERVAL 30 DAY
SETTINGS ttl_only_drop_parts = 1, non_replicated_deduplication_window = 100;

-- Per-minute rollup. Dashboards read this instead of scanning raw rows.
-- uniq() can't be summed across minutes, so we store its intermediate
-- state and finish it with uniqMerge() at query time.
CREATE TABLE IF NOT EXISTS wiki.edits_per_minute
(
    minute      DateTime('UTC'),
    wiki        LowCardinality(String),
    is_bot      Bool,
    edits       SimpleAggregateFunction(sum, UInt64),
    bytes_added SimpleAggregateFunction(sum, Int64),
    editors     AggregateFunction(uniq, String)
)
ENGINE = AggregatingMergeTree
ORDER BY (wiki, is_bot, minute)
SETTINGS non_replicated_deduplication_window = 100;

-- Fires on every insert into recent_changes and aggregates just that block.
CREATE MATERIALIZED VIEW IF NOT EXISTS wiki.edits_per_minute_mv
TO wiki.edits_per_minute
AS
SELECT
    toStartOfMinute(event_time)                      AS minute,
    wiki,
    is_bot,
    count()                                          AS edits,
    sum(toInt64(length_new) - toInt64(length_old))   AS bytes_added,
    uniqState(user)                                  AS editors
FROM wiki.recent_changes
WHERE type IN ('edit', 'new')
GROUP BY minute, wiki, is_bot;
