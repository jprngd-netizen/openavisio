FROM python:3.12-slim
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=$GIT_COMMIT
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml .
RUN uv sync --no-dev

COPY . .
RUN useradd -u 10001 -m app \
    && mkdir -p /data/documents \
    && chown -R app:app /app /data
USER app
EXPOSE 8000
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
