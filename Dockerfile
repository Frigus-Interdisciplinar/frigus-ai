FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY data ./data
COPY assets ./assets

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app/src

EXPOSE 8000

CMD ["python", "-m", "frigus_ai.main", "api"]
