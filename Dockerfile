# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Ask Finance — backend (FastAPI) image for Cloud Run / Artifact Registry.
#
# Build:
#   docker build -t ask-finance-api:local .
# Run locally:
#   docker run --rm -p 8080:8080 \
#     -e GOOGLE_CLOUD_PROJECT=your-project \
#     -e VERTEX_LOCATION=us-central1 \
#     -v "$PWD/authen:/secrets:ro" \
#     -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/service-account.json \
#     ask-finance-api:local
# ---------------------------------------------------------------------------

ARG PYTHON_VERSION=3.11

# -------- builder stage: install Python deps into an isolated prefix --------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

COPY requirements-backend.txt ./requirements-backend.txt
RUN pip install --prefix=/install -r requirements-backend.txt

# -------- runtime stage: minimal layer with code + data + deps --------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    ASK_FINANCE_DATA_DIR=/app/data \
    ASK_FINANCE_LOGS_DIR=/tmp/ask_finance_logs \
    PORT=8080

# Copy installed Python packages from the builder stage.
COPY --from=builder /install /usr/local

WORKDIR /app

# Application source + bundled mock data.
COPY src ./src
COPY data ./data

# Run as a non-root user (Cloud Run best practice).
RUN useradd --create-home --uid 1001 app \
    && mkdir -p /tmp/ask_finance_logs \
    && chown -R app:app /app /tmp/ask_finance_logs
USER app

EXPOSE 8080

# Cloud Run injects $PORT; bind to it so the container is portable.
CMD ["sh", "-c", "exec uvicorn ask_finance.api:app --host 0.0.0.0 --port ${PORT}"]
