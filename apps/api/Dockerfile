# syntax=docker/dockerfile:1
# AnyGet API: Python 3.12 + ffmpeg + git + Deno (yt-dlp needs Deno for full YouTube support).
# Base images are pinned by digest (multi-arch index); Dependabot proposes updates.
FROM denoland/deno:bin-2.9.8@sha256:b507583d3c68ba69f3ed2ce5969ae5b8b70f43421c781279c7aea06435263543 AS deno
FROM ghcr.io/astral-sh/uv:0.11@sha256:77280f2f771df71f90786c314fe1bbc1e023feac652969bbf139c280babf2eb7 AS uv

FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_NO_CACHE=1 \
    PATH="/opt/venv/bin:$PATH"

# OCR is always on with English, Hindi and Arabic (OCRmyPDF + Tesseract), and poppler
# makes PDF thumbnails. WITH_OCR=1 adds more languages (~150 MB):
# `docker compose build --build-arg WITH_OCR=1 api` (the test image always has them).
ARG WITH_OCR=0
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git megatools ca-certificates \
         poppler-utils ocrmypdf tesseract-ocr \
         tesseract-ocr-eng tesseract-ocr-hin tesseract-ocr-ara \
    && if [ "$WITH_OCR" = "1" ]; then \
         apt-get install -y --no-install-recommends tesseract-ocr-jpn \
           tesseract-ocr-chi-sim tesseract-ocr-fra tesseract-ocr-deu tesseract-ocr-spa \
           tesseract-ocr-rus; \
       fi \
    && rm -rf /var/lib/apt/lists/*
COPY --from=deno /deno /usr/local/bin/deno

WORKDIR /app
COPY pyproject.toml uv.lock ./
# uv is mounted only for these steps, so its ~50 MB binary is not in the image, and
# UV_NO_CACHE keeps its download cache (~200 MB of wheels) out of the layer. No cache
# mounts: Railway's builder refuses them without service-specific ids.
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv uv sync --frozen --no-dev --no-install-project
COPY anyget ./anyget
COPY README.md ./
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv uv sync --frozen --no-dev

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
# --timeout-graceful-shutdown: live-update streams (SSE) never finish on their own, so
# without it a stop waits for every open browser tab (Docker kills it after 10 s) and
# the tabs keep talking to the old process instead of reconnecting.
CMD ["uvicorn", "anyget.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", \
     "--timeout-graceful-shutdown", "3"]

# ---- test image: production image + dev tools + tests (used by `make live`) ----
FROM base AS test
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv uv sync --frozen
COPY tests ./tests
ENV PYTEST_ADDOPTS="-p no:cacheprovider"
HEALTHCHECK NONE
CMD ["pytest", "-m", "live", "tests/live", "-v", "-rA"]

# ---- production image (default target) ----
FROM base AS runtime
