-- Compression per column: which codecs paid off?
SELECT
    name,
    type,
    compression_codec,
    formatReadableSize(data_compressed_bytes)   AS compressed,
    formatReadableSize(data_uncompressed_bytes) AS uncompressed,
    round(data_uncompressed_bytes / nullIf(data_compressed_bytes, 0), 1) AS ratio
FROM system.columns
WHERE database = 'wiki' AND table = 'recent_changes'
ORDER BY data_compressed_bytes DESC;

-- Whole-table size: raw events vs. the rollup.
SELECT
    table,
    sum(rows)                                    AS rows,
    count()                                      AS active_parts,
    formatReadableSize(sum(data_compressed_bytes))   AS on_disk,
    formatReadableSize(sum(data_uncompressed_bytes)) AS uncompressed,
    round(sum(data_uncompressed_bytes) / sum(data_compressed_bytes), 1) AS ratio
FROM system.parts
WHERE database = 'wiki' AND active
GROUP BY table;

-- How much does the primary index skip for a typical query?
-- Look at "Granules: X/Y" under PrimaryKey.
EXPLAIN indexes = 1
SELECT count()
FROM wiki.recent_changes
WHERE wiki = 'dewiki' AND type = 'edit' AND event_time >= now() - INTERVAL 10 MINUTE;
