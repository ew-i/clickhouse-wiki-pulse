CH = docker compose exec -T clickhouse sh -c 'clickhouse-client -u "$$CLICKHOUSE_USER" --password "$$CLICKHOUSE_PASSWORD" -d wiki $(1)'

.PHONY: up down reset logs client stats test lint

up:
	docker compose up -d --build

down:
	docker compose down

reset:
	docker compose down -v

logs:
	docker compose logs -f ingester

client:
	docker compose exec clickhouse sh -c 'clickhouse-client -u "$$CLICKHOUSE_USER" --password "$$CLICKHOUSE_PASSWORD" -d wiki'

stats:
	$(call CH,--format PrettyCompactMonoBlock) < queries/inspect.sql

test:
	cd ingester && uv run --locked pytest -q --cov

lint:
	cd ingester && uv run --locked ruff check . && uv run --locked ruff format --check .
