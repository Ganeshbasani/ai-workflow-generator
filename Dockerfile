# syntax=docker/dockerfile:1.7
# Multi-stage, reproducible build. Runtime deps only in the final image.

FROM python:3.12.10-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY requirements.txt pyproject.toml README.md LICENSE ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --upgrade "pip==25.0.1" \
    && /opt/venv/bin/python -m pip install -r requirements.txt


FROM node:22-alpine AS web-build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ARG VITE_POSTHOG_KEY=
ARG VITE_POSTHOG_HOST=https://us.i.posthog.com
ENV VITE_POSTHOG_KEY=${VITE_POSTHOG_KEY} \
    VITE_POSTHOG_HOST=${VITE_POSTHOG_HOST}
RUN npm run build


FROM python:3.12.10-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DATABASE_PATH=/data/workflows.db

# Non-root runtime user with a writable, mountable data directory.
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data \
    && chown -R app:app /data

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app pyproject.toml README.md LICENSE requirements.txt ./
COPY --chown=app:app api.py workflow.py ./
COPY --chown=app:app src ./src
COPY --chown=app:app fonts ./fonts
COPY --from=web-build --chown=app:app /web/dist ./web/dist

USER app:app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"

# Match the readiness/liveness probes and let in-flight requests drain on SIGTERM.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "10"]
