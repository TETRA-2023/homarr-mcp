FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Create non-root user
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies only (reproducible from lockfile)
RUN uv sync --frozen --no-install-project

# Copy application source
COPY src/ src/

# Install the project itself (non-editable) so uv run doesn't need to write at runtime
RUN uv sync --frozen --no-editable

ENV UV_CACHE_DIR=/tmp/uv-cache

USER appuser

ENTRYPOINT ["/app/.venv/bin/python", "src/server.py"]
