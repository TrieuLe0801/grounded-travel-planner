# syntax=docker/dockerfile:1.7

ARG UV_VERSION=0.13.1
ARG PYTHON_VERSION=3.10

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM python:${PYTHON_VERSION}-slim-bookworm AS base

COPY --from=uv /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable


FROM base AS test

COPY tests ./tests
COPY .codex/hooks/format_python.py ./.codex/hooks/format_python.py
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable
RUN uv run --no-sync pytest


FROM base AS runtime

RUN groupadd --gid 10001 app \
    && useradd --create-home --uid 10001 --gid app app

ENV HOME=/home/app

USER app

EXPOSE 8501

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=2).read()"]

CMD ["streamlit", "run", "src/grounded_travel_planner/ui/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
