ARG UV_VERSION=0.13.5

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM python:3.11-slim@sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377 AS base

FROM base AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

COPY --from=uv /uv /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
# Dependencies first so source edits don't invalidate this layer.
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM base

RUN python -m pip uninstall -y pip \
    && useradd --uid 1000 --gid root --no-create-home ingester

# Same path as the builder: the venv's interpreter symlinks and scripts are absolute.
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

USER ingester

ENTRYPOINT ["wiki-pulse-ingester"]
