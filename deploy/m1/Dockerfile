FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_NO_CACHE=1
ARG INSTALL_NETWORK_CAPTURE=0
RUN if [ "$INSTALL_NETWORK_CAPTURE" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends libpcap0.8 && \
      rm -rf /var/lib/apt/lists/*; \
    fi
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --all-extras --no-install-project
COPY src/ ./src/
RUN uv sync --frozen --all-extras --no-editable
COPY tests/ ./tests/
COPY scripts/build_agent_bundle.py ./scripts/build_agent_bundle.py
COPY deploy/agent/ ./deploy/agent/
COPY docs/AGENT_INSTALLATION.md ./docs/AGENT_INSTALLATION.md
COPY migrations/ ./migrations/
COPY alembic.ini ./
CMD ["uv", "run", "--frozen", "pytest", "tests/e2e/test_m1_live.py", "-v"]
