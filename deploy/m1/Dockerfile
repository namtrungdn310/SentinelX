FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_NO_CACHE=1
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --frozen --all-extras --no-editable
COPY tests/ ./tests/
COPY migrations/ ./migrations/
COPY alembic.ini ./
CMD ["uv", "run", "--frozen", "pytest", "tests/e2e/test_m1_live.py", "-v"]
