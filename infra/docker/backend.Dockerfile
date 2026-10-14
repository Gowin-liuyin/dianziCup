ARG UV_IMAGE
ARG PYTHON_IMAGE
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
COPY backend/alembic.ini ./alembic.ini
RUN uv sync --locked --no-dev && mkdir -p /var/lib/ai-intel/raw && chown -R 10001:10001 /app /var/lib/ai-intel
USER 10001:10001
CMD ["uvicorn", "ai_intel.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
