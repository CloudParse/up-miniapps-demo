# Production image of the mini-app API. Built by the CI (Kaniko) from this folder: .gitea/workflows/deploy-backend.yml.
# The listening port is miniapp.yaml `api.port`, passed as --build-arg API_PORT.
FROM ghcr.io/astral-sh/uv:0.13.9 AS uv

FROM python:3.14-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY configs ./configs

FROM python:3.14-slim
ARG API_PORT=8000
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build --chown=10001:10001 /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=${API_PORT}
USER 10001:10001
EXPOSE ${API_PORT}
CMD ["python", "-m", "app"]
