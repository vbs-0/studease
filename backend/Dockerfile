# Build context is the repository root:  docker build -f backend/Dockerfile -t studease-api .
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN useradd --system --uid 10001 studease
WORKDIR /app/backend
COPY --from=build /app/backend/.venv .venv
COPY backend/app app
COPY database ../database
ENV PATH="/app/backend/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER studease
EXPOSE 8110
HEALTHCHECK CMD python -c "import urllib.request as u;u.urlopen('http://127.0.0.1:8110/api/v1/healthz')" || exit 1
# Configure with environment variables (DATABASE_URL, JWT secret, ...); see docs/deploy.md. Run migrations with:
#   docker run --rm --env-file .env IMAGE alembic -c ../database/alembic.ini upgrade head
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8110", "--proxy-headers"]
