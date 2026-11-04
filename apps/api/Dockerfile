# syntax=docker/dockerfile:1
# AnyGet API: Python 3.12 + ffmpeg + git + Deno (yt-dlp needs Deno for full YouTube support).
FROM denoland/deno:bin-2.9.8 AS deno
FROM ghcr.io/astral-sh/uv:0.11 AS uv

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=deno /deno /usr/local/bin/deno
COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY anyget ./anyget
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

RUN useradd --create-home --uid 1000 anyget \
    && mkdir -p /downloads /data && chown anyget:anyget /downloads /data
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# Starts as root, then drops to the "anyget" user with the host's PUID/PGID.
ENTRYPOINT ["docker-entrypoint.sh"]

ENV ANYGET_DOWNLOADS_DIR=/downloads \
    ANYGET_DATA_DIR=/data \
    ANYGET_HOST=0.0.0.0 \
    ANYGET_PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"]
CMD ["uvicorn", "anyget.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
