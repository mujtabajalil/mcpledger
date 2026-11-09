# syntax=docker/dockerfile:1
# One image serves the API and the Angular dashboard. The same image runs
# migrations as a Cloud Run job (command: alembic upgrade head).

# ---- 1. build the Angular dashboard ---------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npx ng build --configuration production

# ---- 2. Python runtime ------------------------------------------------------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY server/requirements.txt server/requirements.txt
RUN pip install -r server/requirements.txt

# The server imports the CLI's detection rules so both always agree.
COPY cli/ cli/
RUN pip install ./cli

COPY server/ server/
COPY --from=web /web/dist/web/browser /app/static

ENV STATIC_DIR=/app/static \
    MCPLEDGER_ENV=production \
    SECURE_COOKIES=1 \
    AUTO_CREATE_TABLES=0 \
    PORT=8080 \
    WEB_CONCURRENCY=2
WORKDIR /app/server
USER app
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*' --no-server-header"]
