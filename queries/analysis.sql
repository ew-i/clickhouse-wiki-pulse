-- Example analytical queries. Run them with `make client` and paste,
-- or open http://localhost:8123/play.

-- 1. Edits per hour by wiki, served from the rollup (reads a few thousand rows).
SELECT
    toStartOfHour(minute) AS hour,
    wiki,
    sum(edits)            AS edits,
    uniqMerge(editors)    AS editors
FROM wiki.edits_per_minute
WHERE minute >= now() - INTERVAL 1 DAY
GROUP BY hour, wiki
ORDER BY hour DESC, edits DESC
LIMIT 50;

-- 2. The same question answered from raw events, for comparison.
--    Compare "Elapsed" and "Processed rows" with query 1.
SELECT
    toStartOfHour(event_time) AS hour,
    wiki,
    count()                   AS edits,
    uniq(user)                AS editors
FROM wiki.recent_changes
WHERE event_time >= now() - INTERVAL 1 DAY AND type IN ('edit', 'new')
GROUP BY hour, wiki
ORDER BY hour DESC, edits DESC
LIMIT 50;

-- 3. Share of bot edits per wiki (only wikis with real traffic).
SELECT
    wiki,
    sum(edits)                                   AS edits,
    round(100 * sumIf(edits, is_bot) / edits, 1) AS bot_pct
FROM wiki.edits_per_minute
GROUP BY wiki
HAVING edits > 500
ORDER BY bot_pct DESC
LIMIT 20;

-- 4. Edit wars: articles with many edits from few people in the last hour.
SELECT
    wiki,
    title,
    count()       AS edits,
    uniq(user)    AS editors,
    edits / editors AS edits_per_editor
FROM wiki.recent_changes
WHERE event_time >= now() - INTERVAL 1 HOUR
  AND type = 'edit' AND namespace = 0 AND NOT is_bot
GROUP BY wiki, title
HAVING editors BETWEEN 2 AND 4 AND edits >= 6
ORDER BY edits_per_editor DESC
LIMIT 20;

-- 5. Largest single additions and removals on English Wikipedia today.
SELECT
    event_time,
    title,
    user,
    toInt64(length_new) - toInt64(length_old) AS byte_delta,
    comment
FROM wiki.recent_changes
WHERE wiki = 'enwiki' AND event_time >= today() AND type = 'edit'
ORDER BY abs(byte_delta) DESC
LIMIT 20;

-- 6. Edits by hour of day (UTC): when is Wikipedia awake?
SELECT
    toHour(minute) AS hour_utc,
    sum(edits)     AS edits,
    bar(edits, 0, max(edits) OVER (), 40) AS chart
FROM wiki.edits_per_minute
WHERE NOT is_bot
GROUP BY hour_utc
ORDER BY hour_utc;
