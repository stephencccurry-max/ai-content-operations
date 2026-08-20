FROM python:3.12-slim

WORKDIR /app

# Install uv from PyPI. ghcr.io/astral-sh/uv is often unreachable on
# personal networks that can still pull Docker Hub / PyPI.
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic/ alembic/
COPY app/ ./app/

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
