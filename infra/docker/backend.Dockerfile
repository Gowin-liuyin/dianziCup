ARG UV_IMAGE=ghcr.io/astral-sh/uv@sha256:10902f58a1606787602f303954cea099626a4adb02acbac4c69920fe9d278f82
ARG PYTHON_IMAGE=python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE}
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/src ./src
COPY backend/migrations ./migrations
RUN uv sync --locked --no-dev && mkdir -p /var/lib/ai-intel/raw && chown -R 10001:10001 /app /var/lib/ai-intel
USER 10001:10001
CMD ["uvicorn", "ai_intel.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
