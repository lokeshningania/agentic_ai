
# ==========================================
# Base
# ==========================================
FROM python:3.12-slim AS base

ARG APP_ENV=production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NATIVE_TLS=true

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=secret,id=corporate_ca,target=/run/secrets/corporate-ca.pem,required=false \
    if [ "$APP_ENV" = "development" ]; then \
        test -s /run/secrets/corporate-ca.pem || \
            (echo "ERROR: Corporate CA certificate was not provided." && exit 1); \
        cp /run/secrets/corporate-ca.pem \
            /usr/local/share/ca-certificates/vmart-corporate-ca.crt; \
        update-ca-certificates; \
    fi \
    && PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
       pip install --no-cache-dir uv


# ==========================================
# Dependencies and application
# ==========================================
FROM base AS builder

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --locked --no-dev


# ==========================================
# Production runtime
# ==========================================
FROM python:3.12-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    APP_ENV=production \
    APP_PORT=8000

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src ./src

EXPOSE 8000

CMD ["uvicorn", "agentlab.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
