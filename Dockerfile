# Base images can be pinned to ones already on the host: --build-arg PYTHON_IMAGE=... --build-arg NODE_IMAGE=...
ARG NODE_IMAGE=node:22-alpine
ARG PYTHON_IMAGE=python:3.12-slim

# ---- 1. build the single-page app (Node is only needed here, never at runtime) ----------------
FROM ${NODE_IMAGE} AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build && npm test

# ---- 2. runtime: API and Worker share this image -------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    NS_WEB_DIR=/app/web
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/nsapp ./nsapp
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/scripts ./scripts
COPY --from=web /web/dist ./web

RUN groupadd --gid 10001 nsapp \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin nsapp \
    && mkdir -p /data \
    && chown -R 10001:10001 /app /data
USER 10001:10001
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/healthz', timeout=3)"
CMD ["uvicorn", "nsapp.api.app:app", "--host", "0.0.0.0", "--port", "8090"]

# ---- 3. test image: `docker build --target test .` runs the backend suite --------------------------
FROM runtime AS test
USER root
COPY backend/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY backend/tests ./tests
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "tests"]
