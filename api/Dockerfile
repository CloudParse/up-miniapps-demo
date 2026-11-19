# Production image of the mini-app API. Built by the CI (Kaniko) from this folder: .gitea/workflows/deploy-backend.yml.
# The listening port is miniapp.yaml `api.port` (1024 or more), passed as --build-arg API_PORT.
# Base images are pinned by tag AND digest: update both together, deliberately.
FROM ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d AS uv

FROM python:3.14.10-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY configs ./configs

FROM python:3.14.10-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f
ARG API_PORT=8000
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
# /app belongs to root and is read-only for the app user: a compromised API cannot rewrite its own code.
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=${API_PORT}
USER 10001:10001
EXPOSE ${API_PORT}
# No HEALTHCHECK: the platform probes `api.healthPath` through Kubernetes (readiness and liveness), which a Docker
# HEALTHCHECK instruction does not feed.
CMD ["python", "-m", "app"]
