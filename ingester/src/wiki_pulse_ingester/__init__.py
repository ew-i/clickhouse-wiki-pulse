"""Stream Wikimedia recent changes into ClickHouse in batches.

ClickHouse writes a new part per INSERT, so inserting events one by one
would create thousands of tiny parts and overload background merges.
We buffer rows and flush every BATCH_MAX_ROWS rows or BATCH_MAX_SECONDS.
"""
